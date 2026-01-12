"""
StepTypeRegistry: Centralized step type semantics.

This module provides a single source of truth for step type knowledge:
- What step types exist
- What engine/executable they use
- What preset dimensions they accept
- What dependencies they have
- Default parameters

Per docs/workflow_refactor_plan.md:
- All step type knowledge should be in registry
- No scattered if/else for step type behavior
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional


@dataclass(frozen=True)
class StepTypeSpec:
    """
    Specification for a step type.
    
    Attributes:
        id: Public/generalized step_type string (e.g., "scf", "nscf") - used in APIs/UI (backward compat)
        machine_type: Machine step_type string (e.g., "qe_scf", "w90_run") - used in step.yaml
        public_type: Public/generalized step_type string (e.g., "scf", "nscf") - alias for id
        engine: Engine identifier (e.g., "qe", "w90", "pyscf")
        executable: QE executable name (e.g., "pw.x", "dos.x")
        description: Human-readable description
        accepts_presets: Whether preset dimensions apply to this step
        allowed_dimensions: Which preset dimensions are allowed
        requires_structure: Whether step needs structure data
        requires_charge_density: Whether step needs prior SCF charge density
        produces_charge_density: Whether step produces charge density for later steps
    """
    id: str  # Public type (for backward compatibility - tests expect this)
    machine_type: str  # Machine type (engine-prefixed, used in step.yaml)
    public_type: str  # Public type (alias for id, for clarity)
    engine: str
    executable: str
    description: str
    accepts_presets: bool = False
    allowed_dimensions: FrozenSet[str] = field(default_factory=frozenset)
    requires_structure: bool = True
    requires_charge_density: bool = False
    produces_charge_density: bool = False
    supports_incremental_skip: bool = True  # Phase 3C: Whether step can be skipped in incremental runs
    consumes_state: Optional[str] = None  # Phase 3C: State type consumed by this step (e.g., "mf" for MP2)
    produces_state: Optional[str] = None  # Phase 3C: State type produced by this step (e.g., "mf" for SCF)


# =============================================================================
# Preset Dimension Constants
# =============================================================================

DIMENSION_MAGNETISM = "magnetism"
DIMENSION_OCCUPATIONS = "occupations_scheme"
DIMENSION_PRECISION = "precision"

# Standard preset dimensions for pw.x-based calculations
PW_DIMENSIONS = frozenset({DIMENSION_MAGNETISM, DIMENSION_OCCUPATIONS, DIMENSION_PRECISION})


# =============================================================================
# Step Type Definitions (v0)
# =============================================================================

_STEP_TYPES: Dict[str, StepTypeSpec] = {
    # -------------------------------------------------------------------------
    # QE pw.x step types (self-consistent and variants)
    # -------------------------------------------------------------------------
    "qe_scf": StepTypeSpec(
        id="scf",  # Public type (for backward compatibility)
        machine_type="qe_scf",  # Machine type (for step.yaml)
        public_type="scf",  # Alias for id
        engine="qe",
        executable="pw.x",
        description="Self-consistent field calculation (ground state)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=True,
    ),
    "qe_nscf": StepTypeSpec(
        id="nscf",
        machine_type="qe_nscf",
        public_type="nscf",
        engine="qe",
        executable="pw.x",
        description="Non-self-consistent field calculation (fixed density)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_relax": StepTypeSpec(
        id="relax",
        machine_type="qe_relax",
        public_type="relax",
        engine="qe",
        executable="pw.x",
        description="Atomic relaxation (optimize positions, fixed cell)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=True,
    ),
    "qe_vc_relax": StepTypeSpec(
        id="vc-relax",
        machine_type="qe_vc_relax",
        public_type="vc-relax",
        engine="qe",
        executable="pw.x",
        description="Variable-cell relaxation (optimize positions and cell)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=True,
    ),
    "qe_bands_pw": StepTypeSpec(
        id="bands_pw",
        machine_type="qe_bands_pw",
        public_type="bands_pw",
        engine="qe",
        executable="pw.x",
        description="Band structure calculation along k-path (pw.x)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_md": StepTypeSpec(
        id="md",
        machine_type="qe_md",
        public_type="md",
        engine="qe",
        executable="pw.x",
        description="Molecular dynamics (Born-Oppenheimer)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    "qe_vc_md": StepTypeSpec(
        id="vc-md",
        machine_type="qe_vc_md",
        public_type="vc-md",
        engine="qe",
        executable="pw.x",
        description="Variable-cell molecular dynamics",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    
    # -------------------------------------------------------------------------
    # QE post-processing step types (no presets)
    # -------------------------------------------------------------------------
    "qe_dos": StepTypeSpec(
        id="dos",
        machine_type="qe_dos",
        public_type="dos",
        engine="qe",
        executable="dos.x",
        description="Density of states calculation",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_bands": StepTypeSpec(
        id="bands",
        machine_type="qe_bands",
        public_type="bands",
        engine="qe",
        executable="bands.x",
        description="Band structure post-processing",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_projwfc": StepTypeSpec(
        id="projwfc",
        machine_type="qe_projwfc",
        public_type="projwfc",
        engine="qe",
        executable="projwfc.x",
        description="Projected density of states (atomic orbitals)",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_pp": StepTypeSpec(
        id="pp",
        machine_type="qe_pp",
        public_type="pp",
        engine="qe",
        executable="pp.x",
        description="Post-processing (charge density, potentials, etc.)",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    
    # -------------------------------------------------------------------------
    # QE phonon step types (no presets in v0)
    # -------------------------------------------------------------------------
    "qe_ph": StepTypeSpec(
        id="ph",
        machine_type="qe_ph",
        public_type="ph",
        engine="qe",
        executable="ph.x",
        description="Phonon calculation (DFPT)",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_q2r": StepTypeSpec(
        id="q2r",
        machine_type="qe_q2r",
        public_type="q2r",
        engine="qe",
        executable="q2r.x",
        description="Interatomic force constants from dynamical matrices",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    "qe_matdyn": StepTypeSpec(
        id="matdyn",
        machine_type="qe_matdyn",
        public_type="matdyn",
        engine="qe",
        executable="matdyn.x",
        description="Phonon frequencies and eigenvectors",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    "qe_dynmat": StepTypeSpec(
        id="dynmat",
        machine_type="qe_dynmat",
        public_type="dynmat",
        engine="qe",
        executable="dynmat.x",
        description="Dynamical matrix analysis",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    
    # -------------------------------------------------------------------------
    # Wannier90 step types (w90_ prefix for Wannier90 tools)
    # -------------------------------------------------------------------------
    "w90_preproc": StepTypeSpec(
        id="w90_preproc",
        machine_type="w90_preproc",
        public_type="w90_preproc",
        engine="qe",  # Legacy: tests expect "qe" for backward compatibility
        executable="wannier90.x",
        description="Wannier90 preprocessing (generate .nnkp)",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=True,
        requires_charge_density=False,  # Needs .win file, not charge density
        produces_charge_density=False,
    ),
    "qe_pw2wannier90": StepTypeSpec(
        id="pw2wannier90",
        machine_type="qe_pw2wannier90",
        public_type="pw2wannier90",
        engine="qe",
        executable="pw2wannier90.x",
        description="QE to Wannier90 interface (compute overlaps)",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,  # Uses .nnkp + QE save files
        requires_charge_density=True,  # Needs NSCF wavefunctions
        produces_charge_density=False,
    ),
    "w90_run": StepTypeSpec(
        id="w90_run",
        machine_type="w90_run",
        public_type="w90_run",
        engine="qe",  # Legacy: tests expect "qe" for backward compatibility
        executable="wannier90.x",
        description="Wannier90 MLWF optimization",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=True,
        requires_charge_density=False,  # Needs .mmn/.amn/.eig files
        produces_charge_density=False,
    ),
    
    # -------------------------------------------------------------------------
    # PySCF step types (molecular quantum chemistry)
    # -------------------------------------------------------------------------
    "pyscf_scf": StepTypeSpec(
        id="scf",  # Public type (shared with qe_scf)
        machine_type="pyscf_scf",
        public_type="scf",
        engine="pyscf",
        executable="python",  # Python-native, no external binary
        description="PySCF single-point calculation (HF/DFT)",
        accepts_presets=False,  # MVP: no presets yet
        allowed_dimensions=frozenset(),
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        supports_incremental_skip=True,  # Can be skipped if checkpoint exists
        produces_state="mf",  # Phase 3C: SCF produces mean-field state
        consumes_state=None,  # Phase 3C: SCF has no dependencies
    ),
    "pyscf_mp2": StepTypeSpec(
        id="mp2",  # Public type
        machine_type="pyscf_mp2",
        public_type="mp2",
        engine="pyscf",
        executable="python",  # Python-native, no external binary
        description="PySCF MP2 correlation energy calculation",
        accepts_presets=False,  # MVP: no presets yet
        allowed_dimensions=frozenset(),
        requires_structure=False,  # Phase 3C: MP2 does NOT require structure; consumes mf from state
        requires_charge_density=False,  # Phase 3C: MP2 does NOT require charge density; consumes mf from state
        produces_charge_density=False,
        supports_incremental_skip=False,  # Always rerun (Phase 3C requirement)
        consumes_state="mf",  # Phase 3C: MP2 consumes mean-field state from SCF
        produces_state="mp2",  # Phase 3C: MP2 produces mp2 state object (in-memory)
    ),
    "pyscf_td": StepTypeSpec(
        id="td",
        machine_type="pyscf_td",
        public_type="td",
        engine="pyscf",
        executable="python",
        description="PySCF TDDFT / TDHF excited states",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,  # Phase 3C: TD does NOT require structure; consumes mf from state
        requires_charge_density=False,  # Phase 3C: TD does NOT require charge density; consumes mf from state
        produces_charge_density=False,
        supports_incremental_skip=False,
        consumes_state="mf",  # Phase 3C: TD consumes mean-field state from SCF
        produces_state=None,  # Phase 3C: TD produces no new persisted state (results to files)
    ),
    
    # -------------------------------------------------------------------------
    # Custom escape hatch
    # -------------------------------------------------------------------------
    "qe_custom": StepTypeSpec(
        id="custom",
        machine_type="qe_custom",
        public_type="custom",
        engine="qe",
        executable="pw.x",
        description="Custom step type (escape hatch)",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
}


# =============================================================================
# StepTypeRegistry
# =============================================================================


class StepTypeRegistry:
    """
    Registry of step type specifications.
    
    Provides:
    - Lookup by step_type id (public or machine type)
    - List all step types (returns public types by default)
    - Filter by engine (returns public types by default)
    - Get defaults for step type
    """
    
    def __init__(self, step_types: Optional[Dict[str, StepTypeSpec]] = None):
        """
        Initialize registry.
        
        Args:
            step_types: Optional custom step types (for testing)
        """
        self._types = step_types if step_types is not None else _STEP_TYPES.copy()
        # Build public_type -> machine_type mapping for fast lookup
        self._public_to_machine: Dict[str, str] = {
            spec.public_type: spec.machine_type for spec in self._types.values()
        }
        # Also build machine_type -> spec mapping
        self._machine_to_spec: Dict[str, StepTypeSpec] = {
            spec.machine_type: spec for spec in self._types.values()
        }
    
    def get(self, step_type: str) -> Optional[StepTypeSpec]:
        """
        Get specification for a step type.
        
        Accepts either public_type (e.g., "scf") or machine_type (e.g., "qe_scf").
        Returns the StepTypeSpec (with both public_type and id fields).
        
        Args:
            step_type: Step type identifier (case-insensitive)
                Can be public_type ("scf") or machine_type ("qe_scf")
            
        Returns:
            StepTypeSpec or None if not found
        """
        step_type_lower = step_type.lower()
        # Try direct lookup by machine type first
        if step_type_lower in self._machine_to_spec:
            return self._machine_to_spec[step_type_lower]
        
        # Try lookup by public type (id field)
        for spec in self._types.values():
            if spec.id.lower() == step_type_lower or spec.public_type.lower() == step_type_lower:
                return spec
        
        return None
    
    def has(self, step_type: str) -> bool:
        """Check if step type exists in registry (supports both public and machine types)."""
        return self.get(step_type) is not None
    
    def list_all(self) -> List[str]:
        """List all registered step types (returns public types)."""
        return sorted(set(spec.id for spec in self._types.values()))
    
    def list_all_machine(self) -> List[str]:
        """List all registered step types (returns machine types)."""
        return sorted(spec.machine_type for spec in self._types.values())
    
    def list_by_engine(self, engine: str) -> List[str]:
        """List step types for a specific engine (returns public types)."""
        return sorted(
            spec.id for spec in self._types.values()
            if spec.engine == engine
        )
    
    def list_by_engine_machine(self, engine: str) -> List[str]:
        """List step types for a specific engine (returns machine types)."""
        return sorted(
            spec.machine_type for spec in self._types.values()
            if spec.engine == engine
        )
    
    def list_accepting_presets(self) -> List[str]:
        """List step types that accept presets (returns public types)."""
        return sorted(
            spec.id for spec in self._types.values()
            if spec.accepts_presets
        )
    
    def get_defaults(self, step_type: str) -> Dict[str, Any]:
        """
        Get default parameters for a step type.
        
        Merges from step_defaults.py.
        
        Returns:
            Dict with "parameters", "cards", "species_overrides" keys
        """
        from quantumvitas.calculation.step_defaults import get_default_step_params
        
        return get_default_step_params(step_type)
    
    def validate_step_type(
        self,
        step_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Validate step type and parameters.
        
        Returns:
            List of validation issues (empty if valid)
        """
        issues: List[str] = []
        
        spec = self.get(step_type)
        if spec is None:
            issues.append(f"Unknown step type: {step_type}")
            return issues
        
        # Basic validation can be extended later
        # For now, just check step_type exists
        
        return issues


