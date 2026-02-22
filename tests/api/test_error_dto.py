"""
Test ErrorDTO structure.

Tests for the ErrorDTO dataclass structure.
"""

import pytest

from qmatsuite.api.types.error import ErrorDTO


def test_error_dto_required_fields():
    """ErrorDTO has all required fields."""
    err = ErrorDTO(
        type="NotFoundError",
        code="NOT_FOUND",
        message="Resource not found",
        retryable=False
    )
    
    assert err.type == "NotFoundError"
    assert err.code == "NOT_FOUND"
    assert err.message == "Resource not found"
    assert err.retryable is False


def test_error_dto_optional_fields():
    """ErrorDTO optional fields work correctly."""
    err = ErrorDTO(
        type="NotFoundError",
        code="NOT_FOUND",
        message="Resource not found",
        retryable=False,
        hint="Did you mean 'x'?",
        context={"selector": "x", "resource_type": "calculation"},
        cause={"origin": "kernel", "class": "CalculationNotFoundError"}
    )
    
    assert err.hint == "Did you mean 'x'?"
    assert err.context == {"selector": "x", "resource_type": "calculation"}
    assert err.cause == {"origin": "kernel", "class": "CalculationNotFoundError"}


def test_error_dto_to_dict():
    """ErrorDTO.to_dict() includes all fields."""
    err = ErrorDTO(
        type="NotFoundError",
        code="NOT_FOUND",
        message="Resource not found",
        retryable=False,
        context={"selector": "x"}
    )
    
    d = err.to_dict()
    
    assert d["type"] == "NotFoundError"
    assert d["code"] == "NOT_FOUND"
    assert d["message"] == "Resource not found"
    assert d["retryable"] is False
    assert d["context"] == {"selector": "x"}
    # Optional fields are omitted if None
    assert "hint" not in d or d["hint"] is None

