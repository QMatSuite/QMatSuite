"""xTB metadata access layer.

Provides cached access to ``xtb_tags.json`` using stdlib-only imports.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any

_METADATA_CACHE: dict[str, Any] | None = None
_METADATA_MTIME: float | None = None

XTB_METADATA_LOAD_STATE: dict[str, Any] = {
    "loaded_via": "not_loaded",
    "loaded_at": None,
    "schema_version": None,
    "path_abs": None,
}


def _update_load_state(
    loaded_via: str,
    path_abs: str | None = None,
    schema_version: int | None = None,
) -> None:
    XTB_METADATA_LOAD_STATE["loaded_via"] = loaded_via
    XTB_METADATA_LOAD_STATE["loaded_at"] = datetime.now(timezone.utc).isoformat()
    if path_abs is not None:
        XTB_METADATA_LOAD_STATE["path_abs"] = path_abs
    if schema_version is not None:
        XTB_METADATA_LOAD_STATE["schema_version"] = schema_version


def _load_raw_metadata() -> dict[str, Any]:
    global _METADATA_CACHE, _METADATA_MTIME

    data_path = resources.files("quantumvitas.drivers.xtb.data").joinpath(
        "xtb_tags.json"
    )
    hot_reload = os.environ.get("QV_XTB_METADATA_HOT_RELOAD", "").strip() == "1"

    path_abs: str | None = None
    try:
        with resources.as_file(data_path) as path:
            path_obj = Path(path)
            if path_obj.exists():
                path_abs = str(path_obj.resolve())
    except Exception:
        pass

    if hot_reload:
        try:
            with resources.as_file(data_path) as path:
                path_obj = Path(path)
                if path_obj.exists():
                    current_mtime = path_obj.stat().st_mtime
                    if _METADATA_CACHE is not None and _METADATA_MTIME == current_mtime:
                        _update_load_state(
                            "cache", path_abs, _METADATA_CACHE.get("schema_version")
                        )
                        return _METADATA_CACHE
                    _METADATA_MTIME = current_mtime
        except Exception:
            pass
    else:
        if _METADATA_CACHE is not None:
            _update_load_state("cache", path_abs, _METADATA_CACHE.get("schema_version"))
            return _METADATA_CACHE

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
            "xtb_tags.json is missing from quantumvitas.drivers.xtb.data."
        ) from exc
    except json.JSONDecodeError as exc:
        _METADATA_CACHE = None
        _METADATA_MTIME = None
        raise RuntimeError(f"xtb_tags.json is invalid JSON: {exc}") from exc

    schema_version = data.get("schema_version", 0)
    if schema_version not in (1,):
        _METADATA_CACHE = None
        _METADATA_MTIME = None
        raise RuntimeError(
            f"Unsupported schema version {schema_version} in xtb_tags.json."
        )

    _METADATA_CACHE = data
    _update_load_state("disk", path_abs, schema_version)
    return _METADATA_CACHE


def safe_load_metadata() -> dict[str, Any]:
    try:
        return _load_raw_metadata()
    except FileNotFoundError as exc:
        raise RuntimeError(f"xTB metadata is not available: {exc}") from exc


def reload_metadata() -> None:
    global _METADATA_CACHE, _METADATA_MTIME
    _METADATA_CACHE = None
    _METADATA_MTIME = None


def get_tag_info(name: str) -> dict[str, Any] | None:
    data = safe_load_metadata()
    tags = data.get("tags", {})
    target = name.lower()
    for tag_name, info in tags.items():
        if tag_name.lower() == target:
            return info
    return None


def list_tags(category: str | None = None) -> list[str]:
    data = safe_load_metadata()
    tags = data.get("tags", {})
    if category is None:
        return sorted(tags)
    return sorted(
        name for name, info in tags.items() if info.get("category") == category
    )


def list_categories() -> list[str]:
    data = safe_load_metadata()
    tags = data.get("tags", {})
    return sorted({
        info.get("category") for info in tags.values() if info.get("category")
    })


def validate_params(params: dict[str, Any]) -> list[str]:
    data = safe_load_metadata()
    known = {k.lower() for k in data.get("tags", {})}
    return sorted(
        key
        for key in params
        if not key.startswith("_") and key.lower() not in known
    )


def get_tag_type(name: str) -> str | None:
    info = get_tag_info(name)
    return info.get("type") if info else None


def get_tag_default(name: str) -> Any:
    info = get_tag_info(name)
    return info.get("default") if info else None


def get_metadata_file_info() -> dict[str, Any]:
    try:
        data = safe_load_metadata()
        return {
            "metadata_path_abs": XTB_METADATA_LOAD_STATE.get("path_abs"),
            "schema_version": data.get("schema_version"),
        }
    except Exception:
        return {"metadata_path_abs": None, "schema_version": None}
