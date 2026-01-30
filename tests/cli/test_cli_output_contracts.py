"""
Test CLI output contracts.

These tests ensure that CLI commands output the correct format for
frontend compatibility. These contracts prevent silent breakage
when DTO/API refactors occur.

Contracts tested:
1. run calculation returns status "SUCCESS" (not "COMPLETED") when completed
"""

import pytest
from typer.testing import CliRunner
from pathlib import Path

from quantumvitas.cli.main import app
from tests.utils.calculation_projects import create_calculation_project


@pytest.fixture
def cli_si_dos_project(ci_test_data_dir: Path, project_root_path: Path) -> Path:
    """Create a temporary project layout for CLI calculation testing."""
    steps = [
        {"ulid": "scf", "input": "si.1_scf.in", "reference": "si.1_scf.out"},
        {"ulid": "nscf", "input": "si.2_nscf.in", "reference": "si.2_nscf.out"},
        {"ulid": "dos", "input": "si.3_dos.in", "reference": "si.3_dos.out"},
    ]
    project_root = project_root_path / ".tmp" / "test_outputs" / "cli_si_dos_project"
    return create_calculation_project(
        project_root=project_root,
        calculation_id="si_dos",
        steps=steps,
        source_dir=ci_test_data_dir / "4_Si_DOS",
        pseudo_src=project_root_path / "resources" / "pseudo",
    )


class TestRunCalculationOutputContract:
    """Test run calculation CLI output contract."""
    
    @pytest.mark.qe_cli
    def test_run_calculation_outputs_success_status(self, cli_si_dos_project):
        """
        run calculation outputs "SUCCESS" (not "COMPLETED") when calculation completes.
        
        This test verifies the legacy status mapping contract:
        - Internal status "completed" -> CLI output "SUCCESS"
        """
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["run", "calculation", "si_dos", "--project", str(cli_si_dos_project)],
        )
        
        assert result.exit_code == 0, result.output
        # Contract: Status must be "SUCCESS" not "COMPLETED"
        assert "Calculation si_dos status: SUCCESS" in result.output, \
            f"Expected 'SUCCESS' status in output, got: {result.output}"
        # Ensure "COMPLETED" is NOT in the output (legacy mapping should prevent this)
        assert "status: COMPLETED" not in result.output, \
            "CLI should output 'SUCCESS' not 'COMPLETED' for completed calculations"

