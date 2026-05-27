from __future__ import annotations

import os
from pathlib import Path


IMAGE_MEDIA_TYPE = "image"
VIDEO_MEDIA_TYPE = "video"


def normalize_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def get_extension(path: Path) -> str:
    return path.suffix.lower()


def detect_media_type(
    path: Path,
    image_extensions: set[str],
    video_extensions: set[str],
) -> str | None:
    extension = get_extension(path)
    if extension in image_extensions:
        return IMAGE_MEDIA_TYPE
    if extension in video_extensions:
        return VIDEO_MEDIA_TYPE
    return None


def detect_storage_type(path: Path) -> str:
    raw = str(path)
    if raw.startswith("\\\\"):
        return "network"
    drive = path.drive.upper()
    if drive.startswith("\\\\"):
        return "network"
    return "local"
