import sqlite3

from media_clinaer.config.models import AppConfig
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.services.detection_service import DetectionService
from media_clinaer.services.scan_service import ScanService
from media_clinaer.storage.database import Database


def test_detection_service_saves_duplicate_groups(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "a.jpg").write_bytes(b"same image")
    (media_dir / "b.jpg").write_bytes(b"same image")
    (media_dir / "c.jpg").write_bytes(b"different")
    (media_dir / "a.mp4").write_bytes(b"same video")
    (media_dir / "b.mp4").write_bytes(b"same video")

    database = Database(tmp_path / "cache" / "media_clinaer.sqlite3")
    database.initialize()
    logger = JsonLineLogger(tmp_path / "logs" / "app.log")
    scan_result = ScanService(database, AppConfig(), logger).scan([str(media_dir)])

    detection_result = DetectionService(database, logger).detect_duplicates(
        scan_result.session_id
    )

    assert detection_result.duplicate_group_count == 2
    assert detection_result.duplicate_item_count == 4

    connection = sqlite3.connect(database.database_path)
    try:
        groups = connection.execute(
            "SELECT group_type FROM detection_groups ORDER BY group_type"
        ).fetchall()
        selected_defaults = connection.execute(
            "SELECT selected_by_default FROM detection_group_items ORDER BY id"
        ).fetchall()
    finally:
        connection.close()

    assert [row[0] for row in groups] == ["duplicate_image", "duplicate_video"]
    assert [row[0] for row in selected_defaults].count(1) == 2
