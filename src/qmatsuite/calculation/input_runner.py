"""
Helpers for running QE steps directly from input files.

These utilities prepare working directories (outdir/pseudo_dir), ensure
pseudopotentials, and execute steps via ``QuantumEspressoEngine``.  They are
shared by tests/CLI to avoid duplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence
import shutil

from qmatsuite.io import (
    QECard,
    QECardType,
    QEInput,
    QEInputGenerator,
    QEInputParser,
    QEModule,
    QENamelist,
)
# Pseudopotential resolution is handled by ensure_qe_pseudos in qmatsuite.core.pseudo
from qmatsuite.core.public import QuantumEspressoEngine, StepResult
from qmatsuite.data import get_module_param_sections, load_qe_parameter_map


@dataclass(slots=True)
class PreparedInputStep:
    """
    Metadata for an input-driven QE step.
    """

    working_dir: Path
    original_input: Path
    modified_input: Path
    project_root: Optional[Path]  # None in standalone mode


@dataclass(slots=True)
class ParameterOverride:
    """
    Declarative override for a QE namelist parameter.
    """

    name: str
    value: Any
    section: Optional[str] = None


def _safe_copy(src: Path, dst: Path) -> None:
    if src == dst:
        return
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except Exception:
        pass


def detect_project_root(start: Optional[Path] = None, *, stop_at: Optional[Path] = None) -> Optional[Path]:
    """
    [DEPRECATED] Legacy alias for find_project_root.
    
    This function previously used repo markers (src/qmatsuite) which was incorrect.
    It now delegates to the canonical marker-based detection (project.qms.yml).
    
    Use find_project_root() or require_project_root() from qmatsuite.core.project_utils instead.
    """
    from qmatsuite.core.public import find_project_root
    return find_project_root(start, stop_at=stop_at)


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


def set_pseudo_dir_in_input(qe_input: QEInput, pseudo_dir: Path, working_dir: Path) -> None:
    """
    Set pseudo_dir in QE input to point to the project/run pseudo directory.
    
    The pseudo_dir is set as a relative path from working_dir if provided,
    otherwise as an absolute path.
    
    Args:
        qe_input: QE input object to modify
        pseudo_dir: Absolute path to the project/run pseudo directory
        working_dir: Optional working directory (for computing relative path)
    """
    # GUARD: Never use repo_root/pseudo (safety check)
    from qmatsuite.core.pseudo_config import _find_qmatsuite_root
    repo_root = _find_qmatsuite_root()
    if repo_root:
        pseudo_resolved = pseudo_dir.resolve()
        repo_pseudo = (repo_root / "pseudo").resolve()
        if pseudo_resolved == repo_pseudo:
            raise RuntimeError(
                f"BUG: set_pseudo_dir_in_input attempted to use repo_root/pseudo at {pseudo_dir}. "
                f"Internal pseudo library must be at resources/pseudo, not repo_root/pseudo."
            )
    
    # Compute relative path from working_dir to pseudo_dir if working_dir is provided
    if working_dir:
        try:
            pseudo_dir_rel = pseudo_dir.relative_to(working_dir)
            pseudo_dir_str = str(pseudo_dir_rel)
        except ValueError:
            # If pseudo_dir is not relative to working_dir, use absolute path
            pseudo_dir_str = str(pseudo_dir.resolve())
    else:
        # No working_dir provided, use absolute path
        pseudo_dir_str = str(pseudo_dir.resolve())
    
    module = qe_input.module or qe_input.detect_module()
    # Post-processing modules that don't have &CONTROL namelist
    # bands.x, dos.x, projwfc.x, pp.x only have their own namelists (&BANDS, &DOS, &PROJWFC, &INPUTPP)
    no_control_modules = [
        QEModule.PH, QEModule.Q2R, QEModule.MATDYN, QEModule.DYNMAT,
        QEModule.BANDS, QEModule.DOS, QEModule.PROJWFC, QEModule.PP,
    ]

    found_pseudo = False
    for namelist in qe_input.namelists:
        if "pseudo_dir" in namelist.parameters:
            namelist.parameters["pseudo_dir"] = pseudo_dir_str
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
        control_namelist.parameters["pseudo_dir"] = pseudo_dir_str
    else:
        control_namelist = QENamelist("control", {"pseudo_dir": pseudo_dir_str})
        qe_input.namelists.insert(0, control_namelist)


def set_pseudo_dir_to_temp(qe_input: QEInput, project_root: Path) -> None:
    """
    [DEPRECATED] Legacy function for backwards compatibility.
    
    Use set_pseudo_dir_in_input() instead.
    """
    project_root_path = Path(project_root).resolve()
    
    # Validate project_root is not repo root
    from qmatsuite.core.pseudo_config import _find_qmatsuite_root
    repo_root = _find_qmatsuite_root()
    if repo_root and project_root_path == repo_root.resolve():
        raise ValueError(
            f"Project root cannot be the repository root. "
            f"Provided project_root={project_root} is the repo root, which is invalid."
        )
    
    pseudo_dir = project_root_path / "pseudo"
    # Use working_dir = project_root as fallback (not ideal but maintains compatibility)
    set_pseudo_dir_in_input(qe_input, pseudo_dir, project_root)


def prepare_input_step(
    input_file: Path,
    working_dir: Path,
    project_root: Optional[Path] = None,
    parameter_overrides: Optional[Sequence[ParameterOverride]] = None,
    card_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    species_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    keep_original: bool = True,
    output_name: Optional[str] = None,
    step_type_spec: Optional[str] = None,
) -> PreparedInputStep:
    """
    Prepare a QE input file for execution inside a working directory.
    
    Args:
        input_file: Path to the original QE input file (or Wannier90 .win/.pw2wan file)
        working_dir: Directory where execution will take place
        project_root: Project root for pseudo_dir resolution
        parameter_overrides: Optional parameter overrides
        card_overrides: Optional card overrides
        species_overrides: Optional species overrides
        keep_original: If True and input comes from outside working_dir, 
                       save a copy as <name>_original.in
        output_name: Optional name for the generated input file (default: use input name)
        step_type_spec: Optional spec step type (e.g., "w90_wannierprep", "w90_wannier", "qe_pw2wannier")
                       If wannier90 step types, skip QE processing
    
    Returns:
        PreparedInputStep with paths to working directory and input files
        
    File naming convention:
        - Final input file: <name>.in or output_name if specified
        - Original copy: <name>_original.in (only if keep_original=True and 
          input is from outside working_dir)
    """
    # Wannier90 steps: skip QE input processing, just copy/move the file
    # Convert spec types to gen types for comparison
    from qmatsuite.workflow.step_type_convert import gen_from, is_spec
    WANNIER90_GEN_STEPS = {"wannierprep", "wannier", "pw2wannier"}
    if step_type_spec:
        step_type_gen = gen_from(step_type_spec) if is_spec(step_type_spec) else step_type_spec
        if step_type_gen.lower() in WANNIER90_GEN_STEPS:
            import logging
            logger = logging.getLogger(__name__)
            
            logger.info(f"[PREPARE_INPUT_STEP] Wannier90 step detected: step_type_spec={step_type_spec}")
        logger.debug(f"[PREPARE_INPUT_STEP] input_file: {input_file}")
        logger.debug(f"[PREPARE_INPUT_STEP] working_dir: {working_dir}")
        
        # For Wannier90 steps, the input file is already generated correctly (e.g., .win, .pw2wan)
        # Just ensure it's in the working directory
        input_path = Path(input_file)
        
        # Safety check: prevent '.' or directory paths
        if str(input_path) in (".", "./", ".."):
            logger.error(f"[PREPARE_INPUT_STEP] ERROR: input_file is '.' or invalid: '{input_file}'")
            raise ValueError(
                f"Invalid input_file for Wannier90 step: '{input_file}'. "
                f"Cannot be '.' or a directory. Must be a valid file path (e.g., 'diamond.win', 'pw2wan.in')."
            )
        
        # Resolve to absolute path for validation
        input_path_resolved = input_path.resolve()
        logger.debug(f"[PREPARE_INPUT_STEP] input_path_resolved: {input_path_resolved}")
        
        # Safety check: ensure it's not a directory
        if input_path_resolved.exists() and input_path_resolved.is_dir():
            logger.error(f"[PREPARE_INPUT_STEP] ERROR: input_file is a directory: {input_path_resolved}")
            raise ValueError(
                f"input_file is a directory: {input_path_resolved}. "
                f"Must be a file path (e.g., 'diamond.win', 'pw2wan.in')."
            )
        
        # Safety check: ensure file exists
        if not input_path_resolved.exists():
            logger.error(f"[PREPARE_INPUT_STEP] ERROR: input_file does not exist: {input_path_resolved}")
            raise FileNotFoundError(
                f"Wannier90 input file not found: {input_path_resolved}. "
                f"Step materialization may have failed to generate the input file."
            )
        
        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
        
        if output_name:
            working_dir_input = working_dir / output_name
        else:
            working_dir_input = working_dir / input_path.name
        
        logger.debug(f"[PREPARE_INPUT_STEP] working_dir_input: {working_dir_input}")
        
        # Copy to working directory if different
        if input_path_resolved != working_dir_input.resolve():
            import shutil
            logger.debug(f"[PREPARE_INPUT_STEP] Copying {input_path_resolved} to {working_dir_input}")
            shutil.copy2(input_path_resolved, working_dir_input)
        
        logger.debug(f"[PREPARE_INPUT_STEP] Wannier90 step prepared: {working_dir_input.name}")
        
        # Return PreparedInputStep with original and modified pointing to same file
        return PreparedInputStep(
            working_dir=working_dir,
            original_input=input_path_resolved,
            modified_input=working_dir_input,
            project_root=project_root,
        )
    # Handle project_root: if None, try to detect from working_dir using marker-based detection
    # If provided, validate it is not repo root and use as-is
    from qmatsuite.core.public import find_project_root
    from qmatsuite.core.pseudo_config import _find_qmatsuite_root
    
    if project_root is None:
        # Auto-detect from working_dir using marker-based detection
        # Use stop_at=None to allow full upward search (product mode)
        detected_project_root = find_project_root(start=working_dir, stop_at=None)
        if detected_project_root:
            # Validate it's not repo root
            repo_root = _find_qmatsuite_root()
            if repo_root and detected_project_root.resolve() == repo_root.resolve():
                # Repo root detected - treat as standalone mode (don't raise, just ignore)
                project_root = None
            else:
                project_root = detected_project_root
        # If not found, project_root stays None (standalone mode)
    else:
        # Validate provided project_root is not repo root
        project_root = Path(project_root).resolve()
        repo_root = _find_qmatsuite_root()
        if repo_root and project_root == repo_root.resolve():
            raise ValueError(
                f"Project root cannot be the repository root. "
                f"Provided project_root={project_root} is the repo root, which is invalid."
            )
    
    working_dir = Path(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)
    (working_dir / "outdir").mkdir(parents=True, exist_ok=True)

    input_path = Path(input_file)
    
    # Determine output file name
    if output_name:
        working_dir_input = working_dir / output_name
    else:
        working_dir_input = working_dir / input_path.name
    
    # Track if input comes from outside working_dir
    input_is_external = input_path.resolve().parent != working_dir.resolve()
    original_copy: Optional[Path] = None
    
    # Constitution: QE runtime only reads project/pseudo
    # Step0 has already prepared pseudos in project/pseudo (if in project mode)
    if project_root is not None:
        project_pseudo_dir = project_root / "pseudo"
    else:
        # Standalone mode: use workdir/pseudo (no Step0 in standalone)
        project_pseudo_dir = working_dir / "pseudo"
    
    # Use central pseudopotential resolution
    from qmatsuite.core.public import ensure_qe_pseudos, get_system_pseudo_dir
    
    pseudo_result = ensure_qe_pseudos(
        qe_input_file=input_file,
        project_pseudo_dir=project_pseudo_dir,
        system_pseudo_dir=get_system_pseudo_dir(),
    )
    
    if not pseudo_result.all_available:
        # This is a missing file error (pseudopotential was configured but file not found)
        # Configuration errors are caught earlier in ensure_qe_pseudos
        raise RuntimeError(
            f"Pseudopotential file(s) not found or could not be downloaded. "
            f"This is a missing file error (pseudopotential was configured but the file is missing). "
            f"Project pseudo dir: {project_pseudo_dir}. "
            f"Check that the pseudopotential filenames in your step spec are correct and the files exist."
        )
    
    try:
        qe_input = QEInputParser.parse_file(input_file)
        if parameter_overrides:
            _apply_parameter_overrides(qe_input, parameter_overrides)
        apply_card_overrides_to_qe_input(qe_input, card_overrides)
        apply_species_overrides_to_qe_input(qe_input, species_overrides)
        set_outdir_to_temp(qe_input)
        # Set pseudo_dir to point to project/run pseudo directory
        set_pseudo_dir_in_input(qe_input, project_pseudo_dir, working_dir)
        QEInputGenerator.write_file(qe_input, working_dir_input)
        
        # Only keep a copy of original if:
        # 1. keep_original is True
        # 2. Input comes from outside the working directory
        if keep_original and input_is_external:
            original_copy = working_dir / f"{input_path.stem}_original.in"
            _safe_copy(input_file, original_copy)
    except Exception:
        if working_dir_input != input_file:
            shutil.copy2(input_file, working_dir_input)
        else:
            working_dir_input = input_file

    # For PreparedInputStep, project_root can be None in standalone mode
    return PreparedInputStep(
        working_dir=working_dir,
        original_input=original_copy or input_path,
        modified_input=working_dir_input,
        project_root=project_root or Path.cwd(),  # Use cwd as fallback for dataclass
    )


def run_prepared_step(
    engine: QuantumEspressoEngine,
    prepared_step: PreparedInputStep,
    step_type_spec: Optional[str] = None,
    timeout: Optional[float] = None,
) -> StepResult:
    """
    Execute a prepared input step via QE engine.
    
    Args:
        step_type_spec: Optional spec step type (e.g., "qe_scf", "qe_nscf").
                       If None, will be detected from input file.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if step_type_spec is None:
        # detect_step_type returns gen type, convert to spec
        step_type_gen = engine.detect_step_type(prepared_step.modified_input)
        from qmatsuite.workflow.step_type_convert import spec_from
        # QE engine always uses "qe" prefix
        step_type_spec = spec_from("qe", step_type_gen)
    
    # E. Logging: Details at DEBUG level
    logger.debug(
        f"[RUN_PREPARED_STEP] step_type_spec={step_type_spec}, "
        f"input={prepared_step.modified_input.name if hasattr(prepared_step.modified_input, 'name') else prepared_step.modified_input}, "
        f"working_dir={prepared_step.working_dir}"
    )
    
    # For pw2wannier, ensure input file path is correct
    if step_type_spec == "qe_pw2wannier":
        # Use filename relative to working_dir for -i flag
        if prepared_step.modified_input.is_absolute():
            try:
                # Try to make it relative to working_dir
                rel_path = prepared_step.modified_input.relative_to(prepared_step.working_dir.resolve())
                logger.debug(f"[RUN_PREPARED_STEP] pw2wannier: converted to relative: {rel_path}")
                input_file_for_command = rel_path
            except ValueError:
                # Not relative, keep absolute
                input_file_for_command = prepared_step.modified_input
                logger.debug(f"[RUN_PREPARED_STEP] pw2wannier: using absolute path")
        else:
            input_file_for_command = prepared_step.modified_input
    else:
        input_file_for_command = prepared_step.modified_input

    step_result = engine.run_step(
        input_file=input_file_for_command,
        working_dir=prepared_step.working_dir,
        step_type_spec=step_type_spec,
        timeout=timeout,
    )

    # Note: step_result.output_file is already correctly set by engine.run_step
    # to {step_type}.out (not based on input filename). Do not override it.
    # The old logic that tried to match input filename was incorrect and caused
    # issues with versioned input files (e.g., scf-1.in -> scf-1.out instead of scf.out).

    return step_result


