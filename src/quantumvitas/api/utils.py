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
        metadata = ResourceMeta.from_dict(metadata, kind="structure")
    
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

