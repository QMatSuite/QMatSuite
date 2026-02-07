"""
API utility functions.

Pure utility functions needed by frontends (CLI, daemon) that don't require
a QVService instance. These are thin wrappers around core utilities to
avoid frontends importing quantumvitas.core.* directly.

Step type conversion functions (thin facades over kernel SSOT):
- is_step_type_spec(s) - Check if string is SPEC format
- step_type_gen_from_spec(spec) - Extract GEN from SPEC
- step_type_spec_from_gen(prefix, gen) - Create SPEC from prefix + gen
"""

from __future__ import annotations

from pathlib import Path


# =============================================================================
# Step type conversion utilities - REMOVED per Constitution v1.1 §4.8
# =============================================================================
# The thin facades (is_step_type_spec, step_type_gen_from_spec, step_type_spec_from_gen)
# have been REMOVED per Constitution v1.1 §4.8 (Ban API-level reexport conversion).
#
# Daemon/CLI MUST NOT convert - they should read from DTO fields.
# Kernel code that needs conversion should import directly from SSOT:
#   from quantumvitas.workflow.step_type_convert import gen_from, is_spec, spec_from
# =============================================================================


# =============================================================================
# Resource utilities
# =============================================================================

def slugify(value: str, fallback: str = "resource") -> str:
    """
    Convert a human-readable name into a filesystem-friendly slug.
    
    Args:
        value: Name to slugify
        fallback: Fallback value if slugification results in empty string
        
    Returns:
        Slug string
    """
    from quantumvitas.core.resources import slugify as _slugify
    return _slugify(value, fallback=fallback)


def meta_from_name(kind: str, *, name: str, path: str) -> dict:
    """
    Generate resource metadata from name.
    
    Args:
        kind: Resource kind (e.g., "calculation", "structure", "step")
        name: Resource name
        path: Resource path
        
    Returns:
        Metadata dict
    """
    from quantumvitas.core.resources import meta_from_name as _meta_from_name
    meta = _meta_from_name(kind, name=name, path=path)
    # Convert ResourceMeta to dict if needed
    if hasattr(meta, 'to_dict'):
        return meta.to_dict()
    return meta


def ensure_relative_path(path: Path | str, *, base: Path) -> str:
    """
    Ensure a path is relative to base.
    
    Args:
        path: Path to make relative
        base: Base directory
        
    Returns:
        Relative path string
    """
    from quantumvitas.core.resources import ensure_relative_path as _ensure_relative_path
    return _ensure_relative_path(path, base=base)


def read_structure(filepath: Path | str, format: str | None = None):
    """
    Read atomic structure from file using pymatgen.
    
    Args:
        filepath: Path to structure file
        format: Optional format hint (e.g., "cif", "qe")
        
    Returns:
        pymatgen Structure or Molecule object
    """
    from quantumvitas.io.structure_io import read_structure as _read_structure
    return _read_structure(filepath, format=format)


def write_structure(
    structure,
    filepath: Path | str,
    format: str | None = None,
    metadata: dict | None = None,
) -> None:
    """
    Write atomic structure to file using pymatgen.
    
    Args:
        structure: pymatgen Structure or Molecule
        filepath: Path to output file
        format: Optional format hint (e.g., "cif", "poscar")
        metadata: Optional metadata dict
    """
    from quantumvitas.io.structure_io import write_structure as _write_structure
    from quantumvitas.core.resources import ResourceMeta
    
    # Convert dict to ResourceMeta if needed
    if metadata is not None and isinstance(metadata, dict):
        # Extract default_name and default_path from metadata dict
        default_name = metadata.get("name") or Path(filepath).stem
        default_path = metadata.get("path") or str(Path(filepath).name)
        metadata = ResourceMeta.from_dict(
            metadata,
            kind="structure",
            default_name=default_name,
            default_path=default_path,
        )
    
    return _write_structure(structure, filepath, format=format, metadata=metadata)


def generate_unique_name_and_slug(
    kind: str,
    preferred_name: str,
    existing_slugs: set[str] | list[str],
) -> tuple[str, str]:
    """
    Generate a unique name and slug for a resource.
    
    Args:
        kind: Resource kind (e.g., "structure", "calculation")
        preferred_name: Preferred name
        existing_slugs: Set or list of existing slugs to avoid
        
    Returns:
        Tuple of (name, slug)
    """
    from quantumvitas.core.resources import generate_unique_name_and_slug as _generate_unique_name_and_slug
    
    existing_set = set(existing_slugs) if isinstance(existing_slugs, list) else existing_slugs
    return _generate_unique_name_and_slug(kind, preferred_name, existing_set)


def list_calculation_templates() -> list[dict]:
    """
    List available calculation templates with metadata.
    
    Returns:
        List of dicts with template metadata
    """
    from quantumvitas.core.templates import list_calculation_templates as _list_calculation_templates
    return _list_calculation_templates()


def copy_calculation_template(
    template_name: str,
    dest_dir: Path,
    project_root: Path,
    new_name: str | None = None,
    structure: str | None = None,
    calculation_ulid: str | None = None,
    engine_family: str | None = None,
) -> tuple[Path, set[str], str]:
    """
    Copy a calculation template to destination.

    Args:
        template_name: Template name
        dest_dir: Destination directory for calculation
        project_root: Project root directory
        new_name: Optional new name for the calculation
        structure: Optional structure name to use (overrides template)
        calculation_ulid: Optional ULID to use for the calculation
        engine_family: Optional engine family to set on the calculation

    Returns:
        Tuple of (calculation.yaml path, set of structure names needed, calculation ULID)
    """
    from quantumvitas.core.templates import copy_calculation_template as _copy_calculation_template
    return _copy_calculation_template(
        template_name=template_name,
        dest_dir=dest_dir,
        project_root=project_root,
        new_name=new_name,
        structure=structure,
        calculation_ulid=calculation_ulid,
        engine_family=engine_family,
    )


def copy_structure_template(
    template_name: str,
    dest_dir: Path,
    new_name: str | None = None,
) -> Path:
    """
    Copy a structure template to destination.
    
    Args:
        template_name: Template name or path to .json file
        dest_dir: Destination directory
        new_name: Optional new name for the structure
        
    Returns:
        Path to the copied structure file
    """
    from quantumvitas.core.templates import copy_structure_template as _copy_structure_template
    return _copy_structure_template(
        template_name=template_name,
        dest_dir=dest_dir,
        new_name=new_name,
    )


def extract_selector_from_entry(entry: dict, kind: str = "calculation") -> str | None:
    """
    Extract a selector from a project.qv.yml or calculation.yaml entry.

    This is the generic selector extraction function. Use with kind parameter:
    - "calculation": for calculation entries
    - "structure": for structure entries
    - "step": for step entries

    Priority order:
    1. {kind}_id or {kind}_ulid (ID-only model)
    2. meta.ulid (ULID)
    3. meta.slug (slug)
    4. ulid (legacy)
    5. name (legacy)

    Args:
        entry: Entry dict from project.qv.yml or calculation.yaml
        kind: Resource kind ("calculation", "structure", or "step")

    Returns:
        Selector string (ULID, slug, or name) or None if no valid selector found

    Example:
        entry = {"calculation_id": "01KC38MFJZ7RF3SB7SHVYDQ4J8"}
        selector = extract_selector_from_entry(entry, "calculation")  # Returns ULID
    """
    from quantumvitas.core.selectors import extract_selector_from_entry as _extract
    return _extract(entry, kind)


