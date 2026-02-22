"""
EngineInput: pre-resolved data object for engine execution.

All data an engine needs to execute a step is provided upfront by the handler,
eliminating the need for engines to read SSOT files (step.yaml, calculation.yaml)
at execution time. This enforces Law K3 (single entry point for YAML reads).

ChainStepEntry provides pre-resolved step data for chain execution (PySCF, ORCA).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ChainStepEntry:
    """Pre-resolved step data for chain execution (PySCF, ORCA)."""

    step_ulid: str
    step_type_spec: str
    step_type_gen: str
    parameters: dict
    requires_structure: bool
    step_artifacts_dir: Path


@dataclass(frozen=True)
class EngineInput:
    """All data an engine needs to execute a step. No SSOT reads needed."""

    step_ulid: str
    step_type_spec: str
    step_type_gen: str
    working_dir: Path
    parameters: dict
    materialized_inputs: dict[str, Path]
    run_ulid: str
    chain: list[ChainStepEntry] | None = None
    upstream_artifacts: dict[str, Path] | None = None
    structure_data: dict | None = None
    structure_ulid: str | None = None
    project_root: Path | None = None
