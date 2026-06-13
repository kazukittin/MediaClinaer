from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from media_clinaer.config.models import AppConfig
from media_clinaer.detection.blurry_detector import BlurryDetector
from media_clinaer.logging.events import EventType
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.storage.database import Database
from media_clinaer.storage.repositories import DetectionRepository


@dataclass(frozen=True)
class DetectionResult:
    scan_session_id: int
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

    def detect_quality_issues(
        self,
        scan_session_id: int,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> DetectionResult:
        connection = self.database.connect()
        try:
            repository = DetectionRepository(connection)
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
            self._emit_progress(
                progress_callback,
                f"検出結果を保存しています。グループ: {len(blurry_groups)} 件",
            )
            repository.replace_detection_groups(scan_session_id, blurry_groups)

            blurry_item_count = sum(len(group.items) for group in blurry_groups)
            self.logger.info(
                EventType.BLURRY_DETECTED,
                "Quality issue detection completed",
                details={
                    "scan_session_id": scan_session_id,
                    "group_count": len(blurry_groups),
                    "item_count": blurry_item_count,
                },
            )
            return DetectionResult(
                scan_session_id=scan_session_id,
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
