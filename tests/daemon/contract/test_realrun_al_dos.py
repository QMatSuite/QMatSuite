"""
Pair 5: Al DOS Real-Run RPC Test

From-scratch user workflow through daemon RPC:
- Try online structure search/import for Al (best effort)
- Fallback to local Al CIF structure fixture if online lookup fails/unavailable
- Create QE DOS workflow (scf -> nscf -> dos)
- Run full calculation and validate DOS analysis
- Assert metallic behavior: DOS at/near Fermi level is non-zero
"""

from __future__ import annotations

from pathlib import Path
import yaml

from quantumvitas.daemon.server import QVDaemon

from .conftest import send_request


class TestRealRunAlDOS:
    """Real QE Al DOS workflow via RPC."""

    def test_al_dos_complete_workflow(
        self,
        qe_project_with_al: tuple[Path, str],
        daemon: QVDaemon,
        wait_for_job,
    ) -> None:
        project_root, local_al_ulid = qe_project_with_al

        # 1) Optional online fetch (best-effort), fallback to local fixture structure.
        structure_ulid = local_al_ulid
        online_used = False
        try:
            online_search = send_request(
                daemon,
                "structure_search_online",
                {
                    "query": "Al",
                    "max_results": 5,
                    "mode": "crystal",
                },
            )
            session_id = online_search.get("session_id")
            candidates = online_search.get("candidates", [])
            if session_id and isinstance(candidates, list) and candidates:
                candidate_id = candidates[0].get("candidate_id")
                if candidate_id:
                    imported = send_request(
                        daemon,
                        "structure_import_online_candidate",
                        {
                            "project_root": str(project_root),
                            "session_id": session_id,
                            "candidate_id": candidate_id,
                            "name": "Al (online)",
                        },
                    )
                    imported_ulid = imported.get("new_structure_ulid") or imported.get("structure_ulid")
                    if imported_ulid:
                        structure_ulid = imported_ulid
                        online_used = True
        except Exception as exc:
            print(f"[pair5] online fetch unavailable, fallback to local Al CIF: {exc}")

        print(f"[pair5] using {'online' if online_used else 'local'} structure ulid={structure_ulid}")

        # 2) Create calculation
        calc_response = send_request(
            daemon,
            "create_calculation",
            {
                "project_root": str(project_root),
                "structure": structure_ulid,
                "name": "Al DOS Test",
                "engine_family": "qe",
            },
        )
        calc_ulid = calc_response.get("calc_ulid") or calc_response.get("calculation_ulid")
        assert calc_ulid, f"No calc ULID in response: {calc_response}"

        # 3) Configure pseudo mapping
        send_request(
            daemon,
            "update_calculation_species_map",
            {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "species_map": {
                    "Al": {"pseudopot": "Al.pbe-n-kjpaw_psl.1.0.0.UPF"},
                },
            },
        )

        # 4) Add workflow steps
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

        # 5) Set step parameters
        common_system = {
            "ecutwfc": 30.0,
            "ecutrho": 240.0,
            "occupations": "smearing",
            "smearing": "gaussian",
            "degauss": 0.02,
        }
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
                "step": step_map["nscf"],
                "parameters": {"SYSTEM": common_system},
                "cards": {
                    "K_POINTS": {
                        "option": "automatic",
                        "data": [[6, 6, 6, 0, 0, 0]],
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
                        "fildos": "al.dos.dat",
                        "emin": -15.0,
                        "emax": 35.0,
                    }
                },
            },
        )

        # 6) Persistence checks (DTO + YAML)
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
        assert scf_detail.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [4, 4, 4], scf_detail
        assert nscf_detail.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [6, 6, 6], nscf_detail
        dos_params = dos_detail.get("parameters", {}).get("DOS", {})
        assert dos_params.get("fildos") == "al.dos.dat", dos_detail
        assert dos_params.get("emin") == -15.0, dos_detail
        assert dos_params.get("emax") == 35.0, dos_detail

        scf_yaml = yaml.safe_load(Path(scf_detail["absolute_path"]).read_text())
        nscf_yaml = yaml.safe_load(Path(nscf_detail["absolute_path"]).read_text())
        dos_yaml = yaml.safe_load(Path(dos_detail["absolute_path"]).read_text())
        assert scf_yaml.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [4, 4, 4], scf_yaml
        assert nscf_yaml.get("cards", {}).get("K_POINTS", {}).get("data", [[None]])[0][:3] == [6, 6, 6], nscf_yaml
        assert dos_yaml.get("parameters", {}).get("DOS", {}).get("fildos") == "al.dos.dat", dos_yaml

        # 7) Run + wait
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

        # 8) Raw input reflects requested setup
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
            raise AssertionError(f"Unable to read step input. Tried={file_names}, discovered={discovered}")

        scf_in = _read_step_input(step_map["scf"], ["scf.in"])
        nscf_in = _read_step_input(step_map["nscf"], ["nscf.in"])
        dos_in = _read_step_input(step_map["dos"], ["dos.in", "dos.dos.in"])
        assert "4 4 4 0 0 0" in scf_in, scf_in
        assert "6 6 6 0 0 0" in nscf_in, nscf_in
        assert "fildos = 'al.dos.dat'" in dos_in or "fildos='al.dos.dat'" in dos_in, dos_in
        assert "emin = -15.0" in dos_in or "emin=-15.0" in dos_in, dos_in
        assert "emax = 35.0" in dos_in or "emax=35.0" in dos_in, dos_in

        # 9) Validate DOS analysis + metallic signature at Fermi
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

        # Determine DOS value at/near Fermi (supports 1D and 2D spin arrays).
        render_meta = bundle.get("render_meta", {})
        fermi = render_meta.get("reference_energy")
        assert fermi is not None, render_meta
        assert min(energies) < float(fermi) < max(energies), (fermi, energies[:5], energies[-5:])

        nearest_idx = min(range(len(energies)), key=lambda i: abs(float(energies[i]) - float(fermi)))
        if total_dos and isinstance(total_dos[0], list):
            dos_at_fermi = max(abs(float(channel[nearest_idx])) for channel in total_dos if isinstance(channel, list))
            assert len(total_dos) == 2, arrays
        else:
            assert len(total_dos) == len(energies), f"DOS/E axis size mismatch: {len(total_dos)} vs {len(energies)}"
            dos_at_fermi = abs(float(total_dos[nearest_idx]))

        assert dos_at_fermi > 1.0e-3, f"Expected metallic DOS at Fermi to be non-zero, got {dos_at_fermi}"
        assert max(abs(float(v)) for v in (total_dos[0] if total_dos and isinstance(total_dos[0], list) else total_dos)) > 0.0
