"""
Centralized selector extraction and matching for workflows, structures, and steps.

This module provides consistent helpers for:
- Extracting selectors from project.qv.yml entries and workflow.yaml entries
- Matching human-friendly selectors (slug, name, type) to actual resources (ULIDs)
- Resolving selectors to resources via the registry

All selector logic should go through these helpers to ensure consistency across
CLI, daemon, API, and project context code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from quantumvitas.core.resolution import (
    ResourceIndex,
    require_step,
    ResolvedResource,
    ResourceNotFoundError,
    SelectorNotFoundError,
    AmbiguousSelectorError,
)


# ---------------------------------------------------------------------------
# Selector extraction from entries
# ---------------------------------------------------------------------------

def extract_workflow_selector_from_entry(entry: dict) -> Optional[str]:
    """
    Extract a workflow selector from a project.qv.yml entry.
    
    Priority order:
    1. workflow_id (ID-only model)
    2. meta.id (ULID)
    3. meta.slug (slug)
    4. id (legacy)
    5. name (legacy)
    
    Returns:
        Selector string (ULID, slug, or name) or None if no valid selector found
        
    Example:
        entry = {"workflow_id": "01KC38MFJZ7RF3SB7SHVYDQ4J8"}
        selector = extract_workflow_selector_from_entry(entry)  # Returns ULID
    """
    return (
        entry.get("workflow_id") or
        (entry.get("meta") or {}).get("id") or
        (entry.get("meta") or {}).get("slug") or
        entry.get("id") or
        entry.get("name")
    )


def extract_structure_selector_from_entry(entry: dict) -> Optional[str]:
    """
    Extract a structure selector from a project.qv.yml entry.
    
    Priority order:
    1. structure_id (ID-only model)
    2. meta.id (ULID)
    3. meta.slug (slug)
    4. id (legacy)
    5. name (legacy)
    
    Returns:
        Selector string (ULID, slug, or name) or None if no valid selector found
    """
    return (
        entry.get("structure_id") or
        (entry.get("meta") or {}).get("id") or
        (entry.get("meta") or {}).get("slug") or
        entry.get("id") or
        entry.get("name")
    )


def extract_step_selector_from_entry(entry: dict) -> Optional[str]:
    """
    Extract a step selector from a workflow.yaml steps entry.
    
    Priority order:
    1. step_id (DAG + ID-only model - ULID)
    2. id (legacy)
    3. name (legacy)
    
    Returns:
        Selector string (ULID or name) or None if no valid selector found
    """
    return (
        entry.get("step_id") or
        entry.get("id") or
        entry.get("name")
    )


# ---------------------------------------------------------------------------
# Step selector matching
# ---------------------------------------------------------------------------

def match_step_selector(
    *,
    project_root: Path,
    workflow_dir: Path,
    steps: list[dict],
    selector: str,
    index: Optional[ResourceIndex] = None,
    config: Optional[dict] = None,
) -> dict:
    """
    Match a human-friendly step selector to a step entry in a workflow's steps list.
    
    Given a workflow's steps list and a selector (ULID / slug / name / step_type / index),
    return the matching step entry dict.
    
    Matching priority:
    1. ULID (26-char alphanumeric) → match step["step_id"] == selector
    2. Resolve via registry to get step metadata, then match by:
       - meta.slug
       - meta.name
       - step_type (from step spec)
    3. step["type"] (from workflow.yaml entry) - legacy/fallback
    4. Numeric string → 1-based index into steps list
    
    Args:
        project_root: Project root path
        workflow_dir: Workflow directory path
        steps: List of step entry dicts from workflow.yaml
        selector: Human selector (ULID, slug, name, step_type, or index)
        index: Optional ResourceIndex (built if None)
        config: Optional project config (loaded if None)
        
    Returns:
        Step entry dict from steps list
        
    Raises:
        SelectorNotFoundError: If selector doesn't match any step
        AmbiguousSelectorError: If selector matches multiple steps
    """
    if not steps:
        raise SelectorNotFoundError(f"No steps found in workflow")
    
    selector = selector.strip()
    
    # Build index and config if not provided
    if index is None:
        from quantumvitas.core.resolution import build_resource_index
        index = build_resource_index(project_root)
    if config is None:
        # Lazy import to avoid circular dependency
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
    
    # Get workflow slug for require_step
    workflow_slug = workflow_dir.name
    
    # Strategy 1: ULID match (exact match on step_id)
    if _is_ulid_like(selector):
        for step_entry in steps:
            step_id_ulid = extract_step_selector_from_entry(step_entry)
            if step_id_ulid == selector:
                return step_entry
        raise SelectorNotFoundError(f"Step with ULID '{selector}' not found in workflow")
    
    # Strategy 2: Numeric index (1-based)
    if selector.isdigit():
        idx = int(selector) - 1  # Convert to 0-based
        if 0 <= idx < len(steps):
            return steps[idx]
        raise SelectorNotFoundError(
            f"Step index '{selector}' out of range. "
            f"Workflow has {len(steps)} step(s) (use 1-{len(steps)})"
        )
    
    # Strategy 3: Resolve via registry and match by slug/name/type
    matches = []
    
    for step_entry in steps:
        step_id_ulid = extract_step_selector_from_entry(step_entry)
        if not step_id_ulid:
            continue
        
        # Try to resolve step to get metadata
        try:
            step_resolved = require_step(
                project_root,
                workflow_slug,
                step_id_ulid,
                config=config,
                index=index,
            )
            
            # Check if selector matches slug
            if step_resolved.meta.slug and step_resolved.meta.slug.lower() == selector.lower():
                matches.append((step_entry, step_resolved, "slug"))
                continue
            
            # Check if selector matches name
            if step_resolved.meta.name and step_resolved.meta.name.lower() == selector.lower():
                matches.append((step_entry, step_resolved, "name"))
                continue
            
            # Check if selector matches step_type (from step spec)
            try:
                from quantumvitas.workflow.structure_steps import StructureStepSpec
                spec = StructureStepSpec.from_yaml(step_resolved.absolute_path)
                if spec.step_type and spec.step_type.lower() == selector.lower():
                    matches.append((step_entry, step_resolved, "step_type"))
                    continue
            except Exception:
                pass
            
        except Exception:
            # Resolution failed - try legacy fallback
            pass
        
        # Strategy 4: Legacy fallback - match by type from workflow.yaml entry
        step_type = step_entry.get("type")
        if step_type and step_type.lower() == selector.lower():
            matches.append((step_entry, None, "type"))
    
    # Handle matches
    if len(matches) == 0:
        # Build available identifiers for error message
        available = []
        for step_entry in steps:
            step_id_ulid = extract_step_selector_from_entry(step_entry)
            if step_id_ulid:
                try:
                    step_resolved = require_step(
                        project_root,
                        workflow_slug,
                        step_id_ulid,
                        config=config,
                        index=index,
                    )
                    if step_resolved.meta.slug:
                        available.append(step_resolved.meta.slug)
                    elif step_resolved.meta.name:
                        available.append(step_resolved.meta.name)
                    else:
                        available.append(step_id_ulid[:8] + "...")
                except Exception:
                    step_type = step_entry.get("type")
                    if step_type:
                        available.append(step_type)
                    else:
                        available.append(step_id_ulid[:8] + "...")
        
        raise SelectorNotFoundError(
            f"Step '{selector}' not found in workflow. "
            f"Available: {', '.join(sorted(set(available)))}"
        )
    
    if len(matches) > 1:
        # Ambiguous match - provide details
        match_details = []
        for step_entry, step_resolved, match_type in matches:
            step_id_ulid = extract_step_selector_from_entry(step_entry)
            if step_resolved:
                identifier = step_resolved.meta.slug or step_resolved.meta.name or step_id_ulid[:8]
            else:
                identifier = step_entry.get("type") or step_id_ulid[:8]
            match_details.append(f"{identifier} (ULID: {step_id_ulid[:8]}...)")
        
        raise AmbiguousSelectorError(
            f"Selector '{selector}' is ambiguous: matches steps {match_details}. "
            f"Please use a more specific selector (ULID or unique slug)."
        )
    
    # Single match found
    return matches[0][0]


def _is_ulid_like(s: str) -> bool:
    """Check if string looks like a ULID (26 chars, alphanumeric, uppercase)."""
    if len(s) != 26:
        return False
    return s.isalnum() and s.isupper()


# ---------------------------------------------------------------------------
# Convenience helpers for common patterns
# ---------------------------------------------------------------------------

def get_workflow_selector_from_entry_or_raise(entry: dict, context: str = "workflow") -> str:
    """
    Extract workflow selector from entry, raising error if not found.
    
    Args:
        entry: Workflow entry dict
        context: Context string for error message (e.g., "workflow", "parent workflow")
        
    Returns:
        Workflow selector string
        
    Raises:
        ValueError: If no valid selector found (indicates corrupt entry)
    """
    selector = extract_workflow_selector_from_entry(entry)
    if not selector:
        raise ValueError(
            f"Invalid {context} entry: missing workflow_id, id, or name. "
            f"This may indicate a corrupted project.qv.yml. Entry: {entry}"
        )
    return selector


def get_structure_selector_from_entry_or_raise(entry: dict, context: str = "structure") -> str:
    """
    Extract structure selector from entry, raising error if not found.
    
    Args:
        entry: Structure entry dict
        context: Context string for error message
        
    Returns:
        Structure selector string
        
    Raises:
        ValueError: If no valid selector found (indicates corrupt entry)
    """
    selector = extract_structure_selector_from_entry(entry)
    if not selector:
        raise ValueError(
            f"Invalid {context} entry: missing structure_id, id, or name. "
            f"This may indicate a corrupted project.qv.yml. Entry: {entry}"
        )
    return selector


def get_step_selector_from_entry_or_raise(entry: dict, context: str = "step") -> str:
    """
    Extract step selector from entry, raising error if not found.
    
    Args:
        entry: Step entry dict from workflow.yaml
        context: Context string for error message
        
    Returns:
        Step selector string (ULID)
        
    Raises:
        ValueError: If no valid selector found (indicates corrupt workflow.yaml)
    """
    selector = extract_step_selector_from_entry(entry)
    if not selector:
        raise ValueError(
            f"Invalid {context} entry: missing step_id or id. "
            f"This may indicate a corrupted workflow.yaml. Entry: {entry}"
        )
    return selector

