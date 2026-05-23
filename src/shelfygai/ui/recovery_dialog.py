from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from shelfygai.constants import resource_path
from shelfygai.crash import (
    RECOVERY_REASON_ERROR,
    RECOVERY_STATUS_FAILED,
    RECOVERY_STATUS_RESTORED,
    RECOVERY_STATUS_SKIPPED,
    CrashManager,
    DetailedRecoveryResult,
    RecoveryCallback,
    RecoveryWindowResult,
)
from shelfygai.i18n import tr

LOGGER = logging.getLogger(__name__)


class RecoveryDialog(QDialog):
    """Startup screen for restoring windows from the emergency recovery file."""

    def __init__(
        self,
        crash_manager: CrashManager,
        restore_record: RecoveryCallback,
        unpin_pinned_record: RecoveryCallback | None = None,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._crash_manager = crash_manager
        self._restore_record = restore_record
        self._unpin_pinned_record = unpin_pinned_record
        self._result = DetailedRecoveryResult(
            source_path=str(self._crash_manager.recovery_store.path)
        )
        self._auto_started = False
        self._running = False

        self.setWindowTitle(tr("recovery.title"))
        self.setWindowIcon(QIcon(str(resource_path("app_icon.svg"))))
        self.setModal(True)
        self.resize(760, 560)
        self.setMinimumSize(620, 460)

        self._status_label = QLabel()
        self._status_label.setObjectName("Muted")
        self._status_label.setWordWrap(True)
        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(10)
        self._restore_button = QPushButton()
        self._restore_button.setObjectName("PrimaryButton")
        self._restore_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)
        )
        self._restore_button.clicked.connect(self.restore_everything_now)
        self._unpin_pinned_button = QPushButton()
        self._unpin_pinned_button.clicked.connect(self.unpin_remembered_windows)
        self._continue_button = QPushButton()
        self._continue_button.clicked.connect(self.accept)

        self._build_layout()
        self._retranslate()
        self._show_initial_state()

    @property
    def result_data(self) -> DetailedRecoveryResult:
        return self._result

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._auto_started:
            self._auto_started = True
            QTimer.singleShot(0, self.restore_everything_now)

    def reject(self) -> None:
        if not self._auto_started:
            self._auto_started = True
            self.restore_everything_now()
        super().reject()

    def restore_everything_now(self) -> None:
        if self._running:
            return

        self._running = True
        self._restore_button.setEnabled(False)
        self._continue_button.setEnabled(False)
        self._status_label.setText(tr("recovery.status.running"))
        QApplication.processEvents()
        LOGGER.warning(
            "Emergency recovery requested from startup screen: path=%s",
            self._crash_manager.recovery_store.path,
        )

        try:
            self._result = self._crash_manager.recover_previous_session_detailed(
                self._restore_record
            )
        except Exception as exc:
            LOGGER.exception("Emergency recovery screen failed unexpectedly")
            self._result = DetailedRecoveryResult(
                items=(
                    RecoveryWindowResult(
                        handle=0,
                        title="",
                        process_id=0,
                        process_name="",
                        status=RECOVERY_STATUS_FAILED,
                        reason=RECOVERY_REASON_ERROR,
                        detail=str(exc),
                    ),
                ),
                source_path=str(self._crash_manager.recovery_store.path),
            )

        self._populate_results()
        self._continue_button.setEnabled(True)
        self._restore_button.setEnabled(
            self._result.failed > 0 and self._crash_manager.recovery_store.exists()
        )
        self._running = False
        self._sync_unpin_pinned_button()
        LOGGER.warning("Emergency recovery screen result: %s", self._result.as_dict())

    def unpin_remembered_windows(self) -> None:
        if self._running or self._unpin_pinned_record is None:
            return

        self._running = True
        self._restore_button.setEnabled(False)
        self._unpin_pinned_button.setEnabled(False)
        self._continue_button.setEnabled(False)
        self._status_label.setText(tr("recovery.status.unpinning_pinned"))
        QApplication.processEvents()
        LOGGER.warning("Remembered pinned-window unpin requested from recovery screen")

        try:
            self._result = self._crash_manager.recover_previous_pinned_detailed(
                self._unpin_pinned_record
            )
        except Exception as exc:
            LOGGER.exception("Remembered pinned-window recovery failed unexpectedly")
            self._result = DetailedRecoveryResult(
                items=(
                    RecoveryWindowResult(
                        handle=0,
                        title="",
                        process_id=0,
                        process_name="",
                        status=RECOVERY_STATUS_FAILED,
                        reason=RECOVERY_REASON_ERROR,
                        detail=str(exc),
                    ),
                ),
                source_path=str(self._crash_manager.recovery_store.path),
            )

        self._populate_results()
        self._continue_button.setEnabled(True)
        self._running = False
        self._sync_unpin_pinned_button()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 22)
        layout.setSpacing(18)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QIcon(str(resource_path("app_icon.svg"))).pixmap(58, 58))
        logo.setFixedSize(66, 66)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        copy = QVBoxLayout()
        copy.setSpacing(6)
        title = QLabel(tr("recovery.heading"))
        title.setObjectName("HeaderTitle")
        description = QLabel(tr("recovery.description"))
        description.setObjectName("HeaderSubtitle")
        description.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(description)

        header.addWidget(logo)
        header.addLayout(copy, 1)
        layout.addLayout(header)

        path_label = QLabel(
            tr("recovery.path", path=str(self._crash_manager.recovery_store.path))
        )
        path_label.setObjectName("Muted")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)
        layout.addWidget(self._status_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._results_container)
        layout.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self._unpin_pinned_button)
        footer.addWidget(self._restore_button)
        footer.addWidget(self._continue_button)
        layout.addLayout(footer)

    def _retranslate(self) -> None:
        self.setWindowTitle(tr("recovery.title"))
        self._restore_button.setText(tr("recovery.restore_now"))
        self._unpin_pinned_button.setText(tr("recovery.unpin_pinned_now"))
        self._continue_button.setText(tr("recovery.continue"))
        self._sync_unpin_pinned_button()

    def _show_initial_state(self) -> None:
        payload = self._crash_manager.recovery_store.load()
        records = _records_from_payload(payload)
        pinned_records = _pinned_records_from_payload(payload)
        pending_records = [*records, *pinned_records]
        if pending_records:
            self._status_label.setText(
                tr("recovery.status.ready", count=len(pending_records))
            )
            self._populate_placeholder(pending_records)
        else:
            self._status_label.setText(tr("recovery.status.none"))
            self._populate_results()
        self._sync_unpin_pinned_button()

    def _sync_unpin_pinned_button(self) -> None:
        payload = self._crash_manager.recovery_store.load()
        pinned_records = _pinned_records_from_payload(payload)
        self._unpin_pinned_button.setVisible(bool(pinned_records))
        self._unpin_pinned_button.setEnabled(
            bool(pinned_records) and self._unpin_pinned_record is not None and not self._running
        )

    def _populate_placeholder(self, records: list[Mapping[str, Any]]) -> None:
        self._clear_layout(self._results_layout)
        for record in records:
            self._results_layout.addWidget(
                self._build_result_card(
                    RecoveryWindowResult(
                        handle=_int_value(record.get("handle")),
                        title=str(record.get("title") or ""),
                        process_id=_int_value(record.get("process_id")),
                        process_name=str(record.get("process_name") or ""),
                        status=RECOVERY_STATUS_SKIPPED,
                        reason="pending",
                    ),
                    pending=True,
                )
            )
        self._results_layout.addStretch(1)

    def _populate_results(self) -> None:
        self._clear_layout(self._results_layout)
        if not self._result.items:
            pinned_records = _pinned_records_from_payload(self._crash_manager.recovery_store.load())
            if pinned_records:
                self._status_label.setText(
                    tr("recovery.status.pinned_ready", count=len(pinned_records))
                )
                self._populate_placeholder(pinned_records)
                return
            empty_label = QLabel(tr("recovery.no_windows"))
            empty_label.setObjectName("EmptyState")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._results_layout.addWidget(empty_label)
            self._results_layout.addStretch(1)
            return

        self._status_label.setText(
            tr(
                "recovery.status.summary",
                restored=self._result.restored,
                skipped=self._result.skipped,
                failed=self._result.failed,
            )
        )
        for item in self._result.items:
            self._results_layout.addWidget(self._build_result_card(item))
        self._results_layout.addStretch(1)

    def _build_result_card(
        self,
        item: RecoveryWindowResult,
        *,
        pending: bool = False,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("ManagedGroupCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        icon = QLabel()
        icon.setFixedSize(34, 34)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(self._status_icon(item.status, pending).pixmap(26, 26))

        copy = QVBoxLayout()
        copy.setSpacing(3)
        title = QLabel(item.title or tr("recovery.unknown_window", handle=item.handle))
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        meta = QLabel(
            tr(
                "recovery.item.meta",
                app=item.process_name or tr("recovery.unknown_app"),
                pid=item.process_id,
                hwnd=item.handle,
            )
        )
        meta.setObjectName("Muted")
        meta.setWordWrap(True)
        reason = QLabel(tr("recovery.status.pending") if pending else self._reason_text(item))
        reason.setObjectName("Muted")
        reason.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(meta)
        copy.addWidget(reason)

        status_text = (
            tr("recovery.result.pending")
            if pending
            else tr(f"recovery.result.{item.status}")
        )
        status = QLabel(status_text)
        status.setStyleSheet(f"font-weight: 700; color: {_status_color(item.status, pending)};")

        layout.addWidget(icon)
        layout.addLayout(copy, 1)
        layout.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
        return card

    def _status_icon(self, status: str, pending: bool) -> QIcon:
        if pending:
            icon = QStyle.StandardPixmap.SP_MessageBoxInformation
        elif status == RECOVERY_STATUS_RESTORED:
            icon = QStyle.StandardPixmap.SP_DialogApplyButton
        elif status == RECOVERY_STATUS_FAILED:
            icon = QStyle.StandardPixmap.SP_MessageBoxCritical
        else:
            icon = QStyle.StandardPixmap.SP_MessageBoxWarning
        return self.style().standardIcon(icon)

    def _reason_text(self, item: RecoveryWindowResult) -> str:
        if item.reason == RECOVERY_REASON_ERROR and item.detail:
            return tr("recovery.reason.error_detail", error=item.detail)
        return tr(f"recovery.reason.{item.reason}")

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()


def _records_from_payload(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if payload is None:
        return []
    records = payload.get("managed_windows", [])
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def _pinned_records_from_payload(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if payload is None:
        return []
    records = payload.get("pinned_windows", [])
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def _int_value(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _status_color(status: str, pending: bool) -> str:
    if pending:
        return "#9da7b1"
    if status == RECOVERY_STATUS_RESTORED:
        return "#55c2a2"
    if status == RECOVERY_STATUS_FAILED:
        return "#e85d75"
    return "#f0b429"
