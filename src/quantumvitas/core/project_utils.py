"""
Project configuration helpers for managing structures, calculations, and steps.

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
from quantumvitas.core.selectors import (
    extract_calculation_selector_from_entry,
    extract_structure_selector_from_entry,
    extract_step_selector_from_entry,
)

if TYPE_CHECKING:
    from quantumvitas.calculation.structure_steps import StructureStepSpec


class ProjectConfigError(ValueError):
    """Raised when project configuration operations fail."""
    pass


class ResourceNotFoundError(ProjectConfigError):
    """Raised when a structure or calculation is not found."""
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


def collect_slugs(entries: list[dict], *, exclude: Optional[dict] = None, project_root: Optional[Path] = None) -> list[str]:
    """
    Collect all slugs from a list of structure or calculation entries.
    
    In ID-only model, entries may only have structure_id/calculation_id (ULID).
    If project_root is provided, resolves slugs from registry.
    Otherwise, falls back to legacy entry format (meta/name fields).
    """
    slugs: list[str] = []
    
    # If project_root is provided, try to resolve from registry (ID-only model)
    if project_root and project_root.exists():
        try:
            from quantumvitas.core.resolution import build_resource_index
            index = build_resource_index(project_root)
            for entry in entries:
                if exclude is not None and entry is exclude:
                    continue
                # Try to get resource ID (structure_id, calculation_id, or id)
                resource_id = entry.get("structure_id") or entry.get("calculation_id") or entry.get("ulid")
                if resource_id and resource_id in index.by_id:
                    meta = index.by_id[resource_id]
                    if meta.slug:
                        slugs.append(meta.slug)
                        continue
        except Exception:
            # If registry resolution fails, fall back to legacy format
            pass
    
    # Fallback: legacy format or registry unavailable
    for entry in entries:
        if exclude is not None and entry is exclude:
            continue
        meta = entry.get("meta") or {}
        slug = meta.get("slug") or slugify(entry.get("name") or entry.get("ulid") or "")
        if slug:
            slugs.append(slug)
    return slugs


def entry_matches(entry: dict, identifier: str) -> bool:
    """
    Check if an entry matches the given identifier.
    
    Matches against (in order): id (ULID), name, slug, file path.
    Comparison is case-insensitive for names/slugs.
    
    Raises:
        ValueError: If identifier is None or not a string
    """
    if identifier is None:
        raise ValueError("identifier must be a non-empty string, got None")
    if not isinstance(identifier, str):
        raise ValueError(f"identifier must be a string, got {type(identifier).__name__}")
    ident = identifier.strip()
    if not ident:
        raise ValueError("identifier must be a non-empty string after stripping")
    ident_lower = ident.lower()
    meta = entry.get("meta") or {}
    
    # Check id first (case-sensitive, exact match for ULID)
    entry_id = meta.get("ulid") or entry.get("ulid")
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
    return entry.get("name") or meta.get("name") or entry.get("ulid") or fallback


def ensure_structure_entry_defaults(entry: dict) -> None:
    """Ensure a structure entry has all required default fields."""
    meta = entry.setdefault("meta", {})
    if not meta.get("ulid"):
        meta["ulid"] = generate_resource_id()
    name_candidate = entry.get("name") or meta.get("name") or entry.get("ulid") or "Structure"
    meta.setdefault("name", name_candidate)
    entry.setdefault("name", meta["name"])
    slug_candidate = meta.get("slug") or slugify(meta["name"])
    meta["slug"] = slug_candidate
    file_path = entry.get("file") or meta.get("path")
    if file_path:
        meta.setdefault("path", file_path)
    else:
        meta.setdefault("path", f"structures/{slug_candidate}.json")


def ensure_calculation_entry_defaults(entry: dict) -> None:
    """Ensure a calculation entry has all required default fields."""
    meta = entry.setdefault("meta", {})
    if not meta.get("ulid"):
        meta["ulid"] = generate_resource_id()
    name_candidate = entry.get("name") or meta.get("name") or entry.get("ulid") or "Calculation"
    meta.setdefault("name", name_candidate)
    entry.setdefault("name", meta["name"])
    slug_candidate = meta.get("slug") or slugify(meta["name"])
    meta["slug"] = slug_candidate
    path_value = entry.get("path") or meta.get("path") or f"calculations/{slug_candidate}"
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
    
    DEPRECATED: Prefer using resolve_structure() with ResourceIndex for new code.
    This function is kept for backwards compatibility.
    
    Raises:
        ResourceNotFoundError: If the structure is not found.
    """
    # Try to use ResourceIndex if project_root is available
    if project_root:
        try:
            from quantumvitas.core.resolution import build_resource_index, resolve_structure
            index = build_resource_index(project_root)
            resolved = resolve_structure(project_root, identifier, config, index=index)
            # Convert ResolvedResource back to entry dict format for backwards compat
            structure_id = resolved.meta.ulid
            # Find entry by ID using centralized selector extraction
            entries = config.setdefault("structures", [])
            for entry in entries:
                entry_id = extract_structure_selector_from_entry(entry)
                if entry_id == structure_id:
                    return entry
            # If not found in config, create minimal entry from resolved resource
            return {
                "ulid": structure_id,
                "meta": resolved.meta.to_dict(),
            }
        except Exception:
            # Fall back to legacy resolution if ResourceIndex fails
            pass
    
    # Legacy resolution (for backwards compatibility)
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


