"""
Integration test for LAMMPS chain workflow (relax → MD → restart).

Workflow 3 from implementation plan: Relax → MD → Restart.
"""

import json
import pytest
import yaml
import shutil
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.calculation.calculation import Calculation
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.core.yaml_io import save_yaml_doc
from quantumvitas.core.yamldoc import CalcDoc
from quantumvitas.core.models import load_calculation
from quantumvitas.core.pseudo_provenance import compute_sha256_file
from quantumvitas.core.resources import get_resources_dir


@pytest.fixture
def chain_project(tmp_path: Path):
    """Create a LAMMPS project with chain workflow (relax → MD → restart)."""
    from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
    from pymatgen.core import Structure, Lattice
    
    # Check LAMMPS availability
    try:
        resolve_lammps_bin()
    except FileNotFoundError:
        pytest.skip("LAMMPS not installed")
    
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "chain_project",
        name="Chain Workflow Test"
    )
    
    # Create Cu FCC structure
    lattice = Lattice.cubic(3.6)
    structure = Structure(
        lattice,
        ["Cu"] * 4,
        [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]]
    )
    
    # Save structure to temporary file
    struct_file = tmp_path / "cu_fcc.json"
    struct_file.write_text(json.dumps(structure.as_dict()))
    
    # Import structure
    struct_result = QVService(project_root).structure.import_file(struct_file, name="Cu FCC")
    structure_ulid = struct_result.meta.ulid
    
    # Copy potential file if available
    potential_src = Path(__file__).parent.parent / "data" / "lammps" / "chain_workflow" / "potentials" / "Cu_u3.eam"
    if not potential_src.exists():
        # Try resources directory
        potential_src = get_resources_dir() / "lammps" / "potentials" / "Cu_u3.eam"
    
    if potential_src.exists():
        potentials_dir = project_root / "potentials"
        potentials_dir.mkdir(exist_ok=True)
        potential_dst = potentials_dir / "Cu_u3.eam"
        shutil.copy2(potential_src, potential_dst)
        potential_sha = compute_sha256_file(potential_dst)
    else:
        pytest.skip("EAM potential file not found")
    
    # Create calculation
    calc_resolved = QVService(project_root).project.init_calculation(
        name="chain_workflow",
        structure_selector=structure_ulid,
    )
    calc_id = calc_resolved.meta.ulid
    calc_dir = calc_resolved.absolute_path
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
    # LAMMPS doesn't need species_map, but set empty dict to avoid validation errors
    calc_model.species_map = {}
    calc_model.potential_map = {
        "eam_cu": {
            "style": "eam",
            "file": "potentials/Cu_u3.eam",
            "elements": ["Cu"],
            "sha256": potential_sha,
        }
    }
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)
    
    # Create steps using domain API
    svc = QVService(project_root)

    # Create relax step
    relax_step = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type_gen="relax",
    )
    relax_step_id = relax_step.step_ulid

    # Note: LAMMPS parameters go inside "parameters" dict
    svc.calculation.update_step_params(
        calc_selector=calc_id,
        step_selector=relax_step_id,
        params={
            "parameters": {
                "potential": "eam_cu",
                "units": "metal",
                "atom_style": "atomic",
                "energy_tolerance": 1e-4,
                "force_tolerance": 1e-6,
                "thermo_frequency": 100,
                "dump_frequency": 1000,
                "dump_trajectory": True,
            },
        },
    )

    # Create first MD step (restart_from relax)
    md_step = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type_gen="md",
    )
    md_step_id = md_step.step_ulid

    svc.calculation.update_step_params(
        calc_selector=calc_id,
        step_selector=md_step_id,
        params={
            "parameters": {
                "potential": "eam_cu",
                "restart_from": relax_step_id,  # Use final.data from relax
                "units": "metal",
                "atom_style": "atomic",
                "ensemble": "nvt",
                "temperature": 300,
                "n_steps": 1000,
                "thermo_frequency": 100,
                "dump_frequency": 100,
                "dump_trajectory": True,
            },
        },
    )

    # Create second MD step (restart_from first MD)
    continue_md = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type_gen="md",
    )
    continue_md_id = continue_md.step_ulid
    
    # ========== ULID UNIQUENESS ASSERTIONS (detect Ubuntu CI root cause) ==========
    # These assertions fail-fast if ULID collision occurs or if restart_from is misconfigured
    assert relax_step_id != md_step_id, (
        f"ULID COLLISION: relax_step_id == md_step_id ({relax_step_id}). "
        f"This indicates ULID generator malfunction."
    )
    assert md_step_id != continue_md_id, (
        f"ULID COLLISION: md_step_id == continue_md_id ({md_step_id}). "
        f"This indicates ULID generator malfunction."
    )
    assert relax_step_id != continue_md_id, (
        f"ULID COLLISION: relax_step_id == continue_md_id ({relax_step_id}). "
        f"This indicates ULID generator malfunction."
    )
    # ========== END ULID ASSERTIONS ==========
    
    svc.calculation.update_step_params(
        calc_selector=calc_id,
        step_selector=continue_md_id,
        params={
            "parameters": {
                "potential": "eam_cu",
                "restart_from": md_step_id,  # Use restart.bin from first MD
                "units": "metal",
                "atom_style": "atomic",
                "ensemble": "nvt",
                "temperature": 300,
                "n_steps": 1000,
                "thermo_frequency": 100,
                "dump_frequency": 100,
                "dump_trajectory": True,
            },
        },
    )

    # ========== RESTART_FROM VERIFICATION ==========
    # Verify restart_from was correctly set to upstream step (not self-reference)
    import yaml
    # Construct step path from calc_dir and step slug
    steps_dir = calc_dir / "steps"
    continue_md_step_path = steps_dir / f"{continue_md.meta.slug}.step.yaml"
    with open(continue_md_step_path) as f:
        continue_md_data = yaml.safe_load(f)
    continue_md_restart_from = continue_md_data.get("parameters", {}).get("restart_from")
    
    assert continue_md_restart_from is not None, (
        f"restart_from not set in step.yaml after configure_step"
    )
    assert continue_md_restart_from != continue_md_id, (
        f"[SELF-REFERENCE BUG] restart_from == continue_md_id ({continue_md_id}). "
        f"This is the root cause of 'No restart artifact found' errors. "
        f"Expected restart_from={md_step_id}"
    )
    assert continue_md_restart_from == md_step_id, (
        f"restart_from MISMATCH: got {continue_md_restart_from}, expected {md_step_id}"
    )
    # ========== END RESTART_FROM VERIFICATION ==========
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
        "relax_step_id": relax_step_id,
        "md_step_id": md_step_id,
        "continue_md_id": continue_md_id,
    }


