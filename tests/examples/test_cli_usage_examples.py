"""
Example tests demonstrating CLI usage patterns.

These tests serve as both documentation and validation of the CLI commands.
They use the Typer CliRunner to simulate actual CLI invocations.
"""

import json
from pathlib import Path

import pytest
import yaml
from pymatgen.core import Lattice, Structure
from typer.testing import CliRunner

from quantumvitas.cli.main import app
from quantumvitas.io import read_structure, write_structure


@pytest.fixture
def sample_project(tmp_path):
    """Create a sample project structure for testing."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # Create project.qv.yml
    project_config = {
        "project": {"name": "test_project"},
        "calculations": [],
        "structures": [],
    }
    (project_root / "project.qv.yml").write_text(
        yaml.safe_dump(project_config, sort_keys=False)
    )

    # Create structures directory
    (project_root / "structures").mkdir()

    # Create a sample CIF file
    lattice = Lattice.cubic(5.43)
    structure = Structure(
        lattice,
        ["Si", "Si"],
        [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
    )
    cif_file = tmp_path / "si.cif"
    write_structure(structure, cif_file, format="cif")

    return project_root, cif_file


class TestImportStructureCommand:
    """Examples of using `qv import-structure` command."""

    def test_import_structure_from_cif(self, sample_project):
        """
        Example: Import structure from CIF file.

        This demonstrates the basic usage of `qv import-structure`.
        """
        project_root, cif_file = sample_project
        runner = CliRunner()

        # Run import-structure command
        result = runner.invoke(
            app,
            [
                "import-structure",
                str(cif_file),
                "--id",
                "si",
                "--project",
                str(project_root),
            ],
        )

        assert result.exit_code == 0
        assert "Imported structure" in result.stdout

        # Verify structure file was created
        structure_file = project_root / "structures" / "si.json"
        assert structure_file.exists()

        # Verify structure can be loaded
        loaded = read_structure(structure_file, format="json")
        assert loaded.formula == "Si2"

        # Verify project.qv.yml was updated
        # ID-only model: entries only have structure_id, not name/file/meta
        config = yaml.safe_load((project_root / "project.qv.yml").read_text())
        structures = config.get("structures", [])
        assert len(structures) == 1
        entry = structures[0]
        assert "structure_id" in entry, "Structure entry should have structure_id (ID-only model)"
        # Resolve structure from registry to verify name and slug
        from quantumvitas.core.resolution import build_resource_index, require_structure
        index = build_resource_index(project_root)
        resolved = require_structure(project_root, entry["structure_id"], index=index)
        assert resolved.meta.name == "si", f"Structure name should be 'si'. Found: {resolved.meta.name}"
        assert resolved.meta.slug == "si", f"Structure slug should be 'si'. Found: {resolved.meta.slug}"
        assert resolved.meta.path == "structures/si.json", f"Structure path should be 'structures/si.json'. Found: {resolved.meta.path}"

    def test_import_structure_with_custom_format(self, sample_project):
        """
        Example: Import structure with custom output format.

        You can specify the output format (default is json).
        """
        project_root, cif_file = sample_project
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "import-structure",
                str(cif_file),
                "--id",
                "si_cif",
                "--project",
                str(project_root),
                "--output-format",
                "cif",
            ],
        )

        assert result.exit_code == 0

        # Verify CIF file was created
        structure_file = project_root / "structures" / "si_cif.cif"
        assert structure_file.exists()

    def test_import_structure_duplicate_id_fails(self, sample_project):
        """
        Example: Import fails if structure ID already exists.

        This prevents accidentally overwriting existing structures.
        """
        project_root, cif_file = sample_project
        runner = CliRunner()

        # First import
        result1 = runner.invoke(
            app,
            [
                "import-structure",
                str(cif_file),
                "--id",
                "si",
                "--project",
                str(project_root),
            ],
        )
        assert result1.exit_code == 0

        # Second import with same ID should fail
        result2 = runner.invoke(
            app,
            [
                "import-structure",
                str(cif_file),
                "--id",
                "si",
                "--project",
                str(project_root),
            ],
        )
        assert result2.exit_code != 0
        # Typer errors show in the output (stdout/stderr combined by default)
        assert "conflicts with an existing entry" in result2.output


class TestRunStructureCommand:
    """Examples of using `qv run structure` command."""

    def test_run_structure_basic(self, sample_project, monkeypatch):
        """
        Example: Run structure with basic parameters.

        This demonstrates generating a QE input from a structure and running it.
        Note: This test mocks the QE execution to avoid requiring QE binaries.
        """
        project_root, cif_file = sample_project
        runner = CliRunner()

        # First import the structure
        result = runner.invoke(
            app,
            [
                "import-structure",
                str(cif_file),
                "--id",
                "si",
                "--project",
                str(project_root),
            ],
        )
        assert result.exit_code == 0

        # Mock QE execution to avoid requiring actual QE binaries
        def mock_run_input_step(*args, **kwargs):
            from quantumvitas.core.engines.qe_calculation import StepResult
            from quantumvitas.calculation.input_runner import PreparedInputStep

            working_dir = kwargs.get("working_dir", Path("temp"))
            return (
                StepResult(
                    step_type="scf",
                    output_file=working_dir / "si.pw.out",
                    return_code=0,
                    message="JOB DONE",
                ),
                PreparedInputStep(
                    working_dir=working_dir,
                    original_input=working_dir / "si.pw.in",
                    modified_input=working_dir / "si.pw.in",
                    project_root=project_root,
                ),
            )

        # Note: In a real test, you'd need to properly mock the engine
        # This is a simplified example showing the expected behavior

    def test_run_structure_with_parameter_overrides(self, sample_project):
        """
        Example: Run structure with parameter overrides.

        This shows how to pass QE parameters via CLI flags.
        """
        project_root, cif_file = sample_project
        runner = CliRunner()

        # Import structure
        runner.invoke(
            app,
            [
                "import-structure",
                str(cif_file),
                "--id",
                "si",
                "--project",
                str(project_root),
            ],
        )

        # Note: Actual execution would require QE binaries
        # This example shows the command syntax
        command = [
            "run",
            "structure",
            "si",
            "--project",
            str(project_root),
            "--ecutwfc=60",
            "--ecutrho=240",
            "--degauss=0.01",
        ]

        # In a real scenario, this would generate and run the QE input
        # with the specified parameters


class TestRunStepCommand:
    """Examples of using `qv run step` command with parameter overrides."""

    def test_run_step_with_overrides(self, tmp_path, sample_project):
        """
        Example: Run QE input file with parameter overrides.

        This demonstrates how to modify QE parameters via CLI.
        """
        project_root, _ = sample_project

        # Create a sample QE input file
        qe_input_file = tmp_path / "si.scf.in"
        qe_input_file.write_text(
            """&CONTROL
    calculation = 'scf'
