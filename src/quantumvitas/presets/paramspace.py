"""
ParamSpace: Generic framework for preset compilation and detection.

Per Constitution Chapter 10.7:
- Preset Space = 声明式数据结构 + 通用算法
- Each dimension must declare a ParamSpace with keys, defaults, aliases, profiles, tolerances
- Core logic must reuse generic framework, not per-dimension special cases

This module provides:
- Cell types: VALUE(v), NOT_APPLICABLE, WILDCARD
- ParamSpace dataclass with full matrix profiles
- Generic match_profile() and compile_profile_patch() functions
- YAML accessors with present vs effective_value distinction
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union, Dict
import math


class CellType(str, Enum):
    """Cell type for profile matrix."""
    VALUE = "VALUE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    WILDCARD = "WILDCARD"


@dataclass(frozen=True)
class Cell:
    """
    A cell in the profile matrix.
    
    Each profile must have a cell for each key in the ParamSpace.
    """
    cell_type: CellType
    value: Any = None  # Only used for VALUE type
    
    @classmethod
    def VALUE(cls, v: Any) -> Cell:
        """Create a VALUE cell with value v."""
        return cls(CellType.VALUE, v)
    
    @classmethod
    def NOT_APPLICABLE(cls) -> Cell:
        """Create a NOT_APPLICABLE cell."""
        return cls(CellType.NOT_APPLICABLE)
    
    @classmethod
    def WILDCARD(cls) -> Cell:
        """Create a WILDCARD cell."""
        return cls(CellType.WILDCARD)


@dataclass(frozen=True, eq=True)
class ParamKey:
    """
    Definition of a parameter key in a ParamSpace.
    
    Attributes:
        section: YAML section name (e.g., "SYSTEM", "ELECTRONS", "cards")
        key: Parameter key name (lowercase canonical)
        parser: Function to parse raw YAML value (str -> Any)
        canonicalizer: Function to canonicalize value for comparison (Any -> Any)
        tolerance: Optional absolute tolerance for numeric comparison (float)
        aliases: Optional frozenset of (alias, canonical) tuples for hashability
        default: Optional default value if key is missing
    """
    section: str
    key: str
    parser: Callable[[Any], Any]
    canonicalizer: Callable[[Any], Any]
    tolerance: Optional[float] = None
    aliases: Optional[frozenset[tuple[str, Any]]] = None
    default: Optional[Any] = None
    
    def canonicalize(self, value: Any) -> Any:
        """Canonicalize a value using aliases and canonicalizer."""
        if value is None:
            return None
        
        # Apply aliases first (if value is a string)
        if self.aliases and isinstance(value, str):
            value_lower = value.lower().strip()
            for alias, canonical in self.aliases:
                if alias == value_lower:
                    value = canonical
                    break
        
        # Apply canonicalizer
        return self.canonicalizer(value)
    
    def matches(self, actual: Any, expected: Any) -> bool:
        """Check if actual value matches expected (after canonicalization)."""
        if actual is None or expected is None:
            return actual == expected
        
        canonical_actual = self.canonicalize(actual)
        canonical_expected = self.canonicalize(expected)
        
        # For numeric values with tolerance
        if self.tolerance is not None:
            try:
                actual_float = float(canonical_actual)
                expected_float = float(canonical_expected)
                return abs(actual_float - expected_float) <= self.tolerance
            except (ValueError, TypeError):
                # Fall back to exact match if not numeric
                return canonical_actual == canonical_expected
        
        # Exact match (after canonicalization)
        return canonical_actual == canonical_expected


@dataclass
class ParamSpace:
    """
    ParamSpace declaration for a preset dimension.
    
    Per Constitution 10.7.2:
    - keys: Fixed ordered list of ParamKey definitions
    - defaults: Implicit default values (via ParamKey.default)
    - aliases: Synonym mappings (via ParamKey.aliases)
    - profiles: Full matrix of cells (one per key)
    - tolerances: Numeric comparison tolerances (via ParamKey.tolerance)
    
    Profiles must be a "full matrix" - all keys must have a cell.
    Missing cells are auto-filled with WILDCARD (but discouraged).
    """
    name: str
    keys: list[ParamKey] = field(default_factory=list)
    profiles: dict[str, dict[ParamKey, Cell]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate that profiles form a full matrix."""
        # Auto-fill missing cells with WILDCARD
        for profile_name, profile_cells in self.profiles.items():
            for key in self.keys:
                if key not in profile_cells:
                    profile_cells[key] = Cell.WILDCARD()
        
        # Validate full matrix
        for profile_name, profile_cells in self.profiles.items():
            missing_keys = set(self.keys) - set(profile_cells.keys())
            if missing_keys:
                raise ValueError(
                    f"Profile '{profile_name}' is missing cells for keys: "
                    f"{[k.key for k in missing_keys]}"
                )
            
            # Check for unknown keys
            unknown_keys = set(profile_cells.keys()) - set(self.keys)
            if unknown_keys:
                raise ValueError(
                    f"Profile '{profile_name}' has unknown keys: "
                    f"{[k.key for k in unknown_keys]}"
                )


