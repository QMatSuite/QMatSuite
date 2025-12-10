"""
Dataclasses representing a QuantumVITAS project on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from quantumvitas.core.resolution import ResourceIndex

import yaml

from quantumvitas.core.resources import (
    ResourceMeta,
    ResourceKind,
    ensure_relative_path,
    meta_from_name,
)


@dataclass(slots=True)
class ProjectSettings:
    """
    Global project settings (parallelism, default tolerances, etc.).

    Stored as a simple dictionary but exposed via a dataclass for type safety.
    """

    data: Dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.data.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value


@dataclass(slots=True)
class StructureRef:
    """
    Reference to a structure file inside the project.

    Structures are resolved relative to ``project.root / "structures"``.
    """

    meta: ResourceMeta
    absolute_path: Path
    format: str = "auto"  # e.g. "cif", "qe_input", "internal"

    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def slug(self) -> str:
        return self.meta.slug

    def relative_path(self) -> str:
        return self.meta.path

    @property
    def path(self) -> Path:
        return self.absolute_path

    def resolve_path(self, project_root: Path) -> Path:
        return self.meta.resolved_path(project_root)


@dataclass(slots=True)
class WorkflowRef:
    """
    Reference to a workflow folder (which is also the workflow workdir).
    """

    meta: ResourceMeta
    absolute_path: Path

    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def slug(self) -> str:
        return self.meta.slug

    def relative_path(self) -> str:
        return self.meta.path

    @property
    def path(self) -> Path:
        return self.absolute_path

    def resolve_path(self, project_root: Path) -> Path:
        return self.meta.resolved_path(project_root)


@dataclass(slots=True)
class Project:
    """
    Container for structures, workflows, pseudo potentials, and settings.
    """

    root: Path
    meta: ResourceMeta
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    structures: Dict[str, StructureRef] = field(default_factory=dict)
    workflows: Dict[str, WorkflowRef] = field(default_factory=dict)

    @classmethod
    def open(cls, project_root: Path | str) -> "Project":
        """
        Load project metadata from ``project.qv.yml``.
        """
        root = Path(project_root).resolve()
        config_file = root / "project.qv.yml"
        if not config_file.exists():
            raise FileNotFoundError(f"project.qv.yml not found under {root}")

        data = yaml.safe_load(config_file.read_text()) or {}
        project_section = data.get("project", {})
        project_name = project_section.get("name") or root.name
        project_meta = ResourceMeta.from_dict(
            project_section.get("meta"),
            kind="project",
            default_name=project_name,
            default_path=".",
        )

        settings = ProjectSettings(data.get("settings", {}))

        project = cls(root=root, meta=project_meta, settings=settings)
        # Build index once and reuse for both structures and workflows
        # This avoids duplicate index builds within Project.open()
        from quantumvitas.core.resolution import build_resource_index
        index = build_resource_index(root)
        
        project.structures = cls._load_structures(
            root, data.get("structures", []), project_section.get("structures_dir", "structures"), index=index
        )
        project.workflows = cls._load_workflows(
            root, data.get("workflows", []), project_section.get("workflows_dir", "workflows"), index=index
        )
        return project

    @staticmethod
    def _load_structures(
        root: Path, entries: list[dict], default_dir: str, index: Optional["ResourceIndex"] = None
    ) -> Dict[str, StructureRef]:
        """
        Load structures from project entries.
        
        In the new DAG + ID-only model:
        - Entries have structure_id (ULID), not file path
        - Structure file location is resolved via ResourceIndex using structure_id
        - Structure meta (name, slug, path) is loaded from the structure file itself
        
        Args:
            root: Project root path
            entries: Structure entries from project.qv.yml
            default_dir: Default structures directory name
            index: Optional ResourceIndex (avoids rebuilding if provided)
        """
        structures: Dict[str, StructureRef] = {}
        
        # Use provided index or build one if needed
        if index is None:
            try:
                from quantumvitas.core.resolution import build_resource_index
                index = build_resource_index(root)
            except Exception:
                index = None
        
        for entry in entries:
            structure_id = entry.get("structure_id") or entry.get("id")
            legacy_file = entry.get("file")
            
            struct_meta: Optional[ResourceMeta] = None
            absolute_path: Optional[Path] = None
            
            # New DAG model: resolve structure_id via ResourceIndex
            if structure_id and index:
                try:
                    # Find structure in index by ID
                    if structure_id in index.by_id:
                        meta = index.by_id[structure_id]
                        if meta.kind == "structure":
                            struct_meta = meta
                            # Find absolute path from index
                            for path, path_id in index.by_path.items():
                                if path_id == structure_id:
                                    absolute_path = path
                                    break
                except Exception:
                    pass
            
            # Legacy: use file path if available
            if not absolute_path and legacy_file:
                default_path = legacy_file
                absolute_path = (root / default_path).resolve()
                if absolute_path.exists():
                    # Load meta from structure file
                    try:
                        import json
                        data = json.loads(absolute_path.read_text())
                        meta_dict = data.get("__qv_meta__") or data.get("meta") or {}
                        struct_meta = ResourceMeta.from_dict(
                            meta_dict,
                            kind="structure",
                            default_name=Path(legacy_file).stem,
                            default_path=default_path,
                        )
                    except Exception:
                        # Fallback: construct meta from file path
                        default_name = entry.get("name") or Path(legacy_file).stem
                        struct_meta = _entry_to_meta(
                            entry=entry,
                            root=root,
                            kind="structure",
                            default_path=default_path,
                            default_name=default_name,
                        )
            
            # If still no meta, construct from entry (fallback)
            if not struct_meta:
                default_name = entry.get("name") or entry.get("id") or Path(
                    legacy_file or "structure"
                ).stem
                default_path = legacy_file or f"{default_dir.rstrip('/')}/{default_name}.json"
                struct_meta = _entry_to_meta(
                    entry=entry,
                    root=root,
                    kind="structure",
                    default_path=default_path,
                    default_name=default_name,
                )
                if not absolute_path:
                    absolute_path = (root / struct_meta.path).resolve()
            
            ref = StructureRef(
                meta=struct_meta,
                absolute_path=absolute_path or (root / struct_meta.path).resolve(),
                format=entry.get("format", "auto"),
            )
            structures[ref.slug] = ref
        return structures

    @staticmethod
    def _load_workflows(
        root: Path, entries: list[dict], default_dir: str, index: Optional["ResourceIndex"] = None
    ) -> Dict[str, WorkflowRef]:
        """
        Load workflows from project entries using ID-based resolution.
        
        Resolution strategy (in order):
        1. Try registry-based resolution by workflow_id (preferred for ID-only model)
        2. Fall back to entry["path"] if available (legacy support)
        3. Fall back to scanning workflows/*/workflow.yaml by meta.id
        4. Raise error if workflow directory cannot be found
        
        Args:
            root: Project root path
            entries: Workflow entries from project.qv.yml
            default_dir: Default workflows directory name
            index: Optional ResourceIndex (built if None, passed from Project.open())
        """
        from quantumvitas.core.resolution import build_resource_index, require_workflow, ResourceNotFoundError
        from quantumvitas.core.resources import ResourceMeta
        
        workflows: Dict[str, WorkflowRef] = {}
        workflows_dir = root / default_dir.rstrip('/')
        
        # Use provided index or build one if needed
        if index is None:
            try:
                registry = build_resource_index(root)
            except Exception:
                registry = None
        else:
            registry = index
        
        for entry in entries:
            workflow_id = entry.get("workflow_id") or entry.get("id")
            if not workflow_id:
                # Skip entries without ID (should not happen in ID-only model)
                continue
            
            workflow_dir = None
            workflow_yaml_path = None
            workflow_meta = None
            
            # Strategy 1: Try registry-based resolution (preferred for ID-only model)
            if registry:
                try:
                    resolved = require_workflow(root, workflow_id, index=registry)
                    # resolved.absolute_path points to workflow.yaml, so get parent directory
                    if resolved.absolute_path.name == "workflow.yaml":
                        workflow_dir = resolved.absolute_path.parent
                    else:
                        workflow_dir = resolved.absolute_path
                    workflow_yaml_path = workflow_dir / "workflow.yaml"
                    workflow_meta = resolved.meta
                    # Prefer name from entry (project.qv.yml) over registry if entry has a human-readable name
                    entry_name = entry.get("name") or (entry.get("meta") or {}).get("name")
                    if entry_name and entry_name != workflow_meta.slug:
                        # Entry has a human-readable name - use it instead of registry name
                        workflow_meta = ResourceMeta(
                            id=workflow_meta.id,
                            name=entry_name,
                            slug=workflow_meta.slug,
                            path=workflow_meta.path,
                            kind=workflow_meta.kind,
                        )
                except (ResourceNotFoundError, Exception):
                    # Registry resolution failed, try fallback strategies
                    pass
            
            # Strategy 2: Fall back to entry["path"] if available (legacy support)
            if workflow_dir is None:
                entry_path = entry.get("path") or (entry.get("meta") or {}).get("path")
                if entry_path:
                    candidate_dir = (root / entry_path).resolve()
                    candidate_yaml = candidate_dir / "workflow.yaml"
                    if candidate_yaml.exists():
                        try:
                            import yaml
                            wf_data = yaml.safe_load(candidate_yaml.read_text()) or {}
                            wf_meta_dict = wf_data.get("meta") or {}
                            # Verify the ID matches
                            if wf_meta_dict.get("id") == workflow_id:
                                workflow_dir = candidate_dir
                                workflow_yaml_path = candidate_yaml
                                # Prefer name from entry (project.qv.yml) over workflow.yaml if entry has a human-readable name
                                entry_name = entry.get("name") or (entry.get("meta") or {}).get("name")
                                default_name = entry_name if entry_name and entry_name != wf_meta_dict.get("slug") else wf_meta_dict.get("name", "Workflow")
                                workflow_meta = ResourceMeta.from_dict(
                                    wf_meta_dict,
                                    kind="workflow",
                                    default_name=default_name,
                                    default_path=entry_path,
                                )
                                # Override with entry name if it's different from slug (preserves human-readable names)
                                if entry_name and entry_name != workflow_meta.slug:
                                    workflow_meta.name = entry_name
                                break
                        except Exception:
                            continue
            
            # Strategy 3: Scan workflows/*/workflow.yaml by meta.id (last resort)
            if workflow_dir is None and workflows_dir.exists():
                for wf_dir in workflows_dir.iterdir():
                    if not wf_dir.is_dir():
                        continue
                    wf_yaml = wf_dir / "workflow.yaml"
                    if wf_yaml.exists():
                        try:
                            import yaml
                            wf_data = yaml.safe_load(wf_yaml.read_text()) or {}
                            wf_meta_dict = wf_data.get("meta") or {}
                            if wf_meta_dict.get("id") == workflow_id:
                                workflow_dir = wf_dir
                                workflow_yaml_path = wf_yaml
                                # Prefer name from entry (project.qv.yml) over workflow.yaml if entry has a human-readable name
                                entry_name = entry.get("name") or (entry.get("meta") or {}).get("name")
                                default_name = entry_name if entry_name and entry_name != wf_meta_dict.get("slug") else wf_meta_dict.get("name", "Workflow")
                                workflow_meta = ResourceMeta.from_dict(
                                    wf_meta_dict,
                                    kind="workflow",
                                    default_name=default_name,
                                    default_path=wf_meta_dict.get("path") or f"{default_dir.rstrip('/')}/{wf_dir.name}",
                                )
                                # Override with entry name if it's different from slug (preserves human-readable names)
                                if entry_name and entry_name != workflow_meta.slug:
                                    workflow_meta.name = entry_name
                                break
                        except Exception:
                            continue
            
            # Strategy 4: If still not found, raise clear error
            if workflow_dir is None or workflow_yaml_path is None or not workflow_yaml_path.exists():
                raise FileNotFoundError(
                    f"Could not locate workflow directory for id '{workflow_id}' under {workflows_dir}. "
                    "Please ensure the workflow.yaml file exists and contains the correct meta.id."
                )
            
            # Ensure workflow_meta is set (should have been set by one of the strategies above)
            if workflow_meta is None:
                # Fallback: construct from entry (should not happen if strategies above worked)
                default_name = entry.get("name") or "workflow"
                default_path = entry.get("path") or f"{default_dir.rstrip('/')}/{default_name}"
                workflow_meta = _entry_to_meta(
                    entry=entry,
                    root=root,
                    kind="workflow",
                    default_path=default_path,
                    default_name=default_name,
                )
                # Try to load from workflow.yaml to get canonical name/slug
                # But prefer name from entry (project.qv.yml) if it exists and is different from slug
                try:
                    import yaml
                    wf_data = yaml.safe_load(workflow_yaml_path.read_text()) or {}
                    wf_meta = wf_data.get("meta") or {}
                    # Prefer name from entry (project.qv.yml) over workflow.yaml if entry has a human-readable name
                    entry_name = entry.get("name") or (entry.get("meta") or {}).get("name")
                    if entry_name and entry_name != workflow_meta.slug:
                        # Entry has a human-readable name - use it instead of workflow.yaml name
                        workflow_meta.name = entry_name
                    elif wf_meta.get("name"):
                        workflow_meta.name = wf_meta["name"]
                    if wf_meta.get("slug"):
                        workflow_meta.slug = wf_meta["slug"]
                    if wf_meta.get("path"):
                        workflow_meta.path = wf_meta["path"]
                except Exception:
                    pass  # Use defaults from entry
            
            # Create WorkflowRef
            ref = WorkflowRef(
                meta=workflow_meta,
                absolute_path=workflow_dir.resolve(),
            )
            workflows[ref.slug] = ref
        
        return workflows

    @property
    def structures_dir(self) -> Path:
        return self.root / "structures"

    @property
    def workflows_dir(self) -> Path:
        return self.root / "workflows"

    @property
    def pseudo_dir(self) -> Path:
        return self.root / "pseudo"

    @property
    def settings_file(self) -> Path:
        return self.root / "settings.yaml"

    def list_structures(self) -> list[str]:
        return [ref.meta.name for ref in self.structures.values()]

    def get_structure(self, structure_id: str) -> StructureRef:
        # Accept slug, name, or meta id for ergonomics
        if structure_id in self.structures:
            return self.structures[structure_id]

        for ref in self.structures.values():
            if ref.meta.id == structure_id or ref.meta.name == structure_id:
                return ref
        raise KeyError(f"Unknown structure '{structure_id}'")

    def list_workflows(self) -> list[str]:
        return [ref.meta.name for ref in self.workflows.values()]

    def get_workflow_ref(self, workflow_id: str) -> WorkflowRef:
        if workflow_id in self.workflows:
            return self.workflows[workflow_id]
        for ref in self.workflows.values():
            if ref.meta.id == workflow_id or ref.meta.name == workflow_id or ref.meta.slug == workflow_id:
                return ref
        raise KeyError(f"Unknown workflow '{workflow_id}'")

    def get_workflow(self, workflow_id: str):
        """
        Load and return a workflow instance for inspection.
        
        This method loads workflows in inspection mode (materialize_steps=False),
        which does not require pseudopotentials or step materialization.
        For execution, use run_workflow or run_step APIs instead.
        """
        from quantumvitas.workflow.workflow import Workflow

        ref = self.get_workflow_ref(workflow_id)
        return Workflow.from_yaml(ref.resolve_path(self.root), self, materialize_steps=False)

    def structure_ref(self, name: str) -> StructureRef:
        """
        Return a structure reference relative to the structures directory.
        """
        structure_path = self.structures_dir / name
        meta = meta_from_name(
            "structure",
            name=name,
            path=ensure_relative_path(structure_path, base=self.root),
        )
        return StructureRef(meta=meta, absolute_path=structure_path.resolve())


def _entry_to_meta(
    *,
    entry: dict,
    root: Path,
    kind: ResourceKind,
    default_path: str,
    default_name: str,
) -> ResourceMeta:
    path_obj = Path(default_path)
    if path_obj.is_absolute():
        try:
            path_obj = path_obj.relative_to(root)
        except ValueError:
            pass
    relative_path = path_obj.as_posix()

    return ResourceMeta.from_dict(
        entry.get("meta"),
        kind=kind,
        default_name=default_name,
        default_path=relative_path,
    )