def find_calculation_entry(
    config: dict, identifier: str, project_root: Optional[Path] = None
) -> dict:
    """
    Find a calculation entry by name, slug, or directory path.
    
    DEPRECATED: Prefer using resolve_calculation() with ResourceIndex for new code.
    This function is kept for backwards compatibility.
    
    Raises:
        ResourceNotFoundError: If the calculation is not found.
    """
    # Try to use ResourceIndex if project_root is available
    if project_root:
        try:
            from quantumvitas.core.resolution import build_resource_index, resolve_calculation
            index = build_resource_index(project_root)
            resolved = resolve_calculation(project_root, identifier, config, index=index)
            # Convert ResolvedResource back to entry dict format for backwards compat
            calculation_id = resolved.meta.ulid
            # Find entry by ID using centralized selector extraction
            entries = config.setdefault("calculations", [])
            for entry in entries:
                entry_id = extract_calculation_selector_from_entry(entry)
                if entry_id == calculation_id:
                    return entry
            # If not found in config, create minimal entry from resolved resource
            return {
                "ulid": calculation_id,
                "meta": resolved.meta.to_dict(),
            }
        except Exception:
            # Fall back to legacy resolution if ResourceIndex fails
            pass
    
    # Legacy resolution (for backwards compatibility)
    entries = config.setdefault("calculations", [])
    for entry in entries:
        ensure_calculation_entry_defaults(entry)
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
    raise ResourceNotFoundError(f"Calculation '{identifier}' not found.")


def calculation_directory(project_root: Path, entry: dict) -> Path:
    """
    Get the absolute path to a calculation directory.
    
    In ID-only model, entry may only have calculation_id/id, not path.
    Uses registry to resolve calculation directory if path is missing.
    
    After renames, the entry path is updated immediately, so we check it first.
    If the path doesn't exist, we fall back to registry resolution.
    """
    # Try to get path from entry (legacy format) - check this FIRST
    # This is important after renames, as the entry path is updated immediately
    rel_path = entry.get("path") or (entry.get("meta") or {}).get("path")
    if rel_path:
        candidate = (project_root / rel_path).resolve()
        # Verify the directory exists (it should after rename)
        if candidate.exists() and candidate.is_dir():
            return candidate
        # If path is set but directory doesn't exist, continue to registry resolution
        # (might be a stale path or registry needs to be checked)
    
    # ID-only model: resolve via registry
    calculation_id = entry.get("calculation_id") or entry.get("ulid") or (entry.get("meta") or {}).get("ulid")
    if calculation_id:
        try:
            from quantumvitas.core.resolution import build_resource_index, require_calculation
            index = build_resource_index(project_root)
            resolved = require_calculation(project_root, calculation_id, index=index)
            # resolved.absolute_path points to calculation.yaml, so get parent directory
            if resolved.absolute_path.name == "calculation.yaml":
                calculation_dir = resolved.absolute_path.parent
            else:
                calculation_dir = resolved.absolute_path
            # Verify the directory exists
            if calculation_dir.exists() and calculation_dir.is_dir():
                return calculation_dir
        except Exception:
            pass
    
    # Fallback: try to construct from slug
    slug = (entry.get("meta") or {}).get("slug") or entry.get("slug")
    if slug:
        candidate = (project_root / "calculations" / slug).resolve()
        if candidate.exists() and candidate.is_dir():
            return candidate
    
    # Last resort: error with helpful message
    rel_path_str = entry.get("path") or (entry.get("meta") or {}).get("path")
    raise ProjectConfigError(
        f"Calculation entry is missing a path and cannot be resolved via registry. "
        f"Entry path: {rel_path_str}, project_root: {project_root}, "
        f"calculation_id: {entry.get('calculation_id') or entry.get("ulid") or (entry.get('meta') or {}).get("ulid")}"
    )


