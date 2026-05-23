from __future__ import annotations

import ctypes
import logging
import os
from collections.abc import Sequence
from ctypes import wintypes
from dataclasses import dataclass
from time import perf_counter

import psutil
import win32con
import win32gui
import win32process

from shelfygai.core.errors import WindowNotFoundError, WindowOperationError
from shelfygai.core.models import WindowInfo
from shelfygai.i18n import tr
from shelfygai.performance import elapsed_ms, log_performance

LOGGER = logging.getLogger(__name__)

DWMWA_CLOAKED = 14
ERROR_ACCESS_DENIED = 5
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TOKEN_ELEVATION_CLASS = 20
SYSTEM_SHELL_WINDOW_CLASSES = {
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Progman",
    "WorkerW",
    "NotifyIconOverflowWindow",
    "DV2ControlHost",
    "Windows.UI.Core.CoreWindow",
}
START_MENU_WINDOW_CLASSES = {
    "Start",
    "StartMenu",
    "StartMenuExperienceHost",
    "Windows.UI.Input.InputSite.WindowClass",
    "Windows.UI.Composition.DesktopWindowContentBridge",
    "XamlExplorerHostIslandWindow",
}
CRITICAL_SYSTEM_PROCESS_NAMES = {
    "credentialuibroker.exe",
    "lockapp.exe",
    "logonui.exe",
    "runtimebroker.exe",
    "searchapp.exe",
    "searchhost.exe",
    "searchui.exe",
    "securityhealthsystray.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "systemsettings.exe",
    "taskmgr.exe",
    "textinputhost.exe",
}
STYLE_REFRESH_FLAGS = (
    win32con.SWP_NOMOVE
    | win32con.SWP_NOSIZE
    | win32con.SWP_NOZORDER
    | win32con.SWP_NOACTIVATE
    | win32con.SWP_FRAMECHANGED
)
TOPMOST_REFRESH_FLAGS = (
    win32con.SWP_NOMOVE
    | win32con.SWP_NOSIZE
    | win32con.SWP_NOACTIVATE
    | win32con.SWP_FRAMECHANGED
)


class TokenElevation(ctypes.Structure):
    _fields_ = [("TokenIsElevated", wintypes.DWORD)]


@dataclass(frozen=True, slots=True)
class ManagedWindowStyle:
    handle: int
    original_extended_style: int
    managed_extended_style: int
    process_id: int
    process_name: str
    class_name: str


@dataclass(frozen=True, slots=True)
class PinnedWindowStyle:
    handle: int
    original_style: int
    original_extended_style: int
    pinned_extended_style: int
    process_id: int
    process_name: str
    class_name: str
    prevent_minimize: bool = False


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    process_id: int
    process_name: str
    executable_path: str | None = None


