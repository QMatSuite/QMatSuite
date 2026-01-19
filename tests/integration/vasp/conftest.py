"""Pytest configuration for VASP integration tests."""

import os
import pytest
from pathlib import Path
from typing import Optional


def get_vasp_path() -> Optional[Path]:
    """Get VASP path using the resolver."""
    try:
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        return resolve_vasp_bin()
    except RuntimeError:
        return None


def get_fake_vasp_path() -> Path:
    """Get path to fake_vasp.py script."""
    # Get path relative to this file
    this_file = Path(__file__).resolve()
    # Go from tests/integration/vasp/conftest.py to tests/fixtures/fake_vasp.py
    fake_vasp = this_file.parent.parent.parent / "fixtures" / "fake_vasp.py"
    if not fake_vasp.exists():
        raise RuntimeError(f"fake_vasp.py not found at {fake_vasp}")
    return fake_vasp


VASP_BIN = get_vasp_path()
FAKE_VASP_BIN = get_fake_vasp_path()


@pytest.fixture
def use_fake_vasp(monkeypatch):
    """Fixture to use fake_vasp instead of real VASP."""
    fake_vasp = str(FAKE_VASP_BIN)
    monkeypatch.setenv("QMATS_VASP_STD_BIN", fake_vasp)
    yield fake_vasp
    # Cleanup: remove env var
    monkeypatch.delenv("QMATS_VASP_STD_BIN", raising=False)


@pytest.fixture
def vasp_available():
    """Fixture: skip if VASP not available (real or fake)."""
    # Always allow fake_vasp
    if VASP_BIN is None:
        # Use fake_vasp
        return None  # Will use fake_vasp via use_fake_vasp fixture
    vasp_path = Path(VASP_BIN)
    if not vasp_path.exists():
        return None  # Will use fake_vasp
    return vasp_path


@pytest.fixture
def vasp_engine(use_fake_vasp):
    """Get VASP engine (using fake_vasp if real VASP not available)."""
    from quantumvitas.engine.vasp_engine import VaspEngine
    return VaspEngine()

