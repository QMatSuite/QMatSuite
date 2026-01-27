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
The ResourceIndex is built by scanning resource files (calculation.yaml, *.step.yaml, *.json)
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
    from quantumvitas.calculation.structure_steps import StructureStepSpec


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
        kind: Resource kind ("calculation", "structure", "step", "project")
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
        message: str | None = None,
    ):
        self.kind = kind
        self.selector = selector
        self.id = id
        self.project_root = project_root
        self._custom_message = message
        
        # Store details dict for additional context (calculation_path, expected_step_path, reason, etc.)
        self.details: Dict[str, Any] = {}
        
        # Build error message
        if message:
            # Use custom message if provided (for more specific errors like "Step file not found")
            error_msg = message
        else:
            parts = [f"{kind.capitalize()} not found"]
            if selector:
                parts.append(f"selector: '{selector}'")
            if id:
                parts.append(f"id: '{id}'")
            if project_root:
                parts.append(f"in project: {project_root}")
            error_msg = " - ".join(parts)
        
        super().__init__(error_msg)


class RegistryOutOfSyncError(Exception):
    """
    Raised when the registry (ResourceIndex) is out of sync with the filesystem or DAG.
    
    This error indicates that:
    - A resource exists in the registry but the file is missing on disk
    - A resource is referenced in a DAG (e.g. calculation.yaml) but not in the registry
    - The registry and filesystem are inconsistent
    
    The user must explicitly refresh the registry to resolve this.
    
    Attributes:
        kind: Resource kind ("calculation", "structure", "step", "project")
        selector: Selector that was used (name, slug, path, or ULID)
        id: Resource ID (ULID) if known
        project_root: Project root path where the resource was expected
        expected_path: Expected file path from registry (if known)
        actual_state: Description of what was wrong ("file does not exist", "step not in calculation DAG", etc.)
        details: Additional context (calculation_path, step_id, etc.)
    """
    def __init__(
        self,
        kind: str,
        selector: str | None = None,
        *,
        id: str | None = None,
        project_root: Path | None = None,
        expected_path: Path | str | None = None,
        actual_state: str | None = None,
        details: Dict[str, Any] | None = None,
    ):
        self.kind = kind
        self.selector = selector
        self.id = id
        self.project_root = project_root
        self.expected_path = Path(expected_path) if expected_path else None
        self.actual_state = actual_state or "registry and filesystem are inconsistent"
        self.details = details or {}
        
        # Build user-facing error message
        parts = [
            f"{kind.capitalize()} '{selector or id or 'unknown'}' could not be resolved."
        ]
        
        if expected_path:
            parts.append(f"Expected path from registry: {expected_path}")
        
        if actual_state:
            parts.append(f"Issue: {actual_state}")
        
        parts.append(
            "The project registry may be out of sync with the filesystem. "
            "Please use the Refresh action in the GUI (or run the appropriate CLI refresh command) to rebuild the registry."
        )
        
        error_msg = " ".join(parts)
        super().__init__(error_msg)


