"""
Test SCF -> NSCF -> DOS calculation using 4_Si_DOS tutorial example.

This test validates the complete calculation:
1. SCF calculation
2. NSCF calculation (reads from SCF .save)
3. DOS calculation (reads from NSCF .save)
"""

from pathlib import Path

import pytest

from qmatsuite.core.resources import get_resources_dir
from qmatsuite.engine.registry import create_default_registry
from qmatsuite.project.model import Project
from qmatsuite.calculation.runner import CalculationRunner
from qmatsuite.calculation.types import StepStatus
from tests.utils.calculation_projects import create_calculation_project

pytestmark = pytest.mark.qe_core


@pytest.fixture
def si_dos_dir(ci_test_data_dir):
    """Fixture for 4_Si_DOS test data directory."""
    return ci_test_data_dir / "4_Si_DOS"


@pytest.fixture
def si_dos_project(project_root_path: Path, si_dos_dir: Path) -> Path:
    steps = [
        {"ulid": "scf", "input": "si.1_scf.in", "reference": "si.1_scf.out"},
        {"ulid": "nscf", "input": "si.2_nscf.in", "reference": "si.2_nscf.out"},
        {"ulid": "dos", "input": "si.3_dos.in", "reference": "si.3_dos.out"},
    ]
    from qmatsuite.core.paths import tmp_runs_dir
    destination = tmp_runs_dir() / "calculation_si_dos"
    return create_calculation_project(
        project_root=destination,
        calculation_id="si_dos",
        steps=steps,
        source_dir=si_dos_dir,
        pseudo_src=get_resources_dir() / "pseudo",
    )


class TestSiDOSCalculation:
    """Test suite for SCF -> NSCF -> DOS calculation."""

    def test_run_full_calculation(self, si_dos_project: Path):
        project = Project.open(si_dos_project)
        calculation = project.get_calculation("si_dos")

        registry = create_default_registry()
        runner = CalculationRunner(registry)
        result = runner.run(calculation, compat_input_playback=True)

        assert result.status == StepStatus.SUCCESS
        for summary in result.steps:
            assert summary.status == StepStatus.SUCCESS, summary.message