# ---------------------------------------------------------------------------
# Auto-find resources from current directory
# ---------------------------------------------------------------------------


def find_project_root(start: Optional[Path] = None, *, stop_at: Optional[Path] = None, max_levels: int = 100) -> Optional[Path]:
    """
    Find project root by walking up from start directory using marker-based detection.
    
    This function walks upward from start_dir looking for project.qv.yml (the project marker).
    It stops at the first marker found, or when it reaches stop_at boundary, filesystem root, or max_levels.
    
    Args:
        start: Starting directory (defaults to cwd)
        stop_at: Optional boundary directory. If provided, search stops when current dir
                 would move above stop_at. You are allowed to check stop_at itself, but
                 must not go above it. This is used to sandbox searches in tests.
        max_levels: Maximum number of parent directories to traverse (default: 100)
        
    Returns:
        Path to project root (directory containing project.qv.yml) if found, None otherwise.
        Returns None if marker not found, boundary exceeded, or max_levels reached.
        Never raises - this is a pure finder function.
    """
    current = Path(start or Path.cwd()).resolve()
    stop_at_resolved = stop_at.resolve() if stop_at else None
    levels = 0
    
    while current != current.parent and levels < max_levels:
        # Check for project marker (project.qv.yml)
        if (current / "project.qv.yml").exists():
            return current
        
        # Check boundary: if stop_at provided, ensure we don't go above it
        if stop_at_resolved:
            # Check if current is within or equal to stop_at
            try:
                current.relative_to(stop_at_resolved)
                # current is within stop_at - check if next parent would be outside
                next_parent = current.parent
                if next_parent == current:
                    # Reached filesystem root
                    return None
                try:
                    next_parent.relative_to(stop_at_resolved)
                    # next_parent is still within - continue
                except ValueError:
                    # next_parent would be outside stop_at - stop here
                    return None
            except ValueError:
                # current is already outside stop_at - should not happen, but stop
                return None
        
        current = current.parent
        levels += 1
    
    # Reached filesystem root or max_levels without finding marker
    return None


def require_project_root(start: Optional[Path] = None, *, stop_at: Optional[Path] = None, max_levels: int = 100) -> Path:
    """
    Require a project root to be found (raises if not found).
    
    This is a strict wrapper around find_project_root for CLI/product code.
    It validates that a project root was found and that it is not the repo root.
    
    Args:
        start: Starting directory (defaults to cwd)
        stop_at: Optional boundary directory (see find_project_root)
        max_levels: Maximum number of parent directories to traverse (default: 100)
        
    Returns:
        Path to project root (directory containing project.qv.yml)
        
    Raises:
        ResourceNotFoundError: If no project.qv.yml found
        ValueError: If project root is the repo root (repo root is not a project root)
    """
    result = find_project_root(start, stop_at=stop_at, max_levels=max_levels)
    if result is None:
        raise ResourceNotFoundError(
            "No project.qv.yml found. Run inside a project or specify --project."
        )
    
    # Validate that project root is not repo root
    from quantumvitas.core.pseudo_config import _find_quantumvitas_root
    repo_root = _find_quantumvitas_root()
    if repo_root and result.resolve() == repo_root.resolve():
        raise ValueError(
            f"Project root cannot be the repository root. "
            f"Found project.qv.yml at repo root ({result}), which is invalid. "
            f"Projects must be created in user directories, not the QMatSuite repository root."
        )
    
    return result


