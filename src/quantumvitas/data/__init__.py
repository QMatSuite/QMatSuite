"""
Embedded data assets for QuantumVITAS.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any, Dict


@lru_cache()
def load_qe_parameter_map() -> Dict[str, Any]:
    """
    Load the generated QE module parameter map.
    """
    data_path = resources.files(__name__).joinpath("qe_module_parameters.json")
    try:
        with resources.as_file(data_path) as path:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "qe_module_parameters.json is missing; run "
            "`python tools/extract_qe_parameters.py` to regenerate it."
        ) from exc