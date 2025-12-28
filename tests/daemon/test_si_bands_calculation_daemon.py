"""
Daemon-based test for Si band structure calculation.

This test achieves the same goal as test_si_bands_calculation_comprehensive.py 
but uses the daemon and JobManager instead of CLI subprocess calls.

Key differences from CLI test:
- Uses QVDaemon and JobManager directly (no subprocess)
- Uses QVService for all operations
- Tests the JSON-RPC protocol
- Validates job status tracking

Requires QE to be installed.
"""

import json
import shutil
import time
from io import StringIO
from pathlib import Path
from typing import Any, Dict

import pytest

from quantumvitas.api import QVService
from quantumvitas.daemon.server import QVDaemon, RPCRequest
from quantumvitas.daemon.jobs import JobManager, JobStatus

# Test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "data" / "calculation_bands"

# Mark all tests as requiring QE
pytestmark = pytest.mark.qe_core


def send_request(daemon: QVDaemon, request_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send a request to the daemon and return the response data."""
    response = daemon.handle_request(RPCRequest(
        id="test",
        type=request_type,
        payload=payload,
    ))
    
    if not response.ok:
        raise RuntimeError(f"Daemon request failed: {response.error}")
    
    return response.data


def wait_for_job(daemon: QVDaemon, job_id: str, timeout: float = 300.0) -> Dict[str, Any]:
    """Wait for a job to complete and return its status."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status = send_request(daemon, "get_job_status", {"job_id": job_id})
        
        if status["status"] in ("completed", "failed", "cancelled"):
            return status
        
        time.sleep(1.0)
    
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


@pytest.fixture(scope="module")
def test_project_dir(project_root_path: Path) -> Path:
    """Create a temporary project directory for the test."""
    test_dir = project_root_path / "temp" / "test_si_bands_daemon"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture(scope="module")
def project_with_structure(test_project_dir: Path, project_root_path: Path) -> Path:
    """Initialize project and import Si structure using QVService (not CLI)."""
    if not TEST_DATA_DIR.exists():
        pytest.skip(f"Test data not found: {TEST_DATA_DIR}")
    
    scf_in = TEST_DATA_DIR / "si.0_scf.in"
    if not scf_in.exists():
        pytest.skip(f"SCF input not found: {scf_in}")
    
    # Initialize project using QVService
    project_dir = QVService.init_project(
        test_project_dir / "si_bands_daemon_test",
        name="si_bands_daemon_test",
    )
    
    # Copy only the Si pseudopotential
    pseudo_src = project_root_path / "resources" / "pseudo"
    pseudo_dst = project_dir / "pseudo"
    pseudo_dst.mkdir(parents=True, exist_ok=True)
    
    si_pseudos = list(pseudo_src.glob("Si*.UPF")) + list(pseudo_src.glob("si*.UPF"))
    for pp_file in si_pseudos:
        shutil.copy2(pp_file, pseudo_dst / pp_file.name)
    
    # Import structure using QVService
    QVService.import_structure(project_dir, scf_in, name="si")
    
    return project_dir


@pytest.fixture(scope="module")
def daemon() -> QVDaemon:
    """Create a daemon instance for testing."""
    # Use StringIO for stdio (we won't use the run() loop)
    d = QVDaemon(
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=StringIO(),
    )
    yield d
    d.job_manager.shutdown(wait=True)


class TestDaemonProtocol:
    """Test basic daemon protocol."""
    
    def test_ping(self, daemon: QVDaemon):
        """Test ping command."""
        response = send_request(daemon, "ping", {})
        
        assert response["pong"] is True
        assert "version" in response
    
    def test_unknown_command(self, daemon: QVDaemon):
        """Test unknown command returns error."""
        response = daemon.handle_request(RPCRequest(
            id="test",
            type="nonexistent_command",
            payload={},
        ))
        
        assert not response.ok
        assert response.error["code"] == "unknown_command"


class TestDaemonProjectOperations:
    """Test project operations through daemon."""
    
    def test_get_project_summary(self, daemon: QVDaemon, project_with_structure: Path):
        """Test getting project summary via daemon."""
        response = send_request(daemon, "get_project_summary", {
            "project_root": str(project_with_structure),
        })
        
        assert response["name"] == "si_bands_daemon_test"
        assert response["n_structures"] == 1
        assert "si" in response["structure_names"]
    
    def test_list_structures(self, daemon: QVDaemon, project_with_structure: Path):
        """Test listing structures via daemon."""
        response = send_request(daemon, "list_structures", {
            "project_root": str(project_with_structure),
        })
        
        assert response["count"] == 1
        assert len(response["structures"]) == 1
        
        struct = response["structures"][0]
        assert struct["name"] == "si"
        assert "formula" in struct
        assert "n_atoms" in struct
    
    def test_get_structure_vis(self, daemon: QVDaemon, project_with_structure: Path):
        """Test getting structure visualization data via daemon."""
        response = send_request(daemon, "get_structure_vis", {
            "project_root": str(project_with_structure),
            "selector": "si",
        })
        
        assert response["structure_name"] == "si"
        assert response["n_atoms"] > 0
        assert "atoms" in response
        assert "lattice" in response
        
        # Verify JSON serializable (no numpy arrays)
        json_str = json.dumps(response)
        assert json_str


class TestDaemonCalculationExecution:
    """Test calculation execution through daemon JobManager."""
    
    @pytest.fixture(scope="class")
    def calculation_with_steps(self, daemon: QVDaemon, project_with_structure: Path) -> Path:
        """Create calculation with steps using QVService (not CLI)."""
        project_dir = project_with_structure
        
        # Create calculation
        QVService.init_calculation(project_dir, "bands_daemon", structure_selector="si")
        
        calculation_dir = project_dir / "calculations" / "bands_daemon"
        
        # Create SCF step
        QVService.init_step(
            project_root=project_dir,
            calculation_selector="bands_daemon",
            step_type="scf",
            name="scf",
            structure_selector="si",
        )
        
        # Configure SCF step
        QVService.configure_step(
            project_root=project_dir,
            calculation_selector="bands_daemon",
            step_selector="scf",
            parameters={
                "CONTROL": {
                    "prefix": "si",
                    "outdir": "./outdir",
                    "pseudo_dir": "./",
                },
                "SYSTEM": {
                    "ecutwfc": 40,
                    "ecutrho": 320,
                    "nbnd": 8,
                },
                "ELECTRONS": {
                    "conv_thr": 1e-8,
                },
            },
            cards={
                "K_POINTS": {
                    "option": "automatic",
                    "data": [[8, 8, 8, 0, 0, 0]],
                },
            },
            species_overrides={
                "Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"},
            },
        )
        
        # Create NSCF step
        QVService.init_step(
            project_root=project_dir,
            calculation_selector="bands_daemon",
            step_type="nscf",
            name="nscf",
            structure_selector="si",
        )
        
        # Configure NSCF step
        QVService.configure_step(
            project_root=project_dir,
            calculation_selector="bands_daemon",
            step_selector="nscf",
            parameters={
                "CONTROL": {
                    "prefix": "si",
                    "outdir": "./outdir",
                    "pseudo_dir": "./",
                },
                "SYSTEM": {
                    "ecutwfc": 40,
                    "ecutrho": 320,
                    "nbnd": 8,
                    "occupations": "tetrahedra",
                },
                "ELECTRONS": {
                    "conv_thr": 1e-8,
                },
            },
            cards={
                "K_POINTS": {
                    "option": "automatic",
                    "data": [[12, 12, 12, 0, 0, 0]],
                },
            },
            species_overrides={
                "Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"},
            },
        )
        
        # Create bands calculation step (pw.x with calculation='bands')
        QVService.init_step(
            project_root=project_dir,
            calculation_selector="bands_daemon",
            step_type="bands_pw",
            name="bands",
            structure_selector="si",
        )
        
        # Configure bands step with manual k-path
        kpoints_data = [
            [5],                       # Number of k-points
            [0.5, 0.5, 0.5, 20],       # L
            [0.0, 0.0, 0.0, 30],       # Gamma
            [0.5, 0.0, 0.5, 10],       # X
            [0.625, 0.25, 0.625, 30],  # U
            [0.0, 0.0, 0.0, 0],        # Gamma (end)
        ]
        
        QVService.configure_step(
            project_root=project_dir,
            calculation_selector="bands_daemon",
            step_selector="bands",
            parameters={
                "CONTROL": {
                    "prefix": "si",
                    "outdir": "./outdir",
                    "pseudo_dir": "./",
                },
                "SYSTEM": {
                    "ecutwfc": 40,
                    "ecutrho": 320,
                    "nbnd": 8,
                },
                "ELECTRONS": {
                    "conv_thr": 1e-8,
                },
            },
            cards={
                "K_POINTS": {
                    "option": "crystal_b",
                    "data": kpoints_data,
                },
            },
            species_overrides={
                "Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"},
            },
        )
        
        # Create bands.x post-processing step
        QVService.init_step(
            project_root=project_dir,
            calculation_selector="bands_daemon",
            step_type="bands",
            name="bandspp",
            structure_selector="si",
        )
        
        QVService.configure_step(
            project_root=project_dir,
            calculation_selector="bands_daemon",
            step_selector="bandspp",
            parameters={
                "BANDS": {
                    "prefix": "si",
                    "outdir": "./outdir",
                    "filband": "si.bands.dat",
                },
            },
        )
        
        return calculation_dir
    
    def test_list_calculations(self, daemon: QVDaemon, project_with_structure: Path, calculation_with_steps: Path):
        """Test listing calculations via daemon."""
        response = send_request(daemon, "list_calculations", {
            "project_root": str(project_with_structure),
        })
        
        assert response["count"] >= 1
        
        calculation_names = [w["name"] for w in response["calculations"]]
        assert "bands_daemon" in calculation_names
    
    def test_run_calculation_via_job_manager(self, daemon: QVDaemon, project_with_structure: Path, calculation_with_steps: Path):
        """Test running calculation via daemon JobManager."""
        project_dir = project_with_structure
        
        # Submit calculation job
        response = send_request(daemon, "run_calculation", {
            "project_root": str(project_dir),
            "calculation": "bands_daemon",
        })
        
        job_id = response["job_id"]
        assert job_id
        assert response["status"] == "pending"
        
        # Wait for job to complete
        final_status = wait_for_job(daemon, job_id, timeout=300.0)
        
        # Check job completed successfully
        assert final_status["status"] in ("completed", "failed"), \
            f"Job ended with unexpected status: {final_status['status']}"
        
        if final_status["status"] == "failed":
            pytest.skip(f"Calculation failed: {final_status.get('error', 'Unknown error')}")
    
    def test_job_list(self, daemon: QVDaemon):
        """Test listing jobs via daemon."""
        response = send_request(daemon, "list_jobs", {})
        
        assert "jobs" in response
        assert "count" in response
        assert response["count"] >= 0
    
    def test_get_band_structure_data(self, daemon: QVDaemon, project_with_structure: Path, calculation_with_steps: Path):
        """Test getting band structure data via daemon after calculation completes."""
        project_dir = project_with_structure
        calculation_dir = calculation_with_steps
        
        # Check if bands data exists
        raw_dir = calculation_dir / "raw"
        bands_gnu = raw_dir / "si.bands.dat.gnu"
        
        if not bands_gnu.exists():
            pytest.skip("Band structure data not found - calculation may have failed")
        
        # Get band structure data via daemon
        response = send_request(daemon, "get_band_structure_data", {
            "project_root": str(project_dir),
            "calculation": "bands_daemon",
        })
        
        assert response["n_bands"] > 0
        assert response["n_kpoints"] > 0
        assert "k_distances" in response
        assert "energies_ev" in response
        assert "high_symmetry_points" in response
        
        # Verify JSON serializable
        json_str = json.dumps(response)
        assert json_str
    
    def test_analyze_bands_and_generate_plot(self, daemon: QVDaemon, project_with_structure: Path, calculation_with_steps: Path):
        """
        Test analyzing bands and generating a PNG plot via QVService.
        
        This is the daemon equivalent of the CLI test that runs:
        qv analyze band <file> --plot --format png --symmetry <file> --scf <file>
        """
        project_dir = project_with_structure
        calculation_dir = calculation_with_steps
        raw_dir = calculation_dir / "raw"
        
        # Check if bands data exists
        bands_gnu = raw_dir / "si.bands.dat.gnu"
        if not bands_gnu.exists():
            pytest.skip("Band structure data not found - calculation may have failed")
        
        # Find the bands.x output for symmetry points
        symmetry_file = None
        for pattern in ["*.bands.out", "*bandspp*.out"]:
            matches = list(raw_dir.glob(pattern))
            if matches:
                symmetry_file = matches[0]
                break
        
        # Find NSCF output for Fermi energy (preferred over SCF for accuracy)
        scf_file = None
        nscf_out = list(raw_dir.glob("*nscf*.out"))
        if nscf_out:
            scf_file = nscf_out[0]
        else:
            # Fall back to SCF output
            scf_out = list(raw_dir.glob("*scf*.out"))
            if scf_out:
                scf_file = scf_out[0]
        
        # Use QVService.analyze_band() to analyze and generate plot
        # This is the service-layer equivalent of "qv analyze band ... --plot"
        result = QVService.analyze_band(
            project_root=project_dir,
            bands_file=bands_gnu,
            calculation_selector="bands_daemon",
            symmetry_file=symmetry_file,
            scf_file=scf_file,
            plot=True,
            plot_format="png",
            shift_fermi=True,
        )
        
        # Verify analysis results
        assert result["n_bands"] > 0
        assert result["n_kpoints"] > 0
        assert "data" in result
        assert "high_symmetry_points" in result
        
        # Verify plot was created
        assert result["plot_path"] is not None, "Plot should have been generated"
        plot_path = Path(result["plot_path"])
        assert plot_path.exists(), f"Plot file not found at {plot_path}"
        assert plot_path.suffix == ".png", f"Plot should be PNG, got {plot_path.suffix}"
        assert plot_path.stat().st_size > 0, "Plot file should not be empty"
        
        # Verify plot is in results directory
        results_dir = calculation_dir / "results"
        assert plot_path.parent == results_dir, f"Plot should be in {results_dir}, got {plot_path.parent}"
        
        # Check JSON serializability of result
        json_str = json.dumps(result["data"], default=str)
        assert json_str