@dataclass
class ResourceIndex:
    """
    Index of all resources in a project, built by scanning resource files.
    
    This is the authoritative source for selector → ID resolution.
    Resource files (calculation.yaml, *.step.yaml, *.json) are scanned and
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
    
    def remove_resource(self, resource_id: str) -> None:
        """
        Remove a resource from the index by ID.
        
        This is used for in-place updates when resources are deleted.
        """
        if resource_id not in self.by_id:
            return
        
        meta = self.by_id[resource_id]
        
        # Remove from all mappings
        del self.by_id[resource_id]
        
        if meta.slug in self.by_slug and self.by_slug[meta.slug] == resource_id:
            del self.by_slug[meta.slug]
        
        # Remove from by_path (need to find the path)
        paths_to_remove = [
            path for path, path_id in self.by_path.items()
            if path_id == resource_id
        ]
        for path in paths_to_remove:
            del self.by_path[path]
        
        # Remove from by_name
        name_lower = meta.name.lower()
        if name_lower in self.by_name:
            if resource_id in self.by_name[name_lower]:
                self.by_name[name_lower].remove(resource_id)
            if not self.by_name[name_lower]:
                del self.by_name[name_lower]
    
    def update_resource_path(self, resource_id: str, old_path: Path, new_path: Path) -> None:
        """
        Update the path mapping for a resource (used for renames/moves).
        
        Args:
            resource_id: Resource ID (ULID)
            old_path: Old absolute path
            new_path: New absolute path
        """
        if resource_id not in self.by_id:
            return
        
        old_path = old_path.resolve()
        new_path = new_path.resolve()
        
        # Update by_path mapping
        if old_path in self.by_path and self.by_path[old_path] == resource_id:
            del self.by_path[old_path]
        self.by_path[new_path] = resource_id
    
    def update_resource_meta(self, resource_id: str, new_meta: ResourceMeta) -> None:
        """
        Update the metadata for a resource (used for renames).
        
        Args:
            resource_id: Resource ID (ULID) - must match new_meta.id
            new_meta: Updated ResourceMeta
        """
        if resource_id != new_meta.id:
            raise ValueError(f"Resource ID mismatch: {resource_id} != {new_meta.id}")
        
        if resource_id not in self.by_id:
            return
        
        old_meta = self.by_id[resource_id]
        
        # Update metadata
        self.by_id[resource_id] = new_meta
        
        # Update slug mapping if changed
        if old_meta.slug != new_meta.slug:
            if old_meta.slug in self.by_slug and self.by_slug[old_meta.slug] == resource_id:
                del self.by_slug[old_meta.slug]
            self.by_slug[new_meta.slug] = resource_id
        
        # Update name mapping if changed
        old_name_lower = old_meta.name.lower()
        new_name_lower = new_meta.name.lower()
        if old_name_lower != new_name_lower:
            if old_name_lower in self.by_name:
                if resource_id in self.by_name[old_name_lower]:
                    self.by_name[old_name_lower].remove(resource_id)
                if not self.by_name[old_name_lower]:
                    del self.by_name[old_name_lower]
            if new_name_lower not in self.by_name:
                self.by_name[new_name_lower] = []
            if resource_id not in self.by_name[new_name_lower]:
                self.by_name[new_name_lower].append(resource_id)
    
    def resolve_id(
        self, 
        selector: str, 
        project_root: Path,
        expected_kind: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolve a selector to a resource ID.
        
        Resolution order:
        1. ULID (if selector is a ULID)
        2. slug (exact match, filtered by expected_kind if provided)
        3. name (case-insensitive exact match, filtered by expected_kind if provided)
        4. path (if selector looks like a path)
        
        Args:
            selector: Selector string (ULID, slug, name, or path)
            project_root: Project root path
            expected_kind: Optional resource kind to filter by ("calculation", "step", "structure", "project")
                          If provided, only resources of this kind will be returned.
                          If multiple matches of expected_kind exist, raises AmbiguousSelectorError.
        
        Returns:
            Resource ID (ULID) if found, None otherwise
            
        Raises:
            AmbiguousSelectorError: If expected_kind is provided and multiple resources of that kind match
        """
        import logging
        from quantumvitas.core.debug import is_resolution_debug_enabled
        
        logger = logging.getLogger(__name__)
        debug_enabled = is_resolution_debug_enabled()
        
        # Strategy 1: ULID
        if _is_ulid_like(selector):
            if selector in self.by_id:
                meta = self.by_id[selector]
                # If expected_kind is provided, verify it matches
                if expected_kind and meta.kind != expected_kind:
                    # Always log warnings (not gated by debug flag)
                    logger.warning(
                        f"[RESOLVE_ID] ULID '{selector}' resolved to kind '{meta.kind}', "
                        f"but expected_kind='{expected_kind}'. Returning None."
                    )
                    return None
                if debug_enabled:
                    logger.debug(
                        f"[RESOLVE_ID] Resolved by ULID: '{selector}' -> {selector} "
                        f"(kind={meta.kind}, expected_kind={expected_kind})"
                    )
                return selector
            else:
                if debug_enabled:
                    logger.debug(f"[RESOLVE_ID] ULID '{selector}' not found in by_id index")
        
        # Strategy 2: slug (exact match, filtered by expected_kind)
        if selector in self.by_slug:
            resource_id = self.by_slug[selector]
            meta = self.by_id.get(resource_id)
            if meta:
                # If expected_kind is provided, filter by kind
                if expected_kind:
                    if meta.kind != expected_kind:
                        if debug_enabled:
                            logger.debug(
                                f"[RESOLVE_ID] Slug '{selector}' resolved to kind '{meta.kind}', "
                                f"but expected_kind='{expected_kind}'. Skipping."
                            )
                    else:
                        if debug_enabled:
                            logger.info(
                                f"[RESOLVE_ID] Resolved by SLUG: '{selector}' -> {resource_id} "
                                f"(kind={meta.kind}, expected_kind={expected_kind}, name={meta.name})"
                            )
                        return resource_id
                else:
                    if debug_enabled:
                        logger.info(
                            f"[RESOLVE_ID] Resolved by SLUG: '{selector}' -> {resource_id} "
                            f"(kind={meta.kind}, name={meta.name})"
                        )
                    return resource_id
        
        # Strategy 3: name (case-insensitive exact match, filtered by expected_kind)
        name_lower = selector.lower()
        if name_lower in self.by_name:
            ids = self.by_name[name_lower]
            
            # Filter by expected_kind if provided
            if expected_kind:
                matching_ids = [
                    id for id in ids 
                    if self.by_id.get(id) and self.by_id[id].kind == expected_kind
                ]
                if len(matching_ids) > 1:
                    # Ambiguous - multiple resources of expected_kind with same name
                    raise AmbiguousSelectorError(
                        f"Name '{selector}' matches {len(matching_ids)} {expected_kind} resources: "
                        f"{matching_ids}. Please use ULID or slug to disambiguate."
                    )
                elif len(matching_ids) == 1:
                    resource_id = matching_ids[0]
                    meta = self.by_id.get(resource_id)
                    if debug_enabled:
                        logger.info(
                            f"[RESOLVE_ID] Resolved by NAME: '{selector}' -> {resource_id} "
                            f"(kind={meta.kind if meta else 'unknown'}, expected_kind={expected_kind})"
                        )
                    return resource_id
                else:
                    # No matches of expected_kind
                    if debug_enabled:
                        logger.debug(
                            f"[RESOLVE_ID] Name '{selector}' matches {len(ids)} resources, "
                            f"but none are of expected_kind='{expected_kind}'"
                        )
                    return None
            else:
                # No expected_kind filter
                if len(ids) == 1:
                    resource_id = ids[0]
                    meta = self.by_id.get(resource_id)
                    if debug_enabled:
                        logger.info(
                            f"[RESOLVE_ID] Resolved by NAME: '{selector}' -> {resource_id} "
                            f"(kind={meta.kind if meta else 'unknown'})"
                        )
                    return resource_id
                elif len(ids) > 1:
                    # Ambiguous - multiple resources with same name
                    # Always log warnings (not gated by debug flag)
                    logger.warning(
                        f"[RESOLVE_ID] Ambiguous name match: '{selector}' matches {len(ids)} resources: {ids}"
                    )
                    # For now, return None (caller should handle ambiguity)
                    return None
        
        # Strategy 4: path
        if _is_path_like(selector):
            path = Path(selector)
            if not path.is_absolute():
                path = (project_root / path).resolve()
            if path in self.by_path:
                resource_id = self.by_path[path]
                meta = self.by_id.get(resource_id)
                # If expected_kind is provided, verify it matches
                if expected_kind and meta and meta.kind != expected_kind:
                    if debug_enabled:
                        logger.debug(
                            f"[RESOLVE_ID] Path '{selector}' resolved to kind '{meta.kind}', "
                            f"but expected_kind='{expected_kind}'. Returning None."
                        )
                    return None
                if debug_enabled:
                    logger.info(
                        f"[RESOLVE_ID] Resolved by PATH: '{selector}' -> {resource_id} "
                        f"(kind={meta.kind if meta else 'unknown'}, expected_kind={expected_kind})"
                    )
                return resource_id
        
        if debug_enabled:
            logger.debug(
                f"[RESOLVE_ID] No match found for selector: '{selector}' "
                f"(expected_kind={expected_kind})"
            )
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


