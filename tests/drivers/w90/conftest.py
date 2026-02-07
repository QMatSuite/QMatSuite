"""Shared fixtures for Wannier90 driver tests.

Provides conditional markers for tests that require real W90 resources:
- w90_binary: wannier90.x available and runnable
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest


def _is_ci() -> bool:
    """Check if running in CI environment."""
    return os.environ.get("CI", "").lower() in ("true", "1", "yes")


def _w90_binary_available() -> bool:
    """Check if a real wannier90.x binary is available."""
    return shutil.which("wannier90.x") is not None


@pytest.fixture(scope="module")
def w90_binary():
    """Skip test if wannier90.x binary is not available."""
    if _is_ci():
        pytest.skip("W90 binary tests skipped in CI")
    if not _w90_binary_available():
        pytest.skip("wannier90.x binary not found")
    return shutil.which("wannier90.x")
