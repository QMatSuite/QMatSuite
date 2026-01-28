"""
API utility functions.

Pure utility functions needed by frontends (CLI, daemon) that don't require
a QVService instance. These are thin wrappers around core utilities to
avoid frontends importing quantumvitas.core.* directly.
"""

from __future__ import annotations

from pathlib import Path


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


def generate_resource_id() -> str:
    """
    Generate a unique resource ID (ULID).
    
    Returns:
        ULID string
    """
    from quantumvitas.core.resources import generate_resource_id as _generate_resource_id
    return _generate_resource_id()


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


def extract_calculation_selector_from_entry(entry: dict) -> str | None:
    """
    Extract a calculation selector from a project.qv.yml entry.
    
    Priority order:
    1. calculation_id (ID-only model)
    2. meta.id (ULID)
    3. meta.slug (slug)
    4. id (legacy)
    5. name (legacy)
    
    Returns:
        Selector string (ULID, slug, or name) or None if no valid selector found
    """
    from quantumvitas.core.selectors import extract_calculation_selector_from_entry as _extract
    return _extract(entry)


def extract_structure_selector_from_entry(entry: dict) -> str | None:
    """
    Extract a structure selector from a project.qv.yml entry.

    Priority order:
    1. structure_id (ID-only model)
    2. meta.id (ULID)
    3. meta.slug (slug)
    4. id (legacy)
    5. name (legacy)

    Returns:
        Selector string (ULID, slug, or name) or None if no valid selector found
    """
    from quantumvitas.core.selectors import extract_structure_selector_from_entry as _extract
    return _extract(entry)


def extract_step_selector_from_entry(entry: dict) -> str | None:
    """
    Extract a step selector from a calculation.yaml step entry.

    Priority order:
    1. step_id (ID-only model)
    2. meta.id (ULID)
    3. meta.slug (slug)
    4. id (legacy)
    5. name (legacy)

    Returns:
        Selector string (ULID, slug, or name) or None if no valid selector found
    """
    from quantumvitas.core.selectors import extract_step_selector_from_entry as _extract
    return _extract(entry)


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


def find_path_context_ref(cwd: Path | str | None = None, max_depth: int = 20) -> dict:
    """
    Find path context from working directory.

    This function scans upward from cwd to find project root and context.

    Args:
        cwd: Starting directory (defaults to current working directory)
        max_depth: Maximum directories to scan upward

    Returns:
        Dict with keys:
        - project_root: Path to project root
        - is_inside_calculation: bool
        - calculation_directory: Optional[Path] if inside a calculation
        - calculation_selector: Optional[str] if inside a calculation
        - step_selector: Optional[str] if inside a step

    Raises:
        APIError: If no project context found
    """
    from quantumvitas.core.context import find_path_context_from_pwd, ContextNotFoundError
    from quantumvitas.api.errors import NotFoundError

    if cwd is None:
        cwd = Path.cwd()
    else:
        cwd = Path(cwd).resolve()

    try:
        path_context = find_path_context_from_pwd(start=cwd, max_depth=max_depth)
        result = {
            "project_root": path_context.project_root,
            "is_inside_calculation": path_context.is_inside_calculation(),
            "calculation_directory": path_context.calculation_directory,
        }

        # Extract calculation and step selectors from context nodes
        calculation_selector = None
        step_selector = None
        for node in path_context.nodes:
            if node.kind == "calculation" and node.selector:
                calculation_selector = node.selector
            elif node.kind == "step" and node.selector:
                step_selector = node.selector

        if calculation_selector:
            result["calculation_selector"] = calculation_selector
        if step_selector:
            result["step_selector"] = step_selector

        return result
    except ContextNotFoundError as e:
        raise NotFoundError(f"No project context found: {e}", context={"cwd": str(cwd)})


def find_project_root(start: Path | str | None = None) -> Path | None:
    """
    Find project root from a starting directory.

    Args:
        start: Starting directory (defaults to current working directory)

    Returns:
        Path to project root or None if not found
    """
    from quantumvitas.core.context import find_path_context_from_pwd, ContextNotFoundError

    if start is None:
        start = Path.cwd()
    else:
        start = Path(start).resolve()

    try:
        ctx = find_path_context_from_pwd(start=start)
        return ctx.project_root
    except ContextNotFoundError:
        return None


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
# Visualization utilities (re-exports from analysis layer)
# =============================================================================

def get_display_mode_params_class():
    """
    Get the DisplayModeParams class for constructing display mode parameters.

    This is the proper way for frontends to access the DisplayModeParams type.

    Returns:
        DisplayModeParams class
    """
    from quantumvitas.analysis.structure_viz import DisplayModeParams
    return DisplayModeParams


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
        structure_meta: Optional metadata dict (structure_id, structure_name, formula)

    Returns:
        Dict with atoms, bonds, lattice, n_atoms, n_bonds, element_colors, etc.
    """
    from quantumvitas.analysis.structure_viz import (
        build_structure_vis_payload as _build_structure_vis_payload
    )
    return _build_structure_vis_payload(structure, params, structure_meta)


# =============================================================================
# Online structure cache (re-export from IO layer)
# =============================================================================

def create_online_structure_cache(cache_dir: Path):
    """
    Create an OnlineStructureCache instance for managing online structure search results.

    Args:
        cache_dir: Directory for cache storage (typically project_root/structures/cache/)

    Returns:
        OnlineStructureCache instance
    """
    from quantumvitas.io.online_cache import OnlineStructureCache
    return OnlineStructureCache(cache_dir)


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

