"""
Engine Handlers: Bridge between JobExecutor and existing engine execution logic.

These handlers wrap the existing step.run() and chain execution code,
adapting them to the Job-based execution model.

Per engine_recipes_jobgraph_plan.md (Constitution):
- Preserve existing filesystem contracts
- QE: raw/outdir unchanged
- Wannier: raw in-place unchanged
- QC: raw/scf_<suffix>/ unchanged

Architecture: Capability-based artifact production
=================================================
Handlers produce step_results with optional "relax_artifact_spec" dict
that describes how to post-process outputs into current.json.
Executor uses RELAX_ARTIFACT_HANDLERS registry to process, not engine branching.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.executor import JobResult
from quantumvitas.execution.relax_artifacts import RelaxArtifactSpec, is_relax_step_type
from quantumvitas.core.driver_registry import DriverRegistry

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.calculation.step import Step
    from quantumvitas.engine.registry import EngineRegistry


logger = logging.getLogger(__name__)


def _format_dir_listing_for_debug(dir_path: Path, max_items: int = 200) -> str:
    """
    Format directory listing with file sizes and mtimes for debug output.
    
    Args:
        dir_path: Directory to list
        max_items: Maximum number of items to list
        
    Returns:
        Formatted string with file info
    """
    if not dir_path.exists():
        return f"<directory does not exist: {dir_path}>"
    
    if not dir_path.is_dir():
        return f"<not a directory: {dir_path}>"
    
    try:
        items = sorted(dir_path.iterdir())
        if len(items) > max_items:
            items = items[:max_items]
            truncated = True
        else:
            truncated = False
        
        lines = []
        for item in items:
            try:
                stat = item.stat()
                size = stat.st_size
                mtime = stat.st_mtime
                item_type = "DIR" if item.is_dir() else "FILE"
                lines.append(f"  {item_type:4s} {item.name:50s} size={size:10d} mtime={mtime:.3f}")
            except Exception as e:
                lines.append(f"  ERR  {item.name:50s} (stat failed: {e})")
        
        result = "\n".join(lines)
        if truncated:
            total_count = len(list(dir_path.iterdir()))
            result += f"\n  ... (truncated, showing first {max_items} of {total_count} items)"
        
        return result
    except Exception as e:
        return f"<listing failed: {e}>"


# Handler type signature
HandlerFunc = Callable[[Job, "Calculation", "EngineRegistry", Dict[str, Any]], JobResult]


def _get_step_input_from_calculation_yaml(
    calculation: "Calculation",
    step_ulid: str,
) -> Optional[Path]:
    """
    Get the input file path from calculation.yaml for a given step.
    
    Used by compat input playback mode to find existing .in files.
    
    Args:
        calculation: Calculation instance
        step_ulid: Step ULID to look up
        
    Returns:
        Path to input file if found in calculation.yaml, None otherwise
    """
    import yaml
    
    calculation_yaml = calculation.dir / "calculation.yaml"
    if not calculation_yaml.exists():
        return None
    
    data = yaml.safe_load(calculation_yaml.read_text())
    steps_data = data.get("steps", [])
    
    for step_data in steps_data:
        if step_data.get("step_ulid") == step_ulid:
            input_path_value = step_data.get("input") or step_data.get("file")
            if input_path_value:
                input_path = Path(input_path_value)
                if not input_path.is_absolute():
                    # Resolve relative to calculation working_dir (raw/)
                    input_path = (calculation.working_dir / input_path).resolve()
                    if not input_path.exists():
                        # Try relative to calculation_dir
                        input_path = (calculation.dir / input_path_value).resolve()
                if input_path.exists():
                    return input_path
                else:
                    # Log for debugging
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"[COMPAT] Input file not found: {input_path} "
                        f"(working_dir={calculation.working_dir}, calc_dir={calculation.dir})"
                    )
    
    return None


def qe_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    DEPRECATED: Use quantumvitas.drivers.qe.handler.qe_step_handler
    
    This is a backward-compatibility wrapper that delegates to the new handler.
    """
    from quantumvitas.drivers.qe.handler import qe_step_handler as _qe_handler
    return _qe_handler(job, calculation, engine_registry, context)


def handle_qe_relax_output(
    step_ulid: str,
    step_type_spec: str,
    calc_dir: Path,
    output_path: Path,
    calculation_ulid: str,
    input_structure_ulid: str,
    run_ulid: Optional[str] = None,
) -> Path:
    """
    DEPRECATED: Use quantumvitas.drivers.qe.handler.handle_qe_relax_output
    
    This is a backward-compatibility wrapper that delegates to the new handler.
    """
    from quantumvitas.drivers.qe.handler import handle_qe_relax_output as _handle_relax
    return _handle_relax(
        step_ulid=step_ulid,
        step_type_spec=step_type_spec,
        calc_dir=calc_dir,
        output_path=output_path,
        calculation_ulid=calculation_ulid,
        input_structure_ulid=input_structure_ulid,
        run_ulid=run_ulid,
    )


def create_handler_map(
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> Dict[str, Callable[[Job, "Calculation"], JobResult]]:
    """
    Create a handler map for JobExecutor.

    Returns handlers that capture engine_registry and context via closure.
    This now delegates to DriverRegistry for all registered drivers.

    Args:
        engine_registry: Engine registry
        context: Execution context (run_ulid, run_mode, etc.)

    Returns:
        Dict mapping engine name to handler function
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers

    def make_handler(base_handler: HandlerFunc):
        """Create a closure that captures engine_registry and context."""
        def handler(job: Job, calculation: "Calculation") -> JobResult:
            return base_handler(job, calculation, engine_registry, context)
        return handler

    # Build handler map from registry
    handler_map = {}

    # Get handlers from registry for all registered engines
    for engine in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine)
        base_handler = driver.get_handler()
        handler_map[engine] = make_handler(base_handler)

    return handler_map


def get_handler_for_step(step_type_spec: str) -> Callable:
    """Get handler for step type via registry.

    This is the preferred entry point for handler lookup.

    Args:
        step_type_spec: Step type identifier (spec type, e.g., "qe_scf")

    Returns:
        Handler function

    Raises:
        UnknownStepTypeError: If step type not registered
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers

    return DriverRegistry.get_handler(step_type_spec)
