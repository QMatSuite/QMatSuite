"""
ParamSpace Variants Registry: Declaration-driven preset application.

This is the single source of truth for "where a preset applies".
Each variant explicitly declares which step types it applies to.

Per Constitution: No heuristics, no JSON-driven behavior, only explicit declarations.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from pathlib import Path

from qmatsuite.presets.space_variant import ParamSpaceVariant
from qmatsuite.presets.paramspace import ParamSpace, match_profile, compile_profile_patch
from qmatsuite.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    PrecisionOption,
    ConvergenceOption,
    CUSTOM,
)
from qmatsuite.presets.paramspace import (
    get_occupations_scheme_paramspace,
    get_magnetism_paramspace,
    get_convergence_paramspace,
)
from qmatsuite.presets.precision_variants import (
    build_precision_pw_default_space,
    build_precision_pw_nscf_space,
    build_precision_pw_bandspw_space,
    get_precision_policy,
    PrecisionPolicy,
)
from qmatsuite.presets.qc_precision import get_qc_precision_paramspace


# ============================================================================
# Variant Definitions (Ground Truth)
# ============================================================================

# OccupationsScheme: single variant for all PW steps
OCCUPATIONS_SCHEME_SPACE = get_occupations_scheme_paramspace()
OCCUPATIONS_SCHEME_VARIANT = ParamSpaceVariant(
    name="OCCUPATIONS_SCHEME_PW",
    dimension="occupations_scheme",
    space=OCCUPATIONS_SCHEME_SPACE,
    applies_to_step_types=frozenset({
        "scf", "nscf", "bandspw", "relax", "md",
        # All pw.x step types share the same parameter space.
        # bandspw needs occupations/smearing for consistent Fermi level with SCF.
        # custom excluded: users opting for custom set all parameters manually.
    }),
)

# Magnetism: single variant for all PW steps
MAGNETISM_SPACE = get_magnetism_paramspace()
MAGNETISM_VARIANT = ParamSpaceVariant(
    name="MAGNETISM_PW",
    dimension="magnetism",
    space=MAGNETISM_SPACE,
    applies_to_step_types=frozenset({
        "scf", "nscf", "bandspw", "relax", "md",
        # VC is a parameter, not a separate gen step
    }),
)

# Precision: three variants
PRECISION_PW_DEFAULT_SPACE = build_precision_pw_default_space()
PRECISION_PW_DEFAULT_VARIANT = ParamSpaceVariant(
    name="PRECISION_PW_DEFAULT",
    dimension="precision",
    space=PRECISION_PW_DEFAULT_SPACE,
    applies_to_step_types=frozenset({
        "scf", "relax", "md",
        # VC is a parameter, not a separate gen step
    }),
)

PRECISION_PW_NSCF_SPACE = build_precision_pw_nscf_space()
PRECISION_PW_NSCF_VARIANT = ParamSpaceVariant(
    name="PRECISION_PW_NSCF",
    dimension="precision",
    space=PRECISION_PW_NSCF_SPACE,
    applies_to_step_types=frozenset({"nscf"}),
)

PRECISION_PW_BANDSPW_SPACE = build_precision_pw_bandspw_space()
PRECISION_PW_BANDSPW_VARIANT = ParamSpaceVariant(
    name="PRECISION_PW_BANDSPW",
    dimension="precision",
    space=PRECISION_PW_BANDSPW_SPACE,
    applies_to_step_types=frozenset({"bandspw"}),
)

# Convergence: single variant for all pw-based steps
CONVERGENCE_SPACE = get_convergence_paramspace()
CONVERGENCE_VARIANT = ParamSpaceVariant(
    name="CONVERGENCE_PW",
    dimension="convergence",
    space=CONVERGENCE_SPACE,
    applies_to_step_types=frozenset({
        "scf", "nscf", "relax", "bandspw", "md",
        # VC is a parameter, not a separate gen step
    }),
)

# QC Precision: single variant for QC SCF steps
QC_PRECISION_SPACE = get_qc_precision_paramspace()
QC_PRECISION_VARIANT = ParamSpaceVariant(
    name="QC_PRECISION_SCF",
    dimension="qc_precision",
    space=QC_PRECISION_SPACE,
    applies_to_step_types=frozenset({"scf"}),  # Only applies to gen step "scf"
)

# All variants (authoritative list)
VARIANTS: tuple[ParamSpaceVariant, ...] = (
    OCCUPATIONS_SCHEME_VARIANT,
    MAGNETISM_VARIANT,
    PRECISION_PW_DEFAULT_VARIANT,
    PRECISION_PW_NSCF_VARIANT,
    PRECISION_PW_BANDSPW_VARIANT,
    CONVERGENCE_VARIANT,
    QC_PRECISION_VARIANT,
)


# ============================================================================
# Indexes (Built at Import Time)
# ============================================================================

def _build_indexes() -> Tuple[
    Dict[str, Tuple[ParamSpaceVariant, ...]],
    Dict[Tuple[str, str], ParamSpaceVariant],
]:
    """
    Build indexes for variant lookup.

    Returns:
        Tuple of (variants_by_dimension, variant_by_step_and_dimension)
    """
    variants_by_dimension: Dict[str, list[ParamSpaceVariant]] = {}
    variant_by_step_and_dimension: Dict[Tuple[str, str], ParamSpaceVariant] = {}

    for variant in VARIANTS:
        # Index by dimension
        if variant.dimension not in variants_by_dimension:
            variants_by_dimension[variant.dimension] = []
        variants_by_dimension[variant.dimension].append(variant)

        # Index by (step_type, dimension)
        for step_type in variant.applies_to_step_types:
            key = (step_type, variant.dimension)
            if key in variant_by_step_and_dimension:
                # Overlap detected - fail fast
                existing = variant_by_step_and_dimension[key]
                raise ValueError(
                    f"Overlap detected: Both {existing.name} and {variant.name} "
                    f"apply to step_type={step_type}, dimension={variant.dimension}"
                )
            variant_by_step_and_dimension[key] = variant

    # Convert lists to tuples
    variants_by_dimension_frozen = {
        dim: tuple(variants) for dim, variants in variants_by_dimension.items()
    }

    return variants_by_dimension_frozen, variant_by_step_and_dimension


VARIANTS_BY_DIMENSION: Dict[str, Tuple[ParamSpaceVariant, ...]]
VARIANT_BY_STEP_AND_DIMENSION: Dict[Tuple[str, str], ParamSpaceVariant]

VARIANTS_BY_DIMENSION, VARIANT_BY_STEP_AND_DIMENSION = _build_indexes()


# ============================================================================
# Capability Contract Functions
# ============================================================================

def list_dimensions_for_gen_step(gen_step: str) -> List[str]:
    """
    List all preset dimensions that apply to a given gen/public step type.
    
    This queries ParamSpace variants to determine which dimensions are applicable
    to the specified gen step. This is part of the capability contract (Contract A).
    
    Args:
        gen_step: Gen/public step type (e.g., "scf", "nscf", "td")
        
    Returns:
        Sorted list of dimension names that have variants applying to this gen step
    """
    dimensions = set()
    
    for variant in VARIANTS:
        if gen_step in variant.applies_to_step_types:
            dimensions.add(variant.dimension)
    
    return sorted(dimensions)


# ============================================================================
# Profile <-> Enum Mappings (Centralized)
# ============================================================================

# OccupationsScheme: profile_name -> enum
OCCUPATIONS_SCHEME_PROFILE_TO_ENUM = {
    "FIXED": OccupationsSchemeOption.FIXED,
    "TETRAHEDRA": OccupationsSchemeOption.TETRAHEDRA,
    "SMEARING_GAUSSIAN": OccupationsSchemeOption.SMEARING_GAUSSIAN,
}

OCCUPATIONS_SCHEME_ENUM_TO_PROFILE = {
    OccupationsSchemeOption.FIXED: "FIXED",
    OccupationsSchemeOption.TETRAHEDRA: "TETRAHEDRA",
    OccupationsSchemeOption.SMEARING_GAUSSIAN: "SMEARING_GAUSSIAN",
}

# Magnetism: profile_name -> enum
MAGNETISM_PROFILE_TO_ENUM = {
    "NM": MagnetismOption.NONMAGNETIC,
    "COL": MagnetismOption.COLLINEAR_LSDA,
    "NC_CANONICAL": MagnetismOption.NONCOLLINEAR,
    "NC_WITH_NSPIN4": MagnetismOption.NONCOLLINEAR,
    "SOC_CANONICAL": MagnetismOption.NONCOLLINEAR_SOC,
    "SOC_WITH_NSPIN4": MagnetismOption.NONCOLLINEAR_SOC,
}

MAGNETISM_ENUM_TO_PROFILE = {
    MagnetismOption.NONMAGNETIC: "NM",
    MagnetismOption.COLLINEAR_LSDA: "COL",
    MagnetismOption.NONCOLLINEAR: "NC_CANONICAL",
    MagnetismOption.NONCOLLINEAR_SOC: "SOC_CANONICAL",
}

# Precision: profile_name -> enum
PRECISION_PROFILE_TO_ENUM = {
    "LOW": PrecisionOption.LOW,
    "MED": PrecisionOption.MED,
    "HIGH": PrecisionOption.HIGH,
}

PRECISION_ENUM_TO_PROFILE = {
    PrecisionOption.LOW: "LOW",
    PrecisionOption.MED: "MED",
    PrecisionOption.HIGH: "HIGH",
}

# Convergence: profile_name -> enum
CONVERGENCE_PROFILE_TO_ENUM = {
    "FAST": ConvergenceOption.FAST,
    "NORMAL": ConvergenceOption.NORMAL,
    "ROBUST": ConvergenceOption.ROBUST,
    "VERY_ROBUST": ConvergenceOption.VERY_ROBUST,
}

CONVERGENCE_ENUM_TO_PROFILE = {
    ConvergenceOption.FAST: "FAST",
    ConvergenceOption.NORMAL: "NORMAL",
    ConvergenceOption.ROBUST: "ROBUST",
    ConvergenceOption.VERY_ROBUST: "VERY_ROBUST",
}

# QC Precision: profile_name -> enum (reuses PrecisionOption)
QC_PRECISION_PROFILE_TO_ENUM = {
    "LOW": PrecisionOption.LOW,
    "MED": PrecisionOption.MED,
    "HIGH": PrecisionOption.HIGH,
}

# Combined mappings per dimension
PROFILE_TO_ENUM: Dict[str, Dict[str, Any]] = {
    "occupations_scheme": OCCUPATIONS_SCHEME_PROFILE_TO_ENUM,
    "magnetism": MAGNETISM_PROFILE_TO_ENUM,
    "precision": PRECISION_PROFILE_TO_ENUM,
    "qc_precision": QC_PRECISION_PROFILE_TO_ENUM,
    "convergence": CONVERGENCE_PROFILE_TO_ENUM,
}

# QC Precision: profile_name -> enum (reuses PrecisionOption)
QC_PRECISION_PROFILE_TO_ENUM = {
    "LOW": PrecisionOption.LOW,
    "MED": PrecisionOption.MED,
    "HIGH": PrecisionOption.HIGH,
}

QC_PRECISION_ENUM_TO_PROFILE = {
    PrecisionOption.LOW: "LOW",
    PrecisionOption.MED: "MED",
    PrecisionOption.HIGH: "HIGH",
}

ENUM_TO_PROFILE: Dict[str, Dict[Any, str]] = {
    "occupations_scheme": OCCUPATIONS_SCHEME_ENUM_TO_PROFILE,
    "magnetism": MAGNETISM_ENUM_TO_PROFILE,
    "precision": PRECISION_ENUM_TO_PROFILE,
    "qc_precision": QC_PRECISION_ENUM_TO_PROFILE,
    "convergence": CONVERGENCE_ENUM_TO_PROFILE,
}


# ============================================================================
# Public APIs
# ============================================================================

def get_variant(dimension: str, step_type_gen: str) -> Optional[ParamSpaceVariant]:
    """
    Get the variant that applies to a given dimension and step type.

    Args:
        dimension: Dimension name (e.g., "precision", "magnetism")
        step_type_gen: Gen step type string (e.g., "scf", "bandspw")
                       Can also accept spec type which will be mapped to gen automatically.

    Returns:
        ParamSpaceVariant if one applies, None otherwise
    """
    # STEP TYPE MAPPING: Map step_type_spec to step_type_gen for variant lookup
    # Presets use gen step types (string), not step_type_spec
    # This is the single mapping point - all preset/paramspace lookups go through here
    from qmatsuite.workflow.registry import get_registry
    registry = get_registry()
    spec = registry.get(step_type_gen)
    if spec and spec.step_type_gen:
        # Map step_type_spec to step_type_gen
        actual_gen_type = spec.step_type_gen
    else:
        actual_gen_type = step_type_gen  # Already gen type
    
    key = (actual_gen_type, dimension)
    return VARIANT_BY_STEP_AND_DIMENSION.get(key)


def compile_dimension_patch_for_step(
    dimension: str,
    option_enum: Union[MagnetismOption, OccupationsSchemeOption, PrecisionOption, ConvergenceOption],
    step_type_gen: str,
    step_yaml: Dict[str, Dict[str, Any]],
    *,
    explicit_defaults: bool = True,
    # Precision-specific context
    precision_context: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Dict[str, Any]], set[Tuple[str, str]]]:
    """
    Compile a preset dimension to YAML patch for a specific step type.

    This selects the appropriate variant and compiles using that variant's ParamSpace.

    Args:
        dimension: Dimension name
        option_enum: Enum option value
        step_type: Step type string
        step_yaml: Current step YAML dict
        explicit_defaults: If True, always write VALUE cells
        precision_context: Optional context for precision (lattice, pseudo cutoffs, etc.)

    Returns:
        Tuple of (patch_dict, deletions_set)
        - patch_dict: Nested dict to merge into YAML
        - deletions_set: Set of (section, key) tuples to delete

    Raises:
        ValueError: If dimension/option not supported
    """
    # Get variant
    variant = get_variant(dimension, step_type_gen)
    if variant is None:
        # No variant applies - return empty patch
        return ({}, set())

    # Get profile name
    enum_to_profile = ENUM_TO_PROFILE[dimension]
    if option_enum not in enum_to_profile:
        raise ValueError(f"Unknown option for dimension {dimension}: {option_enum}")

    profile_name = enum_to_profile[option_enum]

    # Special handling for precision (uses resolver)
    if dimension == "precision":
        # Pass step_yaml to context for degauss applicability check
        precision_context = precision_context or {}
        precision_context["step_yaml"] = step_yaml
        return _compile_precision_patch_for_step(
            variant, profile_name, step_type_gen, precision_context
        )

    # Standard ParamSpace compilation
    # ParamSpace operates on IR YAML (IR is SSOT in v0, IR keys == QE keys due to 1:1 mapping)
    # step_yaml is already IR YAML structure (in v0, step.yaml parameters are IR-compatible)
    # Use ParamSpaceContext for key access enforcement (baac796 requirement)
    from qmatsuite.presets.paramspace import ParamSpaceContext
    with ParamSpaceContext(variant.space):
        ir_patch, deletions = compile_profile_patch(
            variant.space, profile_name, step_yaml, explicit_defaults=explicit_defaults
        )

    # Check for engine-specific patches (dual-path materialization)
    # If engine-specific patch exists, return ONLY that (suppress general IR patch)
    engine_specific_patches = {}
    general_ir_patches = {}
    engine_names = set()
    
    for section_name, section_data in ir_patch.items():
        if section_name.startswith("engine."):
            # Extract engine name (e.g., "engine.orca.scf" -> "orca")
            parts = section_name.split(".")
            if len(parts) >= 2:
                engine_name = parts[1]
                engine_names.add(engine_name)
                engine_specific_patches[section_name] = section_data
        else:
            # General IR patch (not engine-specific)
            general_ir_patches[section_name] = section_data
    
    # If multiple engine-specific patches exist, raise hard error
    if len(engine_names) > 1:
        from qmatsuite.presets.compiler import PresetCompilationError
        raise PresetCompilationError(
            f"Multiple engine-specific patches found for dimension '{dimension}', "
            f"profile '{profile_name}', step_type_gen '{step_type_gen}': {sorted(engine_names)}. "
            f"This is not allowed - only one engine-specific patch may apply."
        )
    
    # If engine-specific patch exists, return ONLY that (suppress general IR patch)
    if engine_specific_patches:
        return (engine_specific_patches, deletions)
    
    # Otherwise, return general IR patch (without engine-specific sections)
    return (general_ir_patches, deletions)


def _compile_precision_patch_for_step(
    variant: ParamSpaceVariant,
    profile_name: str,
    step_type_gen: str,
    context: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], set[Tuple[str, str]]]:
    """
    Compile precision patch using resolver.

    Args:
        variant: Precision variant
        profile_name: "LOW", "MED", or "HIGH"
        step_type: Step type
        context: Context dict with:
            - lattice_matrix: 3x3 lattice matrix
            - base_ecutwfc: Base ecutwfc from pseudos
            - base_ecutrho: Base ecutrho from pseudos

    Returns:
        Tuple of (patch_dict, deletions_set)
    """
    from qmatsuite.presets.precision import (
        compute_kmesh,
        round_cutoff_integer,
    )

    # Get policy
    policy = get_precision_policy(profile_name, variant.name)

    # Resolve values
    base_ecutwfc = context.get("base_ecutwfc")
    base_ecutrho = context.get("base_ecutrho")

    if base_ecutwfc is None or base_ecutrho is None:
        from qmatsuite.presets.compiler import PresetCompilationError
        raise PresetCompilationError(
            "Precision compilation requires base_ecutwfc and base_ecutrho in context"
        )

    # Check if variant includes K_POINTS key
    has_kpoints_key = any(
        key.section == "cards" and key.key == "K_POINTS"
        for key in variant.space.keys
    )

    # If variant includes K_POINTS, lattice_matrix is required
    if has_kpoints_key:
        lattice_matrix = context.get("lattice_matrix")
        if lattice_matrix is None:
            from qmatsuite.presets.compiler import PresetCompilationError
            raise PresetCompilationError(
                f"Precision compilation for {step_type_gen} requires lattice_matrix in context "
                f"(variant {variant.name} includes K_POINTS)"
            )

    # Compute cutoffs
    ecutwfc = round_cutoff_integer(base_ecutwfc * policy.cutoff_multiplier)
    ecutrho = round_cutoff_integer(base_ecutrho * policy.cutoff_multiplier)
    conv_thr = policy.conv_thr

    # Build patch for keys in variant
    patch: Dict[str, Dict[str, Any]] = {
        "SYSTEM": {
            "ecutwfc": int(ecutwfc),
            "ecutrho": int(ecutrho),
        },
        "ELECTRONS": {
            "conv_thr": conv_thr,
        },
    }

    # Per ParamSpace Constitution v1 §7: degauss is owned by Precision ParamSpace
    # When user explicitly sets precision preset, write degauss value
    # LOW / MED / HIGH => 0.01 / 0.02 / 0.03
    # But only if degauss is applicable (smearing is active)
    # Per Constitution 10.8.9.1: Must use Oracle to check applicability, not direct YAML read
    from qmatsuite.presets.oracle import Oracle

    step_yaml = context.get("step_yaml", {})
    oracle = Oracle(step_yaml)
    if oracle.degauss_applicability():
        # degauss is applicable - write value based on precision level
        degauss_map = {
            "LOW": 0.01,
            "MED": 0.02,
            "HIGH": 0.03,
        }
        if profile_name in degauss_map:
            patch["SYSTEM"]["degauss"] = degauss_map[profile_name]

    # Add K_POINTS only if variant includes it
    if has_kpoints_key:
        lattice_matrix = context.get("lattice_matrix")
        # Compute kmesh
        base_nk1, base_nk2, base_nk3, sk1, sk2, sk3 = compute_kmesh(
            lattice_matrix, policy.delta_k
        )

        # Apply nscf factor if needed
        if variant.name == "PRECISION_PW_NSCF":
            nk1 = max(1, int(base_nk1 * policy.nscf_factor))
            nk2 = max(1, int(base_nk2 * policy.nscf_factor))
            nk3 = max(1, int(base_nk3 * policy.nscf_factor))
        else:
            nk1, nk2, nk3 = base_nk1, base_nk2, base_nk3

        patch["cards"] = {
            "K_POINTS": {
                "option": "automatic",
                "data": [[nk1, nk2, nk3, sk1, sk2, sk3]],
            }
        }

    # Return IR patch directly (IR is SSOT; QE writer will convert IR to QE input later)
    deletions: set[Tuple[str, str]] = set()

    return (patch, deletions)


def detect_dimension_for_step(
    dimension: str,
    step_type_gen: str,
    step_yaml: Dict[str, Dict[str, Any]],
    *,
    # Precision-specific context
    precision_context: Optional[Dict[str, Any]] = None,
) -> Optional[Union[MagnetismOption, OccupationsSchemeOption, PrecisionOption]]:
    """
    Detect a preset dimension for a specific step type.

    This selects the appropriate variant and detects using that variant's ParamSpace.

    Args:
        dimension: Dimension name
        step_type_gen: Gen step type string (e.g., "scf", "nscf")
        step_yaml: Step YAML dict
        precision_context: Optional context for precision

    Returns:
        Detected enum option, None if no variant applies, or CUSTOM if no match
    """
    # Get variant
    variant = get_variant(dimension, step_type_gen)
    if variant is None:
        # No variant applies - return None (not CUSTOM, dimension is N/A)
        return None

    # Special handling for precision (uses resolver + canonical matching)
    if dimension == "precision":
        return _detect_precision_for_step(
            variant, step_type_gen, step_yaml, precision_context or {}
        )

    # Standard ParamSpace matching (with key-access enforcement from baac796)
    # ParamSpace operates on IR YAML (IR is SSOT in v0, IR keys == QE keys due to 1:1 mapping)
    # step_yaml is already IR YAML structure (in v0, step.yaml parameters are IR-compatible)
    # Use ParamSpaceContext for key access enforcement (baac796 requirement)
    from qmatsuite.presets.paramspace import ParamSpaceContext

    profile_to_enum = PROFILE_TO_ENUM[dimension]
    with ParamSpaceContext(variant.space):
        matched_profile = match_profile(variant.space, step_yaml)

    if matched_profile is None:
        return CUSTOM

    if matched_profile not in profile_to_enum:
        return CUSTOM

    return profile_to_enum[matched_profile]


def _detect_precision_for_step(
    variant: ParamSpaceVariant,
    step_type_gen: str,
    step_yaml: Dict[str, Dict[str, Any]],
    context: Dict[str, Any],
) -> Optional[PrecisionOption]:
    """
    Detect precision using variant-specific matching.

    Args:
        variant: Precision variant
        step_type_gen: Gen step type (e.g., "scf", "nscf")
        step_yaml: Step YAML dict
        context: Context dict with lattice_matrix, base_ecutwfc, base_ecutrho

    Returns:
        PrecisionOption if match, None if context missing, CUSTOM if no match
    """
    from qmatsuite.presets.precision import (
        compute_kmesh,
        round_cutoff_integer,
    )
    from qmatsuite.presets.paramspace import match_precision_profile

    lattice_matrix = context.get("lattice_matrix")
    base_ecutwfc = context.get("base_ecutwfc")
    base_ecutrho = context.get("base_ecutrho")

    if lattice_matrix is None or base_ecutwfc is None or base_ecutrho is None:
        return None  # Context missing - cannot detect

    # Try matching against each precision level
    for level_name in ["LOW", "MED", "HIGH"]:
        policy = get_precision_policy(level_name, variant.name)

        # Compute canonical values
        canonical_ecutwfc = round_cutoff_integer(base_ecutwfc * policy.cutoff_multiplier)
        canonical_ecutrho = round_cutoff_integer(base_ecutrho * policy.cutoff_multiplier)
        canonical_conv_thr = policy.conv_thr

        # Compute kmesh (only if variant includes K_POINTS)
        has_kpoints_key = any(
            key.section == "cards" and key.key == "K_POINTS"
            for key in variant.space.keys
        )

        if has_kpoints_key:
            base_nk1, base_nk2, base_nk3, sk1, sk2, sk3 = compute_kmesh(
                lattice_matrix, policy.delta_k
            )

            # Apply nscf factor if needed
            if variant.name == "PRECISION_PW_NSCF":
                canonical_nk1 = max(1, int(base_nk1 * policy.nscf_factor))
                canonical_nk2 = max(1, int(base_nk2 * policy.nscf_factor))
                canonical_nk3 = max(1, int(base_nk3 * policy.nscf_factor))
            else:
                canonical_nk1, canonical_nk2, canonical_nk3 = base_nk1, base_nk2, base_nk3

            canonical_kmesh = (canonical_nk1, canonical_nk2, canonical_nk3, sk1, sk2, sk3)
        else:
            # bandspw variant - no kmesh
            canonical_kmesh = None

        canonical_values = {
            "ecutwfc": canonical_ecutwfc,
            "ecutrho": canonical_ecutrho,
            "conv_thr": canonical_conv_thr,
            "kmesh": canonical_kmesh,
            "profile_name": level_name,
        }

        # Match (variant-aware) - ParamSpace operates on IR YAML (IR is SSOT in v0)
        # step_yaml is already IR YAML structure (in v0, step.yaml parameters are IR-compatible)
        # Use ParamSpaceContext for key access enforcement (baac796 requirement)
        from qmatsuite.presets.paramspace import ParamSpaceContext
        if has_kpoints_key:
            with ParamSpaceContext(variant.space):
                matched_profile = match_precision_profile(step_yaml, canonical_values)
        else:
            # Match without K_POINTS (bandspw) - need to set context manually
            with ParamSpaceContext(variant.space):
                matched_profile = _match_precision_without_kpoints(step_yaml, canonical_values)

        if matched_profile is not None:
            profile_to_enum = PRECISION_PROFILE_TO_ENUM
            if matched_profile in profile_to_enum:
                return profile_to_enum[matched_profile]

    return CUSTOM


def _warn_if_key_not_in_schema(
    variant: ParamSpaceVariant,
    step_type_gen: str,
    section: str,
    key: str,
) -> None:
    """
    Optional sanity check: warn if a key is not in QE JSON schema for this step_type.

    This is diagnostics-only and does NOT affect behavior.
    JSON schema is NOT used as truth - variants are.
    """
    try:
        from qmatsuite.data.qe_metadata import safe_load_metadata

        metadata = safe_load_metadata()
        if metadata is None:
            return  # No metadata available - skip check

        # Check if key is accepted by step_type
        # This is a simplified check - full implementation would need to map
        # step_type to QE module and check parameter acceptance
        # For now, just log a warning if we can't verify

        # TODO: Implement full schema check when QE metadata API is available
        # For now, this is a placeholder that does nothing

    except Exception:
        # Ignore errors - this is diagnostics only
        pass


def _match_precision_without_kpoints(
    step_yaml: Dict[str, Dict[str, Any]],
    canonical_values: Dict[str, Any],
) -> Optional[str]:
    """
    Match precision profile without requiring K_POINTS (for bandspw variant).

    Only matches on ecutwfc, ecutrho, and conv_thr.

    Note: This function assumes ParamSpaceContext is already set by the caller.
    """
    from qmatsuite.presets.paramspace import get_yaml_value

    # Use bandspw variant's space to get key parsers
    # Get variant directly (avoid circular import)
    paramspace = PRECISION_PW_BANDSPW_VARIANT.space

    # Extract actual values (context should be set by caller)
    ecutwfc_present, ecutwfc_raw = get_yaml_value(step_yaml, "SYSTEM", "ecutwfc")
    ecutrho_present, ecutrho_raw = get_yaml_value(step_yaml, "SYSTEM", "ecutrho")
    conv_thr_present, conv_thr_raw = get_yaml_value(step_yaml, "ELECTRONS", "conv_thr")

    # All essential params (except K_POINTS) must be present
    if not (ecutwfc_present and ecutrho_present and conv_thr_present):
        return None

    # Parse actual values using variant's keys
    key_ecutwfc = paramspace.keys[0]
    key_ecutrho = paramspace.keys[1]
    key_conv_thr = paramspace.keys[2]

    actual_ecutwfc = key_ecutwfc.parser(ecutwfc_raw)
    actual_ecutrho = key_ecutrho.parser(ecutrho_raw)
    actual_conv_thr = key_conv_thr.parser(conv_thr_raw)

    canonical_ecutwfc = canonical_values["ecutwfc"]
    canonical_ecutrho = canonical_values["ecutrho"]
    canonical_conv_thr = canonical_values["conv_thr"]

    # Check cutoffs (exact match)
    if actual_ecutwfc != canonical_ecutwfc:
        return None
    if actual_ecutrho != canonical_ecutrho:
        return None

    # Check conv_thr (with tolerance using key's matches method)
    if not key_conv_thr.matches(actual_conv_thr, canonical_conv_thr):
        return None

    # All checks passed
    return canonical_values.get("profile_name")

