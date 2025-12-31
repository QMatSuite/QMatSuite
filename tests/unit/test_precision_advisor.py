"""
Unit tests for precision preset advisor (revised v1).

Tests cover:
- K-mesh computation using reciprocal space formulation
- Integer cutoff rounding
- Cutoff aggregation from PSEUDO_FILE_INDEX
- Precision advisor end-to-end
- Strict 3-way detection matching
- PSEUDO_FILE_INDEX caching
"""

import pytest
import math
from typing import Dict, Any
from unittest.mock import patch, MagicMock

from quantumvitas.presets.dimensions import PrecisionOption
from quantumvitas.presets.precision import (
    compute_kmesh,
    compute_reciprocal_lengths,
    aggregate_cutoffs,
    get_cutoffs_from_index,
    round_cutoff_integer,
    PrecisionAdvisor,
    PrecisionAdvice,
    PRECISION_CONSTANTS,
    PRECISION_CONFIGS,
    get_pseudo_index,
    clear_pseudo_index_cache,
)


class TestReciprocalLattice:
    """Tests for reciprocal lattice vector calculation."""
    
    def test_cubic_lattice(self):
        """Cubic lattice has orthogonal reciprocal vectors."""
        a = 5.0
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        
        b1, b2, b3 = compute_reciprocal_lengths(lattice)
        
        # For cubic: |b| = 2π/a
        expected = 2 * math.pi / a
        assert abs(b1 - expected) < 1e-10
        assert abs(b2 - expected) < 1e-10
        assert abs(b3 - expected) < 1e-10
    
    def test_silicon_lattice(self):
        """Si conventional cell reciprocal lengths."""
        a = 5.43
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        
        b1, b2, b3 = compute_reciprocal_lengths(lattice)
        
        # |b| = 2π/5.43 ≈ 1.157 Å⁻¹
        expected = 2 * math.pi / a
        assert abs(b1 - expected) < 1e-10
        assert abs(b2 - expected) < 1e-10
        assert abs(b3 - expected) < 1e-10


class TestKMeshComputation:
    """Tests for k-mesh computation using reciprocal space formulation."""
    
    def test_cubic_silicon_low_precision(self):
        """Si (a ≈ 5.43 Å) with low precision Δk=0.30 Å⁻¹."""
        a = 5.43
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        
        # |b| = 2π/5.43 ≈ 1.157 Å⁻¹
        # nk = ceil(1.157 / 0.30) = ceil(3.86) = 4
        nk1, nk2, nk3, sk1, sk2, sk3 = compute_kmesh(lattice, delta_k=0.30)
        
        assert nk1 == 4
        assert nk2 == 4
        assert nk3 == 4
        assert (sk1, sk2, sk3) == (0, 0, 0)
    
    def test_cubic_silicon_med_precision(self):
        """Si (a ≈ 5.43 Å) with medium precision Δk=0.20 Å⁻¹."""
        a = 5.43
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        
        # nk = ceil(1.157 / 0.20) = ceil(5.79) = 6
        nk1, nk2, nk3, _, _, _ = compute_kmesh(lattice, delta_k=0.20)
        
        assert nk1 == 6
        assert nk2 == 6
        assert nk3 == 6
    
    def test_cubic_silicon_high_precision(self):
        """Si (a ≈ 5.43 Å) with high precision Δk=0.15 Å⁻¹."""
        a = 5.43
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        
        # nk = ceil(1.157 / 0.15) = ceil(7.71) = 8
        nk1, nk2, nk3, _, _, _ = compute_kmesh(lattice, delta_k=0.15)
        
        assert nk1 == 8
        assert nk2 == 8
        assert nk3 == 8
    
    def test_hexagonal_cell(self):
        """Hexagonal cell has different reciprocal lengths in-plane vs out-of-plane."""
        a = 3.2
        c = 5.2
        # Hexagonal lattice vectors
        lattice = [
            [a, 0, 0],
            [-a/2, a * math.sqrt(3)/2, 0],
            [0, 0, c],
        ]
        
        # Volume = a² * sqrt(3)/2 * c
        # b1, b2 are in the basal plane, b3 is along c
        nk1, nk2, nk3, _, _, _ = compute_kmesh(lattice, delta_k=0.20)
        
        # The in-plane directions should have larger nk due to larger |b|
        # The c direction has smaller |b| = 2π/c
        assert nk1 > 1
        assert nk2 > 1
        assert nk3 > 1
    
    def test_large_cell_gives_small_mesh(self):
        """Large real-space cell → small reciprocal vectors → small k-mesh."""
        # 20 Å cubic cell
        lattice = [[20, 0, 0], [0, 20, 0], [0, 0, 20]]
        
        # |b| = 2π/20 ≈ 0.314 Å⁻¹
        # With Δk=0.30, nk = ceil(0.314/0.30) = 2
        nk1, nk2, nk3, _, _, _ = compute_kmesh(lattice, delta_k=0.30)
        
        # Should give small k-mesh
        assert nk1 <= 2
        assert nk2 <= 2
        assert nk3 <= 2
    
    def test_slab_structure(self):
        """Slab structures are handled by physics (no special detection)."""
        # Slab: small a,b, large c
        a = 3.0
        c = 25.0
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, c]]
        
        # b1, b2: |b| = 2π/3 ≈ 2.094 Å⁻¹ (dense k-mesh)
        # b3: |b| = 2π/25 ≈ 0.251 Å⁻¹ (sparse k-mesh)
        nk1, nk2, nk3, _, _, _ = compute_kmesh(lattice, delta_k=0.20)
        
        # In-plane should have many k-points
        assert nk1 >= 10
        assert nk2 >= 10
        # c-direction has small |b3|, so fewer k-points needed
        assert nk3 <= 2  # Physical result: small |b| means Γ-like
    
    def test_minimum_one_kpoint(self):
        """K-mesh should always have at least 1 k-point per direction."""
        # Very large cell
        lattice = [[100, 0, 0], [0, 100, 0], [0, 0, 100]]
        
        nk1, nk2, nk3, _, _, _ = compute_kmesh(lattice, delta_k=0.50)
        
        assert nk1 >= 1
        assert nk2 >= 1
        assert nk3 >= 1