def entry_display_name(entry: dict) -> str:
    """
    Get display name for a resource entry from project.qv.yml.

    Uses meta.name or meta.slug or id or name fields.

    Args:
        entry: Resource entry dict

    Returns:
        Display name string
    """
    from quantumvitas.core.project_utils import entry_display_name as _entry_display_name
    return _entry_display_name(entry)


def move_to_trash(path: Path | str, trash_dir: Path | str) -> Path:
    """
    Move a file or directory to trash.

    Args:
        path: Path to move
        trash_dir: Trash directory (e.g., project_root / ".trash")

    Returns:
        New path in trash directory
    """
    from quantumvitas.core.project_utils import move_to_trash as _move_to_trash
    return _move_to_trash(path, trash_dir)


def entry_matches(entry: dict, identifier: str) -> bool:
    """
    Check if a project entry matches a given identifier.

    Args:
        entry: Resource entry dict from project.qv.yml
        identifier: Selector to match (ULID, slug, or name)

    Returns:
        True if entry matches identifier
    """
    from quantumvitas.core.project_utils import entry_matches as _entry_matches
    return _entry_matches(entry, identifier)


def detect_runtime_control_keys(parameters: dict) -> list[str]:
    """
    Detect runtime control keys in step parameters.

    Args:
        parameters: Step parameters dict

    Returns:
        List of runtime control key names found
    """
    from quantumvitas.calculation.structure_steps import detect_runtime_control_keys as _detect
    return _detect(parameters)


def needs_alat_preservation(qe_input) -> bool:
    """
    Check if QE input needs alat preservation during geometry optimization.

    Args:
        qe_input: QEInput object

    Returns:
        True if alat should be preserved
    """
    from quantumvitas.calculation.importers import _needs_alat_preservation as _needs
    return _needs(qe_input)


def extract_alat_bohr(qe_input) -> float | None:
    """
    Extract alat in Bohr from QE input.

    Args:
        qe_input: QEInput object

    Returns:
        alat in Bohr or None if not found
    """
    from quantumvitas.calculation.importers import _extract_alat_bohr as _extract
    return _extract(qe_input)


def write_qe_input_file(qe_input, filepath: Path | str) -> None:
    """
    Write QE input file to disk.

    Args:
        qe_input: QEInput object
        filepath: Output file path
    """
    from quantumvitas.drivers.qe.io.generator import QEInputGenerator
    QEInputGenerator.write_file(qe_input, Path(filepath))


def build_step_spec_from_qe_input(
    qe_input,
    project_root: Path,
    engine_config: dict | None = None,
) -> dict:
    """
    Build step spec from imported QE input file.

    Args:
        qe_input: QEInput object
        project_root: Project root directory
        engine_config: Optional engine configuration

    Returns:
        Step spec dict
    """
    from quantumvitas.calculation.importers import build_step_spec_from_qe_input as _build
    return _build(qe_input, project_root, engine_config)


def is_ulid_like(s: str) -> bool:
    """
    Check if string looks like a ULID (26 chars, alphanumeric).

    Transparent re-export from quantumvitas.core.resolution.

    Args:
        s: String to check

    Returns:
        True if string looks like a ULID
    """
    from quantumvitas.core.resolution import _is_ulid_like
    return _is_ulid_like(s)


def validate_ulid(ulid_str: str, kind: str = "resource") -> str:
    """
    Validate and normalize a ULID string.

    Transparent re-export from quantumvitas.core.resolution.

    Args:
        ulid_str: ULID string to validate
        kind: Resource kind for error messages (e.g., "calculation", "structure")

    Returns:
        Normalized ULID string (uppercase)

    Raises:
        ValueError: If the string is not a valid ULID
    """
    from quantumvitas.core.resolution import validate_ulid as _validate_ulid
    return _validate_ulid(ulid_str, kind=kind)


def calculations_using_structure(project_root: Path, config: dict | None, struct_entry: dict) -> list:
    """
    Find calculations that use a given structure.

    Transparent re-export from quantumvitas.core.project_utils.

    Args:
        project_root: Project root path
        config: Project configuration dict (from load_project_config)
        struct_entry: Structure entry dict with 'id' field

    Returns:
        List of calculation entries that reference this structure
    """
    from quantumvitas.core.project_utils import calculations_using_structure as _calculations_using_structure
    return _calculations_using_structure(project_root, config, struct_entry)


def load_calculation(path: Path, project_root: Path | None = None):
    """
    Load a CalculationModel from a calculation.yaml file.

    Transparent re-export from quantumvitas.core.models.

    Args:
        path: Path to calculation.yaml or calculation directory
        project_root: Project root for relative path calculation

    Returns:
        CalculationModel instance
    """
    from quantumvitas.core.models import load_calculation as _load_calculation
    return _load_calculation(path, project_root)


def save_calculation(model, path: Path) -> None:
    """
    Save a CalculationModel to a calculation.yaml file.

    Transparent re-export from quantumvitas.core.models.

    Args:
        model: CalculationModel instance
        path: Path to save to (directory or calculation.yaml file)
    """
    from quantumvitas.core.models import save_calculation as _save_calculation
    _save_calculation(model, path)


# =============================================================================
# Pseudo configuration utilities (re-exports from core.pseudo_config)
# =============================================================================

def get_pseudo_status_bundle() -> dict:
    """
    Get comprehensive pseudo configuration status in a single call.

    This bundle function combines multiple pseudo config operations into
    a single response, reducing API surface while providing all data
    needed for the pseudo management UI.

    Returns:
        Dict with:
        - config: Current pseudo configuration
        - validation: Validation result
        - installed_sssp: List of installed SSSP libraries
        - seed_archives: List of available seed archives
        - manifest_archives: List of manifest archives
        - archive_statuses: Installation status of manifest archives
    """
    from pathlib import Path
    from quantumvitas.core.pseudo_config import (
        load_pseudo_config as _load_pseudo_config,
        validate_pseudo_config as _validate_pseudo_config,
        list_installed_sssp as _list_installed_sssp,
        list_seed_archives as _list_seed_archives,
    )
    from quantumvitas.core.pseudo_installs import (
        load_manifest_archives as _load_manifest_archives,
        check_archives_status as _check_archives_status,
    )

    # Load config once
    config_obj = _load_pseudo_config()
    config_dict = config_obj.to_dict()

    # Validation
    validation_result = _validate_pseudo_config(config_obj)
    validation_dict = validation_result.to_dict()

    # Installed libraries
    store_dir = Path(config_obj.store_dir) if config_obj.store_dir else None
    installed = []
    if store_dir and store_dir.exists():
        libs = _list_installed_sssp(store_dir)
        installed = [lib.to_dict() if hasattr(lib, 'to_dict') else lib for lib in libs]

    # Seed archives
    seed_dir = Path(config_obj.seed_dir) if config_obj.seed_dir else None
    seed_archives = []
    if seed_dir and seed_dir.exists():
        archives = _list_seed_archives(seed_dir)
        seed_archives = [arch.to_dict() if hasattr(arch, 'to_dict') else arch for arch in archives]

    # Manifest archives and their status
    manifest_archives_raw = _load_manifest_archives()
    manifest_archives = [arch.to_dict() if hasattr(arch, 'to_dict') else arch for arch in manifest_archives_raw]

    archive_statuses = []
    if manifest_archives_raw:
        statuses = _check_archives_status(archives=manifest_archives_raw, config=config_obj)
        archive_statuses = [s.to_dict() if hasattr(s, 'to_dict') else s for s in statuses]

    return {
        "config": config_dict,
        "validation": validation_dict,
        "installed_sssp": installed,
        "seed_archives": seed_archives,
        "manifest_archives": manifest_archives,
        "archive_statuses": archive_statuses,
    }


