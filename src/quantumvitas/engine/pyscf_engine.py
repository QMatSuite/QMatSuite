"""
PySCF engine adapter for molecular quantum chemistry calculations.

This module provides a subprocess-based engine for PySCF calculations.
The daemon never imports PySCF directly - all PySCF execution happens
in a subprocess via the runner module.

Architecture:
    Daemon (this module)           Runner subprocess
    ┌─────────────────┐           ┌─────────────────┐
    │ PySCFEngine     │  ──────▶  │ runner.py       │
    │   .probe()      │  job.json │   import pyscf  │
    │   .run_step()   │  ◀──────  │   run SCF       │
    └─────────────────┘  results  └─────────────────┘

PySCF is an optional dependency. Calculations will fail gracefully
with a clear error message if PySCF is not installed.

Windows: PySCF native Windows is not supported. The engine will
report unavailable on Windows with instructions for WSL/Docker.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from .base import Engine, EngineConfig, StepResult


class PySCFEngine(Engine):
    """
    PySCF engine adapter.
    
    Provides subprocess-based execution of molecular quantum chemistry
    calculations using PySCF:
    - Hartree-Fock (RHF, UHF, ROHF)
    - DFT (RKS, UKS, ROKS)
    
    Key design decisions:
    - Never imports PySCF in this module (subprocess isolation)
    - Works via job.json / results.json file exchange
    - Supports dev-mode (current venv) and future managed bundles
    """
    
    name = "pyscf"
    
    def __init__(self, config: Optional[EngineConfig] = None):
        """
        Initialize PySCF engine.
        
        Args:
            config: Optional engine configuration
        """
        super().__init__(config or EngineConfig(name="pyscf"))
        self._probe_cache: Optional[Dict[str, Any]] = None
    
    def probe(self) -> Dict[str, Any]:
        """
        Check if PySCF is available without importing it.
        
        Uses subprocess to check if PySCF can be imported.
        Results are cached for performance.
        
        Returns:
            Dict with 'available', 'version', 'reason' keys
        """
        if self._probe_cache is not None:
            return self._probe_cache
        
        # Windows check
        if sys.platform == "win32":
            self._probe_cache = {
                "available": False,
                "version": None,
                "reason": (
                    "PySCF native Windows is not supported. "
                    "Use WSL (Windows Subsystem for Linux) or Docker."
                ),
            }
            return self._probe_cache
        
        # Try to import PySCF via subprocess
        try:
            result = subprocess.run(
                [sys.executable, "-c", "import pyscf; print(pyscf.__version__)"],
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
                    "reason": (
                        f"PySCF import failed. Install with: pip install pyscf\n"
                        f"Error: {result.stderr.strip()}"
                    ),
                }
        except subprocess.TimeoutExpired:
            self._probe_cache = {
                "available": False,
                "version": None,
                "reason": "PySCF import timed out",
            }
        except Exception as e:
            self._probe_cache = {
                "available": False,
                "version": None,
                "reason": f"Failed to check PySCF availability: {e}",
            }
        
        return self._probe_cache
    
    @property
    def pyscf_available(self) -> bool:
        """Check if PySCF is available for calculations."""
        return self.probe().get("available", False)
    
    def _get_runner_command(self) -> list:
        """
        Get the command to run the PySCF runner subprocess.
        
        Future: This method can be extended to support managed engine bundles
        by checking for a managed pyscf-runner executable.
        
        Returns:
            Command list for subprocess execution
        """
        # Dev-mode: use current Python interpreter
        # Future: check for managed bundle first
        return [sys.executable, "-m", "quantumvitas.engines.pyscf.runner"]
    
    def run_step(self, step, working_dir: Path) -> StepResult:
        """
        Run a PySCF calculation step via subprocess.
        
        Args:
            step: Step object with parameters attribute
            working_dir: Working directory for output files
            
        Returns:
            StepResult with calculation results
        """
        start_time = time.time()
        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine step type
        step_type = "pyscf_scf"
        if hasattr(step, 'step_type'):
            step_type_attr = step.step_type
            if hasattr(step_type_attr, 'value'):
                step_type = step_type_attr.value
            else:
                step_type = str(step_type_attr)
        elif hasattr(step, 'type'):
            step_type = step.type
        
        # Check platform
        if sys.platform == "win32":
            return StepResult(
                step_type=step_type,
                input_file=working_dir / "job.json",
                success=False,
                error=(
                    "PySCF native Windows is not supported. "
                    "Use WSL (Windows Subsystem for Linux) or Docker."
                ),
                execution_time=time.time() - start_time,
            )
        
        # Check if PySCF is available
        probe_result = self.probe()
        if not probe_result.get("available"):
            return StepResult(
                step_type=step_type,
                input_file=working_dir / "job.json",
                success=False,
                error=probe_result.get("reason", "PySCF not available"),
                execution_time=time.time() - start_time,
            )
        
        # Extract parameters from step
        if hasattr(step, 'parameters'):
            params = step.parameters
        elif isinstance(step, dict):
            params = step.get('parameters', step)
        else:
            params = {}
        
        # Build job spec
        job_spec = {
            "step_type": step_type,
            "working_dir": str(working_dir),
            "parameters": params,
            "resources": {},
        }
        
        # Add resource settings if available
        if hasattr(step, 'options'):
            options = step.options
            if options.get("max_memory_mb"):
                job_spec["resources"]["max_memory_mb"] = options["max_memory_mb"]
            if options.get("scratch_dir"):
                job_spec["resources"]["scratch_dir"] = str(options["scratch_dir"])
            if options.get("threads"):
                job_spec["resources"]["threads"] = options["threads"]
        
        # Write job.json
        job_file = working_dir / "job.json"
        try:
            job_file.write_text(json.dumps(job_spec, indent=2))
        except Exception as e:
            return StepResult(
                step_type=step_type,
                input_file=job_file,
                success=False,
                error=f"Failed to write job file: {e}",
                execution_time=time.time() - start_time,
            )
        
        # Run subprocess
        cmd = self._get_runner_command() + [str(job_file)]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=step.options.get("timeout") if hasattr(step, 'options') else None,
            )
            stdout = result.stdout
            stderr = result.stderr
            return_code = result.returncode
        except subprocess.TimeoutExpired as e:
            return StepResult(
                step_type=step_type,
                input_file=job_file,
                success=False,
                return_code=None,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr=e.stderr.decode() if e.stderr else "",
                error="Calculation timed out",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return StepResult(
                step_type=step_type,
                input_file=job_file,
                success=False,
                error=f"Subprocess execution failed: {e}",
                execution_time=time.time() - start_time,
            )
        
        # Parse results
        results_file = working_dir / "results.json"
        parsed_output: Optional[Dict[str, Any]] = None
        success = False
        error = None
        
        if results_file.exists():
            try:
                parsed_output = json.loads(results_file.read_text())
                success = parsed_output.get("success", False)
                error = parsed_output.get("error")
            except Exception as e:
                error = f"Failed to parse results.json: {e}"
        else:
            # Try to parse stdout as JSON (runner prints results to stdout)
            try:
                parsed_output = json.loads(stdout)
                success = parsed_output.get("success", False)
                error = parsed_output.get("error")
            except Exception:
                error = stderr or stdout or f"Runner exited with code {return_code}"
        
        # Log file
        log_file = working_dir / "pyscf.log"
        
        return StepResult(
            step_type=step_type,
            input_file=working_dir / "pyscf_input.py",  # Reproducible script
            output_file=results_file if results_file.exists() else log_file,
            success=success,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            error=error,
            execution_time=time.time() - start_time,
            parsed_output=parsed_output,
        )
    
    # =========================================================================
    # Legacy compatibility: Direct execution methods (deprecated)
    # These are kept for backward compatibility with existing tests but
    # should not be used in production. Use run_step() instead.
    # =========================================================================
    
    def _run_scf(self, params: Dict[str, Any], working_dir: Path) -> StepResult:
        """
        Run PySCF SCF calculation (legacy compatibility).
        
        This method is kept for backward compatibility with existing tests.
        New code should use run_step() which uses subprocess.
        
        Args:
            params: Calculation parameters
            working_dir: Working directory for output
            
        Returns:
            StepResult with SCF results
        """
        # Create a mock step object
        class MockStep:
            step_type = "pyscf_scf"
            parameters = params
            options = {}
        
        return self.run_step(MockStep(), working_dir)
