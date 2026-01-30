"""
Test DTO serialization (fail-closed).

Tests for the to_json_value() function and fail-closed behavior.
"""

import math
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

import pytest

from quantumvitas.api.types.base import to_json_value


def test_primitives_pass_through():
    """Primitives serialize correctly."""
    assert to_json_value(None) is None
    assert to_json_value(True) is True
    assert to_json_value(False) is False
    assert to_json_value(42) == 42
    assert to_json_value(3.14) == 3.14
    assert to_json_value("hello") == "hello"


def test_nan_raises_value_error():
    """NaN must raise ValueError."""
    with pytest.raises(ValueError, match="nan"):
        to_json_value(math.nan)


def test_inf_raises_value_error():
    """Infinity must raise ValueError."""
    with pytest.raises(ValueError, match="inf"):
        to_json_value(math.inf)
    with pytest.raises(ValueError, match="inf"):
        to_json_value(-math.inf)


def test_datetime_to_iso():
    """Datetime converts to ISO string."""
    dt = datetime(2026, 1, 23, 14, 30, 0)
    result = to_json_value(dt)
    assert result == "2026-01-23T14:30:00"


def test_date_to_iso():
    """Date converts to ISO string."""
    d = date(2026, 1, 23)
    result = to_json_value(d)
    assert result == "2026-01-23"


def test_uuid_to_string():
    """UUID converts to string."""
    u = UUID("12345678-1234-5678-1234-567812345678")
    result = to_json_value(u)
    assert result == "12345678-1234-5678-1234-567812345678"


def test_decimal_to_string():
    """Decimal converts to string."""
    d = Decimal("123.456")
    result = to_json_value(d)
    assert result == "123.456"


def test_enum_to_string():
    """Enum converts to string value."""
    class TestEnum(Enum):
        VALUE1 = "value1"
        VALUE2 = "value2"
    
    result = to_json_value(TestEnum.VALUE1)
    assert result == "value1"


def test_enum_non_string_value_raises():
    """Enum with non-string value raises TypeError."""
    class TestEnum(Enum):
        VALUE1 = 42
    
    with pytest.raises(TypeError, match="Enum value must be str"):
        to_json_value(TestEnum.VALUE1)


def test_path_to_string():
    """Path converts to string."""
    from pathlib import Path
    p = Path("/tmp/file.txt")
    result = to_json_value(p)
    assert result == "/tmp/file.txt"


def test_list_recursive():
    """Lists are recursively converted."""
    result = to_json_value([1, 2.5, "three", True, None])
    assert result == [1, 2.5, "three", True, None]


def test_tuple_recursive():
    """Tuples are converted to lists."""
    result = to_json_value((1, 2, 3))
    assert isinstance(result, list)
    assert result == [1, 2, 3]


def test_dict_recursive():
    """Dicts are recursively converted."""
    result = to_json_value({"a": 1, "b": 2.5, "c": "three"})
    assert result == {"a": 1, "b": 2.5, "c": "three"}


def test_dict_non_string_key_raises():
    """Dict with non-string key raises TypeError."""
    with pytest.raises(TypeError, match="Dict keys must be str"):
        to_json_value({1: "value"})


def test_fail_closed_on_numpy_array():
    """Numpy arrays must raise TypeError, not silently convert."""
    try:
        import numpy as np
        with pytest.raises(TypeError, match="Cannot serialize.*ndarray"):
            to_json_value(np.array([1, 2, 3]))
    except ImportError:
        pytest.skip("numpy not available")


def test_fail_closed_on_kernel_object():
    """Kernel objects must raise TypeError."""
    # Create a simple class that's not in the whitelist
    class KernelObject:
        pass
    
    with pytest.raises(TypeError, match="Cannot serialize.*KernelObject"):
        to_json_value(KernelObject())


def test_fail_closed_on_function():
    """Functions must raise TypeError."""
    def some_function():
        pass
    
    with pytest.raises(TypeError, match="Cannot serialize.*function"):
        to_json_value(some_function)


def test_nested_structures():
    """Nested lists and dicts work correctly."""
    data = {
        "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
        "steps": [
            {"step_ulid": "01HX7YPVK8DQNZPMJ4GHAB5678", "status": "completed"},
            {"step_ulid": "01HX7YPVK8DQNZPMJ4GHAB9012", "status": "pending"},
        ],
        "meta": {
            "created_at": datetime(2026, 1, 23, 10, 0, 0),
            "tags": ["test", "example"],
        }
    }
    result = to_json_value(data)
    assert result["calc_id"] == "01HX7YPVK8DQNZPMJ4GHAB1234"
    assert len(result["steps"]) == 2
    assert result["meta"]["created_at"] == "2026-01-23T10:00:00"
    assert result["meta"]["tags"] == ["test", "example"]

