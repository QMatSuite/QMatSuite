from __future__ import annotations

from dataclasses import dataclass
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

import yaml

from quantumvitas.core.resources import meta_from_name, ensure_relative_path
from quantumvitas.io import QEInputGenerator, QEInputParser, read_structure, write_structure
from quantumvitas.io.model import QECardType, QEModule, QEInput
from quantumvitas.io.structure_io import structure_from_qe_input, qe_input_has_structure
from quantumvitas.project.model import Project
from quantumvitas.calculation.structure_steps import StructureStepSpec


STRUCTURE_CARDS = {
    QECardType.ATOMIC_POSITIONS,
    QECardType.CELL_PARAMETERS,
    QECardType.ATOMIC_SPECIES,  # ATOMIC_SPECIES should be in species_overrides, not cards
}


@dataclass(slots=True)
class StepImportResult:
    """Details about an imported QE input step."""

    step_id: str
    structure_id: Optional[str]  # None for structure-less steps (e.g., LR/TDDFT)
    step_type: str
    parameters: Dict[str, Dict[str, object]]
    spec: StructureStepSpec
    spec_path: Path
    structure_path: Optional[Path]  # None for structure-less steps


@dataclass(slots=True)
class CalculationImportResult:
    """Summary information for a calculation import."""

    calculation_id: str
    calculation_dir: Path
    calculation_file: Path
    step_results: list[StepImportResult]
    structure_path: Path


def _build_step_spec_from_qe_input_data(
    qe_input: QEInput,
    step_type: str,
    *,
    apply_defaults: bool = False,
) -> tuple[Dict[str, Dict[str, object]], Dict[str, Dict[str, object]]]:
    """
    Build step spec parameters and cards from a QE input, optionally merging with defaults.
    
    Args:
        qe_input: Parsed QE input
        step_type: Step type (scf, nscf, etc.)
        apply_defaults: If True, merge extracted parameters with in-code defaults.
                       If False, use only what's in the input file.
    
    Returns:
        Tuple of (parameters_dict, cards_dict)
    """
    # Extract parameters and cards from the input
    parameters = _extract_parameters(qe_input)
    cards = _extract_cards(qe_input)
    
    if apply_defaults:
        # Merge with in-code defaults (defaults provide base, extracted params override)
        from quantumvitas.calculation.step_defaults import get_default_step_params
        
        defaults = get_default_step_params(step_type)
        default_params = defaults.get("parameters", {})
        default_cards = defaults.get("cards", {})
        
        # Merge: start with defaults, then update with extracted params
        merged_params = {}
        for section in set(list(default_params.keys()) + list(parameters.keys())):
            merged_params[section] = dict(default_params.get(section, {}))
            merged_params[section].update(parameters.get(section, {}))
        
        # Merge cards: defaults first, then extracted
        merged_cards = dict(default_cards)
        merged_cards.update(cards)
        
        return merged_params, merged_cards
    else:
        # Use only what's in the input file
        return parameters, cards


