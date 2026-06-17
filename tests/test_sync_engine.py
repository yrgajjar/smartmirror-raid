from __future__ import annotations

import os

from smartmirror.sync_engine import UPSERT, SyncEvent

from .helpers import make_engine, write_file


def test_full_sync_copies_files(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    write_file(source / "a.txt", "hello")
    write_file(source / "nested" / "b.txt", "world")

    engine.full_sync()

    assert (mirror / "a.txt").read_text() == "hello"
    assert (mirror / "nested" / "b.txt").read_text() == "world"
    assert engine.stats.copied == 2


def test_incremental_skip(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    write_file(source / "a.txt", "hello")
    engine.full_sync()
    # Re-running upsert on an unchanged file should skip it.
    result = engine.upsert_file(source / "a.txt")
    assert result == "skipped"


def test_modify_resyncs_and_versions(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    src_file = write_file(source / "a.txt", "v1")
    engine.full_sync()

    src_file.write_text("v2-longer", encoding="utf-8")
    result = engine.upsert_file(src_file)

    assert result == "copied"
    assert (mirror / "a.txt").read_text() == "v2-longer"
    # The previous mirror content should be retained as a version.
    versions = engine.versioning.list_versions("a.txt")
    assert len(versions) == 1
    assert versions[0].read_text() == "v1"


def test_delete_removes_and_versions(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    src_file = write_file(source / "a.txt", "data")
    engine.full_sync()
    assert (mirror / "a.txt").exists()

    result = engine.delete_path(src_file)

    assert result == "deleted"
    assert not (mirror / "a.txt").exists()
    versions = engine.versioning.list_versions("a.txt")
    assert len(versions) == 1
    assert versions[0].read_text() == "data"


def test_move_renames_mirror(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    old = write_file(source / "old.txt", "data")
    engine.full_sync()
    new = source / "renamed.txt"
    os.replace(old, new)

    result = engine.move_path(old, new)

    assert result == "moved"
    assert not (mirror / "old.txt").exists()
    assert (mirror / "renamed.txt").read_text() == "data"


def test_overflow_prevented(tmp_path):
    source, mirror, engine = make_engine(tmp_path, allocated=10)
    src_file = write_file(source / "big.txt", "this is definitely more than ten bytes")

    result = engine.upsert_file(src_file)

    assert result == "full"
    assert engine.stats.errors == 1
    assert not (mirror / "big.txt").exists()


def test_prune_removes_stale_mirror(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    write_file(source / "keep.txt", "keep")
    # Pre-existing mirror file with no source counterpart.
    write_file(mirror / "stale.txt", "stale")

    engine.full_sync(prune=True)

    assert (mirror / "keep.txt").exists()
    assert not (mirror / "stale.txt").exists()


def test_restore_respects_existing(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    write_file(mirror / "only_in_mirror.txt", "recovered")
    write_file(mirror / "conflict.txt", "MIRROR")
    write_file(source / "conflict.txt", "SOURCE")

    stats = engine.restore(overwrite=False)
    assert (source / "only_in_mirror.txt").read_text() == "recovered"
    assert (source / "conflict.txt").read_text() == "SOURCE"  # preserved
    assert stats.copied == 1
    assert stats.skipped == 1

    stats2 = engine.restore(overwrite=True)
    assert (source / "conflict.txt").read_text() == "MIRROR"
    assert stats2.copied == 1


def test_versions_dir_ignored(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    write_file(source / "a.txt", "x")
    engine.full_sync()
    # The mirror's versions directory must never be mirrored or pruned away.
    assert engine.should_ignore(engine.versioning.versions_root() / "foo")


def test_queue_worker_processes_events(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    src_file = write_file(source / "a.txt", "queued")
    engine.start()
    try:
        engine.enqueue(SyncEvent(UPSERT, str(src_file)))
        engine.wait_until_idle(timeout=5)
    finally:
        engine.stop()
    assert (mirror / "a.txt").read_text() == "queued"
    assert engine.stats.copied == 1


def test_pause_blocks_processing(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    src_file = write_file(source / "a.txt", "data")
    engine.start()
    try:
        engine.pause()
        assert engine.is_paused
        engine.enqueue(SyncEvent(UPSERT, str(src_file)))
        # While paused nothing should be mirrored.
        import time

        time.sleep(0.3)
        assert not (mirror / "a.txt").exists()
        engine.resume()
        engine.wait_until_idle(timeout=5)
    finally:
        engine.stop()
    assert (mirror / "a.txt").exists()
