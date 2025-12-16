"""
Unit tests for online structure import functionality.

Tests that online structures can be imported into projects with unique names/slugs.
"""

import pytest
import tempfile
import json
from pathlib import Path
from pymatgen.core import Structure, Lattice

from quantumvitas.core.project_utils import load_project_config, save_project_config, collect_slugs
from quantumvitas.core.resources import generate_unique_name_and_slug
from quantumvitas.io.structure_io import write_structure, read_structure


def test_import_online_candidate_unique_slug():
    """
    Test that importing an online candidate generates a unique slug when conflicts exist.
    
    Scenario:
    - Create a temp project with one structure slug "silicon"
    - Import an online candidate with name hint "Silicon"
    - Assert: import succeeds; new structure file exists; slug is unique and not colliding
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create project structure
        project_config = {
            "name": "test_project",
            "structures": [
                {
                    "structure_id": "test-id-1",
                    "meta": {
                        "name": "Silicon",
                        "slug": "silicon",
                    }
                }
            ]
        }
        
        # Write project config
        config_path = project_root / "project.qv.yml"
        import yaml
        with open(config_path, 'w') as f:
            yaml.dump(project_config, f)
        
        # Create structures directory and existing structure file
        structures_dir = project_root / "structures"
        structures_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a simple structure for the existing "silicon" entry
        existing_structure = Structure(
            Lattice.cubic(5.43),
            ["Si", "Si"],
            [[0, 0, 0], [0.25, 0.25, 0.25]]
        )
        write_structure(existing_structure, structures_dir / "silicon.json")
        
        # Load project config
        config = load_project_config(project_root)
        structures = config.setdefault("structures", [])
        
        # Collect existing slugs
        existing_slugs = collect_slugs(structures, project_root=project_root)
        assert "silicon" in existing_slugs, "Existing slug 'silicon' should be found"
        
        # Simulate importing an online candidate with name "Silicon"
        # This should generate a unique slug (e.g., "silicon-2")
        name_hint = "Silicon"
        final_name, final_slug = generate_unique_name_and_slug(
            kind="structure",
            preferred_name=name_hint,
            existing_slugs=existing_slugs,
        )
        
        # Assert slug is unique
        assert final_slug != "silicon", f"Slug should be unique, got '{final_slug}'"
        assert final_slug.lower() not in [s.lower() for s in existing_slugs], \
            f"Slug '{final_slug}' should not conflict with existing slugs: {existing_slugs}"
        
        # Assert name is reasonable
        assert "Silicon" in final_name or "silicon" in final_name.lower(), \
            f"Name should contain 'Silicon', got '{final_name}'"
        
        # Create the new structure file
        new_structure = Structure(
            Lattice.cubic(5.43),
            ["Si", "Si"],
            [[0, 0, 0], [0.25, 0.25, 0.25]]
        )
        new_structure_path = structures_dir / f"{final_slug}.json"
        write_structure(new_structure, new_structure_path)
        
        # Assert file exists
        assert new_structure_path.exists(), f"Structure file should exist: {new_structure_path}"
        
        # Assert we can read it back
        loaded_structure = read_structure(new_structure_path)
        assert len(loaded_structure) == 2, "Loaded structure should have 2 sites"
        
        # Verify slug uniqueness by checking all structure files
        all_slugs = []
        for struct_file in structures_dir.glob("*.json"):
            slug_from_file = struct_file.stem
            all_slugs.append(slug_from_file)
        
        assert len(set(all_slugs)) == len(all_slugs), \
            f"All structure slugs should be unique, found duplicates: {all_slugs}"
