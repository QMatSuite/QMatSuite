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
from quantumvitas.execution.handlers import handle_qe_relax_output


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
            step_type="qe_relax",
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

    def test_qe_scf_is_not_relax(self):
        """qe_scf is not a relax step."""
        assert is_relax_step_type("qe_scf") is False

    def test_unknown_type_is_not_relax(self):
        """Unknown step type is not relax."""
        assert is_relax_step_type("unknown_type") is False


class TestHandleQERelaxOutput:
    """Test QE relax output handler."""

    def test_handle_qe_relax_output_creates_current_json(self, tmp_path):
        """handle_qe_relax_output parses QE output and creates current.json."""
        from pymatgen.core import Structure, Lattice
        
        # Create a mock QE output file with final coordinates
        output_path = tmp_path / "relax.out"
        output_text = """
     Begin final coordinates
         new unit-cell volume =    123.456 a.u.^3 (    18.289 Ang^3 )
         density =      2.329 g/cm^3

CELL_PARAMETERS (alat=  7.26553535)
   0.500000000   0.500000000   0.000000000
   0.500000000   0.000000000   0.500000000
   0.000000000   0.500000000   0.500000000

ATOMIC_POSITIONS (alat)
Si   0.000000000   0.000000000   0.000000000
Si   0.250000000   0.250000000   0.250000000

     End final coordinates
"""
        output_path.write_text(output_text)
        
        # Create calc directory
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        step_ulid = "01RELAXTEST"
        step_type= "qe_relax"
        calculation_ulid = "01CALCTEST"
        input_structure_ulid = "01STRUCTEST"
        run_id = "run001"
        
        # Call handler
        artifact_path = handle_qe_relax_output(
            step_ulid=step_ulid,
            step_type=step_type,
            calc_dir=calc_dir,
            output_path=output_path,
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
        loaded = read_generated_structure(calc_dir, step_ulid)
        assert loaded is not None
        assert len(loaded) == 2  # 2 Si atoms


class TestScopedCleanup:
    """Test scoped cleanup of generated structures."""

    def test_scoped_cleanup_removes_current_json(self, tmp_path):
        """Pre-clean removes current.json for relax steps in job."""
        from quantumvitas.execution.executor import JobExecutor
        from quantumvitas.execution.job_graph import Job
        from quantumvitas.execution.relax_artifacts import write_generated_structure
        from pymatgen.core import Structure, Lattice
        from unittest.mock import MagicMock
        
        # Create calc directory
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        # Create a relax step and write current.json
        step_ulid = "01RELAXSTEP"
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_relax",
        )
        
        # Verify it exists
        artifact_path = get_generated_structure_path(calc_dir, step_ulid)
        assert artifact_path.exists()
        
        # Create mock calculation and job
        mock_step = MagicMock()
        mock_step.meta.ulid = step_ulid
        mock_step.step_type_spec= "qe_relax"
        
        mock_calculation = MagicMock()
        mock_calculation.dir = calc_dir
        mock_calculation.steps = [mock_step]
        
        job = Job(
            id="test_job",
            step_ids=[step_ulid],
            working_dir=tmp_path / "work",
            command=["pw.x", "relax.in"],
            input_files=[],
            expected_outputs=[],
            deps=[],
        )
        # Set engine via metadata
        job.metadata = {"engine": "qe"}
        
        # Create executor and call pre-clean
        executor = JobExecutor()
        executor._pre_clean_relax_steps(job, mock_calculation)
        
        # Verify current.json was deleted
        assert not artifact_path.exists()
    
    def test_scoped_cleanup_only_cleans_job_steps(self, tmp_path):
        """Pre-clean only removes current.json for steps in the job."""
        from quantumvitas.execution.executor import JobExecutor
        from quantumvitas.execution.job_graph import Job
        from quantumvitas.execution.relax_artifacts import write_generated_structure
        from pymatgen.core import Structure, Lattice
        from unittest.mock import MagicMock
        
        # Create calc directory
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        # Create two relax steps
        step1_ulid = "01RELAX1"
        step2_ulid = "01RELAX2"
        
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        # Write current.json for both
        write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step1_ulid,
            step_type="qe_relax",
        )
        write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step2_ulid,
            step_type="qe_relax",
        )
        
        # Create job that only includes step1
        mock_step1 = MagicMock()
        mock_step1.meta.ulid = step1_ulid
        mock_step1.step_type_spec= "qe_relax"
        
        mock_step2 = MagicMock()
        mock_step2.meta.ulid = step2_ulid
        mock_step2.step_type_spec= "qe_relax"
        
        mock_calculation = MagicMock()
        mock_calculation.dir = calc_dir
        mock_calculation.steps = [mock_step1, mock_step2]
        
        job = Job(
            id="test_job",
            step_ids=[step1_ulid],  # Only step1
            working_dir=tmp_path / "work",
            command=["pw.x", "relax.in"],
            input_files=[],
            expected_outputs=[],
            deps=[],
        )
        # Set engine via metadata
        job.metadata = {"engine": "qe"}
        
        # Create executor and call pre-clean
        executor = JobExecutor()
        executor._pre_clean_relax_steps(job, mock_calculation)
        
        # Verify step1's current.json was deleted
        artifact1_path = get_generated_structure_path(calc_dir, step1_ulid)
        assert not artifact1_path.exists()
        
        # Verify step2's current.json still exists (not in job)
        artifact2_path = get_generated_structure_path(calc_dir, step2_ulid)
        assert artifact2_path.exists()

