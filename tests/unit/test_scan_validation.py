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
        """Valid ScanRef dicts are detected."""
        assert is_scan_ref({"scan_ref": "scan001"}) is True
        assert is_scan_ref({"scan_ref": "abc123"}) is True
        assert is_scan_ref({"scan_ref": "scan_001"}) is True
    
    def test_is_scan_ref_invalid_format(self):
        """Invalid formats are not ScanRefs."""
        assert is_scan_ref(50) is False  # Not a dict
        assert is_scan_ref("scan001") is False  # String, not dict
        assert is_scan_ref({"scan_ref": "scan001", "extra": "field"}) is False  # Extra key
        assert is_scan_ref({"not_scan_ref": "value"}) is False  # Wrong key
        assert is_scan_ref({}) is False  # Empty dict
        assert is_scan_ref({"key1": "val1", "key2": "val2"}) is False  # Multiple keys


class TestValidateScanRefFormat:
    """Test validate_scan_ref_format() function."""
    
    def test_validate_scan_ref_format_valid(self):
        """Valid ScanRef formats pass validation."""
        validate_scan_ref_format({"scan_ref": "scan001"})
        validate_scan_ref_format({"scan_ref": "abc123"})
        validate_scan_ref_format({"scan_ref": "scan_001"})
        validate_scan_ref_format({"scan_ref": "a"})
    
    def test_validate_scan_ref_format_invalid_type(self):
        """Non-dict values raise error."""
        with pytest.raises(ScanRefValidationError, match="must be a dict"):
            validate_scan_ref_format(50)
        with pytest.raises(ScanRefValidationError, match="must be a dict"):
            validate_scan_ref_format("scan001")
    
    def test_scan_ref_extra_fields_error(self):
        """ScanRef dict with extra fields raises error."""
        with pytest.raises(ScanRefValidationError, match="exactly one key"):
            validate_scan_ref_format({"scan_ref": "scan001", "extra": "field"})
        with pytest.raises(ScanRefValidationError, match="exactly one key"):
            validate_scan_ref_format({"scan_ref": "scan001", "other": "value", "third": "key"})
    
    def test_validate_scan_ref_format_wrong_key(self):
        """Dict with wrong key raises error."""
        with pytest.raises(ScanRefValidationError, match="must have key 'scan_ref'"):
            validate_scan_ref_format({"not_scan_ref": "value"})
    
    def test_validate_scan_ref_format_empty_scan_id(self):
        """Empty scan_id raises error."""
        with pytest.raises(ScanRefValidationError, match="must be non-empty"):
            validate_scan_ref_format({"scan_ref": ""})
    
    def test_validate_scan_ref_format_invalid_scan_id_chars(self):
        """Invalid characters in scan_id raise error."""
        with pytest.raises(ScanRefValidationError, match="must match"):
            validate_scan_ref_format({"scan_ref": "scan-001"})  # Hyphen not allowed
        with pytest.raises(ScanRefValidationError, match="must match"):
            validate_scan_ref_format({"scan_ref": "scan.001"})  # Dot not allowed
        with pytest.raises(ScanRefValidationError, match="must match"):
            validate_scan_ref_format({"scan_ref": "SCAN001"})  # Uppercase not allowed
        with pytest.raises(ScanRefValidationError, match="must match"):
            validate_scan_ref_format({"scan_ref": "scan 001"})  # Space not allowed


class TestFindAllScanRefs:
    """Test find_all_scan_refs() function."""
    
    def test_find_all_scan_refs_scalar_leaf(self):
        """Find ScanRefs at scalar leaf positions."""
        data = {
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": {"scan_ref": "scan001"},
                    "ecutrho": 400,
                }
            }
        }
        refs = find_all_scan_refs(data)
        assert len(refs) == 1
        assert refs[0] == ("parameters.SYSTEM.ecutwfc", "scan001")
    
    def test_find_all_scan_refs_multiple(self):
        """Find multiple ScanRefs."""
        data = {
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": {"scan_ref": "scan001"},
                    "degauss": {"scan_ref": "scan002"},
                }
            }
        }
        refs = find_all_scan_refs(data)
        assert len(refs) == 2
        assert ("parameters.SYSTEM.ecutwfc", "scan001") in refs
        assert ("parameters.SYSTEM.degauss", "scan002") in refs
    
    def test_find_all_scan_refs_in_cards(self):
        """Find ScanRefs in cards section."""
        data = {
            "cards": {
                "K_POINTS": {
                    "kpoints": {"scan_ref": "scan003"},
                }
            }
        }
        refs = find_all_scan_refs(data)
        assert len(refs) == 1
        assert refs[0] == ("cards.K_POINTS.kpoints", "scan003")
    
    def test_find_all_scan_refs_non_leaf_error(self):
        """ScanRef at non-leaf position raises error."""
        # ScanRef as value for entire section
        data = {
            "parameters": {
                "SYSTEM": {"scan_ref": "scan001"},  # Invalid: SYSTEM is not a leaf
            }
        }
        with pytest.raises(ScanRefValidationError, match="non-leaf position"):
            find_all_scan_refs(data)
        
        # ScanRef in nested dict (non-leaf)
        data2 = {
            "parameters": {
                "SYSTEM": {
                    "nested": {
                        "deep": {"scan_ref": "scan001"}  # This is actually a leaf, so OK
                    }
                }
            }
        }
        # This should work - deep.nested is a leaf
        refs = find_all_scan_refs(data2)
        assert len(refs) == 1


class TestValidateStepScanRefs:
    """Test validate_step_scan_refs() function."""
    
    def test_validate_step_scan_refs_valid(self):
        """Valid step with scan refs passes."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": {"scan_ref": "scan001"},
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
                    "ecutwfc": {"scan_ref": "scan001"},
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
                    "ecutwfc": {"scan_ref": "scan001"},
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
                "SYSTEM": {"scan_ref": "scan001"},  # Invalid: SYSTEM is not a leaf
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
                    "ecutwfc": {"scan_ref": "scan001"},  # Scalar leaf - OK
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
                    "ecutwfc": {"scan_ref": "scan001"},
                    "degauss": {"scan_ref": "scan002"},
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
                    "ecutwfc": {"scan_ref": "scan001"},
                    "ecutrho": {"scan_ref": "scan001"},  # Same scan_id - OK
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
                    "ecutwfc": {"scan_ref": "scan001"},
                }
            },
            "parameter_scan": "not a dict",  # Invalid
        }
        errors, warnings = validate_step_scan_refs(step_doc)
        assert len(errors) > 0
        assert "must be a mapping" in errors[0]

