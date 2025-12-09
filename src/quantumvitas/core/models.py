"""
Centralized data models for QuantumVITAS resources.

All resources (project, workflow, step, structure) are represented as dataclasses.
YAML/JSON files are just the persistence format - not the primary representation.

This module provides:
- Dataclass models for each resource type
- load_* / save_* functions for YAML/JSON I/O
- Consistent meta fields (id, name, slug, path) across all resources
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from quantumvitas.core.resources import (
    ResourceMeta,
    ResourceKind,
    ensure_relative_path,
    generate_resource_id,
    slugify,
)


# ---------------------------------------------------------------------------
# Workflow Model
# ---------------------------------------------------------------------------


@dataclass
class WorkflowStepEntry:
    """
    An entry in the workflow's step list.
    
    Cross-resource reference: step_id (ULID) is the canonical reference to the step.
    step_file is kept for file location (not a cross-resource reference).
    """
    step_id: Optional[str] = None  # Canonical step reference (ULID from step meta)
    step_file: Optional[str] = None  # File path for locating step file (not a cross-ref)
    type: Optional[str] = None
    input: Optional[str] = None
    reference: Optional[str] = None
    
    # Legacy field for backwards compatibility
    id: Optional[str] = None  # Legacy slug-based id (deprecated, use step_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        Writes step_id (ULID) as canonical reference.
        Keeps step_file for file location.
        Does not write legacy id field.
        """
        d: Dict[str, Any] = {}
        if self.step_id:
            d["step_id"] = self.step_id
        if self.step_file:
            d["step_file"] = self.step_file
        if self.type:
            d["type"] = self.type
        if self.input:
            d["input"] = self.input
        if self.reference:
            d["reference"] = self.reference
        # Do not write legacy "id" field
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStepEntry":
        """
        Create WorkflowStepEntry from dictionary.
        
        Backwards compatibility: Accepts legacy "id" (slug) field,
        but step_id (ULID) is preferred and canonical.
        """
        # New format: step_id (ULID)
        step_id = data.get("step_id")
        
        # Legacy format: id (slug) - for backwards compat
        legacy_id = data.get("id")
        
        return cls(
            step_id=step_id,
            step_file=data.get("step_file"),
            type=data.get("type"),
            input=data.get("input") or data.get("file"),
            reference=data.get("reference"),
            id=legacy_id,  # Keep for backwards compat
        )


