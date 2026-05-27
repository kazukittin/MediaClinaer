import json

from media_clinaer.logging.events import EventType
from media_clinaer.logging.logger import JsonLineLogger


def test_json_line_logger_writes_one_json_object_per_line(tmp_path):
    log_path = tmp_path / "logs" / "app.log"
    logger = JsonLineLogger(log_path)

    logger.info(EventType.APP_STARTED, "Started", details={"answer": 42})

    lines = log_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    assert len(lines) == 1
    assert record["level"] == "INFO"
    assert record["event"] == "app_started"
    assert record["details"] == {"answer": 42}
