from __future__ import annotations

from dataclasses import dataclass

from media_clinaer.config.models import AppConfig
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

    def detect_duplicates(self, scan_session_id: int) -> DetectionResult:
        connection = self.database.connect()
        try:
            repository = DetectionRepository(connection)
            candidates = repository.list_hash_candidates(scan_session_id)
            groups = DuplicateDetector().detect(candidates)
            similar_groups = []
            if self.config.detection.enable_similar_images:
                similar_candidates = repository.list_similarity_candidates(scan_session_id)
                similar_groups = SimilarDetector(
                    self.config.detection.similar_image_hash_distance
                ).detect(similar_candidates)
                groups.extend(similar_groups)
            repository.replace_detection_groups(scan_session_id, groups)

            duplicate_groups = [
                group
                for group in groups
                if group.group_type in {"duplicate_image", "duplicate_video"}
            ]
            duplicate_item_count = sum(len(group.items) for group in duplicate_groups)
            similar_item_count = sum(len(group.items) for group in similar_groups)
            for group in duplicate_groups:
                self.logger.info(
                    EventType.DUPLICATE_DETECTED,
                    "Duplicate group detected",
                    details={
                        "scan_session_id": scan_session_id,
                        "group_type": group.group_type,
                        "item_count": len(group.items),
                    },
                )
            for group in similar_groups:
                self.logger.info(
                    EventType.SIMILAR_DETECTED,
                    "Similar image group detected",
                    details={
                        "scan_session_id": scan_session_id,
                        "item_count": len(group.items),
                    },
                )
            return DetectionResult(
                scan_session_id=scan_session_id,
                duplicate_group_count=len(duplicate_groups),
                duplicate_item_count=duplicate_item_count,
                similar_group_count=len(similar_groups),
                similar_item_count=similar_item_count,
            )
        finally:
            connection.close()