/
&SYSTEM
    ecutwfc = 30.0
/
&ELECTRONS
/
ATOMIC_SPECIES
Si  28.085  Si.upf
ATOMIC_POSITIONS angstrom
Si  0.0  0.0  0.0
Si  1.3575  1.3575  1.3575
CELL_PARAMETERS angstrom
   5.430000  0.000000  0.000000
   0.000000  5.430000  0.000000
   0.000000  0.000000  5.430000
K_POINTS automatic
4 4 4 0 0 0
"""
        )

        runner = CliRunner()

        # Note: Actual execution would require QE binaries
        # This example shows the command syntax
        command = [
            "run",
            "step",
            str(qe_input_file),
            "--project",
            str(project_root),
            "--ecutwfc=60",
            "--ecutrho=240",
            "--degauss=0.01",
        ]

        # In a real scenario, this would:
        # 1. Parse the input file
        # 2. Apply the overrides (ecutwfc=60, ecutrho=240, degauss=0.01)
        # 3. Run the calculation with modified parameters


class TestParameterOverrideParsing:
    """Examples of parameter override syntax and parsing."""

    def test_parse_simple_overrides(self):
        """
        Example: Parse simple parameter overrides.

        This demonstrates the internal parsing logic.
        """
        from quantumvitas.cli.main import _parse_override_args

        # Simple integer
        bundle = _parse_override_args(["--ecutwfc=60"])
        overrides = bundle.parameters
        assert len(overrides) == 1
        assert overrides[0].name == "ecutwfc"
        assert overrides[0].value == 60

        # Simple float
        bundle = _parse_override_args(["--degauss=0.01"])
        overrides = bundle.parameters
        assert len(overrides) == 1
        assert overrides[0].name == "degauss"
        assert overrides[0].value == 0.01

        # Boolean (true)
        bundle = _parse_override_args(["--tprnfor"])
        overrides = bundle.parameters
        assert len(overrides) == 1
        assert overrides[0].name == "tprnfor"
        assert overrides[0].value is True

        # Boolean (false)
        bundle = _parse_override_args(["--tprnfor=false"])
        overrides = bundle.parameters
        assert len(overrides) == 1
        assert overrides[0].name == "tprnfor"
        assert overrides[0].value is False

    def test_parse_section_prefixed_overrides(self):
        """
        Example: Parse section-prefixed parameter overrides.

        Use SECTION.parameter syntax when needed.
        """
        from quantumvitas.cli.main import _parse_override_args

        # Section-prefixed
        bundle = _parse_override_args(["--SYSTEM.ecutwfc=60"])
        overrides = bundle.parameters
        assert len(overrides) == 1
        assert overrides[0].name == "ecutwfc"
        assert overrides[0].section == "SYSTEM"
        assert overrides[0].value == 60

        # Multiple overrides
        bundle = _parse_override_args(
            [
                "--ecutwfc=60",
                "--ecutrho=240",
                "--SYSTEM.degauss=0.01",
            ]
        )
        overrides = bundle.parameters
        assert len(overrides) == 3
        assert overrides[0].name == "ecutwfc"
        assert overrides[1].name == "ecutrho"
        assert overrides[2].name == "degauss"
        assert overrides[2].section == "SYSTEM"

    def test_parse_list_overrides(self):
        """
        Example: Parse list/array parameter overrides.

        Lists can be specified in multiple formats.
        """
        from quantumvitas.cli.main import _parse_override_args

        # Card override via explicit CARD. prefix
        bundle = _parse_override_args(['--CARD.K_POINTS.data=[[6,6,6,0,0,0]]'])
        assert bundle.card_overrides["K_POINTS"]["data"][0] == [6, 6, 6, 0, 0, 0]

        # Card override fallback without explicit section
        bundle = _parse_override_args(["--k_points=automatic:8,8,8,0,0,0"])
        assert bundle.card_overrides["K_POINTS"]["option"] == "automatic"
        assert bundle.card_overrides["K_POINTS"]["data"][0] == [8, 8, 8, 0, 0, 0]

        # Species override
        bundle = _parse_override_args(["--species.Si.mass=28.0855"])
        assert bundle.species_overrides["Si"]["mass"] == 28.0855


class TestCompleteCalculationExample:
    """Complete calculation example combining multiple commands."""

    def test_complete_calculation_import_and_run(self, sample_project):
        """
        Example: Complete calculation from structure import to calculation.

        This demonstrates a typical user calculation:
        1. Import structure from external file
        2. Run calculation with parameters
        """
        project_root, cif_file = sample_project
        runner = CliRunner()

        # Step 1: Import structure
        result1 = runner.invoke(
            app,
            [
                "import-structure",
                str(cif_file),
                "--id",
                "si",
                "--project",
                str(project_root),
            ],
        )
        assert result1.exit_code == 0

        # Verify structure was imported
        structure_file = project_root / "structures" / "si.json"
        assert structure_file.exists()

        # Step 2: Run calculation (would require QE binaries in real scenario)
        # This shows the command that would be run:
        command = [
            "run",
            "structure",
            "si",
            "--project",
            str(project_root),
            "--ecutwfc=60",
            "--ecutrho=240",
            "--degauss=0.01",
            "--CARD.K_POINTS.data=[[6,6,6,0,0,0]]",
        ]

        # In a real scenario, this would:
        # 1. Load structure from structures/si.json
        # 2. Generate QE input via qe_input_from_structure
        # 3. Apply parameter overrides
        # 4. Run the calculation
        # 5. Save output to working directory

