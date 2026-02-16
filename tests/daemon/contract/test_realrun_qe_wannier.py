"""
Pair 6: QE + Wannier90 Multi-Engine Real-Run RPC Test

From-scratch user workflow through daemon RPC:
- Create calculation with imported Si structure
- Configure pseudo mapping
- Add step chain: scf -> nscf -> wannierprep -> pw2wannier -> wannier
- Set key QE/W90 parameters through RPC only
- Run full chain and validate generated artifacts + convergence analysis
"""

from __future__ import annotations

from pathlib import Path
import re
import yaml

from quantumvitas.daemon.server import QVDaemon

from .conftest import send_request


class TestRealRunQEWannier:
    """Real QE+Wannier90 workflow via RPC."""

    def test_qe_wannier_complete_workflow(
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
                "name": "Si Wannier Test",
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

        # 3) Add required steps in user sequence
        for step_type in ("scf", "nscf", "wannierprep", "pw2wannier", "wannier"):
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
        for required in ("scf", "nscf", "wannierprep", "pw2wannier", "wannier"):
            assert required in step_map, f"Missing {required} step in calculation: {steps}"

        # 4) Set parameters
        send_request(
            daemon,
            "update_step_params",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["scf"],
                "parameters": {
                    "SYSTEM": {
                        "ecutwfc": 30.0,
                        "ecutrho": 240.0,
                    }
                },
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
                "parameters": {
                    "SYSTEM": {
                        "ecutwfc": 30.0,
                        "ecutrho": 240.0,
                        "nosym": True,
                        "noinv": True,
                        "nbnd": 4,
                    }
                },
                "cards": {
                    "K_POINTS": {
                        "option": "crystal",
                        "data": [
                            [8],
                            [0.0, 0.0, 0.0, 1.0],
                            [0.0, 0.0, 0.5, 1.0],
                            [0.0, 0.5, 0.0, 1.0],
                            [0.0, 0.5, 0.5, 1.0],
                            [0.5, 0.0, 0.0, 1.0],
                            [0.5, 0.0, 0.5, 1.0],
                            [0.5, 0.5, 0.0, 1.0],
                            [0.5, 0.5, 0.5, 1.0],
                        ],
                    }
                },
            },
        )
        for step_type in ("wannierprep", "wannier"):
            send_request(
                daemon,
                "update_step_params",
                {
                    "project_root": str(project_root),
                    "calculation": calc_ulid,
                    "step": step_map[step_type],
                    "parameters": {
                        "WANNIER90": {
                            "num_wann": 4,
                            "num_bands": 4,
                            "num_iter": 20,
                            "mp_grid": [2, 2, 2],
                            "projections": ["f=0.0,0.0,0.0:sp3"],
                        }
                    },
                },
            )

        # 5) Assert parameter persistence via DTO and YAML (read-only verification)
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
        wprep_detail = send_request(
            daemon,
            "get_step_detail",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["wannierprep"],
            },
        )
        assert scf_detail.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [2, 2, 2], scf_detail
        assert nscf_detail.get("cards", {}).get("K_POINTS", {}).get("option") == "crystal", nscf_detail
        nscf_k_data = nscf_detail.get("cards", {}).get("K_POINTS", {}).get("data", [])
        assert nscf_k_data and nscf_k_data[0] == [8], nscf_detail
        assert nscf_k_data[1][:4] == [0.0, 0.0, 0.0, 1.0], nscf_detail
        assert nscf_k_data[-1][:4] == [0.5, 0.5, 0.5, 1.0], nscf_detail
        w90_params = wprep_detail.get("parameters", {}).get("WANNIER90", {})
        assert w90_params.get("num_wann") == 4, wprep_detail
        assert w90_params.get("num_bands") == 4, wprep_detail
        assert w90_params.get("num_iter") == 20, wprep_detail
        assert w90_params.get("mp_grid") == [2, 2, 2], wprep_detail
        assert w90_params.get("projections") == ["f=0.0,0.0,0.0:sp3"], wprep_detail

        scf_yaml = yaml.safe_load(Path(scf_detail["absolute_path"]).read_text())
        nscf_yaml = yaml.safe_load(Path(nscf_detail["absolute_path"]).read_text())
        wprep_yaml = yaml.safe_load(Path(wprep_detail["absolute_path"]).read_text())
        assert scf_yaml.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [2, 2, 2], scf_yaml
        assert nscf_yaml.get("cards", {}).get("K_POINTS", {}).get("option") == "crystal", nscf_yaml
        assert nscf_yaml.get("cards", {}).get("K_POINTS", {}).get("data", [None])[0] == [8], nscf_yaml
        assert wprep_yaml.get("parameters", {}).get("WANNIER90", {}).get("num_wann") == 4, wprep_yaml
        assert wprep_yaml.get("parameters", {}).get("WANNIER90", {}).get("mp_grid") == [2, 2, 2], wprep_yaml

        # 6) Preflight then run full chain
        preflight = send_request(
            daemon,
            "preflight_check",
            {
                "project_root": str(project_root),
                "calculation_ulid": calc_ulid,
            },
        )
        if "passed" in preflight:
            assert preflight["passed"], preflight
        elif "valid" in preflight:
            assert preflight["valid"], preflight

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
        final_status = wait_for_job(daemon, project_root, job_id, timeout=240)
        assert final_status.get("status") in {"completed", "success"}, final_status

        # 7) Verify key raw files and artifacts exist and contain expected values.
        raw_listing = send_request(
            daemon,
            "list_raw_files",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_map["scf"],
            },
        )
        raw_files: list[str] = []
        for item in raw_listing.get("files", []):
            if isinstance(item, str):
                raw_files.append(item)
            elif isinstance(item, dict):
                name = item.get("filename") or item.get("name") or item.get("path")
                if isinstance(name, str):
                    raw_files.append(name)

        assert "CRASH" not in raw_files, f"Unexpected crash marker present: {raw_files}"

        def _read_raw(filename: str, required: bool = True) -> str:
            content = send_request(
                daemon,
                "read_raw_file",
                {
                    "project_root": str(project_root),
                    "calculation": calc_ulid,
                    "step": step_map["scf"],
                    "filename": filename,
                    "head_lines": 4000,
                    "tail_lines": 0,
                },
            )
            text = content.get("text") or content.get("content") or ""
            if required:
                assert isinstance(text, str) and text.strip(), f"Could not read raw file {filename}: {content}"
            return text if isinstance(text, str) else ""

        # Check required artifacts with diagnostic output on failure
        for required in (
            "scf.in",
            "nscf.in",
            "wannierprep.win",
            "pw2wan.in",
            "wannierprep.nnkp",
            "wannierprep.amn",
            "wannierprep.mmn",
            "wannierprep.wout",
            "pw2wannier.out",
        ):
            if required not in raw_files:
                # Read available error/output logs for diagnosis
                diag_parts = [f"Missing required artifact {required}"]
                diag_parts.append(f"Available files: {raw_files}")
                for log_file in ("wannierprep.err", "wannierprep.out"):
                    if log_file in raw_files:
                        log_text = _read_raw(log_file, required=False)
                        diag_parts.append(f"\n--- {log_file} ---\n{log_text[:2000]}")
                raise AssertionError("\n".join(diag_parts))

        scf_in = _read_raw("scf.in")
        nscf_in = _read_raw("nscf.in")
        w90_win = _read_raw("wannierprep.win")
        pw2wan_in = _read_raw("pw2wan.in")
        pw2wan_out = _read_raw("pw2wannier.out")

        assert "K_POINTS {automatic}" in scf_in or "K_POINTS automatic" in scf_in, scf_in
        assert "2 2 2 0 0 0" in scf_in, scf_in
        assert "K_POINTS {crystal}" in nscf_in or "K_POINTS crystal" in nscf_in, nscf_in
        assert "\n8\n" in nscf_in or "\n  8\n" in nscf_in or "\n 8\n" in nscf_in, nscf_in
        nscf_compact = re.sub(r"\s+", "", nscf_in.lower())
        assert "nosym=.true." in nscf_compact, nscf_in
        assert "noinv=.true." in nscf_compact, nscf_in
        assert "nosym='.true.'" not in nscf_compact, nscf_in
        assert "noinv='.true.'" not in nscf_compact, nscf_in
        assert "nosym=\".true.\"" not in nscf_compact, nscf_in
        assert "noinv=\".true.\"" not in nscf_compact, nscf_in
        assert "num_wann" in w90_win and "4" in w90_win, w90_win
        assert "num_bands" in w90_win and "4" in w90_win, w90_win
        assert "mp_grid" in w90_win and "2 2 2" in w90_win, w90_win
        assert "f=0.0,0.0,0.0:sp3" in w90_win, w90_win
        w90_wout = _read_raw("wannierprep.wout")
        assert "All done: wannier90 exiting" in w90_wout, w90_wout
        assert "seedname = 'wannierprep'" in pw2wan_in or "seedname='wannierprep'" in pw2wan_in, pw2wan_in
        assert ("PW2WANNIER90" in pw2wan_out) or ("PW2WANNIER" in pw2wan_out), pw2wan_out
        assert "JOB DONE" in pw2wan_out, pw2wan_out

        # 8) Validate at least one real-run analysis object is available and populated.
        scf_instances = send_request(
            daemon,
            "get_analysis_instances_for_step",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step_ulid": step_map["scf"],
            },
        ).get("instances", [])
        scf_conv = next((i for i in scf_instances if i.get("object_type") == "convergence"), None)
        assert scf_conv is not None, f"SCF convergence object missing: {scf_instances}"
        assert scf_conv.get("state") == "ok", scf_conv

        latest_scf = send_request(
            daemon,
            "get_latest_run_for_step",
            {
                "project_root": str(project_root),
                "step_ulid": step_map["scf"],
            },
        )
        scf_run_ulid = latest_scf.get("run_ulid")
        assert scf_run_ulid, f"Missing SCF run_ulid: {latest_scf}"

        convergence = send_request(
            daemon,
            "get_analysis",
            {
                "project_root": str(project_root),
                "step_ulid": step_map["scf"],
                "run_ulid": scf_run_ulid,
                "object_type": "convergence",
            },
        )
        arrays = (convergence.get("bundle") or {}).get("arrays", {})
        energy_candidates = (
            arrays.get("scf_energy"),
            arrays.get("energies"),
            arrays.get("total_energy"),
            arrays.get("etot"),
        )
        energy_series = next((v for v in energy_candidates if isinstance(v, list) and len(v) > 1), None)

        # Multi-step chains may expose sparse convergence arrays; fall back to raw SCF output evidence.
        if energy_series is None:
            scf_out = _read_raw("scf.out").lower()
            assert "total energy" in scf_out, scf_out
            assert ("convergence has been achieved" in scf_out) or ("job done" in scf_out), scf_out
        else:
            numeric = [float(v) for v in energy_series]
            assert len(numeric) > 1, numeric
            assert numeric[-1] < 0.0, numeric[-5:]
