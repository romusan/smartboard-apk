from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Literal
import time
import uuid

Action = Literal[
    "stroke_start", "stroke_update", "stroke_end", "erase", "undo", "redo",
    "page_create", "page_select", "lasso_select", "object_update", "ai_request",
    "ai_response", "sync_state", "command", "ack"
]

class Point(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    pressure: float = Field(default=1.0, ge=0.0, le=1.0)
    t: int

class Stroke(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page_id: str
    color: str = "#111111"
    width: float = 4.0
    points: list[Point] = Field(default_factory=list)

class BoardMessage(BaseModel):
    type: Action
    session_id: str
    client_id: str = "unknown"
    page_id: str = "page-1"
    stroke_id: str | None = None
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    version: int = 1
    payload: dict[str, Any] = Field(default_factory=dict)

class AiRequest(BaseModel):
    action: Literal["explain", "complete", "correct", "solve", "outline", "exercise", "draw3d", "mechanism_synthesis"]
    session_id: str
    page_id: str
    selection_id: str | None = None
    strokes: list[Stroke] = Field(default_factory=list)
    png_base64: str | None = None
    recognized_text: str = ""
    page_context: str = ""
    subject: Literal["materiales", "mecanismos", "dinamica"] = "materiales"

class AiResponse(BaseModel):
    kind: Literal["text", "latex", "svg", "image", "threejs", "openscad"]
    content: str
    editable: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
