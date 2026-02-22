"""
Scan expansion: variant generation and variant_key computation.

This module handles:
- Collecting scan dimensions from job steps
- Expanding variants via Cartesian product
- Computing deterministic variant_key for each variant
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List

from qmatsuite.calculation.public import find_all_scan_refs, is_scan_ref, parse_scan_id


@dataclass
class ScanDimension:
    """A single scan dimension (one parameter being scanned)."""
    
    step_ulid: str
    step_index: int  # Index of step in job's step_ulids list
    param_path: str  # Runtime-only deterministic path (e.g., "parameters.SYSTEM.ecutwfc")
    scan_id: str  # scan_id from parameter_scan section
    values: List[Any]  # List of values to scan over


@dataclass
class VariantAssignment:
    """A single parameter assignment for a variant."""
    
    step_ulid: str
    step_index: int
    param_path: str
    value: Any  # Concrete value for this variant


def _build_param_path(prefix: str, key: str) -> str:
    """Build a deterministic param_path from prefix and key."""
    if prefix:
        return f"{prefix}.{key}"
    return key


def _traverse_and_collect_scan_refs(
    data: dict,
    step_ulid: str,
    step_index: int,
    base_path: str = "",
    parameter_scan: Dict[str, Dict[str, Any]] = None,
) -> List[ScanDimension]:
    """
    Traverse step data and collect all ScanRefs as ScanDimensions.
    
    Args:
        data: Step document dict (parameters or cards section)
        step_ulid: ULID of the step
        step_index: Index of step in job's step_ulids list
        base_path: Base path prefix (e.g., "parameters" or "cards")
        parameter_scan: parameter_scan section from step.yaml
        
    Returns:
        List of ScanDimensions found in this data
    """
    dimensions: List[ScanDimension] = []
    
    if parameter_scan is None:
        parameter_scan = {}
    
    def traverse(obj: Any, path: str) -> None:
        """Recursively traverse dict/list structure."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = _build_param_path(path, key)
                
                if is_scan_ref(value):
                    # Found scan token - extract scan_id and get values
                    scan_id = parse_scan_id(value)
                    if scan_id in parameter_scan:
                        scan_def = parameter_scan[scan_id]
                        values = scan_def.get("values", [])
                        
                        dimension = ScanDimension(
                            step_ulid=step_ulid,
                            step_index=step_index,
                            param_path=current_path,
                            scan_id=scan_id,
                            values=values,
                        )
                        dimensions.append(dimension)
                elif isinstance(value, dict):
                    # Nested dict - recurse
                    traverse(value, current_path)
                elif isinstance(value, list):
                    # List - check if it's a simple list (leaf) or complex
                    # For now, ScanRefs in lists are not supported in MVP
                    # But we still traverse complex lists
                    if not all(isinstance(item, (int, float, str, bool, type(None))) for item in value):
                        # Complex list - recurse into elements
                        for i, item in enumerate(value):
                            traverse(item, f"{current_path}[{i}]")
        elif isinstance(obj, list):
            # Top-level list - recurse into elements
            for i, item in enumerate(obj):
                traverse(item, f"{path}[{i}]" if path else f"[{i}]")
    
    traverse(data, base_path)
    return dimensions


def collect_scan_dimensions(
    step_ulids: List[str],  # Ordered list of step ULIDs in job
    step_docs: Dict[str, dict],  # step_ulid -> step.yaml dict
) -> List[ScanDimension]:
    """
    Collect all scan dimensions from a job's steps.
    
    Args:
        step_ulids: Ordered list of step ULIDs in the job
        step_docs: Mapping from step ULID to step document dict
        
    Returns:
        List of ScanDimensions, sorted by (step_index, param_path) for deterministic ordering
    """
    all_dimensions: List[ScanDimension] = []
    
    for step_index, step_ulid in enumerate(step_ulids):
        step_doc = step_docs.get(step_ulid)
        if step_doc is None:
            continue
        
        parameter_scan = step_doc.get("parameter_scan", {})
        
        # Collect from parameters section
        parameters = step_doc.get("parameters", {})
        if isinstance(parameters, dict):
            dims = _traverse_and_collect_scan_refs(
                parameters,
                step_ulid,
                step_index,
                base_path="parameters",
                parameter_scan=parameter_scan,
            )
            all_dimensions.extend(dims)
        
        # Collect from cards section
        cards = step_doc.get("cards", {})
        if isinstance(cards, dict):
            dims = _traverse_and_collect_scan_refs(
                cards,
                step_ulid,
                step_index,
                base_path="cards",
                parameter_scan=parameter_scan,
            )
            all_dimensions.extend(dims)
    
    # Sort by (step_index, param_path) for deterministic ordering
    all_dimensions.sort(key=lambda d: (d.step_index, d.param_path))
    
    return all_dimensions


