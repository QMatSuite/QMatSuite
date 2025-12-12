"""
QE parameter metadata access layer.

This module provides the central API for accessing Quantum ESPRESSO parameter metadata.
All access to qe_module_parameters.json should go through this module.

The JSON file is the source of truth for:
- Module → namelist/section mappings
- Namelist → parameter name lists
- Documentation URLs

Other code should not directly open or parse qe_module_parameters.json.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional

# Module-level cache for metadata
_METADATA_CACHE: Optional[Dict[str, Any]] = None
_METADATA_MTIME: Optional[float] = None


@dataclass(frozen=True)
class QEUIParam:
    """UI-oriented parameter metadata."""
    namelist: str
    name: str
    label: str
    type: str  # 'number', 'text', 'select', etc.
    unit: Optional[str] = None
    description: Optional[str] = None
    options: Optional[List[str]] = None
    importance: Optional[str] = None  # 'core', 'advanced', etc.


@lru_cache(maxsize=1)
def _load_ui_parameters() -> Dict[str, Any]:
    """Load UI parameter metadata."""
    try:
        data_path = resources.files(__package__).joinpath("qe_ui_parameters.json")
        with resources.as_file(data_path) as path:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
    except FileNotFoundError:
        # UI parameters are optional; return empty dict if not present
        return {}


def _load_raw_metadata() -> Dict[str, Any]:
    """
    Load the raw QE parameter metadata JSON file.
    
    This is the single place that opens qe_module_parameters.json.
    All other functions should call this helper instead of opening the file directly.
    
    Uses module-level caching for performance. First call loads from disk and caches;
    subsequent calls return the cached data. If QV_QE_METADATA_HOT_RELOAD=1 is set,
    the function checks file mtime and reloads if the file has changed.
    
    Returns:
        Raw JSON data as dict.
        
    Raises:
        FileNotFoundError: If the JSON file is missing.
        RuntimeError: If the JSON file is invalid or schema version is unsupported.
    """
    global _METADATA_CACHE, _METADATA_MTIME
    
    # Get the file path
    data_path = resources.files(__package__).joinpath("qe_module_parameters.json")
    
    # Check if hot reload is enabled
    hot_reload = os.environ.get("QV_QE_METADATA_HOT_RELOAD", "").strip() == "1"
    
    # If hot reload is enabled, check if file has changed
    should_reload = False
    if hot_reload:
        try:
            with resources.as_file(data_path) as path:
                path_obj = Path(path)
                if path_obj.exists():
                    current_mtime = path_obj.stat().st_mtime
                    # If cache exists and mtime matches, use cache
                    if _METADATA_CACHE is not None and _METADATA_MTIME == current_mtime:
                        return _METADATA_CACHE
                    # Otherwise, mark for reload
                    should_reload = True
                    _METADATA_MTIME = current_mtime
                else:
                    # File doesn't exist - will be caught below
                    should_reload = True
        except Exception:
            # If checking mtime fails, fall back to normal loading
            should_reload = True
    else:
        # If hot reload is disabled and cache exists, return cached data
        if _METADATA_CACHE is not None:
            return _METADATA_CACHE
        should_reload = True
    
    # Load from disk if cache is empty or hot reload detected changes
    if should_reload or _METADATA_CACHE is None:
        try:
            with resources.as_file(data_path) as path:
                path_obj = Path(path)
                # Update mtime if not already set (for non-hot-reload case)
                if _METADATA_MTIME is None and path_obj.exists():
                    _METADATA_MTIME = path_obj.stat().st_mtime
                
                with open(path_obj, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
        except FileNotFoundError as exc:
            # Clear cache on file not found
            _METADATA_CACHE = None
            _METADATA_MTIME = None
            raise FileNotFoundError(
                "qe_module_parameters.json is missing; run "
                "`python tools/extract_qe_parameters_v3.py` to regenerate it."
            ) from exc
        except json.JSONDecodeError as exc:
            # Clear cache on JSON decode error
            _METADATA_CACHE = None
            _METADATA_MTIME = None
            raise RuntimeError(
                f"qe_module_parameters.json is invalid JSON: {exc}"
            ) from exc
        
        # Validate schema version
        schema_version = data.get("schema_version", 0)
        if schema_version not in (0, 1, 2, 3):
            # Clear cache on validation error
            _METADATA_CACHE = None
            _METADATA_MTIME = None
            raise RuntimeError(
                f"Unsupported schema version {schema_version} in qe_module_parameters.json. "
                f"Expected version 0, 1, 2, or 3."
            )
        
        # Cache the loaded data
        _METADATA_CACHE = data
    
    return _METADATA_CACHE


def safe_load_metadata() -> Dict[str, Any]:
    """
    Load QE metadata for runtime use.
    
    This is a wrapper around _load_raw_metadata() that raises RuntimeError
    instead of FileNotFoundError for better error handling in runtime contexts.
    
    Raises:
        RuntimeError: If metadata is missing, invalid, or has unsupported schema version.
        Never calls extraction scripts or remote URLs.
    """
    try:
        return _load_raw_metadata()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"QE parameter metadata is not available: {exc}. "
            f"This is required for QE-related operations. "
            f"Run `python tools/extract_qe_parameters_v4.py` to generate it."
        ) from exc


def reload_metadata() -> None:
    """
    Clear the QE parameter metadata cache so it will be reloaded on next access.
    
    This function clears both the in-memory cache and the mtime tracking,
    forcing the next call to _load_raw_metadata() or safe_load_metadata() to
    re-read the JSON file from disk.
    
    This is useful when the metadata file has been updated externally and
    you want to force a reload without restarting the daemon.
    """
    global _METADATA_CACHE, _METADATA_MTIME
    _METADATA_CACHE = None
    _METADATA_MTIME = None


def _load_qe_parameter_map() -> Dict[str, Any]:
    """
    Internal helper to load the JSON file, avoiding circular imports.
    
    DEPRECATED: Use _load_raw_metadata() or safe_load_metadata() instead.
    Kept for backward compatibility.
    """
    return _load_raw_metadata()


def _iter_params(module: str) -> List[Dict[str, Any]]:
    """
    Yield canonical parameter metadata items for a given module.
    
    This function abstracts over the schema version (v1 or v2).
    For v1 schema (sections → [names]):
        - Returns list of dicts with {"module": module, "namelist": section, "name": param_name}
          with other fields (type, default, enum, description) set to None.
    
    For v2 schema (parameters map):
        - Returns rich metadata objects with types, defaults, enums, descriptions (may be None).
    
    Args:
        module: QE module name (e.g., 'pw', 'ph')
        
    Returns:
        List of parameter metadata dicts.
        
    Raises:
        RuntimeError: If metadata is missing or invalid (via safe_load_metadata).
    """
    raw_data = safe_load_metadata()
    schema_version = raw_data.get("schema_version", 0)
    modules = raw_data.get("modules", {})
    module_entry = modules.get(module.lower())
    if not module_entry:
        return []
    
    result = []
    
    if schema_version == 0:
        # v0 schema: sections → [param names]
        sections = module_entry.get("sections", {})
        for section_name, param_names in sections.items():
            # Remove '&' prefix from section name to get namelist
            namelist = section_name[1:] if section_name.startswith("&") else section_name
            for param_name in param_names:
                result.append({
                    "module": module.lower(),
                    "namelist": namelist,
                    "name": param_name,
                    # v0 schema doesn't have these, set to None
                    "type": None,
                    "default": None,
                    "enum": None,
                    "description": None,
                })
    elif schema_version in (1, 2, 3):
        # v1/v2/v3 schema: parameters map (v2 adds optional status and see_also fields, v3 adds sections tree but parameters structure is the same)
        parameters = module_entry.get("parameters", {})
        for key, meta in parameters.items():
            namelist = meta.get("namelist")
            name = meta.get("name")
            if not namelist or not name:
                # Skip malformed entries
                continue
            # Remove '&' prefix from namelist if present (for consistency with v1)
            if namelist.startswith("&"):
                namelist = namelist[1:]
            result.append({
                "module": module.lower(),
                "namelist": namelist,
                "name": name,
                "type": meta.get("type"),
                "default": meta.get("default"),
                "enum": meta.get("enum"),
                "description": meta.get("description"),
            })
    else:
        # Unknown schema version
        raise ValueError(f"Unknown schema version: {schema_version}")
    
    return result


def get_module_param_sections(module: str) -> Dict[str, List[str]]:
    """
    Return mapping: section_name (e.g. 'CONTROL') -> list of parameter names.
    
    This function is derived from _iter_params() to ensure consistency
    even when the underlying schema changes (v1 → v2).
    
    Args:
        module: QE module name (e.g., 'pw', 'ph', 'dos')
        
    Returns:
        Dict mapping section names (with '&' prefix, e.g. '&CONTROL') to lists of parameter names.
        Returns empty dict if module is not found.
    """
    sections: Dict[str, List[str]] = {}
    for meta in _iter_params(module):
        namelist = meta.get("namelist")
        name = meta.get("name")
        if not namelist or not name:
            continue
        # Section name includes '&' prefix
        section_name = f"&{namelist.upper()}"
        sections.setdefault(section_name, []).append(name)
    # Sort parameter lists for consistency
    return {k: sorted(v) for k, v in sections.items()}


def get_module_card_sections(module: str) -> List[str]:
    """
    Return list of card section names for a given module.
    
    Cards are stored separately in card_metadata and don't have parameters
    in the same way as namelists. This function extracts card names.
    
    Args:
        module: QE module name (e.g., 'pw', 'ph', 'dos')
        
    Returns:
        List of card section names (e.g., ['K_POINTS', 'ATOMIC_SPECIES', ...]).
        Returns empty list if module is not found or has no cards.
        
    Raises:
        RuntimeError: If metadata is missing or invalid (via safe_load_metadata).
    """
    raw_data = safe_load_metadata()
    modules = raw_data.get("modules", {})
    module_entry = modules.get(module.lower())
    if not module_entry:
        return []
    
    card_metadata = module_entry.get("card_metadata", {})
    # Preserve JSON insertion order (Python 3.7+ dicts maintain insertion order)
    return list(card_metadata.keys())


def list_supported_modules() -> List[str]:
    """
    Return list of all supported QE module names.
    
    Returns:
        List of module names in JSON insertion order (e.g., ['pw', 'ph', 'dos', ...])
        
    Raises:
        RuntimeError: If metadata is missing or invalid.
    """
    raw_data = safe_load_metadata()
    modules = raw_data.get("modules", {})
    # Preserve JSON insertion order (Python 3.7+ dicts maintain insertion order)
    return list(modules.keys())


def get_module_doc_url(module: str) -> Optional[str]:
    """
    Return the documentation URL for a QE module.
    
    Args:
        module: QE module name (e.g., 'pw', 'ph')
        
    Returns:
        Documentation URL string, or None if module not found.
        
    Raises:
        RuntimeError: If metadata is missing or invalid.
    """
    raw_data = safe_load_metadata()
    modules = raw_data.get("modules", {})
    module_entry = modules.get(module.lower())
    if not module_entry:
        return None
    return module_entry.get("doc_url")


def get_doc_url_pattern() -> str:
    """
    Return the documentation URL pattern for QE modules.
    
    Returns:
        Pattern string like "https://www.quantum-espresso.org/Doc/INPUT_{name}.html"
        
    Raises:
        RuntimeError: If metadata is missing or invalid.
    """
    raw_data = safe_load_metadata()
    return raw_data.get("doc_pattern", "https://www.quantum-espresso.org/Doc/INPUT_{name}.html")


def get_module_namelists(module: str) -> List[str]:
    """
    Return list of namelist names for a QE module.
    
    This extracts namelist names from the section keys in the parameter map.
    
    Args:
        module: QE module name (e.g., 'pw', 'ph')
        
    Returns:
        List of namelist names (e.g., ['control', 'system', 'electrons'] for 'pw')
        
    Raises:
        RuntimeError: If metadata is missing or invalid (via get_module_param_sections).
    """
    sections = get_module_param_sections(module)
    # Extract namelist names from section keys (remove '&' prefix and convert to lowercase)
    namelists = []
    for section_name in sections.keys():
        if section_name.startswith("&"):
            namelist_name = section_name[1:].lower()
            if namelist_name not in namelists:
                namelists.append(namelist_name)
    return namelists


def get_ui_parameters(module: str, step_type: str) -> List[QEUIParam]:
    """
    Return a curated list of parameters for UI editing.
    
    Args:
        module: QE module name (e.g., 'pw')
        step_type: Step type (e.g., 'scf', 'nscf', 'dos', 'bands')
        
    Returns:
        List of QEUIParam objects with UI metadata.
        Returns empty list if no UI parameters are defined for this combination.
    """
    ui_data = _load_ui_parameters()
    module_entry = ui_data.get(module.lower(), {})
    step_params = module_entry.get(step_type.lower(), [])
    
    result = []
    for param_dict in step_params:
        try:
            param = QEUIParam(
                namelist=param_dict["namelist"],
                name=param_dict["name"],
                label=param_dict.get("label", param_dict["name"]),
                type=param_dict.get("type", "text"),
                unit=param_dict.get("unit"),
                description=param_dict.get("description"),
                options=param_dict.get("options"),
                importance=param_dict.get("importance"),
            )
            result.append(param)
        except KeyError as e:
            # Skip malformed entries, but log if needed
            continue
    
    return result


def validate_ui_parameters() -> List[str]:
    """
    Validate that all UI parameter names exist in qe_module_parameters.json.
    
    Returns:
        List of error messages. Empty list means all parameters are valid.
        
    Raises:
        RuntimeError: If metadata is missing or invalid.
    """
    errors = []
    ui_data = _load_ui_parameters()
    raw_data = safe_load_metadata()
    modules = raw_data.get("modules", {})
    
    for module_name, module_entry in ui_data.items():
        module_params = modules.get(module_name.lower())
        if not module_params:
            errors.append(f"Module '{module_name}' in UI parameters is not in qe_module_parameters.json")
            continue
        
        sections = module_params.get("sections", {})
        # Build a set of all valid parameter names for this module
        all_params = set()
        for section_params in sections.values():
            all_params.update(param.lower() for param in section_params)
        
        # Check each step type's parameters
        for step_type, step_params in module_entry.items():
            for param_dict in step_params:
                param_name = param_dict.get("name", "").lower()
                namelist = param_dict.get("namelist", "").upper()
                if not param_name:
                    continue
                
                # Check if parameter exists in the module's parameter list
                if param_name not in all_params:
                    errors.append(
                        f"Module '{module_name}', step '{step_type}': parameter '{param_dict.get('name')}' "
                        f"not found in qe_module_parameters.json"
                    )
                else:
                    # Verify it's in the claimed namelist
                    section_name = f"&{namelist}"
                    section_params_list = sections.get(section_name, [])
                    if param_dict.get("name") not in section_params_list:
                        errors.append(
                            f"Module '{module_name}', step '{step_type}': parameter '{param_dict.get('name')}' "
                            f"exists but not in namelist '{namelist}'"
                        )
    
    return errors
