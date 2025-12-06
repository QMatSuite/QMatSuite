"""
Template management for QuantumVITAS.

Provides functionality to copy project/workflow/step/structure templates
with automatic ULID regeneration and proper path updates.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from quantumvitas.core.resources import generate_resource_id as generate_ulid

# Find templates directory relative to this file's location
# templates/ is at the root of the repo, not in src/
_PACKAGE_ROOT = Path(__file__).parent.parent.parent.parent  # src/quantumvitas/core -> root
TEMPLATES_DIR = _PACKAGE_ROOT / "templates"


def list_templates(category: str) -> List[str]:
    """
    List available templates for a category.
    
    Args:
        category: One of 'project', 'workflow', 'step', 'structure'
        
    Returns:
        List of template names available
    """
    template_dir = TEMPLATES_DIR / category
    if not template_dir.exists():
        return []
    
    if category == "structure":
        # Structure templates are .json files
        return [f.stem for f in template_dir.glob("*.json")]
    elif category == "step":
        # Step templates are in steps/ subfolder
        steps_dir = template_dir / "steps"
        if steps_dir.exists():
            return [f.stem.replace(".step", "") for f in steps_dir.glob("*.step.yaml")]
        return []
    else:
        # project/workflow templates are directories
        return [d.name for d in template_dir.iterdir() if d.is_dir()]


def get_template_path(category: str, name: str) -> Optional[Path]:
    """
    Get path to a template.
    
    Args:
        category: One of 'project', 'workflow', 'step', 'structure'
        name: Template name
        
    Returns:
        Path to template or None if not found
    """
    template_dir = TEMPLATES_DIR / category
    
    if category == "structure":
        path = template_dir / f"{name}.json"
        return path if path.exists() else None
    elif category == "step":
        path = template_dir / "steps" / f"{name}.step.yaml"
        return path if path.exists() else None
    else:
        path = template_dir / name
        return path if path.exists() and path.is_dir() else None


def list_workflow_templates() -> List[Dict[str, Any]]:
    """
    List available workflow templates with metadata.
    
    Returns:
        List of dicts, each containing:
        - name: Template name
        - path: Template path
        - description: Optional description
        - n_steps: Number of steps
        - step_types: List of step types
    """
    template_dir = TEMPLATES_DIR / "workflow"
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


def copy_step_template(
    template_name: str,
    dest_dir: Path,
    new_name: Optional[str] = None,
    parent_workflow_id: Optional[str] = None,
    structure: Optional[str] = None,
) -> Path:
    """
    Copy a step template to destination.
    
    Args:
        template_name: Template name
        dest_dir: Destination directory
        new_name: Optional new name for the step
        parent_workflow_id: Optional parent workflow ID to set
        structure: Optional structure name to set
        
    Returns:
        Path to copied step file
    """
    source_path = get_template_path("step", template_name)
    if not source_path:
        raise ValueError(f"Step template '{template_name}' not found")
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    with open(source_path, "r") as f:
        data = yaml.safe_load(f)
    
    # Regenerate ULID
    ulid_map: Dict[str, str] = {}
    _regenerate_ulids_in_meta(data, ulid_map)
    
    # Update name if provided
    if new_name and "meta" in data:
        from quantumvitas.core.resources import slugify
        data["meta"]["name"] = new_name
        data["meta"]["slug"] = slugify(new_name)
    
    # Update structure if provided
    if structure:
        data["structure"] = structure
    
    # Update parent workflow ID if provided
    if parent_workflow_id:
        data["parent_workflow_id"] = parent_workflow_id
    
    # Determine destination filename
    if new_name:
        from quantumvitas.core.resources import slugify
        dest_name = f"{slugify(new_name)}.step.yaml"
    elif "meta" in data:
        dest_name = f"{data['meta']['slug']}.step.yaml"
    else:
        dest_name = source_path.name
    
    dest_path = dest_dir / dest_name
    
    # Update path in meta
    if "meta" in data:
        data["meta"]["path"] = str(dest_path.relative_to(dest_dir.parent.parent))
    
    with open(dest_path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    
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
    
    Returns:
        Tuple of (workflow.yaml path, set of structure names needed, workflow ULID)
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    ulid_map: Dict[str, str] = {}
    structures_needed: Set[str] = set()
    
    # First, read workflow.yaml to get the workflow ULID
    workflow_yaml_src = source_path / "workflow.yaml"
    with open(workflow_yaml_src, "r") as f:
        workflow_data = yaml.safe_load(f)
    
    # Use provided ULID or generate new one
    new_id = workflow_ulid or generate_ulid()
    
    # Track old ID for mapping
    if "id" in workflow_data:
        old_id = workflow_data.get("id", "")
        ulid_map[old_id] = new_id
    
    # Update workflow id (slug) if new_name provided, otherwise keep original
    if new_name:
        workflow_data["id"] = new_name
    
    # Update or track structure
    workflow_section = workflow_data.get("workflow", {})
    template_structure = workflow_section.get("structure")
    if structure:
        workflow_section["structure"] = structure
        workflow_data["workflow"] = workflow_section
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
                rel_path = f"workflows/{dest_dir.name}/steps/{step_file.name}"
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


def copy_project_template(
    template_name: str,
    dest_dir: Path,
    new_name: Optional[str] = None,
) -> Path:
    """
    Copy a project template to destination.
    
    Args:
        template_name: Template name
        dest_dir: Destination directory
        new_name: Optional new project name
        
    Returns:
        Path to project.qv.yml
    """
    source_path = get_template_path("project", template_name)
    if not source_path:
        raise ValueError(f"Project template '{template_name}' not found")
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    ulid_map: Dict[str, str] = {}
    
    # Pre-read project.qv.yml to get old workflow/structure ULIDs for mapping
    project_yaml_src = source_path / "project.qv.yml"
    old_workflow_ulids: Dict[str, str] = {}  # Map workflow slug/path -> old ULID
    if project_yaml_src.exists():
        with open(project_yaml_src, "r") as f:
            old_project_data = yaml.safe_load(f) or {}
        for wf_entry in old_project_data.get("workflows", []):
            wf_meta = wf_entry.get("meta") or {}
            old_ulid = wf_meta.get("id")
            wf_slug = wf_meta.get("slug") or wf_entry.get("name", "").lower().replace(" ", "-")
            if old_ulid and wf_slug:
                old_workflow_ulids[wf_slug] = old_ulid
    
    # Copy structures
    src_structures = source_path / "structures"
    if src_structures.exists():
        dest_structures = dest_dir / "structures"
        dest_structures.mkdir(parents=True, exist_ok=True)
        for struct_file in src_structures.glob("*.json"):
            with open(struct_file, "r") as f:
                data = json.load(f)
            _regenerate_ulids_in_meta(data, ulid_map)
            if "__qv_meta__" in data:
                data["__qv_meta__"]["path"] = f"structures/{struct_file.name}"
            with open(dest_structures / struct_file.name, "w") as f:
                json.dump(data, f, indent=2)
    
    # Copy workflows (recursively handle each)
    src_workflows = source_path / "workflows"
    workflow_ulids: Dict[str, str] = {}  # Map workflow name -> new ULID
    if src_workflows.exists():
        dest_workflows = dest_dir / "workflows"
        for workflow_src_dir in src_workflows.iterdir():
            if workflow_src_dir.is_dir():
                workflow_dest = dest_workflows / workflow_src_dir.name
                _, _, wf_ulid = _copy_workflow_from_path(
                    source_path=workflow_src_dir,
                    dest_dir=workflow_dest,
                    project_root=dest_dir,
                )
                workflow_ulids[workflow_src_dir.name] = wf_ulid
                # Map both directory name and old ULID to new ULID
                ulid_map[workflow_src_dir.name] = wf_ulid
                old_ulid = old_workflow_ulids.get(workflow_src_dir.name)
                if old_ulid:
                    ulid_map[old_ulid] = wf_ulid
    
    # Copy and update project.qv.yml
    project_yaml_src = source_path / "project.qv.yml"
    if project_yaml_src.exists():
        with open(project_yaml_src, "r") as f:
            project_data = yaml.safe_load(f) or {}
        
        # Update project meta
        if "meta" in project_data:
            _regenerate_ulids_in_meta(project_data, ulid_map)
            if new_name:
                from quantumvitas.core.resources import slugify
                project_data["meta"]["name"] = new_name
                project_data["meta"]["slug"] = slugify(new_name)
        
        # Update structure references
        for struct_entry in project_data.get("structures", []):
            if "meta" in struct_entry:
                old_id = struct_entry["meta"].get("id")
                if old_id in ulid_map:
                    struct_entry["meta"]["id"] = ulid_map[old_id]
        
        # Update workflow references
        for wf_entry in project_data.get("workflows", []):
            if "meta" in wf_entry:
                old_id = wf_entry["meta"].get("id")
                if old_id in ulid_map:
                    wf_entry["meta"]["id"] = ulid_map[old_id]
        
        project_yaml_dest = dest_dir / "project.qv.yml"
        with open(project_yaml_dest, "w") as f:
            yaml.safe_dump(project_data, f, default_flow_style=False, sort_keys=False)
        
        return project_yaml_dest
    
    # Create minimal project.qv.yml if template didn't have one
    project_yaml_dest = dest_dir / "project.qv.yml"
    project_data = {
        "meta": {
            "id": generate_ulid(),
            "name": new_name or dest_dir.name,
            "kind": "project",
        },
        "structures": [],
        "workflows": [],
    }
    with open(project_yaml_dest, "w") as f:
        yaml.safe_dump(project_data, f, default_flow_style=False, sort_keys=False)
    
    return project_yaml_dest

