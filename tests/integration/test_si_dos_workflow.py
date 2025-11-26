"""
Test SCF -> NSCF -> DOS workflow using 4_Si_DOS tutorial example.

This test validates the complete workflow:
1. SCF calculation
2. NSCF calculation (reads from SCF .save)
3. DOS calculation (reads from NSCF .save)
"""

from pathlib import Path

import pytest

from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.workflow.runner import WorkflowRunner
from quantumvitas.workflow.types import StepStatus
from tests.utils.workflow_projects import create_workflow_project

pytestmark = pytest.mark.qe_core


@pytest.fixture
def si_dos_dir(ci_test_data_dir):
    """Fixture for 4_Si_DOS test data directory."""
    return ci_test_data_dir / "4_Si_DOS"


@pytest.fixture
def si_dos_project(project_root_path: Path, si_dos_dir: Path) -> Path:
    steps = [
        {"id": "scf", "input": "si.1_scf.in", "reference": "si.1_scf.out"},
        {"id": "nscf", "input": "si.2_nscf.in", "reference": "si.2_nscf.out"},
        {"id": "dos", "input": "si.3_dos.in", "reference": "si.3_dos.out"},
    ]
    destination = project_root_path / "temp" / "test_outputs" / "workflow_si_dos"
    return create_workflow_project(
        project_root=destination,
        workflow_id="si_dos",
        steps=steps,
        source_dir=si_dos_dir,
        pseudo_src=project_root_path / "pseudo",
    )


class TestSiDOSWorkflow:
    """Test suite for SCF -> NSCF -> DOS workflow."""

    def test_run_full_workflow(self, si_dos_project: Path):
        project = Project.open(si_dos_project)
        workflow = project.get_workflow("si_dos")

        registry = create_default_registry()
        runner = WorkflowRunner(registry)
        result = runner.run(workflow)

        assert result.status == StepStatus.SUCCESS
        for summary in result.steps:
            assert summary.status == StepStatus.SUCCESS, summary.message
