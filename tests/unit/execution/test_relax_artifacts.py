"""
Unit tests for relax artifact utilities.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from quantumvitas.execution.relax_artifacts import (
    get_generated_structure_path,
    write_generated_structure,
    read_generated_structure,
    clean_generated_structure,
    is_relax_step_type,
)


class TestGeneratedStructurePath:
    """Test path generation for generated structures."""

    def test_path_format(self, tmp_path):
        """Path follows the canonical format."""
        calc_dir = tmp_path / "calc"
        step_ulid = "01ABC123XYZ"
        
        path = get_generated_structure_path(calc_dir, step_ulid)
        
        assert path == calc_dir / "generated_structures" / f"step_{step_ulid}" / "current.json"


class TestWriteGeneratedStructure:
    """Test writing generated structures."""

    def test_write_creates_file(self, tmp_path):
        """Writing creates current.json with correct structure."""
        # Create a mock pymatgen structure
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.5, 0.5, 0.5]])
        
        calc_dir = tmp_path / "calc"
        step_ulid = "01TESTULID123456789012"
        
        result_path = write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_relax",
            run_id="run001",
            calculation_ulid="calc001",
            input_structure_ulid="struct001",
        )
        
        assert result_path.exists()
        
        # Check content
        data = json.loads(result_path.read_text())
        assert "__qv_meta__" in data
        assert data["__qv_meta__"]["type"] == "generated_structure"
        assert data["__qv_meta__"]["source_step_ulid"] == step_ulid
        assert data["__qv_meta__"]["provenance"]["method"] == "qe_relax"

    def test_write_creates_parent_dirs(self, tmp_path):
        """Writing creates parent directories if needed."""
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        # calc_dir doesn't exist yet
        calc_dir = tmp_path / "nonexistent" / "calc"
        step_ulid = "01TESTULID"
        
        result_path = write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_vc_relax",
        )
        
        assert result_path.exists()


class TestReadGeneratedStructure:
    """Test reading generated structures."""

    def test_read_existing_file(self, tmp_path):
        """Reading an existing file returns a Structure."""
        from pymatgen.core import Structure, Lattice
        
        # Write a structure first
        lattice = Lattice.cubic(5.43)
        original = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        calc_dir = tmp_path / "calc"
        step_ulid = "01READTEST"
        
        write_generated_structure(
            structure=original,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_relax",
        )
        
        # Read it back
        loaded = read_generated_structure(calc_dir, step_ulid)
        
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded.lattice.a == pytest.approx(5.43)

    def test_read_nonexistent_returns_none(self, tmp_path):
        """Reading a nonexistent file returns None."""
        calc_dir = tmp_path / "calc"
        step_ulid = "01NONEXISTENT"
        
        result = read_generated_structure(calc_dir, step_ulid)
        
        assert result is None


class TestCleanGeneratedStructure:
    """Test cleaning generated structures."""

    def test_clean_existing_file(self, tmp_path):
        """Cleaning an existing file deletes it and returns True."""
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        calc_dir = tmp_path / "calc"
        step_ulid = "01CLEANTEST"
        
        path = write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_relax",
        )
        
        assert path.exists()
        
        result = clean_generated_structure(calc_dir, step_ulid)
        
        assert result is True
        assert not path.exists()

    def test_clean_nonexistent_returns_false(self, tmp_path):
        """Cleaning a nonexistent file returns False."""
        calc_dir = tmp_path / "calc"
        step_ulid = "01NONEXISTENT"
        
        result = clean_generated_structure(calc_dir, step_ulid)
        
        assert result is False


class TestIsRelaxStepType:
    """Test relax step type detection."""

    def test_qe_relax_is_relax(self):
        """qe_relax is detected as relax."""
        assert is_relax_step_type("qe_relax") is True

    def test_qe_vc_relax_is_relax(self):
        """qe_vc_relax is detected as relax."""
        assert is_relax_step_type("qe_vc_relax") is True

    def test_qe_scf_is_not_relax(self):
        """qe_scf is not a relax step."""
        assert is_relax_step_type("qe_scf") is False

    def test_unknown_type_is_not_relax(self):
        """Unknown step type is not relax."""
        assert is_relax_step_type("unknown_type") is False