@dataclass
class WorkflowModel:
    """
    Data model for a workflow (workflow.yaml).
    
    All workflows have a meta section with id, name, slug, path.
    
    Structure references:
    - structure_id: ULID of the structure (canonical reference)
    - structure_name: Optional display name (cosmetic only, not used for resolution)
    - structure: Legacy selector field (for backwards compatibility when loading)
    """
    meta: ResourceMeta
    structure_id: Optional[str] = None  # Canonical structure reference (ULID)
    structure_name: Optional[str] = None  # Optional display name (cosmetic)
    structure: Optional[str] = None  # Legacy selector (backwards compat, not authoritative)
    mode: str = "normal"
    working_dir: str = "raw"
    steps: List[WorkflowStepEntry] = field(default_factory=list)
    
    @property
    def id(self) -> str:
        return self.meta.id
    
    @property
    def name(self) -> str:
        return self.meta.name
    
    @property
    def slug(self) -> str:
        return self.meta.slug
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        Cross-resource references:
        - structure_id: ULID only (no structure name/slug/path)
        - steps: step_id (ULID) only (no step name/slug/path)
        """
        result: Dict[str, Any] = {
            "meta": self.meta.to_dict(),
            "mode": self.mode,
            "working_dir": self.working_dir,
            "steps": [s.to_dict() for s in self.steps],
        }
        # Write structure_id (canonical reference - ID only)
        if self.structure_id:
            result["structure_id"] = self.structure_id
        # Optionally write structure_name for UI display (cosmetic only)
        if self.structure_name:
            result["structure_name"] = self.structure_name
        # Do not write structure selector (legacy field - not authoritative)
        return result
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        default_name: str = "Workflow",
        default_path: str = ".",
    ) -> "WorkflowModel":
        """
        Create WorkflowModel from dictionary.
        
        Handles both new format (structure_id) and legacy format (structure selector).
        Legacy structure selector is kept in memory for backwards compatibility but
        should be resolved to structure_id when project_root is available.
        """
        # Handle legacy format where structure is in workflow sub-dict
        workflow_section = data.get("workflow", {})
        working_dir = data.get("working_dir") or workflow_section.get("working_dir", "raw")
        
        # New format: structure_id (canonical)
        structure_id = data.get("structure_id")
        structure_name = data.get("structure_name")
        
        # Legacy format: structure selector (for backwards compat)
        structure = data.get("structure") or workflow_section.get("structure")
        
        # Build meta
        meta = ResourceMeta.from_dict(
            data.get("meta"),
            kind="workflow",
            default_name=data.get("id") or default_name,
            default_path=default_path,
        )
        
        # Parse steps
        steps = [WorkflowStepEntry.from_dict(s) for s in data.get("steps", [])]
        
        return cls(
            meta=meta,
            structure_id=structure_id,
            structure_name=structure_name,
            structure=structure,  # Keep for backwards compat
            mode=data.get("mode", "normal"),
            working_dir=working_dir,
            steps=steps,
        )
    
    def resolve_step_ids(self, workflow_dir: Path) -> None:
        """
        Resolve step_id (ULID) for steps that only have legacy id (slug).
        
        This is called after loading a workflow to ensure all steps have step_id.
        """
        for step_entry in self.steps:
            if not step_entry.step_id and step_entry.step_file:
                # Try to load step file and get its meta.id
                step_file_path = workflow_dir / step_entry.step_file
                if step_file_path.exists():
                    try:
                        import yaml
                        step_data = yaml.safe_load(step_file_path.read_text()) or {}
                        step_meta = step_data.get("meta", {})
                        if step_meta and step_meta.get("id"):
                            step_entry.step_id = step_meta.get("id")
                    except Exception:
                        pass  # If loading fails, keep step_id as None


def load_workflow(path: Path, project_root: Optional[Path] = None) -> WorkflowModel:
    """
    Load a WorkflowModel from a workflow.yaml file.
    
    If project_root is provided and the workflow has a legacy structure selector,
    it will be resolved to structure_id automatically.
    
    Args:
        path: Path to workflow.yaml or workflow directory
        project_root: Project root for relative path calculation and structure resolution
        
    Returns:
        WorkflowModel instance
    """
    if path.is_dir():
        path = path / "workflow.yaml"
    
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")
    
    data = yaml.safe_load(path.read_text()) or {}
    
    # Default name and path
    workflow_dir = path.parent
    default_name = data.get("id") or workflow_dir.name
    
    if project_root:
        try:
            default_path = ensure_relative_path(workflow_dir, base=project_root)
        except ValueError:
            default_path = workflow_dir.name
    else:
        default_path = workflow_dir.name
    
    model = WorkflowModel.from_dict(data, default_name=default_name, default_path=default_path)
    
    # Resolve legacy structure selector to structure_id if needed
    if project_root and model.structure and not model.structure_id:
        try:
            from quantumvitas.core.resolution import resolve_structure, _is_path_like
            # If structure looks like a path, try to resolve it as a path first
            if _is_path_like(model.structure):
                # Try to resolve as path
                structure_path = Path(model.structure)
                if not structure_path.is_absolute():
                    structure_path = project_root / structure_path
                if structure_path.exists():
                    # Path exists, but we can't get structure_id without registration
                    # Keep the path for now - it will be resolved when needed
                    pass
                else:
                    # Path doesn't exist, try as selector
                    resolved = resolve_structure(project_root, model.structure)
                    model.structure_id = resolved.meta.id
                    model.structure_name = resolved.meta.name
            else:
                # Try to resolve as selector
                resolved = resolve_structure(project_root, model.structure)
                model.structure_id = resolved.meta.id
                model.structure_name = resolved.meta.name
        except Exception:
            # If resolution fails, keep structure selector for backwards compat
            # This allows loading workflows even if structure is missing or not registered
            pass
    
    return model


def save_workflow(model: WorkflowModel, path: Path) -> None:
    """
    Save a WorkflowModel to a workflow.yaml file.
    
    Args:
        model: WorkflowModel to save
        path: Path to workflow.yaml or workflow directory
    """
    if path.is_dir():
        path = path / "workflow.yaml"
    
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(model.to_dict(), sort_keys=False))


# ---------------------------------------------------------------------------
# Project Model (extends existing Project)
# ---------------------------------------------------------------------------


@dataclass
class StructureEntry:
    """A structure entry in project.qv.yml."""
    meta: ResourceMeta
    file: str
    format: str = "auto"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        Stores only ID for cross-resource reference (no duplicated name/slug/path).
        The structure's own meta (name/slug/path) lives in the structure JSON file.
        """
        return {
            "id": self.meta.id,  # Only ID - name/slug/path come from structure file meta
            "format": self.format,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: Path) -> "StructureEntry":
        """
        Create StructureEntry from dictionary.
        
        Backwards compatibility: Accepts legacy format with name/slug/path,
        but these are only used to locate the structure file and read its meta.
        """
        # New format: id only
        structure_id = data.get("id")
        
        # Legacy format: name/slug/path (for backwards compat)
        meta_dict = data.get("meta") or {}
        name = data.get("name") or meta_dict.get("name")
        file_path = data.get("file") or meta_dict.get("path")
        
        # If we have an ID, try to load meta from the structure file
        if structure_id:
            # Try to find structure file and load its meta
            structures_dir = project_root / "structures"
            if structures_dir.exists():
                for struct_file in structures_dir.glob("*.json"):
                    try:
                        import json
                        struct_data = json.loads(struct_file.read_text())
                        struct_meta_dict = struct_data.get("__qv_meta__") or struct_data.get("meta")
                        if struct_meta_dict and struct_meta_dict.get("id") == structure_id:
                            # Found matching structure file - use its meta
                            meta = ResourceMeta.from_dict(
                                struct_meta_dict,
                                kind="structure",
                                default_name=struct_meta_dict.get("name", "Structure"),
                                default_path=struct_meta_dict.get("path", f"structures/{struct_file.name}"),
                            )
                            return cls(
                                meta=meta,
                                file=meta.path,
                                format=data.get("format", "auto"),
                            )
                    except Exception:
                        continue
        
        # Fallback: legacy format or structure file not found
        # Use provided name/path or defaults
        if not name:
            name = "Structure"
        if not file_path:
            file_path = f"structures/{slugify(name)}.json"
        
        # Try to load meta from structure file if it exists
        struct_file = project_root / file_path
        if struct_file.exists():
            try:
                import json
                struct_data = json.loads(struct_file.read_text())
                struct_meta_dict = struct_data.get("__qv_meta__") or struct_data.get("meta")
                if struct_meta_dict:
                    meta = ResourceMeta.from_dict(
                        struct_meta_dict,
                        kind="structure",
                        default_name=name,
                        default_path=file_path,
                    )
                    return cls(meta=meta, file=file_path, format=data.get("format", "auto"))
            except Exception:
                pass
        
        # Last resort: create meta from provided/defaults
        meta = ResourceMeta(
            id=meta_dict.get("id") or structure_id or generate_resource_id(),
            name=name,
            slug=meta_dict.get("slug") or slugify(name),
            path=file_path,
            kind="structure",
        )
        
        return cls(
            meta=meta,
            file=file_path,
            format=data.get("format", "auto"),
        )


