"""
Integration test for precision detection returning Custom correctly.

Tests that precision detection returns "Custom" when:
1. Steps don't match canonical precision values (strict 3-way match fails)
2. Calculation cannot be loaded (missing structure/species_map)
3. Steps have mismatched precision parameters
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import yaml

from quantumvitas.presets.integration import detect_presets_from_calculation
from quantumvitas.presets.precision import PrecisionAdvisor, PrecisionOption
from quantumvitas.presets.integration import apply_presets_to_step


class TestPrecisionDetectionCustom:
    """Test precision detection returns Custom when appropriate."""
    
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
        
        # Create structure
        structures_dir = project_root / "structures"
        structures_dir.mkdir(exist_ok=True)
        from pymatgen.core import Structure, Lattice
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
            "structure_id": "test_structure",
            "species_map": {
                "Si": {
                    "pseudo_sha256": "test_sha",
                }
            },
        }))
        
        yield calc_dir
        shutil.rmtree(temp_dir)
    
    def test_custom_on_mismatched_cutoffs(self, temp_calc_dir):
        """Apply med precision, then change ecutrho → should detect Custom."""
        from pymatgen.core import Structure, Lattice
        from quantumvitas.core.models import CalculationModel, ResourceMeta
        
        # Create a minimal structure for CalculationModel
        si_lattice = Lattice.cubic(5.43)
        si_structure = Structure(si_lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        # calculation.yaml already has structure_id="test_structure" from fixture
        
        # Create scf step
        scf_step = temp_calc_dir / "steps" / "scf.step.yaml"
        scf_step.write_text(yaml.safe_dump({
            "step_type_gen": "scf",
            "parameters": {},
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
        )
        
        # Verify initial detection is med (no need to mock - unified resolver handles it)
        detected = detect_presets_from_calculation(temp_calc_dir)
        assert detected["precision"] == "med", f"Expected 'med', got {detected.get('precision')}"
        
        # Manually change ecutrho (+1) - this should break strict match
        scf_content = yaml.safe_load(scf_step.read_text())
        original_ecutrho = scf_content["parameters"]["SYSTEM"]["ecutrho"]
        scf_content["parameters"]["SYSTEM"]["ecutrho"] = original_ecutrho + 1
        scf_step.write_text(yaml.safe_dump(scf_content))
        
        # Detection should now return Custom (strict detection fails)
        detected = detect_presets_from_calculation(temp_calc_dir)
        assert detected["precision"] == "Custom", f"Expected 'Custom' after changing ecutrho, got {detected.get('precision')}"
    
    def test_custom_on_missing_calculation_data(self, temp_calc_dir):
        """Test that missing calculation data returns Custom (not fallback to simple detection)."""
        # Create scf step with some precision-like params but not canonical
        scf_step = temp_calc_dir / "steps" / "scf.step.yaml"
        scf_step.write_text(yaml.safe_dump({
            "step_type_gen": "scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": 50,
                    "ecutrho": 400,
                },
                "ELECTRONS": {
                    "conv_thr": 1e-6,
                },
                "K_POINTS": {
                    "type": "automatic",
                    "mesh": [6, 6, 6],
                    "shifts": [0, 0, 0],
                },
            },
        }))
        
        # Remove calculation.yaml to simulate missing structure/species_map
        calc_yaml = temp_calc_dir / "calculation.yaml"
        calc_yaml.unlink()
        
        # Detection should return Custom (cannot do strict detection without calculation data)
        detected = detect_presets_from_calculation(temp_calc_dir)
        assert detected["precision"] == "Custom", f"Expected 'Custom' when calculation data missing, got {detected.get('precision')}"
    
    def test_custom_on_empty_steps(self, temp_calc_dir):
        """Test that empty steps list returns Custom for precision."""
        # No steps created
        
        # Detection should return Custom (no steps to detect from)
        detected = detect_presets_from_calculation(temp_calc_dir)
        assert detected["precision"] == "Custom", f"Expected 'Custom' for empty steps, got {detected.get('precision')}"

