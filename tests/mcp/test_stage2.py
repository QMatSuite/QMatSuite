"""Stage 2 MCP configuration tools tests.

Tests the five configuration tools: create_calculation, set_parameters,
apply_preset, inspect_calculation, and preview_compilation.
Also tests the upgraded make_error envelope.

All tests call .fn() directly on the @mcp.tool-decorated functions
(no subprocess needed).  A shared fixture wires up a temporary project
with an imported Silicon structure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantumvitas.api import QVService

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
def qv_project(tmp_path, monkeypatch):
    """Create a temporary QMatSuite project with an imported Silicon structure.

    Patches the MCP project module so all tools resolve to this project.
    """
    project_root = QVService.init_project(tmp_path / "project")

    # Import structure
    source = tmp_path / "si.json"
    source.write_text(SI_STRUCTURE_JSON)
    QVService(project_root).structure.import_file(source, name="Silicon")

    # Patch MCP project context
    from quantumvitas.mcp import project as mcp_project
    monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

    return project_root


# ---------------------------------------------------------------------------
# Envelope: make_error upgrade
# ---------------------------------------------------------------------------

def test_make_error_severity_and_diagnostics():
    """New make_error fields: severity, diagnostics, suggested_fixes."""
    from quantumvitas.mcp.envelope import make_error

    result = make_error(
        "validation_error",
        "ENCUT must be positive",
        severity="warning",
        diagnostics=[{"param": "ENCUT", "issue": "must be > 0"}],
        suggested_fixes=[{"action": "set_parameters", "params": {"ENCUT": 520}}],
    )
    assert result["status"] == "error"
    assert result["severity"] == "warning"
    assert result["diagnostics"] == [{"param": "ENCUT", "issue": "must be > 0"}]
    assert result["suggested_fixes"] == [{"action": "set_parameters", "params": {"ENCUT": 520}}]

    # Backward compat: existing calls still work, severity defaults to "error"
    basic = make_error("test", "msg")
    assert basic["severity"] == "error"
    assert "diagnostics" not in basic
    assert "suggested_fixes" not in basic


# ---------------------------------------------------------------------------
# create_calculation
# ---------------------------------------------------------------------------

def test_create_calculation_qe_scf(qv_project):
    """Create a QE SCF calculation — expect 1 step."""
    from quantumvitas.mcp.tools.create_calculation import create_calculation

    result = create_calculation.fn(
        engine="qe", workflow="scf", structure_selector="silicon",
    )
    assert result["status"] == "success"
    data = result["data"]
    assert data["engine"] == "qe"
    assert data["workflow"] == "scf"
    assert data["calc_ulid"]
    assert len(data["steps"]) == 1
    assert data["steps"][0]["step_type_gen"] == "scf"
    assert data["steps"][0]["step_type_spec"] == "qe_scf"


def test_create_calculation_qe_bands(qv_project):
    """Create a QE bands workflow — expect multiple steps (scf + bands)."""
    from quantumvitas.mcp.tools.create_calculation import create_calculation

    result = create_calculation.fn(
        engine="qe", workflow="bands", structure_selector="silicon",
    )
    assert result["status"] == "success"
    data = result["data"]
    assert len(data["steps"]) >= 2
    gen_steps = [s["step_type_gen"] for s in data["steps"]]
    assert "scf" in gen_steps


def test_create_calculation_unknown_engine(qv_project):
    """Unknown engine returns error envelope with suggestions."""
    from quantumvitas.mcp.tools.create_calculation import create_calculation

    result = create_calculation.fn(
        engine="nonexistent", workflow="scf", structure_selector="silicon",
    )
    assert result["status"] == "error"
    assert result["error_type"] == "unknown_engine"
    assert len(result["suggestions"]) > 0


# ---------------------------------------------------------------------------
# set_parameters
# ---------------------------------------------------------------------------

def _create_qe_scf(qv_project):
    """Helper: create a QE SCF calculation and return its data."""
    from quantumvitas.mcp.tools.create_calculation import create_calculation

    result = create_calculation.fn(
        engine="qe", workflow="scf", structure_selector="silicon",
    )
    assert result["status"] == "success"
    return result["data"]


def test_set_parameters_qe_scf(qv_project):
    """Set ecutwfc on step 0 of a QE SCF calculation."""
    from quantumvitas.mcp.tools.set_parameters import set_parameters

    calc_data = _create_qe_scf(qv_project)
    calc_ulid = calc_data["calc_ulid"]

    result = set_parameters.fn(
        calc_ulid=calc_ulid,
        params={"SYSTEM": {"ecutwfc": 60}},
        step=0,
    )
    assert result["status"] == "success"
    data = result["data"]
    assert data["calc_ulid"] == calc_ulid
    assert data["step"] == 0
    assert data["params_set"] == {"SYSTEM": {"ecutwfc": 60}}


def test_set_parameters_step_index(qv_project):
    """Set params on a specific step index in a multi-step workflow."""
    from quantumvitas.mcp.tools.create_calculation import create_calculation
    from quantumvitas.mcp.tools.set_parameters import set_parameters

    # Create bands workflow (scf + nscf + bands or similar)
    result = create_calculation.fn(
        engine="qe", workflow="bands", structure_selector="silicon",
    )
    assert result["status"] == "success"
    data = result["data"]
    n_steps = len(data["steps"])
    assert n_steps >= 2

    # Set params on the second step (index 1)
    calc_ulid = data["calc_ulid"]
    result = set_parameters.fn(
        calc_ulid=calc_ulid,
        params={"SYSTEM": {"nbnd": 20}},
        step=1,
    )
    assert result["status"] == "success"
    assert result["data"]["step"] == 1


def test_set_parameters_invalid_calc(qv_project):
    """Setting params on a nonexistent calculation returns error."""
    from quantumvitas.mcp.tools.set_parameters import set_parameters

    result = set_parameters.fn(
        calc_ulid="NONEXISTENT_ULID_12345678",
        params={"SYSTEM": {"ecutwfc": 60}},
    )
    assert result["status"] == "error"
    assert result["error_type"] == "not_found"


# ---------------------------------------------------------------------------
# apply_preset
# ---------------------------------------------------------------------------

def test_apply_preset_qe_precision(qv_project):
    """Apply magnetism preset to a QE SCF — verify steps_updated > 0."""
    from quantumvitas.mcp.tools.apply_preset import apply_preset

    calc_data = _create_qe_scf(qv_project)
    calc_ulid = calc_data["calc_ulid"]

    # apply_presets expects enum values, not profile names.
    # MagnetismOption.COLLINEAR_LSDA.value == "collinear_lsda"
    result = apply_preset.fn(
        calc_ulid=calc_ulid,
        presets={"magnetism": "collinear_lsda"},
    )
    assert result["status"] == "success"
    data = result["data"]
    assert data["calc_ulid"] == calc_ulid
    assert data["steps_updated"] > 0


def test_apply_preset_invalid_calc(qv_project):
    """Applying preset to nonexistent calculation returns error."""
    from quantumvitas.mcp.tools.apply_preset import apply_preset

    result = apply_preset.fn(
        calc_ulid="NONEXISTENT_ULID_12345678",
        presets={"magnetism": "NM"},
    )
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# inspect_calculation
# ---------------------------------------------------------------------------

def test_inspect_calculation_overview(qv_project):
    """Inspect overview returns engine, structure, and steps list."""
    from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

    calc_data = _create_qe_scf(qv_project)
    calc_ulid = calc_data["calc_ulid"]

    result = inspect_calculation.fn(calc_ulid=calc_ulid)
    assert result["status"] == "success"
    data = result["data"]
    assert data["engine"] == "qe"
    assert data["n_steps"] >= 1
    assert len(data["steps"]) >= 1
    assert data["steps"][0]["step_type_gen"] == "scf"


def test_inspect_calculation_step_detail(qv_project):
    """Inspect specific step returns parameters dict."""
    from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

    calc_data = _create_qe_scf(qv_project)
    calc_ulid = calc_data["calc_ulid"]

    result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0)
    assert result["status"] == "success"
    data = result["data"]
    assert "step_detail" in data
    assert "parameters" in data["step_detail"]


def test_inspect_calculation_after_set_params(qv_project):
    """Set params then inspect — verify persistence round-trip."""
    from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation
    from quantumvitas.mcp.tools.set_parameters import set_parameters

    calc_data = _create_qe_scf(qv_project)
    calc_ulid = calc_data["calc_ulid"]

    # Set parameter
    set_parameters.fn(
        calc_ulid=calc_ulid,
        params={"SYSTEM": {"ecutwfc": 75}},
        step=0,
    )

    # Inspect and verify
    result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0)
    assert result["status"] == "success"
    params = result["data"]["step_detail"]["parameters"]
    # ecutwfc should be under SYSTEM
    system = params.get("SYSTEM", {})
    assert system.get("ecutwfc") == 75


# ---------------------------------------------------------------------------
# preview_compilation
# ---------------------------------------------------------------------------

def test_preview_compilation_qe_scf_magnetism():
    """Compile magnetism preset for QE SCF — verify SYSTEM params."""
    from quantumvitas.mcp.tools.preview_compilation import preview_compilation

    # compile_presets_for_step expects enum values, not profile names.
    # MagnetismOption.COLLINEAR_LSDA.value == "collinear_lsda"
    result = preview_compilation.fn(
        engine="qe",
        workflow="scf",
        presets={"magnetism": "collinear_lsda"},
    )
    assert result["status"] == "success"
    data = result["data"]
    assert len(data["steps"]) >= 1
    # SCF step should have SYSTEM params from magnetism compilation
    scf_step = data["steps"][0]
    assert scf_step["step_type_gen"] == "scf"
    system = scf_step["parameters"].get("SYSTEM", {})
    # Collinear → nspin = 2
    assert system.get("nspin") == 2


def test_preview_compilation_unknown_engine():
    """Unknown engine returns error envelope."""
    from quantumvitas.mcp.tools.preview_compilation import preview_compilation

    result = preview_compilation.fn(
        engine="nonexistent",
        workflow="scf",
        presets={},
    )
    assert result["status"] == "error"
    assert result["error_type"] == "unknown_engine"


def test_preview_compilation_empty_presets():
    """Empty presets returns default/empty parameters."""
    from quantumvitas.mcp.tools.preview_compilation import preview_compilation

    result = preview_compilation.fn(
        engine="qe",
        workflow="scf",
        presets={},
    )
    assert result["status"] == "success"
    data = result["data"]
    assert len(data["steps"]) >= 1
    # With empty presets, should still compile (defaults applied)
    assert isinstance(data["steps"][0]["parameters"], dict)
