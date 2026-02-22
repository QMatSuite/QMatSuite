"""Pytest configuration for VASP integration tests."""

import os
import pytest
from pathlib import Path
from typing import Optional


def get_vasp_path() -> Optional[Path]:
    """Get VASP path using the resolver."""
    try:
        from qmatsuite.core.engines.vasp_resolver import resolve_vasp_bin
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
def use_fake_vasp(monkeypatch, tmp_path):
    """Fixture to use fake_vasp instead of real VASP and mock POTCAR directory."""
    fake_vasp = str(FAKE_VASP_BIN)
    monkeypatch.setenv("QMATS_VASP_STD_BIN", fake_vasp)
    
    # Mock get_potcar_dir to return a fake POTCAR directory
    fake_potcar_dir = tmp_path / "fake_potcar" / "potpaw_PBE.64"
    fake_potcar_dir.mkdir(parents=True, exist_ok=True)
    
    # Create fake POTCAR files for common elements
    for element in ["Si", "H", "O", "C", "N"]:
        element_dir = fake_potcar_dir / element
        element_dir.mkdir(exist_ok=True)
        (element_dir / "POTCAR").write_text(f"FAKE POTCAR for {element}\n")
    
    # Mock get_potcar_dir function in both resolver and writer modules
    def mock_get_potcar_dir(potcar_type: str = "PBE") -> Path:
        # Return the appropriate directory based on potcar_type
        if potcar_type == "LDA":
            potcar_dir = tmp_path / "fake_potcar" / "potpaw_LDA.64"
        else:  # PBE or default
            potcar_dir = tmp_path / "fake_potcar" / "potpaw_PBE.64"
        potcar_dir.mkdir(parents=True, exist_ok=True)
        # Create element directories if they don't exist
        for element in ["Si", "H", "O", "C", "N"]:
            element_dir = potcar_dir / element
            element_dir.mkdir(exist_ok=True)
            if not (element_dir / "POTCAR").exists():
                (element_dir / "POTCAR").write_text(f"FAKE POTCAR for {element}\n")
        return potcar_dir
    
    # Mock in resolver module (source of truth)
    import qmatsuite.core.engines.vasp_resolver
    monkeypatch.setattr(
        qmatsuite.core.engines.vasp_resolver,
        "get_potcar_dir",
        mock_get_potcar_dir
    )
    
    # Mock in writer module (where it's imported)
    import qmatsuite.engine.vasp_writer
    monkeypatch.setattr(
        qmatsuite.engine.vasp_writer,
        "get_potcar_dir",
        mock_get_potcar_dir
    )
    
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
    from qmatsuite.engine.vasp_engine import VaspEngine
    return VaspEngine()

