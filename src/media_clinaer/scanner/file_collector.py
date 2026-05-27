from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from media_clinaer.config.models import ScanConfig
from media_clinaer.logging.events import EventType
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.scanner.path_utils import detect_media_type


class FileCollector:
    def __init__(self, config: ScanConfig, logger: JsonLineLogger | None = None) -> None:
        self.config = config
        self.logger = logger
        self.image_extensions = {ext.lower() for ext in config.image_extensions}
        self.video_extensions = {ext.lower() for ext in config.video_extensions}

    def collect(self, target_paths: list[str]) -> Iterator[Path]:
        for target_path in target_paths:
            root = Path(target_path)
            if not root.exists() or not root.is_dir():
                self._warning(
                    EventType.NAS_FOLDER_UNAVAILABLE,
                    "Target folder is unavailable",
                    root,
                )
                continue
            yield from self._collect_from_root(root)

    def _collect_from_root(self, root: Path) -> Iterator[Path]:
        pattern = "**/*" if self.config.include_subdirectories else "*"
        try:
            candidates = root.rglob("*") if pattern == "**/*" else root.glob("*")
            for candidate in candidates:
                if candidate.is_symlink() and not self.config.follow_symlinks:
                    continue
                try:
                    if not candidate.is_file():
                        continue
                except OSError as exc:
                    self._warning(
                        EventType.FILE_SCAN_FAILED,
                        f"Failed to inspect file: {exc}",
                        candidate,
                    )
                    continue
                if detect_media_type(
                    candidate,
                    self.image_extensions,
                    self.video_extensions,
                ):
                    yield candidate
        except OSError as exc:
            self._warning(
                EventType.FOLDER_SCAN_FAILED,
                f"Failed to scan folder: {exc}",
                root,
            )

    def _warning(self, event: EventType, message: str, path: Path) -> None:
        if self.logger:
            self.logger.warning(event, message, path=str(path))
