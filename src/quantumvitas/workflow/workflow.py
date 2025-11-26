"""
Workflow representation (loaded from workflow.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

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

    @property
    def raw_dir(self) -> Path:
        return self.io.raw_dir

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

        steps: List[Step] = []
        for step_data in data.get("steps", []):
            step = _build_step(step_data, workflow_dir, project)
            steps.append(step)

        return cls(
            id=workflow_id,
            project=project,
            dir=workflow_dir,
            mode=mode,
            steps=steps,
            io=WorkflowIO(workflow_dir),
        )


def _build_step(step_data: dict, workflow_dir: Path, project: Project) -> Step:
    step_id = step_data["id"]
    step_type = StepType(step_data["type"])
    structure_name = step_data.get("structure")
    structure_ref: StructureRef | None = None
    if structure_name:
        structure_ref = project.structure_ref(structure_name)
    reference = step_data.get("reference")
    reference_path = (
        workflow_dir / reference if reference is not None else None
    )
    return Step(
        id=step_id,
        type=step_type,
        engine=step_data.get("engine", "qe"),
        structure=structure_ref,
        parameters=step_data.get("params", {}),
        reference_output=reference_path,
    )

