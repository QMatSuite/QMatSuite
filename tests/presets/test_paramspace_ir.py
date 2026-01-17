"""
Tests for ParamSpace with IR keys.

Tests that ParamSpace operates on IR keys internally, but YAML I/O uses QE keys via adapter.
Tests that ParamSpace reversibility (compile→detect round-trip) is preserved.
"""

import pytest

from quantumvitas.presets.paramspace import (
    ParamSpace,
    ParamKey,
    get_magnetism_paramspace,
    get_occupations_scheme_paramspace,
    get_convergence_paramspace,
)
from quantumvitas.presets.spaces_registry import (
    detect_dimension,
    compile_dimension_patch,
)
from quantumvitas.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    ConvergenceOption,
)


class TestParamSpaceIRKeys:
    """Test that ParamSpace uses IR keys."""
    
    def test_paramspace_keys_are_ir_keys(self):
        """ParamSpace keys should be IR keys (conceptually)."""
        # In v0, IR keys == QE keys, but conceptually they're IR
        magnetism_space = get_magnetism_paramspace()
        
        ir_keys = {key.key for key in magnetism_space.keys}
        expected_ir_keys = {"nspin", "noncolin", "lspinorb"}
        
        assert ir_keys == expected_ir_keys, (
            f"Magnetism ParamSpace keys should be IR keys {expected_ir_keys}, got {ir_keys}"
        )
    
    def test_paramspace_logic_unchanged(self):
        """ParamSpace matching/compilation logic should be unchanged."""
        # Test that profiles still work
        magnetism_space = get_magnetism_paramspace()
        
        # Should have expected profiles
        assert "NM" in magnetism_space.profiles
        assert "COL" in magnetism_space.profiles
        assert "NC_CANONICAL" in magnetism_space.profiles
        assert "SOC_CANONICAL" in magnetism_space.profiles


class TestParamSpaceReversibility:
    """Test that ParamSpace reversibility is preserved with IR keys."""
    
    def test_magnetism_round_trip(self):
        """Test magnetism compile→detect round-trip."""
        # Create QE YAML with collinear magnetism
        qe_yaml = {
            "SYSTEM": {
                "nspin": 2,
                "noncolin": False,
                "lspinorb": False,
            },
        }
        
        # Detect should return COLLINEAR_LSDA
        detected = detect_dimension("magnetism", qe_yaml)
        assert detected == MagnetismOption.COLLINEAR_LSDA
        
        # Compile should produce same QE params
        patch, deletions = compile_dimension_patch(
            "magnetism",
            MagnetismOption.COLLINEAR_LSDA,
            qe_yaml,
        )
        
        assert "SYSTEM" in patch
        assert patch["SYSTEM"]["nspin"] == 2
        # IR patches use Python bool (YAML canonical)
        assert patch["SYSTEM"]["noncolin"] == False
        assert patch["SYSTEM"]["lspinorb"] == False
    
    def test_occupations_scheme_round_trip(self):
        """Test occupations_scheme compile→detect round-trip."""
        # Create QE YAML with fixed occupations
        qe_yaml = {
            "SYSTEM": {
                "occupations": "fixed",
            },
        }
        
        # Detect should return FIXED
        detected = detect_dimension("occupations_scheme", qe_yaml)
        assert detected == OccupationsSchemeOption.FIXED
        
        # Compile should produce same QE params
        patch, deletions = compile_dimension_patch(
            "occupations_scheme",
            OccupationsSchemeOption.FIXED,
            qe_yaml,
        )
        
        assert "SYSTEM" in patch
        assert patch["SYSTEM"]["occupations"] == "fixed"
    
    def test_convergence_round_trip(self):
        """Test convergence compile→detect round-trip."""
        # Create QE YAML with FAST convergence
        qe_yaml = {
            "ELECTRONS": {
                "mixing_beta": 0.7,
                "electron_maxstep": 100,
                "mixing_mode": "plain",
                "mixing_ndim": 8,
                "diagonalization": "david",
            },
        }
        
        # Detect should return FAST
        detected = detect_dimension("convergence", qe_yaml)
        assert detected == ConvergenceOption.FAST
        
        # Compile should produce same QE params
        patch, deletions = compile_dimension_patch(
            "convergence",
            ConvergenceOption.FAST,
            qe_yaml,
        )
        
        assert "ELECTRONS" in patch
        assert patch["ELECTRONS"]["mixing_beta"] == 0.7
        assert patch["ELECTRONS"]["electron_maxstep"] == 100
        assert patch["ELECTRONS"]["mixing_mode"] == "plain"
        assert patch["ELECTRONS"]["mixing_ndim"] == 8
        assert patch["ELECTRONS"]["diagonalization"] == "david"
    
    def test_magnetism_nonmagnetic_round_trip(self):
        """Test nonmagnetic magnetism round-trip."""
        # Create QE YAML with nonmagnetic (default values)
        qe_yaml = {
            "SYSTEM": {
                "nspin": 1,
            },
        }
        
        # Detect should return NONMAGNETIC
        detected = detect_dimension("magnetism", qe_yaml)
        assert detected == MagnetismOption.NONMAGNETIC
        
        # Compile should produce same QE params
        patch, deletions = compile_dimension_patch(
            "magnetism",
            MagnetismOption.NONMAGNETIC,
            qe_yaml,
        )
        
        assert "SYSTEM" in patch
        assert patch["SYSTEM"]["nspin"] == 1


class TestParamSpaceAdapterIntegration:
    """Test that ParamSpace correctly uses IR↔QE adapter at boundaries."""
    
    def test_detection_uses_adapter(self):
        """Detection should convert QE YAML → IR YAML before matching."""
        # QE YAML with QE params
        qe_yaml = {
            "SYSTEM": {
                "nspin": 2,
            },
        }
        
        # Detection should work (implicitly uses adapter)
        detected = detect_dimension("magnetism", qe_yaml)
        assert detected == MagnetismOption.COLLINEAR_LSDA
    
    def test_compilation_uses_adapter(self):
        """Compilation should convert IR patch → QE patch after ParamSpace."""
        qe_yaml = {}
        
        # Compile should produce QE params (not IR params)
        patch, deletions = compile_dimension_patch(
            "magnetism",
            MagnetismOption.COLLINEAR_LSDA,
            qe_yaml,
        )
        
        # Patch should contain QE section/key names
        assert "SYSTEM" in patch
        assert "nspin" in patch["SYSTEM"]  # QE key name
        assert patch["SYSTEM"]["nspin"] == 2
        
        # Should NOT contain IR-specific structures
        # (In v0, IR keys == QE keys, so this is a bit redundant, but good to verify structure)

