"""
Unit test for graphene calculation setup via CLI.

This test verifies the exact CLI command sequence from manual_tests/instructions:
- qms init project --name graphene_project
- cd graphene_project
- qms import-structure tests/data/13_graphene/graphene.2_scf.in
- qms init calculation "graphene bands" --structure C
- cd calculations/graphene-bands
- qms init step scf                 # Should auto-detect parent calculation + structure
- qms configure calculation --name "graph"

This is a unit test (no QE execution required).
"""

import yaml
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qmatsuite.cli.main import app

pytestmark = pytest.mark.unit


def test_graphene_calculation_setup(ci_test_data_dir: Path, tmp_path: Path):
    """Test the complete graphene calculation setup sequence from instructions."""
    runner = CliRunner()
    
    # Get the graphene input file
    graphene_input = ci_test_data_dir / "13_graphene" / "graphene.2_scf.in"
    if not graphene_input.exists():
        pytest.skip(f"Graphene test data not found: {graphene_input}")
    
    # Use isolated filesystem to simulate cd commands
    with runner.isolated_filesystem() as fs:
        fs_path = Path(fs)
        
        # Step 1: Create project
        # qms init project --name graphene_project
        result = runner.invoke(
            app,
            ["init", "project", "--name", "graphene_project"],
        )
        assert result.exit_code == 0, f"Project init failed: {result.stdout}"
        
        # Project is created with slugified name (underscores preserved in slugify)
        # Check what was actually created
        project_dirs = [d for d in fs_path.iterdir() if d.is_dir() and d.name.startswith("graphene")]
        assert len(project_dirs) > 0, f"No project directory found. Created dirs: {list(fs_path.iterdir())}"
        project_dir = project_dirs[0]
        assert (project_dir / "project.qms.yml").exists(), f"project.qms.yml not found in {project_dir}"
        assert (project_dir / "project.qms.yml").exists()
        
        # Verify project name
        project_config = yaml.safe_load((project_dir / "project.qms.yml").read_text())
        assert project_config["project"]["name"] == "graphene_project"
        
        # Step 2: cd graphene_project (simulated by changing working directory)
        # In isolated_filesystem, we need to work from project_dir
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            
            # Step 3: Import structure
            # qms import-structure $PYTHONSRC/tests/data/13_graphene/graphene.2_scf.in
            result = runner.invoke(
                app,
                [
                    "import-structure",
                    str(graphene_input),
                    "--id",
                    "C",
                ],
            )
            assert result.exit_code == 0, f"Import structure failed: {result.stdout}"
            
            # Verify structure was imported
            structures_dir = project_dir / "structures"
            assert structures_dir.exists()
            structure_files = list(structures_dir.glob("*.json"))
            assert len(structure_files) > 0, "Structure file should be created"
            
            # Verify structure is registered in project config
            # ID-only model: project.qms.yml only has structure_ulid, not name
            # Resolve structure from registry to get its name
            project_config = yaml.safe_load((project_dir / "project.qms.yml").read_text())
            structures = project_config.get("structures", [])
            assert len(structures) > 0, "Structure should be registered"
            # In ID-only model, entries have structure_ulid (ULID), not name
            # Resolve the structure to get its meta.name
            from qmatsuite.core.resolution import build_resource_index, require_structure
            index = build_resource_index(project_dir)
            structure_ulid = structures[0].get("structure_ulid")
            assert structure_ulid is not None, "Structure entry should have structure_ulid"
            resolved = require_structure(project_dir, structure_ulid, index=index)
            assert resolved.meta.name == "C", f"Structure name should be 'C'. Found: {resolved.meta.name}"
            
            # Step 4: Create calculation
            # qms init calculation "graphene bands" --structure C
            result = runner.invoke(
                app,
                [
                    "init",
                    "calculation",
                    "graphene bands",
                    "--structure",
                    "C",
                    "--engine-family",
                    "qe",
                ],
            )
            assert result.exit_code == 0, f"Calculation init failed: {result.stdout}"
            
            # Verify calculation directory and files
            calculation_dir = project_dir / "calculations" / "graphene-bands"
            assert calculation_dir.exists()
            assert (calculation_dir / "calculation.yaml").exists()
            
            # Verify calculation.yaml content
            calculation_data = yaml.safe_load((calculation_dir / "calculation.yaml").read_text())
            # Structure reference uses ID (structure_ulid is canonical)
            # Note: structure_ulid may be set even if structure selector is also present (backwards compat)
            assert "structure_ulid" in calculation_data or "structure" in calculation_data, \
                "Calculation should have structure_ulid or structure (for backwards compat)"
            if "structure_ulid" not in calculation_data:
                # If only structure selector is present, it should be resolved to structure_ulid on next load
                # For now, just verify structure is present
                assert calculation_data.get("structure") == "C"
            assert calculation_data["steps"] == []
            
            # Verify calculation is registered in project config
            # API model: project.qms.yml has meta with ulid, name, slug, path
            # Resolve calculation from registry to get its name
            project_config = yaml.safe_load((project_dir / "project.qms.yml").read_text())
            calculations = project_config.get("calculations", [])
            assert len(calculations) > 0, "Calculation should be registered"
            from qmatsuite.core.resolution import build_resource_index, require_calculation
            index = build_resource_index(project_dir)
            calculation_id = (calculations[0].get("meta") or {}).get("ulid")
            assert calculation_id is not None, "Calculation entry should have meta.ulid"
            resolved = require_calculation(project_dir, calculation_id, index=index)
            assert resolved.meta.name == "graphene bands", f"Calculation name should be 'graphene bands'. Found: {resolved.meta.name}"
            
            # Step 5: cd calculations/graphene-bands
            os.chdir(calculation_dir)
            
            # Step 6: Create SCF step (should auto-detect calculation and structure)
            # qms init step scf
            result = runner.invoke(
                app,
                ["init", "step", "scf"],
            )
            assert result.exit_code == 0, f"Step init failed: {result.stdout}"
            
            # Verify step was created
            steps_dir = calculation_dir / "steps"
            assert steps_dir.exists()
            scf_step_file = steps_dir / "scf.step.yaml"
            assert scf_step_file.exists()
            
            # Verify step content
            step_data = yaml.safe_load(scf_step_file.read_text())
            assert step_data["step_type_spec"] == "qe_scf"
            # DAG model: Step YAML should NOT contain structure_ulid or parent_calculation_id
            # Structure is resolved via calculation.structure_ulid at runtime
            assert "structure_ulid" not in step_data, "Step YAML should not contain structure_ulid (DAG model)"
            assert "parent_calculation_id" not in step_data, "Step YAML should not contain parent_calculation_id (DAG model)"
            # Verify calculation has structure_ulid set
            calculation_data = yaml.safe_load((calculation_dir / "calculation.yaml").read_text())
            assert calculation_data.get("structure_ulid") is not None, "Calculation should have structure_ulid set"
            
            # Verify step is in calculation.yaml
            calculation_data = yaml.safe_load((calculation_dir / "calculation.yaml").read_text())
            # Steps now use step_id (ULID) instead of id (slug)
            step_ids = [s.get("step_ulid") or s.get("ulid") for s in calculation_data.get("steps", [])]
            assert len(step_ids) > 0, "SCF step should be in calculation"
            # Verify step entry has step_id (ULID) - step_file is NOT stored (resolved via registry)
            step_entry = calculation_data.get("steps", [])[0]
            assert step_entry.get("step_ulid") is not None, "Step entry should have step_id (ULID)"
            # step_file is NOT stored in calculation.yaml - step location resolved via registry using step_id
            assert "step_file" not in step_entry or step_entry.get("step_file") is None, \
                "step_file should not be stored in calculation.yaml (resolved via registry)"
            
            # Verify defaults were applied (not import mode)
            assert "parameters" in step_data, "Step should have parameters (defaults applied)"
            assert "CONTROL" in step_data.get("parameters", {}), "Step should have CONTROL section from defaults"
            
            # Step 7: Rename calculation
            # qms configure calculation --name "graph"
            result = runner.invoke(
                app,
                [
                    "configure",
                    "calculation",
                    "--name",
                    "graph",
                ],
            )
            assert result.exit_code == 0, f"Calculation rename failed: {result.stdout}"
            
            # Verify calculation name was updated in project config
            project_config = yaml.safe_load((project_dir / "project.qms.yml").read_text())
            calculations = project_config.get("calculations", [])
            calculation_entry = next((w for w in calculations if w.get("name") == "graph"), None)
            assert calculation_entry is not None, "Calculation should be renamed to 'graph' in project config"
            
            # Re-resolve calculation directory (it may have moved if slug changed)
            from qmatsuite.core.project_utils import calculation_directory
            new_calculation_dir = calculation_directory(project_dir, calculation_entry)
            assert new_calculation_dir.exists(), "Calculation directory should exist after rename"
            assert (new_calculation_dir / "calculation.yaml").exists(), "calculation.yaml should exist after rename"
            
            # Verify calculation.yaml meta was updated
            calculation_data = yaml.safe_load((new_calculation_dir / "calculation.yaml").read_text())
            assert "meta" in calculation_data, "calculation.yaml should have meta section"
            assert calculation_data["meta"]["name"] == "graph", "Calculation name in calculation.yaml should be 'graph'"
            
            # The slug may change if the name slugifies differently, or stay the same
            # Either way, it should match what's in the entry
            expected_slug = (calculation_entry.get("meta") or {}).get("slug") or calculation_entry.get("path", "").split("/")[-1]
            assert calculation_data["meta"]["slug"] == expected_slug, \
                f"Calculation slug should match entry. Got: {calculation_data['meta']['slug']}, Expected: {expected_slug}"
            
        finally:
            os.chdir(original_cwd)


