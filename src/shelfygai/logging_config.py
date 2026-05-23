from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from shelfygai.constants import (
    APP_NAME,
    APP_VERSION,
    LOG_BACKUP_COUNT,
    LOG_FILENAME,
    LOG_MAX_BYTES,
    default_logs_dir,
)


class _AppMetadataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.app_name = APP_NAME
        record.app_version = APP_VERSION
        return True


class AppLogger:
    """Application logging facade with rotating file logs and metadata."""

    def __init__(self, log_dir: Path | None = None) -> None:
        self.log_dir = log_dir or default_logs_dir()
        self.log_path = self.log_dir / LOG_FILENAME
        self._configured = False

    def configure(self, *, debug_mode: bool = False) -> Path:
        level = logging.DEBUG if debug_mode else logging.INFO
        root = logging.getLogger()
        root.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(app_name)s %(app_version)s] "
            "[%(name)s] %(message)s"
        )

        self._remove_existing_app_handlers(root)

        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                self.log_path,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(_AppMetadataFilter())
            file_handler._shelfygai_handler = True  # type: ignore[attr-defined]
            root.addHandler(file_handler)
        except OSError:
            root.addHandler(logging.NullHandler())

        if sys.stderr is not None:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            console_handler.addFilter(_AppMetadataFilter())
            console_handler._shelfygai_handler = True  # type: ignore[attr-defined]
            root.addHandler(console_handler)

        self._configured = True
        logging.getLogger(__name__).debug("Logging configured at %s", self.log_path)
        return self.log_path

    def set_debug_mode(self, enabled: bool) -> None:
        level = logging.DEBUG if enabled else logging.INFO
        root = logging.getLogger()
        root.setLevel(level)
        for handler in root.handlers:
            if getattr(handler, "_shelfygai_handler", False):
                handler.setLevel(level)
        logging.getLogger(__name__).info("Debug mode %s", "enabled" if enabled else "disabled")

    def install_exception_hook(self) -> None:
        previous_hook = sys.excepthook

        def log_uncaught_exception(
            exc_type: type[BaseException],
            exc_value: BaseException,
            exc_traceback: TracebackType | None,
        ) -> None:
            logging.getLogger(__name__).critical(
                "Uncaught exception",
                exc_info=(exc_type, exc_value, exc_traceback),
            )
            previous_hook(exc_type, exc_value, exc_traceback)

        sys.excepthook = log_uncaught_exception

    def startup(self, *, debug_mode: bool = False) -> None:
        logging.getLogger(__name__).info(
            "Startup: %s %s, debug_mode=%s",
            APP_NAME,
            APP_VERSION,
            debug_mode,
        )

    def shutdown(self, *, exit_code: int = 0) -> None:
        logging.getLogger(__name__).info("Shutdown: exit_code=%s", exit_code)

    def exception(self, message: str) -> None:
        logging.getLogger(__name__).exception(message)

    def settings_changed(self, fields: list[str]) -> None:
        if fields:
            logging.getLogger(__name__).info("Settings changed: %s", ", ".join(fields))

    def window_operation(
        self,
        action: str,
        *,
        handle: int,
    ) -> None:
        logging.getLogger(__name__).info(
            "Window operation: action=%s handle=%s",
            action,
            handle,
        )

    def _remove_existing_app_handlers(self, root: logging.Logger) -> None:
        for handler in list(root.handlers):
            if getattr(handler, "_shelfygai_handler", False):
                root.removeHandler(handler)
                handler.close()


def configure_logging(*, debug_mode: bool = False) -> Path:
    return AppLogger().configure(debug_mode=debug_mode)
