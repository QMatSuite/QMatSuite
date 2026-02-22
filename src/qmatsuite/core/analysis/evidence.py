"""Evidence bundle for analysis providers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

EvidenceStep = Tuple[str, str, Path]


@dataclass
class EvidenceBundle:
    """Typed context passed to every analysis provider."""

    primary_raw_dir: Path
    calc_dir: Path
    run_ulid: str | None
    calc_ulid: str | None
    step_ulids: List[str]
    gen_steps: List[str]
    engine_name: str
    evidence_steps: List[EvidenceStep]  # always present, may be empty