@dataclass
class WorkflowEntry:
    """A workflow entry in project.qv.yml."""
    meta: ResourceMeta
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        Stores only ID for cross-resource reference (no duplicated name/slug/path).
        The workflow's own meta (name/slug/path) lives in workflow.yaml.
        """
        return {
            "id": self.meta.id,  # Only ID - name/slug/path come from workflow.yaml meta
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: Path) -> "WorkflowEntry":
        """
        Create WorkflowEntry from dictionary.
        
        Backwards compatibility: Accepts legacy format with name/slug/path,
        but these are only used to locate the workflow.yaml file and read its meta.
        """
        # New format: id only
        workflow_id = data.get("id")
        
        # Legacy format: name/slug/path (for backwards compat)
        meta_dict = data.get("meta") or {}
        name = data.get("name") or meta_dict.get("name")
        path = data.get("path") or meta_dict.get("path")
        
        # If we have an ID, try to load meta from workflow.yaml
        if workflow_id:
            # Try to find workflow.yaml and load its meta
            workflows_dir = project_root / "workflows"
            if workflows_dir.exists():
                for workflow_dir in workflows_dir.iterdir():
                    if not workflow_dir.is_dir():
                        continue
                    workflow_yaml = workflow_dir / "workflow.yaml"
                    if workflow_yaml.exists():
                        try:
                            import yaml
                            wf_data = yaml.safe_load(workflow_yaml.read_text()) or {}
                            wf_meta_dict = wf_data.get("meta", {})
                            if wf_meta_dict and wf_meta_dict.get("id") == workflow_id:
                                # Found matching workflow - use its meta
                                meta = ResourceMeta.from_dict(
                                    wf_meta_dict,
                                    kind="workflow",
                                    default_name=wf_meta_dict.get("name", "Workflow"),
                                    default_path=wf_meta_dict.get("path", f"workflows/{workflow_dir.name}"),
                                )
                                return cls(meta=meta)
                        except Exception:
                            continue
        
        # Fallback: legacy format or workflow.yaml not found
        # Use provided name/path or defaults
        if not name:
            name = "Workflow"
        if not path:
            path = f"workflows/{slugify(name)}"
        
        # Try to load meta from workflow.yaml if it exists
        workflow_yaml = project_root / path / "workflow.yaml"
        if workflow_yaml.exists():
            try:
                import yaml
                wf_data = yaml.safe_load(workflow_yaml.read_text()) or {}
                wf_meta_dict = wf_data.get("meta", {})
                if wf_meta_dict:
                    meta = ResourceMeta.from_dict(
                        wf_meta_dict,
                        kind="workflow",
                        default_name=name,
                        default_path=path,
                    )
                    return cls(meta=meta)
            except Exception:
                pass
        
        # Last resort: create meta from provided/defaults
        meta = ResourceMeta(
            id=meta_dict.get("id") or workflow_id or generate_resource_id(),
            name=name,
            slug=meta_dict.get("slug") or slugify(name),
            path=path,
            kind="workflow",
        )
        
        return cls(meta=meta)


@dataclass
class ProjectModel:
    """
    Data model for a project (project.qv.yml).
    """
    meta: ResourceMeta
    root: Path
    structures: List[StructureEntry] = field(default_factory=list)
    workflows: List[WorkflowEntry] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def id(self) -> str:
        return self.meta.id
    
    @property
    def name(self) -> str:
        return self.meta.name
    
    @property
    def slug(self) -> str:
        return self.meta.slug
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "project": {
                "name": self.meta.name,
                "meta": self.meta.to_dict(),
            },
            "settings": self.settings,
            "structures": [s.to_dict() for s in self.structures],
            "workflows": [w.to_dict() for w in self.workflows],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], root: Path) -> "ProjectModel":
        """Create ProjectModel from dictionary."""
        project_section = data.get("project", {})
        
        # Build meta
        meta = ResourceMeta.from_dict(
            project_section.get("meta"),
            kind="project",
            default_name=project_section.get("name") or root.name,
            default_path=".",
        )
        
        # Parse structures
        structures = [
            StructureEntry.from_dict(s, root) 
            for s in data.get("structures", [])
        ]
        
        # Parse workflows
        workflows = [
            WorkflowEntry.from_dict(w, root)
            for w in data.get("workflows", [])
        ]
        
        return cls(
            meta=meta,
            root=root,
            structures=structures,
            workflows=workflows,
            settings=data.get("settings", {}),
        )
    
    def get_structure_by_selector(self, selector: str) -> Optional[StructureEntry]:
        """Find structure by ULID, slug, or name."""
        selector_lower = selector.lower()
        for s in self.structures:
            if s.meta.id == selector:  # ULID exact match
                return s
            if s.meta.slug == selector_lower:
                return s
            if s.meta.name.lower() == selector_lower:
                return s
        return None
    
    def get_workflow_by_selector(self, selector: str) -> Optional[WorkflowEntry]:
        """Find workflow by ULID, slug, or name."""
        selector_lower = selector.lower()
        for w in self.workflows:
            if w.meta.id == selector:  # ULID exact match
                return w
            if w.meta.slug == selector_lower:
                return w
            if w.meta.name.lower() == selector_lower:
                return w
        return None


def load_project(path: Path) -> ProjectModel:
    """
    Load a ProjectModel from project.qv.yml.
    
    Args:
        path: Path to project root or project.qv.yml
        
    Returns:
        ProjectModel instance
    """
    if path.is_file():
        project_root = path.parent
        config_file = path
    else:
        project_root = path
        config_file = path / "project.qv.yml"
    
    if not config_file.exists():
        raise FileNotFoundError(f"project.qv.yml not found: {config_file}")
    
    data = yaml.safe_load(config_file.read_text()) or {}
    return ProjectModel.from_dict(data, project_root.resolve())


def save_project(model: ProjectModel, path: Optional[Path] = None) -> None:
    """
    Save a ProjectModel to project.qv.yml.
    
    Args:
        model: ProjectModel to save
        path: Path to project root (defaults to model.root)
    """
    root = path or model.root
    config_file = root / "project.qv.yml"
    config_file.write_text(yaml.safe_dump(model.to_dict(), sort_keys=False))


# ---------------------------------------------------------------------------
# Structure Model (for structure JSON files)
# ---------------------------------------------------------------------------


@dataclass
class StructureModel:
    """
    Data model for a structure file.
    
    The structure data itself is stored in pymatgen format,
    but we add a meta section for consistent identification.
    """
    meta: ResourceMeta
    data: Dict[str, Any]  # pymatgen structure dict
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = dict(self.data)
        result["meta"] = self.meta.to_dict()
        return result
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        default_name: str = "Structure",
        default_path: str = "structures/structure.json",
    ) -> "StructureModel":
        """Create StructureModel from dictionary."""
        # Check for both "meta" and "__qv_meta__" (structure file format)
        meta_dict = data.get("meta") or data.get("__qv_meta__")
        meta = ResourceMeta.from_dict(
            meta_dict,
            kind="structure",
            default_name=default_name,
            default_path=default_path,
        )
        
        # Remove meta from data to get pure structure
        structure_data = {k: v for k, v in data.items() if k not in ("meta", "__qv_meta__", "structure")}
        # If structure is wrapped in "structure" key, use that
        if "structure" in data and isinstance(data["structure"], dict):
            structure_data = data["structure"]
        
        return cls(meta=meta, data=structure_data)


def load_structure_model(path: Path, project_root: Optional[Path] = None) -> StructureModel:
    """
    Load a StructureModel from a JSON file.
    
    Args:
        path: Path to structure JSON file
        project_root: Project root for relative path calculation
        
    Returns:
        StructureModel instance
    """
    import json
    
    if not path.exists():
        raise FileNotFoundError(f"Structure file not found: {path}")
    
    data = json.loads(path.read_text())
    
    default_name = path.stem
    if project_root:
        try:
            default_path = ensure_relative_path(path, base=project_root)
        except ValueError:
            default_path = f"structures/{path.name}"
    else:
        default_path = f"structures/{path.name}"
    
    return StructureModel.from_dict(data, default_name=default_name, default_path=default_path)


def save_structure_model(model: StructureModel, path: Path) -> None:
    """
    Save a StructureModel to a JSON file.
    
    Args:
        model: StructureModel to save
        path: Path to output JSON file
    """
    import json
    
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.to_dict(), indent=2))


# ---------------------------------------------------------------------------
# Convenience functions for ensuring meta exists
# ---------------------------------------------------------------------------


def ensure_workflow_meta(
    workflow_dir: Path,
    project_root: Path,
    name: Optional[str] = None,
    workflow_id: Optional[str] = None,
) -> ResourceMeta:
    """
    Ensure a workflow has proper meta, creating/updating if needed.
    
    Returns the meta that should be used.
    """
    workflow_yaml = workflow_dir / "workflow.yaml"
    
    # Compute defaults
    default_name = name or workflow_dir.name
    default_slug = slugify(default_name)
    try:
        default_path = ensure_relative_path(workflow_dir, base=project_root)
    except ValueError:
        default_path = f"workflows/{default_slug}"
    
    # Load existing or create new
    if workflow_yaml.exists():
        model = load_workflow(workflow_yaml, project_root)
        # Ensure all fields are populated
        if not model.meta.id or len(model.meta.id) != 26:
            model.meta = ResourceMeta(
                id=workflow_id or generate_resource_id(),
                name=model.meta.name or default_name,
                slug=model.meta.slug or default_slug,
                path=model.meta.path or default_path,
                kind="workflow",
            )
            save_workflow(model, workflow_yaml)
        return model.meta
    else:
        # Create new
        meta = ResourceMeta(
            id=workflow_id or generate_resource_id(),
            name=default_name,
            slug=default_slug,
            path=default_path,
            kind="workflow",
        )
        model = WorkflowModel(meta=meta)
        save_workflow(model, workflow_yaml)
        return meta

