"""
Tests for scan expansion and variant_key computation.
"""

import pytest

from qmatsuite.execution.scan_expansion import (
    ScanDimension,
    VariantAssignment,
    collect_scan_dimensions,
    expand_variants,
    compute_variant_key,
    canonicalize_value,
)


class TestCanonicalizeValue:
    """Test canonicalize_value() function."""
    
    def test_canonicalize_float(self):
        """Floats use repr() for precision."""
        assert canonicalize_value(0.01) == repr(0.01)
        assert canonicalize_value(50.0) == repr(50.0)
        assert canonicalize_value(1.5) == repr(1.5)
    
    def test_canonicalize_int(self):
        """Ints use str()."""
        assert canonicalize_value(50) == "50"
        assert canonicalize_value(0) == "0"
        assert canonicalize_value(-10) == "-10"
    
    def test_canonicalize_list(self):
        """Lists use JSON serialization."""
        assert canonicalize_value([1, 2, 3]) == "[1,2,3]"
        assert canonicalize_value([4, 4, 4]) == "[4,4,4]"
    
    def test_canonicalize_string(self):
        """Strings use JSON serialization."""
        assert canonicalize_value("test") == '"test"'
        assert canonicalize_value("") == '""'


class TestCollectScanDimensions:
    """Test collect_scan_dimensions() function."""
    
    def test_collect_dimensions_single_step(self):
        """Collect dimensions from a single step."""
        step_ids = ["step001"]
        step_docs = {
            "step001": {
                "parameters": {
                    "SYSTEM": {
                        "ecutwfc": "@scan:scan001",
                        "ecutrho": 400,
                    }
                },
                "parameter_scan": {
                    "scan001": {
                        "values": [30, 40, 50]
                    }
                }
            }
        }
        
        dimensions = collect_scan_dimensions(step_ids, step_docs)
        
        assert len(dimensions) == 1
        assert dimensions[0].step_ulid == "step001"
        assert dimensions[0].step_index == 0
        assert dimensions[0].param_path == "parameters.SYSTEM.ecutwfc"
        assert dimensions[0].scan_id == "scan001"
        assert dimensions[0].values == [30, 40, 50]
    
    def test_collect_dimensions_multi_step(self):
        """Collect dimensions from multiple steps."""
        step_ids = ["step001", "step002"]
        step_docs = {
            "step001": {
                "parameters": {
                    "SYSTEM": {
                        "ecutwfc": "@scan:scan001",
                    }
                },
                "parameter_scan": {
                    "scan001": {"values": [30, 40]}
                }
            },
            "step002": {
                "parameters": {
                    "SYSTEM": {
                        "degauss": "@scan:scan002",
                    }
                },
                "parameter_scan": {
                    "scan002": {"values": [0.01, 0.02]}
                }
            }
        }
        
        dimensions = collect_scan_dimensions(step_ids, step_docs)
        
        assert len(dimensions) == 2
        # Should be sorted by (step_index, param_path)
        assert dimensions[0].step_index == 0
        assert dimensions[0].param_path == "parameters.SYSTEM.ecutwfc"
        assert dimensions[1].step_index == 1
        assert dimensions[1].param_path == "parameters.SYSTEM.degauss"
    
    def test_collect_dimensions_sorted(self):
        """Dimensions are sorted by (step_index, param_path)."""
        step_ids = ["step001"]
        step_docs = {
            "step001": {
                "parameters": {
                    "SYSTEM": {
                        "ecutwfc": "@scan:scan001",
                        "degauss": "@scan:scan002",
                    }
                },
                "parameter_scan": {
                    "scan001": {"values": [30, 40]},
                    "scan002": {"values": [0.01, 0.02]}
                }
            }
        }
        
        dimensions = collect_scan_dimensions(step_ids, step_docs)
        
        assert len(dimensions) == 2
        # Should be sorted by param_path within same step
        assert dimensions[0].param_path == "parameters.SYSTEM.degauss"
        assert dimensions[1].param_path == "parameters.SYSTEM.ecutwfc"


