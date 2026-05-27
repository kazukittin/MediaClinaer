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


@dataclass(frozen=True)
class DetectionItemDetail:
    detection_group_item_id: int
    media_file_id: int
    path: str
    media_type: str
    size_bytes: int
    modified_at: str
    sha256: str | None
    perceptual_hash: str | None
    blur_score: float | None
    recommended_action: str
    selected_by_default: bool


@dataclass(frozen=True)
class DetectionGroupDetail:
    summary: DetectionGroupSummary
    items: list[DetectionItemDetail]


class ResultService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_detection_group_summaries(
        self,
        scan_session_id: int,
        max_groups: int | None = None,
    ) -> list[DetectionGroupSummary]:
        connection = self.database.connect()
        try:
            rows = DetectionRepository(connection).list_group_summaries(
                scan_session_id,
                limit=max_groups,
            )
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

    def list_detection_group_details(
        self,
        scan_session_id: int,
        max_groups: int | None = None,
    ) -> list[DetectionGroupDetail]:
        connection = self.database.connect()
        try:
            repository = DetectionRepository(connection)
            summaries = [
                DetectionGroupSummary(
                    group_id=int(row["id"]),
                    group_type=str(row["group_type"]),
                    confidence=float(row["confidence"]),
                    reason=str(row["reason"]),
                    item_count=int(row["item_count"]),
                    selected_count=int(row["selected_count"] or 0),
                )
                for row in repository.list_group_summaries(
                    scan_session_id,
                    limit=max_groups,
                )
            ]
            items_by_group = {
                summary.group_id: [
                    DetectionItemDetail(
                        detection_group_item_id=int(row["detection_group_item_id"]),
                        media_file_id=int(row["media_file_id"]),
                        path=str(row["path"]),
                        media_type=str(row["media_type"]),
                        size_bytes=int(row["size_bytes"]),
                        modified_at=str(row["modified_at"]),
                        sha256=(
                            str(row["sha256"]) if row["sha256"] is not None else None
                        ),
                        perceptual_hash=(
                            str(row["perceptual_hash"])
                            if row["perceptual_hash"] is not None
                            else None
                        ),
                        blur_score=(
                            float(row["blur_score"])
                            if row["blur_score"] is not None
                            else None
                        ),
                        recommended_action=str(row["recommended_action"]),
                        selected_by_default=bool(row["selected_by_default"]),
                    )
                    for row in repository.list_group_items(summary.group_id)
                ]
                for summary in summaries
            }
            return [
                DetectionGroupDetail(
                    summary=summary,
                    items=items_by_group.get(summary.group_id, []),
                )
                for summary in summaries
            ]
        finally:
            connection.close()

    def set_detection_item_selected(
        self,
        detection_group_item_id: int,
        selected: bool,
    ) -> None:
        connection = self.database.connect()
        try:
            DetectionRepository(connection).update_group_item_selection(
                detection_group_item_id,
                selected,
            )
        finally:
            connection.close()
