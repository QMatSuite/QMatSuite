"""
Base DTO class and JSON serialization.

This module provides the base class for all DTOs and fail-closed JSON conversion.
"""

from __future__ import annotations

import math
from abc import ABC
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

# JsonValue type alias
JsonValue = None | bool | int | float | str | list | dict


def to_json_value(obj: Any) -> JsonValue:
    """
    Convert to JSON-friendly value. FAIL-CLOSED.

    Raises:
        TypeError: For unknown types (no str() fallback)
        ValueError: For nan/inf floats
    """
    if obj is None:
        return None
    if isinstance(obj, bool):  # Must be before int
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"Cannot serialize {obj} to JSON (nan/inf)")
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, tuple)):
        return [to_json_value(v) for v in obj]
    if isinstance(obj, dict):
        for k in obj.keys():
            if not isinstance(k, str):
                raise TypeError(f"Dict keys must be str, got {type(k).__name__}")
        return {k: to_json_value(v) for k, v in obj.items()}
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, '__fspath__'):
        return str(obj)
    if isinstance(obj, Enum):
        v = obj.value
        if not isinstance(v, str):
            raise TypeError(f"Enum value must be str, got {type(v).__name__}")
        return v
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return str(obj)
    # FAIL-CLOSED: No str() fallback
    raise TypeError(
        f"Cannot serialize {type(obj).__name__} to JSON. "
        f"Use reference pattern for large data."
    )


@dataclass
class BaseDTO(ABC):
    """
    Base class for all Data Transfer Objects.
    
    All DTOs must inherit from this class and implement to_dict().
    """
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert DTO to JSON-serializable dictionary.
        
        Uses fail-closed serialization via to_json_value().
        """
        result = {}
        for key, value in asdict(self).items():
            result[key] = to_json_value(value)
        return result
