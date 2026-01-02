#!/usr/bin/env python3
"""
Generate Diamond Wannier90 Demo Project.

This script creates a complete Wannier90 tutorial demo based on the diamond
example from the bundled Wannier90 distribution. The demo includes:
- SCF step (pw.x)
- NSCF step (pw.x with uniform k-grid)
- w90_preproc step (wannier90.x -pp)
- pw2wannier90 step (pw2wannier90.x)
- w90_run step (wannier90.x)

Usage:
    python tools/generate_wannier90_demo.py

The demo is created in resources/demo_projects/diamond_wannier90_demo.yml
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path for imports
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT / "src"))


def find_wannier90_example_dir() -> Optional[Path]:
    """Find the Wannier90 example05 (diamond) directory."""
    qe_root = REPO_ROOT / ".qmatsuite" / "engines" / "qe" / "q-e-qe-7.5"
    example_dir = qe_root / "external" / "wannier90" / "examples" / "example05"
    
    if example_dir.exists():
        return example_dir
    
    return None


def find_wannier90_pseudo_dir() -> Optional[Path]:
    """Find the Wannier90 pseudo directory."""
    qe_root = REPO_ROOT / ".qmatsuite" / "engines" / "qe" / "q-e-qe-7.5"
    pseudo_dir = qe_root / "external" / "wannier90" / "pseudo"
    
    if pseudo_dir.exists():
        return pseudo_dir
    
    return None


def copy_pseudo_to_resources(pseudo_name: str, source_dir: Path) -> bool:
    """
    Copy pseudopotential to resources/pseudo if not already there.
    
    Returns True if successful, False otherwise.
    """
    from quantumvitas.core.pseudo_provenance import compute_sha256_file
    from quantumvitas.core.pseudo_libinfo import compute_sha_family_file
    
    target_dir = REPO_ROOT / "resources" / "pseudo"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    source_file = source_dir / pseudo_name
    target_file = target_dir / pseudo_name
    
    if not source_file.exists():
        print(f"  ✗ Source pseudo not found: {source_file}")
        return False
    
    if not target_file.exists():
        shutil.copy2(source_file, target_file)
        print(f"  ✓ Copied pseudo: {pseudo_name}")
    else:
        print(f"  - Pseudo already exists: {pseudo_name}")
    
    # Compute and return identity triple info
    sha256 = compute_sha256_file(target_file)
    sha_family = compute_sha_family_file(target_file)
    print(f"    SHA256: {sha256[:16]}...")
    print(f"    SHA_FAMILY: {sha_family[:16]}...")
    
    return True


def create_species_map(pseudo_name: str) -> Dict[str, Dict[str, Any]]:
    """Create species map with pseudo identity triple."""
    from quantumvitas.core.pseudo_provenance import compute_sha256_file
    from quantumvitas.core.pseudo_libinfo import compute_sha_family_file
    
    pseudo_path = REPO_ROOT / "resources" / "pseudo" / pseudo_name
    
    if not pseudo_path.exists():
        raise FileNotFoundError(f"Pseudo not found: {pseudo_path}")
    
    sha256 = compute_sha256_file(pseudo_path)
    sha_family = compute_sha_family_file(pseudo_path)
    
    return {
        "C": {
            "mass": 12.0,
            "pseudopot": pseudo_name,
            "pseudo_basename": pseudo_name,
            "pseudo_sha256": sha256,
            "pseudo_sha_family": sha_family,
        }
    }


def generate_demo_snapshot() -> Dict[str, Any]:
    """Generate the complete demo snapshot structure."""
    from quantumvitas.io.wannier90_input import Wannier90Input, Pw2Wannier90Input
    
    # Find source files
    example_dir = find_wannier90_example_dir()
    pseudo_dir = find_wannier90_pseudo_dir()
    
    if not example_dir:
        raise RuntimeError("Wannier90 example05 directory not found. Is QE installed?")
    
    if not pseudo_dir:
        raise RuntimeError("Wannier90 pseudo directory not found.")
    
    print(f"Using example from: {example_dir}")
    print(f"Using pseudo from: {pseudo_dir}")
    
    # Copy pseudopotential
    pseudo_name = "C.pz-vbc.UPF"
    if not copy_pseudo_to_resources(pseudo_name, pseudo_dir):
        raise RuntimeError(f"Failed to copy pseudo: {pseudo_name}")
    
    # Create species map with identity triple
    species_map = create_species_map(pseudo_name)
    
    # Read source input files
    scf_content = (example_dir / "diamond.scf").read_text()
    nscf_content = (example_dir / "diamond.nscf").read_text()
    pw2wan_content = (example_dir / "diamond.pw2wan").read_text()
    win_content = (example_dir / "diamond.win").read_text()
    
    # Parse the .win file
    win_input = Wannier90Input.from_string(win_content)
    pw2wan_input = Pw2Wannier90Input.from_string(pw2wan_content)
    
    # Build demo snapshot
    # Structure: Diamond (2 C atoms, FCC)
    structure = {
        "__qv_meta__": {
            "id": "01JGXYZ000000000000STRUCT1",
            "name": "diamond",
            "slug": "diamond",
            "path": "structures/diamond.json",
            "kind": "structure",
        },
        "lattice": {
            "a": [[-1.613990, 0.000000, 1.613990]],
            "b": [[0.000000, 1.613990, 1.613990]],
            "c": [[-1.613990, 1.613990, 0.000000]],
        },
        "species": ["C", "C"],
        "coords": [
            [-0.125, -0.125, -0.125],
            [0.125, 0.125, 0.125],
        ],
        "coord_type": "crystal",
    }
    
    # Steps configuration
    steps = [
        {
            "step_id": "01JGXYZ000000000000STEP001",
            "step_type": "scf",
            "name": "scf",
            "parameters": {
                "CONTROL": {
                    "calculation": "scf",
                    "prefix": "di",
                    "pseudo_dir": "../../../pseudo",
                    "outdir": "./",
                },
                "SYSTEM": {
                    "ibrav": 2,
                    "celldm(1)": 6.1,
                    "nat": 2,
                    "ntyp": 1,
                    "ecutwfc": 40.0,
                },
                "ELECTRONS": {
                    "diagonalization": "david",
                    "mixing_mode": "plain",
                    "mixing_beta": 0.7,
                    "conv_thr": 1.0e-13,
                },
            },
        },
        {
            "step_id": "01JGXYZ000000000000STEP002",
            "step_type": "nscf",
            "name": "nscf",
            "parameters": {
                "CONTROL": {
                    "calculation": "nscf",
                    "prefix": "di",
                    "pseudo_dir": "../../../pseudo",
                    "outdir": "./",
                },
                "SYSTEM": {
                    "ibrav": 2,
                    "celldm(1)": 6.1,
                    "nat": 2,
                    "ntyp": 1,
                    "ecutwfc": 40.0,
                    "nbnd": 4,
                },
                "ELECTRONS": {
                    "conv_thr": 1.0e-11,
                },
            },
            "kpoints": {
                "type": "crystal",
                "grid": [4, 4, 4],
            },
        },
        {
            "step_id": "01JGXYZ000000000000STEP003",
            "step_type": "w90_preproc",
            "name": "w90_preproc",
            "parameters": {
                "seedname": "diamond",
                "num_wann": win_input.num_wann,
                "num_iter": win_input.num_iter,
                "mp_grid": win_input.mp_grid,
                "projections_block": win_input.projections_block,
                "unit_cell_cart": win_input.unit_cell_cart,
                "atoms_frac": win_input.atoms_frac,
                "kpoints": win_input.kpoints,
                "wannier_plot": win_input.wannier_plot,
                "wannier_plot_supercell": win_input.wannier_plot_supercell,
            },
        },
        {
            "step_id": "01JGXYZ000000000000STEP004",
            "step_type": "pw2wannier90",
            "name": "pw2wannier90",
            "parameters": {
                "seedname": pw2wan_input.seedname,
                "prefix": pw2wan_input.prefix,
                "outdir": pw2wan_input.outdir,
                "write_mmn": pw2wan_input.write_mmn,
                "write_amn": pw2wan_input.write_amn,
                "write_unk": pw2wan_input.write_unk,
                "spin_component": pw2wan_input.spin_component,
            },
        },
        {
            "step_id": "01JGXYZ000000000000STEP005",
            "step_type": "w90_run",
            "name": "w90_run",
            "parameters": {
                "seedname": "diamond",
                "num_wann": win_input.num_wann,
                "num_iter": win_input.num_iter,
                "mp_grid": win_input.mp_grid,
                "projections_block": win_input.projections_block,
                "unit_cell_cart": win_input.unit_cell_cart,
                "atoms_frac": win_input.atoms_frac,
                "kpoints": win_input.kpoints,
                "wannier_plot": win_input.wannier_plot,
                "wannier_plot_supercell": win_input.wannier_plot_supercell,
            },
        },
    ]
    
    # Build the full snapshot
    snapshot = {
        "__qv_snapshot_version__": "1.0",
        "project": {
            "name": "Diamond Wannier90 Demo",
            "description": "End-to-end Wannier90 workflow for diamond (4 sp³ MLWFs)",
        },
        "structures": [structure],
        "calculations": [
            {
                "__qv_meta__": {
                    "id": "01JGXYZ000000000000CALC001",
                    "name": "Diamond Wannier90",
                    "slug": "diamond-wannier90",
                    "path": "calculations/diamond-wannier90",
                    "kind": "calculation",
                },
                "structure_id": "01JGXYZ000000000000STRUCT1",
                "species_map": species_map,
                "steps": steps,
            }
        ],
        "raw_inputs": {
            "diamond.scf": scf_content,
            "diamond.nscf": nscf_content,
            "diamond.pw2wan": pw2wan_content,
            "diamond.win": win_content,
        },
    }
    
    return snapshot


def write_demo_yaml(snapshot: Dict[str, Any], output_path: Path) -> None:
    """Write the demo snapshot to YAML file."""
    import yaml
    
    # Custom YAML representer for multiline strings
    def str_representer(dumper, data):
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)
    
    yaml.add_representer(str, str_representer)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        yaml.dump(snapshot, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def main():
    """Main entry point."""
    print("=" * 60)
    print("Generating Diamond Wannier90 Demo")
    print("=" * 60)
    
    try:
        # Generate snapshot
        snapshot = generate_demo_snapshot()
        
        # Write to demo projects directory
        output_path = REPO_ROOT / "resources" / "demo_projects" / "diamond_wannier90_demo.yml"
        write_demo_yaml(snapshot, output_path)
        
        print()
        print(f"✓ Demo generated: {output_path}")
        print()
        print("Demo contents:")
        print(f"  - 1 structure (diamond)")
        print(f"  - 1 calculation with 5 steps:")
        print(f"    1. scf (pw.x)")
        print(f"    2. nscf (pw.x, uniform k-grid)")
        print(f"    3. w90_preproc (wannier90.x -pp)")
        print(f"    4. pw2wannier90 (pw2wannier90.x)")
        print(f"    5. w90_run (wannier90.x)")
        print()
        print("To run the demo:")
        print(f"  1. Load project in QMatSuite UI")
        print(f"  2. Or use CLI: qv run --project <demo_project_path>")
        print()
        print("Expected outputs:")
        print(f"  - diamond.nnkp (from w90_preproc)")
        print(f"  - diamond.mmn, diamond.amn, diamond.eig (from pw2wannier90)")
        print(f"  - diamond.wout, diamond.chk (from w90_run)")
        
        return 0
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

