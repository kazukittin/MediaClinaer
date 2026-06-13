import sqlite3
from datetime import datetime

from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.services.detection_service import DetectionService
from media_clinaer.storage.database import Database


def test_detection_service_saves_blurry_image_groups(tmp_path):
    database = Database(tmp_path / "cache" / "media_clinaer.sqlite3")
    database.initialize()
    logger = JsonLineLogger(tmp_path / "logs" / "app.log")
    connection = sqlite3.connect(database.database_path)
    try:
        now = datetime.now().isoformat(timespec="seconds")
        scan_session_id = connection.execute(
            """
            INSERT INTO scan_sessions (started_at, status, target_paths_json)
            VALUES (?, 'completed', '[]')
            """,
            (now,),
        ).lastrowid
        connection.execute(
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
                blur_score,
                cache_status,
                created_at
            )
            VALUES (?, 'blurry.jpg', 'blurry.jpg', 'local', 'image', '.jpg', 10,
                    ?, 20.0, 'fresh', ?)
            """,
            (scan_session_id, now, now),
        )
        connection.commit()
    finally:
        connection.close()

    result = DetectionService(database, logger).detect_quality_issues(
        int(scan_session_id)
    )

    assert result.blurry_group_count == 1
    assert result.blurry_item_count == 1

    connection = sqlite3.connect(database.database_path)
    try:
        selected = connection.execute(
            """
            SELECT dgi.selected_by_default
            FROM detection_group_items dgi
            INNER JOIN detection_groups dg ON dg.id = dgi.detection_group_id
            WHERE dg.group_type = 'blurry_image'
            """
        ).fetchone()[0]
    finally:
        connection.close()
    assert selected == 1
