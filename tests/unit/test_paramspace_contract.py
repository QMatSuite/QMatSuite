"""
Contract tests for ParamSpace framework.

Per Constitution 10.7.7:
- Each preset space must have roundtrip contract tests
- For each profile: apply → detect must hit the same profile
- For NOT_APPLICABLE: If key is forcibly written, detect must become CUSTOM
- For aliases: Synonym forms must detect the same profile

This module tests the ParamSpace framework contracts for:
- occupations_scheme
- precision

Note: Magnetism tests are in test_magnetism_paramspace_contract.py
"""

import pytest

from qmatsuite.presets.dimensions import (
    OccupationsSchemeOption,
    PrecisionOption,
    CUSTOM,
)
from qmatsuite.presets.compiler import (
    compile_occupations_scheme,
    compile_precision,
)
from qmatsuite.presets.detector import (
    detect_occupations_scheme,
    detect_precision,
)
from qmatsuite.presets.precision import (
    PRECISION_CONSTANTS,
    compute_kmesh,
    round_cutoff_integer,
)


class TestOccupationsSchemeRoundtrip:
    """Roundtrip tests for occupations_scheme."""
    
    def test_roundtrip_fixed(self):
        """FIXED: apply → detect must return FIXED."""
        compiled = compile_occupations_scheme(OccupationsSchemeOption.FIXED)
        # compiled is now {"SYSTEM": {...}}
        params = compiled
        detected = detect_occupations_scheme(params, step_type_gen="scf")
        assert detected == OccupationsSchemeOption.FIXED
    
    def test_roundtrip_tetrahedra(self):
        """TETRAHEDRA: apply → detect must return TETRAHEDRA."""
        compiled = compile_occupations_scheme(OccupationsSchemeOption.TETRAHEDRA)
        # compiled is now {"SYSTEM": {...}}
        params = compiled
        detected = detect_occupations_scheme(params, step_type_gen="scf")
        assert detected == OccupationsSchemeOption.TETRAHEDRA
    
    def test_roundtrip_smearing_gaussian(self):
        """SMEARING_GAUSSIAN: apply → detect must return SMEARING_GAUSSIAN."""
        compiled = compile_occupations_scheme(OccupationsSchemeOption.SMEARING_GAUSSIAN)
        # compiled is now {"SYSTEM": {...}}
        params = compiled
        detected = detect_occupations_scheme(params, step_type_gen="scf")
        assert detected == OccupationsSchemeOption.SMEARING_GAUSSIAN
    
    def test_not_applicable_strictness_fixed(self):
        """NOT_APPLICABLE: FIXED profile with smearing present → CUSTOM."""
        # FIXED profile requires smearing to be NOT_APPLICABLE (absent)
        params = {
            "SYSTEM": {
                "occupations": "fixed",
                "smearing": "gaussian",  # Should not be present for FIXED
            }
        }
        detected = detect_occupations_scheme(params)
        assert detected == CUSTOM
    
    def test_not_applicable_strictness_fixed_degauss(self):
        """NOT_APPLICABLE: FIXED profile with degauss present → FIXED (degauss owned by Precision)."""
        params = {
            "SYSTEM": {
                "occupations": "fixed",
                "degauss": 0.02,  # Should not be present for FIXED, but OccupationsScheme doesn't read it
            }
        }
        detected = detect_occupations_scheme(params)
        # OccupationsScheme detect does NOT read degauss (owned by Precision)
        assert detected == OccupationsSchemeOption.FIXED
    
    def test_not_applicable_strictness_tetrahedra(self):
        """NOT_APPLICABLE: TETRAHEDRA profile with smearing present → CUSTOM."""
        params = {
            "SYSTEM": {
                "occupations": "tetrahedra",
                "smearing": "gaussian",  # Should not be present for TETRAHEDRA
            }
        }
        detected = detect_occupations_scheme(params)
        assert detected == CUSTOM
    
    def test_alias_gauss_detects_gaussian(self):
        """Alias: smearing='gauss' must detect as SMEARING_GAUSSIAN."""
        params = {
            "SYSTEM": {
                "occupations": "smearing",
                "smearing": "gauss",  # Alias for "gaussian"
                "degauss": 0.02,
            }
        }
        detected = detect_occupations_scheme(params)
        assert detected == OccupationsSchemeOption.SMEARING_GAUSSIAN
    
    def test_unrelated_key_wildcard(self):
        """Unrelated keys (ecutwfc) must not affect detection."""
        params = {
            "SYSTEM": {
                "occupations": "fixed",
                "ecutwfc": 50.0,  # Unrelated to occupations_scheme
            }
        }
        detected = detect_occupations_scheme(params)
        assert detected == OccupationsSchemeOption.FIXED
    
    def test_present_vs_effective_value_fixed(self):
        """FIXED: Missing occupations → effective_value='fixed' → detects FIXED."""
        # Missing occupations should use default="fixed" as effective_value
        params = {
            "SYSTEM": {
                # No occupations key
            }
        }
        detected = detect_occupations_scheme(params)
        assert detected == OccupationsSchemeOption.FIXED


