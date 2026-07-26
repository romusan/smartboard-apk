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


def _base_card(title: str, subtitle: str, accent: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (1100, 720), "#f8fafc")
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((28, 28, 1072, 692), radius=34, fill="#ffffff", outline=accent, width=4)
    draw.text((62, 54), title, fill=accent, font=_font(42, True))
    draw.text((64, 112), subtitle, fill="#334155", font=_font(25, True))
    return image, draw


def _electron(draw: ImageDraw.ImageDraw, center: tuple[int, int], angle: float, radius_x: int, radius_y: int, color: str) -> None:
    x = center[0] + radius_x * math.cos(angle)
    y = center[1] + radius_y * math.sin(angle)
    draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=color, outline="#0f172a", width=2)
    draw.text((x + 13, y - 12), "e⁻", fill="#0f172a", font=_font(16, True))


def generate_atom_structure_card(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"atom_structure_{hashlib.sha1(b'atom-structure-v1').hexdigest()[:10]}.png"
    if path.is_file():
        return path

    image, draw = _base_card(
        "Estructura del átomo",
        "Núcleo positivo y electrones distribuidos en niveles de energía",
        "#2563eb",
    )
    center = (390, 392)
    for rx, ry, color in [(245, 90, "#bfdbfe"), (185, 145, "#dbeafe"), (120, 205, "#eff6ff")]:
        draw.ellipse((center[0] - rx, center[1] - ry, center[0] + rx, center[1] + ry), outline="#64748b", width=3)
    draw.ellipse((center[0] - 58, center[1] - 58, center[0] + 58, center[1] + 58), fill="#fecaca", outline="#dc2626", width=4)
    draw.text((center[0] - 38, center[1] - 28), "p⁺", fill="#991b1b", font=_font(28, True))
    draw.text((center[0] + 6, center[1] + 4), "n⁰", fill="#334155", font=_font(26, True))
    for angle, rx, ry in [(0.6, 245, 90), (2.7, 185, 145), (4.7, 120, 205), (5.7, 185, 145)]:
        _electron(draw, center, angle, rx, ry, "#38bdf8")

    draw.rounded_rectangle((675, 170, 1038, 600), radius=24, fill="#eff6ff", outline="#bfdbfe", width=3)
    y = 198
    lines = [
        ("Modelo útil para materiales", True),
        ("• Núcleo: protones y neutrones.", False),
        ("• Electrones: ocupan estados discretos.", False),
        ("• Los electrones de valencia controlan", False),
        ("  enlace, conductividad y reactividad.", False),
        ("", False),
        ("Idea clave", True),
        ("La estructura electrónica explica", False),
        ("por qué los materiales se enlazan y", False),
        ("forman sólidos metálicos, iónicos,", False),
        ("covalentes o secundarios.", False),
    ]
    for text, bold in lines:
        if text:
            draw.text((705, y), text, fill="#0f172a", font=_font(22, bold))
        y += 34 if text else 14
    draw.text((64, 652), "Tarjeta generada desde el submenú Crear esquema → Estructura del átomo.", fill="#475569", font=_font(18))
    image.save(path, "PNG")
    return path


def generate_quantum_numbers_card(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"quantum_numbers_{hashlib.sha1(b'quantum-numbers-v2').hexdigest()[:10]}.png"
    if path.is_file():
        return path

    image, draw = _base_card(
        "Números cuánticos",
        "Niveles de energía y descripción del estado electrónico",
        "#7c3aed",
    )
    x0, y0 = 95, 580
    levels = [(1, ["1s"], 210), (2, ["2s", "2p"], 315), (3, ["3s", "3p", "3d"], 430), (4, ["4s", "4p", "4d", "4f"], 545)]
    for n, subs, y in levels:
        draw.line((x0, y, 560, y), fill="#64748b", width=3)
        draw.text((64, y - 18), f"n={n}", fill="#1e293b", font=_font(22, True))
        for i, sub in enumerate(subs):
            x = 155 + i * 95
            draw.rounded_rectangle((x, y - 24, x + 62, y + 24), radius=12, fill="#ede9fe", outline="#7c3aed", width=2)
            draw.text((x + 13, y - 16), sub, fill="#4c1d95", font=_font(20, True))
    draw.text((120, 165), "Energía ↑", fill="#334155", font=_font(20, True))
    draw.line((112, 560, 112, 205), fill="#334155", width=4)
    draw.polygon([(112, 182), (100, 208), (124, 208)], fill="#334155")

    draw.rounded_rectangle((635, 165, 1038, 615), radius=24, fill="#f5f3ff", outline="#c4b5fd", width=3)
    lines = [
        ("n: número principal", "nivel/capa de energía"),
        ("l: azimutal", "subnivel: s, p, d, f"),
        ("mₗ: magnético", "orientación del orbital"),
        ("mₛ: spin", "+1/2 o -1/2"),
        ("Capacidad", "2n² electrones por nivel"),
        ("Aplicación", "valencia → enlace y propiedades"),
    ]
    y = 195
    for title, body in lines:
        draw.text((668, y), title, fill="#111827", font=_font(22, True))
        draw.text((668, y + 27), body, fill="#334155", font=_font(20))
        y += 68
    draw.text((64, 652), "Tarjeta generada desde el submenú Crear esquema → Números cuánticos.", fill="#475569", font=_font(18))
    image.save(path, "PNG")
    return path
