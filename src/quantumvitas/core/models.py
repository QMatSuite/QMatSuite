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
    """An entry in the workflow's step list."""
    id: str
    type: Optional[str] = None
    step_file: Optional[str] = None
    input: Optional[str] = None
    reference: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"id": self.id}
        if self.type:
            d["type"] = self.type
        if self.step_file:
            d["step_file"] = self.step_file
        if self.input:
            d["input"] = self.input
        if self.reference:
            d["reference"] = self.reference
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStepEntry":
        return cls(
            id=data.get("id", "step"),
            type=data.get("type"),
            step_file=data.get("step_file"),
            input=data.get("input") or data.get("file"),
            reference=data.get("reference"),
        )


@dataclass
class WorkflowModel:
    """
    Data model for a workflow (workflow.yaml).
    
    All workflows have a meta section with id, name, slug, path.
    """
    meta: ResourceMeta
    structure: Optional[str] = None  # Structure selector
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
        """Convert to dictionary for YAML serialization."""
        return {
            "meta": self.meta.to_dict(),
            "structure": self.structure,
            "mode": self.mode,
            "working_dir": self.working_dir,
            "steps": [s.to_dict() for s in self.steps],
        }
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        default_name: str = "Workflow",
        default_path: str = ".",
    ) -> "WorkflowModel":
        """Create WorkflowModel from dictionary."""
        # Handle legacy format where structure is in workflow sub-dict
        workflow_section = data.get("workflow", {})
        structure = data.get("structure") or workflow_section.get("structure")
        working_dir = data.get("working_dir") or workflow_section.get("working_dir", "raw")
        
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
            structure=structure,
            mode=data.get("mode", "normal"),
            working_dir=working_dir,
            steps=steps,
        )


def load_workflow(path: Path, project_root: Optional[Path] = None) -> WorkflowModel:
    """
    Load a WorkflowModel from a workflow.yaml file.
    
    Args:
        path: Path to workflow.yaml or workflow directory
        project_root: Project root for relative path calculation
        
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
    
    return WorkflowModel.from_dict(data, default_name=default_name, default_path=default_path)


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
        return {
            "name": self.meta.name,
            "file": self.file,
            "format": self.format,
            "meta": self.meta.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: Path) -> "StructureEntry":
        meta_dict = data.get("meta") or {}
        name = data.get("name") or meta_dict.get("name") or "Structure"
        file_path = data.get("file") or meta_dict.get("path") or f"structures/{slugify(name)}.json"
        
        meta = ResourceMeta(
            id=meta_dict.get("id") or generate_resource_id(),
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
        return {
            "name": self.meta.name,
            "path": self.meta.path,
            "meta": self.meta.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: Path) -> "WorkflowEntry":
        meta_dict = data.get("meta") or {}
        name = data.get("name") or meta_dict.get("name") or "Workflow"
        path = data.get("path") or meta_dict.get("path") or f"workflows/{slugify(name)}"
        
        meta = ResourceMeta(
            id=meta_dict.get("id") or generate_resource_id(),
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
        meta = ResourceMeta.from_dict(
            data.get("meta"),
            kind="structure",
            default_name=default_name,
            default_path=default_path,
        )
        
        # Remove meta from data to get pure structure
        structure_data = {k: v for k, v in data.items() if k != "meta"}
        
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

