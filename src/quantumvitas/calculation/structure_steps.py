from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple, Union

from typing import TYPE_CHECKING

import yaml
from pymatgen.core import Structure as PMGStructure, Molecule as PMGMolecule

from quantumvitas.core.resources import (
    ResourceMeta,
    ensure_relative_path,
    meta_from_name,
)
from quantumvitas.io import QEInputGenerator, read_structure
from quantumvitas.io.structure_io import qe_input_from_structure
from quantumvitas.io.model import QECardType, QEInput, QENamelist, QEModule
from quantumvitas.calculation.input_runner import (
    ParameterOverride,
    apply_card_overrides_to_qe_input,
    apply_parameter_overrides,
    apply_species_overrides_to_qe_input,
    parameter_dict_to_overrides,
    set_outdir_to_temp,
    set_pseudo_dir_in_input,
)

if TYPE_CHECKING:
    from quantumvitas.project.model import Project


@dataclass(slots=True)
class StructureStepSpec:
    """
    Declarative specification for generating a QE input from a stored structure.
    
    Structure references:
    - structure_id: ULID of the structure (canonical reference)
    - structure: Legacy selector field (for backwards compatibility when loading)
    """

    meta: ResourceMeta
    structure: str  # Legacy selector (backwards compat, not authoritative)
    structure_id: Optional[str] = None  # Canonical structure reference (ULID)
    step_type: str = "scf"
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    input_name: Optional[str] = None
    cards: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    species_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    parent_calculation_id: Optional[str] = None  # Links step to its parent calculation
    kpath_metadata: Optional[Dict[str, Any]] = None  # K-path info for band plots

    @classmethod
    def from_dict(
        cls, 
        data: Dict[str, Any], 
        source_path: Optional[Path] = None,
        resolve_structure_selector: Optional[callable] = None,
    ) -> "StructureStepSpec":
        """
        Create StructureStepSpec from dictionary.
        
        Handles both new format (structure_id) and legacy format (structure selector).
        
        Backwards compatibility (legacy structure selector):
        - If structure_id is missing but structure selector is present, resolve it to structure_id
        - This resolution happens only on input (from_dict/loader), not on output (to_dict)
        - After resolution, the structure_id is stored and the selector is dropped
        
        Args:
            data: Dictionary containing step spec data
            source_path: Optional path to the step spec file
            resolve_structure_selector: Optional callable(selector: str) -> str that resolves
                a structure selector (name/slug/path) to a structure_id (ULID).
                If provided and structure_id is missing, legacy 'structure' selector will be resolved.
        """
        # New format: structure_id (canonical)
        structure_id = data.get("structure_id")
        
        # Legacy format: structure selector (for backwards compat on input only)
        structure = data.get("structure")
        
        # If structure_id is missing but structure selector is present, resolve it via resolver
        if not structure_id and structure and resolve_structure_selector:
            try:
                resolved_resource = resolve_structure_selector(structure)
                # Extract the ID from the resolved resource
                structure_id = resolved_resource.meta.id if hasattr(resolved_resource, 'meta') else str(resolved_resource)
                # Drop the legacy selector after resolution
                structure = None
            except Exception:
                # Resolution failed - keep structure selector for now (will fail on to_dict if not resolved)
                pass
        
        # DAG + ID-only model: Step YAML does NOT contain structure_id.
        # Structure is resolved from calculation.structure_id at execution time.
        # Legacy structure_id/structure fields are accepted for backwards compatibility only.
        # If present, they are kept in memory but not written to YAML.
        
        # Step.yaml stores machine types (SPEC, e.g., "qe_scf").
        # Constitution §B: Persisted truth = SPEC. In-memory model MUST use SPEC types.
        # No normalization to GEN - use registry mapping for display/filenames when needed.
        step_type = str(data.get("step_type", "scf"))
        
        parameters = data.get("parameters") or {}
        if not isinstance(parameters, dict):
            raise ValueError("Step spec 'parameters' must be a mapping")

        input_name = data.get("input_name") or data.get("input")
        cards = data.get("cards") or {}
        if not isinstance(cards, dict):
            raise ValueError("Step spec 'cards' must be a mapping when provided")

        species_overrides = data.get("species_overrides") or {}
        if not isinstance(species_overrides, dict):
            raise ValueError("Step spec 'species_overrides' must be a mapping when provided")

        parent_calculation_id = data.get("parent_calculation_id")
        kpath_metadata = data.get("kpath_metadata")

        meta_dict = data.get("meta")
        default_name = data.get("name") or str(step_type)
        default_path = (
            ensure_relative_path(source_path.name, base=source_path.parent)
            if source_path
            else (meta_dict or {}).get("path") or f"{default_name}.step.yaml"
        )
        meta = ResourceMeta.from_dict(
            meta_dict,
            kind="step",
            default_name=default_name,
            default_path=default_path,
        )

        return cls(
            meta=meta,
            structure_id=structure_id,
            structure=structure or "",  # Provide empty string if only structure_id present
            step_type=step_type,
            parameters=parameters,
            input_name=input_name,
            cards=cards,
            species_overrides=species_overrides,
            parent_calculation_id=parent_calculation_id,
            kpath_metadata=kpath_metadata,
        )

    @classmethod
    def from_yaml(
        cls, 
        path: Path | str, 
        resolve_structure_selector: Optional[callable] = None,
    ) -> "StructureStepSpec":
        """
        Load StructureStepSpec from YAML file.
        
        Args:
            path: Path to step spec YAML file
            resolve_structure_selector: Optional callable(selector: str) -> str that resolves
                a structure selector (name/slug/path) to a structure_id (ULID).
                If provided and structure_id is missing, legacy 'structure' selector will be resolved.
        """
        spec_path = Path(path)
        content = yaml.safe_load(spec_path.read_text()) or {}
        if not isinstance(content, dict):
            raise ValueError(f"Step file {path} must contain a mapping at the root")
        return cls.from_dict(content, source_path=spec_path, resolve_structure_selector=resolve_structure_selector)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        DAG + ID-only model invariants (enforced here):
        - Step YAML contains ONLY step-local configuration (parameters, cards, species_overrides).
        - NO cross-resource references: structure_id, parent_calculation_id, or structure selector.
        - Structure is resolved via calculation.structure_id at execution time (calculation owns structure).
        - Parent calculation is implicit from step file location (calculations/<slug>/steps/<step>.step.yaml).
        
        This method explicitly excludes structure_id, parent_calculation_id, and structure fields
        to enforce the DAG invariant that steps do not duplicate calculation-level references.
        """
        data: Dict[str, Any] = {
            "meta": self.meta.to_dict(),
            "step_type": self.step_type,
        }
        # Step-local configuration only
        if self.parameters:
            data["parameters"] = self.parameters
        if self.input_name:
            data["input_name"] = self.input_name
        if self.cards:
            data["cards"] = self.cards
        if self.species_overrides:
            data["species_overrides"] = self.species_overrides
        if self.kpath_metadata:
            data["kpath_metadata"] = self.kpath_metadata
        # Do NOT write structure_id (inherits from calculation)
        # Do NOT write parent_calculation_id (parent is implicit)
        # Do NOT write structure selector (legacy field)
        return data


# Mapping from step type to QE calculation parameter
# Most step types map directly, but some like 'bands_pw' need translation
STEP_TYPE_TO_CALCULATION = {
    "bands_pw": "bands",  # bands_pw is our internal name for pw.x bands calculation
}


def generate_qe_input_from_structure(
    structure: PMGStructure | PMGMolecule,
    step_type: str,
    parameter_overrides: Sequence[ParameterOverride] | None = None,
) -> QEInput:
    """
    Build a QE input from a structure plus step metadata.
    """

    qe_input = qe_input_from_structure(structure)

    overrides: list[ParameterOverride] = []
    if step_type:
        # Convert step_type to QE calculation value (e.g., bands_pw -> bands)
        calculation_value = STEP_TYPE_TO_CALCULATION.get(step_type.lower(), step_type)
        overrides.append(
            ParameterOverride(
                name="calculation",
                value=calculation_value,
                section="CONTROL",
            )
        )

    if parameter_overrides:
        overrides.extend(parameter_overrides)

    apply_parameter_overrides(qe_input, overrides)
    return qe_input


# Post-processing step types that don't need structure-based input
POST_PROCESSING_STEP_TYPES = {
    "dos", "bands", "projwfc", "pp", "q2r", "matdyn", "dynmat",
    "sumpdos", "band_interpolation", "ppacf", "pprism",
}

# Mapping of step type to primary namelist name
STEP_TYPE_NAMELIST_MAP = {
    "dos": "DOS",
    "bands": "BANDS",
    "projwfc": "PROJWFC",
    "pp": "INPUTPP",
    "pw2wannier90": "INPUTPP",  # pw2wannier90.x uses INPUTPP namelist
    "q2r": "INPUT",
    "matdyn": "INPUT",
    "dynmat": "INPUT",
}

# Mapping of step type to QE module
STEP_TYPE_MODULE_MAP = {
    "scf": QEModule.PW,
    "nscf": QEModule.PW,
    "relax": QEModule.PW,
    "vc-relax": QEModule.PW,
    "md": QEModule.PW,
    "vc-md": QEModule.PW,
    "bands_pw": QEModule.PW,
    "dos": QEModule.DOS,
    "bands": QEModule.BANDS,
    "projwfc": QEModule.PROJWFC,
    "pp": QEModule.PP,
    "pw2wannier90": QEModule.PP,  # pw2wannier90.x uses INPUTPP namelist (same as pp.x)
    "q2r": QEModule.Q2R,
    "matdyn": QEModule.MATDYN,
    "dynmat": QEModule.DYNMAT,
}


def detect_runtime_control_keys(parameters: Dict[str, Dict[str, Any]]) -> list[str]:
    """
    Detect runtime-managed CONTROL keys (prefix, outdir, pseudo_dir) in step parameters.
    
    Pure keyword matching - no engine detection, no step_type inspection.
    
    Args:
        parameters: Step parameters dict (section -> {param: value})
        
    Returns:
        List of found runtime keys (e.g., ["prefix", "outdir"])
    """
    RUNTIME_KEYS = {"prefix", "outdir", "pseudo_dir"}
    found_keys = []
    
    # Check CONTROL section (case-insensitive)
    control_section = None
    for section_name, section_params in parameters.items():
        if section_name.upper() == "CONTROL":
            control_section = section_params
            break
    
    if control_section and isinstance(control_section, dict):
        for key, value in control_section.items():
            if str(key).lower() in RUNTIME_KEYS:
                found_keys.append(str(key).lower())
    
    return found_keys


def stable_short_calc_prefix(ulid: str) -> str:
    """
    Generate a stable, short prefix for QE CONTROL.prefix from calculation ULID.
    
    Stable prefix derived from calc ULID; slug changes do not affect it.
    This ensures QE file reuse works correctly even if user changes calculation slug.
    
    Args:
        ulid: Calculation ULID string (e.g., "01KEZRANCNA0E0C40Y5EPTB4B2")
        
    Returns:
        Short prefix string: "qv" + last 6 characters of ULID (lowercase)
        Example: "qv5epb4b2" for ULID "01KEZRANCNA0E0C40Y5EPTB4B2"
    """
    if not ulid or len(ulid) < 6:
        raise ValueError(f"ULID must be at least 6 characters, got: {ulid}")
    
    # Extract last 6 characters and convert to lowercase
    suffix = ulid[-6:].lower()
    
    # Ensure QE-safe characters (alphanumeric only)
    # ULID uses base32 encoding (0-9, A-Z), so lowercase is safe
    # Prefix with "qv" to make it clearly a QuantumVITAS-generated prefix
    return "qv" + suffix


def _inject_calculation_prefix_outdir(
    qe_input: QEInput,
    step_type: str,
    calculation_prefix: Optional[str],
    calculation_outdir: str,
    spec_params: Dict[str, Any],
    logger,
) -> None:
    """
    R2-R4: Inject calculation-level prefix/outdir into QE input if schema supports it.
    
    This implements the calculation-level prefix/outdir propagation rule:
    - R1: Canonical prefix = stable id-derived prefix (from calculation.meta.id ULID)
    - R2: Only inject if the step's QE module schema defines prefix/outdir parameters
    - R3: Step-level prefix/outdir in spec_params are ignored (overridden by calculation-level)
    - R4: Outdir defaults to "./outdir" if not provided
    
    Args:
        qe_input: QEInput object to modify
        step_type: Step type (e.g., "scf", "pw2wannier90")
        calculation_prefix: Calculation-level prefix (stable id-derived prefix from calc ULID)
        calculation_outdir: Calculation-level outdir (defaults to "./outdir")
        spec_params: Step spec parameters (to detect ignored step-level prefix/outdir)
        logger: Logger instance for diagnostic messages
    """
    # Determine which QE module this step uses
    step_type_lower = step_type.lower()
    module = STEP_TYPE_MODULE_MAP.get(step_type_lower)
    if not module:
        # Unknown step type - skip injection
        return
    
    # Check schema for prefix/outdir parameters
    from quantumvitas.data import get_module_param_sections
    sections = get_module_param_sections(module.value)
    
    # Build parameter-to-section mapping
    param_to_sections: Dict[str, List[str]] = {}
    for section_name, params in sections.items():
        canonical_section = section_name.upper().lstrip("&")
        for param in params:
            param_lower = param.lower()
            param_to_sections.setdefault(param_lower, []).append(canonical_section)
    
    # R3: Track ignored step-level prefix/outdir for UI display
    ignored_step_prefix = None
    ignored_step_outdir = None
    
    # Check step-level spec_params for prefix/outdir (will be ignored)
    flat_spec_params = {}
    for section_name, section_params in spec_params.items():
        if isinstance(section_params, dict):
            flat_spec_params.update({k.lower(): v for k, v in section_params.items()})
        elif isinstance(section_params, str):
            flat_spec_params[section_name.lower()] = section_params
    
    if "prefix" in flat_spec_params and calculation_prefix:
        ignored_step_prefix = flat_spec_params["prefix"]
        logger.info(
            f"[PREFIX_INJECTION] Step-level prefix '{ignored_step_prefix}' will be ignored, "
            f"stable id-derived prefix '{calculation_prefix}' takes precedence"
        )
    
    if "outdir" in flat_spec_params and calculation_outdir:
        ignored_step_outdir = flat_spec_params["outdir"]
        logger.info(
            f"[PREFIX_INJECTION] Step-level outdir '{ignored_step_outdir}' will be ignored, "
            f"calculation outdir '{calculation_outdir}' takes precedence"
        )
    
    # R2: Inject prefix if schema defines it
    if calculation_prefix and "prefix" in param_to_sections:
        prefix_sections = param_to_sections["prefix"]
        if prefix_sections:
            # Use first section (most common case is single section)
            target_section = prefix_sections[0]
            namelist = qe_input.get_namelist(target_section)
            if not namelist:
                namelist = QENamelist(name=target_section)
                qe_input.namelists.append(namelist)
            
            # R3: Override any existing prefix (step-level is ignored)
            namelist.parameters["prefix"] = calculation_prefix
            logger.info(
                f"[PREFIX_INJECTION] Injected stable id-derived prefix '{calculation_prefix}' "
                f"into {target_section}.prefix (step_type={step_type}, module={module.value})"
            )
    
    # R2: Inject outdir if schema defines it
    if calculation_outdir and "outdir" in param_to_sections:
        outdir_sections = param_to_sections["outdir"]
        if outdir_sections:
            # Use first section
            target_section = outdir_sections[0]
            namelist = qe_input.get_namelist(target_section)
            if not namelist:
                namelist = QENamelist(name=target_section)
                qe_input.namelists.append(namelist)
            
            # R3: Override any existing outdir (step-level is ignored)
            namelist.parameters["outdir"] = calculation_outdir
            logger.info(
                f"[PREFIX_INJECTION] Injected calculation outdir '{calculation_outdir}' "
                f"into {target_section}.outdir (step_type={step_type}, module={module.value})"
            )


def _generate_postprocessing_input(
    spec: "StructureStepSpec",
    extra_overrides: Sequence[ParameterOverride] | None = None,
) -> tuple[QEInput, list[ParameterOverride]]:
    """
    Generate QE input for post-processing steps (dos.x, bands.x, projwfc.x, etc.).
    
    These don't need structure-based input, just the appropriate namelist.
    """
    step_type_lower = spec.step_type.lower() if spec.step_type else "dos"
    
    # Get the primary namelist name for this step type
    namelist_name = STEP_TYPE_NAMELIST_MAP.get(step_type_lower, step_type_lower.upper())
    module = STEP_TYPE_MODULE_MAP.get(step_type_lower, QEModule.DOS)
    
    # Build parameters for the namelist
    params: Dict[str, Any] = {}
    
    # Get parameters from spec - they should be under the namelist section
    for section_name, section_params in (spec.parameters or {}).items():
        # Match the namelist name (case-insensitive)
        if section_name.upper() == namelist_name.upper():
            if isinstance(section_params, dict):
                params.update(section_params)
    
    # Apply any extra overrides
    all_overrides: list[ParameterOverride] = []
    if extra_overrides:
        for override in extra_overrides:
            if override.section and override.section.upper() == namelist_name.upper():
                params[override.name] = override.value
            all_overrides.append(override)
    
    # Create the QEInput with just this namelist
    namelist = QENamelist(name=namelist_name.lower(), parameters=params)
    qe_input = QEInput(
        namelists=[namelist],
        cards=[],
        module=module,
    )
    
    return qe_input, all_overrides


def generate_qe_input_from_spec(
    structure: PMGStructure | PMGMolecule,
    spec: StructureStepSpec,
    extra_overrides: Sequence[ParameterOverride] | None = None,
    *,
    species_map: Optional[Dict[str, Dict[str, Any]]] = None,
    allow_step_species_overrides: bool = True,
) -> tuple[QEInput, list[ParameterOverride]]:
    """
    Build a QE input from a structure step specification.
    
    For post-processing steps (dos, bands, projwfc, etc.), creates a simple
    input with just the appropriate namelist instead of structure-based input.
    
    Args:
        structure: The structure to generate input for.
        spec: Step specification with parameters and cards.
        extra_overrides: Additional parameter overrides to apply.
        species_map: Calculation-level species mapping (element -> {pseudopot, mass}).
            Takes precedence over step-level spec.species_overrides.
        allow_step_species_overrides: If True, fall back to spec.species_overrides when
            species_map is None. If False, raise error when species_map is None (project runs only).
    """
    step_type_lower = spec.step_type.lower() if spec.step_type else "scf"
    
    # Handle post-processing step types differently
    if step_type_lower in POST_PROCESSING_STEP_TYPES:
        return _generate_postprocessing_input(spec, extra_overrides)

    spec_overrides = parameter_dict_to_overrides(spec.parameters)
    combined_overrides: list[ParameterOverride] = list(spec_overrides)
    if extra_overrides:
        combined_overrides.extend(extra_overrides)
    qe_input = generate_qe_input_from_structure(
        structure=structure,
        step_type=spec.step_type,
        parameter_overrides=combined_overrides,
    )
    
    # Check if ibrav != 0 is set in the actual QEInput (after overrides applied)
    # If so, remove CELL_PARAMETERS as it's redundant with ibrav != 0
    system_namelist = qe_input.get_namelist("SYSTEM") or qe_input.get_namelist("system")
    if system_namelist:
        ibrav_value = system_namelist.parameters.get("ibrav")
        int_ibrav = int(ibrav_value) if ibrav_value is not None else 0
        if int_ibrav != 0:
            # Remove CELL_PARAMETERS when using ibrav != 0
            qe_input.cards = [
                card
                for card in qe_input.cards
                if card.card_type != QECardType.CELL_PARAMETERS
            ]
        else:
            # Check if celldm(1) is preserved in the spec (for k-point compatibility)
            # If so, convert CELL_PARAMETERS to alat units
            celldm1 = system_namelist.parameters.get("celldm(1)")
            a_param = system_namelist.parameters.get("A") or system_namelist.parameters.get("a")
            
            if celldm1 is not None or a_param is not None:
                # Convert CELL_PARAMETERS to alat units
                _convert_cell_params_to_alat(qe_input, structure, celldm1, a_param)
                # Remove other lattice parameters but keep celldm(1) or A
                lattice_keys = {"alat", "b", "c", "cosab", "cosac", "cosbc"}
                for key in list(system_namelist.parameters.keys()):
                    lower = key.lower()
                    if lower in lattice_keys:
                        system_namelist.parameters.pop(key, None)
                    # Remove celldm(2) through celldm(6) but keep celldm(1)
                    if lower.startswith("celldm") and lower != "celldm(1)":
                        system_namelist.parameters.pop(key, None)
            else:
                # Remove all lattice parameters when using ibrav == 0 without celldm(1)
                lattice_keys = {
                    "a",
                    "alat",
                    "b",
                    "c",
                    "cosab",
                    "cosac",
                    "cosbc",
                }
                for key in list(system_namelist.parameters.keys()):
                    lower = key.lower()
                    if lower.startswith("celldm") or lower in lattice_keys:
                        system_namelist.parameters.pop(key, None)
    
    apply_card_overrides_to_qe_input(qe_input, spec.cards)
    
    # Apply species overrides: calc-level species_map takes precedence
    # For project runs (allow_step_species_overrides=False), species_map is required
    # For standalone runs (allow_step_species_overrides=True), fall back to step-level
    if species_map:
        effective_species_overrides = species_map
    elif allow_step_species_overrides:
        # Standalone mode: allow fallback to step-level species_overrides
        # But check if species_overrides is actually present
        if not spec.species_overrides:
            # Get required elements for error message
            required_elements = sorted(set(str(el) for el in structure.composition.elements))
            elements_str = ", ".join(required_elements)
            raise ValueError(
                f"Missing species_overrides in step.yaml for element(s): {elements_str}. "
                "This step.yaml looks like a normal project step; do not run it with standalone mode. "
                "Standalone mode requires step.yaml to have species_overrides, or use project run mode instead."
            )
        effective_species_overrides = spec.species_overrides
    else:
        # Project run: species_map is required, no fallback
        raise ValueError(
            "species_map is required for project runs. "
            "step.yaml species_overrides is not supported in project runs; it is standalone-only."
        )
    apply_species_overrides_to_qe_input(qe_input, effective_species_overrides)
    
    return qe_input, combined_overrides


def _convert_cell_params_to_alat(
    qe_input: QEInput,
    structure: PMGStructure,
    celldm1: Optional[float],
    a_param: Optional[float],
) -> None:
    """
    Convert CELL_PARAMETERS from angstrom to alat units.
    
    This is needed when celldm(1) or A is preserved to maintain k-point compatibility.
    """
    from quantumvitas.io.structure_io import BOHR_TO_ANGSTROM
    
    # Determine alat in Angstrom
    if celldm1 is not None:
        alat_ang = float(celldm1) * BOHR_TO_ANGSTROM
    elif a_param is not None:
        alat_ang = float(a_param)
    else:
        return
    
    # Find and convert CELL_PARAMETERS
    for card in qe_input.cards:
        if card.card_type == QECardType.CELL_PARAMETERS:
            # Current data is in Angstrom (from qe_input_from_structure)
            # Convert to alat units by dividing by alat
            new_data = []
            for row in card.data:
                if isinstance(row, (list, tuple)) and len(row) == 3:
                    new_row = [float(v) / alat_ang for v in row]
                    new_data.append(new_row)
                else:
                    new_data.append(row)
            card.data = new_data
            card.option = "alat"
            break
    
    # Also convert ATOMIC_POSITIONS if they're in angstrom
    for card in qe_input.cards:
        if card.card_type == QECardType.ATOMIC_POSITIONS:
            if card.option and card.option.lower() == "angstrom":
                new_data = []
                for row in card.data:
                    if isinstance(row, (list, tuple)) and len(row) >= 4:
                        # [symbol, x, y, z, ...]
                        new_row = [row[0]] + [float(v) / alat_ang for v in row[1:4]]
                        if len(row) > 4:
                            new_row.extend(row[4:])
                        new_data.append(new_row)
                    else:
                        new_data.append(row)
                card.data = new_data
                card.option = "alat"
            break


def overrides_from_step_spec(spec: StructureStepSpec) -> list[ParameterOverride]:
    """
    Convenience helper returning overrides declared in a step spec.
    """

    return parameter_dict_to_overrides(spec.parameters)


SpecLike = Union[StructureStepSpec, str, Path]


def materialize_step_spec(
    spec: SpecLike,
    *,
    output_dir: Path | str,
    spec_path: Optional[Path | str] = None,
    calculation_dir: Optional[Path | str] = None,
    project: Optional["Project"] = None,
    input_name: Optional[str] = None,
    project_root: Optional[Path | str] = None,
) -> tuple[Path, StructureStepSpec]:
    """
    Convert a step YAML (or StructureStepSpec) into a QE input file under output_dir.
    
    Args:
        spec: Step spec (YAML path, StructureStepSpec, or path string)
        output_dir: Directory where the generated input file will be written
        spec_path: Optional explicit path to the spec file
        calculation_dir: Optional calculation directory for structure resolution
        project: Optional Project instance for structure resolution
        input_name: Optional name for the generated input file
        project_root: Optional project root for setting outdir and pseudo_dir.
                     If provided, sets outdir to "./outdir" and pseudo_dir to project_root/pseudo.
    
    Returns:
        Tuple of (generated_input_path, StructureStepSpec)
    """

    # Create resolver for legacy structure selectors if project_root is available
    # Only create resolver if project_root is actually a project directory
    resolve_structure_selector = None
    if project_root:
        def _make_resolver(proj_root: Path):
            from quantumvitas.core.resolution import resolve_structure
            from quantumvitas.core.project_utils import load_project_config, ProjectConfigError
            try:
                config = load_project_config(proj_root)
                def resolver(selector: str) -> str:
                    resolved = resolve_structure(proj_root, selector, config)
                    return resolved.meta.id
                return resolver
            except ProjectConfigError:
                # project_root is not a project directory - return None (no resolver)
                # Structure resolution will fall back to filesystem path resolution
                return None
        resolve_structure_selector = _make_resolver(project_root)
    
    spec_obj, resolved_spec_path = _load_step_spec(spec, spec_path, resolve_structure_selector=resolve_structure_selector)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Infer calculation_dir from spec_path if not provided
    # Pattern: calculations/<calculation_slug>/steps/<step_slug>.step.yaml
    if calculation_dir is None and resolved_spec_path:
        spec_path_obj = Path(resolved_spec_path)
        # Check if spec_path looks like a calculation step: .../calculations/.../steps/...step.yaml
        parts = spec_path_obj.parts
        if "steps" in parts:
            steps_idx = parts.index("steps")
            if steps_idx > 0:
                # calculation_dir is the parent of the steps directory
                calculation_dir = spec_path_obj.parent.parent

    # Load project from project_root if project is None but project_root is provided
    if project is None and project_root:
        try:
            from quantumvitas.project.model import Project
            project_root_path = Path(project_root).resolve()
            if (project_root_path / "project.qv.yml").exists():
                project = Project.open(project_root_path)
        except Exception:
            # If project loading fails, continue without project
            pass

    # Check if this is a Wannier90 step type - these need special handling
    # and should NOT go through QE input generation/validation
    step_type_lower = (spec_obj.step_type or "scf").lower()
    WANNIER90_STEP_TYPES = {"w90_preproc", "w90_run", "pw2wannier90"}
    
    # Phase 3C: Check if calculation is PySCF - PySCF steps should NOT go through QE input generation
    # PySCF engine builds input dynamically from structure + parameters
    calculation_engine_family = None
    if calculation_dir and project_root:
        try:
            from quantumvitas.core.models import load_calculation
            from quantumvitas.core.resolution import make_structure_selector_resolver
            from quantumvitas.core.project_utils import load_project_config
            calc_yaml_path = Path(calculation_dir) / "calculation.yaml"
            if calc_yaml_path.exists():
                project_root_path = Path(project_root).resolve()
                config = load_project_config(project_root_path)
                resolver = make_structure_selector_resolver(project_root_path, config=config)
                calc_model_check = load_calculation(calc_yaml_path, project_root=project_root_path, resolve_structure_selector=resolver)
                calculation_engine_family = calc_model_check.engine_family
        except Exception:
            pass
    
    PYSCF_STEP_TYPES = {"pyscf_scf", "pyscf_mp2", "pyscf_td", "pyscf_analysis", "pyscf_freq"}
    is_pyscf_step = step_type_lower in PYSCF_STEP_TYPES or calculation_engine_family == "pyscf"

    # Phase 3C: ORCA step types - ORCA engine builds input dynamically (not QE input)
    ORCA_STEP_TYPES = {"orca_scf", "orca_hf", "orca_td", "orca_mp2", "orca_opt", "orca_freq"}
    is_orca_step = step_type_lower in ORCA_STEP_TYPES or calculation_engine_family == "orca"

    import logging
    logger = logging.getLogger(__name__)
    
    if step_type_lower in WANNIER90_STEP_TYPES:
        # WANNIER90 PATH: Generate .win or .pw2wan files, skip QE input generation
        logger.info(
            f"[MATERIALIZE_STEP_SPEC] Wannier90 step detected: step_type={step_type_lower}, "
            f"skipping QE input generation and validation"
        )
        
        # Generate Wannier90 input file based on step type
        if step_type_lower == "w90_preproc" or step_type_lower == "w90_run":
            # Generate .win file
            from quantumvitas.io.wannier90_input import Wannier90Input
            
            # Resolve structure for Wannier90 input
            structure = _resolve_structure_for_spec(
                spec_obj,
                resolved_spec_path,
                calculation_dir=calculation_dir,
                project=project,
                project_root=project_root,
            )
            
            # Extract parameters from spec
            params = spec_obj.parameters or {}
            # Flatten nested parameters if needed (step parameters may be nested)
            flat_params = {}
            if isinstance(params, dict):
                for key, value in params.items():
                    if isinstance(value, dict):
                        flat_params.update(value)
                    else:
                        flat_params[key] = value
            
            # Create Wannier90Input from spec parameters
            w90_input = Wannier90Input()
            w90_input.seedname = flat_params.get("seedname", spec_obj.meta.slug or "wannier")
            if "num_wann" in flat_params and flat_params["num_wann"] is not None:
                w90_input.num_wann = int(flat_params["num_wann"])
            if "num_bands" in flat_params and flat_params["num_bands"] is not None:
                w90_input.num_bands = int(flat_params["num_bands"])
            if "num_iter" in flat_params and flat_params["num_iter"] is not None:
                w90_input.num_iter = int(flat_params["num_iter"])
            if "mp_grid" in flat_params and flat_params["mp_grid"] is not None:
                mp_grid = flat_params["mp_grid"]
                if isinstance(mp_grid, list):
                    # Filter out None values and convert to int
                    w90_input.mp_grid = [int(x) for x in mp_grid if x is not None]
            
            # CRITICAL: Extract kpoints from nscf step input (preserve exact order)
            # Do NOT generate from mp_grid - order must match nscf to avoid pw2wannier90 errors
            from quantumvitas.calculation.wannier90_kpoints import extract_kpoints_from_nscf_step
            nscf_kpoints = extract_kpoints_from_nscf_step(
                calculation_dir=calculation_dir if calculation_dir else Path("."),
                working_dir=output_dir
            )
            
            if nscf_kpoints:
                # Use kpoints from nscf (preserving order)
                w90_input.kpoints = nscf_kpoints
                logger.info(
                    f"[MATERIALIZE_STEP_SPEC] Extracted {len(nscf_kpoints)} kpoints from nscf step "
                    f"(preserving order for pw2wannier90 compatibility)"
                )
                
                # Consistency check: verify count matches mp_grid if mp_grid is set
                if w90_input.mp_grid:
                    expected_count = w90_input.mp_grid[0] * w90_input.mp_grid[1] * w90_input.mp_grid[2]
                    if len(nscf_kpoints) != expected_count:
                        logger.warning(
                            f"[MATERIALIZE_STEP_SPEC] Kpoints count mismatch: "
                            f"nscf has {len(nscf_kpoints)} kpoints, but mp_grid={w90_input.mp_grid} "
                            f"expects {expected_count}. This may cause pw2wannier90 errors."
                        )
            elif w90_input.mp_grid:
                # Fallback: generate from mp_grid if nscf kpoints not found (but log warning)
                logger.warning(
                    f"[MATERIALIZE_STEP_SPEC] Could not extract kpoints from nscf step. "
                    f"Generating from mp_grid={w90_input.mp_grid}, but order may not match nscf."
                )
                from quantumvitas.io.wannier90_input import generate_kpoints_from_mp_grid
                w90_input.kpoints = generate_kpoints_from_mp_grid(w90_input.mp_grid)
            if "projections" in flat_params and flat_params["projections"] is not None:
                w90_input.projections_block = str(flat_params["projections"])
            if "projections_block" in flat_params and flat_params["projections_block"] is not None:
                w90_input.projections_block = str(flat_params["projections_block"])
            
            # Add structure data
            if structure:
                # Wannier90 unit_cell_cart MUST be in Angstrom (not Bohr)
                # Structure.lattice.matrix is always in Angstrom in pymatgen
                lattice = structure.lattice
                w90_input.unit_cell_cart = [
                    [float(lattice.matrix[i][j]) for j in range(3)]
                    for i in range(3)
                ]
                w90_input.length_unit = "ang"
                
                # Atoms in fractional coordinates (must come from structure.frac_coords)
                w90_input.atoms_frac = []
                for site in structure.sites:
                    w90_input.atoms_frac.append([
                        site.specie.symbol,
                        float(site.frac_coords[0]),
                        float(site.frac_coords[1]),
                        float(site.frac_coords[2]),
                    ])
                
                # Consistency assertion: verify unit_cell_cart * atoms_frac ≈ cartesian coords
                # This ensures we're writing the correct lattice matrix
                import numpy as np
                lattice_matrix = np.array(w90_input.unit_cell_cart)
                for i, site in enumerate(structure.sites):
                    frac_coords = np.array(site.frac_coords)
                    expected_cart = lattice_matrix.T @ frac_coords
                    actual_cart = np.array(site.coords)
                    diff = np.abs(expected_cart - actual_cart)
                    max_diff = np.max(diff)
                    if max_diff > 1e-6:
                        raise ValueError(
                            f"Inconsistent structure data for atom {i} ({site.species_string}):\n"
                            f"  unit_cell_cart (Å) = {w90_input.unit_cell_cart}\n"
                            f"  atoms_frac[{i}] = {list(w90_input.atoms_frac[i][1:])}\n"
                            f"  Expected cartesian (from lattice @ frac) = {expected_cart}\n"
                            f"  Actual cartesian (from structure) = {actual_cart}\n"
                            f"  Max difference = {max_diff} Å (tolerance: 1e-6 Å)\n"
                            f"This indicates a bug in lattice/coordinate handling. "
                            f"structure.lattice.matrix should be in Angstrom and structure.coords should be cartesian."
                        )
            
            # Generate filename - ALWAYS use seedname.win (Wannier90 requirement)
            # Do NOT use input_name override for Wannier90 steps
            seedname = w90_input.seedname
            filename = f"{seedname}.win"
            
            # Safety check: ensure filename is valid
            if not filename or filename == '.' or filename == './':
                raise ValueError(
                    f"Invalid Wannier90 input filename: '{filename}'. "
                    f"Seedname was: {seedname}"
                )
            
            generated_input = output_dir / filename
            generated_input = generated_input.resolve()
            
            # Safety check: ensure we're not creating a directory
            if generated_input.exists() and generated_input.is_dir():
                raise ValueError(
                    f"Generated input path is a directory: {generated_input}. "
                    f"This should not happen. Filename was: {filename}"
                )
            
            # Write .win file
            generated_input.parent.mkdir(parents=True, exist_ok=True)
            w90_input.write(generated_input)
            logger.info(
                f"[MATERIALIZE_STEP_SPEC] Generated Wannier90 .win file: {generated_input}"
            )
            
            # Return relative path from calculation_dir if possible (for Step.input_file)
            # Otherwise return absolute path
            if calculation_dir:
                calc_dir_path = Path(calculation_dir).resolve()
                try:
                    rel_path = generated_input.relative_to(calc_dir_path)
                    return calc_dir_path / rel_path, spec_obj
                except ValueError:
                    # Not relative to calculation_dir, return absolute
                    pass
            
            return generated_input, spec_obj
        
        elif step_type_lower == "pw2wannier90":
            # Generate .pw2wan file
            from quantumvitas.io.wannier90_input import Pw2Wannier90Input
            
            params = spec_obj.parameters or {}
            flat_params = {}
            if isinstance(params, dict):
                for key, value in params.items():
                    if isinstance(value, dict):
                        flat_params.update(value)
                    else:
                        flat_params[key] = value
            
            # Load calculation context for prefix/outdir injection
            calc_prefix = None
            calc_outdir = "./outdir"
            if calculation_dir and project_root:
                try:
                    from quantumvitas.core.models import load_calculation
                    from quantumvitas.core.resolution import make_structure_selector_resolver
                    from quantumvitas.core.project_utils import load_project_config
                    calc_yaml_path = Path(calculation_dir) / "calculation.yaml"
                    if calc_yaml_path.exists():
                        project_root_path = Path(project_root).resolve()
                        config = load_project_config(project_root_path)
                        resolver = make_structure_selector_resolver(project_root_path, config=config)
                        calc_model = load_calculation(calc_yaml_path, project_root=project_root_path, resolve_structure_selector=resolver)
                        # Stable prefix derived from calc ULID; slug changes do not affect it
                        calc_prefix = stable_short_calc_prefix(calc_model.meta.id) if calc_model.meta and calc_model.meta.id else None
                except Exception:
                    pass
            
            pw2wan_input = Pw2Wannier90Input()
            pw2wan_input.seedname = flat_params.get("seedname", spec_obj.meta.slug or "wannier")
            # R1-R3: Use calculation-level prefix, ignore step-level prefix
            if calc_prefix:
                pw2wan_input.prefix = calc_prefix
                if "prefix" in flat_params and flat_params["prefix"] != calc_prefix:
                    logger.info(
                        f"[PREFIX_INJECTION] Step-level prefix '{flat_params['prefix']}' ignored, "
                        f"using stable id-derived prefix '{calc_prefix}' for pw2wannier90"
                    )
            else:
                pw2wan_input.prefix = flat_params.get("prefix", "pwscf")
            pw2wan_input.outdir = calc_outdir
            
            # Generate filename - Use standard QE naming: pw2wan.in (not seedname.pw2wan)
            # The seedname inside the file (e.g., 'diamond') controls output file names (diamond.mmn, etc.)
            # But the input file itself should be pw2wan.in for consistency with other QE steps
            from quantumvitas.calculation.naming import CalculationFileNaming
            if input_name:
                filename = input_name
            else:
                # Use standard naming convention: pw2wan.in
                filename = CalculationFileNaming.input_filename("pw2wannier90")
            
            # Ensure filename is not empty or '.' (safety check)
            if not filename or filename == '.' or filename == './':
                raise ValueError(
                    f"Invalid pw2wannier90 input filename: '{filename}'. "
                    f"Must be a valid filename like 'pw2wan.in'."
                )
            
            generated_input = output_dir / filename
            generated_input = generated_input.resolve()
            
            # Safety check: ensure we're not creating a directory
            if generated_input.exists() and generated_input.is_dir():
                raise ValueError(
                    f"Generated input path is a directory: {generated_input}. "
                    f"This should not happen. Filename was: {filename}"
                )
            
            # Write .pw2wan file (content has seedname='diamond', but filename is pw2wan.in)
            generated_input.parent.mkdir(parents=True, exist_ok=True)
            generated_input.write_text(pw2wan_input.to_string())
            logger.info(
                f"[MATERIALIZE_STEP_SPEC] Generated pw2wannier90 input file: {generated_input} "
                f"(seedname={pw2wan_input.seedname} in content)"
            )
            
            # Return relative path from calculation_dir if possible (for Step.input_file)
            # Otherwise return absolute path
            if calculation_dir:
                calc_dir_path = Path(calculation_dir).resolve()
                try:
                    rel_path = generated_input.relative_to(calc_dir_path)
                    return calc_dir_path / rel_path, spec_obj
                except ValueError:
                    # Not relative to calculation_dir, return absolute
                    pass
            
            return generated_input, spec_obj
    
    # Phase 3C: PySCF steps - no input file generation (PySCF engine builds input dynamically)
    if is_pyscf_step:
        logger.info(
            f"[MATERIALIZE_STEP_SPEC] PySCF step detected: step_type={step_type_lower}, "
            f"engine_family={calculation_engine_family}, skipping QE input generation. "
            f"PySCF engine will build input dynamically from structure + parameters."
        )
        # Generate a dummy input file path (PySCF engine doesn't use it, but Step.input_file requires a path)
        from quantumvitas.calculation.naming import CalculationFileNaming
        if input_name:
            filename = input_name
        else:
            ext = CalculationFileNaming.input_extension(step_type_lower)
            filename = f"{step_type_lower}{ext}"
        
        generated_input = Path(output_dir) / filename
        generated_input = generated_input.resolve()
        generated_input.parent.mkdir(parents=True, exist_ok=True)
        # Don't write a file - PySCF engine builds input dynamically
        return generated_input, spec_obj

    # Phase 3C: ORCA steps - no QE input file generation (ORCA engine builds input dynamically)
    # ORCA uses molecular systems (Molecule), not periodic structures - cannot use qe_input_from_structure()
    if is_orca_step:
        logger.info(
            f"[MATERIALIZE_STEP_SPEC] ORCA step detected: step_type={step_type_lower}, "
            f"engine_family={calculation_engine_family}, skipping QE input generation. "
            f"ORCA engine will build input dynamically from structure + parameters."
        )
        # Generate a dummy input file path (ORCA engine doesn't use it, but Step.input_file requires a path)
        from quantumvitas.calculation.naming import CalculationFileNaming
        if input_name:
            filename = input_name
        else:
            ext = CalculationFileNaming.input_extension(step_type_lower)
            filename = f"{step_type_lower}{ext}"

        generated_input = Path(output_dir) / filename
        generated_input = generated_input.resolve()
        generated_input.parent.mkdir(parents=True, exist_ok=True)
        # Don't write a file - ORCA engine builds input dynamically
        return generated_input, spec_obj

    # QE PATH: Standard QE input generation (existing logic)
    structure = _resolve_structure_for_spec(
        spec_obj,
        resolved_spec_path,
        calculation_dir=calculation_dir,
        project=project,
        project_root=project_root,  # Pass project_root for calculation resolution
    )

    # Load calculation context (species_map, prefix, outdir) if available
    calculation_species_map = None
    calculation_prefix = None
    calculation_outdir = "./outdir"  # Default outdir
    calculation_context = {}
    calc_model = None
    if calculation_dir and project_root:
        try:
            from quantumvitas.core.models import load_calculation
            from quantumvitas.core.resolution import make_structure_selector_resolver, resolve_structure
            from quantumvitas.core.project_utils import load_project_config
            calc_yaml_path = Path(calculation_dir) / "calculation.yaml"
            if calc_yaml_path.exists():
                project_root_path = Path(project_root).resolve()
                config = load_project_config(project_root_path)
                resolver = make_structure_selector_resolver(project_root_path, config=config)
                calc_model = load_calculation(calc_yaml_path, project_root=project_root_path, resolve_structure_selector=resolver)
                # Phase 3C: Use engine_family from calc_model if not already loaded
                if calculation_engine_family is None:
                    calculation_engine_family = calc_model.engine_family
                calculation_species_map = calc_model.species_map
                # R1: Canonical prefix = stable id-derived prefix (from calc ULID)
                # Stable prefix derived from calc ULID; slug changes do not affect it
                calculation_prefix = stable_short_calc_prefix(calc_model.meta.id) if calc_model.meta and calc_model.meta.id else None
                calculation_context["calculation_path"] = str(calc_yaml_path)
                calculation_context["species_map"] = calc_model.species_map
                calculation_context["prefix"] = calculation_prefix
                if calc_model.structure_id:
                    struct_resolved = resolve_structure(project_root_path, calc_model.structure_id, config=config)
                    calculation_context["structure_path"] = str(struct_resolved.absolute_path)
        except Exception:
            # If calculation loading fails, continue without calculation context (fallback to QE input parsing)
            pass
    
    logger.info(
        f"[MATERIALIZE_STEP_SPEC] QE step detected: step_type={step_type_lower}, "
        f"using QE input generation and validation"
    )
    
    # Validate species_map for project runs
    # Project runs require calculation.yaml species_map with all required elements
    is_project_run = (calculation_dir and project_root and calc_model is not None)
    
    # Warn if step-level species_overrides detected in project runs
    if is_project_run and spec_obj.species_overrides:
        import warnings
        warnings.warn(
            "Step-level species_overrides detected in step.yaml. "
            "Project runs ignore step species_overrides and use calculation.yaml species_map instead. "
            "Configure species via `qv configure species ...`.",
            UserWarning,
            stacklevel=2,
        )
    
    if is_project_run:
        if not calculation_species_map:
            # Get required elements from structure
            required_elements = sorted(set(str(el) for el in structure.composition.elements))
            elements_str = ", ".join(required_elements)
            raise ValueError(
                f"Pseudopotential not configured for element(s): {elements_str}. "
                "Project runs require calculation.yaml species_map. step.yaml species_overrides is standalone-only. "
                "Configure using:\n"
                "  - CLI: --SPECIES.<element>.pseudopot=<filename>\n"
                "  - Or set calculation.yaml species_map"
            )
        
        # Check that species_map has all required elements with pseudopot filenames
        required_elements = set(str(el) for el in structure.composition.elements)
        missing_elements = []
        for element in required_elements:
            element_entry = calculation_species_map.get(element)
            if not element_entry or not isinstance(element_entry, dict):
                missing_elements.append(element)
                continue
            
            # Check that pseudopot filename is present (not placeholder)
            pseudo_filename = element_entry.get("pseudo_basename") or element_entry.get("pseudopot")
            if not pseudo_filename:
                missing_elements.append(element)
                continue
            
            # Check for placeholder names
            from quantumvitas.core.pseudo import is_missing_pseudo_placeholder
            if is_missing_pseudo_placeholder(pseudo_filename):
                missing_elements.append(element)
        
        if missing_elements:
            elements_str = ", ".join(sorted(missing_elements))
            raise ValueError(
                f"Pseudopotential not configured for element(s): {elements_str}. "
                "Project runs require calculation.yaml species_map. step.yaml species_overrides is standalone-only. "
                "Configure using:\n"
                "  - CLI: --SPECIES.<element>.pseudopot=<filename>\n"
                "  - Or set calculation.yaml species_map"
            )
    
    # Pass species_map to generate_qe_input_from_spec so it populates ATOMIC_SPECIES correctly
    # This ensures ATOMIC_SPECIES in the generated QE input has actual pseudo filenames
    # (not placeholders) when calculation-level species_map is available
    # For project runs, disallow fallback to step-level species_overrides
    qe_input, _ = generate_qe_input_from_spec(
        structure, 
        spec_obj, 
        species_map=calculation_species_map,
        allow_step_species_overrides=not is_project_run,  # Project runs: False, standalone: True
    )
    
    # R2-R4: Inject calculation-level prefix/outdir if schema supports it
    if calculation_prefix or calculation_outdir:
        _inject_calculation_prefix_outdir(
            qe_input=qe_input,
            step_type=step_type_lower,
            calculation_prefix=calculation_prefix,
            calculation_outdir=calculation_outdir,
            spec_params=spec_obj.parameters or {},
            logger=logger,
        )

    # Set outdir and pseudo_dir if project_root is provided
    if project_root:
        project_root_path = Path(project_root).resolve()
        
        # Validate project_root is not repo root
        from quantumvitas.core.pseudo_config import _find_quantumvitas_root
        repo_root = _find_quantumvitas_root()
        if repo_root and project_root_path == repo_root.resolve():
            raise ValueError(
                f"Project root cannot be the repository root. "
                f"Provided project_root={project_root} is the repo root, which is invalid."
            )
        
        set_outdir_to_temp(qe_input)
        
        # Use central pseudopotential resolution
        from quantumvitas.core.pseudo import ensure_qe_pseudos, get_system_pseudo_dir
        from quantumvitas.calculation.input_runner import set_pseudo_dir_in_input
        
        # Normal case: project_root is a user project
        project_pseudo_dir = project_root_path / "pseudo"
        
        # Write temporary input file to extract required pseudos
        temp_input = output_dir / ".temp_input_for_pseudo_resolution.in"
        QEInputGenerator.write_file(qe_input, temp_input)
        
        # Log before pseudo resolution
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(
            f"[MATERIALIZE_STEP_SPEC] before ensure_qe_pseudos "
            f"calculation_dir={calculation_dir} "
            f"project_pseudo_dir={project_pseudo_dir} "
            f"calculation_context={calculation_context} "
            f"species_map_provided={'Yes' if calculation_species_map else 'No'}"
        )
        
        # Resolve pseudopotentials
        # Pass calculation_species_map as PRIMARY source (calculation-level authority)
        # This ensures calculation.yaml species_map is honored even if temp QE input has placeholders
        pseudo_result = ensure_qe_pseudos(
            qe_input_file=temp_input,
            project_pseudo_dir=project_pseudo_dir,
            system_pseudo_dir=get_system_pseudo_dir(),
            species_map=calculation_species_map,
        )
        
        # Clean up temp file
        if temp_input.exists():
            temp_input.unlink()
        
        if not pseudo_result.all_available:
            # This is a missing file error (pseudopotential was configured but file not found)
            # Configuration errors are caught earlier in ensure_qe_pseudos
            raise RuntimeError(
                f"Pseudopotential file(s) not found or could not be downloaded. "
                f"This is a missing file error (pseudopotential was configured but the file is missing). "
                f"Project pseudo dir: {project_pseudo_dir}. "
                f"Check that the pseudopotential filenames in your step spec are correct and the files exist."
            )
        
        # Set pseudo_dir in QE input
        set_pseudo_dir_in_input(qe_input, project_pseudo_dir, output_dir)

    filename = input_name or spec_obj.input_name or f"{resolved_spec_path.stem}.pw.in"
    generated_input = output_dir / filename
    QEInputGenerator.write_file(qe_input, generated_input)
    return generated_input, spec_obj


def _load_step_spec(
    spec: SpecLike,
    spec_path: Optional[Path | str],
    resolve_structure_selector: Optional[callable] = None,
) -> tuple[StructureStepSpec, Path]:
    if isinstance(spec, StructureStepSpec):
        path = Path(spec_path).resolve() if spec_path else Path.cwd()
        return spec, path

    path = Path(spec).resolve()
    # Load step spec with resolver for legacy structure selector normalization
    return StructureStepSpec.from_yaml(path, resolve_structure_selector=resolve_structure_selector), path


def _resolve_structure_for_spec(
    spec: StructureStepSpec,
    spec_path: Path,
    *,
    calculation_dir: Optional[Path | str],
    project: Optional["Project"],
    project_root: Optional[Path | str] = None,
) -> PMGStructure | PMGMolecule:
    """
    Resolve structure for step spec.
    
    DAG + ID-only model: Steps inherit structure from calculation.structure_id.
    Legacy: Steps may have structure_id (for backwards compatibility).
    
    Resolution order (strict):
    1. Step-local structure (legacy support): If spec.structure_id or spec.structure is present
    2. Calculation-based structure (preferred): If calculation_dir exists, load calculation.yaml and use calculation.structure_id
    3. Registry-based resolution: If project/registry is available, use it
    4. Last-resort filesystem search: Only when there is no calculation context
    
    Args:
        spec: Step spec to resolve structure for
        spec_path: Path to the step spec file
        calculation_dir: Optional calculation directory (for calculation.yaml lookup)
        project: Optional Project instance (for registry-based resolution)
        project_root: Optional project root path (for loading project if project is None)
    """
    # Debug logging (can be enabled for troubleshooting)
    # import logging
    # logger = logging.getLogger(__name__)
    # logger.debug(f"_resolve_structure_for_spec: project_root={project_root}, calculation_dir={calculation_dir}, spec.structure_id={spec.structure_id}")
    
    # Normalize paths
    calculation_dir_path = Path(calculation_dir).resolve() if calculation_dir else None
    project_root_path = Path(project_root).resolve() if project_root else None
    
    # Load project from project_root if project is None but project_root is provided
    if project is None and project_root_path:
        try:
            from quantumvitas.project.model import Project
            if (project_root_path / "project.qv.yml").exists():
                project = Project.open(project_root_path)
                logger.debug(f"  Loaded project from project_root: {project.root}")
        except Exception as e:
            logger.debug(f"  Failed to load project from project_root: {e}")
    
    # ========================================================================
    # 1. Step-local structure (legacy support)
    # ========================================================================
    if spec.structure_id or spec.structure:
        # logger.debug("  Attempting step-local structure resolution")
        if spec.structure_id:
            # Try to resolve via project registry first
            if project:
                try:
                    struct_ref = project.get_structure(spec.structure_id)
                    # logger.debug(f"  Found structure via project registry: {struct_ref.path}")
                    return read_structure(struct_ref.path)
                except Exception:
                    pass
            
            # Try filesystem search by structure_id
            if project_root_path:
                structures_dir = project_root_path / "structures"
                if structures_dir.exists():
                    import json
                    from quantumvitas.io.structure_io import STRUCTURE_META_KEY
                    for struct_file in structures_dir.glob("*.json"):
                        try:
                            struct_data = json.loads(struct_file.read_text())
                            struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                            if struct_meta.get("id") == spec.structure_id:
                                return read_structure(struct_file)
                        except Exception:
                            continue
        
        # Try legacy structure selector (path-based)
        if spec.structure:
            structure_value = spec.structure
            candidate = Path(structure_value)
            
            # Try absolute path
            if candidate.is_absolute() and candidate.exists():
                return read_structure(candidate)
            
            # Try relative paths
            search_roots = [spec_path.parent]
            if calculation_dir_path:
                search_roots.extend([calculation_dir_path, calculation_dir_path.parent])
            if project_root_path:
                search_roots.append(project_root_path / "structures")
            
            for root in search_roots:
                candidate_path = (root / candidate).resolve()
                if candidate_path.exists():
                    return read_structure(candidate_path)
            
            # Try project.get_structure for selector resolution
            if project:
                try:
                    struct_ref = project.get_structure(structure_value)
                    return read_structure(struct_ref.path)
                except Exception:
                    pass
    
    # ========================================================================
    # 2. Calculation-based structure (preferred in project world)
    # ========================================================================
    if calculation_dir_path:
        # logger.debug("  Attempting calculation-based structure resolution")
        calculation_yaml = calculation_dir_path / "calculation.yaml" if calculation_dir_path.is_dir() else calculation_dir_path
        if not calculation_yaml.exists() and calculation_dir_path.is_dir():
            calculation_yaml = calculation_dir_path / "calculation.yaml"
        
        if calculation_yaml.exists():
            try:
                from quantumvitas.core.models import load_calculation
                
                # Determine project_root for load_calculation
                wf_project_root = project.root if project else project_root_path
                if not wf_project_root:
                    # Try to infer from calculation_dir
                    current = calculation_yaml.parent
                    while current != current.parent:
                        if (current / "project.qv.yml").exists():
                            wf_project_root = current
                            break
                        current = current.parent
                
                if wf_project_root:
                    wf_model = load_calculation(calculation_yaml, wf_project_root)
                    # logger.debug(f"  Loaded calculation model: structure_id={wf_model.structure_id}")
                    
                    structure_to_resolve = wf_model.structure_id
                    if not structure_to_resolve and wf_model.structure:
                        # Legacy: calculation has structure path/selector, try to resolve it
                        if project:
                            try:
                                struct_ref = project.get_structure(wf_model.structure)
                                structure_to_resolve = struct_ref.meta.id
                            except Exception:
                                structure_to_resolve = wf_model.structure
                    
                    if structure_to_resolve:
                        # Resolve structure from calculation.structure_id
                        if project:
                            try:
                                struct_ref = project.get_structure(structure_to_resolve)
                                return read_structure(struct_ref.path)
                            except Exception:
                                pass
                        
                        # Fallback: filesystem search by structure_id
                        structures_dir = wf_project_root / "structures"
                        if structures_dir.exists():
                            import json
                            from quantumvitas.io.structure_io import STRUCTURE_META_KEY
                            for struct_file in structures_dir.glob("*.json"):
                                try:
                                    struct_data = json.loads(struct_file.read_text())
                                    struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                                    if struct_meta.get("id") == structure_to_resolve:
                                        return read_structure(struct_file)
                                except Exception:
                                    continue
            except Exception:
                pass
    
    # ========================================================================
    # 3. Registry-based resolution (if available)
    # ========================================================================
    # This would use step_id → calculation_id → structure_id via registry
    # For now, this is handled by calculation-based resolution above
    
    # ========================================================================
    # 4. Last-resort filesystem search (when there is no calculation context or calculation has no structure_id)
    # ========================================================================
    # Try to find structure files in common locations
    import json
    from quantumvitas.io.structure_io import STRUCTURE_META_KEY
    
    search_roots = []
    if calculation_dir_path:
        # Check structures directory relative to calculation_dir
        search_roots.append(calculation_dir_path / "structures")
        search_roots.append(calculation_dir_path.parent / "structures")
    # Also check relative to step spec location
    search_roots.append(spec_path.parent.parent / "structures")
    if project_root_path:
        search_roots.append(project_root_path / "structures")
    
    # Try to find structure JSON files in these directories
    for root in search_roots:
        if root.exists() and root.is_dir():
            struct_files = list(root.glob("*.json"))
            # If there's exactly one structure file, use it
            if len(struct_files) == 1:
                return read_structure(struct_files[0])
            # If multiple, and we have a calculation structure_id, try to match by ID
            if calculation_dir_path:
                try:
                    from quantumvitas.core.models import load_calculation
                    calculation_yaml = calculation_dir_path / "calculation.yaml"
                    if calculation_yaml.exists():
                        wf_project_root = project.root if project else project_root_path
                        if not wf_project_root:
                            current = calculation_yaml.parent
                            while current != current.parent:
                                if (current / "project.qv.yml").exists():
                                    wf_project_root = current
                                    break
                                current = current.parent
                        if wf_project_root:
                            wf_model = load_calculation(calculation_yaml, wf_project_root)
                            if wf_model.structure_id:
                                for struct_file in struct_files:
                                    try:
                                        struct_data = json.loads(struct_file.read_text())
                                        struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                                        if struct_meta.get("id") == wf_model.structure_id:
                                            return read_structure(struct_file)
                                    except Exception:
                                        continue
                except Exception:
                    pass
    
    # ========================================================================
    # All resolution attempts failed
    # ========================================================================
    raise FileNotFoundError(
        f"Step spec at {spec_path} has neither structure_id (current: {spec.structure_id}) nor structure field (current: {spec.structure}). "
        f"Calculation-based resolution also failed (calculation_dir: {calculation_dir_path}). "
        f"Please ensure the step spec has a valid structure_id or structure selector, "
        f"or that a calculation.yaml exists with a valid structure_id."
    )
    # First, try legacy structure_id from step spec (for backwards compatibility)
    # Note: spec.structure_id might be a string, so check it's truthy and non-empty
    if spec.structure_id:
        if project is not None:
            # Try to resolve via project registry
            try:
                # Try to find structure by ID in project's structures dict
                struct_ref = None
                for ref in project.structures.values():
                    if ref.meta.id == spec.structure_id:
                        struct_ref = ref
                        break
                
                if struct_ref is None:
                    # Fall back to get_structure which might resolve by slug/name
                    struct_ref = project.get_structure(spec.structure_id)
                
                return read_structure(struct_ref.path)
            except (KeyError, AttributeError) as e:
                # If structure_id doesn't resolve via project, fall through to calculation resolution
                pass
        
        # If project is None or structure not found in project, try filesystem resolution
        # Look for structure files in common locations relative to spec_path
        import json
        from quantumvitas.io.structure_io import STRUCTURE_META_KEY
        
        search_roots: list[Path] = [spec_path.parent]
        if calculation_dir:
            calculation_dir_path = Path(calculation_dir).resolve()
            search_roots.append(calculation_dir_path)
            search_roots.append(calculation_dir_path.parent)
            # Check structures directory relative to calculation_dir (most common case)
            structures_dir = calculation_dir_path / "structures"
            if structures_dir.exists():
                search_roots.append(structures_dir)
            # Also check structures directory relative to calculation_dir.parent (project-level)
            project_structures_dir = calculation_dir_path.parent / "structures"
            if project_structures_dir.exists():
                search_roots.append(project_structures_dir)
        
        # Try to find structure file by scanning for files with matching meta.id
        for root in search_roots:
            if root.exists() and root.is_dir():
                # Look for JSON files in this directory
                for struct_file in root.glob("*.json"):
                    try:
                        struct_data = json.loads(struct_file.read_text())
                        struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                        if struct_meta.get("id") == spec.structure_id:
                            return read_structure(struct_file)
                    except Exception:
                        continue
        
        # If structure_id doesn't resolve and no structure selector, raise error
        if not spec.structure:
            raise FileNotFoundError(
                f"Step spec at {spec_path} has structure_id ({spec.structure_id}) but structure not found. "
                f"Tried project registry and filesystem search. Project: {project is not None}"
            )
        # Fall through to legacy structure selector
        pass
    
    # DAG + ID-only model: If step doesn't have structure_id, resolve from calculation
    if not spec.structure_id and calculation_dir:
        # Try to load project if not provided but project_root is available
        if project is None and project_root:
            try:
                from quantumvitas.project.model import Project
                project_root_path = Path(project_root).resolve()
                if (project_root_path / "project.qv.yml").exists():
                    project = Project.open(project_root_path)
            except Exception:
                pass
        
        if project:
            try:
                from quantumvitas.core.models import load_calculation
                calculation_path = Path(calculation_dir)
                if calculation_path.is_dir():
                    calculation_path = calculation_path / "calculation.yaml"
                if calculation_path.exists():
                    wf_model = load_calculation(calculation_path, project.root)
                    # Check both structure_id (new) and structure (legacy path selector)
                    structure_to_resolve = wf_model.structure_id
                    if not structure_to_resolve and wf_model.structure:
                        # Legacy: calculation has structure path, try to resolve it
                        try:
                            struct_ref = project.get_structure(wf_model.structure)
                            structure_to_resolve = struct_ref.meta.id
                        except Exception:
                            # If resolution fails, try to use structure as a path
                            structure_to_resolve = wf_model.structure
                    
                    if structure_to_resolve:
                        # Resolve structure from calculation
                        try:
                            if structure_to_resolve.startswith("01") and len(structure_to_resolve) == 26:
                                # It's a ULID, resolve by ID
                                struct_ref = project.get_structure(structure_to_resolve)
                            else:
                                # It's a path or selector, resolve by selector
                                struct_ref = project.get_structure(structure_to_resolve)
                            return read_structure(struct_ref.path)
                        except Exception:
                            # If project.get_structure fails, try filesystem search
                            import json
                            from quantumvitas.io.structure_io import STRUCTURE_META_KEY
                            
                            search_roots = [
                                project.root / "structures",
                                calculation_path.parent / "structures",
                                calculation_path.parent.parent / "structures",
                            ]
                            
                            for root in search_roots:
                                if root.exists() and root.is_dir():
                                    for struct_file in root.glob("*.json"):
                                        try:
                                            struct_data = json.loads(struct_file.read_text())
                                            struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                                            if struct_meta.get("id") == structure_to_resolve:
                                                return read_structure(struct_file)
                                        except Exception:
                                            continue
            except Exception as e:
                # If calculation resolution fails, fall through to legacy structure selector
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Calculation structure resolution failed: {e}")
                pass
        else:
            # No project available, but try to load calculation.yaml directly and find structure via filesystem
            try:
                from quantumvitas.core.models import load_calculation
                calculation_path = Path(calculation_dir)
                if calculation_path.is_dir():
                    calculation_path = calculation_path / "calculation.yaml"
                if calculation_path.exists():
                    # Try to infer project_root from calculation_dir
                    inferred_project_root = None
                    if project_root:
                        inferred_project_root = Path(project_root).resolve()
                    else:
                        # Try to find project root by walking up from calculation_dir
                        current = calculation_path.parent
                        while current != current.parent:
                            if (current / "project.qv.yml").exists():
                                inferred_project_root = current
                                break
                            current = current.parent
                    
                    if inferred_project_root:
                        wf_model = load_calculation(calculation_path, inferred_project_root)
                        if wf_model.structure_id:
                            # Try to find structure file by ID in common locations
                            import json
                            from quantumvitas.io.structure_io import STRUCTURE_META_KEY
                            
                            search_roots = [
                                inferred_project_root / "structures",
                                calculation_path.parent / "structures",
                                calculation_path.parent.parent / "structures",
                            ]
                            
                            for root in search_roots:
                                if root.exists() and root.is_dir():
                                    for struct_file in root.glob("*.json"):
                                        try:
                                            struct_data = json.loads(struct_file.read_text())
                                            struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                                            if struct_meta.get("id") == wf_model.structure_id:
                                                return read_structure(struct_file)
                                        except Exception:
                                            continue
            except Exception:
                # If calculation resolution fails, fall through to legacy structure selector
                pass
    
    # Fall back to structure selector (legacy)
    structure_value = spec.structure
    if not structure_value:
        # Last resort: try to find structure file in common locations
        # This handles cases where step spec was created without structure_id/structure
        # (e.g., by build_step_spec_from_qe_input which creates structure in structures_dir)
        import json
        from quantumvitas.io.structure_io import STRUCTURE_META_KEY
        
        search_roots = []
        if calculation_dir:
            calculation_dir_path = Path(calculation_dir).resolve()
            # Check structures directory relative to calculation_dir
            search_roots.append(calculation_dir_path / "structures")
            search_roots.append(calculation_dir_path.parent / "structures")
        # Also check relative to step spec location
        search_roots.append(spec_path.parent.parent / "structures")
        if project_root:
            project_root_path = Path(project_root).resolve()
            search_roots.append(project_root_path / "structures")
        
        # Try to find any structure JSON file in these directories
        # First, try to get calculation structure_id if available
        calculation_structure_id = None
        if calculation_dir and project:
            try:
                from quantumvitas.core.models import load_calculation
                calculation_path = Path(calculation_dir)
                if calculation_path.is_dir():
                    calculation_path = calculation_path / "calculation.yaml"
                if calculation_path.exists():
                    wf_model = load_calculation(calculation_path, project.root)
                    calculation_structure_id = wf_model.structure_id
            except Exception:
                pass
        
        for root in search_roots:
            if root.exists() and root.is_dir():
                struct_files = list(root.glob("*.json"))
                # If there's only one structure file, use it
                if len(struct_files) == 1:
                    return read_structure(struct_files[0])
                # Otherwise, try to match by ID (from spec or calculation)
                structure_id_to_match = spec.structure_id or calculation_structure_id
                if structure_id_to_match:
                    for struct_file in struct_files:
                        try:
                            struct_data = json.loads(struct_file.read_text())
                            struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                            if struct_meta.get("id") == structure_id_to_match:
                                return read_structure(struct_file)
                        except Exception:
                            continue
        
        # If still no structure found, raise error
        raise FileNotFoundError(
            f"Step spec at {spec_path} has neither structure_id (current: {spec.structure_id}) nor structure field (current: {spec.structure}). "
            f"Please ensure the step spec has a valid structure_id or structure selector, or that a structure file exists in a structures/ directory."
        )
    
    candidate = Path(structure_value)

    if candidate.is_absolute() and candidate.exists():
        return read_structure(candidate)

    search_roots: list[Path] = [spec_path.parent]
    if calculation_dir:
        calculation_dir_path = Path(calculation_dir).resolve()
        search_roots.append(calculation_dir_path)
        search_roots.append(calculation_dir_path.parent)

    for root in search_roots:
        candidate_path = (root / candidate).resolve()
        if candidate_path.exists():
            return read_structure(candidate_path)

    if project:
        try:
            struct_ref = project.get_structure(structure_value)
            return read_structure(struct_ref.path)
        except KeyError:
            pass

    raise FileNotFoundError(
        f"Unable to resolve structure '{structure_value}' referenced in {spec_path}"
    )

