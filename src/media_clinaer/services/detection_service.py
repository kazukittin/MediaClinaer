from __future__ import annotations

from dataclasses import dataclass

from media_clinaer.detection.duplicate_detector import DuplicateDetector
from media_clinaer.logging.events import EventType
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.storage.database import Database
from media_clinaer.storage.repositories import DetectionRepository


@dataclass(frozen=True)
class DetectionResult:
    scan_session_id: int
    duplicate_group_count: int
    duplicate_item_count: int


class DetectionService:
    def __init__(self, database: Database, logger: JsonLineLogger) -> None:
        self.database = database
        self.logger = logger

    def detect_duplicates(self, scan_session_id: int) -> DetectionResult:
        connection = self.database.connect()
        try:
            repository = DetectionRepository(connection)
            candidates = repository.list_hash_candidates(scan_session_id)
            groups = DuplicateDetector().detect(candidates)
            repository.replace_detection_groups(scan_session_id, groups)

            duplicate_item_count = sum(len(group.items) for group in groups)
            for group in groups:
                self.logger.info(
                    EventType.DUPLICATE_DETECTED,
                    "Duplicate group detected",
                    details={
                        "scan_session_id": scan_session_id,
                        "group_type": group.group_type,
                        "item_count": len(group.items),
                    },
                )
            return DetectionResult(
                scan_session_id=scan_session_id,
                duplicate_group_count=len(groups),
                duplicate_item_count=duplicate_item_count,
            )
        finally:
            connection.close()
