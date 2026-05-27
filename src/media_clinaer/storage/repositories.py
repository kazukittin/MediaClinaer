from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from media_clinaer.models.detection_group import DetectionCandidate, DetectionGroup
from media_clinaer.models.media_file import MediaFileRecord, MediaMetadata
from media_clinaer.models.quarantine_record import QuarantineCandidate, QuarantineOutcome
from media_clinaer.models.scan_session import ScanSession


class ScanRepository:
    def __init__(self, connection: sqlite3.Connection, timezone: str = "Asia/Tokyo") -> None:
        self.connection = connection
        self.timezone = ZoneInfo(timezone)

    def create_session(self, target_paths: list[str]) -> ScanSession:
        now = self._now()
        cursor = self.connection.execute(
            """
            INSERT INTO scan_sessions (started_at, status, target_paths_json)
            VALUES (?, ?, ?)
            """,
            (now, "running", json.dumps(target_paths, ensure_ascii=False)),
        )
        self.connection.commit()
        return ScanSession(id=int(cursor.lastrowid), status="running")

    def finish_session(
        self,
        session_id: int,
        *,
        status: str,
        total_files: int,
        scanned_files: int,
        cache_used_count: int,
        error_count: int,
    ) -> None:
        self.connection.execute(
            """
            UPDATE scan_sessions
            SET finished_at = ?,
                status = ?,
                total_files = ?,
                scanned_files = ?,
                cache_used_count = ?,
                error_count = ?
            WHERE id = ?
            """,
            (
                self._now(),
                status,
                total_files,
                scanned_files,
                cache_used_count,
                error_count,
                session_id,
            ),
        )
        self.connection.commit()

    def insert_media_file(self, session_id: int, record: MediaFileRecord) -> int:
        metadata = record.metadata
        cursor = self.connection.execute(
            """
            INSERT INTO media_files (
                scan_session_id,
                path,
                normalized_path,
                storage_type,
                media_type,
                extension,
                size_bytes,
                modified_at,
                sha256,
                perceptual_hash,
                blur_score,
                cache_status,
                scan_error,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                str(metadata.path),
                metadata.normalized_path,
                metadata.storage_type,
                metadata.media_type,
                metadata.extension,
                metadata.size_bytes,
                metadata.modified_at,
                record.sha256,
                record.perceptual_hash,
                record.blur_score,
                record.cache_status,
                record.scan_error,
                self._now(),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def _now(self) -> str:
        return datetime.now(self.timezone).isoformat(timespec="seconds")


class AnalysisCacheRepository:
    def __init__(self, connection: sqlite3.Connection, timezone: str = "Asia/Tokyo") -> None:
        self.connection = connection
        self.timezone = ZoneInfo(timezone)

    def find_reusable(self, metadata: MediaMetadata) -> sqlite3.Row | None:
        self.connection.row_factory = sqlite3.Row
        cursor = self.connection.execute(
            """
            SELECT *
            FROM analysis_cache
            WHERE normalized_path = ?
              AND size_bytes = ?
              AND modified_at = ?
              AND last_error IS NULL
            """,
            (metadata.normalized_path, metadata.size_bytes, metadata.modified_at),
        )
        return cursor.fetchone()

    def upsert_success(self, record: MediaFileRecord) -> None:
        metadata = record.metadata
        self.connection.execute(
            """
            INSERT INTO analysis_cache (
                path,
                normalized_path,
                size_bytes,
                modified_at,
                media_type,
                sha256,
                perceptual_hash,
                blur_score,
                last_scanned_at,
                last_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(path) DO UPDATE SET
                normalized_path = excluded.normalized_path,
                size_bytes = excluded.size_bytes,
                modified_at = excluded.modified_at,
                media_type = excluded.media_type,
                sha256 = excluded.sha256,
                perceptual_hash = excluded.perceptual_hash,
                blur_score = excluded.blur_score,
                last_scanned_at = excluded.last_scanned_at,
                last_error = NULL
            """,
            (
                str(metadata.path),
                metadata.normalized_path,
                metadata.size_bytes,
                metadata.modified_at,
                metadata.media_type,
                record.sha256,
                record.perceptual_hash,
                record.blur_score,
                self._now(),
            ),
        )
        self.connection.commit()

    def upsert_error(self, metadata: MediaMetadata, error: str) -> None:
        self.connection.execute(
            """
            INSERT INTO analysis_cache (
                path,
                normalized_path,
                size_bytes,
                modified_at,
                media_type,
                last_scanned_at,
                last_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                normalized_path = excluded.normalized_path,
                size_bytes = excluded.size_bytes,
                modified_at = excluded.modified_at,
                media_type = excluded.media_type,
                last_scanned_at = excluded.last_scanned_at,
                last_error = excluded.last_error
            """,
            (
                str(metadata.path),
                metadata.normalized_path,
                metadata.size_bytes,
                metadata.modified_at,
                metadata.media_type,
                self._now(),
                error,
            ),
        )
        self.connection.commit()

    def _now(self) -> str:
        return datetime.now(self.timezone).isoformat(timespec="seconds")


class DetectionRepository:
    def __init__(self, connection: sqlite3.Connection, timezone: str = "Asia/Tokyo") -> None:
        self.connection = connection
        self.timezone = ZoneInfo(timezone)

    def list_hash_candidates(self, scan_session_id: int) -> list[DetectionCandidate]:
        self.connection.row_factory = sqlite3.Row
        rows = self.connection.execute(
            """
            SELECT id, path, media_type, sha256, size_bytes, perceptual_hash, blur_score
            FROM media_files
            WHERE scan_session_id = ?
              AND sha256 IS NOT NULL
              AND scan_error IS NULL
            """,
            (scan_session_id,),
        ).fetchall()
        return [
            DetectionCandidate(
                media_file_id=int(row["id"]),
                path=str(row["path"]),
                media_type=str(row["media_type"]),
                sha256=str(row["sha256"]),
                size_bytes=int(row["size_bytes"]),
                perceptual_hash=(
                    str(row["perceptual_hash"])
                    if row["perceptual_hash"] is not None
                    else None
                ),
                blur_score=(
                    float(row["blur_score"]) if row["blur_score"] is not None else None
                ),
            )
            for row in rows
        ]

    def list_similarity_candidates(self, scan_session_id: int) -> list[DetectionCandidate]:
        self.connection.row_factory = sqlite3.Row
        rows = self.connection.execute(
            """
            SELECT id, path, media_type, sha256, size_bytes, perceptual_hash, blur_score
            FROM media_files
            WHERE scan_session_id = ?
              AND media_type = 'image'
              AND sha256 IS NOT NULL
              AND perceptual_hash IS NOT NULL
              AND scan_error IS NULL
            """,
            (scan_session_id,),
        ).fetchall()
        return [
            DetectionCandidate(
                media_file_id=int(row["id"]),
                path=str(row["path"]),
                media_type=str(row["media_type"]),
                sha256=str(row["sha256"]),
                size_bytes=int(row["size_bytes"]),
                perceptual_hash=str(row["perceptual_hash"]),
                blur_score=(
                    float(row["blur_score"]) if row["blur_score"] is not None else None
                ),
            )
            for row in rows
        ]

    def list_blur_candidates(self, scan_session_id: int) -> list[DetectionCandidate]:
        self.connection.row_factory = sqlite3.Row
        rows = self.connection.execute(
            """
            SELECT id, path, media_type, sha256, size_bytes, perceptual_hash, blur_score
            FROM media_files
            WHERE scan_session_id = ?
              AND media_type = 'image'
              AND sha256 IS NOT NULL
              AND blur_score IS NOT NULL
              AND scan_error IS NULL
            """,
            (scan_session_id,),
        ).fetchall()
        return [
            DetectionCandidate(
                media_file_id=int(row["id"]),
                path=str(row["path"]),
                media_type=str(row["media_type"]),
                sha256=str(row["sha256"]),
                size_bytes=int(row["size_bytes"]),
                perceptual_hash=(
                    str(row["perceptual_hash"])
                    if row["perceptual_hash"] is not None
                    else None
                ),
                blur_score=float(row["blur_score"]),
            )
            for row in rows
        ]

    def replace_detection_groups(
        self,
        scan_session_id: int,
        groups: list[DetectionGroup],
    ) -> None:
        existing_ids = [
            row[0]
            for row in self.connection.execute(
                "SELECT id FROM detection_groups WHERE scan_session_id = ?",
                (scan_session_id,),
            ).fetchall()
        ]
        if existing_ids:
            placeholders = ",".join("?" for _ in existing_ids)
            self.connection.execute(
                f"DELETE FROM detection_group_items WHERE detection_group_id IN ({placeholders})",
                existing_ids,
            )
        self.connection.execute(
            "DELETE FROM detection_groups WHERE scan_session_id = ?",
            (scan_session_id,),
        )

        for group in groups:
            cursor = self.connection.execute(
                """
                INSERT INTO detection_groups (
                    scan_session_id,
                    group_type,
                    confidence,
                    reason,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    scan_session_id,
                    group.group_type,
                    group.confidence,
                    group.reason,
                    self._now(),
                ),
            )
            group_id = int(cursor.lastrowid)
            for index, item in enumerate(group.items):
                should_select = group.group_type == "blurry_image" or index > 0
                self.connection.execute(
                    """
                    INSERT INTO detection_group_items (
                        detection_group_id,
                        media_file_id,
                        recommended_action,
                        selected_by_default
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        group_id,
                        item.media_file_id,
                        "quarantine_candidate" if should_select else "keep",
                        1 if should_select else 0,
                    ),
                )

        self.connection.execute(
            """
            UPDATE scan_sessions
            SET detection_group_count = ?
            WHERE id = ?
            """,
            (len(groups), scan_session_id),
        )
        self.connection.commit()

    def list_group_summaries(self, scan_session_id: int) -> list[sqlite3.Row]:
        self.connection.row_factory = sqlite3.Row
        return self.connection.execute(
            """
            SELECT
                dg.id,
                dg.group_type,
                dg.confidence,
                dg.reason,
                COUNT(dgi.id) AS item_count,
                SUM(dgi.selected_by_default) AS selected_count
            FROM detection_groups dg
            INNER JOIN detection_group_items dgi
                ON dgi.detection_group_id = dg.id
            WHERE dg.scan_session_id = ?
            GROUP BY dg.id, dg.group_type, dg.confidence, dg.reason
            ORDER BY dg.group_type, dg.id
            """,
            (scan_session_id,),
        ).fetchall()

    def list_group_items(self, detection_group_id: int) -> list[sqlite3.Row]:
        self.connection.row_factory = sqlite3.Row
        return self.connection.execute(
            """
            SELECT
                dgi.id AS detection_group_item_id,
                mf.id AS media_file_id,
                mf.path,
                mf.media_type,
                mf.size_bytes,
                mf.modified_at,
                mf.sha256,
                mf.perceptual_hash,
                mf.blur_score,
                dgi.recommended_action,
                dgi.selected_by_default
            FROM detection_group_items dgi
            INNER JOIN media_files mf ON mf.id = dgi.media_file_id
            WHERE dgi.detection_group_id = ?
            ORDER BY dgi.selected_by_default DESC, mf.path
            """,
            (detection_group_id,),
        ).fetchall()

    def update_group_item_selection(
        self,
        detection_group_item_id: int,
        selected: bool,
    ) -> None:
        self.connection.execute(
            """
            UPDATE detection_group_items
            SET selected_by_default = ?
            WHERE id = ?
            """,
            (1 if selected else 0, detection_group_item_id),
        )
        self.connection.commit()

    def _now(self) -> str:
        return datetime.now(self.timezone).isoformat(timespec="seconds")


class QuarantineRepository:
    def __init__(self, connection: sqlite3.Connection, timezone: str = "Asia/Tokyo") -> None:
        self.connection = connection
        self.timezone = ZoneInfo(timezone)

    def list_selected_candidates(self, scan_session_id: int) -> list[QuarantineCandidate]:
        self.connection.row_factory = sqlite3.Row
        rows = self.connection.execute(
            """
            SELECT
                mf.id,
                mf.path,
                mf.normalized_path,
                mf.size_bytes,
                mf.modified_at,
                mf.storage_type
            FROM detection_group_items dgi
            INNER JOIN detection_groups dg ON dg.id = dgi.detection_group_id
            INNER JOIN media_files mf ON mf.id = dgi.media_file_id
            WHERE dg.scan_session_id = ?
              AND dgi.selected_by_default = 1
            ORDER BY dg.id, dgi.id
            """,
            (scan_session_id,),
        ).fetchall()
        return [
            QuarantineCandidate(
                media_file_id=int(row["id"]),
                original_path=Path(str(row["path"])),
                original_normalized_path=str(row["normalized_path"]),
                original_size_bytes=int(row["size_bytes"]),
                original_modified_at=str(row["modified_at"]),
                source_storage_type=str(row["storage_type"]),
            )
            for row in rows
        ]

    def insert_outcome(self, outcome: QuarantineOutcome) -> int:
        candidate = outcome.plan.candidate
        cursor = self.connection.execute(
            """
            INSERT INTO quarantine_records (
                media_file_id,
                original_path,
                original_normalized_path,
                quarantined_path,
                original_size_bytes,
                original_modified_at,
                source_storage_type,
                status,
                quarantined_at,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.media_file_id,
                str(candidate.original_path),
                candidate.original_normalized_path,
                str(outcome.plan.quarantined_path),
                candidate.original_size_bytes,
                candidate.original_modified_at,
                candidate.source_storage_type,
                outcome.status,
                self._now(),
                outcome.error_message,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def _now(self) -> str:
        return datetime.now(self.timezone).isoformat(timespec="seconds")
