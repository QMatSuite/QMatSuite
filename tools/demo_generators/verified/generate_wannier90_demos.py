#!/usr/bin/env python3
"""
Generate Wannier90 demo project snapshots from the official examples.

This script creates demo projects from Wannier90 examples:
- Example05: Diamond (4 MLWFs)
- Example06: Copper (7 MLWFs with disentanglement)
- Example16: Silicon (8 MLWFs with disentanglement)

The demos are created in a proper project structure with all input files
copied to the raw/ directory, pseudo files to project/pseudo/, and 
calculation.yaml referencing steps.

Usage:
    python tools/demo_generators/verified/generate_wannier90_demos.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add src to path
repo_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))

from quantumvitas.project.snapshot import export_project_to_snapshot
from quantumvitas.core.pseudo_provenance import compute_sha256_file
from quantumvitas.core.pseudo_libinfo import compute_sha_family_file
from quantumvitas.core.resources import generate_resource_id as generate_ulid
import yaml


# Paths
EXAMPLES_ROOT = repo_root / ".qmatsuite" / "engines" / "qe" / "q-e-qe-7.5" / "external" / "wannier90" / "examples"
PSEUDO_SOURCE = repo_root / ".qmatsuite" / "engines" / "qe" / "q-e-qe-7.5" / "external" / "wannier90" / "pseudo"
PSEUDO_DEST = repo_root / "resources" / "pseudo"
DEMO_OUTPUT_DIR = repo_root / "resources" / "demo_projects"
TEST_DATA_DIR = repo_root / "tests" / "data" / "wannier90_examples"

# Example configurations
EXAMPLES = {
    "diamond": {
        "dir": "example05",
        "seedname": "diamond",
        "prefix": "di",
        "pseudo": "C.pz-vbc.UPF",
        "element": "C",
        "mass": 12.011,
        "num_wann": 4,
        "num_bands": 4,
        "description": "Diamond valence bands - 4 sp3 bonding MLWFs",
    },
    "copper": {
        "dir": "example06", 
        "seedname": "copper",
        "prefix": "cu",
        "pseudo": "Cu.pz-n-van_ak.UPF",
        "element": "Cu",
        "mass": 63.546,
        "num_wann": 7,
        "num_bands": 12,
        "description": "Copper Fermi surface - 7 MLWFs (5d + 2s)",
    },
    "silicon": {
        "dir": "example16-withqe",
        "seedname": "Si",
        "prefix": "si",
        "pseudo": "Si.pbe-n-van.UPF",
        "element": "Si",
        "mass": 28.0855,
        "num_wann": 8,
        "num_bands": 12,
        "description": "Silicon Boltzmann transport - 8 sp3 MLWFs",
    },
}


def ensure_pseudo_in_resources(pseudo_name: str) -> bool:
    """Copy pseudo from wannier90 distribution to resources/pseudo/ if needed."""
    dest = PSEUDO_DEST / pseudo_name
    if dest.exists():
        return True
    
    source = PSEUDO_SOURCE / pseudo_name
    if source.exists():
        PSEUDO_DEST.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, dest)
        print(f"  ✓ Copied {pseudo_name} to resources/pseudo/")
        return True
    
    print(f"  ✗ Pseudo {pseudo_name} not found in wannier90 distribution")
    return False


def compute_pseudo_identity(pseudo_name: str) -> Optional[Dict[str, str]]:
    """Compute pseudo identity triple."""
    pseudo_path = PSEUDO_DEST / pseudo_name
    if not pseudo_path.exists():
        return None
    
    try:
        sha256 = compute_sha256_file(pseudo_path)
        sha_family = compute_sha_family_file(pseudo_path)
        return {
            "pseudo_sha256": sha256,
            "pseudo_sha_family": sha_family,
        }
    except Exception as e:
        print(f"  ⚠️  Error computing hashes for {pseudo_name}: {e}")
        return None


def parse_structure_from_scf(scf_content: str) -> Dict[str, Any]:
    """Extract structure data from SCF input file."""
    lines = scf_content.split("\n")
    
    # Parse CELL_PARAMETERS or celldm/ibrav
    cell_params = []
    atomic_species = {}
    atomic_positions = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # CELL_PARAMETERS block
        if line.upper().startswith("CELL_PARAMETERS"):
            unit = "angstrom" if "angstrom" in line.lower() else "bohr"
            for j in range(1, 4):
                if i + j < len(lines):
                    parts = lines[i + j].split()
                    if len(parts) >= 3:
                        vec = [float(parts[0]), float(parts[1]), float(parts[2])]
                        # Convert to angstrom if needed
                        if unit == "bohr":
                            vec = [v * 0.529177 for v in vec]
                        cell_params.append(vec)
            i += 4
            continue
        
        # ATOMIC_SPECIES block
        if line.upper() == "ATOMIC_SPECIES":
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].strip().upper().startswith(("ATOMIC_POSITIONS", "K_POINTS", "CELL_PARAMETERS")):
                parts = lines[i].split()
                if len(parts) >= 3:
                    elem = parts[0]
                    mass = float(parts[1])
                    pseudo = parts[2]
                    atomic_species[elem] = {"mass": mass, "pseudo": pseudo}
                i += 1
            continue
        
        # ATOMIC_POSITIONS block
        if line.upper().startswith("ATOMIC_POSITIONS"):
            coord_type = "crystal" if "crystal" in line.lower() else "angstrom"
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].strip().upper().startswith(("K_POINTS", "CELL_PARAMETERS")):
                parts = lines[i].split()
                if len(parts) >= 4:
                    elem = parts[0]
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    if coord_type == "crystal":
                        atomic_positions.append({"label": elem, "abc": [x, y, z]})
                    else:
                        atomic_positions.append({"label": elem, "xyz": [x, y, z]})
                i += 1
            continue
        
        # Parse ibrav lattice
        if "ibrav" in line.lower():
            # Extract ibrav and celldm from system namelist
            pass  # For now, skip - we use CELL_PARAMETERS
        
        i += 1
    
    # Build structure dict in our format
    structure = {
        "lattice": {"matrix": cell_params} if cell_params else {},
        "sites": atomic_positions,
    }
    
    return structure, atomic_species


def create_step_spec(step_type: str, index: int, seedname: str, params: Optional[Dict] = None, cards: Optional[Dict] = None, calc_name: str = "") -> Dict[str, Any]:
    """Create a step specification dictionary.

    Constitution §B: Persisted truth must be SPEC format (machine type).
    GEN types are converted to SPEC types for persistence.

    Args:
        step_type: Step type (scf, nscf, w90_wannierprep, etc.) - may be GEN or SPEC
        index: Step index in calculation
        seedname: Seedname for input files
        params: Step parameters (namelist sections) - NO prefix/outdir, NO pseudo mapping
        cards: Step cards (e.g., K_POINTS) - MUST be separate from parameters
        calc_name: Calculation slug for path generation
    """
    step_id = generate_ulid()

    # Convert GEN types to SPEC types for persistence (Constitution §B)
    gen_to_spec = {
        "scf": "qe_scf",
        "nscf": "qe_nscf",
        "pw2wannier90": "qe_pw2wannier90",
        # w90_wannierprep and w90_wannier are already SPEC format
    }
    machine_type = gen_to_spec.get(step_type, step_type)

    # Determine input file name based on step type (use original name for paths)
    if step_type == "scf":
        input_name = f"{seedname}.scf"
    elif step_type == "nscf":
        input_name = f"{seedname}.nscf"
    elif step_type == "w90_wannierprep":
        input_name = f"{seedname}.win"
    elif step_type == "pw2wannier90":
        input_name = f"{seedname}.pw2wan"
    elif step_type == "w90_wannier":
        input_name = f"{seedname}.win"
    else:
        input_name = f"{seedname}.{step_type}"

    calc_slug = calc_name if calc_name else f"{seedname}-mlwfs"

    spec = {
        "meta": {
            "id": step_id,
            "name": step_type,  # Keep original name for display
            "slug": step_type,
            "path": f"calculations/{calc_slug}/steps/{step_type}.step.yaml",
            "kind": "step",
        },
        "step_type": machine_type,  # SPEC type (machine type) for persistence
        "index": index,
    }
    
    # Add parameters if provided (namelist sections only)
    if params:
        spec["parameters"] = params
    
    # Add cards if provided (K_POINTS, etc.) - MUST be separate from parameters
    if cards:
        spec["cards"] = cards
    
    return spec


def generate_demo_snapshot(name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a demo snapshot from example configuration."""
    from quantumvitas.io import QEInputParser
    from quantumvitas.calculation.importers import _build_step_spec_from_qe_input_data
    from quantumvitas.io.structure_io import structure_from_qe_input
    from quantumvitas.io import write_structure
    from quantumvitas.core.resources import meta_from_name, ensure_relative_path
    
    example_dir = EXAMPLES_ROOT / config["dir"]
    seedname = config["seedname"]
    
    print(f"\nGenerating {name} demo from {example_dir}...")
    
    # Ensure pseudo is available
    if not ensure_pseudo_in_resources(config["pseudo"]):
        print(f"  ⚠️  Skipping {name} - pseudo not available")
        return None
    
    # Read and parse QE input files
    scf_file = example_dir / f"{seedname}.scf"
    nscf_file = example_dir / f"{seedname}.nscf"
    
    if not scf_file.exists():
        print(f"  ⚠️  SCF file not found: {scf_file}")
        return None
    
    # Parse QE inputs to extract parameters and cards correctly
    scf_qe_input = QEInputParser.parse_file(scf_file)
    nscf_qe_input = QEInputParser.parse_file(nscf_file) if nscf_file.exists() else None
    
    # Extract structure from SCF input (as PMGStructure, convert to dict for snapshot)
    structure_pmg = structure_from_qe_input(scf_qe_input)
    structure = structure_pmg.as_dict()  # Convert to dict format for snapshot
    # Fix pbc tuple -> list for YAML serialization (safe_dump can't handle tuples)
    if "pbc" in structure and isinstance(structure["pbc"], tuple):
        structure["pbc"] = list(structure["pbc"])
    
    # Build species_map with pseudo identity (calculation-level only)
    pseudo_identity = compute_pseudo_identity(config["pseudo"])
    if not pseudo_identity:
        print(f"  ⚠️  Could not compute pseudo identity")
        return None
    
    species_map = {
        config["element"]: {
            "mass": config["mass"],
            "pseudopot": config["pseudo"],
            "pseudo_basename": config["pseudo"],
            **pseudo_identity,
        }
    }
    
    # Create project structure
    project_id = generate_ulid()
    calc_id = generate_ulid()
    structure_id = generate_ulid()
    
    # Calculate calculation slug for step paths
    calc_slug = f"{name}-mlwfs"
    
    # Create steps by parsing QE inputs (correctly extracts K_POINTS as cards)
    steps = []
    
    # SCF step
    scf_params, scf_cards = _build_step_spec_from_qe_input_data(scf_qe_input, "scf", apply_defaults=False)
    # Remove prefix/outdir from step parameters (injected from calculation.meta.slug)
    for section in scf_params:
        scf_params[section].pop("prefix", None)
        scf_params[section].pop("outdir", None)
    # Remove step-level pseudo mapping if present (should only be in calculation-level species_map)
    # _build_step_spec_from_qe_input_data doesn't include species_overrides, so this is safe
    scf_step = create_step_spec("scf", 0, seedname, params=scf_params, cards=scf_cards, calc_name=calc_slug)
    steps.append(scf_step)
    
    # NSCF step
    if nscf_qe_input:
        nscf_params, nscf_cards = _build_step_spec_from_qe_input_data(nscf_qe_input, "nscf", apply_defaults=False)
        # Remove prefix/outdir from step parameters
        for section in nscf_params:
            nscf_params[section].pop("prefix", None)
            nscf_params[section].pop("outdir", None)
        nscf_step = create_step_spec("nscf", 1, seedname, params=nscf_params, cards=nscf_cards, calc_name=calc_slug)
        nscf_step["depends_on"] = [steps[0]["meta"]["id"]]
        steps.append(nscf_step)
    
    # Wannier90 steps (no QE input, use Wannier90 input files)
    # Read .win file for w90_wannierprep and w90_wannier
    win_file = example_dir / f"{seedname}.win"
    if win_file.exists():
        from quantumvitas.io.wannier90_input import Wannier90Input
        win_input = Wannier90Input.from_file(win_file)
        
        w90_params = {
            "seedname": seedname,
            "num_wann": win_input.num_wann,
            "num_bands": win_input.num_bands,
            "mp_grid": win_input.mp_grid,
            "projections_block": win_input.projections_block,
        }
        if win_input.num_iter:
            w90_params["num_iter"] = win_input.num_iter
        
        w90_wannierprep_step = create_step_spec("w90_wannierprep", len(steps), seedname, params=w90_params, calc_name=calc_slug)
        w90_wannierprep_step["depends_on"] = [steps[-1]["meta"]["id"]] if steps else []
        steps.append(w90_wannierprep_step)
        
        # w90_wannier uses same parameters
        w90_wannier_step = create_step_spec("w90_wannier", len(steps) + 1, seedname, params=w90_params, calc_name=calc_slug)
        steps.append(w90_wannier_step)
    
    # pw2wannier90 step (depends on NSCF and w90_wannierprep, must run before w90_wannier)
    pw2wan_file = example_dir / f"{seedname}.pw2wan"
    pw2wan_step = None
    if pw2wan_file.exists():
        pw2wan_params = {
            "seedname": seedname,
            # prefix/outdir will be injected from calculation.meta.slug
            # Do NOT include them in step parameters
        }
        # Find w90_wannierprep step index
        w90_wannierprep_idx = next((i for i, s in enumerate(steps) if s["step_type"] == "w90_wannierprep"), None)
        nscf_idx = next((i for i, s in enumerate(steps) if s["step_type"] == "nscf"), None)
        
        if w90_wannierprep_idx is not None and nscf_idx is not None:
            pw2wan_step = create_step_spec("pw2wannier90", len(steps), seedname, params=pw2wan_params, calc_name=calc_slug)
            pw2wan_step["depends_on"] = [steps[nscf_idx]["meta"]["id"], steps[w90_wannierprep_idx]["meta"]["id"]]
            # Insert before w90_wannier
            w90_wannier_idx = next((i for i, s in enumerate(steps) if s["step_type"] == "w90_wannier"), None)
            if w90_wannier_idx is not None:
                steps.insert(w90_wannier_idx, pw2wan_step)
            else:
                steps.append(pw2wan_step)
    
    # Update w90_wannier dependency to depend on pw2wannier90
    w90_wannier_idx = next((i for i, s in enumerate(steps) if s["step_type"] == "w90_wannier"), None)
    if w90_wannier_idx is not None and pw2wan_step:
        steps[w90_wannier_idx]["depends_on"] = [pw2wan_step["meta"]["id"]]
    
    # Build snapshot
    snapshot = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "project": {
            "meta": {
                "id": project_id,
                "name": f"{name.title()} Wannier90 Demo",
                "slug": f"{name}-wannier90-demo",
                "path": ".",
                "kind": "project",
            },
            "settings": {},
        },
        "structures": [
            {
                "meta": {
                    "id": structure_id,
                    "name": name.title(),
                    "slug": name.lower(),
                    "path": f"structures/{name.lower()}.json",
                    "kind": "structure",
                },
                "data": structure,
            }
        ],
        "calculations": [
            {
                "meta": {
                    "id": calc_id,
                    "name": f"{name.title()} MLWFs",
                    "slug": f"{name}-mlwfs",
                    "path": f"calculations/{name}-mlwfs",
                    "kind": "calculation",
                },
                "mode": "normal",
                "working_dir": "raw",
                "structure_id": structure_id,
                "species_map": species_map,  # Calculation-level pseudo mapping (authoritative)
                "steps": steps,
            }
        ],
        "pseudo": {
            "files": [config["pseudo"]],
        },
        "raw_inputs": {
            "description": "Original input files from Wannier90 examples",
            "files": [
                f"{seedname}.scf",
                f"{seedname}.nscf", 
                f"{seedname}.pw2wan",
                f"{seedname}.win",
            ],
        },
    }
    
    return snapshot


