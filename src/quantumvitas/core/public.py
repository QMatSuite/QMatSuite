# SSOT
from quantumvitas.core.yaml_io import load_yaml_doc, save_yaml_doc, load_yaml_meta_subtree
from quantumvitas.core.yamldoc import YamlDoc, StepDoc, CalcDoc, ProjectDoc
from quantumvitas.core.locking import calc_edit_lock, calc_run_lock
# Resources
from quantumvitas.core.resolution import (
    require_calculation, require_step, require_structure,
    resolve_structure, resolve_calculation, resolve_step,
    list_calculations, list_structures, build_resource_index,
    ResourceIndex, ResourceNotFoundError,
    AmbiguousSelectorError, SelectorNotFoundError,
    make_structure_selector_resolver,
)
from quantumvitas.core.resources import (
    ResourceMeta, generate_resource_id, meta_from_name, slugify,
    ensure_relative_path, generate_unique_name_and_slug,
)
# Project Utils
from quantumvitas.core.project_utils import (
    load_project_config, save_project_config,
    find_project_root, require_project_root,
    ProjectConfigError,
)
# Models
from quantumvitas.core.models import (
    load_calculation, save_calculation,
    CalculationModel, CalculationStepEntry,
    CalculationEntry, StructureEntry,
    set_calculation_steps, migrate_species_overrides_to_calc,
)
# Exceptions
from quantumvitas.core.exceptions import (
    LegacyProjectError, MissingArtifactError,
)
# Driver Protocol
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_exceptions import (
    UnknownMaterializationError, UnknownEngineError,
)
# Identity
from quantumvitas.core.calc_identity import ensure_calculation_identity
# Pseudo
from quantumvitas.core.pseudo_provenance import compute_sha256_file
from quantumvitas.core.pseudo import (
    is_missing_pseudo_placeholder, ensure_qe_pseudos,
    get_system_pseudo_dir, make_missing_pseudo_placeholder,
)
# Provenance
from quantumvitas.core.provenance import update_provenance_after_step
# Debug
from quantumvitas.core.debug import is_resolution_debug_enabled


# Lazy imports — these modules trigger analysis/calculation cycles at import time
def __getattr__(name):
    _LAZY_MAP = {
        # Structure Utils — trigger analysis.structure_viz → analysis.__init__ → calculation cycle
        "canonicalize_structure_like_in_place": ("quantumvitas.core.structure_canonicalize", "canonicalize_structure_like_in_place"),
        "structure_like_fingerprint": ("quantumvitas.core.structure_fingerprint", "structure_like_fingerprint"),
        "DEFAULT_FINGERPRINT_TOL_ANG": ("quantumvitas.core.structure_fingerprint", "DEFAULT_FINGERPRINT_TOL_ANG"),
        # Legacy engine re-exports — trigger drivers/ cycle
        "EngineConfig": ("quantumvitas.core.engines.base", "EngineConfig"),
        "StepResult": ("quantumvitas.core.engines.qe_calculation", "StepResult"),
        "QuantumEspressoEngine": ("quantumvitas.core.engines.qe", "QuantumEspressoEngine"),
        "QEInstallation": ("quantumvitas.core.engines.qe_installation", "QEInstallation"),
        "PseudoManager": ("quantumvitas.core.engines.qe_pseudopotentials", "PseudoManager"),
    }
    if name in _LAZY_MAP:
        mod_path, attr = _LAZY_MAP[name]
        import importlib
        mod = importlib.import_module(mod_path)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