# ============================================================================
# YAML Accessors (with present vs effective_value)
# ============================================================================

def get_yaml_value(
    yaml_tree: dict[str, dict[str, Any]],
    section: str,
    key: str,
) -> tuple[bool, Any]:
    """
    Get a value from YAML tree with present vs raw_value distinction.
    
    Args:
        yaml_tree: Nested dict structure (section -> key -> value)
        section: Section name (case-insensitive)
        key: Key name (case-insensitive)
        
    Returns:
        Tuple of (present: bool, raw_value: Any)
        - present: True if key exists in YAML, False otherwise
        - raw_value: The actual YAML value if present, None otherwise
    """
    # Case-insensitive section lookup
    section_lower = section.lower()
    section_dict = None
    
    for sec_name, sec_dict in yaml_tree.items():
        if sec_name.lower() == section_lower:
            section_dict = sec_dict
            break
    
    if section_dict is None:
        return (False, None)
    
    # Case-insensitive key lookup
    key_lower = key.lower()
    for k, v in section_dict.items():
        if k.lower() == key_lower:
            return (True, v)
    
    return (False, None)


def compute_effective_value(
    present: bool,
    raw_value: Any,
    default: Optional[Any],
    canonicalizer: Callable[[Any], Any],
) -> Any:
    """
    Compute effective_value from present, raw_value, and default.
    
    Args:
        present: Whether key exists in YAML
        raw_value: Raw YAML value (if present)
        default: Default value (if not present)
        canonicalizer: Function to canonicalize the value
        
    Returns:
        Canonicalized effective value
    """
    if present:
        value = raw_value
    else:
        value = default
    
    if value is None:
        return None
    
    return canonicalizer(value)


# ============================================================================
# Generic Match Logic
# ============================================================================

def match_profile(
    paramspace: ParamSpace,
    yaml_tree: dict[str, dict[str, Any]],
) -> Optional[str]:
    """
    Match a YAML tree against ParamSpace profiles.
    
    Per Constitution 10.7.3 and 10.7.4:
    - VALUE: Compare effective_value with canonicalized expected value
    - NOT_APPLICABLE: Require present == False
    - WILDCARD: Ignore (no checks)
    
    Args:
        paramspace: ParamSpace definition
        yaml_tree: YAML tree to match
        
    Returns:
        Profile name if match found, None otherwise
        
    Raises:
        ValueError: If multiple profiles match (design bug)
    """
    matching_profiles = []
    
    for profile_name, profile_cells in paramspace.profiles.items():
        matches = True
        
        for key in paramspace.keys:
            cell = profile_cells[key]
            
            if cell.cell_type == CellType.WILDCARD:
                # Ignore this key
                continue
            
            # Get present and raw_value from YAML
            present, raw_value = get_yaml_value(yaml_tree, key.section, key.key)
            
            if cell.cell_type == CellType.NOT_APPLICABLE:
                # NOT_APPLICABLE: require present == False
                if present:
                    matches = False
                    break
                # If not present, this key matches
                continue
            
            elif cell.cell_type == CellType.VALUE:
                # VALUE: compare effective_value
                effective_value = compute_effective_value(
                    present, raw_value, key.default, key.canonicalizer
                )
                expected_value = cell.value
                
                if not key.matches(effective_value, expected_value):
                    matches = False
                    break
        
        if matches:
            matching_profiles.append(profile_name)
    
    if len(matching_profiles) > 1:
        raise ValueError(
            f"Multiple profiles match YAML tree: {matching_profiles}. "
            f"This is a design bug - profiles must be mutually exclusive."
        )
    
    if len(matching_profiles) == 1:
        return matching_profiles[0]
    
    return None


