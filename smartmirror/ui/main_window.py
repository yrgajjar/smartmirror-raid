"""Main dashboard window (multi-pair aware)."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import i18n
from ..logger import get_buffer_handler
from ..manager import MirrorManager
from ..service import (
    ERROR,
    PAUSED,
    RUNNING,
    STARTING,
    STOPPED,
    ServiceStatus,
)
from ..version import APP_NAME, AUTHOR_URL, FOOTER_TEXT, __version__
from .settings_dialog import SettingsDialog
from .version_browser import VersionBrowserDialog

_STATE_COLORS = {
    RUNNING: "#2e7d32",
    PAUSED: "#ef6c00",
    STARTING: "#1565c0",
    STOPPED: "#616161",
    ERROR: "#c62828",
}

_LEVEL_COLORS = {
    "ERROR": "#c62828",
    "WARNING": "#ef6c00",
    "CRITICAL": "#b71c1c",
}


def _human_bytes(num: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PiB"


class MainWindow(QMainWindow):
    log_signal = Signal(str, str)
    status_signal = Signal(int, object)
    restore_done = Signal(object)

    # Set by the application bootstrap when a tray icon is available so that
    # closing the window hides it instead of quitting the app.
    minimize_to_tray: bool = False

    def __init__(self, manager: MirrorManager) -> None:
        super().__init__()
        self.manager = manager
        i18n.set_language(manager.app_config.language)
        self.current_index = 0 if len(manager) else -1
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(840, 660)

        self._build_ui()

        self.log_signal.connect(self._append_log)
        self.status_signal.connect(self._on_status)
        self.restore_done.connect(self._on_restore_done)

        get_buffer_handler().subscribe(self._on_log_record)
        manager.add_status_listener(
            lambda index, status: self.status_signal.emit(index, status)
        )

        # Periodic refresh so the storage bar stays current and storage
        # threshold alerts surface in the tray.
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        for line in get_buffer_handler().history()[-200:]:
            self._append_raw(line)
        self._refresh_pairs()

    # -- construction -------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet(
            "background:#fff3cd; color:#7a5b00; border:1px solid #ffe08a;"
            "padding:8px; border-radius:6px; font-weight:600;"
        )
        root.addWidget(self.banner)

        root.addWidget(self._build_paths_group())
        root.addWidget(self._build_status_group())
        root.addLayout(self._build_buttons())

        self.log_label = QLabel()
        self.log_label.setStyleSheet("font-weight:600; margin-top:6px;")
        root.addWidget(self.log_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setStyleSheet("font-family: monospace; font-size: 12px;")
        root.addWidget(self.log_view, stretch=1)

        root.addWidget(self._build_footer())
        self._retranslate()

    def _build_footer(self) -> QLabel:
        self.footer = QLabel()
        self.footer.setObjectName("footer")
        self.footer.setOpenExternalLinks(True)
        self.footer.setAlignment(Qt.AlignCenter)
        self.footer.setStyleSheet("color:#616161; padding:6px; font-size:12px;")
        return self.footer

    def _build_paths_group(self) -> QGroupBox:
        self.paths_box = QGroupBox()
        grid = QGridLayout(self.paths_box)

        self.pair_caption = QLabel()
        grid.addWidget(self.pair_caption, 0, 0)
        self.pair_combo = QComboBox()
        self.pair_combo.currentIndexChanged.connect(self._on_pair_selected)
        grid.addWidget(self.pair_combo, 0, 1)

        self.source_caption = QLabel()
        grid.addWidget(self.source_caption, 1, 0)
        self.source_label = QLabel()
        grid.addWidget(self.source_label, 1, 1)

        self.mirror_caption = QLabel()
        grid.addWidget(self.mirror_caption, 2, 0)
        self.mirror_label = QLabel()
        grid.addWidget(self.mirror_label, 2, 1)

        grid.setColumnStretch(1, 1)
        return self.paths_box

    def _build_status_group(self) -> QGroupBox:
        self.status_box = QGroupBox()
        layout = QVBoxLayout(self.status_box)

        row = QHBoxLayout()
        self.state_label = QLabel()
        self.state_label.setStyleSheet("font-weight:700; font-size:15px;")
        row.addWidget(self.state_label)
        row.addStretch(1)
        self.watch_label = QLabel()
        row.addWidget(self.watch_label)
        layout.addLayout(row)

        self.storage_bar = QProgressBar()
        self.storage_bar.setRange(0, 100)
        self.storage_bar.setFormat("%p%")
        layout.addWidget(self.storage_bar)

        self.usage_label = QLabel("–")
        layout.addWidget(self.usage_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        self.stats_label = QLabel()
        layout.addWidget(self.stats_label)
        return self.status_box

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.start_button = QPushButton()
        self.start_button.clicked.connect(self._on_start)
        self.pause_button = QPushButton()
        self.pause_button.clicked.connect(self._on_pause)
        self.restore_button = QPushButton()
        self.restore_button.clicked.connect(self._on_restore)
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self._on_browse)
        self.settings_button = QPushButton()
        self.settings_button.clicked.connect(self.open_settings)
        for button in (
            self.start_button,
            self.pause_button,
            self.restore_button,
            self.browse_button,
            self.settings_button,
        ):
            row.addWidget(button)
        return row

    # -- i18n ---------------------------------------------------------------
    def _retranslate(self) -> None:
        self.banner.setText(f"⚠  {i18n.t('not_real_raid')}")
        self.paths_box.setTitle(i18n.t("mirror_configuration"))
        self.pair_caption.setText(i18n.t("mirror_pair"))
        self.source_caption.setText(i18n.t("source_path"))
        self.mirror_caption.setText(i18n.t("mirror_path"))
        self.status_box.setTitle(i18n.t("status"))
        self.watch_label.setText(i18n.t("watcher_idle"))
        self.log_label.setText(i18n.t("activity_log"))
        self.restore_button.setText(i18n.t("restore_from_mirror"))
        self.browse_button.setText(i18n.t("browse_versions"))
        self.settings_button.setText(i18n.t("settings"))
        self.footer.setText(
            f"{APP_NAME} v{__version__} &nbsp;—&nbsp; "
            f'<a href="{AUTHOR_URL}" style="color:#1565c0; text-decoration:none;">'
            f"{_escape(FOOTER_TEXT)}</a>"
        )

    # -- pair selection -----------------------------------------------------
    def _refresh_pairs(self) -> None:
        self.pair_combo.blockSignals(True)
        self.pair_combo.clear()
        labels = self.manager.labels()
        self.pair_combo.addItems(labels)
        if labels:
            if not (0 <= self.current_index < len(labels)):
                self.current_index = 0
            self.pair_combo.setCurrentIndex(self.current_index)
        else:
            self.current_index = -1
        self.pair_combo.blockSignals(False)
        self._refresh_current()

    def _on_pair_selected(self, index: int) -> None:
        if index < 0:
            return
        self.current_index = index
        self._refresh_current()

    def _current_service(self):
        if 0 <= self.current_index < len(self.manager):
            return self.manager[self.current_index]
        return None

    def _refresh_current(self) -> None:
        service = self._current_service()
        if service is None:
            self._show_empty()
        else:
            self._update_view(service.status())

    def _show_empty(self) -> None:
        self.source_label.setText(i18n.t("no_pairs"))
        self.mirror_label.setText("")
        self.state_label.setText(i18n.state_label(STOPPED))
        self.state_label.setStyleSheet(
            "font-weight:700; font-size:15px; color:#616161;"
        )
        self.watch_label.setText(i18n.t("watcher_idle"))
        self.storage_bar.setValue(0)
        self.usage_label.setText("–")
        self.stats_label.setText("")
        self._sync_buttons(None)

    # -- actions ------------------------------------------------------------
    def _on_start(self) -> None:
        service = self._current_service()
        if service is None:
            self.open_settings()
            return
        if service.state in (STOPPED, ERROR):
            if not service.config.is_configured():
                self.open_settings()
                return
            service.start()
        elif service.state in (RUNNING, PAUSED):
            service.stop()

    def _on_pause(self) -> None:
        service = self._current_service()
        if service is None:
            return
        if service.state == RUNNING:
            service.pause()
        elif service.state == PAUSED:
            service.resume()

    def _on_restore(self) -> None:
        service = self._current_service()
        if service is None:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle(i18n.t("restore_title"))
        confirm.setIcon(QMessageBox.Warning)
        confirm.setText(i18n.t("restore_text"))
        confirm.setInformativeText(
            f"{i18n.t('source_path')} {service.config.source_path}\n"
            f"{i18n.t('mirror_path')} {service.config.mirror_path}"
        )
        overwrite = QCheckBox(i18n.t("restore_overwrite"))
        confirm.setCheckBox(overwrite)
        confirm.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        if confirm.exec() != QMessageBox.Ok:
            return
        self.restore_button.setEnabled(False)
        self.statusBar().showMessage(i18n.t("restoring"))

        def worker() -> None:
            stats = service.restore(overwrite=overwrite.isChecked())
            self.restore_done.emit(stats)

        threading.Thread(target=worker, daemon=True).start()

    def _on_restore_done(self, stats) -> None:
        self.restore_button.setEnabled(True)
        self.statusBar().clearMessage()
        QMessageBox.information(
            self,
            i18n.t("restore_complete"),
            i18n.t(
                "restore_result",
                copied=stats.copied,
                skipped=stats.skipped,
                errors=stats.errors,
            ),
        )

    def _on_browse(self) -> None:
        service = self._current_service()
        if service is None:
            QMessageBox.information(
                self, i18n.t("vb_title"), i18n.t("select_pair_first")
            )
            return
        VersionBrowserDialog(service, self).exec()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.manager.app_config, self)
        if dialog.exec() != QDialog.Accepted:
            return
        new_app = dialog.result_config()
        i18n.set_language(new_app.language)
        self.manager.replace_config(new_app)
        self._retranslate()
        self._refresh_pairs()

    # -- updates ------------------------------------------------------------
    def _on_tick(self) -> None:
        service = self._current_service()
        if service is not None:
            self.status_signal.emit(self.current_index, service.status())
        for index, message in self.manager.check_storage_alerts():
            self._notify_storage(index, message)

    def _notify_storage(self, index: int, message: str) -> None:
        tray = getattr(self, "tray", None)
        if tray is not None:
            tray.showMessage(i18n.t("storage_alert_title"), message)

    def _on_log_record(self, record, message: str) -> None:
        self.log_signal.emit(record.levelname, message)

    def _append_log(self, level: str, message: str) -> None:
        self._append_raw(message, _LEVEL_COLORS.get(level))

    def _append_raw(self, message: str, color: str | None = None) -> None:
        if color:
            self.log_view.appendHtml(
                f'<span style="color:{QColor(color).name()}">{_escape(message)}</span>'
            )
        else:
            self.log_view.appendPlainText(message)
        self.log_view.moveCursor(QTextCursor.End)

    def _on_status(self, index: int, status: ServiceStatus) -> None:
        if index == self.current_index:
            self._update_view(status)

    def _update_view(self, status: ServiceStatus) -> None:
        self.source_label.setText(status.source_path or i18n.t("not_configured"))
        self.mirror_label.setText(status.mirror_path or i18n.t("not_configured"))

        color = _STATE_COLORS.get(status.state, "#616161")
        self.state_label.setText(i18n.state_label(status.state))
        self.state_label.setStyleSheet(
            f"font-weight:700; font-size:15px; color:{color};"
        )
        if status.message:
            self.state_label.setToolTip(status.message)
        self.watch_label.setText(
            i18n.t("watcher_active") if status.watching else i18n.t("watcher_idle")
        )

        usage = status.usage
        self.storage_bar.setValue(int(usage.percent_used))
        self.usage_label.setText(
            f"{i18n.t('usage')}: {_human_bytes(usage.used_bytes)} / "
            f"{_human_bytes(usage.allocated_bytes)}  •  "
            f"{i18n.t('disk_free')}: {_human_bytes(usage.disk_free_bytes)}"
        )
        stats = status.stats
        self.stats_label.setText(
            f"{i18n.t('copied')}: {stats.copied}   "
            f"{i18n.t('unchanged')}: {stats.skipped}   "
            f"{i18n.t('removed')}: {stats.deleted}   "
            f"{i18n.t('moved')}: {stats.moved}   "
            f"{i18n.t('errors')}: {stats.errors}"
        )

        self._sync_buttons(status.state)

    def _sync_buttons(self, state: str | None) -> None:
        if state is None:
            self.start_button.setText(i18n.t("start_sync"))
            self.start_button.setEnabled(self.current_index < 0)
            self.pause_button.setEnabled(False)
            self.pause_button.setText(i18n.t("pause"))
            self.restore_button.setEnabled(False)
            self.browse_button.setEnabled(False)
            self.settings_button.setEnabled(True)
            return
        running = state in (RUNNING, PAUSED, STARTING)
        self.start_button.setEnabled(True)
        self.start_button.setText(i18n.t("stop_sync") if running else i18n.t("start_sync"))
        self.pause_button.setEnabled(state in (RUNNING, PAUSED))
        self.pause_button.setText(
            i18n.t("resume") if state == PAUSED else i18n.t("pause")
        )
        self.settings_button.setEnabled(not running)
        self.restore_button.setEnabled(state in (STOPPED, ERROR))
        self.browse_button.setEnabled(state in (STOPPED, ERROR))

    # -- window behaviour ---------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if getattr(self, "minimize_to_tray", False):
            event.ignore()
            self.hide()
            return
        event.accept()


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
