"""General preflight checker for missing artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.calculation.public import Calculation


@dataclass
class PreflightRequirement:
    """Declaration of required artifact for preflight check."""
    artifact_type: str  # e.g., "restart", "wfn", "chgcar"
    pattern: str        # Glob pattern
    source_step: str    # "predecessor" or specific step_ulid
    required: bool      # Hard error if missing?
    message: str        # Error message template


@dataclass
class PreflightError:
    """Preflight check failure."""
    requirement: PreflightRequirement
    message: str


class PreflightChecker:
    """
    General preflight checker for missing artifacts.

    CRITICAL: Always searches in Runtime SSOT (raw/<step_ulid>/),
    NEVER in scan archive (raw/scan/).
    """

    def check(
        self,
        requirements: List[PreflightRequirement],
        calculation: "Calculation",
        current_step,
    ) -> List[PreflightError]:
        """Check all requirements before launching engine."""
        errors = []
        for req in requirements:
            source_dir = self._resolve_source_dir(req, calculation, current_step)
            if source_dir is None:
                if req.required:
                    errors.append(PreflightError(
                        requirement=req,
                        message=f"No predecessor step found for {req.artifact_type}",
                    ))
                continue

            matches = list(source_dir.glob(req.pattern))
            if not matches and req.required:
                errors.append(PreflightError(
                    requirement=req,
                    message=req.message.format(
                        pattern=req.pattern,
                        source_dir=source_dir,
                    )
                ))
        return errors

    def _resolve_source_dir(
        self,
        req: PreflightRequirement,
        calculation: "Calculation",
        current_step,
    ) -> Optional[Path]:
        """Resolve source directory for artifact lookup."""
        if req.source_step == "predecessor":
            predecessor = self._get_linear_predecessor(current_step, calculation)
            if predecessor is None:
                return None
            # CRITICAL: Use Runtime SSOT, NOT scan archive
            return calculation.io.raw_dir / predecessor.meta.ulid
        else:
            return calculation.io.raw_dir / req.source_step

    def _get_linear_predecessor(self, current_step, calculation) -> Optional:
        """Get topological predecessor step."""
        steps = calculation.steps
        current_idx = None
        for i, step in enumerate(steps):
            if step.meta.ulid == current_step.meta.ulid:
                current_idx = i
                break
        if current_idx is None or current_idx == 0:
            return None
        return steps[current_idx - 1]