class WindowsWindowGateway:
    def __init__(self) -> None:
        self._own_process_id = os.getpid()
        self._dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self._shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        self._configure_ctypes_signatures()
        self._own_process_elevated = self._is_current_process_elevated()
        self._managed_styles: dict[int, ManagedWindowStyle] = {}
        self._pinned_styles: dict[int, PinnedWindowStyle] = {}

    def _configure_ctypes_signatures(self) -> None:
        self._kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        self._advapi32.OpenProcessToken.restype = wintypes.BOOL
        self._advapi32.GetTokenInformation.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._advapi32.GetTokenInformation.restype = wintypes.BOOL

    def list_windows(self) -> Sequence[WindowInfo]:
        started = perf_counter()
        handles: list[int] = []
        process_cache: dict[int, ProcessInfo] = {}

        def callback(hwnd: int, _extra: int) -> bool:
            try:
                if self._is_candidate_window(hwnd, process_cache):
                    handles.append(hwnd)
            except Exception:
                LOGGER.debug("Skipping window during enumeration: handle=%s", hwnd, exc_info=True)
            return True

        try:
            win32gui.EnumWindows(callback, 0)
        except win32gui.error:
            LOGGER.exception("EnumWindows failed")
            return []

        windows = []
        for handle in handles:
            try:
                windows.append(self.get_window(handle, process_cache=process_cache))
            except WindowNotFoundError:
                continue
            except Exception:
                LOGGER.debug(
                    "Could not inspect enumerated window: handle=%s",
                    handle,
                    exc_info=True,
                )

        sorted_windows = sorted(
            windows,
            key=lambda window: (window.process_name.lower(), window.title.lower()),
        )
        log_performance(
            "window_enumeration",
            elapsed_ms=elapsed_ms(started),
            level=logging.DEBUG,
            handles_seen=len(handles),
            windows=len(sorted_windows),
            process_cache_entries=len(process_cache),
        )
        LOGGER.debug("Enumerated %s open windows", len(sorted_windows))
        return sorted_windows

    def get_window(
        self,
        handle: int,
        *,
        process_cache: dict[int, ProcessInfo] | None = None,
    ) -> WindowInfo:
        if not self.is_window_available(handle):
            raise WindowNotFoundError(tr("error.window_missing", handle=handle))

        try:
            title = win32gui.GetWindowText(handle).strip()
        except win32gui.error as exc:
            raise WindowNotFoundError(tr("error.window_title_read", handle=handle)) from exc
        if not title:
            raise WindowNotFoundError(tr("error.window_title_empty", handle=handle))

        try:
            _thread_id, process_id = win32process.GetWindowThreadProcessId(handle)
        except win32gui.error as exc:
            raise WindowNotFoundError(tr("error.window_process_read", handle=handle)) from exc

        process_info = self._process_info(process_id, process_cache)

        return WindowInfo(
            handle=handle,
            title=title,
            process_id=process_id,
            process_name=process_info.process_name,
            executable_path=process_info.executable_path,
            is_visible=bool(win32gui.IsWindowVisible(handle)),
            is_minimized=bool(win32gui.IsIconic(handle)),
        )

    def hide_window(self, handle: int) -> None:
        self._ensure_window(handle)
        if handle in self._managed_styles:
            LOGGER.info("Window is already managed; skipping duplicate hide: handle=%s", handle)
            return

        self._ensure_safe_to_manage(handle)
        window = self.get_window(handle)
        class_name = self._window_class_name(handle)
        original_style = self._get_extended_style(handle)
        # Do not use SW_HIDE here: preserving process/window state is the feature.
        # Taskbar and Alt+Tab membership is controlled by extended styles instead.
        managed_style = (original_style & ~win32con.WS_EX_APPWINDOW) | win32con.WS_EX_TOOLWINDOW

        LOGGER.info(
            "Managing native window style: handle=%s original_ex_style=0x%08X "
            "managed_ex_style=0x%08X class=%s",
            handle,
            original_style,
            managed_style,
            class_name,
        )

        try:
            self._set_extended_style(handle, managed_style)
            self._verify_extended_style(handle, managed_style)
            self._refresh_window_frame(handle)
        except WindowOperationError:
            LOGGER.exception(
                "Failed to apply managed style; attempting rollback: handle=%s",
                handle,
            )
            self._rollback_style(handle, original_style)
            raise

        self._managed_styles[handle] = ManagedWindowStyle(
            handle=handle,
            original_extended_style=original_style,
            managed_extended_style=managed_style,
            process_id=window.process_id,
            process_name=window.process_name,
            class_name=class_name,
        )

    def restore_window(self, handle: int, *, focus: bool = True) -> None:
        self._ensure_window(handle)
        managed_style = self._managed_styles.get(handle)
        if managed_style is None:
            LOGGER.warning("No original style registered for managed window: handle=%s", handle)
            raise WindowOperationError(tr("error.window_not_managed", handle=handle))

        LOGGER.info(
            "Restoring native window style: handle=%s original_ex_style=0x%08X "
            "managed_ex_style=0x%08X",
            handle,
            managed_style.original_extended_style,
            managed_style.managed_extended_style,
        )
        self._set_extended_style(handle, managed_style.original_extended_style)
        self._refresh_window_frame(handle)
        self._managed_styles.pop(handle, None)
        if focus:
            self.bring_to_front(handle)

    def pin_window(
        self,
        handle: int,
        *,
        prevent_minimize: bool = False,
        allow_own_window: bool = False,
    ) -> None:
        self._ensure_window(handle)
        if handle in self._pinned_styles:
            LOGGER.info("Window is already pinned; refreshing topmost state: handle=%s", handle)
            self._set_topmost(handle, enabled=True)
            if self._pinned_styles[handle].prevent_minimize != prevent_minimize:
                self.set_prevent_minimize(handle, prevent_minimize)
            return

        self._ensure_safe_to_pin(handle, allow_own_window=allow_own_window)
        window = self.get_window(handle)
        class_name = self._window_class_name(handle)
        original_style = self._get_style(handle)
        original_extended_style = self._get_extended_style(handle)
        target_style = (
            original_style & ~win32con.WS_MINIMIZEBOX
            if prevent_minimize
            else original_style
        )
        pinned_extended_style = original_extended_style | win32con.WS_EX_TOPMOST

        LOGGER.info(
            "Pinning native window: handle=%s prevent_minimize=%s original_style=0x%08X "
            "original_ex_style=0x%08X class=%s",
            handle,
            prevent_minimize,
            original_style,
            original_extended_style,
            class_name,
        )

        try:
            if target_style != original_style:
                self._set_style(handle, target_style)
                self._refresh_window_frame(handle)
            self._set_topmost(handle, enabled=True)
        except WindowOperationError:
            LOGGER.exception("Failed to pin window; attempting rollback: handle=%s", handle)
            self._rollback_pin(handle, original_style, original_extended_style)
            raise

        self._pinned_styles[handle] = PinnedWindowStyle(
            handle=handle,
            original_style=original_style,
            original_extended_style=original_extended_style,
            pinned_extended_style=pinned_extended_style,
            process_id=window.process_id,
            process_name=window.process_name,
            class_name=class_name,
            prevent_minimize=prevent_minimize,
        )

    def unpin_window(self, handle: int) -> None:
        pinned_style = self._pinned_styles.get(handle)
        if pinned_style is None:
            LOGGER.warning("No original style registered for pinned window: handle=%s", handle)
            if self.is_window_available(handle):
                self._set_topmost(handle, enabled=False)
            return
        if not self.is_window_available(handle):
            LOGGER.info("Dropping closed pinned window from style registry: handle=%s", handle)
            self._pinned_styles.pop(handle, None)
            return

        LOGGER.info(
            "Unpinning native window: handle=%s original_style=0x%08X "
            "original_ex_style=0x%08X",
            handle,
            pinned_style.original_style,
            pinned_style.original_extended_style,
        )
        self._set_style(handle, pinned_style.original_style)
        self._set_extended_style(handle, pinned_style.original_extended_style)
        self._set_topmost(
            handle,
            enabled=bool(pinned_style.original_extended_style & win32con.WS_EX_TOPMOST),
        )
        self._pinned_styles.pop(handle, None)

    def set_prevent_minimize(self, handle: int, enabled: bool) -> None:
        self._ensure_window(handle)
        pinned_style = self._pinned_styles.get(handle)
        if pinned_style is None:
            LOGGER.warning("Cannot update prevent-minimize for unpinned window: handle=%s", handle)
            raise WindowOperationError(tr("error.window_not_pinned", handle=handle))

        current_style = self._get_style(handle)
        if enabled:
            target_style = current_style & ~win32con.WS_MINIMIZEBOX
        elif pinned_style.original_style & win32con.WS_MINIMIZEBOX:
            target_style = current_style | win32con.WS_MINIMIZEBOX
        else:
            target_style = current_style & ~win32con.WS_MINIMIZEBOX

        if target_style != current_style:
            self._set_style(handle, target_style)
            self._refresh_window_frame(handle)

        self._pinned_styles[handle] = PinnedWindowStyle(
            handle=pinned_style.handle,
            original_style=pinned_style.original_style,
            original_extended_style=pinned_style.original_extended_style,
            pinned_extended_style=pinned_style.pinned_extended_style,
            process_id=pinned_style.process_id,
            process_name=pinned_style.process_name,
            class_name=pinned_style.class_name,
            prevent_minimize=enabled,
        )
        LOGGER.info(
            "Native prevent-minimize updated: handle=%s enabled=%s",
            handle,
            enabled,
        )

    def is_window_minimized(self, handle: int) -> bool:
        self._ensure_window(handle)
        return bool(win32gui.IsIconic(handle))

    def restore_minimized_window(self, handle: int) -> None:
        self._ensure_window(handle)
        try:
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)
            self._set_topmost(handle, enabled=True)
            LOGGER.info("Restored minimized pinned window: handle=%s", handle)
        except win32gui.error as exc:
            LOGGER.exception("ShowWindow(SW_RESTORE) failed: handle=%s", handle)
            raise WindowOperationError(
                tr("error.window_restore_minimized", handle=handle)
            ) from exc

    def bring_to_front(self, handle: int) -> None:
        self._ensure_window(handle)
        try:
            LOGGER.info("Setting native foreground window: handle=%s", handle)
            win32gui.SetForegroundWindow(handle)
        except win32gui.error as exc:
            LOGGER.debug("SetForegroundWindow failed for %s: %s", handle, exc)

    def is_window_available(self, handle: int) -> bool:
        try:
            available = bool(win32gui.IsWindow(handle))
        except win32gui.error:
            return False
        if not available and handle in self._managed_styles:
            LOGGER.info("Dropping closed managed window from style registry: handle=%s", handle)
            self._managed_styles.pop(handle, None)
        if not available and handle in self._pinned_styles:
            LOGGER.info("Dropping closed pinned window from style registry: handle=%s", handle)
            self._pinned_styles.pop(handle, None)
        return available

    def is_window_managed(self, handle: int) -> bool:
        return handle in self._managed_styles

    def managed_styles_snapshot(self) -> dict[int, ManagedWindowStyle]:
        return dict(self._managed_styles)

    def pinned_styles_snapshot(self) -> dict[int, PinnedWindowStyle]:
        return dict(self._pinned_styles)

    def restore_from_recovery_record(self, record: dict[str, object]) -> bool:
        handle = record.get("handle")
        process_id = record.get("process_id")
        original_extended_style = record.get("original_extended_style")
        if not (
            isinstance(handle, int)
            and isinstance(process_id, int)
            and isinstance(original_extended_style, int)
        ):
            LOGGER.warning("Ignoring invalid recovery record: %s", record)
            return False
        if not self.is_window_available(handle):
            LOGGER.info("Recovery target is no longer available: handle=%s", handle)
            return False

        try:
            _thread_id, live_process_id = win32process.GetWindowThreadProcessId(handle)
        except win32gui.error:
            LOGGER.info("Recovery target disappeared before process validation: handle=%s", handle)
            return False
        if live_process_id != process_id:
            LOGGER.warning(
                "Recovery target handle now belongs to a different process: "
                "handle=%s expected_pid=%s live_pid=%s",
                handle,
                process_id,
                live_process_id,
            )
            return False

        try:
            LOGGER.warning(
                "Restoring window from emergency recovery state: handle=%s style=0x%08X",
                handle,
                original_extended_style,
            )
            self._set_extended_style(handle, original_extended_style)
            self._refresh_window_frame(handle)
            self._managed_styles.pop(handle, None)
            return True
        except WindowOperationError:
            LOGGER.exception("Could not restore emergency recovery target: handle=%s", handle)
            return False

    def foreground_window_handle(self) -> int | None:
        try:
            handle = win32gui.GetForegroundWindow()
        except win32gui.error:
            LOGGER.debug("Could not read foreground window", exc_info=True)
            return None
        if not handle:
            return None
        try:
            if not self._is_candidate_window(handle):
                return None
        except Exception:
            LOGGER.debug("Foreground window is not manageable: handle=%s", handle, exc_info=True)
            return None
        return handle

    def _ensure_window(self, handle: int) -> None:
        if not self.is_window_available(handle):
            raise WindowNotFoundError(tr("error.window_missing", handle=handle))

    def _ensure_safe_to_manage(self, handle: int) -> None:
        window = self.get_window(handle)
        class_name = self._window_class_name(handle)
        process_name = window.process_name.lower()
        extended_style = self._get_extended_style(handle)

        if not window.is_visible:
            LOGGER.warning("Refusing to manage invisible window: handle=%s", handle)
            raise WindowOperationError(tr("error.window_invisible"))
        if window.process_id == self._own_process_id:
            LOGGER.warning("Refusing to manage ShelfyGAI's own window: handle=%s", handle)
            raise WindowOperationError(tr("error.window_self"))
        if (
            class_name in START_MENU_WINDOW_CLASSES
            or process_name == "startmenuexperiencehost.exe"
        ):
            LOGGER.warning(
                "Refusing to manage Start Menu window: handle=%s class=%s process=%s",
                handle,
                class_name,
                process_name,
            )
            raise WindowOperationError(tr("error.window_start_menu"))
        if class_name in SYSTEM_SHELL_WINDOW_CLASSES:
            LOGGER.warning(
                "Refusing to manage Explorer shell window: handle=%s class=%s",
                handle,
                class_name,
            )
            raise WindowOperationError(tr("error.window_shell"))
        if process_name in CRITICAL_SYSTEM_PROCESS_NAMES:
            LOGGER.warning(
                "Refusing to manage critical system window: handle=%s process=%s",
                handle,
                process_name,
            )
            raise WindowOperationError(tr("error.window_critical"))
        elevation_state = self._process_elevation_state(window.process_id)
        if not self._own_process_elevated and elevation_state is not False:
            LOGGER.warning(
                "Refusing to manage possible elevated window from non-elevated ShelfyGAI: "
                "handle=%s process=%s elevation_state=%s",
                handle,
                process_name,
                elevation_state,
            )
            raise WindowOperationError(tr("error.window_elevated"))
        if extended_style & win32con.WS_EX_TOOLWINDOW:
            LOGGER.warning("Refusing to manage tool window: handle=%s", handle)
            raise WindowOperationError(tr("error.window_tool"))
        if extended_style & win32con.WS_EX_NOACTIVATE:
            LOGGER.warning(
                "Refusing to manage no-activate window that may not support taskbar style "
                "changes: handle=%s",
                handle,
            )
            raise WindowOperationError(tr("error.window_style_unsupported"))
        owner = self._owner_window(handle)
        if owner and not (extended_style & win32con.WS_EX_APPWINDOW):
            LOGGER.warning("Refusing to manage owned non-app window: handle=%s", handle)
            raise WindowOperationError(tr("error.window_owned"))

    def _ensure_safe_to_pin(self, handle: int, *, allow_own_window: bool) -> None:
        window = self.get_window(handle)
        class_name = self._window_class_name(handle)
        process_name = window.process_name.lower()

        if not window.is_visible:
            LOGGER.warning("Refusing to pin invisible window: handle=%s", handle)
            raise WindowOperationError(tr("error.window_invisible"))
        if window.process_id == self._own_process_id and not allow_own_window:
            LOGGER.warning("Refusing to pin ShelfyGAI's own window: handle=%s", handle)
            raise WindowOperationError(tr("error.window_pin_self_disabled"))
        if (
            class_name in START_MENU_WINDOW_CLASSES
            or process_name == "startmenuexperiencehost.exe"
        ):
            LOGGER.warning(
                "Refusing to pin Start Menu window: handle=%s class=%s process=%s",
                handle,
                class_name,
                process_name,
            )
            raise WindowOperationError(tr("error.window_start_menu"))
        if class_name in SYSTEM_SHELL_WINDOW_CLASSES:
            LOGGER.warning(
                "Refusing to pin Explorer shell window: handle=%s class=%s",
                handle,
                class_name,
            )
            raise WindowOperationError(tr("error.window_shell"))
        if process_name in CRITICAL_SYSTEM_PROCESS_NAMES:
            LOGGER.warning(
                "Refusing to pin critical system window: handle=%s process=%s",
                handle,
                process_name,
            )
            raise WindowOperationError(tr("error.window_critical"))

    def _is_candidate_window(
        self,
        handle: int,
        process_cache: dict[int, ProcessInfo] | None = None,
    ) -> bool:
        if not self.is_window_available(handle):
            return False
        if not win32gui.IsWindowVisible(handle):
            return False
        if self._is_cloaked(handle):
            return False
        if win32gui.GetParent(handle):
            return False

        class_name = self._window_class_name(handle)
        if class_name in START_MENU_WINDOW_CLASSES:
            return False
        if class_name in SYSTEM_SHELL_WINDOW_CLASSES:
            return False

        title = win32gui.GetWindowText(handle).strip()
        if not title:
            return False

        _thread_id, process_id = win32process.GetWindowThreadProcessId(handle)
        if process_id == self._own_process_id:
            return False
        process_name = self._process_info(process_id, process_cache).process_name.lower()
        if process_name == "startmenuexperiencehost.exe":
            return False
        if process_name in CRITICAL_SYSTEM_PROCESS_NAMES:
            return False

        extended_style = win32gui.GetWindowLong(handle, win32con.GWL_EXSTYLE)
        if extended_style & win32con.WS_EX_TOOLWINDOW:
            return False

        try:
            owner = win32gui.GetWindow(handle, win32con.GW_OWNER)
        except win32gui.error:
            LOGGER.debug("Could not inspect window owner: handle=%s", handle, exc_info=True)
            return False
        return not (owner and not (extended_style & win32con.WS_EX_APPWINDOW))

    def _window_class_name(self, handle: int) -> str:
        try:
            return win32gui.GetClassName(handle)
        except win32gui.error:
            return ""

    def _owner_window(self, handle: int) -> int:
        try:
            return int(win32gui.GetWindow(handle, win32con.GW_OWNER))
        except win32gui.error as exc:
            LOGGER.warning(
                "Could not verify window owner; refusing to manage: handle=%s",
                handle,
                exc_info=True,
            )
            raise WindowOperationError(tr("error.window_owner_check", handle=handle)) from exc

    def _process_info(
        self,
        process_id: int,
        process_cache: dict[int, ProcessInfo] | None = None,
    ) -> ProcessInfo:
        if process_cache is not None and process_id in process_cache:
            return process_cache[process_id]

        process_name = "unknown.exe"
        executable_path: str | None = None
        try:
            process = psutil.Process(process_id)
            with process.oneshot():
                process_name = process.name()
                executable_path = process.exe()
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            LOGGER.debug("Could not inspect process %s", process_id)

        process_info = ProcessInfo(
            process_id=process_id,
            process_name=process_name,
            executable_path=executable_path,
        )
        if process_cache is not None:
            process_cache[process_id] = process_info
        return process_info

    def _get_extended_style(self, handle: int) -> int:
        try:
            style = win32gui.GetWindowLong(handle, win32con.GWL_EXSTYLE)
        except win32gui.error as exc:
            LOGGER.exception("GetWindowLong failed: handle=%s", handle)
            raise WindowOperationError(tr("error.window_style_read", handle=handle)) from exc
        LOGGER.debug("GetWindowLong GWL_EXSTYLE: handle=%s style=0x%08X", handle, style)
        return style

    def _get_style(self, handle: int) -> int:
        try:
            style = win32gui.GetWindowLong(handle, win32con.GWL_STYLE)
        except win32gui.error as exc:
            LOGGER.exception("GetWindowLong(GWL_STYLE) failed: handle=%s", handle)
            raise WindowOperationError(tr("error.window_style_read", handle=handle)) from exc
        LOGGER.debug("GetWindowLong GWL_STYLE: handle=%s style=0x%08X", handle, style)
        return style

    def _set_extended_style(self, handle: int, style: int) -> None:
        try:
            previous_style = win32gui.SetWindowLong(handle, win32con.GWL_EXSTYLE, style)
        except win32gui.error as exc:
            LOGGER.exception("SetWindowLong failed: handle=%s style=0x%08X", handle, style)
            raise WindowOperationError(tr("error.window_style_update", handle=handle)) from exc
        LOGGER.debug(
            "SetWindowLong GWL_EXSTYLE: handle=%s previous=0x%08X new=0x%08X",
            handle,
            previous_style,
            style,
        )

    def _set_style(self, handle: int, style: int) -> None:
        try:
            previous_style = win32gui.SetWindowLong(handle, win32con.GWL_STYLE, style)
        except win32gui.error as exc:
            LOGGER.exception(
                "SetWindowLong(GWL_STYLE) failed: handle=%s style=0x%08X",
                handle,
                style,
            )
            raise WindowOperationError(tr("error.window_style_update", handle=handle)) from exc
        LOGGER.debug(
            "SetWindowLong GWL_STYLE: handle=%s previous=0x%08X new=0x%08X",
            handle,
            previous_style,
            style,
        )

    def _verify_extended_style(self, handle: int, expected_style: int) -> None:
        actual_style = self._get_extended_style(handle)
        if actual_style == expected_style:
            return
        LOGGER.warning(
            "Managed style did not stick; target app may not support taskbar style changes: "
            "handle=%s expected=0x%08X actual=0x%08X",
            handle,
            expected_style,
            actual_style,
        )
        raise WindowOperationError(tr("error.window_style_unsupported"))

    def _refresh_window_frame(self, handle: int) -> None:
        try:
            win32gui.SetWindowPos(handle, 0, 0, 0, 0, 0, STYLE_REFRESH_FLAGS)
        except win32gui.error as exc:
            LOGGER.exception("SetWindowPos frame refresh failed: handle=%s", handle)
            raise WindowOperationError(tr("error.window_frame_refresh", handle=handle)) from exc
        LOGGER.debug("SetWindowPos frame refresh complete: handle=%s", handle)

    def _set_topmost(self, handle: int, *, enabled: bool) -> None:
        insert_after = win32con.HWND_TOPMOST if enabled else win32con.HWND_NOTOPMOST
        try:
            win32gui.SetWindowPos(handle, insert_after, 0, 0, 0, 0, TOPMOST_REFRESH_FLAGS)
        except win32gui.error as exc:
            LOGGER.exception(
                "SetWindowPos topmost update failed: handle=%s enabled=%s",
                handle,
                enabled,
            )
            raise WindowOperationError(tr("error.window_topmost_update", handle=handle)) from exc
        LOGGER.debug("SetWindowPos topmost update complete: handle=%s enabled=%s", handle, enabled)

    def _rollback_style(self, handle: int, original_style: int) -> None:
        try:
            win32gui.SetWindowLong(handle, win32con.GWL_EXSTYLE, original_style)
            win32gui.SetWindowPos(handle, 0, 0, 0, 0, 0, STYLE_REFRESH_FLAGS)
            LOGGER.info("Rolled back native window style: handle=%s", handle)
        except win32gui.error:
            LOGGER.exception("Could not roll back native window style: handle=%s", handle)

    def _rollback_pin(
        self,
        handle: int,
        original_style: int,
        original_extended_style: int,
    ) -> None:
        try:
            win32gui.SetWindowLong(handle, win32con.GWL_STYLE, original_style)
            win32gui.SetWindowLong(handle, win32con.GWL_EXSTYLE, original_extended_style)
            insert_after = (
                win32con.HWND_TOPMOST
                if original_extended_style & win32con.WS_EX_TOPMOST
                else win32con.HWND_NOTOPMOST
            )
            win32gui.SetWindowPos(handle, insert_after, 0, 0, 0, 0, TOPMOST_REFRESH_FLAGS)
            LOGGER.info("Rolled back native pinned state: handle=%s", handle)
        except win32gui.error:
            LOGGER.exception("Could not roll back native pinned state: handle=%s", handle)

    def _is_cloaked(self, handle: int) -> bool:
        cloaked = wintypes.DWORD()
        result = self._dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(handle),
            wintypes.DWORD(DWMWA_CLOAKED),
            ctypes.byref(cloaked),
            ctypes.sizeof(cloaked),
        )
        return result == 0 and bool(cloaked.value)

    def _is_current_process_elevated(self) -> bool:
        try:
            return bool(self._shell32.IsUserAnAdmin())
        except OSError:
            LOGGER.debug("Could not determine ShelfyGAI elevation state", exc_info=True)
            return False

    def _process_elevation_state(self, process_id: int) -> bool | None:
        process_handle = self._kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            process_id,
        )
        if not process_handle:
            error_code = ctypes.get_last_error()
            LOGGER.debug(
                "OpenProcess failed while checking elevation: pid=%s error=%s",
                process_id,
                error_code,
            )
            if error_code == ERROR_ACCESS_DENIED:
                return None
            return False

        token_handle = wintypes.HANDLE()
        try:
            if not self._advapi32.OpenProcessToken(
                process_handle,
                TOKEN_QUERY,
                ctypes.byref(token_handle),
            ):
                error_code = ctypes.get_last_error()
                LOGGER.debug(
                    "OpenProcessToken failed while checking elevation: pid=%s error=%s",
                    process_id,
                    error_code,
                )
                return None if error_code == ERROR_ACCESS_DENIED else False

            elevation = TokenElevation()
            returned_length = wintypes.DWORD()
            if not self._advapi32.GetTokenInformation(
                token_handle,
                TOKEN_ELEVATION_CLASS,
                ctypes.byref(elevation),
                ctypes.sizeof(elevation),
                ctypes.byref(returned_length),
            ):
                LOGGER.debug(
                    "GetTokenInformation(TokenElevation) failed: pid=%s error=%s",
                    process_id,
                    ctypes.get_last_error(),
                )
                return None
            return bool(elevation.TokenIsElevated)
        finally:
            if token_handle.value:
                self._kernel32.CloseHandle(token_handle)
            self._kernel32.CloseHandle(process_handle)
