import sqlite3

from media_clinaer.storage.database import Database


def test_database_initializes_schema(tmp_path):
    database = Database(tmp_path / "cache" / "media_clinaer.sqlite3")

    database.initialize()

    with sqlite3.connect(database.database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "scan_sessions" in tables
    assert "media_files" in tables
    assert "analysis_cache" in tables
    assert "quarantine_records" in tables