def validate_ulid(ulid_str: str, kind: str = "resource") -> str:
    """
    Validate that a string is a valid ULID.
    
    Args:
        ulid_str: String to validate
        kind: Resource kind for error message (e.g., "calculation", "step")
        
    Returns:
        The ULID string if valid
        
    Raises:
        ValueError: If the string is not a valid ULID
    """
    if not _is_ulid_like(ulid_str):
        raise ValueError(
            f"Invalid {kind} identifier: '{ulid_str}' is not a ULID. "
            f"Expected 26-character ULID (e.g., '01ABCDEFGHIJKLMNOPQRSTUVWX'). "
            f"Please resolve slug/name to ULID first using resolve_calculation() or similar."
        )
    return ulid_str


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
    - calculations/**/calculation.yaml
    - calculations/**/steps/*.step.yaml
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
    
    # Skip anything under trash/ folder
    trash_dir = project_root / "trash"
    
    # Scan calculations
    calculations_dir = project_root / "calculations"
    if calculations_dir.exists():
        for calculation_dir in calculations_dir.iterdir():
            if not calculation_dir.is_dir():
                continue
            
            # Skip if under trash/
            try:
                if trash_dir.exists() and calculation_dir.is_relative_to(trash_dir):
                    continue
            except (ValueError, AttributeError):
                # is_relative_to may not be available in older Python versions
                # Fallback: check if trash_dir is a parent
                try:
                    calculation_dir.resolve().relative_to(trash_dir.resolve())
                    continue  # Under trash, skip
                except ValueError:
                    pass  # Not under trash, continue
            
            calculation_yaml = calculation_dir / "calculation.yaml"
            if calculation_yaml.exists():
                try:
                    data = yaml.safe_load(calculation_yaml.read_text()) or {}
                    meta_dict = data.get("meta", {})
                    if meta_dict and meta_dict.get("id"):
                        from quantumvitas.core.resources import ResourceMeta
                        default_name = meta_dict.get("name") or calculation_dir.name
                        default_path = meta_dict.get("path") or f"calculations/{calculation_dir.name}"
                        meta = ResourceMeta.from_dict(
                            meta_dict, 
                            kind="calculation",
                            default_name=default_name,
                            default_path=default_path,
                        )
                        index.add_resource(meta, calculation_yaml)
                except Exception as e:
                    # Skip invalid calculation files (log in debug mode if needed)
                    continue
            
            # Scan steps in this calculation
            steps_dir = calculation_dir / "steps"
            if steps_dir.exists():
                for step_file in steps_dir.glob("*.step.yaml"):
                    # Skip if under trash/
                    try:
                        if trash_dir.exists() and step_file.is_relative_to(trash_dir):
                            continue
                    except (ValueError, AttributeError):
                        try:
                            step_file.resolve().relative_to(trash_dir.resolve())
                            continue  # Under trash, skip
                        except ValueError:
                            pass  # Not under trash, continue
                    try:
                        data = yaml.safe_load(step_file.read_text()) or {}
                        meta_dict = data.get("meta", {})
                        if meta_dict and meta_dict.get("id"):
                            from quantumvitas.core.resources import ResourceMeta
                            default_name = meta_dict.get("name") or step_file.stem
                            default_path = meta_dict.get("path") or f"calculations/{calculation_dir.name}/steps/{step_file.name}"
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
            # Skip if under trash/
            try:
                if trash_dir.exists() and struct_file.is_relative_to(trash_dir):
                    continue
            except (ValueError, AttributeError):
                try:
                    struct_file.resolve().relative_to(trash_dir.resolve())
                    continue  # Under trash, skip
                except ValueError:
                    pass  # Not under trash, continue
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
    duration_ms = duration * 1000
    
    # Log if it takes more than 100ms
    if duration_ms > 100:
        import inspect
        import logging
        
        # Get caller info using inspect.stack() for better accuracy
        stack = inspect.stack()
        caller_info = "unknown"
        if len(stack) > 1:
            frame = stack[1]
            caller_file = Path(frame.filename).name
            caller_name = frame.function
            caller_line = frame.lineno
            caller_info = f"{caller_file}:{caller_line} in {caller_name}"
        
        logger = logging.getLogger(__name__)
        logger.warning(
            f"[build_resource_index] SLOW: {duration_ms:.1f}ms for {project_root} "
            f"(called from {caller_info})"
        )
    
    return index


# ---------------------------------------------------------------------------
# In-place registry update helpers (for write operations)
# ---------------------------------------------------------------------------

def update_registry_add_step(
    index: ResourceIndex,
    step_meta: "ResourceMeta",
    step_file_path: Path,
) -> None:
    """
    Add a step to the registry in-place (after step creation).
    
    Args:
        index: ResourceIndex to update
        step_meta: ResourceMeta for the new step
        step_file_path: Absolute path to the step YAML file
    """
    index.add_resource(step_meta, step_file_path.resolve())


def update_registry_remove_step(
    index: ResourceIndex,
    step_id: str,
) -> None:
    """
    Remove a step from the registry in-place (after step deletion).
    
    Args:
        index: ResourceIndex to update
        step_id: Step ID (ULID) to remove
    """
    index.remove_resource(step_id)


def update_registry_add_calculation(
    index: ResourceIndex,
    calculation_meta: "ResourceMeta",
    calculation_yaml_path: Path,
) -> None:
    """
    Add a calculation to the registry in-place (after calculation creation).
    
    Args:
        index: ResourceIndex to update
        calculation_meta: ResourceMeta for the new calculation
        calculation_yaml_path: Absolute path to calculation.yaml
    """
    index.add_resource(calculation_meta, calculation_yaml_path.resolve())


def update_registry_remove_calculation(
    index: ResourceIndex,
    calculation_id: str,
) -> None:
    """
    Remove a calculation from the registry in-place (after calculation deletion).
    
    Args:
        index: ResourceIndex to update
        calculation_id: Calculation ID (ULID) to remove
    """
    index.remove_resource(calculation_id)


def update_registry_rename_calculation(
    index: ResourceIndex,
    calculation_id: str,
    new_meta: "ResourceMeta",
    old_path: Path,
    new_path: Path,
) -> None:
    """
    Update calculation metadata in registry in-place (after rename).
    
    Args:
        index: ResourceIndex to update
        calculation_id: Calculation ID (ULID)
        new_meta: Updated ResourceMeta
        old_path: Old absolute path to calculation.yaml
        new_path: New absolute path to calculation.yaml
    """
    index.update_resource_meta(calculation_id, new_meta)
    index.update_resource_path(calculation_id, old_path, new_path)


def update_registry_add_structure(
    index: ResourceIndex,
    structure_meta: "ResourceMeta",
    structure_file_path: Path,
) -> None:
    """
    Add a structure to the registry in-place (after structure import).
    
    Args:
        index: ResourceIndex to update
        structure_meta: ResourceMeta for the new structure
        structure_file_path: Absolute path to the structure JSON file
    """
    index.add_resource(structure_meta, structure_file_path.resolve())


def update_registry_remove_structure(
    index: ResourceIndex,
    structure_id: str,
) -> None:
    """
    Remove a structure from the registry in-place (after structure deletion).
    
    Args:
        index: ResourceIndex to update
        structure_id: Structure ID (ULID) to remove
    """
    index.remove_resource(structure_id)


def update_registry_rename_structure(
    index: ResourceIndex,
    structure_id: str,
    new_meta: "ResourceMeta",
    old_path: Path,
    new_path: Path,
) -> None:
    """
    Update structure metadata in registry in-place (after rename).
    
    Args:
        index: ResourceIndex to update
        structure_id: Structure ID (ULID)
        new_meta: Updated ResourceMeta
        old_path: Old absolute path to structure file
        new_path: New absolute path to structure file
    """
    index.update_resource_meta(structure_id, new_meta)
    index.update_resource_path(structure_id, old_path, new_path)


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
# Calculation resolution
# ---------------------------------------------------------------------------


def resolve_calculation(
    project_root: Path,
    selector: str,
    config: Optional[dict] = None,
    index: Optional[ResourceIndex] = None,
) -> ResolvedResource:
    """
    Resolve a calculation selector to a resource.
    
    Uses ResourceIndex (built from resource files) as the authoritative source.
    Falls back to config entries for backwards compatibility.
    
    Args:
        project_root: Path to project root (contains project.qv.yml)
        selector: ULID, slug, name, or path to calculation directory
        config: Optional pre-loaded config dict (loaded if None)
        index: Optional ResourceIndex (built if None)
        
    Returns:
        ResolvedResource for the calculation
        
    Raises:
        SelectorNotFoundError: If no calculation matches
        AmbiguousSelectorError: If multiple calculations match
        ValueError: If selector is None
    """
    # Build index if not provided
    if index is None:
        index = build_resource_index(project_root)
    
    # Handle None selector (should not happen, but be defensive)
    if selector is None:
        raise ValueError("Calculation selector cannot be None")
    
    selector = selector.strip()
    
    # Try to resolve via ResourceIndex first (with expected_kind filter)
    resource_id = index.resolve_id(selector, project_root, expected_kind="calculation")
    if resource_id:
        # Found in index - get meta and build ResolvedResource
        meta = index.by_id[resource_id]
        if meta.kind != "calculation":
            # Should not happen with expected_kind filter, but defensive check
            raise SelectorNotFoundError(f"Resource '{selector}' is not a calculation (kind: {meta.kind})")
        
        # Find absolute path (calculation directory)
        # Note: absolute_path points to the calculation directory, not the calculation.yaml file.
        # This matches the contract expected by most code which uses absolute_path directly as a directory.
        abs_path = None
        for path, path_id in index.by_path.items():
            if path_id == resource_id:
                # index.by_path stores the calculation.yaml file path, so get parent directory
                abs_path = path.parent
                break
        
        if abs_path is None:
            # Fallback: construct from meta.path (which is a directory path like "calculations/wf")
            # CRITICAL: meta.path must be the correct directory path, not just "calculations"
            abs_path = (project_root / meta.path).resolve()
            # Verify the path is correct - it should be a directory, not a file
            if not abs_path.is_dir():
                # If meta.path is wrong, try to find the correct path from the index
                # This should not happen if the index was built correctly, but defensive check
                raise SelectorNotFoundError(
                    f"Calculation '{selector}' resolved but path construction failed. "
                    f"meta.path={meta.path}, constructed_path={abs_path}"
                )
        
        # Build entry dict for backwards compatibility (minimal, ID-only)
        entry = {"id": resource_id, "meta": meta.to_dict()}
        
        return ResolvedResource(meta=meta, entry=entry, absolute_path=abs_path)
    
    # Fallback to legacy config-based resolution for backwards compatibility
    if config is None:
        config = _load_config(project_root)
    
    entries = config.get("calculations", [])
    selector = selector.strip()
    
    # Strategy 1: Path
    if _is_path_like(selector):
        resolved = _resolve_calculation_by_path(project_root, entries, selector)
        if resolved:
            return resolved
    
    # Strategy 2: ULID
    if _is_ulid_like(selector):
        matches = [e for e in entries if _entry_matches_ulid(e, selector)]
        if len(matches) == 1:
            return _calculation_to_resolved(project_root, matches[0])
        if len(matches) > 1:
            raise AmbiguousSelectorError(f"ULID '{selector}' matches multiple calculations")
    
    # Strategy 3: slug (exact match)
    slug_matches = [e for e in entries if _entry_matches_slug(e, selector)]
    if len(slug_matches) == 1:
        return _calculation_to_resolved(project_root, slug_matches[0])
    if len(slug_matches) > 1:
        raise AmbiguousSelectorError(f"Slug '{selector}' matches multiple calculations")
    
    # Strategy 4: name (case-insensitive exact match)
    name_matches = [e for e in entries if _entry_matches_name(e, selector)]
    if len(name_matches) == 1:
        return _calculation_to_resolved(project_root, name_matches[0])
    if len(name_matches) > 1:
        raise AmbiguousSelectorError(f"Name '{selector}' matches multiple calculations")
    
    raise SelectorNotFoundError(f"Calculation '{selector}' not found")


def _resolve_calculation_by_path(
    project_root: Path,
    entries: list,
    selector: str,
) -> Optional[ResolvedResource]:
    """Try to resolve calculation by path."""
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
            return _calculation_to_resolved(project_root, entry)
    
    return None


def _calculation_to_resolved(project_root: Path, entry: dict) -> ResolvedResource:
    """Convert a calculation entry to ResolvedResource."""
    # ID-only model: entry only has calculation_id (or id), need to load calculation.yaml to get meta
    calculation_id = entry.get("calculation_id") or entry.get("id")
    
    # Try to find and load calculation.yaml by ID
    calculations_dir = project_root / "calculations"
    if calculations_dir.exists() and calculation_id:
        for calculation_dir in calculations_dir.iterdir():
            if not calculation_dir.is_dir():
                continue
            calculation_yaml = calculation_dir / "calculation.yaml"
            if calculation_yaml.exists():
                try:
                    import yaml
                    wf_data = yaml.safe_load(calculation_yaml.read_text())
                    wf_meta_dict = wf_data.get("meta") or {}
                    if wf_meta_dict.get("id") == calculation_id:
                        # Found matching calculation - use its meta
                        from quantumvitas.core.resources import ResourceMeta
                        resource_meta = ResourceMeta.from_dict(
                            wf_meta_dict,
                            kind="calculation",
                            default_name=wf_meta_dict.get("name", "Calculation"),
                            default_path=wf_meta_dict.get("path", f"calculations/{calculation_dir.name}"),
                        )
                        # absolute_path must point to the calculation directory, not the file
                        abs_path = calculation_dir.resolve()
                        return ResolvedResource(meta=resource_meta, entry=entry, absolute_path=abs_path)
                except Exception:
                    continue
    
    # Fallback: use entry data (legacy format or calculation.yaml not found)
    meta = entry.get("meta") or {}
    default_name = entry.get("name") or meta.get("name") or "Calculation"
    default_path = entry.get("path") or meta.get("path") or f"calculations/{slugify(default_name)}"
    
    resource_meta = _entry_to_meta(entry, "calculation", default_path)
    # absolute_path must point to the calculation directory, not the file
    # If default_path already includes "calculation.yaml", strip it
    calc_dir_path = resource_meta.path
    if calc_dir_path.endswith("/calculation.yaml"):
        calc_dir_path = calc_dir_path[:-len("/calculation.yaml")]
    elif calc_dir_path.endswith("calculation.yaml"):
        calc_dir_path = calc_dir_path[:-len("calculation.yaml")]
    abs_path = (project_root / calc_dir_path).resolve()
    
    return ResolvedResource(meta=resource_meta, entry=entry, absolute_path=abs_path)
    """Convert a calculation entry to ResolvedResource."""
    meta = entry.get("meta") or {}
    default_name = entry.get("name") or meta.get("name") or "Calculation"
    default_path = entry.get("path") or meta.get("path") or f"calculations/{slugify(default_name)}"
    
    resource_meta = _entry_to_meta(entry, "calculation", default_path)
    abs_path = (project_root / resource_meta.path).resolve()
    
    return ResolvedResource(meta=resource_meta, entry=entry, absolute_path=abs_path)


# ---------------------------------------------------------------------------
# Step resolution
# ---------------------------------------------------------------------------


def resolve_step(
    project_root: Path,
    calculation_selector: str,
    step_selector: str,
    config: Optional[dict] = None,
    index: Optional[ResourceIndex] = None,
) -> ResolvedResource:
    """
    Resolve a step selector within a calculation.
    
    Uses ResourceIndex (built from resource files) as the authoritative source.
    Falls back to scanning step files for backwards compatibility.
    
    Args:
        project_root: Path to project root
        calculation_selector: Selector for parent calculation
        step_selector: ULID, id, name, or path to step YAML
        config: Optional pre-loaded config dict
        index: Optional ResourceIndex (built if None)
        
    Returns:
        ResolvedResource for the step
        
    Raises:
        SelectorNotFoundError: If calculation or step not found
    """
    # Resolve calculation first (pass index to avoid rebuilding)
    calculation = resolve_calculation(project_root, calculation_selector, config=config, index=index)
    # calculation.absolute_path points to calculation.yaml, so get the parent directory
    if calculation.absolute_path.name == "calculation.yaml":
        calculation_dir = calculation.absolute_path.parent
    else:
        calculation_dir = calculation.absolute_path
    
    # Handle None step_selector (should not happen, but be defensive)
    if step_selector is None:
        raise ValueError("Step selector cannot be None")
    
    step_selector = step_selector.strip()
    
    # Build index if not provided
    if index is None:
        index = build_resource_index(project_root)
    
    import logging
    from quantumvitas.core.debug import is_resolution_debug_enabled
    
    logger = logging.getLogger(__name__)
    debug_enabled = is_resolution_debug_enabled()
    
    if debug_enabled:
        logger.info(
            f"[RESOLVE_STEP] Resolving step: selector='{step_selector}', "
            f"calculation='{calculation_selector}', project_root={project_root}"
        )
    
    # Strategy 1: Try ResourceIndex first (preferred)
    # Use expected_kind="step" to prevent slug collisions with calculations/structures
    resource_id = index.resolve_id(step_selector, project_root, expected_kind="step")
    if resource_id:
        meta = index.by_id.get(resource_id)
        if debug_enabled:
            logger.info(
                f"[RESOLVE_STEP] ResourceIndex resolved: selector='{step_selector}' -> "
                f"resource_id={resource_id}, kind={meta.kind if meta else 'unknown'}, "
                f"slug={meta.slug if meta else 'unknown'}, name={meta.name if meta else 'unknown'}, "
                f"expected_kind=step"
            )
        if meta and meta.kind == "step":
            # Verify this step belongs to the calculation
            # Check if step path is within calculation directory
            # NOTE: meta.path is used ONLY for verification (belongs-to check), NOT for resolution
            # Resolution happens via ResourceIndex.resolve_id() above, which uses ULID/slug/name/path selectors
            step_path = project_root / meta.path if meta.path else None
            if step_path and step_path.is_relative_to(calculation_dir):
                # Find absolute path
                abs_path = None
                for path, path_id in index.by_path.items():
                    if path_id == resource_id:
                        abs_path = path
                        break
                
                if abs_path is None:
                    # Fallback: construct from meta.path (display-only, should not be used for resolution)
                    if step_path:
                        abs_path = step_path.resolve()
                    else:
                        logger.error(
                            f"[RESOLVE_STEP] ERROR: Cannot construct step path - meta.path is missing. "
                            f"step_id={resource_id}, slug={meta.slug}"
                        )
                        raise SelectorNotFoundError(
                            f"Step '{step_selector}' resolved but meta.path is missing. "
                            f"This is a data integrity issue."
                        )
                
                if debug_enabled:
                    logger.info(
                        f"[RESOLVE_STEP] Step resolved successfully: "
                        f"id={resource_id}, slug={meta.slug}, path={abs_path}"
                    )
                
                # CRITICAL: Verify the file actually exists on disk
                # If registry says it exists but file is missing, raise RegistryOutOfSyncError
                if not abs_path.exists():
                    raise RegistryOutOfSyncError(
                        kind="step",
                        selector=step_selector,
                        id=resource_id,
                        project_root=project_root,
                        expected_path=abs_path,
                        actual_state="file does not exist",
                        details={
                            "calculation_selector": calculation_selector,
                            "calculation_dir": str(calculation_dir),
                            "reason": "step_file_missing",
                        },
                    )
                
                # Build entry dict for backwards compatibility
                try:
                    entry_data = yaml.safe_load(abs_path.read_text()) or {}
                except Exception:
                    entry_data = {}
                
                return ResolvedResource(meta=meta, entry=entry_data, absolute_path=abs_path)
        else:
            # Resource found but wrong kind (should not happen with expected_kind filter)
            kind_str = meta.kind if meta else "unknown"
            # Always log errors (not gated by debug flag)
            logger.error(
                f"[RESOLVE_STEP] ERROR: Resource '{step_selector}' resolved to "
                f"kind='{kind_str}', expected='step'. "
                f"This should not happen when expected_kind='step' is used. "
                f"This indicates a bug in resolve_id() filtering."
            )
    
    # Strategy 2: Path (fallback for backwards compat)
    if _is_path_like(step_selector):
        step_path = _resolve_step_by_path(calculation_dir, step_selector)
        if step_path:
            return _step_path_to_resolved(step_path, project_root)
    
    # Strategy 3: Scan step files (fallback for backwards compat)
    steps_dir = calculation_dir / "steps"
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
        f"Step '{step_selector}' not found in calculation '{calculation.name}'"
    )


def _resolve_step_by_path(calculation_dir: Path, selector: str) -> Optional[Path]:
    """Try to resolve step by direct path."""
    # Handle relative paths like "steps/scf.step.yaml"
    if selector.startswith("steps/"):
        selector = selector[6:]  # Remove "steps/" prefix
    
    candidates = [
        Path(selector),
        calculation_dir / selector,
        calculation_dir / "steps" / selector,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.suffix in (".yaml", ".yml"):
            return candidate.resolve()
    return None


def _step_path_to_resolved(step_path: Path, project_root: Path) -> ResolvedResource:
    """Convert a step file path to ResolvedResource.
    
    CRITICAL: meta.slug MUST come from the YAML file (authoritative source),
    not re-computed from name. This ensures consistency between YAML and
    in-memory Step objects (constitution requirement).
    """
    try:
        data = yaml.safe_load(step_path.read_text()) or {}
    except Exception:
        data = {}
    
    meta_dict = data.get("meta") or {}
    step_id = meta_dict.get("id") or data.get("id") or step_path.stem.replace(".step", "")
    step_name = meta_dict.get("name") or data.get("step_type") or step_id
    # CRITICAL FIX: Use meta.slug from YAML (authoritative), fallback to slugify(name)
    # Previously: slug=slugify(step_name) - this caused inconsistency when step_name="md"
    # but YAML meta.slug="md-1"
    step_slug = meta_dict.get("slug") or slugify(step_name)
    
    from quantumvitas.core.resources import generate_resource_id
    
    resource_meta = ResourceMeta(
        id=meta_dict.get("id") or generate_resource_id(),
        name=step_name,
        slug=step_slug,  # Use YAML-sourced slug (authoritative)
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
        resolved = resolve_structure(project_root, selector_or_id, config, index)
        
        # CRITICAL: Verify the file actually exists on disk
        # If registry says it exists but file is missing, raise RegistryOutOfSyncError
        if not resolved.absolute_path.exists():
            # Find expected path from registry if available
            expected_path = None
            if index:
                resource_id = index.resolve_id(selector_or_id, project_root)
                if resource_id:
                    for path, path_id in index.by_path.items():
                        if path_id == resource_id:
                            expected_path = path
                            break
            
            raise RegistryOutOfSyncError(
                kind="structure",
                selector=selector_or_id,
                id=resolved.meta.id if resolved.meta else None,
                project_root=project_root,
                expected_path=expected_path or resolved.absolute_path,
                actual_state="file does not exist",
                details={
                    "reason": "structure_file_missing",
                },
            )
        
        return resolved
    except RegistryOutOfSyncError:
        # Propagate RegistryOutOfSyncError as-is
        raise
    except SelectorNotFoundError as e:
        # Convert to ResourceNotFoundError for API/CLI layers
        raise ResourceNotFoundError(
            kind="structure",
            selector=selector_or_id,
            project_root=project_root,
        ) from e


def require_calculation(
    project_root: Path,
    selector_or_id: str,
    config: Optional[dict] = None,
    index: Optional[ResourceIndex] = None,
) -> ResolvedResource:
    """
    Require a calculation resource - raise ResourceNotFoundError if not found.
    
    This is a wrapper around resolve_calculation that converts SelectorNotFoundError
    to ResourceNotFoundError for clearer error handling in API/CLI layers.
    
    Args:
        project_root: Path to project root
        selector_or_id: Calculation selector (name, slug, path, or ULID)
        config: Optional pre-loaded config dict
        index: Optional ResourceIndex (built if None)
        
    Returns:
        ResolvedResource for the calculation
        
    Raises:
        ResourceNotFoundError: If calculation not found
        AmbiguousSelectorError: If multiple calculations match
    """
    try:
        resolved = resolve_calculation(project_root, selector_or_id, config, index)
        
        # CRITICAL: Verify the file actually exists on disk
        # If registry says it exists but file is missing, raise RegistryOutOfSyncError
        if not resolved.absolute_path.exists():
            # Find expected path from registry if available
            expected_path = None
            if index:
                resource_id = index.resolve_id(selector_or_id, project_root)
                if resource_id:
                    for path, path_id in index.by_path.items():
                        if path_id == resource_id:
                            expected_path = path
                            break
            
            raise RegistryOutOfSyncError(
                kind="calculation",
                selector=selector_or_id,
                id=resolved.meta.id if resolved.meta else None,
                project_root=project_root,
                expected_path=expected_path or resolved.absolute_path,
                actual_state="file does not exist",
                details={
                    "reason": "calculation_file_missing",
                },
            )
        
        return resolved
    except RegistryOutOfSyncError:
        # Propagate RegistryOutOfSyncError as-is
        raise
    except SelectorNotFoundError as e:
        # Convert to ResourceNotFoundError for API/CLI layers
        raise ResourceNotFoundError(
            kind="calculation",
            selector=selector_or_id,
            project_root=project_root,
        ) from e


def require_step(
    project_root: Path,
    calculation_selector: str,
    step_selector_or_id: str,
    config: Optional[dict] = None,
    index: Optional[ResourceIndex] = None,
) -> ResolvedResource:
    """
    Require a step resource within a calculation - raise ResourceNotFoundError if not found.
    
    This is a wrapper around resolve_step that converts SelectorNotFoundError
    to ResourceNotFoundError for clearer error handling in API/CLI layers.
    
    Args:
        project_root: Path to project root
        calculation_selector: Calculation selector (name, slug, path, or ULID)
        step_selector_or_id: Step selector (ULID, id, name, or path)
        config: Optional pre-loaded config dict
        index: Optional ResourceIndex (built if None)
        
    Returns:
        ResolvedResource for the step
        
    Raises:
        ResourceNotFoundError: If calculation or step not found
        AmbiguousSelectorError: If multiple calculations match
    """
    try:
        return resolve_step(project_root, calculation_selector, step_selector_or_id, config=config, index=index)
    except SelectorNotFoundError as e:
        # Convert to ResourceNotFoundError for API/CLI layers
        # Try to extract calculation name for better error message
        calculation_name = calculation_selector
        try:
            calculation = resolve_calculation(project_root, calculation_selector, config=config, index=index)
            calculation_name = calculation.meta.name
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


def list_calculations(project_root: Path, config: Optional[dict] = None) -> List[ResolvedResource]:
    """List all calculations in a project."""
    if config is None:
        config = _load_config(project_root)
    
    results = []
    for entry in config.get("calculations", []):
        try:
            results.append(_calculation_to_resolved(project_root, entry))
        except Exception:
            continue
    return results


def list_steps(
    project_root: Path,
    calculation_selector: str,
    config: Optional[dict] = None,
) -> List[ResolvedResource]:
    """List all steps in a calculation."""
    calculation = resolve_calculation(project_root, calculation_selector, config)
    steps_dir = calculation.absolute_path / "steps"
    
    results = []
    if steps_dir.exists():
        for step_file in steps_dir.glob("*.step.yaml"):
            try:
                results.append(_step_path_to_resolved(step_file, project_root))
            except Exception:
                continue
    return results