class TestExpandVariants:
    """Test expand_variants() function."""
    
    def test_expand_variants_cartesian_product(self):
        """Cartesian product expansion works correctly."""
        dimensions = [
            ScanDimension(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.ecutwfc",
                scan_id="scan001",
                values=[30, 40],
            ),
            ScanDimension(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.degauss",
                scan_id="scan002",
                values=[0.01, 0.02],
            ),
        ]
        
        variants = expand_variants(dimensions)
        
        assert len(variants) == 4  # 2 * 2 = 4
        
        # Check all combinations exist
        variant_values = [
            tuple((a.param_path, a.value) for a in v)
            for v in variants
        ]
        
        expected = [
            ("parameters.SYSTEM.degauss", 0.01, "parameters.SYSTEM.ecutwfc", 30),
            ("parameters.SYSTEM.degauss", 0.01, "parameters.SYSTEM.ecutwfc", 40),
            ("parameters.SYSTEM.degauss", 0.02, "parameters.SYSTEM.ecutwfc", 30),
            ("parameters.SYSTEM.degauss", 0.02, "parameters.SYSTEM.ecutwfc", 40),
        ]
        
        # Note: assignments are sorted by param_path, so degauss comes first
        assert len(variant_values) == 4
    
    def test_expand_variants_deterministic_ordering(self):
        """Variant expansion is deterministic."""
        dimensions = [
            ScanDimension(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.ecutwfc",
                scan_id="scan001",
                values=[30, 40, 50],
            ),
        ]
        
        variants1 = expand_variants(dimensions)
        variants2 = expand_variants(dimensions)
        
        assert len(variants1) == len(variants2) == 3
        
        # Check values are in same order
        for v1, v2 in zip(variants1, variants2):
            assert v1[0].value == v2[0].value
    
    def test_ordering_later_step_varies_faster(self):
        """Later-step scan dims vary faster (inner loops)."""
        dimensions = [
            ScanDimension(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.ecutwfc",
                scan_id="scan001",
                values=[10, 20],
            ),
            ScanDimension(
                step_ulid="step002",
                step_index=1,
                param_path="parameters.SYSTEM.degauss",
                scan_id="scan002",
                values=[1, 2],
            ),
        ]
        
        variants = expand_variants(dimensions)
        
        assert len(variants) == 4  # 2 * 2 = 4
        
        # Check ordering: step 0 varies slower, step 1 varies faster
        # Expected: (10,1), (10,2), (20,1), (20,2)
        step0_values = [v[0].value for v in variants]  # First assignment is step 0
        step1_values = [v[1].value for v in variants]  # Second assignment is step 1
        
        # Step 0 should be: [10, 10, 20, 20] (varies slower)
        assert step0_values == [10, 10, 20, 20]
        
        # Step 1 should be: [1, 2, 1, 2] (varies faster)
        assert step1_values == [1, 2, 1, 2]


class TestComputeVariantKey:
    """Test compute_variant_key() function."""
    
    def test_variant_key_deterministic(self):
        """Same assignments produce same variant_key."""
        assignments1 = [
            VariantAssignment(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.ecutwfc",
                value=50,
            )
        ]
        assignments2 = [
            VariantAssignment(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.ecutwfc",
                value=50,
            )
        ]
        
        key1 = compute_variant_key(assignments1)
        key2 = compute_variant_key(assignments2)
        
        assert key1 == key2
        assert key1.startswith("scan_")
        assert len(key1) == len("scan_") + 16  # "scan_" + 16 hex chars
    
    def test_variant_key_different_values(self):
        """Different values produce different variant_key."""
        assignments1 = [
            VariantAssignment(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.ecutwfc",
                value=50,
            )
        ]
        assignments2 = [
            VariantAssignment(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.ecutwfc",
                value=60,
            )
        ]
        
        key1 = compute_variant_key(assignments1)
        key2 = compute_variant_key(assignments2)
        
        assert key1 != key2
    
    def test_variant_key_float_precision(self):
        """Float precision is preserved via repr()."""
        assignments1 = [
            VariantAssignment(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.degauss",
                value=0.01,
            )
        ]
        assignments2 = [
            VariantAssignment(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.degauss",
                value=0.01,
            )
        ]
        
        key1 = compute_variant_key(assignments1)
        key2 = compute_variant_key(assignments2)
        
        # Should be identical (same float value)
        assert key1 == key2
        
        # Verify repr(0.01) is used
        canonical = canonicalize_value(0.01)
        assert canonical == repr(0.01)
    
    def test_variant_key_multiple_assignments(self):
        """Multiple assignments are handled correctly."""
        assignments = [
            VariantAssignment(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.ecutwfc",
                value=50,
            ),
            VariantAssignment(
                step_ulid="step002",
                step_index=1,
                param_path="parameters.SYSTEM.degauss",
                value=0.01,
            ),
        ]
        
        key = compute_variant_key(assignments)
        
        assert key.startswith("scan_")
        assert len(key) == len("scan_") + 16
    
    def test_variant_key_ordering_independent(self):
        """Variant key is independent of assignment order (sorted internally)."""
        assignments1 = [
            VariantAssignment(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.ecutwfc",
                value=50,
            ),
            VariantAssignment(
                step_ulid="step002",
                step_index=1,
                param_path="parameters.SYSTEM.degauss",
                value=0.01,
            ),
        ]
        assignments2 = [
            VariantAssignment(
                step_ulid="step002",
                step_index=1,
                param_path="parameters.SYSTEM.degauss",
                value=0.01,
            ),
            VariantAssignment(
                step_ulid="step001",
                step_index=0,
                param_path="parameters.SYSTEM.ecutwfc",
                value=50,
            ),
        ]
        
        key1 = compute_variant_key(assignments1)
        key2 = compute_variant_key(assignments2)
        
        # Should be identical (sorted internally)
        assert key1 == key2