class TestCutoffResolution:
    """Tests for cutoff lookup from pseudo index."""
    
    @pytest.fixture
    def mock_index_files(self):
        """Create mock PSEUDO_FILE_INDEX entries."""
        return [
            {
                "sha256": "abc123",
                "sha_family": "fam123",
                "element": "Si",
                "cutoff_wfc_normal": 40.0,
                "cutoff_rho_normal": 320.0,
            },
            {
                "sha256": "def456",
                "sha_family": "fam456",
                "element": "O",
                "cutoff_wfc_normal": 60.0,
                "cutoff_rho_normal": 480.0,
            },
            {
                "sha256": "ghi789",
                "sha_family": "fam789",
                "element": "C",
                "cutoff_wfc_normal": 50.0,
                "cutoff_rho_normal": "na",  # NC pseudo without rho recommendation
            },
        ]
    
    def test_lookup_by_sha256(self, mock_index_files):
        """Look up cutoffs by exact sha256."""
        ecutwfc, ecutrho = get_cutoffs_from_index("abc123", mock_index_files)
        assert ecutwfc == 40.0
        assert ecutrho == 320.0
    
    def test_lookup_missing_sha256(self, mock_index_files):
        """Missing sha256 returns None."""
        ecutwfc, ecutrho = get_cutoffs_from_index("not_found", mock_index_files)
        assert ecutwfc is None
        assert ecutrho is None
    
    def test_aggregate_single_species(self, mock_index_files):
        """Aggregate cutoffs for single species."""
        species_map = {
            "Si": {"pseudo_sha256": "abc123"}
        }
        
        ecutwfc, ecutrho = aggregate_cutoffs(species_map, mock_index_files)
        
        assert ecutwfc == 40.0
        assert ecutrho == 320.0
    
    def test_aggregate_multiple_species_takes_max(self, mock_index_files):
        """Aggregate takes max cutoff across species."""
        species_map = {
            "Si": {"pseudo_sha256": "abc123"},  # 40/320
            "O": {"pseudo_sha256": "def456"},   # 60/480
        }
        
        ecutwfc, ecutrho = aggregate_cutoffs(species_map, mock_index_files)
        
        # Should take max: 60 and 480
        assert ecutwfc == 60.0
        assert ecutrho == 480.0
    
    def test_aggregate_empty_species_map(self, mock_index_files):
        """Empty species map uses defaults."""
        ecutwfc, ecutrho = aggregate_cutoffs({}, mock_index_files)
        
        # Default values (defined in precision.py)
        assert ecutwfc == 50.0
        assert ecutrho == 400.0


