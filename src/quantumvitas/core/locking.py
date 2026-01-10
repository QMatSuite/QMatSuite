"""
Cross-process file locking for calculation operations.

Provides context managers for per-calc locks:
- run.lock: Long-held during entire calculation run (materialization + execution)
- edit.lock: Short-held during YAML file writes

Uses portalocker for cross-platform support (Windows/macOS/Linux).
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Optional

import portalocker


class CalculationLockError(Exception):
    """Raised when a calculation lock cannot be acquired."""
    pass


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
    
    Args:
        calc_dir: Path to calculation directory
        fail_fast: If True, raise CalculationLockError immediately if lock is held.
                   If False, block until lock is available (default for edit operations).
    
    Yields:
        None
    
    Raises:
        CalculationLockError: If fail_fast=True and lock cannot be acquired
        
    Example:
        with calc_edit_lock(calc_dir, fail_fast=False):
            # Write calculation.yaml or step YAML
            save_yaml_doc(doc, path)
    """
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
        
        yield
        
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

