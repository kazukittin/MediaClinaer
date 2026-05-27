from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from media_clinaer.config.models import ScanConfig
from media_clinaer.models.media_file import MediaMetadata
from media_clinaer.scanner.path_utils import (
    detect_media_type,
    detect_storage_type,
    get_extension,
    normalize_path,
)


class MetadataReader:
    def __init__(self, config: ScanConfig, timezone: str = "Asia/Tokyo") -> None:
        self.image_extensions = {ext.lower() for ext in config.image_extensions}
        self.video_extensions = {ext.lower() for ext in config.video_extensions}
        self.timezone = ZoneInfo(timezone)

    def read(self, path: Path) -> MediaMetadata:
        stat = path.stat()
        media_type = detect_media_type(path, self.image_extensions, self.video_extensions)
        if media_type is None:
            raise ValueError(f"Unsupported media extension: {path.suffix}")
        modified_at = datetime.fromtimestamp(stat.st_mtime, self.timezone).isoformat(
            timespec="seconds"
        )
        return MediaMetadata(
            path=path,
            normalized_path=normalize_path(path),
            storage_type=detect_storage_type(path),
            media_type=media_type,
            extension=get_extension(path),
            size_bytes=stat.st_size,
            modified_at=modified_at,
        )
