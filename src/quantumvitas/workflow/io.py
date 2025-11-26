"""
Helper for workflow directory layout (raw/reference/results).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class WorkflowIO:
    """
    Manage the canonical sub-directories inside a workflow folder.
    """

    root: Path

    def ensure(self) -> None:
        for path in [self.raw_dir, self.reference_dir, self.results_dir]:
            path.mkdir(parents=True, exist_ok=True)

    @property
    def raw_dir(self) -> Path:
        """
        Directory where the engine writes raw QE inputs/outputs.
        """
        return self.root / "raw"

    @property
    def reference_dir(self) -> Path:
        """
        Directory storing reference outputs (strict/test workflows).
        """
        return self.root / "reference"

    @property
    def results_dir(self) -> Path:
        """
        Directory where analysis results are written.
        """
        return self.root / "results"

