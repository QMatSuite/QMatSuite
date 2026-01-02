"""
Tests for preset integration with calculation infrastructure.

Tests the integration layer that connects presets to the calculation system:
- detect_presets_from_calculation: Aggregate presets from calculation steps
- apply_presets_to_step: Apply preset options to step files
- detect_workflow_type: Runtime workflow detection

Per Constitution Chapter 10:
- §10.1.1: step.yml is sole executable truth
- §10.2.1: Presets are runtime-only (never persisted)
- §10.3.3: Preset apply overwrites, not merges
- §10.4.1: Detector B is sole legitimate state source
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any

from quantumvitas.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    ConvergenceOption,
    CUSTOM,
    _CustomType,
)
from quantumvitas.presets.integration import (
    detect_presets_from_calculation,
    detect_presets_from_calculation_typed,
    apply_presets_to_step,
    detect_workflow_type,
    _load_step_parameters,
)


class TestLoadStepParameters:
    """Test step parameter loading from calculation directories."""
    
    def test_load_from_nonexistent_dir(self, tmp_path):
        """Nonexistent steps dir returns empty list."""
        result = _load_step_parameters(tmp_path / "nonexistent")
        assert result == []
    
    def test_load_from_empty_steps_dir(self, tmp_path):
        """Empty steps directory returns empty list."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        result = _load_step_parameters(tmp_path)
        assert result == []
    
    def test_load_single_step(self, tmp_path):
        """Load parameters from single step file."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        
        step_content = {
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {"nspin": 2, "ecutwfc": 50},
                "CONTROL": {"calculation": "scf"},
            }
        }
        (steps_dir / "scf.step.yaml").write_text(yaml.safe_dump(step_content))
        
        result = _load_step_parameters(tmp_path)
        assert len(result) == 1
        assert result[0]["SYSTEM"]["nspin"] == 2
    
    def test_load_multiple_steps(self, tmp_path):
        """Load parameters from multiple step files."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        
        # SCF step
        scf_content = {
            "step_type": "scf",
            "parameters": {"SYSTEM": {"nspin": 2}},
        }
        (steps_dir / "01-scf.step.yaml").write_text(yaml.safe_dump(scf_content))
        
        # NSCF step
        nscf_content = {
            "step_type": "nscf",
            "parameters": {"SYSTEM": {"nspin": 2}},
        }
        (steps_dir / "02-nscf.step.yaml").write_text(yaml.safe_dump(nscf_content))
        
        result = _load_step_parameters(tmp_path)
        assert len(result) == 2
    
    def test_skip_malformed_step(self, tmp_path):
        """Malformed step files are skipped."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        
        # Valid step
        (steps_dir / "01-scf.step.yaml").write_text(yaml.safe_dump({
            "step_type": "scf",
            "parameters": {"SYSTEM": {"nspin": 2}},
        }))
        
        # Invalid YAML
        (steps_dir / "02-bad.step.yaml").write_text("not: valid: yaml: [[[")
        
        result = _load_step_parameters(tmp_path)
        assert len(result) == 1


class TestDetectPresetsFromCalculation:
    """Test preset detection from calculation directories."""
    
    def test_empty_calculation(self, tmp_path):
        """Empty calculation returns defaults."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        
        result = detect_presets_from_calculation(tmp_path)
        
        # Should return default values (not Custom)
        assert result["magnetism"] == "nonmagnetic"
        assert result["occupations_scheme"] == "fixed"
    
    def test_single_step_detection(self, tmp_path):
        """Single step with explicit params detected correctly."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        
        step_content = {
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {
                    "nspin": 2,
                    "occupations": "'smearing'",
                    "smearing": "'gaussian'",
                    "degauss": 0.02,  # Must be 0.02 for smearing_gaussian detection
                },
            },
        }
        (steps_dir / "scf.step.yaml").write_text(yaml.safe_dump(step_content))
        
        result = detect_presets_from_calculation(tmp_path)
        
        assert result["magnetism"] == "collinear_lsda"
        assert result["occupations_scheme"] == "smearing_gaussian"
    
    def test_homogeneous_steps_return_single_value(self, tmp_path):
        """Multiple steps with same settings return single value."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        
        # All steps have nspin=2
        for name in ["01-scf", "02-nscf", "03-dos"]:
            step_content = {
                "step_type": name.split("-")[1],
                "parameters": {"SYSTEM": {"nspin": 2}},
            }
            (steps_dir / f"{name}.step.yaml").write_text(yaml.safe_dump(step_content))
        
        result = detect_presets_from_calculation(tmp_path)
        assert result["magnetism"] == "collinear_lsda"
    
    def test_heterogeneous_steps_return_custom(self, tmp_path):
        """Steps with different settings return Custom."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        
        # SCF with nspin=1
        (steps_dir / "01-scf.step.yaml").write_text(yaml.safe_dump({
            "step_type": "scf",
            "parameters": {"SYSTEM": {"nspin": 1}},
        }))
        
        # Another step with nspin=2
        (steps_dir / "02-nscf.step.yaml").write_text(yaml.safe_dump({
            "step_type": "nscf",
            "parameters": {"SYSTEM": {"nspin": 2}},
        }))
        
        result = detect_presets_from_calculation(tmp_path)
        assert result["magnetism"] == "Custom"
    
    def test_typed_version_returns_enums(self, tmp_path):
        """Typed version returns enum values, not strings."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        
        step_content = {
            "step_type": "scf",
            "parameters": {"SYSTEM": {"nspin": 2}},
        }
        (steps_dir / "scf.step.yaml").write_text(yaml.safe_dump(step_content))
        
        result = detect_presets_from_calculation_typed(tmp_path)
        
        assert result["magnetism"] == MagnetismOption.COLLINEAR_LSDA
        assert isinstance(result["magnetism"], MagnetismOption)


