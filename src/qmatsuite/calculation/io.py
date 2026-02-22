"""
Helper for calculation directory layout (raw/reference/results).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CalculationIO:
    """
    Manage the canonical sub-directories inside a calculation folder.
    """

    root: Path
    raw_subdir: str = "raw"
    reference_subdir: str = "reference"
    results_subdir: str = "results"

    def ensure(self) -> None:
        for path in [self.raw_dir, self.reference_dir, self.results_dir]:
            path.mkdir(parents=True, exist_ok=True)

    @property
    def raw_dir(self) -> Path:
        """
        Directory where the engine writes raw QE inputs/outputs.
        """
        return self.root / self.raw_subdir

    @property
    def reference_dir(self) -> Path:
        """
        Directory storing reference outputs (strict/test calculations).
        """
        return self.root / self.reference_subdir

    @property
    def results_dir(self) -> Path:
        """
        Directory where analysis results are written.
        """
        return self.root / self.results_subdir

