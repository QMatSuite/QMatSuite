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
    SpinOption,
    SOCOption,
    MaterialOption,
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
        assert result["spin"] == "nonspin"
        assert result["soc"] == "no_soc"
        assert result["material"] == "insulator"
    
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
                    "degauss": 0.01,
                },
            },
        }
        (steps_dir / "scf.step.yaml").write_text(yaml.safe_dump(step_content))
        
        result = detect_presets_from_calculation(tmp_path)
        
        assert result["spin"] == "collinear"
        assert result["soc"] == "no_soc"
        assert result["material"] == "metal"
    
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
        assert result["spin"] == "collinear"
    
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
        assert result["spin"] == "Custom"
    
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
        
        assert result["spin"] == SpinOption.COLLINEAR
        assert isinstance(result["spin"], SpinOption)


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
                    "ecutwfc": 50,  # Non-preset param
                    "occupations": "'fixed'",
                },
            },
        }
        step_path.write_text(yaml.safe_dump(original_content))
        
        # Apply collinear + metal
        result = apply_presets_to_step(
            step_path,
            {"spin": "collinear", "material": "metal"},
        )
        
        # Result now includes accepted flag and content
        assert result["accepted"] is True
        system = result["content"]["parameters"]["SYSTEM"]
        
        # Preset params changed
        assert system["nspin"] == 2
        assert system["occupations"] == "'smearing'"
        assert system["smearing"] == "'gaussian'"
        assert system["degauss"] == 0.01
        
        # Non-preset params preserved
        assert system["ecutwfc"] == 50
    
    def test_apply_preserves_nonpreset_params(self, tmp_path):
        """Non-preset SYSTEM params are preserved."""
        step_path = tmp_path / "test.step.yaml"
        original_content = {
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {
                    "nspin": 1,
                    "ecutwfc": 60,
                    "ecutrho": 600,
                    "nbnd": 20,
                },
                "CONTROL": {
                    "calculation": "scf",
                },
            },
        }
        step_path.write_text(yaml.safe_dump(original_content))
        
        apply_presets_to_step(step_path, {"spin": "collinear"})
        
        # Reload and check
        updated = yaml.safe_load(step_path.read_text())
        system = updated["parameters"]["SYSTEM"]
        
        assert system["ecutwfc"] == 60
        assert system["ecutrho"] == 600
        assert system["nbnd"] == 20
        
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
        
        # Apply insulator preset
        apply_presets_to_step(step_path, {"material": "insulator"})
        
        updated = yaml.safe_load(step_path.read_text())
        system = updated["parameters"]["SYSTEM"]
        
        assert system["occupations"] == "'fixed'"
        assert "smearing" not in system
        assert "degauss" not in system
    
    def test_apply_validates_physics_by_default(self, tmp_path):
        """Physics validation is on by default."""
        from quantumvitas.presets.compiler import PresetCompilationError
        
        step_path = tmp_path / "test.step.yaml"
        step_path.write_text(yaml.safe_dump({"step_type": "scf", "parameters": {}}))
        
        # SOC + nonspin is invalid physics
        with pytest.raises(PresetCompilationError):
            apply_presets_to_step(
                step_path,
                {"spin": "nonspin", "soc": "with_soc"},
            )
    
    def test_apply_can_skip_physics_validation(self, tmp_path):
        """Physics validation can be disabled."""
        step_path = tmp_path / "test.step.yaml"
        step_path.write_text(yaml.safe_dump({"step_type": "scf", "parameters": {}}))
        
        # SOC + nonspin - invalid but validation disabled
        result = apply_presets_to_step(
            step_path,
            {"spin": "nonspin", "soc": "with_soc"},
            validate_physics=False,
        )
        
        # Result includes accepted flag
        assert result["accepted"] is True
        
        # Parameters written despite invalid physics
        system = result["content"]["parameters"]["SYSTEM"]
        assert system["lspinorb"] == ".true."
        assert system["nspin"] == 1
    
    def test_apply_nonexistent_file_raises(self, tmp_path):
        """Applying to nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            apply_presets_to_step(
                tmp_path / "nonexistent.step.yaml",
                {"spin": "collinear"},
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
            {"spin": "noncollinear", "soc": "with_soc", "material": "metal"},
        )
        
        # Detect presets from calculation
        result = detect_presets_from_calculation(tmp_path)
        
        assert result["spin"] == "noncollinear"
        assert result["soc"] == "with_soc"
        assert result["material"] == "metal"


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

