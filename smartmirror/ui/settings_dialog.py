"""Settings: manage mirror pairs and the app-wide preferences."""

from __future__ import annotations

import copy

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .. import i18n
from ..config import GIB, AppConfig, MirrorConfig


class _PathPicker(QHBoxLayout):
    def __init__(self, line_edit: QLineEdit) -> None:
        super().__init__()
        self.line_edit = line_edit
        button = QPushButton(i18n.t("browse"))
        button.clicked.connect(self._browse)
        self.addWidget(line_edit)
        self.addWidget(button)

    def _browse(self) -> None:
        start = self.line_edit.text() or ""
        directory = QFileDialog.getExistingDirectory(None, i18n.t("browse"), start)
        if directory:
            self.line_edit.setText(directory)


class PairEditorDialog(QDialog):
    """Create or edit a single mirror pair."""

    def __init__(self, config: MirrorConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.t("pair_settings_title"))
        self.setMinimumWidth(560)
        self._config = config

        form = QFormLayout()

        self.name_edit = QLineEdit(config.name)
        form.addRow(i18n.t("pair_name"), self.name_edit)

        self.source_edit = QLineEdit(config.source_path)
        form.addRow(i18n.t("source_folder"), _PathPicker(self.source_edit))

        self.mirror_edit = QLineEdit(config.mirror_path)
        form.addRow(i18n.t("mirror_folder"), _PathPicker(self.mirror_edit))

        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(0.1, 1024.0 * 64)
        self.size_spin.setDecimals(1)
        self.size_spin.setSuffix(" GiB")
        self.size_spin.setValue(max(0.1, config.allocated_bytes / GIB))
        form.addRow(i18n.t("mirror_size"), self.size_spin)

        self.versioning_check = QCheckBox(i18n.t("keep_versions"))
        self.versioning_check.setChecked(config.versioning_enabled)
        form.addRow(self.versioning_check)

        self.versions_spin = QSpinBox()
        self.versions_spin.setRange(1, 50)
        self.versions_spin.setValue(config.max_versions)
        form.addRow(i18n.t("versions_to_keep"), self.versions_spin)

        self.hash_check = QCheckBox(i18n.t("hash_verify"))
        self.hash_check.setChecked(config.hash_verify)
        form.addRow(self.hash_check)

        self.exclude_edit = QPlainTextEdit("\n".join(config.ignore_patterns))
        self.exclude_edit.setPlaceholderText("*.tmp\nnode_modules\n*.log")
        self.exclude_edit.setMaximumHeight(110)
        form.addRow(i18n.t("exclude_patterns"), self.exclude_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(i18n.t("ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(i18n.t("cancel"))
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        candidate = self.result_config()
        problems = candidate.validate()
        if problems:
            QMessageBox.warning(
                self, i18n.t("invalid_settings"), "\n".join(f"• {p}" for p in problems)
            )
            return
        self.accept()

    def result_config(self) -> MirrorConfig:
        patterns = [
            line.strip()
            for line in self.exclude_edit.toPlainText().splitlines()
            if line.strip()
        ]
        return MirrorConfig(
            name=self.name_edit.text().strip(),
            source_path=self.source_edit.text().strip(),
            mirror_path=self.mirror_edit.text().strip(),
            allocated_bytes=int(self.size_spin.value() * GIB),
            versioning_enabled=self.versioning_check.isChecked(),
            max_versions=self.versions_spin.value(),
            hash_verify=self.hash_check.isChecked(),
            ignore_patterns=patterns,
            paused=self._config.paused,
            max_retries=self._config.max_retries,
            retry_delay=self._config.retry_delay,
            debounce_seconds=self._config.debounce_seconds,
            storage_warn_percent=self._config.storage_warn_percent,
        )


class SettingsDialog(QDialog):
    """Top-level settings: a list of mirror pairs plus global preferences."""

    def __init__(self, app_config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.t("title_settings"))
        self.setMinimumWidth(620)
        # Work on a copy so Cancel discards everything.
        self._app = copy.deepcopy(app_config)

        root = QVBoxLayout(self)

        pairs_box = QGroupBox(i18n.t("mirror_pairs"))
        pairs_layout = QVBoxLayout(pairs_box)
        self.pairs_list = QListWidget()
        self.pairs_list.itemDoubleClicked.connect(lambda *_: self._edit_pair())
        pairs_layout.addWidget(self.pairs_list)

        pair_buttons = QHBoxLayout()
        add_btn = QPushButton(i18n.t("add"))
        add_btn.clicked.connect(self._add_pair)
        edit_btn = QPushButton(i18n.t("edit"))
        edit_btn.clicked.connect(self._edit_pair)
        remove_btn = QPushButton(i18n.t("remove"))
        remove_btn.clicked.connect(self._remove_pair)
        for btn in (add_btn, edit_btn, remove_btn):
            pair_buttons.addWidget(btn)
        pair_buttons.addStretch(1)
        pairs_layout.addLayout(pair_buttons)
        root.addWidget(pairs_box)

        global_box = QGroupBox(i18n.t("global_settings"))
        global_form = QFormLayout(global_box)

        self.language_combo = QComboBox()
        for code, label in i18n.available_languages().items():
            self.language_combo.addItem(label, code)
        self._select_language(self._app.language)
        global_form.addRow(i18n.t("language"), self.language_combo)

        self.autostart_check = QCheckBox(i18n.t("start_on_login"))
        self.autostart_check.setChecked(self._app.autostart_enabled)
        global_form.addRow(self.autostart_check)
        root.addWidget(global_box)

        note = QLabel(i18n.t("settings_note"))
        note.setWordWrap(True)
        note.setStyleSheet("color: #b26a00;")
        root.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(i18n.t("ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(i18n.t("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._refresh_list()

    # -- helpers ------------------------------------------------------------
    def _select_language(self, code: str) -> None:
        idx = self.language_combo.findData(code)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)

    def _refresh_list(self) -> None:
        self.pairs_list.clear()
        for pair in self._app.pairs:
            text = (
                f"{pair.label()}  —  {pair.source_path or '(no source)'} → "
                f"{pair.mirror_path or '(no mirror)'}"
            )
            self.pairs_list.addItem(QListWidgetItem(text))

    def _current_row(self) -> int:
        return self.pairs_list.currentRow()

    # -- pair actions -------------------------------------------------------
    def _add_pair(self) -> None:
        dialog = PairEditorDialog(MirrorConfig(), self)
        if dialog.exec() == QDialog.Accepted:
            self._app.pairs.append(dialog.result_config())
            self._refresh_list()
            self.pairs_list.setCurrentRow(len(self._app.pairs) - 1)

    def _edit_pair(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        dialog = PairEditorDialog(self._app.pairs[row], self)
        if dialog.exec() == QDialog.Accepted:
            self._app.pairs[row] = dialog.result_config()
            self._refresh_list()
            self.pairs_list.setCurrentRow(row)

    def _remove_pair(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        del self._app.pairs[row]
        self._refresh_list()

    # -- result -------------------------------------------------------------
    def result_config(self) -> AppConfig:
        self._app.language = self.language_combo.currentData()
        self._app.autostart_enabled = self.autostart_check.isChecked()
        return self._app
