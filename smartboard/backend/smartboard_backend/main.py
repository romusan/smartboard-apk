from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
import pypdfium2 as pdfium

from .models import AiRequest, AiResponse, BoardMessage
from .mechanism_synthesis import synthesize_mechanism
from .ollama import query_ollama
from .store import SessionStore
from .tutor_adapter import query_tutor_materials

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("SMARTBOARD_DATA", ROOT / "sessions"))
GENERATED_DIR = Path(os.getenv("SMARTBOARD_GENERATED_DIR", ROOT / "generated"))
DOCUMENTS_DIR = Path(os.getenv("SMARTBOARD_DOCUMENTS_DIR", ROOT / "documents"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
AI_PROVIDER = os.getenv("SMARTBOARD_AI_PROVIDER", "tutor").strip().lower()

app = FastAPI(title="SmartBoard Vector Sync", version="0.1.0")
store = SessionStore(DATA_DIR)
clients: dict[str, set[WebSocket]] = {}

app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=GENERATED_DIR), name="generated")
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/")
async def index() -> FileResponse:
    return FileResponse(ROOT / "web" / "index.html")

@app.post("/sessions")
async def create_session() -> dict[str, str]:
    return {"session_id": str(uuid.uuid4())}

@app.get("/sessions/{session_id}")
async def session_history(session_id: str) -> dict:
    return {"session_id": session_id, "messages": await store.history(session_id)}

@app.post("/documents/upload")
async def upload_document(request: Request, session_id: str = "demo", filename: str = "documento.pdf") -> dict:
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF.")
    document_id = str(uuid.uuid4())
    document_dir = DOCUMENTS_DIR / document_id
    document_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = document_dir / "source.pdf"
    pdf_path.write_bytes(await request.body())
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        pages = []
        for index in range(len(pdf)):
            page = pdf[index]
            bitmap = page.render(scale=1.8)
            image = bitmap.to_pil()
            page_path = document_dir / f"page-{index + 1}.png"
            image.save(page_path, "PNG")
            pages.append({
                "index": index,
                "page_id": f"doc-{document_id}-page-{index + 1}",
                "image_url": f"/documents/{document_id}/{page_path.name}",
                "width": image.width,
                "height": image.height,
            })
        pdf.close()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No pude convertir el PDF: {exc}") from exc
    message = BoardMessage(
        type="object_update",
        session_id=session_id,
        client_id="backend",
        page_id=pages[0]["page_id"] if pages else "page-1",
        payload={
            "action": "document_set",
            "document": {
                "id": document_id,
                "filename": filename,
                "pages": pages,
                "current_page": 0,
            },
        },
    )
    await store.append(message)
    await broadcast(session_id, message.model_dump())
    return message.payload

app.mount("/documents", StaticFiles(directory=DOCUMENTS_DIR), name="documents")

@app.post("/ai/query")
async def ai_query(request: AiRequest) -> dict:
    try:
        result = await run_ai(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Tutor_materias/Ollama no respondió: {exc}") from exc
    message = BoardMessage(
        type="ai_response",
        session_id=request.session_id,
        page_id=request.page_id,
        client_id="backend",
        payload=result.model_dump(),
    )
    await store.append(message)
    await broadcast(request.session_id, message.model_dump())
    return result.model_dump()

async def run_ai(request: AiRequest) -> AiResponse:
    if request.action == "mechanism_synthesis" or request.subject == "mecanismos" and request.strokes:
        return synthesize_mechanism(request, GENERATED_DIR)
    if AI_PROVIDER in {"tutor", "tutor_materias", "materials"}:
        return await query_tutor_materials(request)
    return await query_ollama(OLLAMA_URL, OLLAMA_MODEL, request)

async def handle_ai_request(message: BoardMessage) -> BoardMessage:
    payload = message.payload or {}
    recognized_text = payload.get("recognized_text", "")
    card_type = payload.get("card_type")
    if card_type and not recognized_text:
        recognized_text = str(card_type).replace("_", " ")
    page_context = payload.get("page_context", "")
    if card_type:
        page_context = f"{page_context}\ncard_type: {card_type}".strip()
    request = AiRequest(
        action=payload.get("action", "explain"),
        session_id=message.session_id,
        page_id=message.page_id,
        selection_id=payload.get("selection_id"),
        strokes=payload.get("strokes", []),
        png_base64=payload.get("png_base64"),
        recognized_text=recognized_text,
        page_context=page_context,
        subject=payload.get("subject", "materiales"),
    )
    result = await run_ai(request)
    return BoardMessage(
        type="ai_response",
        session_id=message.session_id,
        page_id=message.page_id,
        client_id="backend",
        payload=result.model_dump(),
    )

async def broadcast(session_id: str, data: dict, sender: WebSocket | None = None) -> None:
    dead: list[WebSocket] = []
    for websocket in clients.get(session_id, set()):
        if websocket is sender:
            continue
        try:
            await websocket.send_json(data)
        except Exception:
            dead.append(websocket)
    for websocket in dead:
        clients.get(session_id, set()).discard(websocket)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    clients.setdefault(session_id, set()).add(websocket)
    await websocket.send_json({"type": "sync_state", "session_id": session_id, "payload": {"history": await store.history(session_id)}})
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = BoardMessage.model_validate_json(raw)
            except ValidationError:
                message = BoardMessage.model_validate(json.loads(raw) | {"session_id": session_id})
            if message.session_id != session_id:
                message.session_id = session_id
            await store.append(message)
            await websocket.send_json({"type": "ack", "session_id": session_id, "payload": {"timestamp": message.timestamp, "stroke_id": message.stroke_id}})
            await broadcast(session_id, message.model_dump(), sender=websocket)
            if message.type == "ai_request":
                try:
                    response_message = await handle_ai_request(message)
                    await store.append(response_message)
                    await websocket.send_json(response_message.model_dump())
                    await broadcast(session_id, response_message.model_dump(), sender=websocket)
                except Exception as exc:
                    await websocket.send_json({
                        "type": "command",
                        "session_id": session_id,
                        "client_id": "backend",
                        "page_id": message.page_id,
                        "payload": {"error": f"Tutor_materias/Ollama no respondió: {exc}"},
                    })
    except WebSocketDisconnect:
        clients.get(session_id, set()).discard(websocket)
