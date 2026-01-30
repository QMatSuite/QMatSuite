"""
Test that update_step_params daemon RPC actually persists changes to disk.

This test simulates the UI flow:
1. Create a step with initial parameters
2. Call update_step_params via daemon RPC (simulating UI Apply)
3. Verify the YAML file on disk actually changed (mtime and content)
4. Verify round-trip: reload and check values persisted

This is a regression test for the bug where UI edits don't persist to disk.
"""

import os
import time
from pathlib import Path

import pytest

from quantumvitas.api import QVService
from quantumvitas.core.yamldoc import StepDoc
from quantumvitas.daemon.server import QVDaemon, RPCRequest


def send_request(daemon: QVDaemon, request_type: str, payload: dict) -> dict:
    """Send a request to the daemon and return the response data."""
    response = daemon.handle_request(RPCRequest(
        id="test",
        type=request_type,
        payload=payload,
    ))

    if not response.ok:
        raise RuntimeError(f"Daemon request failed: {response.error}")

    return response.data


def _get_step_yaml_path(project_root: Path, calc_slug: str, step_slug: str) -> Path:
    """Helper to construct step YAML path."""
    return project_root / "calculations" / calc_slug / "steps" / f"{step_slug}.step.yaml"


@pytest.fixture
def temp_project(tmp_path: Path) -> tuple[Path, str, str]:
    """Create a temporary project with a calculation and step.

    Returns:
        (project_root, calc_ulid, step_ulid) tuple
    """
    project_root = QVService.init_project(tmp_path / "project")

    # Import structure
    source = tmp_path / "si.json"
    source.write_text("""{
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
        "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
    }""")
    QVService.import_structure(project_root, source, name="Silicon")

    # Create calculation and get ULID
    calc_result = QVService.init_calculation(project_root, "calc001", structure_selector="silicon")
    calc_ulid = calc_result.ulid

    # Create step and get ULID
    svc = QVService(project_root)
    step_dto = svc.calculation.add_step(calc_selector=calc_ulid, step_type="scf", name="step001")
    step_ulid = step_dto.step_ulid

    return (project_root, calc_ulid, step_ulid)


def test_update_step_params_scalar_persists_to_disk(temp_project: tuple[Path, str, str]):
    """Test that scalar parameter changes persist to disk via daemon RPC."""
    project_root, calc_ulid, step_ulid = temp_project
    daemon = QVDaemon()

    # Get step YAML path
    step_yaml_path = _get_step_yaml_path(project_root, "calc001", "step001")

    # Record initial mtime
    initial_mtime = os.path.getmtime(step_yaml_path)

    # Wait a bit to ensure mtime will change
    time.sleep(0.1)

    # Call update_step_params via daemon (simulating UI Apply)
    # Use ULID for calculation (daemon handler will accept ULID or slug, but ULID is safer)
    result = send_request(daemon, "update_step_params", {
        "project_root": str(project_root),
        "calculation": calc_ulid,  # ULID
        "step": step_ulid,  # ULID
        "parameters": {
            "SYSTEM": {
                "ecutwfc": 60,  # Change from default
            },
        },
        "parameter_scan": None,  # No scan changes
    })

    assert result is not None

    # Verify file mtime changed (proves write happened)
    new_mtime = os.path.getmtime(step_yaml_path)
    assert new_mtime > initial_mtime, "File mtime did not change - write did not occur"

    # Verify content changed
    step_doc = StepDoc.load(step_yaml_path)
    assert step_doc.get(["parameters", "SYSTEM", "ecutwfc"]) == 60

    # Verify round-trip: reload via StepDoc
    reloaded_doc = StepDoc.load(step_yaml_path)
    assert reloaded_doc.get(["parameters", "SYSTEM", "ecutwfc"]) == 60