def find_enclosing_calculation(
    project_root: Path, 
    config: dict, 
    start: Optional[Path] = None
) -> Optional[dict]:
    """
    Find calculation entry that encloses the current directory.
    
    Args:
        project_root: Project root path
        config: Project configuration dict
        start: Starting directory (defaults to cwd)
        
    Returns:
        Calculation entry dict if found, None otherwise
    """
    current = Path(start or Path.cwd()).resolve()
    
    # Must be inside project
    try:
        current.relative_to(project_root)
    except ValueError:
        return None
    
    calculations = config.get("calculations", [])
    
    # Try registry-based resolution first (ID-only model)
    try:
        from quantumvitas.core.resolution import build_resource_index, require_calculation
        index = build_resource_index(project_root)
        
        for entry in calculations:
            calculation_id = entry.get("calculation_id") or entry.get("ulid") or (entry.get("meta") or {}).get("ulid")
            if not calculation_id:
                continue
            try:
                resolved = require_calculation(project_root, calculation_id, index=index)
                # resolved.absolute_path points to calculation.yaml, so get parent directory
                calculation_dir = resolved.absolute_path.parent if resolved.absolute_path.name == "calculation.yaml" else resolved.absolute_path
                # Check if current dir is calculation dir or inside it
                if current == calculation_dir:
                    return entry
                try:
                    current.relative_to(calculation_dir)
                    return entry
                except ValueError:
                    continue
            except Exception:
                continue
    except Exception:
        # Registry resolution failed, fall back to path-based
        pass
    
    # Fallback: path-based resolution (legacy format)
    for entry in calculations:
        ensure_calculation_entry_defaults(entry)
        rel_path = entry.get("path") or (entry.get("meta") or {}).get("path")
        if not rel_path:
            continue
        calculation_dir = (project_root / rel_path).resolve()
        # Check if current dir is calculation dir or inside it
        if current == calculation_dir:
            return entry
        try:
            current.relative_to(calculation_dir)
            return entry
        except ValueError:
            continue
    return None


