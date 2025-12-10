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
    
    Cross-resource reference: step_id (ULID) is the ONLY allowed cross-resource field.
    All other fields (type, input, reference) are workflow-local metadata, not cross-references.
    
    The step file location is resolved via ResourceIndex using step_id, not stored here.
    """
    step_id: Optional[str] = None  # Canonical step reference (ULID from step meta) - REQUIRED
    type: Optional[str] = None  # Workflow-local metadata (step type for display/ordering)
    input: Optional[str] = None  # Workflow-local metadata (legacy input file reference)
    reference: Optional[str] = None  # Workflow-local metadata (reference file)
    
    # Legacy field removed - step_id (ULID) is the only identifier
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        Writes step_id (ULID) as the ONLY cross-resource reference.
        Does NOT write step_file (file location resolved via registry).
        Does not write legacy id field.
        """
        d: Dict[str, Any] = {}
        if self.step_id:
            d["step_id"] = self.step_id
        if self.type:
            d["type"] = self.type
        if self.input:
            d["input"] = self.input
        if self.reference:
            d["reference"] = self.reference
        # Do not write legacy "id" field
        # Do not write step_file (resolved via registry using step_id)
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: Optional[Path] = None) -> "WorkflowStepEntry":
        """
        Create WorkflowStepEntry from dictionary.
        
        This method only supports the DAG + ULID model. Legacy workflows
        (with step_file or non-ULID step_id) must be migrated first.
        
        Args:
            data: Dictionary containing step entry data
            project_root: Optional project root for error messages
        
        Raises:
            LegacyProjectError: If legacy fields are detected (step_file, non-ULID step_id)
        """
        from quantumvitas.core.exceptions import LegacyProjectError
        
        # New format: step_id (ULID) - REQUIRED
        step_id = data.get("step_id")
        
        # Detect legacy patterns
        has_step_file = "step_file" in data
        has_legacy_id = "id" in data and data.get("id") != step_id
        
        # Check if step_id is missing or not a ULID (26 chars starting with "01")
        is_ulid = step_id and len(step_id) == 26 and step_id.startswith("01")
        missing_or_invalid_step_id = not step_id or not is_ulid
        
        if has_step_file or has_legacy_id or missing_or_invalid_step_id:
            error_msg = "Legacy workflow step entry detected. "
            if has_step_file:
                error_msg += "Field 'step_file' is not supported (use step_id ULID instead). "
            if missing_or_invalid_step_id:
                error_msg += f"step_id must be a ULID (26 chars), got: {step_id}. "
            if has_legacy_id:
                error_msg += "Legacy 'id' field detected (use step_id ULID instead). "
            error_msg += "Please run the migration script to upgrade this workflow."
            
            if project_root:
                raise LegacyProjectError(project_root, error_msg)
            else:
                raise LegacyProjectError(Path.cwd(), error_msg)
        
        return cls(
            step_id=step_id,
            type=data.get("type"),
            input=data.get("input") or data.get("file"),
            reference=data.get("reference"),
            # Do not store legacy id field
        )


