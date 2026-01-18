"""
Scan validation for parameter scan feature.

Validates ScanRef syntax and parameter_scan definitions in step.yaml.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class ScanRefNotFoundError(ValueError):
    """Raised when a ScanRef references a missing scan_id."""
    pass


class ScanRefValidationError(ValueError):
    """Raised when ScanRef format or location is invalid."""
    pass


def is_scan_ref(value: Any) -> bool:
    """
    Check if a value is a ScanRef dict.
    
    A ScanRef is a dict with exactly one key: "scan_ref".
    
    Args:
        value: Value to check
        
    Returns:
        True if value is a ScanRef dict, False otherwise
    """
    if not isinstance(value, dict):
        return False
    
    # Must have exactly one key: "scan_ref"
    if len(value) != 1:
        return False
    
    if "scan_ref" not in value:
        return False
    
    return True


def validate_scan_ref_format(value: dict) -> bool:
    """
    Validate ScanRef format.
    
    Checks:
    - Has exactly one key: "scan_ref"
    - scan_ref value is non-empty string matching ^[a-z0-9_]+$
    
    Args:
        value: Dict to validate
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ScanRefValidationError: If format is invalid
    """
    if not isinstance(value, dict):
        raise ScanRefValidationError(f"ScanRef must be a dict, got {type(value)}")
    
    # Must have exactly one key
    if len(value) != 1:
        raise ScanRefValidationError(
            f"ScanRef dict must have exactly one key 'scan_ref', got keys: {list(value.keys())}"
        )
    
    if "scan_ref" not in value:
        raise ScanRefValidationError(
            f"ScanRef dict must have key 'scan_ref', got keys: {list(value.keys())}"
        )
    
    scan_id = value["scan_ref"]
    if not isinstance(scan_id, str):
        raise ScanRefValidationError(
            f"ScanRef 'scan_ref' value must be a string, got {type(scan_id)}"
        )
    
    if not scan_id:
        raise ScanRefValidationError("ScanRef 'scan_ref' value must be non-empty")
    
    # Must match ^[a-z0-9_]+$
    if not re.match(r"^[a-z0-9_]+$", scan_id):
        raise ScanRefValidationError(
            f"ScanRef 'scan_ref' value must match ^[a-z0-9_]+$, got '{scan_id}'"
        )
    
    return True


def _is_leaf_value(value: Any) -> bool:
    """
    Check if value is a leaf (scalar or simple list).
    
    Leaf values are:
    - Scalar: int, float, str, bool, None
    - Simple list: list of scalars (int, float)
    
    Args:
        value: Value to check
        
    Returns:
        True if leaf, False otherwise
    """
    if isinstance(value, (int, float, str, bool, type(None))):
        return True
    
    if isinstance(value, list):
        # Simple list: all elements are scalars
        return all(isinstance(item, (int, float, str, bool, type(None))) for item in value)
    
    return False


def find_all_scan_refs(
    data: dict,
    base_path: str = "",
) -> List[Tuple[str, str]]:
    """
    Find all ScanRef occurrences in a dict structure.
    
    Returns list of (param_path, scan_id) tuples.
    Only finds ScanRefs at leaf positions (scalar or simple list).
    
    Args:
        data: Dict to search (typically step.yaml dict)
        base_path: Base path prefix for building full paths
        
    Returns:
        List of (param_path, scan_id) tuples
        
    Raises:
        ScanRefValidationError: If ScanRef found at non-leaf position
    """
    results: List[Tuple[str, str]] = []
    
    def traverse(obj: Any, path: str) -> None:
        """
        Recursively traverse dict/list structure.
        
        Args:
            obj: Current object to traverse
            path: Current path string
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                
                if is_scan_ref(value):
                    # Found ScanRef
                    # Check if it's at a valid leaf position
                    # Valid: parameters.SECTION.param or cards.CARD.leaf
                    # Invalid: parameters.SECTION (section itself is ScanRef)
                    path_parts = current_path.split(".")
                    if len(path_parts) >= 2:
                        # We're inside parameters or cards
                        if path_parts[0] in ("parameters", "cards") and len(path_parts) == 2:
                            # This is like "parameters.SYSTEM" - invalid, SYSTEM should be a dict
                            raise ScanRefValidationError(
                                f"ScanRef at non-leaf position: '{current_path}' is a section/card name, "
                                f"not a leaf parameter. ScanRefs can only appear at leaf positions "
                                f"(e.g., 'parameters.SYSTEM.ecutwfc', not 'parameters.SYSTEM')."
                            )
                    
                    # Validate format and extract scan_id
                    try:
                        validate_scan_ref_format(value)
                        scan_id = value["scan_ref"]
                        results.append((current_path, scan_id))
                    except ScanRefValidationError as e:
                        raise ScanRefValidationError(
                            f"Invalid ScanRef at path '{current_path}': {e}"
                        ) from e
                elif isinstance(value, dict):
                    # Nested dict - recurse
                    traverse(value, current_path)
                elif isinstance(value, list):
                    # List - check if it's a simple list (leaf) or complex
                    if _is_leaf_value(value):
                        # Simple list leaf - ScanRefs in lists not yet supported in MVP
                        # But structure is valid, so continue
                        pass
                    else:
                        # Complex list - recurse into elements
                        for i, item in enumerate(value):
                            traverse(item, f"{current_path}[{i}]")
                # else: scalar value - leaf, no ScanRef, continue
        elif isinstance(obj, list):
            # Top-level list - recurse into elements
            for i, item in enumerate(obj):
                traverse(item, f"{path}[{i}]" if path else f"[{i}]")
    
    traverse(data, base_path)
    return results


