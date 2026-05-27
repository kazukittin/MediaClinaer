from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from media_clinaer.config.models import AppConfig
from media_clinaer.detection.blurry_detector import BlurryDetector
from media_clinaer.detection.duplicate_detector import DuplicateDetector
from media_clinaer.detection.similar_detector import SimilarDetector
from media_clinaer.logging.events import EventType
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.storage.database import Database
from media_clinaer.storage.repositories import DetectionRepository


@dataclass(frozen=True)
class DetectionResult:
    scan_session_id: int
    duplicate_group_count: int
    duplicate_item_count: int
    similar_group_count: int = 0
    similar_item_count: int = 0
    blurry_group_count: int = 0
    blurry_item_count: int = 0


class DetectionService:
    def __init__(
        self,
        database: Database,
        logger: JsonLineLogger,
        config: AppConfig | None = None,
    ) -> None:
        self.database = database
        self.logger = logger
        self.config = config or AppConfig()

    def detect_duplicates(
        self,
        scan_session_id: int,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> DetectionResult:
        connection = self.database.connect()
        try:
            repository = DetectionRepository(connection)
            self._emit_progress(progress_callback, "重複候補を読み込んでいます。")
            candidates = repository.list_hash_candidates(scan_session_id)
            self._emit_progress(progress_callback, "完全重複を検出しています。")
            groups = DuplicateDetector().detect(candidates)
            similar_groups = []
            if self.config.detection.enable_similar_images:
                self._emit_progress(progress_callback, "類似画像候補を読み込んでいます。")
                similar_candidates = repository.list_similarity_candidates(scan_session_id)
                self._emit_progress(
                    progress_callback,
                    f"類似画像を検出しています。対象: {len(similar_candidates)} 件",
                )
                similar_groups = SimilarDetector(
                    self.config.detection.similar_image_hash_distance
                ).detect(similar_candidates)
                groups.extend(similar_groups)
            blurry_groups = []
            if self.config.detection.enable_blurry_images:
                self._emit_progress(progress_callback, "ブレ画像候補を読み込んでいます。")
                blur_candidates = repository.list_blur_candidates(scan_session_id)
                self._emit_progress(
                    progress_callback,
                    f"ブレ画像を検出しています。対象: {len(blur_candidates)} 件",
                )
                blurry_groups = BlurryDetector(
                    self.config.detection.blur_threshold
                ).detect(blur_candidates)
                groups.extend(blurry_groups)
            self._emit_progress(
                progress_callback,
                f"検出結果を保存しています。グループ: {len(groups)} 件",
            )
            repository.replace_detection_groups(scan_session_id, groups)

            duplicate_groups = [
                group
                for group in groups
                if group.group_type in {"duplicate_image", "duplicate_video"}
            ]
            duplicate_item_count = sum(len(group.items) for group in duplicate_groups)
            similar_item_count = sum(len(group.items) for group in similar_groups)
            blurry_item_count = sum(len(group.items) for group in blurry_groups)
            self.logger.info(
                EventType.DUPLICATE_DETECTED,
                "Duplicate detection completed",
                details={
                    "scan_session_id": scan_session_id,
                    "group_count": len(duplicate_groups),
                    "item_count": duplicate_item_count,
                },
            )
            self.logger.info(
                EventType.SIMILAR_DETECTED,
                "Similar image detection completed",
                details={
                    "scan_session_id": scan_session_id,
                    "group_count": len(similar_groups),
                    "item_count": similar_item_count,
                },
            )
            self.logger.info(
                EventType.BLURRY_DETECTED,
                "Blurry image detection completed",
                details={
                    "scan_session_id": scan_session_id,
                    "group_count": len(blurry_groups),
                    "item_count": blurry_item_count,
                },
            )
            return DetectionResult(
                scan_session_id=scan_session_id,
                duplicate_group_count=len(duplicate_groups),
                duplicate_item_count=duplicate_item_count,
                similar_group_count=len(similar_groups),
                similar_item_count=similar_item_count,
                blurry_group_count=len(blurry_groups),
                blurry_item_count=blurry_item_count,
            )
        finally:
            connection.close()

    def _emit_progress(
        self,
        progress_callback: Callable[[dict[str, object]], None] | None,
        message: str,
    ) -> None:
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "detecting",
                    "message": message,
                    "total_files": 0,
                    "processed_files": 0,
                    "cache_used_count": 0,
                    "error_count": 0,
                }
            )
