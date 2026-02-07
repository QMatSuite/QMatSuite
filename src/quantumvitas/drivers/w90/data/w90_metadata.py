"""Wannier90 parameter metadata access layer.

Provides the central API for accessing W90 .win parameter metadata.
All access to w90_tags.json should go through this module.

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
W90_METADATA_LOAD_STATE: Dict[str, Any] = {
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
    W90_METADATA_LOAD_STATE["loaded_via"] = loaded_via
    W90_METADATA_LOAD_STATE["loaded_at"] = datetime.now(timezone.utc).isoformat()
    if path_abs is not None:
        W90_METADATA_LOAD_STATE["path_abs"] = path_abs
    if schema_version is not None:
        W90_METADATA_LOAD_STATE["schema_version"] = schema_version


def _load_raw_metadata() -> Dict[str, Any]:
    """Load the raw W90 tag metadata JSON file.

    Single entry point for JSON file access. Uses module-level caching.
    If ``QV_W90_METADATA_HOT_RELOAD=1`` is set, checks file mtime and
    reloads when the file has changed on disk.

    Returns:
        Raw JSON data as dict.

    Raises:
        FileNotFoundError: If the JSON file is missing.
        RuntimeError: If the JSON is invalid or schema version unsupported.
    """
    global _METADATA_CACHE, _METADATA_MTIME

    data_path = resources.files("quantumvitas.drivers.w90.data").joinpath(
        "w90_tags.json"
    )

    hot_reload = os.environ.get("QV_W90_METADATA_HOT_RELOAD", "").strip() == "1"

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
            "w90_tags.json is missing from quantumvitas.drivers.w90.data."
        ) from exc
    except json.JSONDecodeError as exc:
        _METADATA_CACHE = None
        _METADATA_MTIME = None
        raise RuntimeError(f"w90_tags.json is invalid JSON: {exc}") from exc

    schema_version = data.get("schema_version", 0)
    if schema_version not in (1,):
        _METADATA_CACHE = None
        _METADATA_MTIME = None
        raise RuntimeError(
            f"Unsupported schema version {schema_version} in w90_tags.json. "
            f"Expected version 1."
        )

    _METADATA_CACHE = data
    _update_load_state("disk", path_abs, schema_version)
    return _METADATA_CACHE


def safe_load_metadata() -> Dict[str, Any]:
    """Load W90 metadata for runtime use.

    Raises RuntimeError instead of FileNotFoundError for consistent
    error handling in runtime contexts.
    """
    try:
        return _load_raw_metadata()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"W90 tag metadata is not available: {exc}"
        ) from exc


def reload_metadata() -> None:
    """Clear the metadata cache, forcing reload on next access."""
    global _METADATA_CACHE, _METADATA_MTIME
    _METADATA_CACHE = None
    _METADATA_MTIME = None


def get_tag_info(tag_name: str) -> Optional[Dict[str, Any]]:
    """Look up a single W90 parameter by name (case-insensitive).

    Returns:
        Tag metadata dict, or None if not found.
    """
    data = safe_load_metadata()
    tags = data.get("tags", {})
    tag_lower = tag_name.lower()
    # Try exact match first, then lowercase
    if tag_lower in tags:
        return tags[tag_lower]
    # Fallback: scan keys case-insensitively
    for key, val in tags.items():
        if key.lower() == tag_lower:
            return val
    return None


def list_tags(category: Optional[str] = None) -> List[str]:
    """Return all tag names, optionally filtered by category.

    Args:
        category: If given, only return tags in this category.

    Returns:
        Sorted list of tag names.
    """
    data = safe_load_metadata()
    tags = data.get("tags", {})
    if category is None:
        return sorted(tags.keys())
    return sorted(
        name for name, meta in tags.items()
        if meta.get("category") == category
    )


def list_categories() -> List[str]:
    """Return all unique categories, sorted."""
    data = safe_load_metadata()
    tags = data.get("tags", {})
    cats = {meta.get("category") for meta in tags.values() if meta.get("category")}
    return sorted(cats)


def get_metadata_file_info() -> Dict[str, Any]:
    """Return metadata file path and schema version for debug."""
    try:
        data = safe_load_metadata()
        return {
            "metadata_path_abs": W90_METADATA_LOAD_STATE.get("path_abs"),
            "schema_version": data.get("schema_version"),
        }
    except Exception:
        return {"metadata_path_abs": None, "schema_version": None}


def validate_params(params: Dict[str, Any]) -> List[str]:
    """Return list of unknown parameter names from a params dict.

    Known tags (case-insensitive) are not included in the result.
    """
    data = safe_load_metadata()
    known = {name.lower() for name in data.get("tags", {})}
    return sorted(
        key for key in params
        if key.lower() not in known
    )


def get_tag_type(tag_name: str) -> Optional[str]:
    """Return the type string of a tag, or None if not found."""
    info = get_tag_info(tag_name)
    return info["type"] if info else None


def get_tag_default(tag_name: str) -> Optional[str]:
    """Return the default string of a tag, or None if not found."""
    info = get_tag_info(tag_name)
    return info.get("default") if info else None