def build_step_spec_from_qe_input(
    input_file: Path | str,
    *,
    destination_dir: Path | str,
    structure_dir: Path | str | None = None,
    step_id: Optional[str] = None,
    structure_id: Optional[str] = None,
    reference_structure_by: str = "path",
    apply_defaults: bool = False,
) -> StepImportResult:
    """
    Convert a QE input file into a StructureStepSpec + structure JSON.

    Args:
        input_file: QE input file to convert.
        destination_dir: Where to place the generated step YAML.
        structure_dir: Directory used to store the extracted structure JSON.
                       Defaults to ``destination_dir / 'structures'``.
        step_id: Optional explicit step id; defaults to ``input_file.stem``.
        structure_id: Optional structure id; defaults to ``input_file.stem``.
        reference_structure_by: Either ``'path'`` or ``'id'``. Controls how the
                                step spec references the structure. When ``id``
                                is used you are responsible for ensuring the
                                structure is registered in ``project.qv.yml``.
        apply_defaults: If True, merge extracted parameters with in-code defaults.
                       If False (default), preserve only what's in the input file.
                       Use False for round-trip import scenarios, True for "from scratch" creation.

    Returns:
        StepImportResult describing the generated assets.
    """

    input_path = Path(input_file).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"QE input not found: {input_path}")

    destination = Path(destination_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    structure_base = Path(structure_dir).resolve() if structure_dir else (destination / "structures")
    structure_base.mkdir(parents=True, exist_ok=True)

    qe_input = QEInputParser.parse_file(input_path)
    
    # Check if input has structure information
    has_structure = qe_input_has_structure(qe_input)
    
    # Generate ULID for step_id (DAG + ULID model requirement)
    from quantumvitas.core.resources import generate_resource_id
    if step_id:
        # If step_id is provided but not a ULID, generate one
        if len(step_id) != 26 or not step_id.startswith("01"):
            step_id = generate_resource_id()
    else:
        # Generate new ULID for step_id
        step_id = generate_resource_id()
    
    # Use input_path.stem for step name/slug (human-readable identifier)
    step_name = input_path.stem
    
    # Handle structure parsing only if input has structure
    structure_path = None
    if has_structure:
        structure = structure_from_qe_input(qe_input)
        
        # Generate a proper ULID for structure_id if not provided
        if not structure_id:
            structure_id = generate_resource_id()
        else:
            # If structure_id is provided but not a ULID, generate one
            # (structure_id should be a ULID, not a name)
            if len(structure_id) != 26 or not structure_id.startswith("01"):
                structure_id = generate_resource_id()
        
        # Use a filename based on the input stem for the structure file
        structure_filename = input_path.stem
        structure_path = (structure_base / f"{structure_filename}.json").resolve()
        
        # Create structure file with proper meta (ID-only model)
        try:
            structure_meta_path = ensure_relative_path(structure_path, base=structure_base.parent)
        except ValueError:
            structure_meta_path = f"structures/{structure_filename}.json"
        
        structure_meta = meta_from_name(
            "structure",
            name=input_path.stem,  # Use input filename as name
            path=structure_meta_path,
        )
        structure_meta.id = structure_id  # Set the ULID
        
        # Write structure with meta
        write_structure(structure, structure_path, format="json", metadata=structure_meta)
    else:
        # Structure-less step (e.g., LR/TDDFT post-processing)
        # structure_id will be None or set by caller (fallback to last structure)
        structure_id = structure_id  # Keep provided value or None

    step_type = _infer_step_type(qe_input)
    parameters, cards = _build_step_spec_from_qe_input_data(
        qe_input, step_type, apply_defaults=apply_defaults
    )
    
    # Extract species_overrides from ATOMIC_SPECIES card (if present)
    # ATOMIC_SPECIES should not be in cards - it should be in species_overrides
    species_overrides = {}
    atomic_species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    if atomic_species_card and atomic_species_card.data:
        for row in atomic_species_card.data:
            if isinstance(row, list) and len(row) >= 3:
                element_symbol = str(row[0]).strip()
                mass = row[1] if len(row) > 1 else None
                pseudo_filename = str(row[2]).strip() if len(row) > 2 else None
                
                # Build species override
                override = {}
                if mass is not None:
                    try:
                        override["mass"] = float(mass)
                    except (TypeError, ValueError):
                        override["mass"] = mass
                if pseudo_filename:
                    # Skip placeholder names
                    from quantumvitas.core.pseudo import is_missing_pseudo_placeholder
                    if not is_missing_pseudo_placeholder(pseudo_filename):
                        override["pseudopot"] = pseudo_filename
                
                if override:
                    species_overrides[element_symbol] = override
    
    # Remove ATOMIC_SPECIES from cards if it was included (shouldn't happen after filtering, but just in case)
    cards.pop("ATOMIC_SPECIES", None)

    if reference_structure_by not in {"path", "id"}:
        raise ValueError("reference_structure_by must be either 'path' or 'id'")

    # Always set structure_id (ID-only model requirement)
    # For backwards compat, we can also set structure as a path selector if needed
    if reference_structure_by == "id":
        structure_ref_value = structure_id
        structure_selector = ""  # ID-only: no legacy selector
    else:
        structure_ref_value = _relative_path_for_spec(structure_path, destination)
        structure_selector = str(structure_ref_value)  # Legacy path selector for backwards compat

    # Use step_name for filename (human-readable), step_id (ULID) for meta.id
    step_file = destination / f"{step_name}.step.yaml"
    step_meta = meta_from_name("step", name=step_name, path=step_file.name)
    step_meta.id = step_id  # Set ULID as meta.id
    spec = StructureStepSpec(
        meta=step_meta,
        structure_id=structure_id,  # Always set structure_id (ID-only model)
        structure=structure_selector,  # Legacy selector (empty if using ID-only)
        step_type_spec=step_type,
        parameters=parameters,
        input_name=input_path.name,
        cards=cards,
        species_overrides=species_overrides if species_overrides else None,
    )
    step_file.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))

    return StepImportResult(
        step_id=step_id,
        structure_id=structure_id,
        step_type=step_type,
        parameters=parameters,
        spec=spec,
        spec_path=step_file,
        structure_path=structure_path,
    )


