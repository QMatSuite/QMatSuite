#!/usr/bin/env python3
"""
Generate ORCA demo projects from definitions.

Reads demo definitions from tools/orca_demo_definitions.yaml and generates
QMatSuite demo project YAML files.

Usage:
    python tools/demo_generators/verified/generate_orca_demos.py

Output:
    resources/demo_projects/{demo_id}.yml
    resources/demo_projects/orca_demo_index.json
"""

import json
import yaml
from pathlib import Path
import sys

# Add src to path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from quantumvitas.core.resources import generate_resource_id


def load_demo_definitions() -> dict:
    """Load demo definitions from YAML file."""
    definitions_path = REPO_ROOT / "tools" / "demo_generators" / "verified" / "orca_demo_definitions.yaml"
    with open(definitions_path, "r") as f:
        return yaml.safe_load(f)


def generate_project_meta(demo_id: str, title: str) -> dict:
    """Generate project metadata."""
    return {
        "id": generate_resource_id(),
        "name": title,
        "slug": demo_id.replace("_", "-"),
        "path": ".",
        "kind": "project",
    }


def generate_structure_meta(molecule_name: str, demo_id: str) -> dict:
    """Generate structure metadata."""
    return {
        "id": generate_resource_id(),
        "name": molecule_name,
        "slug": molecule_name.lower().replace(" ", "-"),
        "path": f"structures/{molecule_name.lower().replace(' ', '_')}.json",
        "kind": "structure",
    }


def generate_structure_data(molecule: dict) -> dict:
    """Generate structure data from molecule definition.
    
    Returns pymatgen Molecule-compatible format.
    For molecules, we need to convert atoms list to pymatgen format.
    """
    from pymatgen.core import Molecule
    
    # Extract species and coords
    species = [atom["element"] for atom in molecule["atoms"]]
    coords = [atom["coords"] for atom in molecule["atoms"]]
    
    # Create pymatgen Molecule
    mol = Molecule(
        species=species,
        coords=coords,
        charge=molecule["charge"],
        spin_multiplicity=molecule.get("spin", 0) + 1,  # pymatgen uses multiplicity (2S+1)
    )
    
    # Return pymatgen dict format (has @module, @class, sites, charge, etc.)
    return mol.as_dict()


def generate_step_meta(step_name: str, step_type: str, calc_slug: str) -> dict:
    """Generate step metadata."""
    return {
        "id": generate_resource_id(),
        "name": step_name,
        "slug": step_name.replace("_", "-"),
        "path": f"calculations/{calc_slug}/steps/{step_name}.step.yaml",
        "kind": "step",
    }


def generate_step_spec(step_def: dict, structure_id: str) -> dict:
    """Generate step specification from step definition.

    Constitution §B: Persisted truth must be SPEC format (machine type).
    GEN types from definitions are converted to SPEC types for persistence.
    """
    # Convert GEN type to SPEC type for ORCA
    gen_type = step_def["step_type"]
    spec_type = f"orca_{gen_type}"  # e.g., "scf" -> "orca_scf"

    params = step_def["parameters"].copy()

    # Build step spec with SPEC type (machine type)
    spec = {
        "step_type": spec_type,  # SPEC type (machine type) for persistence
        "parameters": params,
    }

    return spec


def generate_calculation_meta(calc_name: str, demo_id: str) -> dict:
    """Generate calculation metadata."""
    return {
        "id": generate_resource_id(),
        "name": calc_name,
        "slug": calc_name.lower().replace(" ", "-").replace("+", "-plus"),
        "path": f"calculations/{calc_name.lower().replace(' ', '-').replace('+', '-plus')}",
        "kind": "calculation",
    }


def generate_demo_project(demo_def: dict) -> dict:
    """Generate a complete demo project from definition."""
    demo_id = demo_def["id"]
    molecule = demo_def["molecule"]
    calculation = demo_def["calculation"]
    
    # Generate IDs
    project_meta = generate_project_meta(demo_id, demo_def["title"])
    structure_meta = generate_structure_meta(molecule["name"], demo_id)
    structure_data = generate_structure_data(molecule)
    calculation_meta = generate_calculation_meta(calculation["name"], demo_id)
    
    # Generate steps
    steps = []
    for step_def in calculation["steps"]:
        step_meta = generate_step_meta(
            step_def["name"],
            step_def["step_type"],
            calculation_meta["slug"]
        )
        step_spec = generate_step_spec(step_def, structure_meta["id"])
        
        step = {
            "meta": step_meta,
            **step_spec,
        }
        steps.append(step)
    
    # Build complete project
    project = {
        "version": 1,
        "project": {
            "meta": project_meta,
            "settings": {},
        },
        "structures": [
            {
                "meta": structure_meta,
                "data": structure_data,
            }
        ],
        "calculations": [
            {
                "meta": calculation_meta,
                "mode": "normal",
                "working_dir": "raw",
                "structure_id": structure_meta["id"],
                "structure_kind": "molecule",  # ORCA is for molecular systems
                "engine_family": "orca",  # Explicitly set ORCA engine family
                "steps": steps,
            }
        ],
        "meta": {
            "id": demo_id,
            "title": demo_def["title"],
            "subtitle": demo_def["subtitle"],
            "tags": demo_def["tags"],
            "recommended_analysis": demo_def["recommended_analysis"],
            "difficulty": demo_def["difficulty"],
        },
    }
    
    return project


