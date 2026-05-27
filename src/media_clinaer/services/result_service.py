from __future__ import annotations

from dataclasses import dataclass

from media_clinaer.storage.database import Database
from media_clinaer.storage.repositories import DetectionRepository


@dataclass(frozen=True)
class DetectionGroupSummary:
    group_id: int
    group_type: str
    confidence: float
    reason: str
    item_count: int
    selected_count: int


class ResultService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_detection_group_summaries(
        self,
        scan_session_id: int,
    ) -> list[DetectionGroupSummary]:
        connection = self.database.connect()
        try:
            rows = DetectionRepository(connection).list_group_summaries(scan_session_id)
            return [
                DetectionGroupSummary(
                    group_id=int(row["id"]),
                    group_type=str(row["group_type"]),
                    confidence=float(row["confidence"]),
                    reason=str(row["reason"]),
                    item_count=int(row["item_count"]),
                    selected_count=int(row["selected_count"] or 0),
                )
                for row in rows
            ]
        finally:
            connection.close()
