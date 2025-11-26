"""
Utilities for loading/saving project metadata and workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

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
        return [
            WorkflowRef(name=path.name, path=path)
            for path in workflows_dir.iterdir()
            if path.is_dir()
        ]

    def ensure_directories(self) -> None:
        """
        Create the canonical project sub-directories if they do not exist.
        """
        for subdir in ["structures", "workflows", "pseudo"]:
            (self.project.root / subdir).mkdir(parents=True, exist_ok=True)

