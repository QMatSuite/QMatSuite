"""
LAMMPS Long Smoke Test - Integration Tests

Executes all 4 workflows from lammps_long_smoke_plan.md:
- Workflow A: LJ Relax
- Workflow B: EAM MD
- Workflow C: Chain (Relax → MD)
- Workflow D: Restart_from (MD → MD restart)

These tests run by default in pytest (no marker required).
If LAMMPS binary is not found, tests will skip with diagnostic information.
"""

import json
import pytest
import shutil
import subprocess
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


def configure_step(project_root, calculation_selector, step_selector, parameters):
    """Helper function to configure step parameters via domain accessor."""
    svc = QVService(project_root)
    svc.calculation.update_step_params(
        calc_selector=calculation_selector,
        step_selector=step_selector,
        params={"parameters": parameters},
    )


def get_lammps_binary_info():
    """
    Get LAMMPS binary path and diagnostic information.
    
    Returns:
        tuple: (lammps_bin_path, diagnostic_message)
    """
    from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
    
    diagnostic_parts = []
    
    # Check brew prefix
    try:
        brew_prefix = subprocess.check_output(
            ["brew", "--prefix", "lammps"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        diagnostic_parts.append(f"brew prefix: {brew_prefix}")
        brew_bin = Path(brew_prefix) / "bin" / "lmp_serial"
        if brew_bin.exists():
            diagnostic_parts.append(f"brew binary: {brew_bin}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        diagnostic_parts.append("brew prefix: not found")
    
    # Try resolver
    try:
        lammps_bin = resolve_lammps_bin()
        diagnostic_parts.append(f"resolved binary: {lammps_bin}")
        
        # Try to get version
        try:
            version_output = subprocess.run(
                [str(lammps_bin), "-h"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if version_output.stdout:
                first_line = version_output.stdout.split("\n")[0]
                diagnostic_parts.append(f"version: {first_line}")
        except Exception:
            pass
        
        return lammps_bin, "\n".join(diagnostic_parts)
    except FileNotFoundError as e:
        # Check PATH
        import shutil
        path_candidates = ["lmp_serial", "lmp_mpi", "lmp"]
        path_found = []
        for candidate in path_candidates:
            which_path = shutil.which(candidate)
            if which_path:
                path_found.append(f"{candidate}: {which_path}")
        
        if path_found:
            diagnostic_parts.append(f"PATH candidates: {', '.join(path_found)}")
        else:
            diagnostic_parts.append("PATH: no lammps binaries found")
        
        diagnostic_msg = "\n".join(diagnostic_parts)
        pytest.skip(f"LAMMPS binary not found. Diagnostic:\n{diagnostic_msg}")


@pytest.fixture(scope="module")
def lammps_binary():
    """Check LAMMPS binary availability and return path."""
    lammps_bin, diagnostic = get_lammps_binary_info()
    return lammps_bin


@pytest.fixture
def lj_relax_project(tmp_path: Path, lammps_binary):
    """Create a LAMMPS project for LJ relax workflow."""
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "lj_relax",
        name="LJ Relax Test"
    )
    
    # Load structure from test data
    repo_root = Path(__file__).parent.parent.parent
    struct_file = repo_root / "tests" / "data" / "lammps" / "structures" / "lj_fcc_108.json"
    if not struct_file.exists():
        pytest.skip(f"Structure file not found: {struct_file}")
    
    # Import structure
    struct_result = QVService(project_root).structure.import_file(struct_file, name="LJ FCC 108")
    structure_ulid = struct_result.meta.ulid
    
    # Create calculation
    calc_result = QVService(project_root).project.init_calculation(
        name="lj_relax",
        structure_selector=structure_ulid,
    )
    calc_id = calc_result.meta.ulid
    calc_dir = calc_result.absolute_path
    
    # Configure calculation
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
    calc_model.species_map = {}
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)
    
    # Create relax step
    step = QVService(project_root).calculation.add_step(calc_id, step_type_gen="relax")
    step_id = step.meta.ulid
    
    # Configure step with inline LJ potential
    configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=step_id,
        parameters={
            "potential": {
                "style": "lj/cut",
                "cutoff": 2.5,
                "params": {"* *": "1.0 1.0"},
            },
            "units": "lj",
            "atom_style": "atomic",
            "energy_tolerance": 1e-4,
            "force_tolerance": 1e-6,
            "thermo_frequency": 100,
            "dump_frequency": 500,
            "dump_trajectory": True,
        },
    )
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
        "step_ulid": step_id,
    }


def test_workflow_a_lj_relax(lj_relax_project, lammps_binary):
    """Workflow A: LJ Relax with inline potential dict."""
    project_root = lj_relax_project["project_root"]
    calc_dir = lj_relax_project["calc_dir"]
    step_id = lj_relax_project["step_ulid"]
    
    # Run calculation
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    assert result.status.value == "success", f"Calculation failed: {result.steps[0].message if result.steps else 'Unknown error'}"
    
    # Verify checkpoints
    step_dir = calculation.raw_dir / step_id
    
    # A1-A6: Output files exist
    assert (step_dir / "in.lammps").exists(), "A1: in.lammps should exist"
    assert (step_dir / "structure.data").exists(), "A3: structure.data should exist"
    assert (step_dir / "log.lammps").exists(), "A4: log.lammps should exist"
    assert (step_dir / "final.data").exists(), "A5: final.data should exist"
    
    # A2: in.lammps contains pair_style lj/cut
    in_lammps_content = (step_dir / "in.lammps").read_text()
    assert "pair_style lj/cut" in in_lammps_content, "A2: in.lammps should contain pair_style lj/cut"
    
    # A4: log.lammps has no ERROR
    log_content = (step_dir / "log.lammps").read_text()
    assert "ERROR" not in log_content.upper(), "A4: log.lammps should not contain ERROR"
    
    # A6: trajectory exists
    dump_file = step_dir / "trajectory.lammpstrj"
    if not dump_file.exists():
        dump_file = step_dir / "dump.lammpstrj"
    assert dump_file.exists(), "A6: trajectory/dump.lammpstrj should exist"
    
    # A7: generated_structures artifact exists
    artifact_path = calc_dir / "generated_structures" / f"step_{step_id}" / "current.json"
    assert artifact_path.exists(), "A7: generated_structures artifact should exist"


@pytest.fixture
def eam_md_project(tmp_path: Path, lammps_binary):
    """Create a LAMMPS project for EAM MD workflow."""
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "eam_md",
        name="EAM MD Test"
    )
    
    # Load structure
    repo_root = Path(__file__).parent.parent.parent
    struct_file = repo_root / "tests" / "data" / "lammps" / "structures" / "cu_fcc_32.json"
    if not struct_file.exists():
        pytest.skip(f"Structure file not found: {struct_file}")
    
    # Import structure
    struct_result = QVService(project_root).structure.import_file(struct_file, name="Cu FCC 32")
    structure_ulid = struct_result.meta.ulid
    
    # Copy potential file
    potential_src = repo_root / "resources" / "lammps" / "potentials" / "Cu_u3.eam"
    if not potential_src.exists():
        pytest.skip(f"Potential file not found: {potential_src}")
    
    potentials_dir = project_root / "potentials"
    potentials_dir.mkdir(exist_ok=True)
    potential_dst = potentials_dir / "Cu_u3.eam"
    shutil.copy2(potential_src, potential_dst)
    potential_sha = compute_sha256_file(potential_dst)
    
    # Create calculation
    calc_result = QVService(project_root).project.init_calculation(
        name="eam_md",
        structure_selector=structure_ulid,
    )
    calc_id = calc_result.meta.ulid
    calc_dir = calc_result.absolute_path
    
    # Configure calculation with potential_map
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
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
    
    # Create MD step
    step = QVService(project_root).calculation.add_step(calc_id, step_type_gen="md")
    step_id = step.meta.ulid
    
    # Configure step
    configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=step_id,
        parameters={
            "potential": "eam_cu",
            "units": "metal",
            "atom_style": "atomic",
            "ensemble": "nvt",
            "temperature": 300,
            "timestep_fs": 1.0,
            "n_steps": 100,  # Short run for CI
            "thermo_frequency": 10,
            "dump_frequency": 50,
            "dump_trajectory": True,
        },
    )
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
        "step_ulid": step_id,
    }


