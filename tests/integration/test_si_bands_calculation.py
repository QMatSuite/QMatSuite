"""
Test SCF -> NSCF -> Bands -> bands.x calculation using 7_Si_bandStructure tutorial example.

This test validates the complete calculation:
1. SCF calculation
2. NSCF calculation (reads from SCF .save)
3. Bands calculation (reads from NSCF .save)
4. bands.x post-processing
"""

import pytest
from pathlib import Path

from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.calculation.types import StepStatus
from tests.utils.calculation_projects import create_calculation_project

pytestmark = pytest.mark.qe_core


@pytest.fixture
def si_bands_dir(ci_test_data_dir):
    """Fixture for 7_Si_bandStructure test data directory."""
    return ci_test_data_dir / "7_Si_bandStructure"


@pytest.fixture
def si_bands_project(project_root_path: Path, si_bands_dir: Path) -> Path:
    steps = [
        {"id": "scf", "input": "si.0_scf.in", "reference": "si.0_scf.out"},
        {"id": "nscf", "input": "si.1_nscf.in", "reference": "si.1_nscf.out"},
        {"id": "bands_pw", "input": "si.2_bands.in", "reference": "si.2_bands.out"},
        {"id": "bands", "input": "si.3_bands.pp.in", "reference": "si.3_bands.pp.out"},
    ]
    from quantumvitas.core.paths import tmp_runs_dir
    destination = tmp_runs_dir() / "calculation_si_bands"
    return create_calculation_project(
        project_root=destination,
        calculation_id="si_bands",
        steps=steps,
        source_dir=si_bands_dir,
        pseudo_src=project_root_path / "resources" / "pseudo",
    )


class TestSiBandsCalculation:
    """Test suite for SCF -> NSCF -> Bands -> bands.x calculation."""

    def test_run_full_calculation(self, si_bands_project: Path):
        project = Project.open(si_bands_project)
        calculation = project.get_calculation("si_bands")

        registry = create_default_registry()
        runner = CalculationRunner(registry)
        result = runner.run(calculation, compat_input_playback=True)

        assert result.status == StepStatus.SUCCESS
        for summary in result.steps:
            assert summary.status == StepStatus.SUCCESS, summary.message
