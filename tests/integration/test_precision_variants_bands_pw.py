"""
Test precision variants: bands_pw must preserve K_POINTS kpath.

This test enforces the fix for the precision↔bands_pw K_POINTS issue.
"""

import tempfile
import shutil
from pathlib import Path
import yaml
import pytest

from quantumvitas.presets.integration import apply_presets_to_step
from quantumvitas.presets.precision import PrecisionAdvisor, PrecisionOption
from quantumvitas.presets.variants_registry import get_variant, PRECISION_PW_BANDS_PW_VARIANT


class TestPrecisionVariantsBandsPw:
    """Test that precision variants correctly handle bands_pw K_POINTS."""
    
    @pytest.fixture
    def temp_calc_dir(self):
        """Create a temporary calculation directory."""
        temp_dir = tempfile.mkdtemp()
        project_root = Path(temp_dir) / "test_project"
        project_root.mkdir()
        calc_dir = project_root / "calculations" / "test_calc"
        calc_dir.mkdir(parents=True)
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir()
        
        # Create project.qv.yml
        project_qv_yml = project_root / "project.qv.yml"
        project_qv_yml.write_text(yaml.safe_dump({
            "name": "Test Project",
            "version": "1.0",
        }))
        
        # Create calculation.yaml
        calc_yaml = calc_dir / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "name": "Test Calculation",
            "species_map": {"Si": {"pseudo_sha256": "test_sha"}},
        }))
        
        yield calc_dir
        shutil.rmtree(temp_dir)
    
    def test_bands_pw_variant_excludes_kpoints(self):
        """Test that PRECISION_PW_BANDS_PW variant does NOT include K_POINTS key."""
        variant = PRECISION_PW_BANDS_PW_VARIANT
        
        # Check applies_to
        assert variant.applies_to("bands_pw")
        assert not variant.applies_to("scf")
        assert not variant.applies_to("nscf")
        
        # Check keys - must NOT include K_POINTS
        has_kpoints = any(
            key.section == "cards" and key.key == "K_POINTS"
            for key in variant.space.keys
        )
        assert not has_kpoints, "bands_pw variant must NOT include K_POINTS key"
        
        # Check it has the other keys
        key_sections = {key.section for key in variant.space.keys}
        assert "SYSTEM" in key_sections
        assert "ELECTRONS" in key_sections
        assert "cards" not in key_sections
    
    def test_get_variant_bands_pw(self):
        """Test that get_variant returns correct variant for bands_pw."""
        variant = get_variant("precision", "bands_pw")
        assert variant is not None
        assert variant.name == "PRECISION_PW_BANDS_PW"
        
        # Check scf gets default variant
        scf_variant = get_variant("precision", "scf")
        assert scf_variant is not None
        assert scf_variant.name == "PRECISION_PW_DEFAULT"
        
        # Check nscf gets nscf variant
        nscf_variant = get_variant("precision", "nscf")
        assert nscf_variant is not None
        assert nscf_variant.name == "PRECISION_PW_NSCF"
    
    def test_bands_pw_kpoints_preserved(self, temp_calc_dir):
        """
        Apply precision to bands_pw, K_POINTS must remain unchanged (k-path).
        
        This is the critical regression test.
        """
        # Create bands_pw step with explicit k-path
        bands_step = temp_calc_dir / "steps" / "bands.step.yaml"
        original_kpoints = {
            "option": "crystal_b",
            "data": [
                [0.0, 0.0, 0.0, 1.0],
                [0.5, 0.5, 0.5, 1.0],
            ],
        }
        bands_step.write_text(yaml.safe_dump({
            "step_type": "bands_pw",
            "parameters": {},
            "cards": {
                "K_POINTS": original_kpoints,
            },
        }))
        
        # Create PrecisionAdvisor
        species_map = {"Si": {"pseudo_sha256": "test_sha"}}
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice, repo_root=temp_calc_dir.parent.parent)
        
        # Apply precision=med
        precision_advice = advisor.advise_for_step(PrecisionOption.MED, "bands_pw")
        apply_presets_to_step(
            bands_step,
            {"precision": "med"},
            precision_advice=precision_advice,
            precision_lattice_matrix=lattice,
        )
        
        # Verify K_POINTS unchanged (still k-path, not automatic)
        bands_content = yaml.safe_load(bands_step.read_text())
        bands_kpoints_card = bands_content.get("cards", {}).get("K_POINTS", {})
        
        # Must be unchanged
        assert bands_kpoints_card.get("option") == "crystal_b"
        assert "data" in bands_kpoints_card
        assert len(bands_kpoints_card["data"]) == 2
        assert bands_kpoints_card["data"] == original_kpoints["data"]
        
        # Verify cutoffs were applied
        system = bands_content["parameters"]["SYSTEM"]
        assert "ecutwfc" in system
        assert "ecutrho" in system
        
        # Verify conv_thr was applied
        electrons = bands_content["parameters"]["ELECTRONS"]
        assert "conv_thr" in electrons

