from __future__ import annotations

import logging
import sys

from shelfygai.constants import APP_VERSION, LOG_FILENAME
from shelfygai.logging_config import AppLogger


def test_app_logger_writes_rotating_log_with_metadata(tmp_path) -> None:
    app_logger = AppLogger(tmp_path)

    log_path = app_logger.configure(debug_mode=True)
    app_logger.startup(debug_mode=True)
    logging.getLogger("shelfygai.test").debug("debug detail")
    app_logger.shutdown(exit_code=0)

    for handler in logging.getLogger().handlers:
        handler.flush()

    contents = log_path.read_text(encoding="utf-8")

    assert log_path == tmp_path / LOG_FILENAME
    assert APP_VERSION in contents
    assert "Startup" in contents
    assert "Shutdown" in contents
    assert "debug detail" in contents


def test_app_logger_handles_windowed_runtime_without_stderr(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sys, "stderr", None)
    app_logger = AppLogger(tmp_path)

    log_path = app_logger.configure()
    logging.getLogger("shelfygai.test").info("file only")

    for handler in logging.getLogger().handlers:
        handler.flush()

    assert "file only" in log_path.read_text(encoding="utf-8")