def copy_example_inputs_to_test_data(name: str, config: Dict[str, Any]) -> bool:
    """Copy example input files to tests/data for roundtrip tests."""
    example_dir = EXAMPLES_ROOT / config["dir"]
    seedname = config["seedname"]
    
    dest_dir = TEST_DATA_DIR / config["dir"].replace("-withqe", "")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    files = [f"{seedname}.scf", f"{seedname}.nscf", f"{seedname}.pw2wan", f"{seedname}.win"]
    
    for f in files:
        src = example_dir / f
        if src.exists():
            shutil.copy(src, dest_dir / f)
    
    # Also copy to pseudo dir
    pseudo_dest = TEST_DATA_DIR / "pseudo"
    pseudo_dest.mkdir(exist_ok=True)
    pseudo_src = PSEUDO_SOURCE / config["pseudo"]
    if pseudo_src.exists():
        shutil.copy(pseudo_src, pseudo_dest / config["pseudo"])
    
    return True


def main():
    """Generate all Wannier90 demos."""
    print("=" * 60)
    print("Generating Wannier90 Demo Projects")
    print("=" * 60)
    
    DEMO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    generated = []
    skipped = []
    
    for name, config in EXAMPLES.items():
        # Generate snapshot
        snapshot = generate_demo_snapshot(name, config)
        
        if snapshot:
            # Write demo file
            demo_file = DEMO_OUTPUT_DIR / f"{name}_wannier90_demo.yml"
            with open(demo_file, "w") as f:
                yaml.safe_dump(snapshot, f, default_flow_style=False, sort_keys=False)
            print(f"  ✓ Written {demo_file.name}")
            generated.append(name)
            
            # Also copy test data
            copy_example_inputs_to_test_data(name, config)
        else:
            skipped.append(name)
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Generated: {len(generated)}")
    for name in generated:
        print(f"  - {name}_wannier90_demo.yml")
    
    if skipped:
        print(f"\nSkipped: {len(skipped)}")
        for name in skipped:
            print(f"  - {name}")
    
    print("\nTo run Wannier90 tests:")
    print("  python -m pytest tests/integration/test_wannier90_project_execution.py -v")


if __name__ == "__main__":
    main()