@dataclass
class WorkflowModel:
    """
    Data model for a workflow (workflow.yaml).
    
    All workflows have a meta section with id, name, slug, path.
    
    Structure references:
    - structure_id: ULID of the structure (canonical reference)
    - structure_name: Optional display name (cosmetic only, not used for resolution)
    """
    meta: ResourceMeta
    structure_id: Optional[str] = None  # Canonical structure reference (ULID)
    structure_name: Optional[str] = None  # Optional display name (cosmetic)
    # Legacy structure selector field removed - use structure_id (ULID) only
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
        
        DAG + ID-only constitution:
        - structure_id: ULID only (canonical reference)
        - steps: step_id (ULID) only
        - Do NOT write structure_name (cosmetic only, not used for resolution)
        """
        result: Dict[str, Any] = {
            "meta": self.meta.to_dict(),
            "mode": self.mode,
            "working_dir": self.working_dir,
            "steps": [s.to_dict() for s in self.steps],
        }
        # Write structure_id (canonical reference - ID only)
        # Do NOT write structure_name (cosmetic only, not used for resolution)
        if self.structure_id:
            result["structure_id"] = self.structure_id
        return result
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        default_name: str = "Workflow",
        default_path: str = ".",
        resolve_structure_selector: Optional[callable] = None,  # DEPRECATED - no longer used
        project_root: Optional[Path] = None,  # Optional project root for error messages
    ) -> "WorkflowModel":
        """
        Create WorkflowModel from dictionary.
        
        This method only supports the DAG + ULID model. Legacy workflows
        (with structure selector instead of structure_id) must be migrated first.
        
        Args:
            data: Dictionary containing workflow data
            default_name: Default name if not in data
            default_path: Default path if not in data
            resolve_structure_selector: DEPRECATED - no longer used (legacy compatibility removed)
            project_root: Optional project root for error messages
        
        Raises:
            LegacyProjectError: If legacy fields are detected (structure selector without structure_id)
        """
        from quantumvitas.core.exceptions import LegacyProjectError
        
        # Handle workflow section (for working_dir)
        workflow_section = data.get("workflow", {})
        working_dir = data.get("working_dir") or workflow_section.get("working_dir", "raw")
        
        # New format: structure_id (canonical) - REQUIRED if structure is referenced
        structure_id = data.get("structure_id") or workflow_section.get("structure_id")
        structure_name = data.get("structure_name") or workflow_section.get("structure_name")
        
        # Legacy format: structure selector (NOT SUPPORTED)
        structure = data.get("structure") or workflow_section.get("structure")
        
        # Detect legacy pattern: structure selector without structure_id
        if structure and not structure_id:
            error_msg = (
                "Legacy workflow detected: has 'structure' selector but no 'structure_id' ULID. "
                "Please run the migration script to upgrade this workflow."
            )
            if project_root:
                raise LegacyProjectError(project_root, error_msg)
            else:
                raise LegacyProjectError(Path(default_path) if default_path else Path.cwd(), error_msg)
        
        # Build meta
        meta = ResourceMeta.from_dict(
            data.get("meta"),
            kind="workflow",
            default_name=data.get("id") or default_name,
            default_path=default_path,
        )
        
        # Parse steps with legacy detection
        effective_project_root = project_root if project_root else (Path(default_path) if default_path else Path.cwd())
        steps = [WorkflowStepEntry.from_dict(s, project_root=effective_project_root) for s in data.get("steps", [])]
        
        return cls(
            meta=meta,
            structure_id=structure_id,
            structure_name=structure_name,
            mode=data.get("mode", "normal"),
            working_dir=working_dir,
            steps=steps,
        )
    
    # Legacy resolve_step_ids method removed - all steps must have step_id (ULID) at load time


def load_workflow(
    path: Path, 
    project_root: Optional[Path] = None,
    resolve_structure_selector: Optional[callable] = None,  # DEPRECATED - no longer used
) -> WorkflowModel:
    """
    Load a WorkflowModel from a workflow.yaml file.
    
    This function only supports the DAG + ULID model. Legacy workflows
    (with structure selector instead of structure_id) will raise LegacyProjectError.
    
    Args:
        path: Path to workflow.yaml or workflow directory
        project_root: Project root for relative path calculation and error messages
        resolve_structure_selector: DEPRECATED - no longer used (legacy compatibility removed)
        
    Returns:
        WorkflowModel instance
        
    Raises:
        LegacyProjectError: If legacy fields are detected in the workflow
        FileNotFoundError: If workflow.yaml does not exist
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
    
    # Load workflow model - will raise LegacyProjectError if legacy fields detected
    model = WorkflowModel.from_dict(
        data, 
        default_name=default_name, 
        default_path=default_path,
        project_root=project_root or workflow_dir,
    )
    
    # If structure_id exists but structure_name is missing, look it up for display
    if model.structure_id and not model.structure_name and project_root:
        try:
            from quantumvitas.core.resolution import resolve_structure
            from quantumvitas.core.project_utils import load_project_config
            config = load_project_config(project_root)
            resolved = resolve_structure(project_root, model.structure_id, config=config)
            model.structure_name = resolved.meta.name
        except Exception:
            # If lookup fails, structure_name remains None (cosmetic field)
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
        
        DAG + ID-only model: Stores only structure_id (ULID) for cross-resource reference.
        No duplicated name/slug/path - structure's own meta lives in structure JSON file.
        No file path - structure location resolved via ResourceIndex using structure_id.
        """
        result = {
            "structure_id": self.meta.id,  # ID-only reference (ULID)
        }
        # Format is optional metadata, not a cross-reference
        if self.format != "auto":
            result["format"] = self.format
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: Path) -> "StructureEntry":
        """
        Create StructureEntry from dictionary.
        
        DAG + ID-only model: Requires structure_id (ULID).
        Structure file location is resolved via ResourceIndex using structure_id.
        """
        # structure_id (ULID) is required
        structure_id = data.get("structure_id")
        if not structure_id:
            structure_id = data.get("id")  # Fallback to 'id' field if structure_id missing
        
        # Extract name/slug/path from meta for display
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
        
        DAG + ID-only model: Stores only workflow_id (ULID) for cross-resource reference.
        No duplicated name/slug/path - workflow's own meta lives in workflow.yaml.
        No path - workflow location resolved via ResourceIndex using workflow_id.
        """
        return {
            "workflow_id": self.meta.id,  # ID-only reference (ULID)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: Path) -> "WorkflowEntry":
        """
        Create WorkflowEntry from dictionary.
        
        DAG + ID-only model: Requires workflow_id (ULID).
        Workflow file location is resolved via ResourceIndex using workflow_id.
        """
        # workflow_id (ULID) is required
        workflow_id = data.get("workflow_id")
        if not workflow_id:
            workflow_id = data.get("id")  # Fallback to 'id' field if workflow_id missing
        
        # Extract name/slug/path from meta for display
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
                                # But prefer name from entry (project.qv.yml) if it exists and is different from slug
                                entry_name = data.get("name") or meta_dict.get("name")
                                default_name = entry_name if entry_name and entry_name != wf_meta_dict.get("slug") else wf_meta_dict.get("name", "Workflow")
                                meta = ResourceMeta.from_dict(
                                    wf_meta_dict,
                                    kind="workflow",
                                    default_name=default_name,
                                    default_path=wf_meta_dict.get("path", f"workflows/{workflow_dir.name}"),
                                )
                                # Override with entry name if it's different from slug (preserves human-readable names)
                                if entry_name and entry_name != meta.slug:
                                    meta.name = entry_name
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
                    # Prefer name from entry (project.qv.yml) over workflow.yaml if entry has a human-readable name
                    entry_name = data.get("name") or meta_dict.get("name")
                    default_name = entry_name if entry_name and entry_name != wf_meta_dict.get("slug") else (name or wf_meta_dict.get("name", "Workflow"))
                    meta = ResourceMeta.from_dict(
                        wf_meta_dict,
                        kind="workflow",
                        default_name=default_name,
                        default_path=path,
                    )
                    # Override with entry name if it's different from slug (preserves human-readable names)
                    if entry_name and entry_name != meta.slug:
                        meta.name = entry_name
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

