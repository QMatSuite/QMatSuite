"""
Contract tests for Magnetism ParamSpace (merged spin + SOC).

Per Constitution 10.7:
- Roundtrip apply→detect must hold for all non-custom options
- Explicit false values must not break detection
- Contradictions must not match (strict detection)
- Apply must output canonical clean input (NOT_APPLICABLE keys deleted)
"""

import pytest

from quantumvitas.presets.dimensions import MagnetismOption, CUSTOM
from quantumvitas.presets.compiler import compile_magnetism
from quantumvitas.presets.detector import detect_magnetism


class TestMagnetismRoundtrip:
    """Test roundtrip apply→detect for all non-custom options."""
    
    def test_roundtrip_nonmagnetic(self):
        """NONMAGNETIC: apply → detect → same option."""
        option = MagnetismOption.NONMAGNETIC
        compiled = compile_magnetism(option)
        
        # Create YAML from compiled (compiled is now {"SYSTEM": {...}})
        yaml_tree = compiled
        detected = detect_magnetism(yaml_tree, step_type="scf")
        
        assert detected == option, f"Roundtrip failed: {option} → {detected}"
    
    def test_roundtrip_collinear_lsda(self):
        """COLLINEAR_LSDA: apply → detect → same option."""
        option = MagnetismOption.COLLINEAR_LSDA
        compiled = compile_magnetism(option)
        
        yaml_tree = compiled
        detected = detect_magnetism(yaml_tree, step_type="scf")
        
        assert detected == option, f"Roundtrip failed: {option} → {detected}"
    
    def test_roundtrip_noncollinear(self):
        """NONCOLLINEAR: apply → detect → same option."""
        option = MagnetismOption.NONCOLLINEAR
        compiled = compile_magnetism(option)
        
        yaml_tree = compiled
        detected = detect_magnetism(yaml_tree, step_type="scf")
        
        assert detected == option, f"Roundtrip failed: {option} → {detected}"
    
    def test_roundtrip_noncollinear_soc(self):
        """NONCOLLINEAR_SOC: apply → detect → same option."""
        option = MagnetismOption.NONCOLLINEAR_SOC
        compiled = compile_magnetism(option)
        
        yaml_tree = compiled
        detected = detect_magnetism(yaml_tree, step_type="scf")
        
        assert detected == option, f"Roundtrip failed: {option} → {detected}"


class TestMagnetismExplicitFalse:
    """Test that explicit false values don't break detection."""
    
    def test_nonmagnetic_only_nspin(self):
        """YAML with only nspin=1 => NONMAGNETIC."""
        yaml_tree = {"SYSTEM": {"nspin": 1}}
        detected = detect_magnetism(yaml_tree)
        assert detected == MagnetismOption.NONMAGNETIC
    
    def test_nonmagnetic_explicit_false(self):
        """YAML with nspin=1, noncolin=false, lspinorb=false => NONMAGNETIC."""
        yaml_tree = {
            "SYSTEM": {
                "nspin": 1,
                "noncolin": ".false.",
                "lspinorb": ".false.",
            }
        }
        detected = detect_magnetism(yaml_tree)
        assert detected == MagnetismOption.NONMAGNETIC
    
    def test_collinear_only_nspin(self):
        """YAML with only nspin=2 => COLLINEAR_LSDA."""
        yaml_tree = {"SYSTEM": {"nspin": 2}}
        detected = detect_magnetism(yaml_tree)
        assert detected == MagnetismOption.COLLINEAR_LSDA
    
    def test_collinear_explicit_false(self):
        """YAML with nspin=2, noncolin=false, lspinorb=false => COLLINEAR_LSDA."""
        yaml_tree = {
            "SYSTEM": {
                "nspin": 2,
                "noncolin": ".false.",
                "lspinorb": ".false.",
            }
        }
        detected = detect_magnetism(yaml_tree)
        assert detected == MagnetismOption.COLLINEAR_LSDA