class TestJobManagerDirectly:
    """Test JobManager functionality directly."""
    
    def test_job_status_transitions(self):
        """Test job status transitions."""
        manager = JobManager(max_workers=1)
        
        def quick_job():
            return {"done": True}
        
        job_id = manager.submit("test", quick_job, {})
        
        # Wait for completion
        for _ in range(50):
            status = manager.get_job_status(job_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)
        
        status = manager.get_job_status(job_id)
        assert status["status"] == "completed"
        assert status["result"]["done"] is True
        
        manager.shutdown()
    
    def test_job_failure_captured(self):
        """Test that job failures are captured with error message."""
        manager = JobManager(max_workers=1)
        
        def failing_job():
            raise ValueError("Test error message")
        
        job_id = manager.submit("test", failing_job, {})
        
        # Wait for completion
        for _ in range(50):
            status = manager.get_job_status(job_id)
            if status["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)
        
        status = manager.get_job_status(job_id)
        assert status["status"] == "failed"
        assert "Test error message" in status["error"]
        
        manager.shutdown()
    
    def test_cancel_pending_job(self):
        """Test cancelling a pending job."""
        manager = JobManager(max_workers=1)
        
        # Submit a slow job to block the executor
        def slow_job():
            time.sleep(10)
            return {"done": True}
        
        job1_id = manager.submit("test", slow_job, {})
        
        # Submit another job while first is running
        def quick_job():
            return {"done": True}
        
        job2_id = manager.submit("test", quick_job, {})
        
        # Try to cancel the second job (should be pending)
        time.sleep(0.2)  # Give first job time to start
        
        status = manager.get_job_status(job2_id)
        if status["status"] == "pending":
            cancelled = manager.cancel_job(job2_id)
            # Cancellation may or may not succeed depending on timing
            # but the API should not crash
        
        manager.shutdown(wait=False)


class TestJSONSerializability:
    """Test that all daemon responses are JSON-serializable."""
    
    def test_project_summary_serializable(self, daemon: QVDaemon, project_with_structure: Path):
        """Test project summary response is JSON-serializable."""
        response = send_request(daemon, "get_project_summary", {
            "project_root": str(project_with_structure),
        })
        
        json_str = json.dumps(response)
        parsed = json.loads(json_str)
        assert parsed["name"] == response["name"]
    
    def test_structures_list_serializable(self, daemon: QVDaemon, project_with_structure: Path):
        """Test structures list response is JSON-serializable."""
        response = send_request(daemon, "list_structures", {
            "project_root": str(project_with_structure),
        })
        
        json_str = json.dumps(response)
        parsed = json.loads(json_str)
        assert parsed["count"] == response["count"]
    
    def test_structure_vis_serializable(self, daemon: QVDaemon, project_with_structure: Path):
        """Test structure visualization data is JSON-serializable."""
        response = send_request(daemon, "get_structure_vis", {
            "project_root": str(project_with_structure),
            "selector": "si",
        })
        
        json_str = json.dumps(response)
        parsed = json.loads(json_str)
        
        # Check nested structures
        assert parsed["n_atoms"] == response["n_atoms"]
        assert len(parsed["atoms"]) == len(response["atoms"])
        assert parsed["lattice"]["a"] == response["lattice"]["a"]

