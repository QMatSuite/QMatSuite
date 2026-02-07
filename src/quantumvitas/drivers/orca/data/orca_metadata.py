"""ORCA keyword metadata access layer.

Provides the central API for accessing ORCA keyword parameter metadata.
All access to orca_keywords.json should go through this module.

Mirrors the VASP vasp_metadata.py pattern: module-level cache, hot-reload,
importlib.resources-based loading. Stdlib only — no kernel imports.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional


# Module-level cache
_METADATA_CACHE: Optional[Dict[str, Any]] = None
_METADATA_MTIME: Optional[float] = None

# Load state tracking (debug/internal)
ORCA_METADATA_LOAD_STATE: Dict[str, Any] = {
    "loaded_via": "not_loaded",
    "loaded_at": None,
    "schema_version": None,
    "path_abs": None,
}


def _update_load_state(
    loaded_via: str,
    path_abs: Optional[str] = None,
    schema_version: Optional[int] = None,
) -> None:
    """Update the global load state tracker."""
    ORCA_METADATA_LOAD_STATE["loaded_via"] = loaded_via
    ORCA_METADATA_LOAD_STATE["loaded_at"] = datetime.now(timezone.utc).isoformat()
    if path_abs is not None:
        ORCA_METADATA_LOAD_STATE["path_abs"] = path_abs
    if schema_version is not None:
        ORCA_METADATA_LOAD_STATE["schema_version"] = schema_version


def _load_raw_metadata() -> Dict[str, Any]:
    """Load the raw ORCA keyword metadata JSON file.

    Single entry point for JSON file access. Uses module-level caching.
    If ``QV_ORCA_METADATA_HOT_RELOAD=1`` is set, checks file mtime and
    reloads when the file has changed on disk.

    Returns:
        Raw JSON data as dict.

    Raises:
        FileNotFoundError: If the JSON file is missing.
        RuntimeError: If the JSON is invalid or schema version unsupported.
    """
    global _METADATA_CACHE, _METADATA_MTIME

    data_path = resources.files("quantumvitas.drivers.orca.data").joinpath(
        "orca_keywords.json"
    )

    hot_reload = os.environ.get("QV_ORCA_METADATA_HOT_RELOAD", "").strip() == "1"

    # Resolve absolute path for load state
    path_abs: Optional[str] = None
    try:
        with resources.as_file(data_path) as path:
            path_obj = Path(path)
            if path_obj.exists():
                path_abs = str(path_obj.resolve())
    except Exception:
        pass

    # Hot-reload: check mtime
    if hot_reload:
        try:
            with resources.as_file(data_path) as path:
                path_obj = Path(path)
                if path_obj.exists():
                    current_mtime = path_obj.stat().st_mtime
                    if _METADATA_CACHE is not None and _METADATA_MTIME == current_mtime:
                        sv = _METADATA_CACHE.get("schema_version")
                        _update_load_state("cache", path_abs, sv)
                        return _METADATA_CACHE
                    _METADATA_MTIME = current_mtime
        except Exception:
            pass
    else:
        if _METADATA_CACHE is not None:
            sv = _METADATA_CACHE.get("schema_version")
            _update_load_state("cache", path_abs, sv)
            return _METADATA_CACHE

    # Load from disk
    try:
        with resources.as_file(data_path) as path:
            path_obj = Path(path)
            if _METADATA_MTIME is None and path_obj.exists():
                _METADATA_MTIME = path_obj.stat().st_mtime
            with open(path_obj, "r", encoding="utf-8") as fh:
                data = json.load(fh)
    except FileNotFoundError as exc:
        _METADATA_CACHE = None
        _METADATA_MTIME = None
        raise FileNotFoundError(
            "orca_keywords.json is missing from quantumvitas.drivers.orca.data."
        ) from exc
    except json.JSONDecodeError as exc:
        _METADATA_CACHE = None
        _METADATA_MTIME = None
        raise RuntimeError(f"orca_keywords.json is invalid JSON: {exc}") from exc

    schema_version = data.get("schema_version", 0)
    if schema_version not in (1,):
        _METADATA_CACHE = None
        _METADATA_MTIME = None
        raise RuntimeError(
            f"Unsupported schema version {schema_version} in orca_keywords.json. "
            f"Expected version 1."
        )

    _METADATA_CACHE = data
    _update_load_state("disk", path_abs, schema_version)
    return _METADATA_CACHE


def safe_load_metadata() -> Dict[str, Any]:
    """Load ORCA metadata for runtime use.

    Raises RuntimeError instead of FileNotFoundError for consistent
    error handling in runtime contexts.
    """
    try:
        return _load_raw_metadata()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"ORCA keyword metadata is not available: {exc}"
        ) from exc


def reload_metadata() -> None:
    """Clear the metadata cache, forcing reload on next access."""
    global _METADATA_CACHE, _METADATA_MTIME
    _METADATA_CACHE = None
    _METADATA_MTIME = None


def get_keyword_info(keyword: str) -> Optional[Dict[str, Any]]:
    """Look up a single keyword by name (case-insensitive).

    Returns:
        Keyword metadata dict, or None if not found.
    """
    data = safe_load_metadata()
    keywords = data.get("keywords", {})
    # Try exact match first, then uppercase
    keyword_upper = keyword.upper()
    return keywords.get(keyword_upper)


def get_block_info(block_name: str) -> Optional[Dict[str, Any]]:
    """Look up a block definition by name (case-insensitive).

    Returns:
        Block metadata dict, or None if not found.
    """
    data = safe_load_metadata()
    blocks = data.get("blocks", {})
    block_lower = block_name.lower()
    return blocks.get(block_lower)


def list_keywords(category: Optional[str] = None) -> List[str]:
    """Return all keyword names, optionally filtered by category.

    Args:
        category: If given, only return keywords in this category.

    Returns:
        Sorted list of keyword names.
    """
    data = safe_load_metadata()
    keywords = data.get("keywords", {})
    if category is None:
        return sorted(keywords.keys())
    return sorted(
        name for name, meta in keywords.items()
        if meta.get("category") == category
    )


def list_blocks() -> List[str]:
    """Return all block names, sorted."""
    data = safe_load_metadata()
    blocks = data.get("blocks", {})
    return sorted(blocks.keys())


def list_categories() -> List[str]:
    """Return all unique keyword categories, sorted."""
    data = safe_load_metadata()
    keywords = data.get("keywords", {})
    cats = {meta.get("category") for meta in keywords.values() if meta.get("category")}
    return sorted(cats)


def get_metadata_file_info() -> Dict[str, Any]:
    """Return metadata file path and schema version for debug."""
    try:
        data = safe_load_metadata()
        return {
            "metadata_path_abs": ORCA_METADATA_LOAD_STATE.get("path_abs"),
            "schema_version": data.get("schema_version"),
        }
    except Exception:
        return {"metadata_path_abs": None, "schema_version": None}


def validate_keywords(keywords: List[str]) -> List[str]:
    """Return list of unknown keywords from a list.

    Known keywords (case-insensitive) are not included in the result.
    """
    data = safe_load_metadata()
    known = {name.upper() for name in data.get("keywords", {})}
    return sorted(
        kw for kw in keywords
        if kw.upper() not in known
    )


def is_known_keyword(keyword: str) -> bool:
    """Check if a keyword is known (case-insensitive)."""
    return get_keyword_info(keyword) is not None


def is_known_block(block_name: str) -> bool:
    """Check if a block name is known (case-insensitive)."""
    return get_block_info(block_name) is not None


def get_block_parameter_info(block_name: str, param_name: str) -> Optional[Dict[str, Any]]:
    """Look up a parameter within a block.

    Args:
        block_name: Block name (e.g., "scf", "geom")
        param_name: Parameter name within the block

    Returns:
        Parameter metadata dict, or None if not found.
    """
    block_info = get_block_info(block_name)
    if block_info is None:
        return None
    params = block_info.get("parameters", {})
    return params.get(param_name)
