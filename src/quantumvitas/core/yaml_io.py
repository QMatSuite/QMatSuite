"""
YAML IO utilities for YamlDoc abstraction.

This module provides centralized YAML loading/saving that:
- Returns YamlDoc instances instead of raw dicts
- Provides the single commit point for Journal integration
- Enforces that business logic uses Doc, not raw yaml.safe_load

Per docs/yamldoc_refactor_plan.md:
- Business logic should use load_yaml_doc/save_yaml_doc
- Direct yaml.safe_load/dump should only be in this module

Journal Integration:
- save_yaml_doc() is the ONLY place that records journal entries
- All YamlDoc.save() methods delegate to save_yaml_doc()
- See docs/journal_design.md for architecture details
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Type, TypeVar

import yaml

from quantumvitas.core.yamldoc import YamlDoc, StepDoc, CalcDoc, ProjectDoc


T = TypeVar("T", bound=YamlDoc)


def _load_yaml_raw(path: Path) -> dict:
    """
    Load raw YAML file content.
    
    This is the ONLY place in the codebase that should use yaml.safe_load
    for document loading. All other code should use load_yaml_doc().
    
    Args:
        path: Path to YAML file
        
    Returns:
        Raw dict from YAML
        
    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML is malformed
    """
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    
    content = path.read_text()
    data = yaml.safe_load(content)
    
    # Handle empty files
    if data is None:
        return {}
    
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a mapping at root: {path}")
    
    return data


def load_yaml_meta_subtree(path: Path) -> dict:
    """Load a YAML file and return ONLY the 'meta' subtree.

    Returns the dict under the 'meta' key. All other top-level keys
    are discarded. Uses _load_yaml_raw() internally.

    This is the ONLY YAML loader that the resources/resolution domain
    should call during index building and resolution.
    """
    data = _load_yaml_raw(path)
    return data.get("meta") or data.get("__qv_meta__") or {}


def load_json_meta_subtree(path: Path) -> dict:
    """Load a JSON file and return ONLY the meta subtree.

    Returns the dict under the '__qv_meta__' or 'meta' key.
    All other top-level keys are discarded.
    """
    import json
    data = json.loads(path.read_text())
    return data.get("__qv_meta__") or data.get("meta") or {}


def _save_yaml_raw(data: dict, path: Path) -> None:
    """
    Save raw dict to YAML file.
    
    This is the ONLY place in the codebase that should use yaml.safe_dump
    for document saving. All other code should use save_yaml_doc().
    
    Args:
        data: Dict to save
        path: Path to YAML file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)
    path.write_text(content)


def load_yaml_doc(
    path: Path,
    doc_type: Type[T] = YamlDoc,
    **kwargs,
) -> T:
    """
    Load YAML file as Doc.
    
    Business logic should use this instead of yaml.safe_load.
    
    Args:
        path: Path to YAML file
        doc_type: Document class to instantiate (YamlDoc, StepDoc, etc.)
        **kwargs: Additional arguments passed to doc_type constructor
        
    Returns:
        Document instance
        
    Example:
        # Generic YAML doc
        doc = load_yaml_doc(path)
        
        # Step doc with access control
        step = load_yaml_doc(path, StepDoc, access_control=True, owner="compiler")
        
        # Calculation doc
        calc = load_yaml_doc(calc_dir / "calculation.yaml", CalcDoc)
    """
    # Use type-specific load if available
    if hasattr(doc_type, "load") and doc_type is not YamlDoc:
        return doc_type.load(path, **kwargs)
    
    data = _load_yaml_raw(path)
    return doc_type(data, **kwargs)


