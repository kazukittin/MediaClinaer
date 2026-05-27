from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PathConfig:
    cache_dir: str = "cache"
    logs_dir: str = "logs"
    quarantine_dir: str = "quarantine"


@dataclass
class ScanConfig:
    target_paths: list[str] = field(default_factory=list)
    image_extensions: list[str] = field(
        default_factory=lambda: [".jpg", ".jpeg", ".png", ".webp", ".bmp"]
    )
    video_extensions: list[str] = field(
        default_factory=lambda: [".mp4", ".mov", ".avi", ".mkv"]
    )
    include_subdirectories: bool = True
    follow_symlinks: bool = False


@dataclass
class DetectionConfig:
    enable_duplicate_images: bool = True
    enable_similar_images: bool = True
    enable_blurry_images: bool = True
    enable_duplicate_videos: bool = True
    similar_image_hash_distance: int = 8
    blur_threshold: float = 100.0


@dataclass
class CacheConfig:
    enabled: bool = True
    retention_days: int | None = None


@dataclass
class QuarantineConfig:
    preserve_relative_path: bool = True
    on_name_collision: str = "append_hash"
    verify_copy_before_delete: bool = True


@dataclass
class UiConfig:
    theme: str = "system"
    last_opened_result_session_id: int | None = None


@dataclass
class AppConfig:
    version: int = 1
    paths: PathConfig = field(default_factory=PathConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    quarantine: QuarantineConfig = field(default_factory=QuarantineConfig)
    ui: UiConfig = field(default_factory=UiConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls(
            version=int(data.get("version", 1)),
            paths=PathConfig(**data.get("paths", {})),
            scan=ScanConfig(**data.get("scan", {})),
            detection=DetectionConfig(**data.get("detection", {})),
            cache=CacheConfig(**data.get("cache", {})),
            quarantine=QuarantineConfig(**data.get("quarantine", {})),
            ui=UiConfig(**data.get("ui", {})),
        )
