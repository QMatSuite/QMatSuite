"""Engine interfaces used by the workflow runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from quantumvitas.core.engines.base import EngineConfig as _LegacyEngineConfig
from quantumvitas.core.engines.qe_workflow import StepResult as _LegacyStepResult


EngineConfig = _LegacyEngineConfig
StepResult = _LegacyStepResult


class Engine:
    """Abstract engine capable of running a single workflow step."""

    name: str = "engine"

    def __init__(self, config: EngineConfig):
        self.config = config

    def run_step(self, step, working_dir: Path) -> StepResult:  # pragma: no cover - interface
        raise NotImplementedError