def save_yaml_doc(
    doc: YamlDoc,
    path: Path,
    *,
    skip_journal: bool = False,
    skip_history: bool = False,
    actor: Optional[str] = None,
) -> None:
    """
    Save Doc to YAML file.
    
    This is the SINGLE COMMIT POINT for all YAML changes.
    Journal and Project History are hooked here - no other place records changes.
    
    Args:
        doc: Document to save
        path: Path to save to
        skip_journal: If True, skip journal recording (for internal use)
        skip_history: If True, skip project history recording
        actor: Actor for history event ("gui", "cli", "daemon", "system")
        
    Journal Integration:
        - Captures before (snapshot) and after (current state)
        - Records entry with target ULID from meta.ulid
        - Infers doc_type from document structure
        
    Project History Integration:
        - Records semantic edit events for project-scoped files
        - Computes structured diffs (not text diffs)
        - Stored in project/.history/events.jsonl
    """
    # Capture before/after for Journal and History
    before = doc.get_snapshot()
    after = doc.to_dict()
    
    # Resolve path for different doc types
    resolved_path = path
    if isinstance(doc, StepDoc):
        pass  # Step paths are already files
    elif isinstance(doc, CalcDoc) and path.is_dir():
        resolved_path = path / "calculation.yaml"
    elif isinstance(doc, ProjectDoc) and path.is_dir():
        resolved_path = path / "project.qv.yml"
    
    # Acquire edit lock for calculation/step YAML files
    calc_dir = None
    if isinstance(doc, (CalcDoc, StepDoc)):
        from quantumvitas.core.locking import find_calc_dir_from_path, calc_edit_lock
        calc_dir = find_calc_dir_from_path(resolved_path)
    
    # Write to disk with edit lock if applicable
    if calc_dir:
        with calc_edit_lock(calc_dir, fail_fast=False):
            _save_yaml_raw(after, resolved_path)
    else:
        _save_yaml_raw(after, resolved_path)
    
    # Update doc's snapshot
    doc.commit_changes()
    
    # Record in Journal (lazy import to avoid circular dependencies)
    if not skip_journal and before is not None:
        try:
            from quantumvitas.core.journal import (
                get_journal,
                JournalEntry,
                infer_doc_type,
                extract_target_ulid,
                generate_summary,
            )
            
            journal = get_journal()
            if journal.enabled:
                doc_type = infer_doc_type(after)
                target_ulid = extract_target_ulid(after)
                summary = generate_summary(doc_type, before, after)
                
                entry = JournalEntry.create(
                    target_ulid=target_ulid,
                    doc_type=doc_type,
                    before=before,
                    after=after,
                    summary=summary,
                    path=resolved_path,
                )
                journal.record_change(entry)
        except Exception:
            # Journal failures should not break saves
            # In production, consider logging this
            pass
    
    # Record in Project History (lazy import to avoid circular dependencies)
    if not skip_history and before is not None:
        try:
            _record_history_edit_event(
                resolved_path=resolved_path,
                before=before,
                after=after,
                actor=actor,
            )
        except Exception:
            # History failures should not break saves
            pass


def _record_history_edit_event(
    resolved_path: Path,
    before: dict,
    after: dict,
    actor: Optional[str] = None,
) -> None:
    """
    Record a semantic edit event in project history.
    
    Only records if we can determine the project root from the path.
    """
    from quantumvitas.history.events import (
        EditEvent,
        EditChange,
        EditOperation,
        compute_semantic_diff,
    )
    from quantumvitas.history.storage import ProjectHistory
    
    # Try to find project root by walking up from the file path
    project_root = _find_project_root(resolved_path)
    if project_root is None:
        return  # Not inside a project, skip history recording
    
    history = ProjectHistory(project_root)
    
    # Ensure baseline exists
    history.ensure_baseline()
    
    # Determine doc type and IDs
    doc_type = _infer_history_doc_type(after)
    project_ulid = _extract_project_ulid(project_root)
    calc_ulid = _extract_calc_ulid(after, resolved_path)
    step_ulid = _extract_step_ulid(after)
    
    # Compute semantic diff
    changes = compute_semantic_diff(before, after)
    
    # Skip if no changes
    if not changes:
        return
    
    # Generate summary
    summary = _generate_edit_summary(doc_type, changes)
    
    # Get relative path
    try:
        rel_path = str(resolved_path.relative_to(project_root))
    except ValueError:
        rel_path = str(resolved_path)
    
    # Create and append event
    event = EditEvent.create(
        project_ulid=project_ulid,
        calc_ulid=calc_ulid,
        step_ulid=step_ulid,
        doc_type=doc_type,
        doc_path=rel_path,
        changes=[c.__dict__ if hasattr(c, "__dict__") else c for c in changes],
        actor=actor,
        summary=summary,
    )
    
    history.append_event(event)


