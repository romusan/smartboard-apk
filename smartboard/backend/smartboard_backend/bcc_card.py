from __future__ import annotations

import hashlib
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


def _sphere(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, fill: str, outline: str, cut: str | None = None) -> None:
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline=outline, width=3)
    draw.ellipse((x - radius // 2, y - radius // 2, x - radius // 8, y - radius // 8), fill=(255, 255, 255, 120))
    if cut:
        draw.line((x - radius, y, x + radius, y), fill="#475569", width=2)
        draw.text((x + radius + 3, y - 8), cut, fill="#475569", font=_font(14, True))


def generate_bcc_card(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(b"bcc-body-centered-cubic-equal-radius-v2").hexdigest()[:10]
    path = output_dir / f"bcc_structure_{digest}.png"
    if path.is_file():
        return path

    width, height = 1100, 720
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = _font(42, True)
    subtitle_font = _font(25, True)
    body_font = _font(23)
    small_font = _font(18)

    draw.rounded_rectangle((28, 28, width - 28, height - 28), radius=34, fill="#ffffff", outline="#7c3aed", width=4)
    draw.text((62, 54), "Estructura BCC", fill="#4c1d95", font=title_font)
    draw.text((64, 112), "Cúbica centrada en el cuerpo: átomos recortados por la celda", fill="#334155", font=subtitle_font)

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

    far_corners = ["010", "001", "011", "111"]
    near_corners = ["000", "100", "110", "101"]
    atom_radius = 48
    for name in far_corners:
        _sphere(draw, _project(vertices[name], origin, scale), atom_radius, "#ddd6fe", "#7c3aed", "1/8")
    _sphere(draw, _project((0.5, 0.5, 0.5), origin, scale), atom_radius, "#fbbf24", "#b45309", "1")
    for start, end in edges:
        draw.line((*_project(vertices[start], origin, scale), *_project(vertices[end], origin, scale)), fill="#334155", width=4)
    for name in near_corners:
        _sphere(draw, _project(vertices[name], origin, scale), atom_radius, "#ddd6fe", "#7c3aed", "1/8")

    box_x = 670
    draw.rounded_rectangle((box_x, 170, 1038, 605), radius=24, fill="#f5f3ff", outline="#c4b5fd", width=3)
    lines = [
        "BCC = Body Centered Cubic",
        "• 8 átomos en esquinas.",
        "• Cada esquina aporta 1/8.",
        "• 1 átomo completo en el centro.",
        "",
        "Átomos por celda:",
        "8 × 1/8 + 1 = 2",
        "",
        "Relación geométrica:",
        "4r = √3 a  →  r = √3a/4",
        "",
        "Coordinación:",
        "cada átomo toca 8 vecinos."
    ]
    y = 196
    for line in lines:
        font = subtitle_font if line.endswith(":") or line.startswith("BCC") else body_font
        draw.text((box_x + 28, y), line, fill="#111827", font=font)
        y += 36 if line else 12

    draw.text((64, 640), "Las esferas de esquina aparecen cortadas por los límites de la caja cristalina.", fill="#475569", font=small_font)
    draw.text((64, 666), "Tarjeta generada automáticamente al escribir “bcc” en la tablet.", fill="#475569", font=small_font)
    image.save(path, "PNG")
    return path
