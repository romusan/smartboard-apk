from __future__ import annotations

import hashlib
import json
import math
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
    px = origin[0] + scale * (x - 0.58 * y)
    py = origin[1] + scale * (0.34 * y - z)
    return round(px), round(py)


def _sphere(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, fill: str, outline: str, label: str) -> None:
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline=outline, width=3)
    draw.ellipse((x - radius // 2, y - radius // 2, x - radius // 8, y - radius // 8), fill=(255, 255, 255, 120))
    draw.line((x - radius, y, x + radius, y), fill="#475569", width=2)
    draw.text((x + radius + 3, y - 8), label, fill="#475569", font=_font(14, True))


def generate_fcc_card(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(b"fcc-plotly-inspired-v3").hexdigest()[:10]
    path = output_dir / f"fcc_structure_{digest}.png"
    if path.is_file():
        return path

    width, height = 1100, 720
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = _font(42, True)
    subtitle_font = _font(25, True)
    body_font = _font(22)
    small_font = _font(18)

    draw.rounded_rectangle((28, 28, width - 28, height - 28), radius=34, fill="#ffffff", outline="#059669", width=4)
    draw.text((62, 54), "Estructura FCC", fill="#065f46", font=title_font)
    draw.text((64, 112), "Cúbica centrada en las caras: corte por celda + deslizamiento", fill="#334155", font=subtitle_font)

    origin = (380, 520)
    scale = 310
    vertices = {
        "000": (0, 0, 0), "100": (1, 0, 0), "010": (0, 1, 0), "001": (0, 0, 1),
        "110": (1, 1, 0), "101": (1, 0, 1), "011": (0, 1, 1), "111": (1, 1, 1),
    }
    edges = [
        ("000", "100"), ("000", "010"), ("000", "001"), ("100", "110"), ("100", "101"),
        ("010", "110"), ("010", "011"), ("001", "101"), ("001", "011"), ("110", "111"),
        ("101", "111"), ("011", "111"),
    ]
    face_centers_back = [(0.5, 0.5, 1), (0, 0.5, 0.5), (0.5, 1, 0.5)]
    face_centers_front = [(0.5, 0.5, 0), (1, 0.5, 0.5), (0.5, 0, 0.5)]
    far_corners = ["010", "001", "011", "111"]
    near_corners = ["000", "100", "110", "101"]
    corner_radius = 38
    face_radius = 46

    plane111 = [_project(point, origin, scale) for point in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    draw.polygon(plane111, fill=(16, 185, 129, 60), outline="#059669")
    draw.line(plane111 + [plane111[0]], fill="#059669", width=4)

    for name in far_corners:
        _sphere(draw, _project(vertices[name], origin, scale), corner_radius, "#bbf7d0", "#059669", "1/8")
    for point in face_centers_back:
        _sphere(draw, _project(point, origin, scale), face_radius, "#67e8f9", "#0891b2", "1/2")
    for start, end in edges:
        draw.line((*_project(vertices[start], origin, scale), *_project(vertices[end], origin, scale)), fill="#334155", width=4)
    for point in face_centers_front:
        _sphere(draw, _project(point, origin, scale), face_radius, "#67e8f9", "#0891b2", "1/2")
    for name in near_corners:
        _sphere(draw, _project(vertices[name], origin, scale), corner_radius, "#bbf7d0", "#059669", "1/8")

    for start, end in (((1, 0, 0), (0, 1, 0)), ((1, 0, 0), (0, 0, 1)), ((0, 1, 0), (0, 0, 1))):
        p0 = _project(start, origin, scale)
        p1 = _project(end, origin, scale)
        draw.line((*p0, *p1), fill="#dc2626", width=5)
    draw.text((230, 250), "{111}<110>", fill="#991b1b", font=_font(18, True))

    box_x = 670
    draw.rounded_rectangle((box_x, 170, 1038, 605), radius=24, fill="#ecfdf5", outline="#6ee7b7", width=3)
    lines = [
        "FCC = Face Centered Cubic",
        "• 8 esquinas + 6 centros de cara.",
        "• Z = 8×1/8 + 6×1/2 = 4",
        "• Coordinación = 12",
        "",
        "Geometría:",
        "a = 2R sqrt(2)  <=>  a sqrt(2) = 4R",
        "APF = 0.74",
        "",
        "Deslizamiento:",
        "12 sistemas: {111}<110>",
    ]
    y = 190
    for line in lines:
        font = subtitle_font if line.endswith(":") or line.startswith("FCC") else body_font
        draw.text((box_x + 28, y), line, fill="#111827", font=font)
        y += 34 if line else 10

    draw.text((64, 630), "Se resalta un plano compacto {111} y direcciones compactas <110>.", fill="#475569", font=small_font)
    draw.text((64, 656), "Tarjeta generada automáticamente al escribir “fcc” en la tablet.", fill="#475569", font=small_font)
    image.save(path, "PNG")
    return path


def generate_fcc_3d_html(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(b"fcc-plotly-3d-v1").hexdigest()[:10]
    path = output_dir / f"fcc_3d_{digest}.html"
    if path.is_file():
        return path

    radius = 1.0
    cell = 2 * radius * math.sqrt(2)
    corners = [
        [0, 0, 0], [cell, 0, 0], [0, cell, 0], [cell, cell, 0],
        [0, 0, cell], [cell, 0, cell], [0, cell, cell], [cell, cell, cell],
    ]
    faces = [
        [cell / 2, cell / 2, 0], [cell / 2, cell / 2, cell],
        [cell / 2, 0, cell / 2], [cell / 2, cell, cell / 2],
        [0, cell / 2, cell / 2], [cell, cell / 2, cell / 2],
    ]
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>FCC 3D interactivo</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ margin:0; font-family: system-ui, sans-serif; background:#f8fafc; }}
    #plot {{ width:100vw; height:100vh; }}
    .note {{ position:fixed; left:16px; bottom:16px; max-width:500px; padding:12px 14px; background:rgba(255,255,255,.88); border:1px solid #cbd5e1; border-radius:12px; }}
  </style>
</head>
<body>
  <div id="plot"></div>
  <div class="note"><b>FCC — Características</b><br>
  Z=4 · Coordinación=12 · APF=0.74<br>
  a = 2R√2 · Sistemas de deslizamiento: 12 ({111}&lt;110&gt;).<br>
  Botones: esferas completas, corte por celda o plano de deslizamiento.</div>
  <script>
    const R = {radius};
    const a = {cell};
    const corners = {json.dumps(corners)};
    const faces = {json.dumps(faces)};
    const atoms = corners.concat(faces);
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
    const full = atoms.map((c,i)=>sphere(c,false,i<8?'#22c55e':'#06b6d4',0.32));
    const cut = atoms.map((c,i)=>sphere(c,true,i<8?'#22c55e':'#06b6d4',0.90));
    const plane111 = {{type:'surface', x:[[0,a,0],[0,a,0]], y:[[0,0,a],[0,0,a]], z:[[a,0,0],[a,0,0]], opacity:.28, showscale:false, colorscale:[[0,'#10b981'],[1,'#10b981']], name:'Plano (111)'}};
    const dirs = {{type:'scatter3d', mode:'lines+text', x:[a,0,null,a,0,null,0,0], y:[0,a,null,0,0,null,a,0], z:[0,0,null,0,a,null,0,a], line:{{width:10,color:'#dc2626'}}, text:['','','','<110>','','','<110>',''], textposition:'top center', name:'<110>'}};
    const data = cube.concat(full, cut, [plane111, dirs]);
    const cutStart = cube.length + full.length;
    const fullVisible = data.map((_,i)=> i < cutStart || i >= cutStart + cut.length);
    const cutVisible = data.map((_,i)=> i < cube.length || (i >= cutStart && i < cutStart + cut.length));
    const slipVisible = data.map((_,i)=> i < cube.length || (i >= cutStart && i < cutStart + cut.length) || i >= cutStart + cut.length);
    data.forEach((trace,i)=>trace.visible=fullVisible[i]);
    Plotly.newPlot('plot', data, {{
      title:'FCC interactivo: corte por cubo y sistema {111}<110>',
      scene:{{aspectmode:'data', xaxis:{{title:'x'}}, yaxis:{{title:'y'}}, zaxis:{{title:'z'}}}},
      margin:{{l:0,r:0,t:55,b:0}},
      updatemenus:[{{type:'buttons', direction:'left', x:.02, y:1.08, buttons:[
        {{label:'Sin corte', method:'update', args:[{{visible:fullVisible}}]}},
        {{label:'Corte del cubo', method:'update', args:[{{visible:cutVisible}}]}},
        {{label:'{111}<110>', method:'update', args:[{{visible:slipVisible}}]}}
      ]}}]
    }});
  </script>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")
    return path
