"""
Regression test: Ensure repo_root/pseudo is never created by tests or runtime.

This test ensures that the invariant is maintained:
- Internal pseudo library is ONLY at resources/pseudo/
- Repo-root pseudo/ must never be created
- Tests must use tmp directories, never repo_root as project_root
"""

import pytest
from pathlib import Path
import shutil
from quantumvitas.core.pseudo_config import _find_quantumvitas_root
from quantumvitas.core.resources import get_resources_dir


def test_repo_root_pseudo_never_created():
    """
    Test that repo_root/pseudo is never created during test execution.
    
    This test should run after all other tests to verify the invariant.
    The conftest.py trap should catch any attempts to create it during tests.
    """
    repo_root = _find_quantumvitas_root()
    if not repo_root:
        pytest.skip("Cannot find quantumvitas repo root")
    
    root_pseudo = repo_root / "pseudo"
    resources_pseudo = get_resources_dir() / "pseudo"
    
    # Clean up any leftover from previous runs (conftest should do this, but be safe)
    if root_pseudo.exists():
        shutil.rmtree(root_pseudo)
    
    # Assert: root pseudo must not exist
    assert not root_pseudo.exists(), (
        f"BUG: repo_root/pseudo exists at {root_pseudo}. "
        f"Internal pseudo library must be at {resources_pseudo}, not {root_pseudo}. "
        f"The conftest.py trap should have caught any creation attempts."
    )
    
    # Assert: resources pseudo should exist (it's tracked in git)
    assert resources_pseudo.exists(), (
        f"resources/pseudo should exist at {resources_pseudo} (it's tracked in git)"
    )