# ============================================================================
# Generic Compile Logic
# ============================================================================

def compile_profile_patch(
    paramspace: ParamSpace,
    profile_name: str,
    yaml_tree: dict[str, dict[str, Any]],
    explicit_defaults: bool = True,
) -> tuple[dict[str, dict[str, Any]], set[tuple[str, str]]]:
    """
    Compile a profile to YAML patch and deletions.
    
    Per Constitution 10.7.5:
    - VALUE: Write if explicit_defaults=True or if value != default
    - NOT_APPLICABLE: Always delete
    - WILDCARD: Do nothing
    
    Args:
        paramspace: ParamSpace definition
        profile_name: Profile to compile
        yaml_tree: Current YAML tree (for checking existing values)
        explicit_defaults: If True, always write VALUE cells; if False, skip if value == default
        
    Returns:
        Tuple of (patch_dict, deletions_set)
        - patch_dict: Nested dict to merge into YAML (section -> key -> value)
        - deletions_set: Set of (section, key) tuples to delete
    """
    if profile_name not in paramspace.profiles:
        raise ValueError(f"Unknown profile: {profile_name}")
    
    profile_cells = paramspace.profiles[profile_name]
    patch: dict[str, dict[str, Any]] = {}
    deletions: set[tuple[str, str]] = set()
    
    for key in paramspace.keys:
        cell = profile_cells[key]
        
        if cell.cell_type == CellType.WILDCARD:
            # Do nothing
            continue
        
        elif cell.cell_type == CellType.NOT_APPLICABLE:
            # Always delete
            deletions.add((key.section, key.key))
            continue
        
        elif cell.cell_type == CellType.VALUE:
            # VALUE: write based on explicit_defaults
            value = cell.value
            
            # Check if we should skip writing (if explicit_defaults=False and value == default)
            if not explicit_defaults and key.default is not None:
                canonical_value = key.canonicalize(value)
                canonical_default = key.canonicalize(key.default)
                if canonical_value == canonical_default:
                    # Skip writing (will be missing, using default)
                    continue
            
            # Write the value
            if key.section not in patch:
                patch[key.section] = {}
            patch[key.section][key.key] = value
    
    return (patch, deletions)


# ============================================================================
# Helper Functions for Common Parsers/Canonicalizers
# ============================================================================

