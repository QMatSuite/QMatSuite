"""
Pair 3: Si Bands Real-Run RPC Test

From-scratch real user workflow through daemon RPC:
- Create calculation from imported Si structure
- Configure pseudo mapping
- Add multi-step QE chain: scf -> nscf -> bandspw -> bands
- Set practical smoke-test parameters
- Run full calculation
- Validate bands analysis payload (shape + metadata)
"""

from __future__ import annotations

from pathlib import Path
import yaml

from qmatsuite.daemon.server import QMSDaemon

from .conftest import send_request


class TestRealRunSiBands:
    """Real QE multi-step bands workflow via RPC."""

    def test_si_bands_complete_workflow(
        self,
        qe_project_with_si: tuple[Path, str],
        daemon: QMSDaemon,
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
                "name": "Si Bands Test",
                "engine_family": "qe",
            },
        )
        calc_ulid = calc_response.get("calc_ulid") or calc_response.get("calculation_ulid")
        assert calc_ulid, f"No calc ULID in response: {calc_response}"

        # 2) Configure pseudo mapping
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

        # 3) Add required steps in sequence
        for step_type in ("scf", "nscf", "bandspw", "bands"):
            send_request(
                daemon,
                "add_step_to_calculation",
                {
                    "project_root": str(project_root),
                    "calculation": calc_ulid,
                    "step_type_gen": step_type,
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
        steps = calc_detail.get("steps", [])
        step_map: dict[str, str] = {}
        for step in steps:
            gen = step.get("step_type_gen")
            ulid = step.get("ulid")
            if gen and ulid:
                step_map[gen] = ulid

        for required in ("scf", "nscf", "bandspw", "bands"):
            assert required in step_map, f"Missing {required} step in calculation: {steps}"

        # 4) Set parameters for each step
        common_system = {"ecutwfc": 30.0, "ecutrho": 240.0}
        send_request(
            daemon,
            "update_step_params",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["scf"],
                "parameters": {"SYSTEM": common_system},
                "cards": {
                    "K_POINTS": {
                        "option": "automatic",
                        "data": [[2, 2, 2, 0, 0, 0]],
                    }
                },
            },
        )
        send_request(
            daemon,
            "update_step_params",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["nscf"],
                "parameters": {"SYSTEM": common_system},
                "cards": {
                    "K_POINTS": {
                        "option": "automatic",
                        "data": [[4, 4, 4, 0, 0, 0]],
                    }
                },
            },
        )
        send_request(
            daemon,
            "update_step_params",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["bandspw"],
                "parameters": {
                    "CONTROL": {"calculation": "bands"},
                    "ELECTRONS": {"conv_thr": 1.0e-6},
                    "SYSTEM": common_system,
                },
                "cards": {
                    "K_POINTS": {
                        "option": "crystal_b",
                        "data": [
                            [5],
                            [0.0, 0.5, 0.0, 6],
                            [0.0, 0.0, 0.0, 8],
                            [-0.5, 0.0, -0.5, 4],
                            [-0.375, 0.25, -0.375, 8],
                            [0.0, 0.0, 0.0, 0],
                        ],
                    }
                },
            },
        )
        # Required for bands parser evidence (.bands.dat.gnu)
        send_request(
            daemon,
            "update_step_params",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["bands"],
                "parameters": {"BANDS": {"filband": "bands.dat"}},
            },
        )

        # Assert K_POINTS edits were persisted (demonstrates card-level control via RPC).
        scf_detail = send_request(
            daemon,
            "get_step_detail",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["scf"],
            },
        )
        nscf_detail = send_request(
            daemon,
            "get_step_detail",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["nscf"],
            },
        )
        bandspw_detail = send_request(
            daemon,
            "get_step_detail",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["bandspw"],
            },
        )
        assert scf_detail.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [2, 2, 2], scf_detail
        assert nscf_detail.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [4, 4, 4], nscf_detail
        bandspw_card = bandspw_detail.get("cards", {}).get("K_POINTS", {})
        assert bandspw_card.get("option") == "crystal_b", bandspw_detail
        bandspw_rows = bandspw_card.get("data", [])
        assert len(bandspw_rows) >= 6, bandspw_card
        assert bandspw_rows[1][:4] == [0.0, 0.5, 0.0, 6], bandspw_card
        assert bandspw_rows[2][:4] == [0.0, 0.0, 0.0, 8], bandspw_card
        assert bandspw_rows[3][:4] == [-0.5, 0.0, -0.5, 4], bandspw_card

        # Verify persisted YAML files, not only in-memory DTOs.
        scf_yaml = yaml.safe_load(Path(scf_detail["absolute_path"]).read_text())
        nscf_yaml = yaml.safe_load(Path(nscf_detail["absolute_path"]).read_text())
        bandspw_yaml = yaml.safe_load(Path(bandspw_detail["absolute_path"]).read_text())
        assert scf_yaml.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [2, 2, 2], scf_yaml
        assert nscf_yaml.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [4, 4, 4], nscf_yaml
        assert bandspw_yaml.get("cards", {}).get("K_POINTS", {}).get("option") == "crystal_b", bandspw_yaml
        assert bandspw_yaml.get("cards", {}).get("K_POINTS", {}).get("data", [[], []])[1][:4] == [0.0, 0.5, 0.0, 6], bandspw_yaml

        # 5) Run full calculation
        run_response = send_request(
            daemon,
            "run_calculation",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
            },
        )
        job_id = run_response.get("job_id")
        assert job_id, f"No job_id in response: {run_response}"
        final_status = wait_for_job(daemon, project_root, job_id, timeout=180)
        assert final_status.get("status") in {"completed", "success"}, final_status

        # Verify generated raw inputs reflect the requested meshes/path (not defaults).
        def _read_step_input(step_ulid: str, file_name: str) -> str:
            content = send_request(
                daemon,
                "read_raw_file",
                {
                    "project_root": str(project_root),
                    "calculation": calc_ulid,
                    "step": step_ulid,
                    "filename": file_name,
                    "head_lines": 2000,
                    "tail_lines": 0,
                },
            )
            text = content.get("text") or content.get("content") or ""
            assert isinstance(text, str) and text.strip(), f"Failed to read raw input {file_name}: {content}"
            return text

        scf_in = _read_step_input(step_map["scf"], "scf.in")
        nscf_in = _read_step_input(step_map["nscf"], "nscf.in")
        bandspw_in = _read_step_input(step_map["bandspw"], "bandspw.in")

        assert "K_POINTS {automatic}" in scf_in or "K_POINTS automatic" in scf_in, scf_in
        assert "2 2 2 0 0 0" in scf_in, scf_in
        assert "K_POINTS {automatic}" in nscf_in or "K_POINTS automatic" in nscf_in, nscf_in
        assert "4 4 4 0 0 0" in nscf_in, nscf_in
        assert "K_POINTS {crystal_b}" in bandspw_in or "K_POINTS crystal_b" in bandspw_in, bandspw_in
        assert "0.0000 0.5000 0.0000 6" in bandspw_in or "0.0 0.5 0.0 6" in bandspw_in, bandspw_in
        assert "-0.5000 0.0000 -0.5000 4" in bandspw_in or "-0.5 0.0 -0.5 4" in bandspw_in, bandspw_in

        # 6) Validate SCF convergence analysis exists in this multi-step workflow.
        scf_instances_response = send_request(
            daemon,
            "get_analysis_instances_for_step",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step_ulid": step_map["scf"],
            },
        )
        scf_instances = scf_instances_response.get("instances", [])
        assert scf_instances, f"No analysis instances for SCF step: {scf_instances_response}"
        scf_conv_instance = next((i for i in scf_instances if i.get("object_type") == "convergence"), None)
        assert scf_conv_instance is not None, f"SCF convergence object missing: {scf_instances}"
        assert scf_conv_instance.get("state") == "ok", scf_conv_instance

        scf_latest_run = send_request(
            daemon,
            "get_latest_run_for_step",
            {
                "project_root": str(project_root),
                "step_ulid": step_map["scf"],
            },
        )
        scf_run_ulid = scf_latest_run.get("run_ulid")
        assert scf_run_ulid, f"Missing SCF run_ulid: {scf_latest_run}"

        # Some runs expose convergence state without dense arrays at this step in multi-step chains.
        # Verify real SCF convergence evidence directly in raw output.
        scf_out_resp = send_request(
            daemon,
            "read_raw_file",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["scf"],
                "filename": "scf.out",
                "head_lines": 2000,
                "tail_lines": 0,
            },
        )
        scf_out = (scf_out_resp.get("text") or scf_out_resp.get("content") or "")
        assert isinstance(scf_out, str) and scf_out.strip(), scf_out_resp
        scf_out_lower = scf_out.lower()
        assert "total energy" in scf_out_lower, scf_out
        assert ("convergence has been achieved" in scf_out_lower) or ("job done" in scf_out_lower), scf_out

        # 7) Validate bands analysis availability on bandspw step
        bandspw_ulid = step_map["bandspw"]
        instances_response = send_request(
            daemon,
            "get_analysis_instances_for_step",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step_ulid": bandspw_ulid,
            },
        )
        instances = instances_response.get("instances", [])
        assert instances, f"No analysis instances for bandspw: {instances_response}"
        bands_instance = next((i for i in instances if i.get("object_type") == "bands"), None)
        assert bands_instance is not None, f"No bands instance: {instances}"
        assert bands_instance.get("state") == "ok", bands_instance

        latest_run = send_request(
            daemon,
            "get_latest_run_for_step",
            {
                "project_root": str(project_root),
                "step_ulid": bandspw_ulid,
            },
        )
        run_ulid = latest_run.get("run_ulid")
        assert run_ulid, f"Missing run_ulid: {latest_run}"

        bands_analysis = send_request(
            daemon,
            "get_analysis",
            {
                "project_root": str(project_root),
                "step_ulid": bandspw_ulid,
                "run_ulid": run_ulid,
                "object_type": "bands",
            },
        )
        bundle = bands_analysis.get("bundle", {})
        arrays = bundle.get("arrays", {})
        k_distances = arrays.get("k_distances", [])
        eigenvalues = arrays.get("eigenvalues", [])
        assert isinstance(k_distances, list) and len(k_distances) > 1, arrays
        assert isinstance(eigenvalues, list) and len(eigenvalues) > 1, arrays

        n_k = len(eigenvalues)
        n_bands = len(eigenvalues[0]) if eigenvalues and isinstance(eigenvalues[0], list) else 0
        assert n_k > 1, f"Unexpected n_kpoints: {n_k}"
        assert n_bands > 0, f"Unexpected n_bands: {n_bands}"
        assert all(isinstance(row, list) and len(row) == n_bands for row in eigenvalues[: min(10, n_k)])

        render_meta = bundle.get("render_meta", {})
        assert render_meta.get("axis_labels", {}).get("x"), render_meta
        assert render_meta.get("axis_labels", {}).get("y"), render_meta
        assert len(render_meta.get("markers", [])) >= 2, render_meta
        assert render_meta.get("reference_energy") is not None, render_meta