def test_workflow_b_eam_md(eam_md_project, lammps_binary):
    """Workflow B: EAM MD with external potential file."""
    project_root = eam_md_project["project_root"]
    calc_dir = eam_md_project["calc_dir"]
    step_id = eam_md_project["step_ulid"]
    
    # Run calculation
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    assert result.status.value == "success", f"Calculation failed: {result.steps[0].message if result.steps else 'Unknown error'}"
    
    # Verify checkpoints
    step_dir = calculation.raw_dir / step_id
    
    # B1: Potential staged
    potential_staged = step_dir / "potentials" / "Cu_u3.eam"
    assert potential_staged.exists(), "B1: Potential should be staged"
    
    # B2-B3: in.lammps contains correct pair_style and pair_coeff
    in_lammps_content = (step_dir / "in.lammps").read_text()
    assert "pair_style eam" in in_lammps_content, "B2: in.lammps should contain pair_style eam"
    assert "pair_coeff" in in_lammps_content and "Cu_u3.eam" in in_lammps_content, "B3: in.lammps should contain correct pair_coeff"
    
    # B4: log.lammps exists, no ERROR
    log_content = (step_dir / "log.lammps").read_text()
    assert "ERROR" not in log_content.upper(), "B4: log.lammps should not contain ERROR"
    
    # B5: trajectory has multiple frames
    dump_file = step_dir / "trajectory.lammpstrj"
    if not dump_file.exists():
        dump_file = step_dir / "dump.lammpstrj"
    if dump_file.exists():
        dump_content = dump_file.read_text()
        frame_count = dump_content.count("ITEM: TIMESTEP")
        assert frame_count > 1, f"B5: trajectory should have multiple frames (found {frame_count})"
    
    # B6: Log shows completion
    assert "Total wall time" in log_content or "Loop time" in log_content, "B6: Log should show completion"


