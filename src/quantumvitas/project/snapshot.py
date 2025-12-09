"""
Project snapshot format for exporting and importing complete projects.

A snapshot is a single YAML file that contains all project metadata, structures,
workflows, and step specifications needed to recreate a project. Pseudopotential
filenames are preserved but file contents are NOT embedded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from quantumvitas.core.models import (
    ProjectModel,
    StructureModel,
    WorkflowModel,
    load_project,
    load_structure_model,
    load_workflow,
    save_project,
    save_structure_model,
    save_workflow,
)
from quantumvitas.core.resources import (
    ResourceMeta,
    ensure_relative_path,
    generate_resource_id,
    slugify,
)
from quantumvitas.workflow.structure_steps import StructureStepSpec

# Structure file format constants
STRUCTURE_META_KEY = "__qv_meta__"
STRUCTURE_DATA_KEY = "structure"


@dataclass
class ProjectSnapshot:
    """
    Snapshot of a complete QuantumVITAS project.
    
    Contains all metadata, structures, workflows, and steps needed to
    recreate the project. ULIDs are preserved for reference but will be
    regenerated when materializing the project.
    
    The `meta` field (optional) contains demo-specific metadata for gallery display:
    - id: Demo identifier (e.g., "si_bands_demo")
    - title: Display title (e.g., "Silicon band structure")
    - subtitle: Short description (e.g., "SCF → NSCF → Bands")
    - tags: List of tags (e.g., ["bands", "Si", "PW", "tutorial"])
    - recommended_analysis: Default analysis type (e.g., "bands", "dos")
    - difficulty: Difficulty level (e.g., "beginner", "intermediate", "advanced")
    """
    version: int = 1
    project: Dict[str, Any] = field(default_factory=dict)
    structures: List[Dict[str, Any]] = field(default_factory=list)
    workflows: List[Dict[str, Any]] = field(default_factory=list)
    pseudo: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: Dict[str, Any] = {
            "version": self.version,
            "project": self.project,
            "structures": self.structures,
            "workflows": self.workflows,
        }
        if self.pseudo:
            result["pseudo"] = self.pseudo
        if self.extra:
            result["extra"] = self.extra
        if self.meta:
            result["meta"] = self.meta
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectSnapshot":
        """Create ProjectSnapshot from dictionary."""
        return cls(
            version=data.get("version", 1),
            project=data.get("project", {}),
            structures=data.get("structures", []),
            workflows=data.get("workflows", []),
            pseudo=data.get("pseudo"),
            extra=data.get("extra"),
            meta=data.get("meta"),
        )


def export_project_to_snapshot(project_root: Path) -> ProjectSnapshot:
    """
    Export a project directory to a ProjectSnapshot.
    
    Reads project.qv.yml, all structures, workflows, and step specs
    and packages them into a single snapshot object.
    
    Args:
        project_root: Path to project root directory
        
    Returns:
        ProjectSnapshot containing all project data
    """
    project_root = project_root.resolve()
    
    # Load project model
    project_model = load_project(project_root)
    
    # Export project metadata
    project_data = {
        "meta": project_model.meta.to_dict(),
        "settings": project_model.settings,
    }
    
    # Export structures
    structures_data = []
    for struct_entry in project_model.structures:
        struct_path = project_root / struct_entry.file
        if struct_path.exists():
            # Get structure data (pymatgen format)
            # Handle both __qv_meta__ wrapper and direct structure dict
            struct_file_data = json.loads(struct_path.read_text())
            if STRUCTURE_META_KEY in struct_file_data and STRUCTURE_DATA_KEY in struct_file_data:
                structure_data = struct_file_data[STRUCTURE_DATA_KEY]
            else:
                # Direct structure dict (remove meta if present)
                structure_data = {k: v for k, v in struct_file_data.items() if k not in ("meta", STRUCTURE_META_KEY)}
            
            # Use struct_entry.meta (from project.qv.yml) for name, as it has the correct name
            # The structure file might have name=slug if it was created with old format
            structures_data.append({
                "meta": struct_entry.meta.to_dict(),
                "data": structure_data,
            })
    
    # Export workflows and their steps
    workflows_data = []
    for workflow_entry in project_model.workflows:
        workflow_path = project_root / workflow_entry.meta.path / "workflow.yaml"
        if not workflow_path.exists():
            continue
        
        workflow_model = load_workflow(workflow_path, project_root)
        workflow_dir = workflow_path.parent
        
        # Export workflow metadata
        # Use workflow_entry.meta (from project.qv.yml) for name, as it has the correct name
        # workflow_model.meta might have name=slug if workflow.yaml uses old format
        workflow_meta_dict = workflow_entry.meta.to_dict()
        # But keep the path from workflow_model if it's more accurate
        if workflow_model.meta.path:
            workflow_meta_dict["path"] = workflow_model.meta.path
        
        workflow_dict = {
            "meta": workflow_meta_dict,
            "mode": workflow_model.mode,
            "working_dir": workflow_model.working_dir,
            "steps": [],
        }
        # Export structure_id (canonical reference)
        if workflow_model.structure_id:
            workflow_dict["structure_id"] = workflow_model.structure_id
            # Optionally include structure_name for display
            if workflow_model.structure_name:
                workflow_dict["structure_name"] = workflow_model.structure_name
        # Keep structure selector for backwards compatibility
        if workflow_model.structure:
            workflow_dict["structure"] = workflow_model.structure
        
        # Export each step
        for step_entry in workflow_model.steps:
            if not step_entry.step_file:
                continue
            
            step_path = workflow_dir / step_entry.step_file
            if not step_path.exists():
                continue
            
            step_spec = StructureStepSpec.from_yaml(step_path)
            step_dict = step_spec.to_dict()
            
            workflow_dict["steps"].append(step_dict)
        
        workflows_data.append(workflow_dict)
    
    # Export pseudo file list (filenames only, no content)
    pseudo_data = None
    pseudo_dir = project_root / "pseudo"
    if pseudo_dir.exists() and pseudo_dir.is_dir():
        pseudo_files = [p.name for p in pseudo_dir.iterdir() if p.is_file()]
        if pseudo_files:
            pseudo_data = {
                "directory": "pseudo",
                "files": sorted(pseudo_files),
            }
    
    return ProjectSnapshot(
        version=1,
        project=project_data,
        structures=structures_data,
        workflows=workflows_data,
        pseudo=pseudo_data,
    )


def materialize_project_from_snapshot(
    snapshot: ProjectSnapshot,
    parent_dir: Path,
    new_project_name: Optional[str] = None,
) -> Path:
    """
    Create a new project directory from a ProjectSnapshot.
    
    Generates new ULIDs for all resources and rewrites references
    to maintain consistency.
    
    Args:
        snapshot: ProjectSnapshot to materialize
        parent_dir: Directory where the new project will be created
        new_project_name: Optional name for the new project (defaults to snapshot name)
        
    Returns:
        Path to the new project root
    """
    parent_dir = parent_dir.resolve()
    
    # Determine project name and directory
    project_meta = snapshot.project.get("meta", {})
    original_name = project_meta.get("name", "project")
    project_name = new_project_name or original_name
    project_slug = slugify(project_name)
    
    # Find a unique directory name (add suffix if needed)
    project_dir = parent_dir / project_slug
    if project_dir.exists():
        # Directory exists - find unique name with suffix
        suffix = 2
        while True:
            candidate = parent_dir / f"{project_slug}-{suffix}"
            if not candidate.exists():
                project_dir = candidate
                project_name = f"{project_name}-{suffix}"
                project_slug = f"{project_slug}-{suffix}"
                break
            suffix += 1
            if suffix > 100:  # Safety limit
                raise RuntimeError(f"Could not find unique project name for {project_slug}")
    
    project_dir.mkdir(parents=True, exist_ok=False)
    
    # Build ULID mapping: old_id -> new_id
    id_mapping: Dict[str, str] = {}
    
    # Map project ID
    old_project_id = project_meta.get("id")
    if old_project_id:
        new_project_id = generate_resource_id()
        id_mapping[old_project_id] = new_project_id
    
    # Map structure IDs
    structure_slug_to_new_id: Dict[str, str] = {}
    for struct_data in snapshot.structures:
        struct_meta = struct_data.get("meta", {})
        old_struct_id = struct_meta.get("id")
        struct_slug = struct_meta.get("slug") or slugify(struct_meta.get("name", "structure"))
        
        if old_struct_id:
            new_struct_id = generate_resource_id()
            id_mapping[old_struct_id] = new_struct_id
            structure_slug_to_new_id[struct_slug] = new_struct_id
    
    # Map workflow IDs
    workflow_slug_to_new_id: Dict[str, str] = {}
    for workflow_data in snapshot.workflows:
        workflow_meta = workflow_data.get("meta", {})
        old_workflow_id = workflow_meta.get("id")
        workflow_slug = workflow_meta.get("slug") or slugify(workflow_meta.get("name", "workflow"))
        
        if old_workflow_id:
            new_workflow_id = generate_resource_id()
            id_mapping[old_workflow_id] = new_workflow_id
            workflow_slug_to_new_id[workflow_slug] = new_workflow_id
    
    # Map step IDs
    for workflow_data in snapshot.workflows:
        for step_data in workflow_data.get("steps", []):
            step_meta = step_data.get("meta", {})
            old_step_id = step_meta.get("id")
            if old_step_id:
                new_step_id = generate_resource_id()
                id_mapping[old_step_id] = new_step_id
    
    # Create project.qv.yml
    new_project_meta = ResourceMeta(
        id=new_project_id,
        name=project_name,
        slug=project_slug,
        path=".",
        kind="project",
    )
    
    project_model = ProjectModel(
        meta=new_project_meta,
        root=project_dir,
        structures=[],
        workflows=[],
        settings=snapshot.project.get("settings", {}),
    )
    
    # Create structures
    structures_dir = project_dir / "structures"
    structures_dir.mkdir(exist_ok=True)
    
    for struct_data in snapshot.structures:
        struct_meta = struct_data.get("meta", {})
        struct_name = struct_meta.get("name", "structure")
        struct_slug = struct_meta.get("slug") or slugify(struct_name)
        old_struct_id = struct_meta.get("id")
        new_struct_id = id_mapping.get(old_struct_id, generate_resource_id())
        
        # Create structure file
        struct_file = structures_dir / f"{struct_slug}.json"
        
        # Prepare structure JSON with meta wrapper
        structure_json = {
            STRUCTURE_META_KEY: {
                "id": new_struct_id,
                "name": struct_name,
                "slug": struct_slug,
                "path": f"structures/{struct_slug}.json",
                "kind": "structure",
            },
            STRUCTURE_DATA_KEY: struct_data.get("data", {}),
        }
        
        struct_file.write_text(json.dumps(structure_json, indent=2))
        
        # Add to project model
        from quantumvitas.core.models import StructureEntry
        struct_entry = StructureEntry(
            meta=ResourceMeta(
                id=new_struct_id,
                name=struct_name,
                slug=struct_slug,
                path=f"structures/{struct_slug}.json",
                kind="structure",
            ),
            file=f"structures/{struct_slug}.json",
            format="auto",
        )
        project_model.structures.append(struct_entry)
    
    # Create workflows and steps
    workflows_dir = project_dir / "workflows"
    workflows_dir.mkdir(exist_ok=True)
    
    for workflow_data in snapshot.workflows:
        workflow_meta = workflow_data.get("meta", {})
        workflow_name = workflow_meta.get("name") or workflow_meta.get("slug") or "workflow"
        workflow_slug = workflow_meta.get("slug") or slugify(workflow_name)
        old_workflow_id = workflow_meta.get("id")
        new_workflow_id = id_mapping.get(old_workflow_id, generate_resource_id())
        
        # Create workflow directory
        workflow_path = workflows_dir / workflow_slug
        workflow_path.mkdir(exist_ok=True)
        steps_dir = workflow_path / "steps"
        steps_dir.mkdir(exist_ok=True)
        (workflow_path / "raw").mkdir(exist_ok=True)
        
        # Resolve structure reference from snapshot
        # New format: structure_id (canonical)
        workflow_structure_id = workflow_data.get("structure_id")
        workflow_structure_name = workflow_data.get("structure_name")
        # Legacy format: structure selector
        workflow_structure_selector = workflow_data.get("structure")
        
        # If structure_id is present, map it to the new structure ID
        if workflow_structure_id:
            # Find the structure in the snapshot by old ID
            structure_found = False
            for struct_data in snapshot.structures:
                struct_meta = struct_data.get("meta", {})
                if struct_meta.get("id") == workflow_structure_id:
                    # Map to new structure ID
                    new_structure_id = id_mapping.get(workflow_structure_id)
                    if new_structure_id:
                        workflow_structure_id = new_structure_id
                        workflow_structure_name = struct_meta.get("name")
                    structure_found = True
                    break
            if not structure_found:
                # Structure ID not found in snapshot - this shouldn't happen, but handle gracefully
                workflow_structure_id = None
        
        # If only structure selector is present (legacy), try to resolve it
        elif workflow_structure_selector:
            # Try to find structure by slug/name in the snapshot
            for struct_data in snapshot.structures:
                struct_meta = struct_data.get("meta", {})
                struct_slug = struct_meta.get("slug") or slugify(struct_meta.get("name", ""))
                struct_name = struct_meta.get("name", "")
                old_struct_id = struct_meta.get("id")
                
                if (struct_slug == workflow_structure_selector or 
                    struct_name.lower() == workflow_structure_selector.lower()):
                    # Found matching structure - use its new ID
                    if old_struct_id:
                        workflow_structure_id = id_mapping.get(old_struct_id)
                        workflow_structure_name = struct_name
                    break
        
        # Create workflow.yaml
        workflow_model = WorkflowModel(
            meta=ResourceMeta(
                id=new_workflow_id,
                name=workflow_name,
                slug=workflow_slug,
                path=f"workflows/{workflow_slug}",
                kind="workflow",
            ),
            structure_id=workflow_structure_id,
            structure_name=workflow_structure_name,
            structure=workflow_structure_selector,  # Keep for backwards compat
            mode=workflow_data.get("mode", "normal"),
            working_dir=workflow_data.get("working_dir", "raw"),
            steps=[],
        )
        
        # Create step files
        for step_data in workflow_data.get("steps", []):
            step_meta = step_data.get("meta", {})
            step_name = step_meta.get("name", step_data.get("step_type", "step"))
            step_slug = step_meta.get("slug") or slugify(step_name)
            old_step_id = step_meta.get("id")
            new_step_id = id_mapping.get(old_step_id, generate_resource_id())
            
            # Create step spec with new IDs
            step_spec_dict = dict(step_data)
            step_spec_dict["meta"] = {
                "id": new_step_id,
                "name": step_name,
                "slug": step_slug,
                "path": f"workflows/{workflow_slug}/steps/{step_slug}.step.yaml",
                "kind": "step",
            }
            # Update parent_workflow_id reference
            if step_spec_dict.get("parent_workflow_id"):
                step_spec_dict["parent_workflow_id"] = new_workflow_id
            
            # Resolve structure reference from snapshot
            # New format: structure_id (canonical)
            step_structure_id = step_spec_dict.get("structure_id")
            step_structure_selector = step_spec_dict.get("structure")
            
            # If structure_id is present, map it to the new structure ID
            if step_structure_id:
                new_structure_id = id_mapping.get(step_structure_id)
                if new_structure_id:
                    step_spec_dict["structure_id"] = new_structure_id
                else:
                    # Structure ID not found in mapping - this shouldn't happen, but handle gracefully
                    step_spec_dict.pop("structure_id", None)
            # If only structure selector is present (legacy), try to resolve it
            elif step_structure_selector:
                # Try to find structure by slug/name in the snapshot
                for struct_data in snapshot.structures:
                    struct_meta = struct_data.get("meta", {})
                    struct_slug = struct_meta.get("slug") or slugify(struct_meta.get("name", ""))
                    struct_name = struct_meta.get("name", "")
                    old_struct_id = struct_meta.get("id")
                    
                    if (struct_slug == step_structure_selector or 
                        struct_name.lower() == step_structure_selector.lower()):
                        # Found matching structure - use its new ID
                        if old_struct_id:
                            step_spec_dict["structure_id"] = id_mapping.get(old_struct_id)
                            # Remove structure selector since we now have structure_id
                            step_spec_dict.pop("structure", None)
                        break
            
            # If step still has no structure_id, inherit from workflow
            if not step_spec_dict.get("structure_id"):
                if workflow_structure_id:
                    step_spec_dict["structure_id"] = workflow_structure_id
                    # Remove structure selector since we now have structure_id
                    step_spec_dict.pop("structure", None)
                elif step_structure_selector:
                    # Keep structure selector for backwards compat if we can't resolve to ID
                    pass  # Already set above
                elif workflow_data.get("structure"):
                    # Fallback: use workflow structure selector
                    step_spec_dict["structure"] = workflow_data.get("structure")
            
            # Write step file
            step_file = steps_dir / f"{step_slug}.step.yaml"
            step_file.write_text(yaml.safe_dump(step_spec_dict, sort_keys=False))
            
            # Add to workflow steps list using step_id (ULID) from step meta
            from quantumvitas.core.models import WorkflowStepEntry
            step_meta = step_spec_dict.get("meta", {})
            step_id = step_meta.get("id") or step_spec_dict.get("id")
            workflow_model.steps.append(WorkflowStepEntry(
                step_id=step_id,  # Use ULID from step meta (canonical reference)
                type=step_data.get("step_type"),
                step_file=f"steps/{step_slug}.step.yaml",
            ))
        
        # Save workflow.yaml
        save_workflow(workflow_model, workflow_path / "workflow.yaml")
        
        # Add to project model
        from quantumvitas.core.models import WorkflowEntry
        workflow_entry = WorkflowEntry(
            meta=ResourceMeta(
                id=new_workflow_id,
                name=workflow_name,
                slug=workflow_slug,
                path=f"workflows/{workflow_slug}",
                kind="workflow",
            ),
        )
        project_model.workflows.append(workflow_entry)
    
    # Save project.qv.yml
    save_project(project_model, project_dir)
    
    # Create pseudo directory (empty, just the directory structure)
    if snapshot.pseudo:
        pseudo_dir = project_dir / snapshot.pseudo.get("directory", "pseudo")
        pseudo_dir.mkdir(exist_ok=True)
        # Note: We do NOT create the pseudo files themselves, only the directory
        # The snapshot format documents which files are expected but doesn't embed content
    
    return project_dir

