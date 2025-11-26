"""
Helpers for running QE steps directly from input files.

These utilities prepare working directories (outdir/pseudo_dir), ensure
pseudopotentials, and execute steps via ``QuantumEspressoEngine``.  They are
shared by tests/CLI to avoid duplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import shutil

from quantumvitas.io import (
    QEInput,
    QEInputGenerator,
    QEInputParser,
    QEModule,
    QENamelist,
)
from quantumvitas.core.engines import ensure_pseudopotentials
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.qe_workflow import StepResult


@dataclass(slots=True)
class PreparedInputStep:
    """
    Metadata for an input-driven QE step.
    """

    working_dir: Path
    original_input: Path
    modified_input: Path
    project_root: Path


def _safe_copy(src: Path, dst: Path) -> None:
    if src == dst:
        return
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except Exception:
        pass


def detect_project_root(start: Optional[Path] = None) -> Path:
    """
    Try to locate the project root (directory containing src/quantumvitas).
    """
    start_path = Path(start or Path.cwd()).resolve()
    current = start_path
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / "src" / "quantumvitas").exists():
            return current
        current = current.parent
    return start_path


def set_outdir_to_temp(qe_input: QEInput, _project_root: Optional[Path] = None) -> None:
    """
    Force outdir to ./outdir relative to the working directory.
    """
    outdir_rel = "./outdir"
    module = qe_input.module or qe_input.detect_module()
    no_control_modules = [QEModule.PH, QEModule.Q2R, QEModule.MATDYN, QEModule.DYNMAT]

    found_outdir = False
    for namelist in qe_input.namelists:
        if "outdir" in namelist.parameters:
            namelist.parameters["outdir"] = outdir_rel
            found_outdir = True

    if found_outdir:
        return

    if module in no_control_modules:
        if module == QEModule.PH:
            for namelist in qe_input.namelists:
                if namelist.name.lower() == "inputph":
                    namelist.parameters["outdir"] = outdir_rel
                    break
    else:
        control_namelist: Optional[QENamelist] = None
        for namelist in qe_input.namelists:
            if namelist.name.lower() == "control":
                control_namelist = namelist
                break
        if control_namelist:
            control_namelist.parameters["outdir"] = outdir_rel
        else:
            control_namelist = QENamelist("control", {"outdir": outdir_rel})
            qe_input.namelists.insert(0, control_namelist)


def set_pseudo_dir_to_temp(qe_input: QEInput, project_root: Path) -> None:
    """
    Force pseudo_dir to project_root/pseudo for all control namelists.
    """
    pseudo_dir_path = str((project_root / "pseudo").resolve())
    module = qe_input.module or qe_input.detect_module()
    no_control_modules = [QEModule.PH, QEModule.Q2R, QEModule.MATDYN, QEModule.DYNMAT]

    found_pseudo = False
    for namelist in qe_input.namelists:
        if "pseudo_dir" in namelist.parameters:
            namelist.parameters["pseudo_dir"] = pseudo_dir_path
            found_pseudo = True

    if found_pseudo:
        return

    if module in no_control_modules:
        return

    control_namelist: Optional[QENamelist] = None
    for namelist in qe_input.namelists:
        if namelist.name.lower() == "control":
            control_namelist = namelist
            break

    if control_namelist:
        control_namelist.parameters["pseudo_dir"] = pseudo_dir_path
    else:
        control_namelist = QENamelist("control", {"pseudo_dir": pseudo_dir_path})
        qe_input.namelists.insert(0, control_namelist)


def prepare_input_step(
    input_file: Path,
    working_dir: Path,
    project_root: Optional[Path] = None,
) -> PreparedInputStep:
    """
    Prepare a QE input file for execution inside a working directory.
    """
    project_root = detect_project_root(project_root)
    working_dir = Path(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)
    (working_dir / "outdir").mkdir(parents=True, exist_ok=True)

    unified_pseudo_dir = project_root / "pseudo"
    unified_pseudo_dir.mkdir(parents=True, exist_ok=True)
    if not ensure_pseudopotentials(input_file, working_dir, unified_pseudo_dir, None):
        raise RuntimeError("Failed to obtain required pseudopotentials")

    working_dir_input = working_dir / Path(input_file).name
    try:
        qe_input = QEInputParser.parse_file(input_file)
        set_outdir_to_temp(qe_input)
        set_pseudo_dir_to_temp(qe_input, project_root)
        QEInputGenerator.write_file(qe_input, working_dir_input)
    except Exception:
        if working_dir_input != input_file:
            shutil.copy2(input_file, working_dir_input)
        else:
            working_dir_input = input_file

    input_stem = Path(input_file).stem
    original_copy = working_dir / f"{input_stem}_original.in"
    modified_copy = working_dir / f"{input_stem}_modified.in"
    _safe_copy(input_file, original_copy)
    _safe_copy(working_dir_input, modified_copy)

    return PreparedInputStep(
        working_dir=working_dir,
        original_input=original_copy,
        modified_input=working_dir_input,
        project_root=project_root,
    )


def run_prepared_step(
    engine: QuantumEspressoEngine,
    prepared_step: PreparedInputStep,
    step_type: Optional[str] = None,
    timeout: Optional[float] = None,
) -> StepResult:
    """
    Execute a prepared input step via QE engine.
    """
    if step_type is None:
        step_type = engine.detect_step_type(prepared_step.modified_input)

    step_result = engine.run_step(
        input_file=prepared_step.modified_input,
        working_dir=prepared_step.working_dir,
        step_type=step_type,
        timeout=timeout,
    )

    expected_output = prepared_step.working_dir / f"{prepared_step.modified_input.stem}.out"
    if step_result.output_file and step_result.output_file.exists():
        if step_result.output_file != expected_output:
            step_result.output_file = expected_output

    return step_result


def run_input_step(
    engine: QuantumEspressoEngine,
    input_file: Path,
    working_dir: Path,
    project_root: Optional[Path] = None,
    step_type: Optional[str] = None,
    timeout: Optional[float] = None,
) -> tuple[StepResult, PreparedInputStep]:
    """
    Convenience function combining preparation + execution.
    """
    prepared = prepare_input_step(
        input_file=input_file,
        working_dir=working_dir,
        project_root=project_root,
    )
    result = run_prepared_step(
        engine=engine,
        prepared_step=prepared,
        step_type=step_type,
        timeout=timeout,
    )
    return result, prepared


