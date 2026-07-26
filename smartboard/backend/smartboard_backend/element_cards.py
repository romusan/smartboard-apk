from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class ElementInfo:
    symbol: str
    name: str
    atomic_number: int
    configuration: str
    shells: tuple[int, ...]
    stable: bool = False


ELEMENTS: dict[str, ElementInfo] = {
    "H": ElementInfo("H", "Hydrogen", 1, "1s1", (1,)),
    "He": ElementInfo("He", "Helium", 2, "1s2", (2,), True),
    "Li": ElementInfo("Li", "Lithium", 3, "1s2 2s1", (2, 1)),
    "Be": ElementInfo("Be", "Beryllium", 4, "1s2 2s2", (2, 2)),
    "B": ElementInfo("B", "Boron", 5, "1s2 2s2 2p1", (2, 3)),
    "C": ElementInfo("C", "Carbon", 6, "1s2 2s2 2p2", (2, 4)),
    "N": ElementInfo("N", "Nitrogen", 7, "1s2 2s2 2p3", (2, 5)),
    "O": ElementInfo("O", "Oxygen", 8, "1s2 2s2 2p4", (2, 6)),
    "F": ElementInfo("F", "Fluorine", 9, "1s2 2s2 2p5", (2, 7)),
    "Ne": ElementInfo("Ne", "Neon", 10, "1s2 2s2 2p6", (2, 8), True),
    "Na": ElementInfo("Na", "Sodium", 11, "1s2 2s2 2p6 3s1", (2, 8, 1)),
    "Mg": ElementInfo("Mg", "Magnesium", 12, "1s2 2s2 2p6 3s2", (2, 8, 2)),
    "Al": ElementInfo("Al", "Aluminum", 13, "1s2 2s2 2p6 3s2 3p1", (2, 8, 3)),
    "Si": ElementInfo("Si", "Silicon", 14, "1s2 2s2 2p6 3s2 3p2", (2, 8, 4)),
    "P": ElementInfo("P", "Phosphorus", 15, "1s2 2s2 2p6 3s2 3p3", (2, 8, 5)),
    "S": ElementInfo("S", "Sulfur", 16, "1s2 2s2 2p6 3s2 3p4", (2, 8, 6)),
    "Cl": ElementInfo("Cl", "Chlorine", 17, "1s2 2s2 2p6 3s2 3p5", (2, 8, 7)),
    "Ar": ElementInfo("Ar", "Argon", 18, "1s2 2s2 2p6 3s2 3p6", (2, 8, 8), True),
    "K": ElementInfo("K", "Potassium", 19, "[Ar] 4s1", (2, 8, 8, 1)),
    "Ca": ElementInfo("Ca", "Calcium", 20, "[Ar] 4s2", (2, 8, 8, 2)),
    "Sc": ElementInfo("Sc", "Scandium", 21, "[Ar] 3d1 4s2", (2, 8, 9, 2)),
    "Ti": ElementInfo("Ti", "Titanium", 22, "[Ar] 3d2 4s2", (2, 8, 10, 2)),
    "V": ElementInfo("V", "Vanadium", 23, "[Ar] 3d3 4s2", (2, 8, 11, 2)),
    "Cr": ElementInfo("Cr", "Chromium", 24, "[Ar] 3d5 4s1", (2, 8, 13, 1)),
    "Mn": ElementInfo("Mn", "Manganese", 25, "[Ar] 3d5 4s2", (2, 8, 13, 2)),
    "Fe": ElementInfo("Fe", "Iron", 26, "[Ar] 3d6 4s2", (2, 8, 14, 2)),
    "Co": ElementInfo("Co", "Cobalt", 27, "[Ar] 3d7 4s2", (2, 8, 15, 2)),
    "Ni": ElementInfo("Ni", "Nickel", 28, "[Ar] 3d8 4s2", (2, 8, 16, 2)),
    "Cu": ElementInfo("Cu", "Copper", 29, "[Ar] 3d10 4s1", (2, 8, 18, 1)),
    "Zn": ElementInfo("Zn", "Zinc", 30, "[Ar] 3d10 4s2", (2, 8, 18, 2)),
    "Ga": ElementInfo("Ga", "Gallium", 31, "[Ar] 3d10 4s2 4p1", (2, 8, 18, 3)),
    "Ge": ElementInfo("Ge", "Germanium", 32, "[Ar] 3d10 4s2 4p2", (2, 8, 18, 4)),
    "As": ElementInfo("As", "Arsenic", 33, "[Ar] 3d10 4s2 4p3", (2, 8, 18, 5)),
    "Se": ElementInfo("Se", "Selenium", 34, "[Ar] 3d10 4s2 4p4", (2, 8, 18, 6)),
    "Br": ElementInfo("Br", "Bromine", 35, "[Ar] 3d10 4s2 4p5", (2, 8, 18, 7)),
    "Kr": ElementInfo("Kr", "Krypton", 36, "[Ar] 3d10 4s2 4p6", (2, 8, 18, 8), True),
}