def run_input_step(
    engine: QuantumEspressoEngine,
    input_file: Path,
    working_dir: Path,
    project_root: Optional[Path] = None,
    step_type_spec: Optional[str] = None,
    timeout: Optional[float] = None,
    parameter_overrides: Optional[Sequence[ParameterOverride]] = None,
    card_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    species_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    keep_original: bool = True,
    output_name: Optional[str] = None,
    species_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[StepResult, PreparedInputStep]:
    """
    Convenience function combining preparation + execution.
    
    Args:
        engine: QE engine to execute the step
        input_file: Path to the QE input file (or Wannier90 .win/.pw2wan file)
        working_dir: Working directory for execution
        project_root: Project root for pseudo_dir resolution
        step_type_spec: Optional spec step type override (e.g., "qe_scf", "w90_wannier")
        timeout: Optional execution timeout
        parameter_overrides: Optional parameter overrides
        card_overrides: Optional card overrides
        species_overrides: Optional species overrides
        keep_original: If True and input is from outside working_dir, 
                       save original as <name>_original.in
        output_name: Optional name for the generated input file
        species_map: Optional calculation-level species_map (for sha256-pinned pseudo materialization)
    
    Returns:
        Tuple of (StepResult, PreparedInputStep)
    """
    # Constitution: Pseudos are prepared in project/pseudo by Step0 (before this function is called)
    # No materialization needed here - Step0 has already handled it
    # This function only prepares the QE input file, which references project/pseudo
    
    prepared = prepare_input_step(
        input_file=input_file,
        working_dir=working_dir,
        project_root=project_root,
        parameter_overrides=parameter_overrides,
        card_overrides=card_overrides,
        species_overrides=species_overrides,
        keep_original=keep_original,
        output_name=output_name,
        step_type_spec=step_type_spec,  # Pass step_type_spec so Wannier90 steps skip QE processing
    )
    result = run_prepared_step(
        engine=engine,
        prepared_step=prepared,
        step_type_spec=step_type_spec,
        timeout=timeout,
    )
    return result, prepared


# Legacy function kept for backward compatibility.
# New code should use get_module_param_sections() from qe_metadata instead.
_PARAMETER_MAP_CACHE: Optional[Dict[str, Any]] = None


def _get_parameter_map() -> Dict[str, Any]:
    """Legacy function - use get_module_param_sections() instead."""
    global _PARAMETER_MAP_CACHE
    if _PARAMETER_MAP_CACHE is None:
        _PARAMETER_MAP_CACHE = load_qe_parameter_map()
    return _PARAMETER_MAP_CACHE


def _normalize_section_name(section: str) -> str:
    normalized = section.strip()
    if not normalized:
        return ""
    normalized = normalized.upper()
    if not normalized.startswith("&"):
        normalized = f"&{normalized}"
    return normalized


def _resolve_override_key(
    param_name: str,
    section_hint: Optional[str],
    param_to_sections: Dict[str, list[str]],
    module_key: str,
) -> tuple[str, bool, Optional[str]]:
    """
    Resolve override key to target section following new rules:
    - Unqualified (no section hint): Must use JSON to infer, fail if not found or ambiguous
    - Qualified (has section hint): Always allow, warn if unknown or mismatch
    
    Args:
        param_name: Parameter name (e.g., "ecutwfc")
        section_hint: Optional section prefix (e.g., "SYSTEM" or None)
        param_to_sections: Mapping from param.lower() -> list of canonical sections
        module_key: QE module name (for error messages)
    
    Returns:
        Tuple of (target_section, is_known, warning_message)
        - target_section: Canonical section name (e.g., "&SYSTEM")
        - is_known: Whether parameter is known in JSON schema
        - warning_message: Optional warning message (None if no warning)
    
    Raises:
        ValueError: For unqualified unknown parameters or ambiguous parameters
    """
    canonical_param = param_name.lower()
    available_sections = param_to_sections.get(canonical_param, [])
    is_known = len(available_sections) > 0
    
    if section_hint:
        # Qualified parameter: always allow
        target_section = _normalize_section_name(section_hint)
        warning = None
        
        if not is_known:
            warning = (
                f"Parameter '{param_name}' is not defined in QE schema for module '{module_key}'. "
                f"Writing to section '{target_section}' anyway (qualified override)."
            )
        elif target_section not in available_sections:
            warning = (
                f"Parameter '{param_name}' belongs to {available_sections} according to QE schema, "
                f"but writing to '{target_section}' as specified (qualified override)."
            )
        
        return (target_section, is_known, warning)
    else:
        # Unqualified parameter: must infer from JSON
        if not is_known:
            raise ValueError(
                f"Parameter '{param_name}' is not defined for module '{module_key}'. "
                f"Provide the section explicitly via SECTION.{param_name}=value."
            )
        if len(available_sections) > 1:
            raise ValueError(
                f"Parameter '{param_name}' exists in multiple sections {available_sections}. "
                f"Specify the section explicitly via SECTION.{param_name}=value."
            )
        # Unique match: use canonical section
        target_section = available_sections[0]
        return (target_section, True, None)


def _apply_parameter_overrides(
    qe_input: QEInput, overrides: Sequence[ParameterOverride]
) -> None:
    """
    Apply CLI-specified overrides to the parsed QE input.
    
    New rules:
    - Unqualified parameters (no section): Must use JSON to infer canonical section
    - Qualified parameters (has section): Always allow, warn if unknown or mismatch
    - Unknown unqualified parameters: Fail with error
    """

    if not overrides:
        return

    module = qe_input.module or qe_input.detect_module()
    module_key = module.value
    
    # Use the centralized helper instead of direct JSON access
    sections = get_module_param_sections(module_key)
    if not sections:
        raise ValueError(
            f"No parameter metadata available for module '{module_key}'. Unable to apply overrides."
        )
    
    section_lookup = {name.upper(): params for name, params in sections.items()}

    # Build param -> sections mapping for inference
    param_to_sections: Dict[str, list[str]] = {}
    for section_name, params in sections.items():
        canonical_section = section_name.upper()
        for param in params:
            param_to_sections.setdefault(param.lower(), []).append(canonical_section)

    import warnings
    
    for override in overrides:
        param_name = override.name.strip()
        if not param_name:
            continue
        
        # Resolve target section using new rules
        target_section, is_known, warning = _resolve_override_key(
            param_name=param_name,
            section_hint=override.section,
            param_to_sections=param_to_sections,
            module_key=module_key,
        )
        
        # Emit warning if needed (for qualified overrides)
        if warning:
            warnings.warn(warning, UserWarning, stacklevel=2)
        
        # Validate section exists (for qualified overrides)
        if target_section not in section_lookup:
            # For qualified overrides, allow unknown sections (just warn)
            if override.section:
                warnings.warn(
                    f"Section '{target_section}' is not a known section for module '{module_key}'. "
                    f"Writing parameter '{param_name}' anyway (qualified override).",
                    UserWarning,
                    stacklevel=2,
                )
            else:
                # This should not happen for unqualified (caught in _resolve_override_key)
                raise ValueError(
                    f"Resolved section '{target_section}' is not valid for module '{module_key}'."
                )

        namelist_name = target_section.lstrip("&")
        target_namelist = qe_input.get_namelist(namelist_name)
        if target_namelist is None:
            target_namelist = QENamelist(name=namelist_name)
            qe_input.namelists.append(target_namelist)

        target_namelist.parameters[param_name] = override.value


def apply_species_overrides_to_qe_input(
    qe_input: QEInput, overrides: Optional[Mapping[str, Mapping[str, Any]]]
) -> None:
    """
    Apply element-specific mass/pseudopotential overrides to ATOMIC_SPECIES card.
    """

    if not overrides:
        return
    species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    if not species_card or not species_card.data:
        return

    def normalize_symbol(symbol: str) -> str:
        return str(symbol).strip().lower()

    lookup: Dict[str, list] = {}
    for row in species_card.data:
        if not row:
            continue
        symbol_key = normalize_symbol(row[0])
        lookup[symbol_key] = row

    for symbol, values in overrides.items():
        row = lookup.get(normalize_symbol(symbol))
        if not row:
            continue
        if "mass" in values:
            while len(row) < 2:
                row.append(None)
            try:
                row[1] = float(values["mass"])
            except (TypeError, ValueError):
                row[1] = values["mass"]
        # Check both "pseudopot" (legacy) and "pseudo_basename" (new)
        pseudo_value = values.get("pseudopot") or values.get("pseudo_basename")
        if pseudo_value:
            while len(row) < 3:
                row.append("")
            # Only set if value is non-empty (empty string means keep placeholder/default)
            row[2] = str(pseudo_value)
            # If empty, leave placeholder in place (will be caught by ensure_qe_pseudos)


def apply_card_overrides_to_qe_input(
    qe_input: QEInput, overrides: Optional[Mapping[str, Mapping[str, Any]]]
) -> None:
    if not overrides:
        return

    card_lookup: Dict[str, QECard] = {
        card.card_type.name: card for card in qe_input.cards
    }
    for card_name, payload in overrides.items():
        try:
            card_type = QECardType[card_name]
        except KeyError as exc:
            raise ValueError(f"Unknown card type '{card_name}' in overrides.") from exc
        card = card_lookup.get(card_type.name)
        if card is None:
            card = QECard(card_type=card_type)
            qe_input.cards.append(card)
            card_lookup[card_type.name] = card
        
        # For K_POINTS cards with k-path formats (crystal_b, crystal_c, tpiba_b, tpiba_c),
        # we must have valid data. If option is set but data is missing/invalid, clear the option.
        if card.card_type == QECardType.K_POINTS:
            if "option" in payload:
                new_option = payload.get("option")
                # K-path formats require valid segment data
                kpath_formats = ["crystal_b", "crystal_c", "tpiba_b", "tpiba_c"]
                if new_option and new_option.lower() in kpath_formats:
                    # If setting to k-path format, data must be provided and valid
                    if "data" not in payload:
                        raise ValueError(
                            f"K_POINTS option '{new_option}' requires 'data' to be provided. "
                            "K-path formats (crystal_b, crystal_c, tpiba_b, tpiba_c) cannot use automatic grid data."
                        )
                    # Validate data format (should be list of [kx, ky, kz, npts] rows)
                    data = payload.get("data")
                    if not data or not isinstance(data, list):
                        raise ValueError(
                            f"K_POINTS option '{new_option}' requires 'data' to be a non-empty list of "
                            "[kx, ky, kz, npts] segments."
                        )
                card.option = new_option
            elif "data" in payload:
                # Clear default 'automatic' option when explicit k-point list is provided
                card.option = None
        
        # For non-K_POINTS cards or if option wasn't handled above
        if card.card_type != QECardType.K_POINTS and "option" in payload:
            card.option = payload.get("option")
        
        if "data" in payload:
            card.data = _normalize_card_data(payload["data"])
        rows = payload.get("rows")
        if rows:
            card.data = _apply_row_updates(card.data, rows)

    _sort_cards(qe_input)


_CARD_PRIORITY = {
    QECardType.ATOMIC_SPECIES: 0,
    QECardType.ATOMIC_POSITIONS: 1,
    QECardType.CELL_PARAMETERS: 2,
    QECardType.K_POINTS: 3,
}


def _sort_cards(qe_input: QEInput) -> None:
    qe_input.cards = sorted(
        qe_input.cards, key=lambda c: _CARD_PRIORITY.get(c.card_type, 999)
    )


def _normalize_card_data(data: Any) -> List[List[Any]]:
    if data is None:
        return []
    if not isinstance(data, list):
        return [[data]]
    normalized: List[List[Any]] = []
    for row in data:
        if isinstance(row, list):
            normalized.append(row)
        else:
            normalized.append([row])
    return normalized


def _apply_row_updates(
    existing: List[Any], updates: Mapping[str, List[Any]]
) -> List[List[Any]]:
    data = _normalize_card_data(existing)
    for key, row in updates.items():
        idx = _row_index_from_key(key)
        while len(data) <= idx:
            data.append([])
        data[idx] = row
    return data


def _row_index_from_key(key: str) -> int:
    digits = "".join(ch for ch in key if ch.isdigit())
    if digits:
        return max(int(digits) - 1, 0)
    raise ValueError(
        f"Row override '{key}' must include a numeric index, e.g. row1, row2, ..."
    )
def apply_parameter_overrides(
    qe_input: QEInput, overrides: Sequence[ParameterOverride]
) -> None:
    """
    Public helper to apply parameter overrides to a QE input file.
    """

    _apply_parameter_overrides(qe_input, overrides)


def parameter_dict_to_overrides(
    parameter_dict: Mapping[str, Mapping[str, Any]] | None,
) -> list[ParameterOverride]:
    """
    Convert nested parameter dictionaries into ParameterOverride objects.

    Expected format:
    {
        "CONTROL": {"calculation": "scf", "prefix": "si"},
        "SYSTEM": {"ecutwfc": 60, "ecutrho": 240},
    }
    """

    overrides: list[ParameterOverride] = []
    if not parameter_dict:
        return overrides

    for section, params in parameter_dict.items():
        if not isinstance(params, Mapping):
            overrides.append(
                ParameterOverride(
                    name=str(section),
                    value=params,
                    section=None,
                )
            )
            continue

        for name, value in params.items():
            overrides.append(
                ParameterOverride(
                    name=str(name),
                    value=value,
                    section=section,
                )
            )

    return overrides


