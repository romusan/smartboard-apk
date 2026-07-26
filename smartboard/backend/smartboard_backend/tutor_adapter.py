from __future__ import annotations

import asyncio
import json
import os
from urllib import parse, request as urlrequest
import re
import sys
import threading
import unicodedata
from pathlib import Path

from .models import AiRequest, AiResponse
from .atomic_cards import generate_atom_structure_card, generate_quantum_numbers_card
from .bcc_card import generate_bcc_card
from .fcc_card import generate_fcc_card
from .miller_card import generate_miller_card

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_components: tuple[dict, object] | None = None
_components_lock = threading.Lock()
SMARTBOARD_AI_TIMEOUT = int(os.getenv("SMARTBOARD_AI_TIMEOUT", "75"))
SMARTBOARD_GEMINI_SUPERVISION = os.getenv("SMARTBOARD_GEMINI_SUPERVISION", "true").strip().lower() in {"1", "true", "yes", "si", "sí"}
SMARTBOARD_GEMINI_TIMEOUT = int(os.getenv("SMARTBOARD_GEMINI_TIMEOUT", "8"))
GENERATED_DIR = Path(os.getenv("SMARTBOARD_GENERATED_DIR", Path(__file__).resolve().parent.parent / "generated"))

ACTION_PROMPTS = {
    "explain": "Explica de forma clara y breve el contenido seleccionado.",
    "complete": "Completa la idea del estudiante usando el material de clase.",
    "correct": "Corrige errores conceptuales o de procedimiento en el contenido.",
    "solve": "Resuelve u orienta paso a paso el problema planteado.",
    "outline": "Crea un esquema ordenado para estudiar este tema.",
    "exercise": "Genera un ejercicio nuevo relacionado, con pista y respuesta.",
    "draw3d": "Propón una representación 3D o geométrica simple del concepto.",
}


TECHNICAL_TERMS = {
    "miller": "números de Miller",
    "millo": "números de Miller",
    "miler": "números de Miller",
    "milles": "números de Miller",
    "muller": "números de Miller",
    "milleres": "números de Miller",
    "ferrita": "ferrita",
    "austenita": "austenita",
    "cementita": "cementita",
    "perlita": "perlita",
    "martensita": "martensita",
    "bainita": "bainita",
    "eutectoide": "eutectoide",
    "eutectico": "eutéctico",
    "eutéctico": "eutéctico",
    "temple": "temple",
    "revenido": "revenido",
    "recocido": "recocido",
    "normalizado": "normalizado",
    "dureza": "dureza",
    "rockwell": "Rockwell",
    "brinell": "Brinell",
    "vickers": "Vickers",
}


def _load_components() -> tuple[dict, object]:
    global _components
    if _components is None:
        with _components_lock:
            if _components is None:
                from app.bot import components

                _components = components()
    return _components


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _distance(left: str, right: str) -> int:
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, 1):
        current = [left_index]
        for right_index, right_char in enumerate(right, 1):
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def autocorrect_materials_text(text: str) -> tuple[str, list[dict[str, str]]]:
    original = text.strip()
    if not original:
        return "", []
    corrections: list[dict[str, str]] = []
    tokens = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", original)
    corrected_parts: list[str] = []
    for token in tokens:
        plain_token = _plain(token)
        replacement = TECHNICAL_TERMS.get(plain_token)
        if replacement is None:
            candidates = [
                (term, value)
                for term, value in TECHNICAL_TERMS.items()
                if abs(len(term) - len(plain_token)) <= 2 and _distance(plain_token, term) <= 2
            ]
            replacement = candidates[0][1] if candidates else token
        corrected_parts.append(replacement)
        if replacement != token:
            corrections.append({"from": token, "to": replacement})
    return " ".join(corrected_parts).strip() or original, corrections


def _build_question(request: AiRequest) -> str:
    stroke_count = len(request.strokes)
    points_count = sum(len(stroke.points) for stroke in request.strokes)
    corrected_text, corrections = autocorrect_materials_text(request.recognized_text)
    text = corrected_text or "No hay texto OCR reconocido; usa el contexto y los trazos seleccionados."
    correction_note = f"\nCorrección OCR aplicada: {corrections}" if corrections else ""
    context = request.page_context.strip() or "Clase de Ciencia e Ingeniería de Materiales."
    action = ACTION_PROMPTS.get(request.action, ACTION_PROMPTS["explain"])
    return f"""
Contexto de pizarra: {context}
Acción solicitada: {action}
Texto seleccionado o reconocido: {text}
Texto OCR original: {request.recognized_text.strip() or "vacío"}{correction_note}
Resumen de trazos vectoriales: {stroke_count} trazos, {points_count} puntos.

Responde como tutor de la asignatura de materiales. Usa el material del curso, evita inventar,
y entrega una respuesta breve, editable y útil para insertar en la pizarra.
""".strip()


