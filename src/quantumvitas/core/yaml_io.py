"""
YAML IO utilities for YamlDoc abstraction.

This module provides centralized YAML loading/saving that:
- Returns YamlDoc instances instead of raw dicts
- Provides the single commit point for Journal integration
- Enforces that business logic uses Doc, not raw yaml.safe_load

Per docs/yamldoc_refactor_plan.md:
- Business logic should use load_yaml_doc/save_yaml_doc
- Direct yaml.safe_load/dump should only be in this module
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


def save_yaml_doc(doc: YamlDoc, path: Path) -> None:
    """
    Save Doc to YAML file.
    
    This is the single commit point for all YAML changes.
    Journal integration hooks here.
    
    Args:
        doc: Document to save
        path: Path to save to
        
    Journal Integration Point:
        Future implementation will add:
        ```
        journal.record_change(
            path=path,
            before=doc.get_snapshot(),
            after=doc.to_dict(),
        )
        ```
    """
    # Use type-specific save if available
    if hasattr(doc, "save"):
        doc.save(path)
        return
    
    _save_yaml_raw(doc.to_dict(), path)
    doc.commit_changes()


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

