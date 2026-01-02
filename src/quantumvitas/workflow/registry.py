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
from typing import Any, Dict, FrozenSet, List, Optional


@dataclass(frozen=True)
class StepTypeSpec:
    """
    Specification for a step type.
    
    Attributes:
        id: Canonical step_type string (e.g., "scf", "dos")
        engine: Engine identifier (e.g., "qe")
        executable: QE executable name (e.g., "pw.x", "dos.x")
        description: Human-readable description
        accepts_presets: Whether preset dimensions apply to this step
        allowed_dimensions: Which preset dimensions are allowed
        requires_structure: Whether step needs structure data
        requires_charge_density: Whether step needs prior SCF charge density
        produces_charge_density: Whether step produces charge density for later steps
    """
    id: str
    engine: str
    executable: str
    description: str
    accepts_presets: bool = False
    allowed_dimensions: FrozenSet[str] = field(default_factory=frozenset)
    requires_structure: bool = True
    requires_charge_density: bool = False
    produces_charge_density: bool = False


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
    # pw.x step types (self-consistent and variants)
    # -------------------------------------------------------------------------
    "scf": StepTypeSpec(
        id="scf",
        engine="qe",
        executable="pw.x",
        description="Self-consistent field calculation (ground state)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=True,
    ),
    "nscf": StepTypeSpec(
        id="nscf",
        engine="qe",
        executable="pw.x",
        description="Non-self-consistent field calculation (fixed density)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "relax": StepTypeSpec(
        id="relax",
        engine="qe",
        executable="pw.x",
        description="Atomic relaxation (optimize positions, fixed cell)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=True,
    ),
    "vc-relax": StepTypeSpec(
        id="vc-relax",
        engine="qe",
        executable="pw.x",
        description="Variable-cell relaxation (optimize positions and cell)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=True,
    ),
    "bands_pw": StepTypeSpec(
        id="bands_pw",
        engine="qe",
        executable="pw.x",
        description="Band structure calculation along k-path (pw.x)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "md": StepTypeSpec(
        id="md",
        engine="qe",
        executable="pw.x",
        description="Molecular dynamics (Born-Oppenheimer)",
        accepts_presets=True,
        allowed_dimensions=PW_DIMENSIONS,
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    "vc-md": StepTypeSpec(
        id="vc-md",
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
    # Post-processing step types (no presets)
    # -------------------------------------------------------------------------
    "dos": StepTypeSpec(
        id="dos",
        engine="qe",
        executable="dos.x",
        description="Density of states calculation",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "bands": StepTypeSpec(
        id="bands",
        engine="qe",
        executable="bands.x",
        description="Band structure post-processing",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "projwfc": StepTypeSpec(
        id="projwfc",
        engine="qe",
        executable="projwfc.x",
        description="Projected density of states (atomic orbitals)",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "pp": StepTypeSpec(
        id="pp",
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
    # Phonon step types (no presets in v0)
    # -------------------------------------------------------------------------
    "ph": StepTypeSpec(
        id="ph",
        engine="qe",
        executable="ph.x",
        description="Phonon calculation (DFPT)",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "q2r": StepTypeSpec(
        id="q2r",
        engine="qe",
        executable="q2r.x",
        description="Interatomic force constants from dynamical matrices",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    "matdyn": StepTypeSpec(
        id="matdyn",
        engine="qe",
        executable="matdyn.x",
        description="Phonon frequencies and eigenvectors",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=False,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    "dynmat": StepTypeSpec(
        id="dynmat",
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
    # Wannier90 step types
    # -------------------------------------------------------------------------
    "w90_preproc": StepTypeSpec(
        id="w90_preproc",
        engine="qe",
        executable="wannier90.x",
        description="Wannier90 preprocessing (generate .nnkp)",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=True,
        requires_charge_density=False,  # Needs .win file, not charge density
        produces_charge_density=False,
    ),
    "pw2wannier90": StepTypeSpec(
        id="pw2wannier90",
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
        engine="qe",
        executable="wannier90.x",
        description="Wannier90 MLWF optimization",
        accepts_presets=False,
        allowed_dimensions=frozenset(),
        requires_structure=True,
        requires_charge_density=False,  # Needs .mmn/.amn/.eig files
        produces_charge_density=False,
    ),
    
    # -------------------------------------------------------------------------
    # Custom escape hatch
    # -------------------------------------------------------------------------
    "custom": StepTypeSpec(
        id="custom",
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
    - Lookup by step_type id
    - List all step types
    - Filter by engine
    - Get defaults for step type
    """
    
    def __init__(self, step_types: Optional[Dict[str, StepTypeSpec]] = None):
        """
        Initialize registry.
        
        Args:
            step_types: Optional custom step types (for testing)
        """
        self._types = step_types if step_types is not None else _STEP_TYPES.copy()
    
    def get(self, step_type: str) -> Optional[StepTypeSpec]:
        """
        Get specification for a step type.
        
        Args:
            step_type: Step type identifier (case-insensitive)
            
        Returns:
            StepTypeSpec or None if not found
        """
        return self._types.get(step_type.lower())
    
    def has(self, step_type: str) -> bool:
        """Check if step type exists in registry."""
        return step_type.lower() in self._types
    
    def list_all(self) -> List[str]:
        """List all registered step type ids."""
        return sorted(self._types.keys())
    
    def list_by_engine(self, engine: str) -> List[str]:
        """List step types for a specific engine."""
        return sorted(
            spec.id for spec in self._types.values()
            if spec.engine == engine
        )
    
    def list_accepting_presets(self) -> List[str]:
        """List step types that accept presets."""
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

