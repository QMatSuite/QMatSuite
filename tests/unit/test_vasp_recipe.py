"""Unit tests for VASPRecipe."""

import pytest
from pathlib import Path
from quantumvitas.execution.recipes import VASPRecipe
from quantumvitas.execution.job_graph import JobGraph


class MockStep:
    """Mock step for testing."""
    def __init__(self, step_type: str, step_id: str = "01TEST"):
        self.step_type = step_type
        self.meta = type('meta', (), {'id': step_id})()


class TestVASPRecipe:
    """Test VASPRecipe materialization."""
    
    def test_vasp_recipe_creates_isolated_workdirs(self, tmp_path):
        """Test that VASPRecipe creates isolated workdir per step."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        steps = [
            MockStep("vasp_scf", "01SCF"),
            MockStep("vasp_bands", "02BANDS"),
        ]
        
        recipe = VASPRecipe()
        jobgraph = recipe.materialize(steps, calc_raw_dir)
        
        assert len(jobgraph.jobs) == 2
        
        # Check workdirs are isolated
        job1 = jobgraph.jobs[0]
        job2 = jobgraph.jobs[1]
        
        assert job1.working_dir == calc_raw_dir / "01SCF"
        assert job2.working_dir == calc_raw_dir / "02BANDS"
        assert job1.working_dir != job2.working_dir
    
    def test_vasp_recipe_creates_linear_dependencies(self, tmp_path):
        """Test that VASPRecipe creates linear job dependencies."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        steps = [
            MockStep("vasp_scf", "01SCF"),
            MockStep("vasp_bands", "02BANDS"),
            MockStep("vasp_nscf", "03NSCF"),
        ]
        
        recipe = VASPRecipe()
        jobgraph = recipe.materialize(steps, calc_raw_dir)
        
        assert len(jobgraph.jobs) == 3
        
        # First job has no deps
        assert jobgraph.jobs[0].deps == []
        
        # Second job depends on first
        assert jobgraph.jobs[1].deps == [jobgraph.jobs[0].id]
        
        # Third job depends on second
        assert jobgraph.jobs[2].deps == [jobgraph.jobs[1].id]
    
    def test_vasp_recipe_command_is_executable_only(self, tmp_path):
        """Test that VASP command is just the executable (VASP reads from CWD)."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        steps = [MockStep("vasp_scf", "01SCF")]
        
        recipe = VASPRecipe()
        jobgraph = recipe.materialize(steps, calc_raw_dir)
        
        job = jobgraph.jobs[0]
        assert job.command == ["vasp_std"]
    
    def test_vasp_recipe_input_files_listed(self, tmp_path):
        """Test that VASPRecipe lists expected input files."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        steps = [MockStep("vasp_scf", "01SCF")]
        
        recipe = VASPRecipe()
        jobgraph = recipe.materialize(steps, calc_raw_dir)
        
        job = jobgraph.jobs[0]
        input_files = set(job.input_files)
        
        expected = {
            calc_raw_dir / "01SCF" / "POSCAR",
            calc_raw_dir / "01SCF" / "INCAR",
            calc_raw_dir / "01SCF" / "KPOINTS",
            calc_raw_dir / "01SCF" / "POTCAR",
        }
        assert input_files == expected
    
    def test_vasp_recipe_expected_outputs(self, tmp_path):
        """Test that VASPRecipe lists expected outputs."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        steps = [MockStep("vasp_scf", "01SCF")]
        
        recipe = VASPRecipe()
        jobgraph = recipe.materialize(steps, calc_raw_dir)
        
        job = jobgraph.jobs[0]
        output_files = set(job.expected_outputs)
        
        expected = {
            calc_raw_dir / "01SCF" / "OUTCAR",
            calc_raw_dir / "01SCF" / "OSZICAR",
        }
        assert output_files == expected

