from __future__ import annotations

import os
from pathlib import Path

from shelfygai import __version__

APP_NAME = "ShelfyGAI"
APP_ID = "shelfygai"
APP_ORGANIZATION = "ShelfyGAI"
APP_VERSION = __version__
APP_DESCRIPTION = "A local-first Windows taskbar organization utility."
GITHUB_REPOSITORY_URL = "https://github.com/shelfygai/shelfygai"
SETTINGS_SCHEMA_VERSION = 1
SETTINGS_FILENAME = "settings.json"
RECOVERY_STATE_FILENAME = "recovery.json"
LOGS_DIRNAME = "logs"
CRASHES_DIRNAME = "crashes"
LOG_FILENAME = "shelfygai.log"
LOG_MAX_BYTES = 1_048_576
LOG_BACKUP_COUNT = 5


def package_root() -> Path:
    return Path(__file__).resolve().parent


def resource_path(name: str) -> Path:
    return package_root() / "resources" / name


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / "AppData" / "Roaming" / APP_NAME


def default_settings_path() -> Path:
    return app_data_dir() / SETTINGS_FILENAME


def default_recovery_state_path() -> Path:
    return app_data_dir() / RECOVERY_STATE_FILENAME


def default_logs_dir() -> Path:
    return app_data_dir() / LOGS_DIRNAME


def default_crashes_dir() -> Path:
    return default_logs_dir() / CRASHES_DIRNAME
