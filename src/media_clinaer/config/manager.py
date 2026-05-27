from __future__ import annotations

import json
from pathlib import Path

from media_clinaer.config.models import AppConfig


class ConfigManager:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def load_or_create(self) -> AppConfig:
        if not self.config_path.exists():
            config = AppConfig()
            self.save(config)
            return config
        return self.load()

    def load(self) -> AppConfig:
        with self.config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return AppConfig.from_dict(data)

    def save(self, config: AppConfig) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as file:
            json.dump(config.to_dict(), file, ensure_ascii=False, indent=2)
            file.write("\n")