class TestPrecisionRoundtrip:
    """Roundtrip tests for precision."""
    
    def test_roundtrip_low(self):
        """LOW: apply → detect must return LOW."""
        # Compute canonical values for LOW
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]  # Si
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        constants = PRECISION_CONSTANTS[PrecisionOption.LOW]
        
        canonical_ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
        canonical_ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
        canonical_conv_thr = constants.conv_thr
        canonical_kmesh = compute_kmesh(lattice, constants.delta_k)
        
        # Compile
        compiled = compile_precision(
            PrecisionOption.LOW,
            ecutwfc=canonical_ecutwfc,
            ecutrho=canonical_ecutrho,
            conv_thr=canonical_conv_thr,
            nk1=canonical_kmesh[0],
            nk2=canonical_kmesh[1],
            nk3=canonical_kmesh[2],
            sk1=canonical_kmesh[3],
            sk2=canonical_kmesh[4],
            sk3=canonical_kmesh[5],
        )
        
        # Build params dict
        params = {
            "SYSTEM": compiled["SYSTEM"],
            "ELECTRONS": compiled["ELECTRONS"],
            "cards": {
                "K_POINTS": compiled["K_POINTS_CARD"],
            },
        }
        
        # Detect
        detected = detect_precision(
            params,
            lattice_matrix=lattice,
            base_ecutwfc=base_ecutwfc,
            base_ecutrho=base_ecutrho,
        )
        assert detected == PrecisionOption.LOW
    
    def test_roundtrip_med(self):
        """MED: apply → detect must return MED."""
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        constants = PRECISION_CONSTANTS[PrecisionOption.MED]
        
        canonical_ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
        canonical_ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
        canonical_conv_thr = constants.conv_thr
        canonical_kmesh = compute_kmesh(lattice, constants.delta_k)
        
        compiled = compile_precision(
            PrecisionOption.MED,
            ecutwfc=canonical_ecutwfc,
            ecutrho=canonical_ecutrho,
            conv_thr=canonical_conv_thr,
            nk1=canonical_kmesh[0],
            nk2=canonical_kmesh[1],
            nk3=canonical_kmesh[2],
        )
        
        params = {
            "SYSTEM": compiled["SYSTEM"],
            "ELECTRONS": compiled["ELECTRONS"],
            "cards": {"K_POINTS": compiled["K_POINTS_CARD"]},
        }
        
        detected = detect_precision(
            params,
            lattice_matrix=lattice,
            base_ecutwfc=base_ecutwfc,
            base_ecutrho=base_ecutrho,
        )
        assert detected == PrecisionOption.MED
    
    def test_roundtrip_high(self):
        """HIGH: apply → detect must return HIGH."""
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        constants = PRECISION_CONSTANTS[PrecisionOption.HIGH]
        
        canonical_ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
        canonical_ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
        canonical_conv_thr = constants.conv_thr
        canonical_kmesh = compute_kmesh(lattice, constants.delta_k)
        
        compiled = compile_precision(
            PrecisionOption.HIGH,
            ecutwfc=canonical_ecutwfc,
            ecutrho=canonical_ecutrho,
            conv_thr=canonical_conv_thr,
            nk1=canonical_kmesh[0],
            nk2=canonical_kmesh[1],
            nk3=canonical_kmesh[2],
        )
        
        params = {
            "SYSTEM": compiled["SYSTEM"],
            "ELECTRONS": compiled["ELECTRONS"],
            "cards": {"K_POINTS": compiled["K_POINTS_CARD"]},
        }
        
        detected = detect_precision(
            params,
            lattice_matrix=lattice,
            base_ecutwfc=base_ecutwfc,
            base_ecutrho=base_ecutrho,
        )
        assert detected == PrecisionOption.HIGH
    
    def test_missing_essential_key_returns_custom(self):
        """Missing essential keys (ecutwfc, ecutrho, conv_thr, K_POINTS) → CUSTOM."""
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        
        # Missing ecutwfc
        params1 = {
            "SYSTEM": {"ecutrho": 240},
            "ELECTRONS": {"conv_thr": 1e-8},
            "cards": {"K_POINTS": {"option": "automatic", "data": [[6, 6, 6, 0, 0, 0]]}},
        }
        detected1 = detect_precision(params1, lattice_matrix=lattice, base_ecutwfc=base_ecutwfc, base_ecutrho=base_ecutrho)
        assert detected1 == CUSTOM
        
        # Missing K_POINTS
        params2 = {
            "SYSTEM": {"ecutwfc": 30, "ecutrho": 240},
            "ELECTRONS": {"conv_thr": 1e-8},
        }
        detected2 = detect_precision(params2, lattice_matrix=lattice, base_ecutwfc=base_ecutwfc, base_ecutrho=base_ecutrho)
        assert detected2 == CUSTOM
    
    def test_non_automatic_kpoints_returns_custom(self):
        """Non-automatic K_POINTS must return CUSTOM."""
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        
        params = {
            "SYSTEM": {"ecutwfc": 30, "ecutrho": 240},
            "ELECTRONS": {"conv_thr": 1e-8},
            "cards": {"K_POINTS": {"option": "gamma", "data": [[1, 1, 1, 0, 0, 0]]}},  # Not automatic
        }
        detected = detect_precision(params, lattice_matrix=lattice, base_ecutwfc=base_ecutwfc, base_ecutrho=base_ecutrho)
        assert detected == CUSTOM
    
    def test_unrelated_key_wildcard(self):
        """Unrelated keys (occupations, degauss) must not affect detection."""
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        constants = PRECISION_CONSTANTS[PrecisionOption.MED]
        
        canonical_ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
        canonical_ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
        canonical_conv_thr = constants.conv_thr
        canonical_kmesh = compute_kmesh(lattice, constants.delta_k)
        
        params = {
            "SYSTEM": {
                "ecutwfc": canonical_ecutwfc,
                "ecutrho": canonical_ecutrho,
                "occupations": "fixed",  # Unrelated to precision
                "degauss": 0.02,  # Unrelated to precision
            },
            "ELECTRONS": {"conv_thr": canonical_conv_thr},
            "cards": {"K_POINTS": {"option": "automatic", "data": [list(canonical_kmesh)]}},
        }
        
        detected = detect_precision(params, lattice_matrix=lattice, base_ecutwfc=base_ecutwfc, base_ecutrho=base_ecutrho)
        assert detected == PrecisionOption.MED
    
    def test_no_context_returns_custom(self):
        """Without context (lattice/pseudos), detect must return CUSTOM."""
        params = {
            "SYSTEM": {"ecutwfc": 30, "ecutrho": 240},
            "ELECTRONS": {"conv_thr": 1e-8},
            "cards": {"K_POINTS": {"option": "automatic", "data": [[6, 6, 6, 0, 0, 0]]}},
        }
        # No context provided
        detected = detect_precision(params)
        assert detected == CUSTOM

