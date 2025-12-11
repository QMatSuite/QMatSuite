"""
Embedded data assets for QuantumVITAS.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any, Dict

# Re-export qe_metadata helpers for convenience
from .qe_metadata import (
    get_doc_url_pattern,
    get_module_doc_url,
    get_module_namelists,
    get_module_param_sections,
    get_ui_parameters,
    list_supported_modules,
    validate_ui_parameters,
    QEUIParam,
)

__all__ = [
    "load_qe_parameter_map",
    "get_module_param_sections",
    "get_module_doc_url",
    "get_doc_url_pattern",
    "get_module_namelists",
    "list_supported_modules",
    "get_ui_parameters",
    "validate_ui_parameters",
    "QEUIParam",
]


@lru_cache()
def load_qe_parameter_map() -> Dict[str, Any]:
    """
    Load the generated QE module parameter map.
    
    DEPRECATED: Most code should use the helper functions in qe_metadata.py instead
    of calling this directly. This function is kept for backward compatibility only.
    
    This now delegates to qe_metadata._load_raw_metadata() to ensure all access
    goes through the single source of truth.
    """
    from .qe_metadata import _load_raw_metadata
    return _load_raw_metadata()