def set_pseudo_config(
    store_dir: str | None = None,
    seed_dir: str | None = None,
    allow_download: bool | None = None,
) -> dict:
    """
    Update pseudo configuration.

    Transparent wrapper around core.pseudo_config.save_pseudo_config().

    Args:
        store_dir: New store directory (optional)
        seed_dir: New seed directory (optional)
        allow_download: Whether to allow downloading (optional)

    Returns:
        Updated configuration dict
    """
    from quantumvitas.core.pseudo_config import (
        load_pseudo_config as _load_pseudo_config,
        save_pseudo_config as _save_pseudo_config,
    )

    config = _load_pseudo_config()

    if store_dir is not None:
        config.store_dir = store_dir
    if seed_dir is not None:
        config.seed_dir = seed_dir
    if allow_download is not None:
        config.allow_download = allow_download

    _save_pseudo_config(config)
    return config.to_dict()


# =============================================================================
# Visualization utilities (re-exports from analysis layer)
# =============================================================================

# Re-export DisplayModeParams directly for type hints and direct construction
from quantumvitas.analysis.structure_viz import DisplayModeParams  # noqa: E402, F401


def build_structure_vis_payload(
    structure,
    params,
    structure_meta: dict | None = None,
) -> dict:
    """
    Build visualization payload from a structure.

    Pure transformation: Structure + DisplayModeParams → visualization primitives dict.

    This function transforms a pymatgen Structure into a dict containing all data
    needed for 3D visualization (atoms, bonds, lattice).

    Args:
        structure: pymatgen Structure object
        params: DisplayModeParams with mode, supercell, box_bounds, repeat_boundary
        structure_meta: Optional metadata dict (structure_ulid, structure_name, formula)

    Returns:
        Dict with atoms, bonds, lattice, n_atoms, n_bonds, element_colors, etc.
    """
    from quantumvitas.analysis.structure_viz import (
        build_structure_vis_payload as _build_structure_vis_payload
    )
    return _build_structure_vis_payload(structure, params, structure_meta)


# Re-export OnlineStructureCache class for type hints
from quantumvitas.io.online_cache import OnlineStructureCache  # noqa: E402, F401


# =============================================================================
# QE metadata utilities (re-exports from drivers layer)
# =============================================================================

# Re-export QE metadata functions for daemon/CLI use
from quantumvitas.drivers.qe.data.qe_metadata import (  # noqa: E402, F401
    get_ui_parameters,
    list_supported_modules,
    get_module_param_sections,
    get_module_card_sections,
    get_module_doc_url,
    get_metadata_file_info,
    get_qe_metadata_debug_info,
    safe_load_metadata,
    reload_metadata,
    QEUIParam,
    _iter_params,  # Private helper needed by daemon
)


# =============================================================================
# Generic engine registry queries (for daemon RPCs, M4)
# =============================================================================

def _get_engine_metadata_module(engine_family: str):
    """
    Get the metadata module for an engine, or None if not available.

    JUSTIFICATION: Internal helper for get_engine_ui_parameters and
    get_engine_parameter_metadata. Centralizes lazy imports of engine
    data modules so daemon handlers don't import from drivers directly.
    """
    if engine_family == "vasp":
        from quantumvitas.drivers.vasp.data import vasp_metadata
        return vasp_metadata
    elif engine_family == "orca":
        from quantumvitas.drivers.orca.data import orca_metadata
        return orca_metadata
    elif engine_family == "lammps":
        from quantumvitas.drivers.lammps.data import lammps_metadata
        return lammps_metadata
    elif engine_family == "gaussian":
        from quantumvitas.drivers.gaussian.data import gaussian_metadata
        return gaussian_metadata
    elif engine_family == "abinit":
        from quantumvitas.drivers.abinit.data import abinit_metadata
        return abinit_metadata
    elif engine_family == "cp2k":
        from quantumvitas.drivers.cp2k.data import cp2k_metadata
        return cp2k_metadata
    elif engine_family == "qmcpack":
        from quantumvitas.drivers.qmcpack.data import qmcpack_metadata
        return qmcpack_metadata
    return None


def list_engine_families() -> list[dict]:
    """
    List all registered engine families with classification metadata.

    JUSTIFICATION: Needed by daemon for list_engine_families RPC.
    Global driver registry query — no project context required.
    Same pattern as QE metadata re-exports (line 616) but engine-agnostic.

    PROXIES: quantumvitas.core.driver_registry.DriverRegistry
    """
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers  # noqa: F401 — ensure loaded

    engines = []
    for family in sorted(DriverRegistry.get_all_engines()):
        driver = DriverRegistry.get_driver(family)
        engines.append({
            "engine_family": family,
            "display_name": driver.display_name,
            "engine_role": getattr(driver, 'ENGINE_ROLE', 'base'),
            "companion_engines": sorted(getattr(driver, 'COMPANION_ENGINES', frozenset())),
            "supported_gen_steps": sorted(getattr(driver, 'SUPPORTED_GEN_STEPS', set())),
        })
    return engines


def get_step_palette(engine_family: str | None) -> dict:
    """
    Get step palette (base + companion steps) for a given engine family.

    JUSTIFICATION: Needed by daemon for list_step_palette RPC.
    Global driver registry query — no project context required.

    PROXIES: quantumvitas.core.driver_registry.DriverRegistry
    """
    if engine_family is None:
        return {"base_steps": [], "companion_steps": {}}

    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers  # noqa: F401

    driver = DriverRegistry.get_driver(engine_family)
    supported = getattr(driver, 'SUPPORTED_GEN_STEPS', set())

    base_steps = []
    for gen in sorted(supported):
        try:
            spec = DriverRegistry.materialize_step_type(engine_family, gen)
            try:
                spec_obj = DriverRegistry.get_step_type_spec(spec)
                desc = spec_obj.description
            except Exception:
                desc = gen
            base_steps.append({"gen": gen, "spec": spec, "description": desc})
        except Exception:
            continue

    companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
    companion_steps = {}
    for comp in sorted(companions):
        try:
            comp_driver = DriverRegistry.get_driver(comp)
            comp_supported = getattr(comp_driver, 'SUPPORTED_GEN_STEPS', set())
            comp_list = []
            for gen in sorted(comp_supported):
                try:
                    spec = DriverRegistry.materialize_step_type(comp, gen)
                    try:
                        spec_obj = DriverRegistry.get_step_type_spec(spec)
                        desc = spec_obj.description
                    except Exception:
                        desc = gen
                    comp_list.append({"gen": gen, "spec": spec, "description": desc})
                except Exception:
                    continue
            if comp_list:
                companion_steps[comp] = comp_list
        except Exception:
            continue

    return {"base_steps": base_steps, "companion_steps": companion_steps}