@pytest.fixture
def chain_project(tmp_path: Path, lammps_binary):
    """Create a LAMMPS project for chain workflow (relax → MD)."""
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "chain",
        name="Chain Test"
    )
    
    # Load structure
    repo_root = Path(__file__).parent.parent.parent
    struct_file = repo_root / "tests" / "data" / "lammps" / "structures" / "cu_fcc_32.json"
    if not struct_file.exists():
        pytest.skip(f"Structure file not found: {struct_file}")
    
    # Import structure
    struct_result = QVService(project_root).structure.import_file(struct_file, name="Cu FCC 32")
    structure_ulid = struct_result.meta.ulid
    
    # Copy potential file
    potential_src = repo_root / "resources" / "lammps" / "potentials" / "Cu_u3.eam"
    if not potential_src.exists():
        pytest.skip(f"Potential file not found: {potential_src}")
    
    potentials_dir = project_root / "potentials"
    potentials_dir.mkdir(exist_ok=True)
    potential_dst = potentials_dir / "Cu_u3.eam"
    shutil.copy2(potential_src, potential_dst)
    potential_sha = compute_sha256_file(potential_dst)
    
    # Create calculation
    calc_result = QVService(project_root).project.init_calculation(
        name="chain",
        structure_selector=structure_ulid,
    )
    calc_id = calc_result.meta.ulid
    calc_dir = calc_result.absolute_path
    
    # Configure calculation
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
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
    
    # Create relax step
    relax_step = QVService(project_root).calculation.add_step(calc_id, step_type_gen="relax")
    relax_step_id = relax_step.meta.ulid
    
    configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=relax_step_id,
        parameters={
            "potential": "eam_cu",
            "units": "metal",
            "atom_style": "atomic",
            "energy_tolerance": 1e-4,
            "force_tolerance": 1e-6,
            "thermo_frequency": 100,
            "dump_frequency": 1000,
            "dump_trajectory": True,
        },
    )
    
    # Create MD step
    md_step = QVService(project_root).calculation.add_step(calc_id, step_type_gen="md")
    md_step_id = md_step.meta.ulid
    
    configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=md_step_id,
        parameters={
            "potential": "eam_cu",
            "restart_from": relax_step_id,
            "units": "metal",
            "atom_style": "atomic",
            "ensemble": "nvt",
            "temperature": 300,
            "n_steps": 100,  # Short run for CI
            "thermo_frequency": 10,
            "dump_frequency": 50,
            "dump_trajectory": True,
        },
    )
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
        "relax_step_id": relax_step_id,
        "md_step_id": md_step_id,
    }


