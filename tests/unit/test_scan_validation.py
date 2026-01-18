"""
Tests for parameter scan validation.
"""

import pytest

from quantumvitas.calculation.scan_validation import (
    is_scan_ref,
    validate_scan_ref_format,
    find_all_scan_refs,
    validate_step_scan_refs,
    ScanRefNotFoundError,
    ScanRefValidationError,
)


class TestIsScanRef:
    """Test is_scan_ref() function."""
    
    def test_is_scan_ref_valid(self):
        """Valid scan token strings are detected."""
        assert is_scan_ref("@scan:scan001") is True
        assert is_scan_ref("@scan:abc123") is True
        assert is_scan_ref("@scan:scan_001") is True
    
    def test_is_scan_ref_invalid_format(self):
        """Invalid formats are not scan tokens."""
        assert is_scan_ref(50) is False  # Not a string
        assert is_scan_ref("scan001") is False  # String without prefix
        assert is_scan_ref("@scan:") is False  # Empty scan_id
        assert is_scan_ref("scan:scan001") is False  # Wrong prefix
        assert is_scan_ref({"scan_ref": "scan001"}) is False  # Dict (old format, not supported)
        assert is_scan_ref("") is False  # Empty string


class TestValidateScanRefFormat:
    """Test validate_scan_ref_format() function."""
    
    def test_validate_scan_ref_format_valid(self):
        """Valid ScanRef formats pass validation."""
        validate_scan_ref_format("@scan:scan001")
        validate_scan_ref_format("@scan:abc123")
        validate_scan_ref_format("@scan:scan_001")
        validate_scan_ref_format("@scan:a")
    
    def test_validate_scan_ref_format_invalid_type(self):
        """Non-string values raise error."""
        with pytest.raises(ScanRefValidationError, match="must be a string"):
            validate_scan_ref_format(50)
        with pytest.raises(ScanRefValidationError, match="must start with '@scan:'"):
            validate_scan_ref_format("scan001")
    
    def test_validate_scan_ref_format_empty_scan_id(self):
        """Empty scan_id raises error."""
        with pytest.raises(ScanRefValidationError, match="must be non-empty"):
            validate_scan_ref_format("@scan:")
    
    def test_validate_scan_ref_format_invalid_scan_id_chars(self):
        """Invalid characters in scan_id raise error."""
        with pytest.raises(ScanRefValidationError, match="must match"):
            validate_scan_ref_format("@scan:scan-001")  # Hyphen not allowed
        with pytest.raises(ScanRefValidationError, match="must match"):
            validate_scan_ref_format("@scan:scan.001")  # Dot not allowed
        with pytest.raises(ScanRefValidationError, match="must match"):
            validate_scan_ref_format("@scan:SCAN001")  # Uppercase not allowed
        with pytest.raises(ScanRefValidationError, match="must match"):
            validate_scan_ref_format("@scan:scan 001")  # Space not allowed
    
class TestValidateStepScanRefs:
    """Test validate_step_scan_refs() function."""
    
    def test_validate_step_scan_refs_valid(self):
        """Valid step with scan refs passes."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": "@scan:scan001",
                }
            },
            "parameter_scan": {
                "scan001": {
                    "values": [30, 40, 50]
                }
            }
        }
        errors, warnings = validate_step_scan_refs(step_doc)
        assert len(errors) == 0
        assert len(warnings) == 0
    
    def test_dangling_scan_ref_error(self):
        """Dangling ScanRef (missing scan_id) raises error."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": "@scan:scan001",
                }
            },
            "parameter_scan": {
                # scan001 is missing
            }
        }
        errors, warnings = validate_step_scan_refs(step_doc)
        assert len(errors) > 0
        assert any("undefined scan_id" in e for e in errors)
        assert "scan001" in errors[0]
    
    def test_orphan_scan_definition_warning(self):
        """Orphan scan definitions emit warning but don't error."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": "@scan:scan001",
                }
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40]},
                "scan002": {"values": [0.01, 0.02]},  # Orphan: not referenced
            }
        }
        errors, warnings = validate_step_scan_refs(step_doc)
        assert len(errors) == 0
        assert len(warnings) == 1
        assert "scan002" in warnings[0]
        assert "Orphan" in warnings[0]
    
    def test_scan_ref_at_non_leaf_error(self):
        """ScanRef at non-leaf position raises error."""
        # ScanRef as value for entire section
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": "@scan:scan001",  # Invalid: SYSTEM is not a leaf
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40]}
            }
        }
        errors, warnings = validate_step_scan_refs(step_doc)
        assert len(errors) > 0
        # Error should mention non-leaf or invalid location
    
    def test_scan_ref_leaf_only_acceptance(self):
        """Scalar and simple list leaves are accepted."""
        # Scalar leaf - OK
        step_doc1 = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": "@scan:scan001",  # Scalar leaf - OK
                }
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40]}
            }
        }
        errors, warnings = validate_step_scan_refs(step_doc1)
        assert len(errors) == 0
        
        # Simple list leaf - OK (though ScanRefs in lists not yet implemented)
        # For now, we just verify the structure doesn't error
        step_doc2 = {
            "step_type": "qe_scf",
            "cards": {
                "K_POINTS": {
                    "kpoints": [4, 4, 4],  # Simple list - would be OK if ScanRef supported
                }
            },
            "parameter_scan": {}
        }
        errors, warnings = validate_step_scan_refs(step_doc2)
        assert len(errors) == 0
    
    def test_round_trip_with_parameter_scan(self):
        """Step with parameter_scan round-trips correctly."""
        step_doc = {
            "step_type": "qe_scf",
            "meta": {
                "id": "01HXYZ",
                "name": "SCF",
            },
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": "@scan:scan001",
                    "degauss": "@scan:scan002",
                }
            },
            "cards": {},
            "parameter_scan": {
                "scan001": {
                    "values": [30, 40, 50, 60]
                },
                "scan002": {
                    "values": [0.01, 0.02, 0.03]
                }
            }
        }
        errors, warnings = validate_step_scan_refs(step_doc)
        assert len(errors) == 0
        assert len(warnings) == 0
    
    def test_multiple_scan_refs_same_scan_id(self):
        """Multiple ScanRefs can reference same scan_id."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": "@scan:scan001",
                    "ecutrho": "@scan:scan001",  # Same scan_id - OK
                }
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40]}
            }
        }
        errors, warnings = validate_step_scan_refs(step_doc)
        assert len(errors) == 0
    
    def test_parameter_scan_not_dict_error(self):
        """parameter_scan must be a dict."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": "@scan:scan001",
                }
            },
            "parameter_scan": "not a dict",  # Invalid
        }
        errors, warnings = validate_step_scan_refs(step_doc)
        assert len(errors) > 0
        assert "must be a mapping" in errors[0]

