from __future__ import annotations

import logging
from collections import OrderedDict, deque
from collections.abc import Iterable
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QFileInfo, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QFileIconProvider, QStyle, QWidget

from shelfygai.constants import resource_path
from shelfygai.core.models import WindowInfo
from shelfygai.performance import elapsed_ms, log_performance

LOGGER = logging.getLogger(__name__)
ICON_CACHE_LIMIT = 128
ICON_LOAD_INTERVAL_MS = 25


class AppIconProvider(QObject):
    """Cached application icon extractor for executable-backed windows."""

    iconLoaded = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._file_icon_provider = QFileIconProvider()
        self._cache: OrderedDict[str, QIcon] = OrderedDict()
        self._pending = deque[str]()
        self._pending_keys: set[str] = set()
        self._fallback_icon: QIcon | None = None
        self._folder_icon: QIcon | None = None
        self._cache_hits = 0
        self._cache_misses = 0
        self._queued_loads = 0
        self._loaded_icons = 0
        self._failed_loads = 0
        self._load_timer = QTimer(self)
        self._load_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._load_timer.setInterval(ICON_LOAD_INTERVAL_MS)
        self._load_timer.timeout.connect(self._load_next_icon)

    def icon_for_window(self, window: WindowInfo, *, queue: bool = True) -> QIcon:
        return self.icon_for_executable(window.executable_path, queue=queue)

    def icon_for_executable(self, executable_path: str | None, *, queue: bool = True) -> QIcon:
        key = self._cache_key(executable_path)
        if key is None:
            return self.fallback_icon()
        icon = self._cache.get(key)
        if icon is not None:
            self._cache_hits += 1
            self._cache.move_to_end(key)
            return icon
        self._cache_misses += 1
        if queue:
            self._queue_icon_load(key)
            return self.fallback_icon()
        return self.fallback_icon()

    def group_icon(self, items: Iterable[WindowInfo]) -> QIcon:
        for item in items:
            if item.executable_path:
                return self.icon_for_window(item)
        return self.folder_icon()

    def preload_windows(self, windows: Iterable[WindowInfo]) -> None:
        for window in windows:
            key = self._cache_key(window.executable_path)
            if key is not None and key not in self._cache:
                self._queue_icon_load(key)

    def cache_stats(self) -> dict[str, int]:
        return {
            "cached": len(self._cache),
            "pending": len(self._pending_keys),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "queued": self._queued_loads,
            "loaded": self._loaded_icons,
            "failed": self._failed_loads,
            "timer_active": int(self._load_timer.isActive()),
        }

    def pixmap(self, icon: QIcon, size: int, widget: QWidget | None = None) -> QPixmap:
        dpr = self._device_pixel_ratio(widget)
        physical_size = QSize(max(1, round(size * dpr)), max(1, round(size * dpr)))
        pixmap = icon.pixmap(physical_size)
        pixmap.setDevicePixelRatio(dpr)
        return pixmap

    def fallback_icon(self) -> QIcon:
        if self._fallback_icon is not None:
            return self._fallback_icon
        app = QApplication.instance()
        if app is not None:
            self._fallback_icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        else:
            self._fallback_icon = QIcon(str(resource_path("app_icon.svg")))
        return self._fallback_icon

    def folder_icon(self) -> QIcon:
        if self._folder_icon is not None:
            return self._folder_icon
        app = QApplication.instance()
        if app is not None:
            self._folder_icon = app.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        else:
            self._folder_icon = self.fallback_icon()
        return self._folder_icon

    def _queue_icon_load(self, key: str) -> None:
        if key in self._cache or key in self._pending_keys:
            return
        self._pending.append(key)
        self._pending_keys.add(key)
        self._queued_loads += 1
        if not self._load_timer.isActive():
            self._load_timer.start()

    def _load_next_icon(self) -> None:
        if not self._pending:
            self._load_timer.stop()
            return

        key = self._pending.popleft()
        self._pending_keys.discard(key)
        started = perf_counter()
        icon = self._extract_icon(key)
        self._store_icon(key, icon)
        self._loaded_icons += 1
        log_performance(
            "icon.load",
            elapsed_ms=elapsed_ms(started),
            level=logging.DEBUG,
            cached=len(self._cache),
            pending=len(self._pending_keys),
        )
        self.iconLoaded.emit(key)

        if not self._pending:
            self._load_timer.stop()

    def _store_icon(self, key: str, icon: QIcon) -> None:
        self._cache[key] = icon
        self._cache.move_to_end(key)
        while len(self._cache) > ICON_CACHE_LIMIT:
            self._cache.popitem(last=False)

    def _extract_icon(self, executable_path: str) -> QIcon:
        try:
            path = Path(executable_path)
            if not path.exists() or not path.is_file():
                self._failed_loads += 1
                return self.fallback_icon()
            icon = self._file_icon_provider.icon(QFileInfo(str(path)))
            if not icon.isNull():
                return icon
        except OSError:
            self._failed_loads += 1
            LOGGER.debug("Could not inspect executable icon path: %s", executable_path)
        except Exception:
            self._failed_loads += 1
            LOGGER.debug("Could not extract executable icon: %s", executable_path, exc_info=True)
        return self.fallback_icon()

    def _cache_key(self, executable_path: str | None) -> str | None:
        if not executable_path:
            return None
        try:
            return str(Path(executable_path)).casefold()
        except (OSError, ValueError):
            return None

    def _device_pixel_ratio(self, widget: QWidget | None) -> float:
        if widget is not None:
            handle = widget.window().windowHandle()
            if handle is not None and handle.screen() is not None:
                return float(handle.screen().devicePixelRatio())
        screen = QApplication.primaryScreen()
        if screen is not None:
            return float(screen.devicePixelRatio())
        return 1.0
