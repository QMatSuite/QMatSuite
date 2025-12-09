"""
Helpers for scaffolding temporary workflow projects inside tests.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import yaml
from typing import Sequence, Dict, Any


def create_workflow_project(
    project_root: Path,
    workflow_id: str,
    steps: Sequence[Dict[str, Any]],
    source_dir: Path,
    pseudo_src: Path,
) -> Path:
    """
    Create a minimal project layout under ``project_root`` with a single workflow.

    Args:
        project_root: Destination directory (will be created/overwritten).
        workflow_id: Name of the workflow folder/id.
        input_files: Iterable of QE input filenames to copy into ``raw/``.
        reference_files: Mapping of step ids -> reference filename in ``reference/``.
        source_dir: Directory containing the source ``.in`` and reference files.
        pseudo_src: Directory containing pseudopotentials (copied into project).

    Returns:
        Path to the created project root.
    """

    if project_root.exists():
        shutil.rmtree(project_root)
    workflow_dir = project_root / "workflows" / workflow_id
    raw_dir = workflow_dir / "raw"
    reference_dir = workflow_dir / "reference"
    raw_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)

    for step in steps:
        input_name = step["input"]
        shutil.copy2(source_dir / input_name, raw_dir / input_name)
        reference_name = step.get("reference")
        if reference_name:
            dest = reference_dir / reference_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_dir / "reference" / reference_name, dest)

    shutil.copytree(pseudo_src, project_root / "pseudo")

    # Create a minimal structure for the workflow (required for steps)
    from quantumvitas.core.resources import generate_resource_id, meta_from_name
    structure_id = generate_resource_id()
    structure_meta = meta_from_name("structure", name="test_structure", path="structures/test_structure.json")
    structure_meta.id = structure_id
    
    structures_dir = project_root / "structures"
    structures_dir.mkdir(parents=True, exist_ok=True)
    from quantumvitas.io.structure_io import STRUCTURE_META_KEY, STRUCTURE_DATA_KEY
    import json
    structure_json = {
        STRUCTURE_META_KEY: structure_meta.to_dict(),
        STRUCTURE_DATA_KEY: {
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[5.43, 0.0, 0.0], [0.0, 5.43, 0.0], [0.0, 0.0, 5.43]]},
            "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0.0, 0.0, 0.0]}],
        },
    }
    (structures_dir / "test_structure.json").write_text(json.dumps(structure_json, indent=2))
    
    project_config = {
        "project": {"name": project_root.name},
        "workflows": [{"id": workflow_id, "path": f"workflows/{workflow_id}"}],
        "structures": [
            {
                "id": structure_id,
                "file": "structures/test_structure.json",
                "meta": structure_meta.to_dict(),
            }
        ],
        "settings": {},
    }
    (project_root / "project.qv.yml").write_text(
        yaml.safe_dump(project_config, sort_keys=False)
    )

    # Create step files with proper meta (ID-only model)
    from quantumvitas.core.resources import generate_resource_id, meta_from_name
    steps_dir = workflow_dir / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    
    step_entries = []
    for step in steps:
        step_id = step["id"]
        step_ulid = generate_resource_id()
        step_file = steps_dir / f"{step_id}.step.yaml"
        step_meta = meta_from_name("step", name=step_id, path=f"workflows/{workflow_id}/steps/{step_id}.step.yaml")
        step_meta.id = step_ulid
        
        # Create minimal step spec with structure_id
        step_spec = {
            "meta": step_meta.to_dict(),
            "step_type": step_id,  # Use step id as step_type (scf, nscf, dos, etc.)
            "structure_id": structure_id,  # Reference to the test structure
        }
        step_file.write_text(yaml.safe_dump(step_spec, sort_keys=False))
        
        # Create step entry with step_id (ULID)
        step_entry = {
            "step_id": step_ulid,
            "input": step["input"],
        }
        if step.get("reference"):
            step_entry["reference"] = f"reference/{step['reference']}"
        step_entries.append(step_entry)
    
    workflow_config = {
        "id": workflow_id,
        "mode": "strict",
        "workflow": {"working_dir": "raw"},
        "structure_id": structure_id,  # Workflow-level structure reference
        "steps": step_entries,
    }
    (workflow_dir / "workflow.yaml").write_text(
        yaml.safe_dump(workflow_config, sort_keys=False)
    )

    return project_root

