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

import yaml

from quantumvitas.core.pseudo_provenance import compute_sha256_file

# Float comparison tolerance for canonicalization
FLOAT_TOLERANCE = 1e-10


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


def compute_step_sha(step_doc: Union[Dict[str, Any], Path]) -> str:
    """
    Compute SHA256 hash of step YAML.
    
    Strips meta fields for physics equivalence.
    Normalizes step_type to public format for backward compatibility.
    
    Args:
        step_doc: Step YAML as dict or Path to step YAML file
        
    Returns:
        SHA256 hash as hex string (without "sha256:" prefix)
    """
    if isinstance(step_doc, Path):
        if not step_doc.exists():
            raise FileNotFoundError(f"Step file not found: {step_doc}")
        data = yaml.safe_load(step_doc.read_text()) or {}
    else:
        data = step_doc
    
    # Strip meta fields
    step_data = strip_resource_meta(data)
    
    # Normalize step_type to public format for backward compatibility
    # This ensures hashes match between machine types (qe_scf) and public types (scf)
    if "step_type" in step_data:
        from quantumvitas.workflow.registry import normalize_step_type_to_public
        step_data["step_type"] = normalize_step_type_to_public(step_data["step_type"])
    
    # Canonicalize and serialize
    serialized = stable_serialize(step_data)
    
    # Compute hash
    return hashlib.sha256(serialized).hexdigest()


def compute_pseudo_set_sha(
    project_pseudo_dir: Path,
    species_map: Dict[str, Dict[str, Any]],
) -> str:
    """
    Compute SHA256 hash of pseudopotential set.
    
    Creates canonical token per element: "ElementSymbol:file_sha"
    Sorts by element symbol and joins with '|', then computes SHA256.
    
    Args:
        project_pseudo_dir: Directory containing pseudopotential files
        species_map: Calculation species_map (element -> {pseudopot, mass, ...})
        
    Returns:
        SHA256 hash as hex string (without "sha256:" prefix)
    """
    if not project_pseudo_dir.exists():
        # No pseudo dir, return hash of empty string
        return hashlib.sha256(b"").hexdigest()
    
    tokens = []
    
    # Extract elements and pseudo filenames from species_map
    for element, info in sorted(species_map.items()):
        pseudo_filename = info.get("pseudopot") or info.get("pseudo_basename")
        if not pseudo_filename:
            # Element has no pseudo, skip
            continue
        
        # Find pseudo file
        pseudo_path = project_pseudo_dir / pseudo_filename
        if not pseudo_path.exists():
            # Pseudo file missing, include element but with empty hash
            tokens.append(f"{element}:")
            continue
        
        # Compute file SHA256
        file_sha = compute_sha256_file(pseudo_path)
        tokens.append(f"{element}:{file_sha}")
    
    # Join tokens and hash
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
    
    data = yaml.safe_load(calc_yaml.read_text()) or {}
    calculation_section = data.get("calculation", {})
    species_map = calculation_section.get("species_map", {})
    
    return species_map