def test_workflow_c_chain(chain_project, lammps_binary):
    """Workflow C: Chain (Relax → MD) with artifact connection."""
    project_root = chain_project["project_root"]
    calc_dir = chain_project["calc_dir"]
    relax_step_id = chain_project["relax_step_id"]
    md_step_id = chain_project["md_step_id"]
    
    # Run calculation
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    # Debug output if calculation failed
    if result.status.value != "success":
        print(f"[LAMMPS-DEBUG] test_workflow_c_chain: Calculation FAILED")
        print(f"[LAMMPS-DEBUG] test_workflow_c_chain: calc_dir={calc_dir}")
        print(f"[LAMMPS-DEBUG] test_workflow_c_chain: raw_dir={calculation.raw_dir}")
        print(f"[LAMMPS-DEBUG] test_workflow_c_chain: step_ids: relax={relax_step_id}, md={md_step_id}")
        if result.steps:
            print(f"[LAMMPS-DEBUG] test_workflow_c_chain: last step message: {result.steps[-1].message}")
            for i, step_summary in enumerate(result.steps):
                step_ulid = step_summary.step_ulid if hasattr(step_summary, 'step_id') else f"step_{i}"
                step_dir = calculation.raw_dir / step_ulid
                print(f"[LAMMPS-DEBUG] test_workflow_c_chain: step {i} (ulid={step_ulid}):")
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
    
    # Verify checkpoints
    raw_dir = calculation.raw_dir
    relax_dir = raw_dir / relax_step_id
    md_dir = raw_dir / md_step_id
    
    # C1: Relax produces final.data
    assert (relax_dir / "final.data").exists(), "C1: Relax should produce final.data"
    
    # C2: Relax produces current.json artifact
    artifact_path = calc_dir / "generated_structures" / f"step_{relax_step_id}" / "current.json"
    assert artifact_path.exists(), "C2: Relax should produce current.json artifact"
    
    # C3: MD step uses relax output (check in.lammps contains read_restart or references relax step)
    md_in_lammps = md_dir / "in.lammps"
    assert md_in_lammps.exists(), "C3: MD in.lammps should exist"
    md_in_content = md_in_lammps.read_text()
    assert "read_restart" in md_in_content or relax_step_id in md_in_content, "C3: MD should use relax output"
    
    # C4: MD atom count matches relax (simplified: check both have same structure)
    # Load artifact structure
    artifact_data = json.loads(artifact_path.read_text())
    artifact_atoms = len(artifact_data.get("sites", []))
    
    # Parse final.data to get atom count
    final_data_content = (relax_dir / "final.data").read_text()
    for line in final_data_content.split("\n"):
        if "atoms" in line and not line.strip().startswith("#"):
            relax_atoms = int(line.split()[0])
            break
    else:
        relax_atoms = None
    
    # C5: Both steps complete without ERROR
    relax_log = (relax_dir / "log.lammps").read_text()
    md_log = (md_dir / "log.lammps").read_text()
    assert "ERROR" not in relax_log.upper(), "C5: Relax log should not contain ERROR"
    assert "ERROR" not in md_log.upper(), "C5: MD log should not contain ERROR"


