from __future__ import annotations

import hashlib
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
    px = origin[0] + scale * (x - 0.55 * y)
    py = origin[1] + scale * (0.32 * y - z)
    return round(px), round(py)


def _plane_polygon(h: int, k: int, l: int) -> list[tuple[float, float, float]]:
    intercepts = [
        1.0 / h if h else math.inf,
        1.0 / k if k else math.inf,
        1.0 / l if l else math.inf,
    ]
    points: list[tuple[float, float, float]] = []
    axes = [(intercepts[0], 0.0, 0.0), (0.0, intercepts[1], 0.0), (0.0, 0.0, intercepts[2])]
    for point in axes:
        if all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in point):
            points.append(point)
    if len(points) >= 3:
        return points
    return [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def generate_miller_card(output_dir: Path, h: int, k: int, l: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(f"{h}{k}{l}".encode()).hexdigest()[:10]
    path = output_dir / f"miller_{h}{k}{l}_{digest}.png"
    if path.is_file():
        return path

    width, height = 1100, 720
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = _font(44, True)
    subtitle_font = _font(25, True)
    body_font = _font(23)
    small_font = _font(19)

    draw.rounded_rectangle((28, 28, width - 28, height - 28), radius=34, fill="#ffffff", outline="#2563eb", width=4)
    draw.text((62, 54), f"Plano de Miller ({h}{k}{l})", fill="#1e3a8a", font=title_font)
    draw.text((64, 112), "Interceptos y orientación en una celda cúbica", fill="#334155", font=subtitle_font)

    origin = (350, 500)
    scale = 300
    vertices = {
        "000": (0, 0, 0), "100": (1, 0, 0), "010": (0, 1, 0), "001": (0, 0, 1),
        "110": (1, 1, 0), "101": (1, 0, 1), "011": (0, 1, 1), "111": (1, 1, 1),
    }
    edges = [
        ("000", "100"), ("000", "010"), ("000", "001"), ("100", "110"), ("100", "101"),
        ("010", "110"), ("010", "011"), ("001", "101"), ("001", "011"), ("110", "111"),
        ("101", "111"), ("011", "111"),
    ]
    for start, end in edges:
        draw.line((*_project(vertices[start], origin, scale), *_project(vertices[end], origin, scale)), fill="#64748b", width=4)

    plane = _plane_polygon(h, k, l)
    projected = [_project(point, origin, scale) for point in plane]
    draw.polygon(projected, fill=(251, 146, 60, 135), outline="#ea580c")
    draw.line(projected + [projected[0]], fill="#c2410c", width=5)
    for label, point in zip(("a/h", "b/k", "c/l"), plane):
        px, py = _project(point, origin, scale)
        draw.ellipse((px - 8, py - 8, px + 8, py + 8), fill="#dc2626")
        draw.text((px + 10, py - 22), label, fill="#991b1b", font=small_font)

    axes = [((0, 0, 0), (1.16, 0, 0), "a"), ((0, 0, 0), (0, 1.16, 0), "b"), ((0, 0, 0), (0, 0, 1.16), "c")]
    for start, end, label in axes:
        draw.line((*_project(start, origin, scale), *_project(end, origin, scale)), fill="#111827", width=5)
        draw.text(_project(end, origin, scale), label, fill="#111827", font=subtitle_font)

    box_x = 650
    draw.rounded_rectangle((box_x, 165, 1038, 610), radius=24, fill="#eff6ff", outline="#bfdbfe", width=3)
    lines = [
        f"Para ({h}{k}{l}):",
        f"• h={h}: corta el eje a en 1/{h}",
        f"• k={k}: corta el eje b en 1/{k}",
        f"• l={l}: corta el eje c en 1/{l}",
        "",
        "Procedimiento:",
        "1. Identifica interceptos.",
        "2. Toma recíprocos.",
        "3. Reduce a enteros mínimos.",
    ]
    y = 190
    for line in lines:
        font = subtitle_font if line.endswith(":") else body_font
        for wrapped in _wrap(draw, line, font, 335):
            draw.text((box_x + 28, y), wrapped, fill="#0f172a", font=font)
            y += 34
        if not line:
            y += 10

    draw.text((64, 652), "Tarjeta generada automáticamente desde la escritura manuscrita en la tablet.", fill="#475569", font=small_font)
    image.save(path, "PNG")
    return path
