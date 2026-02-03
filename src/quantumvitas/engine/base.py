"""Engine interfaces used by the calculation runner."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from quantumvitas.core.public import EngineConfig as _LegacyEngineConfig, StepResult as _LegacyStepResult


EngineConfig = _LegacyEngineConfig
StepResult = _LegacyStepResult


class Engine:
    """Abstract engine capable of running a single calculation step."""

    name: str = "engine"

    def __init__(self, config: EngineConfig):
        self.config = config

    @property
    @abstractmethod
    def supported_presets(self) -> List[str]:
        """
        List of preset dimensions supported by this engine.
        
        This is the SSOT for engine capability declaration.
        Each engine must explicitly declare which preset dimensions it supports.
        
        Returns:
            List of dimension names (e.g., ["precision", "magnetism"] or ["qc_precision"])
        """
        raise NotImplementedError

    def run_step(self, step_or_input, working_dir: Path | None = None) -> StepResult:  # pragma: no cover - interface
        """Run a calculation step.

        Accepts either an ``EngineInput`` (preferred) or the legacy
        ``(step, working_dir)`` pair.  During the transition period each
        concrete engine checks ``isinstance(step_or_input, EngineInput)``
        and branches accordingly.
        """
        raise NotImplementedError
