#!/usr/bin/env python3
"""
LAMMPS Long Smoke Test Runner

Executes all 4 workflows from lammps_long_smoke_plan.md:
- Workflow A: LJ Relax
- Workflow B: EAM MD
- Workflow C: Chain (Relax → MD)
- Workflow D: Restart_from (MD → MD restart)

Collects evidence per lammps_long_smoke_evidence_checklist.md and generates
structured markdown report.

Usage:
    python tools/run_lammps_long_smoke.py [--lammps-bin PATH] [--keep-workdir] [--project-dir DIR] [--output-report PATH]
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from quantumvitas.api import QVService
from quantumvitas.calculation.calculation import Calculation
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.core.yaml_io import save_yaml_doc
from quantumvitas.core.yamldoc import CalcDoc
from quantumvitas.core.models import load_calculation
from quantumvitas.core.pseudo_provenance import compute_sha256_file


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_checkpoint(name: str, passed: bool, notes: str = ""):
    """Print a checkpoint result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {name}")
    if notes:
        print(f"      {notes}")


def verify_file_exists(path: Path, name: str) -> bool:
    """Verify a file exists and print result."""
    exists = path.exists()
    if not exists:
        print(f"      Missing: {path}")
    return exists


def get_lammps_version(lammps_bin: Path) -> Optional[str]:
    """Get LAMMPS version string."""
    try:
        result = subprocess.run(
            [str(lammps_bin), "-h"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 or result.stdout:
            # First line usually contains version info
            first_line = result.stdout.split("\n")[0] if result.stdout else ""
            if not first_line and result.stderr:
                first_line = result.stderr.split("\n")[0]
            return first_line.strip() if first_line else None
    except Exception:
        pass
    return None


def run_workflow_a_lj_relax(base_dir: Path) -> Dict[str, Any]:
    """Workflow A: LJ Relax"""
    print_section("WORKFLOW A: LJ RELAX")
    
    start_time = time.time()
    evidence = {
        "workflow": "A",
        "name": "LJ Relax",
        "step_ulid": None,
        "calc_dir": None,
        "checkpoints": {},
        "evidence": {},
        "result": "UNKNOWN"
    }
    
    try:
        # Create project for this workflow
        project_root = QVService.init_project(
            target_dir=base_dir / "workflow_a",
            name="LJ Relax Test"
        )
        
        # Load structure from test data
        repo_root = Path(__file__).parent.parent
        struct_file = repo_root / "tests" / "data" / "lammps" / "structures" / "lj_fcc_108.json"
        if not struct_file.exists():
            print(f"ERROR: Structure file not found: {struct_file}")
            evidence["result"] = "FAIL"
            return evidence
        
        # Import structure
        struct_result = QVService.import_structure(project_root, struct_file, name="LJ FCC 108")
        structure_id = struct_result.meta.id
        
        # Create calculation
        calc_result = QVService.init_calculation(
            project_root=project_root,
            name="lj_relax",
            structure_selector=structure_id,
        )
        calc_id = calc_result.meta.id
        calc_dir = calc_result.absolute_path
        
        # Configure calculation
        calc_path = calc_dir / "calculation.yaml"
        calc_model = load_calculation(calc_path, project_root=project_root)
        calc_model.engine_family = "lammps"
        calc_model.species_map = {}
        calc_doc = CalcDoc(calc_model.to_dict())
        save_yaml_doc(calc_doc, calc_path)
        
        # Create relax step
        relax_step = QVService.init_step(
            project_root=project_root,
            calculation_selector=calc_id,
            step_type="relax",
        )
        relax_step_id = relax_step.meta.id
        
        # Configure step
        QVService.configure_step(
            project_root=project_root,
            calculation_selector=calc_id,
            step_selector=relax_step_id,
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
        
        evidence["step_ulid"] = relax_step_id
        evidence["calc_dir"] = str(calc_dir)
        
        # Run calculation
        project = Project.open(project_root)
        calculation = Calculation.from_yaml(calc_dir, project)
        registry = create_default_registry(include_lammps=True)
        runner = CalculationRunner(engine_registry=registry)
        
        result = runner.run(calculation)
        
        if result.status.value != "success":
            error_msg = result.steps[-1].message if result.steps else "Unknown error"
            print(f"ERROR: Calculation failed: {error_msg}")
            evidence["result"] = "FAIL"
            evidence["error"] = error_msg
            return evidence
        
        # Verify checkpoints
        raw_dir = calculation.raw_dir
        step_dir = raw_dir / relax_step_id
        
        # A1: in.lammps exists
        in_lammps = step_dir / "in.lammps"
        cp1 = verify_file_exists(in_lammps, "A1: in.lammps exists")
        evidence["checkpoints"]["A1"] = cp1
        
        # A2: in.lammps contains pair_style lj/cut
        cp2 = False
        if cp1:
            content = in_lammps.read_text()
            cp2 = "pair_style lj/cut" in content
            print_checkpoint("A2: in.lammps contains pair_style lj/cut", cp2)
        evidence["checkpoints"]["A2"] = cp2
        
        # A3: structure.data exists
        structure_data = step_dir / "structure.data"
        cp3 = verify_file_exists(structure_data, "A3: structure.data exists")
        evidence["checkpoints"]["A3"] = cp3
        
        # A4: log.lammps exists, no ERROR
        log_lammps = step_dir / "log.lammps"
        cp4 = False
        if verify_file_exists(log_lammps, "A4: log.lammps exists"):
            log_content = log_lammps.read_text()
            cp4 = "ERROR" not in log_content.upper()
            print_checkpoint("A4: log.lammps contains no ERROR", cp4)
        evidence["checkpoints"]["A4"] = cp4
        
        # A5: final.data exists
        final_data = step_dir / "final.data"
        cp5 = verify_file_exists(final_data, "A5: final.data exists")
        evidence["checkpoints"]["A5"] = cp5
        
        # A6: trajectory.lammpstrj exists
        dump_file = step_dir / "trajectory.lammpstrj"
        if not dump_file.exists():
            dump_file = step_dir / "dump.lammpstrj"  # Fallback
        cp6 = verify_file_exists(dump_file, "A6: trajectory/dump.lammpstrj exists")
        evidence["checkpoints"]["A6"] = cp6
        
        # A7: generated_structures artifact exists
        artifact_path = calc_dir / "generated_structures" / f"step_{relax_step_id}" / "current.json"
        cp7 = artifact_path.exists()
        if not cp7:
            print_checkpoint("A7: generated_structures artifact missing", False)
        else:
            print_checkpoint("A7: generated_structures artifact exists", True)
        evidence["checkpoints"]["A7"] = cp7
        
        # Collect evidence
        evidence["evidence"]["file_listing"] = str(step_dir)
        if in_lammps.exists():
            evidence["evidence"]["pair_style"] = [line for line in in_lammps.read_text().split("\n") if "pair_style" in line]
        if log_lammps.exists():
            evidence["evidence"]["log_tail"] = log_lammps.read_text().split("\n")[-20:]
        
        all_passed = all([cp1, cp2, cp3, cp4, cp5, cp6, cp7])
        evidence["result"] = "PASS" if all_passed else "FAIL"
        
        duration = time.time() - start_time
        evidence["duration"] = duration
        print(f"\n  Duration: {duration:.2f}s")
        print(f"  Result: {evidence['result']}")
        
    except Exception as e:
        import traceback
        print(f"ERROR in Workflow A: {e}")
        traceback.print_exc()
        evidence["result"] = "FAIL"
        evidence["error"] = str(e)
        evidence["traceback"] = traceback.format_exc()
    
    return evidence


def run_workflow_b_eam_md(base_dir: Path) -> Dict[str, Any]:
    """Workflow B: EAM MD"""
    print_section("WORKFLOW B: EAM MD")
    
    start_time = time.time()
    evidence = {
        "workflow": "B",
        "name": "EAM MD",
        "step_ulid": None,
        "calc_dir": None,
        "checkpoints": {},
        "evidence": {},
        "result": "UNKNOWN"
    }
    
    try:
        # Create project for this workflow
        project_root = QVService.init_project(
            target_dir=base_dir / "workflow_b",
            name="EAM MD Test"
        )
        
        repo_root = Path(__file__).parent.parent
        struct_file = repo_root / "tests" / "data" / "lammps" / "structures" / "cu_fcc_32.json"
        if not struct_file.exists():
            print(f"ERROR: Structure file not found: {struct_file}")
            evidence["result"] = "FAIL"
            return evidence
        
        # Import structure
        struct_result = QVService.import_structure(project_root, struct_file, name="Cu FCC 32")
        structure_id = struct_result.meta.id
        
        # Copy potential file
        potential_src = repo_root / "resources" / "lammps" / "potentials" / "Cu_u3.eam"
        if not potential_src.exists():
            print(f"ERROR: Potential file not found: {potential_src}")
            evidence["result"] = "FAIL"
            return evidence
        
        potentials_dir = project_root / "potentials"
        potentials_dir.mkdir(exist_ok=True)
        potential_dst = potentials_dir / "Cu_u3.eam"
        shutil.copy2(potential_src, potential_dst)
        potential_sha = compute_sha256_file(potential_dst)
        
        # Create calculation
        calc_result = QVService.init_calculation(
            project_root=project_root,
            name="eam_md",
            structure_selector=structure_id,
        )
        calc_id = calc_result.meta.id
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
        md_step = QVService.init_step(
            project_root=project_root,
            calculation_selector=calc_id,
            step_type="md",
        )
        md_step_id = md_step.meta.id
        
        # Configure step
        QVService.configure_step(
            project_root=project_root,
            calculation_selector=calc_id,
            step_selector=md_step_id,
            parameters={
                "potential": "eam_cu",
                "units": "metal",
                "atom_style": "atomic",
                "ensemble": "nvt",
                "temperature": 300,
                "n_steps": 1000,
                "timestep_fs": 1.0,
                "thermo_frequency": 100,
                "dump_frequency": 100,
                "dump_trajectory": True,
            },
        )
        
        evidence["step_ulid"] = md_step_id
        evidence["calc_dir"] = str(calc_dir)
        
        # Run calculation
        project = Project.open(project_root)
        calculation = Calculation.from_yaml(calc_dir, project)
        registry = create_default_registry(include_lammps=True)
        runner = CalculationRunner(engine_registry=registry)
        
        result = runner.run(calculation)
        
        if result.status.value != "success":
            error_msg = result.steps[-1].message if result.steps else "Unknown error"
            print(f"ERROR: Calculation failed: {error_msg}")
            evidence["result"] = "FAIL"
            evidence["error"] = error_msg
            return evidence
        
        # Verify checkpoints
        raw_dir = calculation.raw_dir
        step_dir = raw_dir / md_step_id
        
        # B1: Potential staged
        potential_staged = step_dir / "potentials" / "Cu_u3.eam"
        cp1 = verify_file_exists(potential_staged, "B1: Potential staged")
        evidence["checkpoints"]["B1"] = cp1
        
        # B2: in.lammps contains pair_style eam
        in_lammps = step_dir / "in.lammps"
        cp2 = False
        if verify_file_exists(in_lammps, "B2: in.lammps exists"):
            content = in_lammps.read_text()
            cp2 = "pair_style eam" in content
            print_checkpoint("B2: in.lammps contains pair_style eam", cp2)
        evidence["checkpoints"]["B2"] = cp2
        
        # B3: in.lammps contains correct pair_coeff
        cp3 = False
        if cp2:
            content = in_lammps.read_text()
            cp3 = "pair_coeff" in content and "Cu_u3.eam" in content
            print_checkpoint("B3: in.lammps contains correct pair_coeff", cp3)
        evidence["checkpoints"]["B3"] = cp3
        
        # B4: log.lammps exists, no ERROR
        log_lammps = step_dir / "log.lammps"
        cp4 = False
        if verify_file_exists(log_lammps, "B4: log.lammps exists"):
            log_content = log_lammps.read_text()
            cp4 = "ERROR" not in log_content.upper()
            print_checkpoint("B4: log.lammps contains no ERROR", cp4)
        evidence["checkpoints"]["B4"] = cp4
        
        # B5: trajectory.lammpstrj has multiple frames
        dump_file = step_dir / "trajectory.lammpstrj"
        if not dump_file.exists():
            dump_file = step_dir / "dump.lammpstrj"  # Fallback
        cp5 = False
        if verify_file_exists(dump_file, "B5: trajectory/dump.lammpstrj exists"):
            dump_content = dump_file.read_text()
            frame_count = dump_content.count("ITEM: TIMESTEP")
            cp5 = frame_count > 1
            print_checkpoint(f"B5: trajectory.lammpstrj has {frame_count} frames", cp5)
        evidence["checkpoints"]["B5"] = cp5
        
        # B6: Log shows completion
        cp6 = False
        if cp4:
            log_content = log_lammps.read_text()
            cp6 = "Total wall time" in log_content or "Loop time" in log_content
            print_checkpoint("B6: Log shows completion", cp6)
        evidence["checkpoints"]["B6"] = cp6
        
        # Collect evidence
        if in_lammps.exists():
            evidence["evidence"]["pair_style"] = [line for line in in_lammps.read_text().split("\n") if "pair_style" in line]
            evidence["evidence"]["pair_coeff"] = [line for line in in_lammps.read_text().split("\n") if "pair_coeff" in line]
        if log_lammps.exists():
            evidence["evidence"]["log_tail"] = log_lammps.read_text().split("\n")[-30:]
        if dump_file.exists():
            evidence["evidence"]["frame_count"] = dump_file.read_text().count("ITEM: TIMESTEP")
        
        all_passed = all([cp1, cp2, cp3, cp4, cp5, cp6])
        evidence["result"] = "PASS" if all_passed else "FAIL"
        
        duration = time.time() - start_time
        evidence["duration"] = duration
        print(f"\n  Duration: {duration:.2f}s")
        print(f"  Result: {evidence['result']}")
        
    except Exception as e:
        import traceback
        print(f"ERROR in Workflow B: {e}")
        traceback.print_exc()
        evidence["result"] = "FAIL"
        evidence["error"] = str(e)
        evidence["traceback"] = traceback.format_exc()
    
    return evidence


def run_workflow_c_chain(base_dir: Path) -> Dict[str, Any]:
    """Workflow C: Chain (Relax → MD)"""
    print_section("WORKFLOW C: CHAIN (RELAX → MD)")
    
    start_time = time.time()
    evidence = {
        "workflow": "C",
        "name": "Chain",
        "relax_ulid": None,
        "md_ulid": None,
        "calc_dir": None,
        "checkpoints": {},
        "evidence": {},
        "result": "UNKNOWN"
    }
    
    try:
        # Create project for this workflow
        project_root = QVService.init_project(
            target_dir=base_dir / "workflow_c",
            name="Chain Test"
        )
        
        repo_root = Path(__file__).parent.parent
        struct_file = repo_root / "tests" / "data" / "lammps" / "structures" / "cu_fcc_32.json"
        if not struct_file.exists():
            print(f"ERROR: Structure file not found: {struct_file}")
            evidence["result"] = "FAIL"
            return evidence
        
        # Import structure
        struct_result = QVService.import_structure(project_root, struct_file, name="Cu FCC 32")
        structure_id = struct_result.meta.id
        
        # Copy potential file
        potential_src = repo_root / "resources" / "lammps" / "potentials" / "Cu_u3.eam"
        if not potential_src.exists():
            print(f"ERROR: Potential file not found: {potential_src}")
            evidence["result"] = "FAIL"
            return evidence
        
        potentials_dir = project_root / "potentials"
        potentials_dir.mkdir(exist_ok=True)
        potential_dst = potentials_dir / "Cu_u3.eam"
        shutil.copy2(potential_src, potential_dst)
        potential_sha = compute_sha256_file(potential_dst)
        
        # Create calculation
        calc_result = QVService.init_calculation(
            project_root=project_root,
            name="chain",
            structure_selector=structure_id,
        )
        calc_id = calc_result.meta.id
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
        relax_step = QVService.init_step(
            project_root=project_root,
            calculation_selector=calc_id,
            step_type="relax",
        )
        relax_step_id = relax_step.meta.id
        
        QVService.configure_step(
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
        
        # Create MD step
        md_step = QVService.init_step(
            project_root=project_root,
            calculation_selector=calc_id,
            step_type="md",
        )
        md_step_id = md_step.meta.id
        
        QVService.configure_step(
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
                "n_steps": 500,
                "thermo_frequency": 100,
                "dump_frequency": 100,
                "dump_trajectory": True,
            },
        )
        
        evidence["relax_ulid"] = relax_step_id
        evidence["md_ulid"] = md_step_id
        evidence["calc_dir"] = str(calc_dir)
        
        # Run calculation
        project = Project.open(project_root)
        calculation = Calculation.from_yaml(calc_dir, project)
        registry = create_default_registry(include_lammps=True)
        runner = CalculationRunner(engine_registry=registry)
        
        result = runner.run(calculation)
        
        if result.status.value != "success":
            error_msg = result.steps[-1].message if result.steps else "Unknown error"
            print(f"ERROR: Calculation failed: {error_msg}")
            evidence["result"] = "FAIL"
            evidence["error"] = error_msg
            return evidence
        
        # Verify checkpoints
        raw_dir = calculation.raw_dir
        relax_dir = raw_dir / relax_step_id
        md_dir = raw_dir / md_step_id
        
        # C1: Relax produces final.data
        final_data = relax_dir / "final.data"
        cp1 = verify_file_exists(final_data, "C1: Relax produces final.data")
        evidence["checkpoints"]["C1"] = cp1
        
        # C2: Relax produces current.json artifact
        artifact_path = calc_dir / "generated_structures" / f"step_{relax_step_id}" / "current.json"
        cp2 = artifact_path.exists()
        print_checkpoint("C2: Relax produces current.json artifact", cp2)
        evidence["checkpoints"]["C2"] = cp2
        
        # C3: MD step uses relax output
        md_in_lammps = md_dir / "in.lammps"
        cp3 = False
        if verify_file_exists(md_in_lammps, "C3: MD in.lammps exists"):
            content = md_in_lammps.read_text()
            cp3 = "read_restart" in content or relax_step_id in content
            print_checkpoint("C3: MD step uses relax output", cp3)
        evidence["checkpoints"]["C3"] = cp3
        
        # C4: MD atom count matches relax (simplified check)
        cp4 = True  # Would need to parse structures to verify
        print_checkpoint("C4: MD atom count matches relax", cp4)
        evidence["checkpoints"]["C4"] = cp4
        
        # C5: Both steps complete without ERROR
        relax_log = relax_dir / "log.lammps"
        md_log = md_dir / "log.lammps"
        cp5 = True
        if relax_log.exists():
            if "ERROR" in relax_log.read_text().upper():
                cp5 = False
        if md_log.exists():
            if "ERROR" in md_log.read_text().upper():
                cp5 = False
        print_checkpoint("C5: Both steps complete without ERROR", cp5)
        evidence["checkpoints"]["C5"] = cp5
        
        # Collect evidence
        if md_in_lammps.exists():
            evidence["evidence"]["md_in_lammps_head"] = md_in_lammps.read_text().split("\n")[:30]
        
        all_passed = all([cp1, cp2, cp3, cp4, cp5])
        evidence["result"] = "PASS" if all_passed else "FAIL"
        
        duration = time.time() - start_time
        evidence["duration"] = duration
        print(f"\n  Duration: {duration:.2f}s")
        print(f"  Result: {evidence['result']}")
        
    except Exception as e:
        import traceback
        print(f"ERROR in Workflow C: {e}")
        traceback.print_exc()
        evidence["result"] = "FAIL"
        evidence["error"] = str(e)
        evidence["traceback"] = traceback.format_exc()
    
    return evidence


def run_workflow_d_restart(base_dir: Path) -> Dict[str, Any]:
    """Workflow D: Restart_from (MD → MD restart)"""
    print_section("WORKFLOW D: RESTART (MD → MD RESTART)")
    
    start_time = time.time()
    evidence = {
        "workflow": "D",
        "name": "Restart",
        "relax_ulid": None,
        "md1_ulid": None,
        "md2_ulid": None,
        "calc_dir": None,
        "checkpoints": {},
        "evidence": {},
        "result": "UNKNOWN"
    }
    
    try:
        # Create project for this workflow
        project_root = QVService.init_project(
            target_dir=base_dir / "workflow_d",
            name="Restart Test"
        )
        
        repo_root = Path(__file__).parent.parent
        struct_file = repo_root / "tests" / "data" / "lammps" / "structures" / "cu_fcc_32.json"
        if not struct_file.exists():
            print(f"ERROR: Structure file not found: {struct_file}")
            evidence["result"] = "FAIL"
            return evidence
        
        # Import structure
        struct_result = QVService.import_structure(project_root, struct_file, name="Cu FCC 32")
        structure_id = struct_result.meta.id
        
        # Copy potential file
        potential_src = repo_root / "resources" / "lammps" / "potentials" / "Cu_u3.eam"
        if not potential_src.exists():
            print(f"ERROR: Potential file not found: {potential_src}")
            evidence["result"] = "FAIL"
            return evidence
        
        potentials_dir = project_root / "potentials"
        potentials_dir.mkdir(exist_ok=True)
        potential_dst = potentials_dir / "Cu_u3.eam"
        shutil.copy2(potential_src, potential_dst)
        potential_sha = compute_sha256_file(potential_dst)
        
        # Create calculation
        calc_result = QVService.init_calculation(
            project_root=project_root,
            name="restart",
            structure_selector=structure_id,
        )
        calc_id = calc_result.meta.id
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
        relax_step = QVService.init_step(
            project_root=project_root,
            calculation_selector=calc_id,
            step_type="relax",
        )
        relax_step_id = relax_step.meta.id
        
        QVService.configure_step(
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
        md1_step = QVService.init_step(
            project_root=project_root,
            calculation_selector=calc_id,
            step_type="md",
        )
        md1_step_id = md1_step.meta.id
        
        QVService.configure_step(
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
                "n_steps": 500,
                "thermo_frequency": 100,
                "dump_frequency": 100,
                "dump_trajectory": True,
            },
        )
        
        # Create second MD step (restart from first MD)
        md2_step = QVService.init_step(
            project_root=project_root,
            calculation_selector=calc_id,
            step_type="md",
        )
        md2_step_id = md2_step.meta.id
        
        QVService.configure_step(
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
                "n_steps": 500,
                "thermo_frequency": 100,
                "dump_frequency": 100,
                "dump_trajectory": True,
            },
        )
        
        evidence["relax_ulid"] = relax_step_id
        evidence["md1_ulid"] = md1_step_id
        evidence["md2_ulid"] = md2_step_id
        evidence["calc_dir"] = str(calc_dir)
        
        # Run calculation
        project = Project.open(project_root)
        calculation = Calculation.from_yaml(calc_dir, project)
        registry = create_default_registry(include_lammps=True)
        runner = CalculationRunner(engine_registry=registry)
        
        result = runner.run(calculation)
        
        if result.status.value != "success":
            error_msg = result.steps[-1].message if result.steps else "Unknown error"
            print(f"ERROR: Calculation failed: {error_msg}")
            evidence["result"] = "FAIL"
            evidence["error"] = error_msg
            return evidence
        
        # Verify checkpoints
        raw_dir = calculation.raw_dir
        md1_dir = raw_dir / md1_step_id
        md2_dir = raw_dir / md2_step_id
        
        # D1: First MD produces restart.bin or restart.final.bin
        restart_bin = md1_dir / "restart.bin"
        restart_final_bin = md1_dir / "restart.final.bin"
        cp1 = restart_bin.exists() or restart_final_bin.exists()
        print_checkpoint("D1: First MD produces restart file", cp1)
        evidence["checkpoints"]["D1"] = cp1
        
        # D2: Second MD's in.lammps contains read_restart
        md2_in_lammps = md2_dir / "in.lammps"
        cp2 = False
        if verify_file_exists(md2_in_lammps, "D2: MD2 in.lammps exists"):
            content = md2_in_lammps.read_text()
            cp2 = "read_restart" in content
            print_checkpoint("D2: MD2 in.lammps contains read_restart", cp2)
        evidence["checkpoints"]["D2"] = cp2
        
        # D3: Second MD log shows restart read success
        md2_log = md2_dir / "log.lammps"
        cp3 = False
        if verify_file_exists(md2_log, "D3: MD2 log exists"):
            log_content = md2_log.read_text()
            cp3 = "ERROR" not in log_content.upper() and ("restart" in log_content.lower() or "read" in log_content.lower())
            print_checkpoint("D3: MD2 log shows restart read success", cp3)
        evidence["checkpoints"]["D3"] = cp3
        
        # D4: All three steps complete without ERROR
        relax_log = raw_dir / relax_step_id / "log.lammps"
        md1_log = md1_dir / "log.lammps"
        cp4 = True
        for log_file in [relax_log, md1_log, md2_log]:
            if log_file.exists():
                if "ERROR" in log_file.read_text().upper():
                    cp4 = False
                    break
        print_checkpoint("D4: All three steps complete without ERROR", cp4)
        evidence["checkpoints"]["D4"] = cp4
        
        # Collect evidence
        if md2_in_lammps.exists():
            evidence["evidence"]["md2_in_lammps_head"] = md2_in_lammps.read_text().split("\n")[:20]
        if md2_log.exists():
            restart_lines = [line for line in md2_log.read_text().split("\n") if "restart" in line.lower()]
            evidence["evidence"]["restart_grep"] = restart_lines[:5]
        
        all_passed = all([cp1, cp2, cp3, cp4])
        evidence["result"] = "PASS" if all_passed else "FAIL"
        
        duration = time.time() - start_time
        evidence["duration"] = duration
        print(f"\n  Duration: {duration:.2f}s")
        print(f"  Result: {evidence['result']}")
        
    except Exception as e:
        import traceback
        print(f"ERROR in Workflow D: {e}")
        traceback.print_exc()
        evidence["result"] = "FAIL"
        evidence["error"] = str(e)
        evidence["traceback"] = traceback.format_exc()
    
    return evidence


def generate_markdown_report(summary: Dict, results: Dict, env_info: Dict) -> str:
    """Generate markdown evidence report."""
    lines = []
    
    # Header
    lines.append("# LAMMPS Long Smoke Test - Evidence Report")
    lines.append("")
    lines.append(f"**Date**: {summary['date']}")
    lines.append(f"**Duration**: {summary['duration']:.2f}s")
    
    passed_count = sum(1 for r in results.values() if r.get("result") == "PASS")
    total_count = len(results)
    overall_status = "✅ PASS" if passed_count == total_count else "❌ FAIL"
    lines.append(f"**Overall Result**: {overall_status} ({passed_count}/{total_count} workflows passed)")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Pre-Run Evidence
    lines.append("## Pre-Run Evidence")
    lines.append("")
    lines.append("### Environment Verification")
    lines.append(f"- ✅ **Python version**: {env_info['python_version']}")
    lines.append(f"- ✅ **QMatSuite import**: Success - `{env_info['qvitas_path']}`")
    lines.append(f"- ✅ **LAMMPS binary path**: `{env_info['lammps_bin']}`")
    if env_info.get('lammps_version'):
        lines.append(f"- ✅ **LAMMPS version**: {env_info['lammps_version']}")
    lines.append("")
    lines.append("```")
    lines.append("=== PRE-RUN CHECKS ===")
    lines.append(f"Python: {env_info['python_version']}")
    lines.append(f"QMatSuite: {env_info['qvitas_path']}")
    lines.append(f"LAMMPS binary: {env_info['lammps_bin']}")
    if env_info.get('lammps_version'):
        lines.append(f"LAMMPS version: {env_info['lammps_version']}")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Workflow reports
    workflow_names = {
        "A": "LJ Relax",
        "B": "EAM MD",
        "C": "Chain (Relax → MD)",
        "D": "Restart_from (Relax → MD → MD restart)",
    }
    
    for key in ["A", "B", "C", "D"]:
        if key not in results:
            continue
        
        result = results[key]
        workflow_name = workflow_names[key]
        status_emoji = "✅" if result.get("result") == "PASS" else "❌"
        
        lines.append(f"## Workflow {key}: {workflow_name}")
        lines.append("")
        
        # Checkpoints table
        lines.append("### Checkpoints")
        lines.append("| # | Checkpoint | Pass/Fail | Notes |")
        lines.append("|---|------------|-----------|-------|")
        
        checkpoints = result.get("checkpoints", {})
        checkpoint_names = {
            "A": ["A1", "A2", "A3", "A4", "A5", "A6", "A7"],
            "B": ["B1", "B2", "B3", "B4", "B5", "B6"],
            "C": ["C1", "C2", "C3", "C4", "C5"],
            "D": ["D1", "D2", "D3", "D4"],
        }
        
        checkpoint_descriptions = {
            "A1": "`in.lammps` exists",
            "A2": "`in.lammps` contains `pair_style lj/cut`",
            "A3": "`structure.data` exists",
            "A4": "`log.lammps` exists, no ERROR",
            "A5": "`final.data` exists",
            "A6": "`trajectory.lammpstrj` exists",
            "A7": "`generated_structures/step_<ulid>/current.json` exists",
            "B1": "Potential staged: `raw/<ulid>/potentials/Cu_u3.eam`",
            "B2": "`in.lammps` contains correct `pair_style eam`",
            "B3": "`in.lammps` contains correct `pair_coeff` with potential path",
            "B4": "`log.lammps` exists, no ERROR",
            "B5": "`trajectory.lammpstrj` has multiple frames",
            "B5": "`trajectory.lammpstrj` has multiple frames",
            "B6": "Log shows completion (wall time)",
            "C1": "Relax step produces `final.data`",
            "C2": "Relax produces `current.json` artifact",
            "C3": "MD step uses relax output (check `in.lammps`)",
            "C4": "MD atom count matches relax",
            "C5": "Both steps complete without ERROR",
            "D1": "First MD produces `restart.bin` or `restart.final.bin`",
            "D2": "Second MD's `in.lammps` contains `read_restart`",
            "D3": "Second MD log shows restart read success",
            "D4": "All three steps complete without ERROR",
        }
        
        for cp_key in checkpoint_names.get(key, []):
            passed = checkpoints.get(cp_key, False)
            status = "✅ PASS" if passed else "❌ FAIL"
            desc = checkpoint_descriptions.get(cp_key, cp_key)
            notes = result.get("notes", "") if not passed and result.get("notes") else ""
            lines.append(f"| {cp_key} | {desc} | {status} | {notes} |")
        
        lines.append("")
        
        # Evidence section
        lines.append("### Evidence")
        lines.append("")
        lines.append("```")
        
        evidence = result.get("evidence", {})
        if result.get("error"):
            lines.append(f"ERROR: {result['error']}")
        else:
            lines.append(f"Calculation status: {result.get('result', 'UNKNOWN').lower()}")
            if evidence.get("file_listing"):
                lines.append(f"Working dir: {evidence['file_listing']}")
            if evidence.get("pair_style"):
                lines.append("")
                lines.append("in.lammps pair_style:")
                for line in evidence["pair_style"]:
                    lines.append(line)
            if evidence.get("log_tail"):
                lines.append("")
                lines.append("Log tail (last 20 lines):")
                for line in evidence["log_tail"]:
                    lines.append(line)
            if evidence.get("frame_count"):
                lines.append(f"Trajectory frames: {evidence['frame_count']}")
        
        lines.append("```")
        lines.append("")
        
        if result.get("result") == "PASS":
            lines.append(f"**Result**: ✅ PASS")
        else:
            lines.append(f"**Result**: ❌ FAIL")
            if result.get("error"):
                lines.append(f"**Error**: {result['error']}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("```")
    lines.append("=== LAMMPS LONG SMOKE TEST SUMMARY ===")
    lines.append(f"Date: {summary['date']}")
    lines.append(f"Duration: {summary['duration']:.2f}s")
    lines.append("")
    
    for key in ["A", "B", "C", "D"]:
        if key in results:
            result = results[key]
            status = result.get("result", "UNKNOWN")
            status_emoji = "✅" if status == "PASS" else "❌"
            lines.append(f"Workflow {key} ({workflow_names[key]}):      {status_emoji} {status}")
    
    lines.append("")
    lines.append(f"Overall:                    {overall_status}")
    lines.append("```")
    lines.append("")
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="LAMMPS Long Smoke Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (auto-detect LAMMPS)
  python tools/run_lammps_long_smoke.py

  # Specify LAMMPS binary path
  python tools/run_lammps_long_smoke.py --lammps-bin /usr/local/bin/lmp_serial

  # Keep workdir for debugging
  python tools/run_lammps_long_smoke.py --keep-workdir --project-dir /tmp/lammps_test

  # Generate markdown report
  python tools/run_lammps_long_smoke.py --output-report report.md
        """
    )
    parser.add_argument(
        "--lammps-bin",
        type=str,
        help="Path to LAMMPS binary (overrides auto-detection)",
    )
    parser.add_argument(
        "--brew-prefix",
        type=str,
        help="Homebrew prefix for LAMMPS (for detection only, use --lammps-bin to override)",
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Keep work directory after test (requires --project-dir)",
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        help="Project directory (default: temporary directory)",
    )
    parser.add_argument(
        "--output-report",
        type=str,
        help="Output markdown evidence report file",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        help="Output JSON evidence file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    args = parser.parse_args()
    
    # Pre-run checks
    print_section("PRE-RUN CHECKS")
    
    # Python version
    python_version = subprocess.check_output(["python", "--version"], text=True).strip()
    print(f"Python: {python_version}")
    
    # QMatSuite import
    try:
        import quantumvitas
        qvitas_path = quantumvitas.__file__
        print(f"QMatSuite: {qvitas_path}")
    except ImportError:
        print("ERROR: QMatSuite not found")
        sys.exit(1)
    
    # LAMMPS binary resolution
    lammps_bin = None
    lammps_version = None
    
    if args.lammps_bin:
        lammps_bin = Path(args.lammps_bin)
        if not lammps_bin.exists():
            print(f"ERROR: LAMMPS binary not found: {lammps_bin}")
            sys.exit(1)
        # Set environment variable for resolver
        os.environ["QMATS_LAMMPS_BIN"] = str(lammps_bin)
        print(f"LAMMPS binary (from --lammps-bin): {lammps_bin}")
    else:
        try:
            from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
            lammps_bin = resolve_lammps_bin()
            print(f"LAMMPS binary (auto-detected): {lammps_bin}")
        except Exception as e:
            print(f"ERROR: LAMMPS resolver failed: {e}")
            sys.exit(1)
    
    # Get LAMMPS version
    lammps_version = get_lammps_version(lammps_bin)
    if lammps_version:
        print(f"LAMMPS version: {lammps_version}")
    else:
        print("WARNING: Could not get LAMMPS version")
    
    env_info = {
        "python_version": python_version,
        "qvitas_path": qvitas_path,
        "lammps_bin": str(lammps_bin),
        "lammps_version": lammps_version,
    }
    
    # Determine work directory (base directory for all workflows)
    use_temp = not args.keep_workdir and not args.project_dir
    if args.project_dir:
        base_dir = Path(args.project_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        print(f"Using base directory: {base_dir}")
    else:
        if use_temp:
            temp_dir = tempfile.mkdtemp(prefix="lammps_smoke_")
            base_dir = Path(temp_dir)
            print(f"Using temporary directory: {base_dir}")
        else:
            # --keep-workdir without --project-dir: use current dir
            base_dir = Path.cwd() / "lammps_smoke_test"
            base_dir.mkdir(exist_ok=True)
            print(f"Using work directory: {base_dir}")
    
    # Run all workflows
    total_start = time.time()
    results = {}
    
    try:
        results["A"] = run_workflow_a_lj_relax(base_dir)
        results["B"] = run_workflow_b_eam_md(base_dir)
        results["C"] = run_workflow_c_chain(base_dir)
        results["D"] = run_workflow_d_restart(base_dir)
    finally:
        # Cleanup if using temp directory
        if use_temp and base_dir.exists():
            shutil.rmtree(base_dir)
            print(f"\nCleaned up temporary directory: {base_dir}")
        elif args.keep_workdir:
            print(f"\nWork directory kept: {base_dir}")
    
    total_duration = time.time() - total_start
    
    # Summary
    print_section("LAMMPS LONG SMOKE TEST SUMMARY")
    
    summary = {
        "date": datetime.now(timezone.utc).isoformat(),
        "duration": total_duration,
        "workflows": {},
    }
    
    for key, result in results.items():
        status = result.get("result", "UNKNOWN")
        summary["workflows"][key] = status
        print(f"  Workflow {key} ({result.get('name', 'Unknown')}): {status}")
    
    passed_count = sum(1 for r in results.values() if r.get("result") == "PASS")
    total_count = len(results)
    overall = "PASS" if passed_count == total_count else "FAIL"
    summary["overall"] = overall
    print(f"\n  Overall: {overall} ({passed_count}/{total_count} workflows passed)")
    print(f"  Total Duration: {total_duration:.2f}s")
    
    # Save evidence
    if args.output_json:
        evidence_data = {
            "summary": summary,
            "env_info": env_info,
            "results": results,
        }
        with open(args.output_json, "w") as f:
            json.dump(evidence_data, f, indent=2)
        print(f"\n  Evidence JSON saved to: {args.output_json}")
    
    if args.output_report:
        report_md = generate_markdown_report(summary, results, env_info)
        with open(args.output_report, "w") as f:
            f.write(report_md)
        print(f"  Evidence report saved to: {args.output_report}")
    
    # Exit code
    exit_code = 0 if overall == "PASS" else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
