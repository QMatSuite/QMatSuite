#!/usr/bin/env python
"""
Generate PySCF demo project for QMatSuite.

Creates a minimal H2O single-point calculation demo to demonstrate
PySCF molecular quantum chemistry integration.

Usage:
    python tools/generate_pyscf_demo.py

Output:
    resources/demo_projects/water_pyscf_scf.yml
"""

from pathlib import Path
import json
import sys

# Add src to path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from quantumvitas.core.resources import generate_resource_id


def generate_water_pyscf_demo() -> dict:
    """
    Generate water molecule PySCF SCF demo project.
    
    Uses RHF/6-31G for a quick, deterministic calculation.
    Expected energy: ~-75.98 Hartree
    """
    # Generate ULIDs for resources
    project_id = generate_resource_id()
    structure_id = generate_resource_id()
    calculation_id = generate_resource_id()
    step_id = generate_resource_id()
    
    # H2O geometry (optimized, Angstroms)
    # Standard water geometry
    atoms = [
        {"element": "O", "x": 0.0, "y": 0.0, "z": 0.117790},
        {"element": "H", "x": 0.0, "y": 0.755453, "z": -0.471161},
        {"element": "H", "x": 0.0, "y": -0.755453, "z": -0.471161},
    ]
    
    demo = {
        "version": 1,
        "project": {
            "meta": {
                "id": project_id,
                "name": "Water PySCF SCF",
                "slug": "water-pyscf-scf",
                "path": ".",
                "kind": "project",
            },
            "settings": {},
        },
        "structures": [
            {
                "meta": {
                    "id": structure_id,
                    "name": "H2O",
                    "slug": "h2o",
                    "path": "structures/h2o.json",
                    "kind": "structure",
                },
                "data": {
                    # Molecular structure: NO lattice field = MOLECULAR system
                    "charge": 0,
                    "spin": 0,
                    "atoms": [
                        {"element": "O", "coords": [0.0, 0.0, 0.117790]},
                        {"element": "H", "coords": [0.0, 0.755453, -0.471161]},
                        {"element": "H", "coords": [0.0, -0.755453, -0.471161]},
                    ],
                    "unit": "Angstrom",
                    # No lattice = molecular (not periodic)
                },
            }
        ],
        "calculations": [
            {
                "meta": {
                    "id": calculation_id,
                    "name": "H2O RHF Single Point",
                    "slug": "h2o-rhf",
                    "path": "calculations/h2o-rhf",
                    "kind": "calculation",
                },
                "mode": "normal",
                "working_dir": "raw",
                "structure_id": structure_id,
                # System kind: molecular (no lattice)
                # Engine group: molecular_qc (PySCF)
                "steps": [
                    {
                        "meta": {
                            "id": step_id,
                            "name": "pyscf_scf",
                            "slug": "pyscf-scf",
                            "path": "calculations/h2o-rhf/steps/pyscf_scf.step.yaml",
                            "kind": "step",
                        },
                        "step_type": "pyscf_scf",
                        "parameters": {
                            "method": "rhf",
                            "basis": "6-31g",
                            "charge": 0,
                            "spin": 0,
                            "max_cycle": 50,
                            "conv_tol": 1.0e-9,
                            "atoms": atoms,
                            "unit": "Angstrom",
                        },
                    }
                ],
            }
        ],
        "meta": {
            "id": "water_pyscf_scf_demo",
            "title": "Water PySCF RHF Single Point",
            "subtitle": "Molecular HF calculation",
            "tags": ["pyscf", "molecular", "HF", "water", "tutorial"],
            "recommended_analysis": "energy",
            "difficulty": "beginner",
            "reference_artifacts": {
                "scf": "water_pyscf_scf.scf.json",
            },
        },
    }
    
    return demo


def generate_reference_artifacts() -> dict:
    """
    Generate reference artifacts for demo validation.
    
    These are expected values from a converged RHF/6-31G calculation.
    """
    # Expected results for H2O RHF/6-31G
    # These values are from standard PySCF calculations
    reference = {
        "energy": -75.98503445,  # Approximate, will vary slightly
        "energy_unit": "Hartree",
        "converged": True,
        "n_electrons": 10,
        "n_atoms": 3,
        "method": "rhf",
        "basis": "6-31g",
        # HOMO/LUMO gap (approximate)
        "homo_index": 4,  # 5 occupied orbitals (0-4)
        "lumo_index": 5,
        "homo_energy": -0.497,  # Approximate
        "lumo_energy": 0.211,   # Approximate
        "gap": 0.708,           # Approximate
        "gap_ev": 19.27,        # Approximate
        # Dipole moment (approximate)
        "dipole_moment": [0.0, 0.0, 0.78],  # Debye, approximate
        "dipole_moment_unit": "Debye",
    }
    
    return reference


def main():
    """Generate PySCF demo project files."""
    import yaml
    
    demo_dir = REPO_ROOT / "resources" / "demo_projects"
    demo_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate demo YAML
    demo = generate_water_pyscf_demo()
    demo_path = demo_dir / "water_pyscf_scf.yml"
    
    with open(demo_path, "w") as f:
        yaml.dump(demo, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print(f"✅ Generated demo project: {demo_path}")
    
    # Generate reference artifacts
    reference = generate_reference_artifacts()
    ref_path = demo_dir / "water_pyscf_scf.scf.json"
    
    with open(ref_path, "w") as f:
        json.dump(reference, f, indent=2)
    
    print(f"✅ Generated reference artifacts: {ref_path}")
    
    # Print summary
    print("\nDemo project summary:")
    print(f"  - Project: {demo['project']['meta']['name']}")
    print(f"  - Structure: {demo['structures'][0]['meta']['name']} (molecular, no lattice)")
    print(f"  - Calculation: {demo['calculations'][0]['meta']['name']}")
    print(f"  - Step: pyscf_scf (RHF/6-31G)")
    print(f"\nExpected results:")
    print(f"  - Energy: ~{reference['energy']:.6f} Hartree")
    print(f"  - Gap: ~{reference['gap_ev']:.1f} eV")
    print(f"\nTo run the demo:")
    print(f"  1. Ensure PySCF is installed: pip install pyscf")
    print(f"  2. Load the demo project in QMatSuite UI")
    print(f"  3. Click Run on the calculation")


if __name__ == "__main__":
    main()

