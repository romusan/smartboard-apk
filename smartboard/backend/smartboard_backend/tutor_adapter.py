from __future__ import annotations

import asyncio
import os
import re
import sys
import threading
import unicodedata
from pathlib import Path

from .models import AiRequest, AiResponse

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_components: tuple[dict, object] | None = None
_components_lock = threading.Lock()
SMARTBOARD_AI_TIMEOUT = int(os.getenv("SMARTBOARD_AI_TIMEOUT", "75"))
SMARTBOARD_GEMINI_SUPERVISION = os.getenv("SMARTBOARD_GEMINI_SUPERVISION", "true").strip().lower() in {"1", "true", "yes", "si", "sí"}

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


def _supervise_answer(answer: str, question: str) -> tuple[str, dict[str, str]]:
    if not SMARTBOARD_GEMINI_SUPERVISION:
        return answer, {"supervisor": "disabled"}
    try:
        from app.bot import config
        from app.gemini import Gemini

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
        supervised = Gemini(cfg["gemini_api_key"]).chat(
            cfg.get("backup_chat_model", "gemini-3.5-flash"),
            [
                {"role": "system", "content": "Eres un revisor académico cuidadoso y conciso."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        return supervised, {"supervisor": "gemini", "supervisor_model": cfg.get("backup_chat_model", "gemini-3.5-flash")}
    except Exception as exc:
        return answer, {"supervisor": "failed", "supervisor_error": str(exc)}


def _ask_tutor_sync(request: AiRequest) -> AiResponse:
    corrected_text, corrections = autocorrect_materials_text(request.recognized_text)
    question = _build_question(request)
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
