"""Programmatically generated application icon (no binary asset required)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap


def make_app_icon(size: int = 256) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#1565c0"))
    gradient.setColorAt(1.0, QColor("#0d47a1"))
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.NoPen)

    margin = size * 0.08
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.drawRoundedRect(rect, size * 0.18, size * 0.18)

    # Two mirrored discs to suggest RAID-1 style duplication.
    painter.setBrush(QColor("#ffffff"))
    disc_w = size * 0.16
    disc_h = size * 0.10
    cx = size / 2
    for offset in (-size * 0.13, size * 0.13):
        painter.drawEllipse(
            QRectF(cx - disc_w, size * 0.34 + offset, 2 * disc_w, disc_h)
        )

    painter.setPen(QColor("#ffffff"))
    font = QFont()
    font.setBold(True)
    font.setPointSizeF(size * 0.16)
    painter.setFont(font)
    painter.drawText(
        QRectF(0, size * 0.58, size, size * 0.34),
        Qt.AlignCenter,
        "RAID",
    )
    painter.end()

    return QIcon(pixmap)
