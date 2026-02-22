"""GPAW engine adapter for periodic and molecular DFT calculations.

This module provides a subprocess-based engine for GPAW calculations.
GPAW is Python-native — execution happens via subprocess calling
generated Python scripts. The daemon never imports GPAW directly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import Engine, EngineConfig, StepResult


class GpawEngine(Engine):
    """GPAW DFT engine adapter."""

    name = "gpaw"

    def __init__(self, config: Optional[EngineConfig] = None):
        super().__init__(config or EngineConfig(name="gpaw"))
        self._probe_cache: Optional[Dict[str, Any]] = None

    @property
    def supported_presets(self) -> List[str]:
        return ["precision"]

    def _get_gpaw_python(self) -> str:
        """Resolve Python executable for GPAW runner (registry first)."""
        try:
            from quantumvitas.core.public import resolve_active_python

            registry_python = resolve_active_python("gpaw")
            if registry_python:
                return str(registry_python)
        except Exception:
            pass
        return sys.executable

    def probe(self) -> Dict[str, Any]:
        """Check if GPAW is available without importing it."""
        if self._probe_cache is not None:
            return self._probe_cache

        try:
            gpaw_python = self._get_gpaw_python()
            result = subprocess.run(
                [gpaw_python, "-c", "import gpaw; print(gpaw.__version__)"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                self._probe_cache = {
                    "available": True,
                    "version": version,
                    "reason": None,
                }
            else:
                self._probe_cache = {
                    "available": False,
                    "version": None,
                    "reason": result.stderr.strip()[:200],
                }
        except Exception as e:
            self._probe_cache = {
                "available": False,
                "version": None,
                "reason": str(e),
            }

        return self._probe_cache

    def run_step(
        self,
        step_or_input,
        working_dir: Path | None = None,
    ) -> StepResult:
        """Execute a GPAW step via subprocess."""
        from quantumvitas.engine.engine_input import EngineInput

        if isinstance(step_or_input, EngineInput):
            ei = step_or_input
            wd = ei.working_dir
            step_type = ei.step_type_spec
            script_name = ei.metadata.get("script_name", "scf.py")
        else:
            step = step_or_input
            if working_dir is None:
                raise ValueError("working_dir is required for legacy step objects")
            wd = working_dir
            step_type = step.step_type_spec if hasattr(step, "step_type_spec") else ""
            gen_type = step_type.replace("gpaw_", "") if step_type.startswith("gpaw_") else "scf"
            script_name = f"{gen_type}.py"

        cmd = [self._get_gpaw_python(), script_name]

        result = subprocess.run(
            cmd,
            cwd=str(wd),
            capture_output=True,
            text=True,
        )

        error = None
        success = result.returncode == 0

        if result.returncode != 0:
            error = f"GPAW exited with code {result.returncode}"
            if result.stderr:
                error += f"\n{result.stderr[:500]}"

        return StepResult(
            step_type_spec=step_type,
            input_file=wd / script_name,
            success=success,
            error=error,
            output_file=wd / "results.json" if (wd / "results.json").exists() else None,
            return_code=result.returncode,
        )