class TestIntegerCutoffRounding:
    """Tests for integer cutoff rounding."""
    
    def test_round_cutoff_integer(self):
        """Cutoffs are rounded to nearest integer."""
        assert round_cutoff_integer(42.3) == 42
        assert round_cutoff_integer(42.7) == 43
        assert round_cutoff_integer(42.5) == 42  # Python rounds to even
        assert round_cutoff_integer(43.5) == 44
    
    def test_advisor_returns_integer_cutoffs(self):
        """PrecisionAdvisor returns integer cutoffs."""
        species_map = {"Si": {}}
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        
        advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice)
        advice = advisor.advise(PrecisionOption.MED)
        
        # Cutoffs should be integers
        assert isinstance(advice.ecutwfc, int)
        assert isinstance(advice.ecutrho, int)
    
    def test_cutoffs_stable_across_multipliers(self):
        """Integer rounding gives stable cutoffs."""
        base_wfc = 50.0
        base_rho = 400.0
        
        # Low: 0.8×
        low_wfc = round_cutoff_integer(base_wfc * 0.8)
        low_rho = round_cutoff_integer(base_rho * 0.8)
        assert low_wfc == 40
        assert low_rho == 320
        
        # Med: 1.0×
        med_wfc = round_cutoff_integer(base_wfc * 1.0)
        med_rho = round_cutoff_integer(base_rho * 1.0)
        assert med_wfc == 50
        assert med_rho == 400
        
        # High: 1.2×
        high_wfc = round_cutoff_integer(base_wfc * 1.2)
        high_rho = round_cutoff_integer(base_rho * 1.2)
        assert high_wfc == 60
        assert high_rho == 480


class TestPrecisionConstants:
    """Tests for centralized precision constants."""
    
    def test_constants_ordering(self):
        """Verify constant values are ordered correctly."""
        low = PRECISION_CONSTANTS[PrecisionOption.LOW]
        med = PRECISION_CONSTANTS[PrecisionOption.MED]
        high = PRECISION_CONSTANTS[PrecisionOption.HIGH]
        
        # delta_k: LOW > MED > HIGH (coarser → finer spacing)
        assert low.delta_k > med.delta_k > high.delta_k
        
        # conv_thr: LOW > MED > HIGH (looser → tighter)
        assert low.conv_thr > med.conv_thr > high.conv_thr
        
        # cutoff_multiplier: LOW < MED < HIGH
        assert low.cutoff_multiplier < med.cutoff_multiplier < high.cutoff_multiplier
    
    def test_symmetric_cutoff_multipliers(self):
        """Cutoff multipliers are symmetric around 1.0."""
        low = PRECISION_CONSTANTS[PrecisionOption.LOW]
        med = PRECISION_CONSTANTS[PrecisionOption.MED]
        high = PRECISION_CONSTANTS[PrecisionOption.HIGH]
        
        assert low.cutoff_multiplier == 0.8
        assert med.cutoff_multiplier == 1.0
        assert high.cutoff_multiplier == 1.2
        
        # Symmetric: 1.0 - 0.2 and 1.0 + 0.2
        assert med.cutoff_multiplier - low.cutoff_multiplier == high.cutoff_multiplier - med.cutoff_multiplier
    
    def test_delta_k_values(self):
        """Delta k values are as specified."""
        assert PRECISION_CONSTANTS[PrecisionOption.LOW].delta_k == 0.30
        assert PRECISION_CONSTANTS[PrecisionOption.MED].delta_k == 0.20
        assert PRECISION_CONSTANTS[PrecisionOption.HIGH].delta_k == 0.15
    
    def test_conv_thr_values(self):
        """Conv_thr values are as specified."""
        assert PRECISION_CONSTANTS[PrecisionOption.LOW].conv_thr == 1e-6
        assert PRECISION_CONSTANTS[PrecisionOption.MED].conv_thr == 1e-8
        assert PRECISION_CONSTANTS[PrecisionOption.HIGH].conv_thr == 1e-10


