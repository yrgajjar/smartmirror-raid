from __future__ import annotations

from smartmirror.versioning import VERSIONS_DIRNAME

from .helpers import make_engine, write_file


def test_list_mirror_files_excludes_versions_and_tmp(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    write_file(source / "a.txt", "one")
    write_file(source / "sub" / "b.txt", "two")
    engine.full_sync()
    # A leftover temp file and a versions directory must not be listed.
    write_file(mirror / "leftover.smtmp", "junk")
    listing = engine.list_mirror_files()
    assert "a.txt" in listing
    assert any(name.endswith("b.txt") for name in listing)
    assert all(not name.endswith(".smtmp") for name in listing)
    assert all(VERSIONS_DIRNAME not in name for name in listing)


def test_restore_single_file(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    write_file(source / "doc.txt", "hello")
    engine.full_sync()
    # Delete from source, then restore just that file.
    (source / "doc.txt").unlink()
    result = engine.restore_file("doc.txt")
    assert result == "restored"
    assert (source / "doc.txt").read_text() == "hello"


def test_restore_file_skips_existing_without_overwrite(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    write_file(source / "doc.txt", "v1")
    engine.full_sync()
    write_file(source / "doc.txt", "v2-local")
    # Without overwrite the differing local copy is preserved.
    assert engine.restore_file("doc.txt", overwrite=False) == "skipped"
    assert (source / "doc.txt").read_text() == "v2-local"
    # With overwrite it is replaced by the mirror copy.
    assert engine.restore_file("doc.txt", overwrite=True) == "restored"
    assert (source / "doc.txt").read_text() == "v1"


def test_restore_specific_version(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    write_file(source / "doc.txt", "version-1")
    engine.full_sync()
    write_file(source / "doc.txt", "version-2")
    engine.full_sync()
    versions = engine.versions_for("doc.txt")
    assert versions, "expected at least one stored version"
    # The oldest stored version holds the original content.
    result = engine.restore_version("doc.txt", versions[0], overwrite=True)
    assert result == "restored"
    assert (source / "doc.txt").read_text() == "version-1"


def test_restore_missing_file_reports_missing(tmp_path):
    source, mirror, engine = make_engine(tmp_path)
    assert engine.restore_file("nope.txt") == "missing"