def build_calculation_from_qe_inputs(
    input_files: Sequence[Path | str],
    *,
    calculation_dir: Path | str,
    calculation_id: Optional[str] = None,
    structure_id: Optional[str] = None,
    reference_structure_by: str = "path",
    working_dir_name: str = "raw",
    mode: str = "normal",
    project_root: Optional[Path | str] = None,
) -> CalculationImportResult:
    """
    Convert a series of QE input files into a calculation folder.

    The calculation will contain:
    - ``calculation.yaml`` referencing generated step specs
    - ``steps/<step_id>.step.yaml`` files
    - ``structures/<structure_id>.json`` (unless already present)
    - Optional copies of the original QE inputs under ``<working_dir_name>/original/``

    Args:
        input_files: Iterable of QE input files in execution order.
        calculation_dir: Destination directory for the calculation.
        calculation_id: Optional calculation identifier (defaults to destination name).
        structure_id: Optional structure id shared by all steps (defaults to stem of first input).
        reference_structure_by: ``'path'`` or ``'id'`` (propagated to step specs).
        working_dir_name: Name of the calculation raw directory.
        mode: Calculation mode (e.g., ``normal`` or ``strict``).
        project_root: Optional project root for relative paths.
    """

    files = [Path(p).resolve() for p in input_files]
    if not files:
        raise ValueError("At least one QE input is required to build a calculation")
    for path in files:
        if not path.exists():
            raise FileNotFoundError(f"QE input not found: {path}")

    calculation_dir = Path(calculation_dir).resolve()
    calculation_dir.mkdir(parents=True, exist_ok=True)

    steps_dir = (calculation_dir / "steps").resolve()
    steps_dir.mkdir(parents=True, exist_ok=True)

    project_root_path = Path(project_root).resolve() if project_root else None
    if project_root_path and not calculation_dir.is_relative_to(project_root_path):
        raise ValueError("calculation_dir must live inside the project root when project_root is provided")

    structure_store = (
        (project_root_path / "structures").resolve()
        if project_root_path
        else (calculation_dir / "structures").resolve()
    )
    structure_store.mkdir(parents=True, exist_ok=True)

    calculation_id = calculation_id or calculation_dir.name
    
    # Handle structure_id parameter:
    # - If it's a ULID and reference_structure_by="id", treat it as a selector for existing structure
    # - Otherwise, we're creating a new structure, so generate a ULID upfront
    from quantumvitas.core.resources import generate_resource_id
    
    # Check if structure_id is a valid ULID
    is_ulid = structure_id and len(structure_id) == 26 and structure_id.startswith("01")
    
    # If structure_id is provided but not a ULID, and we're creating new structures,
    # generate a ULID upfront (the parameter is treated as a legacy name/selector, not used)
    if structure_id and not is_ulid:
        # This is a legacy name/selector - we'll create a new structure with a ULID
        # The structure_id parameter is ignored when creating new structures
        structure_id = None
    
    # Generate ULID if not provided (we're creating a new structure)
    if not structure_id:
        structure_id = generate_resource_id()
    
    # Allow each step to have its own structure_id (multi-structure support)
    # Steps will dedup structures by fingerprint via QVService.import_step_from_qe_input()
    step_results: list[StepImportResult] = []
    for input_path in files:
        # Generate ULID for step_id (DAG + ULID model)
        # step_id will be generated inside build_step_spec_from_qe_input if not provided
        # structure_id=None allows each step to extract its own structure from the input
        step_result = build_step_spec_from_qe_input(
            input_path,
            destination_dir=steps_dir,
            structure_dir=structure_store,
            step_id=None,  # Let function generate ULID
            structure_id=None,  # Let each step extract its own structure (will dedup by fingerprint)
            reference_structure_by=reference_structure_by,
        )
        step_results.append(step_result)
    
    # Note: Steps may have different structure_ids if inputs contain different structures
    # This is intentional to support relax/vc-relax flows where later steps have updated structures

    raw_dir = (calculation_dir / working_dir_name).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)

    originals_dir = raw_dir / "original_inputs"
    originals_dir.mkdir(parents=True, exist_ok=True)
    for input_path in files:
        shutil.copy2(input_path, originals_dir / input_path.name)

    calculation_meta: Dict[str, object] = {"working_dir": working_dir_name}
    # For multi-structure support, we don't enforce a single structure_id at calculation level
    # Each step references its own structure_id
    # If all steps share the same structure, we can optionally set it for convenience
    # but it's not required
    if step_results:
        # Use the first step's structure_id as a default (for backward compatibility)
        # but steps can have different structures
        first_structure_id = step_results[0].structure_id
        calculation_meta["structure_id"] = first_structure_id
    # Explicitly ensure structure_name and structure are NOT written
    calculation_meta.pop("structure_name", None)
    calculation_meta.pop("structure", None)

    steps_section = [
        {
            "step_id": result.step_id,  # ULID (canonical reference)
            # step_file is NOT stored - step location resolved via registry using step_id
        }
        for result in step_results
    ]

    # Build calc-level species_map from all input files
    # This is the authoritative source of truth for pseudo mapping
    from quantumvitas.calculation.folder_import import (
        extract_species_map_from_qe_input,
        merge_species_maps,
    )
    
    calc_species_map: Dict[str, Dict[str, Any]] = {}
    for input_path in files:
        try:
            qe_input = QEInputParser.parse_file(input_path)
            file_species_map = extract_species_map_from_qe_input(qe_input)
            if file_species_map:
                calc_species_map = merge_species_maps(
                    calc_species_map,
                    file_species_map,
                    source_file=input_path.name,
                )
        except ValueError:
            # Re-raise conflict errors
            raise
        except Exception:
            # Ignore other parse errors
            continue
    
    # Add species_map to calculation metadata if we have any mappings
    if calc_species_map:
        calculation_meta["species_map"] = calc_species_map

    calculation_config = {
        "id": calculation_id,
        "mode": mode,
        "calculation": calculation_meta,
        "steps": steps_section,
    }
    # Ensure top-level structure_name and structure are also NOT written (DAG + ID-only constitution)
    calculation_config.pop("structure_name", None)
    calculation_config.pop("structure", None)
    
    calculation_file = calculation_dir / "calculation.yaml"
    calculation_file.write_text(yaml.safe_dump(calculation_config, sort_keys=False))

    return CalculationImportResult(
        calculation_id=calculation_id,
        calculation_dir=calculation_dir,
        calculation_file=calculation_file,
        step_results=step_results,
        structure_path=step_results[0].structure_path,
    )


