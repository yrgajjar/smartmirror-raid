from __future__ import annotations

from types import SimpleNamespace

from smartmirror.sync_engine import DELETE, MOVE, UPSERT
from smartmirror.watcher import _EngineEventHandler

from .helpers import make_engine


def _drain(engine):
    events = []
    while not engine._queue.empty():
        events.append(engine._queue.get())
    return events


def test_handler_translates_events(tmp_path):
    _source, _mirror, engine = make_engine(tmp_path)
    handler = _EngineEventHandler(engine)

    handler.on_created(SimpleNamespace(src_path="/s/a.txt", is_directory=False))
    handler.on_modified(SimpleNamespace(src_path="/s/a.txt", is_directory=False))
    handler.on_deleted(SimpleNamespace(src_path="/s/b.txt", is_directory=False))
    handler.on_moved(
        SimpleNamespace(src_path="/s/c.txt", dest_path="/s/d.txt", is_directory=False)
    )

    events = _drain(engine)
    actions = [(e.action, e.src_path, e.dest_path) for e in events]
    assert ("upsert", "/s/a.txt", None) in actions
    assert ("delete", "/s/b.txt", None) in actions
    assert (MOVE, "/s/c.txt", "/s/d.txt") in actions


def test_modified_directory_ignored(tmp_path):
    _source, _mirror, engine = make_engine(tmp_path)
    handler = _EngineEventHandler(engine)
    handler.on_modified(SimpleNamespace(src_path="/s/dir", is_directory=True))
    assert engine._queue.empty()


def test_enqueue_coalesces_duplicates(tmp_path):
    _source, _mirror, engine = make_engine(tmp_path)
    handler = _EngineEventHandler(engine)
    for _ in range(5):
        handler.on_modified(SimpleNamespace(src_path="/s/a.txt", is_directory=False))
    events = _drain(engine)
    assert len(events) == 1
    assert events[0].action == UPSERT
    # sanity: DELETE constant import is exercised
    assert DELETE == "delete"
