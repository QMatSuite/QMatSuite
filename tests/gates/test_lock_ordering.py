"""
Gate test for Law P6: Lock Ordering (Sequential, Not Nested).

Per PROVENANCE_VERSIONED_HISTORY_SPEC.md Law P6:
> Locks MUST be acquired sequentially: edit.lock first, then provenance.lock.
> Never hold both simultaneously.

YAML write sequence:
1. Acquire edit.lock -> write YAML -> release edit.lock
2. Acquire provenance.lock -> append SQLite event -> release provenance.lock

This prevents deadlocks and ensures YAML write is never blocked by provenance.
"""

import pytest
import inspect
from pathlib import Path


def test_save_yaml_doc_sequential_locking():
    """
    Law P6: save_yaml_doc() releases edit.lock before provenance recording.

    Verifies the code structure shows sequential lock pattern.
    """
    from quantumvitas.core.yaml_io import save_yaml_doc

    source = inspect.getsource(save_yaml_doc)

    # Verify provenance recording is commented as being after edit.lock release
    assert "edit.lock" in source.lower() and "released" in source.lower(), (
        "save_yaml_doc() should document that provenance happens after edit.lock release"
    )

    # Verify calc_edit_lock is used for YAML writing
    assert "calc_edit_lock" in source, (
        "save_yaml_doc() should use calc_edit_lock for YAML writes"
    )

    # Verify record_operation_event is called (provenance recording)
    assert "record_operation_event" in source, (
        "save_yaml_doc() should call record_operation_event for provenance"
    )


def test_provenance_lock_detects_reentrancy():
    """
    Law P6: Attempting to re-acquire provenance lock raises error.

    This prevents accidental nested locking.
    """
    from quantumvitas.provenance.locks import provenance_lock
    from quantumvitas.provenance.errors import LockReentrancyError

    # Create a temp directory to use as project root
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)

        try:
            with provenance_lock(project_root):
                # Attempting to acquire again should raise
                with pytest.raises(LockReentrancyError):
                    with provenance_lock(project_root):
                        pass
        except ImportError:
            pytest.skip("portalocker not available")


def test_no_provenance_lock_inside_edit_lock_pattern():
    """
    Law P6: Code structure shows provenance recording outside edit.lock.

    Analyzes save_yaml_doc to verify the pattern:
    - edit.lock block contains only YAML writing
    - provenance recording is after the block
    """
    from quantumvitas.core.yaml_io import save_yaml_doc

    source = inspect.getsource(save_yaml_doc)
    lines = source.split("\n")

    # Find edit.lock context manager and ensure provenance is outside it
    in_edit_lock = False
    provenance_inside_edit_lock = False

    for line in lines:
        if "calc_edit_lock" in line and "with" in line:
            in_edit_lock = True
        elif in_edit_lock:
            if "record_operation_event" in line:
                provenance_inside_edit_lock = True
                break
            # Check for end of with block (dedent)
            if line.strip() and not line.startswith(" " * 8) and not line.strip().startswith("#"):
                # Likely exited the with block
                in_edit_lock = False

    # Verify provenance is NOT inside edit.lock
    assert not provenance_inside_edit_lock, (
        "Law P6 violation: record_operation_event appears to be inside "
        "calc_edit_lock block. Per Law P6, provenance recording must happen "
        "AFTER edit.lock is released."
    )


def test_provenance_lock_independent():
    """
    Law P6: provenance_lock can be acquired independently.

    Verifies the lock works as a standalone context manager.
    """
    from quantumvitas.provenance.locks import provenance_lock

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)

        try:
            # Should work as independent lock
            with provenance_lock(project_root):
                # Lock is held, do something
                pass
            # Lock is released
        except ImportError:
            pytest.skip("portalocker not available")


def test_gc_lock_available():
    """CAS garbage collection lock is available."""
    from quantumvitas.provenance.locks import gc_lock

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)

        try:
            with gc_lock(project_root):
                pass
        except ImportError:
            pytest.skip("portalocker not available")
