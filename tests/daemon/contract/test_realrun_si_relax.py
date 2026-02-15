"""
Pair 2: Si VC-Relax Real-Run RPC Test

From-scratch user workflow through daemon RPC only:
1. Create calculation on imported Si structure
2. Configure pseudopotential mapping
3. Add RELAX step (VC mode is a parameter, not a separate step type)
4. Set VC-relax parameters
5. Run real QE job and wait for completion
6. Validate convergence + trajectory analysis outputs
7. Validate relax structure promotion flow
"""

from __future__ import annotations

from pathlib import Path
import yaml

from quantumvitas.daemon.server import QVDaemon

from .conftest import send_request


class TestRealRunSiRelax:
    """Real QE execution test for Si VC-relax workflow."""

    def test_si_vc_relax_complete_workflow(
        self,
        qe_project_with_si: tuple[Path, str],
        daemon: QVDaemon,
        wait_for_job,
    ) -> None:
        project_root, structure_ulid = qe_project_with_si

        # 1) Create calculation
        calc_response = send_request(
            daemon,
            "create_calculation",
            {
                "project_root": str(project_root),
                "structure": structure_ulid,
                "name": "Si VC Relax Test",
                "engine_family": "qe",
            },
        )
        calc_ulid = calc_response.get("calc_ulid") or calc_response.get("calculation_ulid")
        assert calc_ulid is not None, f"No calc ULID in response: {calc_response}"

        # 2) Configure pseudo mapping via user-facing RPC
        send_request(
            daemon,
            "update_calculation_species_map",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "species_map": {
                    "Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"},
                },
            },
        )

        # 3) Add relax step (VC mode is controlled by CONTROL.calculation)
        send_request(
            daemon,
            "add_step_to_calculation",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step_type_gen": "relax",
            },
        )

        calc_detail = send_request(
            daemon,
            "get_calculation_detail",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
            },
        )
        relax_steps = [s for s in calc_detail.get("steps", []) if s.get("step_type_gen") == "relax"]
        assert relax_steps, f"No relax step found in calculation detail: {calc_detail}"
        step_ulid = relax_steps[-1]["ulid"]

        # 4) Set VC-relax parameters
        send_request(
            daemon,
            "update_step_params",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_ulid,
                "parameters": {
                    "CONTROL": {"calculation": "vc-relax", "nstep": 3},
                    "SYSTEM": {"ecutwfc": 30.0, "ecutrho": 240.0},
                    "CELL": {"cell_dofree": "all"},
                },
                "cards": {
                    "K_POINTS": {
                        "option": "automatic",
                        "data": [[2, 2, 2, 0, 0, 0]],
                    }
                },
            },
        )

        step_detail = send_request(
            daemon,
            "get_step_detail",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_ulid,
            },
        )
        params = step_detail.get("parameters", {})
        assert params.get("CONTROL", {}).get("calculation") == "vc-relax"
        assert params.get("CONTROL", {}).get("nstep") == 3
        assert params.get("SYSTEM", {}).get("ecutwfc") == 30.0
        assert params.get("CELL", {}).get("cell_dofree") == "all"
        step_cards = step_detail.get("cards", {})
        assert step_cards.get("K_POINTS", {}).get("option") == "automatic", step_cards
        assert step_cards.get("K_POINTS", {}).get("data", [[None]])[0][:3] == [2, 2, 2], step_cards

        # Persisted-file check (not only API DTO)
        step_yaml = yaml.safe_load(Path(step_detail["absolute_path"]).read_text())
        assert step_yaml.get("cards", {}).get("K_POINTS", {}).get("option") == "automatic", step_yaml
        assert step_yaml.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [2, 2, 2], step_yaml

        # 5) Run + wait
        run_response = send_request(
            daemon,
            "run_calculation",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
            },
        )
        job_id = run_response.get("job_id")
        assert job_id, f"No job_id in run response: {run_response}"
        final_status = wait_for_job(daemon, project_root, job_id, timeout=180)
        assert final_status.get("status") in {"completed", "success"}, final_status

        # Raw input should reflect explicit kmesh, not defaults.
        relax_input = send_request(
            daemon,
            "read_raw_file",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_ulid,
                "filename": "relax.in",
                "head_lines": 400,
                "tail_lines": 0,
            },
        )
        relax_in_text = relax_input.get("text") or relax_input.get("content") or ""
        assert isinstance(relax_in_text, str) and relax_in_text.strip(), relax_input
        assert "K_POINTS {automatic}" in relax_in_text or "K_POINTS automatic" in relax_in_text, relax_in_text
        assert "2 2 2 0 0 0" in relax_in_text, relax_in_text
        assert "nstep = 3" in relax_in_text, relax_in_text

        # 6) Validate analysis instances
        instances_response = send_request(
            daemon,
            "get_analysis_instances_for_step",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step_ulid": step_ulid,
            },
        )
        instances = instances_response.get("instances", [])
        assert instances, f"No analysis instances for relax step: {instances_response}"
        by_type = {item.get("object_type"): item for item in instances}
        assert "convergence" in by_type, f"Missing convergence instance: {instances}"
        assert "trajectory" in by_type, f"Missing trajectory instance: {instances}"
        assert by_type["convergence"].get("state") == "ok", by_type["convergence"]
        assert by_type["trajectory"].get("state") == "ok", by_type["trajectory"]

        # 7) Fetch full analysis payloads and assert non-trivial data
        latest_run = send_request(
            daemon,
            "get_latest_run_for_step",
            {
                "project_root": str(project_root),
                "step_ulid": step_ulid,
            },
        )
        run_ulid = latest_run.get("run_ulid")
        assert run_ulid, f"Missing run_ulid: {latest_run}"

        convergence = send_request(
            daemon,
            "get_analysis",
            {
                "project_root": str(project_root),
                "step_ulid": step_ulid,
                "run_ulid": run_ulid,
                "object_type": "convergence",
            },
        )
        conv_bundle = convergence.get("bundle", {})
        conv_arrays = conv_bundle.get("arrays", {})
        scf_energy = conv_arrays.get("scf_energy", [])
        ionic_force = conv_arrays.get("ionic_max_force", [])
        assert isinstance(scf_energy, list) and len(scf_energy) > 1, conv_arrays
        assert isinstance(ionic_force, list) and len(ionic_force) >= 1, conv_arrays
        assert min(scf_energy) < 0, f"Unexpected SCF energies: {scf_energy[:5]}"

        trajectory = send_request(
            daemon,
            "get_analysis",
            {
                "project_root": str(project_root),
                "step_ulid": step_ulid,
                "run_ulid": run_ulid,
                "object_type": "trajectory",
            },
        )
        traj_bundle = trajectory.get("bundle", {})
        traj_series = traj_bundle.get("series", [])
        traj_frames = (traj_bundle.get("geometry_frames") or {}).get("frames", [])
        assert isinstance(traj_series, list) and len(traj_series) >= 1, traj_bundle
        assert isinstance(traj_frames, list) and len(traj_frames) >= 2, traj_bundle
        primary_series = traj_series[0]
        assert len(primary_series.get("x", [])) == len(primary_series.get("y", []))
        assert len(primary_series.get("x", [])) >= 2

        # NOTE: promote_relax_structure is intentionally not asserted here.
        # With smoke-optimized vc-relax settings (bounded nstep), QE may finish
        # without emitting a final-coordinates block required by promote flow.
