from __future__ import annotations

import sys

import pytest

startup = pytest.importorskip("shelfygai.platform.windows.startup")
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows startup only")


class FakeKey:
    def __enter__(self) -> FakeKey:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class FakeWinreg:
    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1
    REG_EXPAND_SZ = 2

    def __init__(self, value: object | None = None, value_type: int | None = None) -> None:
        self.value = value
        self.value_type = value_type if value_type is not None else self.REG_SZ
        self.deleted = False
        self.written_value: str | None = None

    def OpenKey(self, *_args: object) -> FakeKey:
        if self.value is None:
            raise FileNotFoundError
        return FakeKey()

    def QueryValueEx(self, _key: FakeKey, _name: str) -> tuple[object, int]:
        return self.value, self.value_type

    def CreateKeyEx(self, *_args: object) -> FakeKey:
        return FakeKey()

    def SetValueEx(
        self,
        _key: FakeKey,
        _name: str,
        _reserved: int,
        _value_type: int,
        value: str,
    ) -> None:
        self.written_value = value

    def DeleteValue(self, _key: FakeKey, _name: str) -> None:
        self.deleted = True


class FailingCreateWinreg(FakeWinreg):
    def CreateKeyEx(self, *_args: object) -> FakeKey:
        raise OSError("registry denied")


def test_startup_command_uses_module_launch_and_silent_flag() -> None:
    command = startup._startup_command(silent_startup=True)

    args = startup._split_command(command)

    assert args[1:] == ["-m", "shelfygai", "--silent-startup"]
    assert startup._is_valid_executable_path(args[0])


def test_startup_command_uses_packaged_exe_directly(monkeypatch) -> None:
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)

    command = startup._startup_command(silent_startup=True)
    args = startup._split_command(command)

    assert args == [sys.executable, "--silent-startup"]


def test_get_startup_status_detects_missing_entry(monkeypatch) -> None:
    monkeypatch.setattr(startup, "winreg", FakeWinreg())

    status = startup.get_startup_status()

    assert status.enabled is False
    assert status.healthy is False


def test_get_startup_status_detects_valid_entry(monkeypatch) -> None:
    command = startup._startup_command(silent_startup=True)
    monkeypatch.setattr(startup, "winreg", FakeWinreg(command))

    status = startup.get_startup_status()

    assert status.enabled is True
    assert status.path_valid is True
    assert status.command_valid is True
    assert status.silent_startup is True
    assert status.healthy is True


def test_get_startup_status_detects_invalid_path(monkeypatch) -> None:
    monkeypatch.setattr(
        startup,
        "winreg",
        FakeWinreg('"C:\\Missing\\shelfygai.exe" -m shelfygai'),
    )

    status = startup.get_startup_status()

    assert status.enabled is True
    assert status.path_valid is False
    assert status.healthy is False


def test_get_startup_status_rejects_non_string_registry_value(monkeypatch) -> None:
    monkeypatch.setattr(startup, "winreg", FakeWinreg(123, FakeWinreg.REG_SZ))

    status = startup.get_startup_status()

    assert status.enabled is True
    assert status.command == "123"
    assert status.error == "Startup entry is not a string command."
    assert status.healthy is False


def test_set_launch_writes_hkcu_run_command(monkeypatch) -> None:
    fake_winreg = FakeWinreg()
    monkeypatch.setattr(startup, "winreg", fake_winreg)

    startup.set_launch_with_windows_enabled(True, silent_startup=True)

    assert fake_winreg.written_value is not None
    assert "--silent-startup" in fake_winreg.written_value


def test_remove_startup_entry_is_safe_when_missing(monkeypatch) -> None:
    fake_winreg = FakeWinreg()
    monkeypatch.setattr(startup, "winreg", fake_winreg)

    assert startup.remove_startup_entry() is True
    assert fake_winreg.deleted is True


def test_remove_startup_entry_reports_registry_errors(monkeypatch) -> None:
    monkeypatch.setattr(startup, "winreg", FailingCreateWinreg())

    assert startup.remove_startup_entry() is False
