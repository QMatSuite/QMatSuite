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
        
        Phase 3C: Uses per-step artifact directory if available in step.options.
        
        Args:
            step: Step object with parameters attribute
            working_dir: Working directory for output files (base directory)
            
        Returns:
            StepResult with calculation results
        """
        start_time = time.time()
        # Phase 3C: Use per-step artifact directory if provided, otherwise use working_dir
        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
        
        if hasattr(step, 'options') and step.options.get('step_artifacts_dir'):
            step_artifacts_dir = Path(step.options['step_artifacts_dir'])
            step_artifacts_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Fallback: use working_dir as step_artifacts_dir if not provided
            step_artifacts_dir = working_dir
        
        # Determine step type (Phase 3C: map public types to machine types)
        # Step.step_type is StepType enum with public values (e.g., "scf"), but runner expects machine types (e.g., "pyscf_scf")
        step_type = "pyscf_scf"  # Default
        if hasattr(step, 'step_type'):
            step_type_attr = step.step_type
            if hasattr(step_type_attr, 'value'):
                public_type = step_type_attr.value
                # Phase 3C: Map public types to PySCF machine types
                # This mapping is PySCF-specific (engine knows it's PySCF)
                type_map = {
                    "scf": "pyscf_scf",
                    "mp2": "pyscf_mp2",
                    "td": "pyscf_td",
                    "analysis": "pyscf_analysis",
                    "freq": "pyscf_freq",
                }
                step_type = type_map.get(public_type, public_type)  # Use mapping if available, else use as-is
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
            params = step.parameters.copy() if isinstance(step.parameters, dict) else step.parameters
        elif isinstance(step, dict):
            params = step.get('parameters', step).copy() if isinstance(step.get('parameters', step), dict) else step.get('parameters', step)
        else:
            params = {}
        
        # Phase 3C: Resolve structure canonically using structure_id and project_root
        if hasattr(step, 'options') and step.options.get('structure_id') and step.options.get('project_root'):
            structure_id = step.options['structure_id']
            project_root = Path(step.options['project_root'])
            
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
                
                # Assert structure file exists
                assert structure_path.exists(), f"Structure file does not exist: {structure_path}"
                
                # Load structure
                structure = read_structure(structure_path)
                
                # Assert it's a Molecule (not Structure)
                assert isinstance(structure, PMGMolecule), f"Expected Molecule, got {type(structure)}"
                
                # Assert molecule has sites
                assert len(structure) > 0, "Molecule has no sites"
                
                # Convert pymatgen.Molecule to atoms format
                atoms = []
                for site in structure:
                    atoms.append({
                        "element": site.species_string,
                        "coords": [float(c) for c in site.coords],
                    })
                
                # Assert atoms list is non-empty
                assert len(atoms) > 0, "Atoms list is empty after conversion"
                
                # Merge structure data into params
                params["atoms"] = atoms
                params["charge"] = structure.charge
                params["spin"] = structure.spin_multiplicity - 1  # PySCF uses 2S, pymatgen uses 2S+1
                params["unit"] = "Angstrom"  # Default unit (pymatgen stores in Angstrom)
                
            except Exception as e:
                # If structure loading fails, return error with details
                import traceback
                return StepResult(
                    step_type=step_type,
                    input_file=working_dir / "job.json",
                    success=False,
                    error=f"Failed to load structure (structure_id={structure_id}, project_root={project_root}): {e}\n{traceback.format_exc()}",
                    execution_time=time.time() - start_time,
                )
        
        # Build job spec
        job_spec = {
            "step_type": step_type,
            "working_dir": str(step_artifacts_dir),  # Use step_artifacts_dir for per-step artifacts
            "parameters": params,
            "resources": {},
        }
        
        # Phase 3C: Add run_mode and allow_chkfile_init_guess control
        if hasattr(step, 'options'):
            options = step.options
            run_mode = options.get("run_mode", "incremental")
            # For SCF steps: allow_chkfile_init_guess = True if incremental, False if full
            # For non-SCF steps: not applicable (they don't use chkfile init_guess)
            if step_type in ("pyscf_scf", "pyscf_rhf", "pyscf_uhf", "pyscf_rks", "pyscf_uks"):
                job_spec["allow_chkfile_init_guess"] = (run_mode == "incremental")
            
            # Add resource settings if available
            if options.get("max_memory_mb"):
                job_spec["resources"]["max_memory_mb"] = options["max_memory_mb"]
            if options.get("scratch_dir"):
                job_spec["resources"]["scratch_dir"] = str(options["scratch_dir"])
            if options.get("threads"):
                job_spec["resources"]["threads"] = options["threads"]
        
        # Write job.json
        job_file = step_artifacts_dir / "job.json"
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
                cwd=step_artifacts_dir,
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
        results_file = step_artifacts_dir / "results.json"
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
        log_file = step_artifacts_dir / "pyscf.log"
        
        return StepResult(
            step_type=step_type,
            input_file=step_artifacts_dir / "pyscf_input.py",  # Reproducible script
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
        
        # Determine target step type
        target_step_type = "pyscf_scf"
        if hasattr(target_step, 'step_type'):
            step_type_attr = target_step.step_type
            if hasattr(step_type_attr, 'value'):
                target_step_type = step_type_attr.value
            else:
                target_step_type = str(step_type_attr)
        elif hasattr(target_step, 'type'):
            target_step_type = target_step.type
        
        # Check platform
        if sys.platform == "win32":
            return StepResult(
                step_type=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
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
                step_type=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=probe_result.get("reason", "PySCF not available"),
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
            
            # Convert pymatgen.Molecule to atoms format
            atoms = []
            for site in structure:
                atoms.append({
                    "element": site.species_string,
                    "coords": [float(c) for c in site.coords],
                })
            
            structure_data = {
                "atoms": atoms,
                "charge": structure.charge,
                "spin": structure.spin_multiplicity - 1,  # PySCF uses 2S, pymatgen uses 2S+1
                "unit": "Angstrom",
            }
            
            # Assert structure_data is valid (atoms list must be non-empty)
            if not structure_data.get("atoms") or len(structure_data["atoms"]) == 0:
                return StepResult(
                    step_type=target_step_type,
                    input_file=calculation_raw_dir / "job_chain.json",
                    success=False,
                    error=f"Structure has no atoms (structure_id={structure_id})",
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
            step_ulid = step.meta.id if hasattr(step, 'meta') and hasattr(step.meta, 'id') else "unknown"
            
            step_type = "pyscf_scf"
            if hasattr(step, 'step_type'):
                step_type_attr = step.step_type
                if hasattr(step_type_attr, 'value'):
                    public_type = step_type_attr.value
                    # Map public types to PySCF machine types
                    type_map = {
                        "scf": "pyscf_scf",
                        "mp2": "pyscf_mp2",
                        "td": "pyscf_td",
                        "analysis": "pyscf_analysis",
                        "freq": "pyscf_freq",
                    }
                    step_type = type_map.get(public_type, public_type)
                else:
                    step_type = str(step_type_attr)
            elif hasattr(step, 'type'):
                step_type = step.type
            
            # Get parameters
            params = {}
            if hasattr(step, 'parameters'):
                params = step.parameters.copy() if isinstance(step.parameters, dict) else step.parameters
            elif isinstance(step, dict):
                params = step.get('parameters', step).copy() if isinstance(step.get('parameters', step), dict) else step.get('parameters', step)
            
            # Phase 3C: Merge structure data into parameters (all chain steps use the same structure)
            if structure_data:
                params = {**params, **structure_data}
            
            # Get step artifacts directory
            step_artifacts_dir = calculation_raw_dir / "step_artifacts" / step_ulid
            
            # Determine allow_chkfile_init_guess
            # Target step: always False (full rerun)
            # Prerequisite steps: True (incremental semantics - may use chkfile)
            is_target = (step_ulid == target_step.meta.id)
            allow_chkfile_init_guess = not is_target
            
            chain_step_specs.append({
                "step_ulid": step_ulid,
                "step_type": step_type,
                "parameters": params,
                "step_artifacts_dir": str(step_artifacts_dir),
                "allow_chkfile_init_guess": allow_chkfile_init_guess,
            })
        
        # Build job chain spec
        job_chain_spec = {
            "base_working_dir": str(calculation_raw_dir),
            "chain_steps": chain_step_specs,
            "target_step_ulid": target_step.meta.id,
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
        target_artifacts_dir = calculation_raw_dir / "step_artifacts" / target_step.meta.id
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
