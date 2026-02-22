"""Shared fixtures for MCP integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qmatsuite.api import QMSService

# Minimal pymatgen-format Silicon structure (1 atom, FCC-like).
SI_STRUCTURE_JSON = json.dumps({
    "@module": "pymatgen.core.structure",
    "@class": "Structure",
    "lattice": {
        "matrix": [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]],
        "a": 5.43, "b": 5.43, "c": 5.43,
        "alpha": 90, "beta": 90, "gamma": 90,
    },
    "sites": [
        {"species": [{"element": "Si", "occu": 1}], "abc": [0, 0, 0], "xyz": [0, 0, 0]},
    ],
})


@pytest.fixture
def qms_project(tmp_path, monkeypatch):
    """Create a temporary QMatSuite project with an imported Silicon structure.

    Patches the MCP project module so all tools resolve to this project.
    """
    project_root = QMSService.init_project(tmp_path / "project")

    # Import structure
    source = tmp_path / "si.json"
    source.write_text(SI_STRUCTURE_JSON)
    QMSService(project_root).structure.import_file(source, name="Silicon")

    # Patch MCP project context
    from qmatsuite.mcp import project as mcp_project
    monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

    return project_root


@pytest.fixture
def qe_available() -> bool:
    """Ensure QE is available. Fails (not skips) if not found."""
    from qmatsuite.api.utils import get_qe_engine_status

    status = get_qe_engine_status()
    if not status.get("detection", {}).get("found"):
        pytest.fail("QE not found — real-run tests require QE installation")
    return True


@pytest.fixture
def qe_project_with_si(tmp_path, qe_available, monkeypatch):
    """Create a project with Si imported from CIF, species_map set, MCP patched.

    Returns project_root for a project ready for QE calculations.
    """
    project_root = QMSService.init_project(tmp_path / "si_qe_project")
    svc = QMSService(project_root)

    # Import Si structure from test CIF
    si_cif = Path(__file__).parent.parent / "data" / "structures" / "si_diamond.cif"
    if not si_cif.exists():
        pytest.fail(f"Si structure file not found: {si_cif}")

    svc.structure.import_file(source=si_cif, name="Si")

    # Patch MCP project context
    from qmatsuite.mcp import project as mcp_project
    monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

    return project_root
