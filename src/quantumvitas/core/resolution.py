"""
Centralized resource resolution for QuantumVITAS.

All selector → resource lookup logic lives here. A selector is any of:
- ULID: exact match on resource id
- slug: exact match (e.g., "si-dos")
- name: exact match (case-insensitive, but NOT normalized to slug)
- path-like string: absolute or relative path to YAML/JSON file

Resolution rules (in order):
1. Path - if selector looks like a path → normalize → load YAML → return resource
2. ULID - if matches any resource ULID → return resource
3. slug - exact slug match within the parent scope
4. name - case-insensitive exact name match

This module does NOT use Path.cwd().

ResourceIndex:
The ResourceIndex is built by scanning resource files (workflow.yaml, *.step.yaml, *.json)
and reading their meta blocks. This is the authoritative source for selector → ID resolution.
project.qv.yml only stores IDs for relationships, not duplicated name/slug/path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING

import json
import yaml

from quantumvitas.core.resources import (
    ResourceMeta,
    ResourceKind,
    ensure_relative_path,
    slugify,
)

if TYPE_CHECKING:
    from quantumvitas.workflow.structure_steps import StructureStepSpec


class AmbiguousSelectorError(ValueError):
    """Raised when a selector matches multiple resources."""
    pass


class SelectorNotFoundError(ValueError):
    """Raised when a selector matches no resources."""
    pass


class ResourceNotFoundError(Exception):
    """
    Raised when a required resource cannot be found.
    
    This is a more specific error than SelectorNotFoundError, intended for
    cases where a resource is required (not optional) and its absence should
    be treated as a hard failure.
    
    Attributes:
        kind: Resource kind ("workflow", "structure", "step", "project")
        selector: Selector that was used (name, slug, path, or ULID)
        id: Resource ID (ULID) if known
        project_root: Project root path where the resource was expected
    """
    def __init__(
        self,
        kind: str,
        selector: str | None = None,
        *,
        id: str | None = None,
        project_root: Path | None = None,
    ):
        self.kind = kind
        self.selector = selector
        self.id = id
        self.project_root = project_root
        
        # Build error message
        parts = [f"{kind.capitalize()} not found"]
        if selector:
            parts.append(f"selector: '{selector}'")
        if id:
            parts.append(f"id: '{id}'")
        if project_root:
            parts.append(f"in project: {project_root}")
        
        message = " - ".join(parts)
        super().__init__(message)


@dataclass
class ResourceIndex:
    """
    Index of all resources in a project, built by scanning resource files.
    
    This is the authoritative source for selector → ID resolution.
    Resource files (workflow.yaml, *.step.yaml, *.json) are scanned and
    their meta blocks are indexed. project.qv.yml only stores IDs for relationships.
    """
    by_id: Dict[str, ResourceMeta] = field(default_factory=dict)
    by_slug: Dict[str, str] = field(default_factory=dict)  # slug -> id
    by_path: Dict[Path, str] = field(default_factory=dict)  # absolute path -> id
    by_name: Dict[str, List[str]] = field(default_factory=dict)  # lower(name) -> [id,...]
    
    def add_resource(self, meta: ResourceMeta, absolute_path: Path) -> None:
        """Add a resource to the index."""
        self.by_id[meta.id] = meta
        self.by_slug[meta.slug] = meta.id
        self.by_path[absolute_path.resolve()] = meta.id
        name_lower = meta.name.lower()
        if name_lower not in self.by_name:
            self.by_name[name_lower] = []
        if meta.id not in self.by_name[name_lower]:
            self.by_name[name_lower].append(meta.id)
    
    def resolve_id(self, selector: str, project_root: Path) -> Optional[str]:
        """
        Resolve a selector to a resource ID.
        
        Resolution order:
        1. ULID (if selector is a ULID)
        2. slug (exact match)
        3. name (case-insensitive exact match)
        4. path (if selector looks like a path)
        
        Returns:
            Resource ID (ULID) if found, None otherwise
        """
        # Strategy 1: ULID
        if _is_ulid_like(selector):
            if selector in self.by_id:
                return selector
        
        # Strategy 2: slug (exact match)
        if selector in self.by_slug:
            return self.by_slug[selector]
        
        # Strategy 3: name (case-insensitive exact match)
        name_lower = selector.lower()
        if name_lower in self.by_name:
            ids = self.by_name[name_lower]
            if len(ids) == 1:
                return ids[0]
            elif len(ids) > 1:
                # Ambiguous - multiple resources with same name
                # For now, return None (caller should handle ambiguity)
                return None
        
        # Strategy 4: path
        if _is_path_like(selector):
            path = Path(selector)
            if not path.is_absolute():
                path = (project_root / path).resolve()
            if path in self.by_path:
                return self.by_path[path]
        
        return None


@dataclass(slots=True)
class ResolvedResource:
    """Result of resolving a selector to a resource."""
    meta: ResourceMeta
    entry: dict  # Raw entry from project.qv.yml
    absolute_path: Path  # Resolved absolute path to resource
    
    @property
    def id(self) -> str:
        return self.meta.id
    
    @property
    def name(self) -> str:
        return self.meta.name
    
    @property
    def slug(self) -> str:
        return self.meta.slug
    
    @property
    def kind(self) -> ResourceKind:
        return self.meta.kind


# ---------------------------------------------------------------------------
# Selector classification
# ---------------------------------------------------------------------------


def _is_ulid_like(s: str) -> bool:
    """Check if string looks like a ULID (26 chars, alphanumeric, uppercase)."""
    if len(s) != 26:
        return False
    return s.isalnum() and s.isupper()


def _is_path_like(s: str) -> bool:
    """Check if string looks like a path."""
    return "/" in s or "\\" in s or s.endswith((".yaml", ".yml", ".json"))


# ---------------------------------------------------------------------------
# ResourceIndex building
# ---------------------------------------------------------------------------

def build_resource_index(project_root: Path) -> ResourceIndex:
    """
    Build a ResourceIndex by scanning resource files in the project.
    
    Scans:
    - workflows/**/workflow.yaml
    - workflows/**/steps/*.step.yaml
    - structures/*.json
    
    Reads meta blocks from each resource file and indexes them.
    This is the authoritative source for selector → ID resolution.
    
    Args:
        project_root: Path to project root directory
        
    Returns:
        ResourceIndex with all resources indexed
    """
    import time
    start_time = time.time()
    project_root = project_root.resolve()
    index = ResourceIndex()
    
    # Scan workflows
    workflows_dir = project_root / "workflows"
    if workflows_dir.exists():
        for workflow_dir in workflows_dir.iterdir():
            if not workflow_dir.is_dir():
                continue
            
            workflow_yaml = workflow_dir / "workflow.yaml"
            if workflow_yaml.exists():
                try:
                    data = yaml.safe_load(workflow_yaml.read_text()) or {}
                    meta_dict = data.get("meta", {})
                    if meta_dict and meta_dict.get("id"):
                        from quantumvitas.core.resources import ResourceMeta
                        default_name = meta_dict.get("name") or workflow_dir.name
                        default_path = meta_dict.get("path") or f"workflows/{workflow_dir.name}"
                        meta = ResourceMeta.from_dict(
                            meta_dict, 
                            kind="workflow",
                            default_name=default_name,
                            default_path=default_path,
                        )
                        index.add_resource(meta, workflow_yaml)
                except Exception as e:
                    # Skip invalid workflow files (log in debug mode if needed)
                    continue
            
            # Scan steps in this workflow
            steps_dir = workflow_dir / "steps"
            if steps_dir.exists():
                for step_file in steps_dir.glob("*.step.yaml"):
                    try:
                        data = yaml.safe_load(step_file.read_text()) or {}
                        meta_dict = data.get("meta", {})
                        if meta_dict and meta_dict.get("id"):
                            from quantumvitas.core.resources import ResourceMeta
                            default_name = meta_dict.get("name") or step_file.stem
                            default_path = meta_dict.get("path") or f"workflows/{workflow_dir.name}/steps/{step_file.name}"
                            meta = ResourceMeta.from_dict(
                                meta_dict,
                                kind="step",
                                default_name=default_name,
                                default_path=default_path,
                            )
                            index.add_resource(meta, step_file)
                    except Exception:
                        # Skip invalid step files
                        continue
    
    # Scan structures
    structures_dir = project_root / "structures"
    if structures_dir.exists():
        for struct_file in structures_dir.glob("*.json"):
            try:
                data = json.loads(struct_file.read_text())
                # Handle both __qv_meta__ wrapper and direct meta
                meta_dict = data.get("__qv_meta__") or data.get("meta")
                if meta_dict and meta_dict.get("id"):
                    from quantumvitas.core.resources import ResourceMeta
                    default_name = meta_dict.get("name") or struct_file.stem
                    default_path = meta_dict.get("path") or f"structures/{struct_file.name}"
                    meta = ResourceMeta.from_dict(
                        meta_dict,
                        kind="structure",
                        default_name=default_name,
                        default_path=default_path,
                    )
                    index.add_resource(meta, struct_file)
            except Exception:
                # Skip invalid structure files
                continue
    
    duration = time.time() - start_time
    if duration > 0.1:  # Only log if it takes more than 100ms
        import sys
        import traceback
        # Get caller info for debugging
        frame = sys._getframe(1)
        caller_file = frame.f_code.co_filename
        caller_name = frame.f_code.co_name
        caller_line = frame.f_lineno
        sys.stderr.write(
            f"[build_resource_index] SLOW: {duration:.3f}s for {project_root} "
            f"(called from {caller_file}:{caller_line} in {caller_name})\n"
        )
        sys.stderr.flush()
    
    return index


# ---------------------------------------------------------------------------
# Entry helpers
# ---------------------------------------------------------------------------


def _entry_to_meta(entry: dict, kind: ResourceKind, default_path: str) -> ResourceMeta:
    """Extract or create ResourceMeta from an entry dict."""
    meta_dict = entry.get("meta") or {}
    from quantumvitas.core.resources import generate_resource_id
    
    resource_id = meta_dict.get("id") or entry.get("id") or generate_resource_id()
    name = meta_dict.get("name") or entry.get("name") or kind.capitalize()
    slug = meta_dict.get("slug") or slugify(name)
    path = meta_dict.get("path") or entry.get("path") or entry.get("file") or default_path
    
    return ResourceMeta(
        id=str(resource_id),
        name=name,
        slug=slug,
        path=path,
        kind=kind,
    )


def _entry_matches_ulid(entry: dict, ulid: str) -> bool:
    """Check if entry has the given ULID."""
    meta = entry.get("meta") or {}
    entry_id = meta.get("id") or entry.get("id")
    return entry_id == ulid


def _entry_matches_slug(entry: dict, slug: str) -> bool:
    """Check if entry has the given slug (exact match)."""
    meta = entry.get("meta") or {}
    entry_slug = meta.get("slug") or slugify(
        meta.get("name") or entry.get("name") or ""
    )
    return entry_slug == slug


def _entry_matches_name(entry: dict, name: str) -> bool:
    """Check if entry has the given name (case-insensitive exact match)."""
    meta = entry.get("meta") or {}
    entry_name = meta.get("name") or entry.get("name") or ""
    return entry_name.lower() == name.lower()


def _entry_matches_path(entry: dict, rel_path: str) -> bool:
    """Check if entry's path matches the given relative path."""
    meta = entry.get("meta") or {}
    entry_path = meta.get("path") or entry.get("path") or entry.get("file") or ""
    return Path(entry_path).as_posix() == Path(rel_path).as_posix()


# ---------------------------------------------------------------------------
# Structure resolution
# ---------------------------------------------------------------------------


def resolve_structure(
    project_root: Path,
    selector: str,
    config: Optional[dict] = None,
    index: Optional[ResourceIndex] = None,
) -> ResolvedResource:
    """
    Resolve a structure selector to a resource.
    
    Resolution order (preferred first):
    1. ID (ULID) via registry: if selector is 26-char ULID, resolve by ID
    2. Slug/name via registry: match by meta.slug or meta.name (case-insensitive)
    3. Path-based resolution: match by meta.path (legacy/compat)
    4. Config fallback: scan project.qv.yml entries (backwards compatibility)
    
    Uses ResourceIndex (built from resource files) as the authoritative source.
    
    Args:
        project_root: Path to project root (contains project.qv.yml)
        selector: ULID, slug, name, or path to structure
        config: Optional pre-loaded config dict (loaded if None)
        index: Optional ResourceIndex (built if None)
        
    Returns:
        ResolvedResource for the structure
        
    Raises:
        SelectorNotFoundError: If no structure matches
        AmbiguousSelectorError: If multiple structures match
    """
    # Build index if not provided
    if index is None:
        index = build_resource_index(project_root)
    
    # Handle None selector (should not happen, but be defensive)
    if selector is None:
        raise ValueError("Structure selector cannot be None")
    
    selector = selector.strip()
    
    # Try to resolve via ResourceIndex first
    resource_id = index.resolve_id(selector, project_root)
    if resource_id:
        # Found in index - get meta and build ResolvedResource
        meta = index.by_id[resource_id]
        if meta.kind != "structure":
            raise SelectorNotFoundError(f"Resource '{selector}' is not a structure (kind: {meta.kind})")
        
        # Find absolute path
        abs_path = None
        for path, path_id in index.by_path.items():
            if path_id == resource_id:
                abs_path = path
                break
        
        if abs_path is None:
            # Fallback: construct from meta.path
            abs_path = (project_root / meta.path).resolve()
        
        # Build entry dict for backwards compatibility (minimal, ID-only)
        entry = {"id": resource_id, "meta": meta.to_dict()}
        
        return ResolvedResource(meta=meta, entry=entry, absolute_path=abs_path)
    
    # Fallback to legacy config-based resolution for backwards compatibility
    if config is None:
        config = _load_config(project_root)
    
    entries = config.get("structures", [])
    
    # Strategy 1: Path
    if _is_path_like(selector):
        resolved = _resolve_structure_by_path(project_root, entries, selector)
        if resolved:
            return resolved
    
    # Strategy 2: ULID
    if _is_ulid_like(selector):
        matches = [e for e in entries if _entry_matches_ulid(e, selector)]
        if len(matches) == 1:
            return _structure_to_resolved(project_root, matches[0])
        if len(matches) > 1:
            raise AmbiguousSelectorError(f"ULID '{selector}' matches multiple structures")
    
    # Strategy 3: slug (exact match)
    slug_matches = [e for e in entries if _entry_matches_slug(e, selector)]
    if len(slug_matches) == 1:
        return _structure_to_resolved(project_root, slug_matches[0])
    if len(slug_matches) > 1:
        raise AmbiguousSelectorError(f"Slug '{selector}' matches multiple structures")
    
    # Strategy 4: name (case-insensitive exact match)
    name_matches = [e for e in entries if _entry_matches_name(e, selector)]
    if len(name_matches) == 1:
        return _structure_to_resolved(project_root, name_matches[0])
    if len(name_matches) > 1:
        raise AmbiguousSelectorError(f"Name '{selector}' matches multiple structures")
    
    raise SelectorNotFoundError(f"Structure '{selector}' not found")


def _resolve_structure_by_path(
    project_root: Path,
    entries: list,
    selector: str,
) -> Optional[ResolvedResource]:
    """Try to resolve structure by path."""
    candidate = Path(selector)
    if not candidate.is_absolute():
        candidate = project_root / selector
    
    try:
        resolved = candidate.resolve()
    except (FileNotFoundError, OSError):
        return None
    
    if not resolved.exists():
        return None
    
    try:
        rel_path = ensure_relative_path(resolved, base=project_root)
    except ValueError:
        return None
    
    for entry in entries:
        if _entry_matches_path(entry, rel_path):
            return _structure_to_resolved(project_root, entry)
    
    return None


def make_structure_selector_resolver(
    project_root: Path,
    config: Optional[dict] = None,
    index: Optional[ResourceIndex] = None,
) -> callable:
    """
    Create a resolver function that converts structure selectors to structure_id (ULID).
    
    This is used for normalizing legacy 'structure' selectors in step specs to structure_id.
    
    Args:
        project_root: Project root path
        config: Optional pre-loaded config dict (loaded if None)
        index: Optional ResourceIndex (built if None)
        
    Returns:
        A callable(selector: str) -> str that resolves a structure selector to structure_id.
        Raises ResourceNotFoundError if selector cannot be resolved.
    """
    def resolver(selector: str) -> str:
        resolved = resolve_structure(project_root, selector, config=config, index=index)
        return resolved.meta.id
    return resolver


def _structure_to_resolved(project_root: Path, entry: dict) -> ResolvedResource:
    """Convert a structure entry to ResolvedResource."""
    # ID-only model: entry only has structure_id, need to load structure file to get meta
    structure_id = entry.get("structure_id") or entry.get("id")
    
    # Try to find and load structure file by ID
    structures_dir = project_root / "structures"
    if structures_dir.exists() and structure_id:
        for struct_file in structures_dir.glob("*.json"):
            try:
                import json
                struct_data = json.loads(struct_file.read_text())
                struct_meta_dict = struct_data.get("__qv_meta__") or struct_data.get("meta")
                if struct_meta_dict and struct_meta_dict.get("id") == structure_id:
                    # Found matching structure file - use its meta
                    from quantumvitas.core.resources import ResourceMeta
                    resource_meta = ResourceMeta.from_dict(
                        struct_meta_dict,
                        kind="structure",
                        default_name=struct_meta_dict.get("name", "Structure"),
                        default_path=struct_meta_dict.get("path", f"structures/{struct_file.name}"),
                    )
                    abs_path = struct_file.resolve()
                    return ResolvedResource(meta=resource_meta, entry=entry, absolute_path=abs_path)
            except Exception:
                continue
    
    # Fallback: use entry data (legacy format or structure file not found)
    meta = entry.get("meta") or {}
    default_name = entry.get("name") or meta.get("name") or "Structure"
    default_path = entry.get("file") or meta.get("path") or f"structures/{slugify(default_name)}.json"
    
    resource_meta = _entry_to_meta(entry, "structure", default_path)
    abs_path = (project_root / resource_meta.path).resolve()
    
    return ResolvedResource(meta=resource_meta, entry=entry, absolute_path=abs_path)


# ---------------------------------------------------------------------------
# Workflow resolution
# ---------------------------------------------------------------------------


def resolve_workflow(
    project_root: Path,
    selector: str,
    config: Optional[dict] = None,
    index: Optional[ResourceIndex] = None,
) -> ResolvedResource:
    """
    Resolve a workflow selector to a resource.
    
    Uses ResourceIndex (built from resource files) as the authoritative source.
    Falls back to config entries for backwards compatibility.
    
    Args:
        project_root: Path to project root (contains project.qv.yml)
        selector: ULID, slug, name, or path to workflow directory
        config: Optional pre-loaded config dict (loaded if None)
        index: Optional ResourceIndex (built if None)
        
    Returns:
        ResolvedResource for the workflow
        
    Raises:
        SelectorNotFoundError: If no workflow matches
        AmbiguousSelectorError: If multiple workflows match
        ValueError: If selector is None
    """
    # Build index if not provided
    if index is None:
        index = build_resource_index(project_root)
    
    # Handle None selector (should not happen, but be defensive)
    if selector is None:
        raise ValueError("Workflow selector cannot be None")
    
    selector = selector.strip()
    
    # Try to resolve via ResourceIndex first
    resource_id = index.resolve_id(selector, project_root)
    if resource_id:
        # Found in index - get meta and build ResolvedResource
        meta = index.by_id[resource_id]
        if meta.kind != "workflow":
            raise SelectorNotFoundError(f"Resource '{selector}' is not a workflow (kind: {meta.kind})")
        
        # Find absolute path (workflow directory)
        abs_path = None
        for path, path_id in index.by_path.items():
            if path_id == resource_id:
                # workflow.yaml path -> workflow directory
                abs_path = path.parent
                break
        
        if abs_path is None:
            # Fallback: construct from meta.path
            abs_path = (project_root / meta.path).resolve()
        
        # Build entry dict for backwards compatibility (minimal, ID-only)
        entry = {"id": resource_id, "meta": meta.to_dict()}
        
        return ResolvedResource(meta=meta, entry=entry, absolute_path=abs_path)
    
    # Fallback to legacy config-based resolution for backwards compatibility
    if config is None:
        config = _load_config(project_root)
    
    entries = config.get("workflows", [])
    selector = selector.strip()
    
    # Strategy 1: Path
    if _is_path_like(selector):
        resolved = _resolve_workflow_by_path(project_root, entries, selector)
        if resolved:
            return resolved
    
    # Strategy 2: ULID
    if _is_ulid_like(selector):
        matches = [e for e in entries if _entry_matches_ulid(e, selector)]
        if len(matches) == 1:
            return _workflow_to_resolved(project_root, matches[0])
        if len(matches) > 1:
            raise AmbiguousSelectorError(f"ULID '{selector}' matches multiple workflows")
    
    # Strategy 3: slug (exact match)
    slug_matches = [e for e in entries if _entry_matches_slug(e, selector)]
    if len(slug_matches) == 1:
        return _workflow_to_resolved(project_root, slug_matches[0])
    if len(slug_matches) > 1:
        raise AmbiguousSelectorError(f"Slug '{selector}' matches multiple workflows")
    
    # Strategy 4: name (case-insensitive exact match)
    name_matches = [e for e in entries if _entry_matches_name(e, selector)]
    if len(name_matches) == 1:
        return _workflow_to_resolved(project_root, name_matches[0])
    if len(name_matches) > 1:
        raise AmbiguousSelectorError(f"Name '{selector}' matches multiple workflows")
    
    raise SelectorNotFoundError(f"Workflow '{selector}' not found")


def _resolve_workflow_by_path(
    project_root: Path,
    entries: list,
    selector: str,
) -> Optional[ResolvedResource]:
    """Try to resolve workflow by path."""
    candidate = Path(selector)
    if not candidate.is_absolute():
        candidate = project_root / selector
    
    try:
        resolved = candidate.resolve()
    except (FileNotFoundError, OSError):
        return None
    
    if not resolved.exists():
        return None
    
    try:
        rel_path = ensure_relative_path(resolved, base=project_root)
    except ValueError:
        return None
    
    for entry in entries:
        if _entry_matches_path(entry, rel_path):
            return _workflow_to_resolved(project_root, entry)
    
    return None


def _workflow_to_resolved(project_root: Path, entry: dict) -> ResolvedResource:
    """Convert a workflow entry to ResolvedResource."""
    # ID-only model: entry only has workflow_id (or id), need to load workflow.yaml to get meta
    workflow_id = entry.get("workflow_id") or entry.get("id")
    
    # Try to find and load workflow.yaml by ID
    workflows_dir = project_root / "workflows"
    if workflows_dir.exists() and workflow_id:
        for workflow_dir in workflows_dir.iterdir():
            if not workflow_dir.is_dir():
                continue
            workflow_yaml = workflow_dir / "workflow.yaml"
            if workflow_yaml.exists():
                try:
                    import yaml
                    wf_data = yaml.safe_load(workflow_yaml.read_text())
                    wf_meta_dict = wf_data.get("meta") or {}
                    if wf_meta_dict.get("id") == workflow_id:
                        # Found matching workflow - use its meta
                        from quantumvitas.core.resources import ResourceMeta
                        resource_meta = ResourceMeta.from_dict(
                            wf_meta_dict,
                            kind="workflow",
                            default_name=wf_meta_dict.get("name", "Workflow"),
                            default_path=wf_meta_dict.get("path", f"workflows/{workflow_dir.name}"),
                        )
                        abs_path = workflow_yaml.resolve()
                        return ResolvedResource(meta=resource_meta, entry=entry, absolute_path=abs_path)
                except Exception:
                    continue
    
    # Fallback: use entry data (legacy format or workflow.yaml not found)
    meta = entry.get("meta") or {}
    default_name = entry.get("name") or meta.get("name") or "Workflow"
    default_path = entry.get("path") or meta.get("path") or f"workflows/{slugify(default_name)}"
    
    resource_meta = _entry_to_meta(entry, "workflow", default_path)
    abs_path = (project_root / resource_meta.path / "workflow.yaml").resolve()
    
    return ResolvedResource(meta=resource_meta, entry=entry, absolute_path=abs_path)
    """Convert a workflow entry to ResolvedResource."""
    meta = entry.get("meta") or {}
    default_name = entry.get("name") or meta.get("name") or "Workflow"
    default_path = entry.get("path") or meta.get("path") or f"workflows/{slugify(default_name)}"
    
    resource_meta = _entry_to_meta(entry, "workflow", default_path)
    abs_path = (project_root / resource_meta.path).resolve()
    
    return ResolvedResource(meta=resource_meta, entry=entry, absolute_path=abs_path)


# ---------------------------------------------------------------------------
# Step resolution
# ---------------------------------------------------------------------------


def resolve_step(
    project_root: Path,
    workflow_selector: str,
    step_selector: str,
    config: Optional[dict] = None,
    index: Optional[ResourceIndex] = None,
) -> ResolvedResource:
    """
    Resolve a step selector within a workflow.
    
    Uses ResourceIndex (built from resource files) as the authoritative source.
    Falls back to scanning step files for backwards compatibility.
    
    Args:
        project_root: Path to project root
        workflow_selector: Selector for parent workflow
        step_selector: ULID, id, name, or path to step YAML
        config: Optional pre-loaded config dict
        index: Optional ResourceIndex (built if None)
        
    Returns:
        ResolvedResource for the step
        
    Raises:
        SelectorNotFoundError: If workflow or step not found
    """
    # Resolve workflow first
    workflow = resolve_workflow(project_root, workflow_selector, config)
    # workflow.absolute_path points to workflow.yaml, so get the parent directory
    if workflow.absolute_path.name == "workflow.yaml":
        workflow_dir = workflow.absolute_path.parent
    else:
        workflow_dir = workflow.absolute_path
    
    # Handle None step_selector (should not happen, but be defensive)
    if step_selector is None:
        raise ValueError("Step selector cannot be None")
    
    step_selector = step_selector.strip()
    
    # Build index if not provided
    if index is None:
        index = build_resource_index(project_root)
    
    # Strategy 1: Try ResourceIndex first (preferred)
    resource_id = index.resolve_id(step_selector, project_root)
    if resource_id:
        meta = index.by_id.get(resource_id)
        if meta and meta.kind == "step":
            # Verify this step belongs to the workflow
            # Check if step path is within workflow directory
            step_path = project_root / meta.path
            if step_path.is_relative_to(workflow_dir):
                # Find absolute path
                abs_path = None
                for path, path_id in index.by_path.items():
                    if path_id == resource_id:
                        abs_path = path
                        break
                
                if abs_path is None:
                    abs_path = step_path.resolve()
                
                # Build entry dict for backwards compatibility
                try:
                    entry_data = yaml.safe_load(abs_path.read_text()) or {}
                except Exception:
                    entry_data = {}
                
                return ResolvedResource(meta=meta, entry=entry_data, absolute_path=abs_path)
    
    # Strategy 2: Path (fallback for backwards compat)
    if _is_path_like(step_selector):
        step_path = _resolve_step_by_path(workflow_dir, step_selector)
        if step_path:
            return _step_path_to_resolved(step_path, project_root)
    
    # Strategy 3: Scan step files (fallback for backwards compat)
    steps_dir = workflow_dir / "steps"
    step_files = list(steps_dir.glob("*.step.yaml")) if steps_dir.exists() else []
    step_entries = []
    for step_file in step_files:
        try:
            data = yaml.safe_load(step_file.read_text()) or {}
            step_entries.append((step_file, data))
        except Exception:
            continue
    
    # Strategy 4: ULID (in step meta)
    if _is_ulid_like(step_selector):
        for step_file, data in step_entries:
            meta = data.get("meta") or {}
            if meta.get("id") == step_selector:
                return _step_path_to_resolved(step_file, project_root)
    
    # Strategy 5: step meta.name or meta.slug (exact match)
    for step_file, data in step_entries:
        meta = data.get("meta") or {}
        step_name = meta.get("name", "")
        step_slug = meta.get("slug", "")
        if step_name.lower() == step_selector.lower() or step_slug.lower() == step_selector.lower():
            return _step_path_to_resolved(step_file, project_root)
    
    # Strategy 6: step id field from step YAML (exact match) - check both top-level and meta
    for step_file, data in step_entries:
        step_id = data.get("id", "")
        meta = data.get("meta") or {}
        meta_id = meta.get("id", "")
        # Check both top-level id and meta.id
        if step_id.lower() == step_selector.lower() or meta_id.lower() == step_selector.lower():
            return _step_path_to_resolved(step_file, project_root)
    
    # Strategy 7: step_type (exact match) - for backwards compatibility
    for step_file, data in step_entries:
        step_type = data.get("step_type", "")
        if step_type.lower() == step_selector.lower():
            return _step_path_to_resolved(step_file, project_root)
    
    # Strategy 8: filename stem match
    for step_file, _ in step_entries:
        stem = step_file.stem.replace(".step", "")
        if stem.lower() == step_selector.lower():
            return _step_path_to_resolved(step_file, project_root)
    
    raise SelectorNotFoundError(
        f"Step '{step_selector}' not found in workflow '{workflow.name}'"
    )


def _resolve_step_by_path(workflow_dir: Path, selector: str) -> Optional[Path]:
    """Try to resolve step by direct path."""
    # Handle relative paths like "steps/scf.step.yaml"
    if selector.startswith("steps/"):
        selector = selector[6:]  # Remove "steps/" prefix
    
    candidates = [
        Path(selector),
        workflow_dir / selector,
        workflow_dir / "steps" / selector,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.suffix in (".yaml", ".yml"):
            return candidate.resolve()
    return None


def _step_path_to_resolved(step_path: Path, project_root: Path) -> ResolvedResource:
    """Convert a step file path to ResolvedResource."""
    try:
        data = yaml.safe_load(step_path.read_text()) or {}
    except Exception:
        data = {}
    
    meta_dict = data.get("meta") or {}
    step_id = meta_dict.get("id") or data.get("id") or step_path.stem.replace(".step", "")
    step_name = meta_dict.get("name") or data.get("step_type") or step_id
    
    from quantumvitas.core.resources import generate_resource_id
    
    resource_meta = ResourceMeta(
        id=meta_dict.get("id") or generate_resource_id(),
        name=step_name,
        slug=slugify(step_name),
        path=ensure_relative_path(step_path, base=project_root),
        kind="step",
    )
    
    return ResolvedResource(meta=resource_meta, entry=data, absolute_path=step_path)


# ---------------------------------------------------------------------------
# Project resolution (simple case)
# ---------------------------------------------------------------------------


def resolve_project(selector: str) -> ResolvedResource:
    """
    Resolve a project selector (typically a path).
    
    Args:
        selector: Path to project root
        
    Returns:
        ResolvedResource for the project
        
    Raises:
        SelectorNotFoundError: If project.qv.yml not found
    """
    project_root = Path(selector).expanduser().resolve()
    config_file = project_root / "project.qv.yml"
    
    if not config_file.exists():
        raise SelectorNotFoundError(f"No project.qv.yml found at {project_root}")
    
    config = _load_config(project_root)
    project_section = config.get("project", {})
    
    meta_dict = project_section.get("meta") or {}
    from quantumvitas.core.resources import generate_resource_id
    
    resource_meta = ResourceMeta(
        id=meta_dict.get("id") or generate_resource_id(),
        name=meta_dict.get("name") or project_section.get("name") or project_root.name,
        slug=meta_dict.get("slug") or slugify(project_root.name),
        path=".",
        kind="project",
    )
    
    return ResolvedResource(
        meta=resource_meta,
        entry=project_section,
        absolute_path=project_root,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config(project_root: Path) -> dict:
    """Load project.qv.yml from project root."""
    config_file = project_root / "project.qv.yml"
    if not config_file.exists():
        raise SelectorNotFoundError(f"No project.qv.yml found at {project_root}")
    return yaml.safe_load(config_file.read_text()) or {}


# ---------------------------------------------------------------------------
# Required resource helpers (raise ResourceNotFoundError on failure)
# ---------------------------------------------------------------------------


def require_structure(
    project_root: Path,
    selector_or_id: str,
    config: Optional[dict] = None,
    index: Optional[ResourceIndex] = None,
) -> ResolvedResource:
    """
    Require a structure resource - raise ResourceNotFoundError if not found.
    
    This is a wrapper around resolve_structure that converts SelectorNotFoundError
    to ResourceNotFoundError for clearer error handling in API/CLI layers.
    
    Args:
        project_root: Path to project root
        selector_or_id: Structure selector (name, slug, path, or ULID)
        config: Optional pre-loaded config dict
        index: Optional ResourceIndex (built if None)
        
    Returns:
        ResolvedResource for the structure
        
    Raises:
        ResourceNotFoundError: If structure not found
        AmbiguousSelectorError: If multiple structures match
    """
    try:
        return resolve_structure(project_root, selector_or_id, config, index)
    except SelectorNotFoundError as e:
        # Convert to ResourceNotFoundError for API/CLI layers
        raise ResourceNotFoundError(
            kind="structure",
            selector=selector_or_id,
            project_root=project_root,
        ) from e


def require_workflow(
    project_root: Path,
    selector_or_id: str,
    config: Optional[dict] = None,
    index: Optional[ResourceIndex] = None,
) -> ResolvedResource:
    """
    Require a workflow resource - raise ResourceNotFoundError if not found.
    
    This is a wrapper around resolve_workflow that converts SelectorNotFoundError
    to ResourceNotFoundError for clearer error handling in API/CLI layers.
    
    Args:
        project_root: Path to project root
        selector_or_id: Workflow selector (name, slug, path, or ULID)
        config: Optional pre-loaded config dict
        index: Optional ResourceIndex (built if None)
        
    Returns:
        ResolvedResource for the workflow
        
    Raises:
        ResourceNotFoundError: If workflow not found
        AmbiguousSelectorError: If multiple workflows match
    """
    try:
        return resolve_workflow(project_root, selector_or_id, config, index)
    except SelectorNotFoundError as e:
        # Convert to ResourceNotFoundError for API/CLI layers
        raise ResourceNotFoundError(
            kind="workflow",
            selector=selector_or_id,
            project_root=project_root,
        ) from e


def require_step(
    project_root: Path,
    workflow_selector: str,
    step_selector_or_id: str,
    config: Optional[dict] = None,
) -> ResolvedResource:
    """
    Require a step resource within a workflow - raise ResourceNotFoundError if not found.
    
    This is a wrapper around resolve_step that converts SelectorNotFoundError
    to ResourceNotFoundError for clearer error handling in API/CLI layers.
    
    Args:
        project_root: Path to project root
        workflow_selector: Workflow selector (name, slug, path, or ULID)
        step_selector_or_id: Step selector (ULID, id, name, or path)
        config: Optional pre-loaded config dict
        
    Returns:
        ResolvedResource for the step
        
    Raises:
        ResourceNotFoundError: If workflow or step not found
        AmbiguousSelectorError: If multiple workflows match
    """
    try:
        return resolve_step(project_root, workflow_selector, step_selector_or_id, config)
    except SelectorNotFoundError as e:
        # Convert to ResourceNotFoundError for API/CLI layers
        # Try to extract workflow name for better error message
        workflow_name = workflow_selector
        try:
            workflow = resolve_workflow(project_root, workflow_selector, config)
            workflow_name = workflow.meta.name
        except Exception:
            pass
        
        raise ResourceNotFoundError(
            kind="step",
            selector=step_selector_or_id,
            project_root=project_root,
        ) from e


def list_structures(project_root: Path, config: Optional[dict] = None) -> List[ResolvedResource]:
    """List all structures in a project."""
    if config is None:
        config = _load_config(project_root)
    
    results = []
    for entry in config.get("structures", []):
        try:
            results.append(_structure_to_resolved(project_root, entry))
        except Exception:
            continue
    return results


def list_workflows(project_root: Path, config: Optional[dict] = None) -> List[ResolvedResource]:
    """List all workflows in a project."""
    if config is None:
        config = _load_config(project_root)
    
    results = []
    for entry in config.get("workflows", []):
        try:
            results.append(_workflow_to_resolved(project_root, entry))
        except Exception:
            continue
    return results


def list_steps(
    project_root: Path,
    workflow_selector: str,
    config: Optional[dict] = None,
) -> List[ResolvedResource]:
    """List all steps in a workflow."""
    workflow = resolve_workflow(project_root, workflow_selector, config)
    steps_dir = workflow.absolute_path / "steps"
    
    results = []
    if steps_dir.exists():
        for step_file in steps_dir.glob("*.step.yaml"):
            try:
                results.append(_step_path_to_resolved(step_file, project_root))
            except Exception:
                continue
    return results

