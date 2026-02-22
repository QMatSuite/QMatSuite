"""
Test BaseDTO serialization.

Tests for the BaseDTO base class and JSON serialization.
"""

import json

import pytest

from qmatsuite.api.types.base import BaseDTO
from qmatsuite.api.types.error import ErrorDTO


def test_base_dto_to_dict():
    """BaseDTO.to_dict() returns a dictionary."""
    # Create a simple DTO instance
    dto = ErrorDTO(
        type="TestError",
        code="TEST_ERROR",
        message="Test message",
        retryable=False
    )
    
    result = dto.to_dict()
    
    assert isinstance(result, dict)
    assert result["type"] == "TestError"
    assert result["code"] == "TEST_ERROR"
    assert result["message"] == "Test message"
    assert result["retryable"] is False


def test_dto_json_serializable():
    """DTO.to_dict() is JSON-serializable."""
    dto = ErrorDTO(
        type="TestError",
        code="TEST_ERROR",
        message="Test message",
        retryable=False,
        hint="Test hint",
        context={"key": "value"}
    )
    
    # Should not raise
    json_str = json.dumps(dto.to_dict())
    assert isinstance(json_str, str)
    
    # Should be parseable
    parsed = json.loads(json_str)
    assert parsed["type"] == "TestError"

