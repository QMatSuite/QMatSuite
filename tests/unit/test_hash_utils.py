"""
Tests for hash utilities, including effective fingerprint integration.
"""

import pytest

from quantumvitas.calculation.hash_utils import (
    build_effective_engine_params_view,
    compute_step_sha,
)


class TestBuildEffectiveEngineParamsView:
    """Test build_effective_engine_params_view() function."""
    
    def test_build_effective_view_resolves_scan_refs(self):
        """ScanRefs are resolved to concrete values."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": {"scan_ref": "scan001"},
                    "ecutrho": 400,
                }
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40, 50]}
            }
        }
        
        variant_assignments = {
            "parameters.SYSTEM.ecutwfc": 50,
        }
        
        effective = build_effective_engine_params_view(step_doc, variant_assignments)
        
        # ScanRef should be resolved
        assert effective["parameters"]["SYSTEM"]["ecutwfc"] == 50
        # Other params preserved
        assert effective["parameters"]["SYSTEM"]["ecutrho"] == 400
        # parameter_scan removed
        assert "parameter_scan" not in effective
    
    def test_build_effective_view_removes_parameter_scan(self):
        """parameter_scan section is always removed."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": 50,
                }
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40]}
            }
        }
        
        effective = build_effective_engine_params_view(step_doc, None)
        
        assert "parameter_scan" not in effective
        assert effective["parameters"]["SYSTEM"]["ecutwfc"] == 50
    
    def test_build_effective_view_no_mutation(self):
        """Input dict is not mutated."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": {"scan_ref": "scan001"},
                }
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40]}
            }
        }
        
        original_scan_ref = step_doc["parameters"]["SYSTEM"]["ecutwfc"]
        
        variant_assignments = {
            "parameters.SYSTEM.ecutwfc": 50,
        }
        
        effective = build_effective_engine_params_view(step_doc, variant_assignments)
        
        # Original should be unchanged
        assert step_doc["parameters"]["SYSTEM"]["ecutwfc"] == original_scan_ref
        assert step_doc["parameter_scan"] == {"scan001": {"values": [30, 40]}}
        
        # Effective should have resolved value
        assert effective["parameters"]["SYSTEM"]["ecutwfc"] == 50


class TestComputeStepShaEffective:
    """Test compute_step_sha() with effective params view."""
    
    def test_effective_sha_resolves_scan_refs(self):
        """Step SHA with resolved ScanRefs is computed correctly."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": {"scan_ref": "scan001"},
                    "ecutrho": 400,
                }
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40, 50]}
            }
        }
        
        variant_assignments = {
            "parameters.SYSTEM.ecutwfc": 50,
        }
        
        sha_with_scan = compute_step_sha(step_doc, variant_assignments)
        
        # Should be deterministic
        sha_with_scan2 = compute_step_sha(step_doc, variant_assignments)
        assert sha_with_scan == sha_with_scan2
    
    def test_effective_sha_removes_parameter_scan_section(self):
        """parameter_scan section does not affect fingerprint."""
        step_doc1 = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": 50,
                }
            },
        }
        
        step_doc2 = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": 50,
                }
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40]}
            }
        }
        
        sha1 = compute_step_sha(step_doc1)
        sha2 = compute_step_sha(step_doc2)
        
        # Should be identical (parameter_scan removed before hashing)
        assert sha1 == sha2
    
    def test_effective_sha_equivalence(self):
        """Step with concrete value and scan-variant with same value produce identical SHA."""
        # Step with concrete value
        step_doc_concrete = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": 50,
                    "ecutrho": 400,
                }
            },
        }
        
        # Step with ScanRef resolved to same value
        step_doc_scan = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": {"scan_ref": "scan001"},
                    "ecutrho": 400,
                }
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40, 50]}
            }
        }
        
        variant_assignments = {
            "parameters.SYSTEM.ecutwfc": 50,
        }
        
        sha_concrete = compute_step_sha(step_doc_concrete)
        sha_scan = compute_step_sha(step_doc_scan, variant_assignments)
        
        # **Critical test**: Should produce identical fingerprints
        assert sha_concrete == sha_scan
    
    def test_effective_sha_no_mutation(self):
        """compute_step_sha does not mutate input."""
        step_doc = {
            "step_type": "qe_scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": {"scan_ref": "scan001"},
                }
            },
            "parameter_scan": {
                "scan001": {"values": [30, 40]}
            }
        }
        
        original_scan_ref = step_doc["parameters"]["SYSTEM"]["ecutwfc"]
        original_parameter_scan = step_doc["parameter_scan"]
        
        variant_assignments = {
            "parameters.SYSTEM.ecutwfc": 50,
        }
        
        compute_step_sha(step_doc, variant_assignments)
        
        # Original should be unchanged
        assert step_doc["parameters"]["SYSTEM"]["ecutwfc"] == original_scan_ref
        assert step_doc["parameter_scan"] == original_parameter_scan

