"""
Step definitions used by calculations.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from qmatsuite.core.public import ResourceMeta
from qmatsuite.engine.base import Engine, StepResult
from qmatsuite.project.model import StructureRef

from .input_runner import run_input_step
from .types import StepMode


@dataclass(slots=True)
class Step:
    """
    One unit of execution inside a calculation.
    """

    meta: ResourceMeta
    input_file: Path
    engine: Optional[str] = None
    step_type_spec: Optional[str] = None
    options: Dict[str, object] = field(default_factory=dict)
    mode: StepMode = StepMode.NORMAL
    reference_output: Optional[Path] = None
    structure: Optional[StructureRef] = None

    def __post_init__(self):
        """Validate that engine field is set."""
        if self.engine is None:
            raise ValueError("Step requires explicit 'engine' field")

    def resolve_input_path(self, calculation_raw_dir: Path) -> Path:
        """
        Resolve input file path relative to calculation_raw_dir.
        
        Raises ValueError if input_file is a directory (e.g., '.') or invalid.
        """
        path = Path(self.input_file)
        
        # Safety check: prevent '.' or directory paths
        if str(path) in ('.', './', '.'):
            raise ValueError(
                f"Invalid input_file '{self.input_file}': cannot be a directory. "
                f"Step input_file must point to a file, not a directory."
            )
        
        if not path.is_absolute():
            path = (calculation_raw_dir / path).resolve()
        
        # Additional safety check: ensure resolved path is not a directory
        if path.exists() and path.is_dir():
            raise ValueError(
                f"Resolved input_file path is a directory: {path}. "
                f"This usually indicates a bug where input_file was set to '.' or a directory path. "
                f"Step input_file must point to a file (e.g., 'scf.in', 'diamond.win')."
            )
        
        return path

    def run(
        self,
        engine: Engine,
        calculation_raw_dir: Path,
        project_root: Optional[Path] = None,
        species_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> StepResult:
        """
        Execute the step using the provided engine inside the calculation raw dir.
        
        Args:
            engine: Engine to use for execution
            calculation_raw_dir: Working directory for this calculation (e.g., raw_dir)
            project_root: Project root path (can be None for standalone mode)
            species_map: Optional species mapping from calculation (for pseudo materialization)
        """
        if engine.name != "qe":
            return engine.run_step(self, calculation_raw_dir)

        from qmatsuite.engine.qe_engine import QeEngine

        if not isinstance(engine, QeEngine):
            raise TypeError("QE steps require QeEngine instances")

        import logging
        logger = logging.getLogger(__name__)
        
        try:
            input_path = self.resolve_input_path(calculation_raw_dir)
            step_type_value = self.step_type_spec
            timeout = self.options.get("timeout")

            # E. Logging: Essential info only
            logger.debug(
                f"[Step.run] Executing step: slug={self.meta.slug}, ulid={self.meta.ulid}, type={step_type_value}"
            )
            
            # Production run contract: never parse .in files during execution.
            # The .in file was already generated from step.yaml by materialize_step_spec()
            # with all cards, parameters, and runtime overrides (outdir, pseudo_dir) applied.
            # We simply call the engine directly with the generated input file.
            # See docs/dev/exec-pipeline-ssot-contract.md for details.
            
            # Resolve pseudo_dir for engine (already set in .in by materialize_step_spec during materialization)
            # In standalone mode, pseudo_dir is set relative to workdir during materialization
            
            # Call engine directly - no re-parsing of .in file
            result = engine.backend.run_step(
                input_file=input_path,
                working_dir=calculation_raw_dir,
                step_type_spec=step_type_value,
                timeout=timeout,
            )
            
            logger.debug(
                f"[Step.run] Step {self.meta.slug} (ulid={self.meta.ulid}) completed: success={result.success}, return_code={getattr(result, 'return_code', 'N/A')}"
            )
            
            return result
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            logger.exception(f"[Step.run] Step {self.meta.slug} (ulid={self.meta.ulid}) raised exception: {type(e).__name__}: {e}")
            
            # Create a failed StepResult from the exception
            from qmatsuite.engine.base import StepResult as StepResultClass
            return StepResultClass(
                step_type_spec=self.step_type_spec or "unknown",
                input_file=getattr(self, 'input_file', Path()),
                success=False,
                error=f"{type(e).__name__}: {str(e)}\n\nTraceback (first 500 chars):\n{tb_str[:500]}",
                return_code=-1,
            )

