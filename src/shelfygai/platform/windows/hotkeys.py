from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication

from shelfygai.i18n import tr

LOGGER = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

MODIFIER_TOKENS = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
    "meta": MOD_WIN,
}

KEY_TOKENS = {
    "space": 0x20,
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "escape": 0x1B,
    "esc": 0x1B,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "ins": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}


@dataclass(frozen=True, slots=True)
class HotkeySpec:
    sequence: str
    modifiers: int
    virtual_key: int


class HotkeyParseError(ValueError):
    pass


class GlobalHotkeyManager(QObject, QAbstractNativeEventFilter):
    activated = Signal(str)
    registrationFailed = Signal(str, str)
    registrationChanged = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        QObject.__init__(self, parent)
        QAbstractNativeEventFilter.__init__(self)
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._registered: dict[int, str] = {}
        self._installed = False

    def register_hotkeys(self, hotkeys: dict[str, dict[str, Any]]) -> None:
        self.unregister_all()
        seen_specs: set[tuple[int, int]] = set()

        for index, (action_id, config) in enumerate(hotkeys.items(), start=1):
            if not config.get("enabled", False):
                continue
            sequence = str(config.get("sequence", "")).strip()
            if not sequence:
                continue

            try:
                spec = parse_hotkey_sequence(sequence)
            except HotkeyParseError as exc:
                self.registrationFailed.emit(action_id, str(exc))
                LOGGER.warning("Invalid global hotkey for %s: %s", action_id, exc)
                continue

            spec_key = (spec.modifiers, spec.virtual_key)
            if spec_key in seen_specs:
                message = tr("hotkey.error.duplicate")
                self.registrationFailed.emit(action_id, message)
                LOGGER.warning("Duplicate global hotkey skipped: action=%s", action_id)
                continue
            seen_specs.add(spec_key)

            # RegisterHotKey ids are process-local and must stay below 0xC000.
            # The 0x4700 range keeps ShelfyGAI ids grouped and out of common samples.
            hotkey_id = 0x4700 + index
            modifiers = spec.modifiers | MOD_NOREPEAT
            if not self._user32.RegisterHotKey(None, hotkey_id, modifiers, spec.virtual_key):
                error_code = ctypes.get_last_error()
                message = tr("hotkey.error.rejected", error=error_code)
                self.registrationFailed.emit(action_id, message)
                LOGGER.warning(
                    "RegisterHotKey failed: action=%s sequence=%s error=%s",
                    action_id,
                    sequence,
                    error_code,
                )
                continue

            self._registered[hotkey_id] = action_id
            LOGGER.info("Registered global hotkey: action=%s sequence=%s", action_id, sequence)

        self._sync_event_filter()
        self.registrationChanged.emit(self.summary())

    def unregister_all(self) -> None:
        for hotkey_id in list(self._registered):
            if not self._user32.UnregisterHotKey(None, hotkey_id):
                LOGGER.debug("UnregisterHotKey failed: id=%s", hotkey_id)
        self._registered.clear()
        self._sync_event_filter()

    def summary(self) -> str:
        return tr("hotkey.status.count", count=self.registered_count())

    def registered_count(self) -> int:
        return len(self._registered)

    def nativeEventFilter(self, event_type: object, message: object) -> tuple[bool, int]:
        if _event_type_text(event_type) not in {"windows_generic_MSG", "windows_dispatcher_MSG"}:
            return False, 0

        address = _message_address(message)
        if address is None:
            return False, 0

        msg = wintypes.MSG.from_address(address)
        if msg.message != WM_HOTKEY:
            return False, 0

        action_id = self._registered.get(int(msg.wParam))
        if action_id is None:
            return False, 0

        LOGGER.info("Global hotkey activated: action=%s", action_id)
        self.activated.emit(action_id)
        return True, 0

    def _sync_event_filter(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        if self._registered and not self._installed:
            app.installNativeEventFilter(self)
            self._installed = True
        elif not self._registered and self._installed:
            app.removeNativeEventFilter(self)
            self._installed = False


def parse_hotkey_sequence(sequence: str) -> HotkeySpec:
    tokens = [
        token.strip()
        for token in sequence.replace("++", "+Plus").split("+")
        if token.strip()
    ]
    if not tokens:
        raise HotkeyParseError(tr("hotkey.error.empty"))

    modifiers = 0
    key_token = ""
    for token in tokens:
        normalized = _normalize_token(token)
        modifier = MODIFIER_TOKENS.get(normalized)
        if modifier is not None:
            modifiers |= modifier
        else:
            key_token = normalized

    if key_token == "":
        raise HotkeyParseError(tr("hotkey.error.missing_key"))
    if modifiers == 0:
        raise HotkeyParseError(tr("hotkey.error.missing_modifier"))

    virtual_key = _virtual_key_from_token(key_token)
    if virtual_key is None:
        raise HotkeyParseError(tr("hotkey.error.unsupported_key", token=key_token))

    return HotkeySpec(sequence=sequence, modifiers=modifiers, virtual_key=virtual_key)


def _virtual_key_from_token(token: str) -> int | None:
    if len(token) == 1 and "a" <= token <= "z":
        return ord(token.upper())
    if len(token) == 1 and "0" <= token <= "9":
        return ord(token)
    if token.startswith("f") and token[1:].isdigit():
        function_number = int(token[1:])
        if 1 <= function_number <= 24:
            return 0x70 + function_number - 1
    return KEY_TOKENS.get(token)


def _normalize_token(token: str) -> str:
    return token.lower().replace(" ", "").replace("_", "")


def _event_type_text(event_type: object) -> str:
    if isinstance(event_type, bytes):
        return event_type.decode("ascii", errors="ignore")
    return str(event_type)


def _message_address(message: object) -> int | None:
    try:
        return int(message)
    except (TypeError, ValueError):
        try:
            return message.__int__()  # type: ignore[attr-defined]
        except (AttributeError, TypeError, ValueError):
            return None
