from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from media_clinaer.logging.events import EventType


class JsonLineLogger:
    def __init__(self, log_path: Path, timezone: str = "Asia/Tokyo") -> None:
        self.log_path = log_path
        self.timezone = ZoneInfo(timezone)

    def debug(
        self,
        event: EventType,
        message: str,
        *,
        path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.write("DEBUG", event, message, path=path, details=details)

    def info(
        self,
        event: EventType,
        message: str,
        *,
        path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.write("INFO", event, message, path=path, details=details)

    def warning(
        self,
        event: EventType,
        message: str,
        *,
        path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.write("WARNING", event, message, path=path, details=details)

    def error(
        self,
        event: EventType,
        message: str,
        *,
        path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.write("ERROR", event, message, path=path, details=details)

    def write(
        self,
        level: str,
        event: EventType,
        message: str,
        *,
        path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "time": datetime.now(self.timezone).isoformat(timespec="seconds"),
            "level": level,
            "event": event.value,
            "message": message,
            "path": path,
            "details": details or {},
        }
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False))
            file.write("\n")