class TestPrecisionAdvisor:
    """Tests for PrecisionAdvisor end-to-end."""
    
    def test_advisor_silicon_all_levels(self):
        """Advisor for Si returns expected k-mesh for each level."""
        species_map = {"Si": {}}
        a = 5.43
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        
        advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice)
        
        # Low: Δk=0.30, nk = ceil(1.157/0.30) = 4
        low_advice = advisor.advise(PrecisionOption.LOW)
        assert low_advice.nk1 == 4
        assert low_advice.conv_thr == 1e-6
        
        # Med: Δk=0.20, nk = ceil(1.157/0.20) = 6
        med_advice = advisor.advise(PrecisionOption.MED)
        assert med_advice.nk1 == 6
        assert med_advice.conv_thr == 1e-8
        
        # High: Δk=0.15, nk = ceil(1.157/0.15) = 8
        high_advice = advisor.advise(PrecisionOption.HIGH)
        assert high_advice.nk1 == 8
        assert high_advice.conv_thr == 1e-10
    
    def test_advisor_all_levels(self):
        """Advisor returns advice for all precision levels."""
        species_map = {"Si": {}}
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        
        advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice)
        all_advice = advisor.advise_all()
        
        assert PrecisionOption.LOW in all_advice
        assert PrecisionOption.MED in all_advice
        assert PrecisionOption.HIGH in all_advice
        
        # Verify ordering: HIGH should have denser mesh than LOW
        assert all_advice[PrecisionOption.HIGH].nk1 > all_advice[PrecisionOption.LOW].nk1


class TestPrecisionDetectorSimple:
    """Tests for simple precision detection from conv_thr."""
    
    def test_detect_low_from_conv_thr(self):
        """Detect LOW precision from loose conv_thr."""
        from quantumvitas.presets.detector import detect_precision
        
        params = {"ELECTRONS": {"conv_thr": 1e-6}}
        result = detect_precision(params)
        
        assert result == PrecisionOption.LOW
    
    def test_detect_med_from_conv_thr(self):
        """Detect MED precision from typical conv_thr."""
        from quantumvitas.presets.detector import detect_precision
        
        params = {"ELECTRONS": {"conv_thr": 1e-8}}
        result = detect_precision(params)
        
        assert result == PrecisionOption.MED
    
    def test_detect_high_from_conv_thr(self):
        """Detect HIGH precision from tight conv_thr."""
        from quantumvitas.presets.detector import detect_precision
        
        params = {"ELECTRONS": {"conv_thr": 1e-10}}
        result = detect_precision(params)
        
        assert result == PrecisionOption.HIGH


class TestPrecisionDetectorStrict:
    """Tests for strict 3-way precision detection."""
    
    def test_strict_detect_matches_level(self):
        """Strict detection matches when all three aspects align."""
        from quantumvitas.presets.detector import detect_precision_strict
        from quantumvitas.presets.precision import round_cutoff_integer
        
        # Si lattice
        a = 5.43
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        base_ecutwfc = 50.0
        base_ecutrho = 400.0
        
        # Compute canonical values for MED
        # Δk=0.20 → nk=6 for Si
        # cutoff_mult=1.0 → ecutwfc=50, ecutrho=400
        # conv_thr=1e-8
        params = {
            "SYSTEM": {
                "ecutwfc": round_cutoff_integer(base_ecutwfc * 1.0),  # 50
                "ecutrho": round_cutoff_integer(base_ecutrho * 1.0),  # 400
            },
            "ELECTRONS": {
                "conv_thr": 1e-8,
            },
            "K_POINTS": {
                "type": "automatic",
                "mesh": [6, 6, 6, 0, 0, 0],
            },
        }
        
        result = detect_precision_strict(params, lattice, base_ecutwfc, base_ecutrho)
        assert result == PrecisionOption.MED
    
    def test_strict_detect_mismatch_cutoff(self):
        """Strict detection returns None if cutoffs don't match."""
        from quantumvitas.presets.detector import detect_precision_strict
        
        a = 5.43
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        base_ecutwfc = 50.0
        base_ecutrho = 400.0
        
        # All params for MED except wrong ecutwfc
        params = {
            "SYSTEM": {
                "ecutwfc": 55,  # Wrong! Should be 50
                "ecutrho": 400,
            },
            "ELECTRONS": {
                "conv_thr": 1e-8,
            },
            "K_POINTS": {
                "type": "automatic",
                "mesh": [6, 6, 6, 0, 0, 0],
            },
        }
        
        result = detect_precision_strict(params, lattice, base_ecutwfc, base_ecutrho)
        assert result is None  # No level matches
    
    def test_strict_detect_mismatch_kmesh(self):
        """Strict detection returns None if k-mesh doesn't match."""
        from quantumvitas.presets.detector import detect_precision_strict
        
        a = 5.43
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        base_ecutwfc = 50.0
        base_ecutrho = 400.0
        
        # All params for MED except wrong k-mesh
        params = {
            "SYSTEM": {
                "ecutwfc": 50,
                "ecutrho": 400,
            },
            "ELECTRONS": {
                "conv_thr": 1e-8,
            },
            "K_POINTS": {
                "type": "automatic",
                "mesh": [8, 8, 8, 0, 0, 0],  # Wrong! Should be 6×6×6 for MED
            },
        }
        
        result = detect_precision_strict(params, lattice, base_ecutwfc, base_ecutrho)
        assert result is None  # No level matches
    
    def test_strict_detect_mismatch_conv_thr(self):
        """Strict detection returns None if conv_thr doesn't match."""
        from quantumvitas.presets.detector import detect_precision_strict
        
        a = 5.43
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        base_ecutwfc = 50.0
        base_ecutrho = 400.0
        
        # All params for MED except wrong conv_thr
        params = {
            "SYSTEM": {
                "ecutwfc": 50,
                "ecutrho": 400,
            },
            "ELECTRONS": {
                "conv_thr": 1e-7,  # Wrong! Should be 1e-8 for MED
            },
            "K_POINTS": {
                "type": "automatic",
                "mesh": [6, 6, 6, 0, 0, 0],
            },
        }
        
        result = detect_precision_strict(params, lattice, base_ecutwfc, base_ecutrho)
        assert result is None  # No level matches


