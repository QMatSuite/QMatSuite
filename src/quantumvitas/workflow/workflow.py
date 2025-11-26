"""
Workflow representation (loaded from workflow.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from quantumvitas.project.model import Project, StructureRef
from .types import StepMode, StepType
from .step import Step
from .io import WorkflowIO


@dataclass(slots=True)
class Workflow:
    id: str
    project: Project
    dir: Path
    mode: StepMode
    steps: List[Step]
    io: WorkflowIO
    structure: Optional[StructureRef] = None
    working_dir: Path = field(default_factory=Path)

    @property
    def raw_dir(self) -> Path:
        return self.working_dir

    @property
    def reference_dir(self) -> Path:
        return self.io.reference_dir

    @property
    def results_dir(self) -> Path:
        return self.io.results_dir

    @classmethod
    def from_yaml(cls, workflow_dir: Path, project: Project) -> "Workflow":
        workflow_yaml = workflow_dir / "workflow.yaml"
        if not workflow_yaml.exists():
            raise FileNotFoundError(f"workflow.yaml not found: {workflow_yaml}")

        data = yaml.safe_load(workflow_yaml.read_text())
        workflow_id = data.get("id", workflow_dir.name)
        mode = StepMode(data.get("mode", StepMode.NORMAL.value))

        workflow_meta = data.get("workflow", {})
        structure_id = workflow_meta.get("structure")
        structure_ref: Optional[StructureRef] = None
        if structure_id:
            structure_ref = project.get_structure(structure_id)

        raw_subdir = workflow_meta.get("working_dir", "raw")
        working_dir = (workflow_dir / raw_subdir).resolve()

        steps: List[Step] = []
        for step_data in data.get("steps", []):
            step = _build_step(step_data, workflow_dir, working_dir)
            steps.append(step)

        return cls(
            id=workflow_id,
            project=project,
            dir=workflow_dir,
            mode=mode,
            steps=steps,
            io=WorkflowIO(workflow_dir, raw_subdir=raw_subdir),
            structure=structure_ref,
            working_dir=working_dir,
        )


def _build_step(step_data: dict, workflow_dir: Path, working_dir: Path) -> Step:
    step_id = step_data["id"]
    engine_name = step_data.get("engine", "qe")

    input_path_value = step_data.get("input") or step_data.get("file")
    if not input_path_value:
        raise ValueError(f"Step '{step_id}' requires an 'input' path")
    input_path = Path(input_path_value)
    if not input_path.is_absolute():
        parts = input_path.parts
        if parts and parts[0] == working_dir.name:
            if len(parts) == 1:
                raise ValueError(f"Step '{step_id}' input path must point to a file inside '{working_dir.name}'")
            input_path = Path(*parts[1:])

    step_type = StepType(step_data["type"]) if "type" in step_data else None
    options = step_data.get("options", step_data.get("params", {})) or {}
    reference = step_data.get("reference")
    if reference:
        reference_path = (workflow_dir / reference).resolve() if not Path(reference).is_absolute() else Path(reference)
    else:
        reference_path = None

    return Step(
        id=step_id,
        input_file=input_path,
        engine=engine_name,
        step_type=step_type,
        options=options,
        reference_output=reference_path,
    )