def find_step_in_calculation(
    calculation_dir: Path, 
    step_identifier: str
) -> Optional[Path]:
    """
    Find a step YAML file in a calculation by id, name, or path.
    
    Args:
        calculation_dir: Path to calculation directory
        step_identifier: Step id, name, or path to .step.yaml
        
    Returns:
        Path to step YAML if found, None otherwise
    """
    steps_dir = calculation_dir / "steps"
    
    # Check if it's a direct path
    if step_identifier.endswith(".yaml") or step_identifier.endswith(".yml"):
        candidates = [
            Path(step_identifier),
            calculation_dir / step_identifier,
            steps_dir / step_identifier,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
    
    # Search by step id in calculation.yaml and step files
    calculation_yaml = calculation_dir / "calculation.yaml"
    if calculation_yaml.exists():
        try:
            wf_data = yaml.safe_load(calculation_yaml.read_text()) or {}
            for step in wf_data.get("steps", []):
                step_id = step.get("ulid", "")
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
                if step_data.get("ulid", "").lower() == ident_lower:
                    return step_path
                if step_data.get("step_type_spec", "").lower() == ident_lower:
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
    parent_entry: Optional[dict] = None  # Parent resource (calculation for step)
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
    2. For resources needing a parent (step needs calculation):
       - If parent_identifier given, find parent first
       - Else auto-detect parent from cwd
    3. Find the resource:
       - By path: direct lookup
       - By id (ULID): search all entries
       - By name/slug: search within parent scope
    
    Args:
        resource_type: "project", "structure", "calculation", or "step"
        identifier: Resource id/name/slug/path (optional for calculation/step if inside one)
        parent_identifier: Parent resource id/name/slug/path (for step: the calculation)
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
        project_root = require_project_root(start)
    
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
    
    # Step 4: Handle calculation (parent is always project)
    if resource_type == "calculation":
        if identifier:
            # Check if it's a direct path first
            if _is_path_like(identifier):
                candidate = Path(identifier)
                if not candidate.is_absolute():
                    candidate = project_root / identifier
                if candidate.exists():
                    # Find matching entry in config
                    for entry in config.get("calculations", []):
                        ensure_calculation_entry_defaults(entry)
                        wf_dir = calculation_directory(project_root, entry)
                        if wf_dir == candidate.resolve():
                            return ResourceContext(
                                project_root=project_root,
                                config=config,
                                entry=entry,
                                resource_path=wf_dir,
                            )
            # Search by id/name/slug
            entry = find_calculation_entry(config, identifier, project_root)
            return ResourceContext(
                project_root=project_root,
                config=config,
                entry=entry,
                resource_path=calculation_directory(project_root, entry),
            )
        else:
            # Auto-find enclosing calculation from cwd
            entry = find_enclosing_calculation(project_root, config, start)
            if entry:
                return ResourceContext(
                    project_root=project_root,
                    config=config,
                    entry=entry,
                    resource_path=calculation_directory(project_root, entry),
                )
            raise ResourceNotFoundError(
                "No calculation specified and not inside a calculation directory."
            )
    
    # Step 5: Handle step (parent is calculation)
    if resource_type == "step":
        # First, find the parent calculation
        calculation_entry = None
        calculation_dir = None
        
        if parent_identifier:
            # User specified calculation explicitly
            calculation_entry = find_calculation_entry(config, parent_identifier, project_root)
            calculation_dir = calculation_directory(project_root, calculation_entry)
        else:
            # Try to auto-detect enclosing calculation from cwd
            calculation_entry = find_enclosing_calculation(project_root, config, start)
            if calculation_entry:
                calculation_dir = calculation_directory(project_root, calculation_entry)
        
        if not calculation_entry:
            raise ResourceNotFoundError(
                "Could not determine calculation. Specify --calculation or run inside a calculation directory."
            )
        
        if not identifier:
            raise ResourceNotFoundError("Step identifier required.")
        
        # Find the step within the calculation
        step_path = find_step_in_calculation(calculation_dir, identifier)
        if step_path:
            return ResourceContext(
                project_root=project_root,
                config=config,
                entry={"ulid": identifier, "path": str(step_path)},
                parent_entry=calculation_entry,
                resource_path=step_path,
            )
        
        raise ResourceNotFoundError(
            f"Step '{identifier}' not found in calculation '{entry_display_name(calculation_entry)}'."
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
        meta.get("ulid"),
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


def calculations_using_structure(
    project_root: Path, config: dict, entry: dict
) -> list[dict]:
    """Find all calculations that reference a given structure."""
    from quantumvitas.calculation.structure_steps import StructureStepSpec
    
    aliases, resolved_path = structure_reference_tokens(entry, project_root)
    matches: list[dict] = []
    for calculation_entry in list(config.get("calculations", [])):
        calculation_path = calculation_entry.get("path") or (calculation_entry.get("meta") or {}).get("path")
        if not calculation_path:
            continue
        calculation_dir = (project_root / calculation_path).resolve()
        steps_dir = calculation_dir / "steps"
        if not steps_dir.exists():
            continue
        for spec_path in steps_dir.rglob("*.step.yaml"):
            try:
                spec = StructureStepSpec.from_yaml(spec_path)
            except Exception:
                continue
            if spec_uses_structure(spec, spec_path, aliases, resolved_path):
                matches.append(calculation_entry)
                break
    return matches


# ---------------------------------------------------------------------------
# Calculation dependencies
# ---------------------------------------------------------------------------


def calculation_identifiers(entry: dict) -> set[str]:
    """Get all identifiers (name, slug, id) for a calculation entry."""
    meta = entry.get("meta") or {}
    identifiers = {
        entry.get("name"),
        meta.get("name"),
        meta.get("slug"),
        meta.get("ulid"),
    }
    return {str(value) for value in identifiers if value}


def calculations_depending_on(config: dict, target_entry: dict) -> list[dict]:
    """Find all calculations that depend on the given calculation as a parent."""
    identifiers = calculation_identifiers(target_entry)
    matches: list[dict] = []
    for calculation_entry in config.get("calculations", []):
        if calculation_entry is target_entry:
            continue
        meta = calculation_entry.get("meta") or {}
        parents = meta.get("parents") or []
        for parent in parents:
            if str(parent) in identifiers:
                matches.append(calculation_entry)
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
    existing_slugs = collect_slugs(structures, exclude=entry, project_root=project_root)
    previous_slug = meta.get("slug")
    slug_changed = False
    previous_path = entry.get("file") or meta.get("path")
    
    # In ID-only model, entry might only have structure_id - resolve path from registry if needed
    if not previous_path:
        structure_id = entry.get("structure_id") or entry.get("ulid") or meta.get("ulid")
        if structure_id:
            try:
                from quantumvitas.core.resolution import build_resource_index, resolve_structure
                index = build_resource_index(project_root)
                resolved = resolve_structure(project_root, structure_id, config=config, index=index)
                # Get relative path from absolute path
                previous_path = resolved.meta.path
                # Also update entry and meta with path if missing
                if not entry.get("file"):
                    entry["file"] = previous_path
                if not meta.get("path"):
                    meta["path"] = previous_path
            except Exception:
                # If resolution fails, continue without path (file update will be skipped)
                pass

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
        name_changed = name_candidate != (entry.get("name") or meta.get("name"))

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
        
        # Update structure file's meta block (for registry consistency)
        try:
            import json
            from quantumvitas.io.structure_io import STRUCTURE_META_KEY
            struct_data = json.loads(new_abs.read_text())
            if STRUCTURE_META_KEY in struct_data:
                struct_data[STRUCTURE_META_KEY].update({
                    "name": meta.get("name"),
                    "slug": meta.get("slug"),
                    "path": relative,
                })
                new_abs.write_text(json.dumps(struct_data, indent=2))
        except Exception:
            pass  # If update fails, continue (config is still updated)
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
            
            # Update structure file's meta block (for registry consistency)
            try:
                import json
                from quantumvitas.io.structure_io import STRUCTURE_META_KEY
                struct_data = json.loads(new_abs.read_text())
                if STRUCTURE_META_KEY in struct_data:
                    struct_data[STRUCTURE_META_KEY].update({
                        "name": meta.get("name"),
                        "slug": meta.get("slug"),
                        "path": rel_str,
                    })
                    new_abs.write_text(json.dumps(struct_data, indent=2))
            except Exception:
                pass  # If update fails, continue (config is still updated)
    
    # Always update structure file's meta block when name/slug changes (even if path doesn't change)
    # This ensures that get_structure() reads the updated name from the file
    # Use the current path (which may have changed due to file rename above)
    current_path = entry.get("file") or meta.get("path") or previous_path
    if (new_name or new_slug) and current_path:
        struct_abs = (project_root / current_path).resolve()
        if struct_abs.exists():
            try:
                import json
                from quantumvitas.io.structure_io import STRUCTURE_META_KEY
                struct_data = json.loads(struct_abs.read_text())
                # Ensure meta block exists
                if STRUCTURE_META_KEY not in struct_data:
                    struct_data[STRUCTURE_META_KEY] = {}
                # Update with the new name and slug from meta (which was updated above)
                struct_data[STRUCTURE_META_KEY].update({
                    "name": meta.get("name"),
                    "slug": meta.get("slug"),
                    "path": current_path,  # Ensure path is also updated
                })
                struct_abs.write_text(json.dumps(struct_data, indent=2))
            except Exception as e:
                # Log but don't fail - config is still updated
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not update structure file meta: {e}")


def apply_calculation_rename(
    *,
    project_root: Path,
    config: dict,
    entry: dict,
    new_name: Optional[str],
    new_slug: Optional[str],
    new_path: Optional[Path],
) -> None:
    """
    Apply a rename operation to a calculation entry.
    
    Updates the entry in-place and moves the directory if needed.
    
    Raises:
        ProjectConfigError: If the operation fails.
    """
    calculations = config.setdefault("calculations", [])
    meta = entry.setdefault("meta", {})
    existing_slugs = collect_slugs(calculations, exclude=entry, project_root=project_root)
    previous_slug = meta.get("slug")
    slug_changed = False
    previous_path = entry.get("path") or meta.get("path")

    if new_name or new_slug:
        if new_slug:
            slug_candidate = slugify(new_slug)
            if slug_candidate in existing_slugs:
                raise ProjectConfigError(
                    f"Slug '{new_slug}' conflicts with an existing calculation."
                )
            name_candidate = new_name or entry.get("name") or meta.get("name") or slug_candidate
        else:
            preferred = new_name or entry.get("name") or meta.get("name")
            name_candidate, slug_candidate = generate_unique_name_and_slug(
                kind="calculation",
                preferred_name=preferred,
                existing_slugs=existing_slugs,
            )
        entry["name"] = name_candidate
        meta["name"] = name_candidate
        meta["slug"] = slug_candidate
        if not entry.get("path"):
            entry["path"] = f"calculations/{slug_candidate}"
        slug_changed = slug_candidate != previous_slug

    if new_path is not None:
        relative = ensure_relative_path(new_path, base=project_root)
        old_path = entry.get("path") or meta.get("path")
        if not old_path:
            raise ProjectConfigError("Calculation entry is missing a path.")
        old_abs = (project_root / old_path).resolve()
        if not old_abs.exists():
            raise ProjectConfigError(f"Calculation directory '{old_path}' does not exist.")
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
                    f"Cannot rename calculation directory to '{new_rel}': destination exists."
                )
            new_abs.parent.mkdir(parents=True, exist_ok=True)
            old_abs.rename(new_abs)
            rel_str = new_rel.as_posix()
            entry["path"] = rel_str
            meta["path"] = rel_str
            
            # Update calculation.yaml meta block to reflect new name/slug/path
            calculation_yaml_path = new_abs / "calculation.yaml"
            if calculation_yaml_path.exists():
                try:
                    import yaml
                    wf_data = yaml.safe_load(calculation_yaml_path.read_text()) or {}
                    wf_meta = wf_data.setdefault("meta", {})
                    wf_meta["name"] = name_candidate
                    wf_meta["slug"] = slug_candidate
                    wf_meta["path"] = rel_str
                    # Remove legacy structure_name and structure fields before writing (DAG + ID-only constitution)
                    wf_data.pop("structure_name", None)
                    wf_data.pop("structure", None)
                    if "calculation" in wf_data:
                        wf_data["calculation"].pop("structure_name", None)
                        wf_data["calculation"].pop("structure", None)
                    calculation_yaml_path.write_text(yaml.safe_dump(wf_data, sort_keys=False))
                except Exception:
                    pass  # If update fails, continue (config is still updated)


# ---------------------------------------------------------------------------
# Delete operations
# ---------------------------------------------------------------------------


def delete_calculation_entry(
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
    Delete a calculation entry, moving its directory to trash.
    
    Args:
        project_root: Path to the project root.
        config: The project configuration dict.
        entry: The calculation entry to delete.
        trash_dir: Directory to move deleted files to.
        force: If True, delete even if other calculations depend on this one.
        cascade: If True, also delete calculations that depend on this one.
        visited: Set of already-visited calculation identifiers (for recursion).
    
    Raises:
        ProjectConfigError: If the calculation is required by others and neither force nor cascade is set.
    """
    identifiers = calculation_identifiers(entry)
    if visited is None:
        visited = set()
    if identifiers & visited:
        return
    visited.update(identifiers)

    dependents = calculations_depending_on(config, entry)
    if dependents:
        if cascade:
            for dependent in list(dependents):
                delete_calculation_entry(
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
                f"Calculation '{entry_display_name(entry)}' is required by: {names}. "
                "Use force to remove it anyway or cascade to delete dependents."
            )

    # Resolve calculation directory - try path first, then resolve via registry
    calculation_dir = None
    rel_path = entry.get("path") or (entry.get("meta") or {}).get("path")
    if rel_path:
        calculation_dir = (project_root / rel_path).resolve()
    else:
        # ID-only model: resolve via registry
        calculation_id = extract_calculation_selector_from_entry(entry)
        if calculation_id:
            try:
                from quantumvitas.core.resolution import build_resource_index, require_calculation
                index = build_resource_index(project_root)
                resolved = require_calculation(project_root, calculation_id, index=index)
                calculation_dir = resolved.absolute_path.parent if resolved.absolute_path.name == "calculation.yaml" else resolved.absolute_path
            except Exception:
                pass  # If resolution fails, calculation_dir stays None
    
    if calculation_dir and calculation_dir.exists():
        move_to_trash(calculation_dir, trash_dir)

    # Remove from config by calculation_id (ID-only model)
    # entry from resolve_resource might be a new dict, so match by ID
    calculation_id = extract_calculation_selector_from_entry(entry)
    calculations = config.setdefault("calculations", [])
    if calculation_id:
        # Remove by matching calculation_id
        calculations[:] = [
            e for e in calculations
            if (e.get("calculation_id") or e.get("ulid") or (e.get("meta") or {}).get("ulid")) != calculation_id
        ]
    else:
        # Fallback: try to remove by object identity
        if entry in calculations:
            calculations.remove(entry)

