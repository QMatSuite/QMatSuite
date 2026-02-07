"""
Tests for parameter_scan persistence in update_step_params API.

Verifies that:
1. Scan values arrays persist correctly
2. Orphan scans are deleted (full replace semantics)
3. Round-trip: save -> reload returns same values
"""

import pytest
from pathlib import Path
from quantumvitas.api import QVService, get_service
from quantumvitas.core.yamldoc import StepDoc
from quantumvitas.workflow.step_factory import save_step_doc


def test_update_step_params_parameter_scan_merge(tmp_path):
    """Test that parameter_scan merges new scans with existing (merge semantics).

    Note: The domain API uses merge semantics, not full replace. Orphan scans are
    preserved with a warning, not automatically deleted. Use explicit deletion if needed.
    """
    # Create project using QVService
    project_root = QVService.init_project(tmp_path / "project")

    # Import structure (required for calculation)
    source = tmp_path / "si.json"
    source.write_text("""{
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
        "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
    }""")
    QVService(project_root).structure.import_file(source, name="Silicon")

    # Create calculation
    calc_result = QVService(project_root).project.init_calculation("calc001", structure_selector="silicon", engine_family="qe")
    calc_ulid = calc_result.ulid

    # Create step using domain API
    svc = get_service(project_root)
    step_result = svc.calculation.add_step(calc_selector="calc001", step_type_gen="scf", name="step001")
    step_yaml = project_root / "calculations" / "calc001" / "steps" / "step001.step.yaml"

    # Set initial parameter_scan via direct YAML edit (for test setup)
    step_doc = StepDoc.load(step_yaml)
    step_doc.apply_patch({
        "parameters": {
            "SYSTEM": {"ecutwfc": 50}
        },
        "parameter_scan": {
            "scan001": {"values": [30, 40, 50]},
        }
    })
    save_step_doc(step_doc, step_yaml)

    # Update with new parameter_scan - merge semantics adds scan003
    result = svc.calculation.update_step_params(
        calc_selector="calc001",
        step_selector="step001",
        params={
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": "@scan:scan003",
                },
            },
            "parameter_scan": {
                "scan003": {
                    "values": [330, 340, 350],
                },
            },
        },
    )

    assert result is not None

    # Reload step and verify scans
    step_doc = StepDoc.load(step_yaml)
    parameter_scan = step_doc.export_copy(["parameter_scan"]) or {}

    # scan001 is preserved (merge semantics - orphan warning issued but not deleted)
    assert "scan001" in parameter_scan

    # scan003 should exist with correct values
    assert "scan003" in parameter_scan
    assert parameter_scan["scan003"]["values"] == [330, 340, 350]

    # Parameter should have scan token
    assert step_doc.get(["parameters", "SYSTEM", "ecutwfc"]) == "@scan:scan003"


def test_update_step_params_parameter_scan_preserves_array_values(tmp_path):
    """Test that scan values arrays persist correctly (not truncated to single value).

    This is an end-to-end test: update with array of length 3, reload, verify length is 3.
    """
    # Create project using QVService
    project_root = QVService.init_project(tmp_path / "project")

    # Import structure (required for calculation)
    source = tmp_path / "si.json"
    source.write_text("""{
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
        "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
    }""")
    QVService(project_root).structure.import_file(source, name="Silicon")

    # Create calculation
    calc_result = QVService(project_root).project.init_calculation("calc001", structure_selector="silicon", engine_family="qe")
    calc_ulid = calc_result.ulid

    # Create step using domain API
    svc = get_service(project_root)
    step_result = svc.calculation.add_step(calc_selector="calc001", step_type_gen="scf", name="step001")
    step_yaml = project_root / "calculations" / "calc001" / "steps" / "step001.step.yaml"

    # Update with scan values array of length 3
    result = svc.calculation.update_step_params(
        calc_selector="calc001",
        step_selector="step001",
        params={
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": "@scan:scan001",
                },
            },
            "parameter_scan": {
                "scan001": {
                    "values": [330, 340, 350],
                },
            },
        },
    )

    assert result is not None

    # Reload step and verify values array is preserved (length 3, not 0 or 1)
    step_doc = StepDoc.load(step_yaml)
    parameter_scan = step_doc.export_copy(["parameter_scan"]) or {}

    assert "scan001" in parameter_scan
    values = parameter_scan["scan001"]["values"]
    assert len(values) == 3, f"Expected 3 values, got {len(values)}: {values}"
    assert values == [330, 340, 350]


