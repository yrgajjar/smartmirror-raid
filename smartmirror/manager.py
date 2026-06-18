"""Orchestrates several independent mirror pairs.

Each source -> mirror pair is handled by its own :class:`MirrorService`
(unchanged, single-pair). :class:`MirrorManager` simply owns a list of them,
persists the combined :class:`AppConfig`, fans status/log events out to UI
listeners (tagged with the pair index) and applies the app-wide preferences
(UI language, launch-on-login).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import autostart
from .config import AppConfig, MirrorConfig, load_app_config, save_app_config
from .logger import get_logger
from .service import MirrorService, ServiceStatus

log = get_logger("manager")

ManagerStatusListener = Callable[[int, ServiceStatus], None]
ManagerLogListener = Callable[[int, str, str], None]


class MirrorManager:
    """Owns every configured mirror pair and the global app preferences."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        config_path: Path | None = None,
    ) -> None:
        self.config_path = config_path
        self.app_config = (
            app_config if app_config is not None else load_app_config(config_path)
        )
        self.services: list[MirrorService] = []
        self._status_listeners: list[ManagerStatusListener] = []
        self._log_listeners: list[ManagerLogListener] = []
        for pair in self.app_config.pairs:
            self._attach_service(pair)

    # -- internals ----------------------------------------------------------
    def _index_of(self, service: MirrorService) -> int:
        try:
            return self.services.index(service)
        except ValueError:  # pragma: no cover - defensive
            return -1

    def _attach_service(self, pair: MirrorConfig) -> MirrorService:
        service = MirrorService(pair)
        service.add_status_listener(self._make_status_relay(service))
        service.add_log_listener(self._make_log_relay(service))
        self.services.append(service)
        return service

    def _make_status_relay(
        self, service: MirrorService
    ) -> Callable[[ServiceStatus], None]:
        def relay(status: ServiceStatus) -> None:
            self._on_status(self._index_of(service), status)

        return relay

    def _make_log_relay(
        self, service: MirrorService
    ) -> Callable[[str, str], None]:
        def relay(level: str, message: str) -> None:
            self._on_log(self._index_of(service), level, message)

        return relay

    def _on_status(self, index: int, status: ServiceStatus) -> None:
        if index < 0:
            return
        for listener in list(self._status_listeners):
            try:
                listener(index, status)
            except Exception:  # pragma: no cover
                pass

    def _on_log(self, index: int, level: str, message: str) -> None:
        if index < 0:
            return
        for listener in list(self._log_listeners):
            try:
                listener(index, level, message)
            except Exception:  # pragma: no cover
                pass

    # -- listeners ----------------------------------------------------------
    def add_status_listener(self, listener: ManagerStatusListener) -> None:
        self._status_listeners.append(listener)

    def add_log_listener(self, listener: ManagerLogListener) -> None:
        self._log_listeners.append(listener)

    # -- persistence --------------------------------------------------------
    def save(self) -> None:
        save_app_config(self.app_config, self.config_path)

    # -- pair management ----------------------------------------------------
    def __len__(self) -> int:
        return len(self.services)

    def __getitem__(self, index: int) -> MirrorService:
        return self.services[index]

    def is_configured(self) -> bool:
        return self.app_config.is_configured()

    def labels(self) -> list[str]:
        return [s.config.label() for s in self.services]

    def add_pair(self, pair: MirrorConfig) -> int:
        self.app_config.pairs.append(pair)
        self._attach_service(pair)
        self.save()
        return len(self.services) - 1

    def update_pair(self, index: int, pair: MirrorConfig) -> None:
        self.app_config.pairs[index] = pair
        self.services[index].reconfigure(pair)
        self.save()

    def remove_pair(self, index: int) -> None:
        service = self.services.pop(index)
        service.stop()
        del self.app_config.pairs[index]
        self.save()

    def replace_config(self, app_config: AppConfig) -> None:
        """Swap in a whole new :class:`AppConfig` (used by the Settings dialog).

        Every existing service is stopped and rebuilt from the new pair list;
        listeners registered on the manager keep working because they are bound
        to the manager, not to individual services.
        """
        self.stop_all()
        self.app_config = app_config
        self.services = []
        for pair in app_config.pairs:
            self._attach_service(pair)
        autostart.set_enabled(app_config.autostart_enabled)
        self.save()

    # -- global preferences -------------------------------------------------
    def set_language(self, language: str) -> None:
        self.app_config.language = language
        self.save()

    def set_autostart(self, enabled: bool) -> bool:
        self.app_config.autostart_enabled = enabled
        ok = autostart.set_enabled(enabled)
        self.save()
        return ok

    # -- lifecycle (per pair) ----------------------------------------------
    def start(self, index: int) -> None:
        self.services[index].start()

    def stop(self, index: int) -> None:
        self.services[index].stop()

    def pause(self, index: int) -> None:
        self.services[index].pause()

    def resume(self, index: int) -> None:
        self.services[index].resume()

    # -- lifecycle (all pairs) ---------------------------------------------
    def start_all(self) -> None:
        for service in self.services:
            if service.config.is_configured() and not service.config.validate():
                service.start()

    def stop_all(self) -> None:
        for service in self.services:
            service.stop()

    def pause_all(self) -> None:
        for service in self.services:
            service.pause()

    def resume_all(self) -> None:
        for service in self.services:
            service.resume()

    # -- storage alerts -----------------------------------------------------
    def check_storage_alerts(self) -> list[tuple[int, str]]:
        alerts: list[tuple[int, str]] = []
        for index, service in enumerate(self.services):
            msg = service.check_storage_alert()
            if msg:
                alerts.append((index, msg))
        return alerts
