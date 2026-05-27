from media_clinaer.app_context import AppContext


def test_app_context_creates_portable_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_CLINAER_APP_FOLDER", str(tmp_path))

    context = AppContext.discover()
    context.ensure_portable_dirs()
    context.verify_writable()

    assert context.cache_dir.is_dir()
    assert context.logs_dir.is_dir()
    assert context.quarantine_dir.is_dir()
    assert context.config_path == tmp_path / "config.json"
    assert context.database_path == tmp_path / "cache" / "media_clinaer.sqlite3"
