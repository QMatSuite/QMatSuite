"""
Hash utilities for incremental run tracking.

Computes SHA256 hashes for:
- pseudo_set_sha: Combined hash of all pseudopotential files used in calculation
- structure_sha: Hash of structure JSON (meta stripped, floats normalized)
- step_sha: Hash of step YAML (meta stripped)
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from quantumvitas.core.public import compute_sha256_file

# Float comparison tolerance for canonicalization
FLOAT_TOLERANCE = 1e-10


def _set_nested(data: dict, path: str, value: Any) -> None:
    """
    Set value at dot-separated path in nested dict.
    
    Args:
        data: Dict to modify
        path: Dot-separated path (e.g., "parameters.SYSTEM.ecutwfc")
        value: Value to set
    """
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _resolve_scan_refs_in_dict(
    data: dict,
    variant_assignments: Dict[str, Any],  # param_path -> value
) -> dict:
    """
    Recursively resolve ScanRefs in a dict structure.
    
    Args:
        data: Dict to process
        variant_assignments: Mapping from param_path to concrete value
        
    Returns:
        New dict with ScanRefs replaced by concrete values
    """
    from quantumvitas.calculation.scan_validation import is_scan_ref
    from quantumvitas.calculation.scan_tokens import parse_scan_id
    
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if is_scan_ref(value):
                # This should not happen if we're using variant_assignments correctly
                # But handle it gracefully
                param_path = key  # This is incomplete - we need full path
                if param_path in variant_assignments:
                    result[key] = variant_assignments[param_path]
                else:
                    # Keep ScanRef if no assignment (shouldn't happen)
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = _resolve_scan_refs_in_dict(value, variant_assignments)
            elif isinstance(value, list):
                result[key] = [
                    _resolve_scan_refs_in_dict(item, variant_assignments)
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result
    elif isinstance(data, list):
        return [
            _resolve_scan_refs_in_dict(item, variant_assignments)
            if isinstance(item, dict)
            else item
            for item in data
        ]
    else:
        return data


def build_effective_engine_params_view(
    step_doc: Dict[str, Any],
    variant_assignments: Optional[Dict[str, Any]] = None,  # param_path -> value
) -> Dict[str, Any]:
    """
    Build effective engine params view by resolving ScanRefs to concrete values.
    
    Returns a dict suitable for feeding into existing compute_step_sha().
    - If variant_assignments provided: replaces @scan:X tokens with concrete values
    - Always removes parameter_scan section (not an engine parameter)
    - Preserves all other fields (parameters, cards, species_overrides, step_type, etc.)
    
    Args:
        step_doc: Step document dict
        variant_assignments: Optional mapping from param_path to concrete value
        
    Returns:
        Effective step document dict with ScanRefs resolved and parameter_scan removed
    """
    import copy
    
    # Deep copy to avoid mutating input
    effective = copy.deepcopy(step_doc)
    
    # Remove parameter_scan section (not an engine parameter)
    if "parameter_scan" in effective:
        del effective["parameter_scan"]
    
    # If variant_assignments provided, resolve ScanRefs
    if variant_assignments:
        # Apply assignments to the effective dict
        for param_path, value in variant_assignments.items():
            _set_nested(effective, param_path, value)
    
    return effective


def strip_resource_meta(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove meta/metadata keys from a dictionary.
    
    Strips keys like: meta, __qv_meta__, id, name, slug, path, kind, created_at, updated_at
    that are used for resource identification but not for physics equivalence.
    
    Args:
        obj: Dictionary potentially containing meta fields
        
    Returns:
        Copy of dictionary with meta fields removed
    """
    result = {}
    meta_keys = {"meta", "__qv_meta__", "id", "name", "slug", "path", "kind", "created_at", "updated_at"}
    
    for key, value in obj.items():
        if key in meta_keys:
            continue
        if isinstance(value, dict):
            result[key] = strip_resource_meta(value)
        elif isinstance(value, list):
            result[key] = [strip_resource_meta(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    
    return result


def canonicalize_float(value: float) -> float:
    """
    Canonicalize float to a stable representation.
    
    Rounds to nearest multiple of tolerance to handle floating-point precision issues.
    
    Args:
        value: Float value
        
    Returns:
        Canonicalized float
    """
    if math.isnan(value):
        return float('nan')
    if math.isinf(value):
        return value
    # Round to nearest multiple of tolerance
    return round(value / FLOAT_TOLERANCE) * FLOAT_TOLERANCE


def canonicalize(obj: Any) -> Any:
    """
    Canonicalize an object for stable hashing.
    
    - Sorts dict keys recursively
    - Normalizes floats with tolerance
    - Ensures consistent ordering
    
    Args:
        obj: Object to canonicalize
        
    Returns:
        Canonicalized object
    """
    if isinstance(obj, dict):
        # Sort keys and recursively canonicalize values
        return {k: canonicalize(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [canonicalize(item) for item in obj]
    elif isinstance(obj, float):
        return canonicalize_float(obj)
    elif isinstance(obj, (int, str, bool, type(None))):
        return obj
    else:
        # For unknown types, convert to string
        return str(obj)


def stable_serialize(obj: Any) -> bytes:
    """
    Serialize object to stable JSON bytes.
    
    Uses canonicalization and JSON serialization with sorted keys.
    
    Args:
        obj: Object to serialize
        
    Returns:
        UTF-8 encoded JSON bytes
    """
    canonical = canonicalize(obj)
    # Use ensure_ascii=False to preserve Unicode, but sort_keys=True for stability
    json_str = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return json_str.encode('utf-8')


def compute_structure_sha(structure_path: Path) -> str:
    """
    Compute SHA256 hash of structure JSON.
    
    Strips meta fields and normalizes floats for physics equivalence.
    
    Args:
        structure_path: Path to structure JSON file
        
    Returns:
        SHA256 hash as hex string (without "sha256:" prefix)
    """
    if not structure_path.exists():
        raise FileNotFoundError(f"Structure file not found: {structure_path}")
    
    data = json.loads(structure_path.read_text())
    
    # Extract structure data (strip meta)
    if "__qv_meta__" in data:
        structure_data = data.get("structure", data)
        # Remove meta from top level if present
        if isinstance(structure_data, dict):
            structure_data = {k: v for k, v in structure_data.items() if k != "__qv_meta__"}
    elif "meta" in data:
        structure_data = data.get("structure", data)
        if isinstance(structure_data, dict):
            structure_data = {k: v for k, v in structure_data.items() if k != "meta"}
    else:
        structure_data = data
    
    # Strip any remaining meta fields recursively
    structure_data = strip_resource_meta(structure_data)
    
    # Canonicalize and serialize
    serialized = stable_serialize(structure_data)
    
    # Compute hash
    return hashlib.sha256(serialized).hexdigest()


def compute_step_sha(
    step_doc: Union[Dict[str, Any], Path],
    variant_assignments: Optional[Dict[str, Any]] = None,  # param_path -> value
) -> str:
    """
    Compute SHA256 hash of step YAML.
    
    Strips meta fields for physics equivalence.
    For scan variants: resolves ScanRefs to concrete values before hashing.
    Always removes parameter_scan section (not an engine parameter).
    
    Args:
        step_doc: Step YAML as dict or Path to step YAML file
        variant_assignments: Optional mapping from param_path to concrete value
                           (for scan variants)
        
    Returns:
        SHA256 hash as hex string (without "sha256:" prefix)
    """
    if isinstance(step_doc, Path):
        if not step_doc.exists():
            raise FileNotFoundError(f"Step file not found: {step_doc}")
        from quantumvitas.core.public import StepDoc
        data = StepDoc.load(step_doc).to_dict()
    else:
        data = step_doc
    
    # Build effective view (resolves ScanRefs, removes parameter_scan)
    if variant_assignments is not None:
        effective_data = build_effective_engine_params_view(data, variant_assignments)
    else:
        # For non-scan runs, still remove parameter_scan if present
        effective_data = build_effective_engine_params_view(data, None)
    
    # Strip meta fields
    step_data = strip_resource_meta(effective_data)
    
    # Constitution §B: SHA MUST be computed on SPEC types (matching persisted YAML truth).
    # No normalization - step_type stays as-is (SPEC format, e.g., "qe_scf").
    # This ensures fingerprints match the actual persisted content.
    
    # Canonicalize and serialize
    serialized = stable_serialize(step_data)
    
    # Compute hash
    return hashlib.sha256(serialized).hexdigest()


def compute_pseudo_set_sha(
    project_pseudo_dir: Path,
    species_map: Dict[str, Dict[str, Any]],
) -> str:
    """
    Compute SHA256 hash of pseudopotential set from calc.yaml atomic records.
    
    This is the canonical function for computing pseudo_set_sha. It derives the hash
    from the atomic pseudo records in species_map (element -> {pseudo_sha256, ...}).
    
    Algorithm:
    - Extract (element, pseudo_sha256) pairs from species_map
    - Sort by element symbol
    - Create tokens: "element:sha256" (exclude filename and sha_family)
    - Join with '|' and compute SHA256
    
    Args:
        project_pseudo_dir: Directory containing pseudopotential files (unused, kept for API compatibility)
        species_map: Calculation species_map (element -> {pseudo_sha256, ...})
                   Must contain pseudo_sha256 for each element (atomic record from calc.yaml)
        
    Returns:
        SHA256 hash as hex string (without "sha256:" prefix)
        
    Note:
        This function does NOT read files from disk. It uses pseudo_sha256 from species_map
        (the atomic record stored in calc.yaml). This ensures SSOT: calc.yaml stores atomic
        records; pseudo_set_sha is derived and stored only in manifest.
    """
    tokens = []
    
    # Extract (element, pseudo_sha256) pairs from species_map
    # Sort by element symbol for canonical ordering
    for element, info in sorted(species_map.items()):
        if not isinstance(info, dict):
            continue
        
        # Get pseudo_sha256 from atomic record (SSOT: stored in calc.yaml)
        pseudo_sha256 = info.get("pseudo_sha256")
        
        if not pseudo_sha256:
            # Element has no pseudo_sha256 record, skip
            continue
        
        # Create token: "element:sha256" (exclude filename and sha_family)
        tokens.append(f"{element}:{pseudo_sha256}")
    
    # Join tokens and hash
    if not tokens:
        # No pseudo records, return hash of empty string
        return hashlib.sha256(b"").hexdigest()
    
    joined = "|".join(tokens)
    return hashlib.sha256(joined.encode('utf-8')).hexdigest()


def compute_potential_assets_sha(
    potential_map: Dict[str, Dict[str, Any]],
) -> str:
    """
    Compute SHA256 hash of potential assets from potential_map.
    
    For LAMMPS, this is analogous to compute_pseudo_set_sha for QE.
    The pseudo_set_sha field in manifest is reused for potential_assets_sha.
    
    Algorithm:
    - Extract (potential_key, potential_sha256) pairs from potential_map
    - Sort by potential_key
    - Create tokens: "key:sha256"
    - Join with '|' and compute SHA256
    
    Args:
        potential_map: Calculation potential_map (key -> {style, file, sha256, ...})
                      Must contain sha256 for each potential (atomic record from calc.yaml)
    
    Returns:
        SHA256 hash as hex string (without "sha256:" prefix)
    
    Note:
        This function does NOT read files from disk. It uses sha256 from potential_map
        (the atomic record stored in calc.yaml). This ensures SSOT: calc.yaml stores atomic
        records; potential_assets_sha is derived and stored only in manifest.
    """
    import hashlib
    
    tokens = []
    
    # Extract (potential_key, sha256) pairs from potential_map
    # Sort by key for canonical ordering
    for key, info in sorted(potential_map.items()):
        if not isinstance(info, dict):
            continue
        
        # Get sha256 from atomic record (SSOT: stored in calc.yaml)
        sha256 = info.get("sha256")
        
        if not sha256:
            # Potential has no sha256 record, skip
            continue
        
        # Create token: "key:sha256"
        tokens.append(f"{key}:{sha256}")
    
    # Join tokens and hash
    if not tokens:
        # No potential records, return hash of empty string
        return hashlib.sha256(b"").hexdigest()
    
    joined = "|".join(tokens)
    return hashlib.sha256(joined.encode('utf-8')).hexdigest()


def get_pseudo_refs_from_calc(calculation_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Extract pseudo references from calculation.yaml.
    
    Reads species_map from calculation.yaml to get pseudo info.
    
    Args:
        calculation_dir: Path to calculation directory
        
    Returns:
        species_map dict (element -> {pseudopot, mass, ...})
    """
    calc_yaml = calculation_dir / "calculation.yaml"
    if not calc_yaml.exists():
        return {}
    
    from quantumvitas.core.public import CalcDoc
    data = CalcDoc.load(calc_yaml).to_dict()
    calculation_section = data.get("calculation", {})
    species_map = calculation_section.get("species_map", {})
    
    return species_map

