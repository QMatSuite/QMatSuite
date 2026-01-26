"""
Tests for update_step_params Class A/B typing behavior.
"""

import pytest
import yaml
from pathlib import Path

from quantumvitas.api import QVService, APIError
from quantumvitas.core.resources import generate_resource_id
from quantumvitas.core.yamldoc import StepDoc


class TestClassATyping:
    """Test Class A keys are stored with correct types."""
    
    def test_class_a_bool_stored_as_bool(self, tmp_path):
        """Test that Class A bool values are parsed and stored as Python bool."""
        from quantumvitas.ir.backends.qe.mapping import is_class_a_key, get_class_a_type
        from quantumvitas.core.param_validation import validate_and_parse
        
        # Simulate the patching logic
        section = "SYSTEM"
        key = "noncolin"
        raw_value = "true"
        
        assert is_class_a_key(section, key)
        expected_type = get_class_a_type(section, key)
        assert expected_type == "bool"
        
        parsed = validate_and_parse(section, key, raw_value, expected_type)
        assert parsed is True
        assert isinstance(parsed, bool)
    
    def test_class_a_int_stored_as_int(self, tmp_path):
        """Test that Class A int values are parsed and stored as Python int."""
        from quantumvitas.ir.backends.qe.mapping import is_class_a_key, get_class_a_type
        from quantumvitas.core.param_validation import validate_and_parse
        
        section = "SYSTEM"
        key = "nspin"
        raw_value = "2"
        
        assert is_class_a_key(section, key)
        expected_type = get_class_a_type(section, key)
        assert expected_type == "int"
        
        parsed = validate_and_parse(section, key, raw_value, expected_type)
        assert parsed == 2
        assert isinstance(parsed, int)
    
    def test_class_a_float_stored_as_float(self, tmp_path):
        """Test that Class A float values are parsed and stored as Python float."""
        from quantumvitas.ir.backends.qe.mapping import is_class_a_key, get_class_a_type
        from quantumvitas.core.param_validation import validate_and_parse
        
        section = "SYSTEM"
        key = "ecutwfc"
        raw_value = "50.0"
        
        assert is_class_a_key(section, key)
        expected_type = get_class_a_type(section, key)
        assert expected_type == "float"
        
        parsed = validate_and_parse(section, key, raw_value, expected_type)
        assert parsed == 50.0
        assert isinstance(parsed, float)


class TestClassBTyping:
    """Test Class B keys are stored as trimmed strings."""
    
    def test_class_b_stored_as_string(self, tmp_path):
        """Test that Class B keys are normalized (trim only)."""
        from quantumvitas.ir.backends.qe.mapping import is_class_a_key
        from quantumvitas.core.param_validation import normalize_class_b_value
        
        section = "SYSTEM"
        key = "unknown_param"
        
        assert not is_class_a_key(section, key)
        
        normalized = normalize_class_b_value("  some_value  ")
        assert normalized == "some_value"
        assert isinstance(normalized, str)
    
    def test_class_b_preserves_case(self, tmp_path):
        """Test that Class B values preserve case."""
        from quantumvitas.core.param_validation import normalize_class_b_value
        
        normalized = normalize_class_b_value("MixedCase")
        assert normalized == "MixedCase"
        
        normalized = normalize_class_b_value("  .true.  ")
        assert normalized == ".true."


class TestClassAValidation:
    """Test Class A validation errors."""
    
    def test_class_a_invalid_raises_error(self, tmp_path):
        """Invalid Class A value raises ValidationError."""
        from quantumvitas.ir.backends.qe.mapping import is_class_a_key, get_class_a_type
        from quantumvitas.core.param_validation import validate_and_parse, ValidationError
        
        section = "SYSTEM"
        key = "nspin"
        raw_value = "not_a_number"
        
        assert is_class_a_key(section, key)
        expected_type = get_class_a_type(section, key)
        
        with pytest.raises(ValidationError, match="Invalid integer"):
            validate_and_parse(section, key, raw_value, expected_type)

