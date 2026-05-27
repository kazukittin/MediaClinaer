from __future__ import annotations

from media_clinaer.models.media_file import MediaFileRecord, MediaMetadata
from media_clinaer.storage.repositories import AnalysisCacheRepository


class CacheService:
    def __init__(self, repository: AnalysisCacheRepository) -> None:
        self.repository = repository

    def build_from_cache(self, metadata: MediaMetadata) -> MediaFileRecord | None:
        row = self.repository.find_reusable(metadata)
        if row is None:
            return None
        if metadata.media_type == "image" and row["perceptual_hash"] is None:
            return None
        return MediaFileRecord(
            metadata=metadata,
            sha256=row["sha256"],
            perceptual_hash=row["perceptual_hash"],
            blur_score=row["blur_score"],
            cache_status="reused",
        )

    def save_success(self, record: MediaFileRecord) -> None:
        self.repository.upsert_success(record)

    def save_error(self, metadata: MediaMetadata, error: str) -> None:
        self.repository.upsert_error(metadata, error)
