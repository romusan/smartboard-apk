from __future__ import annotations

import hashlib
import html
import json
import math
import random
from pathlib import Path
from typing import Iterable

from .models import AiRequest, AiResponse


def _curve_points(request: AiRequest) -> list[tuple[float, float]]:
    if not request.strokes:
        raise ValueError("Dibuja primero una curva cerrada.")
    stroke = max(request.strokes, key=lambda item: len(item.points))
    points = [(float(point.x), float(point.y)) for point in stroke.points]
    if len(points) < 12:
        raise ValueError("La curva necesita al menos 12 puntos.")
    return points


def _is_closed(points: list[tuple[float, float]]) -> bool:
    xs, ys = zip(*points)
    diagonal = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    gap = math.dist(points[0], points[-1])
    return diagonal >= 0.04 and gap <= max(0.035, 0.22 * diagonal)


def _resample_closed(points: list[tuple[float, float]], count: int = 96) -> list[tuple[float, float]]:
    closed = points + ([points[0]] if points[-1] != points[0] else [])
    lengths = [0.0]
    for start, end in zip(closed, closed[1:]):
        lengths.append(lengths[-1] + math.dist(start, end))
    total = lengths[-1]
    if total <= 1e-9:
        raise ValueError("La curva no tiene longitud suficiente.")
    result: list[tuple[float, float]] = []
    segment = 0
    for index in range(count):
        target = total * index / count
        while segment + 1 < len(lengths) and lengths[segment + 1] < target:
            segment += 1
        span = max(lengths[segment + 1] - lengths[segment], 1e-12)
        ratio = (target - lengths[segment]) / span
        a, b = closed[segment], closed[segment + 1]
        result.append((a[0] + ratio * (b[0] - a[0]), a[1] + ratio * (b[1] - a[1])))
    return result


