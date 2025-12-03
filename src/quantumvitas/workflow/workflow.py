"""
Workflow representation (loaded from workflow.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from quantumvitas.core.resources import ResourceMeta, ensure_relative_path
from quantumvitas.project.model import Project, StructureRef
from .types import StepMode, StepType
from .step import Step
from .io import WorkflowIO
from .structure_steps import StructureStepSpec, materialize_step_spec


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
            step = _build_step(step_data, workflow_dir, working_dir, project)
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


def _build_step(
    step_data: dict,
    workflow_dir: Path,
    working_dir: Path,
    project: Project,
) -> Step:
    step_id = step_data["id"]
    engine_name = step_data.get("engine", "qe")

    step_file_value = step_data.get("step_file")
    input_path_value = step_data.get("input") or step_data.get("file")
    if not step_file_value and not input_path_value:
        raise ValueError(f"Step '{step_id}' requires an 'input' path or 'step_file'")
    input_path: Optional[Path] = None
    if input_path_value:
        input_path = Path(input_path_value)
        if not input_path.is_absolute():
            parts = input_path.parts
            if parts and parts[0] == working_dir.name:
                if len(parts) == 1:
                    raise ValueError(
                        f"Step '{step_id}' input path must point to a file inside '{working_dir.name}'"
                    )
                input_path = Path(*parts[1:])

    options = step_data.get("options", step_data.get("params", {})) or {}
    reference_path = _resolve_reference_path(step_data.get("reference"), workflow_dir)

    step_meta = _build_step_meta(
        step_data=step_data,
        workflow_dir=workflow_dir,
        project=project,
    )

    if step_file_value:
        return _build_step_from_spec(
            step_id=step_id,
            engine_name=engine_name,
            step_file=step_file_value,
            workflow_dir=workflow_dir,
            working_dir=working_dir,
            project=project,
            options=options,
            reference=reference_path,
            step_meta=step_meta,
        )

    step_type = StepType(step_data["type"]) if "type" in step_data else None

    return Step(
        meta=step_meta,
        input_file=input_path,
        engine=engine_name,
        step_type=step_type,
        options=options,
        reference_output=reference_path,
    )


def _input_file_extension(step_type: str) -> str:
    """
    Get appropriate file extension based on step type.
    
    Returns .in for all QE modules (simpler naming), but with a prefix
    that indicates the module:
    - pw.x steps: scf, nscf, relax, vc-relax, md, bands_pw -> .in
    - bands.x: bands -> .bands.in
    - dos.x: dos -> .dos.in
    - Other post-processing: pp, projwfc -> .<type>.in
    """
    # Post-processing modules get their own suffix
    POST_PROC_TYPES = {"dos", "bands", "pp", "projwfc", "ph", "q2r", "matdyn", "dynmat"}
    
    if step_type.lower() in POST_PROC_TYPES:
        return f".{step_type.lower()}.in"
    
    # Default for pw.x calculations
    return ".in"


def _build_step_from_spec(
    *,
    step_id: str,
    engine_name: str,
    step_file: str,
    workflow_dir: Path,
    working_dir: Path,
    project: Project,
    options: dict,
    reference: Optional[Path],
    step_meta: ResourceMeta,
) -> Step:
    spec_path = Path(step_file)
    if not spec_path.is_absolute():
        spec_path = (workflow_dir / spec_path).resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"Step spec not found: {spec_path}")

    spec_preview = StructureStepSpec.from_yaml(spec_path)
    # Determine appropriate file extension based on step type
    ext = _input_file_extension(spec_preview.step_type)
    input_override = spec_preview.input_name or f"{step_id}{ext}"
    generated_input, spec = materialize_step_spec(
        spec_preview,
        output_dir=working_dir,
        workflow_dir=workflow_dir,
        project=project,
        spec_path=spec_path,
        input_name=input_override,
        project_root=project.root if project else None,
    )

    step_type = _coerce_step_type(spec.step_type)

    return Step(
        meta=step_meta,
        input_file=generated_input,
        engine=engine_name,
        step_type=step_type,
        options=options,
        reference_output=reference,
    )


def _coerce_step_type(raw: Optional[str]) -> Optional[StepType]:
    if not raw:
        return None
    try:
        return StepType(raw)
    except ValueError:
        return StepType.CUSTOM


def _resolve_reference_path(reference: Optional[str], workflow_dir: Path) -> Optional[Path]:
    if not reference:
        return None
    reference_path = Path(reference)
    if not reference_path.is_absolute():
        reference_path = (workflow_dir / reference_path).resolve()
    return reference_path


def _build_step_meta(
    *,
    step_data: dict,
    workflow_dir: Path,
    project: Project,
) -> ResourceMeta:
    name = step_data.get("name") or step_data.get("id") or "step"
    default_path = step_data.get("path") or _default_step_path(
        workflow_dir=workflow_dir, project=project, step_name=name
    )
    return ResourceMeta.from_dict(
        step_data.get("meta"),
        kind="step",
        default_name=name,
        default_path=default_path,
    )


def _default_step_path(*, workflow_dir: Path, project: Project, step_name: str) -> str:
    """
    Steps live under ``workflows/<id>/steps`` by default. This helper makes sure
    we keep the path relative to the project root.
    """
    base = workflow_dir
    try:
        workflow_rel = ensure_relative_path(base, base=project.root)
    except ValueError:
        workflow_rel = base.name
    return f"{workflow_rel.rstrip('/')}/steps/{step_name}"