class TestMagnetismNoncollinearNspinRule:
    """Test noncollinear nspin rule (two accepted forms)."""
    
    def test_noncollinear_canonical(self):
        """noncolin=true and nspin missing, lspinorb missing/false => NONCOLLINEAR."""
        yaml_tree = {
            "SYSTEM": {
                "noncolin": ".true.",
            }
        }
        detected = detect_magnetism(yaml_tree)
        assert detected == MagnetismOption.NONCOLLINEAR
    
    def test_noncollinear_with_nspin4(self):
        """noncolin=true and nspin=4, lspinorb missing/false => NONCOLLINEAR."""
        yaml_tree = {
            "SYSTEM": {
                "nspin": 4,
                "noncolin": ".true.",
            }
        }
        detected = detect_magnetism(yaml_tree)
        assert detected == MagnetismOption.NONCOLLINEAR
    
    def test_noncollinear_soc_canonical(self):
        """noncolin=true, lspinorb=true, nspin missing => NONCOLLINEAR_SOC."""
        yaml_tree = {
            "SYSTEM": {
                "noncolin": ".true.",
                "lspinorb": ".true.",
            }
        }
        detected = detect_magnetism(yaml_tree)
        assert detected == MagnetismOption.NONCOLLINEAR_SOC
    
    def test_noncollinear_soc_with_nspin4(self):
        """noncolin=true, lspinorb=true, nspin=4 => NONCOLLINEAR_SOC."""
        yaml_tree = {
            "SYSTEM": {
                "nspin": 4,
                "noncolin": ".true.",
                "lspinorb": ".true.",
            }
        }
        detected = detect_magnetism(yaml_tree)
        assert detected == MagnetismOption.NONCOLLINEAR_SOC


class TestMagnetismContradictions:
    """Test that contradictions must not match (strict detection)."""
    
    def test_contradiction_noncolin_true_nspin2(self):
        """noncolin=true and nspin=2 => CUSTOM (contradiction)."""
        yaml_tree = {
            "SYSTEM": {
                "nspin": 2,
                "noncolin": ".true.",
            }
        }
        detected = detect_magnetism(yaml_tree)
        assert detected == CUSTOM, "Contradiction must return CUSTOM"
    
    def test_contradiction_lspinorb_true_noncolin_false(self):
        """lspinorb=true and noncolin=false => CUSTOM (contradiction)."""
        yaml_tree = {
            "SYSTEM": {
                "noncolin": ".false.",
                "lspinorb": ".true.",
            }
        }
        detected = detect_magnetism(yaml_tree)
        assert detected == CUSTOM, "Contradiction must return CUSTOM"
    
    def test_contradiction_lspinorb_true_noncolin_missing(self):
        """lspinorb=true and noncolin missing => CUSTOM (contradiction)."""
        yaml_tree = {
            "SYSTEM": {
                "lspinorb": ".true.",
            }
        }
        detected = detect_magnetism(yaml_tree)
        assert detected == CUSTOM, "Contradiction must return CUSTOM"
    
    def test_contradiction_lspinorb_true_nspin2(self):
        """lspinorb=true and nspin=2 (even if noncolin missing) => CUSTOM."""
        yaml_tree = {
            "SYSTEM": {
                "nspin": 2,
                "lspinorb": ".true.",
            }
        }
        detected = detect_magnetism(yaml_tree)
        assert detected == CUSTOM, "Contradiction must return CUSTOM"


class TestMagnetismApplyCanonicalization:
    """Test that apply canonicalization deletes nspin in noncollinear modes."""
    
    def test_apply_noncollinear_deletes_nspin(self):
        """Apply NONCOLLINEAR: output must NOT contain SYSTEM.nspin."""
        option = MagnetismOption.NONCOLLINEAR
        compiled = compile_magnetism(option)
        
        # compiled is now {"SYSTEM": {...}}
        assert "SYSTEM" in compiled
        system = compiled["SYSTEM"]
        # nspin should not be in the output (NOT_APPLICABLE)
        assert "nspin" not in system, "NONCOLLINEAR apply must delete nspin"
        assert system.get("noncolin") == ".true."
        assert system.get("lspinorb") == ".false."
    
    def test_apply_noncollinear_soc_deletes_nspin(self):
        """Apply NONCOLLINEAR_SOC: output must NOT contain SYSTEM.nspin."""
        option = MagnetismOption.NONCOLLINEAR_SOC
        compiled = compile_magnetism(option)
        
        # compiled is now {"SYSTEM": {...}}
        assert "SYSTEM" in compiled
        system = compiled["SYSTEM"]
        # nspin should not be in the output (NOT_APPLICABLE)
        assert "nspin" not in system, "NONCOLLINEAR_SOC apply must delete nspin"
        assert system.get("noncolin") == ".true."
        assert system.get("lspinorb") == ".true."

