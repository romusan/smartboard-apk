from __future__ import annotations

import asyncio
import os
import sys
import threading
from pathlib import Path

from .models import AiRequest, AiResponse

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_components: tuple[dict, object] | None = None
_components_lock = threading.Lock()
SMARTBOARD_AI_TIMEOUT = int(os.getenv("SMARTBOARD_AI_TIMEOUT", "75"))

ACTION_PROMPTS = {
    "explain": "Explica de forma clara y breve el contenido seleccionado.",
    "complete": "Completa la idea del estudiante usando el material de clase.",
    "correct": "Corrige errores conceptuales o de procedimiento en el contenido.",
    "solve": "Resuelve u orienta paso a paso el problema planteado.",
    "outline": "Crea un esquema ordenado para estudiar este tema.",
    "exercise": "Genera un ejercicio nuevo relacionado, con pista y respuesta.",
    "draw3d": "Propón una representación 3D o geométrica simple del concepto.",
}


def _load_components() -> tuple[dict, object]:
    global _components
    if _components is None:
        with _components_lock:
            if _components is None:
                from app.bot import components

                _components = components()
    return _components


def _build_question(request: AiRequest) -> str:
    stroke_count = len(request.strokes)
    points_count = sum(len(stroke.points) for stroke in request.strokes)
    text = request.recognized_text.strip() or "No hay texto OCR reconocido; usa el contexto y los trazos seleccionados."
    context = request.page_context.strip() or "Clase de Ciencia e Ingeniería de Materiales."
    action = ACTION_PROMPTS.get(request.action, ACTION_PROMPTS["explain"])
    return f"""
Contexto de pizarra: {context}
Acción solicitada: {action}
Texto seleccionado o reconocido: {text}
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


def _ask_tutor_sync(request: AiRequest) -> AiResponse:
    cfg, index = _load_components()
    question = _build_question(request)
    answer, hits = index.answer(question, cfg["chat_model"], mode="fuentes")
    sources = [f"{hit.source} ({hit.location})" for hit in hits[:5]]
    return AiResponse(
        kind=_response_kind(request.action, answer),
        content=answer,
        metadata={
            "provider": "Tutor_materias",
            "model": cfg.get("chat_model"),
            "sources": sources,
            "question": question,
        },
    )


async def query_tutor_materials(request: AiRequest) -> AiResponse:
    return await asyncio.wait_for(
        asyncio.to_thread(_ask_tutor_sync, request),
        timeout=SMARTBOARD_AI_TIMEOUT,
    )
