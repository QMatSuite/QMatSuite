"""
Project configuration helpers for managing structures, workflows, and steps.

These utilities operate on the raw project config dict loaded from project.qv.yml.
They are used by both CLI and programmatic APIs.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence, TYPE_CHECKING

import yaml

from quantumvitas.core.resources import (
    ensure_relative_path,
    generate_resource_id,
    generate_unique_name_and_slug,
    slugify,
)

if TYPE_CHECKING:
    from quantumvitas.workflow.structure_steps import StructureStepSpec


class ProjectConfigError(ValueError):
    """Raised when project configuration operations fail."""
    pass


class ResourceNotFoundError(ProjectConfigError):
    """Raised when a structure or workflow is not found."""
    pass


# ---------------------------------------------------------------------------
# Config I/O
# ---------------------------------------------------------------------------


def load_project_config(project_root: Path) -> dict:
    """Load project.qv.yml from the given project root."""
    config_file = project_root / "project.qv.yml"
    if not config_file.exists():
        raise ProjectConfigError(f"project.qv.yml not found under {project_root}")
    return yaml.safe_load(config_file.read_text()) or {}


def save_project_config(project_root: Path, data: dict) -> None:
    """Write project configuration to project.qv.yml."""
    config_file = project_root / "project.qv.yml"
    config_file.write_text(yaml.safe_dump(data, sort_keys=False))


# ---------------------------------------------------------------------------
# Entry utilities
# ---------------------------------------------------------------------------


def collect_slugs(entries: list[dict], *, exclude: Optional[dict] = None) -> list[str]:
    """Collect all slugs from a list of structure or workflow entries."""
    slugs: list[str] = []
    for entry in entries:
        if exclude is not None and entry is exclude:
            continue
        meta = entry.get("meta") or {}
        slug = meta.get("slug") or slugify(entry.get("name") or entry.get("id") or "")
        if slug:
            slugs.append(slug)
    return slugs


def entry_matches(entry: dict, identifier: str) -> bool:
    """
    Check if an entry matches the given identifier.
    
    Matches against (in order): id (ULID), name, slug, file path.
    Comparison is case-insensitive for names/slugs.
    """
    ident = identifier.strip()
    ident_lower = ident.lower()
    meta = entry.get("meta") or {}
    
    # Check id first (case-sensitive, exact match for ULID)
    entry_id = meta.get("id") or entry.get("id")
    if entry_id and entry_id == ident:
        return True
    
    # Check other candidates (case-insensitive)
    candidates = filter(
        None,
        [
            entry.get("name"),
            entry.get("file"),
            entry.get("path"),
            meta.get("slug"),
            meta.get("name"),
        ],
    )
    for candidate in candidates:
        if str(candidate).lower() == ident_lower:
            return True
    return False


def entry_display_name(entry: dict, fallback: str = "resource") -> str:
    """Get a human-readable display name for an entry."""
    meta = entry.get("meta") or {}
    return entry.get("name") or meta.get("name") or entry.get("id") or fallback


def ensure_structure_entry_defaults(entry: dict) -> None:
    """Ensure a structure entry has all required default fields."""
    meta = entry.setdefault("meta", {})
    if not meta.get("id"):
        meta["id"] = generate_resource_id()
    name_candidate = entry.get("name") or meta.get("name") or entry.get("id") or "Structure"
    meta.setdefault("name", name_candidate)
    entry.setdefault("name", meta["name"])
    slug_candidate = meta.get("slug") or slugify(meta["name"])
    meta["slug"] = slug_candidate
    file_path = entry.get("file") or meta.get("path")
    if file_path:
        meta.setdefault("path", file_path)
    else:
        meta.setdefault("path", f"structures/{slug_candidate}.json")


def ensure_workflow_entry_defaults(entry: dict) -> None:
    """Ensure a workflow entry has all required default fields."""
    meta = entry.setdefault("meta", {})
    if not meta.get("id"):
        meta["id"] = generate_resource_id()
    name_candidate = entry.get("name") or meta.get("name") or entry.get("id") or "Workflow"
    meta.setdefault("name", name_candidate)
    entry.setdefault("name", meta["name"])
    slug_candidate = meta.get("slug") or slugify(meta["name"])
    meta["slug"] = slug_candidate
    path_value = entry.get("path") or meta.get("path") or f"workflows/{slug_candidate}"
    entry.setdefault("path", path_value)
    meta.setdefault("path", path_value)


# ---------------------------------------------------------------------------
# Find entries
# ---------------------------------------------------------------------------


def find_structure_entry(
    config: dict, identifier: str, project_root: Optional[Path] = None
) -> dict:
    """
    Find a structure entry by name, slug, or file path.
    
    Raises:
        ResourceNotFoundError: If the structure is not found.
    """
    entries = config.setdefault("structures", [])
    for entry in entries:
        ensure_structure_entry_defaults(entry)
        if entry_matches(entry, identifier):
            return entry
    if project_root:
        candidates: list[Path] = []
        raw_candidate = Path(identifier).expanduser()
        if raw_candidate.is_absolute():
            candidates.append(raw_candidate)
        else:
            candidates.append((project_root / raw_candidate))
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except FileNotFoundError:
                continue
            if not resolved.exists():
                continue
            try:
                rel = ensure_relative_path(resolved, base=project_root)
            except ValueError:
                continue
            for entry in entries:
                file_rel = entry.get("file") or (entry.get("meta") or {}).get("path")
                if file_rel and Path(file_rel).as_posix() == rel:
                    return entry
    raise ResourceNotFoundError(f"Structure '{identifier}' not found.")


def find_workflow_entry(
    config: dict, identifier: str, project_root: Optional[Path] = None
) -> dict:
    """
    Find a workflow entry by name, slug, or directory path.
    
    Raises:
        ResourceNotFoundError: If the workflow is not found.
    """
    entries = config.setdefault("workflows", [])
    for entry in entries:
        ensure_workflow_entry_defaults(entry)
        if entry_matches(entry, identifier):
            return entry
    if project_root:
        candidates: list[Path] = []
        raw_candidate = Path(identifier).expanduser()
        if raw_candidate.is_absolute():
            candidates.append(raw_candidate)
        else:
            candidates.append((project_root / raw_candidate))
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except FileNotFoundError:
                continue
            if not resolved.exists():
                continue
            try:
                rel = ensure_relative_path(resolved, base=project_root)
            except ValueError:
                continue
            for entry in entries:
                wf_rel = entry.get("path") or (entry.get("meta") or {}).get("path")
                if wf_rel and Path(wf_rel).as_posix() == rel:
                    return entry
    raise ResourceNotFoundError(f"Workflow '{identifier}' not found.")


def workflow_directory(project_root: Path, entry: dict) -> Path:
    """Get the absolute path to a workflow directory."""
    rel_path = entry.get("path") or (entry.get("meta") or {}).get("path")
    if not rel_path:
        raise ProjectConfigError("Workflow entry is missing a path.")
    return (project_root / rel_path).resolve()


# ---------------------------------------------------------------------------
# Auto-find resources from current directory
# ---------------------------------------------------------------------------


def find_project_root(start: Optional[Path] = None) -> Path:
    """
    Find project root by walking up from start directory.
    
    Args:
        start: Starting directory (defaults to cwd)
        
    Returns:
        Path to project root (directory containing project.qv.yml)
        
    Raises:
        ResourceNotFoundError: If no project.qv.yml found
    """
    current = Path(start or Path.cwd()).resolve()
    while current != current.parent:
        if (current / "project.qv.yml").exists():
            return current
        current = current.parent
    raise ResourceNotFoundError(
        "No project.qv.yml found. Run inside a project or specify --project."
    )


def find_enclosing_workflow(
    project_root: Path, 
    config: dict, 
    start: Optional[Path] = None
) -> Optional[dict]:
    """
    Find workflow entry that encloses the current directory.
    
    Args:
        project_root: Project root path
        config: Project configuration dict
        start: Starting directory (defaults to cwd)
        
    Returns:
        Workflow entry dict if found, None otherwise
    """
    current = Path(start or Path.cwd()).resolve()
    
    # Must be inside project
    try:
        current.relative_to(project_root)
    except ValueError:
        return None
    
    workflows = config.get("workflows", [])
    for entry in workflows:
        ensure_workflow_entry_defaults(entry)
        rel_path = entry.get("path") or (entry.get("meta") or {}).get("path")
        if not rel_path:
            continue
        workflow_dir = (project_root / rel_path).resolve()
        # Check if current dir is workflow dir or inside it
        if current == workflow_dir:
            return entry
        try:
            current.relative_to(workflow_dir)
            return entry
        except ValueError:
            continue
    return None


def find_step_in_workflow(
    workflow_dir: Path, 
    step_identifier: str
) -> Optional[Path]:
    """
    Find a step YAML file in a workflow by id, name, or path.
    
    Args:
        workflow_dir: Path to workflow directory
        step_identifier: Step id, name, or path to .step.yaml
        
    Returns:
        Path to step YAML if found, None otherwise
    """
    steps_dir = workflow_dir / "steps"
    
    # Check if it's a direct path
    if step_identifier.endswith(".yaml") or step_identifier.endswith(".yml"):
        candidates = [
            Path(step_identifier),
            workflow_dir / step_identifier,
            steps_dir / step_identifier,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
    
    # Search by step id in workflow.yaml and step files
    workflow_yaml = workflow_dir / "workflow.yaml"
    if workflow_yaml.exists():
        try:
            wf_data = yaml.safe_load(workflow_yaml.read_text()) or {}
            for step in wf_data.get("steps", []):
                step_id = step.get("id", "")
                if step_id.lower() == step_identifier.lower():
                    # Found step id, look for corresponding YAML
                    step_yaml = steps_dir / f"{step_id}.step.yaml"
                    if step_yaml.exists():
                        return step_yaml
                    # Try input file path
                    input_file = step.get("input")
                    if input_file:
                        base = Path(input_file).stem
                        step_yaml = steps_dir / f"{base}.step.yaml"
                        if step_yaml.exists():
                            return step_yaml
        except Exception:
            pass
    
    # Fallback: search all .step.yaml files
    if steps_dir.exists():
        ident_lower = step_identifier.lower()
        for step_path in steps_dir.glob("*.step.yaml"):
            # Match by filename stem
            if step_path.stem.replace(".step", "").lower() == ident_lower:
                return step_path
            # Or parse and check step_type/id inside
            try:
                step_data = yaml.safe_load(step_path.read_text()) or {}
                if step_data.get("id", "").lower() == ident_lower:
                    return step_path
                if step_data.get("step_type", "").lower() == ident_lower:
                    return step_path
            except Exception:
                continue
    
    return None


@dataclass
class ResourceContext:
    """Result of resource resolution."""
    project_root: Path
    config: dict
    entry: Optional[dict] = None  # The found resource entry
    parent_entry: Optional[dict] = None  # Parent resource (workflow for step)
    resource_path: Optional[Path] = None  # Resolved absolute path


def _is_ulid_like(s: str) -> bool:
    """Check if string looks like a ULID (26 chars, alphanumeric)."""
    if len(s) != 26:
        return False
    return s.isalnum() and s.isupper()


def _is_path_like(s: str) -> bool:
    """Check if string looks like a path."""
    return "/" in s or "\\" in s or s.endswith(".yaml") or s.endswith(".yml")


def resolve_resource(
    resource_type: str,
    identifier: Optional[str] = None,
    parent_identifier: Optional[str] = None,
    project_path: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> ResourceContext:
    """
    Universal resource resolver with auto-detection from current directory.
    
    Resolution strategy:
    1. Find project root (from project_path or walking up from cwd)
    2. For resources needing a parent (step needs workflow):
       - If parent_identifier given, find parent first
       - Else auto-detect parent from cwd
    3. Find the resource:
       - By path: direct lookup
       - By id (ULID): search all entries
       - By name/slug: search within parent scope
    
    Args:
        resource_type: "project", "structure", "workflow", or "step"
        identifier: Resource id/name/slug/path (optional for workflow/step if inside one)
        parent_identifier: Parent resource id/name/slug/path (for step: the workflow)
        project_path: Explicit project path
        cwd: Starting directory for auto-detection (defaults to Path.cwd())
        
    Returns:
        ResourceContext with project_root, config, entry, parent_entry, resource_path
        
    Raises:
        ResourceNotFoundError: If resource cannot be found
    """
    start = Path(cwd or Path.cwd()).resolve()
    
    # Step 1: Find project root
    if project_path:
        project_root = Path(project_path).expanduser().resolve()
        if not (project_root / "project.qv.yml").exists():
            raise ResourceNotFoundError(f"No project.qv.yml in {project_root}")
    else:
        project_root = find_project_root(start)
    
    config = load_project_config(project_root)
    
    # Step 2: Handle project type (simplest case)
    if resource_type == "project":
        return ResourceContext(
            project_root=project_root,
            config=config,
            entry=config.get("project", {}),
            resource_path=project_root,
        )
    
    # Step 3: Handle structure (parent is always project)
    if resource_type == "structure":
        if not identifier:
            raise ResourceNotFoundError("Structure identifier required.")
        entry = find_structure_entry(config, identifier, project_root)
        file_path = entry.get("file") or (entry.get("meta") or {}).get("path")
        return ResourceContext(
            project_root=project_root,
            config=config,
            entry=entry,
            resource_path=(project_root / file_path) if file_path else None,
        )
    
    # Step 4: Handle workflow (parent is always project)
    if resource_type == "workflow":
        if identifier:
            # Check if it's a direct path first
            if _is_path_like(identifier):
                candidate = Path(identifier)
                if not candidate.is_absolute():
                    candidate = project_root / identifier
                if candidate.exists():
                    # Find matching entry in config
                    for entry in config.get("workflows", []):
                        ensure_workflow_entry_defaults(entry)
                        wf_dir = workflow_directory(project_root, entry)
                        if wf_dir == candidate.resolve():
                            return ResourceContext(
                                project_root=project_root,
                                config=config,
                                entry=entry,
                                resource_path=wf_dir,
                            )
            # Search by id/name/slug
            entry = find_workflow_entry(config, identifier, project_root)
            return ResourceContext(
                project_root=project_root,
                config=config,
                entry=entry,
                resource_path=workflow_directory(project_root, entry),
            )
        else:
            # Auto-find enclosing workflow from cwd
            entry = find_enclosing_workflow(project_root, config, start)
            if entry:
                return ResourceContext(
                    project_root=project_root,
                    config=config,
                    entry=entry,
                    resource_path=workflow_directory(project_root, entry),
                )
            raise ResourceNotFoundError(
                "No workflow specified and not inside a workflow directory."
            )
    
    # Step 5: Handle step (parent is workflow)
    if resource_type == "step":
        # First, find the parent workflow
        workflow_entry = None
        workflow_dir = None
        
        if parent_identifier:
            # User specified workflow explicitly
            workflow_entry = find_workflow_entry(config, parent_identifier, project_root)
            workflow_dir = workflow_directory(project_root, workflow_entry)
        else:
            # Try to auto-detect enclosing workflow from cwd
            workflow_entry = find_enclosing_workflow(project_root, config, start)
            if workflow_entry:
                workflow_dir = workflow_directory(project_root, workflow_entry)
        
        if not workflow_entry:
            raise ResourceNotFoundError(
                "Could not determine workflow. Specify --workflow or run inside a workflow directory."
            )
        
        if not identifier:
            raise ResourceNotFoundError("Step identifier required.")
        
        # Find the step within the workflow
        step_path = find_step_in_workflow(workflow_dir, identifier)
        if step_path:
            return ResourceContext(
                project_root=project_root,
                config=config,
                entry={"id": identifier, "path": str(step_path)},
                parent_entry=workflow_entry,
                resource_path=step_path,
            )
        
        raise ResourceNotFoundError(
            f"Step '{identifier}' not found in workflow '{entry_display_name(workflow_entry)}'."
        )
    
    raise ValueError(f"Unknown resource type: {resource_type}")


# Keep backward compatibility alias
def find_resource_auto(
    resource_type: str,
    identifier: Optional[str] = None,
    project_path: Optional[Path] = None,
    start: Optional[Path] = None,
) -> tuple[Path, dict, Optional[dict]]:
    """Backward-compatible wrapper for resolve_resource."""
    ctx = resolve_resource(
        resource_type=resource_type,
        identifier=identifier,
        project_path=project_path,
        cwd=start,
    )
    return ctx.project_root, ctx.config, ctx.entry


# ---------------------------------------------------------------------------
# Structure reference tracking
# ---------------------------------------------------------------------------


def structure_reference_tokens(entry: dict, project_root: Path) -> tuple[set[str], Optional[Path]]:
    """Get all identifiers and resolved path for a structure entry."""
    meta = entry.get("meta") or {}
    aliases: set[str] = set()
    for candidate in (
        entry.get("name"),
        meta.get("name"),
        meta.get("slug"),
        meta.get("id"),
    ):
        if candidate:
            aliases.add(str(candidate).strip().lower())
    rel_path = entry.get("file") or meta.get("path")
    resolved = None
    if rel_path:
        resolved = (project_root / rel_path).resolve()
    return aliases, resolved


def spec_uses_structure(
    spec: "StructureStepSpec",
    spec_path: Path,
    aliases: set[str],
    resolved_path: Optional[Path],
) -> bool:
    """Check if a step spec references a structure by its aliases or path."""
    identifier = (spec.structure or "").strip()
    if not identifier:
        return False
    if identifier.lower() in aliases:
        return True
    candidate = Path(identifier)
    if not candidate.is_absolute():
        candidate = (spec_path.parent / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if resolved_path and candidate == resolved_path:
        return True
    return False


def workflows_using_structure(
    project_root: Path, config: dict, entry: dict
) -> list[dict]:
    """Find all workflows that reference a given structure."""
    from quantumvitas.workflow.structure_steps import StructureStepSpec
    
    aliases, resolved_path = structure_reference_tokens(entry, project_root)
    matches: list[dict] = []
    for workflow_entry in list(config.get("workflows", [])):
        workflow_path = workflow_entry.get("path") or (workflow_entry.get("meta") or {}).get("path")
        if not workflow_path:
            continue
        workflow_dir = (project_root / workflow_path).resolve()
        steps_dir = workflow_dir / "steps"
        if not steps_dir.exists():
            continue
        for spec_path in steps_dir.rglob("*.step.yaml"):
            try:
                spec = StructureStepSpec.from_yaml(spec_path)
            except Exception:
                continue
            if spec_uses_structure(spec, spec_path, aliases, resolved_path):
                matches.append(workflow_entry)
                break
    return matches


# ---------------------------------------------------------------------------
# Workflow dependencies
# ---------------------------------------------------------------------------


def workflow_identifiers(entry: dict) -> set[str]:
    """Get all identifiers (name, slug, id) for a workflow entry."""
    meta = entry.get("meta") or {}
    identifiers = {
        entry.get("name"),
        meta.get("name"),
        meta.get("slug"),
        meta.get("id"),
    }
    return {str(value) for value in identifiers if value}


def workflows_depending_on(config: dict, target_entry: dict) -> list[dict]:
    """Find all workflows that depend on the given workflow as a parent."""
    identifiers = workflow_identifiers(target_entry)
    matches: list[dict] = []
    for workflow_entry in config.get("workflows", []):
        if workflow_entry is target_entry:
            continue
        meta = workflow_entry.get("meta") or {}
        parents = meta.get("parents") or []
        for parent in parents:
            if str(parent) in identifiers:
                matches.append(workflow_entry)
                break
    return matches


# ---------------------------------------------------------------------------
# Trash operations
# ---------------------------------------------------------------------------


def move_to_trash(target: Path, trash_dir: Path) -> Path:
    """Move a file or directory to the trash folder with a timestamp."""
    trash_dir = trash_dir.resolve()
    trash_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    destination = trash_dir / f"{target.name}_{timestamp}"
    idx = 1
    while destination.exists():
        destination = trash_dir / f"{target.name}_{timestamp}_{idx}"
        idx += 1
    shutil.move(str(target), str(destination))
    return destination


# ---------------------------------------------------------------------------
# Rename operations
# ---------------------------------------------------------------------------


def apply_structure_rename(
    *,
    project_root: Path,
    config: dict,
    entry: dict,
    new_name: Optional[str],
    new_slug: Optional[str],
    new_path: Optional[Path],
) -> None:
    """
    Apply a rename operation to a structure entry.
    
    Updates the entry in-place and moves the file if needed.
    
    Raises:
        ProjectConfigError: If the operation fails.
    """
    structures = config.setdefault("structures", [])
    meta = entry.setdefault("meta", {})
    existing_slugs = collect_slugs(structures, exclude=entry)
    previous_slug = meta.get("slug")
    slug_changed = False
    previous_path = entry.get("file") or meta.get("path")

    if new_name or new_slug:
        if new_slug:
            slug_candidate = slugify(new_slug)
            if slug_candidate in existing_slugs:
                raise ProjectConfigError(
                    f"Slug '{new_slug}' conflicts with an existing structure."
                )
            name_candidate = new_name or entry.get("name") or meta.get("name") or slug_candidate
        else:
            preferred = new_name or entry.get("name") or meta.get("name")
            name_candidate, slug_candidate = generate_unique_name_and_slug(
                kind="structure",
                preferred_name=preferred,
                existing_slugs=existing_slugs,
            )
        entry["name"] = name_candidate
        meta["name"] = name_candidate
        meta["slug"] = slug_candidate
        slug_changed = slug_candidate != previous_slug

    if new_path is not None:
        relative = ensure_relative_path(new_path, base=project_root)
        old_path = entry.get("file") or meta.get("path")
        if not old_path:
            raise ProjectConfigError("Structure entry is missing a file path.")
        old_abs = (project_root / old_path).resolve()
        if not old_abs.exists():
            raise ProjectConfigError(f"Structure file '{old_path}' does not exist.")
        new_abs = (project_root / relative).resolve()
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        old_abs.rename(new_abs)
        entry["file"] = relative
        meta["path"] = relative
    elif slug_changed and previous_path:
        old_abs = (project_root / previous_path).resolve()
        if old_abs.exists():
            old_rel = Path(previous_path)
            suffix = "".join(old_rel.suffixes)
            parent = old_rel.parent
            new_rel_path = (parent / f"{meta['slug']}{suffix}")
            new_abs = (project_root / new_rel_path).resolve()
            if new_abs.exists():
                raise ProjectConfigError(
                    f"Cannot rename structure file to '{new_rel_path}': destination exists."
                )
            new_abs.parent.mkdir(parents=True, exist_ok=True)
            old_abs.rename(new_abs)
            rel_str = new_rel_path.as_posix()
            entry["file"] = rel_str
            meta["path"] = rel_str


def apply_workflow_rename(
    *,
    project_root: Path,
    config: dict,
    entry: dict,
    new_name: Optional[str],
    new_slug: Optional[str],
    new_path: Optional[Path],
) -> None:
    """
    Apply a rename operation to a workflow entry.
    
    Updates the entry in-place and moves the directory if needed.
    
    Raises:
        ProjectConfigError: If the operation fails.
    """
    workflows = config.setdefault("workflows", [])
    meta = entry.setdefault("meta", {})
    existing_slugs = collect_slugs(workflows, exclude=entry)
    previous_slug = meta.get("slug")
    slug_changed = False
    previous_path = entry.get("path") or meta.get("path")

    if new_name or new_slug:
        if new_slug:
            slug_candidate = slugify(new_slug)
            if slug_candidate in existing_slugs:
                raise ProjectConfigError(
                    f"Slug '{new_slug}' conflicts with an existing workflow."
                )
            name_candidate = new_name or entry.get("name") or meta.get("name") or slug_candidate
        else:
            preferred = new_name or entry.get("name") or meta.get("name")
            name_candidate, slug_candidate = generate_unique_name_and_slug(
                kind="workflow",
                preferred_name=preferred,
                existing_slugs=existing_slugs,
            )
        entry["name"] = name_candidate
        meta["name"] = name_candidate
        meta["slug"] = slug_candidate
        if not entry.get("path"):
            entry["path"] = f"workflows/{slug_candidate}"
        slug_changed = slug_candidate != previous_slug

    if new_path is not None:
        relative = ensure_relative_path(new_path, base=project_root)
        old_path = entry.get("path") or meta.get("path")
        if not old_path:
            raise ProjectConfigError("Workflow entry is missing a path.")
        old_abs = (project_root / old_path).resolve()
        if not old_abs.exists():
            raise ProjectConfigError(f"Workflow directory '{old_path}' does not exist.")
        new_abs = (project_root / relative).resolve()
        if new_abs.exists():
            raise ProjectConfigError(f"Destination '{relative}' already exists.")
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        old_abs.rename(new_abs)
        entry["path"] = relative
        meta["path"] = relative
    elif slug_changed and previous_path:
        old_abs = (project_root / previous_path).resolve()
        if old_abs.exists():
            old_rel = Path(previous_path)
            parent = old_rel.parent
            new_rel = (parent / meta["slug"])
            new_abs = (project_root / new_rel).resolve()
            if new_abs.exists():
                raise ProjectConfigError(
                    f"Cannot rename workflow directory to '{new_rel}': destination exists."
                )
            new_abs.parent.mkdir(parents=True, exist_ok=True)
            old_abs.rename(new_abs)
            rel_str = new_rel.as_posix()
            entry["path"] = rel_str
            meta["path"] = rel_str


# ---------------------------------------------------------------------------
# Delete operations
# ---------------------------------------------------------------------------


def delete_workflow_entry(
    *,
    project_root: Path,
    config: dict,
    entry: dict,
    trash_dir: Path,
    force: bool,
    cascade: bool,
    visited: Optional[set[str]] = None,
) -> None:
    """
    Delete a workflow entry, moving its directory to trash.
    
    Args:
        project_root: Path to the project root.
        config: The project configuration dict.
        entry: The workflow entry to delete.
        trash_dir: Directory to move deleted files to.
        force: If True, delete even if other workflows depend on this one.
        cascade: If True, also delete workflows that depend on this one.
        visited: Set of already-visited workflow identifiers (for recursion).
    
    Raises:
        ProjectConfigError: If the workflow is required by others and neither force nor cascade is set.
    """
    identifiers = workflow_identifiers(entry)
    if visited is None:
        visited = set()
    if identifiers & visited:
        return
    visited.update(identifiers)

    dependents = workflows_depending_on(config, entry)
    if dependents:
        if cascade:
            for dependent in list(dependents):
                delete_workflow_entry(
                    project_root=project_root,
                    config=config,
                    entry=dependent,
                    trash_dir=trash_dir,
                    force=force,
                    cascade=True,
                    visited=visited,
                )
        elif not force:
            names = ", ".join(entry_display_name(dep) for dep in dependents)
            raise ProjectConfigError(
                f"Workflow '{entry_display_name(entry)}' is required by: {names}. "
                "Use force to remove it anyway or cascade to delete dependents."
            )

    workflow_dir = None
    rel_path = entry.get("path") or (entry.get("meta") or {}).get("path")
    if rel_path:
        workflow_dir = (project_root / rel_path).resolve()
        if workflow_dir.exists():
            move_to_trash(workflow_dir, trash_dir)

    workflows = config.setdefault("workflows", [])
    if entry in workflows:
        workflows.remove(entry)

