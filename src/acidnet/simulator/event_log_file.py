from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


class EventLogFile:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    def write(
        self,
        *,
        kind: str,
        message: str,
        day: int | None = None,
        tick: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")
        prefix_parts = [timestamp, kind]
        if day is not None:
            prefix_parts.append(f"day={day}")
        if tick is not None:
            prefix_parts.append(f"tick={tick}")
        normalized_message = message.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " \\n ")
        line = " | ".join(prefix_parts) + " | " + normalized_message
        if payload:
            line += " | " + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self._handle.write(line + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()
