from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _project(point: tuple[float, float, float], origin: tuple[int, int], scale: float) -> tuple[int, int]:
    x, y, z = point
    return round(origin[0] + scale * (x - 0.58 * y)), round(origin[1] + scale * (0.34 * y - z))


def _sphere(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, fill: str, outline: str, label: str) -> None:
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline=outline, width=3)
    draw.ellipse((x - radius // 2, y - radius // 2, x - radius // 8, y - radius // 8), fill=(255, 255, 255, 130))
    draw.line((x - radius, y, x + radius, y), fill="#475569", width=2)
    draw.text((x + radius + 3, y - 8), label, fill="#475569", font=_font(14, True))


def generate_sc_card(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(b"sc-plotly-inspired-v2").hexdigest()[:10]
    path = output_dir / f"sc_structure_{digest}.png"
    if path.is_file():
        return path

    width, height = 1100, 720
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = _font(42, True)
    subtitle_font = _font(25, True)
    body_font = _font(22)
    small_font = _font(18)

    draw.rounded_rectangle((28, 28, width - 28, height - 28), radius=34, fill="#ffffff", outline="#2563eb", width=4)
    draw.text((62, 54), "Estructura SC", fill="#1e3a8a", font=title_font)
    draw.text((64, 112), "Cubica simple: atomos solo en los vertices de la celda", fill="#334155", font=subtitle_font)

    origin = (395, 525)
    scale = 315
    vertices = {
        "000": (0, 0, 0), "100": (1, 0, 0), "010": (0, 1, 0), "001": (0, 0, 1),
        "110": (1, 1, 0), "101": (1, 0, 1), "011": (0, 1, 1), "111": (1, 1, 1),
    }
    edges = [
        ("000", "100"), ("000", "010"), ("000", "001"), ("100", "110"), ("100", "101"),
        ("010", "110"), ("010", "011"), ("001", "101"), ("001", "011"), ("110", "111"),
        ("101", "111"), ("011", "111"),
    ]
    far_corners = ["010", "001", "011", "111"]
    near_corners = ["000", "100", "110", "101"]

    atom_radius = 48
    for name in far_corners:
        _sphere(draw, _project(vertices[name], origin, scale), atom_radius, "#bfdbfe", "#2563eb", "1/8")

    plane100 = [_project(point, origin, scale) for point in ((0.5, 0, 0), (0.5, 1, 0), (0.5, 1, 1), (0.5, 0, 1))]
    draw.polygon(plane100, fill=(59, 130, 246, 55), outline="#2563eb")
    draw.line(plane100 + [plane100[0]], fill="#2563eb", width=3)

    for start, end in edges:
        draw.line((*_project(vertices[start], origin, scale), *_project(vertices[end], origin, scale)), fill="#334155", width=4)
    for name in near_corners:
        _sphere(draw, _project(vertices[name], origin, scale), atom_radius, "#bfdbfe", "#2563eb", "1/8")

    p0 = _project((0, 0, 0), origin, scale)
    p1 = _project((1, 0, 0), origin, scale)
    draw.line((*p0, *p1), fill="#dc2626", width=6)
    draw.text((560, p1[1] - 36), "<100>", fill="#991b1b", font=_font(18, True))
    draw.text((315, 275), "{100}", fill="#1d4ed8", font=_font(18, True))

    box_x = 670
    draw.rounded_rectangle((box_x, 170, 1038, 605), radius=24, fill="#eff6ff", outline="#93c5fd", width=3)
    lines = [
        "SC = Simple Cubic",
        "• 8 atomos en vertices.",
        "• Cada vertice aporta 1/8.",
        "• Z = 8 x 1/8 = 1",
        "",
        "Geometria:",
        "a = 2R",
        "APF = pi/6 = 0.52",
        "",
        "Coordinacion: 6 vecinos.",
        "Planos: familia {100}.",
        "Direccion compacta: <100>.",
    ]
    y = 190
    for line in lines:
        font = subtitle_font if line.endswith(":") or line.startswith("SC") else body_font
        draw.text((box_x + 28, y), line, fill="#111827", font=font)
        y += 34 if line else 10

    draw.text((64, 630), "SC tiene bajo empaquetamiento; ejemplo clasico: polonio alfa.", fill="#475569", font=small_font)
    draw.text((64, 656), "Tarjeta generada automaticamente al escribir \"sc\" o \"cubica simple\" en la tablet.", fill="#475569", font=small_font)
    image.save(path, "PNG")
    return path


def generate_sc_3d_html(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(b"sc-plotly-3d-v1").hexdigest()[:10]
    path = output_dir / f"sc_3d_{digest}.html"
    if path.is_file():
        return path

    radius = 1.0
    cell = 2.0 * radius
    corners = [
        [0, 0, 0], [cell, 0, 0], [0, cell, 0], [cell, cell, 0],
        [0, 0, cell], [cell, 0, cell], [0, cell, cell], [cell, cell, cell],
    ]
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>SC 3D interactivo</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ margin:0; font-family: system-ui, sans-serif; background:#f8fafc; }}
    #plot {{ width:100vw; height:100vh; }}
    .note {{ position:fixed; left:16px; bottom:16px; max-width:470px; padding:12px 14px; background:rgba(255,255,255,.88); border:1px solid #cbd5e1; border-radius:12px; }}
  </style>
</head>
<body>
  <div id="plot"></div>
  <div class="note"><b>SC — Caracteristicas</b><br>
  Z=1 · Coordinacion=6 · APF=pi/6≈0.52<br>
  Contacto por arista: a = 2R<br>
  Plano representativo: (100). Direccion compacta: &lt;100&gt;.</div>
  <script>
    const R = {radius};
    const a = {cell};
    const corners = {json.dumps(corners)};
    function sphere(c, cut, color, opacity) {{
      const nu=48, nv=28, x=[], y=[], z=[];
      for (let i=0;i<nv;i++) {{
        const v=Math.PI*i/(nv-1), rowX=[], rowY=[], rowZ=[];
        for (let j=0;j<nu;j++) {{
          const u=2*Math.PI*j/(nu-1);
          let px=c[0]+R*Math.cos(u)*Math.sin(v);
          let py=c[1]+R*Math.sin(u)*Math.sin(v);
          let pz=c[2]+R*Math.cos(v);
          if (cut && (px<0||px>a||py<0||py>a||pz<0||pz>a)) {{ px=py=pz=NaN; }}
          rowX.push(px); rowY.push(py); rowZ.push(pz);
        }}
        x.push(rowX); y.push(rowY); z.push(rowZ);
      }}
      return {{type:'surface', x, y, z, showscale:false, opacity, colorscale:[[0,color],[1,color]], hoverinfo:'skip'}};
    }}
    const edges = [
      [[0,0,0],[a,0,0]], [[0,0,0],[0,a,0]], [[0,0,0],[0,0,a]], [[a,0,0],[a,a,0]],
      [[a,0,0],[a,0,a]], [[0,a,0],[a,a,0]], [[0,a,0],[0,a,a]], [[0,0,a],[a,0,a]],
      [[0,0,a],[0,a,a]], [[a,a,0],[a,a,a]], [[a,0,a],[a,a,a]], [[0,a,a],[a,a,a]]
    ];
    function edge(e) {{ return {{type:'scatter3d', mode:'lines', x:[e[0][0],e[1][0]], y:[e[0][1],e[1][1]], z:[e[0][2],e[1][2]], line:{{width:6,color:'#334155'}}, showlegend:false}}; }}
    const cube = edges.map(edge);
    const full = corners.map(c=>sphere(c,false,'#3b82f6',0.35));
    const cut = corners.map(c=>sphere(c,true,'#3b82f6',0.95));
    const plane100 = {{type:'surface', x:[[a/2,a/2],[a/2,a/2]], y:[[0,a],[0,a]], z:[[0,0],[a,a]], opacity:.25, showscale:false, colorscale:[[0,'#2563eb'],[1,'#2563eb']], name:'Plano (100)'}};
    const dir100 = {{type:'scatter3d', mode:'lines+text', x:[0,a], y:[0,0], z:[0,0], line:{{width:12,color:'#dc2626'}}, text:['','<100>'], textposition:'top right', name:'<100>'}};
    const centers = {{type:'scatter3d', mode:'markers', x:corners.map(p=>p[0]), y:corners.map(p=>p[1]), z:corners.map(p=>p[2]), marker:{{size:4,color:'#111827'}}, name:'Centros atomicos'}};
    const data = cube.concat(full, cut, [plane100, dir100, centers]);
    const cutStart = cube.length + full.length;
    const fullVisible = data.map((_,i)=> i < cutStart || i >= cutStart + cut.length);
    const cutVisible = data.map((_,i)=> i < cube.length || (i >= cutStart && i < cutStart + cut.length) || i >= cutStart + cut.length);
    data.forEach((trace,i)=>trace.visible=fullVisible[i]);
    Plotly.newPlot('plot', data, {{
      title:'SC interactivo: esferas completas ↔ corte por cubo',
      scene:{{aspectmode:'data', xaxis:{{title:'x'}}, yaxis:{{title:'y'}}, zaxis:{{title:'z'}}}},
      margin:{{l:0,r:0,t:55,b:0}},
      updatemenus:[{{type:'buttons', direction:'left', x:.02, y:1.08, buttons:[
        {{label:'Sin corte', method:'update', args:[{{visible:fullVisible}}]}},
        {{label:'Corte del cubo', method:'update', args:[{{visible:cutVisible}}]}}
      ]}}]
    }});
  </script>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")
    return path