class TestCompilerDetectorEquivalence:
    """Test that detect(compile(x)) == x for precision."""
    
    def test_equivalence_via_strict_detection(self):
        """Compiled params can be strictly detected back to the same level."""
        from quantumvitas.presets.compiler import compile_precision_from_advice
        from quantumvitas.presets.detector import detect_precision_strict
        
        # Si lattice
        a = 5.43
        lattice = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        species_map = {"Si": {}}
        
        advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice)
        
        for level in PrecisionOption:
            advice = advisor.advise(level)
            compiled = compile_precision_from_advice(advice)
            
            # Build params dict
            params = {
                "SYSTEM": compiled.get("SYSTEM", {}),
                "ELECTRONS": compiled.get("ELECTRONS", {}),
                "K_POINTS": compiled.get("K_POINTS", {}),
            }
            
            # Detect with strict matching
            detected = detect_precision_strict(
                params, lattice, advice.base_ecutwfc, advice.base_ecutrho
            )
            
            assert detected == level, f"Failed for {level}: detected {detected}"


class TestPseudoIndexCaching:
    """Tests for PSEUDO_FILE_INDEX caching."""
    
    def test_cache_prevents_repeated_loads(self):
        """Index is loaded only once despite multiple advisor calls."""
        clear_pseudo_index_cache()
        
        species_map = {"Si": {}}
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        
        # Create multiple advisors and get advice
        for _ in range(5):
            advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice)
            advisor.advise(PrecisionOption.MED)
        
        # Check cache info - should have 1 hit per call after first
        from quantumvitas.presets.precision import _load_pseudo_index_cached
        info = _load_pseudo_index_cached.cache_info()
        
        # hits should be 4 (first call is a miss, next 4 are hits)
        assert info.hits >= 4
        assert info.misses == 1
    
    def test_clear_cache_works(self):
        """Cache can be cleared."""
        from quantumvitas.presets.precision import _load_pseudo_index_cached
        
        clear_pseudo_index_cache()
        info = _load_pseudo_index_cached.cache_info()
        
        assert info.hits == 0
        assert info.misses == 0


# Legacy test compatibility
class TestLegacyPrecisionConfigs:
    """Tests for legacy PRECISION_CONFIGS compatibility."""
    
    def test_legacy_configs_exist(self):
        """Legacy PRECISION_CONFIGS mapping exists."""
        assert PrecisionOption.LOW in PRECISION_CONFIGS
        assert PrecisionOption.MED in PRECISION_CONFIGS
        assert PrecisionOption.HIGH in PRECISION_CONFIGS
    
    def test_legacy_config_has_expected_fields(self):
        """Legacy config has expected fields."""
        config = PRECISION_CONFIGS[PrecisionOption.MED]
        assert hasattr(config, 'k_density')
        assert hasattr(config, 'conv_thr')
        assert hasattr(config, 'cutoff_multiplier')
