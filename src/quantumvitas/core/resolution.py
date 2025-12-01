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
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

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
) -> ResolvedResource:
    """
    Resolve a structure selector to a resource.
    
    Args:
        project_root: Path to project root (contains project.qv.yml)
        selector: ULID, slug, name, or path to structure
        config: Optional pre-loaded config dict (loaded if None)
        
    Returns:
        ResolvedResource for the structure
        
    Raises:
        SelectorNotFoundError: If no structure matches
        AmbiguousSelectorError: If multiple structures match
    """
    if config is None:
        config = _load_config(project_root)
    
    entries = config.get("structures", [])
    selector = selector.strip()
    
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


def _structure_to_resolved(project_root: Path, entry: dict) -> ResolvedResource:
    """Convert a structure entry to ResolvedResource."""
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
) -> ResolvedResource:
    """
    Resolve a workflow selector to a resource.
    
    Args:
        project_root: Path to project root (contains project.qv.yml)
        selector: ULID, slug, name, or path to workflow directory
        config: Optional pre-loaded config dict (loaded if None)
        
    Returns:
        ResolvedResource for the workflow
        
    Raises:
        SelectorNotFoundError: If no workflow matches
        AmbiguousSelectorError: If multiple workflows match
    """
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
) -> ResolvedResource:
    """
    Resolve a step selector within a workflow.
    
    Args:
        project_root: Path to project root
        workflow_selector: Selector for parent workflow
        step_selector: ULID, id, name, or path to step YAML
        config: Optional pre-loaded config dict
        
    Returns:
        ResolvedResource for the step
        
    Raises:
        SelectorNotFoundError: If workflow or step not found
    """
    workflow = resolve_workflow(project_root, workflow_selector, config)
    workflow_dir = workflow.absolute_path
    steps_dir = workflow_dir / "steps"
    
    step_selector = step_selector.strip()
    
    # Strategy 1: Path
    if _is_path_like(step_selector):
        step_path = _resolve_step_by_path(workflow_dir, step_selector)
        if step_path:
            return _step_path_to_resolved(step_path, project_root)
    
    # Collect all step files
    step_files = list(steps_dir.glob("*.step.yaml")) if steps_dir.exists() else []
    step_entries = []
    for step_file in step_files:
        try:
            data = yaml.safe_load(step_file.read_text()) or {}
            step_entries.append((step_file, data))
        except Exception:
            continue
    
    # Strategy 2: ULID (in step meta)
    if _is_ulid_like(step_selector):
        for step_file, data in step_entries:
            meta = data.get("meta") or {}
            if meta.get("id") == step_selector:
                return _step_path_to_resolved(step_file, project_root)
    
    # Strategy 3: step id/type (exact match)
    for step_file, data in step_entries:
        step_id = data.get("id", "")
        step_type = data.get("step_type", "")
        if step_id.lower() == step_selector.lower() or step_type.lower() == step_selector.lower():
            return _step_path_to_resolved(step_file, project_root)
    
    # Strategy 4: filename stem match
    for step_file, _ in step_entries:
        stem = step_file.stem.replace(".step", "")
        if stem.lower() == step_selector.lower():
            return _step_path_to_resolved(step_file, project_root)
    
    raise SelectorNotFoundError(
        f"Step '{step_selector}' not found in workflow '{workflow.name}'"
    )


def _resolve_step_by_path(workflow_dir: Path, selector: str) -> Optional[Path]:
    """Try to resolve step by direct path."""
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

