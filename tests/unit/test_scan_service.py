import sqlite3

from media_clinaer.config.models import AppConfig
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.services.scan_service import ScanService
from media_clinaer.storage.database import Database


def test_scan_service_saves_media_and_reuses_cache(tmp_path):
    app_config = AppConfig()
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "a.jpg").write_bytes(b"duplicate")
    (media_dir / "b.txt").write_text("ignored", encoding="utf-8")

    database = Database(tmp_path / "cache" / "media_clinaer.sqlite3")
    database.initialize()
    logger = JsonLineLogger(tmp_path / "logs" / "app.log")
    service = ScanService(database, app_config, logger)

    first = service.scan([str(media_dir)])
    second = service.scan([str(media_dir)])

    assert first.total_files == 1
    assert first.scanned_files == 1
    assert first.cache_used_count == 0
    assert second.cache_used_count == 1

    connection = sqlite3.connect(database.database_path)
    try:
        media_count = connection.execute("SELECT COUNT(*) FROM media_files").fetchone()[0]
        cache_count = connection.execute("SELECT COUNT(*) FROM analysis_cache").fetchone()[0]
    finally:
        connection.close()
    assert media_count == 2
    assert cache_count == 1