def generate_readme(demo_def: dict, demo_id: str) -> str:
    """Generate README.md content for a demo."""
    molecule = demo_def["molecule"]
    calculation = demo_def["calculation"]
    expected_outputs = demo_def.get("expected_outputs", [])
    runtime = demo_def.get("runtime_estimate", "Unknown")
    
    readme = f"""# {demo_def['title']}

{demo_def['subtitle']}

## Overview

This demo demonstrates a {calculation['name']} calculation using ORCA.

**Molecule**: {molecule['name']}  
**Method**: {calculation['steps'][0]['parameters'].get('method', 'DFT')}  
**Basis**: {calculation['steps'][0]['parameters'].get('basis', 'def2-SVP')}  
**Runtime**: {runtime}

## What It Computes

"""
    
    # Check step types (definitions use GEN types like "scf")
    step_types = [s["step_type"] for s in calculation["steps"]]
    if "scf" in step_types:
        readme += "- Single-point energy calculation\n"

    if "td" in step_types:
        readme += "- Excited states via TDDFT\n"

    if "freq" in step_types:
        readme += "- Vibrational frequencies and normal modes\n"
    
    readme += f"""
## Required Engine

- **ORCA**: Must be installed and available in PATH or configured in QMatSuite settings

## How to Run

### Via CLI

```bash
# Create project from demo
qv create-demo-project --demo-id {demo_id}

# Or specify target directory
qv create-demo-project /path/to/project --demo-id {demo_id}

# Run calculation
qv run calc {demo_id.replace('_', '-')}
```

### Via GUI

1. Open QMatSuite GUI
2. Navigate to Demo Gallery
3. Select "{demo_def['title']}"
4. Click "Create Project"
5. Click "Run" on the calculation

## Expected Outputs

After running, you should find the following files in `calculations/*/raw/qc_chains/scf_*/`:

"""
    
    for output in expected_outputs:
        readme += f"- `{output}`\n"
    
    readme += f"""
## Output Files Description

"""
    
    if "s.out" in expected_outputs or "s_t.out" in expected_outputs or "s_f.out" in expected_outputs:
        readme += "- **`.out`**: ORCA text output with calculation details, energies, and convergence information\n"
    
    if "s.property.txt" in expected_outputs or "s_t.property.txt" in expected_outputs or "s_f.property.txt" in expected_outputs:
        readme += "- **`.property.txt`**: Structured properties file (JSON-like format) with energies, geometries, and computed properties\n"
    
    if "scf.gbw" in expected_outputs:
        readme += "- **`scf.gbw`**: ORCA wavefunction file (binary format)\n"
    
    if "s_f.hess" in expected_outputs:
        readme += "- **`s_f.hess`**: Hessian matrix for frequency calculation\n"
    
    readme += f"""
## Documentation Reference

This demo is based on ORCA documentation:
- Source: `{demo_def.get('doc_source', 'ORCA Manual')}`

## Tags

{', '.join(demo_def['tags'])}

## Difficulty

**{demo_def['difficulty'].title()}** - {demo_def['subtitle']}
"""
    
    return readme


def main():
    """Main entry point."""
    # Load definitions
    definitions = load_demo_definitions()
    demos = definitions["demos"]
    
    # Output directory
    output_dir = REPO_ROOT / "resources" / "demo_projects"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate each demo
    generated_demos = []
    total_files = 0
    
    for demo_def in demos:
        demo_id = demo_def["id"]
        print(f"Generating demo: {demo_id}...")
        
        # Generate project YAML
        project = generate_demo_project(demo_def)
        yaml_path = output_dir / f"{demo_id}.yml"
        
        with open(yaml_path, "w") as f:
            yaml.dump(project, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        total_files += 1
        
        # Generate README
        readme_content = generate_readme(demo_def, demo_id)
        readme_path = output_dir / f"{demo_id}_README.md"
        
        with open(readme_path, "w") as f:
            f.write(readme_content)
        
        total_files += 1
        
        # Record in index
        generated_demos.append({
            "id": demo_id,
            "title": demo_def["title"],
            "yaml_file": f"{demo_id}.yml",
            "readme_file": f"{demo_id}_README.md",
            "tags": demo_def["tags"],
            "difficulty": demo_def["difficulty"],
        })
    
    # Write demo index
    index_data = {
        "generated_at": str(Path(__file__).stat().st_mtime),
        "total_demos": len(generated_demos),
        "demos": generated_demos,
    }
    
    index_path = output_dir / "orca_demo_index.json"
    with open(index_path, "w") as f:
        json.dump(index_data, f, indent=2)
    
    total_files += 1
    
    # Print summary
    print("\n" + "=" * 60)
    print("Demo Generation Summary")
    print("=" * 60)
    print(f"Demos generated: {len(generated_demos)}")
    print(f"Total files created: {total_files}")
    print(f"Output directory: {output_dir}")
    print("\nGenerated demos:")
    for demo in generated_demos:
        print(f"  - {demo['id']}: {demo['title']}")
    print(f"\nIndex file: {index_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()

