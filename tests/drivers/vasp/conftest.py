"""Shared fixtures for VASP driver tests.

Provides conditional markers for tests that require real VASP resources:
- vasp_binary: VASP binary (vasp_std) available and runnable
- potcar_library: POTCAR library (potpaw_PBE.64) available
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _is_ci() -> bool:
    """Check if running in CI environment."""
    return os.environ.get("CI", "").lower() in ("true", "1", "yes")


def _vasp_binary_available() -> bool:
    """Check if a real VASP binary is available."""
    from qmatsuite.drivers.vasp.engine.vasp_runner import find_vasp_binary

    path = find_vasp_binary("vasp_std")
    if path is None:
        return False
    # Exclude fake_vasp.py (test fixture)
    if path.suffix == ".py":
        return False
    return True


def _potcar_library_available() -> bool:
    """Check if a POTCAR library is available."""
    from qmatsuite.drivers.vasp.engine.vasp_potcar import (
        get_default_potcar_root,
        POTCAR_LIBRARY_DIRS,
    )

    root = get_default_potcar_root()
    if root is None:
        return False
    for lib in POTCAR_LIBRARY_DIRS.values():
        if (root / lib).is_dir():
            return True
    return False


@pytest.fixture(scope="module")
def vasp_binary():
    """Skip test if VASP binary is not available."""
    if _is_ci():
        pytest.skip("VASP binary tests skipped in CI")
    if not _vasp_binary_available():
        pytest.skip("VASP binary not found")
    from qmatsuite.drivers.vasp.engine.vasp_runner import find_vasp_binary

    return find_vasp_binary("vasp_std")


@pytest.fixture(scope="module")
def potcar_library():
    """Skip test if POTCAR library is not available."""
    if _is_ci():
        pytest.skip("POTCAR library tests skipped in CI")
    if not _potcar_library_available():
        pytest.skip("POTCAR library not found")
    from qmatsuite.drivers.vasp.engine.vasp_potcar import get_default_potcar_root

    return get_default_potcar_root()


@pytest.fixture
def si_scf_case_dir() -> Path:
    """Path to the Si SCF curated sample."""
    samples = Path(__file__).resolve().parent.parent.parent / "inputformat" / "samples" / "vasp" / "si_scf"
    if not samples.is_dir():
        pytest.skip("Si SCF sample directory not found")
    return samples
