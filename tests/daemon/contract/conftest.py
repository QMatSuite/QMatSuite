"""
Shared fixtures for RPC contract tests.

These fixtures provide:
- Clean daemon instances
- Temporary projects with varying complexity
- Helper functions for RPC communication
- Demo project imports for analysis tests
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from quantumvitas.api import QVService
from quantumvitas.core.resources import get_resources_dir
from quantumvitas.daemon.server import QVDaemon, RPCRequest


def send_request(daemon: QVDaemon, request_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Send an RPC request to the daemon and return the response data.

    Raises RuntimeError if the request fails.

    Args:
        daemon: QVDaemon instance
        request_type: RPC command name
        payload: Request payload

    Returns:
        Response data dictionary

    Raises:
        RuntimeError: If the RPC call fails
    """
    response = daemon.handle_request(RPCRequest(
        id="test",
        type=request_type,
        payload=payload,
    ))

    if not response.ok:
        error_msg = response.error.get("message", "Unknown error") if response.error else "Unknown error"
        error_code = response.error.get("code", "unknown") if response.error else "unknown"
        raise RuntimeError(f"RPC {request_type} failed ({error_code}): {error_msg}")

    return response.data


@pytest.fixture
def daemon() -> QVDaemon:
    """Create a clean daemon instance for testing."""
    return QVDaemon()


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """
    Create a minimal temporary project.

    Returns:
        Path to project root
    """
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    QVService.init_project(project_dir, name="test_project")
    return project_dir


@pytest.fixture
def demo_project_with_structure(tmp_path: Path) -> tuple[Path, str]:
    """
    Create a project with a structure (Si crystal).

    Uses test data if available, otherwise creates a minimal structure.

    Returns:
        (project_root, structure_ulid)
    """
    project_dir = tmp_path / "test_project_with_structure"
    project_dir.mkdir()
    QVService.init_project(project_dir, name="test_project_with_structure")

    svc = QVService(project_dir)

    # Try to import from test data, otherwise create minimal structure
    test_data = Path(__file__).parent.parent.parent / "data" / "calculation_bands"
    if test_data.exists():
        scf_in = test_data / "si.0_scf.in"
        if scf_in.exists():
            structure_resolved = svc.structure.import_file(
                source=scf_in,
                name="Si",
            )
            structure_ulid = structure_resolved.meta.ulid
            return project_dir, structure_ulid

    # Fallback: create minimal structure using pymatgen
    try:
        from pymatgen.core import Structure, Lattice

        structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
        structure_resolved = svc.structure.import_structure(
            structure=structure,
            name="Si",
        )
        structure_ulid = structure_resolved.meta.ulid
        return project_dir, structure_ulid
    except ImportError:
        pytest.skip("Test data not available and pymatgen not installed")


@pytest.fixture
def demo_project_with_calculation(tmp_path: Path) -> tuple[Path, str, str]:
    """
    Create a project with structure + calculation + 1 SCF step.

    Returns:
        (project_root, structure_ulid, calculation_ulid)
    """
    project_dir = tmp_path / "test_project_with_calculation"
    project_dir.mkdir()
    QVService.init_project(project_dir, name="test_project_with_calculation")

    svc = QVService(project_dir)

    # Import structure
    test_data = Path(__file__).parent.parent.parent / "data" / "calculation_bands"
    if test_data.exists():
        scf_in = test_data / "si.0_scf.in"
        if scf_in.exists():
            structure_resolved = svc.structure.import_file(
                source=scf_in,
                name="Si",
            )
            structure_ulid = structure_resolved.meta.ulid
        else:
            pytest.skip("Test data not available")
    else:
        # Fallback: create minimal structure
        try:
            from pymatgen.core import Structure, Lattice

            structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
            structure_resolved = svc.structure.import_structure(
                structure=structure,
                name="Si",
            )
            structure_ulid = structure_resolved.meta.ulid
        except ImportError:
            pytest.skip("Test data not available and pymatgen not installed")

    # Create calculation
    calculation_result = svc.project.init_calculation(
        name="test_calculation",
        structure_selector=structure_ulid,
        engine_family="qe",
    )
    calculation_ulid = calculation_result.meta.ulid

    # Add SCF step
    svc.calculation.add_step(
        calc_selector=calculation_ulid,
        step_type_gen="scf",
    )

    return project_dir, structure_ulid, calculation_ulid


