"""Browse mirrored files and restore individual files or older versions."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .. import i18n
from ..service import MirrorService


class VersionBrowserDialog(QDialog):
    """Selective restore: pick a mirrored file (and optionally an older
    version of it) and copy it back into the source folder."""

    def __init__(self, service: MirrorService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle(i18n.t("vb_title"))
        self.setMinimumSize(720, 480)
        self._all_files: list[str] = []

        root = QVBoxLayout(self)

        intro = QLabel(i18n.t("vb_intro"))
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.overwrite_check = QCheckBox(i18n.t("vb_overwrite"))
        self.overwrite_check.setChecked(True)
        root.addWidget(self.overwrite_check)

        columns = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel(i18n.t("vb_files")))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(i18n.t("vb_search"))
        self.filter_edit.textChanged.connect(self._apply_filter)
        left.addWidget(self.filter_edit)
        self.files_list = QListWidget()
        self.files_list.currentItemChanged.connect(self._on_file_changed)
        left.addWidget(self.files_list, stretch=1)
        columns.addLayout(left, stretch=3)

        right = QVBoxLayout()
        right.addWidget(QLabel(i18n.t("vb_versions")))
        self.versions_list = QListWidget()
        right.addWidget(self.versions_list, stretch=1)
        columns.addLayout(right, stretch=2)

        root.addLayout(columns, stretch=1)

        actions = QHBoxLayout()
        self.refresh_button = QPushButton(i18n.t("vb_refresh"))
        self.refresh_button.clicked.connect(self.reload)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        self.restore_file_button = QPushButton(i18n.t("vb_restore_selected"))
        self.restore_file_button.clicked.connect(self._restore_file)
        actions.addWidget(self.restore_file_button)
        self.restore_version_button = QPushButton(i18n.t("vb_restore_version"))
        self.restore_version_button.clicked.connect(self._restore_version)
        actions.addWidget(self.restore_version_button)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(i18n.t("close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.reload()

    # -- data ---------------------------------------------------------------
    def reload(self) -> None:
        self._all_files = self.service.list_mirror_files()
        self._apply_filter(self.filter_edit.text())

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        self.files_list.clear()
        for rel in self._all_files:
            if needle and needle not in rel.lower():
                continue
            self.files_list.addItem(QListWidgetItem(rel))
        if self.files_list.count():
            self.files_list.setCurrentRow(0)
        else:
            self.versions_list.clear()
        self._sync_buttons()

    def _current_rel(self) -> str | None:
        item = self.files_list.currentItem()
        return item.text() if item is not None else None

    def _on_file_changed(self, *_args) -> None:
        self.versions_list.clear()
        rel = self._current_rel()
        if rel is None:
            self._sync_buttons()
            return
        current = QListWidgetItem(i18n.t("vb_current"))
        current.setData(Qt.UserRole, None)
        self.versions_list.addItem(current)
        versions = self.service.versions_for(rel)
        for version in reversed(versions):  # newest first
            label = self._version_label(version)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(version))
            self.versions_list.addItem(item)
        if not versions:
            note = QListWidgetItem(i18n.t("vb_no_versions"))
            note.setFlags(Qt.NoItemFlags)
            self.versions_list.addItem(note)
        self.versions_list.setCurrentRow(0)
        self._sync_buttons()

    @staticmethod
    def _version_label(version: Path) -> str:
        try:
            mtime = version.stat().st_mtime
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
        except OSError:
            stamp = version.name
        return stamp

    def _sync_buttons(self) -> None:
        has_file = self._current_rel() is not None
        self.restore_file_button.setEnabled(has_file)
        self.restore_version_button.setEnabled(has_file)

    # -- actions ------------------------------------------------------------
    def _restore_file(self) -> None:
        rel = self._current_rel()
        if rel is None:
            return
        result = self.service.restore_file(
            rel, overwrite=self.overwrite_check.isChecked()
        )
        self._report(rel, result)

    def _restore_version(self) -> None:
        rel = self._current_rel()
        if rel is None:
            return
        item = self.versions_list.currentItem()
        version_path = item.data(Qt.UserRole) if item is not None else None
        if version_path is None:
            # "Current (mirror copy)" selected -> same as restoring the file.
            result = self.service.restore_file(
                rel, overwrite=self.overwrite_check.isChecked()
            )
        else:
            result = self.service.restore_version(
                rel, version_path, overwrite=self.overwrite_check.isChecked()
            )
        self._report(rel, result)

    def _report(self, rel: str, result: str) -> None:
        if result == "restored":
            QMessageBox.information(
                self, i18n.t("vb_title"), i18n.t("vb_restored", name=rel)
            )
        elif result == "skipped":
            QMessageBox.warning(
                self,
                i18n.t("vb_title"),
                f"{rel}: kept the existing source file "
                "(enable overwrite to replace it).",
            )
        else:
            QMessageBox.critical(
                self, i18n.t("vb_title"), f"{rel}: {result}."
            )
