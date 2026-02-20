from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple, Union

from typing import TYPE_CHECKING

from pymatgen.core import Structure as PMGStructure, Molecule as PMGMolecule

from quantumvitas.core.public import ResourceMeta, ensure_relative_path, meta_from_name
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
    - structure_ulid: ULID of the structure (canonical reference)
    - structure: Legacy selector field (for backwards compatibility when loading)
    """

    meta: ResourceMeta
    structure: str  # Legacy selector (backwards compat, not authoritative)
    structure_ulid: Optional[str] = None  # Canonical structure reference (ULID)
    step_type_spec: str = "scf"
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
        
        Handles both new format (structure_ulid) and legacy format (structure selector).
        
        Backwards compatibility (legacy structure selector):
        - If structure_ulid is missing but structure selector is present, resolve it to structure_ulid
        - This resolution happens only on input (from_dict/loader), not on output (to_dict)
        - After resolution, the structure_ulid is stored and the selector is dropped
        
        Args:
            data: Dictionary containing step spec data
            source_path: Optional path to the step spec file
            resolve_structure_selector: Optional callable(selector: str) -> str that resolves
                a structure selector (name/slug/path) to a structure_ulid (ULID).
                If provided and structure_ulid is missing, legacy 'structure' selector will be resolved.
        """
        # New format: structure_ulid (canonical)
        structure_ulid = data.get("structure_ulid")
        
        # Legacy format: structure selector (for backwards compat on input only)
        structure = data.get("structure")
        
        # If structure_ulid is missing but structure selector is present, resolve it via resolver
        if not structure_ulid and structure and resolve_structure_selector:
            try:
                resolved_resource = resolve_structure_selector(structure)
                # Extract the ID from the resolved resource
                structure_ulid = resolved_resource.meta.ulid if hasattr(resolved_resource, 'meta') else str(resolved_resource)
                # Drop the legacy selector after resolution
                structure = None
            except Exception:
                # Resolution failed - keep structure selector for now (will fail on to_dict if not resolved)
                pass
        
        # DAG + ID-only model: Step YAML does NOT contain structure_ulid.
        # Structure is resolved from calculation.structure_ulid at execution time.
        # Legacy structure_ulid/structure fields are accepted for backwards compatibility only.
        # If present, they are kept in memory but not written to YAML.
        
        # Step.yaml stores machine types (SPEC, e.g., "qe_scf").
        # Constitution §B: Persisted truth = SPEC. In-memory model MUST use SPEC types.
        # No normalization to GEN - use registry mapping for display/filenames when needed.
        # HARD ERROR if old keys exist
        if "step_type" in data and "step_type_spec" not in data:
            raise ValueError("Legacy 'step_type' key found in step.yaml. Run migration script.")
        step_type_spec = str(data.get("step_type_spec", "scf"))
        
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
        # HARD ERROR if old meta.ulid key exists
        if meta_dict and "id" in meta_dict and "ulid" not in meta_dict:
            raise ValueError("Legacy 'meta.ulid' key found in step.yaml. Run migration script.")
        default_name = data.get("name") or str(step_type_spec)
        default_path = (
            ensure_relative_path(source_path.name, base=source_path.parent)
            if source_path
            else (meta_dict or {}).get("path") or f"{default_name}.step.yaml"
        )
        # CANONICAL: meta_dict must have "ulid" key only (NO backwards compat)
        meta = ResourceMeta.from_dict(
            meta_dict,
            kind="step",
            default_name=default_name,
            default_path=default_path,
        )

        return cls(
            meta=meta,
            structure_ulid=structure_ulid,
            structure=structure or "",  # Provide empty string if only structure_ulid present
            step_type_spec=step_type_spec,
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
                a structure selector (name/slug/path) to a structure_ulid (ULID).
                If provided and structure_ulid is missing, legacy 'structure' selector will be resolved.
        """
        spec_path = Path(path)
        from quantumvitas.core.public import StepDoc
        content = StepDoc.load(spec_path).to_dict()
        if not isinstance(content, dict):
            raise ValueError(f"Step file {path} must contain a mapping at the root")
        return cls.from_dict(content, source_path=spec_path, resolve_structure_selector=resolve_structure_selector)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        DAG + ID-only model invariants (enforced here):
        - Step YAML contains ONLY step-local configuration (parameters, cards, species_overrides).
        - NO cross-resource references: structure_ulid, parent_calculation_id, or structure selector.
        - Structure is resolved via calculation.structure_ulid at execution time (calculation owns structure).
        - Parent calculation is implicit from step file location (calculations/<slug>/steps/<step>.step.yaml).
        
        This method explicitly excludes structure_ulid, parent_calculation_id, and structure fields
        to enforce the DAG invariant that steps do not duplicate calculation-level references.
        """
        # CANONICAL: ResourceMeta.to_dict() outputs "ulid" only
        meta_dict = self.meta.to_dict()
        data: Dict[str, Any] = {
            "meta": meta_dict,
            "step_type_spec": self.step_type_spec,
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
        # Do NOT write structure_ulid (inherits from calculation)
        # Do NOT write parent_calculation_id (parent is implicit)
        # Do NOT write structure selector (legacy field)
        return data


# Mapping from step type to QE calculation parameter
# Most step types map directly, but some like 'bandspw' need translation
STEP_TYPE_TO_CALCULATION = {
    "bandspw": "bands",  # bandspw is our internal name for pw.x bands calculation
}


def generate_qe_input_from_structure(
    structure: PMGStructure | PMGMolecule,
    step_type_gen: str,
    parameter_overrides: Sequence[ParameterOverride] | None = None,
) -> QEInput:
    """
    Build a QE input from a structure plus step metadata.

    Args:
        step_type_gen: Gen step type (e.g., "scf", "nscf", "relax", "md").
                      Will be converted to QE calculation parameter value.
    """

    qe_input = qe_input_from_structure(structure)

    overrides: list[ParameterOverride] = []
    if step_type_gen:
        step_type_lower = step_type_gen.lower()
        # Convert gen step type to QE calculation value (e.g., bandspw -> bands)
        # Note: Do NOT use normalize_step_type_to_gen here as it applies aliases (vc-relax -> relax)
        # which would change the actual QE calculation type
        calculation_value = STEP_TYPE_TO_CALCULATION.get(step_type_lower, step_type_lower)
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
# These are step_type_gen names (not step_type_spec like qe_bands)
POST_PROCESSING_STEP_TYPES = {
    "dos", "bands", "projwfc", "pp", "q2r", "matdyn", "dynmat",
    "sumpdos", "band_interpolation", "ppacf", "pprism",
    "pw2wannier",  # pw2wannier90.x uses INPUTPP namelist (like pp.x)
}


# Import normalize_step_type_to_gen from registry (SSOT for spec→gen conversion)
from quantumvitas.workflow.registry import normalize_step_type_to_gen as _normalize_step_type_to_gen

# Mapping of step type to primary namelist name
STEP_TYPE_NAMELIST_MAP = {
    "dos": "DOS",
    "bands": "BANDS",
    "projwfc": "PROJWFC",
    "pp": "INPUTPP",
    "pw2wannier": "INPUTPP",  # pw2wannier90.x uses INPUTPP namelist
    "q2r": "INPUT",
    "matdyn": "INPUT",
    "dynmat": "INPUT",
}

# Mapping of GEN step type to QE module
# Note: VC (variable-cell) is a PARAMETER for relax/md, NOT a separate step type
STEP_TYPE_MODULE_MAP = {
    "scf": QEModule.PW,
    "nscf": QEModule.PW,
    "relax": QEModule.PW,  # Covers both fixed-cell and VC relaxation
    "md": QEModule.PW,  # Covers both fixed-cell and VC MD
    "bandspw": QEModule.PW,
    "dos": QEModule.DOS,
    "bands": QEModule.BANDS,
    "projwfc": QEModule.PROJWFC,
    "pp": QEModule.PP,
    "pw2wannier": QEModule.PP,  # pw2wannier90.x uses INPUTPP namelist (same as pp.x)
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
    step_type_spec: str,
    calculation_prefix: Optional[str],
    calculation_outdir: str,
    spec_params: Dict[str, Any],
    logger,
) -> None:
    """
    R2-R4: Inject calculation-level prefix/outdir into QE input if schema supports it.
    
    This implements the calculation-level prefix/outdir propagation rule:
    - R1: Canonical prefix = stable id-derived prefix (from calculation.meta.ulid ULID)
    - R2: Only inject if the step's QE module schema defines prefix/outdir parameters
    - R3: Step-level prefix/outdir in spec_params are ignored (overridden by calculation-level)
    - R4: Outdir defaults to "./outdir" if not provided
    
    Args:
        qe_input: QEInput object to modify
        step_type_spec: Spec step type (e.g., "qe_scf", "qe_pw2wannier")
        calculation_prefix: Calculation-level prefix (stable id-derived prefix from calc ULID)
        calculation_outdir: Calculation-level outdir (defaults to "./outdir")
        spec_params: Step spec parameters (to detect ignored step-level prefix/outdir)
        logger: Logger instance for diagnostic messages
    """
    # Determine which QE module this step uses
    step_type_lower = step_type_spec.lower()
    # Convert step_type_spec (e.g., 'qe_scf') to step_type_gen (e.g., 'scf') for lookup
    step_gen_type = _normalize_step_type_to_gen(step_type_lower)
    module = STEP_TYPE_MODULE_MAP.get(step_gen_type)
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
                f"into {target_section}.prefix (step_type_spec={step_type_spec}, module={module.value})"
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
                f"into {target_section}.outdir (step_type_spec={step_type_spec}, module={module.value})"
            )

    # Inject filband for BANDS module: {prefix}.bands.dat → output *.bands.dat.gnu
    # Unlike prefix/outdir (which always override per R3), filband is only a
    # default — if the user already set filband explicitly, we respect that.
    if calculation_prefix and "filband" in param_to_sections:
        filband_sections = param_to_sections["filband"]
        if filband_sections:
            target_section = filband_sections[0]
            namelist = qe_input.get_namelist(target_section)
            existing_filband = namelist.parameters.get("filband") if namelist else None
            if not existing_filband:
                if not namelist:
                    namelist = QENamelist(name=target_section)
                    qe_input.namelists.append(namelist)
                filband_value = f"{calculation_prefix}.bands.dat"
                namelist.parameters["filband"] = filband_value
                logger.info(
                    f"[FILBAND_INJECTION] Injected filband '{filband_value}' "
                    f"into {target_section}.filband"
                )


def _generate_postprocessing_input(
    spec: "StructureStepSpec",
    extra_overrides: Sequence[ParameterOverride] | None = None,
) -> tuple[QEInput, list[ParameterOverride]]:
    """
    Generate QE input for post-processing steps (dos.x, bands.x, projwfc.x, etc.).
    
    These don't need structure-based input, just the appropriate namelist.
    """
    step_type_lower = spec.step_type_spec.lower() if spec.step_type_spec else "dos"
    # Convert step_type_spec (e.g., 'qe_bands') to step_type_gen (e.g., 'bands') for lookup
    step_gen_type = _normalize_step_type_to_gen(step_type_lower)

    # Get the primary namelist name for this step type (using step_type_gen)
    namelist_name = STEP_TYPE_NAMELIST_MAP.get(step_gen_type, step_gen_type.upper())
    module = STEP_TYPE_MODULE_MAP.get(step_gen_type, QEModule.DOS)
    
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
    step_type_lower = spec.step_type_spec.lower() if spec.step_type_spec else "scf"
    # Convert step_type_spec (e.g., 'qe_bands') to step_type_gen (e.g., 'bands') for lookup
    step_gen_type = _normalize_step_type_to_gen(step_type_lower)

    # Handle post-processing step types differently
    if step_gen_type in POST_PROCESSING_STEP_TYPES:
        return _generate_postprocessing_input(spec, extra_overrides)

    spec_overrides = parameter_dict_to_overrides(spec.parameters)
    combined_overrides: list[ParameterOverride] = list(spec_overrides)
    if extra_overrides:
        combined_overrides.extend(extra_overrides)
    qe_input = generate_qe_input_from_structure(
        structure=structure,
        step_type_gen=step_gen_type,  # Use GEN type (e.g., "nscf"), not SPEC type (e.g., "qe_nscf")
        parameter_overrides=combined_overrides,
    )

    # Ensure empty namelists from parameters are preserved (e.g., IONS: {} for relax).
    # parameter_dict_to_overrides drops empty sections since they have no keys,
    # but QE requires the namelist header to be present (e.g., &IONS / for relax).
    from quantumvitas.drivers.qe.io.model import QENamelist
    if spec.parameters and isinstance(spec.parameters, dict):
        for section_name, section_params in spec.parameters.items():
            if isinstance(section_params, dict) and not section_params:
                nl_name = section_name.upper().lstrip("&")
                if qe_input.get_namelist(nl_name) is None:
                    qe_input.namelists.append(QENamelist(name=nl_name))

    # QE requires &IONS for relax/vc-relax and &CELL for vc-relax even if empty.
    # The translator may drop these sections entirely if the corpus input has
    # empty namelists (e.g., &IONS /). Ensure they exist in correct order.
    # QE namelist order: CONTROL → SYSTEM → ELECTRONS → IONS → CELL
    control_nl = qe_input.get_namelist("CONTROL")
    calc_type = None
    if control_nl:
        calc_type = control_nl.parameters.get("calculation", "").strip("'\"")
    if calc_type in ("relax", "vc-relax"):
        if qe_input.get_namelist("IONS") is None:
            qe_input.namelists.append(QENamelist(name="IONS"))
    if calc_type == "vc-relax":
        if qe_input.get_namelist("CELL") is None:
            qe_input.namelists.append(QENamelist(name="CELL"))

    # Enforce QE namelist ordering (CONTROL → SYSTEM → ELECTRONS → IONS → CELL)
    _QE_NL_ORDER = {"CONTROL": 0, "SYSTEM": 1, "ELECTRONS": 2, "IONS": 3, "CELL": 4}
    qe_input.namelists.sort(
        key=lambda nl: _QE_NL_ORDER.get(nl.name.upper(), 99)
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
            from quantumvitas.core.public import resolve_structure
            from quantumvitas.core.public import load_project_config, ProjectConfigError
            try:
                config = load_project_config(proj_root)
                def resolver(selector: str) -> str:
                    resolved = resolve_structure(proj_root, selector, config)
                    return resolved.meta.ulid
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
    step_type_lower = (spec_obj.step_type_spec or "scf").lower()
    # Convert to GEN type for comparison (e.g., "qe_pw2wannier" -> "pw2wannier")
    step_type_gen = _normalize_step_type_to_gen(step_type_lower)
    WANNIER90_STEP_TYPES = {"wannierprep", "wannier", "pw2wannier", "pw2qmcpack"}
    
    # Phase 3C: Check if calculation is PySCF - PySCF steps should NOT go through QE input generation
    # PySCF engine builds input dynamically from structure + parameters
    calculation_engine_family = None
    if calculation_dir and project_root:
        try:
            from quantumvitas.core.public import load_calculation
            from quantumvitas.core.public import make_structure_selector_resolver
            from quantumvitas.core.public import load_project_config
            calc_yaml_path = Path(calculation_dir) / "calculation.yaml"
            if calc_yaml_path.exists():
                project_root_path = Path(project_root).resolve()
                config = load_project_config(project_root_path)
                resolver = make_structure_selector_resolver(project_root_path, config=config)
                calc_model_check = load_calculation(calc_yaml_path, project_root=project_root_path, resolve_structure_selector=resolver)
                calculation_engine_family = calc_model_check.engine_family
        except Exception:
            pass
    
    # Use registry to determine engine for step type
    import quantumvitas.drivers
    from quantumvitas.core.public import DriverRegistry
    
    # Determine engine via registry — no scattered per-engine boolean flags.
    # Only QE steps go through QE input generation; all other registered engines
    # build input dynamically and skip QE materialization.
    resolved_engine = None
    if DriverRegistry.is_step_type_registered(step_type_lower):
        resolved_engine = DriverRegistry.get_engine_for_step_type(step_type_lower)

    # Fallback: use calculation-level engine_family if registry lookup didn't match
    if not resolved_engine and calculation_engine_family:
        resolved_engine = calculation_engine_family

    is_non_qe_engine = resolved_engine is not None and resolved_engine != "qe"

    import logging
    logger = logging.getLogger(__name__)
    
    if step_type_gen in WANNIER90_STEP_TYPES:
        # WANNIER90 PATH: Generate .win or .pw2wan files, skip QE input generation
        logger.info(
            f"[MATERIALIZE_STEP_SPEC] Wannier90 step detected: step_type_gen={step_type_gen}, "
            f"skipping QE input generation and validation"
        )

        # Generate Wannier90 input file based on step type (using GEN type)
        if step_type_gen == "wannierprep" or step_type_gen == "wannier":
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
            # For wannier step (not wannierprep), auto-detect seedname from the prior
            # wannierprep step's .win file. This ensures the wannier step uses the same
            # seedname as wannierprep, so it reads the .amn/.mmn/.eig files produced
            # by pw2wannier under the matching seedname.
            if step_type_gen == "wannier":
                win_files = list(output_dir.glob("*.win"))
                if win_files:
                    detected_seedname = win_files[0].stem
                    w90_input.seedname = detected_seedname
                    logger.info(
                        f"[SEEDNAME_SYNC] Auto-detected seedname '{detected_seedname}' from .win file "
                        f"for wannier step (overriding slug '{spec_obj.meta.slug}')"
                    )
                else:
                    w90_input.seedname = flat_params.get("seedname", spec_obj.meta.slug or "wannier")
            else:
                w90_input.seedname = flat_params.get("seedname", spec_obj.meta.slug or "wannier")
            if "num_wann" in flat_params and flat_params["num_wann"] is not None:
                w90_input.num_wann = int(flat_params["num_wann"])
            if "num_bands" in flat_params and flat_params["num_bands"] is not None:
                w90_input.num_bands = int(flat_params["num_bands"])
            if "num_iter" in flat_params and flat_params["num_iter"] is not None:
                w90_input.num_iter = int(flat_params["num_iter"])
            explicit_mp_grid = False
            if "mp_grid" in flat_params and flat_params["mp_grid"] is not None:
                mp_grid = flat_params["mp_grid"]
                if isinstance(mp_grid, str):
                    tokens = [tok for tok in mp_grid.replace(",", " ").split() if tok]
                    if len(tokens) >= 3:
                        try:
                            mp_grid = [int(tok) for tok in tokens[:3]]
                        except ValueError:
                            mp_grid = None
                if isinstance(mp_grid, (list, tuple)):
                    # Filter out None values and convert to int.
                    normalized = [int(x) for x in mp_grid if x is not None]
                    if len(normalized) >= 3:
                        w90_input.mp_grid = normalized[:3]
                        explicit_mp_grid = True
            
            # CRITICAL: K-points must match NSCF exactly (order and values) for pw2wannier.
            # Priority: 1) YAML-stored kpoints (parsed from corpus, guaranteed to match NSCF)
            #           2) Extract from nscf.in at runtime (if YAML kpoints not available)
            #           3) Generate from mp_grid (last resort, order may differ)
            yaml_kpoints = None
            # Check both original params and flat_params for kpoints.
            # The flattening loop expands dict values via .update(), so
            # params["kpoints"]["points"] becomes flat_params["points"] but
            # flat_params["kpoints"] is lost. Use original params first.
            kp_data = params.get("kpoints") or flat_params.get("kpoints")
            if isinstance(kp_data, dict) and "points" in kp_data:
                points = kp_data["points"]
                if isinstance(points, list) and len(points) > 0:
                    yaml_kpoints = [[float(c) for c in pt] for pt in points]

            if yaml_kpoints:
                w90_input.kpoints = yaml_kpoints
                logger.info(
                    f"[MATERIALIZE_STEP_SPEC] Using {len(yaml_kpoints)} kpoints from YAML params "
                    f"(preserving order for pw2wannier compatibility)"
                )
            else:
                # Fallback: extract from materialized nscf.in
                from quantumvitas.calculation.wannier90_kpoints import (
                    extract_kpoints_from_nscf_step,
                    infer_mp_grid_from_kpoints,
                )
                nscf_kpoints = extract_kpoints_from_nscf_step(
                    calculation_dir=calculation_dir if calculation_dir else Path("."),
                    working_dir=output_dir
                )
                if nscf_kpoints:
                    w90_input.kpoints = nscf_kpoints
                    if not explicit_mp_grid:
                        inferred_mp_grid = infer_mp_grid_from_kpoints(nscf_kpoints)
                        if inferred_mp_grid is not None:
                            w90_input.mp_grid = inferred_mp_grid
                            logger.info(
                                f"[MATERIALIZE_STEP_SPEC] Inferred mp_grid={inferred_mp_grid} "
                                f"from NSCF kpoints ({len(nscf_kpoints)} points)"
                            )
                    logger.info(
                        f"[MATERIALIZE_STEP_SPEC] Extracted {len(nscf_kpoints)} kpoints from nscf step"
                    )
                elif w90_input.mp_grid:
                    logger.warning(
                        f"[MATERIALIZE_STEP_SPEC] No kpoints in YAML or nscf step. "
                        f"Generating from mp_grid={w90_input.mp_grid}, order may not match nscf."
                    )
                    from quantumvitas.io.wannier90_input import generate_kpoints_from_mp_grid
                    w90_input.kpoints = generate_kpoints_from_mp_grid(w90_input.mp_grid)

            # Consistency check: verify count matches mp_grid if both are set
            if w90_input.kpoints and w90_input.mp_grid:
                expected_count = w90_input.mp_grid[0] * w90_input.mp_grid[1] * w90_input.mp_grid[2]
                if len(w90_input.kpoints) != expected_count:
                    logger.warning(
                        f"[MATERIALIZE_STEP_SPEC] Kpoints count mismatch: "
                        f"have {len(w90_input.kpoints)} kpoints, but mp_grid={w90_input.mp_grid} "
                        f"expects {expected_count}. This may cause pw2wannier errors."
                    )
            if "projections" in flat_params and flat_params["projections"] is not None:
                proj_val = flat_params["projections"]
                if isinstance(proj_val, list):
                    w90_input.projections_block = "\n".join(str(p) for p in proj_val)
                else:
                    w90_input.projections_block = str(proj_val)
            if "projections_block" in flat_params and flat_params["projections_block"] is not None:
                proj_block_val = flat_params["projections_block"]
                if isinstance(proj_block_val, list):
                    w90_input.projections_block = "\n".join(str(p) for p in proj_block_val)
                else:
                    w90_input.projections_block = str(proj_block_val)
            
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
        
        elif step_type_gen == "pw2wannier":
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
                    from quantumvitas.core.public import load_calculation
                    from quantumvitas.core.public import make_structure_selector_resolver
                    from quantumvitas.core.public import load_project_config
                    calc_yaml_path = Path(calculation_dir) / "calculation.yaml"
                    if calc_yaml_path.exists():
                        project_root_path = Path(project_root).resolve()
                        config = load_project_config(project_root_path)
                        resolver = make_structure_selector_resolver(project_root_path, config=config)
                        calc_model = load_calculation(calc_yaml_path, project_root=project_root_path, resolve_structure_selector=resolver)
                        # Stable prefix derived from calc ULID; slug changes do not affect it
                        calc_prefix = stable_short_calc_prefix(calc_model.meta.ulid) if calc_model.meta and calc_model.meta.ulid else None
                except Exception:
                    pass
            
            pw2wan_input = Pw2Wannier90Input()
            # Auto-detect seedname from .win file produced by the prior wannierprep step.
            # At materialization time, steps are materialized in order, so the wannierprep
            # .win file already exists but the .nnkp does not (execution hasn't started yet).
            win_files = list(output_dir.glob("*.win"))
            if win_files:
                detected_seedname = win_files[0].stem
                pw2wan_input.seedname = detected_seedname
                logger.info(
                    f"[SEEDNAME_SYNC] Auto-detected seedname '{detected_seedname}' from .win file "
                    f"for pw2wannier (overriding YAML seedname '{flat_params.get('seedname', 'N/A')}')"
                )
            else:
                pw2wan_input.seedname = flat_params.get("seedname", spec_obj.meta.slug or "wannier")
            # R1-R3: Use calculation-level prefix, ignore step-level prefix
            if calc_prefix:
                pw2wan_input.prefix = calc_prefix
                if "prefix" in flat_params and flat_params["prefix"] != calc_prefix:
                    logger.info(
                        f"[PREFIX_INJECTION] Step-level prefix '{flat_params['prefix']}' ignored, "
                        f"using stable id-derived prefix '{calc_prefix}' for pw2wannier"
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
                filename = CalculationFileNaming.input_filename("pw2wannier")
            
            # Ensure filename is not empty or '.' (safety check)
            if not filename or filename == '.' or filename == './':
                raise ValueError(
                    f"Invalid pw2wannier input filename: '{filename}'. "
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
                f"[MATERIALIZE_STEP_SPEC] Generated pw2wannier input file: {generated_input} "
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

        elif step_type_gen == "pw2qmcpack":
            # Generate pw2qmcpack input file (INPUTPP-only, like pw2wannier)
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
                    from quantumvitas.core.public import load_calculation
                    from quantumvitas.core.public import make_structure_selector_resolver
                    from quantumvitas.core.public import load_project_config
                    calc_yaml_path = Path(calculation_dir) / "calculation.yaml"
                    if calc_yaml_path.exists():
                        project_root_path = Path(project_root).resolve()
                        config = load_project_config(project_root_path)
                        resolver = make_structure_selector_resolver(project_root_path, config=config)
                        calc_model = load_calculation(calc_yaml_path, project_root=project_root_path, resolve_structure_selector=resolver)
                        calc_prefix = stable_short_calc_prefix(calc_model.meta.ulid) if calc_model.meta and calc_model.meta.ulid else None
                except Exception:
                    pass

            # Build INPUTPP-only file
            prefix = calc_prefix or flat_params.get("prefix", "pwscf")
            # Always use calc_outdir (same as SCF step), not YAML outdir
            outdir = calc_outdir
            write_psir = flat_params.get("write_psir", False)
            lines = ["&INPUTPP"]
            lines.append(f"   outdir = '{outdir}'")
            lines.append(f"   prefix = '{prefix}'")
            if isinstance(write_psir, bool):
                lines.append(f"   write_psir = .{'true' if write_psir else 'false'}.")
            else:
                lines.append(f"   write_psir = {write_psir}")
            lines.append("/")
            lines.append("")

            from quantumvitas.calculation.naming import CalculationFileNaming
            filename = input_name or CalculationFileNaming.input_filename("pw2qmcpack")
            generated_input = (output_dir / filename).resolve()
            generated_input.parent.mkdir(parents=True, exist_ok=True)
            generated_input.write_text("\n".join(lines))
            logger.info(
                f"[MATERIALIZE_STEP_SPEC] Generated pw2qmcpack input file: {generated_input} "
                f"(prefix={prefix})"
            )

            if calculation_dir:
                calc_dir_path = Path(calculation_dir).resolve()
                try:
                    rel_path = generated_input.relative_to(calc_dir_path)
                    return calc_dir_path / rel_path, spec_obj
                except ValueError:
                    pass

            return generated_input, spec_obj

    # Phase 3C: Non-QE engines — use companion engine's writer to generate input.
    # Dispatched via DriverRegistry (no per-engine boolean flags needed).
    if is_non_qe_engine:
        from quantumvitas.calculation.naming import CalculationFileNaming
        if input_name:
            filename = input_name
        else:
            ext = CalculationFileNaming.input_extension(step_type_lower)
            filename = f"{step_type_lower}{ext}"

        generated_input = Path(output_dir) / filename
        generated_input = generated_input.resolve()
        generated_input.parent.mkdir(parents=True, exist_ok=True)

        # Try to materialize using the companion engine's inputformat writer
        params = spec_obj.parameters or {}
        try:
            from quantumvitas.core.public import DriverRegistry
            driver = DriverRegistry.get_driver(resolved_engine)
            input_spec = driver.get_input_spec(gen_type=step_type_gen)
            if input_spec and input_spec.input_files:
                file_spec = input_spec.input_files[0]
                # Use the inputspec's canonical filename (e.g., "qmc_input.xml")
                # so the engine handler can find it at the expected path.
                if file_spec.filename:
                    canonical_name = file_spec.filename
                    generated_input = Path(output_dir) / canonical_name
                    generated_input = generated_input.resolve()
                if file_spec.custom_writer:
                    # Build the correct fragment based on content_role.
                    # "combined" writers expect {"params": ..., "structure": ...}
                    # "parameters" writers expect the params dict directly.
                    if file_spec.content_role == "combined":
                        struct_dict = {}
                        try:
                            structure = _resolve_structure_for_spec(
                                spec_obj, resolved_spec_path,
                                calculation_dir=calculation_dir,
                                project=project,
                                project_root=project_root,
                            )
                            struct_dict = {
                                "lattice": structure.lattice.matrix.tolist(),
                                "species": [str(site.specie) for site in structure],
                                "frac_coords": structure.frac_coords.tolist(),
                            }
                        except Exception as struct_exc:
                            logger.debug(
                                f"[MATERIALIZE_STEP_SPEC] Could not resolve structure "
                                f"for {resolved_engine}: {struct_exc}"
                            )

                        # QMCPACK uses Bohr internally; pymatgen gives Angstroms.
                        # Convert lattice vectors to Bohr for QMCPACK XML.
                        if resolved_engine == "qmcpack" and struct_dict.get("lattice"):
                            _ANG_TO_BOHR = 1.8897259886
                            struct_dict["lattice"] = [
                                [v * _ANG_TO_BOHR for v in row]
                                for row in struct_dict["lattice"]
                            ]

                        # Fix HDF5 href in preserved wavefunction XML if calc prefix
                        # differs from the original corpus prefix.
                        _fix_qmcpack_hrefs(params, calculation_dir, project_root)

                        # Extract zval from BFD PP files so the writer can set
                        # correct ion group charges for QMCPACK.
                        if resolved_engine == "qmcpack":
                            _inject_species_zval(params, project_root)

                        fragment = {"params": params, "structure": struct_dict}
                        content = file_spec.custom_writer(fragment)
                    else:
                        content = file_spec.custom_writer(params)
                    if content:
                        generated_input.write_text(content)
                        logger.info(
                            f"[MATERIALIZE_STEP_SPEC] Generated companion engine input "
                            f"via {resolved_engine} writer: {generated_input}"
                        )
                        # Stage referenced resources (e.g., BFD pseudopotentials)
                        _stage_companion_resources(
                            params, output_dir, project_root
                        )
                        if calculation_dir:
                            calc_dir_path = Path(calculation_dir).resolve()
                            try:
                                rel_path = generated_input.relative_to(calc_dir_path)
                                return calc_dir_path / rel_path, spec_obj
                            except ValueError:
                                pass
                        return generated_input, spec_obj
        except Exception as exc:
            logger.warning(
                f"[MATERIALIZE_STEP_SPEC] Could not use {resolved_engine} writer: {exc}. "
                f"Falling back to placeholder."
            )

        logger.info(
            f"[MATERIALIZE_STEP_SPEC] Non-QE engine '{resolved_engine}' detected: "
            f"step_type_spec={step_type_lower}, no writer available. "
            f"Engine will build input dynamically from structure + parameters."
        )
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
            from quantumvitas.core.public import load_calculation
            from quantumvitas.core.public import make_structure_selector_resolver, resolve_structure
            from quantumvitas.core.public import load_project_config
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
                calculation_prefix = stable_short_calc_prefix(calc_model.meta.ulid) if calc_model.meta and calc_model.meta.ulid else None
                calculation_context["calculation_path"] = str(calc_yaml_path)
                calculation_context["species_map"] = calc_model.species_map
                calculation_context["prefix"] = calculation_prefix
                if calc_model.structure_ulid:
                    struct_resolved = resolve_structure(project_root_path, calc_model.structure_ulid, config=config)
                    calculation_context["structure_path"] = str(struct_resolved.absolute_path)
        except Exception:
            # If calculation loading fails, continue without calculation context (fallback to QE input parsing)
            pass
    
    logger.info(
        f"[MATERIALIZE_STEP_SPEC] QE step detected: step_type_spec={step_type_lower}, "
        f"using QE input generation and validation"
    )
    
    # Validate species_map for project runs
    # Project runs require calculation.yaml species_map with all required elements
    is_project_run = (calculation_dir and project_root and calc_model is not None)
    
    # Determine if this engine requires pseudopotentials
    # Only QE and VASP require species_map; LAMMPS and other engines don't
    requires_pseudopotentials = False
    if calculation_engine_family:
        requires_pseudopotentials = calculation_engine_family in ("qe", "vasp")
    elif step_type_lower:
        # Fallback: check step_type prefix for engines that require pseudo
        requires_pseudopotentials = step_type_lower.startswith(("qe_", "vasp_"))
    
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
    
    # Only enforce species_map validation for engines that require pseudopotentials
    if is_project_run and requires_pseudopotentials:
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
            from quantumvitas.core.public import is_missing_pseudo_placeholder
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
            step_type_spec=step_type_lower,
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
        from quantumvitas.core.public import ensure_qe_pseudos, get_system_pseudo_dir
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


def _fix_qmcpack_hrefs(
    params: dict,
    calculation_dir: Optional[Path | str],
    project_root: Optional[Path | str],
) -> None:
    """Fix HDF5 href in preserved wavefunction XML to match actual calc prefix.

    When a QMCPACK XML is parsed from the corpus, ``_wavefunction_xml`` may
    contain ``href="lih.pwscf.h5"`` (the original corpus prefix).  At runtime
    pw2qmcpack generates ``<calc_prefix>.pwscf.h5`` using the ULID-based
    prefix.  This function replaces the old href in-place so the written XML
    references the correct file.
    """
    import logging
    _logger = logging.getLogger(__name__)

    wf_xml = params.get("_wavefunction_xml")
    if not wf_xml or ".pwscf.h5" not in wf_xml:
        return  # nothing to fix

    # Compute the actual calc prefix
    calc_prefix = None
    if calculation_dir and project_root:
        try:
            from quantumvitas.core.public import (
                load_calculation,
                load_project_config,
                make_structure_selector_resolver,
            )
            calc_yaml_path = Path(calculation_dir) / "calculation.yaml"
            if calc_yaml_path.exists():
                prp = Path(project_root).resolve()
                config = load_project_config(prp)
                resolver = make_structure_selector_resolver(prp, config=config)
                calc_model = load_calculation(
                    calc_yaml_path, project_root=prp,
                    resolve_structure_selector=resolver,
                )
                if calc_model.meta and calc_model.meta.ulid:
                    calc_prefix = stable_short_calc_prefix(calc_model.meta.ulid)
        except Exception:
            pass

    if not calc_prefix:
        return

    import re
    # pw2qmcpack writes the HDF5 into outdir/ (same as QE scratch).
    # Replace any href="<old_prefix>.pwscf.h5" with the actual path.
    new_wf_xml = re.sub(
        r'href="[^"]*\.pwscf\.h5"',
        f'href="outdir/{calc_prefix}.pwscf.h5"',
        wf_xml,
    )
    if new_wf_xml != wf_xml:
        params["_wavefunction_xml"] = new_wf_xml
        _logger.info(
            f"[MATERIALIZE_STEP_SPEC] Fixed QMCPACK HDF5 href to "
            f"outdir/{calc_prefix}.pwscf.h5"
        )


def _stage_companion_resources(
    params: dict,
    output_dir: Path,
    project_root: Optional[Path | str],
) -> None:
    """Stage referenced resource files (e.g., BFD pseudopotentials) into the
    working directory so the companion engine can find them at runtime.

    Extracts hrefs from ``_resource_refs`` in the params dict and copies
    matching files from the project's ``pseudo/`` directory.
    """
    import logging
    import shutil
    _logger = logging.getLogger(__name__)

    refs = params.get("_resource_refs", {})
    pseudo_hrefs = refs.get("pseudopotential_hrefs", [])
    if not pseudo_hrefs or not project_root:
        return

    prp = Path(project_root).resolve()
    # Search candidate directories for the pseudo files.
    # Include the repo resources/pseudo/ dir (found via the package install path)
    # so that companion-engine pseudos (e.g., BFD XMLs) that are not in the
    # project pseudo/ dir can still be located.
    candidate_dirs = [
        prp / "pseudo",              # project pseudo dir (demo runtime)
        prp / "resources" / "pseudo", # repo resources dir (development)
    ]
    try:
        from quantumvitas.core.public import get_resources_dir
        repo_pseudo = get_resources_dir() / "pseudo"
        if repo_pseudo.is_dir() and repo_pseudo not in candidate_dirs:
            candidate_dirs.append(repo_pseudo)
    except Exception:
        pass
    for href in pseudo_hrefs:
        dst = Path(output_dir) / href
        if dst.exists():
            continue
        for pseudo_dir in candidate_dirs:
            src = pseudo_dir / href
            if src.exists():
                shutil.copy2(src, dst)
                _logger.info(
                    f"[MATERIALIZE_STEP_SPEC] Staged companion resource: "
                    f"{src.name} -> {dst}"
                )
                break


def _inject_species_zval(
    params: dict,
    project_root: Optional[Path | str],
) -> None:
    """Extract zval from BFD PP XML files and inject into params as
    ``_species_zval``.  The QMCPACK writer uses this to set ion group
    charges correctly.
    """
    import logging
    import xml.etree.ElementTree as _ET
    _logger = logging.getLogger(__name__)

    refs = params.get("_resource_refs", {})
    pseudo_hrefs = refs.get("pseudopotential_hrefs", [])
    if not pseudo_hrefs:
        return

    # Build candidate dirs (same as _stage_companion_resources)
    candidate_dirs: list[Path] = []
    if project_root:
        prp = Path(project_root).resolve()
        candidate_dirs.append(prp / "pseudo")
        candidate_dirs.append(prp / "resources" / "pseudo")
    try:
        from quantumvitas.core.public import get_resources_dir
        repo_pseudo = get_resources_dir() / "pseudo"
        if repo_pseudo.is_dir():
            candidate_dirs.append(repo_pseudo)
    except Exception:
        pass

    species_zval: dict[str, float] = {}
    for href in pseudo_hrefs:
        pp_path = None
        for d in candidate_dirs:
            candidate = d / href
            if candidate.exists():
                pp_path = candidate
                break
        if not pp_path:
            continue
        try:
            tree = _ET.parse(pp_path)
            header = tree.find(".//header")
            if header is not None:
                symbol = header.get("symbol", "")
                zval_str = header.get("zval", "")
                if symbol and zval_str:
                    species_zval[symbol] = float(zval_str)
        except Exception:
            pass

    if species_zval:
        params["_species_zval"] = species_zval
        _logger.info(
            f"[MATERIALIZE_STEP_SPEC] Injected species zval from PP: {species_zval}"
        )


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
    
    DAG + ID-only model: Steps inherit structure from calculation.structure_ulid.
    Legacy: Steps may have structure_ulid (for backwards compatibility).
    
    Resolution order (strict):
    1. Step-local structure (legacy support): If spec.structure_ulid or spec.structure is present
    2. Calculation-based structure (preferred): If calculation_dir exists, load calculation.yaml and use calculation.structure_ulid
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
    # logger.debug(f"_resolve_structure_for_spec: project_root={project_root}, calculation_dir={calculation_dir}, spec.structure_ulid={spec.structure_ulid}")
    
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
    if spec.structure_ulid or spec.structure:
        # logger.debug("  Attempting step-local structure resolution")
        if spec.structure_ulid:
            # Try to resolve via project registry first
            if project:
                try:
                    struct_ref = project.get_structure(spec.structure_ulid)
                    # logger.debug(f"  Found structure via project registry: {struct_ref.path}")
                    return read_structure(struct_ref.path)
                except Exception:
                    pass
            
            # Try filesystem search by structure_ulid
            if project_root_path:
                structures_dir = project_root_path / "structures"
                if structures_dir.exists():
                    import json
                    from quantumvitas.io.structure_io import STRUCTURE_META_KEY
                    for struct_file in structures_dir.glob("*.json"):
                        try:
                            struct_data = json.loads(struct_file.read_text())
                            struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                            if struct_meta.get("ulid") == spec.structure_ulid:
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
                from quantumvitas.core.public import load_calculation
                
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
                    # logger.debug(f"  Loaded calculation model: structure_ulid={wf_model.structure_ulid}")
                    
                    structure_to_resolve = wf_model.structure_ulid
                    if not structure_to_resolve and wf_model.structure:
                        # Legacy: calculation has structure path/selector, try to resolve it
                        if project:
                            try:
                                struct_ref = project.get_structure(wf_model.structure)
                                structure_to_resolve = struct_ref.meta.ulid
                            except Exception:
                                structure_to_resolve = wf_model.structure
                    
                    if structure_to_resolve:
                        # Resolve structure from calculation.structure_ulid
                        if project:
                            try:
                                struct_ref = project.get_structure(structure_to_resolve)
                                return read_structure(struct_ref.path)
                            except Exception:
                                pass
                        
                        # Fallback: filesystem search by structure_ulid
                        structures_dir = wf_project_root / "structures"
                        if structures_dir.exists():
                            import json
                            from quantumvitas.io.structure_io import STRUCTURE_META_KEY
                            for struct_file in structures_dir.glob("*.json"):
                                try:
                                    struct_data = json.loads(struct_file.read_text())
                                    struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                                    if struct_meta.get("ulid") == structure_to_resolve:
                                        return read_structure(struct_file)
                                except Exception:
                                    continue
            except Exception:
                pass
    
    # ========================================================================
    # 3. Registry-based resolution (if available)
    # ========================================================================
    # This would use step_ulid → calculation_id → structure_ulid via registry
    # For now, this is handled by calculation-based resolution above
    
    # ========================================================================
    # 4. Last-resort filesystem search (when there is no calculation context or calculation has no structure_ulid)
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
            # If multiple, and we have a calculation structure_ulid, try to match by ID
            if calculation_dir_path:
                try:
                    from quantumvitas.core.public import load_calculation
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
                            if wf_model.structure_ulid:
                                for struct_file in struct_files:
                                    try:
                                        struct_data = json.loads(struct_file.read_text())
                                        struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                                        if struct_meta.get("ulid") == wf_model.structure_ulid:
                                            return read_structure(struct_file)
                                    except Exception:
                                        continue
                except Exception:
                    pass
    
    # ========================================================================
    # All resolution attempts failed
    # ========================================================================
    raise FileNotFoundError(
        f"Step spec at {spec_path} has neither structure_ulid (current: {spec.structure_ulid}) nor structure field (current: {spec.structure}). "
        f"Calculation-based resolution also failed (calculation_dir: {calculation_dir_path}). "
        f"Please ensure the step spec has a valid structure_ulid or structure selector, "
        f"or that a calculation.yaml exists with a valid structure_ulid."
    )
    # First, try legacy structure_ulid from step spec (for backwards compatibility)
    # Note: spec.structure_ulid might be a string, so check it's truthy and non-empty
    if spec.structure_ulid:
        if project is not None:
            # Try to resolve via project registry
            try:
                # Try to find structure by ID in project's structures dict
                struct_ref = None
                for ref in project.structures.values():
                    if ref.meta.ulid == spec.structure_ulid:
                        struct_ref = ref
                        break
                
                if struct_ref is None:
                    # Fall back to get_structure which might resolve by slug/name
                    struct_ref = project.get_structure(spec.structure_ulid)
                
                return read_structure(struct_ref.path)
            except (KeyError, AttributeError) as e:
                # If structure_ulid doesn't resolve via project, fall through to calculation resolution
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
        
        # Try to find structure file by scanning for files with matching meta.ulid
        for root in search_roots:
            if root.exists() and root.is_dir():
                # Look for JSON files in this directory
                for struct_file in root.glob("*.json"):
                    try:
                        struct_data = json.loads(struct_file.read_text())
                        struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                        if struct_meta.get("ulid") == spec.structure_ulid:
                            return read_structure(struct_file)
                    except Exception:
                        continue
        
        # If structure_ulid doesn't resolve and no structure selector, raise error
        if not spec.structure:
            raise FileNotFoundError(
                f"Step spec at {spec_path} has structure_ulid ({spec.structure_ulid}) but structure not found. "
                f"Tried project registry and filesystem search. Project: {project is not None}"
            )
        # Fall through to legacy structure selector
        pass
    
    # DAG + ID-only model: If step doesn't have structure_ulid, resolve from calculation
    if not spec.structure_ulid and calculation_dir:
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
                from quantumvitas.core.public import load_calculation
                calculation_path = Path(calculation_dir)
                if calculation_path.is_dir():
                    calculation_path = calculation_path / "calculation.yaml"
                if calculation_path.exists():
                    wf_model = load_calculation(calculation_path, project.root)
                    # Check both structure_ulid (new) and structure (legacy path selector)
                    structure_to_resolve = wf_model.structure_ulid
                    if not structure_to_resolve and wf_model.structure:
                        # Legacy: calculation has structure path, try to resolve it
                        try:
                            struct_ref = project.get_structure(wf_model.structure)
                            structure_to_resolve = struct_ref.meta.ulid
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
                                            if struct_meta.get("ulid") == structure_to_resolve:
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
                from quantumvitas.core.public import load_calculation
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
                        if wf_model.structure_ulid:
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
                                            if struct_meta.get("ulid") == wf_model.structure_ulid:
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
        # This handles cases where step spec was created without structure_ulid/structure
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
        # First, try to get calculation structure_ulid if available
        calculation_structure_ulid = None
        if calculation_dir and project:
            try:
                from quantumvitas.core.public import load_calculation
                calculation_path = Path(calculation_dir)
                if calculation_path.is_dir():
                    calculation_path = calculation_path / "calculation.yaml"
                if calculation_path.exists():
                    wf_model = load_calculation(calculation_path, project.root)
                    calculation_structure_ulid = wf_model.structure_ulid
            except Exception:
                pass
        
        for root in search_roots:
            if root.exists() and root.is_dir():
                struct_files = list(root.glob("*.json"))
                # If there's only one structure file, use it
                if len(struct_files) == 1:
                    return read_structure(struct_files[0])
                # Otherwise, try to match by ID (from spec or calculation)
                structure_ulid_to_match = spec.structure_ulid or calculation_structure_ulid
                if structure_ulid_to_match:
                    for struct_file in struct_files:
                        try:
                            struct_data = json.loads(struct_file.read_text())
                            struct_meta = struct_data.get(STRUCTURE_META_KEY, {})
                            if struct_meta.get("ulid") == structure_ulid_to_match:
                                return read_structure(struct_file)
                        except Exception:
                            continue
        
        # If still no structure found, raise error
        raise FileNotFoundError(
            f"Step spec at {spec_path} has neither structure_ulid (current: {spec.structure_ulid}) nor structure field (current: {spec.structure}). "
            f"Please ensure the step spec has a valid structure_ulid or structure selector, or that a structure file exists in a structures/ directory."
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