@pytest.fixture
def demo_project_with_run(tmp_path: Path) -> tuple[Path, str, str, str | None]:
    """
    Create a project with a completed run using demo ref_pack data.

    Imports the qe_si_scf demo which has pre-computed results.

    Returns:
        (project_root, calculation_ulid, step_ulid, run_ulid)

    Note:
        run_ulid may be None if history data is not available
    """
    # Try to import qe_si_scf demo ref_pack
    demo_pack_path = get_resources_dir() / "demo_projects" / "ref_packs" / "qe_si_scf"

    if not demo_pack_path.exists():
        pytest.skip("qe_si_scf demo ref_pack not available")

    # Copy demo to tmp_path
    project_dir = tmp_path / "qe_si_scf"
    shutil.copytree(demo_pack_path, project_dir)

    # Get calculation and step ULIDs from the demo
    svc = QVService(project_dir)
    index = svc.project.build_resource_index()

    if not index.calculations:
        pytest.skip("Demo project has no calculations")

    calc = index.calculations[0]
    calculation_ulid = calc.meta.ulid

    if not calc.steps:
        pytest.skip("Demo calculation has no steps")

    step = calc.steps[0]
    step_ulid = step.meta.ulid

    # Try to get run ULID from history (may not exist)
    run_ulid = None
    try:
        from quantumvitas.provenance.query import get_latest_run_for_step

        run = get_latest_run_for_step(project_dir, step_ulid)
        if run:
            run_ulid = run.run_ulid
    except Exception:
        pass  # History may not be available, that's ok

    return project_dir, calculation_ulid, step_ulid, run_ulid


# =============================================================================
# Real-Run Test Fixtures (QE Smoke Tests)
# =============================================================================

@pytest.fixture
def qe_available() -> bool:
    """
    Ensure QE is available for real-run tests.

    Fails the test if QE is not detected.
    """
    from quantumvitas.api.utils import get_qe_engine_status

    status = get_qe_engine_status()
    if not status.get("detection", {}).get("found"):
        pytest.fail("QE not found - real-run tests require QE installation")

    return True


@pytest.fixture
def wait_for_job():
    """
    Returns a function that polls job status until complete or timeout.

    Usage:
        wait_fn = wait_for_job
        final_status = wait_fn(daemon, project_root, job_id, timeout=120)
    """
    def _wait(daemon, project_root: str | Path, job_id: str, timeout: int = 120) -> dict:
        """
        Poll job status until complete, failed, or timeout.

        Args:
            daemon: QVDaemon instance
            project_root: Project root path
            job_id: Job ID to monitor
            timeout: Timeout in seconds

        Returns:
            Final job status dict

        Raises:
            TimeoutError: If job doesn't complete within timeout
            RuntimeError: If job fails
        """
        import time

        start_time = time.time()
        poll_interval = 2  # Poll every 2 seconds

        while time.time() - start_time < timeout:
            response = daemon.handle_request(RPCRequest(
                id=f"poll_{job_id}",
                type="get_job_status",
                payload={
                    "project_root": str(project_root),
                    "job_id": job_id
                }
            ))

            if not response.ok:
                raise RuntimeError(f"Failed to get job status: {response.error}")

            status_data = response.data
            status = status_data.get("status", "unknown")

            if status in ["completed", "success"]:
                return status_data
            elif status in ["failed", "error"]:
                error_msg = status_data.get("error_message") or status_data.get("error") or "Unknown error"
                print(f"DEBUG: Job failed. Full status_data: {status_data}")
                raise RuntimeError(f"Job failed: {error_msg}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

    return _wait


@pytest.fixture
def qe_project_with_si(tmp_path: Path, qe_available) -> tuple[Path, str]:
    """
    Create a project with Si structure imported from local CIF test data.

    Returns:
        (project_root, structure_ulid)
    """
    # Create project
    project_dir = tmp_path / "si_test"
    project_dir.mkdir()
    QVService.init_project(project_dir, name="Si Test")

    # Create service instance
    svc = QVService(project_dir)

    # Import Si structure from dedicated smoke-test structure asset
    si_cif = Path(__file__).parent.parent.parent / "data" / "structures" / "si_diamond.cif"
    if not si_cif.exists():
        pytest.fail(f"Si structure file not found: {si_cif}")

    # Import structure using the same pattern as demo_project_with_structure
    structure_resolved = svc.structure.import_file(
        source=si_cif,
        name="Si",
    )

    structure_ulid = structure_resolved.meta.ulid

    # NOTE: Pseudopotentials are NOT manually copied here.
    # The runner auto-stages from bundled src/quantumvitas/resources/pseudo/ during run.
    # The test must set species_map via RPC (update_calculation_species_map)
    # to tell the runner which pseudo file to use — just like a real user would.

    return project_dir, structure_ulid


@pytest.fixture
def qe_project_with_al(tmp_path: Path, qe_available) -> tuple[Path, str]:
    """
    Create a project with Al structure imported from local CIF test data.

    Returns:
        (project_root, structure_ulid)
    """
    project_dir = tmp_path / "al_test"
    project_dir.mkdir()
    QVService.init_project(project_dir, name="Al Test")

    svc = QVService(project_dir)

    al_cif = Path(__file__).parent.parent.parent / "data" / "structures" / "al_fcc.cif"
    if not al_cif.exists():
        pytest.fail(f"Al structure file not found: {al_cif}")

    structure_resolved = svc.structure.import_file(
        source=al_cif,
        name="Al",
    )

    return project_dir, structure_resolved.meta.ulid
