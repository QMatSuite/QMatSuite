"""
Standalone step execution context and logic.

This module provides support for running QE steps without a project context,
reusing the core run logic from the workflow system.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.workflow.input_runner import (
    run_input_step,
    prepare_input_step,
    run_prepared_step,
    PreparedInputStep,
)
from quantumvitas.core.engines.qe_workflow import StepResult
from quantumvitas.io.parser.qe_parser import QEInputParser
from quantumvitas.io.generator import QEInputGenerator


@dataclass
class StandaloneStepContext:
    """
    Context for running a step in standalone mode (no project).
    
    Attributes:
        input_file: Path to QE input file
        workdir: Working directory for execution
        outdir: QE outdir (typically workdir / "outdir")
        engine: QE engine instance
    """
    input_file: Path
    workdir: Path
    outdir: Path
    engine: QuantumEspressoEngine


def run_standalone_step(ctx: StandaloneStepContext) -> tuple[StepResult, PreparedInputStep]:
    """
    Run a QE step in standalone mode.
    
    Standalone mode always performs a full roundtrip:
    1. Read original QE input file
    2. Parse into internal representation
    3. Generate normalized QE input using QEInputGenerator
    4. Run QE on the generated input
    
    The original input is preserved as <stem>.raw.in, and the generated
    input is used for the actual QE run.
    
    Args:
        ctx: Standalone step context
        
    Returns:
        Tuple of (StepResult, PreparedInputStep)
    """
    input_file = Path(ctx.input_file).resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    workdir = Path(ctx.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    
    outdir = Path(ctx.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Standalone mode: always do roundtrip (parse → generate → run)
    original_input = input_file
    
    # Copy original to workdir if not already there
    if not original_input.is_relative_to(workdir):
        original_in_workdir = workdir / f"{original_input.stem}.raw.in"
        import shutil
        shutil.copy2(original_input, original_in_workdir)
    else:
        # If original is in workdir, rename it to .raw.in to preserve it
        original_in_workdir = workdir / f"{original_input.stem}.raw.in"
        if original_input != original_in_workdir:
            import shutil
            shutil.copy2(original_input, original_in_workdir)
    
    # Parse original input and generate normalized version
    qe_input = QEInputParser.parse_file(original_input)
    
    # Set outdir in the QE input (relative to workdir) if not already set
    outdir_rel = outdir.relative_to(workdir)
    if "CONTROL" in qe_input.namelists:
        control = qe_input.namelists["CONTROL"]
        if "outdir" not in control.parameters:
            control.parameters["outdir"] = str(outdir_rel)
    else:
        # Create CONTROL namelist if it doesn't exist
        from quantumvitas.io.model import QENamelist
        control = QENamelist("CONTROL", {"outdir": str(outdir_rel)})
        qe_input.namelists.insert(0, control)
    
    # Handle pseudopotentials: use central ensure_qe_pseudos function
    from quantumvitas.core.pseudo import ensure_qe_pseudos, get_system_pseudo_dir
    
    project_pseudo_dir = workdir / "pseudo"
    system_pseudo_dir = get_system_pseudo_dir()
    
    # Resolve pseudopotentials (this will copy required pseudos to project_pseudo_dir)
    pseudo_result = ensure_qe_pseudos(
        qe_input_file=original_input,
        project_pseudo_dir=project_pseudo_dir,
        system_pseudo_dir=system_pseudo_dir,
    )
    
    if not pseudo_result.all_available:
        raise RuntimeError(
            f"Failed to obtain required pseudopotentials. "
            f"Project pseudo dir: {project_pseudo_dir}, "
            f"System pseudo dir: {system_pseudo_dir}"
        )
    
    # Set pseudo_dir in QE input to point to project_pseudo_dir
    pseudo_dir_rel = project_pseudo_dir.relative_to(workdir)
    if "CONTROL" in qe_input.namelists:
        control = qe_input.namelists["CONTROL"]
        control.parameters["pseudo_dir"] = str(pseudo_dir_rel)
    
    # Generate normalized input file
    generated_input = workdir / f"{original_input.stem}.in"
    QEInputGenerator.write_file(qe_input, generated_input)
    
    # Use generated input for the run
    input_for_run = generated_input
    
    # Reuse existing run logic
    from quantumvitas.workflow.input_runner import run_input_step
    
    result, prepared = run_input_step(
        engine=ctx.engine,
        input_file=input_for_run,
        working_dir=workdir,
        project_root=None,  # Standalone mode: no project
        step_type=None,  # Auto-detect from input
        keep_original=False,  # We've already handled file copying
    )
    
    return result, prepared

