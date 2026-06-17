"""Settings dialog for configuring the mirror."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..config import GIB, MirrorConfig


class _PathPicker(QHBoxLayout):
    def __init__(self, line_edit: QLineEdit) -> None:
        super().__init__()
        self.line_edit = line_edit
        button = QPushButton("Browse…")
        button.clicked.connect(self._browse)
        self.addWidget(line_edit)
        self.addWidget(button)

    def _browse(self) -> None:
        start = self.line_edit.text() or ""
        directory = QFileDialog.getExistingDirectory(
            None, "Select folder", start
        )
        if directory:
            self.line_edit.setText(directory)


class SettingsDialog(QDialog):
    def __init__(self, config: MirrorConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SmartMirror RAID — Settings")
        self.setMinimumWidth(560)
        self._config = config

        form = QFormLayout()

        self.source_edit = QLineEdit(config.source_path)
        form.addRow("Source folder", _PathPicker(self.source_edit))

        self.mirror_edit = QLineEdit(config.mirror_path)
        form.addRow("Mirror folder", _PathPicker(self.mirror_edit))

        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(0.1, 1024.0 * 64)
        self.size_spin.setDecimals(1)
        self.size_spin.setSuffix(" GiB")
        self.size_spin.setValue(max(0.1, config.allocated_bytes / GIB))
        form.addRow("Mirror size (allocation)", self.size_spin)

        self.versioning_check = QCheckBox("Keep previous versions of changed files")
        self.versioning_check.setChecked(config.versioning_enabled)
        form.addRow(self.versioning_check)

        self.versions_spin = QSpinBox()
        self.versions_spin.setRange(1, 50)
        self.versions_spin.setValue(config.max_versions)
        form.addRow("Versions to keep", self.versions_spin)

        self.hash_check = QCheckBox(
            "Verify file contents with a hash (slower, more precise)"
        )
        self.hash_check.setChecked(config.hash_verify)
        form.addRow(self.hash_check)

        self.autostart_check = QCheckBox("Start automatically on login")
        self.autostart_check.setChecked(config.autostart_enabled)
        form.addRow(self.autostart_check)

        warning = QLabel(
            "Note: This is NOT real RAID. It mirrors files on a schedule and "
            "does not protect against disk hardware failure."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b26a00;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(warning)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        candidate = self.result_config()
        problems = candidate.validate()
        if problems:
            QMessageBox.warning(
                self, "Invalid settings", "\n".join(f"• {p}" for p in problems)
            )
            return
        self.accept()

    def result_config(self) -> MirrorConfig:
        return MirrorConfig(
            source_path=self.source_edit.text().strip(),
            mirror_path=self.mirror_edit.text().strip(),
            allocated_bytes=int(self.size_spin.value() * GIB),
            versioning_enabled=self.versioning_check.isChecked(),
            max_versions=self.versions_spin.value(),
            autostart_enabled=self.autostart_check.isChecked(),
            hash_verify=self.hash_check.isChecked(),
            paused=self._config.paused,
            ignore_patterns=list(self._config.ignore_patterns),
        )
