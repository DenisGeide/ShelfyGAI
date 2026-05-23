from __future__ import annotations

import json

from shelfygai.constants import default_recovery_state_path
from shelfygai.crash import CrashManager, CrashReporter, EmergencyRecoveryStore
from shelfygai.settings.settings_manager import current_boot_id


def _record(handle: int = 100) -> dict[str, object]:
    return {
        "boot_id": current_boot_id(),
        "handle": handle,
        "title": "Editor",
        "process_id": 42,
        "process_name": "editor.exe",
        "executable_path": None,
        "group_id": "ungrouped",
        "hidden_at": "2026-05-23T00:00:00+00:00",
        "original_extended_style": 262400,
        "managed_extended_style": 128,
    }


def _pinned_record(handle: int = 300) -> dict[str, object]:
    return {
        "boot_id": current_boot_id(),
        "handle": handle,
        "title": "Pinned",
        "process_id": 43,
        "process_name": "pinned.exe",
    }


def test_emergency_recovery_store_round_trip(tmp_path) -> None:
    path = tmp_path / "recovery.json"
    store = EmergencyRecoveryStore(path)

    assert store.save([_record()], reason="window hidden") is True

    records = store.records_for_current_boot()
    assert len(records) == 1
    assert records[0]["handle"] == 100
    assert json.loads(path.read_text(encoding="utf-8"))["reason"] == "window hidden"


def test_emergency_recovery_store_filters_invalid_records(tmp_path) -> None:
    path = tmp_path / "recovery.json"
    store = EmergencyRecoveryStore(path)

    assert store.save([_record(100), {"handle": "not-an-int"}], reason="mixed records") is True

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["managed_windows"]) == 1
    assert payload["managed_windows"][0]["handle"] == 100


def test_emergency_recovery_store_keeps_pinned_records(tmp_path) -> None:
    path = tmp_path / "recovery.json"
    store = EmergencyRecoveryStore(path)

    assert store.save([], pinned_records=[_pinned_record()], reason="window pinned") is True

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["managed_windows"] == []
    assert payload["pinned_windows"][0]["handle"] == 300


def test_emergency_recovery_store_ignores_corrupted_json(tmp_path) -> None:
    path = tmp_path / "recovery.json"
    path.write_text("{not-json", encoding="utf-8")

    assert EmergencyRecoveryStore(path).records_for_current_boot() == []


def test_default_recovery_path_uses_recovery_json(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert default_recovery_state_path() == tmp_path / "ShelfyGAI" / "recovery.json"


def test_recover_previous_session_restores_and_clears_state(tmp_path) -> None:
    path = tmp_path / "recovery.json"
    store = EmergencyRecoveryStore(path)
    store.save([_record(100), _record(200)], reason="fatal crash")
    manager = CrashManager(
        recovery_store=store,
        reporter=CrashReporter(tmp_path / "crashes"),
    )
    restored_handles: list[int] = []

    result = manager.recover_previous_session(
        lambda record: restored_handles.append(int(record["handle"])) is None or True
    )

    assert result.as_dict() == {"attempted": 2, "restored": 2, "failed": 0, "skipped": 0}
    assert restored_handles == [100, 200]
    assert not path.exists()


def test_recover_previous_session_keeps_pending_pinned_records(tmp_path) -> None:
    path = tmp_path / "recovery.json"
    store = EmergencyRecoveryStore(path)
    store.save([_record(100)], pinned_records=[_pinned_record()], reason="fatal crash")
    manager = CrashManager(
        recovery_store=store,
        reporter=CrashReporter(tmp_path / "crashes"),
    )

    result = manager.recover_previous_session_detailed(lambda _record: True)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert result.restored == 1
    assert payload["managed_windows"] == []
    assert payload["pinned_windows"][0]["handle"] == 300


def test_recover_previous_pinned_unpins_and_clears_state(tmp_path) -> None:
    path = tmp_path / "recovery.json"
    store = EmergencyRecoveryStore(path)
    store.save([], pinned_records=[_pinned_record()], reason="fatal crash")
    manager = CrashManager(
        recovery_store=store,
        reporter=CrashReporter(tmp_path / "crashes"),
    )
    unpinned_handles: list[int] = []

    result = manager.recover_previous_pinned_detailed(
        lambda record: unpinned_handles.append(int(record["handle"])) is None or True
    )

    assert result.restored == 1
    assert unpinned_handles == [300]
    assert not path.exists()


def test_detailed_recovery_reports_skipped_and_failed_windows(tmp_path) -> None:
    path = tmp_path / "recovery.json"
    store = EmergencyRecoveryStore(path)
    store.save([_record(100), _record(200), _record(300)], reason="fatal crash")
    manager = CrashManager(
        recovery_store=store,
        reporter=CrashReporter(tmp_path / "crashes"),
    )

    def restore(record: dict[str, object]) -> bool:
        if record["handle"] == 300:
            raise RuntimeError("native restore failed")
        return record["handle"] == 100

    result = manager.recover_previous_session_detailed(restore)

    assert result.restored == 1
    assert result.skipped == 1
    assert result.failed == 1
    assert [item.status for item in result.items] == ["restored", "skipped", "failed"]
    assert path.exists()


def test_detailed_recovery_clears_stale_boot_state(tmp_path) -> None:
    path = tmp_path / "recovery.json"
    payload = {
        "app_name": "ShelfyGAI",
        "app_version": "0.1.0",
        "boot_id": "previous-boot",
        "managed_windows": [_record(100)],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    manager = CrashManager(
        recovery_store=EmergencyRecoveryStore(path),
        reporter=CrashReporter(tmp_path / "crashes"),
    )

    result = manager.recover_previous_session_detailed(
        lambda _record: (_ for _ in ()).throw(AssertionError("should not restore"))
    )

    assert result.stale_state is True
    assert result.skipped == 1
    assert result.items[0].reason == "stale_boot"
    assert not path.exists()


def test_crash_manager_writes_report_and_calls_restore_once(tmp_path) -> None:
    store = EmergencyRecoveryStore(tmp_path / "recovery.json")
    reporter = CrashReporter(tmp_path / "crashes")
    manager = CrashManager(recovery_store=store, reporter=reporter)
    restore_calls = 0

    def restore_callback() -> dict[str, object]:
        nonlocal restore_calls
        restore_calls += 1
        return {"attempted": True, "restored": 1, "skipped": 0}

    manager.set_restore_callback(restore_callback)
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        result = manager.handle_exception(
            type(exc),
            exc,
            exc.__traceback__,
            source="test",
        )
        duplicate = manager.handle_exception(
            type(exc),
            exc,
            exc.__traceback__,
            source="test",
        )

    reports = list((tmp_path / "crashes").glob("crash-*.json"))
    assert restore_calls == 1
    assert result["restored"] == 1
    assert duplicate == {"already_handled": True}
    assert len(reports) == 1
    assert "RuntimeError" in reports[0].read_text(encoding="utf-8")