def parse_bool(value: Any) -> bool:
    """
    Parse a QE boolean value (handles Fortran .true./.false. strings).
    
    Reuses logic from detector._parse_bool().
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in (".true.", "true", "t", ".t."):
            return True
        if lower in (".false.", "false", "f", ".f."):
            return False
    # Numeric: 0 = False, non-zero = True
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def parse_int(value: Any) -> int:
    """Parse an integer value."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def parse_float(value: Any) -> float:
    """Parse a float value (handles Fortran-style exponents)."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            # Handle Fortran-style exponents (1d-8 -> 1e-8)
            value = value.lower().replace('d', 'e')
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def canonicalize_string(value: Any) -> str:
    """Canonicalize a string value (lowercase, strip quotes)."""
    if value is None:
        return ""
    s = str(value).lower().strip().strip("'\"")
    return s


def canonicalize_bool(value: Any) -> bool:
    """Canonicalize a boolean value."""
    return parse_bool(value)


def canonicalize_int(value: Any) -> int:
    """Canonicalize an integer value."""
    return parse_int(value)


def canonicalize_float(value: Any) -> float:
    """Canonicalize a float value."""
    return parse_float(value)


# ============================================================================
# OccupationsScheme ParamSpace Definition
# ============================================================================

def build_occupations_scheme_paramspace() -> ParamSpace:
    """
    Build the ParamSpace for occupations_scheme dimension.
    
    Keys:
    - SYSTEM.occupations (string, default="fixed")
    - SYSTEM.smearing (string, no default, aliases: "gauss" -> "gaussian")
    - SYSTEM.degauss (float, no default, tolerance=1e-12)
    
    Profiles:
    - FIXED: occupations=VALUE("fixed"), smearing=NOT_APPLICABLE, degauss=NOT_APPLICABLE
    - TETRAHEDRA: occupations=VALUE("tetrahedra"), smearing=NOT_APPLICABLE, degauss=NOT_APPLICABLE
    - SMEARING_GAUSSIAN_0.02: occupations=VALUE("smearing"), smearing=VALUE("gaussian"), degauss=VALUE(0.02)
    """
    # Define keys
    key_occupations = ParamKey(
        section="SYSTEM",
        key="occupations",
        parser=canonicalize_string,
        canonicalizer=canonicalize_string,
        default="fixed",
    )
    
    key_smearing = ParamKey(
        section="SYSTEM",
        key="smearing",
        parser=canonicalize_string,
        canonicalizer=canonicalize_string,
        aliases=frozenset({("gauss", "gaussian")}),  # "gauss" is alias for "gaussian"
        default=None,  # No default - if missing, detection fails for smearing profile
    )
    
    key_degauss = ParamKey(
        section="SYSTEM",
        key="degauss",
        parser=parse_float,
        canonicalizer=canonicalize_float,
        tolerance=1e-12,  # Absolute tolerance for degauss comparison
        default=None,  # No default - if missing, detection fails for smearing profile
    )
    
    keys = [key_occupations, key_smearing, key_degauss]
    
    # Define profiles
    profiles = {
        "FIXED": {
            key_occupations: Cell.VALUE("fixed"),
            key_smearing: Cell.NOT_APPLICABLE(),
            key_degauss: Cell.NOT_APPLICABLE(),
        },
        "TETRAHEDRA": {
            key_occupations: Cell.VALUE("tetrahedra"),
            key_smearing: Cell.NOT_APPLICABLE(),
            key_degauss: Cell.NOT_APPLICABLE(),
        },
        "SMEARING_GAUSSIAN_0.02": {
            key_occupations: Cell.VALUE("smearing"),
            key_smearing: Cell.VALUE("gaussian"),
            key_degauss: Cell.VALUE(0.02),
        },
    }
    
    return ParamSpace(
        name="occupations_scheme",
        keys=keys,
        profiles=profiles,
    )


# Module-level instance (cached)
_OCCUPATIONS_SCHEME_PARAMSPACE: Optional[ParamSpace] = None


def get_occupations_scheme_paramspace() -> ParamSpace:
    """Get the OccupationsScheme ParamSpace (singleton)."""
    global _OCCUPATIONS_SCHEME_PARAMSPACE
    if _OCCUPATIONS_SCHEME_PARAMSPACE is None:
        _OCCUPATIONS_SCHEME_PARAMSPACE = build_occupations_scheme_paramspace()
    return _OCCUPATIONS_SCHEME_PARAMSPACE


# ============================================================================
# Magnetism ParamSpace Definition (merged spin + SOC)
# ============================================================================

def build_magnetism_paramspace() -> ParamSpace:
    """
    Build the ParamSpace for magnetism dimension (merged spin + SOC).
    
    Keys:
    - SYSTEM.nspin (int, default=1)
    - SYSTEM.noncolin (bool, default=False)
    - SYSTEM.lspinorb (bool, default=False)
    
    Profiles:
    - NM (NONMAGNETIC): nspin=VALUE(1), noncolin=VALUE(False), lspinorb=VALUE(False)
    - COL (COLLINEAR_LSDA): nspin=VALUE(2), noncolin=VALUE(False), lspinorb=VALUE(False)
    - NC_CANONICAL (NONCOLLINEAR, apply): nspin=NOT_APPLICABLE, noncolin=VALUE(True), lspinorb=VALUE(False)
    - NC_WITH_NSPIN4 (NONCOLLINEAR, detect tolerance): nspin=VALUE(4), noncolin=VALUE(True), lspinorb=VALUE(False)
    - SOC_CANONICAL (NONCOLLINEAR_SOC, apply): nspin=NOT_APPLICABLE, noncolin=VALUE(True), lspinorb=VALUE(True)
    - SOC_WITH_NSPIN4 (NONCOLLINEAR_SOC, detect tolerance): nspin=VALUE(4), noncolin=VALUE(True), lspinorb=VALUE(True)
    
    Note: NC_CANONICAL and SOC_CANONICAL are used for apply (clean output).
    NC_WITH_NSPIN4 and SOC_WITH_NSPIN4 are detect-only tolerances for common redundant forms.
    """
    key_nspin = ParamKey(
        section="SYSTEM",
        key="nspin",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=1,
    )
    
    key_noncolin = ParamKey(
        section="SYSTEM",
        key="noncolin",
        parser=parse_bool,
        canonicalizer=canonicalize_bool,
        default=False,
    )
    
    key_lspinorb = ParamKey(
        section="SYSTEM",
        key="lspinorb",
        parser=parse_bool,
        canonicalizer=canonicalize_bool,
        default=False,
    )
    
    keys = [key_nspin, key_noncolin, key_lspinorb]
    
    profiles = {
        # NONMAGNETIC
        "NM": {
            key_nspin: Cell.VALUE(1),
            key_noncolin: Cell.VALUE(False),
            key_lspinorb: Cell.VALUE(False),
        },
        # COLLINEAR_LSDA
        "COL": {
            key_nspin: Cell.VALUE(2),
            key_noncolin: Cell.VALUE(False),
            key_lspinorb: Cell.VALUE(False),
        },
        # NONCOLLINEAR (canonical - used for apply)
        "NC_CANONICAL": {
            key_nspin: Cell.NOT_APPLICABLE(),  # Apply will delete nspin
            key_noncolin: Cell.VALUE(True),
            key_lspinorb: Cell.VALUE(False),
        },
        # NONCOLLINEAR (detect tolerance - accepts nspin=4)
        "NC_WITH_NSPIN4": {
            key_nspin: Cell.VALUE(4),
            key_noncolin: Cell.VALUE(True),
            key_lspinorb: Cell.VALUE(False),
        },
        # NONCOLLINEAR_SOC (canonical - used for apply)
        "SOC_CANONICAL": {
            key_nspin: Cell.NOT_APPLICABLE(),  # Apply will delete nspin
            key_noncolin: Cell.VALUE(True),
            key_lspinorb: Cell.VALUE(True),
        },
        # NONCOLLINEAR_SOC (detect tolerance - accepts nspin=4)
        "SOC_WITH_NSPIN4": {
            key_nspin: Cell.VALUE(4),
            key_noncolin: Cell.VALUE(True),
            key_lspinorb: Cell.VALUE(True),
        },
    }
    
    return ParamSpace(
        name="magnetism",
        keys=keys,
        profiles=profiles,
    )


_MAGNETISM_PARAMSPACE: Optional[ParamSpace] = None


def get_magnetism_paramspace() -> ParamSpace:
    """Get the Magnetism ParamSpace (singleton)."""
    global _MAGNETISM_PARAMSPACE
    if _MAGNETISM_PARAMSPACE is None:
        _MAGNETISM_PARAMSPACE = build_magnetism_paramspace()
    return _MAGNETISM_PARAMSPACE


# ============================================================================
# Precision ParamSpace Definition
# ============================================================================

def build_precision_paramspace() -> ParamSpace:
    """
    Build the ParamSpace for precision dimension.
    
    Keys:
    - SYSTEM.ecutwfc (int, no default, exact match)
    - SYSTEM.ecutrho (int, no default, exact match)
    - ELECTRONS.conv_thr (float, no default, tolerance=1e-11)
    - cards.K_POINTS (automatic mesh, no default, exact match)
    
    Note: Precision values are computed from structure + pseudos, so profiles
    are not hardcoded. Instead, matching uses computed canonical values.
    
    Profiles are defined as functions that compute values on demand.
    """
    key_ecutwfc = ParamKey(
        section="SYSTEM",
        key="ecutwfc",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,  # No default - missing => no match
    )
    
    key_ecutrho = ParamKey(
        section="SYSTEM",
        key="ecutrho",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,  # No default - missing => no match
    )
    
    key_conv_thr = ParamKey(
        section="ELECTRONS",
        key="conv_thr",
        parser=parse_float,
        canonicalizer=canonicalize_float,
        tolerance=1e-11,  # From CONV_THR_ABS_TOL
        default=None,  # No default - missing => no match
    )
    
    # K_POINTS is special - it's in cards section
    # We'll handle it separately in matching logic
    key_kpoints = ParamKey(
        section="cards",
        key="K_POINTS",
        parser=lambda x: x,  # Custom parser for K_POINTS card
        canonicalizer=lambda x: x,  # Custom canonicalizer
        default=None,  # No default - missing => no match
    )
    
    keys = [key_ecutwfc, key_ecutrho, key_conv_thr, key_kpoints]
    
    # Profiles are not hardcoded - they're computed from structure + pseudos
    # We define empty profiles here; matching uses computed canonical values
    profiles = {
        "LOW": {},  # Will be filled with computed values during matching
        "MED": {},
        "HIGH": {},
    }
    
    return ParamSpace(
        name="precision",
        keys=keys,
        profiles=profiles,
    )


_PRECISION_PARAMSPACE: Optional[ParamSpace] = None


def get_precision_paramspace() -> ParamSpace:
    """Get the Precision ParamSpace (singleton)."""
    global _PRECISION_PARAMSPACE
    if _PRECISION_PARAMSPACE is None:
        _PRECISION_PARAMSPACE = build_precision_paramspace()
    return _PRECISION_PARAMSPACE


def match_precision_profile(
    yaml_tree: dict[str, dict[str, Any]],
    canonical_values: dict[str, Any],
) -> Optional[str]:
    """
    Match precision YAML against computed canonical values.
    
    This is a special matching function for precision because canonical values
    are computed from structure + pseudos, not hardcoded in profiles.
    
    Args:
        yaml_tree: YAML tree to match
        canonical_values: Dict with computed canonical values:
            - "ecutwfc": int
            - "ecutrho": int
            - "conv_thr": float
            - "kmesh": tuple[int, int, int, int, int, int] (nk1, nk2, nk3, sk1, sk2, sk3)
        
    Returns:
        Profile name ("LOW", "MED", "HIGH") if match, None otherwise
    """
    from quantumvitas.presets.paramspace import get_precision_paramspace
    
    paramspace = get_precision_paramspace()
    
    # Extract actual values from YAML
    ecutwfc_present, ecutwfc_raw = get_yaml_value(yaml_tree, "SYSTEM", "ecutwfc")
    ecutrho_present, ecutrho_raw = get_yaml_value(yaml_tree, "SYSTEM", "ecutrho")
    conv_thr_present, conv_thr_raw = get_yaml_value(yaml_tree, "ELECTRONS", "conv_thr")
    kpoints_present, kpoints_raw = get_yaml_value(yaml_tree, "cards", "K_POINTS")
    
    # All essential params must be present
    if not (ecutwfc_present and ecutrho_present and conv_thr_present and kpoints_present):
        return None
    
    # Parse actual values
    key_ecutwfc = paramspace.keys[0]
    key_ecutrho = paramspace.keys[1]
    key_conv_thr = paramspace.keys[2]
    key_kpoints = paramspace.keys[3]
    
    actual_ecutwfc = key_ecutwfc.parser(ecutwfc_raw)
    actual_ecutrho = key_ecutrho.parser(ecutrho_raw)
    actual_conv_thr = key_conv_thr.parser(conv_thr_raw)
    
    # Parse K_POINTS card
    if not isinstance(kpoints_raw, dict):
        return None
    
    kpoints_option = kpoints_raw.get("option", "").lower()
    if kpoints_option != "automatic":
        return None
    
    kpoints_data = kpoints_raw.get("data", [])
    if not kpoints_data or not isinstance(kpoints_data, list) or len(kpoints_data) == 0:
        return None
    
    mesh_row = kpoints_data[0]
    if not isinstance(mesh_row, (list, tuple)) or len(mesh_row) < 3:
        return None
    
    actual_nk1 = int(mesh_row[0])
    actual_nk2 = int(mesh_row[1])
    actual_nk3 = int(mesh_row[2])
    actual_sk1 = int(mesh_row[3]) if len(mesh_row) > 3 else 0
    actual_sk2 = int(mesh_row[4]) if len(mesh_row) > 4 else 0
    actual_sk3 = int(mesh_row[5]) if len(mesh_row) > 5 else 0
    
    # Compare with canonical values
    canonical_ecutwfc = canonical_values["ecutwfc"]
    canonical_ecutrho = canonical_values["ecutrho"]
    canonical_conv_thr = canonical_values["conv_thr"]
    canonical_kmesh = canonical_values["kmesh"]
    canonical_nk1, canonical_nk2, canonical_nk3, canonical_sk1, canonical_sk2, canonical_sk3 = canonical_kmesh
    
    # Check cutoffs (exact integer match)
    if actual_ecutwfc != canonical_ecutwfc:
        return None
    if actual_ecutrho != canonical_ecutrho:
        return None
    
    # Check conv_thr (with tolerance)
    if not key_conv_thr.matches(actual_conv_thr, canonical_conv_thr):
        return None
    
    # Check k-mesh (exact match)
    if (actual_nk1, actual_nk2, actual_nk3) != (canonical_nk1, canonical_nk2, canonical_nk3):
        return None
    if (actual_sk1, actual_sk2, actual_sk3) != (canonical_sk1, canonical_sk2, canonical_sk3):
        return None
    
    # All checks passed - return the profile name from canonical_values
    return canonical_values.get("profile_name")


# ============================================================================
# Convergence ParamSpace Definition
# ============================================================================

def build_convergence_paramspace() -> ParamSpace:
    """
    Build the ParamSpace for convergence dimension.
    
    Keys:
    - ELECTRONS.mixing_beta (float, no default)
    - ELECTRONS.electron_maxstep (int, no default)
    - ELECTRONS.mixing_mode (string, no default)
    - ELECTRONS.mixing_ndim (int, no default)
    - ELECTRONS.diagonalization (string, no default)
    
    Note: conv_thr is NOT included (belongs to precision dimension).
    
    Profiles:
    - FAST: mixing_beta=0.7, electron_maxstep=100, mixing_mode='plain', mixing_ndim=8, diagonalization='david'
    - NORMAL: mixing_beta=0.4, electron_maxstep=150, mixing_mode='plain', mixing_ndim=8, diagonalization='david'
    - ROBUST: mixing_beta=0.2, electron_maxstep=200, mixing_mode='TF', mixing_ndim=10, diagonalization='rmm-davidson'
    - VERY_ROBUST: mixing_beta=0.1, electron_maxstep=250, mixing_mode='local-TF', mixing_ndim=12, diagonalization='cg'
    """
    key_mixing_beta = ParamKey(
        section="ELECTRONS",
        key="mixing_beta",
        parser=parse_float,
        canonicalizer=canonicalize_float,
        default=None,  # No default - must be set by profile
    )
    
    key_electron_maxstep = ParamKey(
        section="ELECTRONS",
        key="electron_maxstep",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,  # No default - must be set by profile
    )
    
    key_mixing_mode = ParamKey(
        section="ELECTRONS",
        key="mixing_mode",
        parser=canonicalize_string,
        canonicalizer=canonicalize_string,
        default=None,  # No default - must be set by profile
    )
    
    key_mixing_ndim = ParamKey(
        section="ELECTRONS",
        key="mixing_ndim",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,  # No default - must be set by profile
    )
    
    key_diagonalization = ParamKey(
        section="ELECTRONS",
        key="diagonalization",
        parser=canonicalize_string,
        canonicalizer=canonicalize_string,
        default=None,  # No default - must be set by profile
    )
    
    keys = [key_mixing_beta, key_electron_maxstep, key_mixing_mode, key_mixing_ndim, key_diagonalization]
    
    profiles = {
        "FAST": {
            key_mixing_beta: Cell.VALUE(0.7),
            key_electron_maxstep: Cell.VALUE(100),
            key_mixing_mode: Cell.VALUE("plain"),
            key_mixing_ndim: Cell.VALUE(8),
            key_diagonalization: Cell.VALUE("david"),
        },
        "NORMAL": {
            key_mixing_beta: Cell.VALUE(0.4),
            key_electron_maxstep: Cell.VALUE(150),
            key_mixing_mode: Cell.VALUE("plain"),
            key_mixing_ndim: Cell.VALUE(8),
            key_diagonalization: Cell.VALUE("david"),
        },
        "ROBUST": {
            key_mixing_beta: Cell.VALUE(0.2),
            key_electron_maxstep: Cell.VALUE(200),
            key_mixing_mode: Cell.VALUE("TF"),
            key_mixing_ndim: Cell.VALUE(10),
            key_diagonalization: Cell.VALUE("rmm-davidson"),
        },
        "VERY_ROBUST": {
            key_mixing_beta: Cell.VALUE(0.1),
            key_electron_maxstep: Cell.VALUE(250),
            key_mixing_mode: Cell.VALUE("local-TF"),
            key_mixing_ndim: Cell.VALUE(12),
            key_diagonalization: Cell.VALUE("cg"),
        },
    }
    
    return ParamSpace(
        name="convergence",
        keys=keys,
        profiles=profiles,
    )


_CONVERGENCE_PARAMSPACE: Optional[ParamSpace] = None


def get_convergence_paramspace() -> ParamSpace:
    """Get the Convergence ParamSpace (singleton)."""
    global _CONVERGENCE_PARAMSPACE
    if _CONVERGENCE_PARAMSPACE is None:
        _CONVERGENCE_PARAMSPACE = build_convergence_paramspace()
    return _CONVERGENCE_PARAMSPACE

