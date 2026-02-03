"""
Utilities for loading/saving project metadata and calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from quantumvitas.core.resources import ensure_relative_path, meta_from_name
from .model import Project, ProjectSettings, CalculationRef


@dataclass(slots=True)
class ProjectStorage:
    """
    Responsible for persisting project-level files (settings, calculations).
    """

    project: Project

    def load_settings(self) -> ProjectSettings:
        if not self.project.settings_file.exists():
            return ProjectSettings()
        data = yaml.safe_load(self.project.settings_file.read_text()) or {}  # EXC-004: settings file, not SSOT
        return ProjectSettings(data=data)

    def save_settings(self, settings: ProjectSettings) -> None:
        self.project.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.project.settings_file.write_text(yaml.safe_dump(settings.data))  # EXC-004: settings file is not SSOT

    def list_calculations(self) -> Iterable[CalculationRef]:
        calculations_dir = self.project.calculations_dir
        if not calculations_dir.exists():
            return []
        refs: list[CalculationRef] = []
        for path in calculations_dir.iterdir():
            if not path.is_dir():
                continue
            meta = meta_from_name(
                "calculation",
                name=path.name,
                path=ensure_relative_path(path, base=self.project.root),
            )
            refs.append(CalculationRef(meta=meta, absolute_path=path.resolve()))
        return refs

    def ensure_directories(self) -> None:
        """
        Create the canonical project sub-directories if they do not exist.
        """
        for subdir in ["structures", "calculations", "pseudo"]:
            (self.project.root / subdir).mkdir(parents=True, exist_ok=True)

