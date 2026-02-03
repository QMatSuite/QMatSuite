"""
Resource management for QuantumVITAS.

Provides functionality to access calculation templates and structure library
from resources/ directory. Step templates have been replaced with in-code defaults.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set



from quantumvitas.core.resources import generate_resource_id as generate_ulid

# Find resources directory relative to this file's location
# resources/ is at the root of the repo, not in src/
_PACKAGE_ROOT = Path(__file__).parent.parent.parent.parent  # src/quantumvitas/core -> root
RESOURCES_DIR = _PACKAGE_ROOT / "resources"


def get_template_path(category: str, name: str) -> Optional[Path]:
    """
    Get path to a template.
    
    For calculation templates, reads from resources/calculation_templates/ only.
    For structures, uses get_structure_library_path (resources/structure_library/ only).
    
    Args:
        category: One of 'calculation', 'structure'
        name: Template name
        
    Returns:
        Path to template or None if not found
    """
    if category == "calculation":
        # Only read from resources/ (no fallback)
        resources_dir = RESOURCES_DIR / "calculation_templates" / name
        if resources_dir.exists() and resources_dir.is_dir():
            return resources_dir
        return None
    elif category == "structure":
        # Use get_structure_library_path for structure (resources/ only)
        return get_structure_library_path(name)
    else:
        # Other categories no longer supported
        return None


def list_calculation_templates() -> List[Dict[str, Any]]:
    """
    List available calculation templates with metadata.
    
    Reads from resources/calculation_templates/ only.
    
    Returns:
        List of dicts, each containing:
        - name: Template name
        - path: Template path
        - description: Optional description
        - n_steps: Number of steps
        - step_types: List of step types
    """
    template_dir = RESOURCES_DIR / "calculation_templates"
    if not template_dir.exists():
        return []
    
    templates = []
    for tpl_dir in template_dir.iterdir():
        if not tpl_dir.is_dir():
            continue
        
        calculation_yaml = tpl_dir / "calculation.yaml"
        if not calculation_yaml.exists():
            continue
        
        try:
            from quantumvitas.core.yamldoc import CalcDoc
            data = CalcDoc.load(calculation_yaml).to_dict()
            
            steps = data.get("steps", [])
            step_types = [s.get("type", "unknown") for s in steps]
            
            # Try to get description from meta or calculation data
            meta = data.get("meta", {})
            description = meta.get("description") or data.get("description")
            
            templates.append({
                "name": tpl_dir.name,
                "path": str(tpl_dir),
                "description": description,
                "n_steps": len(steps),
                "step_types": step_types,
            })
        except Exception:
            # Skip templates with parse errors
            continue
    
    return templates


def list_structure_library() -> List[str]:
    """
    List available structures in the structure library.
    
    Reads from resources/structure_library/ only.
    
    Returns:
        List of structure names (without .json extension)
    """
    struct_dir = RESOURCES_DIR / "structure_library"
    if not struct_dir.exists():
        return []
    
    return [f.stem for f in struct_dir.glob("*.json")]


def get_structure_library_path(name: str) -> Optional[Path]:
    """
    Get path to a structure in the structure library.
    
    Reads from resources/structure_library/ only.
    
    Args:
        name: Structure name (without .json extension)
        
    Returns:
        Path to structure JSON or None if not found
    """
    struct_dir = RESOURCES_DIR / "structure_library"
    path = struct_dir / f"{name}.json"
    return path if path.exists() else None


def _regenerate_ulids_in_meta(data: Dict[str, Any], ulid_map: Dict[str, str]) -> None:
    """
    Regenerate ULIDs in meta sections and track the mapping.
    """
    if "meta" in data and isinstance(data["meta"], dict):
        old_id = data["meta"].get("ulid")
        if old_id:
            new_id = generate_ulid()
            ulid_map[old_id] = new_id
            data["meta"]["ulid"] = new_id
    
    # Also handle __qv_meta__ for structure JSON
    if "__qv_meta__" in data and isinstance(data["__qv_meta__"], dict):
        old_id = data["__qv_meta__"].get("ulid")
        if old_id:
            new_id = generate_ulid()
            ulid_map[old_id] = new_id
            data["__qv_meta__"]["ulid"] = new_id


def _update_parent_calculation_ids(data: Dict[str, Any], ulid_map: Dict[str, str]) -> None:
    """Update parent_calculation_id references using the ULID map."""
    if "parent_calculation_id" in data:
        old_id = data["parent_calculation_id"]
        if old_id in ulid_map:
            data["parent_calculation_id"] = ulid_map[old_id]


def copy_structure_template(
    template_name: str,
    dest_dir: Path,
    new_name: Optional[str] = None,
) -> Path:
    """
    Copy a structure template to destination.
    
    Args:
        template_name: Template name or path to .json file
        dest_dir: Destination directory
        new_name: Optional new name for the structure
        
    Returns:
        Path to copied structure file
    """
    # Check if it's a direct file path
    source_path = Path(template_name)
    if source_path.exists() and source_path.suffix == ".json":
        # Direct file import
        pass
    else:
        # Look up in templates
        source_path = get_template_path("structure", template_name)
        if not source_path:
            raise ValueError(f"Structure template '{template_name}' not found")
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Load and modify the structure
    with open(source_path, "r") as f:
        data = json.load(f)
    
    # Regenerate ULID
    ulid_map: Dict[str, str] = {}
    _regenerate_ulids_in_meta(data, ulid_map)
    
    # Update name if provided
    if new_name and "__qv_meta__" in data:
        from quantumvitas.core.resources import slugify
        data["__qv_meta__"]["name"] = new_name
        data["__qv_meta__"]["slug"] = slugify(new_name)
    
    # Determine destination filename
    if new_name:
        from quantumvitas.core.resources import slugify
        dest_name = slugify(new_name) + ".json"
    elif "__qv_meta__" in data:
        dest_name = data["__qv_meta__"]["slug"] + ".json"
    else:
        dest_name = source_path.name
    
    dest_path = dest_dir / dest_name
    
    # Update path in meta
    if "__qv_meta__" in data:
        data["__qv_meta__"]["path"] = f"structures/{dest_name}"
    
    with open(dest_path, "w") as f:
        json.dump(data, f, indent=2)
    
    return dest_path


def _copy_calculation_from_path(
    source_path: Path,
    dest_dir: Path,
    project_root: Path,
    new_name: Optional[str] = None,
    structure: Optional[str] = None,
    calculation_ulid: Optional[str] = None,
) -> tuple[Path, Set[str], str]:
    """
    Internal: Copy calculation from a source path to destination.
    
    Handles both old format (with calculation: section) and new format (with meta: section).
    
    Returns:
        Tuple of (calculation.yaml path, set of structure names needed, calculation ULID)
    """
    from quantumvitas.core.resources import slugify
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    ulid_map: Dict[str, str] = {}
    structures_needed: Set[str] = set()
    
    # First, read calculation.yaml to get the calculation ULID
    calculation_yaml_src = source_path / "calculation.yaml"
    from quantumvitas.core.yamldoc import CalcDoc
    calculation_data = CalcDoc.load(calculation_yaml_src).to_dict()
    
    # Use provided ULID or generate new one
    new_id = calculation_ulid or generate_ulid()
    
    # Determine the new name and slug
    if new_name:
        final_name = new_name
        final_slug = slugify(new_name)
    else:
        # Use template name
        meta = calculation_data.get("meta", {})
        final_name = meta.get("name") or calculation_data.get("ulid") or dest_dir.name
        final_slug = meta.get("slug") or slugify(final_name)
    
    # Get old ID for mapping (from meta or top-level id field)
    meta = calculation_data.get("meta", {})
    old_id = meta.get("ulid") or calculation_data.get("ulid", "")
    if old_id:
        ulid_map[old_id] = new_id
    
    # Determine calculation path relative to project
    calculation_path = f"calculations/{final_slug}"
    
    # Update the meta section (new format)
    calculation_data["meta"] = {
        "ulid": new_id,
        "name": final_name,
        "slug": final_slug,
        "path": calculation_path,
        "kind": "calculation",
    }
    
    # Remove old-format id field if present (replaced by meta.ulid)
    if "id" in calculation_data and calculation_data["ulid"] != new_id:
        del calculation_data["ulid"]
    
    # Handle structure - check both new format (top-level) and old format (calculation section)
    calculation_section = calculation_data.get("calculation", {})
    template_structure = calculation_data.get("structure") or calculation_section.get("structure")
    
    # Resolve structure to structure_ulid (ULID) if structure selector is provided
    structure_ulid = None
    if structure:
        # Resolve structure selector to structure_ulid (ULID)
        from quantumvitas.core.resolution import resolve_structure
        from quantumvitas.core.project_utils import load_project_config
        try:
            config = load_project_config(project_root)
            resolved = resolve_structure(project_root, structure, config)
            structure_ulid = resolved.meta.ulid
        except Exception:
            # If resolution fails, structure_ulid remains None (will be set later if structure is added)
            pass
    elif template_structure:
        structures_needed.add(template_structure)
        # Try to resolve template structure to structure_ulid if it exists in project
        from quantumvitas.core.resolution import resolve_structure
        from quantumvitas.core.project_utils import load_project_config
        try:
            config = load_project_config(project_root)
            resolved = resolve_structure(project_root, template_structure, config)
            structure_ulid = resolved.meta.ulid
        except Exception:
            # Structure not found in project yet - will be copied from template
            pass
    
    # Set structure_ulid (ULID) if we have it
    # Remove any legacy structure selector fields (violates DAG + ID-only constitution)
    if structure_ulid:
        calculation_data["structure_ulid"] = structure_ulid
        # Remove legacy structure selector fields (DAG + ID-only constitution)
        calculation_data.pop("structure", None)
        calculation_data.pop("structure_name", None)
        if "calculation" in calculation_data:
            calculation_data["calculation"]["structure_ulid"] = structure_ulid
            calculation_data["calculation"].pop("structure", None)
            calculation_data["calculation"].pop("structure_name", None)
    else:
        # If no structure_ulid, remove any structure selector fields
        calculation_data.pop("structure", None)
        calculation_data.pop("structure_name", None)
        if "calculation" in calculation_data:
            calculation_data["calculation"].pop("structure", None)
            calculation_data["calculation"].pop("structure_name", None)
    
    # Copy step files
    steps_src_dir = source_path / "steps"
    steps_dest_dir = dest_dir / "steps"
    if steps_src_dir.exists():
        steps_dest_dir.mkdir(parents=True, exist_ok=True)
        for step_file in steps_src_dir.glob("*.step.yaml"):
            from quantumvitas.core.yamldoc import StepDoc
            step_data = StepDoc.load(step_file).to_dict()
            
            # Regenerate step ULID
            _regenerate_ulids_in_meta(step_data, ulid_map)
            
            # Track structure name if present (for copying structure template) BEFORE removing it
            structure_name = step_data.get("structure")
            if structure_name:
                structures_needed.add(structure_name)
            
            # DAG + ID-only model: Step YAML must NOT contain structure, structure_ulid, or parent_calculation_id
            # Remove these fields before writing
            step_data.pop("parent_calculation_id", None)
            step_data.pop("structure_ulid", None)
            step_data.pop("structure", None)
            
            # Update path in meta
            if "meta" in step_data:
                rel_path = f"calculations/{final_slug}/steps/{step_file.name}"
                step_data["meta"]["path"] = rel_path
            
            # Use StructureStepSpec.to_dict() to ensure proper serialization
            from quantumvitas.calculation.structure_steps import StructureStepSpec
            try:
                step_spec = StructureStepSpec.from_dict(step_data)
                step_dict = step_spec.to_dict()
            except Exception:
                # If parsing fails, use cleaned dict directly
                step_dict = step_data
            
            from quantumvitas.core.yamldoc import StepDoc
            from quantumvitas.core.yaml_io import save_yaml_doc

            step_doc = StepDoc(step_dict)
            save_yaml_doc(step_doc, steps_dest_dir / step_file.name, skip_journal=True)
    
    # Copy raw input files if they exist
    raw_src_dir = source_path / "raw"
    if raw_src_dir.exists():
        raw_dest_dir = dest_dir / "raw"
        shutil.copytree(raw_src_dir, raw_dest_dir, dirs_exist_ok=True)
    
    # Phase 2: Ensure structure_kind and engine_family are set (defaults if missing)
    if "structure_kind" not in calculation_data:
        calculation_data["structure_kind"] = "periodic"
    if "engine_family" not in calculation_data:
        structure_kind = calculation_data.get("structure_kind", "periodic")
        if structure_kind == "molecule":
            calculation_data["engine_family"] = "pyscf"
        else:
            calculation_data["engine_family"] = "qe"
    
    # Write calculation.yaml
    from quantumvitas.core.yamldoc import CalcDoc
    from quantumvitas.core.yaml_io import save_yaml_doc

    calculation_dest = dest_dir / "calculation.yaml"
    calc_doc = CalcDoc(calculation_data)
    save_yaml_doc(calc_doc, calculation_dest, skip_journal=True)
    
    return calculation_dest, structures_needed, new_id


def copy_calculation_template(
    template_name: str,
    dest_dir: Path,
    project_root: Path,
    new_name: Optional[str] = None,
    structure: Optional[str] = None,
    calculation_ulid: Optional[str] = None,
) -> tuple[Path, Set[str], str]:
    """
    Copy a calculation template to destination, including step files.
    
    Args:
        template_name: Template name
        dest_dir: Destination directory for calculation
        project_root: Project root directory
        new_name: Optional new name for the calculation
        structure: Optional structure name to use (overrides template)
        calculation_ulid: Optional ULID to use for the calculation (for parent_calculation_id in steps)
        
    Returns:
        Tuple of (calculation.yaml path, set of structure names needed, calculation ULID)
    """
    source_path = get_template_path("calculation", template_name)
    if not source_path:
        raise ValueError(f"Calculation template '{template_name}' not found")
    
    return _copy_calculation_from_path(
        source_path=source_path,
        dest_dir=dest_dir,
        project_root=project_root,
        new_name=new_name,
        structure=structure,
        calculation_ulid=calculation_ulid,
    )



