"""ORCA MCP real-run integration tests.

These tests exercise the full MCP tool chain for ORCA calculations:
create_calculation -> set_parameters -> run_calculation -> inspect

They require a local ORCA installation and will be skipped on CI or
any machine without ORCA.

Skip condition: ``shutil.which("orca") is None``
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from qmatsuite.api import QMSService


# ---------------------------------------------------------------------------
# Skip if ORCA not installed
# ---------------------------------------------------------------------------

def _find_orca() -> bool:
    """Check if ORCA is available (PATH or managed engine)."""
    if shutil.which("orca"):
        return True
    try:
        from qmatsuite.core.engines.orca_resolver import resolve_orca_bin
        return Path(resolve_orca_bin()).exists()
    except Exception:
        return False


requires_orca = pytest.mark.skipif(
    not _find_orca(),
    reason="ORCA not available (not in PATH, not in managed engines)",
)

pytestmark = [pytest.mark.integration, requires_orca]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

H2O_MOLECULE_JSON = json.dumps({
    "@module": "pymatgen.core.structure",
    "@class": "Molecule",
    "charge": 0,
    "spin_multiplicity": 1,
    "sites": [
        {"species": [{"element": "O", "occu": 1}], "xyz": [0.0, 0.0, 0.1173]},
        {"species": [{"element": "H", "occu": 1}], "xyz": [0.0, 0.7572, -0.4692]},
        {"species": [{"element": "H", "occu": 1}], "xyz": [0.0, -0.7572, -0.4692]},
    ],
})


@pytest.fixture
def orca_project(tmp_path, monkeypatch):
    """Create a QMatSuite project with a water molecule, patched for MCP."""
    project_root = QMSService.init_project(tmp_path / "orca_project")
    svc = QMSService(project_root)

    # Import water molecule
    mol_file = tmp_path / "water.json"
    mol_file.write_text(H2O_MOLECULE_JSON)
    svc.structure.import_file(mol_file, name="Water")

    # Patch MCP project context
    from qmatsuite.mcp import project as mcp_project
    monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

    return project_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_orca_calc(workflow: str, name: str) -> dict:
    from qmatsuite.mcp.tools.create_calculation import create_calculation
    result = create_calculation.fn(
        engine="orca", workflow=workflow,
        structure_selector="water", name=name,
    )
    assert result["status"] == "success", f"create_calculation: {result}"
    return result["data"]


def _set_params(calc_ulid: str, params: dict, step: int = 0) -> dict:
    from qmatsuite.mcp.tools.set_parameters import set_parameters
    result = set_parameters.fn(calc_ulid=calc_ulid, params=params, step=step)
    assert result["status"] == "success", f"set_parameters: {result}"
    return result["data"]


def _run(calc_ulid: str) -> dict:
    from qmatsuite.mcp.tools.run_calculation import run_calculation
    result = run_calculation.fn(calc_ulid=calc_ulid)
    return result  # May be success or error — caller decides


def _inspect(calc_ulid: str) -> dict:
    from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation
    result = inspect_calculation.fn(calc_ulid=calc_ulid)
    assert result["status"] == "success", f"inspect: {result}"
    return result["data"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestORCAWaterSinglePoint:
    """ORCA single-point energy on water (HF/STO-3G)."""

    def test_sp_completes(self, orca_project):
        """Full MCP flow: create -> set_params -> run -> inspect."""
        calc_data = _create_orca_calc("scf", "water_sp")
        calc_ulid = calc_data["calc_ulid"]

        _set_params(calc_ulid, {"method": "HF", "basis": "STO-3G"})

        result = _run(calc_ulid)
        status = result.get("data", {}).get("status", result.get("status"))
        assert status == "completed", f"ORCA SCF failed: {result}"


class TestORCAWaterOpt:
    """ORCA geometry optimization on water (HF/STO-3G)."""

    def test_opt_completes(self, orca_project):
        """Relax workflow via MCP — verifies relax-as-root Opt keyword fix."""
        calc_data = _create_orca_calc("relax", "water_opt")
        calc_ulid = calc_data["calc_ulid"]

        _set_params(calc_ulid, {
            "method": "HF",
            "basis": "STO-3G",
            "geom": {"MaxIter": 50},
        })

        result = _run(calc_ulid)
        status = result.get("data", {}).get("status", result.get("status"))
        assert status == "completed", f"ORCA relax failed: {result}"


class TestORCAChargeMult:
    """Charge/multiplicity override from parameters."""

    def test_triplet_o2_completes(self, orca_project):
        """O2 triplet UHF: charge=0, multiplicity=3."""
        # Import O2
        svc = QMSService(orca_project)
        o2_json = json.dumps({
            "@module": "pymatgen.core.structure",
            "@class": "Molecule",
            "charge": 0, "spin_multiplicity": 3,
            "sites": [
                {"species": [{"element": "O", "occu": 1}], "xyz": [0.0, 0.0, 0.0]},
                {"species": [{"element": "O", "occu": 1}], "xyz": [0.0, 0.0, 1.21]},
            ],
        })
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write(o2_json)
            o2_path = Path(f.name)
        svc.structure.import_file(o2_path, name="O2_triplet")
        o2_path.unlink()

        from qmatsuite.mcp.tools.create_calculation import create_calculation
        result = create_calculation.fn(
            engine="orca", workflow="scf",
            structure_selector="o2_triplet", name="o2_triplet",
        )
        assert result["status"] == "success"
        calc_ulid = result["data"]["calc_ulid"]

        _set_params(calc_ulid, {
            "method": "UHF", "basis": "STO-3G",
            "charge": 0, "multiplicity": 3,
        })

        run_result = _run(calc_ulid)
        status = run_result.get("data", {}).get("status", run_result.get("status"))
        assert status == "completed", f"O2 triplet failed: {run_result}"


class TestORCAMolecularStructureInspect:
    """MCP inspect_calculation correctly handles molecular structures."""

    def test_inspect_shows_structure(self, orca_project):
        """inspect_calculation returns structure info for molecular calc."""
        calc_data = _create_orca_calc("scf", "water_inspect")
        calc_ulid = calc_data["calc_ulid"]

        inspection = _inspect(calc_ulid)
        # Should have structure info (not None — the bug B3 fixed)
        assert inspection.get("structure") is not None or inspection.get("structure_info") is not None, (
            "Molecular structure not returned by inspect_calculation"
        )
