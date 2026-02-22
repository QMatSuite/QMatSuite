"""
Constitution-grade negative tests for ParamSpace.

Invariant: mutate ANY owned key → detect() == CUSTOM

This test suite verifies that any mutation of an owned key causes
CUSTOM detection, ensuring strict reversibility.
"""

import pytest

from qmatsuite.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    PrecisionOption,
    ConvergenceOption,
    CUSTOM,
)
from tests.utils.preset_helpers import (
    apply_and_detect_roundtrip,
    apply_preset_to_yaml,
    build_test_step_yaml,
)


class TestNegativeInvariants:
    """
    Constitution-grade negative tests.
    
    Invariant: mutate ANY owned key → detect() == CUSTOM
    """
    
    # --- Magnetism ---
    
    def test_negative_magnetism_mutate_nspin(self):
        """Mutate nspin from COL (expects 2) to 3 → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        # Apply COL preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "magnetism",
            MagnetismOption.COLLINEAR_LSDA,
            "scf",
            step_yaml,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("magnetism", "scf", modified_yaml)
        assert detected == MagnetismOption.COLLINEAR_LSDA
        
        # Now mutate nspin
        modified_yaml["SYSTEM"]["nspin"] = 3  # Should be 2 for COL
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "magnetism",
            "scf",
            modified_yaml,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating nspin, got {detected_after_mutation}"
    
    def test_negative_magnetism_mutate_noncolin(self):
        """Mutate noncolin from NC_CANONICAL: add nspin=2 (contradiction) → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        # Apply NONCOLLINEAR preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "magnetism",
            MagnetismOption.NONCOLLINEAR,
            "scf",
            step_yaml,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("magnetism", "scf", modified_yaml)
        assert detected == MagnetismOption.NONCOLLINEAR
        
        # Now add nspin=2 (contradiction: noncolin=True with nspin=2)
        # This should cause CUSTOM because it violates physics constraints
        modified_yaml["SYSTEM"]["nspin"] = 2  # Contradiction: noncolin=True but nspin=2
        
        # Detect again - should be CUSTOM (contradiction)
        detected_after_mutation = detect_dimension_for_step(
            "magnetism",
            "scf",
            modified_yaml,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after adding nspin=2 (contradiction), got {detected_after_mutation}"
    
    def test_negative_magnetism_mutate_lspinorb(self):
        """Mutate lspinorb from SOC: add nspin=2 (contradiction) → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        # Apply NONCOLLINEAR_SOC preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "magnetism",
            MagnetismOption.NONCOLLINEAR_SOC,
            "scf",
            step_yaml,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("magnetism", "scf", modified_yaml)
        assert detected == MagnetismOption.NONCOLLINEAR_SOC
        
        # Now add nspin=2 (contradiction: noncolin=True with nspin=2)
        # This should cause CUSTOM because it violates physics constraints
        modified_yaml["SYSTEM"]["nspin"] = 2  # Contradiction: noncolin=True but nspin=2
        
        # Detect again - should be CUSTOM (contradiction)
        detected_after_mutation = detect_dimension_for_step(
            "magnetism",
            "scf",
            modified_yaml,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after adding nspin=2 (contradiction), got {detected_after_mutation}"
    
    # --- OccupationsScheme ---
    
    def test_negative_occupations_mutate_occupations(self):
        """Mutate occupations from FIXED (expects "fixed") to "smearing" → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        # Apply FIXED preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "occupations_scheme",
            OccupationsSchemeOption.FIXED,
            "scf",
            step_yaml,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("occupations_scheme", "scf", modified_yaml)
        assert detected == OccupationsSchemeOption.FIXED
        
        # Now mutate occupations
        modified_yaml["SYSTEM"]["occupations"] = "smearing"  # Should be "fixed" for FIXED
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "occupations_scheme",
            "scf",
            modified_yaml,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating occupations, got {detected_after_mutation}"
    
    def test_negative_occupations_mutate_smearing(self):
        """Mutate smearing from SMEARING_GAUSSIAN to "mp" → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        # Apply SMEARING_GAUSSIAN preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "occupations_scheme",
            OccupationsSchemeOption.SMEARING_GAUSSIAN,
            "scf",
            step_yaml,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("occupations_scheme", "scf", modified_yaml)
        assert detected == OccupationsSchemeOption.SMEARING_GAUSSIAN
        
        # Now mutate smearing
        modified_yaml["SYSTEM"]["smearing"] = "mp"  # Should be "gaussian" for SMEARING_GAUSSIAN
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "occupations_scheme",
            "scf",
            modified_yaml,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating smearing, got {detected_after_mutation}"
    
    # --- Precision ---
    
    def test_negative_precision_mutate_ecutwfc(self):
        """Mutate ecutwfc from MED → +1 → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        precision_context = {
            "lattice_matrix": lattice,
            "base_ecutwfc": base_ecutwfc,
            "base_ecutrho": base_ecutrho,
        }
        # Apply MED preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "precision",
            PrecisionOption.MED,
            "scf",
            step_yaml,
            precision_context=precision_context,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("precision", "scf", modified_yaml, precision_context=precision_context)
        assert detected == PrecisionOption.MED
        
        # Now mutate ecutwfc (+1)
        original_ecutwfc = modified_yaml["SYSTEM"]["ecutwfc"]
        modified_yaml["SYSTEM"]["ecutwfc"] = original_ecutwfc + 1
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "precision",
            "scf",
            modified_yaml,
            precision_context=precision_context,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating ecutwfc, got {detected_after_mutation}"
    
    def test_negative_precision_mutate_ecutrho(self):
        """Mutate ecutrho from MED → +1 → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        precision_context = {
            "lattice_matrix": lattice,
            "base_ecutwfc": base_ecutwfc,
            "base_ecutrho": base_ecutrho,
        }
        # Apply MED preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "precision",
            PrecisionOption.MED,
            "scf",
            step_yaml,
            precision_context=precision_context,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("precision", "scf", modified_yaml, precision_context=precision_context)
        assert detected == PrecisionOption.MED
        
        # Now mutate ecutrho (+1)
        original_ecutrho = modified_yaml["SYSTEM"]["ecutrho"]
        modified_yaml["SYSTEM"]["ecutrho"] = original_ecutrho + 1
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "precision",
            "scf",
            modified_yaml,
            precision_context=precision_context,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating ecutrho, got {detected_after_mutation}"
    
    def test_negative_precision_mutate_conv_thr(self):
        """Mutate conv_thr from MED → 1e-5 → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        precision_context = {
            "lattice_matrix": lattice,
            "base_ecutwfc": base_ecutwfc,
            "base_ecutrho": base_ecutrho,
        }
        # Apply MED preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "precision",
            PrecisionOption.MED,
            "scf",
            step_yaml,
            precision_context=precision_context,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("precision", "scf", modified_yaml, precision_context=precision_context)
        assert detected == PrecisionOption.MED
        
        # Now mutate conv_thr
        modified_yaml["ELECTRONS"]["conv_thr"] = 1e-5  # Should be ~1e-8 for MED
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "precision",
            "scf",
            modified_yaml,
            precision_context=precision_context,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating conv_thr, got {detected_after_mutation}"
    
    def test_negative_precision_mutate_kpoints(self):
        """Mutate K_POINTS from MED → different mesh → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        base_ecutwfc, base_ecutrho = 30.0, 240.0
        precision_context = {
            "lattice_matrix": lattice,
            "base_ecutwfc": base_ecutwfc,
            "base_ecutrho": base_ecutrho,
        }
        # Apply MED preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "precision",
            PrecisionOption.MED,
            "scf",
            step_yaml,
            precision_context=precision_context,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("precision", "scf", modified_yaml, precision_context=precision_context)
        assert detected == PrecisionOption.MED
        
        # Now mutate K_POINTS mesh
        if "cards" in modified_yaml and "K_POINTS" in modified_yaml["cards"]:
            # Change mesh from [6,6,6] to [7,7,7]
            modified_yaml["cards"]["K_POINTS"]["data"] = [[7, 7, 7, 0, 0, 0]]
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "precision",
            "scf",
            modified_yaml,
            precision_context=precision_context,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating K_POINTS, got {detected_after_mutation}"
    
    # --- Convergence ---
    
    def test_negative_convergence_mutate_mixing_beta(self):
        """Mutate mixing_beta from NORMAL (expects 0.4) to 0.5 → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        # Apply NORMAL preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "convergence",
            ConvergenceOption.NORMAL,
            "scf",
            step_yaml,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("convergence", "scf", modified_yaml)
        assert detected == ConvergenceOption.NORMAL
        
        # Now mutate mixing_beta
        modified_yaml["ELECTRONS"]["mixing_beta"] = 0.5  # Should be 0.4 for NORMAL
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "convergence",
            "scf",
            modified_yaml,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating mixing_beta, got {detected_after_mutation}"
    
    def test_negative_convergence_mutate_electron_maxstep(self):
        """Mutate electron_maxstep from NORMAL (expects 150) to 200 → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        # Apply NORMAL preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "convergence",
            ConvergenceOption.NORMAL,
            "scf",
            step_yaml,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("convergence", "scf", modified_yaml)
        assert detected == ConvergenceOption.NORMAL
        
        # Now mutate electron_maxstep
        modified_yaml["ELECTRONS"]["electron_maxstep"] = 200  # Should be 150 for NORMAL
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "convergence",
            "scf",
            modified_yaml,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating electron_maxstep, got {detected_after_mutation}"
    
    def test_negative_convergence_mutate_mixing_mode(self):
        """Mutate mixing_mode from NORMAL (expects "plain") to "TF" → CUSTOM."""
        step_yaml = build_test_step_yaml("scf")
        # Apply NORMAL preset and get modified yaml
        modified_yaml = apply_preset_to_yaml(
            "convergence",
            ConvergenceOption.NORMAL,
            "scf",
            step_yaml,
        )
        
        # Verify initial detection
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step("convergence", "scf", modified_yaml)
        assert detected == ConvergenceOption.NORMAL
        
        # Now mutate mixing_mode
        modified_yaml["ELECTRONS"]["mixing_mode"] = "TF"  # Should be "plain" for NORMAL
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "convergence",
            "scf",
            modified_yaml,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating mixing_mode, got {detected_after_mutation}"
    
    # --- QC Precision ---
    
    def test_negative_qc_precision_mutate_conv_tol(self):
        """Mutate scf.conv_tol from MED (expects 1e-8) to 1e-7 → CUSTOM."""
        # For qc_precision, use full patch (includes all keys)
        from qmatsuite.presets.qc_precision import get_qc_precision_paramspace
        from qmatsuite.presets.paramspace import compile_profile_patch
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        from tests.utils.preset_helpers import _apply_patch_to_yaml
        
        space = get_qc_precision_paramspace()
        step_yaml = {}
        patch, deletions = compile_profile_patch(space, "MED", step_yaml, explicit_defaults=True)
        modified_yaml = _apply_patch_to_yaml(step_yaml, patch, deletions)
        
        # Verify initial detection
        detected = detect_dimension_for_step("qc_precision", "scf", modified_yaml)
        assert detected == PrecisionOption.MED
        
        # Now mutate conv_tol
        modified_yaml["scf"]["conv_tol"] = 1e-7  # Should be 1e-8 for MED
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "qc_precision",
            "scf",
            modified_yaml,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating conv_tol, got {detected_after_mutation}"
    
    def test_negative_qc_precision_mutate_max_cycle(self):
        """Mutate scf.max_cycle from MED (expects 100) to 150 → CUSTOM."""
        # For qc_precision, use full patch (includes all keys)
        from qmatsuite.presets.qc_precision import get_qc_precision_paramspace
        from qmatsuite.presets.paramspace import compile_profile_patch
        from qmatsuite.presets.variants_registry import detect_dimension_for_step
        from tests.utils.preset_helpers import _apply_patch_to_yaml
        
        space = get_qc_precision_paramspace()
        step_yaml = {}
        patch, deletions = compile_profile_patch(space, "MED", step_yaml, explicit_defaults=True)
        modified_yaml = _apply_patch_to_yaml(step_yaml, patch, deletions)
        
        # Verify initial detection
        detected = detect_dimension_for_step("qc_precision", "scf", modified_yaml)
        assert detected == PrecisionOption.MED
        
        # Now mutate max_cycle
        modified_yaml["scf"]["max_cycle"] = 150  # Should be 100 for MED
        
        # Detect again - should be CUSTOM
        detected_after_mutation = detect_dimension_for_step(
            "qc_precision",
            "scf",
            modified_yaml,
        )
        assert detected_after_mutation == CUSTOM, \
            f"Expected CUSTOM after mutating max_cycle, got {detected_after_mutation}"

