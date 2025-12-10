"""
Unit test for graphene workflow setup via CLI.

This test verifies the exact CLI command sequence from manual_tests/instructions:
- qv init project --name graphene_project
- cd graphene_project
- qv import-structure tests/data/13_graphene/graphene.2_scf.in
- qv init workflow "graphene bands" --structure C
- cd workflows/graphene-bands
- qv init step scf                 # Should auto-detect parent workflow + structure
- qv configure workflow --name "graph"

This is a unit test (no QE execution required).
"""

import yaml
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quantumvitas.cli.main import app

pytestmark = pytest.mark.unit


def test_graphene_workflow_setup(ci_test_data_dir: Path, tmp_path: Path):
    """Test the complete graphene workflow setup sequence from instructions."""
    runner = CliRunner()
    
    # Get the graphene input file
    graphene_input = ci_test_data_dir / "13_graphene" / "graphene.2_scf.in"
    if not graphene_input.exists():
        pytest.skip(f"Graphene test data not found: {graphene_input}")
    
    # Use isolated filesystem to simulate cd commands
    with runner.isolated_filesystem() as fs:
        fs_path = Path(fs)
        
        # Step 1: Create project
        # qv init project --name graphene_project
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
        assert (project_dir / "project.qv.yml").exists(), f"project.qv.yml not found in {project_dir}"
        assert (project_dir / "project.qv.yml").exists()
        
        # Verify project name
        project_config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
        assert project_config["project"]["name"] == "graphene_project"
        
        # Step 2: cd graphene_project (simulated by changing working directory)
        # In isolated_filesystem, we need to work from project_dir
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            
            # Step 3: Import structure
            # qv import-structure $PYTHONSRC/tests/data/13_graphene/graphene.2_scf.in
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
            # ID-only model: project.qv.yml only has structure_id, not name
            # Resolve structure from registry to get its name
            project_config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
            structures = project_config.get("structures", [])
            assert len(structures) > 0, "Structure should be registered"
            # In ID-only model, entries have structure_id (ULID), not name
            # Resolve the structure to get its meta.name
            from quantumvitas.core.resolution import build_resource_index, require_structure
            index = build_resource_index(project_dir)
            structure_id = structures[0].get("structure_id")
            assert structure_id is not None, "Structure entry should have structure_id"
            resolved = require_structure(project_dir, structure_id, index=index)
            assert resolved.meta.name == "C", f"Structure name should be 'C'. Found: {resolved.meta.name}"
            
            # Step 4: Create workflow
            # qv init workflow "graphene bands" --structure C
            result = runner.invoke(
                app,
                [
                    "init",
                    "workflow",
                    "graphene bands",
                    "--structure",
                    "C",
                ],
            )
            assert result.exit_code == 0, f"Workflow init failed: {result.stdout}"
            
            # Verify workflow directory and files
            workflow_dir = project_dir / "workflows" / "graphene-bands"
            assert workflow_dir.exists()
            assert (workflow_dir / "workflow.yaml").exists()
            
            # Verify workflow.yaml content
            workflow_data = yaml.safe_load((workflow_dir / "workflow.yaml").read_text())
            # Structure reference uses ID (structure_id is canonical)
            # Note: structure_id may be set even if structure selector is also present (backwards compat)
            assert "structure_id" in workflow_data or "structure" in workflow_data, \
                "Workflow should have structure_id or structure (for backwards compat)"
            if "structure_id" not in workflow_data:
                # If only structure selector is present, it should be resolved to structure_id on next load
                # For now, just verify structure is present
                assert workflow_data.get("structure") == "C"
            assert workflow_data["steps"] == []
            
            # Verify workflow is registered in project config
            # ID-only model: project.qv.yml only has workflow_id, not name
            # Resolve workflow from registry to get its name
            project_config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
            workflows = project_config.get("workflows", [])
            assert len(workflows) > 0, "Workflow should be registered"
            from quantumvitas.core.resolution import build_resource_index, require_workflow
            index = build_resource_index(project_dir)
            workflow_id = workflows[0].get("id") or workflows[0].get("workflow_id")
            assert workflow_id is not None, "Workflow entry should have id"
            resolved = require_workflow(project_dir, workflow_id, index=index)
            assert resolved.meta.name == "graphene bands", f"Workflow name should be 'graphene bands'. Found: {resolved.meta.name}"
            
            # Step 5: cd workflows/graphene-bands
            os.chdir(workflow_dir)
            
            # Step 6: Create SCF step (should auto-detect workflow and structure)
            # qv init step scf
            result = runner.invoke(
                app,
                ["init", "step", "scf"],
            )
            assert result.exit_code == 0, f"Step init failed: {result.stdout}"
            
            # Verify step was created
            steps_dir = workflow_dir / "steps"
            assert steps_dir.exists()
            scf_step_file = steps_dir / "scf.step.yaml"
            assert scf_step_file.exists()
            
            # Verify step content
            step_data = yaml.safe_load(scf_step_file.read_text())
            assert step_data["step_type"] == "scf"
            # DAG model: Step YAML should NOT contain structure_id or parent_workflow_id
            # Structure is resolved via workflow.structure_id at runtime
            assert "structure_id" not in step_data, "Step YAML should not contain structure_id (DAG model)"
            assert "parent_workflow_id" not in step_data, "Step YAML should not contain parent_workflow_id (DAG model)"
            # Verify workflow has structure_id set
            workflow_data = yaml.safe_load((workflow_dir / "workflow.yaml").read_text())
            assert workflow_data.get("structure_id") is not None, "Workflow should have structure_id set"
            
            # Verify step is in workflow.yaml
            workflow_data = yaml.safe_load((workflow_dir / "workflow.yaml").read_text())
            # Steps now use step_id (ULID) instead of id (slug)
            step_ids = [s.get("step_id") or s.get("id") for s in workflow_data.get("steps", [])]
            assert len(step_ids) > 0, "SCF step should be in workflow"
            # Verify step entry has step_id (ULID) - step_file is NOT stored (resolved via registry)
            step_entry = workflow_data.get("steps", [])[0]
            assert step_entry.get("step_id") is not None, "Step entry should have step_id (ULID)"
            # step_file is NOT stored in workflow.yaml - step location resolved via registry using step_id
            assert "step_file" not in step_entry or step_entry.get("step_file") is None, \
                "step_file should not be stored in workflow.yaml (resolved via registry)"
            
            # Verify defaults were applied (not import mode)
            assert "parameters" in step_data, "Step should have parameters (defaults applied)"
            assert "CONTROL" in step_data.get("parameters", {}), "Step should have CONTROL section from defaults"
            
            # Step 7: Rename workflow
            # qv configure workflow --name "graph"
            result = runner.invoke(
                app,
                [
                    "configure",
                    "workflow",
                    "--name",
                    "graph",
                ],
            )
            assert result.exit_code == 0, f"Workflow rename failed: {result.stdout}"
            
            # Verify workflow name was updated in project config
            project_config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
            workflows = project_config.get("workflows", [])
            workflow_entry = next((w for w in workflows if w.get("name") == "graph"), None)
            assert workflow_entry is not None, "Workflow should be renamed to 'graph' in project config"
            
            # Re-resolve workflow directory (it may have moved if slug changed)
            from quantumvitas.core.project_utils import workflow_directory
            new_workflow_dir = workflow_directory(project_dir, workflow_entry)
            assert new_workflow_dir.exists(), "Workflow directory should exist after rename"
            assert (new_workflow_dir / "workflow.yaml").exists(), "workflow.yaml should exist after rename"
            
            # Verify workflow.yaml meta was updated
            workflow_data = yaml.safe_load((new_workflow_dir / "workflow.yaml").read_text())
            assert "meta" in workflow_data, "workflow.yaml should have meta section"
            assert workflow_data["meta"]["name"] == "graph", "Workflow name in workflow.yaml should be 'graph'"
            
            # The slug may change if the name slugifies differently, or stay the same
            # Either way, it should match what's in the entry
            expected_slug = (workflow_entry.get("meta") or {}).get("slug") or workflow_entry.get("path", "").split("/")[-1]
            assert workflow_data["meta"]["slug"] == expected_slug, \
                f"Workflow slug should match entry. Got: {workflow_data['meta']['slug']}, Expected: {expected_slug}"
            
        finally:
            os.chdir(original_cwd)


def test_init_step_fails_at_project_root_without_workflow(ci_test_data_dir: Path, tmp_path: Path):
    """Test that qv init step scf fails with clear error when at project root without --workflow."""
    runner = CliRunner()
    
    with runner.isolated_filesystem() as fs:
        fs_path = Path(fs)
        
        # Create project
        result = runner.invoke(app, ["init", "project", "--name", "test_project"])
        assert result.exit_code == 0
        
        # Find the actual project directory (may be slugified)
        project_dirs = [d for d in fs_path.iterdir() if d.is_dir() and (d / "project.qv.yml").exists()]
        assert len(project_dirs) > 0, f"No project directory found. Created dirs: {list(fs_path.iterdir())}"
        project_dir = project_dirs[0]
        
        # Change to project root
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            
            # Try to create step without --workflow (should fail)
            result = runner.invoke(app, ["init", "step", "scf"])
            assert result.exit_code != 0, "Should fail when at project root without --workflow"
            assert "project root" in result.stdout.lower() or "specify --workflow" in result.stdout.lower(), \
                f"Error message should mention project root or --workflow. Got: {result.stdout}"
                
        finally:
            os.chdir(original_cwd)