def test_update_step_params_scan_persists_to_disk(temp_project: tuple[Path, str, str]):
    """Test that scan value changes persist to disk via daemon RPC."""
    project_root, calc_ulid, step_ulid = temp_project
    daemon = QVDaemon()

    # Get step YAML path
    step_yaml_path = _get_step_yaml_path(project_root, "calc001", "step001")

    # Set initial parameter to use scan (via direct YAML edit for setup)
    step_doc = StepDoc.load(step_yaml_path)
    step_doc.apply_patch({
        "parameters": {
            "SYSTEM": {"ecutwfc": "@scan:scan001"},
        },
        "parameter_scan": {
            "scan001": {"values": [30, 40, 50]},
        },
    })
    from quantumvitas.workflow.step_factory import save_step_doc
    save_step_doc(step_doc, step_yaml_path)

    # Record initial mtime
    initial_mtime = os.path.getmtime(step_yaml_path)

    # Wait a bit to ensure mtime will change
    time.sleep(0.1)

    # Call update_step_params via daemon with new scan values (simulating UI Apply)
    # Use ULID for calculation (daemon handler will accept ULID or slug, but ULID is safer)
    result = send_request(daemon, "update_step_params", {
        "project_root": str(project_root),
        "calculation": calc_ulid,  # ULID
        "step": step_ulid,  # ULID
        "parameters": {
            "SYSTEM": {
                "ecutwfc": "@scan:scan001",  # Keep scan token
            },
        },
        "parameter_scan": {
            "scan001": {
                "values": [40, 50, 60],  # Changed values
            },
        },
    })

    assert result is not None

    # Verify file mtime changed (proves write happened)
    new_mtime = os.path.getmtime(step_yaml_path)
    assert new_mtime > initial_mtime, "File mtime did not change - write did not occur"

    # Verify content changed
    step_doc = StepDoc.load(step_yaml_path)
    parameter_scan = step_doc.export_copy(["parameter_scan"]) or {}
    assert "scan001" in parameter_scan
    assert parameter_scan["scan001"]["values"] == [40, 50, 60]

    # Verify round-trip: reload via StepDoc
    reloaded_doc = StepDoc.load(step_yaml_path)
    reloaded_scan = reloaded_doc.export_copy(["parameter_scan"]) or {}
    assert reloaded_scan["scan001"]["values"] == [40, 50, 60]


def test_update_step_params_scalar_and_scan_persist_to_disk(temp_project: tuple[Path, str, str]):
    """Test that both scalar and scan changes persist in a single RPC call."""
    project_root, calc_ulid, step_ulid = temp_project
    daemon = QVDaemon()

    # Get step YAML path
    step_yaml_path = _get_step_yaml_path(project_root, "calc001", "step001")

    # Set initial state with scan (via direct YAML edit for setup)
    step_doc = StepDoc.load(step_yaml_path)
    step_doc.apply_patch({
        "parameters": {
            "SYSTEM": {
                "ecutwfc": "@scan:scan001",
                "ecutrho": 200,  # Scalar
            },
        },
        "parameter_scan": {
            "scan001": {"values": [30, 40, 50]},
        },
    })
    from quantumvitas.workflow.step_factory import save_step_doc
    save_step_doc(step_doc, step_yaml_path)

    # Record initial mtime
    initial_mtime = os.path.getmtime(step_yaml_path)

    # Wait a bit to ensure mtime will change
    time.sleep(0.1)

    # Call update_step_params via daemon with both changes (simulating UI Apply)
    # Use ULID for calculation (daemon handler will accept ULID or slug, but ULID is safer)
    result = send_request(daemon, "update_step_params", {
        "project_root": str(project_root),
        "calculation": calc_ulid,  # ULID
        "step": step_ulid,  # ULID
        "parameters": {
            "SYSTEM": {
                "ecutwfc": "@scan:scan001",  # Keep scan token
                "ecutrho": 250,  # Changed scalar
            },
        },
        "parameter_scan": {
            "scan001": {
                "values": [40, 50, 60],  # Changed scan values
            },
        },
    })

    assert result is not None

    # Verify file mtime changed (proves write happened)
    new_mtime = os.path.getmtime(step_yaml_path)
    assert new_mtime > initial_mtime, "File mtime did not change - write did not occur"

    # Verify both changes persisted
    step_doc = StepDoc.load(step_yaml_path)
    assert step_doc.get(["parameters", "SYSTEM", "ecutrho"]) == 250
    parameter_scan = step_doc.export_copy(["parameter_scan"]) or {}
    assert "scan001" in parameter_scan
    assert parameter_scan["scan001"]["values"] == [40, 50, 60]

    # Verify round-trip: reload via StepDoc
    reloaded_doc = StepDoc.load(step_yaml_path)
    assert reloaded_doc.get(["parameters", "SYSTEM", "ecutrho"]) == 250
    reloaded_scan = reloaded_doc.export_copy(["parameter_scan"]) or {}
    assert reloaded_scan["scan001"]["values"] == [40, 50, 60]
