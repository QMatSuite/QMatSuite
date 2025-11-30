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

from quantumvitas.io import (
    QECard,
    QECardType,
    QEInput,
    QEInputGenerator,
    QEInputParser,
    QEModule,
    QENamelist,
)
from quantumvitas.core.engines import ensure_pseudopotentials
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.qe_workflow import StepResult
from quantumvitas.data import load_qe_parameter_map


@dataclass(slots=True)
class PreparedInputStep:
    """
    Metadata for an input-driven QE step.
    """

    working_dir: Path
    original_input: Path
    modified_input: Path
    project_root: Path


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
    parameter_overrides: Optional[Sequence[ParameterOverride]] = None,
    card_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    species_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    keep_original: bool = True,
) -> PreparedInputStep:
    """
    Prepare a QE input file for execution inside a working directory.
    
    Args:
        input_file: Path to the original QE input file
        working_dir: Directory where execution will take place
        project_root: Project root for pseudo_dir resolution
        parameter_overrides: Optional parameter overrides
        card_overrides: Optional card overrides
        species_overrides: Optional species overrides
        keep_original: If True and input is modified, save original as <name>_original.in
    
    Returns:
        PreparedInputStep with paths to working directory and input files
    """
    project_root = detect_project_root(project_root)
    working_dir = Path(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)
    (working_dir / "outdir").mkdir(parents=True, exist_ok=True)

    input_path = Path(input_file)
    # Use a clean input file name in the working directory
    working_dir_input = working_dir / input_path.name
    
    # If input is already in working dir, use a different name for the processed version
    if input_path.resolve().parent == working_dir.resolve():
        working_dir_input = working_dir / f"{input_path.stem}_run.in"
    
    original_copy = input_path  # Default: original is the source file
    
    try:
        qe_input = QEInputParser.parse_file(input_file)
        if parameter_overrides:
            _apply_parameter_overrides(qe_input, parameter_overrides)
        apply_card_overrides_to_qe_input(qe_input, card_overrides)
        apply_species_overrides_to_qe_input(qe_input, species_overrides)
        set_outdir_to_temp(qe_input)
        set_pseudo_dir_to_temp(qe_input, project_root)
        QEInputGenerator.write_file(qe_input, working_dir_input)
        
        # Only keep a copy of original if requested and input was modified
        if keep_original and input_path.resolve() != working_dir_input.resolve():
            original_copy = working_dir / f"{input_path.stem}_original.in"
            _safe_copy(input_file, original_copy)
    except Exception:
        if working_dir_input != input_file:
            shutil.copy2(input_file, working_dir_input)
        else:
            working_dir_input = input_file

    unified_pseudo_dir = project_root / "pseudo"
    unified_pseudo_dir.mkdir(parents=True, exist_ok=True)
    if not ensure_pseudopotentials(working_dir_input, working_dir, unified_pseudo_dir, None):
        raise RuntimeError("Failed to obtain required pseudopotentials")

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
    parameter_overrides: Optional[Sequence[ParameterOverride]] = None,
    card_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    species_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    keep_original: bool = True,
) -> tuple[StepResult, PreparedInputStep]:
    """
    Convenience function combining preparation + execution.
    
    Args:
        engine: QE engine to execute the step
        input_file: Path to the QE input file
        working_dir: Working directory for execution
        project_root: Project root for pseudo_dir resolution
        step_type: Optional step type override
        timeout: Optional execution timeout
        parameter_overrides: Optional parameter overrides
        card_overrides: Optional card overrides
        species_overrides: Optional species overrides
        keep_original: If True, save original input as <name>_original.in for debugging
    
    Returns:
        Tuple of (StepResult, PreparedInputStep)
    """
    prepared = prepare_input_step(
        input_file=input_file,
        working_dir=working_dir,
        project_root=project_root,
        parameter_overrides=parameter_overrides,
        card_overrides=card_overrides,
        species_overrides=species_overrides,
        keep_original=keep_original,
    )
    result = run_prepared_step(
        engine=engine,
        prepared_step=prepared,
        step_type=step_type,
        timeout=timeout,
    )
    return result, prepared


_PARAMETER_MAP_CACHE: Optional[Dict[str, Any]] = None


def _get_parameter_map() -> Dict[str, Any]:
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


def _apply_parameter_overrides(
    qe_input: QEInput, overrides: Sequence[ParameterOverride]
) -> None:
    """
    Apply CLI-specified overrides to the parsed QE input.
    """

    if not overrides:
        return

    module = qe_input.module or qe_input.detect_module()
    module_key = module.value
    parameter_map = _get_parameter_map().get("modules", {})
    module_entry = parameter_map.get(module_key)
    if not module_entry:
        raise ValueError(
            f"No parameter metadata available for module '{module_key}'. Unable to apply overrides."
        )

    sections: Dict[str, list[str]] = module_entry.get("sections", {})
    section_lookup = {name.upper(): params for name, params in sections.items()}

    param_to_sections: Dict[str, list[str]] = {}
    for section_name, params in sections.items():
        canonical_section = section_name.upper()
        for param in params:
            param_to_sections.setdefault(param.lower(), []).append(canonical_section)

    for override in overrides:
        param_name = override.name.strip()
        if not param_name:
            continue
        canonical_param = param_name.lower()
        available_sections = param_to_sections.get(canonical_param, [])

        target_section: Optional[str] = None
        if override.section:
            candidate = _normalize_section_name(override.section)
            if not candidate or candidate not in section_lookup:
                raise ValueError(
                    f"Section '{override.section}' is not valid for module '{module_key}'."
                )
            if available_sections and candidate not in available_sections:
                raise ValueError(
                    f"Parameter '{param_name}' does not belong to section '{override.section}' "
                    f"for module '{module_key}'."
                )
            target_section = candidate
        else:
            if not available_sections:
                raise ValueError(
                    f"Parameter '{param_name}' is not defined for module '{module_key}'. "
                    "Provide the section explicitly via --SECTION.parameter=value."
                )
            if len(available_sections) > 1:
                raise ValueError(
                    f"Parameter '{param_name}' exists in multiple sections {available_sections}. "
                    "Specify the section explicitly via --SECTION.parameter=value."
                )
            target_section = available_sections[0]

        if not target_section:
            continue

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
        if "pseudopot" in values:
            while len(row) < 3:
                row.append("")
            row[2] = str(values["pseudopot"])


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
        if "option" in payload:
            card.option = payload.get("option")
        elif "data" in payload and card.card_type == QECardType.K_POINTS:
            # Clear default 'automatic' option when explicit k-point list is provided
            card.option = None
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


