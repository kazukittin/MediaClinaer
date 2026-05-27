import sqlite3
from datetime import datetime

from media_clinaer.config.models import AppConfig
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.services.detection_service import DetectionService
from media_clinaer.services.scan_service import ScanService
from media_clinaer.storage.database import Database
from tests.image_helpers import write_test_image


def test_detection_service_saves_duplicate_groups(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    write_test_image(media_dir / "a.jpg")
    write_test_image(media_dir / "b.jpg")
    write_test_image(media_dir / "c.jpg", variant=12)
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


def test_detection_service_saves_similar_image_groups(tmp_path):
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
        for index, phash in enumerate(["0000000000000000", "0000000000000001"]):
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
                    sha256,
                    perceptual_hash,
                    cache_status,
                    created_at
                )
                VALUES (?, ?, ?, 'local', 'image', '.jpg', 10, ?, ?, ?, 'fresh', ?)
                """,
                (
                    scan_session_id,
                    f"image_{index}.jpg",
                    f"image_{index}.jpg",
                    now,
                    f"sha-{index}",
                    phash,
                    now,
                ),
            )
        connection.commit()
    finally:
        connection.close()

    result = DetectionService(database, logger).detect_duplicates(int(scan_session_id))

    assert result.similar_group_count == 1
    assert result.similar_item_count == 2


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
                sha256,
                perceptual_hash,
                blur_score,
                cache_status,
                created_at
            )
            VALUES (?, 'blurry.jpg', 'blurry.jpg', 'local', 'image', '.jpg', 10,
                    ?, 'sha-blurry', '0000000000000000', 20.0, 'fresh', ?)
            """,
            (scan_session_id, now, now),
        )
        connection.commit()
    finally:
        connection.close()

    result = DetectionService(database, logger).detect_duplicates(int(scan_session_id))

    assert result.blurry_group_count == 1
    assert result.blurry_item_count == 1
