"""
Tests for CLI structure_kind and engine_family options in calculation creation.
"""

import pytest
import yaml
from pathlib import Path
from typer.testing import CliRunner

from quantumvitas.cli.main import app as cli_app


@pytest.fixture
def test_project(tmp_path: Path):
    """Create a minimal test project with a structure."""
    project_root = tmp_path / "test_project"
    
    # Create project using QVService API (more reliable than CLI)
    from quantumvitas.api import QVService
    project_root = QVService.init_project(target_dir=project_root, name="TestProject")
    
    # Create a structure using QVService API
    from pymatgen.core import Structure, Lattice
    import tempfile
    
    lattice = Lattice.cubic(2.0)
    structure = Structure(lattice, ["Si"], [[0, 0, 0]])
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
        cif_path = Path(f.name)
    
    try:
        structure.to(filename=str(cif_path), fmt="cif")
        
        QVService(project_root).structure.import_file(
            source=cif_path,
            name="test_structure",
        )
    finally:
        if cif_path.exists():
            cif_path.unlink()
    
    return project_root


def test_calculation_defaults_to_periodic_qe(test_project: Path):
    """Test that calculation defaults to periodic/qe when not specified."""
    runner = CliRunner()
    
    result = runner.invoke(
        cli_app,
        [
            "init", "calculation", "test_calc",
            "--structure", "test_structure",
            "--project", str(test_project),
        ],
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    
    # Find the actual calculation directory (slugified name)
    calc_dir = test_project / "calculations"
    calc_dirs = [d for d in calc_dir.iterdir() if d.is_dir() and d.name.startswith("test")]
    assert len(calc_dirs) == 1, f"Expected 1 calculation dir, found: {[d.name for d in calc_dirs]}"
    calc_yaml = calc_dirs[0] / "calculation.yaml"
    assert calc_yaml.exists(), f"calculation.yaml not found at {calc_yaml}"
    
    with open(calc_yaml) as f:
        calc_data = yaml.safe_load(f)
    
    assert calc_data["structure_kind"] == "periodic"
    assert calc_data["engine_family"] == "qe"


def test_calculation_with_molecule_structure_kind(test_project: Path):
    """Test that molecule structure_kind defaults to pyscf engine_family."""
    runner = CliRunner()
    
    result = runner.invoke(
        cli_app,
        [
            "init", "calculation", "test_calc_mol",
            "--structure", "test_structure",
            "--structure-kind", "molecule",
            "--project", str(test_project),
        ],
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    
    calc_dir = test_project / "calculations"
    calc_dirs = [d for d in calc_dir.iterdir() if d.is_dir() and "mol" in d.name]
    assert len(calc_dirs) == 1
    calc_yaml = calc_dirs[0] / "calculation.yaml"
    assert calc_yaml.exists()
    
    with open(calc_yaml) as f:
        calc_data = yaml.safe_load(f)
    
    assert calc_data["structure_kind"] == "molecule"
    assert calc_data["engine_family"] == "pyscf"


def test_calculation_with_explicit_engine_family(test_project: Path):
    """Test that explicit engine_family overrides default."""
    runner = CliRunner()
    
    result = runner.invoke(
        cli_app,
        [
            "init", "calculation", "test_calc_explicit",
            "--structure", "test_structure",
            "--structure-kind", "periodic",
            "--engine-family", "qe",
            "--project", str(test_project),
        ],
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    
    calc_dir = test_project / "calculations"
    calc_dirs = [d for d in calc_dir.iterdir() if d.is_dir() and "explicit" in d.name]
    assert len(calc_dirs) == 1
    calc_yaml = calc_dirs[0] / "calculation.yaml"
    assert calc_yaml.exists()
    
    with open(calc_yaml) as f:
        calc_data = yaml.safe_load(f)
    
    assert calc_data["structure_kind"] == "periodic"
    assert calc_data["engine_family"] == "qe"


def test_calculation_invalid_structure_kind(test_project: Path):
    """Test that invalid structure_kind raises an error."""
    runner = CliRunner()
    
    result = runner.invoke(
        cli_app,
        [
            "init", "calculation", "test_calc_invalid",
            "--structure", "test_structure",
            "--structure-kind", "invalid",
            "--project", str(test_project),
        ],
    )
    assert result.exit_code != 0
    assert "Invalid structure_kind" in result.output


def test_calculation_molecule_with_qe_engine_family(test_project: Path):
    """Test that molecule can explicitly use qe engine_family."""
    runner = CliRunner()
    
    result = runner.invoke(
        cli_app,
        [
            "init", "calculation", "test_calc_mol_qe",
            "--structure", "test_structure",
            "--structure-kind", "molecule",
            "--engine-family", "qe",
            "--project", str(test_project),
        ],
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    
    calc_dir = test_project / "calculations"
    calc_dirs = [d for d in calc_dir.iterdir() if d.is_dir() and "mol" in d.name and "qe" in d.name]
    assert len(calc_dirs) == 1
    calc_yaml = calc_dirs[0] / "calculation.yaml"
    assert calc_yaml.exists()
    
    with open(calc_yaml) as f:
        calc_data = yaml.safe_load(f)
    
    assert calc_data["structure_kind"] == "molecule"
    assert calc_data["engine_family"] == "qe"

