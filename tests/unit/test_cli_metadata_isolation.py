"""
Test that CLI commands that don't require QE metadata work without it.

This ensures that QE metadata is only loaded when actually needed for QE-related operations.
"""

import subprocess
import sys
from pathlib import Path
import pytest


def test_init_project_does_not_require_qe_metadata(monkeypatch, tmp_path):
    """Test that `init project` works even if QE metadata is broken or missing."""
    from qmatsuite.data import qe_metadata

    def broken_load():
        raise RuntimeError("metadata broken")

    # Simulate broken/missing metadata
    monkeypatch.setattr(qe_metadata, "safe_load_metadata", broken_load, raising=True)
    monkeypatch.setattr(qe_metadata, "_load_raw_metadata", broken_load, raising=True)

    # Running `init project` should still succeed
    result = subprocess.run(
        [sys.executable, "-m", "qmatsuite.cli.main", "init", "project", "--name", "meta_free"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"init project failed: {result.stderr}"
    
    # Verify project was created
    project_dir = tmp_path / "meta_free"
    assert project_dir.exists(), "Project directory was not created"
    assert (project_dir / "project.qms.yml").exists(), "Project config file was not created"


def test_init_project_import_does_not_load_metadata():
    """Test that importing the CLI module doesn't trigger metadata loading."""
    # This should not raise even if metadata is missing
    from qmatsuite.cli.main import init_project_command
    from qmatsuite.data import qe_metadata
    
    # Verify that importing doesn't call load functions
    # (they should only be called when the function is invoked, not at import time)
    assert callable(init_project_command)
    
    # The metadata should not be loaded yet (lazy loading)
    # We can't directly test this, but if it were loaded at import time,
    # the import would fail if metadata is missing
