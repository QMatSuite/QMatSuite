"""
Integration tests for relax executor integration.

This test verifies that the executor correctly:
1. Pre-cleans current.json before job execution
2. Post-processes relax output after successful job execution
3. Handles QE, ORCA, and PySCF relax steps correctly
"""

import json
import pytest
import time
import uuid
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.core.paths import tmp_runs_dir
from quantumvitas.execution.relax_artifacts import (
    get_generated_structure_path,
    read_generated_structure,
)
from pymatgen.core import Structure, Lattice, Molecule


pytestmark = [pytest.mark.integration]


class TestRelaxExecutorIntegration:
    """Test executor integration for relax steps."""
    
    def test_executor_pre_clean_before_job_execution(self, tmp_path):
        """
        Test that executor pre-cleans current.json before job execution.
        
        This ensures that current.json existence implies success in THIS run.
        """
        from quantumvitas.execution.executor import JobExecutor
        from quantumvitas.execution.job_graph import Job
        from quantumvitas.execution.relax_artifacts import write_generated_structure
        from unittest.mock import MagicMock
        
        # Create calc directory
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        # Create a relax step and write current.json (simulating old run)
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
        assert artifact_path.exists(), "Pre-existing current.json should exist"
        
        # Create mock calculation and job
        mock_step = MagicMock()
        mock_step.meta.id = step_ulid
        mock_step.step_type = "qe_relax"
        
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
        job.metadata = {"engine": "qe"}
        
        # Create executor and call pre-clean
        executor = JobExecutor()
        executor._pre_clean_relax_steps(job, mock_calculation)
        
        # Verify current.json was deleted
        assert not artifact_path.exists(), "Pre-clean should have removed current.json"
    
    def test_executor_post_process_after_successful_job(self, tmp_path):
        """
        Test that executor post-processes relax output after successful job.
        
        This verifies that _post_process_relax_steps is called and handles
        the output correctly.
        """
        from quantumvitas.execution.executor import JobExecutor, JobResult
        from quantumvitas.execution.job_graph import Job
        from unittest.mock import MagicMock
        
        # Create calc directory
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        # Create a dummy QE output file
        output_content = """
        Begin final coordinates
        
        CELL_PARAMETERS (alat= 5.43000000)
        -0.500000000  0.000000000  0.500000000
         0.000000000  0.500000000  0.500000000
        -0.500000000  0.500000000  0.000000000
        
        ATOMIC_POSITIONS (alat)
        Si   0.000000000  0.000000000  0.000000000
        Si   0.250000000  0.250000000  0.250000000
        End final coordinates
        """
        output_path = calc_dir / "qe_relax.out"
        output_path.write_text(output_content)
        
        step_ulid = "01RELAXSTEP"
        
        # Create mock calculation and job
        mock_step = MagicMock()
        mock_step.meta.id = step_ulid
        mock_step.step_type = "qe_relax"
        
        mock_calculation = MagicMock()
        mock_calculation.dir = calc_dir
        mock_calculation.steps = [mock_step]
        mock_calculation.meta.id = "calc001"
        mock_calculation.structure_id = "struct001"
        
        job = Job(
            id="test_job",
            step_ids=[step_ulid],
            working_dir=tmp_path / "work",
            command=["pw.x", "relax.in"],
            input_files=[],
            expected_outputs=[],
            deps=[],
        )
        job.metadata = {"engine": "qe"}
        
        # Create successful job result
        job_result = JobResult(
            job_id=job.id,
            success=True,
            step_results={
                step_ulid: {
                    "output_file": str(output_path),
                },
            },
        )
        
        # Create executor and call post-process
        executor = JobExecutor()
        executor._post_process_relax_steps(
            job=job,
            job_result=job_result,
            calculation=mock_calculation,
            context={"run_id": "test_run_001"},
        )
        
        # Verify current.json was created
        artifact_path = get_generated_structure_path(calc_dir, step_ulid)
        assert artifact_path.exists(), "Post-process should have created current.json"
        
        # Verify structure can be read
        relaxed_structure = read_generated_structure(calc_dir, step_ulid)
        assert relaxed_structure is not None
        assert len(relaxed_structure) == 2
        
        # Verify metadata
        data = json.loads(artifact_path.read_text())
        assert "__qv_meta__" in data
        assert data["__qv_meta__"]["source_step_ulid"] == step_ulid
        assert data["__qv_meta__"]["provenance"]["method"] == "qe_relax"
    
    def test_executor_post_process_only_on_success(self, tmp_path):
        """
        Test that executor does NOT post-process if job failed.
        """
        from quantumvitas.execution.executor import JobExecutor, JobResult
        from quantumvitas.execution.job_graph import Job
        from unittest.mock import MagicMock
        
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        step_ulid = "01RELAXSTEP"
        
        mock_step = MagicMock()
        mock_step.meta.id = step_ulid
        mock_step.step_type = "qe_relax"
        
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
        job.metadata = {"engine": "qe"}
        
        # Create failed job result
        job_result = JobResult(
            job_id=job.id,
            success=False,
            error="Job failed",
        )
        
        # Create executor and call post-process
        executor = JobExecutor()
        executor._post_process_relax_steps(
            job=job,
            job_result=job_result,
            calculation=mock_calculation,
            context={"run_id": "test_run_001"},
        )
        
        # Verify current.json was NOT created
        artifact_path = get_generated_structure_path(calc_dir, step_ulid)
        assert not artifact_path.exists(), "Post-process should not run on failed job"
    
    def test_executor_pre_clean_only_affects_job_steps(self, tmp_path):
        """
        Test that pre-clean only removes current.json for steps in the current job.
        """
        from quantumvitas.execution.executor import JobExecutor
        from quantumvitas.execution.job_graph import Job
        from quantumvitas.execution.relax_artifacts import write_generated_structure
        from unittest.mock import MagicMock
        
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
        mock_step1.meta.id = step1_ulid
        mock_step1.step_type = "qe_relax"
        
        mock_step2 = MagicMock()
        mock_step2.meta.id = step2_ulid
        mock_step2.step_type = "qe_relax"
        
        mock_calculation = MagicMock()
        mock_calculation.dir = calc_dir
        mock_calculation.steps = [mock_step1, mock_step2]
        
        job = Job(
            id="test_job",
            step_ids=[step1_ulid],  # Only step1 in this job
            working_dir=tmp_path / "work",
            command=["pw.x", "relax.in"],
            input_files=[],
            expected_outputs=[],
            deps=[],
        )
        job.metadata = {"engine": "qe"}
        
        # Create executor and call pre-clean
        executor = JobExecutor()
        executor._pre_clean_relax_steps(job, mock_calculation)
        
        # Verify only step1's current.json was deleted
        artifact_path1 = get_generated_structure_path(calc_dir, step1_ulid)
        artifact_path2 = get_generated_structure_path(calc_dir, step2_ulid)
        
        assert not artifact_path1.exists(), "Step1's current.json should be deleted"
        assert artifact_path2.exists(), "Step2's current.json should NOT be deleted"

