"""
Pair 1: Si SCF Real-Run RPC Test

Tests the complete workflow as a USER would through the daemon:
1. Create project + import structure (fixture)
2. Create calculation (engine_family=qe)
3. Set species_map (pseudopotential selection)
4. Add SCF step
5. Set parameters
6. Run calculation with real QE
7. Validate analysis results

This is a REAL QE execution test - QE must be available.

CONSTRAINT: No direct YAML/JSON writes. All state changes go through
RPC calls (daemon.handle_request), exactly as the GUI would.
"""

from pathlib import Path
import pytest
from quantumvitas.daemon.server import QVDaemon
from .conftest import send_request


class TestRealRunSiSCF:
    """Real QE execution test for Si SCF calculation."""

    def test_si_scf_complete_workflow(self, qe_project_with_si, daemon: QVDaemon, wait_for_job):
        """
        Complete Si SCF workflow from project creation to analysis.

        This test exercises the full user journey via RPC only:
        - Create calculation with imported structure
        - Configure pseudopotential via species_map RPC
        - Add SCF step with reasonable parameters
        - Run real QE calculation
        - Validate convergence analysis output
        """
        project_root, structure_ulid = qe_project_with_si

        # --- User action 1: Create calculation ---
        calc_response = send_request(daemon, "create_calculation", {
            "project_root": str(project_root),
            "structure": structure_ulid,
            "name": "Si SCF Test",
            "engine_family": "qe",
        })
        calc_ulid = calc_response.get("calc_ulid") or calc_response.get("calculation_ulid")
        assert calc_ulid is not None, f"No calc ULID in response: {calc_response}"

        # --- User action 2: Select pseudopotential for Si ---
        # The runner auto-stages from <repo_root>/resources/pseudo/ at run time.
        # The user just picks the filename via the GUI species-map selector.
        send_request(daemon, "update_calculation_species_map", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "species_map": {
                "Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"},
            },
        })

        # --- User action 3: Add SCF step ---
        add_step_response = send_request(daemon, "add_step_to_calculation", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step_type_gen": "scf",
        })
        steps = add_step_response.get("steps", [])
        assert steps, f"No steps returned: {add_step_response}"
        step_ulid = steps[-1]["step_ulid"]

        # --- User action 4: Set parameters (low cutoff for speed) ---
        # NOTE: K_POINTS in QE is a CARD, not a namelist. Set via k_points
        # at top level, not nested under K_POINTS as a namelist.
        send_request(daemon, "update_step_params", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step": step_ulid,
            "parameters": {
                "SYSTEM": {"ecutwfc": 20.0},
            },
        })

        # Verify parameters were persisted (read-back)
        step_detail = send_request(daemon, "get_step_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step": step_ulid,
        })
        params = step_detail.get("parameters", {})
        assert params.get("SYSTEM", {}).get("ecutwfc") == 20.0, \
            f"ecutwfc not set correctly. Got: {params}"

        # --- User action 5: Run calculation ---
        run_response = send_request(daemon, "run_calculation", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
        })
        job_id = run_response.get("job_id")
        assert job_id is not None, f"No job_id in response: {run_response}"

        # --- Wait for QE to finish ---
        final_status = wait_for_job(daemon, project_root, job_id, timeout=120)
        print(f"Job status: {final_status.get('status')}")

        # --- User action 6: Check analysis ---
        analysis_instances = send_request(daemon, "get_analysis_instances_for_step", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step_ulid": step_ulid,
        })

        assert "instances" in analysis_instances, "No instances field"
        instances = analysis_instances["instances"]
        assert len(instances) > 0, "No analysis instances"

        # Convergence instance must exist
        convergence = next(
            (i for i in instances if i.get("object_type") == "convergence"),
            None,
        )
        assert convergence is not None, \
            f"No convergence instance. Types: {[i['object_type'] for i in instances]}"
        assert "state" in convergence
        assert "bundle" in convergence

        print(f"Convergence state: {convergence['state']}")

        # Deep payload assertions: verify real convergence data, not only instance existence.
        latest_run = send_request(daemon, "get_latest_run_for_step", {
            "project_root": str(project_root),
            "step_ulid": step_ulid,
        })
        run_ulid = latest_run.get("run_ulid")
        assert run_ulid, f"Missing run_ulid: {latest_run}"

        convergence_payload = send_request(daemon, "get_analysis", {
            "project_root": str(project_root),
            "step_ulid": step_ulid,
            "run_ulid": run_ulid,
            "object_type": "convergence",
        })
        bundle = convergence_payload.get("bundle", {})
        arrays = bundle.get("arrays", {})

        # Accept schema aliases and select the first non-trivial energy vector.
        energy_aliases = (
            "scf_energy",
            "energies",
            "total_energy",
            "total_energy_ry",
            "etot",
        )
        energy_series = None
        for key in energy_aliases:
            candidate = arrays.get(key)
            if isinstance(candidate, list) and len(candidate) > 1:
                energy_series = candidate
                break
        assert energy_series is not None, f"No non-trivial energy series in convergence arrays: {arrays}"

        numeric_energy = [float(v) for v in energy_series]
        assert len(numeric_energy) > 1, numeric_energy
        assert numeric_energy[-1] < 0.0, f"Final total energy should be negative for Si SCF: {numeric_energy[-5:]}"

        # Convergence trend check: end-of-run energy differences should be smaller than early-run deltas.
        deltas = [abs(numeric_energy[i + 1] - numeric_energy[i]) for i in range(len(numeric_energy) - 1)]
        assert len(deltas) >= 1, deltas
        if len(deltas) >= 2:
            early_max = max(deltas[: min(3, len(deltas))])
            late_min = min(deltas[-min(3, len(deltas)):])
            assert late_min <= early_max, f"SCF deltas did not tighten toward the end: {deltas}"

    def test_si_scf_preflight_check(self, qe_project_with_si, daemon: QVDaemon):
        """
        Test that preflight check passes for a properly configured Si SCF calc.

        Lighter test — validates setup without executing QE.
        """
        project_root, structure_ulid = qe_project_with_si

        # Create calculation
        calc_response = send_request(daemon, "create_calculation", {
            "project_root": str(project_root),
            "structure": structure_ulid,
            "name": "Si SCF Preflight",
            "engine_family": "qe",
        })
        calc_ulid = calc_response.get("calc_ulid") or calc_response.get("calculation_ulid")

        # Verify engine_family was stored
        calc_detail = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
        })
        assert calc_detail.get("engine_family") == "qe", \
            f"engine_family={calc_detail.get('engine_family')}"

        # Add step
        send_request(daemon, "add_step_to_calculation", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step_type_gen": "scf",
        })

        # Preflight check
        preflight = send_request(daemon, "preflight_check", {
            "project_root": str(project_root),
            "calculation_ulid": calc_ulid,
        })

        assert preflight is not None
        if "passed" in preflight:
            assert preflight["passed"], f"Preflight failed: {preflight}"
        elif "valid" in preflight:
            assert preflight["valid"], f"Preflight invalid: {preflight}"