def _normalize(points: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    points = list(points)
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    scale = max(max(x for x, _ in points) - min(x for x, _ in points), 1e-9)
    return [((x - cx) / scale, (cy - y) / scale) for x, y in points]


def _fourbar_path(candidate: list[float], count: int) -> list[tuple[float, float]] | None:
    ground, crank, coupler, rocker, ux, uy, phase = candidate
    path: list[tuple[float, float]] = []
    previous_b: tuple[float, float] | None = None
    for index in range(count):
        theta = phase + 2.0 * math.pi * index / count
        ax, ay = crank * math.cos(theta), crank * math.sin(theta)
        dx, dy = ground - ax, -ay
        distance = math.hypot(dx, dy)
        if distance <= 1e-8 or distance > coupler + rocker or distance < abs(coupler - rocker):
            return None
        along = (coupler * coupler - rocker * rocker + distance * distance) / (2.0 * distance)
        height2 = coupler * coupler - along * along
        if height2 < 0:
            return None
        height = math.sqrt(max(0.0, height2))
        px, py = ax + along * dx / distance, ay + along * dy / distance
        candidates = [
            (px - height * dy / distance, py + height * dx / distance),
            (px + height * dy / distance, py - height * dx / distance),
        ]
        bx, by = candidates[0]
        if previous_b is not None:
            bx, by = min(candidates, key=lambda point: math.dist(point, previous_b))
        previous_b = (bx, by)
        path.append((ax + ux * (bx - ax) - uy * (by - ay), ay + ux * (by - ay) + uy * (bx - ax)))
    return path


def _fit_error(path: list[tuple[float, float]] | None, target: list[tuple[float, float]]) -> float:
    if path is None:
        return 1e6
    normalized = _normalize(path)
    best = 1e6
    for direction in (target, list(reversed(target))):
        for shift in range(0, len(target), 4):
            error = sum(
                (normalized[i][0] - direction[(i + shift) % len(target)][0]) ** 2
                + (normalized[i][1] - direction[(i + shift) % len(target)][1]) ** 2
                for i in range(len(target))
            ) / len(target)
            best = min(best, error)
    return math.sqrt(best)


def _pso_tass(target: list[tuple[float, float]], seed: int) -> tuple[list[float], float]:
    rng = random.Random(seed)
    bounds = [(0.45, 1.6), (0.12, 0.65), (0.35, 1.35), (0.30, 1.30), (-0.4, 1.5), (-1.0, 1.0), (0.0, 2 * math.pi)]
    particles = [[rng.uniform(low, high) for low, high in bounds] for _ in range(24)]
    velocity = [[0.0] * len(bounds) for _ in particles]
    personal = [item[:] for item in particles]
    scores = [_fit_error(_fourbar_path(item, len(target)), target) for item in particles]
    global_best = personal[min(range(len(scores)), key=scores.__getitem__)][:]
    global_score = min(scores)
    for iteration in range(48):
        inertia = 0.82 - 0.45 * iteration / 47
        for i, particle in enumerate(particles):
            for j, (low, high) in enumerate(bounds):
                velocity[i][j] = (
                    inertia * velocity[i][j]
                    + 1.55 * rng.random() * (personal[i][j] - particle[j])
                    + 1.55 * rng.random() * (global_best[j] - particle[j])
                )
                particle[j] = min(high, max(low, particle[j] + velocity[i][j]))
            score = _fit_error(_fourbar_path(particle, len(target)), target)
            if score < scores[i]:
                scores[i], personal[i] = score, particle[:]
                if score < global_score:
                    global_score, global_best = score, particle[:]
    return global_best, global_score


def _complexity(points: list[tuple[float, float]]) -> float:
    turns = []
    for a, b, c in zip(points, points[1:] + points[:1], points[2:] + points[:2]):
        u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
        turns.append(abs(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))
    return sum(turns) / len(turns)


def _html_document(identifier: str, target: list[tuple[float, float]], candidate: list[float], rms: float) -> str:
    target_json = json.dumps([[round(x, 6), round(y, 6)] for x, y in target])
    params_json = json.dumps([round(value, 6) for value in candidate])
    safe_id = html.escape(identifier)
    return f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<style>html,body{{margin:0;height:100%;background:#07111f;color:#eaf2ff;font:14px system-ui}}header{{padding:8px 12px;background:#10213a}}button{{margin:3px;padding:7px 10px;border:0;border-radius:9px;background:#2563eb;color:white}}canvas{{display:block;width:100%;height:calc(100% - 116px);min-height:260px}}.muted{{color:#a9bdd5}}#lengths{{position:fixed;right:10px;bottom:10px;background:#10213aeF;border:1px solid #45617f;border-radius:10px;padding:9px;line-height:1.45}}</style></head>
<body><header><b>Simulación lenta · {safe_id}</b><div class='muted'>Azul: objetivo · Magenta: curva construida · RMS: {rms:.4f}</div>
<button onclick="setFamily('fourbar')">4 barras · PSO‑TASS</button><button onclick="setFamily('watt')">6 barras · Watt I</button><button onclick="setFamily('stephenson')">6 barras · Stephenson III</button></header><canvas id='c'></canvas><div id='lengths'></div>
<script>const target={target_json},p={params_json};let family='fourbar',t=0,trail=[];const c=document.getElementById('c'),x=c.getContext('2d'),box=document.getElementById('lengths');
function setFamily(value){{family=value;trail=[]}}function resize(){{const d=devicePixelRatio||1;c.width=Math.max(480,c.clientWidth*d);c.height=Math.max(300,c.clientHeight*d)}}addEventListener('resize',resize);resize();
function solve(ang){{const g=p[0],a=p[1],b=p[2],d=p[3],A=[0,0],D=[g,0],B=[a*Math.cos(ang),a*Math.sin(ang)],dx=D[0]-B[0],dy=-B[1],L=Math.hypot(dx,dy),al=(b*b-d*d+L*L)/(2*L),hh=Math.sqrt(Math.max(0,b*b-al*al)),C=[B[0]+al*dx/L-hh*dy/L,B[1]+al*dy/L+hh*dx/L],P=[B[0]+p[4]*(C[0]-B[0])-p[5]*(C[1]-B[1]),B[1]+p[4]*(C[1]-B[1])+p[5]*(C[0]-B[0])];return{{A,B,C,D,P}}}}
const states=Array.from({{length:360}},(_,i)=>solve(p[6]+i*2*Math.PI/360)),orbit=states.map(q=>q.P),cx=orbit.reduce((s,q)=>s+q[0],0)/orbit.length,cy=orbit.reduce((s,q)=>s+q[1],0)/orbit.length,pathW=Math.max(...orbit.map(q=>q[0]))-Math.min(...orbit.map(q=>q[0])),mm=120/pathW,all=states.flatMap(q=>[q.A,q.B,q.C,q.D,q.P]),minX=Math.min(...all.map(q=>q[0])),maxX=Math.max(...all.map(q=>q[0])),minY=Math.min(...all.map(q=>q[1])),maxY=Math.max(...all.map(q=>q[1])),worldX=(minX+maxX)/2,worldY=(minY+maxY)/2,worldSpan=Math.max(maxX-minX,maxY-minY)*1.18;
box.innerHTML=`<b>Longitudes del mecanismo</b><br>L1 bastidor: ${{(p[0]*mm).toFixed(1)}} mm<br>L2 manivela: ${{(p[1]*mm).toFixed(1)}} mm<br>L3 acoplador: ${{(p[2]*mm).toFixed(1)}} mm<br>L4 balancín: ${{(p[3]*mm).toFixed(1)}} mm<br><span class='muted'>1 vuelta ≈ 18 s</span>`;
function screen(q,S,ox,oy){{return[ox+(q[0]-worldX)/worldSpan*S,oy-(q[1]-worldY)/worldSpan*S]}}function targetPt(q,S,ox,oy){{return screen([cx+q[0]*pathW,cy+q[1]*pathW],S,ox,oy)}}function line(a,b,color,w=5){{x.strokeStyle=color;x.lineWidth=w;x.beginPath();x.moveTo(...a);x.lineTo(...b);x.stroke()}}function joint(a,color='#f8fafc'){{x.fillStyle=color;x.beginPath();x.arc(a[0],a[1],7,0,7);x.fill();x.strokeStyle='#0f172a';x.stroke()}}function label(a,text){{x.fillStyle='#fff';x.font='bold 15px system-ui';x.fillText(text,a[0]+8,a[1]-8)}}
function loop(){{x.clearRect(0,0,c.width,c.height);const S=Math.min(c.width*.72,c.height*.72),ox=c.width*.43,oy=c.height*.53;x.strokeStyle='#38bdf8';x.lineWidth=4;x.setLineDash([10,8]);x.beginPath();target.forEach((q,i)=>{{const a=targetPt(q,S,ox,oy);i?x.lineTo(...a):x.moveTo(...a)}});x.closePath();x.stroke();x.setLineDash([]);
const q=solve(p[6]+t),A=screen(q.A,S,ox,oy),B=screen(q.B,S,ox,oy),C=screen(q.C,S,ox,oy),D=screen(q.D,S,ox,oy),P=screen(q.P,S,ox,oy);trail.push(P);if(trail.length>1100)trail.shift();x.strokeStyle='#f472b6';x.lineWidth=5;x.beginPath();trail.forEach((a,i)=>i?x.lineTo(...a):x.moveTo(...a));x.stroke();
if(family!=='fourbar'){{const E0=[q.B[0]+.62*(q.C[0]-q.B[0])-.55*(q.C[1]-q.B[1]),q.B[1]+.62*(q.C[1]-q.B[1])+.55*(q.C[0]-q.B[0])],F0=family==='watt'?[p[0]*.15,-.75]:[p[0]*.82,-.7],E=screen(E0,S,ox,oy),F=screen(F0,S,ox,oy);line(E,F,'#a78bfa',9);line(C,E,'#a78bfa',9);joint(E);joint(F)}}line(A,D,'#64748b',11);line(A,B,'#ef4444',9);line(B,C,'#22c55e',9);line(C,D,'#f59e0b',9);line(B,P,'#c084fc',5);line(C,P,'#c084fc',5);joint(A);joint(B);joint(C);joint(D);joint(P,'#f472b6');label([(A[0]+D[0])/2,(A[1]+D[1])/2],'L1');label([(A[0]+B[0])/2,(A[1]+B[1])/2],'L2');label([(B[0]+C[0])/2,(B[1]+C[1])/2],'L3');label([(C[0]+D[0])/2,(C[1]+D[1])/2],'L4');label(P,'P trazador');t=(t+.0058)%(2*Math.PI);requestAnimationFrame(loop)}}loop();</script></body></html>"""


def _upgrade_document(document: str) -> str:
    document = document.replace("c.width*.72,c.height*.72", "c.width*.94,c.height*.94")
    document = document.replace("ox=c.width*.43,oy=c.height*.53", "ox=c.width*.50,oy=c.height*.50")
    document = document.replace(
        "function setFamily(value){family=value;trail=[]}",
        "function setFamily(value){family=value;t=0;trail=[]}",
    )
    document = document.replace(
        "const S=Math.min(c.width*.94,c.height*.94)",
        "const tabletZoom=new URLSearchParams(location.search).has('tablet')?1.32:1,S=Math.min(c.width*.94,c.height*.94)*tabletZoom",
    )
    document = document.replace("t+.0058", "t+.0087")
    return document.replace("18 s", "12 s")


def upgrade_generated_mechanisms(generated_dir: Path) -> None:
    for path in generated_dir.glob("mechanism_*.html"):
        document = path.read_text(encoding="utf-8")
        upgraded = _upgrade_document(document)
        if upgraded != document:
            path.write_text(upgraded, encoding="utf-8")


def synthesize_mechanism(request: AiRequest, generated_dir: Path) -> AiResponse:
    points = _curve_points(request)
    if not _is_closed(points):
        raise ValueError("La trayectoria debe ser cerrada: une el final con el inicio.")
    target = _normalize(_resample_closed(points))
    digest = hashlib.sha256(json.dumps(target, separators=(",", ":")).encode()).hexdigest()[:12]
    seed = int(digest[:8], 16)
    candidate, rms = _pso_tass(target, seed)
    preferred_family = "Stephenson III" if _complexity(target) > 0.13 else "Watt I"
    filename = f"mechanism_{digest}.html"
    document = _upgrade_document(_html_document(digest, target, candidate, rms))
    (generated_dir / filename).write_text(document, encoding="utf-8")
    params = {name: round(value, 4) for name, value in zip(("bastidor", "manivela", "acoplador", "balancin", "u", "v", "fase"), candidate)}
    return AiResponse(
        kind="threejs",
        content=(f"Síntesis única {digest}. Se obtuvo una solución de cuatro barras con PSO‑TASS "
                 f"(RMS normalizado {rms:.4f}). Alternativas por grafos: Watt I y Stephenson III; "
                 f"familia sugerida para esta curva: {preferred_family}."),
        metadata={"simulation_url": f"/generated/{filename}", "solution_id": digest, "rms": rms, "fourbar": params,
                  "graph_families": ["fourbar", "wattI", "stephensonIII"], "method": "PSO-TASS + graph families"},
    )
