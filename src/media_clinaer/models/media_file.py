from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaMetadata:
    path: Path
    normalized_path: str
    storage_type: str
    media_type: str
    extension: str
    size_bytes: int
    modified_at: str


@dataclass(frozen=True)
class MediaFileRecord:
    metadata: MediaMetadata
    sha256: str | None
    perceptual_hash: str | None
    blur_score: float | None
    cache_status: str
    scan_error: str | None = None
