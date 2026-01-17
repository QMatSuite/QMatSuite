"""
Tests for parameter validation (Class A/B typing).
"""

import pytest

from quantumvitas.core.param_validation import (
    validate_and_parse,
    normalize_class_b_value,
    ValidationError,
)


class TestBoolParsing:
    """Test strict bool parsing for Class A keys."""
    
    def test_parse_bool_true_variants(self):
        """Accept various true representations."""
        assert validate_and_parse("SYSTEM", "noncolin", "true", "bool") is True
        assert validate_and_parse("SYSTEM", "noncolin", "True", "bool") is True
        assert validate_and_parse("SYSTEM", "noncolin", "1", "bool") is True
        assert validate_and_parse("SYSTEM", "noncolin", "yes", "bool") is True
        assert validate_and_parse("SYSTEM", "noncolin", "on", "bool") is True
    
    def test_parse_bool_false_variants(self):
        """Accept various false representations."""
        assert validate_and_parse("SYSTEM", "noncolin", "false", "bool") is False
        assert validate_and_parse("SYSTEM", "noncolin", "False", "bool") is False
        assert validate_and_parse("SYSTEM", "noncolin", "0", "bool") is False
        assert validate_and_parse("SYSTEM", "noncolin", "no", "bool") is False
        assert validate_and_parse("SYSTEM", "noncolin", "off", "bool") is False
    
    def test_parse_bool_rejects_dotted(self):
        """Reject .true./.false. strings (strict parsing)."""
        with pytest.raises(ValidationError, match="Invalid boolean"):
            validate_and_parse("SYSTEM", "noncolin", ".true.", "bool")
        with pytest.raises(ValidationError, match="Invalid boolean"):
            validate_and_parse("SYSTEM", "noncolin", ".false.", "bool")
    
    def test_parse_bool_rejects_invalid(self):
        """Reject invalid boolean strings."""
        with pytest.raises(ValidationError, match="Invalid boolean"):
            validate_and_parse("SYSTEM", "noncolin", "maybe", "bool")
        with pytest.raises(ValidationError, match="Invalid boolean"):
            validate_and_parse("SYSTEM", "noncolin", "2", "bool")


class TestIntParsing:
    """Test strict int parsing for Class A keys."""
    
    def test_parse_int_valid(self):
        """Accept valid integers."""
        assert validate_and_parse("SYSTEM", "nspin", "1", "int") == 1
        assert validate_and_parse("SYSTEM", "nspin", "2", "int") == 2
        assert validate_and_parse("SYSTEM", "nspin", "4", "int") == 4
        assert validate_and_parse("SYSTEM", "nspin", "0", "int") == 0
        assert validate_and_parse("SYSTEM", "nspin", "-1", "int") == -1
    
    def test_parse_int_rejects_float(self):
        """Reject float strings."""
        with pytest.raises(ValidationError, match="Invalid integer"):
            validate_and_parse("SYSTEM", "nspin", "1.5", "int")
        with pytest.raises(ValidationError, match="Invalid integer"):
            validate_and_parse("SYSTEM", "nspin", "1.0", "int")
    
    def test_parse_int_rejects_text(self):
        """Reject non-numeric strings."""
        with pytest.raises(ValidationError, match="Invalid integer"):
            validate_and_parse("SYSTEM", "nspin", "abc", "int")


class TestFloatParsing:
    """Test strict float parsing for Class A keys."""
    
    def test_parse_float_valid(self):
        """Accept valid floats."""
        assert validate_and_parse("SYSTEM", "ecutwfc", "50.0", "float") == 50.0
        assert validate_and_parse("SYSTEM", "ecutwfc", "1e-6", "float") == 1e-6
        assert validate_and_parse("ELECTRONS", "conv_thr", "1.0e-6", "float") == 1.0e-6
        assert validate_and_parse("SYSTEM", "ecutwfc", "50", "float") == 50.0  # int string → float
    
    def test_parse_float_rejects_text(self):
        """Reject non-numeric strings."""
        with pytest.raises(ValidationError, match="Invalid numeric"):
            validate_and_parse("SYSTEM", "ecutwfc", "abc", "float")


class TestStringParsing:
    """Test string parsing for Class A keys."""
    
    def test_parse_string_trimmed(self):
        """String values are trimmed but preserved."""
        assert validate_and_parse("SYSTEM", "occupations", "smearing", "str") == "smearing"
        assert validate_and_parse("SYSTEM", "occupations", "  smearing  ", "str") == "smearing"
        assert validate_and_parse("SYSTEM", "smearing", "gaussian", "str") == "gaussian"


class TestClassBNormalization:
    """Test Class B value normalization (trim only)."""
    
    def test_class_b_preserves_case(self):
        """Class B values preserve case."""
        assert normalize_class_b_value("MixedCase") == "MixedCase"
        assert normalize_class_b_value("Gaussian") == "Gaussian"
        assert normalize_class_b_value("TRUE") == "TRUE"
    
    def test_class_b_trims_whitespace(self):
        """Class B values are trimmed."""
        assert normalize_class_b_value("  value  ") == "value"
        assert normalize_class_b_value("\tvalue\n") == "value"
    
    def test_class_b_preserves_dot_true(self):
        """Class B can preserve .true. strings."""
        assert normalize_class_b_value(".true.") == ".true."
        assert normalize_class_b_value("  .true.  ") == ".true."

