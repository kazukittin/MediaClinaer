from media_clinaer.config.manager import ConfigManager


def test_config_manager_creates_default_config(tmp_path):
    manager = ConfigManager(tmp_path / "config.json")

    config = manager.load_or_create()
    loaded = manager.load()

    assert config.scan.image_extensions[0] == ".jpg"
    assert loaded.cache.retention_days is None
    assert loaded.quarantine.verify_copy_before_delete is True
