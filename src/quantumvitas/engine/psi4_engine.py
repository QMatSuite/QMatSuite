"""
Psi4 engine adapter for molecular quantum chemistry calculations.

This module provides a subprocess-based engine for Psi4 calculations.
The daemon never imports Psi4 directly - all Psi4 execution happens
in a subprocess via the runner module.

Architecture:
    Daemon (this module)           Runner subprocess
    +------------------+           +------------------+
    | Psi4Engine       |  -------> | runner.py        |
    |   .probe()       |  job.json |   import psi4    |
    |   .run_step()    |  <------- |   run SCF/MP2/...|
    +------------------+  results  +------------------+
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import Engine, EngineConfig, StepResult


class Psi4Engine(Engine):
    """
    Psi4 engine adapter.

    Provides subprocess-based execution of molecular quantum chemistry
    calculations using Psi4:
    - Hartree-Fock (RHF, UHF, ROHF)
    - DFT (B3LYP, PBE, PBE0, etc.)
    - MP2 (post-HF correlation)
    - Geometry optimization
    - TDDFT excited states

    Key design decisions:
    - Never imports Psi4 in this module (subprocess isolation)
    - Works via job_chain.json / results.json file exchange
    - Wavefunction shared between steps via in-memory ref_wfn in subprocess
    """

    name = "psi4"

    def __init__(self, config: Optional[EngineConfig] = None):
        super().__init__(config or EngineConfig(name="psi4"))
        self._probe_cache: Optional[Dict[str, Any]] = None

    @property
    def supported_presets(self) -> List[str]:
        return ["qc_precision"]

    def probe(self) -> Dict[str, Any]:
        """
        Check if Psi4 is available without importing it.

        Uses subprocess to check if Psi4 can be imported.
        Results are cached for performance.
        """
        if self._probe_cache is not None:
            return self._probe_cache

        try:
            result = subprocess.run(
                [sys.executable, "-c", "import psi4; print(psi4.__version__)"],
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
                        f"Psi4 import failed. Install with: conda install psi4 -c conda-forge\n"
                        f"Error: {result.stderr.strip()}"
                    ),
                }
        except subprocess.TimeoutExpired:
            self._probe_cache = {
                "available": False,
                "version": None,
                "reason": "Psi4 import timed out",
            }
        except Exception as e:
            self._probe_cache = {
                "available": False,
                "version": None,
                "reason": f"Failed to check Psi4 availability: {e}",
            }

        return self._probe_cache

    @property
    def psi4_available(self) -> bool:
        return self.probe().get("available", False)

    def _get_runner_command(self) -> list:
        """Get the command to run the Psi4 runner subprocess."""
        return [sys.executable, "-m", "quantumvitas.engines.psi4"]

    def run_step(self, step_or_input, working_dir: Path | None = None) -> StepResult:
        """Run a Psi4 calculation step via subprocess."""
        from quantumvitas.engine.engine_input import EngineInput

        if isinstance(step_or_input, EngineInput):
            return self._run_with_engine_input(step_or_input)

        # Legacy path
        return self._run_legacy(step_or_input, working_dir)

    def _run_legacy(self, step, working_dir: Path | None) -> StepResult:
        """Legacy run_step path."""
        structure_ulid = None
        resolved_project_root = None

        if hasattr(step, "options"):
            structure_ulid = step.options.get("structure_ulid")
            project_root_str = step.options.get("project_root")
            if project_root_str:
                resolved_project_root = Path(project_root_str)

        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)

        return self.run_step_with_chain(
            target_step=step,
            chain_steps=[step],
            calculation_raw_dir=working_dir,
            structure_ulid=structure_ulid,
            project_root=resolved_project_root,
        )

    def _run_with_engine_input(self, ei: "EngineInput") -> StepResult:
        """Run Psi4 via EngineInput — no SSOT reads needed."""
        start_time = time.time()
        calculation_raw_dir = ei.working_dir
        calculation_raw_dir.mkdir(parents=True, exist_ok=True)

        # Availability check
        probe_result = self.probe()
        if not probe_result.get("available"):
            return StepResult(
                step_type_spec=ei.step_type_spec,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=probe_result.get("reason", "Psi4 not available"),
                execution_time=time.time() - start_time,
            )

        target_step_type = ei.step_type_spec
        target_step_type_gen = ei.step_type_gen

        # Validate in registry
        from quantumvitas.workflow.public import get_registry
        registry = get_registry()
        if not registry.has(target_step_type_gen):
            return StepResult(
                step_type_spec=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=f"Step type '{target_step_type}' (gen: '{target_step_type_gen}') not found in registry.",
                execution_time=time.time() - start_time,
            )

        # Structure validation
        if not ei.structure_ulid:
            return StepResult(
                step_type_spec=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error="Structure ID is required for Psi4 chain execution, but structure_ulid is None",
                execution_time=time.time() - start_time,
            )
        if not ei.project_root:
            return StepResult(
                step_type_spec=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error="Project root is required for structure resolution, but project_root is None",
                execution_time=time.time() - start_time,
            )

        # Resolve structure
        structure_data = None
        try:
            from quantumvitas.core.public import require_structure
            from quantumvitas.io.structure_io import read_structure
            from pymatgen.core import Molecule as PMGMolecule

            structure_resolved = require_structure(ei.project_root, ei.structure_ulid)
            structure_path = structure_resolved.absolute_path
            structure = read_structure(structure_path)

            if not isinstance(structure, PMGMolecule):
                return StepResult(
                    step_type_spec=target_step_type,
                    input_file=calculation_raw_dir / "job_chain.json",
                    success=False,
                    error=f"Expected Molecule for Psi4, got {type(structure)}",
                    execution_time=time.time() - start_time,
                )
            if len(structure) == 0:
                return StepResult(
                    step_type_spec=target_step_type,
                    input_file=calculation_raw_dir / "job_chain.json",
                    success=False,
                    error=f"Structure has no atoms (structure_ulid={ei.structure_ulid})",
                    execution_time=time.time() - start_time,
                )

            structure_path_abs = Path(structure_path).resolve()
            structure_data = {
                "structure_path": str(structure_path_abs),
                "charge": structure.charge,
                "multiplicity": structure.spin_multiplicity,
                "unit": "Angstrom",
            }
        except Exception as e:
            import traceback
            return StepResult(
                step_type_spec=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=f"Failed to load structure: {e}\n{traceback.format_exc()}",
                execution_time=time.time() - start_time,
            )

        # Build chain from EngineInput.chain
        chain_step_specs = []
        chain_entries = ei.chain or []
        if not chain_entries:
            from quantumvitas.engine.engine_input import ChainStepEntry
            chain_entries = [ChainStepEntry(
                step_ulid=ei.step_ulid,
                step_type_spec=ei.step_type_spec,
                step_type_gen=ei.step_type_gen,
                parameters=ei.parameters,
                requires_structure=True,
                step_artifacts_dir=calculation_raw_dir / "step_artifacts" / ei.step_ulid,
            )]

        for entry in chain_entries:
            params = entry.parameters.copy()
            if entry.requires_structure and structure_data:
                params = {**params, **structure_data}
            elif not entry.requires_structure:
                params = {k: v for k, v in params.items()
                          if k not in ("atoms", "structure_path", "charge", "multiplicity", "unit", "structure")}

            step_artifacts_dir = entry.step_artifacts_dir

            chain_step_specs.append({
                "step_ulid": entry.step_ulid,
                "step_type_spec": entry.step_type_spec,
                "parameters": params,
                "step_artifacts_dir": str(step_artifacts_dir),
            })

        # Build and write job chain spec
        job_chain_spec = {
            "base_working_dir": str(calculation_raw_dir),
            "chain_steps": chain_step_specs,
            "target_step_ulid": ei.step_ulid,
            "resources": {},
        }

        job_chain_file = calculation_raw_dir / "job_chain.json"
        try:
            job_chain_file.write_text(json.dumps(job_chain_spec, indent=2))
        except Exception as e:
            return StepResult(
                step_type_spec=target_step_type,
                input_file=job_chain_file,
                success=False,
                error=f"Failed to write job chain file: {e}",
                execution_time=time.time() - start_time,
            )

        # Run subprocess
        cmd = self._get_runner_command() + [str(job_chain_file)]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=calculation_raw_dir,
                timeout=ei.parameters.get("timeout"),
            )
            stdout = result.stdout
            stderr = result.stderr
            return_code = result.returncode
        except subprocess.TimeoutExpired as e:
            return StepResult(
                step_type_spec=target_step_type,
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
                step_type_spec=target_step_type,
                input_file=job_chain_file,
                success=False,
                error=f"Subprocess execution failed: {e}",
                execution_time=time.time() - start_time,
            )

        # Parse results
        target_artifacts_dir = calculation_raw_dir / "step_artifacts" / ei.step_ulid
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
            try:
                parsed_output = json.loads(stdout)
                success = parsed_output.get("success", False)
                error = parsed_output.get("error")
            except Exception:
                error = stderr or stdout or f"Runner exited with code {return_code}"

        output_file = results_file if results_file.exists() else job_chain_file

        return StepResult(
            step_type_spec=target_step_type,
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

    def run_step_with_chain(
        self,
        target_step,
        chain_steps: List[Any],
        calculation_raw_dir: Path,
        structure_ulid: Optional[str] = None,
        project_root: Optional[Path] = None,
    ) -> StepResult:
        """
        Run a Psi4 dependency chain in one session.

        Args:
            target_step: Target Step object
            chain_steps: List of Step objects in dependency order
            calculation_raw_dir: Base working directory
            structure_ulid: Structure ULID for molecule
            project_root: Project root for resolution

        Returns:
            StepResult for the target step
        """
        start_time = time.time()
        calculation_raw_dir = Path(calculation_raw_dir)
        calculation_raw_dir.mkdir(parents=True, exist_ok=True)

        # Availability check
        probe_result = self.probe()
        if not probe_result.get("available"):
            return StepResult(
                step_type_spec="unknown",
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=probe_result.get("reason", "Psi4 not available"),
                execution_time=time.time() - start_time,
            )

        # Read target step type from step.yaml
        target_step_type = None
        if hasattr(target_step, "meta") and hasattr(target_step.meta, "path") and target_step.meta.path and project_root:
            step_yaml_path = project_root / target_step.meta.path
            if step_yaml_path.exists():
                import yaml
                step_data = yaml.safe_load(step_yaml_path.read_text()) or {}  # K4-ALLOW
                target_step_type = step_data.get("step_type_spec")

        if not target_step_type:
            return StepResult(
                step_type_spec="unknown",
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error="Failed to read machine step_type from step.yaml for target step.",
                execution_time=time.time() - start_time,
            )

        # Validate in registry
        from quantumvitas.workflow.public import get_registry, gen_from
        registry = get_registry()
        target_step_type_gen = gen_from(target_step_type)
        if not registry.has(target_step_type_gen):
            return StepResult(
                step_type_spec=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=f"Step type '{target_step_type}' not found in registry.",
                execution_time=time.time() - start_time,
            )

        # Resolve structure
        if not structure_ulid or not project_root:
            return StepResult(
                step_type_spec=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error="Structure and project_root are required for Psi4 chain execution",
                execution_time=time.time() - start_time,
            )

        structure_data = None
        try:
            from quantumvitas.core.public import require_structure
            from quantumvitas.io.structure_io import read_structure
            from pymatgen.core import Molecule as PMGMolecule

            structure_resolved = require_structure(project_root, structure_ulid, config=None, index=None)
            structure_path = structure_resolved.absolute_path
            structure = read_structure(structure_path)

            if not isinstance(structure, PMGMolecule):
                return StepResult(
                    step_type_spec=target_step_type,
                    input_file=calculation_raw_dir / "job_chain.json",
                    success=False,
                    error=f"Expected Molecule for Psi4, got {type(structure)}",
                    execution_time=time.time() - start_time,
                )

            structure_path_abs = Path(structure_path).resolve()
            structure_data = {
                "structure_path": str(structure_path_abs),
                "charge": structure.charge,
                "multiplicity": structure.spin_multiplicity,
                "unit": "Angstrom",
            }
        except Exception as e:
            import traceback
            return StepResult(
                step_type_spec=target_step_type,
                input_file=calculation_raw_dir / "job_chain.json",
                success=False,
                error=f"Failed to load structure: {e}\n{traceback.format_exc()}",
                execution_time=time.time() - start_time,
            )

        # Build chain step specs
        chain_step_specs = []
        for step in chain_steps:
            step_ulid = step.meta.ulid if hasattr(step, "meta") and hasattr(step.meta, "ulid") else "unknown"

            step_type_spec = "unknown"
            if hasattr(step, "meta") and hasattr(step.meta, "path") and step.meta.path:
                step_yaml_path = project_root / step.meta.path
                if step_yaml_path.exists():
                    import yaml
                    step_data = yaml.safe_load(step_yaml_path.read_text()) or {}  # K4-ALLOW
                    step_type_spec = step_data.get("step_type_spec") or "unknown"

            if step_type_spec == "unknown":
                return StepResult(
                    step_type_spec="unknown",
                    input_file=calculation_raw_dir / "job_chain.json",
                    success=False,
                    error=f"Failed to read step_type_spec from step.yaml for chain step {step_ulid}.",
                    execution_time=time.time() - start_time,
                )

            params = {}
            if hasattr(step, "parameters"):
                params = step.parameters.copy() if isinstance(step.parameters, dict) else step.parameters

            # Merge structure data for steps that require it
            step_type_gen = gen_from(step_type_spec)
            step_spec = registry.get(step_type_gen)
            if step_spec and step_spec.requires_structure and structure_data:
                params = {**params, **structure_data}
            elif step_spec and not step_spec.requires_structure:
                params = {k: v for k, v in params.items()
                          if k not in ("atoms", "structure_path", "charge", "multiplicity", "unit", "structure")}

            step_artifacts_dir = calculation_raw_dir / "step_artifacts" / step_ulid

            chain_step_specs.append({
                "step_ulid": step_ulid,
                "step_type_spec": step_type_spec,
                "parameters": params,
                "step_artifacts_dir": str(step_artifacts_dir),
            })

        # Write job_chain.json
        job_chain_spec = {
            "base_working_dir": str(calculation_raw_dir),
            "chain_steps": chain_step_specs,
            "target_step_ulid": target_step.meta.ulid,
            "resources": {},
        }

        job_chain_file = calculation_raw_dir / "job_chain.json"
        job_chain_file.write_text(json.dumps(job_chain_spec, indent=2))

        # Run subprocess
        cmd = self._get_runner_command() + [str(job_chain_file)]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=calculation_raw_dir,
                timeout=target_step.options.get("timeout") if hasattr(target_step, "options") else None,
            )
            stdout = result.stdout
            stderr = result.stderr
            return_code = result.returncode
        except subprocess.TimeoutExpired as e:
            return StepResult(
                step_type_spec=target_step_type,
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
                step_type_spec=target_step_type,
                input_file=job_chain_file,
                success=False,
                error=f"Subprocess execution failed: {e}",
                execution_time=time.time() - start_time,
            )

        # Parse results
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
            try:
                parsed_output = json.loads(stdout)
                success = parsed_output.get("success", False)
                error = parsed_output.get("error")
            except Exception:
                error = stderr or stdout or f"Runner exited with code {return_code}"

        output_file = results_file if results_file.exists() else job_chain_file

        return StepResult(
            step_type_spec=target_step_type,
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