def _extract_parameters(qe_input: QEInput) -> Dict[str, Dict[str, object]]:
    parameters: Dict[str, Dict[str, object]] = {}
    for namelist in qe_input.namelists:
        if not namelist.parameters:
            continue
        section = namelist.name.upper()
        parameters.setdefault(section, {})
        parameters[section].update(namelist.parameters)
    _remove_structure_parameters(parameters, qe_input)
    return parameters


STRUCTURAL_SYSTEM_KEYS = {"ibrav", "nat", "ntyp"}
LATTICE_PARAM_KEYS = {"a", "b", "c", "cosab", "cosac", "cosbc"}


def _needs_alat_preservation(qe_input: QEInput) -> bool:
    """
    Determine if we need to preserve alat (celldm(1) or A) for k-point compatibility.
    
    Returns True if:
    - K_POINTS are in tpiba format (or variants like tpiba_b, tpiba_c)
    - AND the input has an alat defined (via celldm(1), A, or ibrav != 0)
    """
    kpoints = qe_input.get_card(QECardType.K_POINTS)
    if not kpoints:
        return False
    
    option = (kpoints.option or "").lower()
    # These formats don't depend on alat
    if option in ("gamma", "automatic", "crystal", "crystal_b", "crystal_c"):
        return False
    
    # tpiba (default), tpiba_b, tpiba_c depend on alat
    # Check if there's an alat defined
    system = qe_input.get_namelist("SYSTEM") or qe_input.get_namelist("system")
    if not system:
        return False
    
    # Check for explicit alat (celldm(1) or A)
    has_celldm1 = any(str(k).lower() == "celldm(1)" for k in system.parameters.keys())
    has_a = any(str(k).lower() == "a" for k in system.parameters.keys())
    
    if has_celldm1 or has_a:
        return True
    
    # If ibrav != 0, alat is derived from celldm(1) which must exist
    ibrav = system.parameters.get("ibrav", 0)
    try:
        ibrav = int(ibrav)
    except (TypeError, ValueError):
        ibrav = 0
    
    return ibrav != 0


