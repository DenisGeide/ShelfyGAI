from __future__ import annotations

import logging
import os
import subprocess
import sys
import winreg
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from shelfygai.constants import APP_NAME

LOGGER = logging.getLogger(__name__)

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
SILENT_STARTUP_FLAG = "--silent-startup"


@dataclass(frozen=True, slots=True)
class StartupStatus:
    enabled: bool
    command: str | None = None
    executable_path: str | None = None
    path_valid: bool = False
    command_valid: bool = False
    silent_startup: bool = False
    error: str | None = None

    @property
    def healthy(self) -> bool:
        return self.enabled and self.path_valid and self.command_valid and self.error is None


def is_launch_with_windows_enabled() -> bool:
    status = get_startup_status()
    return status.enabled and status.path_valid


def get_startup_status() -> StartupStatus:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            command, value_type = winreg.QueryValueEx(key, APP_NAME)
    except FileNotFoundError:
        return StartupStatus(enabled=False)
    except OSError as exc:
        LOGGER.warning("Could not read startup entry: %s", exc)
        return StartupStatus(enabled=False, error=str(exc))

    if value_type not in {winreg.REG_SZ, winreg.REG_EXPAND_SZ} or not isinstance(command, str):
        return StartupStatus(
            enabled=True,
            command=str(command),
            error="Startup entry is not a string command.",
        )

    expanded_command = os.path.expandvars(command)
    args = _split_command(expanded_command)
    executable_path = args[0] if args else None
    path_valid = _is_valid_executable_path(executable_path)
    command_valid = path_valid and _is_shelfygai_startup_command(args)
    return StartupStatus(
        enabled=True,
        command=command,
        executable_path=executable_path,
        path_valid=path_valid,
        command_valid=command_valid,
        silent_startup=SILENT_STARTUP_FLAG in args,
    )


def set_launch_with_windows_enabled(enabled: bool, *, silent_startup: bool = False) -> None:
    if not enabled:
        remove_startup_entry()
        return

    command = _startup_command(silent_startup=silent_startup)
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY_PATH,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
    LOGGER.info("Startup entry enabled: silent_startup=%s", silent_startup)


def remove_startup_entry() -> bool:
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key, suppress(FileNotFoundError):
            winreg.DeleteValue(key, APP_NAME)
    except OSError as exc:
        LOGGER.warning("Could not remove startup entry: %s", exc)
        return False
    LOGGER.info("Startup entry removed")
    return True


def cleanup_startup_entry() -> bool:
    return remove_startup_entry()


def _startup_command(*, silent_startup: bool = False) -> str:
    executable = _validated_current_executable()
    if getattr(sys, "frozen", False):
        args = [str(executable)]
    else:
        args = [str(executable), "-m", "shelfygai"]
    if silent_startup:
        args.append(SILENT_STARTUP_FLAG)
    return subprocess.list2cmdline(args)


def _validated_current_executable() -> Path:
    executable = Path(sys.executable)
    # HKCU Run executes whatever path is stored, so validate before persisting it.
    if not _is_valid_executable_path(str(executable)):
        raise OSError(f"Current Python executable is not a valid startup target: {executable}")
    return executable


def _is_valid_executable_path(executable_path: str | None) -> bool:
    if not executable_path:
        return False
    try:
        path = Path(executable_path).expanduser()
        return path.exists() and path.is_file() and path.suffix.lower() == ".exe"
    except (OSError, ValueError):
        return False


def _is_shelfygai_startup_command(args: list[str]) -> bool:
    if len(args) >= 3 and args[1] == "-m" and args[2].lower() == "shelfygai":
        return True
    executable_name = Path(args[0]).name.lower() if args else ""
    return executable_name in {"shelfygai.exe", "shelfygai-gui.exe"}


def _split_command(command: str) -> list[str]:
    stripped = command.strip()
    if not stripped:
        return []
    if stripped.startswith('"'):
        closing_quote = stripped.find('"', 1)
        if closing_quote == -1:
            return []
        executable = stripped[1:closing_quote]
        remainder = stripped[closing_quote + 1 :].strip()
        args = _split_unquoted_args(remainder)
        return [executable, *args]
    parts = stripped.split(maxsplit=1)
    executable = parts[0]
    args = _split_unquoted_args(parts[1]) if len(parts) > 1 else []
    return [executable, *args]


def _split_unquoted_args(text: str) -> list[str]:
    if not text:
        return []
    return [part.strip('"') for part in text.split() if part]
