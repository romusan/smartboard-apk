from __future__ import annotations

import httpx

from .models import AiRequest, AiResponse

SYSTEM = """Eres una IA educativa para una pizarra inteligente. Responde solo con material útil para insertar en la pizarra. Si piden 3D, entrega Three.js u OpenSCAD mínimo y claro."""

async def query_ollama(base_url: str, model: str, request: AiRequest) -> AiResponse:
    prompt = f"""
Acción: {request.action}
Texto reconocido: {request.recognized_text}
Contexto de página: {request.page_context}
Trazos vectoriales JSON: {[stroke.model_dump() for stroke in request.strokes]}
Devuelve una respuesta breve y editable. Si hay ecuaciones usa LaTeX. Si hay diagrama usa SVG.
""".strip()
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.2},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(f"{base_url.rstrip('/')}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
    content = ((data.get("message") or {}).get("content") or "").strip()
    kind = "openscad" if request.action == "draw3d" and "module" in content else "text"
    if "<svg" in content.lower():
        kind = "svg"
    if "\\(" in content or "\\[" in content or "\\frac" in content:
        kind = "latex"
    return AiResponse(kind=kind, content=content or "No se recibió respuesta de Ollama.")
