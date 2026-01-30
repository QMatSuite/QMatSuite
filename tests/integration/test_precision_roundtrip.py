"""
Integration test for precision preset roundtrip safety.

Tests that:
1. Applying precision=Medium to a calc with scf, nscf, bands_pw, bands
2. Detection returns Medium (NOT CUSTOM) after apply
3. Manual parameter changes cause detection to return CUSTOM
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import yaml

from quantumvitas.presets.integration import (
    apply_presets_to_step,
    detect_presets_from_calculation,
)
from quantumvitas.presets.precision import PrecisionAdvisor, PrecisionOption
from pymatgen.core import Structure, Lattice
from quantumvitas.core.models import CalculationModel, ResourceMeta


class TestPrecisionRoundtrip:
    """Test precision preset roundtrip: apply → detect should match."""
    
    @pytest.fixture
    def temp_calc_dir(self):
        """Create a temporary calculation directory with structure."""
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
        
        # Create structure
        structures_dir = project_root / "structures"
        structures_dir.mkdir(exist_ok=True)
        structure = Structure(
            lattice=Lattice.cubic(5.43),
            species=["Si", "Si"],
            coords=[[0, 0, 0], [0.25, 0.25, 0.25]],
        )
        structure_file = structures_dir / "test_structure.json"
        import json
        from quantumvitas.io.structure_io import STRUCTURE_META_KEY
        struct_dict = structure.as_dict()
        struct_dict[STRUCTURE_META_KEY] = {
            "ulid": "test_structure",
            "name": "test_structure",
            "slug": "test_structure",
        }
        structure_file.write_text(json.dumps(struct_dict))
        
        # Create calculation.yaml
        calc_yaml = calc_dir / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "name": "Test Calculation",
            "structure_ulid": "test_structure",  # Must match structure file meta id
            "species_map": {
                "Si": {
                    "pseudo_sha256": "test_sha",
                }
            },
        }))
        
        yield calc_dir
        shutil.rmtree(temp_dir)
    
    def test_roundtrip_scf_nscf_bands_pw_bands(self, temp_calc_dir):
        """
        Apply precision=Medium to calc with scf, nscf, bands_pw, bands.
        Detection should return Medium (not CUSTOM).
        """
        # Create steps: scf, nscf, bands_pw, bands
        scf_step = temp_calc_dir / "steps" / "scf.step.yaml"
        nscf_step = temp_calc_dir / "steps" / "nscf.step.yaml"
        bands_pw_step = temp_calc_dir / "steps" / "bands_pw.step.yaml"
        bands_step = temp_calc_dir / "steps" / "bands.step.yaml"
        
        # Initialize empty steps with step_type_spec (engine-prefixed)
        for step_file in [scf_step, nscf_step, bands_pw_step, bands_step]:
            step_type_gen = step_file.stem.split(".")[0]  # e.g., "scf", "nscf"
            step_file.write_text(yaml.safe_dump({
                "step_type_spec": f"qe_{step_type_gen}",
                "parameters": {},
                "cards": {},
            }))
        
        # Create PrecisionAdvisor
        species_map = {"Si": {"pseudo_sha256": "test_sha"}}
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice)
        
        # Apply precision=med to all steps
        for step_file, step_type in [
            (scf_step, "scf"),
            (nscf_step, "nscf"),
            (bands_pw_step, "bands_pw"),
            (bands_step, "bands"),
        ]:
            precision_advice = advisor.advise_for_step(PrecisionOption.MED, step_type)
            # bands_pw doesn't need lattice_matrix (variant doesn't include K_POINTS)
            apply_presets_to_step(
                step_file,
                {"precision": "med"},
                precision_advice=precision_advice,
                precision_lattice_matrix=lattice if step_type != "bands_pw" else None,
            )
        
        # Verify YAML structure
        scf_content = yaml.safe_load(scf_step.read_text())
        nscf_content = yaml.safe_load(nscf_step.read_text())
        bands_pw_content = yaml.safe_load(bands_pw_step.read_text())
        
        # scf should have K_POINTS with base mesh (6×6×6 for Si med)
        assert "cards" in scf_content
        assert "K_POINTS" in scf_content["cards"]
        scf_kpoints = scf_content["cards"]["K_POINTS"]
        assert scf_kpoints["option"] == "automatic"
        assert scf_kpoints["data"] == [[6, 6, 6, 0, 0, 0]]
        
        # nscf should have K_POINTS with 2x mesh (12×12×12)
        assert "cards" in nscf_content
        assert "K_POINTS" in nscf_content["cards"]
        nscf_kpoints = nscf_content["cards"]["K_POINTS"]
        assert nscf_kpoints["option"] == "automatic"
        assert nscf_kpoints["data"] == [[12, 12, 12, 0, 0, 0]]
        
        # bands_pw should have cutoffs but no K_POINTS (k-path preserved)
        assert "cards" in bands_pw_content
        # bands_pw may or may not have K_POINTS depending on receiver design
        # But it should have cutoffs
        assert "parameters" in bands_pw_content
        assert "SYSTEM" in bands_pw_content["parameters"]
        assert "ecutwfc" in bands_pw_content["parameters"]["SYSTEM"]
        
        # Run detection - should return MED (not CUSTOM)
        detected = detect_presets_from_calculation(temp_calc_dir)
        assert detected["precision"] == "med", \
            f"Expected 'med' after applying precision=med, got {detected.get('precision')}"
    
    def test_roundtrip_breaks_on_manual_change(self, temp_calc_dir):
        """
        Apply precision=Medium, then manually change one parameter.
        Detection should return CUSTOM.
        """
        # Create scf step
        scf_step = temp_calc_dir / "steps" / "scf.step.yaml"
        scf_step.write_text(yaml.safe_dump({
            "step_type_spec": "qe_scf",
            "parameters": {},
            "cards": {},
        }))
        
        # Apply precision=med
        species_map = {"Si": {"pseudo_sha256": "test_sha"}}
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice)
        precision_advice = advisor.advise_for_step(PrecisionOption.MED, "scf")
        
        apply_presets_to_step(
            scf_step,
            {"precision": "med"},
            precision_advice=precision_advice,
            precision_lattice_matrix=lattice,
        )
        
        # Verify initial detection is MED
        detected = detect_presets_from_calculation(temp_calc_dir)
        assert detected["precision"] == "med"
        
        # Manually change ecutrho (+1)
        scf_content = yaml.safe_load(scf_step.read_text())
        scf_content["parameters"]["SYSTEM"]["ecutrho"] += 1
        scf_step.write_text(yaml.safe_dump(scf_content))
        
        # Detection should now return CUSTOM
        detected = detect_presets_from_calculation(temp_calc_dir)
        assert detected["precision"] == "Custom", \
            f"Expected 'Custom' after changing ecutrho, got {detected.get('precision')}"

