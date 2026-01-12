"""
Step definitions used by calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from quantumvitas.core.resources import ResourceMeta
from quantumvitas.engine.base import Engine, StepResult
from quantumvitas.project.model import StructureRef

from .input_runner import run_input_step
from .types import StepMode, StepType


@dataclass(slots=True)
class Step:
    """
    One unit of execution inside a calculation.
    """

    meta: ResourceMeta
    input_file: Path
    engine: str = "qe"
    step_type: Optional[StepType] = None
    options: Dict[str, object] = field(default_factory=dict)
    mode: StepMode = StepMode.NORMAL
    reference_output: Optional[Path] = None
    structure: Optional[StructureRef] = None

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
        project_root: Path,
        species_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> StepResult:
        """
        Execute the step using the provided engine inside the calculation raw dir.
        
        Args:
            engine: Engine to use for execution
            calculation_raw_dir: Working directory for this calculation (e.g., raw_dir)
            project_root: Project root path
            species_map: Optional species mapping from calculation (for pseudo materialization)
        """
        if engine.name != "qe":
            return engine.run_step(self, calculation_raw_dir)

        from quantumvitas.engine.qe_engine import QeEngine

        if not isinstance(engine, QeEngine):
            raise TypeError("QE steps require QeEngine instances")

        import logging
        logger = logging.getLogger(__name__)
        
        try:
            input_path = self.resolve_input_path(calculation_raw_dir)
            step_type_value = self.step_type.value if self.step_type else None
            timeout = self.options.get("timeout")

            # E. Logging: Essential info only
            logger.debug(
                f"[Step.run] Executing step: slug={self.meta.slug}, ulid={self.meta.id}, type={step_type_value}"
            )
            
            result, _ = run_input_step(
                engine=engine.backend,
                input_file=input_path,
                working_dir=calculation_raw_dir,
                project_root=project_root,
                step_type=step_type_value,
                timeout=timeout,
                species_map=species_map,
            )
            
            logger.debug(
                f"[Step.run] Step {self.meta.slug} (ulid={self.meta.id}) completed: success={result.success}, return_code={getattr(result, 'return_code', 'N/A')}"
            )
            
            return result
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            logger.exception(f"[Step.run] Step {self.meta.slug} (ulid={self.meta.id}) raised exception: {type(e).__name__}: {e}")
            
            # Create a failed StepResult from the exception
            from quantumvitas.engine.base import StepResult as StepResultClass
            return StepResultClass(
                step_type=str(self.step_type.value) if self.step_type else "unknown",
                input_file=getattr(self, 'input_file', Path()),
                success=False,
                error=f"{type(e).__name__}: {str(e)}\n\nTraceback (first 500 chars):\n{tb_str[:500]}",
                return_code=-1,
            )

