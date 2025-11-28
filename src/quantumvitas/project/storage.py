"""
Utilities for loading/saving project metadata and workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from quantumvitas.core.resources import ensure_relative_path, meta_from_name
from .model import Project, ProjectSettings, WorkflowRef


@dataclass(slots=True)
class ProjectStorage:
    """
    Responsible for persisting project-level files (settings, workflows).
    """

    project: Project

    def load_settings(self) -> ProjectSettings:
        if not self.project.settings_file.exists():
            return ProjectSettings()
        data = yaml.safe_load(self.project.settings_file.read_text()) or {}
        return ProjectSettings(data=data)

    def save_settings(self, settings: ProjectSettings) -> None:
        self.project.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.project.settings_file.write_text(yaml.safe_dump(settings.data))

    def list_workflows(self) -> Iterable[WorkflowRef]:
        workflows_dir = self.project.workflows_dir
        if not workflows_dir.exists():
            return []
        refs: list[WorkflowRef] = []
        for path in workflows_dir.iterdir():
            if not path.is_dir():
                continue
            meta = meta_from_name(
                "workflow",
                name=path.name,
                path=ensure_relative_path(path, base=self.project.root),
            )
            refs.append(WorkflowRef(meta=meta, absolute_path=path.resolve()))
        return refs

    def ensure_directories(self) -> None:
        """
        Create the canonical project sub-directories if they do not exist.
        """
        for subdir in ["structures", "workflows", "pseudo"]:
            (self.project.root / subdir).mkdir(parents=True, exist_ok=True)

