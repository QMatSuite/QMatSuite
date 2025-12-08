"""
Resource management for QuantumVITAS.

Provides functionality to access workflow templates and structure library
from resources/ directory. Step templates have been replaced with in-code defaults.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from quantumvitas.core.resources import generate_resource_id as generate_ulid

# Find resources directory relative to this file's location
# resources/ is at the root of the repo, not in src/
_PACKAGE_ROOT = Path(__file__).parent.parent.parent.parent  # src/quantumvitas/core -> root
RESOURCES_DIR = _PACKAGE_ROOT / "resources"


def get_template_path(category: str, name: str) -> Optional[Path]:
    """
    Get path to a template.
    
    For workflow templates, reads from resources/workflow_templates/ only.
    For structures, uses get_structure_library_path (resources/structure_library/ only).
    
    Args:
        category: One of 'workflow', 'structure'
        name: Template name
        
    Returns:
        Path to template or None if not found
    """
    if category == "workflow":
        # Only read from resources/ (no fallback)
        resources_dir = RESOURCES_DIR / "workflow_templates" / name
        if resources_dir.exists() and resources_dir.is_dir():
            return resources_dir
        return None
    elif category == "structure":
        # Use get_structure_library_path for structure (resources/ only)
        return get_structure_library_path(name)
    else:
        # Other categories no longer supported
        return None


def list_workflow_templates() -> List[Dict[str, Any]]:
    """
    List available workflow templates with metadata.
    
    Reads from resources/workflow_templates/ only.
    
    Returns:
        List of dicts, each containing:
        - name: Template name
        - path: Template path
        - description: Optional description
        - n_steps: Number of steps
        - step_types: List of step types
    """
    template_dir = RESOURCES_DIR / "workflow_templates"
    if not template_dir.exists():
        return []
    
    templates = []
    for tpl_dir in template_dir.iterdir():
        if not tpl_dir.is_dir():
            continue
        
        workflow_yaml = tpl_dir / "workflow.yaml"
        if not workflow_yaml.exists():
            continue
        
        try:
            with open(workflow_yaml, "r") as f:
                data = yaml.safe_load(f) or {}
            
            steps = data.get("steps", [])
            step_types = [s.get("type", "unknown") for s in steps]
            
            # Try to get description from meta or workflow data
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
        old_id = data["meta"].get("id")
        if old_id:
            new_id = generate_ulid()
            ulid_map[old_id] = new_id
            data["meta"]["id"] = new_id
    
    # Also handle __qv_meta__ for structure JSON
    if "__qv_meta__" in data and isinstance(data["__qv_meta__"], dict):
        old_id = data["__qv_meta__"].get("id")
        if old_id:
            new_id = generate_ulid()
            ulid_map[old_id] = new_id
            data["__qv_meta__"]["id"] = new_id


def _update_parent_workflow_ids(data: Dict[str, Any], ulid_map: Dict[str, str]) -> None:
    """Update parent_workflow_id references using the ULID map."""
    if "parent_workflow_id" in data:
        old_id = data["parent_workflow_id"]
        if old_id in ulid_map:
            data["parent_workflow_id"] = ulid_map[old_id]


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


def _copy_workflow_from_path(
    source_path: Path,
    dest_dir: Path,
    project_root: Path,
    new_name: Optional[str] = None,
    structure: Optional[str] = None,
    workflow_ulid: Optional[str] = None,
) -> tuple[Path, Set[str], str]:
    """
    Internal: Copy workflow from a source path to destination.
    
    Handles both old format (with workflow: section) and new format (with meta: section).
    
    Returns:
        Tuple of (workflow.yaml path, set of structure names needed, workflow ULID)
    """
    from quantumvitas.core.resources import slugify
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    ulid_map: Dict[str, str] = {}
    structures_needed: Set[str] = set()
    
    # First, read workflow.yaml to get the workflow ULID
    workflow_yaml_src = source_path / "workflow.yaml"
    with open(workflow_yaml_src, "r") as f:
        workflow_data = yaml.safe_load(f)
    
    # Use provided ULID or generate new one
    new_id = workflow_ulid or generate_ulid()
    
    # Determine the new name and slug
    if new_name:
        final_name = new_name
        final_slug = slugify(new_name)
    else:
        # Use template name
        meta = workflow_data.get("meta", {})
        final_name = meta.get("name") or workflow_data.get("id") or dest_dir.name
        final_slug = meta.get("slug") or slugify(final_name)
    
    # Get old ID for mapping (from meta or top-level id field)
    meta = workflow_data.get("meta", {})
    old_id = meta.get("id") or workflow_data.get("id", "")
    if old_id:
        ulid_map[old_id] = new_id
    
    # Determine workflow path relative to project
    workflow_path = f"workflows/{final_slug}"
    
    # Update the meta section (new format)
    workflow_data["meta"] = {
        "id": new_id,
        "name": final_name,
        "slug": final_slug,
        "path": workflow_path,
        "kind": "workflow",
    }
    
    # Remove old-format id field if present (replaced by meta.id)
    if "id" in workflow_data and workflow_data["id"] != new_id:
        del workflow_data["id"]
    
    # Handle structure - check both new format (top-level) and old format (workflow section)
    workflow_section = workflow_data.get("workflow", {})
    template_structure = workflow_data.get("structure") or workflow_section.get("structure")
    
    if structure:
        # New format: structure at top level
        workflow_data["structure"] = structure
        # Also update old format section if present
        if "workflow" in workflow_data:
            workflow_data["workflow"]["structure"] = structure
    elif template_structure:
        structures_needed.add(template_structure)
    
    # Copy step files
    steps_src_dir = source_path / "steps"
    steps_dest_dir = dest_dir / "steps"
    if steps_src_dir.exists():
        steps_dest_dir.mkdir(parents=True, exist_ok=True)
        for step_file in steps_src_dir.glob("*.step.yaml"):
            with open(step_file, "r") as f:
                step_data = yaml.safe_load(f)
            
            # Regenerate step ULID
            _regenerate_ulids_in_meta(step_data, ulid_map)
            
            # Update parent_workflow_id
            if "parent_workflow_id" in step_data:
                step_data["parent_workflow_id"] = new_id
            
            # Update structure if provided
            if structure:
                step_data["structure"] = structure
            elif step_data.get("structure"):
                structures_needed.add(step_data["structure"])
            
            # Update path in meta
            if "meta" in step_data:
                rel_path = f"workflows/{final_slug}/steps/{step_file.name}"
                step_data["meta"]["path"] = rel_path
            
            with open(steps_dest_dir / step_file.name, "w") as f:
                yaml.safe_dump(step_data, f, default_flow_style=False, sort_keys=False)
    
    # Copy raw input files if they exist
    raw_src_dir = source_path / "raw"
    if raw_src_dir.exists():
        raw_dest_dir = dest_dir / "raw"
        shutil.copytree(raw_src_dir, raw_dest_dir, dirs_exist_ok=True)
    
    # Write workflow.yaml
    workflow_dest = dest_dir / "workflow.yaml"
    with open(workflow_dest, "w") as f:
        yaml.safe_dump(workflow_data, f, default_flow_style=False, sort_keys=False)
    
    return workflow_dest, structures_needed, new_id


def copy_workflow_template(
    template_name: str,
    dest_dir: Path,
    project_root: Path,
    new_name: Optional[str] = None,
    structure: Optional[str] = None,
    workflow_ulid: Optional[str] = None,
) -> tuple[Path, Set[str], str]:
    """
    Copy a workflow template to destination, including step files.
    
    Args:
        template_name: Template name
        dest_dir: Destination directory for workflow
        project_root: Project root directory
        new_name: Optional new name for the workflow
        structure: Optional structure name to use (overrides template)
        workflow_ulid: Optional ULID to use for the workflow (for parent_workflow_id in steps)
        
    Returns:
        Tuple of (workflow.yaml path, set of structure names needed, workflow ULID)
    """
    source_path = get_template_path("workflow", template_name)
    if not source_path:
        raise ValueError(f"Workflow template '{template_name}' not found")
    
    return _copy_workflow_from_path(
        source_path=source_path,
        dest_dir=dest_dir,
        project_root=project_root,
        new_name=new_name,
        structure=structure,
        workflow_ulid=workflow_ulid,
    )



