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
        """
        Create ProjectSnapshot from dictionary.
        
        Supports both old format (project/structures/workflows at top level)
        and new minimal format (snapshot_meta + files list).
        """
        # Check for new minimal format (snapshot_meta + files)
        if "snapshot_meta" in data and "files" in data:
            # New minimal format: convert files list to old format structure
            return cls._from_minimal_format(data)
        
        # Old format: project/structures/workflows at top level
        return cls(
            version=data.get("version", 1),
            project=data.get("project", {}),
            structures=data.get("structures", []),
            workflows=data.get("workflows", []),
            pseudo=data.get("pseudo"),
            extra=data.get("extra"),
            meta=data.get("meta"),
        )
    
    @classmethod
    def _from_minimal_format(cls, data: Dict[str, Any]) -> "ProjectSnapshot":
        """
        Convert new minimal snapshot format (snapshot_meta + files) to ProjectSnapshot.
        
        The minimal format has:
        - snapshot_meta: {version, created_at, ...}
        - files: [{path: "project.qv.yml", content: "..."}, ...]
        
        We need to parse the YAML content from files to reconstruct the old format structure.
        """
        import yaml
        
        snapshot_meta = data.get("snapshot_meta", {})
        files = data.get("files", [])
        
        # Build a map of file paths to content
        file_map: Dict[str, str] = {}
        for file_entry in files:
            path = file_entry.get("path", "")
            content = file_entry.get("content", "")
            if path and content:
                file_map[path] = content
        
        # Parse project.qv.yml to get project metadata
        project_data = {}
        if "project.qv.yml" in file_map:
            try:
                project_data = yaml.safe_load(file_map["project.qv.yml"]) or {}
            except Exception:
                project_data = {}
        
        # Parse structures
        structures_data = []
        for file_path, content in file_map.items():
            if file_path.startswith("structures/") and file_path.endswith(".json"):
                try:
                    import json
                    struct_data = json.loads(content)
                    # Extract meta if present
                    meta = struct_data.get("__qv_meta__", {})
                    # Extract structure data
                    structure_data = struct_data.get("structure", struct_data)
                    structures_data.append({
                        "meta": meta,
                        "data": structure_data,
                    })
                except Exception:
                    pass  # Skip malformed structure files
        
        # Parse workflows
        workflows_data = []
        for file_path, content in file_map.items():
            if file_path.endswith("/workflow.yaml"):
                try:
                    workflow_data = yaml.safe_load(content) or {}
                    # Extract steps from step files
                    workflow_dir = file_path.rsplit("/", 1)[0]
                    steps_data = []
                    for step_path, step_content in file_map.items():
                        if step_path.startswith(workflow_dir + "/steps/") and step_path.endswith(".step.yaml"):
                            try:
                                step_data = yaml.safe_load(step_content) or {}
                                steps_data.append(step_data)
                            except Exception:
                                pass
                    workflow_data["steps"] = steps_data
                    workflows_data.append(workflow_data)
                except Exception:
                    pass  # Skip malformed workflow files
        
        return cls(
            version=snapshot_meta.get("version", 1),
            project=project_data,
            structures=structures_data,
            workflows=workflows_data,
            pseudo=None,  # Pseudo files not embedded in minimal format
            extra=None,
            meta=snapshot_meta,  # Use snapshot_meta as meta
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
    # Use structure's meta.path (ID-only model) instead of legacy file field
    structures_data = []
    for struct_entry in project_model.structures:
        # Use meta.path (canonical) or fall back to legacy file field for location
        struct_path = project_root / (struct_entry.meta.path or struct_entry.file)
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
    # Use Project.open() and Workflow.from_yaml() to load workflows (DAG + ULID model only)
    from quantumvitas.project.model import Project
    from quantumvitas.workflow.workflow import Workflow
    from quantumvitas.core.project_utils import load_project_config
    
    try:
        project = Project.open(project_root)
    except Exception:
        # Fall back to basic loading if Project.open() fails
        project = None
    
    # Load raw config to check for legacy name fields in workflow entries
    raw_config = load_project_config(project_root)
    # Build mapping from workflow ID to raw entry (handle workflow_id, id, and meta.id keys)
    raw_workflow_entries = {}
    for entry in raw_config.get("workflows", []):
        wf_id = entry.get("workflow_id") or entry.get("id") or (entry.get("meta") or {}).get("id")
        if wf_id:
            raw_workflow_entries[wf_id] = entry
    
    workflows_data = []
    for workflow_entry in project_model.workflows:
        workflow_path = project_root / workflow_entry.meta.path / "workflow.yaml"
        if not workflow_path.exists():
            continue
        
        workflow_dir = workflow_path.parent
        
        # Try to load via Workflow.from_yaml (with migration support) if project is available
        # Use inspection mode for snapshot export (no step materialization needed)
        if project:
            try:
                workflow = Workflow.from_yaml(workflow_dir, project, materialize_steps=False)
                # Extract workflow model data from the Workflow object
                workflow_model = load_workflow(workflow_path, project_root)
                # But use the actual Step objects from Workflow for step export
                workflow_steps = workflow.steps
            except Exception:
                # Fall back to basic load_workflow if Workflow.from_yaml fails
                workflow_model = load_workflow(workflow_path, project_root)
                workflow_steps = None
        else:
            # Fall back to basic loading
            workflow_model = load_workflow(workflow_path, project_root)
            workflow_steps = None
        
        # Export workflow metadata
        # Prefer name from raw project.qv.yml entry (legacy format) as it may have the correct human-readable name
        # workflow.yaml might have name=slug if it was created with old format
        # Use workflow_model.meta for other fields (slug, path) as workflow.yaml is the source of truth for those
        workflow_meta_dict = workflow_model.meta.to_dict()
        # Check raw project.qv.yml entry for legacy name field
        # Try both workflow_entry.meta.id and workflow_model.meta.id as keys
        raw_entry = raw_workflow_entries.get(workflow_entry.meta.id) or raw_workflow_entries.get(workflow_model.meta.id)
        legacy_name = None
        if raw_entry:
            # Check for legacy 'name' field at top level or in meta
            legacy_name = raw_entry.get("name") or (raw_entry.get("meta") or {}).get("name")
        # Also check workflow_entry.meta.name directly (might be set from registry)
        if not legacy_name:
            legacy_name = workflow_entry.meta.name
        # Override name with legacy name if it exists and is different from slug (preserves human-readable names)
        if legacy_name and legacy_name != workflow_model.meta.slug and legacy_name != workflow_model.meta.name:
            workflow_meta_dict["name"] = legacy_name
        # Preserve the workflow ID from workflow_entry if it's different (shouldn't happen, but be safe)
        if workflow_entry.meta.id and workflow_entry.meta.id != workflow_model.meta.id:
            workflow_meta_dict["id"] = workflow_entry.meta.id
        
        workflow_dict = {
            "meta": workflow_meta_dict,
            "mode": workflow_model.mode,
            "working_dir": workflow_model.working_dir,
            "steps": [],
        }
        # Export structure_id (canonical reference - ID only)
        # Do NOT export structure_name or structure selector (violates DAG + ID-only constitution)
        if workflow_model.structure_id:
            workflow_dict["structure_id"] = workflow_model.structure_id
        
        # Export each step
        # Strategy: Scan step files directly and export them, matching by ID when possible
        # This handles cases where workflow.yaml step_id doesn't match step file meta.id
        # Create resolver for legacy structure selector normalization
        from quantumvitas.core.resolution import make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        try:
            config = load_project_config(project_root)
            resolver = make_structure_selector_resolver(project_root, config=config)
        except Exception:
            resolver = None
        
        # Export steps in the order specified in workflow.yaml
        # Use workflow_model.steps to get the correct order (from workflow.yaml)
        steps_dir = workflow_dir / "steps"
        exported_step_ids = set()
        
        # Build a map of step_id -> step_file_path for quick lookup
        step_file_map = {}
        if steps_dir.exists():
            for step_file in steps_dir.glob("*.step.yaml"):
                try:
                    # Load step spec to get its ID
                    step_spec = StructureStepSpec.from_yaml(step_file, resolve_structure_selector=resolver)
                    step_id = step_spec.meta.id
                    step_file_map[step_id] = step_file
                except Exception:
                    # Skip step files that can't be loaded
                    continue
        
        # Export steps in the order from workflow.yaml
        # Use workflow_model.steps which preserves the order from workflow.yaml
        for step_entry in workflow_model.steps:
            step_id = step_entry.step_id  # DAG + ULID model: only step_id (ULID) is used
            if not step_id:
                continue
            
            # Find the step file for this step_id
            step_file = step_file_map.get(step_id)
            if not step_file:
                # Step file not found - skip this step
                continue
            
            # Skip if already exported (shouldn't happen, but be safe)
            if step_id in exported_step_ids:
                continue
            
            try:
                # Load step spec (DAG + ULID model: structure_id is already in spec)
                step_spec = StructureStepSpec.from_yaml(step_file, resolve_structure_selector=resolver)
                
                # Export step data (ID-only model: structure_id, no structure selector)
                step_dict = step_spec.to_dict()
                workflow_dict["steps"].append(step_dict)
                exported_step_ids.add(step_id)
            except Exception:
                # Skip step files that can't be loaded
                continue
        
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
        
        # If only structure selector is present, try to resolve it to structure_id
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
            # structure_name and structure are in-memory only (not persisted to YAML)
            structure_name=workflow_structure_name,
            # structure selector field removed - use structure_id (ULID) only
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
            # DAG + ID-only model: Step YAML must NOT contain structure_id or parent_workflow_id
            # Structure is resolved via workflow.structure_id at runtime
            # Parent workflow is implicit from step file location
            step_spec_dict = dict(step_data)
            
            # Remove structure_id and parent_workflow_id from dict (DAG invariant)
            step_spec_dict.pop("structure_id", None)
            step_spec_dict.pop("parent_workflow_id", None)
            step_spec_dict.pop("structure", None)  # Also remove legacy structure selector
            
            # Update meta with new IDs
            step_spec_dict["meta"] = {
                "id": new_step_id,
                "name": step_name,
                "slug": step_slug,
                "path": f"workflows/{workflow_slug}/steps/{step_slug}.step.yaml",
                "kind": "step",
            }
            
            # Create StructureStepSpec object to ensure proper serialization
            # This will strip any remaining structure_id/parent_workflow_id via to_dict()
            from quantumvitas.workflow.structure_steps import StructureStepSpec
            step_spec = StructureStepSpec.from_dict(step_spec_dict)
            
            # Write step file using to_dict() which enforces DAG invariants
            step_file = steps_dir / f"{step_slug}.step.yaml"
            step_file.write_text(yaml.safe_dump(step_spec.to_dict(), sort_keys=False))
            
            # Add to workflow steps list using step_id (ULID) from step meta
            from quantumvitas.core.models import WorkflowStepEntry
            step_meta = step_spec_dict.get("meta", {})
            step_id = step_meta.get("id") or step_spec_dict.get("id")
            workflow_model.steps.append(WorkflowStepEntry(
                step_id=step_id,  # Use ULID from step meta (canonical reference)
                type=step_data.get("step_type"),
                # step_file is NOT stored - step location resolved via registry using step_id
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

