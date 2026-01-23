"""
ErrorDTO for structured API errors.

This module defines the ErrorDTO structure for API error responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quantumvitas.api.types.base import BaseDTO


@dataclass
class ErrorDTO(BaseDTO):
    """
    Structured error DTO for API boundary.
    
    All fields are stable and must not change without versioning.
    The `cause` field is debug-only and its structure is NOT stable.
    """
    # Required fields (stable contract)
    type: str           # Error class name
    code: str           # Stable error code
    message: str        # Human-readable message
    retryable: bool     # Whether retry may succeed
    
    # Optional fields
    hint: str | None = None
    context: dict[str, Any] | None = None
    
    # Debug-only (NOT stable)
    cause: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert ErrorDTO to JSON-serializable dictionary.
        
        Returns:
            Dictionary with all fields (None values are included)
        """
        result = {
            "type": self.type,
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        
        # Add optional fields if present
        if self.hint is not None:
            result["hint"] = self.hint
        if self.context is not None:
            result["context"] = self.context
        if self.cause is not None:
            result["cause"] = self.cause
        
        return result
