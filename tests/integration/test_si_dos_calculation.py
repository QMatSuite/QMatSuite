"""
Test SCF -> NSCF -> DOS calculation using 4_Si_DOS tutorial example.

This test validates the complete calculation:
1. SCF calculation
2. NSCF calculation (reads from SCF .save)
3. DOS calculation (reads from NSCF .save)
"""

from pathlib import Path

import pytest

from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.calculation.types import StepStatus
from tests.utils.calculation_projects import create_calculation_project

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
    from quantumvitas.core.paths import tmp_runs_dir
    destination = tmp_runs_dir() / "calculation_si_dos"
    return create_calculation_project(
        project_root=destination,
        calculation_id="si_dos",
        steps=steps,
        source_dir=si_dos_dir,
        pseudo_src=project_root_path / "resources" / "pseudo",
    )


class TestSiDOSCalculation:
    """Test suite for SCF -> NSCF -> DOS calculation."""

    def test_run_full_calculation(self, si_dos_project: Path):
        project = Project.open(si_dos_project)
        calculation = project.get_calculation("si_dos")

        registry = create_default_registry()
        runner = CalculationRunner(registry)
        result = runner.run(calculation)

        assert result.status == StepStatus.SUCCESS
        for summary in result.steps:
            assert summary.status == StepStatus.SUCCESS, summary.message