def validate_engine_family(engine_family: str) -> tuple[bool, str]:
    """
    Validate that engine_family is a registered base engine.

    JUSTIFICATION: Needed by daemon for set_engine_family RPC validation.
    Pure validation check on static registry data, no project context.

    PROXIES: quantumvitas.core.driver_registry.DriverRegistry

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers  # noqa: F401

    if not DriverRegistry.is_engine_registered(engine_family):
        return False, (
            f"Unknown engine_family '{engine_family}'. "
            f"Registered: {sorted(DriverRegistry.get_all_engines())}"
        )

    driver = DriverRegistry.get_driver(engine_family)
    role = getattr(driver, 'ENGINE_ROLE', 'base')
    if role != 'base':
        return False, (
            f"Cannot set engine_family to '{engine_family}' — "
            f"it has ENGINE_ROLE='{role}'. Only base engines can be set as engine_family."
        )

    return True, ""


def get_engine_ui_parameters(engine_family: str, step_type_gen: str) -> list[dict]:
    """
    Get UI parameter metadata for any engine + step type.

    JUSTIFICATION: Needed by daemon for list_engine_ui_parameters RPC.
    Generic replacement for QE-specific get_ui_parameters.
    Queries static engine metadata modules, no project context.

    PROXIES: quantumvitas.drivers.<engine>.data.<engine>_metadata
    """
    engine_family = engine_family.strip().lower()
    step_type_gen = step_type_gen.strip().lower()

    # QE: delegate to existing QE metadata infrastructure
    if engine_family == "qe":
        module_map = {
            "scf": "pw", "nscf": "pw", "relax": "pw",
            "bands_pw": "pw", "bandspw": "pw", "dos": "pw", "md": "pw",
            "bands": "bands", "ph": "ph", "projwfc": "projwfc", "pp": "pp",
        }
        module = module_map.get(step_type_gen)
        if module and module in list_supported_modules():
            ui_params = get_ui_parameters(module, step_type_gen)
            result = []
            for param in ui_params:
                param_dict = {
                    "key": param.name,
                    "label": param.label,
                    "type": param.type,
                    "section": param.namelist,
                }
                if param.unit:
                    param_dict["unit"] = param.unit
                if param.description:
                    param_dict["description"] = param.description
                if param.options:
                    param_dict["options"] = param.options
                if param.importance:
                    param_dict["importance"] = param.importance
                result.append(param_dict)
            return result

    # For engines with metadata modules (VASP, ORCA, etc.)
    try:
        metadata_module = _get_engine_metadata_module(engine_family)
        if metadata_module and hasattr(metadata_module, 'list_tags'):
            tags = metadata_module.list_tags()
            result = []
            for tag_name in sorted(tags):
                info = metadata_module.get_tag_info(tag_name)
                if info:
                    result.append({
                        "key": tag_name,
                        "label": tag_name,
                        "type": info.get("type", "string"),
                        "default": info.get("default"),
                        "description": info.get("description", ""),
                        "section": info.get("category", "general"),
                    })
            return result
    except (ImportError, AttributeError):
        pass

    return []


def get_engine_parameter_metadata(
    engine_family: str,
    operation: str,
    category: str = "",
    query: str = "",
) -> dict:
    """
    Browse parameter metadata for any engine.

    JUSTIFICATION: Needed by daemon for list_engine_parameter_metadata RPC.
    Generic replacement for QE-specific parameter metadata queries.
    Queries static engine metadata modules, no project context.

    PROXIES: quantumvitas.drivers.<engine>.data.<engine>_metadata
    """
    engine_family = engine_family.strip().lower()

    try:
        metadata_module = _get_engine_metadata_module(engine_family)
        if metadata_module is None:
            return {"categories": [], "tags": [], "results": []}

        if operation == "list_categories":
            if hasattr(metadata_module, 'list_categories'):
                cats = metadata_module.list_categories()
                return {"categories": [{"id": c, "label": c} for c in sorted(cats)]}
            return {"categories": []}

        elif operation == "list_tags":
            if hasattr(metadata_module, 'list_tags'):
                tags = (
                    metadata_module.list_tags(category=category)
                    if category
                    else metadata_module.list_tags()
                )
                result = []
                for tag_name in sorted(tags) if isinstance(tags, (list, set)) else sorted(tags):
                    info = (
                        metadata_module.get_tag_info(tag_name)
                        if hasattr(metadata_module, 'get_tag_info')
                        else {}
                    )
                    if info:
                        result.append({
                            "name": tag_name,
                            "type": info.get("type", "string"),
                            "default": info.get("default"),
                            "description": info.get("description", ""),
                            "category": info.get("category", category),
                        })
                return {"tags": result}
            return {"tags": []}

        elif operation == "search":
            if not query:
                raise ValueError("'query' is required for search operation")
            query_lower = query.lower()
            if hasattr(metadata_module, 'list_tags'):
                tags = metadata_module.list_tags()
                results = []
                for tag_name in tags if isinstance(tags, (list, set)) else list(tags):
                    info = (
                        metadata_module.get_tag_info(tag_name)
                        if hasattr(metadata_module, 'get_tag_info')
                        else {}
                    )
                    name_lower = tag_name.lower()
                    desc_lower = (info.get("description", "") or "").lower() if info else ""
                    if query_lower in name_lower or query_lower in desc_lower:
                        results.append({
                            "name": tag_name,
                            "type": info.get("type", "string") if info else "string",
                            "default": info.get("default") if info else None,
                            "description": info.get("description", "") if info else "",
                            "category": info.get("category", "") if info else "",
                        })
                return {"results": results}
            return {"results": []}

        else:
            raise ValueError(
                f"Unknown operation '{operation}'. Must be: list_categories, list_tags, search"
            )

    except (ImportError, AttributeError) as e:
        return {"categories": [], "tags": [], "results": [], "error": str(e)}


# =============================================================================
# Calculation detection utilities (re-exports from presets layer)
# =============================================================================


def get_calculation_preset_bundle(calculation_dir: Path) -> dict:
    """
    Get comprehensive preset detection for a calculation in a single call.

    This bundle function combines multiple preset detection operations into
    a single response, reducing API surface while providing all data
    needed for the calculation preset UI.

    Args:
        calculation_dir: Path to calculation directory

    Returns:
        Dict with:
        - detected_engine: Engine detected from steps (e.g., "qe", "pyscf")
        - dimension_states: Detected preset dimension values
        - workflow_type: Detected workflow type ("SCF", "DOS", etc.)
        - step_footprints: Preset footprints per step
    """
    from quantumvitas.presets.integration import (
        _detect_engine_for_calculation as _detect_engine,
        detect_presets_from_calculation as _detect_presets,
        detect_workflow_type as _detect_workflow,
        get_step_preset_footprints as _get_footprints,
    )

    # Detect engine first (needed for presets detection)
    engine = _detect_engine(calculation_dir)

    return {
        "detected_engine": engine,
        "dimension_states": _detect_presets(calculation_dir, engine_filter=engine),
        "workflow_type": _detect_workflow(calculation_dir),
        "step_footprints": _get_footprints(calculation_dir),
    }


# =============================================================================
# Pseudo download utilities
# =============================================================================

def download_pseudo_by_filename(
    project_root: Path,
    filename: str,
    dest_dir: Path | None = None,
    config: dict | None = None,
) -> dict:
    """
    Download a pseudopotential by filename from QE network repository.

    Args:
        project_root: Project root path
        filename: Exact UPF filename (e.g., "Si.pbe-n-rrkjus_psl.1.0.0.UPF")
        dest_dir: Optional destination directory (default: project_root/pseudo)
        config: Optional project config (unused, for backwards compatibility)

    Returns:
        Dict with:
        - filename: Final filename in destination (may be renamed if conflict)
        - renamed: True if filename was changed due to conflict
        - skipped: True if file already exists with same SHA256
        - errors: List of error messages
    """
    import urllib.request
    import urllib.error
    import hashlib
    import tempfile
    from quantumvitas.core.pseudo_config import get_ssl_context, load_pseudo_config

    if dest_dir is None:
        dest_dir = project_root / "pseudo"
    dest_dir = Path(dest_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Load pseudo config (network URLs are user-level, not project-level)
    pseudo_config = load_pseudo_config()

    download_url = f"{pseudo_config.network_pseudo_base_url}/{filename}"

    def compute_sha256(file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    # Build SHA256 index of existing pseudos
    existing_hashes: dict[str, str] = {}
    for existing_file in dest_dir.iterdir():
        if existing_file.is_file() and existing_file.suffix.lower() in ('.upf',):
            try:
                existing_hashes[compute_sha256(existing_file)] = existing_file.name
            except Exception:
                pass

    result = {
        "filename": filename,
        "renamed": False,
        "skipped": False,
        "errors": [],
    }

    try:
        ssl_context = get_ssl_context(pseudo_config.verify_ssl)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.upf') as tmp_file:
            tmp_path = Path(tmp_file.name)

        request = urllib.request.Request(download_url)
        with urllib.request.urlopen(request, context=ssl_context, timeout=60) as response:
            tmp_path.write_bytes(response.read())

        # Check if we already have this file
        file_hash = compute_sha256(tmp_path)
        if file_hash in existing_hashes:
            result["skipped"] = True
            result["filename"] = existing_hashes[file_hash]
            tmp_path.unlink()
            return result

        # Check for filename conflicts
        dest_path = dest_dir / filename
        if dest_path.exists():
            # Rename with hash suffix
            stem = dest_path.stem
            suffix = dest_path.suffix
            result["filename"] = f"{stem}_{file_hash[:8]}{suffix}"
            result["renamed"] = True
            dest_path = dest_dir / result["filename"]

        # Move temp file to destination
        import shutil
        shutil.move(str(tmp_path), str(dest_path))

    except urllib.error.URLError as e:
        result["errors"].append(f"Download failed: {e}")
    except Exception as e:
        result["errors"].append(f"Error: {e}")

    return result


# =============================================================================
# QE engine utilities
# =============================================================================


def get_qe_engine_status() -> dict:
    """
    Get comprehensive QE engine status in a single call.

    This bundle function combines multiple QE detection operations into
    a single response, reducing API surface while providing all data
    needed for the QE configuration UI.

    Returns:
        Dict with:
        - detection: QE detection result (found, qe_home, version, executables)
        - environment: Environment info (python_version, qv_version, qe_found)
        - available_engines: List of available QE engines (internal)
        - discovered: Auto-discovered engines (cached)
    """
    import json
    import platform
    import shutil
    import sys
    import time
    from quantumvitas.core.settings import load_settings
    from quantumvitas.core.engines.qe_resolver import resolve_qe_bin_dir
    from quantumvitas.core.engines.qe_installation import QEInstallation, get_qe_home
    from quantumvitas.core.paths import home_qe_engines_dir, tmp_probe_dir

    # === Detection ===
    detection: dict
    try:
        settings = load_settings()
        qe_bin_dir = resolve_qe_bin_dir(settings)
        qe_home = qe_bin_dir.parent

        detection = {
            "found": True,
            "qe_home": str(qe_home),
            "qe_bin_dir": str(qe_bin_dir),
            "version": None,
            "executables": [],
            "mode": "external" if settings.qe.bin_dir else "internal",
        }

        if qe_bin_dir.exists():
            executables = []
            for exe in ["pw.x", "ph.x", "dos.x", "bands.x", "projwfc.x", "pp.x"]:
                if (qe_bin_dir / exe).exists():
                    executables.append(exe)
            detection["executables"] = executables

        try:
            installation = QEInstallation(qe_home)
            version = installation.version
            if version:
                detection["version"] = version
        except Exception:
            pass
    except RuntimeError as e:
        detection = {
            "found": False,
            "qe_home": None,
            "qe_bin_dir": None,
            "version": None,
            "executables": [],
            "error": str(e),
        }

    # === Environment ===
    qe_home_path = get_qe_home()
    environment = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_executable": sys.executable,
        "qv_version": "2.0.0",
        "qe_home": str(qe_home_path) if qe_home_path else None,
        "qe_found": qe_home_path is not None,
    }

    # === Available Engines ===
    settings = load_settings()
    current_bin_dir = None
    current_mode = "internal"

    try:
        resolved_bin_dir = resolve_qe_bin_dir(settings)
        current_bin_dir = str(resolved_bin_dir)
        if settings.qe.bin_dir:
            current_mode = "external"
        else:
            current_mode = "internal"
    except RuntimeError:
        pass

    engines_base = home_qe_engines_dir()
    internal_engines = []

    if engines_base.exists():
        for engine_dir in engines_base.rglob("bin"):
            if not engine_dir.is_dir():
                continue
            pw_x = engine_dir / "pw.x"
            pw_exe = engine_dir / "pw.x.exe"
            if pw_x.exists() or pw_exe.exists():
                parent_engine = engine_dir.parent
                internal_engines.append({
                    "bin_dir": str(engine_dir),
                    "engine_path": str(parent_engine),
                    "pw_path": str(pw_x if pw_x.exists() else pw_exe),
                })

    available_engines = {
        "current_mode": current_mode,
        "current_bin_dir": current_bin_dir,
        "internal_engines": internal_engines,
    }

    # === Discovery (cached) ===
    cache_path = tmp_probe_dir() / "qe_discovery.json"
    discovered: dict

    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if time.time() - cached.get("cached_at", 0) < 3600:
                    discovered = cached
                else:
                    discovered = _discover_qe_engines_impl(cache_path)
        except Exception:
            discovered = _discover_qe_engines_impl(cache_path)
    else:
        discovered = _discover_qe_engines_impl(cache_path)

    return {
        "detection": detection,
        "environment": environment,
        "available_engines": available_engines,
        "discovered": discovered,
    }


def _discover_qe_engines_impl(cache_path: Path) -> dict:
    """Internal implementation for QE engine discovery with caching."""
    import json
    import platform
    import shutil
    import time
    from quantumvitas.core.engines.qe_installation import QEInstallation

    discovered_list = []
    search_paths = []
    if platform.system() == "Windows":
        search_paths.extend([
            Path("C:/Program Files"),
            Path.home() / "AppData" / "Local",
        ])
    else:
        search_paths.extend([
            Path.home() / "src",
            Path.home() / "local",
            Path("/usr/local"),
            Path("/opt"),
        ])

    pw_path = shutil.which("pw.x")
    if pw_path:
        qe_home = QEInstallation.qe_home_from_binary(Path(pw_path))
        if qe_home:
            discovered_list.append({
                "engine_id": f"external:path:{qe_home.name}",
                "label": f"QE from PATH ({qe_home})",
                "qe_home": str(qe_home),
                "pw_path": pw_path,
            })

    for search_root in search_paths[:3]:
        if not search_root.exists():
            continue
        try:
            for qe_dir in search_root.rglob("q-e-qe-*"):
                if (qe_dir / "bin" / "pw.x").exists() or (qe_dir / "bin" / "pw.x.exe").exists():
                    pw_path_str = str(qe_dir / "bin" / "pw.x")
                    if not (qe_dir / "bin" / "pw.x").exists():
                        pw_path_str = str(qe_dir / "bin" / "pw.x.exe")
                    discovered_list.append({
                        "engine_id": f"external:discovered:{qe_dir.name}",
                        "label": f"QE {qe_dir.name} ({qe_dir})",
                        "qe_home": str(qe_dir),
                        "pw_path": pw_path_str,
                    })
                    if len(discovered_list) >= 10:
                        break
            if len(discovered_list) >= 10:
                break
        except (PermissionError, OSError):
            continue

    result = {
        "discovered_engines": discovered_list,
        "cached_at": time.time(),
    }

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    except Exception:
        pass

    return result


def set_qe_engine(bin_dir: str | None) -> dict:
    """
    Set QE bin directory (two-state model).

    Args:
        bin_dir: Absolute path to QE bin directory, or None to use internal QE

    Returns:
        Success status dict
    """
    from quantumvitas.core.settings import load_settings, save_settings
    from quantumvitas.core.engines.qe_resolver import validate_qe_bin_dir

    settings = load_settings()

    if bin_dir:
        bin_path = Path(bin_dir).resolve()
        validate_qe_bin_dir(bin_path)
        settings.qe.bin_dir = str(bin_path)
    else:
        settings.qe.bin_dir = None

    save_settings(settings)

    return {"success": True}


# =============================================================================
# Additional pseudo utilities
# =============================================================================

def resolve_pseudo_provenance(
    pseudo_path: str,
    project_root: str | None = None,
) -> dict:
    """
    Resolve pseudo provenance by matching against libinfo index.

    Args:
        pseudo_path: Path to pseudo file (absolute or relative to project_root)
        project_root: Optional project root (for resolving relative paths)

    Returns:
        Dict with provenance information
    """
    from quantumvitas.core.pseudo_provenance import resolve_pseudo_provenance as _resolve
    from quantumvitas.core.serialization import to_jsonable

    pseudo_path_obj = Path(pseudo_path)
    if not pseudo_path_obj.is_absolute() and project_root:
        pseudo_path_obj = Path(project_root) / pseudo_path_obj

    result = _resolve(pseudo_path_obj)

    return to_jsonable({
        "path": result.path,
        "element": result.element,
        "basename": result.basename,
        "sha256": result.sha256,
        "sha_family": result.sha_family,
        "match_kind": result.match_kind,
        "matches": [
            {
                "archive_name": m.archive_name,
                "archive_sha256": m.archive_sha256,
                "library_name": m.library_name,
                "category": m.category,
                "library_version": m.library_version,
                "xc": m.xc,
                "quality": m.quality,
                "type": m.type,
                "relativistic": m.relativistic,
                "path_in_archive": m.path_in_archive,
                "basename": m.basename,
            }
            for m in result.matches
        ],
        "warnings": result.warnings,
    })


def download_pseudo_from_url(
    project_root: Path,
    url: str,
    dest_dir: Path | None = None,
    preferred_filename: str | None = None,
) -> dict:
    """
    Download a pseudopotential from any URL.

    Args:
        project_root: Project root path
        url: Full URL to download from
        dest_dir: Optional destination directory (default: project_root/pseudo)
        preferred_filename: Optional preferred filename (extracted from URL if not provided)

    Returns:
        Dict with filename, renamed, skipped, errors
    """
    import urllib.request
    import urllib.error
    import urllib.parse
    import hashlib
    import shutil
    import tempfile
    from quantumvitas.core.pseudo_config import get_ssl_context

    if dest_dir is None:
        dest_dir = project_root / "pseudo"
    dest_dir = Path(dest_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    if preferred_filename is None:
        preferred_filename = url.split('/')[-1]
        preferred_filename = urllib.parse.unquote(preferred_filename)

    def compute_sha256(file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    existing_hashes: dict[str, str] = {}
    for existing_file in dest_dir.iterdir():
        if existing_file.is_file() and existing_file.suffix.lower() in ('.upf',):
            try:
                existing_hashes[compute_sha256(existing_file)] = existing_file.name
            except Exception:
                pass

    result = {
        "filename": preferred_filename,
        "renamed": False,
        "skipped": False,
        "errors": [],
    }

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.upf') as tmp_file:
            tmp_path = Path(tmp_file.name)

        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'QuantumVITAS/1.0')

        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=30) as response:
            with open(tmp_path, 'wb') as f:
                shutil.copyfileobj(response, f)

        downloaded_hash = compute_sha256(tmp_path)

        if downloaded_hash in existing_hashes:
            existing_name = existing_hashes[downloaded_hash]
            tmp_path.unlink()
            result["skipped"] = True
            result["filename"] = existing_name
            return result

        final_filename = preferred_filename
        final_path = dest_dir / final_filename

        if final_path.exists():
            base_name = Path(preferred_filename).stem
            extension = Path(preferred_filename).suffix
            counter = 1
            while final_path.exists():
                final_filename = f"{base_name}_{counter}{extension}"
                final_path = dest_dir / final_filename
                counter += 1
            result["renamed"] = True
            result["filename"] = final_filename

        shutil.move(str(tmp_path), str(final_path))

    except urllib.error.HTTPError as e:
        result["errors"].append(f"HTTP error {e.code}: {e.reason}")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
    except urllib.error.URLError as e:
        result["errors"].append(f"Network error: {e}")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
    except Exception as e:
        result["errors"].append(f"Error downloading from {url}: {e}")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()

    return result


# =============================================================================
# Journal and blob store utilities (re-exports from kernel layer)
# =============================================================================

def get_journal():
    """
    Get the global journal instance.

    Returns:
        Journal instance for event logging
    """
    from quantumvitas.core.journal import get_journal as _get_journal
    return _get_journal()


def create_blob_store(calc_dir: Path):
    """
    Create a BlobStore instance for a calculation directory.

    Args:
        calc_dir: Calculation directory for blob storage

    Returns:
        BlobStore instance
    """
    from quantumvitas.analysis.blob_store import BlobStore
    return BlobStore(calc_dir)


def compute_io_dir_from_calculation_model(
    calculation_dir: Path,
    working_dir_name: str | None = None,
) -> Path:
    """
    Compute the I/O directory path from calculation model/context.

    This is the SINGLE SOURCE OF TRUTH for determining the I/O directory.
    Both the server (for pending jobs) and runner (for execution) use this function.

    Args:
        calculation_dir: Path to the calculation directory (containing calculation.yaml)
        working_dir_name: Name of the working directory subdirectory (from calculation.working_dir).
                         If None, defaults to "raw" (the convention for local runner).

    Returns:
        Absolute Path to the I/O directory
    """
    from quantumvitas.calculation.runner import compute_io_dir_from_calculation_model as _compute_io_dir
    return _compute_io_dir(calculation_dir, working_dir_name)


def parse_volume_artifact(
    file_path: Path,
    calc_dir: Path,
    file_type: str | None = None,
    band_index: int = 1,
) -> dict:
    """
    Parse a volume artifact file (XSF or BXSF) and create blob storage.

    Args:
        file_path: Path to volume file (.xsf or .bxsf)
        calc_dir: Calculation directory for blob storage
        file_type: Optional file type hint ("xsf" or "bxsf"), auto-detected from suffix if None
        band_index: Band index for BXSF files (1-indexed, default 1)

    Returns:
        Dict with volume data and blob storage info
    """
    from quantumvitas.io.parser.volume_parsers import parse_volume_artifact as _parse_volume_artifact
    return _parse_volume_artifact(file_path, calc_dir, file_type=file_type, band_index=band_index)


# =============================================================================
# Preset utilities (re-exports from presets layer)
# =============================================================================

def apply_presets_to_step(
    step_path: Path,
    options: dict,
    *,
    validate_physics: bool = True,
    precision_advice=None,
    precision_lattice_matrix: list | None = None,
) -> dict:
    """
    Apply preset options to an existing step.

    Per Constitution §10.3.3: This OVERWRITES preset-related parameters,
    it does NOT merge. Non-preset parameters are preserved.

    Args:
        step_path: Path to step YAML file
        options: Dict with preset options (e.g., {"spin": "collinear"})
        validate_physics: Validate physics constraints
        precision_advice: Optional PrecisionAdvice object
        precision_lattice_matrix: For precision context

    Returns:
        Dict with applied options summary
    """
    from quantumvitas.presets.integration import apply_presets_to_step as _apply_presets
    return _apply_presets(
        step_path,
        options,
        validate_physics=validate_physics,
        precision_advice=precision_advice,
        precision_lattice_matrix=precision_lattice_matrix,
    )


def get_preset_catalog() -> dict:
    """
    Get preset catalog (UI's single source of truth).

    Returns:
        Dict with catalog structure containing dimensions, options, labels, etc.
    """
    from quantumvitas.presets.catalog import get_preset_catalog as _get_catalog
    return _get_catalog()


def resolve_precision_context(
    structure,
    pseudo_library: str | None = None,
    elements: list | None = None,
) -> dict:
    """
    Resolve precision context for a structure.

    Args:
        structure: pymatgen Structure
        pseudo_library: Optional pseudo library name
        elements: Optional list of elements

    Returns:
        Dict with precision context data
    """
    from quantumvitas.presets.precision_context import resolve_precision_context as _resolve
    return _resolve(structure, pseudo_library=pseudo_library, elements=elements)


# =============================================================================
# Path context and structure utilities
# =============================================================================

# Re-export ContextNotFoundError for CLI error handling
from quantumvitas.core.context import ContextNotFoundError  # noqa: E402, F401


def find_path_context_from_pwd(start_dir: Path | None = None, max_depth: int = 20):
    """
    Scan upward from a directory to find project context.

    Args:
        start_dir: Starting directory (defaults to cwd)
        max_depth: Maximum directories to scan upward

    Returns:
        PathContext with project_root and context nodes

    Raises:
        ContextNotFoundError: If no project context found
    """
    from quantumvitas.core.context import find_path_context_from_pwd as _find_context
    return _find_context(start_dir, max_depth=max_depth)


def canonicalize_structure(structure) -> None:
    """
    Canonicalize structure in place (wrap coords, stable species ordering).

    Args:
        structure: Structure object (modified in place)
    """
    from quantumvitas.analysis.structure_viz import canonicalize_structure_in_place
    canonicalize_structure_in_place(structure)


def reduce_formula(formula: str) -> str:
    """
    Reduce chemical formula to canonical form.

    Args:
        formula: Chemical formula string

    Returns:
        Reduced formula string (e.g., "Si2O4" -> "SiO2")
    """
    from quantumvitas.io.online_search import reduce_formula as _reduce_formula
    return _reduce_formula(formula)


# =============================================================================
# Online search utilities
# =============================================================================

def search_online_structures(
    query: str,
    max_results: int = 50,
):
    """
    Search online structure databases.

    Args:
        query: Search query (formula or text)
        max_results: Maximum number of results

    Returns:
        Tuple of (source_summary, candidates, structures, optimade_base)
    """
    from quantumvitas.io.online_search import search_online_structures as _search
    return _search(query, max_results=max_results)


def fetch_structure_from_optimade(optimade_base: str, source_id: str):
    """
    Fetch a structure from OPTIMADE API.

    Args:
        optimade_base: OPTIMADE API base URL
        source_id: Structure source ID

    Returns:
        Tuple of (structure, raw_data)
    """
    from quantumvitas.io.online_search import fetch_structure_from_optimade as _fetch
    return _fetch(optimade_base, source_id)


def score_candidate(structure, source: str, query_reduced: str, raw_data: dict) -> tuple:
    """
    Score a structure candidate for relevance.

    Args:
        structure: Structure object
        source: Source name
        query_reduced: Reduced query formula
        raw_data: Raw candidate data

    Returns:
        Tuple of (score, flags)
    """
    from quantumvitas.io.online_search import score_candidate as _score
    return _score(structure, source, query_reduced, raw_data)


def extract_provenance(structure, source: str, raw_data: dict) -> dict:
    """
    Extract provenance information from a structure candidate.

    Args:
        structure: Structure object
        source: Source name
        raw_data: Raw candidate data

    Returns:
        Dict with provenance information
    """
    from quantumvitas.io.online_search import extract_provenance as _extract
    return _extract(structure, source, raw_data)


# =============================================================================
# Settings utilities
# =============================================================================

def set_settings(settings_dict: dict) -> None:
    """
    Update user settings.

    Args:
        settings_dict: Dict with settings to update
    """
    from quantumvitas.core.settings import load_settings, save_settings
    settings = load_settings()
    for key, value in settings_dict.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    save_settings(settings)


# =============================================================================
# Engine utilities (transparent re-exports for CLI)
# =============================================================================

def create_default_registry(config_dict: dict | None = None):
    """
    Create default engine registry.

    Args:
        config_dict: Optional engine config dict

    Returns:
        Engine registry instance
    """
    from quantumvitas.engine.registry import create_default_registry as _create_default_registry
    return _create_default_registry(config_dict)


def get_qe_home():
    """
    Get QE home directory from internal registry.

    Returns:
        Path to QE home or None if not found
    """
    from quantumvitas.core.engines.qe_installation import get_qe_home as _get_qe_home
    return _get_qe_home()


# =============================================================================
# Calculation execution utilities (transparent re-exports for CLI)
# =============================================================================

def run_input_step(
    engine,
    input_file,
    working_dir,
    project_root=None,
    step_type_spec=None,
    parameter_overrides=None,
    card_overrides=None,
    species_overrides=None,
    keep_original: bool = True,
):
    """
    Run a QE input step directly.

    Args:
        engine: Engine name or backend
        input_file: Path to input file
        working_dir: Working directory
        project_root: Project root (for pseudo resolution)
        step_type_spec: Step type spec hint (e.g., "qe_scf")
        parameter_overrides: Parameter overrides dict
        card_overrides: Card overrides dict
        species_overrides: Species overrides dict
        keep_original: Whether to keep original input file

    Returns:
        Tuple of (result, prepared_input_path)
    """
    from quantumvitas.calculation.input_runner import run_input_step as _run_input_step
    return _run_input_step(
        engine=engine,
        input_file=input_file,
        working_dir=working_dir,
        project_root=project_root,
        step_type_spec=step_type_spec,
        parameter_overrides=parameter_overrides,
        card_overrides=card_overrides,
        species_overrides=species_overrides,
        keep_original=keep_original,
    )


def apply_card_overrides_to_qe_input(qe_input, card_overrides: dict | None) -> None:
    """
    Apply card overrides to QE input object in place.

    Args:
        qe_input: QEInput object
        card_overrides: Card overrides dict
    """
    from quantumvitas.calculation.input_runner import apply_card_overrides_to_qe_input as _apply
    _apply(qe_input, card_overrides)


def apply_species_overrides_to_qe_input(qe_input, species_overrides: dict | None) -> None:
    """
    Apply species overrides to QE input object in place.

    Args:
        qe_input: QEInput object
        species_overrides: Species overrides dict
    """
    from quantumvitas.calculation.input_runner import apply_species_overrides_to_qe_input as _apply
    _apply(qe_input, species_overrides)


# =============================================================================
# Calculation naming utilities (transparent re-exports for CLI)
# =============================================================================

def find_calculation_raw_dir(calculation_dir, working_dir_name: str | None = None):
    """
    Find calculation raw output directory.

    Args:
        calculation_dir: Path to calculation directory
        working_dir_name: Optional working directory name from calculation.yaml

    Returns:
        Path to raw directory
    """
    from quantumvitas.calculation.naming import find_calculation_raw_dir as _find
    return _find(calculation_dir, working_dir_name)


def find_calculation_results_dir(calculation_dir):
    """
    Find calculation results directory (creates if needed).

    Args:
        calculation_dir: Path to calculation directory

    Returns:
        Path to results directory
    """
    from quantumvitas.calculation.naming import find_calculation_results_dir as _find
    return _find(calculation_dir)


def find_band_analysis_files(search_dir):
    """
    Find band analysis files in a directory.

    Args:
        search_dir: Directory to search

    Returns:
        BandAnalysisFiles namedtuple with paths to found files
    """
    from quantumvitas.calculation.naming import find_band_analysis_files as _find
    return _find(search_dir)


# =============================================================================
# Analysis utilities (transparent re-exports for CLI)
# =============================================================================

def parse_scf_output(output_file):
    """
    Parse SCF output file for energies and convergence.

    Args:
        output_file: Path to SCF output file

    Returns:
        SCFResult object
    """
    from quantumvitas.analysis.parsers import parse_scf_output as _parse
    return _parse(output_file)


def plot_scf_convergence(scf_result, ax=None):
    """
    Plot SCF convergence from result.

    Args:
        scf_result: SCFResult object
        ax: Optional matplotlib axis

    Returns:
        Tuple of (figure, axis)
    """
    from quantumvitas.analysis.plotting import plot_scf_convergence as _plot
    return _plot(scf_result, ax)


def save_figure(fig, output_path, **kwargs):
    """
    Save matplotlib figure to file.

    Args:
        fig: Matplotlib figure
        output_path: Output path
        **kwargs: Additional savefig kwargs
    """
    from quantumvitas.analysis.plotting import save_figure as _save
    return _save(fig, output_path, **kwargs)


def visualize_structure(
    structure,
    output_path=None,
    supercell=None,
    repeat_boundary: bool = False,
    show: bool = False,
    plot_format: str = "png",
):
    """
    Visualize atomic structure.

    Args:
        structure: pymatgen Structure
        output_path: Output file path
        supercell: Supercell tuple (nx, ny, nz)
        repeat_boundary: Whether to repeat atoms at boundaries
        show: Whether to show interactively
        plot_format: Output format (png, svg, etc.)

    Returns:
        VisualizationResult with output_path, n_atoms, n_bonds
    """
    from quantumvitas.analysis.structure_viz import visualize_structure as _visualize
    return _visualize(
        structure=structure,
        output_path=output_path,
        supercell=supercell,
        repeat_boundary=repeat_boundary,
        show=show,
        plot_format=plot_format,
    )


# =============================================================================
# Project snapshot utilities (transparent re-exports for CLI)
# =============================================================================

def materialize_project_from_snapshot(
    snapshot,
    parent_dir,
    new_project_name: str | None = None,
):
    """
    Materialize a project from a snapshot.

    Args:
        snapshot: ProjectSnapshot object
        parent_dir: Parent directory for the new project
        new_project_name: Optional new project name

    Returns:
        Path to the created project directory
    """
    from quantumvitas.project.snapshot import materialize_project_from_snapshot as _materialize
    return _materialize(
        snapshot=snapshot,
        parent_dir=parent_dir,
        new_project_name=new_project_name,
    )


def export_project_to_snapshot(project_root):
    """
    Export a project to a snapshot.

    Args:
        project_root: Path to project root

    Returns:
        ProjectSnapshot object
    """
    from quantumvitas.project.snapshot import export_project_to_snapshot as _export
    return _export(project_root)


# Re-export ProjectSnapshot class for type hints and construction
def get_project_snapshot_class():
    """
    Get ProjectSnapshot class.

    Returns:
        ProjectSnapshot class
    """
    from quantumvitas.project.snapshot import ProjectSnapshot
    return ProjectSnapshot


# =============================================================================
# Pseudo management utilities (transparent re-exports for daemon)
# =============================================================================

def search_legacy_pseudos(
    element: str,
    config: dict | None = None,
) -> dict:
    """
    Search for pseudopotentials by element using QE legacy tables.

    Args:
        element: Element symbol (e.g., "Si", "Mo")
        config: Optional project config

    Returns:
        Dict with candidates list and errors
    """
    import urllib.request
    import re
    from quantumvitas.core.pseudo_config import load_pseudo_config, get_ssl_context

    pseudo_config = load_pseudo_config()
    element_lower = element.lower()
    legacy_url = f"{pseudo_config.legacy_tables_base_url}/ps-library/{element_lower}"

    candidates: list[dict] = []
    errors: list[str] = []

    try:
        req = urllib.request.Request(legacy_url)
        req.add_header('User-Agent', 'QuantumVITAS/1.0')

        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=30) as response:
            html_content = response.read().decode('utf-8', errors='ignore')

        upf_pattern = re.compile(r'href=["\']([^"\']*\.(?:UPF|upf))["\']', re.IGNORECASE)
        filename_pattern = re.compile(r'([^/]+\.(?:UPF|upf))', re.IGNORECASE)

        seen_filenames = set()
        for match in upf_pattern.finditer(html_content):
            url = match.group(1)
            filename_match = filename_pattern.search(url)
            if filename_match:
                filename = filename_match.group(1)
                if filename not in seen_filenames:
                    seen_filenames.add(filename)

                    if url.startswith('http'):
                        full_url = url
                    elif url.startswith('/'):
                        base = pseudo_config.legacy_tables_base_url.rsplit('/', 1)[0]
                        full_url = f"{base}{url}"
                    else:
                        full_url = f"{legacy_url.rsplit('/', 1)[0]}/{url}"

                    candidates.append({
                        "filename": filename,
                        "url": full_url,
                        "element": element,
                    })

    except Exception as e:
        errors.append(str(e))

    return {
        "candidates": candidates,
        "errors": errors,
    }


def create_precision_advisor(
    species_map: dict,
    lattice_matrix,
    repo_root,
):
    """
    Create PrecisionAdvisor instance.

    Args:
        species_map: Species mapping dict
        lattice_matrix: Lattice matrix
        repo_root: Repository root path

    Returns:
        PrecisionAdvisor instance
    """
    from quantumvitas.presets.precision import PrecisionAdvisor
    return PrecisionAdvisor(
        species_map=species_map,
        lattice_matrix=lattice_matrix,
        repo_root=repo_root,
    )



