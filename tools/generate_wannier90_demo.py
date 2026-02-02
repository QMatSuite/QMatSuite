#!/usr/bin/env python3
"""
Generate Diamond Wannier90 Demo Project.

This script creates a complete Wannier90 tutorial demo based on the diamond
example from the bundled Wannier90 distribution. The demo includes:
- SCF step (pw.x)
- NSCF step (pw.x with uniform k-grid)
- w90_wannierprep step (wannier90.x -pp)
- pw2wannier90 step (pw2wannier90.x)
- w90_wannier step (wannier90.x)

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
    
    # Parse QE input files to extract parameters and cards correctly
    from quantumvitas.io import QEInputParser
    from quantumvitas.calculation.importers import _build_step_spec_from_qe_input_data
    from quantumvitas.io.structure_io import structure_from_qe_input
    
    scf_file = example_dir / "diamond.scf"
    nscf_file = example_dir / "diamond.nscf"
    scf_qe_input = QEInputParser.parse_file(scf_file)
    nscf_qe_input = QEInputParser.parse_file(nscf_file)
    
    # Extract structure from SCF input (as PMGStructure, convert to dict for snapshot)
    structure_pmg = structure_from_qe_input(scf_qe_input)
    
    # Parse the .win file
    win_input = Wannier90Input.from_string(win_content)
    pw2wan_input = Pw2Wannier90Input.from_string(pw2wan_content)
    
    # Build demo snapshot structure
    from quantumvitas.core.resources import generate_ulid
    structure_id = generate_ulid()
    structure = {
        "meta": {
            "id": structure_id,
            "name": "diamond",
            "slug": "diamond",
            "path": "structures/diamond.json",
            "kind": "structure",
        },
        "data": structure_pmg.as_dict(),  # Convert PMGStructure to dict
    }
    # Fix pbc tuple -> list for YAML serialization (safe_dump can't handle tuples)
    if "pbc" in structure["data"] and isinstance(structure["data"]["pbc"], tuple):
        structure["data"]["pbc"] = list(structure["data"]["pbc"])
    
    # Helper to create step specs
    def create_step_spec(step_type: str, index: int, seedname: str, params: Optional[Dict] = None, cards: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a step specification dictionary.

        Constitution §B: Persisted truth must be SPEC format (machine type).
        Uses canonical spec_from() for GEN→SPEC conversion.
        """
        from quantumvitas.workflow.step_type_convert import spec_from, is_spec

        step_id = generate_ulid()
        calc_slug = "diamond-mlwfs"

        # Convert GEN types to SPEC types for persistence (Constitution §B)
        # Use canonical spec_from() - no hardcoded mappings
        if is_spec(step_type):
            # Already SPEC format (e.g., w90_wannierprep)
            machine_type = step_type
        else:
            # GEN type - convert to SPEC using canonical function
            machine_type = spec_from("qe", step_type)

        spec = {
            "meta": {
                "id": step_id,
                "name": step_type,
                "slug": step_type,
                "path": f"calculations/{calc_slug}/steps/{step_type}.step.yaml",
                "kind": "step",
            },
            "step_type": machine_type,  # SPEC type (machine type) for persistence
            "index": index,
        }
        if params:
            spec["parameters"] = params
        if cards:
            spec["cards"] = cards
        return spec
    
    # Build steps using QE input parser for QE steps (ensures K_POINTS is in cards, not parameters)
    steps = []
    seedname = "diamond"
    calc_slug = "diamond-mlwfs"
    
    # SCF step: use _build_step_spec_from_qe_input_data to correctly extract parameters and cards
    scf_params, scf_cards = _build_step_spec_from_qe_input_data(scf_qe_input, "scf", apply_defaults=False)
    # Remove prefix/outdir from step parameters (injected from calculation.meta.slug)
    for section in scf_params:
        scf_params[section].pop("prefix", None)
        scf_params[section].pop("outdir", None)
    scf_step = create_step_spec("scf", 0, seedname, params=scf_params, cards=scf_cards)
    steps.append(scf_step)
    
    # NSCF step: use _build_step_spec_from_qe_input_data
    nscf_params, nscf_cards = _build_step_spec_from_qe_input_data(nscf_qe_input, "nscf", apply_defaults=False)
    # Remove prefix/outdir from step parameters
    for section in nscf_params:
        nscf_params[section].pop("prefix", None)
        nscf_params[section].pop("outdir", None)
    nscf_step = create_step_spec("nscf", 1, seedname, params=nscf_params, cards=nscf_cards)
    nscf_step["depends_on"] = [steps[0]["meta"]["id"]]
    steps.append(nscf_step)
    
    # W90 preprocessing step: generate .win file (kpoints handled via mp_grid and kpoints in .win)
    w90_preproc_params = {
        "seedname": seedname,
        "num_wann": win_input.num_wann,
        "num_iter": win_input.num_iter,
        "mp_grid": win_input.mp_grid,
        "projections_block": win_input.projections_block,
        "unit_cell_cart": win_input.unit_cell_cart,
        "atoms_frac": win_input.atoms_frac,
        # Note: kpoints handled via mp_grid in Wannier90, not as a separate parameter
        "wannier_plot": win_input.wannier_plot,
        "wannier_plot_supercell": win_input.wannier_plot_supercell,
    }
    w90_wannierprep_step = create_step_spec("w90_wannierprep", 2, seedname, params=w90_preproc_params)
    w90_wannierprep_step["depends_on"] = [steps[1]["meta"]["id"]]  # Depends on NSCF
    steps.append(w90_wannierprep_step)
    
    # pw2wannier90 step: remove prefix/outdir (injected from calculation level)
    pw2wan_params = {
        "seedname": pw2wan_input.seedname,
        # prefix and outdir removed - injected from calculation.meta.slug
        "write_mmn": pw2wan_input.write_mmn,
        "write_amn": pw2wan_input.write_amn,
        "write_unk": pw2wan_input.write_unk,
        "spin_component": pw2wan_input.spin_component,
    }
    pw2wan_step = create_step_spec("pw2wannier90", 3, seedname, params=pw2wan_params)
    pw2wan_step["depends_on"] = [steps[1]["meta"]["id"], steps[2]["meta"]["id"]]  # Depends on NSCF and w90_wannierprep
    steps.append(pw2wan_step)
    
    # W90 wannier step: generate .win file (same structure as w90_wannierprep)
    w90_wannier_params = {
        "seedname": seedname,
        "num_wann": win_input.num_wann,
        "num_iter": win_input.num_iter,
        "mp_grid": win_input.mp_grid,
        "projections_block": win_input.projections_block,
        "unit_cell_cart": win_input.unit_cell_cart,
        "atoms_frac": win_input.atoms_frac,
        # Note: kpoints handled via mp_grid in Wannier90
        "wannier_plot": win_input.wannier_plot,
        "wannier_plot_supercell": win_input.wannier_plot_supercell,
    }
    w90_wannier_step = create_step_spec("w90_wannier", 4, seedname, params=w90_wannier_params)
    w90_wannier_step["depends_on"] = [steps[3]["meta"]["id"]]  # Depends on pw2wannier90
    steps.append(w90_wannier_step)
    
    # Build the full snapshot (canonical format)
    project_id = generate_ulid()
    snapshot = {
        "version": "1",
        "project": {
            "meta": {
                "id": project_id,
                "name": "Diamond Wannier90 Demo",
                "slug": "diamond-wannier90-demo",
                "path": ".",
                "kind": "project",
            },
            "settings": {},
        },
        "structures": [structure],
        "calculations": [
            {
                "meta": {
                    "id": calc_id,
                    "name": "Diamond MLWFs",
                    "slug": calc_slug,
                    "path": f"calculations/{calc_slug}",
                    "kind": "calculation",
                },
                "mode": "normal",
                "working_dir": "raw",
                "structure_id": structure_id,
                "species_map": species_map,  # Calculation-level pseudo mapping (authoritative)
                "steps": steps,
            }
        ],
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
        yaml.safe_dump(snapshot, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


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
        print(f"    3. w90_wannierprep (wannier90.x -pp)")
        print(f"    4. pw2wannier90 (pw2wannier90.x)")
        print(f"    5. wannier (wannier90.x)")
        print()
        print("To run the demo:")
        print(f"  1. Load project in QMatSuite UI")
        print(f"  2. Or use CLI: qv run --project <demo_project_path>")
        print()
        print("Expected outputs:")
        print(f"  - diamond.nnkp (from wannierprep)")
        print(f"  - diamond.mmn, diamond.amn, diamond.eig (from pw2wannier90)")
        print(f"  - diamond.wout, diamond.chk (from wannier)")
        
        return 0
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

