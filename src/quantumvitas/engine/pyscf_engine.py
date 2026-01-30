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
from typing import Any, Dict, List, Optional, TYPE_CHECKING

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

    @property
    def supported_presets(self) -> List[str]:
        """
        PySCF engine supports QC-based preset dimensions.
        
        Returns:
            List of supported preset dimensions: qc_precision
        """
        return ["qc_precision"]
    
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
        
        Phase 3C: Use quantumvitas.engines.pyscf (not .runner) to support both
        single-step and chain execution via __main__.py.
        
        Future: This method can be extended to support managed engine bundles
        by checking for a managed pyscf-runner executable.
        
        Returns:
            Command list for subprocess execution
        """
        # Dev-mode: use current Python interpreter
        # Phase 3C: Use pyscf package (not pyscf.runner) to support chain execution
        # Future: check for managed bundle first
        return [sys.executable, "-m", "quantumvitas.engines.pyscf"]
    
    def run_step(self, step, working_dir: Path) -> StepResult:
        """
        Run a PySCF calculation step via subprocess.
        
        Phase 3C: Single-step execution is now a chain of length 1.
        All PySCF execution goes through chain execution for consistency.
        
        Args:
            step: Step object with parameters attribute
            working_dir: Working directory for output files (base directory)
            
        Returns:
            StepResult with calculation results
        """
        # Phase 3C: Unify execution path - single step is now a chain of length 1
        # Extract structure_id and project_root from step.options (set by CalculationRunner)
        structure_id = None
        resolved_project_root = None
        
        if hasattr(step, 'options'):
            structure_id = step.options.get('structure_id')
            project_root_str = step.options.get('project_root')
            if project_root_str:
                resolved_project_root = Path(project_root_str)
        
        # Phase 3C: Single-step execution becomes chain of length 1
        # working_dir is the base directory (e.g., calculation.raw_dir)
        # run_step_with_chain will create step_artifacts_dir inside it
        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Phase 3C: Single-step execution becomes chain of length 1
        # Call run_step_with_chain with a single-step chain
        # calculation_raw_dir should be the base directory (working_dir), not step_artifacts_dir
        # run_step_with_chain will create step_artifacts_dir inside calculation_raw_dir
        return self.run_step_with_chain(
            target_step=step,
            chain_steps=[step],  # Chain of length 1
            calculation_raw_dir=working_dir,
            structure_id=structure_id,
            project_root=resolved_project_root,
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
        # Legacy method: bypass step.yaml requirement by directly writing job.json
        start_time = time.time()
        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
        
        job_spec = {
            "step_type_spec": "pyscf_scf",
            "working_dir": str(working_dir),
            "parameters": params,
            "resources": {},
        }
        
        job_file = working_dir / "job.json"
        try:
            job_file.write_text(json.dumps(job_spec, indent=2))
        except Exception as e:
            return StepResult(
                step_type="pyscf_scf",
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
                timeout=None,
            )
            stdout = result.stdout
            stderr = result.stderr
            return_code = result.returncode
        except subprocess.TimeoutExpired as e:
            return StepResult(
                step_type="pyscf_scf",
                input_file=job_file,
                success=False,
                error=f"Subprocess timeout: {e}",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return StepResult(
                step_type="pyscf_scf",
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
            except Exception:
                pass
        
        if not success and not error:
            error = f"Subprocess returned code {return_code}" if return_code != 0 else "Unknown error"
        
        output_file = results_file if results_file.exists() else job_file
        
        return StepResult(
            step_type="pyscf_scf",
            input_file=job_file,
            output_file=output_file,
            success=success,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            error=error,
            execution_time=time.time() - start_time,
            parsed_output=parsed_output,
        )
    
    def run_step_with_chain(
        self,
        target_step,
        chain_steps: List[Any],  # List of Step objects
        calculation_raw_dir: Path,
        structure_id: Optional[str] = None,
        project_root: Optional[Path] = None,
    ) -> StepResult:
        """
        Run a PySCF dependency chain in one session.
        
        Phase 3C: One-session execution model for RunStep mode.
        
        Args:
            target_step: Target Step object (always full rerun)
            chain_steps: List of Step objects in dependency order (from root to target)
            calculation_raw_dir: Base working directory
            
        Returns:
            StepResult for the target step
        """
        start_time = time.time()
        calculation_raw_dir = Path(calculation_raw_dir)
        calculation_raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Fix #1: Check PySCF availability BEFORE trying to read step.yaml
        # This allows graceful failure messages when PySCF is not installed
        # Check platform first
        if sys.platform == "win32":
            return StepResult(
                step_type="unknown",
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=(
                    "PySCF native Windows is not supported. "
                    "Use WSL (Windows Subsystem for Linux) or Docker."
                ),
                execution_time=time.time() - start_time,
            )
        
        # Check if PySCF is available (before step.yaml read for graceful failure)
        probe_result = self.probe()
        if not probe_result.get("available"):
            return StepResult(
                step_type="unknown",
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=probe_result.get("reason", "PySCF not available"),
                execution_time=time.time() - start_time,
            )
        
        # SINGLE SOURCE OF TRUTH: Read machine step_type from step.yaml
        # step.yaml stores machine types (e.g., "pyscf_scf", "pyscf_mp2")
        # Step.step_type_spec enum MUST NOT be used for execution
        target_step_type = None
        if hasattr(target_step, 'meta') and hasattr(target_step.meta, 'path') and target_step.meta.path and project_root:
            step_yaml_path = project_root / target_step.meta.path
            if step_yaml_path.exists():
                import yaml
                step_data = yaml.safe_load(step_yaml_path.read_text()) or {}
                target_step_type = step_data.get("step_type")
        
        # HARD ERROR if step_type not found
        if not target_step_type:
            return StepResult(
                step_type="unknown",
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=f"Failed to read machine step_type from step.yaml for target step. Step meta.path={getattr(target_step.meta, 'path', 'None') if hasattr(target_step, 'meta') else 'No meta'}, project_root={project_root}. Execution MUST use machine step_type from step.yaml, not Step.step_type_spec enum.",
                execution_time=time.time() - start_time,
            )
        
        # Validate step_type is in registry
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()
        if not registry.has(target_step_type):
            return StepResult(
                step_type=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=f"Step type '{target_step_type}' not found in registry. This indicates an invalid or corrupted step.yaml file.",
                execution_time=time.time() - start_time,
            )
        
        # Phase 3C: Resolve structure once for all chain steps (structure is calc-level)
        # Structure is required for PySCF calculations - raise error if missing
        if not structure_id:
            return StepResult(
                step_type=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=f"Structure ID is required for PySCF chain execution, but calculation.structure_id is None",
                execution_time=time.time() - start_time,
            )
        if not project_root:
            return StepResult(
                step_type=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=f"Project root is required for structure resolution, but project_root is None",
                execution_time=time.time() - start_time,
            )
        
        structure_data = None
        try:
            from quantumvitas.core.resolution import require_structure
            from quantumvitas.io.structure_io import read_structure
            from pymatgen.core import Molecule as PMGMolecule
            
            # Resolve structure using canonical resolver
            structure_resolved = require_structure(
                project_root,
                structure_id,
                config=None,
                index=None,
            )
            structure_path = structure_resolved.absolute_path
            
            # Load structure
            structure = read_structure(structure_path)
            
            # Assert it's a Molecule (not Structure)
            if not isinstance(structure, PMGMolecule):
                return StepResult(
                    step_type=target_step_type,
                    input_file=calculation_raw_dir / "job_chain.json",
                    success=False,
                    error=f"Expected Molecule for PySCF, got {type(structure)}",
                    execution_time=time.time() - start_time,
                )
            
            # Validate structure has atoms
            if len(structure) == 0:
                return StepResult(
                    step_type=target_step_type,
                    input_file=calculation_raw_dir / "job_chain.json",
                    success=False,
                    error=f"Structure has no atoms (structure_id={structure_id})",
                    execution_time=time.time() - start_time,
                )
            
            # Store structure_path (canonical path) and metadata for chain jobs
            # Phase 3C: Use structure_path as SSOT, not precomputed atoms list
            structure_path_abs = Path(structure_path).resolve()
            structure_data = {
                "structure_path": str(structure_path_abs),
                "charge": structure.charge,
                "spin": structure.spin_multiplicity - 1,  # PySCF uses 2S, pymatgen uses 2S+1
                "unit": "Angstrom",
            }
            
            # Validate structure file exists
            if not structure_path_abs.exists():
                return StepResult(
                    step_type=target_step_type,
                    input_file=calculation_raw_dir / "job_chain.json",
                    success=False,
                    error=f"Structure file does not exist: {structure_path_abs}",
                    execution_time=time.time() - start_time,
                )
        except Exception as e:
            import traceback
            return StepResult(
                step_type=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=f"Failed to load structure (structure_id={structure_id}, project_root={project_root}): {e}\n{traceback.format_exc()}",
                execution_time=time.time() - start_time,
            )
        
        # Build chain step specs
        chain_step_specs = []
        for step in chain_steps:
            step_ulid = step.meta.ulid if hasattr(step, 'meta') and hasattr(step.meta, 'id') else "unknown"
            
            # Phase 3C: Read machine step_type from step.yaml (step.yaml stores machine types)
            # Step.step_type_spec is StepType enum which doesn't have all machine types (e.g., no "mp2")
            step_type= "unknown"
            if hasattr(step, 'meta') and hasattr(step.meta, 'path') and step.meta.path:
                # step.meta.path is relative to project root
                step_yaml_path = project_root / step.meta.path
                if step_yaml_path.exists():
                    import yaml
                    step_data = yaml.safe_load(step_yaml_path.read_text()) or {}
                    step_type = step_data.get("step_type_spec") or step_data.get("step_type") or "unknown"
            
            # HARD ERROR if step_type not found - no fallbacks allowed
            if step_type == "unknown" or not step_type:
                return StepResult(
                    step_type="unknown",
                    input_file=calculation_raw_dir / "job_chain.json",
                    success=False,
                    error=f"Failed to read machine step_type from step.yaml for chain step {step_ulid}. Step meta.path={getattr(step.meta, 'path', 'None') if hasattr(step, 'meta') else 'No meta'}, project_root={project_root}. Execution MUST use machine step_type from step.yaml, not Step.step_type_spec enum.",
                    execution_time=time.time() - start_time,
                )
            
            # Validate step_type is in registry
            from quantumvitas.workflow.registry import get_registry
            registry = get_registry()
            if not registry.has(step_type):
                return StepResult(
                    step_type=step_type,
                    input_file=calculation_raw_dir / "job_chain.json",
                    success=False,
                    error=f"Step type '{step_type}' not found in registry for chain step {step_ulid}. This indicates an invalid or corrupted step.yaml file.",
                    execution_time=time.time() - start_time,
                )
            
            # Get parameters
            params = {}
            if hasattr(step, 'parameters'):
                params = step.parameters.copy() if isinstance(step.parameters, dict) else step.parameters
            elif isinstance(step, dict):
                params = step.get('parameters', step).copy() if isinstance(step.get('parameters', step), dict) else step.get('parameters', step)
            
            # Phase 3C: Merge structure data into parameters ONLY for steps that require structure
            # SCF steps require structure (to build molecule), but MP2/TD steps only need mf from state
            # Per contract: MP2 must NOT receive structure/atoms - it consumes mf from chain state only
            from quantumvitas.workflow.registry import get_registry
            registry = get_registry()
            step_spec = registry.get(step_type)
            if step_spec and step_spec.requires_structure and structure_data:
                # Merge structure_path and metadata into params
                params = {**params, **structure_data}
            # Explicitly ensure MP2/TD/etc do NOT get structure data even if somehow passed
            elif step_spec and not step_spec.requires_structure:
                # Remove any structure-related keys that might have been incorrectly included
                params = {k: v for k, v in params.items() if k not in ("atoms", "structure_path", "charge", "spin", "unit", "structure")}
            
            # Get step artifacts directory
            step_artifacts_dir = calculation_raw_dir / "step_artifacts" / step_ulid
            
            # Determine allow_chkfile_init_guess
            # Target step: always False (full rerun)
            # Prerequisite steps: True (incremental semantics - may use chkfile)
            is_target = (step_ulid == target_step.meta.ulid)
            allow_chkfile_init_guess = not is_target
            
            # Validation before adding to chain
            if step_spec and step_spec.requires_structure:
                # For SCF steps: validate structure_path exists
                if "structure_path" not in params:
                    return StepResult(
                        step_type=step_type,
                        input_file=calculation_raw_dir / "job_chain.json",
                        success=False,
                        error=f"SCF step ({step_ulid}) requires structure_path but it's missing from parameters",
                        execution_time=time.time() - start_time,
                    )
                structure_path_check = Path(params["structure_path"])
                if not structure_path_check.exists():
                    return StepResult(
                        step_type=step_type,
                        input_file=calculation_raw_dir / "job_chain.json",
                        success=False,
                        error=f"SCF step ({step_ulid}) structure_path does not exist: {structure_path_check}",
                        execution_time=time.time() - start_time,
                    )
            elif step_spec and not step_spec.requires_structure:
                # For MP2/TD steps: ensure no structure keys exist
                structure_keys = {"atoms", "structure_path", "structure", "charge", "spin", "unit"}
                found_structure_keys = structure_keys.intersection(params.keys())
                if found_structure_keys:
                    return StepResult(
                        step_type=step_type,
                        input_file=calculation_raw_dir / "job_chain.json",
                        success=False,
                        error=f"Step {step_ulid} ({step_type}) must not receive structure data, but found keys: {found_structure_keys}",
                        execution_time=time.time() - start_time,
                    )
            
            chain_step_specs.append({
                "step_ulid": step_ulid,
                "step_type_spec": step_type,
                "parameters": params,
                "step_artifacts_dir": str(step_artifacts_dir),
                "allow_chkfile_init_guess": allow_chkfile_init_guess,
            })
        
        # Build job chain spec
        job_chain_spec = {
            "base_working_dir": str(calculation_raw_dir),
            "chain_steps": chain_step_specs,
            "target_step_ulid": target_step.meta.ulid,
            "resources": {},
        }
        
        # Add resource settings if available
        if hasattr(target_step, 'options'):
            options = target_step.options
            if options.get("max_memory_mb"):
                job_chain_spec["resources"]["max_memory_mb"] = options["max_memory_mb"]
            if options.get("scratch_dir"):
                job_chain_spec["resources"]["scratch_dir"] = str(options["scratch_dir"])
            if options.get("threads"):
                job_chain_spec["resources"]["threads"] = options["threads"]
        
        # Write job_chain.json
        job_chain_file = calculation_raw_dir / "job_chain.json"
        try:
            job_chain_file.write_text(json.dumps(job_chain_spec, indent=2))
        except Exception as e:
            return StepResult(
                step_type=target_step_type,
                input_file=job_chain_file,
                success=False,
                error=f"Failed to write job chain file: {e}",
                execution_time=time.time() - start_time,
            )
        
        # Run subprocess using run_job_chain
        cmd = self._get_runner_command() + [str(job_chain_file)]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=calculation_raw_dir,
                timeout=target_step.options.get("timeout") if hasattr(target_step, 'options') else None,
            )
            stdout = result.stdout
            stderr = result.stderr
            return_code = result.returncode
        except subprocess.TimeoutExpired as e:
            return StepResult(
                step_type=target_step_type,
                input_file=job_chain_file,
                success=False,
                return_code=None,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr=e.stderr.decode() if e.stderr else "",
                error="Chain execution timed out",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return StepResult(
                step_type=target_step_type,
                input_file=job_chain_file,
                success=False,
                error=f"Subprocess execution failed: {e}",
                execution_time=time.time() - start_time,
            )
        
        # Parse results (from target step's artifacts directory)
        target_artifacts_dir = calculation_raw_dir / "step_artifacts" / target_step.meta.ulid
        results_file = target_artifacts_dir / "results.json"
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
            # Try to parse stdout as JSON
            try:
                parsed_output = json.loads(stdout)
                success = parsed_output.get("success", False)
                error = parsed_output.get("error")
            except Exception:
                error = stderr or stdout or f"Runner exited with code {return_code}"
        
        output_file = results_file if results_file.exists() else job_chain_file
        
        return StepResult(
            step_type=target_step_type,
            input_file=job_chain_file,
            output_file=output_file,
            success=success,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            error=error,
            execution_time=time.time() - start_time,
            parsed_output=parsed_output,
        )
