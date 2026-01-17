"""
Parameter validation for Class A (strict-typed) keys.

Class A keys must be validated and parsed to their canonical types.
Class B keys are stored as trimmed strings without parsing.
"""

from typing import Any, Optional


class ValidationError(Exception):
    """Raised when a Class A parameter value fails validation."""
    pass


def validate_and_parse(
    section: str,
    key: str,
    raw_value: str,
    expected_type: str,
) -> Any:
    """
    Validate and parse a raw string value to its canonical type.
    
    Args:
        section: YAML section (e.g., "SYSTEM")
        key: Parameter key
        raw_value: Raw string from UI
        expected_type: 'bool', 'int', 'float', 'str'
        
    Returns:
        Parsed value with correct Python type
        
    Raises:
        ValidationError: If parsing fails
    """
    raw_value = raw_value.strip()
    
    if expected_type == "bool":
        return _parse_bool_strict(raw_value, section, key)
    elif expected_type == "int":
        return _parse_int_strict(raw_value, section, key)
    elif expected_type == "float":
        return _parse_float_strict(raw_value, section, key)
    elif expected_type == "str":
        return raw_value  # Already a string, just trimmed
    else:
        raise ValidationError(f"Unknown type '{expected_type}' for {section}.{key}")


def _parse_bool_strict(value: str, section: str, key: str) -> bool:
    """Parse bool strictly - no .true./.false. strings allowed."""
    v = value.lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off"):
        return False
    raise ValidationError(
        f"Invalid boolean value for {section}.{key}: '{value}'. "
        f"Use true/false, yes/no, or 1/0."
    )


def _parse_int_strict(value: str, section: str, key: str) -> int:
    """Parse int strictly."""
    try:
        return int(value)
    except ValueError:
        raise ValidationError(
            f"Invalid integer value for {section}.{key}: '{value}'. "
            f"Enter a whole number."
        )


def _parse_float_strict(value: str, section: str, key: str) -> float:
    """Parse float strictly."""
    try:
        return float(value)
    except ValueError:
        raise ValidationError(
            f"Invalid numeric value for {section}.{key}: '{value}'. "
            f"Enter a number."
        )


def normalize_class_b_value(value: str) -> str:
    """Normalize a Class B value: trim whitespace only."""
    return value.strip()

