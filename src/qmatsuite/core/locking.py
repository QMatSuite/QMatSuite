"""
Cross-process file locking for calculation operations.

Provides context managers for per-calc locks:
- run.lock: Long-held during entire calculation run (materialization + execution)
- edit.lock: Short-held during YAML file writes

Uses portalocker for cross-platform support (Windows/macOS/Linux).

Reentrancy:
- portalocker locks are NOT re-entrant. This module enforces non-reentrancy
  with a per-thread guard to fail fast instead of deadlocking.
"""

from __future__ import annotations

import contextlib
import threading
from pathlib import Path
from typing import Optional, Set

import portalocker


class CalculationLockError(Exception):
    """Raised when a calculation lock cannot be acquired."""
    pass


class LockReentrancyError(RuntimeError):
    """Raised when attempting to nest locks in the same thread."""
    pass


# Per-thread tracking of held edit locks (by canonical calc_dir path)
_thread_local = threading.local()


def _get_held_edit_locks() -> Set[Path]:
    """Get the set of calc_dir paths for which this thread holds edit locks."""
    if not hasattr(_thread_local, 'held_edit_locks'):
        _thread_local.held_edit_locks = set()
    return _thread_local.held_edit_locks


def _ensure_lock_dir(calc_dir: Path) -> Path:
    """Ensure .locks directory exists in calculation directory."""
    lock_dir = calc_dir / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir


@contextlib.contextmanager
def calc_run_lock(calc_dir: Path, fail_fast: bool = True):
    """
    Context manager for calculation run lock.
    
    This lock is held for the entire duration of a calculation run,
    including materialization and engine execution.
    
    Args:
        calc_dir: Path to calculation directory
        fail_fast: If True, raise CalculationLockError immediately if lock is held.
                   If False, block until lock is available.
    
    Yields:
        None
    
    Raises:
        CalculationLockError: If fail_fast=True and lock cannot be acquired
        
    Example:
        with calc_run_lock(calc_dir, fail_fast=True):
            # Materialize inputs
            # Execute steps
            pass
    """
    lock_dir = _ensure_lock_dir(calc_dir)
    lock_path = lock_dir / "run.lock"
    
    # Open lock file in write mode (required for portalocker on Windows)
    lock_file = open(lock_path, "w")
    
    try:
        if fail_fast:
            # Non-blocking lock acquisition
            try:
                portalocker.lock(lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
            except portalocker.LockException:
                lock_file.close()
                raise CalculationLockError(
                    f"Calculation at {calc_dir} is currently running. "
                    "Please wait for the current run to complete or stop it first."
                )
        else:
            # Blocking lock acquisition
            portalocker.lock(lock_file, portalocker.LOCK_EX)
        
        yield
        
    finally:
        try:
            portalocker.unlock(lock_file)
        except Exception:
            # Ignore unlock errors (file may already be closed)
            pass
        finally:
            lock_file.close()


@contextlib.contextmanager
def calc_edit_lock(calc_dir: Path, fail_fast: bool = False):
    """
    Context manager for calculation edit lock.
    
    This lock is held during YAML file writes (calculation.yaml and step YAML files).
    Should be held for short durations only (< 100ms typically).
    
    IMPORTANT: This lock is NOT re-entrant. Do NOT nest calc_edit_lock calls
    in the same thread. Instead, let save_yaml_doc() acquire the lock internally.
    
    Args:
        calc_dir: Path to calculation directory
        fail_fast: If True, raise CalculationLockError immediately if lock is held.
                   If False, block until lock is available (default for edit operations).
    
    Yields:
        None
    
    Raises:
        CalculationLockError: If fail_fast=True and lock cannot be acquired
        LockReentrancyError: If attempting to nest locks in the same thread
        
    Example:
        # CORRECT: Let save_yaml_doc handle locking internally
        save_yaml_doc(doc, path)
        
        # INCORRECT: Don't nest locks
        with calc_edit_lock(calc_dir):
            save_yaml_doc(doc, path)  # This will raise LockReentrancyError
    """
    # Canonicalize path for thread-local tracking
    canonical_calc_dir = calc_dir.resolve()
    
    # Check for reentrancy in the same thread
    held_locks = _get_held_edit_locks()
    if canonical_calc_dir in held_locks:
        raise LockReentrancyError(
            f"Non-reentrant calc_edit_lock attempted for {calc_dir}. "
            "Do not nest calc_edit_lock around save_yaml_doc(). "
            "The save_yaml_doc() function already acquires the lock internally."
        )
    
    lock_dir = _ensure_lock_dir(calc_dir)
    lock_path = lock_dir / "edit.lock"
    
    # Open lock file in write mode
    lock_file = open(lock_path, "w")
    
    try:
        if fail_fast:
            # Non-blocking lock acquisition
            try:
                portalocker.lock(lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
            except portalocker.LockException:
                lock_file.close()
                raise CalculationLockError(
                    f"Calculation at {calc_dir} is being edited by another process. "
                    "Please try again in a moment."
                )
        else:
            # Blocking lock acquisition (with timeout for safety)
            # Portalocker doesn't support timeout directly, so we use blocking
            # but edit operations should be fast anyway
            portalocker.lock(lock_file, portalocker.LOCK_EX)
        
        # Mark as held in this thread
        held_locks.add(canonical_calc_dir)
        
        try:
            yield
        finally:
            # Always remove from held set, even on exceptions
            held_locks.discard(canonical_calc_dir)
        
    finally:
        try:
            portalocker.unlock(lock_file)
        except Exception:
            # Ignore unlock errors
            pass
        finally:
            lock_file.close()


def find_calc_dir_from_path(path: Path) -> Optional[Path]:
    """
    Find calculation directory by walking up from a file path.
    
    Looks for calculation.yaml in parent directories.
    
    Args:
        path: File path (may be calculation.yaml, step YAML, or file inside calc dir)
    
    Returns:
        Calculation directory path if found, None otherwise
    """
    current = path.resolve()
    if current.is_file():
        current = current.parent
    
    # Walk up to find calculation.yaml
    for _ in range(10):  # Limit depth to avoid infinite loops
        if (current / "calculation.yaml").exists():
            return current
        if current == current.parent:
            break
        current = current.parent
    
    return None