def _response_kind(action: str, content: str) -> str:
    lowered = content.lower()
    if action == "draw3d" and ("openscad" in lowered or "module " in lowered):
        return "openscad"
    if action == "draw3d" and ("three.js" in lowered or "new three." in lowered):
        return "threejs"
    if "<svg" in lowered:
        return "svg"
    if "\\(" in content or "\\[" in content or "\\frac" in content:
        return "latex"
    return "text"


def _quick_materials_answer(corrected_text: str) -> str | None:
    if "numeros de miller" not in _plain(corrected_text):
        return None
    return """
Los números de Miller son una forma compacta de identificar planos cristalográficos en materiales.

Idea central:
- Se escriben como (h k l).
- Indican la orientación de un plano dentro de la celda cristalina.
- Se obtienen mirando dónde el plano corta los ejes cristalográficos a, b y c.
- Luego se toman los recíprocos de esos interceptos y se reducen a enteros mínimos.

Ejemplo rápido:
Si un plano corta los ejes en a, b e infinito en c, sus interceptos son 1, 1, ∞.
Los recíprocos son 1, 1, 0, por eso el plano es (110).

¿Quieres que hagamos un dibujo de una celda cúbica con el plano (110)?
""".strip()


def _detect_miller_plane(text: str) -> tuple[int, int, int] | None:
    plain = _plain(text)
    keyword_match = re.search(r"\b(?:plano|planos|miller|hkl)\b(.{0,20})", plain)
    if keyword_match:
        digit_tail = (
            keyword_match.group(1)
            .replace("|", "1")
            .replace("i", "1")
            .replace("l", "1")
            .replace("o", "0")
            .replace("z", "2")
            .replace("s", "5")
        )
        compact = re.sub(r"[^0-9]", "", digit_tail)
        if len(compact) >= 3:
            return tuple(int(value) for value in compact[:3])
    patterns = (
        r"\b(?:plano|planos|miller|hkl)\s*\(?\s*([0-9])\s*[,;\-\s]\s*([0-9])\s*[,;\-\s]\s*([0-9])\s*\)?",
        r"\b(?:plano|planos|miller|hkl)\s*\(?\s*([0-9])\s*([0-9])\s*([0-9])\s*\)?",
        r"\(([0-9])\s*[,;\-\s]?\s*([0-9])\s*[,;\-\s]?\s*([0-9])\)",
    )
    for pattern in patterns:
        match = re.search(pattern, plain)
        if match:
            return tuple(int(value) for value in match.groups())
    return None


def _stroke_bounds(stroke) -> tuple[float, float, float, float] | None:
    points = getattr(stroke, "points", []) or []
    if not points:
        return None
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _classify_digit_stroke(stroke) -> str | None:
    bounds = _stroke_bounds(stroke)
    if bounds is None:
        return None
    min_x, min_y, max_x, max_y = bounds
    width = max(max_x - min_x, 0.001)
    height = max(max_y - min_y, 0.001)
    points = getattr(stroke, "points", []) or []
    if len(points) < 2:
        return None
    aspect = width / height
    start = points[0]
    end = points[-1]
    direction_x = end.x - start.x
    direction_y = end.y - start.y
    if aspect < 0.35 and height > 0.035:
        return "1"
    if aspect > 0.55 and abs(direction_x) > width * 0.35 and direction_y > height * 0.15:
        return "2"
    if aspect > 0.45 and abs(direction_x) < width * 0.45 and abs(direction_y) < height * 0.45:
        return "0"
    return None


def _infer_miller_plane_from_strokes(request: AiRequest) -> tuple[int, int, int] | None:
    text = _plain(request.recognized_text)
    if not any(keyword in text for keyword in ("plano", "planos", "miller", "hkl")):
        return None
    digits: list[tuple[float, str]] = []
    for stroke in request.strokes:
        digit = _classify_digit_stroke(stroke)
        bounds = _stroke_bounds(stroke)
        if digit and bounds:
            digits.append((bounds[0], digit))
    if len(digits) < 3:
        return None
    ordered = [digit for _, digit in sorted(digits, key=lambda item: item[0])[-3:]]
    return tuple(int(value) for value in ordered)


