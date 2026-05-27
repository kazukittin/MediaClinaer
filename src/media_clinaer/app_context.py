from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


class AppFolderNotWritableError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppContext:
    app_folder: Path
    cache_dir: Path
    logs_dir: Path
    quarantine_dir: Path
    config_path: Path
    database_path: Path
    log_path: Path

    @classmethod
    def discover(cls) -> "AppContext":
        app_folder = _resolve_app_folder()
        cache_dir = app_folder / "cache"
        logs_dir = app_folder / "logs"
        quarantine_dir = app_folder / "quarantine"
        return cls(
            app_folder=app_folder,
            cache_dir=cache_dir,
            logs_dir=logs_dir,
            quarantine_dir=quarantine_dir,
            config_path=app_folder / "config.json",
            database_path=cache_dir / "media_clinaer.sqlite3",
            log_path=logs_dir / "app.log",
        )

    def ensure_portable_dirs(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def verify_writable(self) -> None:
        probe = self.app_folder / ".write_test"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            raise AppFolderNotWritableError(
                f"App folder is not writable: {self.app_folder}"
            ) from exc


def _resolve_app_folder() -> Path:
    override = os.environ.get("MEDIA_CLINAER_APP_FOLDER")
    if override:
        return Path(override).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()
