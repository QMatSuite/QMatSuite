"""
Tests for IR↔QE adapter mapping.

Tests that mapping is complete, bijective, and handles conversions correctly.
"""

import pytest

from quantumvitas.ir.backends.qe.mapping import (
    IR_TO_QE_MAPPING,
    QE_TO_IR_MAPPING,
    ir_to_qe_param,
    qe_to_ir_param,
    ir_patch_to_qe_patch,
    qe_yaml_to_ir_yaml,
    validate_ir_qe_mapping,
)


class TestIRQEMapping:
    """Test IR↔QE mapping."""
    
    def test_mapping_validation(self):
        """Mapping validation should pass."""
        validate_ir_qe_mapping()  # Should not raise
    
    def test_all_ir_keys_have_qe_mappings(self):
        """All IR keys must have QE mappings."""
        from quantumvitas.ir.parameters import IR_REGISTRY
        
        for ir_key in IR_REGISTRY.keys():
            assert ir_key in IR_TO_QE_MAPPING, (
                f"IR key '{ir_key}' missing from IR→QE mapping"
            )
    
    def test_mapping_is_bijective(self):
        """IR↔QE mapping must be bijective (one-to-one)."""
        # Check forward mapping completeness
        for ir_key, qe_tuple in IR_TO_QE_MAPPING.items():
            assert qe_tuple in QE_TO_IR_MAPPING, (
                f"IR→QE mapping '{ir_key} → {qe_tuple}' missing reverse mapping"
            )
            reverse_ir_key = QE_TO_IR_MAPPING[qe_tuple]
            assert reverse_ir_key == ir_key, (
                f"Reverse mapping inconsistent: {ir_key} → {qe_tuple} → {reverse_ir_key}"
            )
        
        # Check reverse mapping completeness
        for qe_tuple, ir_key in QE_TO_IR_MAPPING.items():
            assert ir_key in IR_TO_QE_MAPPING, (
                f"QE→IR mapping '{qe_tuple} → {ir_key}' points to unknown IR key"
            )
            forward_qe_tuple = IR_TO_QE_MAPPING[ir_key]
            assert forward_qe_tuple == qe_tuple, (
                f"Forward mapping inconsistent: {ir_key} → {forward_qe_tuple}, "
                f"but reverse says {qe_tuple} → {ir_key}"
            )
    
    def test_ir_to_qe_param(self):
        """Test IR→QE parameter conversion."""
        # Test standard parameter
        qe_module, qe_section, qe_key, qe_value = ir_to_qe_param("ecutwfc", 50.0)
        assert qe_module == "pw"
        assert qe_section == "SYSTEM"
        assert qe_key == "ecutwfc"
        assert qe_value == 50.0  # No unit conversion in v0
        
        # Test card parameter
        kpoints_value = {"option": "automatic", "data": [[4, 4, 4, 0, 0, 0]]}
        qe_module, qe_section, qe_key, qe_value = ir_to_qe_param("K_POINTS", kpoints_value)
        assert qe_module == "pw"
        assert qe_section == "cards"
        assert qe_key == "K_POINTS"
        assert qe_value == kpoints_value
        
        # Non-existent IR key
        with pytest.raises(KeyError):
            ir_to_qe_param("nonexistent", 42)
    
    def test_qe_to_ir_param(self):
        """Test QE→IR parameter conversion."""
        # Test standard parameter
        ir_key, ir_value = qe_to_ir_param("pw", "SYSTEM", "ecutwfc", 50.0)
        assert ir_key == "ecutwfc"
        assert ir_value == 50.0  # No unit conversion in v0
        
        # Test card parameter
        kpoints_value = {"option": "automatic", "data": [[4, 4, 4, 0, 0, 0]]}
        ir_key, ir_value = qe_to_ir_param("pw", "cards", "K_POINTS", kpoints_value)
        assert ir_key == "K_POINTS"
        assert ir_value == kpoints_value
        
        # Non-existent QE parameter
        with pytest.raises(KeyError):
            qe_to_ir_param("pw", "SYSTEM", "nonexistent", 42)
    
    def test_ir_patch_to_qe_patch(self):
        """Test IR patch to QE patch conversion."""
        ir_patch = {
            "SYSTEM": {
                "ecutwfc": 50.0,
                "nspin": 2,
            },
            "ELECTRONS": {
                "conv_thr": 1e-6,
            },
        }
        
        qe_patch = ir_patch_to_qe_patch(ir_patch)
        
        assert "SYSTEM" in qe_patch
        assert qe_patch["SYSTEM"]["ecutwfc"] == 50.0
        assert qe_patch["SYSTEM"]["nspin"] == 2
        assert "ELECTRONS" in qe_patch
        assert qe_patch["ELECTRONS"]["conv_thr"] == 1e-6
    
    def test_ir_patch_to_qe_patch_with_cards(self):
        """Test IR patch to QE patch conversion with cards."""
        ir_patch = {
            "SYSTEM": {"ecutwfc": 50.0},
            "cards": {
                "K_POINTS": {
                    "option": "automatic",
                    "data": [[4, 4, 4, 0, 0, 0]],
                },
            },
        }
        
        qe_patch = ir_patch_to_qe_patch(ir_patch)
        
        assert "SYSTEM" in qe_patch
        assert "cards" in qe_patch
        assert "K_POINTS" in qe_patch["cards"]
        assert qe_patch["cards"]["K_POINTS"]["option"] == "automatic"
    
    def test_qe_yaml_to_ir_yaml(self):
        """Test QE YAML to IR YAML conversion."""
        qe_yaml = {
            "SYSTEM": {
                "ecutwfc": 50.0,
                "nspin": 2,
                "some_other_param": 42,  # Non-IR parameter
            },
            "ELECTRONS": {
                "conv_thr": 1e-6,
            },
        }
        
        ir_yaml = qe_yaml_to_ir_yaml(qe_yaml, qe_module="pw")
        
        # IR YAML should contain IR parameters only
        assert "SYSTEM" in ir_yaml
        assert "ecutwfc" in ir_yaml["SYSTEM"]
        assert ir_yaml["SYSTEM"]["ecutwfc"] == 50.0
        assert "nspin" in ir_yaml["SYSTEM"]
        assert ir_yaml["SYSTEM"]["nspin"] == 2
        assert "some_other_param" not in ir_yaml["SYSTEM"]  # Non-IR parameter excluded
        
        assert "ELECTRONS" in ir_yaml
        assert "conv_thr" in ir_yaml["ELECTRONS"]
        assert ir_yaml["ELECTRONS"]["conv_thr"] == 1e-6
    
    def test_round_trip_conversion(self):
        """Test round-trip conversion (QE→IR→QE)."""
        qe_yaml = {
            "SYSTEM": {
                "ecutwfc": 50.0,
                "nspin": 2,
                "noncolin": False,
            },
            "ELECTRONS": {
                "conv_thr": 1e-6,
                "mixing_beta": 0.7,
            },
        }
        
        # QE → IR
        ir_yaml = qe_yaml_to_ir_yaml(qe_yaml, qe_module="pw")
        
        # IR → QE (via patch conversion)
        ir_patch = ir_yaml
        qe_patch = ir_patch_to_qe_patch(ir_patch)
        
        # Verify round-trip preserves IR parameters
        assert "SYSTEM" in qe_patch
        assert qe_patch["SYSTEM"]["ecutwfc"] == 50.0
        assert qe_patch["SYSTEM"]["nspin"] == 2
        # IR→QE conversion preserves Python bool; QE generator handles .true./.false. at output
        assert qe_patch["SYSTEM"]["noncolin"] == False
        assert "ELECTRONS" in qe_patch
        assert qe_patch["ELECTRONS"]["conv_thr"] == 1e-6
        assert qe_patch["ELECTRONS"]["mixing_beta"] == 0.7

