"""
Pair 4: Si DOS Real-Run RPC Test

From-scratch user workflow through daemon RPC:
- Create calculation from imported Si structure
- Configure pseudo mapping
- Add SCF -> NSCF -> DOS chain
- Set practical smoke-test parameters and explicit k-meshes
- Run full calculation with real QE
- Validate DOS analysis payload (arrays, Fermi reference, non-trivial data)
"""

from __future__ import annotations

from pathlib import Path
import yaml

from quantumvitas.daemon.server import QVDaemon

from .conftest import send_request


class TestRealRunSiDOS:
    """Real QE DOS workflow via RPC."""

    def test_si_dos_complete_workflow(
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
                "name": "Si DOS Test",
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

        # 3) Add workflow steps
        for step_type in ("scf", "nscf", "dos"):
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
        step_map: dict[str, str] = {}
        for step in calc_detail.get("steps", []):
            gen = step.get("step_type_gen")
            ulid = step.get("ulid")
            if gen and ulid:
                step_map[gen] = ulid
        for required in ("scf", "nscf", "dos"):
            assert required in step_map, f"Missing {required} step: {calc_detail.get('steps', [])}"

        # 4) Set step parameters
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
                "step": step_map["dos"],
                "parameters": {
                    "DOS": {
                        "fildos": "si.dos.dat",
                        "emin": -9.0,
                        "emax": 16.0,
                    }
                },
            },
        )

        # 5) Assert step parameter persistence in DTO + YAML
        def _get_detail(step_ulid: str) -> dict:
            return send_request(
                daemon,
                "get_step_detail",
                {
                    "project_root": str(project_root),
                    "calculation": calc_ulid,
                    "step": step_ulid,
                },
            )

        scf_detail = _get_detail(step_map["scf"])
        nscf_detail = _get_detail(step_map["nscf"])
        dos_detail = _get_detail(step_map["dos"])

        assert scf_detail.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [2, 2, 2], scf_detail
        assert nscf_detail.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [4, 4, 4], nscf_detail
        dos_params = dos_detail.get("parameters", {}).get("DOS", {})
        assert dos_params.get("fildos") == "si.dos.dat", dos_detail
        assert dos_params.get("emin") == -9.0, dos_detail
        assert dos_params.get("emax") == 16.0, dos_detail

        scf_yaml = yaml.safe_load(Path(scf_detail["absolute_path"]).read_text())
        nscf_yaml = yaml.safe_load(Path(nscf_detail["absolute_path"]).read_text())
        dos_yaml = yaml.safe_load(Path(dos_detail["absolute_path"]).read_text())
        assert scf_yaml.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [2, 2, 2], scf_yaml
        assert nscf_yaml.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [4, 4, 4], nscf_yaml
        assert dos_yaml.get("parameters", {}).get("DOS", {}).get("fildos") == "si.dos.dat", dos_yaml

        # 6) Run calculation
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

        # 7) Raw input reflects configured meshes/params
        def _read_step_input(step_ulid: str, file_names: list[str]) -> str:
            listing = send_request(
                daemon,
                "list_raw_files",
                {
                    "project_root": str(project_root),
                    "calculation": calc_ulid,
                    "step": step_ulid,
                },
            )
            discovered: list[str] = []
            for item in listing.get("files", []):
                if isinstance(item, str):
                    discovered.append(item)
                elif isinstance(item, dict):
                    name = item.get("filename") or item.get("name") or item.get("path")
                    if isinstance(name, str):
                        discovered.append(name)

            # Some QE modules materialize module-qualified input names (e.g., dos.dos.in).
            for candidate in file_names + discovered:
                if not candidate:
                    continue
                try:
                    content = send_request(
                        daemon,
                        "read_raw_file",
                        {
                            "project_root": str(project_root),
                            "calculation": calc_ulid,
                            "step": step_ulid,
                            "filename": candidate,
                            "head_lines": 2000,
                            "tail_lines": 0,
                        },
                    )
                except RuntimeError:
                    continue
                text = content.get("text") or content.get("content") or ""
                if isinstance(text, str) and text.strip():
                    return text
            raise AssertionError(f"Unable to read any step input. Tried={file_names}, discovered={discovered}")

        scf_in = _read_step_input(step_map["scf"], ["scf.in"])
        nscf_in = _read_step_input(step_map["nscf"], ["nscf.in"])
        dos_in = _read_step_input(step_map["dos"], ["dos.in", "dos.dos.in"])

        assert "2 2 2 0 0 0" in scf_in, scf_in
        assert "4 4 4 0 0 0" in nscf_in, nscf_in
        # fildos is runtime-managed: derived from input filename stem, not user value
        assert "fildos" in dos_in.lower(), f"fildos not found in materialized dos input: {dos_in}"
        assert "emin = -9.0" in dos_in or "emin=-9.0" in dos_in, dos_in
        assert "emax = 16.0" in dos_in or "emax=16.0" in dos_in, dos_in

        # 8) Validate DOS analysis instance + payload
        instances_response = send_request(
            daemon,
            "get_analysis_instances_for_step",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step_ulid": step_map["dos"],
            },
        )
        instances = instances_response.get("instances", [])
        assert instances, f"No analysis instances for dos step: {instances_response}"
        dos_instance = next((i for i in instances if i.get("object_type") == "dos"), None)
        assert dos_instance is not None, f"No DOS instance: {instances}"
        assert dos_instance.get("state") == "ok", dos_instance

        latest_run = send_request(
            daemon,
            "get_latest_run_for_step",
            {
                "project_root": str(project_root),
                "step_ulid": step_map["dos"],
            },
        )
        run_ulid = latest_run.get("run_ulid")
        assert run_ulid, f"Missing run_ulid: {latest_run}"

        dos_analysis = send_request(
            daemon,
            "get_analysis",
            {
                "project_root": str(project_root),
                "step_ulid": step_map["dos"],
                "run_ulid": run_ulid,
                "object_type": "dos",
            },
        )
        bundle = dos_analysis.get("bundle", {})
        arrays = bundle.get("arrays", {})
        energies = arrays.get("energies", [])
        total_dos = arrays.get("total_dos", [])
        assert isinstance(energies, list) and len(energies) > 20, arrays
        assert isinstance(total_dos, list) and len(total_dos) > 0, arrays

        # total_dos can be 1D (non-spin) or 2D ([up, down]).
        if total_dos and isinstance(total_dos[0], list):
            dos_vector = total_dos[0]
            assert len(total_dos) == 2, arrays
        else:
            dos_vector = total_dos
        assert len(dos_vector) == len(energies), f"DOS/E axis size mismatch: {len(dos_vector)} vs {len(energies)}"
        assert min(energies) < 0 < max(energies), energies[:5]
        assert max(abs(float(v)) for v in dos_vector) > 0.0, "DOS values are all zero"

        render_meta = bundle.get("render_meta", {})
        assert render_meta.get("axis_labels", {}).get("x"), render_meta
        assert render_meta.get("axis_labels", {}).get("y"), render_meta
        assert render_meta.get("reference_energy") is not None, render_meta