def _miller_plane_card_response(request: AiRequest, corrected_text: str, corrections: list[dict[str, str]], question: str) -> AiResponse | None:
    plane = (
        _detect_miller_plane(corrected_text)
        or _detect_miller_plane(request.recognized_text)
        or _infer_miller_plane_from_strokes(request)
    )
    if plane is None:
        return None
    h, k, l = plane
    image_path = generate_miller_card(GENERATED_DIR, h, k, l)
    image_url = f"/generated/{image_path.name}"
    content = f"Tarjeta didáctica generada para el plano de Miller ({h}{k}{l})."
    return AiResponse(
        kind="image",
        content=content,
        metadata={
            "provider": "Tutor_materias",
            "model": "python-miller-card",
            "question": question,
            "recognized_text_original": request.recognized_text,
            "recognized_text_corrected": corrected_text,
            "ocr_corrections": corrections,
            "miller_plane": {"h": h, "k": k, "l": l},
            "image_url": image_url,
            "supervisor": "not_required_for_generated_diagram",
        },
    )


def _detect_bcc(text: str) -> bool:
    plain = _plain(text)
    compact = re.sub(r"[^a-z0-9]", "", plain)
    return "bcc" in compact or "bce" in compact or "bec" in compact or "cubicaentradaenelcuerpo" in compact


def _detect_fcc(text: str) -> bool:
    plain = _plain(text)
    compact = re.sub(r"[^a-z0-9]", "", plain)
    return "fcc" in compact or "fce" in compact or "fec" in compact or "cubicacentradaenlascaras" in compact


def _detect_atom_structure(text: str) -> bool:
    plain = _plain(text)
    compact = re.sub(r"[^a-z0-9]", "", plain)
    return (
        "atomo" in plain
        or "atomica" in plain
        or "atomic" in compact
        or "atomstructure" in compact
        or "estructuraatom" in compact
    )


def _detect_quantum_numbers(text: str) -> bool:
    plain = _plain(text)
    compact = re.sub(r"[^a-z0-9]", "", plain)
    return (
        "numero cuantico" in plain
        or "numeros cuanticos" in plain
        or "cuantico" in plain
        or "niveles de energia" in plain
        or "quantum" in compact
    )


def _image_response(
    *,
    request: AiRequest,
    corrected_text: str,
    corrections: list[dict[str, str]],
    question: str,
    image_path: Path,
    content: str,
    model: str,
    metadata: dict,
) -> AiResponse:
    return AiResponse(
        kind="image",
        content=content,
        metadata={
            "provider": "Tutor_materias",
            "model": model,
            "question": question,
            "recognized_text_original": request.recognized_text,
            "recognized_text_corrected": corrected_text,
            "ocr_corrections": corrections,
            "image_url": f"/generated/{image_path.name}",
            "supervisor": "not_required_for_generated_diagram",
            **metadata,
        },
    )


def _atom_card_response(request: AiRequest, corrected_text: str, corrections: list[dict[str, str]], question: str) -> AiResponse | None:
    if not (_detect_atom_structure(corrected_text) or _detect_atom_structure(request.recognized_text)):
        return None
    image_path = generate_atom_structure_card(GENERATED_DIR)
    return _image_response(
        request=request,
        corrected_text=corrected_text,
        corrections=corrections,
        question=question,
        image_path=image_path,
        content="Tarjeta didáctica generada para estructura del átomo.",
        model="python-atom-structure-card",
        metadata={"card_type": "atom_structure"},
    )


def _quantum_card_response(request: AiRequest, corrected_text: str, corrections: list[dict[str, str]], question: str) -> AiResponse | None:
    if not (_detect_quantum_numbers(corrected_text) or _detect_quantum_numbers(request.recognized_text)):
        return None
    image_path = generate_quantum_numbers_card(GENERATED_DIR)
    return _image_response(
        request=request,
        corrected_text=corrected_text,
        corrections=corrections,
        question=question,
        image_path=image_path,
        content="Tarjeta didáctica generada para números cuánticos y niveles de energía.",
        model="python-quantum-numbers-card",
        metadata={"card_type": "quantum_numbers"},
    )


def _bcc_card_response(request: AiRequest, corrected_text: str, corrections: list[dict[str, str]], question: str) -> AiResponse | None:
    if not (_detect_bcc(corrected_text) or _detect_bcc(request.recognized_text)):
        return None
    image_path = generate_bcc_card(GENERATED_DIR)
    image_url = f"/generated/{image_path.name}"
    return AiResponse(
        kind="image",
        content="Tarjeta didáctica generada para estructura BCC.",
        metadata={
            "provider": "Tutor_materias",
            "model": "python-bcc-card",
            "question": question,
            "recognized_text_original": request.recognized_text,
            "recognized_text_corrected": corrected_text,
            "ocr_corrections": corrections,
            "crystal_structure": "bcc",
            "image_url": image_url,
            "supervisor": "not_required_for_generated_diagram",
        },
    )


