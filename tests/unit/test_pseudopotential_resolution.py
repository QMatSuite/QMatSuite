"""
Unit tests for pseudopotential resolution in workflows.

Tests that pseudopotentials are correctly extracted from existing input files
and preserved in step specs when building workflows.
"""

from pathlib import Path

import pytest

from quantumvitas.io.parser.qe_parser import QEInputParser
from quantumvitas.io.model import QECardType
from quantumvitas.workflow.structure_steps import StructureStepSpec
from quantumvitas.workflow.workflow import _build_step_from_spec
from quantumvitas.core.resources import meta_from_name, generate_resource_id
from quantumvitas.project.model import Project


class TestPseudopotentialResolution:
    """Test pseudopotential resolution from existing input files."""
    
    def test_extract_pseudopotentials_from_input_file(self, ci_test_data_dir: Path):
        """Test that pseudopotentials are extracted from existing input files."""
        input_file = ci_test_data_dir / "4_Si_DOS" / "si.1_scf.in"
        if not input_file.exists():
            pytest.skip(f"Test input file not found: {input_file}")
        
        # Parse the input file
        qe_input = QEInputParser.parse_file(input_file)
        atomic_species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
        
        assert atomic_species_card is not None, "ATOMIC_SPECIES card should be present"
        assert len(atomic_species_card.data) > 0, "ATOMIC_SPECIES card should have data"
        
        # Extract pseudopotential for Si
        si_pseudo = None
        for row in atomic_species_card.data:
            if isinstance(row, list) and len(row) >= 3:
                element = str(row[0]).strip()
                if element == "Si":
                    si_pseudo = str(row[2]).strip()
                    break
        
        assert si_pseudo is not None, "Si pseudopotential should be found"
        assert si_pseudo == "Si.pbe-n-rrkjus_psl.1.0.0.UPF", f"Expected Si.pbe-n-rrkjus_psl.1.0.0.UPF, got {si_pseudo}"
        assert si_pseudo != "Si.upf", "Should not be generic fallback"
    
    def test_step_spec_preserves_species_overrides(self, tmp_path: Path):
        """Test that step spec preserves species_overrides with pseudopotentials."""
        # Create a step spec with species_overrides
        step_spec_dict = {
            "meta": {
                "id": generate_resource_id(),
                "name": "test_step",
                "slug": "test_step",
                "path": "test_step.step.yaml",
                "kind": "step",
            },
            "step_type": "scf",
            "structure_id": generate_resource_id(),
            "species_overrides": {
                "Si": {
                    "pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
                },
            },
        }
        
        spec = StructureStepSpec.from_dict(step_spec_dict)
        
        # Verify species_overrides are preserved
        assert "Si" in spec.species_overrides
        assert spec.species_overrides["Si"]["pseudopot"] == "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
        
        # Verify to_dict includes species_overrides
        spec_dict = spec.to_dict()
        assert "species_overrides" in spec_dict
        assert "Si" in spec_dict["species_overrides"]
        assert spec_dict["species_overrides"]["Si"]["pseudopot"] == "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
    
    def test_extract_pseudopotentials_into_species_overrides(self, ci_test_data_dir: Path):
        """Test that pseudopotentials are correctly extracted and can be merged into species_overrides."""
        input_file = ci_test_data_dir / "4_Si_DOS" / "si.1_scf.in"
        if not input_file.exists():
            pytest.skip(f"Test input file not found: {input_file}")
        
        # Parse the input file and extract pseudopotentials
        qe_input = QEInputParser.parse_file(input_file)
        atomic_species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
        
        assert atomic_species_card is not None, "ATOMIC_SPECIES card should be present"
        
        # Extract pseudopotential mappings (simulating what _build_step_from_spec does)
        extracted_overrides = {}
        for row in atomic_species_card.data:
            if isinstance(row, list) and len(row) >= 3:
                element_symbol = str(row[0]).strip()
                pseudo_filename = str(row[2]).strip()
                # Only add if it's not the default generic name
                if pseudo_filename and pseudo_filename != f"{element_symbol}.upf":
                    extracted_overrides[element_symbol] = {
                        "pseudopot": pseudo_filename,
                    }
        
        # Verify extraction worked
        assert "Si" in extracted_overrides, "Si should be in extracted overrides"
        assert extracted_overrides["Si"]["pseudopot"] == "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
        
        # Verify it can be merged into a step spec
        step_spec = StructureStepSpec(
            meta=meta_from_name("step", name="test", path="test.step.yaml"),
            structure="test_structure",  # Required field
            structure_id=generate_resource_id(),
            step_type="scf",
            species_overrides={},  # Empty initially
        )
        
        # Merge extracted overrides
        step_spec.species_overrides.update(extracted_overrides)
        
        # Verify merge worked
        assert "Si" in step_spec.species_overrides
        assert step_spec.species_overrides["Si"]["pseudopot"] == "Si.pbe-n-rrkjus_psl.1.0.0.UPF"

