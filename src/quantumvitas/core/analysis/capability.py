"""Analysis capability declarations and matching logic."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AnalysisCapability:
    """Engine-declared ability to produce one analysis object type."""

    object_type: str
    gen_step_sequence: list[str]
    evidence_files: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.object_type:
            raise ValueError("object_type cannot be empty")
        if not self.gen_step_sequence:
            raise ValueError("gen_step_sequence must have length >= 1")


@dataclass
class CapabilityMatch:
    """A successful capability match against ordered run steps."""

    object_type: str
    step_ulids: list[str]
    gen_steps: list[str]
    evidence_dirs: list[Path]


def find_contiguous_match(
    capability: AnalysisCapability,
    ordered_gen_steps: list[tuple[str, str, Path]],
) -> CapabilityMatch | None:
    """
    Match capability.gen_step_sequence against an ordered run step list.

    Returns the first contiguous match if present, otherwise None.
    """
    sequence = capability.gen_step_sequence
    n_required = len(sequence)
    if n_required < 1:
        raise ValueError("gen_step_sequence must have length >= 1")

    if n_required > len(ordered_gen_steps):
        return None

    for start in range(0, len(ordered_gen_steps) - n_required + 1):
        window = ordered_gen_steps[start : start + n_required]
        if all(window[index][1] == sequence[index] for index in range(n_required)):
            return CapabilityMatch(
                object_type=capability.object_type,
                step_ulids=[row[0] for row in window],
                gen_steps=[row[1] for row in window],
                evidence_dirs=[row[2] for row in window],
            )

    return None

