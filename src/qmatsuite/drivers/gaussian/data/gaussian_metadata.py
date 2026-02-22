"""Gaussian route keyword metadata access layer.

Provides the central API for accessing Gaussian route keyword metadata.
All access to gaussian_route_keywords.json should go through this module.

Mirrors the VASP vasp_metadata.py pattern: module-level cache, hot-reload,
importlib.resources-based loading. Stdlib only -- no kernel imports.
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
GAUSSIAN_METADATA_LOAD_STATE: Dict[str, Any] = {
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
    GAUSSIAN_METADATA_LOAD_STATE["loaded_via"] = loaded_via
    GAUSSIAN_METADATA_LOAD_STATE["loaded_at"] = datetime.now(timezone.utc).isoformat()
    if path_abs is not None:
        GAUSSIAN_METADATA_LOAD_STATE["path_abs"] = path_abs
    if schema_version is not None:
        GAUSSIAN_METADATA_LOAD_STATE["schema_version"] = schema_version


def _load_raw_metadata() -> Dict[str, Any]:
    """Load the raw Gaussian route keyword metadata JSON file.

    Single entry point for JSON file access. Uses module-level caching.
    If ``QMS_GAUSSIAN_METADATA_HOT_RELOAD=1`` is set, checks file mtime
    and reloads when the file has changed on disk.

    Returns:
        Raw JSON data as dict.

    Raises:
        FileNotFoundError: If the JSON file is missing.
        RuntimeError: If the JSON is invalid or schema version unsupported.
    """
    global _METADATA_CACHE, _METADATA_MTIME

    data_path = resources.files("qmatsuite.drivers.gaussian.data").joinpath(
        "gaussian_route_keywords.json"
    )

    hot_reload = (
        os.environ.get("QMS_GAUSSIAN_METADATA_HOT_RELOAD", "").strip() == "1"
    )

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
                    if (
                        _METADATA_CACHE is not None
                        and _METADATA_MTIME == current_mtime
                    ):
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
            "gaussian_route_keywords.json is missing from "
            "qmatsuite.drivers.gaussian.data."
        ) from exc
    except json.JSONDecodeError as exc:
        _METADATA_CACHE = None
        _METADATA_MTIME = None
        raise RuntimeError(
            f"gaussian_route_keywords.json is invalid JSON: {exc}"
        ) from exc

    schema_version = data.get("schema_version", 0)
    if schema_version not in (1,):
        _METADATA_CACHE = None
        _METADATA_MTIME = None
        raise RuntimeError(
            f"Unsupported schema version {schema_version} in "
            f"gaussian_route_keywords.json. Expected version 1."
        )

    _METADATA_CACHE = data
    _update_load_state("disk", path_abs, schema_version)
    return _METADATA_CACHE


def safe_load_metadata() -> Dict[str, Any]:
    """Load Gaussian metadata for runtime use.

    Raises RuntimeError instead of FileNotFoundError for consistent
    error handling in runtime contexts.
    """
    try:
        return _load_raw_metadata()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Gaussian route keyword metadata is not available: {exc}"
        ) from exc


def reload_metadata() -> None:
    """Clear the metadata cache, forcing reload on next access."""
    global _METADATA_CACHE, _METADATA_MTIME
    _METADATA_CACHE = None
    _METADATA_MTIME = None


def get_keyword_info(keyword_name: str) -> Optional[Dict[str, Any]]:
    """Look up a single route keyword by name (case-insensitive).

    Returns:
        Keyword metadata dict, or None if not found.
    """
    data = safe_load_metadata()
    keywords = data.get("keywords", {})
    # Case-insensitive lookup: try exact, then upper-case keys
    kw_upper = keyword_name.upper()
    for name, info in keywords.items():
        if name.upper() == kw_upper:
            return info
        # Check aliases
        aliases = info.get("aliases", [])
        for alias in aliases:
            if alias.upper() == kw_upper:
                return info
    return None


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
        name
        for name, meta in keywords.items()
        if meta.get("category") == category
    )


def list_categories() -> List[str]:
    """Return all unique categories, sorted."""
    data = safe_load_metadata()
    keywords = data.get("keywords", {})
    cats = {
        meta.get("category")
        for meta in keywords.values()
        if meta.get("category")
    }
    return sorted(cats)


def list_builtin_basis_sets() -> List[str]:
    """Return list of built-in basis set names."""
    data = safe_load_metadata()
    return list(data.get("builtin_basis_sets", []))


def get_link0_info(directive: str) -> Optional[Dict[str, Any]]:
    """Look up a Link0 directive by name (case-insensitive).

    Args:
        directive: Link0 directive name (e.g., "%Mem", "Mem", "%Chk").

    Returns:
        Directive metadata dict, or None if not found.
    """
    data = safe_load_metadata()
    directives = data.get("link0_directives", {})
    # Normalize: strip leading % and do case-insensitive lookup
    key = directive.lstrip("%")
    for name, info in directives.items():
        if name.lstrip("%").upper() == key.upper():
            return info
    return None


def validate_route_keywords(route_keywords: List[str]) -> List[str]:
    """Return list of unknown keywords from a route keyword list.

    Known keywords (case-insensitive, including aliases) are excluded.
    Basis set names and method/basis combos (e.g., "B3LYP/6-31G*") are
    also excluded from the unknown list.
    """
    data = safe_load_metadata()
    keywords = data.get("keywords", {})
    basis_sets = {b.upper() for b in data.get("builtin_basis_sets", [])}

    # Build known set (keywords + aliases, all upper-cased)
    known: set[str] = set()
    for name, info in keywords.items():
        known.add(name.upper())
        for alias in info.get("aliases", []):
            known.add(alias.upper())

    unknown = []
    for kw in route_keywords:
        kw_upper = kw.upper()
        # Skip method/basis combos like "B3LYP/6-31G*"
        if "/" in kw:
            continue
        # Skip parenthetical options like "Opt=(Tight)"
        base = kw.split("(")[0].split("=")[0]
        if base.upper() in known:
            continue
        if kw_upper in basis_sets:
            continue
        # Strip R/U/RO method prefix
        for prefix in ("RO", "R", "U"):
            if base.upper().startswith(prefix) and base[len(prefix):].upper() in known:
                break
        else:
            unknown.append(kw)

    return unknown


def get_tag_type(name: str) -> Optional[str]:
    """Return the type string for a keyword (case-insensitive).

    Returns:
        Type string (e.g., "method", "keyword"), or None if not found.
    """
    info = get_keyword_info(name)
    if info is None:
        return None
    return info.get("type")


def get_tag_default(name: str) -> Optional[str]:
    """Return the default value for a keyword (case-insensitive).

    Returns:
        Default string, or None if not found or no default.
    """
    info = get_keyword_info(name)
    if info is None:
        return None
    return info.get("default")


def validate_params(params: Dict[str, Any]) -> List[str]:
    """Return unknown param names from a params dict.

    Alias for validate_route_keywords() that accepts a dict
    and validates the keys.
    """
    return validate_route_keywords(list(params.keys()))


def get_metadata_file_info() -> Dict[str, Any]:
    """Return metadata file path and schema version for debug."""
    try:
        data = safe_load_metadata()
        return {
            "metadata_path_abs": GAUSSIAN_METADATA_LOAD_STATE.get("path_abs"),
            "schema_version": data.get("schema_version"),
        }
    except Exception:
        return {"metadata_path_abs": None, "schema_version": None}
