"""
Provenance database connection management.

Per Law P1 (SSOT Separation): The provenance database is auxiliary.
Deleting .provenance/ must leave the project fully runnable.

Per Law P7 (Graceful Degradation): Database operations may fail;
callers should catch ProvenanceError and continue.
"""

from __future__ import annotations

import sqlite3
import logging
from pathlib import Path
from typing import Optional

from quantumvitas.provenance.errors import ProvenanceError
from quantumvitas.provenance.schema import create_schema, get_schema_version, CURRENT_SCHEMA_VERSION

logger = logging.getLogger(__name__)


def get_provenance_dir(project_root: Path) -> Path:
    """
    Get the provenance directory path.

    Args:
        project_root: Project root directory

    Returns:
        Path to .provenance/ directory
    """
    return project_root / ".provenance"


def get_db_path(project_root: Path) -> Path:
    """
    Get the provenance database path.

    Args:
        project_root: Project root directory

    Returns:
        Path to provenance.db
    """
    return get_provenance_dir(project_root) / "provenance.db"


def ensure_provenance_initialized(project_root: Path) -> bool:
    """
    Initialize provenance for a project if needed.

    Lazy initialization: creates .provenance/ directory and database
    on first provenance-aware operation.

    Args:
        project_root: Project root directory

    Returns:
        True if newly initialized, False if already existed
    """
    provenance_dir = get_provenance_dir(project_root)

    if provenance_dir.exists():
        return False

    # Create directory structure
    provenance_dir.mkdir(parents=True)
    (provenance_dir / ".cas" / "objects").mkdir(parents=True)
    (provenance_dir / ".cas" / "tmp").mkdir(parents=True)

    # Initialize database
    db_path = provenance_dir / "provenance.db"
    conn = sqlite3.connect(str(db_path))
    try:
        create_schema(conn)
    finally:
        conn.close()

    return True


def open_provenance_db(project_root: Path) -> sqlite3.Connection:
    """
    Open provenance database connection.

    Initializes the database if it doesn't exist.

    Args:
        project_root: Project root directory

    Returns:
        SQLite connection with row_factory set to sqlite3.Row

    Raises:
        ProvenanceError: If database cannot be opened
    """
    try:
        ensure_provenance_initialized(project_root)
        db_path = get_db_path(project_root)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Ensure schema is up to date
        version = get_schema_version(conn)
        if version < CURRENT_SCHEMA_VERSION:
            from quantumvitas.provenance.schema import migrate_schema
            migrate_schema(conn, version, CURRENT_SCHEMA_VERSION)

        return conn
    except Exception as e:
        raise ProvenanceError(f"Failed to open provenance database: {e}") from e


class ProvenanceDB:
    """
    Context manager for provenance database operations.

    Usage:
        with ProvenanceDB(project_root) as db:
            db.execute("INSERT INTO operations ...")

    Per Law P7: All operations are wrapped in try/except with logging.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        self.conn = open_provenance_db(self.project_root)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
            finally:
                self.conn.close()
                self.conn = None
        return False  # Don't suppress exceptions
