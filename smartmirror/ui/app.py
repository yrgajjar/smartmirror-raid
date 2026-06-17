"""Application bootstrap: QApplication, tray icon and window wiring."""

from __future__ import annotations

import sys

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .. import paths
from ..config import load_config
from ..logger import get_logger, setup_logging
from ..service import PAUSED, RUNNING, MirrorService
from ..version import APP_NAME
from .icon import make_app_icon
from .main_window import MainWindow

log = get_logger("ui")


def _build_tray(app: QApplication, window: MainWindow, service: MirrorService):
    if not QSystemTrayIcon.isSystemTrayAvailable():
        log.info("System tray not available; running without tray icon.")
        return None

    tray = QSystemTrayIcon(app.windowIcon(), app)
    tray.setToolTip(APP_NAME)
    menu = QMenu()

    show_action = QAction("Show dashboard", menu)
    show_action.triggered.connect(lambda: (window.showNormal(), window.activateWindow()))
    menu.addAction(show_action)

    toggle_action = QAction("Pause / Resume", menu)

    def _toggle() -> None:
        if service.state == RUNNING:
            service.pause()
        elif service.state == PAUSED:
            service.resume()

    toggle_action.triggered.connect(_toggle)
    menu.addAction(toggle_action)

    menu.addSeparator()
    quit_action = QAction("Quit", menu)

    def _quit() -> None:
        window.minimize_to_tray = False
        service.stop()
        app.quit()

    quit_action.triggered.connect(_quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)

    def _on_activated(reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            if window.isVisible():
                window.hide()
            else:
                window.showNormal()
                window.activateWindow()

    tray.activated.connect(_on_activated)
    tray.show()
    return tray


def run(start_in_tray: bool = False) -> int:
    paths.ensure_app_dirs()
    setup_logging()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    icon = make_app_icon()
    app.setWindowIcon(icon)

    config = load_config()
    service = MirrorService(config)

    window = MainWindow(service)
    window.setWindowIcon(icon)

    tray = _build_tray(app, window, service)
    window.minimize_to_tray = tray is not None

    if not start_in_tray:
        window.show()
    elif tray is None:
        # No tray to hide into; show the window anyway.
        window.show()

    # Auto-start syncing if a valid configuration already exists.
    if config.is_configured() and not config.validate():
        service.start()

    exit_code = app.exec()
    service.stop()
    return exit_code