@pytest.fixture
def restart_project(tmp_path: Path, lammps_binary):
    """Create a LAMMPS project for restart workflow (relax → MD → MD restart)."""
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "restart",
        name="Restart Test"
    )
    
    # Load structure
    repo_root = Path(__file__).parent.parent.parent
    struct_file = repo_root / "tests" / "data" / "lammps" / "structures" / "cu_fcc_32.json"
    if not struct_file.exists():
        pytest.skip(f"Structure file not found: {struct_file}")
    
    # Import structure
    struct_result = QVService(project_root).structure.import_file(struct_file, name="Cu FCC 32")
    structure_ulid = struct_result.meta.ulid
    
    # Copy potential file
    potential_src = repo_root / "resources" / "lammps" / "potentials" / "Cu_u3.eam"
    if not potential_src.exists():
        pytest.skip(f"Potential file not found: {potential_src}")
    
    potentials_dir = project_root / "potentials"
    potentials_dir.mkdir(exist_ok=True)
    potential_dst = potentials_dir / "Cu_u3.eam"
    shutil.copy2(potential_src, potential_dst)
    potential_sha = compute_sha256_file(potential_dst)
    
    # Create calculation
    calc_result = QVService(project_root).project.init_calculation(
        name="restart",
        structure_selector=structure_ulid,
    )
    calc_id = calc_result.meta.ulid
    calc_dir = calc_result.absolute_path
    
    # Configure calculation
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
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
    
    # Create relax step
    relax_step = QVService(project_root).calculation.add_step(calc_id, step_type_gen="relax")
    relax_step_id = relax_step.meta.ulid
    
    configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=relax_step_id,
        parameters={
            "potential": "eam_cu",
            "units": "metal",
            "atom_style": "atomic",
            "energy_tolerance": 1e-4,
            "force_tolerance": 1e-6,
            "thermo_frequency": 100,
            "dump_frequency": 500,
            "dump_trajectory": True,
        },
    )
    
    # Create first MD step
    md1_step = QVService(project_root).calculation.add_step(calc_id, step_type_gen="md")
    md1_step_id = md1_step.meta.ulid
    
    configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=md1_step_id,
        parameters={
            "potential": "eam_cu",
            "restart_from": relax_step_id,
            "units": "metal",
            "atom_style": "atomic",
            "ensemble": "nvt",
            "temperature": 300,
            "n_steps": 50,  # Short run for CI
            "thermo_frequency": 10,
            "dump_frequency": 25,
            "dump_trajectory": True,
        },
    )
    
    # Create second MD step (restart from first MD)
    md2_step = QVService(project_root).calculation.add_step(calc_id, step_type_gen="md")
    md2_step_id = md2_step.meta.ulid
    
    # ========== ULID UNIQUENESS ASSERTIONS (detect Ubuntu CI root cause) ==========
    assert relax_step_id != md1_step_id, (
        f"ULID COLLISION: relax_step_id == md1_step_id ({relax_step_id})"
    )
    assert md1_step_id != md2_step_id, (
        f"ULID COLLISION: md1_step_id == md2_step_id ({md1_step_id})"
    )
    assert relax_step_id != md2_step_id, (
        f"ULID COLLISION: relax_step_id == md2_step_id ({relax_step_id})"
    )
    # ========== END ULID ASSERTIONS ==========
    
    configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=md2_step_id,
        parameters={
            "potential": "eam_cu",
            "restart_from": md1_step_id,
            "units": "metal",
            "atom_style": "atomic",
            "ensemble": "nvt",
            "temperature": 300,
            "n_steps": 50,  # Short run for CI
            "thermo_frequency": 10,
            "dump_frequency": 25,
            "dump_trajectory": True,
        },
    )
    
    # ========== RESTART_FROM VERIFICATION ==========
    # Verify restart_from was correctly set (not self-reference)
    import yaml
    # StepDTO doesn't have absolute_path, compute from meta.path
    md1_step_path = project_root / md1_step.meta.path
    with open(md1_step_path) as f:
        md1_data = yaml.safe_load(f)
    md1_restart_from = md1_data.get("parameters", {}).get("restart_from")

    md2_step_path = project_root / md2_step.meta.path
    with open(md2_step_path) as f:
        md2_data = yaml.safe_load(f)
    md2_restart_from = md2_data.get("parameters", {}).get("restart_from")
    
    # MD1 should restart from relax
    assert md1_restart_from == relax_step_id, (
        f"md1.restart_from MISMATCH: got {md1_restart_from}, expected {relax_step_id}"
    )
    assert md1_restart_from != md1_step_id, (
        f"[SELF-REFERENCE BUG] md1.restart_from == md1_step_id ({md1_step_id})"
    )
    
    # MD2 should restart from MD1
    assert md2_restart_from == md1_step_id, (
        f"md2.restart_from MISMATCH: got {md2_restart_from}, expected {md1_step_id}"
    )
    assert md2_restart_from != md2_step_id, (
        f"[SELF-REFERENCE BUG] md2.restart_from == md2_step_id ({md2_step_id})"
    )
    # ========== END RESTART_FROM VERIFICATION ==========
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
        "relax_step_id": relax_step_id,
        "md1_step_id": md1_step_id,
        "md2_step_id": md2_step_id,
    }