def test_init_step_fails_at_project_root_without_calculation(ci_test_data_dir: Path, tmp_path: Path):
    """Test that qms init step scf fails with clear error when at project root without --calculation."""
    runner = CliRunner()
    
    with runner.isolated_filesystem() as fs:
        fs_path = Path(fs)
        
        # Create project
        result = runner.invoke(app, ["init", "project", "--name", "test_project"])
        assert result.exit_code == 0
        
        # Find the actual project directory (may be slugified)
        project_dirs = [d for d in fs_path.iterdir() if d.is_dir() and (d / "project.qms.yml").exists()]
        assert len(project_dirs) > 0, f"No project directory found. Created dirs: {list(fs_path.iterdir())}"
        project_dir = project_dirs[0]
        
        # Change to project directory to simulate being at project root
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            
            # Try to create step without --calculation (should fail)
            result = runner.invoke(app, ["init", "step", "scf"])
            assert result.exit_code != 0, f"Should fail when at project root without --calculation. stdout: {result.stdout}"
            # Check stdout for the error message (typer errors go to stdout via CliRunner)
            error_output = result.stdout.lower()
            assert "project root" in error_output or "specify --calculation" in error_output or "--calculation" in error_output, \
                f"Error message should mention project root or --calculation. Got stdout: {result.stdout}"
                
        finally:
            os.chdir(original_cwd)

