from media_clinaer.config.models import AppConfig
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.services.detection_service import DetectionService
from media_clinaer.services.result_service import ResultService
from media_clinaer.services.scan_service import ScanService
from media_clinaer.storage.database import Database
from tests.image_helpers import write_blurry_test_image, write_test_image


def test_result_service_returns_detection_group_details(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    write_test_image(media_dir / "a.jpg")
    write_test_image(media_dir / "b.jpg")
    write_blurry_test_image(media_dir / "blurry.jpg")

    database = Database(tmp_path / "cache" / "media_clinaer.sqlite3")
    database.initialize()
    logger = JsonLineLogger(tmp_path / "logs" / "app.log")
    config = AppConfig()
    scan_result = ScanService(database, config, logger).scan([str(media_dir)])
    DetectionService(database, logger, config).detect_duplicates(scan_result.session_id)

    details = ResultService(database).list_detection_group_details(scan_result.session_id)

    assert details
    assert any(detail.summary.group_type == "duplicate_image" for detail in details)
    assert any(item.path.endswith("b.jpg") for detail in details for item in detail.items)
    assert any(item.selected_by_default for detail in details for item in detail.items)
    assert any(item.blur_score is not None for detail in details for item in detail.items)


def test_result_service_updates_detection_item_selection(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    write_test_image(media_dir / "a.jpg")
    write_test_image(media_dir / "b.jpg")

    database = Database(tmp_path / "cache" / "media_clinaer.sqlite3")
    database.initialize()
    logger = JsonLineLogger(tmp_path / "logs" / "app.log")
    config = AppConfig()
    scan_result = ScanService(database, config, logger).scan([str(media_dir)])
    DetectionService(database, logger, config).detect_duplicates(scan_result.session_id)

    service = ResultService(database)
    details = service.list_detection_group_details(scan_result.session_id)
    selected_item = next(item for detail in details for item in detail.items if item.selected_by_default)

    service.set_detection_item_selected(selected_item.detection_group_item_id, False)

    updated_details = service.list_detection_group_details(scan_result.session_id)
    updated_item = next(
        item
        for detail in updated_details
        for item in detail.items
        if item.detection_group_item_id == selected_item.detection_group_item_id
    )
    assert updated_item.selected_by_default is False