def _fcc_card_response(request: AiRequest, corrected_text: str, corrections: list[dict[str, str]], question: str) -> AiResponse | None:
    if not (_detect_fcc(corrected_text) or _detect_fcc(request.recognized_text)):
        return None
    image_path = generate_fcc_card(GENERATED_DIR)
    image_url = f"/generated/{image_path.name}"
    return AiResponse(
        kind="image",
        content="Tarjeta didáctica generada para estructura FCC.",
        metadata={
            "provider": "Tutor_materias",
            "model": "python-fcc-card",
            "question": question,
            "recognized_text_original": request.recognized_text,
            "recognized_text_corrected": corrected_text,
            "ocr_corrections": corrections,
            "crystal_structure": "fcc",
            "image_url": image_url,
            "supervisor": "not_required_for_generated_diagram",
        },
    )


def _supervise_answer(answer: str, question: str) -> tuple[str, dict[str, str]]:
    if not SMARTBOARD_GEMINI_SUPERVISION:
        return answer, {"supervisor": "disabled"}
    try:
        from app.bot import config

        cfg = config()
        if not cfg.get("gemini_api_key"):
            return answer, {"supervisor": "missing_api_key"}
        prompt = f"""
Pregunta o contexto del estudiante:
{question}

Respuesta propuesta:
{answer}

Actúa como supervisor académico de Ciencia e Ingeniería de Materiales.
Verifica si la respuesta es correcta, clara y didáctica. Si está bien, reescríbela
en formato breve para pizarra. Si tiene errores, corrígela. No agregues información
incierta ni extensa.
""".strip()
        model = cfg.get("backup_chat_model", "gemini-3.5-flash")
        payload = {
            "systemInstruction": {
                "parts": [{"text": "Eres un revisor académico cuidadoso y conciso."}]
            },
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{parse.quote(model, safe='')}:generateContent"
        gemini_request = urlrequest.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": cfg["gemini_api_key"],
            },
            method="POST",
        )
        with urlrequest.urlopen(gemini_request, timeout=SMARTBOARD_GEMINI_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
        parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
        supervised = "".join(str(part.get("text", "")) for part in parts).strip()
        return supervised or answer, {"supervisor": "gemini", "supervisor_model": model}
    except Exception as exc:
        return answer, {"supervisor": "failed", "supervisor_error": str(exc)}


def _ask_tutor_sync(request: AiRequest) -> AiResponse:
    corrected_text, corrections = autocorrect_materials_text(request.recognized_text)
    question = _build_question(request)
    atom_card = _atom_card_response(request, corrected_text, corrections, question)
    if atom_card is not None:
        return atom_card
    quantum_card = _quantum_card_response(request, corrected_text, corrections, question)
    if quantum_card is not None:
        return quantum_card
    bcc_card = _bcc_card_response(request, corrected_text, corrections, question)
    if bcc_card is not None:
        return bcc_card
    fcc_card = _fcc_card_response(request, corrected_text, corrections, question)
    if fcc_card is not None:
        return fcc_card
    plane_card = _miller_plane_card_response(request, corrected_text, corrections, question)
    if plane_card is not None:
        return plane_card
    quick_answer = _quick_materials_answer(corrected_text)
    if quick_answer is not None:
        supervised_answer, supervisor_metadata = _supervise_answer(quick_answer, question)
        return AiResponse(
            kind="text",
            content=supervised_answer,
            metadata={
                "provider": "Tutor_materias",
                "model": "quick-materials-answer",
                "question": question,
                "recognized_text_original": request.recognized_text,
                "recognized_text_corrected": corrected_text,
                "ocr_corrections": corrections,
                **supervisor_metadata,
            },
        )
    cfg, index = _load_components()
    answer, hits = index.answer(question, cfg["chat_model"], mode="fuentes")
    supervised_answer, supervisor_metadata = _supervise_answer(answer, question)
    sources = [f"{hit.source} ({hit.location})" for hit in hits[:5]]
    return AiResponse(
        kind=_response_kind(request.action, supervised_answer),
        content=supervised_answer,
        metadata={
            "provider": "Tutor_materias",
            "model": cfg.get("chat_model"),
            "sources": sources,
            "question": question,
            "recognized_text_original": request.recognized_text,
            "recognized_text_corrected": corrected_text,
            "ocr_corrections": corrections,
            **supervisor_metadata,
        },
    )


async def query_tutor_materials(request: AiRequest) -> AiResponse:
    return await asyncio.wait_for(
        asyncio.to_thread(_ask_tutor_sync, request),
        timeout=SMARTBOARD_AI_TIMEOUT,
    )
