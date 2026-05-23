from __future__ import annotations

import logging
import sys
from time import perf_counter

from PySide6.QtWidgets import QDialog

from shelfygai.app import build_application, build_main_window
from shelfygai.constants import resource_path
from shelfygai.crash import CrashManager, DetailedRecoveryResult
from shelfygai.i18n import Translator, set_language
from shelfygai.logging_config import AppLogger
from shelfygai.performance import elapsed_ms, log_performance, memory_usage_mb
from shelfygai.settings.settings_manager import SettingsManager
from shelfygai.ui.onboarding_dialog import SettingsDialog

LOGGER = logging.getLogger(__name__)
SILENT_STARTUP_FLAG = "--silent-startup"
PACKAGING_SMOKE_TEST_FLAG = "--packaging-smoke-test"


def run(argv: list[str] | None = None) -> int:
    startup_started = perf_counter()
    args = list(sys.argv if argv is None else argv)
    silent_startup = SILENT_STARTUP_FLAG in args
    packaging_smoke_test = PACKAGING_SMOKE_TEST_FLAG in args
    qt_args = [
        argument
        for argument in args
        if argument not in {SILENT_STARTUP_FLAG, PACKAGING_SMOKE_TEST_FLAG}
    ]
    app_logger = AppLogger()
    app_logger.configure()
    crash_manager = CrashManager()
    crash_manager.install_global_handlers()
    exit_code = 0

    try:
        settings_started = perf_counter()
        settings_manager = SettingsManager()
        settings = settings_manager.load()
        set_language(settings.language)
        app_logger.set_debug_mode(settings.debug_mode)
        app_logger.startup(debug_mode=settings.debug_mode)
        log_performance(
            "settings.load",
            elapsed_ms=elapsed_ms(settings_started),
            memory_mb=memory_usage_mb(),
        )
        qt_started = perf_counter()
        qt_app = build_application(qt_args, settings)
        log_performance(
            "qt.application.build",
            elapsed_ms=elapsed_ms(qt_started),
            memory_mb=memory_usage_mb(),
        )
        if packaging_smoke_test:
            _run_packaging_smoke_test(settings_manager, app_logger)
            return 0

        recovery_result = _show_recovery_screen_if_needed(crash_manager)
        if (
            recovery_result is not None
            and recovery_result.has_work
            and recovery_result.failed == 0
        ):
            settings.managed_windows = []
            settings_manager.save(settings, reason="previous emergency recovery completed")

        if not settings.onboarding_completed:
            onboarding_started = perf_counter()
            onboarding = SettingsDialog(settings_manager, settings, first_launch=True)
            if onboarding.exec() != QDialog.DialogCode.Accepted:
                LOGGER.info("First-launch onboarding was cancelled")
                return 0
            settings = onboarding.settings
            set_language(settings.language)
            app_logger.set_debug_mode(settings.debug_mode)
            silent_startup = False
            log_performance(
                "onboarding.complete",
                elapsed_ms=elapsed_ms(onboarding_started),
                memory_mb=memory_usage_mb(),
            )

        window_started = perf_counter()
        main_window = build_main_window(settings_manager, settings)
        crash_manager.set_restore_callback(main_window.emergency_restore_for_crash)
        log_performance(
            "main_window.build",
            elapsed_ms=elapsed_ms(window_started),
            memory_mb=memory_usage_mb(),
        )
        if silent_startup and main_window.start_hidden_in_tray():
            LOGGER.info("Application started silently in the system tray")
        else:
            main_window.show()
            if not silent_startup:
                main_window.show_startup_notification()

        log_performance(
            "startup.ui_ready",
            elapsed_ms=elapsed_ms(startup_started),
            memory_mb=memory_usage_mb(),
            silent_startup=silent_startup,
        )
        exit_code = qt_app.exec()
        return exit_code
    except Exception:
        app_logger.exception("Fatal application error")
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_type is not None and exc_value is not None:
            crash_manager.handle_exception(
                exc_type,
                exc_value,
                exc_traceback,
                source="run",
            )
        raise
    finally:
        log_performance(
            "shutdown",
            elapsed_ms=elapsed_ms(startup_started),
            memory_mb=memory_usage_mb(),
            exit_code=exit_code,
        )
        app_logger.shutdown(exit_code=exit_code)
        crash_manager.close()


def _show_recovery_screen_if_needed(
    crash_manager: CrashManager,
) -> DetailedRecoveryResult | None:
    if sys.platform != "win32":
        return None
    if not crash_manager.recovery_store.exists():
        return None
    try:
        from shelfygai.platform.windows.window_gateway import WindowsWindowGateway
        from shelfygai.ui.recovery_dialog import RecoveryDialog

        gateway = WindowsWindowGateway()
        dialog = RecoveryDialog(
            crash_manager,
            gateway.restore_from_recovery_record,
            gateway.unpin_from_recovery_record,
        )
        dialog.exec()
        result = dialog.result_data
    except Exception:
        LOGGER.exception("Previous-session emergency recovery screen failed")
        return None
    if result.has_work:
        LOGGER.warning(
            "Previous-session emergency recovery completed: %s",
            result.as_dict(),
        )
    return result


def _run_packaging_smoke_test(
    settings_manager: SettingsManager,
    app_logger: AppLogger,
) -> None:
    icon_path = resource_path("app_icon.svg")
    if not icon_path.is_file():
        raise RuntimeError(f"Packaged icon resource is missing: {icon_path}")

    english = Translator("en").tr("action.save")
    russian = Translator("ru").tr("action.save")
    if english == "action.save" or russian == "action.save" or english == russian:
        raise RuntimeError("Packaged translations did not load correctly")

    if not settings_manager.path.is_file():
        settings_manager.save(settings_manager.settings, reason="packaging smoke test")
    if not settings_manager.path.is_file():
        raise RuntimeError(f"Settings file was not created: {settings_manager.path}")

    LOGGER.info(
        "Packaging smoke test completed: icon=%s settings=%s log=%s",
        icon_path,
        settings_manager.path,
        app_logger.log_path,
    )
    for handler in logging.getLogger().handlers:
        handler.flush()
    if not app_logger.log_path.is_file():
        raise RuntimeError(f"Log file was not created: {app_logger.log_path}")


if __name__ == "__main__":
    raise SystemExit(run())
