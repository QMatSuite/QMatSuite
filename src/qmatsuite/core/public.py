# SSOT
from qmatsuite.core.yaml_io import load_yaml_doc, save_yaml_doc, load_yaml_meta_subtree
from qmatsuite.core.yamldoc import YamlDoc, StepDoc, CalcDoc, ProjectDoc
from qmatsuite.core.locking import calc_edit_lock, calc_run_lock
# Resources
from qmatsuite.core.resolution import (
    require_calculation, require_step, require_structure,
    resolve_structure, resolve_calculation, resolve_step,
    list_calculations, list_structures, build_resource_index,
    ResourceIndex, ResourceNotFoundError,
    AmbiguousSelectorError, SelectorNotFoundError,
    make_structure_selector_resolver,
)
from qmatsuite.core.resources import (
    ResourceMeta, generate_resource_id, meta_from_name, slugify,
    ensure_relative_path, generate_unique_name_and_slug,
    get_resources_dir,
)
# Project Utils
from qmatsuite.core.project_utils import (
    load_project_config, save_project_config,
    find_project_root, require_project_root,
    ProjectConfigError,
)
# Models
from qmatsuite.core.models import (
    load_calculation, save_calculation,
    CalculationModel, CalculationStepEntry,
    CalculationEntry, StructureEntry,
    set_calculation_steps, migrate_species_overrides_to_calc,
)
# Exceptions
from qmatsuite.core.exceptions import (
    LegacyProjectError, MissingArtifactError,
)
# Driver Protocol
from qmatsuite.core.driver_registry import DriverRegistry
from qmatsuite.core.driver_exceptions import (
    UnknownMaterializationError, UnknownEngineError,
)
# Identity
from qmatsuite.core.calc_identity import ensure_calculation_identity
# Pseudo
from qmatsuite.core.pseudo_provenance import compute_sha256_file
from qmatsuite.core.pseudo import (
    is_missing_pseudo_placeholder, ensure_qe_pseudos,
    get_system_pseudo_dir, make_missing_pseudo_placeholder,
)
# Provenance
from qmatsuite.core.provenance import update_provenance_after_step
# Debug
from qmatsuite.core.debug import is_resolution_debug_enabled
# Engine registry
from qmatsuite.core.engines.engine_registry import resolve_active_python


# Lazy imports — these modules trigger analysis/calculation cycles at import time
def __getattr__(name):
    _LAZY_MAP = {
        # Structure Utils — trigger analysis.structure_viz → analysis.__init__ → calculation cycle
        "canonicalize_structure_like_in_place": ("qmatsuite.core.structure_canonicalize", "canonicalize_structure_like_in_place"),
        "structure_like_fingerprint": ("qmatsuite.core.structure_fingerprint", "structure_like_fingerprint"),
        "DEFAULT_FINGERPRINT_TOL_ANG": ("qmatsuite.core.structure_fingerprint", "DEFAULT_FINGERPRINT_TOL_ANG"),
        # Legacy engine re-exports — trigger drivers/ cycle
        "EngineConfig": ("qmatsuite.core.engines.base", "EngineConfig"),
        "StepResult": ("qmatsuite.core.engines.qe_calculation", "StepResult"),
        "QuantumEspressoEngine": ("qmatsuite.core.engines.qe", "QuantumEspressoEngine"),
        "QEInstallation": ("qmatsuite.core.engines.qe_installation", "QEInstallation"),
        "PseudoManager": ("qmatsuite.core.engines.qe_pseudopotentials", "PseudoManager"),
    }
    if name in _LAZY_MAP:
        mod_path, attr = _LAZY_MAP[name]
        import importlib
        mod = importlib.import_module(mod_path)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