def canonicalize_value(v: Any) -> str:
    """
    Canonicalize a value for variant_key computation.
    
    - Floats: use repr() for precision
    - Ints: use str()
    - Lists: JSON serialization
    - Other: JSON serialization
    
    Args:
        v: Value to canonicalize
        
    Returns:
        Canonical string representation
    """
    if isinstance(v, float):
        return repr(v)
    elif isinstance(v, int):
        return str(v)
    elif isinstance(v, (list, dict)):
        # Use JSON with sorted keys and no whitespace
        return json.dumps(v, sort_keys=True, separators=(",", ":"))
    else:
        # For strings, bools, None, etc., use JSON
        return json.dumps(v, sort_keys=True, separators=(",", ":"))


def expand_variants(dimensions: List[ScanDimension]) -> List[List[VariantAssignment]]:
    """
    Expand scan dimensions into variants via Cartesian product.
    
    Ordering: later-step scan dims vary faster (inner loops).
    Within a step, dimensions are ordered by param_path.
    
    Example: step 0 has [10, 20], step 1 has [1, 2]
    Result: (10,1), (10,2), (20,1), (20,2)
    Step 0 varies slower (outer loop), step 1 varies faster (inner loop).
    
    Args:
        dimensions: List of ScanDimensions
        
    Returns:
        List of variant assignments (one list per variant)
    """
    if not dimensions:
        return []
    
    # Group dimensions by step_index
    by_step: Dict[int, List[ScanDimension]] = {}
    for dim in dimensions:
        if dim.step_index not in by_step:
            by_step[dim.step_index] = []
        by_step[dim.step_index].append(dim)
    
    # Sort step indices (earlier steps first)
    step_indices = sorted(by_step.keys())
    
    # Build variant list: later steps vary faster
    # Process steps in order (earlier first = outer loops)
    variants: List[List[VariantAssignment]] = [[]]
    
    from itertools import product
    
    for step_index in step_indices:
        step_dims = by_step[step_index]
        # Sort dimensions within step by param_path for determinism
        step_dims.sort(key=lambda d: d.param_path)
        
        # Build Cartesian product of all dimensions in this step
        new_variants: List[List[VariantAssignment]] = []
        
        for variant_prefix in variants:
            # Build all combinations of values for dimensions in this step
            dim_value_lists = [dim.values for dim in step_dims]
            
            # Generate Cartesian product of values within this step
            for value_combo in product(*dim_value_lists):
                new_variant = list(variant_prefix)
                for dim, value in zip(step_dims, value_combo):
                    assignment = VariantAssignment(
                        step_ulid=dim.step_ulid,
                        step_index=dim.step_index,
                        param_path=dim.param_path,
                        value=value,
                    )
                    new_variant.append(assignment)
                new_variants.append(new_variant)
        
        variants = new_variants
    
    # Sort each variant's assignments by (step_index, param_path) for consistency
    for variant in variants:
        variant.sort(key=lambda a: (a.step_index, a.param_path))
    
    return variants


def compute_variant_key(assignments: List[VariantAssignment]) -> str:
    """
    Compute a deterministic variant_key from assignments.
    
    Args:
        assignments: List of VariantAssignments for this variant
        
    Returns:
        Variant key as "scan_" + 16 hex chars
    """
    # Build assignment list: (step_ulid, param_path, canonical_value)
    assignment_data = []
    for assignment in sorted(assignments, key=lambda a: (a.step_index, a.param_path)):
        canonical_val = canonicalize_value(assignment.value)
        assignment_data.append({
            "step_ulid": assignment.step_ulid,
            "param_path": assignment.param_path,
            "value": canonical_val,
        })
    
    # Serialize to canonical JSON (sorted keys, no whitespace)
    serialized = json.dumps(assignment_data, sort_keys=True, separators=(",", ":"))
    
    # Compute SHA256
    sha256_hash = hashlib.sha256(serialized.encode()).hexdigest()
    
    # Return "scan_" + first 16 hex chars
    return f"scan_{sha256_hash[:16]}"

