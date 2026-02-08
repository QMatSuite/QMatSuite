"""
Regression tests for provenance database initialization and repair.

Tests that ensure_provenance_initialized handles corrupt/incomplete databases
gracefully by reinitializing the schema when needed.
"""

import sqlite3

import pytest

from quantumvitas.provenance.db import (
    ensure_provenance_initialized,
    get_provenance_dir,
    open_provenance_db,
)


def test_ensure_initialized_fresh(tmp_path):
    """Fresh project: creates .provenance/ and valid DB."""
    result = ensure_provenance_initialized(tmp_path)
    assert result is True
    provenance_dir = get_provenance_dir(tmp_path)
    assert provenance_dir.exists()
    assert (provenance_dir / "provenance.db").exists()
    # Verify schema is queryable
    conn = open_provenance_db(tmp_path)
    try:
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        assert row[0] is not None and row[0] >= 1
    finally:
        conn.close()


def test_ensure_initialized_skips_valid_db(tmp_path):
    """Already initialized: returns False (no reinit)."""
    ensure_provenance_initialized(tmp_path)
    result = ensure_provenance_initialized(tmp_path)
    assert result is False


def test_ensure_initialized_repairs_missing_db(tmp_path):
    """Directory exists but DB file is missing: reinitializes."""
    provenance_dir = get_provenance_dir(tmp_path)
    provenance_dir.mkdir(parents=True)
    # DB file is missing
    assert not (provenance_dir / "provenance.db").exists()

    result = ensure_provenance_initialized(tmp_path)
    assert result is True
    assert (provenance_dir / "provenance.db").exists()
    # Verify schema is valid
    conn = open_provenance_db(tmp_path)
    conn.close()


def test_ensure_initialized_repairs_corrupt_db(tmp_path):
    """Directory + corrupt DB file: reinitializes schema."""
    provenance_dir = get_provenance_dir(tmp_path)
    provenance_dir.mkdir(parents=True)
    (provenance_dir / "provenance.db").write_text("not a sqlite database")

    result = ensure_provenance_initialized(tmp_path)
    assert result is True
    # Verify schema is now valid
    conn = open_provenance_db(tmp_path)
    try:
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        assert row[0] is not None
    finally:
        conn.close()


def test_ensure_initialized_repairs_empty_sqlite(tmp_path):
    """Directory + empty SQLite DB (no tables): reinitializes schema."""
    provenance_dir = get_provenance_dir(tmp_path)
    provenance_dir.mkdir(parents=True)
    # Create empty SQLite DB (valid file but no tables)
    db_path = provenance_dir / "provenance.db"
    conn = sqlite3.connect(str(db_path))
    conn.close()

    result = ensure_provenance_initialized(tmp_path)
    assert result is True
    # Verify schema is now valid
    conn = open_provenance_db(tmp_path)
    try:
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        assert row[0] is not None
    finally:
        conn.close()


def test_ensure_initialized_creates_cas_dirs(tmp_path):
    """Verify CAS subdirectories are created during init."""
    ensure_provenance_initialized(tmp_path)
    provenance_dir = get_provenance_dir(tmp_path)
    assert (provenance_dir / ".cas" / "objects").is_dir()
    assert (provenance_dir / ".cas" / "tmp").is_dir()


def test_ensure_initialized_repairs_cas_dirs(tmp_path):
    """Directory exists without CAS subdirs: creates them during repair."""
    provenance_dir = get_provenance_dir(tmp_path)
    provenance_dir.mkdir(parents=True)
    # No CAS dirs, no DB
    result = ensure_provenance_initialized(tmp_path)
    assert result is True
    assert (provenance_dir / ".cas" / "objects").is_dir()
    assert (provenance_dir / ".cas" / "tmp").is_dir()