def _extract_alat_bohr(qe_input: QEInput) -> Optional[float]:
    """
    Extract alat in Bohr from the input.
    
    Returns alat in Bohr, or None if not determinable.
    """
    from quantumvitas.io.structure_io import BOHR_TO_ANGSTROM
    
    system = qe_input.get_namelist("SYSTEM") or qe_input.get_namelist("system")
    if not system:
        return None
    
    # Check celldm(1) first (in Bohr)
    for key, value in system.parameters.items():
        if str(key).lower() == "celldm(1)":
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    
    # Check A (in Angstrom, convert to Bohr)
    for key, value in system.parameters.items():
        if str(key).lower() == "a":
            try:
                return float(value) / BOHR_TO_ANGSTROM
            except (TypeError, ValueError):
                pass
    
    return None


def _remove_structure_parameters(parameters: Dict[str, Dict[str, object]], qe_input: QEInput) -> None:
    """
    Remove structure-related SYSTEM parameters so they live exclusively in the structure payload.
    
    Exception: When k-points are in tpiba format, we preserve alat (as celldm(1))
    so that k-points remain correct when we regenerate with ibrav=0 and CELL_PARAMETERS (alat).
    """
    system_params = parameters.get("SYSTEM")
    if not system_params:
        return

    preserve_alat = _needs_alat_preservation(qe_input)
    alat_bohr = _extract_alat_bohr(qe_input) if preserve_alat else None

    keys_to_remove: list[str] = []
    for key in list(system_params.keys()):
        key_str = str(key)
        lower_key = key_str.lower()
        if lower_key in STRUCTURAL_SYSTEM_KEYS:
            keys_to_remove.append(key)
        elif lower_key.startswith("celldm"):
            keys_to_remove.append(key)
        elif lower_key in LATTICE_PARAM_KEYS:
            keys_to_remove.append(key)

    for key in keys_to_remove:
        system_params.pop(key, None)

    # Add back celldm(1) if we need to preserve alat
    if alat_bohr is not None:
        system_params["celldm(1)"] = alat_bohr

    if not system_params:
        parameters.pop("SYSTEM", None)


def _extract_cards(qe_input: QEInput) -> Dict[str, Dict[str, object]]:
    cards: Dict[str, Dict[str, object]] = {}
    for card in qe_input.cards:
        if card.card_type in STRUCTURE_CARDS:
            continue
        # Convert K_POINTS from tpiba to crystal if ibrav != 0
        # This is needed because when we convert to ibrav=0, the alat changes
        if card.card_type == QECardType.K_POINTS:
            converted = _convert_kpoints_if_needed(qe_input, card)
            cards[card.card_type.value] = {
                "option": converted["option"],
                "data": converted["data"],
            }
        else:
            cards[card.card_type.value] = {
                "option": card.option,
                "data": card.data,
            }
    return cards


def _convert_kpoints_if_needed(qe_input: QEInput, kpoints_card) -> Dict[str, object]:
    """
    Handle K_POINTS when importing a QE input.
    
    K_POINTS are kept as-is because:
    - crystal/crystal_b/crystal_c: Independent of alat, work with any cell representation
    - gamma/automatic: Independent of alat
    - tpiba/tpiba_b/tpiba_c (or no option): alat is preserved via celldm(1) in the
      step spec, and CELL_PARAMETERS (alat) is used when regenerating
    
    If the original input has no alat (ibrav=0 with absolute CELL_PARAMETERS units),
    tpiba k-points would be interpreted using the derived alat from the cell vectors,
    which is the same behavior as the original.
    """
    return {"option": kpoints_card.option, "data": kpoints_card.data}


def _infer_step_type(qe_input: QEInput) -> str:
    module = qe_input.detect_module()
    if module == QEModule.PW:
        control = qe_input.get_namelist("CONTROL") or qe_input.get_namelist("control")
        calculation = (control.get("calculation") if control else "scf") if control else "scf"
        calculation = str(calculation).lower().strip("'\"")  # Strip quotes that may be in parsed value
        mapping = {
            "scf": "scf",
            "nscf": "nscf",
            "bands": "bands_pw",
            "relax": "relax",
            "vc-relax": "vc-relax",
            "md": "md",
            "vc-md": "vc-md",
        }
        return mapping.get(calculation, calculation)

    module_map = {
        QEModule.DOS: "dos",
        QEModule.BANDS: "bands",
        QEModule.PROJWFC: "projwfc",
        QEModule.PH: "ph",
        QEModule.Q2R: "q2r",
        QEModule.MATDYN: "matdyn",
        QEModule.DYNMAT: "dynmat",
        QEModule.PP: "pp",
        QEModule.GIPAW: "gipaw",
    }
    return module_map.get(module, "custom")


def _relative_path_for_spec(target: Path, base: Path) -> Path:
    try:
        return target.relative_to(base)
    except ValueError:
        return target

