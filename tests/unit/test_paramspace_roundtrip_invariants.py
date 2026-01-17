"""
Constitution-grade roundtrip tests for ParamSpace.

Invariant: apply(preset) → detect() == preset

This test suite systematically verifies roundtrip behavior for ALL dimensions
with explicit engine coverage.
"""

import pytest

from quantumvitas.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    PrecisionOption,
    ConvergenceOption,
    CUSTOM,
)
from tests.utils.preset_helpers import (
    apply_and_detect_roundtrip,
    build_test_step_yaml,
    is_pyscf_available,
    is_orca_available,
    _apply_patch_to_yaml,
)


class TestRoundtripInvariants:
    """
    Constitution-grade roundtrip tests.
    
    Invariant: apply(preset) → detect() == preset
    """
    
    # --- Magnetism ---
    
    def test_roundtrip_magnetism_nm(self):
        """NONMAGNETIC: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "magnetism",
            MagnetismOption.NONMAGNETIC,
            "scf",
            step_yaml,
        )
        assert detected == MagnetismOption.NONMAGNETIC, \
            f"Roundtrip failed: NONMAGNETIC → {detected}"
    
    def test_roundtrip_magnetism_col(self):
        """COLLINEAR_LSDA: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "magnetism",
            MagnetismOption.COLLINEAR_LSDA,
            "scf",
            step_yaml,
        )
        assert detected == MagnetismOption.COLLINEAR_LSDA, \
            f"Roundtrip failed: COLLINEAR_LSDA → {detected}"
    
    def test_roundtrip_magnetism_nc(self):
        """NONCOLLINEAR: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "magnetism",
            MagnetismOption.NONCOLLINEAR,
            "scf",
            step_yaml,
        )
        assert detected == MagnetismOption.NONCOLLINEAR, \
            f"Roundtrip failed: NONCOLLINEAR → {detected}"
    
    def test_roundtrip_magnetism_soc(self):
        """NONCOLLINEAR_SOC: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "magnetism",
            MagnetismOption.NONCOLLINEAR_SOC,
            "scf",
            step_yaml,
        )
        assert detected == MagnetismOption.NONCOLLINEAR_SOC, \
            f"Roundtrip failed: NONCOLLINEAR_SOC → {detected}"
    
    # --- OccupationsScheme ---
    
    def test_roundtrip_occupations_fixed(self):
        """FIXED: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "occupations_scheme",
            OccupationsSchemeOption.FIXED,
            "scf",
            step_yaml,
        )
        assert detected == OccupationsSchemeOption.FIXED, \
            f"Roundtrip failed: FIXED → {detected}"
    
    def test_roundtrip_occupations_smearing(self):
        """SMEARING_GAUSSIAN: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "occupations_scheme",
            OccupationsSchemeOption.SMEARING_GAUSSIAN,
            "scf",
            step_yaml,
        )
        assert detected == OccupationsSchemeOption.SMEARING_GAUSSIAN, \
            f"Roundtrip failed: SMEARING_GAUSSIAN → {detected}"
    
    def test_roundtrip_occupations_tetrahedra(self):
        """TETRAHEDRA: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "occupations_scheme",
            OccupationsSchemeOption.TETRAHEDRA,
            "scf",
            step_yaml,
        )
        assert detected == OccupationsSchemeOption.TETRAHEDRA, \
            f"Roundtrip failed: TETRAHEDRA → {detected}"
    
    # --- Precision (QE) ---
    
    def test_roundtrip_precision_low_scf(self):
        """Precision LOW on scf: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        # Precision requires context (lattice, base cutoffs)
        # Use Si lattice for testing
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        precision_context = {
            "lattice_matrix": lattice,
            "base_ecutwfc": base_ecutwfc,
            "base_ecutrho": base_ecutrho,
        }
        detected = apply_and_detect_roundtrip(
            "precision",
            PrecisionOption.LOW,
            "scf",
            step_yaml,
            precision_context=precision_context,
        )
        assert detected == PrecisionOption.LOW, \
            f"Roundtrip failed: LOW → {detected}"
    
    def test_roundtrip_precision_med_scf(self):
        """Precision MED on scf: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        precision_context = {
            "lattice_matrix": lattice,
            "base_ecutwfc": base_ecutwfc,
            "base_ecutrho": base_ecutrho,
        }
        detected = apply_and_detect_roundtrip(
            "precision",
            PrecisionOption.MED,
            "scf",
            step_yaml,
            precision_context=precision_context,
        )
        assert detected == PrecisionOption.MED, \
            f"Roundtrip failed: MED → {detected}"
    
    def test_roundtrip_precision_high_scf(self):
        """Precision HIGH on scf: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        precision_context = {
            "lattice_matrix": lattice,
            "base_ecutwfc": base_ecutwfc,
            "base_ecutrho": base_ecutrho,
        }
        detected = apply_and_detect_roundtrip(
            "precision",
            PrecisionOption.HIGH,
            "scf",
            step_yaml,
            precision_context=precision_context,
        )
        assert detected == PrecisionOption.HIGH, \
            f"Roundtrip failed: HIGH → {detected}"
    
    def test_roundtrip_precision_med_nscf(self):
        """Precision MED on nscf: apply → detect → same option."""
        step_yaml = build_test_step_yaml("nscf")
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        precision_context = {
            "lattice_matrix": lattice,
            "base_ecutwfc": base_ecutwfc,
            "base_ecutrho": base_ecutrho,
        }
        detected = apply_and_detect_roundtrip(
            "precision",
            PrecisionOption.MED,
            "nscf",
            step_yaml,
            precision_context=precision_context,
        )
        assert detected == PrecisionOption.MED, \
            f"Roundtrip failed: MED (nscf) → {detected}"
    
    # --- Convergence ---
    
    def test_roundtrip_convergence_fast(self):
        """Convergence FAST: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "convergence",
            ConvergenceOption.FAST,
            "scf",
            step_yaml,
        )
        assert detected == ConvergenceOption.FAST, \
            f"Roundtrip failed: FAST → {detected}"
    
    def test_roundtrip_convergence_normal(self):
        """Convergence NORMAL: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "convergence",
            ConvergenceOption.NORMAL,
            "scf",
            step_yaml,
        )
        assert detected == ConvergenceOption.NORMAL, \
            f"Roundtrip failed: NORMAL → {detected}"
    
    def test_roundtrip_convergence_robust(self):
        """Convergence ROBUST: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "convergence",
            ConvergenceOption.ROBUST,
            "scf",
            step_yaml,
        )
        assert detected == ConvergenceOption.ROBUST, \
            f"Roundtrip failed: ROBUST → {detected}"
    
    def test_roundtrip_convergence_very_robust(self):
        """Convergence VERY_ROBUST: apply → detect → same option."""
        step_yaml = build_test_step_yaml("scf")
        detected = apply_and_detect_roundtrip(
            "convergence",
            ConvergenceOption.VERY_ROBUST,
            "scf",
            step_yaml,
        )
        assert detected == ConvergenceOption.VERY_ROBUST, \
            f"Roundtrip failed: VERY_ROBUST → {detected}"
    
    # --- QC Precision (PySCF) ---
    
    @pytest.mark.skipif(not is_pyscf_available(), reason="PySCF not installed")
    def test_roundtrip_qc_precision_low_pyscf(self):
        """QC Precision LOW on PySCF scf: apply → detect → same option."""
        # For qc_precision, use full patch (includes all keys: scf, dft, engine.orca.scf)
        # Detection needs all keys to match correctly
        from quantumvitas.presets.qc_precision import get_qc_precision_paramspace
        from quantumvitas.presets.paramspace import compile_profile_patch
        from quantumvitas.presets.variants_registry import detect_dimension_for_step
        
        space = get_qc_precision_paramspace()
        step_yaml = {}
        patch, deletions = compile_profile_patch(space, "LOW", step_yaml, explicit_defaults=True)
        
        # Apply patch
        modified_yaml = _apply_patch_to_yaml(step_yaml, patch, deletions)
        
        # Detect
        detected = detect_dimension_for_step("qc_precision", "scf", modified_yaml)
        assert detected == PrecisionOption.LOW, \
            f"Roundtrip failed: LOW (PySCF) → {detected}"
    
    @pytest.mark.skipif(not is_pyscf_available(), reason="PySCF not installed")
    def test_roundtrip_qc_precision_med_pyscf(self):
        """QC Precision MED on PySCF scf: apply → detect → same option."""
        from quantumvitas.presets.qc_precision import get_qc_precision_paramspace
        from quantumvitas.presets.paramspace import compile_profile_patch
        from quantumvitas.presets.variants_registry import detect_dimension_for_step
        
        space = get_qc_precision_paramspace()
        step_yaml = {}
        patch, deletions = compile_profile_patch(space, "MED", step_yaml, explicit_defaults=True)
        modified_yaml = _apply_patch_to_yaml(step_yaml, patch, deletions)
        detected = detect_dimension_for_step("qc_precision", "scf", modified_yaml)
        assert detected == PrecisionOption.MED, \
            f"Roundtrip failed: MED (PySCF) → {detected}"
    
    @pytest.mark.skipif(not is_pyscf_available(), reason="PySCF not installed")
    def test_roundtrip_qc_precision_high_pyscf(self):
        """QC Precision HIGH on PySCF scf: apply → detect → same option."""
        from quantumvitas.presets.qc_precision import get_qc_precision_paramspace
        from quantumvitas.presets.paramspace import compile_profile_patch
        from quantumvitas.presets.variants_registry import detect_dimension_for_step
        
        space = get_qc_precision_paramspace()
        step_yaml = {}
        patch, deletions = compile_profile_patch(space, "HIGH", step_yaml, explicit_defaults=True)
        modified_yaml = _apply_patch_to_yaml(step_yaml, patch, deletions)
        detected = detect_dimension_for_step("qc_precision", "scf", modified_yaml)
        assert detected == PrecisionOption.HIGH, \
            f"Roundtrip failed: HIGH (PySCF) → {detected}"
    
    # --- QC Precision (ORCA) - skip if binary not available ---
    
    @pytest.mark.skipif(not is_orca_available(), reason="ORCA not in registry")
    def test_roundtrip_qc_precision_low_orca(self):
        """QC Precision LOW on ORCA scf: apply → detect → same option."""
        from quantumvitas.presets.qc_precision import get_qc_precision_paramspace
        from quantumvitas.presets.paramspace import compile_profile_patch
        from quantumvitas.presets.variants_registry import detect_dimension_for_step
        
        space = get_qc_precision_paramspace()
        step_yaml = {}
        patch, deletions = compile_profile_patch(space, "LOW", step_yaml, explicit_defaults=True)
        modified_yaml = _apply_patch_to_yaml(step_yaml, patch, deletions)
        detected = detect_dimension_for_step("qc_precision", "scf", modified_yaml)
        assert detected == PrecisionOption.LOW, \
            f"Roundtrip failed: LOW (ORCA) → {detected}"
    
    @pytest.mark.skipif(not is_orca_available(), reason="ORCA not in registry")
    def test_roundtrip_qc_precision_med_orca(self):
        """QC Precision MED on ORCA scf: apply → detect → same option."""
        from quantumvitas.presets.qc_precision import get_qc_precision_paramspace
        from quantumvitas.presets.paramspace import compile_profile_patch
        from quantumvitas.presets.variants_registry import detect_dimension_for_step
        
        space = get_qc_precision_paramspace()
        step_yaml = {}
        patch, deletions = compile_profile_patch(space, "MED", step_yaml, explicit_defaults=True)
        modified_yaml = _apply_patch_to_yaml(step_yaml, patch, deletions)
        detected = detect_dimension_for_step("qc_precision", "scf", modified_yaml)
        assert detected == PrecisionOption.MED, \
            f"Roundtrip failed: MED (ORCA) → {detected}"
    
    @pytest.mark.skipif(not is_orca_available(), reason="ORCA not in registry")
    def test_roundtrip_qc_precision_high_orca(self):
        """QC Precision HIGH on ORCA scf: apply → detect → same option."""
        from quantumvitas.presets.qc_precision import get_qc_precision_paramspace
        from quantumvitas.presets.paramspace import compile_profile_patch
        from quantumvitas.presets.variants_registry import detect_dimension_for_step
        
        space = get_qc_precision_paramspace()
        step_yaml = {}
        patch, deletions = compile_profile_patch(space, "HIGH", step_yaml, explicit_defaults=True)
        modified_yaml = _apply_patch_to_yaml(step_yaml, patch, deletions)
        detected = detect_dimension_for_step("qc_precision", "scf", modified_yaml)
        assert detected == PrecisionOption.HIGH, \
            f"Roundtrip failed: HIGH (ORCA) → {detected}"