# =============================================================================
# Global Registry Instance
# =============================================================================

_registry: Optional[StepTypeRegistry] = None


def get_registry() -> StepTypeRegistry:
    """Get the global step type registry."""
    global _registry
    if _registry is None:
        _registry = StepTypeRegistry()
    return _registry


def reset_registry() -> None:
    """Reset global registry (for testing)."""
    global _registry
    _registry = None


def normalize_step_type_to_public(step_type: str) -> str:
    """
    Normalize step_type to public (legacy) format for backward compatibility.
    
    Converts machine types (e.g., "qe_scf") to public types (e.g., "scf").
    If step_type is already a public type or unknown, returns it unchanged.
    
    Args:
        step_type: Step type (machine or public format)
        
    Returns:
        Public step type (legacy format)
    """
    if not step_type:
        return step_type
    
    registry = get_registry()
    spec = registry.get(step_type)
    if spec:
        return spec.public_type
    return step_type


def resolve_engine_for_step(
    step_yaml_path: Optional[Path] = None,
    machine_step_type: Optional[str] = None,
) -> str:
    """
    Resolve engine ID from step.yaml machine step_type.
    
    This is the canonical execution-time engine resolver. It reads the machine step_type
    from step.yaml (or receives it directly) and looks up the engine in the registry.
    
    Contract (CLARIFIED):
    - engine_family is NOT consulted (it's only for materialization-time)
    - Machine step_type from step.yaml is the SSOT for execution routing
    - Unknown machine step types MUST raise (no "custom" fallback)
    - calculation.yaml is consulted ONLY for structure resolution, NOT for engine routing
    
    Args:
        step_yaml_path: Path to step.yaml file (reads machine step_type from it directly)
        machine_step_type: Direct machine step_type string (e.g., "pyscf_scf", "qe_scf")
        
    Returns:
        Engine ID (e.g., "qe", "pyscf", "w90")
        
    Raises:
        ValueError: If machine step_type is unknown (not in registry)
        ValueError: If neither step_yaml_path nor machine_step_type is provided
        FileNotFoundError: If step_yaml_path is provided but file doesn't exist
    """
    registry = get_registry()
    
    # Determine machine step_type from input
    if machine_step_type:
        step_type_str = machine_step_type
    elif step_yaml_path:
        # Read machine step_type directly from step.yaml (step.yaml stores machine type, not public type)
        import yaml
        step_yaml_path = Path(step_yaml_path)  # Path is imported at module level
        if not step_yaml_path.exists():
            raise FileNotFoundError(f"Step YAML file not found: {step_yaml_path}")
        step_data = yaml.safe_load(step_yaml_path.read_text()) or {}
        step_type_str = step_data.get("step_type")
        if not step_type_str:
            raise ValueError(f"Step YAML file missing 'step_type' field: {step_yaml_path}")
    else:
        raise ValueError("Must provide one of: step_yaml_path or machine_step_type")
    
    if not step_type_str:
        raise ValueError("Machine step_type is empty or None")
    
    # Look up machine step_type in registry (registry.get() accepts machine type directly)
    spec = registry.get(step_type_str)
    if spec is None:
        # List some known types for error message (limit to avoid huge error messages)
        # Access internal _types dict directly (registry implementation detail)
        try:
            known_types = sorted([s.machine_type for s in registry._types.values()])[:20]
            known_str = ', '.join(known_types)
        except AttributeError:
            known_str = "unknown"
        raise ValueError(
            f"Unknown machine step_type '{step_type_str}' (not in registry). "
            f"This step type is not supported. Known machine types (sample): {known_str}..."
        )
    
    return spec.engine

