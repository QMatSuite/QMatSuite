"""
Tests for step parameter defaults behavior.

This module tests two distinct scenarios:
A. "Create step from scratch" - uses QMS's in-code defaults
B. "Import from QE input" - preserves original parameters, no defaults injected
"""
import shlex
import yaml
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qmatsuite.cli.main import app
from qmatsuite.io import QEInputParser
from qmatsuite.calculation.structure_steps import StructureStepSpec, generate_qe_input_from_spec
from qmatsuite.io import read_structure


def _param_map_from_qe_input(qe_input):
    """Extract non-structural parameters from QE input as a dict."""
    STRUCTURAL_KEYS = {"ibrav", "nat", "ntyp", "a", "b", "c", "cosab", "cosac", "cosbc"}
    result = {}
    for nl in qe_input.namelists:
        params = dict(nl.parameters)
        # Remove structural parameters from comparison
        for key in list(params.keys()):
            lower_key = str(key).lower()
            if lower_key in STRUCTURAL_KEYS or lower_key.startswith("celldm"):
                del params[key]
        if params:
            result[nl.name.upper()] = params
    return result


class TestStepDefaultsFromScratch:
    """Test Scenario A: Creating steps from scratch uses QMS defaults."""
    
    def test_init_step_scf_uses_defaults(self, tmp_path: Path):
        """Test that creating a step from scratch includes QMS's default parameters."""
        runner = CliRunner()
        project_root = tmp_path / "proj"
        
        # Create project
        result = runner.invoke(app, ["init", "project", "--path", str(project_root)])
        assert result.exit_code == 0, result.stdout
        
        # Create structure
        from pymatgen.core import Lattice, Structure
        structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
        si_cif = tmp_path / "si.cif"
        structure.to(fmt="cif", filename=str(si_cif))
        
        result = runner.invoke(
            app,
            [
                "import-structure",
                str(si_cif),
                "--project",
                str(project_root),
                "--name",
                "si",
            ],
        )
        assert result.exit_code == 0, result.stdout
        
        # Create calculation
        result = runner.invoke(
            app,
            [
                "init",
                "calculation",
                "test_wf",
                "--structure",
                "si",
                "--project",
                str(project_root),
                "--engine-family",
                "qe",
            ],
        )
        assert result.exit_code == 0, result.stdout
        
        # Create step from scratch (no --no-defaults flag)
        result = runner.invoke(
            app,
            [
                "init",
                "step",
                "scf",
                "--structure",
                "si",
                "--calculation",
                "test_wf",
                "--project",
                str(project_root),
            ],
        )
        assert result.exit_code == 0, result.stdout
        
        # Load the step spec
        from qmatsuite.core.resources import slugify
        calculation_slug = slugify("test_wf")
        calculation_dir = project_root / "calculations" / calculation_slug
        step_spec_path = calculation_dir / "steps" / "scf.step.yaml"
        assert step_spec_path.exists(), "Step spec should be created"
        
        spec = StructureStepSpec.from_yaml(step_spec_path)
        
        # Verify defaults are present in the spec
        assert "CONTROL" in spec.parameters
        assert "outdir" in spec.parameters["CONTROL"]
        assert spec.parameters["CONTROL"]["outdir"] == "./outdir"
        assert "restart_mode" in spec.parameters["CONTROL"]
        assert spec.parameters["CONTROL"]["restart_mode"] == "from_scratch"
        
        assert "ELECTRONS" in spec.parameters
        assert "conv_thr" in spec.parameters["ELECTRONS"]
        assert abs(spec.parameters["ELECTRONS"]["conv_thr"] - 1.0e-08) < 1e-12
        
        # For standalone mode, add species_overrides if not present
        # (in project runs, species_map from calculation.yaml would be used instead)
        if not spec.species_overrides:
            spec.species_overrides = {"Si": {"pseudopot": "Si.upf"}}
        
        # Generate QE input from spec
        structure_obj = read_structure(project_root / "structures" / "si.json")
        qe_input, _ = generate_qe_input_from_spec(structure_obj, spec)
        
        # Verify defaults are in the generated QE input
        params = _param_map_from_qe_input(qe_input)
        assert "CONTROL" in params
        assert "outdir" in params["CONTROL"]
        assert "restart_mode" in params["CONTROL"]
        assert "ELECTRONS" in params
        assert "conv_thr" in params["ELECTRONS"]


