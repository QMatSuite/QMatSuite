"""Analysis capability declarations and matching logic."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ResultState(Enum):
    """Outcome state for an analysis match instance (spec §5.5)."""

    OK = "ok"
    MISSING_EVIDENCE = "missing_evidence"
    PARSER_ERROR = "parser_error"


class MissingReason(Enum):
    """Sub-reason for MISSING_EVIDENCE state (spec §5.5)."""

    NO_PROVIDER = "no_provider"
    NO_EVIDENCE = "no_evidence"


@dataclass
class AnalysisResult:
    """Result of processing one capability match instance (spec §5.5)."""

    object_type: str
    step_ulids: list[str]
    gen_steps: list[str]
    evidence_dirs: list[Path]
    state: ResultState
    reason: MissingReason | None = None
    canonical: Any = None
    analysis_object: Any = None
    error: str | None = None
    effective_sequence: list[str] = field(default_factory=list)
    match_key: str = ""


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
        if len(self.gen_step_sequence) != len(set(self.gen_step_sequence)):
            raise ValueError(
                f"gen_step_sequence must not contain repeated step types: "
                f"{self.gen_step_sequence}"
            )


@dataclass
class CapabilityMatch:
    """A successful capability match against ordered run steps."""

    object_type: str
    step_ulids: list[str]
    gen_steps: list[str]
    evidence_dirs: list[Path]
    effective_sequence: list[str] = field(default_factory=list)


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


def enumerate_all_matches(
    capabilities: list[AnalysisCapability],
    ordered_gen_steps: list[tuple[str, str, Path]],
) -> list[CapabilityMatch]:
    """
    Sliding-window multi-match: emit ALL capability instances (spec §5.4, §5.9).

    Algorithm:
    - For each start_idx in ordered_gen_steps, collect all capabilities whose
      gen_step_sequence matches at that start.
    - Group by object_type; per group keep the longest span (tie-break by
      declaration order = cap_idx).
    - Emit one CapabilityMatch per surviving match.

    This replaces the old first-match-per-type logic with full multi-match
    semantics required by spec v2.2.
    """
    n_steps = len(ordered_gen_steps)
    if not capabilities or n_steps == 0:
        return []

    # Pre-index capabilities by declaration order for tie-breaking
    indexed_caps: list[tuple[int, AnalysisCapability]] = list(enumerate(capabilities))

    results: list[CapabilityMatch] = []

    for start_idx in range(n_steps):
        # Collect all capabilities that match starting at start_idx
        matches_at_start: dict[str, tuple[int, int, CapabilityMatch]] = {}
        # key = object_type.lower()
        # value = (span_length, cap_idx, match)  — for longest-wins + tie-break

        for cap_idx, cap in indexed_caps:
            seq = cap.gen_step_sequence
            n_required = len(seq)
            if start_idx + n_required > n_steps:
                continue

            window = ordered_gen_steps[start_idx : start_idx + n_required]
            if all(window[i][1] == seq[i] for i in range(n_required)):
                obj_key = cap.object_type.lower()
                match = CapabilityMatch(
                    object_type=cap.object_type,
                    step_ulids=[row[0] for row in window],
                    gen_steps=[row[1] for row in window],
                    evidence_dirs=[row[2] for row in window],
                    effective_sequence=list(cap.gen_step_sequence),
                )
                existing = matches_at_start.get(obj_key)
                # Longest wins; tie-break: lower cap_idx wins
                if existing is None or (
                    n_required > existing[0]
                    or (n_required == existing[0] and cap_idx < existing[1])
                ):
                    matches_at_start[obj_key] = (n_required, cap_idx, match)

        # Emit surviving matches for this start index
        for _obj_key, (_span, _cidx, match) in matches_at_start.items():
            results.append(match)

    return results


def canonical_match_key(
    engine_name: str,
    object_type: str,
    effective_sequence: list[str],
    step_ulids: list[str],
) -> str:
    """Stable bijective match_key (design doc §1.3, spec §10.4).

    Format: ``engine:object_type:seq1+seq2:ulid1,ulid2``
    """
    seq = "+".join(effective_sequence)
    ulids = ",".join(step_ulids)
    return f"{engine_name}:{object_type}:{seq}:{ulids}"