def test_update_step_params_parameter_scan_empty_preserves(tmp_path):
    """Test that sending parameter_scan={} preserves existing scans (merge semantics).

    Note: The domain API uses merge semantics. Empty dict {} merges nothing,
    so existing scans are preserved. This is intentional - use explicit
    field deletion if clearing is needed.
    """
    # Create project using QVService
    project_root = QVService.init_project(tmp_path / "project")

    # Import structure (required for calculation)
    source = tmp_path / "si.json"
    source.write_text("""{
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
        "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
    }""")
    QVService(project_root).structure.import_file(source, name="Silicon")

    # Create calculation
    calc_result = QVService(project_root).project.init_calculation("calc001", structure_selector="silicon", engine_family="qe")
    calc_ulid = calc_result.ulid

    # Create step using domain API
    svc = get_service(project_root)
    step_result = svc.calculation.add_step(calc_selector="calc001", step_type_gen="scf", name="step001")
    step_yaml = project_root / "calculations" / "calc001" / "steps" / "step001.step.yaml"

    # Set initial parameter_scan via direct YAML edit (for test setup)
    step_doc = StepDoc.load(step_yaml)
    step_doc.apply_patch({
        "parameters": {
            "SYSTEM": {"ecutwfc": 50}
        },
        "parameter_scan": {
            "scan001": {"values": [30, 40, 50]},
        }
    })
    save_step_doc(step_doc, step_yaml)

    # Update with empty parameter_scan (preserves existing - merge semantics)
    result = svc.calculation.update_step_params(
        calc_selector="calc001",
        step_selector="step001",
        params={
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": 50,
                },
            },
            "parameter_scan": {},  # Empty dict merges nothing, existing preserved
        },
    )

    assert result is not None

    # Reload step and verify scans are preserved
    step_doc = StepDoc.load(step_yaml)
    parameter_scan = step_doc.export_copy(["parameter_scan"]) or {}

    # Existing scans should be preserved (merge semantics)
    assert "scan001" in parameter_scan
    assert parameter_scan["scan001"]["values"] == [30, 40, 50]


def test_update_step_params_parameter_scan_multiple_scans(tmp_path):
    """Test that multiple scan definitions persist correctly."""
    # Create project using QVService
    project_root = QVService.init_project(tmp_path / "project")

    # Import structure (required for calculation)
    source = tmp_path / "si.json"
    source.write_text("""{
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
        "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
    }""")
    QVService(project_root).structure.import_file(source, name="Silicon")

    # Create calculation
    calc_result = QVService(project_root).project.init_calculation("calc001", structure_selector="silicon", engine_family="qe")
    calc_ulid = calc_result.ulid

    # Create step using domain API
    svc = get_service(project_root)
    step_result = svc.calculation.add_step(calc_selector="calc001", step_type_gen="scf", name="step001")
    step_yaml = project_root / "calculations" / "calc001" / "steps" / "step001.step.yaml"

    # Update with multiple scans
    result = svc.calculation.update_step_params(
        calc_selector="calc001",
        step_selector="step001",
        params={
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": "@scan:scan001",
                    "ecutrho": "@scan:scan002",
                },
            },
            "parameter_scan": {
                "scan001": {
                    "values": [40, 50, 60],
                },
                "scan002": {
                    "values": [330, 340, 350],
                },
            },
        },
    )

    assert result is not None

    # Reload step and verify both scans persist
    step_doc = StepDoc.load(step_yaml)
    parameter_scan = step_doc.export_copy(["parameter_scan"]) or {}

    assert "scan001" in parameter_scan
    assert parameter_scan["scan001"]["values"] == [40, 50, 60]

    assert "scan002" in parameter_scan
    assert parameter_scan["scan002"]["values"] == [330, 340, 350]

    # Verify parameters have scan tokens
    assert step_doc.get(["parameters", "SYSTEM", "ecutwfc"]) == "@scan:scan001"
    assert step_doc.get(["parameters", "SYSTEM", "ecutrho"]) == "@scan:scan002"
