import json
import stat
import sqlite3

from media_clinaer.config.models import AppConfig
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.services.detection_service import DetectionService
from media_clinaer.services.quarantine_service import QuarantineService
from media_clinaer.services.scan_service import ScanService
from media_clinaer.storage.database import Database
from tests.image_helpers import write_test_image


def test_quarantine_service_moves_selected_duplicate_candidates(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    keep_file = media_dir / "a.jpg"
    duplicate_file = media_dir / "b.jpg"
    write_test_image(keep_file)
    write_test_image(duplicate_file)

    database = Database(tmp_path / "cache" / "media_clinaer.sqlite3")
    database.initialize()
    logger = JsonLineLogger(tmp_path / "logs" / "app.log")
    scan_result = ScanService(database, AppConfig(), logger).scan([str(media_dir)])
    DetectionService(database, logger).detect_duplicates(scan_result.session_id)

    result = QuarantineService(
        database,
        logger,
        tmp_path / "quarantine",
    ).quarantine_selected_defaults(scan_result.session_id)

    assert result.total_count == 1
    assert result.completed_count == 1
    assert result.failed_count == 0
    assert keep_file.exists()
    assert not duplicate_file.exists()
    assert result.manifest_path.exists()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest[0]["status"] == "completed"
    assert result.manifest_path.parent.name

    connection = sqlite3.connect(database.database_path)
    try:
        rows = connection.execute(
            "SELECT status, original_path, quarantined_path FROM quarantine_records"
        ).fetchall()
    finally:
        connection.close()

    assert rows[0][0] == "completed"
    assert rows[0][1] == str(duplicate_file)
    assert rows[0][2].endswith("b.jpg")


def test_quarantine_service_deletes_readonly_duplicate_after_copy(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    keep_file = media_dir / "a.jpg"
    duplicate_file = media_dir / "b.jpg"
    write_test_image(keep_file)
    write_test_image(duplicate_file)
    duplicate_file.chmod(stat.S_IREAD)

    database = Database(tmp_path / "cache" / "media_clinaer.sqlite3")
    database.initialize()
    logger = JsonLineLogger(tmp_path / "logs" / "app.log")
    scan_result = ScanService(database, AppConfig(), logger).scan([str(media_dir)])
    DetectionService(database, logger).detect_duplicates(scan_result.session_id)

    result = QuarantineService(
        database,
        logger,
        tmp_path / "quarantine",
    ).quarantine_selected_defaults(scan_result.session_id)

    assert result.completed_count == 1
    assert not duplicate_file.exists()
