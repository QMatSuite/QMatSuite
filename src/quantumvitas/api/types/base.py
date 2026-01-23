"""
Base DTO class and JSON serialization.

This module provides the base class for all DTOs and fail-closed JSON conversion.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import asdict, dataclass
from typing import Any

# JsonValue type alias (will be used in PR2)
JsonValue = None | bool | int | float | str | list | dict


@dataclass
class BaseDTO(ABC):
    """
    Base class for all Data Transfer Objects.
    
    All DTOs must inherit from this class and implement to_dict().
    """
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert DTO to JSON-serializable dictionary.
        
        This is a stub implementation for PR0.
        Full implementation with fail-closed serialization will be in PR2.
        """
        # Stub: use dataclass.asdict for now
        # PR2 will implement fail-closed to_json_value()
        return asdict(self)

