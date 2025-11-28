"""
Dataclasses representing a QuantumVITAS project on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml

from quantumvitas.core.resources import (
    ResourceMeta,
    ResourceKind,
    ensure_relative_path,
    meta_from_name,
)


@dataclass(slots=True)
class ProjectSettings:
    """
    Global project settings (parallelism, default tolerances, etc.).

    Stored as a simple dictionary but exposed via a dataclass for type safety.
    """

    data: Dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.data.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value


@dataclass(slots=True)
class StructureRef:
    """
    Reference to a structure file inside the project.

    Structures are resolved relative to ``project.root / "structures"``.
    """

    meta: ResourceMeta
    absolute_path: Path
    format: str = "auto"  # e.g. "cif", "qe_input", "internal"

    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def slug(self) -> str:
        return self.meta.slug

    def relative_path(self) -> str:
        return self.meta.path

    @property
    def path(self) -> Path:
        return self.absolute_path

    def resolve_path(self, project_root: Path) -> Path:
        return self.meta.resolved_path(project_root)


@dataclass(slots=True)
class WorkflowRef:
    """
    Reference to a workflow folder (which is also the workflow workdir).
    """

    meta: ResourceMeta
    absolute_path: Path

    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def slug(self) -> str:
        return self.meta.slug

    def relative_path(self) -> str:
        return self.meta.path

    @property
    def path(self) -> Path:
        return self.absolute_path

    def resolve_path(self, project_root: Path) -> Path:
        return self.meta.resolved_path(project_root)


@dataclass(slots=True)
class Project:
    """
    Container for structures, workflows, pseudo potentials, and settings.
    """

    root: Path
    meta: ResourceMeta
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    structures: Dict[str, StructureRef] = field(default_factory=dict)
    workflows: Dict[str, WorkflowRef] = field(default_factory=dict)

    @classmethod
    def open(cls, project_root: Path | str) -> "Project":
        """
        Load project metadata from ``project.qv.yml``.
        """
        root = Path(project_root).resolve()
        config_file = root / "project.qv.yml"
        if not config_file.exists():
            raise FileNotFoundError(f"project.qv.yml not found under {root}")

        data = yaml.safe_load(config_file.read_text()) or {}
        project_section = data.get("project", {})
        project_name = project_section.get("name") or root.name
        project_meta = ResourceMeta.from_dict(
            project_section.get("meta"),
            kind="project",
            default_name=project_name,
            default_path=".",
        )

        settings = ProjectSettings(data.get("settings", {}))

        project = cls(root=root, meta=project_meta, settings=settings)
        project.structures = cls._load_structures(
            root, data.get("structures", []), project_section.get("structures_dir", "structures")
        )
        project.workflows = cls._load_workflows(
            root, data.get("workflows", []), project_section.get("workflows_dir", "workflows")
        )
        return project

    @staticmethod
    def _load_structures(
        root: Path, entries: list[dict], default_dir: str
    ) -> Dict[str, StructureRef]:
        structures: Dict[str, StructureRef] = {}
        for entry in entries:
            default_name = entry.get("name") or entry.get("id") or Path(
                entry.get("file") or "structure"
            ).stem
            default_path = entry.get("file") or f"{default_dir.rstrip('/')}/{default_name}.json"
            struct_meta = _entry_to_meta(
                entry=entry,
                root=root,
                kind="structure",
                default_path=default_path,
                default_name=default_name,
            )
            ref = StructureRef(
                meta=struct_meta,
                absolute_path=(root / struct_meta.path).resolve(),
                format=entry.get("format", "auto"),
            )
            structures[ref.slug] = ref
        return structures

    @staticmethod
    def _load_workflows(
        root: Path, entries: list[dict], default_dir: str
    ) -> Dict[str, WorkflowRef]:
        workflows: Dict[str, WorkflowRef] = {}
        for entry in entries:
            default_name = entry.get("name") or entry.get("id") or "workflow"
            default_path = entry.get("path") or f"{default_dir.rstrip('/')}/{default_name}"
            workflow_meta = _entry_to_meta(
                entry=entry,
                root=root,
                kind="workflow",
                default_path=default_path,
                default_name=default_name,
            )
            ref = WorkflowRef(
                meta=workflow_meta,
                absolute_path=(root / workflow_meta.path).resolve(),
            )
            workflows[ref.slug] = ref
        return workflows

    @property
    def structures_dir(self) -> Path:
        return self.root / "structures"

    @property
    def workflows_dir(self) -> Path:
        return self.root / "workflows"

    @property
    def pseudo_dir(self) -> Path:
        return self.root / "pseudo"

    @property
    def settings_file(self) -> Path:
        return self.root / "settings.yaml"

    def list_structures(self) -> list[str]:
        return [ref.meta.name for ref in self.structures.values()]

    def get_structure(self, structure_id: str) -> StructureRef:
        # Accept slug, name, or meta id for ergonomics
        if structure_id in self.structures:
            return self.structures[structure_id]

        for ref in self.structures.values():
            if ref.meta.id == structure_id or ref.meta.name == structure_id:
                return ref
        raise KeyError(f"Unknown structure '{structure_id}'")

    def list_workflows(self) -> list[str]:
        return [ref.meta.name for ref in self.workflows.values()]

    def get_workflow_ref(self, workflow_id: str) -> WorkflowRef:
        if workflow_id in self.workflows:
            return self.workflows[workflow_id]
        for ref in self.workflows.values():
            if ref.meta.id == workflow_id or ref.meta.name == workflow_id:
                return ref
        raise KeyError(f"Unknown workflow '{workflow_id}'")

    def get_workflow(self, workflow_id: str):
        """
        Load and return a workflow instance.
        """
        from quantumvitas.workflow.workflow import Workflow

        ref = self.get_workflow_ref(workflow_id)
        return Workflow.from_yaml(ref.resolve_path(self.root), self)

    def structure_ref(self, name: str) -> StructureRef:
        """
        Return a structure reference relative to the structures directory.
        """
        structure_path = self.structures_dir / name
        meta = meta_from_name(
            "structure",
            name=name,
            path=ensure_relative_path(structure_path, base=self.root),
        )
        return StructureRef(meta=meta, absolute_path=structure_path.resolve())


def _entry_to_meta(
    *,
    entry: dict,
    root: Path,
    kind: ResourceKind,
    default_path: str,
    default_name: str,
) -> ResourceMeta:
    path_obj = Path(default_path)
    if path_obj.is_absolute():
        try:
            path_obj = path_obj.relative_to(root)
        except ValueError:
            pass
    relative_path = path_obj.as_posix()

    return ResourceMeta.from_dict(
        entry.get("meta"),
        kind=kind,
        default_name=default_name,
        default_path=relative_path,
    )