class TestStepDefaultsImportFromInput:
    """Test Scenario B: Importing from QE input preserves original parameters."""
    
    def test_import_step_from_qe_input_does_not_inject_defaults(
        self, ci_test_data_dir: Path, tmp_path: Path
    ):
        """Test that importing a step from QE input does NOT inject defaults."""
        runner = CliRunner()
        project_root = tmp_path / "proj"
        
        # Create project
        result = runner.invoke(app, ["init", "project", "--path", str(project_root)])
        assert result.exit_code == 0, result.stdout
        
        # Get a test input file
        from tests.core.test_data import load_test_cases
        pw_dir = ci_test_data_dir / "pw_single_tests"
        cases = load_test_cases(pw_dir, ci_root=ci_test_data_dir)
        assert cases, "No test cases found"
        
        # Use the first test case
        input_path = cases[0].input_path
        structure_name = f"struct_{input_path.stem}"
        calculation_name = f"wf_{input_path.stem}"
        
        # Import structure
        result = runner.invoke(
            app,
            [
                "import-structure",
                str(input_path),
                "--project",
                str(project_root),
                "--name",
                structure_name,
            ],
        )
        assert result.exit_code == 0, result.stdout
        
        # Create calculation
        result = runner.invoke(
            app,
            [
                "init",
                "calculation",
                calculation_name,
                "--structure",
                structure_name,
                "--project",
                str(project_root),
                "--engine-family",
                "qe",
            ],
        )
        assert result.exit_code == 0, result.stdout
        
        # Parse original input to get its parameters
        original_qe = QEInputParser.parse_file(input_path)
        original_params = _param_map_from_qe_input(original_qe)
        
        # Use show-command to get the import command (which includes --no-defaults)
        show_output = runner.invoke(app, ["show-command", str(input_path)])
        assert show_output.exit_code == 0, show_output.stdout
        
        # Extract the command (should include --no-defaults)
        init_line = next(
            line.strip()
            for line in show_output.stdout.splitlines()
            if line.strip().startswith("qms init step")
        )
        init_args = shlex.split(init_line)[1:]
        
        # Add required calculation/structure/project args
        init_args.extend([
            "--structure", structure_name,
            "--calculation", calculation_name,
            "--project", str(project_root)
        ])
        
        # Verify --no-defaults is in the command
        assert "--no-defaults" in init_args, "show-command should suggest --no-defaults"
        
        # Create step using the import command
        init_result = runner.invoke(app, init_args)
        assert init_result.exit_code == 0, init_result.stdout
        
        # Load the step spec
        from qmatsuite.core.resources import slugify
        from qmatsuite.core.resolution import require_step
        calculation_slug = slugify(calculation_name)
        calculation_dir = project_root / "calculations" / calculation_slug
        calculation_yaml = yaml.safe_load((calculation_dir / "calculation.yaml").read_text())
        last_step = calculation_yaml["steps"][-1]
        # ID-only model: use step_id (ULID) to resolve step file
        step_id = last_step.get("step_ulid") or last_step.get("ulid")
        assert step_id, "Step entry should have step_id"
        # Resolve step to get its file path
        step_resolved = require_step(project_root, calculation_slug, step_id)
        step_spec_path = step_resolved.absolute_path
        
        spec = StructureStepSpec.from_yaml(step_spec_path)
        
        # Generate QE input from spec
        structure_obj = read_structure(project_root / "structures" / f"{structure_name}.json")
        qe_input, _ = generate_qe_input_from_spec(structure_obj, spec)
        
        # Extract parameters from generated input
        generated_params = _param_map_from_qe_input(qe_input)
        
        # Compare: generated should match original (no defaults injected)
        # Note: We compare section by section to allow for minor differences in structure
        for section, original_section_params in original_params.items():
            assert section in generated_params, f"Section {section} missing in generated"
            generated_section_params = generated_params[section]
            
            # Check that generated doesn't have extra keys that weren't in original
            for key in generated_section_params:
                if key not in original_section_params:
                    # This is a default that was injected - should not happen
                    pytest.fail(
                        f"Generated input has key '{key}' in section '{section}' "
                        f"that wasn't in original. This indicates defaults were injected."
                    )
            
            # Check that values match (for keys present in original)
            for key, original_value in original_section_params.items():
                if key in generated_section_params:
                    generated_value = generated_section_params[key]
                    # Allow for small floating point differences
                    if isinstance(original_value, float) and isinstance(generated_value, float):
                        assert abs(original_value - generated_value) < 1e-10, (
                            f"Value mismatch for {section}.{key}: "
                            f"original={original_value}, generated={generated_value}"
                        )
                    else:
                        assert generated_value == original_value, (
                            f"Value mismatch for {section}.{key}: "
                            f"original={original_value}, generated={generated_value}"
                        )

