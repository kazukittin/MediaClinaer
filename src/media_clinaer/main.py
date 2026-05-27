from __future__ import annotations

from dataclasses import dataclass

from media_clinaer.app_context import AppContext
from media_clinaer.config.manager import ConfigManager
from media_clinaer.config.models import AppConfig
from media_clinaer.logging.events import EventType
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.storage.database import Database


@dataclass(frozen=True)
class Runtime:
    context: AppContext
    config_manager: ConfigManager
    config: AppConfig
    logger: JsonLineLogger
    database: Database


def bootstrap() -> Runtime:
    context = AppContext.discover()
    context.ensure_portable_dirs()
    context.verify_writable()

    config_manager = ConfigManager(context.config_path)
    config = config_manager.load_or_create()

    logger = JsonLineLogger(context.log_path)
    database = Database(context.database_path)
    database.initialize()

    logger.info(
        EventType.APP_STARTED,
        "Application bootstrap completed",
        details={"app_folder": str(context.app_folder)},
    )
    return Runtime(
        context=context,
        config_manager=config_manager,
        config=config,
        logger=logger,
        database=database,
    )


def main() -> int:
    runtime = bootstrap()
    from PySide6.QtWidgets import QApplication

    from media_clinaer.ui.main_window import MainWindow

    app = QApplication([])
    window = MainWindow(
        runtime.context,
        runtime.config_manager,
        runtime.config,
        runtime.database,
        runtime.logger,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
