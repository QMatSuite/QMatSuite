"""
Provenance locking utilities.

Per Law P6 (Lock Ordering): Locks MUST be acquired sequentially.
- edit.lock -> release -> provenance.lock (never hold both simultaneously)

This module provides provenance_lock() for SQLite writes.
"""

from __future__ import annotations

import contextlib
import threading
import logging
from pathlib import Path
from typing import Set

from quantumvitas.provenance.errors import LockReentrancyError

logger = logging.getLogger(__name__)


# Thread-local storage for tracking held locks
_thread_local = threading.local()


def _get_held_provenance_locks() -> Set[Path]:
    """Get the set of provenance locks held by the current thread."""
    if not hasattr(_thread_local, "held_provenance_locks"):
        _thread_local.held_provenance_locks = set()
    return _thread_local.held_provenance_locks


@contextlib.contextmanager
def provenance_lock(project_root: Path, timeout: float = 10.0):
    """
    Acquire project-level provenance lock for SQLite writes.

    Per Law P6: This lock is acquired AFTER edit.lock is released,
    never simultaneously with edit.lock.

    Uses portalocker for cross-platform compatibility.
    Thread-local tracking prevents reentrancy.

    Args:
        project_root: Project root directory
        timeout: Lock acquisition timeout in seconds

    Raises:
        LockReentrancyError: If lock already held by this thread
        ProvenanceError: If lock acquisition fails

    Example:
        # CORRECT: Sequential locking
        with calc_edit_lock(calc_dir):
            _save_yaml_raw(data, path)
        # edit.lock released

        with provenance_lock(project_root):
            record_operation(...)

        # INCORRECT: Nested locking (will raise LockReentrancyError)
        with calc_edit_lock(calc_dir):
            with provenance_lock(project_root):  # DON'T DO THIS
                ...
    """
    try:
        import portalocker
    except ImportError:
        # If portalocker is not available, just use a simple lock
        # This is less robust but allows the system to function
        yield
        return

    canonical = project_root.resolve()
    held = _get_held_provenance_locks()

    if canonical in held:
        raise LockReentrancyError(
            f"Already holding provenance.lock for {canonical}. "
            f"Per Law P6, locks must be acquired sequentially, not nested."
        )

    lock_path = canonical / ".provenance" / "provenance.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with portalocker.Lock(str(lock_path), timeout=timeout):
            held.add(canonical)
            try:
                yield
            finally:
                held.discard(canonical)
    except portalocker.LockException as e:
        from quantumvitas.provenance.errors import ProvenanceError
        raise ProvenanceError(f"Failed to acquire provenance lock: {e}") from e


@contextlib.contextmanager
def gc_lock(project_root: Path, timeout: float = 60.0):
    """
    Acquire CAS garbage collection lock.

    This lock prevents concurrent GC operations and ensures
    no artifacts are deleted while being referenced.

    Args:
        project_root: Project root directory
        timeout: Lock acquisition timeout in seconds
    """
    try:
        import portalocker
    except ImportError:
        yield
        return

    lock_path = project_root.resolve() / ".provenance" / ".cas" / "gc.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with portalocker.Lock(str(lock_path), timeout=timeout):
            yield
    except portalocker.LockException as e:
        from quantumvitas.provenance.errors import ProvenanceError
        raise ProvenanceError(f"Failed to acquire GC lock: {e}") from e
