"""
Dataclasses representing a QuantumVITAS project on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


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

    def workflow_ref(self, name: str) -> WorkflowRef:
        """
        Return a workflow reference by name without reading workflow.yaml.
        """
        workflow_path = self.workflows_dir / name
        return WorkflowRef(name=name, path=workflow_path)

    def structure_ref(self, name: str) -> StructureRef:
        """
        Return a structure reference relative to the structures directory.
        """
        structure_path = self.structures_dir / name
        return StructureRef(name=name, path=structure_path)

