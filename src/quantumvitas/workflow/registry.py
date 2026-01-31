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
        step_type_spec: Engine-prefixed type (e.g., "qe_scf", "w90_wannier") - used in step.yaml
        step_type_gen: Engine-agnostic type (e.g., "scf", "nscf") - used in APIs/UI
        engine: Engine identifier (e.g., "qe", "w90", "pyscf")
        executable: QE executable name (e.g., "pw.x", "dos.x")
        description: Human-readable description
        requires_structure: Whether step needs structure data
        requires_charge_density: Whether step needs prior SCF charge density
        produces_charge_density: Whether step produces charge density for later steps
        token: Stable short token for subchain basenames (immutable once published)
               e.g., scf→s, td→t, mp2→m2, freq→f, nmr→n
               Used in QC chain basenames: s, s_t, s_m2, s_m2_n
    """
    step_type_spec: str  # SPEC: Engine-prefixed (e.g., "qe_scf")
    step_type_gen: str  # GEN: Engine-agnostic (e.g., "scf")
    engine: str
    executable: str
    description: str
    requires_structure: bool = True
    requires_charge_density: bool = False
    produces_charge_density: bool = False
    supports_incremental_skip: bool = True  # Phase 3C: Whether step can be skipped in incremental runs
    consumes_state: Optional[str] = None  # Phase 3C: State type consumed by this step (e.g., "mf" for MP2)
    produces_state: Optional[str] = None  # Phase 3C: State type produced by this step (e.g., "mf" for SCF)
    is_structure_transform: bool = False  # NEW: True for relax/vc-relax steps that produce structure artifacts
    token: Optional[str] = None  # Stable token for subchain basenames (immutable once published)


# =============================================================================
# Stable Token Mapping (Immutable Contract)
# =============================================================================
# These tokens are used for QC chain subchain basenames.
# IMMUTABLE ONCE PUBLISHED - do not change existing mappings.
# Format: step_type_gen → token
# Subchain basenames: s, s_t, s_m2, s_m2_n (joined by _)

GEN_TYPE_TOKENS: Dict[str, str] = {
    "scf": "s",     # SCF/DFT root
    "hf": "h",      # Hartree-Fock root
    "td": "t",      # TDDFT/TDHF excited states
    "mp2": "m2",    # MP2 correlation
    "freq": "f",    # Frequency/vibrational analysis
    "nmr": "n",     # NMR chemical shifts
}


def get_token_for_gen_type(gen_type: str) -> str:
    """
    Get stable token for a gen step type.

    Args:
        gen_type: Generalized step type (e.g., "scf", "td")

    Returns:
        Stable token for subchain basename (e.g., "s", "t")

    Raises:
        ValueError: If gen_type has no defined token
    """
    token = GEN_TYPE_TOKENS.get(gen_type.lower())
    if token is None:
        raise ValueError(
            f"No stable token defined for gen_type '{gen_type}'. "
            f"Known tokens: {list(GEN_TYPE_TOKENS.keys())}"
        )
    return token


def generate_subchain_basename(gen_types: List[str]) -> str:
    """
    Generate subchain basename from sequence of gen step types.

    Args:
        gen_types: List of gen step types in execution order
                   e.g., ["scf", "mp2"] or ["scf", "td"]

    Returns:
        Subchain basename using stable tokens joined by '_'
        e.g., "s_m2", "s_t", "s_m2_n"

    Raises:
        ValueError: If any gen_type has no defined token
        ValueError: If gen_types is empty

    Examples:
        >>> generate_subchain_basename(["scf"])
        "s"
        >>> generate_subchain_basename(["scf", "td"])
        "s_t"
        >>> generate_subchain_basename(["scf", "mp2"])
        "s_m2"
        >>> generate_subchain_basename(["scf", "mp2", "nmr"])
        "s_m2_n"
    """
    if not gen_types:
        raise ValueError("gen_types cannot be empty")

    tokens = [get_token_for_gen_type(gt) for gt in gen_types]
    return "_".join(tokens)


def get_chain_namespace_folder(scf_root_ulid: str) -> str:
    """
    Get chain namespace folder name from SCF root ULID.

    Chain folders are keyed by the last 6 characters of the SCF root ULID,
    providing a stable, content-addressable namespace.

    Args:
        scf_root_ulid: Full ULID of the SCF root step
                       e.g., "01HY2Q9W8A1234ABCDEF"

    Returns:
        Chain namespace folder name: "scf_<suffix>"
        where suffix is the last 6 characters of the ULID

    Raises:
        ValueError: If ULID is too short (< 6 chars)

    Examples:
        >>> get_chain_namespace_folder("01HY2Q9W8A1234ABCDEF")
        "scf_ABCDEF"
    """
    if len(scf_root_ulid) < 6:
        raise ValueError(
            f"ULID too short: '{scf_root_ulid}' (need at least 6 chars for suffix)"
        )

    suffix = scf_root_ulid[-6:]
    return f"scf_{suffix}"


# =============================================================================
# Step Type Definitions (v0)
# =============================================================================

_STEP_TYPES: Dict[str, StepTypeSpec] = {
    # -------------------------------------------------------------------------
    # QE pw.x step types (self-consistent and variants)
    # -------------------------------------------------------------------------
    "qe_scf": StepTypeSpec(
        step_type_spec="qe_scf",
        step_type_gen="scf",
        engine="qe",
        executable="pw.x",
        description="Self-consistent field calculation (ground state)",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=True,
    ),
    "qe_nscf": StepTypeSpec(
        step_type_spec="qe_nscf",
        step_type_gen="nscf",
        engine="qe",
        executable="pw.x",
        description="Non-self-consistent field calculation (fixed density)",
        requires_structure=True,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_relax": StepTypeSpec(
        step_type_spec="qe_relax",
        step_type_gen="relax",
        engine="qe",
        executable="pw.x",
        description="Structure relaxation (positions and optionally cell)",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,  # CHANGED: Relax doesn't produce reusable electronic state
        is_structure_transform=True,     # NEW: Marks step as structure transform
    ),
    "qe_bandspw": StepTypeSpec(
        step_type_spec="qe_bandspw",
        step_type_gen="bandspw",
        engine="qe",
        executable="pw.x",
        description="Band structure calculation along k-path (pw.x)",
        requires_structure=True,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_md": StepTypeSpec(
        step_type_spec="qe_md",
        step_type_gen="md",
        engine="qe",
        executable="pw.x",
        description="Molecular dynamics (Born-Oppenheimer)",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    "qe_vc_md": StepTypeSpec(
        step_type_spec="qe_vc_md",
        step_type_gen="vc-md",
        engine="qe",
        executable="pw.x",
        description="Variable-cell molecular dynamics",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    
    # -------------------------------------------------------------------------
    # QE post-processing step types (no presets)
    # -------------------------------------------------------------------------
    "qe_dos": StepTypeSpec(
        step_type_spec="qe_dos",
        step_type_gen="dos",
        engine="qe",
        executable="dos.x",
        description="Density of states calculation",
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_bands": StepTypeSpec(
        step_type_spec="qe_bands",
        step_type_gen="bands",
        engine="qe",
        executable="bands.x",
        description="Band structure post-processing",
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_projwfc": StepTypeSpec(
        step_type_spec="qe_projwfc",
        step_type_gen="projwfc",
        engine="qe",
        executable="projwfc.x",
        description="Projected density of states (atomic orbitals)",
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_pp": StepTypeSpec(
        step_type_spec="qe_pp",
        step_type_gen="pp",
        engine="qe",
        executable="pp.x",
        description="Post-processing (charge density, potentials, etc.)",
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    
    # -------------------------------------------------------------------------
    # QE phonon step types (no presets in v0)
    # -------------------------------------------------------------------------
    "qe_ph": StepTypeSpec(
        step_type_spec="qe_ph",
        step_type_gen="ph",
        engine="qe",
        executable="ph.x",
        description="Phonon calculation (DFPT)",
        requires_structure=False,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "qe_q2r": StepTypeSpec(
        step_type_spec="qe_q2r",
        step_type_gen="q2r",
        engine="qe",
        executable="q2r.x",
        description="Interatomic force constants from dynamical matrices",
        requires_structure=False,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    "qe_matdyn": StepTypeSpec(
        step_type_spec="qe_matdyn",
        step_type_gen="matdyn",
        engine="qe",
        executable="matdyn.x",
        description="Phonon frequencies and eigenvectors",
        requires_structure=False,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    "qe_dynmat": StepTypeSpec(
        step_type_spec="qe_dynmat",
        step_type_gen="dynmat",
        engine="qe",
        executable="dynmat.x",
        description="Dynamical matrix analysis",
        requires_structure=False,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    
    # -------------------------------------------------------------------------
    # Wannier90 step types (w90_ prefix for Wannier90 tools)
    # -------------------------------------------------------------------------
    "w90_wannierprep": StepTypeSpec(
        step_type_spec="w90_wannierprep",
        step_type_gen="wannierprep",
        engine="w90",
        executable="wannier90.x",
        description="Wannier90 preprocessing (generate .nnkp)",
        requires_structure=True,
        requires_charge_density=False,  # Needs .win file, not charge density
        produces_charge_density=False,
    ),
    "qe_pw2wannier": StepTypeSpec(
        step_type_spec="qe_pw2wannier",
        step_type_gen="pw2wannier",
        engine="qe",
        executable="pw2wannier90.x",
        description="QE to Wannier90 interface (compute overlaps)",
        requires_structure=False,  # Uses .nnkp + QE save files
        requires_charge_density=True,  # Needs NSCF wavefunctions
        produces_charge_density=False,
    ),
    "w90_wannier": StepTypeSpec(
        step_type_spec="w90_wannier",
        step_type_gen="wannier",
        engine="w90",
        executable="wannier90.x",
        description="Wannier90 MLWF optimization",
        requires_structure=True,
        requires_charge_density=False,  # Needs .mmn/.amn/.eig files
        produces_charge_density=False,
    ),
    
    # -------------------------------------------------------------------------
    # PySCF step types (molecular quantum chemistry)
    # -------------------------------------------------------------------------
    "pyscf_scf": StepTypeSpec(
        step_type_spec="pyscf_scf",
        step_type_gen="scf",  # Public type (shared with qe_scf)
        engine="pyscf",
        executable="python",  # Python-native, no external binary
        description="PySCF single-point calculation (HF/DFT)",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        supports_incremental_skip=True,  # Can be skipped if checkpoint exists
        produces_state="mf",  # Phase 3C: SCF produces mean-field state
        consumes_state=None,  # Phase 3C: SCF has no dependencies
        token="s",  # Stable token for subchain basenames
    ),
    "pyscf_mp2": StepTypeSpec(
        step_type_spec="pyscf_mp2",
        step_type_gen="mp2",  # Public type
        engine="pyscf",
        executable="python",  # Python-native, no external binary
        description="PySCF MP2 correlation energy calculation",
        requires_structure=False,  # Phase 3C: MP2 does NOT require structure; consumes mf from state
        requires_charge_density=False,  # Phase 3C: MP2 does NOT require charge density; consumes mf from state
        produces_charge_density=False,
        supports_incremental_skip=False,  # Always rerun (Phase 3C requirement)
        consumes_state="mf",  # Phase 3C: MP2 consumes mean-field state from SCF
        produces_state="mp2",  # Phase 3C: MP2 produces mp2 state object (in-memory)
        token="m2",  # Stable token for subchain basenames
    ),
    "pyscf_td": StepTypeSpec(
        step_type_spec="pyscf_td",
        step_type_gen="td",
        engine="pyscf",
        executable="python",
        description="PySCF TDDFT / TDHF excited states",
        requires_structure=False,  # Phase 3C: TD does NOT require structure; consumes mf from state
        requires_charge_density=False,  # Phase 3C: TD does NOT require charge density; consumes mf from state
        produces_charge_density=False,
        supports_incremental_skip=False,
        consumes_state="mf",  # Phase 3C: TD consumes mean-field state from SCF
        produces_state=None,  # Phase 3C: TD produces no new persisted state (results to files)
        token="t",  # Stable token for subchain basenames
    ),
    "pyscf_relax": StepTypeSpec(
        step_type_spec="pyscf_relax",
        step_type_gen="relax",
        engine="pyscf",
        executable="python",
        description="PySCF geometry optimization (geomopt)",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        is_structure_transform=True,
    ),

    # -------------------------------------------------------------------------
    # ORCA step types (molecular quantum chemistry - external binary)
    # -------------------------------------------------------------------------
    "orca_scf": StepTypeSpec(
        step_type_spec="orca_scf",
        step_type_gen="scf",
        engine="orca",
        executable="orca",  # External ORCA binary
        description="ORCA DFT/HF single-point calculation",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        supports_incremental_skip=True,  # Via AutoStart from gbw
        produces_state="gbw",  # ORCA produces wavefunction file
        consumes_state=None,  # SCF has no dependencies
        token="s",  # Stable token for subchain basenames
    ),
    "orca_hf": StepTypeSpec(
        step_type_spec="orca_hf",
        step_type_gen="hf",
        engine="orca",
        executable="orca",
        description="ORCA Hartree-Fock calculation",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        supports_incremental_skip=True,
        produces_state="gbw",
        consumes_state=None,
        token="h",  # Stable token for subchain basenames
    ),
    "orca_td": StepTypeSpec(
        step_type_spec="orca_td",
        step_type_gen="td",
        engine="orca",
        executable="orca",
        description="ORCA TDDFT/CIS excited states",
        requires_structure=False,  # Fused into chain with SCF
        requires_charge_density=False,
        produces_charge_density=False,
        supports_incremental_skip=False,  # Always run with chain
        consumes_state="gbw",  # Depends on SCF wavefunction
        produces_state=None,
        token="t",  # Stable token for subchain basenames
    ),
    "orca_relax": StepTypeSpec(
        step_type_spec="orca_relax",
        step_type_gen="relax",
        engine="orca",
        executable="orca",
        description="ORCA geometry optimization",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        is_structure_transform=True,
    ),

    # -------------------------------------------------------------------------
    # VASP step types (Periodic Boundary Conditions - PBC)
    # -------------------------------------------------------------------------
    "vasp_scf": StepTypeSpec(
        step_type_spec="vasp_scf",
        step_type_gen="scf",
        engine="vasp",
        executable="vasp_std",
        description="VASP self-consistent field calculation (ground state)",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=True,
    ),
    "vasp_nscf": StepTypeSpec(
        step_type_spec="vasp_nscf",
        step_type_gen="nscf",
        engine="vasp",
        executable="vasp_std",
        description="VASP non-self-consistent field calculation (fixed density)",
        requires_structure=True,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "vasp_bands": StepTypeSpec(
        step_type_spec="vasp_bands",
        step_type_gen="bands",
        engine="vasp",
        executable="vasp_std",
        description="VASP band structure calculation along k-path",
        requires_structure=True,
        requires_charge_density=True,
        produces_charge_density=False,
    ),
    "vasp_relax": StepTypeSpec(
        step_type_spec="vasp_relax",
        step_type_gen="relax",
        engine="vasp",
        executable="vasp_std",
        description="VASP structure relaxation (positions and optionally cell)",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        is_structure_transform=True,
    ),

    # -------------------------------------------------------------------------
    # LAMMPS step types (Classical Molecular Dynamics)
    # -------------------------------------------------------------------------
    "lammps_relax": StepTypeSpec(
        step_type_spec="lammps_relax",
        step_type_gen="relax",
        engine="lammps",
        executable="lmp",
        description="LAMMPS classical energy minimization (structure relaxation)",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        is_structure_transform=True,  # Produces relaxed structure artifact
    ),
    "lammps_md": StepTypeSpec(
        step_type_spec="lammps_md",
        step_type_gen="md",
        engine="lammps",
        executable="lmp",
        description="LAMMPS molecular dynamics simulation (NVE/NVT/NPT)",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
    ),
    
    # -------------------------------------------------------------------------
    # CP2K step types
    # -------------------------------------------------------------------------
    "cp2k_scf": StepTypeSpec(
        step_type_spec="cp2k_scf",
        step_type_gen="scf",
        engine="cp2k",
        executable="cp2k.ssmp",
        description="CP2K single-point energy/force calculation",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        supports_incremental_skip=True,
        is_structure_transform=False,
    ),
    "cp2k_relax": StepTypeSpec(
        step_type_spec="cp2k_relax",
        step_type_gen="relax",
        engine="cp2k",
        executable="cp2k.ssmp",
        description="CP2K geometry optimization",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        supports_incremental_skip=True,
        is_structure_transform=True,
    ),
    "cp2k_md": StepTypeSpec(
        step_type_spec="cp2k_md",
        step_type_gen="md",
        engine="cp2k",
        executable="cp2k.ssmp",
        description="CP2K molecular dynamics",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        supports_incremental_skip=False,  # CRITICAL: MD skip disabled
        is_structure_transform=False,
    ),

    # -------------------------------------------------------------------------
    # Custom escape hatch
    # -------------------------------------------------------------------------
    "qe_custom": StepTypeSpec(
        step_type_spec="qe_custom",
        step_type_gen="custom",
        engine="qe",
        executable="pw.x",
        description="Custom step type (escape hatch)",
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
        # Build spec -> spec object mapping for fast lookup
        self._spec_to_obj: Dict[str, StepTypeSpec] = {
            spec.step_type_spec: spec for spec in self._types.values()
        }
    
    def get(self, step_type: str) -> Optional[StepTypeSpec]:
        """
        Get specification for a step type.

        Accepts either step_type_gen (e.g., "scf") or step_type_spec (e.g., "qe_scf").
        Returns the StepTypeSpec (with both step_type_gen and step_type_spec fields).

        Args:
            step_type: Step type identifier (case-insensitive)
                Can be step_type_gen ("scf") or step_type_spec ("qe_scf")

        Returns:
            StepTypeSpec or None if not found
        """
        step_type_lower = step_type.lower()
        # Try direct lookup by spec type first
        if step_type_lower in self._spec_to_obj:
            return self._spec_to_obj[step_type_lower]
        
        # Try lookup by gen type
        for spec in self._types.values():
            if spec.step_type_gen.lower() == step_type_lower:
                return spec
        
        return None
    
    def has(self, step_type: str) -> bool:
        """Check if step type exists in registry (supports both public and machine types)."""
        return self.get(step_type) is not None

    def get_for_engine(self, step_type: str, engine: str) -> Optional[StepTypeSpec]:
        """
        Get specification for a step type within a specific engine.

        This is used when creating steps for calculations with a known engine_family.
        For example, get_for_engine("relax", "lammps") returns lammps_relax spec,
        while get_for_engine("relax", "qe") returns qe_relax spec.

        Args:
            step_type: Step type identifier (public or machine type)
            engine: Engine identifier (e.g., "qe", "lammps", "pyscf")

        Returns:
            StepTypeSpec for the engine-specific step type, or None if not found
        """
        step_type_lower = step_type.lower()
        engine_lower = engine.lower()

        # First try direct lookup (if step_type is already spec type like "lammps_relax")
        if step_type_lower in self._spec_to_obj:
            spec = self._spec_to_obj[step_type_lower]
            # Verify it matches the requested engine
            if spec.engine.lower() == engine_lower:
                return spec

        # Search for matching gen type + engine combination
        for spec in self._types.values():
            if spec.engine.lower() == engine_lower:
                if spec.step_type_gen.lower() == step_type_lower:
                    return spec

        # Fallback: return any match if no engine-specific match found
        # This handles cases where engine doesn't have that step type but qe does
        return self.get(step_type)

    def list_all(self) -> List[str]:
        """List all registered step types (returns gen types)."""
        return sorted(set(spec.step_type_gen for spec in self._types.values()))
    
    def list_all_machine(self) -> List[str]:
        """List all registered step types (returns spec types)."""
        return sorted(spec.step_type_spec for spec in self._types.values())
    
    def list_by_engine(self, engine: str) -> List[str]:
        """List step types for a specific engine (returns gen types)."""
        return sorted(
            spec.step_type_gen for spec in self._types.values()
            if spec.engine == engine
        )
    
    def list_by_engine_machine(self, engine: str) -> List[str]:
        """List step types for a specific engine (returns spec types)."""
        return sorted(
            spec.step_type_spec for spec in self._types.values()
            if spec.engine == engine
        )
    
    def list_accepting_presets_for_engine(self, engine_name: str) -> Dict[str, List[str]]:
        """
        List preset dimensions available for each gen step for a given engine.
        
        This implements the new capability contract (Contract C):
        - Engine.supported_presets (engine capability declaration)
        - ParamSpace gen-step applicability (Contract A)
        
        Returns the intersection for each gen step that the engine supports.
        
        Args:
            engine_name: Engine identifier (e.g., "qe", "pyscf", "orca")
            
        Returns:
            Dict mapping gen_step -> sorted list of available dimension names
            Example: {"scf": ["precision", "magnetism"], "nscf": ["precision"]}
            
        Raises:
            KeyError: If engine_name is not found in engine registry
        """
        from quantumvitas.engine.registry import create_default_registry
        from quantumvitas.presets.catalog import list_presets_for_engine
        
        # Get engine instance
        engine_registry = create_default_registry()
        if not engine_registry.has(engine_name):
            raise KeyError(f"Engine '{engine_name}' not found in registry")
        
        engine = engine_registry.get(engine_name)
        
        # Get all gen steps that this engine supports (via machine types)
        engine_gen_steps = set()
        for spec in self._types.values():
            if spec.engine == engine_name:
                engine_gen_steps.add(spec.step_type_gen)
        
        # For each gen step, compute available presets
        result: Dict[str, List[str]] = {}
        for gen_step in sorted(engine_gen_steps):
            available = list_presets_for_engine(engine_name, gen_step)
            if available:  # Only include gen steps that have at least one available preset
                result[gen_step] = available
        
        return result
    
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


# Compatibility aliases for deprecated step types
# These map old step types to the unified "relax" type for workflow purposes.
# NOTE: This aliasing is for workflow/registry lookup only. When generating QE input,
# the actual calculation parameter (vc-relax, relax, etc.) should be preserved.
STEP_TYPE_ALIASES = {
    "vc-relax": "relax",
    "qe_vc_relax": "qe_relax",
    "opt": "relax",
    "geomopt": "relax",
}


def normalize_step_type(step_type: str) -> str:
    """
    Normalize step type, applying compatibility aliases.
    
    Maps deprecated step types (vc-relax, opt, geomopt) to the unified "relax" type.
    Issues a deprecation warning when an alias is used.
    
    Args:
        step_type: Step type (may be deprecated alias)
        
    Returns:
        Normalized step type (e.g., "relax" instead of "vc-relax")
    """
    if not step_type:
        return step_type
    
    if step_type in STEP_TYPE_ALIASES:
        import warnings
        warnings.warn(
            f"Step type '{step_type}' is deprecated. Use 'relax' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return STEP_TYPE_ALIASES[step_type]
    
    return step_type


def normalize_step_type_to_gen(step_type: str) -> str:
    """
    Normalize step_type_spec to step_type_gen.

    Converts spec types (e.g., "qe_scf") to gen types (e.g., "scf").
    If step_type is already a gen type or unknown, returns it unchanged.

    Args:
        step_type: Step type (spec or gen format)

    Returns:
        Gen step type
    """
    if not step_type:
        return step_type

    # First apply compatibility aliases
    step_type = normalize_step_type(step_type)

    registry = get_registry()
    spec = registry.get(step_type)
    if spec:
        return spec.step_type_gen

    # Fallback: strip known engine prefixes (e.g., "qe_vc-relax" -> "vc-relax")
    ENGINE_PREFIXES = ("qe_", "pyscf_", "orca_", "vasp_", "lammps_", "cp2k_", "w90_")
    lower = step_type.lower()
    for prefix in ENGINE_PREFIXES:
        if lower.startswith(prefix):
            return step_type[len(prefix):]

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
        # Read step_type_spec directly from step.yaml
        import yaml
        step_yaml_path = Path(step_yaml_path)  # Path is imported at module level
        if not step_yaml_path.exists():
            raise FileNotFoundError(f"Step YAML file not found: {step_yaml_path}")
        step_data = yaml.safe_load(step_yaml_path.read_text()) or {}
        step_type_str = step_data.get("step_type_spec")
        if not step_type_str:
            raise ValueError(f"Step YAML file missing 'step_type_spec' field: {step_yaml_path}")
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
            known_types = sorted([s.step_type_spec for s in registry._types.values()])[:20]
            known_str = ', '.join(known_types)
        except AttributeError:
            known_str = "unknown"
        raise ValueError(
            f"Unknown machine step_type '{step_type_str}' (not in registry). "
            f"This step type is not supported. Known machine types (sample): {known_str}..."
        )
    
    return spec.engine

