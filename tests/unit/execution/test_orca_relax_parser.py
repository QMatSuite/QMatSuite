"""
Unit tests for ORCA relax parser.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from quantumvitas.execution.orca_relax_parser import (
    parse_orca_optimized_xyz,
    handle_orca_relax_output,
)
from quantumvitas.execution.relax_artifacts import get_generated_structure_path, read_generated_structure


class TestParseOrcaOptimizedXyz:
    """Test parsing ORCA xyz files."""

    def test_parse_xyz_creates_molecule(self, tmp_path):
        """Parsing xyz file creates a pymatgen Molecule."""
        # Create a simple xyz file
        xyz_path = tmp_path / "test.xyz"
        xyz_content = """3
Coordinates from ORCA-job test E -76.123456
O     0.000000     0.000000     0.117000
H     0.757160     0.000000    -0.468000
H    -0.757160     0.000000    -0.468000
"""
        xyz_path.write_text(xyz_content)
        
        molecule = parse_orca_optimized_xyz(xyz_path)
        
        assert molecule is not None
        assert len(molecule) == 3
        assert molecule[0].species_string == "O"
        assert molecule[1].species_string == "H"
        assert molecule[2].species_string == "H"

    def test_parse_xyz_nonexistent_raises(self, tmp_path):
        """Parsing nonexistent xyz file raises FileNotFoundError."""
        xyz_path = tmp_path / "nonexistent.xyz"
        
        with pytest.raises(FileNotFoundError):
            parse_orca_optimized_xyz(xyz_path)


class TestHandleOrcaRelaxOutput:
    """Test handling ORCA relax output."""

    def test_handle_orca_relax_creates_current_json(self, tmp_path):
        """handle_orca_relax_output creates current.json from xyz file."""
        from pymatgen.core import Molecule
        
        # Create calc directory
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        # Create working directory with xyz file
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        
        chain_key = "chain01_scf"
        xyz_path = working_dir / f"{chain_key}.xyz"
        xyz_content = """3
Coordinates from ORCA-job chain01_scf E -76.123456
O     0.000000     0.000000     0.117000
H     0.757160     0.000000    -0.468000
H    -0.757160     0.000000    -0.468000
"""
        xyz_path.write_text(xyz_content)
        
        step_ulid = "01ORCARELAX"
        step_type= "orca_relax"
        calculation_ulid = "01CALCTEST"
        input_structure_ulid = "01STRUCTEST"
        run_id = "run001"
        
        # Call handler
        artifact_path = handle_orca_relax_output(
            step_ulid=step_ulid,
            step_type=step_type,
            calc_dir=calc_dir,
            working_dir=working_dir,
            chain_key=chain_key,
            calculation_ulid=calculation_ulid,
            input_structure_ulid=input_structure_ulid,
            run_id=run_id,
        )
        
        # Verify current.json was created
        assert artifact_path.exists()
        assert artifact_path == get_generated_structure_path(calc_dir, step_ulid)
        
        # Verify content
        data = json.loads(artifact_path.read_text())
        assert "__qv_meta__" in data
        assert data["__qv_meta__"]["source_step_ulid"] == step_ulid
        assert data["__qv_meta__"]["provenance"]["method"] == step_type
        assert data["__qv_meta__"]["provenance"]["calculation_ulid"] == calculation_ulid
        assert data["__qv_meta__"]["provenance"]["input_structure_ulid"] == input_structure_ulid
        
        # Verify structure can be read
        # Note: For molecules, we need to read as Molecule, not Structure
        from pymatgen.core import Molecule
        structure_dict = json.loads(artifact_path.read_text())
        structure_dict.pop("__qv_meta__", None)
        loaded = Molecule.from_dict(structure_dict)
        assert loaded is not None
        assert len(loaded) == 3  # 3 atoms (O, H, H)

    def test_handle_orca_relax_missing_xyz_raises(self, tmp_path):
        """handle_orca_relax_output raises FileNotFoundError if xyz doesn't exist."""
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        
        chain_key = "chain01_scf"
        # DO NOT create xyz file
        
        with pytest.raises(FileNotFoundError, match="ORCA optimized structure not found"):
            handle_orca_relax_output(
                step_ulid="01TEST",
                step_type="orca_relax",
                calc_dir=calc_dir,
                working_dir=working_dir,
                chain_key=chain_key,
                calculation_ulid="01CALC",
                input_structure_ulid="01STRUCT",
            )