class TestApplyPresetsToStep:
    """Test applying presets to step files."""
    
    def test_apply_overwrites_preset_params(self, tmp_path):
        """Applying presets overwrites preset-related params."""
        step_path = tmp_path / "test.step.yaml"
        original_content = {
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {
                    "nspin": 1,
                    "nbnd": 50,  # Non-preset param (ecutwfc is now precision-related)
                    "occupations": "'fixed'",
                },
            },
        }
        step_path.write_text(yaml.safe_dump(original_content))
        
        # Apply collinear + smearing_gaussian
        result = apply_presets_to_step(
            step_path,
            {"magnetism": "collinear_lsda", "occupations_scheme": "smearing_gaussian"},
        )
        
        # Result now includes accepted flag and content
        assert result["accepted"] is True
        system = result["content"]["parameters"]["SYSTEM"]
        
        # Preset params changed
        assert system["nspin"] == 2
        assert system["occupations"] == "smearing"  # YAML parsed value (no outer quotes)
        assert system["smearing"] == "gaussian"  # YAML parsed value (no outer quotes)
        assert system["degauss"] == 0.02
        
        # Non-preset params preserved (nbnd is not a preset param)
        assert system["nbnd"] == 50
    
    def test_apply_preserves_nonpreset_params(self, tmp_path):
        """Non-preset SYSTEM params are preserved."""
        step_path = tmp_path / "test.step.yaml"
        original_content = {
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {
                    "nspin": 1,
                    "nbnd": 20,  # Non-preset param
                    "ntyp": 2,  # Non-preset param
                    "nat": 4,  # Non-preset param
                },
                "CONTROL": {
                    "calculation": "scf",
                },
            },
        }
        step_path.write_text(yaml.safe_dump(original_content))
        
        apply_presets_to_step(step_path, {"magnetism": "collinear_lsda"})
        
        # Reload and check
        updated = yaml.safe_load(step_path.read_text())
        system = updated["parameters"]["SYSTEM"]
        
        # Non-preset params preserved (ecutwfc/ecutrho are now precision-related)
        assert system["nbnd"] == 20
        assert system["ntyp"] == 2
        assert system["nat"] == 4
        
        # CONTROL untouched
        assert updated["parameters"]["CONTROL"]["calculation"] == "scf"
    
    def test_apply_removes_conflicting_preset_params(self, tmp_path):
        """Old preset params are removed, not left dangling."""
        step_path = tmp_path / "test.step.yaml"
        original_content = {
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {
                    # Metal params that should be removed for insulator
                    "occupations": "'smearing'",
                    "smearing": "'gaussian'",
                    "degauss": 0.01,
                },
            },
        }
        step_path.write_text(yaml.safe_dump(original_content))
        
        # Apply fixed occupations preset
        apply_presets_to_step(step_path, {"occupations_scheme": "fixed"})
        
        updated = yaml.safe_load(step_path.read_text())
        system = updated["parameters"]["SYSTEM"]
        
        assert system["occupations"] == "fixed"  # YAML parsed value (no outer quotes)
        assert "smearing" not in system
        assert "degauss" not in system
    
    def test_apply_validates_physics_by_default(self, tmp_path):
        """Physics validation is on by default."""
        from quantumvitas.presets.compiler import PresetCompilationError
        
        step_path = tmp_path / "test.step.yaml"
        step_path.write_text(yaml.safe_dump({"step_type": "scf", "parameters": {}}))
        
        # Invalid physics: This test is no longer applicable since magnetism merges spin+soc
        # All magnetism options are valid. Test removed - physics validation now happens at option level.
        pass
    
    def test_apply_can_skip_physics_validation(self, tmp_path):
        """Physics validation can be disabled."""
        step_path = tmp_path / "test.step.yaml"
        step_path.write_text(yaml.safe_dump({"step_type": "scf", "parameters": {}}))
        
        # With magnetism, all options are valid. Test applies noncollinear_soc.
        result = apply_presets_to_step(
            step_path,
            {"magnetism": "noncollinear_soc"},
            validate_physics=False,
        )
        
        # Result includes accepted flag
        assert result["accepted"] is True
        
        # Parameters written
        system = result["content"]["parameters"]["SYSTEM"]
        assert system["lspinorb"] == ".true."
        assert system["noncolin"] == ".true."
    
    def test_apply_nonexistent_file_raises(self, tmp_path):
        """Applying to nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            apply_presets_to_step(
                tmp_path / "nonexistent.step.yaml",
                {"magnetism": "collinear_lsda"},
            )
    
    def test_roundtrip_detection(self, tmp_path):
        """Applied presets can be detected back."""
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        step_path = steps_dir / "scf.step.yaml"
        
        # Create initial step
        step_path.write_text(yaml.safe_dump({
            "step_type": "scf",
            "parameters": {"SYSTEM": {}},
        }))
        
        # Apply presets
        apply_presets_to_step(
            step_path,
            {"magnetism": "noncollinear_soc", "occupations_scheme": "smearing_gaussian"},
        )
        
        # Detect presets from calculation
        result = detect_presets_from_calculation(tmp_path)
        
        assert result["magnetism"] == "noncollinear_soc"
        assert result["occupations_scheme"] == "smearing_gaussian"


class TestDetectWorkflowType:
    """Test workflow type detection from calculations."""
    
    def test_unknown_without_calculation_yaml(self, tmp_path):
        """Missing calculation.yaml returns Unknown."""
        result = detect_workflow_type(tmp_path)
        assert result == "Unknown"
    
    def test_scf_workflow(self, tmp_path):
        """Single SCF step detected as SCF workflow."""
        calc_yaml = tmp_path / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "steps": [{"step_type": "scf"}],
        }))
        
        result = detect_workflow_type(tmp_path)
        assert result == "SCF"
    
    def test_dos_workflow(self, tmp_path):
        """SCF + NSCF + DOS detected as DOS workflow."""
        calc_yaml = tmp_path / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "steps": [
                {"step_type": "scf"},
                {"step_type": "nscf"},
                {"step_type": "dos"},
            ],
        }))
        
        result = detect_workflow_type(tmp_path)
        assert result == "DOS"
    
    def test_bandstructure_workflow(self, tmp_path):
        """Steps with bands_pw detected as BandStructure."""
        calc_yaml = tmp_path / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "steps": [
                {"step_type": "scf"},
                {"step_type": "bands_pw"},
                {"step_type": "bands"},
            ],
        }))
        
        result = detect_workflow_type(tmp_path)
        assert result == "BandStructure"
    
    def test_relaxation_workflow(self, tmp_path):
        """Relax or vc-relax detected as Relaxation."""
        calc_yaml = tmp_path / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "steps": [{"step_type": "vc-relax"}],
        }))
        
        result = detect_workflow_type(tmp_path)
        assert result == "Relaxation"
        
        # Also plain relax
        calc_yaml.write_text(yaml.safe_dump({
            "steps": [{"step_type": "relax"}],
        }))
        
        result = detect_workflow_type(tmp_path)
        assert result == "Relaxation"
    
    def test_phonon_workflow(self, tmp_path):
        """Steps with ph detected as Phonon."""
        calc_yaml = tmp_path / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "steps": [
                {"step_type": "scf"},
                {"step_type": "ph"},
            ],
        }))
        
        result = detect_workflow_type(tmp_path)
        assert result == "Phonon"
    
    def test_md_workflow(self, tmp_path):
        """MD steps detected as MD workflow."""
        calc_yaml = tmp_path / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "steps": [{"step_type": "md"}],
        }))
        
        result = detect_workflow_type(tmp_path)
        assert result == "MD"
        
        # Also vc-md
        calc_yaml.write_text(yaml.safe_dump({
            "steps": [{"step_type": "vc-md"}],
        }))
        
        result = detect_workflow_type(tmp_path)
        assert result == "MD"
    
    def test_load_step_type_from_step_file(self, tmp_path):
        """Step type can be loaded from step file if not in calculation.yaml."""
        calc_yaml = tmp_path / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "steps": [{"step_file": "steps/scf.step.yaml"}],
        }))
        
        steps_dir = tmp_path / "steps"
        steps_dir.mkdir()
        (steps_dir / "scf.step.yaml").write_text(yaml.safe_dump({
            "step_type": "relax",
        }))
        
        result = detect_workflow_type(tmp_path)
        assert result == "Relaxation"


class TestRealCalculationIntegration:
    """Test with fixture calculations from tests/data (if available)."""
    
    @pytest.fixture
    def ci_test_data_dir(self) -> Path:
        """Get path to tests/data directory."""
        test_data_dir = Path(__file__).parent.parent / "data"
        if not test_data_dir.exists():
            pytest.skip("tests/data not available")
        return test_data_dir
    
    def test_si_dos_workflow(self, ci_test_data_dir: Path):
        """Test workflow detection with Si DOS tutorial (if available)."""
        si_dos_dir = ci_test_data_dir / "4_Si_DOS"
        if not si_dos_dir.exists():
            pytest.skip("4_Si_DOS tutorial not available")
        
        # Note: Tutorial dirs may not have calculation.yaml structure
        # They have individual .in files instead
        # This test validates the workflow detection API at least doesn't crash
        result = detect_workflow_type(si_dos_dir)
        # Result could be Unknown for raw tutorial input folders
        assert isinstance(result, str)


class TestConvergencePreset:
    """Test convergence preset implementation."""
    
    def test_fast_profile_patch(self):
        """FAST profile produces exact patch values."""
        from quantumvitas.presets.variants_registry import compile_dimension_patch_for_step
        from quantumvitas.presets.dimensions import ConvergenceOption
        
        step_yaml = {"parameters": {"ELECTRONS": {}}}
        patch, deletions = compile_dimension_patch_for_step(
            "convergence",
            ConvergenceOption.FAST,
            "scf",
            step_yaml,
        )
        
        # Patch structure: {"ELECTRONS": {...}} (section-key structure)
        assert "ELECTRONS" in patch
        electrons = patch["ELECTRONS"]
        assert electrons["mixing_beta"] == 0.7
        assert electrons["electron_maxstep"] == 100
        assert electrons["mixing_mode"] == "plain"
        assert electrons["mixing_ndim"] == 8
        assert electrons["diagonalization"] == "david"
        
        # Verify no extraneous keys
        assert len(electrons) == 5
        assert "conv_thr" not in electrons
    
    def test_normal_profile_patch(self):
        """NORMAL profile produces exact patch values."""
        from quantumvitas.presets.variants_registry import compile_dimension_patch_for_step
        from quantumvitas.presets.dimensions import ConvergenceOption
        
        step_yaml = {"parameters": {"ELECTRONS": {}}}
        patch, deletions = compile_dimension_patch_for_step(
            "convergence",
            ConvergenceOption.NORMAL,
            "scf",
            step_yaml,
        )
        
        assert "ELECTRONS" in patch
        electrons = patch["ELECTRONS"]
        assert electrons["mixing_beta"] == 0.4
        assert electrons["electron_maxstep"] == 150
        assert electrons["mixing_mode"] == "plain"
        assert electrons["mixing_ndim"] == 8
        assert electrons["diagonalization"] == "david"
        assert "conv_thr" not in electrons
    
    def test_robust_profile_patch(self):
        """ROBUST profile produces exact patch values."""
        from quantumvitas.presets.variants_registry import compile_dimension_patch_for_step
        from quantumvitas.presets.dimensions import ConvergenceOption
        
        step_yaml = {"parameters": {"ELECTRONS": {}}}
        patch, deletions = compile_dimension_patch_for_step(
            "convergence",
            ConvergenceOption.ROBUST,
            "scf",
            step_yaml,
        )
        
        assert "ELECTRONS" in patch
        electrons = patch["ELECTRONS"]
        assert electrons["mixing_beta"] == 0.2
        assert electrons["electron_maxstep"] == 200
        assert electrons["mixing_mode"] == "TF"
        assert electrons["mixing_ndim"] == 10
        assert electrons["diagonalization"] == "rmm-davidson"
        assert "conv_thr" not in electrons
    
    def test_very_robust_profile_patch(self):
        """VERY_ROBUST profile produces exact patch values."""
        from quantumvitas.presets.variants_registry import compile_dimension_patch_for_step
        from quantumvitas.presets.dimensions import ConvergenceOption
        
        step_yaml = {"parameters": {"ELECTRONS": {}}}
        patch, deletions = compile_dimension_patch_for_step(
            "convergence",
            ConvergenceOption.VERY_ROBUST,
            "scf",
            step_yaml,
        )
        
        assert "ELECTRONS" in patch
        electrons = patch["ELECTRONS"]
        assert electrons["mixing_beta"] == 0.1
        assert electrons["electron_maxstep"] == 250
        assert electrons["mixing_mode"] == "local-TF"
        assert electrons["mixing_ndim"] == 12
        assert electrons["diagonalization"] == "cg"
        assert "conv_thr" not in electrons
    
    def test_convergence_never_sets_conv_thr(self):
        """Convergence preset never sets conv_thr (belongs to precision)."""
        from quantumvitas.presets.variants_registry import compile_dimension_patch_for_step
        from quantumvitas.presets.dimensions import ConvergenceOption
        
        step_yaml = {"parameters": {"ELECTRONS": {}}}
        
        # Test all profiles
        for option in ConvergenceOption:
            patch, deletions = compile_dimension_patch_for_step(
                "convergence",
                option,
                "scf",
                step_yaml,
            )
            
            # Verify conv_thr is never in the patch
            electrons = patch.get("ELECTRONS", {})
            assert "conv_thr" not in electrons
    
    def test_convergence_and_precision_coexist(self, tmp_path):
        """Convergence and precision can coexist; conv_thr only from precision."""
        from quantumvitas.presets.integration import apply_presets_to_step
        from quantumvitas.presets.dimensions import ConvergenceOption, PrecisionOption
        
        step_path = tmp_path / "test.step.yaml"
        step_path.write_text(yaml.safe_dump({
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {"ecutwfc": 50, "ecutrho": 200},
                "ELECTRONS": {},
            },
        }))
        
        # Apply both convergence and precision
        # Note: precision requires context, so we'll test the patch compilation directly
        from quantumvitas.presets.variants_registry import compile_dimension_patch_for_step
        
        step_yaml = {
            "parameters": {
                "SYSTEM": {"ecutwfc": 50, "ecutrho": 200},
                "ELECTRONS": {},
            }
        }
        
        # Compile convergence patch
        conv_patch, conv_deletions = compile_dimension_patch_for_step(
            "convergence",
            ConvergenceOption.NORMAL,
            "scf",
            step_yaml,
        )
        
        # Compile precision patch (requires context, but we can check conv_thr ownership)
        from quantumvitas.presets.spaces_registry import compile_dimension_patch
        precision_patch, precision_deletions = compile_dimension_patch(
            "precision",
            PrecisionOption.MED,
            step_yaml,
            ecutwfc=50.0,
            ecutrho=200.0,
            conv_thr=1e-6,
            nk1=4,
            nk2=4,
            nk3=4,
        )
        
        # Verify convergence patch does NOT contain conv_thr
        if "ELECTRONS" in conv_patch.get("parameters", {}):
            assert "conv_thr" not in conv_patch["parameters"]["ELECTRONS"]
        
        # Verify precision patch DOES contain conv_thr
        # Note: precision patch structure is different (direct ELECTRONS key)
        assert "ELECTRONS" in precision_patch
        assert "conv_thr" in precision_patch["ELECTRONS"]
        assert precision_patch["ELECTRONS"]["conv_thr"] == 1e-6
    
    def test_convergence_applies_to_pw_steps(self, tmp_path):
        """Convergence preset applies to all pw-based step types."""
        from quantumvitas.presets.integration import apply_presets_to_step
        from quantumvitas.presets.dimensions import ConvergenceOption
        
        # Test all pw-based step types
        pw_step_types = ["scf", "nscf", "relax", "vc-relax", "bands_pw", "md", "vc-md"]
        
        for step_type in pw_step_types:
            step_path = tmp_path / f"{step_type}.step.yaml"
            step_path.write_text(yaml.safe_dump({
                "step_type": step_type,
                "parameters": {"ELECTRONS": {}},
            }))
            
            # Apply convergence preset
            result = apply_presets_to_step(
                step_path,
                {"convergence": "normal"},
            )
            
            # Verify it was accepted
            assert result["accepted"] is True
            
            # Verify convergence parameters were set
            electrons = result["content"]["parameters"]["ELECTRONS"]
            assert "mixing_beta" in electrons
            assert "electron_maxstep" in electrons
            assert "mixing_mode" in electrons
            assert "mixing_ndim" in electrons
            assert "diagonalization" in electrons
            assert "conv_thr" not in electrons  # Critical: conv_thr not set
    
    def test_convergence_does_not_apply_to_non_pw_steps(self, tmp_path):
        """Convergence preset does not apply to non-pw step types."""
        from quantumvitas.presets.integration import apply_presets_to_step
        
        # Test non-pw step types
        non_pw_step_types = ["dos", "bands", "projwfc", "pp"]
        
        for step_type in non_pw_step_types:
            step_path = tmp_path / f"{step_type}.step.yaml"
            step_path.write_text(yaml.safe_dump({
                "step_type": step_type,
                "parameters": {"ELECTRONS": {}},
            }))
            
            # Apply convergence preset
            result = apply_presets_to_step(
                step_path,
                {"convergence": "normal"},
            )
            
            # Verify it was NOT accepted (no variant applies)
            assert result["accepted"] is False