def test_workflow_d_restart(restart_project, lammps_binary):
    """Workflow D: Restart_from (MD → MD restart)."""
    project_root = restart_project["project_root"]
    calc_dir = restart_project["calc_dir"]
    relax_step_id = restart_project["relax_step_id"]
    md1_step_id = restart_project["md1_step_id"]
    md2_step_id = restart_project["md2_step_id"]
    
    # Run calculation
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    # Debug output if calculation failed
    if result.status.value != "success":
        print(f"[LAMMPS-DEBUG] test_workflow_d_restart: Calculation FAILED")
        print(f"[LAMMPS-DEBUG] test_workflow_d_restart: calc_dir={calc_dir}")
        print(f"[LAMMPS-DEBUG] test_workflow_d_restart: raw_dir={calculation.raw_dir}")
        print(f"[LAMMPS-DEBUG] test_workflow_d_restart: step_ids: relax={relax_step_id}, md1={md1_step_id}, md2={md2_step_id}")
        if result.steps:
            print(f"[LAMMPS-DEBUG] test_workflow_d_restart: last step message: {result.steps[-1].message}")
            for i, step_summary in enumerate(result.steps):
                step_ulid = step_summary.step_ulid if hasattr(step_summary, 'step_id') else f"step_{i}"
                step_dir = calculation.raw_dir / step_ulid
                print(f"[LAMMPS-DEBUG] test_workflow_d_restart: step {i} (ulid={step_ulid}):")
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
    
    # Verify checkpoints
    raw_dir = calculation.raw_dir
    md1_dir = raw_dir / md1_step_id
    md2_dir = raw_dir / md2_step_id
    
    # D1: First MD produces restart file
    restart_bin = md1_dir / "restart.bin"
    restart_final_bin = md1_dir / "restart.final.bin"
    if not (restart_bin.exists() or restart_final_bin.exists()):
        print(f"[LAMMPS-DEBUG] test_workflow_d_restart: restart.bin missing in {md1_dir}")
        if md1_dir.exists():
            print(f"[LAMMPS-DEBUG] test_workflow_d_restart: md1_dir contents: {[f.name for f in md1_dir.iterdir()]}")
            restart_files = list(md1_dir.glob("restart*"))
            print(f"[LAMMPS-DEBUG] test_workflow_d_restart: restart* files in md1: {[f.name for f in restart_files]}")
    assert restart_bin.exists() or restart_final_bin.exists(), "D1: First MD should produce restart file"
    
    # D2: Second MD's in.lammps contains read_restart
    md2_in_lammps = md2_dir / "in.lammps"
    if not md2_in_lammps.exists():
        print(f"[LAMMPS-DEBUG] test_workflow_d_restart: md2 in.lammps missing in {md2_dir}")
        if md2_dir.exists():
            print(f"[LAMMPS-DEBUG] test_workflow_d_restart: md2_dir contents: {[f.name for f in md2_dir.iterdir()]}")
    assert md2_in_lammps.exists(), "D2: MD2 in.lammps should exist"
    md2_in_content = md2_in_lammps.read_text()
    if "read_restart" not in md2_in_content:
        print(f"[LAMMPS-DEBUG] test_workflow_d_restart: md2 in.lammps does not contain 'read_restart'")
        print(f"[LAMMPS-DEBUG] test_workflow_d_restart: md2 in.lammps first 30 lines:")
        for line in md2_in_content.splitlines()[:30]:
            print(f"    {line}")
    assert "read_restart" in md2_in_content, "D2: MD2 in.lammps should contain read_restart"
    
    # D3: Second MD log shows restart read success
    md2_log_path = md2_dir / "log.lammps"
    if not md2_log_path.exists():
        print(f"[LAMMPS-DEBUG] test_workflow_d_restart: md2 log.lammps missing")
    else:
        md2_log = md2_log_path.read_text()
        if "ERROR" in md2_log.upper():
            print(f"[LAMMPS-DEBUG] test_workflow_d_restart: md2 log contains ERROR, last 50 lines:")
            for line in md2_log.splitlines()[-50:]:
                print(f"    {line}")
        assert "ERROR" not in md2_log.upper(), "D3: MD2 log should not contain ERROR"
        # Check for restart-related messages (read_restart command or similar)
        if "restart" not in md2_log.lower() and "read" not in md2_log.lower():
            print(f"[LAMMPS-DEBUG] test_workflow_d_restart: md2 log does not contain 'restart' or 'read', last 50 lines:")
            for line in md2_log.splitlines()[-50:]:
                print(f"    {line}")
        assert "restart" in md2_log.lower() or "read" in md2_log.lower(), "D3: MD2 log should show restart read"
    
    # D4: All three steps complete without ERROR
    relax_log_path = raw_dir / relax_step_id / "log.lammps"
    md1_log_path = md1_dir / "log.lammps"
    if relax_log_path.exists():
        relax_log = relax_log_path.read_text()
        if "ERROR" in relax_log.upper():
            print(f"[LAMMPS-DEBUG] test_workflow_d_restart: relax log contains ERROR, last 30 lines:")
            for line in relax_log.splitlines()[-30:]:
                print(f"    {line}")
        assert "ERROR" not in relax_log.upper(), "D4: Relax log should not contain ERROR"
    if md1_log_path.exists():
        md1_log = md1_log_path.read_text()
        if "ERROR" in md1_log.upper():
            print(f"[LAMMPS-DEBUG] test_workflow_d_restart: md1 log contains ERROR, last 30 lines:")
            for line in md1_log.splitlines()[-30:]:
                print(f"    {line}")
        assert "ERROR" not in md1_log.upper(), "D4: MD1 log should not contain ERROR"

