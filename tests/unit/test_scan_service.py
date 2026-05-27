import sqlite3

from media_clinaer.config.models import AppConfig
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.services.scan_service import ScanService
from media_clinaer.storage.database import Database
from tests.image_helpers import write_test_image


def test_scan_service_saves_media_and_reuses_cache(tmp_path):
    app_config = AppConfig()
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    write_test_image(media_dir / "a.jpg")
    (media_dir / "b.txt").write_text("ignored", encoding="utf-8")

    database = Database(tmp_path / "cache" / "media_clinaer.sqlite3")
    database.initialize()
    logger = JsonLineLogger(tmp_path / "logs" / "app.log")
    service = ScanService(database, app_config, logger)
    progress_events = []

    first = service.scan([str(media_dir)], progress_callback=progress_events.append)
    second = service.scan([str(media_dir)])

    assert first.total_files == 1
    assert first.scanned_files == 1
    assert first.cache_used_count == 0
    assert second.cache_used_count == 1
    assert progress_events[0].phase == "collecting"
    assert any(event.phase == "scanning" for event in progress_events)
    assert progress_events[-1].processed_files == 1

    connection = sqlite3.connect(database.database_path)
    try:
        media_count = connection.execute("SELECT COUNT(*) FROM media_files").fetchone()[0]
        cache_count = connection.execute("SELECT COUNT(*) FROM analysis_cache").fetchone()[0]
        perceptual_hash = connection.execute(
            "SELECT perceptual_hash FROM analysis_cache"
        ).fetchone()[0]
        blur_score = connection.execute("SELECT blur_score FROM analysis_cache").fetchone()[0]
    finally:
        connection.close()
    assert media_count == 2
    assert cache_count == 1
    assert perceptual_hash is not None
    assert blur_score is not None
