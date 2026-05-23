from __future__ import annotations

import faulthandler
import json
import logging
import os
import platform
import sys
import threading
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from shelfygai.constants import (
    APP_NAME,
    APP_VERSION,
    default_crashes_dir,
    default_recovery_state_path,
)
from shelfygai.performance import memory_usage_mb
from shelfygai.settings.settings_manager import current_boot_id

LOGGER = logging.getLogger(__name__)
RecoveryRecord = Mapping[str, Any]
RecoveryCallback = Callable[[RecoveryRecord], bool]
RestoreCallback = Callable[[], Mapping[str, Any]]
RECOVERY_STATUS_RESTORED = "restored"
RECOVERY_STATUS_SKIPPED = "skipped"
RECOVERY_STATUS_FAILED = "failed"
RECOVERY_REASON_RESTORED = "restored"
RECOVERY_REASON_STALE_BOOT = "stale_boot"
RECOVERY_REASON_NOT_FOUND = "not_found"
RECOVERY_REASON_INVALID_RECORD = "invalid_record"
RECOVERY_REASON_ERROR = "error"


@dataclass(frozen=True, slots=True)
class RecoveryWindowResult:
    handle: int
    title: str
    process_id: int
    process_name: str
    status: str
    reason: str
    detail: str | None = None

    @property
    def restored(self) -> bool:
        return self.status == RECOVERY_STATUS_RESTORED

    @property
    def skipped(self) -> bool:
        return self.status == RECOVERY_STATUS_SKIPPED

    @property
    def failed(self) -> bool:
        return self.status == RECOVERY_STATUS_FAILED

    def as_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "title": self.title,
            "process_id": self.process_id,
            "process_name": self.process_name,
            "status": self.status,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class DetailedRecoveryResult:
    items: tuple[RecoveryWindowResult, ...] = ()
    stale_state: bool = False
    source_path: str | None = None

    @property
    def attempted(self) -> int:
        return len(self.items)

    @property
    def restored(self) -> int:
        return sum(1 for item in self.items if item.restored)

    @property
    def failed(self) -> int:
        return sum(1 for item in self.items if item.failed)

    @property
    def skipped(self) -> int:
        return sum(1 for item in self.items if item.skipped)

    @property
    def has_work(self) -> bool:
        return bool(self.items)

    def as_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "restored": self.restored,
            "failed": self.failed,
            "skipped": self.skipped,
            "stale_state": self.stale_state,
            "source_path": self.source_path,
            "items": [item.as_dict() for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class PreviousRecoveryResult:
    attempted: int = 0
    restored: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def has_work(self) -> bool:
        return self.attempted > 0

    def as_dict(self) -> dict[str, int]:
        return {
            "attempted": self.attempted,
            "restored": self.restored,
            "failed": self.failed,
            "skipped": self.skipped,
        }


class EmergencyRecoveryStore:
    """Durable state for windows that must be recoverable after a crash."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_recovery_state_path()

    def save(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        reason: str = "managed windows changed",
    ) -> bool:
        normalized_records = [record for record in records if _is_valid_record(record)]
        if not normalized_records:
            return self.clear(reason=reason)

        payload = {
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "boot_id": current_boot_id(),
            "reason": reason,
            "updated_at": _utc_now(),
            "managed_windows": normalized_records,
        }
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            temp_path.replace(self.path)
        except OSError:
            LOGGER.exception("Could not write emergency recovery state: %s", self.path)
            return False

        LOGGER.info(
            "Emergency recovery state saved: records=%s reason=%s",
            len(normalized_records),
            reason,
        )
        return True

    def load(self) -> dict[str, Any] | None:
        try:
            if not self.path.exists():
                return None
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            LOGGER.exception("Emergency recovery state is unreadable; ignoring it")
            return None
        if not isinstance(payload, dict):
            LOGGER.warning("Emergency recovery state has invalid shape; ignoring it")
            return None
        return payload

    def exists(self) -> bool:
        try:
            return self.path.exists()
        except OSError:
            LOGGER.exception("Could not inspect emergency recovery state: %s", self.path)
            return False

    def records_for_current_boot(self) -> list[dict[str, Any]]:
        payload = self.load()
        if payload is None:
            return []
        if payload.get("boot_id") != current_boot_id():
            LOGGER.info("Ignoring stale emergency recovery state from a previous boot")
            return []
        return [
            dict(record)
            for record in _records_from_payload(payload)
            if isinstance(record, dict) and _is_valid_record(record)
        ]

    def clear(self, *, reason: str = "no managed windows") -> bool:
        try:
            if self.path.exists():
                self.path.unlink()
                LOGGER.info("Emergency recovery state cleared: %s", reason)
        except OSError:
            LOGGER.exception("Could not clear emergency recovery state: %s", self.path)
            return False
        return True


class CrashReporter:
    """Writes structured crash diagnostics next to the rotating application log."""

    def __init__(self, crashes_dir: Path | None = None) -> None:
        self.crashes_dir = crashes_dir or default_crashes_dir()

    def write_report(
        self,
        *,
        source: str,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
        recovery_state: Mapping[str, Any] | None = None,
        restore_result: Mapping[str, Any] | None = None,
    ) -> Path | None:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        report_path = self.crashes_dir / f"crash-{timestamp}-{os.getpid()}.json"
        payload = {
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "boot_id": current_boot_id(),
            "created_at": _utc_now(),
            "source": source,
            "exception": {
                "type": f"{exc_type.__module__}.{exc_type.__name__}",
                "message": str(exc_value),
                "traceback": "".join(
                    traceback.format_exception(exc_type, exc_value, exc_traceback)
                ),
            },
            "diagnostics": self._diagnostics(),
            "recovery_state": recovery_state,
            "restore_result": restore_result,
        }
        try:
            self.crashes_dir.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            latest_path = self.crashes_dir / "latest_crash.json"
            latest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        except OSError:
            LOGGER.exception("Could not write crash report: %s", report_path)
            return None

        LOGGER.critical("Crash report written: %s", report_path)
        return report_path

    def _diagnostics(self) -> dict[str, Any]:
        return {
            "argv": list(sys.argv),
            "executable": sys.executable,
            "memory_mb": memory_usage_mb(),
            "os": platform.platform(),
            "pid": os.getpid(),
            "python": platform.python_version(),
            "thread": threading.current_thread().name,
        }


class CrashManager:
    """Coordinates global exception handling and emergency window restore."""

    def __init__(
        self,
        *,
        recovery_store: EmergencyRecoveryStore | None = None,
        reporter: CrashReporter | None = None,
    ) -> None:
        self.recovery_store = recovery_store or EmergencyRecoveryStore()
        self.reporter = reporter or CrashReporter()
        self._restore_callback: RestoreCallback | None = None
        self._handled_exception_ids: set[int] = set()
        self._previous_excepthook = sys.excepthook
        self._previous_threading_excepthook = getattr(threading, "excepthook", None)
        self._faulthandler_file = None

    def install_global_handlers(self) -> None:
        sys.excepthook = self._handle_sys_exception
        if hasattr(threading, "excepthook"):
            threading.excepthook = self._handle_threading_exception
        self._enable_faulthandler()
        LOGGER.debug("Global crash handlers installed")

    def set_restore_callback(self, callback: RestoreCallback | None) -> None:
        self._restore_callback = callback

    def recover_previous_session(self, restore_record: RecoveryCallback) -> PreviousRecoveryResult:
        detailed = self.recover_previous_session_detailed(restore_record)
        result = PreviousRecoveryResult(
            attempted=detailed.attempted,
            restored=detailed.restored,
            failed=detailed.failed,
            skipped=detailed.skipped,
        )
        return result

    def recover_previous_session_detailed(
        self,
        restore_record: RecoveryCallback,
    ) -> DetailedRecoveryResult:
        payload = self.recovery_store.load()
        if payload is None:
            if self.recovery_store.exists():
                self.recovery_store.clear(reason="unreadable emergency recovery state")
            return DetailedRecoveryResult(source_path=str(self.recovery_store.path))

        records = _records_from_payload(payload)
        if not records:
            LOGGER.info("Emergency recovery state had no window records")
            self.recovery_store.clear(reason="empty emergency recovery state")
            return DetailedRecoveryResult(source_path=str(self.recovery_store.path))

        saved_boot_id = payload.get("boot_id")
        active_boot_id = current_boot_id()
        LOGGER.warning(
            "Emergency recovery state found: path=%s records=%s saved_boot=%s current_boot=%s",
            self.recovery_store.path,
            len(records),
            saved_boot_id,
            active_boot_id,
        )

        if saved_boot_id != active_boot_id:
            items = tuple(
                _recovery_result_from_record(
                    record,
                    status=RECOVERY_STATUS_SKIPPED,
                    reason=RECOVERY_REASON_STALE_BOOT,
                )
                for record in records
            )
            result = DetailedRecoveryResult(
                items=items,
                stale_state=True,
                source_path=str(self.recovery_store.path),
            )
            LOGGER.warning(
                "Ignoring stale emergency recovery state from a previous boot: %s",
                result.as_dict(),
            )
            self.recovery_store.clear(reason="stale emergency recovery state")
            return result

        items: list[RecoveryWindowResult] = []
        for record in records:
            if not _is_valid_record(record):
                item = _recovery_result_from_record(
                    record,
                    status=RECOVERY_STATUS_SKIPPED,
                    reason=RECOVERY_REASON_INVALID_RECORD,
                )
                items.append(item)
                LOGGER.warning("Skipping invalid emergency recovery record: %s", item.as_dict())
                continue

            try:
                if restore_record(record):
                    item = _recovery_result_from_record(
                        record,
                        status=RECOVERY_STATUS_RESTORED,
                        reason=RECOVERY_REASON_RESTORED,
                    )
                    LOGGER.warning(
                        "Emergency recovery restored window: handle=%s pid=%s title=%r",
                        item.handle,
                        item.process_id,
                        item.title,
                    )
                else:
                    item = _recovery_result_from_record(
                        record,
                        status=RECOVERY_STATUS_SKIPPED,
                        reason=RECOVERY_REASON_NOT_FOUND,
                    )
                    LOGGER.info(
                        "Emergency recovery skipped missing or stale window: "
                        "handle=%s pid=%s title=%r",
                        item.handle,
                        item.process_id,
                        item.title,
                    )
            except Exception as exc:
                item = _recovery_result_from_record(
                    record,
                    status=RECOVERY_STATUS_FAILED,
                    reason=RECOVERY_REASON_ERROR,
                    detail=str(exc),
                )
                LOGGER.exception(
                    "Emergency recovery restore failed: handle=%s pid=%s",
                    item.handle,
                    item.process_id,
                )
            items.append(item)

        result = DetailedRecoveryResult(
            items=tuple(items),
            source_path=str(self.recovery_store.path),
        )
        if result.failed == 0:
            self.recovery_store.clear(reason="previous session recovered")
        else:
            LOGGER.warning("Emergency recovery state kept for a future retry: %s", result)
        LOGGER.warning("Emergency recovery result: %s", result.as_dict())
        return result

    def handle_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
        *,
        source: str,
    ) -> Mapping[str, Any]:
        exception_id = id(exc_value)
        if exception_id in self._handled_exception_ids:
            return {"already_handled": True}
        self._handled_exception_ids.add(exception_id)

        LOGGER.critical(
            "Fatal exception captured by crash manager: source=%s",
            source,
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        recovery_state = self.recovery_store.load()
        restore_result = self._restore_managed_windows()
        report_path = self.reporter.write_report(
            source=source,
            exc_type=exc_type,
            exc_value=exc_value,
            exc_traceback=exc_traceback,
            recovery_state=recovery_state,
            restore_result=restore_result,
        )
        result = dict(restore_result)
        result["report_path"] = str(report_path) if report_path is not None else None
        return result

    def close(self) -> None:
        if self._faulthandler_file is not None:
            try:
                if faulthandler.is_enabled():
                    faulthandler.disable()
                self._faulthandler_file.close()
            except OSError:
                LOGGER.debug("Could not close faulthandler crash log", exc_info=True)
            self._faulthandler_file = None

    def _restore_managed_windows(self) -> Mapping[str, Any]:
        if self._restore_callback is None:
            return {"attempted": False, "reason": "no restore callback registered"}
        try:
            result = dict(self._restore_callback())
            result.setdefault("attempted", True)
            return result
        except Exception as exc:
            LOGGER.exception("Fatal-crash restore callback failed")
            return {"attempted": True, "restored": 0, "failed": True, "error": str(exc)}

    def _handle_sys_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        self.handle_exception(exc_type, exc_value, exc_traceback, source="sys.excepthook")
        self._previous_excepthook(exc_type, exc_value, exc_traceback)

    def _handle_threading_exception(self, args: threading.ExceptHookArgs) -> None:
        self.handle_exception(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            source=f"threading.excepthook:{args.thread.name if args.thread else 'unknown'}",
        )
        if self._previous_threading_excepthook is not None:
            self._previous_threading_excepthook(args)

    def _enable_faulthandler(self) -> None:
        try:
            self.reporter.crashes_dir.mkdir(parents=True, exist_ok=True)
            path = self.reporter.crashes_dir / "faulthandler.log"
            self._faulthandler_file = path.open("a", encoding="utf-8")
            faulthandler.enable(file=self._faulthandler_file, all_threads=True)
        except OSError:
            LOGGER.exception("Could not enable faulthandler crash log")


def _is_valid_record(record: Mapping[str, Any]) -> bool:
    return (
        isinstance(record.get("boot_id"), str)
        and isinstance(record.get("handle"), int)
        and isinstance(record.get("process_id"), int)
        and isinstance(record.get("process_name"), str)
        and isinstance(record.get("title"), str)
        and isinstance(record.get("original_extended_style"), int)
    )


def _records_from_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("managed_windows", [])
    if not isinstance(records, list):
        return []
    return [dict(record) for record in records if isinstance(record, dict)]


def _recovery_result_from_record(
    record: Mapping[str, Any],
    *,
    status: str,
    reason: str,
    detail: str | None = None,
) -> RecoveryWindowResult:
    handle = record.get("handle")
    process_id = record.get("process_id")
    title = record.get("title")
    process_name = record.get("process_name")
    return RecoveryWindowResult(
        handle=handle if isinstance(handle, int) and not isinstance(handle, bool) else 0,
        title=title if isinstance(title, str) else "",
        process_id=(
            process_id
            if isinstance(process_id, int) and not isinstance(process_id, bool)
            else 0
        ),
        process_name=process_name if isinstance(process_name, str) else "",
        status=status,
        reason=reason,
        detail=detail,
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