def validate_step_scan_refs(step_doc: dict) -> Tuple[List[str], List[str]]:
    """
    Validate ScanRefs and parameter_scan section in step document.
    
    Args:
        step_doc: Step document dict (from step.yaml)
        
    Returns:
        Tuple of (errors, warnings)
        - errors: List of error messages (hard errors that should block save/run)
        - warnings: List of warning messages (non-blocking)
        
    Raises:
        ScanRefNotFoundError: If dangling ScanRef found
        ScanRefValidationError: If ScanRef format or location invalid
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    # Get parameter_scan section
    parameter_scan = step_doc.get("parameter_scan", {})
    if not isinstance(parameter_scan, dict):
        errors.append("parameter_scan must be a mapping (dict)")
        return errors, warnings
    
    # Find all ScanRefs in parameters and cards
    scan_refs: List[Tuple[str, str]] = []
    
    # Check parameters section
    parameters = step_doc.get("parameters", {})
    if isinstance(parameters, dict):
        try:
            refs = find_all_scan_refs(parameters, "parameters")
            scan_refs.extend(refs)
        except ScanRefValidationError as e:
            errors.append(str(e))
            return errors, warnings
    
    # Check cards section
    cards = step_doc.get("cards", {})
    if isinstance(cards, dict):
        try:
            refs = find_all_scan_refs(cards, "cards")
            scan_refs.extend(refs)
        except ScanRefValidationError as e:
            errors.append(str(e))
            return errors, warnings
    
    # Validate each ScanRef
    defined_scan_ids = set(parameter_scan.keys())
    referenced_scan_ids = set()
    
    for param_path, scan_id in scan_refs:
        referenced_scan_ids.add(scan_id)
        
        # Check if scan_id is defined
        if scan_id not in defined_scan_ids:
            errors.append(
                f"ScanRef 'scan_ref: {scan_id}' references undefined scan_id '{scan_id}' "
                f"at path '{param_path}'. Defined scan_ids: {sorted(defined_scan_ids)}"
            )
    
    # Check for orphan scan definitions
    orphan_ids = defined_scan_ids - referenced_scan_ids
    if orphan_ids:
        warnings.append(
            f"Orphan scan definition(s) not referenced: {sorted(orphan_ids)}. Consider removing."
        )
    
    return errors, warnings

