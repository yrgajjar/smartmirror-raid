"""Logging configuration with an in-memory buffer for the UI."""

from __future__ import annotations

import logging
import threading
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from . import paths

ROOT_LOGGER_NAME = "smartmirror"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LogSubscriber = Callable[[logging.LogRecord, str], None]


class BufferLogHandler(logging.Handler):
    """Keeps the most recent log lines and notifies UI subscribers.

    Qt signals are connected through :meth:`subscribe`; the callback is invoked
    from whichever thread emitted the log record, so subscribers must marshal
    back to the GUI thread themselves.
    """

    def __init__(self, capacity: int = 5000) -> None:
        super().__init__()
        self._records: deque[str] = deque(maxlen=capacity)
        self._subscribers: list[LogSubscriber] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:  # pragma: no cover - formatting should not fail
            return
        with self._lock:
            self._records.append(message)
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(record, message)
            except Exception:  # pragma: no cover - subscriber errors are non-fatal
                pass

    def history(self) -> list[str]:
        with self._lock:
            return list(self._records)

    def subscribe(self, callback: LogSubscriber) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: LogSubscriber) -> None:
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)


_buffer_handler: BufferLogHandler | None = None
_configured = False


def setup_logging(
    log_directory: Path | None = None,
    level: int = logging.INFO,
) -> BufferLogHandler:
    """Configure the package logger. Safe to call more than once."""
    global _buffer_handler, _configured

    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if _configured and _buffer_handler is not None:
        return _buffer_handler

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    log_directory = log_directory or paths.log_dir()
    try:
        log_directory.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_directory / "smartmirror.log",
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Logging to disk is best-effort; never crash because of it.
        pass

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    _buffer_handler = BufferLogHandler()
    _buffer_handler.setFormatter(formatter)
    logger.addHandler(_buffer_handler)

    _configured = True
    return _buffer_handler


def get_buffer_handler() -> BufferLogHandler:
    if _buffer_handler is None:
        return setup_logging()
    return _buffer_handler


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")
