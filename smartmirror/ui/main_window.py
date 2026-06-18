"""Main dashboard window."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
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

from .. import autostart
from ..config import MirrorConfig, save_config
from ..logger import get_buffer_handler
from ..service import (
    ERROR,
    PAUSED,
    RUNNING,
    STARTING,
    STOPPED,
    MirrorService,
    ServiceStatus,
)
from ..version import APP_NAME, AUTHOR_URL, FOOTER_TEXT, NOT_REAL_RAID_WARNING, __version__
from .settings_dialog import SettingsDialog

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
    status_signal = Signal(object)
    restore_done = Signal(object)

    # Set by the application bootstrap when a tray icon is available so that
    # closing the window hides it instead of quitting the app.
    minimize_to_tray: bool = False

    def __init__(self, service: MirrorService) -> None:
        super().__init__()
        self.service = service
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(820, 640)

        self._build_ui()

        # Event-driven updates from background threads, marshalled to the GUI
        # thread via queued signal connections.
        self.log_signal.connect(self._append_log)
        self.status_signal.connect(self._update_status)
        self.restore_done.connect(self._on_restore_done)

        get_buffer_handler().subscribe(self._on_log_record)
        service.add_status_listener(lambda s: self.status_signal.emit(s))

        # Periodic refresh so the storage bar stays current.
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(lambda: self.status_signal.emit(service.status()))
        self._timer.start()

        for line in get_buffer_handler().history()[-200:]:
            self._append_raw(line)
        self._update_status(service.status())

    # -- construction -------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        banner = QLabel(f"⚠  {NOT_REAL_RAID_WARNING}")
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background:#fff3cd; color:#7a5b00; border:1px solid #ffe08a;"
            "padding:8px; border-radius:6px; font-weight:600;"
        )
        root.addWidget(banner)

        root.addWidget(self._build_paths_group())
        root.addWidget(self._build_status_group())
        root.addLayout(self._build_buttons())

        log_label = QLabel("Activity log")
        log_label.setStyleSheet("font-weight:600; margin-top:6px;")
        root.addWidget(log_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setStyleSheet("font-family: monospace; font-size: 12px;")
        root.addWidget(self.log_view, stretch=1)

        root.addWidget(self._build_footer())

    def _build_footer(self) -> QLabel:
        footer = QLabel(
            f'{APP_NAME} v{__version__} &nbsp;—&nbsp; '
            f'<a href="{AUTHOR_URL}" style="color:#1565c0; text-decoration:none;">'
            f"{_escape(FOOTER_TEXT)}</a>"
        )
        footer.setObjectName("footer")
        footer.setOpenExternalLinks(True)
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color:#616161; padding:6px; font-size:12px;")
        return footer

    def _build_paths_group(self) -> QGroupBox:
        box = QGroupBox("Mirror configuration")
        grid = QGridLayout(box)
        grid.addWidget(QLabel("Source path:"), 0, 0)
        self.source_label = QLabel("(not configured)")
        self.source_label.setTextInteractionFlags(
            self.source_label.textInteractionFlags()
        )
        grid.addWidget(self.source_label, 0, 1)
        grid.addWidget(QLabel("Mirror path:"), 1, 0)
        self.mirror_label = QLabel("(not configured)")
        grid.addWidget(self.mirror_label, 1, 1)
        grid.setColumnStretch(1, 1)
        return box

    def _build_status_group(self) -> QGroupBox:
        box = QGroupBox("Status")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        self.state_label = QLabel("Stopped")
        self.state_label.setStyleSheet("font-weight:700; font-size:15px;")
        row.addWidget(self.state_label)
        row.addStretch(1)
        self.watch_label = QLabel("Watcher: idle")
        row.addWidget(self.watch_label)
        layout.addLayout(row)

        self.storage_bar = QProgressBar()
        self.storage_bar.setRange(0, 100)
        self.storage_bar.setFormat("%p% of allocation")
        layout.addWidget(self.storage_bar)

        self.usage_label = QLabel("Usage: –")
        layout.addWidget(self.usage_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        self.stats_label = QLabel(
            "Copied: 0   Unchanged: 0   Removed: 0   Moved: 0   Errors: 0"
        )
        layout.addWidget(self.stats_label)
        return box

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.start_button = QPushButton("Start Sync")
        self.start_button.clicked.connect(self._on_start)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self._on_pause)
        self.restore_button = QPushButton("Restore from Mirror")
        self.restore_button.clicked.connect(self._on_restore)
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.open_settings)
        for button in (
            self.start_button,
            self.pause_button,
            self.restore_button,
            self.settings_button,
        ):
            row.addWidget(button)
        return row

    # -- actions ------------------------------------------------------------
    def _on_start(self) -> None:
        if self.service.state == STOPPED or self.service.state == ERROR:
            if not self.service.config.is_configured():
                self.open_settings()
                if not self.service.config.is_configured():
                    return
            self.service.start()
        elif self.service.state in (RUNNING, PAUSED):
            self.service.stop()

    def _on_pause(self) -> None:
        if self.service.state == RUNNING:
            self.service.pause()
        elif self.service.state == PAUSED:
            self.service.resume()

    def _on_restore(self) -> None:
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore from Mirror")
        confirm.setIcon(QMessageBox.Warning)
        confirm.setText(
            "Restore copies files from the mirror back into the source folder."
        )
        confirm.setInformativeText(
            f"Source: {self.service.config.source_path}\n"
            f"Mirror: {self.service.config.mirror_path}"
        )
        overwrite = QCheckBox("Overwrite existing source files that differ")
        confirm.setCheckBox(overwrite)
        confirm.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        if confirm.exec() != QMessageBox.Ok:
            return
        self.restore_button.setEnabled(False)
        self.statusBar().showMessage("Restoring from mirror…")

        def worker() -> None:
            stats = self.service.restore(overwrite=overwrite.isChecked())
            self.restore_done.emit(stats)

        threading.Thread(target=worker, daemon=True).start()

    def _on_restore_done(self, stats) -> None:
        self.restore_button.setEnabled(True)
        self.statusBar().clearMessage()
        QMessageBox.information(
            self,
            "Restore complete",
            f"Restored {stats.copied} file(s).\n"
            f"Skipped {stats.skipped}.\nErrors: {stats.errors}.",
        )

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.service.config, self)
        if dialog.exec() != SettingsDialog.Accepted:
            return
        new_config: MirrorConfig = dialog.result_config()
        autostart.set_enabled(new_config.autostart_enabled)
        save_config(new_config)
        self.service.reconfigure(new_config)
        self._update_status(self.service.status())

    # -- updates ------------------------------------------------------------
    def _on_log_record(self, record, message: str) -> None:
        # Called from arbitrary threads; hop to the GUI thread via the signal.
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

    def _update_status(self, status: ServiceStatus) -> None:
        self.source_label.setText(status.source_path or "(not configured)")
        self.mirror_label.setText(status.mirror_path or "(not configured)")

        color = _STATE_COLORS.get(status.state, "#616161")
        self.state_label.setText(status.state.capitalize())
        self.state_label.setStyleSheet(
            f"font-weight:700; font-size:15px; color:{color};"
        )
        if status.message:
            self.state_label.setToolTip(status.message)
        self.watch_label.setText(
            "Watcher: active" if status.watching else "Watcher: idle"
        )

        usage = status.usage
        self.storage_bar.setValue(int(usage.percent_used))
        self.usage_label.setText(
            f"Usage: {_human_bytes(usage.used_bytes)} / "
            f"{_human_bytes(usage.allocated_bytes)}  •  "
            f"Disk free: {_human_bytes(usage.disk_free_bytes)}"
        )
        stats = status.stats
        self.stats_label.setText(
            f"Copied: {stats.copied}   Unchanged: {stats.skipped}   "
            f"Removed: {stats.deleted}   Moved: {stats.moved}   "
            f"Errors: {stats.errors}"
        )

        self._sync_buttons(status.state)

    def _sync_buttons(self, state: str) -> None:
        running = state in (RUNNING, PAUSED, STARTING)
        self.start_button.setText("Stop Sync" if running else "Start Sync")
        self.pause_button.setEnabled(state in (RUNNING, PAUSED))
        self.pause_button.setText("Resume" if state == PAUSED else "Pause")
        self.settings_button.setEnabled(not running)
        self.restore_button.setEnabled(state in (STOPPED, ERROR))

    # -- window behaviour ---------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        # If a tray icon is present the app hides instead of quitting; the
        # application object sets this attribute.
        if getattr(self, "minimize_to_tray", False):
            event.ignore()
            self.hide()
            return
        event.accept()


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