def _find_project_root(path: Path) -> Optional[Path]:
    """
    Find project root by walking up from path looking for project.qv.yml.
    """
    current = path.resolve()
    if current.is_file():
        current = current.parent
    
    while current != current.parent:  # Stop at filesystem root
        if (current / "project.qv.yml").exists():
            return current
        current = current.parent
    
    return None


def _infer_history_doc_type(data: dict) -> str:
    """Infer document type from data structure."""
    meta = data.get("meta", {})
    kind = meta.get("kind", "")
    
    if kind == "step":
        return "step"
    if kind == "calculation":
        return "calc"
    if kind == "project":
        return "project"
    if kind == "structure":
        return "structure"
    
    # Heuristics
    if "step_type_spec" in data or "parameters" in data:
        return "step"
    if "steps" in data or "structure_ulid" in data:
        return "calc"
    if "calculations" in data or "structures" in data:
        return "project"
    
    return "unknown"


def _extract_project_ulid(project_root: Path) -> str:
    """Extract project ULID from project.qv.yml."""
    try:
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        return config.get("project", {}).get("meta", {}).get("ulid", "")
    except Exception:
        return ""


def _extract_calc_ulid(data: dict, path: Path) -> Optional[str]:
    """Extract calculation ULID from data or path context."""
    # From data meta
    meta = data.get("meta", {})
    if meta.get("kind") == "calculation":
        return meta.get("ulid")
    
    # From step's parent calculation
    if meta.get("kind") == "step":
        # Try to find calculation.yaml in parent directories
        current = path.parent
        for _ in range(3):  # Max depth
            calc_yaml = current / "calculation.yaml"
            if calc_yaml.exists():
                try:
                    calc_data = _load_yaml_raw(calc_yaml)
                    return calc_data.get("meta", {}).get("ulid")
                except Exception:
                    pass
            current = current.parent
    
    return None


def _extract_step_ulid(data: dict) -> Optional[str]:
    """Extract step ID from data."""
    meta = data.get("meta", {})
    if meta.get("kind") == "step":
        return meta.get("ulid")
    return None


def _generate_edit_summary(doc_type: str, changes: list) -> str:
    """Generate human-readable summary of changes."""
    n_changes = len(changes)
    
    if n_changes == 0:
        return f"Saved {doc_type}"
    
    # Count operation types
    sets = sum(1 for c in changes if getattr(c, "op", c.get("op") if isinstance(c, dict) else None) == "set")
    deletes = sum(1 for c in changes if getattr(c, "op", c.get("op") if isinstance(c, dict) else None) == "delete")
    
    parts = []
    if sets:
        parts.append(f"+{sets}")
    if deletes:
        parts.append(f"-{deletes}")
    
    if parts:
        return f"Edited {doc_type} ({', '.join(parts)} changes)"
    return f"Edited {doc_type} ({n_changes} changes)"


# =============================================================================
# Convenience Functions for Specific Doc Types
# =============================================================================


def load_step_doc(
    path: Path,
    *,
    access_control: bool = False,
    owner: Optional[str] = None,
) -> StepDoc:
    """
    Load step document from YAML file.
    
    Args:
        path: Path to step YAML file
        access_control: Enable access control
        owner: Owner identity ("compiler", "detector", "user")
        
    Returns:
        StepDoc instance
    """
    return StepDoc.load(path, access_control=access_control, owner=owner)


def load_calc_doc(path: Path) -> CalcDoc:
    """
    Load calculation document from YAML file.
    
    Args:
        path: Path to calculation.yaml or calculation directory
        
    Returns:
        CalcDoc instance
    """
    return CalcDoc.load(path)


def load_project_doc(path: Path) -> ProjectDoc:
    """
    Load project document from YAML file.
    
    Args:
        path: Path to project.qv.yml or project directory
        
    Returns:
        ProjectDoc instance
    """
    return ProjectDoc.load(path)

