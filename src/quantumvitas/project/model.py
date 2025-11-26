"""
Dataclasses representing a QuantumVITAS project on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml


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

    name: str
    path: Path
    format: str = "auto"  # e.g. "cif", "qe_input", "internal"


@dataclass(slots=True)
class WorkflowRef:
    """
    Reference to a workflow folder (which is also the workflow workdir).
    """

    name: str
    path: Path


@dataclass(slots=True)
class Project:
    """
    Container for structures, workflows, pseudo potentials, and settings.
    """

    root: Path
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
        settings = ProjectSettings(data.get("settings", {}))

        project = cls(root=root, settings=settings)
        project.structures = cls._load_structures(root, data.get("structures", []))
        project.workflows = cls._load_workflows(root, data.get("workflows", []))
        return project

    @staticmethod
    def _load_structures(root: Path, entries: list[dict]) -> Dict[str, StructureRef]:
        structures: Dict[str, StructureRef] = {}
        for entry in entries:
            struct_id = entry["id"]
            struct_path = entry.get("file")
            if not struct_path:
                raise ValueError(f"Structure '{struct_id}' is missing 'file'")
            path = (root / struct_path).resolve()
            structures[struct_id] = StructureRef(
                name=struct_id,
                path=path,
                format=entry.get("format", "auto"),
            )
        return structures

    @staticmethod
    def _load_workflows(root: Path, entries: list[dict]) -> Dict[str, WorkflowRef]:
        workflows: Dict[str, WorkflowRef] = {}
        for entry in entries:
            workflow_id = entry["id"]
            workflow_path = entry.get("path") or f"workflows/{workflow_id}"
            path = (root / workflow_path).resolve()
            workflows[workflow_id] = WorkflowRef(name=workflow_id, path=path)
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
        return list(self.structures.keys())

    def get_structure(self, structure_id: str) -> StructureRef:
        try:
            return self.structures[structure_id]
        except KeyError as exc:
            raise KeyError(f"Unknown structure '{structure_id}'") from exc

    def list_workflows(self) -> list[str]:
        return list(self.workflows.keys())

    def get_workflow_ref(self, workflow_id: str) -> WorkflowRef:
        try:
            return self.workflows[workflow_id]
        except KeyError as exc:
            raise KeyError(f"Unknown workflow '{workflow_id}'") from exc

    def get_workflow(self, workflow_id: str):
        """
        Load and return a workflow instance.
        """
        from quantumvitas.workflow.workflow import Workflow

        ref = self.get_workflow_ref(workflow_id)
        return Workflow.from_yaml(ref.path, self)

    def structure_ref(self, name: str) -> StructureRef:
        """
        Return a structure reference relative to the structures directory.
        """
        structure_path = self.structures_dir / name
        return StructureRef(name=name, path=structure_path)