NAME_TO_SYMBOL = {info.name.lower(): symbol for symbol, info in ELEMENTS.items()}
NAME_TO_SYMBOL.update({
    "hidrogeno": "H", "helio": "He", "litio": "Li", "berilio": "Be", "boro": "B", "carbono": "C",
    "nitrogeno": "N", "oxigeno": "O", "fluor": "F", "neon": "Ne", "sodio": "Na", "magnesio": "Mg",
    "aluminio": "Al", "silicio": "Si", "fosforo": "P", "azufre": "S", "cloro": "Cl", "argon": "Ar",
    "potasio": "K", "calcio": "Ca", "titanio": "Ti", "cromo": "Cr", "manganeso": "Mn", "hierro": "Fe",
    "cobalto": "Co", "niquel": "Ni", "cobre": "Cu", "zinc": "Zn", "galio": "Ga", "germanio": "Ge",
    "arsenico": "As", "selenio": "Se", "bromo": "Br", "kripton": "Kr", "krypton": "Kr",
})


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


def normalize_element_symbol(value: str) -> str | None:
    cleaned = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", " ", value).strip()
    if not cleaned:
        return None
    words = cleaned.split()
    for word in words:
        symbol = word[:1].upper() + word[1:].lower()
        if symbol in ELEMENTS:
            return symbol
        mapped = NAME_TO_SYMBOL.get(word.lower())
        if mapped:
            return mapped
    compact = "".join(words)
    symbol = compact[:1].upper() + compact[1:].lower()
    if symbol in ELEMENTS:
        return symbol
    return NAME_TO_SYMBOL.get(compact.lower())


def detect_element_query(value: str) -> str | None:
    cleaned = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", " ", value).strip()
    if not cleaned:
        return None
    words = cleaned.split()
    plain_words = [word.lower() for word in words]
    element_keywords = {
        "elemento", "element", "atomico", "atomica", "atomo", "electron", "electrones",
        "configuracion", "niveles", "energia", "energeticos", "valencia",
    }
    has_keyword = any(word in element_keywords for word in plain_words)
    for word in words:
        symbol = word[:1].upper() + word[1:].lower()
        if symbol in ELEMENTS and (has_keyword or len(words) <= 3):
            return symbol
        mapped = NAME_TO_SYMBOL.get(word.lower())
        if mapped and (has_keyword or len(words) <= 4):
            return mapped
    return None


def generate_element_energy_card(output_dir: Path, symbol: str) -> Path:
    info = ELEMENTS[symbol]
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(f"element-energy-{symbol}-v2".encode()).hexdigest()[:10]
    path = output_dir / f"element_energy_{symbol.lower()}_{digest}.png"
    if path.is_file():
        return path

    image = Image.new("RGB", (1100, 720), "#f8fafc")
    draw = ImageDraw.Draw(image, "RGBA")
    accent = "#0891b2" if info.stable else "#7c3aed"
    draw.rounded_rectangle((28, 28, 1072, 692), radius=34, fill="#ffffff", outline=accent, width=4)
    draw.text((62, 54), f"{info.name} ({info.symbol})", fill=accent, font=_font(42, True))
    draw.text((64, 112), "Configuracion electronica y niveles de energia", fill="#334155", font=_font(25, True))

    center = (385, 390)
    max_radius = 230
    for index, electrons in enumerate(info.shells, start=1):
        radius = 72 + (index - 1) * 52
        draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), outline="#64748b", width=3)
        count = min(electrons, 18)
        for electron_index in range(count):
            angle = 2 * math.pi * electron_index / max(count, 1) + index * 0.25
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill="#38bdf8", outline="#0f172a", width=1)
    draw.ellipse((center[0] - 46, center[1] - 46, center[0] + 46, center[1] + 46), fill="#fecaca", outline="#dc2626", width=4)
    draw.text((center[0] - 26, center[1] - 18), f"Z={info.atomic_number}", fill="#991b1b", font=_font(20, True))
    legend_x, legend_y = 92, 180
    draw.rounded_rectangle((legend_x, legend_y, legend_x + 170, legend_y + 32 + 28 * len(info.shells)), radius=14, fill=(255, 255, 255, 215), outline="#cbd5e1", width=2)
    draw.text((legend_x + 14, legend_y + 10), "Niveles", fill="#0f172a", font=_font(18, True))
    for index, electrons in enumerate(info.shells, start=1):
        draw.text((legend_x + 14, legend_y + 12 + 28 * index), f"n={index}: {electrons} e-", fill="#334155", font=_font(17))

    draw.rounded_rectangle((645, 170, 1038, 610), radius=24, fill="#f5f3ff", outline="#c4b5fd", width=3)
    valence = info.shells[-1]
    lines = [
        ("Elemento", f"{info.name} / {info.symbol}"),
        ("Numero atomico", str(info.atomic_number)),
        ("Configuracion", info.configuration),
        ("Electrones por nivel", " - ".join(str(v) for v in info.shells)),
        ("Valencia externa", f"{valence} electron(es)"),
        ("Estabilidad", "estable: capa externa completa" if info.stable else "no estable: valencia incompleta"),
    ]
    y = 195
    for title, body in lines:
        draw.text((675, y), title, fill="#111827", font=_font(21, True))
        draw.text((675, y + 27), body, fill="#334155", font=_font(20))
        y += 68

    draw.line((86, 620, 565, 620), fill="#334155", width=3)
    draw.polygon([(565, 620), (540, 608), (540, 632)], fill="#334155")
    draw.text((96, 636), "energia aumenta hacia niveles externos", fill="#475569", font=_font(18))
    draw.text((64, 662), "Si escribes a mano el simbolo o nombre del elemento, se genera esta tarjeta.", fill="#475569", font=_font(18))
    image.save(path, "PNG")
    return path