@pytest.mark.requires_lammps
def test_chain_workflow(chain_project):
    """Test chain workflow (relax → MD → restart) end-to-end."""
    project_root = chain_project["project_root"]
    calc_dir = chain_project["calc_dir"]
    
    # Load and run
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    # Debug output if calculation failed
    if result.status.value != "success":
        print(f"[LAMMPS-DEBUG] test_chain_workflow: Calculation FAILED")
        print(f"[LAMMPS-DEBUG] test_chain_workflow: calc_dir={calc_dir}")
        print(f"[LAMMPS-DEBUG] test_chain_workflow: raw_dir={calculation.raw_dir}")
        if result.steps:
            print(f"[LAMMPS-DEBUG] test_chain_workflow: last step message: {result.steps[-1].message}")
            for i, step_summary in enumerate(result.steps):
                step_ulid = step_summary.step_ulid if hasattr(step_summary, 'step_id') else f"step_{i}"
                step_dir = calculation.raw_dir / step_ulid
                print(f"[LAMMPS-DEBUG] test_chain_workflow: step {i} (ulid={step_ulid}):")
                print(f"  status={step_summary.status if hasattr(step_summary, 'status') else 'unknown'}")
                print(f"  dir={step_dir}, exists={step_dir.exists()}")
                if step_dir.exists():
                    files = list(step_dir.iterdir())
                    print(f"  files ({len(files)}): {[f.name for f in files[:20]]}")
                    log_file = step_dir / "log.lammps"
                    if log_file.exists():
                        try:
                            log_lines = log_file.read_text().splitlines()
                            print(f"  log.lammps last 50 lines:")
                            for line in log_lines[-50:]:
                                print(f"    {line}")
                        except Exception as e:
                            print(f"  log.lammps read failed: {e}")
    
    assert result.status.value == "success", f"Calculation failed: {result.steps[-1].message if result.steps else 'Unknown error'}"
    
    # Verify all steps completed
    assert len(result.steps) == 3, "Should have 3 steps"
    
    # Verify restart artifacts exist
    relax_dir = calculation.raw_dir / calculation.steps[0].meta.ulid
    md_dir = calculation.raw_dir / calculation.steps[1].meta.ulid
    
    if not (relax_dir / "final.data").exists():
        print(f"[LAMMPS-DEBUG] test_chain_workflow: final.data missing in {relax_dir}")
        if relax_dir.exists():
            print(f"[LAMMPS-DEBUG] test_chain_workflow: relax_dir contents: {[f.name for f in relax_dir.iterdir()]}")
    assert (relax_dir / "final.data").exists(), "Relax should produce final.data"
    
    if not ((md_dir / "restart.bin").exists() or (md_dir / "restart.final.bin").exists()):
        print(f"[LAMMPS-DEBUG] test_chain_workflow: restart.bin missing in {md_dir}")
        if md_dir.exists():
            print(f"[LAMMPS-DEBUG] test_chain_workflow: md_dir contents: {[f.name for f in md_dir.iterdir()]}")
            restart_files = list(md_dir.glob("restart*"))
            print(f"[LAMMPS-DEBUG] test_chain_workflow: restart* files: {[f.name for f in restart_files]}")
    assert (md_dir / "restart.bin").exists() or (md_dir / "restart.final.bin").exists(), "MD should produce restart file"
    
    print("✓ Chain workflow completed successfully")
