"""
Tests for parameter_scan persistence in update_step_params API.

Verifies that:
1. Scan values arrays persist correctly
2. Orphan scans are deleted (full replace semantics)
3. Round-trip: save -> reload returns same values
"""

import pytest
from pathlib import Path
from quantumvitas.api import QVService
from quantumvitas.core.yamldoc import StepDoc
from quantumvitas.workflow.step_factory import save_step_doc


def test_update_step_params_parameter_scan_full_replace(tmp_path):
    """Test that parameter_scan uses full replace (not merge), deleting orphans."""
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
    QVService.import_structure(project_root, source, name="Silicon")
    
    # Create calculation
    calc_result = QVService.init_calculation(project_root, "calc001", structure_selector="silicon")
    calc_ulid = calc_result.id
    
    # Create step
    step_result = QVService.init_step(project_root, "calc001", step_type="scf", name="step001")
    step_yaml = step_result.absolute_path
    
    # Set initial parameter_scan via direct YAML edit (for test setup)
    step_doc = StepDoc.load(step_yaml)
    step_doc.apply_patch({
        "parameters": {
            "SYSTEM": {"ecutwfc": 50}
        },
        "parameter_scan": {
            "scan001": {"values": [30, 40, 50]},
            "scan002": {"values": [0.01, 0.02]},
        }
    })
    save_step_doc(step_doc, step_yaml)
    
    # Update with new parameter_scan (only scan003, should delete scan001/scan002)
    result = QVService.update_step_params(
        project_root=project_root,
        calculation_ulid=calc_ulid,
        step_selector=step_result.id,
        parameters={
            "SYSTEM": {
                "ecutwfc": "@scan:scan003",
            },
        },
        parameter_scan={
            "scan003": {
                "values": [330, 340, 350],
            },
        },
    )
    
    assert result is not None
    
    # Reload step and verify orphan scans are deleted
    step_doc = StepDoc.load(step_yaml)
    parameter_scan = step_doc.export_copy(["parameter_scan"]) or {}
    
    # scan001 and scan002 should be deleted (full replace)
    assert "scan001" not in parameter_scan
    assert "scan002" not in parameter_scan
    
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
    QVService.import_structure(project_root, source, name="Silicon")
    
    # Create calculation
    calc_result = QVService.init_calculation(project_root, "calc001", structure_selector="silicon")
    calc_ulid = calc_result.id
    
    # Create step
    step_result = QVService.init_step(project_root, "calc001", step_type="scf", name="step001")
    step_yaml = step_result.absolute_path
    
    # Update with scan values array of length 3
    result = QVService.update_step_params(
        project_root=project_root,
        calculation_ulid=calc_ulid,
        step_selector=step_result.id,
        parameters={
            "SYSTEM": {
                "ecutwfc": "@scan:scan001",
            },
        },
        parameter_scan={
            "scan001": {
                "values": [330, 340, 350],
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
    
    # Verify round-trip: get_step_detail returns same values
    step_detail = QVService.get_step_detail(
        project_root=project_root,
        calculation_ulid=calc_ulid,
        step_selector=step_result.id,
    )
    
    assert "parameter_scan" in step_detail
    assert "scan001" in step_detail["parameter_scan"]
    assert step_detail["parameter_scan"]["scan001"]["values"] == [330, 340, 350]


def test_update_step_params_parameter_scan_empty_clears_all(tmp_path):
    """Test that sending parameter_scan={} clears all scan definitions."""
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
    QVService.import_structure(project_root, source, name="Silicon")
    
    # Create calculation
    calc_result = QVService.init_calculation(project_root, "calc001", structure_selector="silicon")
    calc_ulid = calc_result.id
    
    # Create step
    step_result = QVService.init_step(project_root, "calc001", step_type="scf", name="step001")
    step_yaml = step_result.absolute_path
    
    # Set initial parameter_scan via direct YAML edit (for test setup)
    step_doc = StepDoc.load(step_yaml)
    step_doc.apply_patch({
        "parameters": {
            "SYSTEM": {"ecutwfc": 50}
        },
        "parameter_scan": {
            "scan001": {"values": [30, 40, 50]},
            "scan002": {"values": [0.01, 0.02]},
        }
    })
    save_step_doc(step_doc, step_yaml)
    
    # Update with empty parameter_scan (should clear all)
    result = QVService.update_step_params(
        project_root=project_root,
        calculation_ulid=calc_ulid,
        step_selector=step_result.id,
        parameters={
            "SYSTEM": {
                "ecutwfc": 50,
            },
        },
        parameter_scan={},  # Empty dict clears all
    )
    
    assert result is not None
    
    # Reload step and verify all scans are deleted
    step_doc = StepDoc.load(step_yaml)
    parameter_scan = step_doc.export_copy(["parameter_scan"]) or {}
    
    # Should be empty or not present
    assert not parameter_scan or len(parameter_scan) == 0


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
    QVService.import_structure(project_root, source, name="Silicon")
    
    # Create calculation
    calc_result = QVService.init_calculation(project_root, "calc001", structure_selector="silicon")
    calc_ulid = calc_result.id
    
    # Create step
    step_result = QVService.init_step(project_root, "calc001", step_type="scf", name="step001")
    step_yaml = step_result.absolute_path
    
    # Update with multiple scans
    result = QVService.update_step_params(
        project_root=project_root,
        calculation_ulid=calc_ulid,
        step_selector=step_result.id,
        parameters={
            "SYSTEM": {
                "ecutwfc": "@scan:scan001",
                "ecutrho": "@scan:scan002",
            },
        },
        parameter_scan={
            "scan001": {
                "values": [40, 50, 60],
            },
            "scan002": {
                "values": [330, 340, 350],
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

