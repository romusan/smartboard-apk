from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import BoardMessage

class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.messages: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.lock = asyncio.Lock()

    async def append(self, message: BoardMessage) -> None:
        record = message.model_dump()
        async with self.lock:
            self.messages[message.session_id].append(record)
            path = self.root / f"{message.session_id}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def history(self, session_id: str) -> list[dict[str, Any]]:
        async with self.lock:
            if session_id not in self.messages:
                path = self.root / f"{session_id}.jsonl"
                if path.is_file():
                    self.messages[session_id] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            return list(self.messages.get(session_id, []))
