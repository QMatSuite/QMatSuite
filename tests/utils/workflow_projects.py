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

    project_config = {
        "project": {"name": project_root.name},
        "workflows": [{"id": workflow_id, "path": f"workflows/{workflow_id}"}],
        "structures": [],
        "settings": {},
    }
    (project_root / "project.qv.yml").write_text(
        yaml.safe_dump(project_config, sort_keys=False)
    )

    workflow_config = {
        "id": workflow_id,
        "mode": "strict",
        "workflow": {"working_dir": "raw"},
        "steps": [
            {
                "id": step["id"],
                "input": step["input"],
                **({"reference": f"reference/{step['reference']}"} if step.get("reference") else {}),
            }
            for step in steps
        ],
    }
    (workflow_dir / "workflow.yaml").write_text(
        yaml.safe_dump(workflow_config, sort_keys=False)
    )

    return project_root

