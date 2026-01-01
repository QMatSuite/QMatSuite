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


def save_yaml_doc(doc: YamlDoc, path: Path, *, skip_journal: bool = False) -> None:
    """
    Save Doc to YAML file.
    
    This is the SINGLE COMMIT POINT for all YAML changes.
    Journal is hooked here - no other place records changes.
    
    Args:
        doc: Document to save
        path: Path to save to
        skip_journal: If True, skip journal recording (for internal use)
        
    Journal Integration:
        - Captures before (snapshot) and after (current state)
        - Records entry with target ULID from meta.id
        - Infers doc_type from document structure
    """
    # Capture before/after for Journal
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
    
    # Write to disk
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

