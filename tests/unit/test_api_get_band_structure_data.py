"""
Unit tests for QVService.get_band_structure_data RPC.

Tests the complete pipeline from GUI request to parsed band structure data,
including high-symmetry point parsing from bands.out.
"""

import pytest
import yaml
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from quantumvitas.api import QVService
from quantumvitas.analysis.artifacts import AnalysisType


def create_minimal_bands_gnu(path: Path, n_bands: int = 4, n_kpoints: int = 100) -> None:
    """
    Create a minimal synthetic bands.dat.gnu file for testing.
    
    Format: k_distance energy (blank line between bands)
    """
    lines = []
    for band_idx in range(n_bands):
        for k_idx in range(n_kpoints):
            k_dist = k_idx * 0.01  # Simple linear k-path
            energy = -2.0 + band_idx * 2.0 + k_dist * 0.1  # Bands separated by 2 eV
            lines.append(f"{k_dist:.6f}  {energy:.6f}")
        if band_idx < n_bands - 1:
            lines.append("")  # Blank line between bands
    
    path.write_text("\n".join(lines))


def create_bands_stdout(path: Path) -> None:
    """
    Create a bands.out file with high-symmetry point markers.
    
    Uses the exact format from QE bands.x output.
    """
    content = """high-symmetry point:  0.3536 0.3536 0.3536   x coordinate   0.0000
high-symmetry point:  0.0000 0.0000 0.0000   x coordinate   0.6124
high-symmetry point:  0.7071 0.0000 0.0000   x coordinate   1.3195
high-symmetry point:  0.7071 0.1768 0.1768   x coordinate   1.5695
high-symmetry point:  0.0000 0.0000 0.0000   x coordinate   2.3195

Plottable bands (eV) written to file si.bands.dat.gnu
Bands written to file si.bands.dat
"""
    path.write_text(content)


@pytest.fixture
def tmp_project_with_bands(tmp_path: Path):
    """
    Create a minimal project structure with bands calculation and step.
    
    Structure:
    <tmp_path>/
      calculations/
        si-bands/
          calculation.yaml
          steps/
            <step_ulid>.step.yaml
          raw/
            si.bands.dat.gnu
            bands.out
          analysis/  (created by parser)
    """
    from quantumvitas.core.resources import generate_resource_id
    
    # Create project using QVService
    project_root = tmp_path / "test_project"
    QVService.init_project(project_root)
    
    # Import a minimal structure (required for calculation)
    struct_file = tmp_path / "si.json"
    struct_file.write_text("""{
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
        "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
    }""")
    QVService.import_structure(project_root, struct_file, name="Silicon")
    
    # Create calculation
    calc_slug = "si-bands"
    QVService.init_calculation(project_root, calc_slug, structure_selector="silicon")
    
    calc_dir = project_root / "calculations" / calc_slug
    steps_dir = calc_dir / "steps"
    raw_dir = calc_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    
    # Get calculation ID and create step
    from quantumvitas.core.models import load_calculation
    from quantumvitas.core.project_utils import load_project_config
    from quantumvitas.core.resolution import make_structure_selector_resolver
    
    config = load_project_config(project_root)
    resolver = make_structure_selector_resolver(project_root, config=config)
    calc_yaml = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_yaml, project_root=project_root, resolve_structure_selector=resolver)
    
    # Generate step ULID
    step_ulid = generate_resource_id()
    
    # Use domain accessor API for step creation
    svc = QVService(project_root)
    svc.calculation.add_step(
        calc_selector=calc_slug,
        step_type_gen="bands",
        name="bands",
    )
    
    # Get the actual step ID that was created
    calc_model = load_calculation(calc_yaml, project_root=project_root, resolve_structure_selector=resolver)
    if calc_model.steps:
        step_ulid = calc_model.steps[0].step_ulid
    
    # Update step YAML with filband parameter
    step_yaml = steps_dir / f"{step_ulid}.step.yaml"
    if step_yaml.exists():
        step_data = yaml.safe_load(step_yaml.read_text()) or {}
        if "parameters" not in step_data:
            step_data["parameters"] = {}
        step_data["parameters"]["filband"] = "si.bands.dat"
        step_yaml.write_text(yaml.dump(step_data))
    
    # Create band data files
    bands_gnu = raw_dir / "si.bands.dat.gnu"
    create_minimal_bands_gnu(bands_gnu, n_bands=4, n_kpoints=100)
    
    bands_out = raw_dir / "bands.out"
    create_bands_stdout(bands_out)
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
        "raw_dir": raw_dir,
        "step_ulid": step_ulid,
        "calc_slug": calc_slug,
    }


def test_get_band_structure_data_success(tmp_project_with_bands):
    """Test successful parsing of band structure with high-symmetry points."""
    fixture = tmp_project_with_bands
    project_root = fixture["project_root"]
    calc_slug = fixture["calc_slug"]
    step_ulid = fixture["step_ulid"]
    
    # Call the service method
    svc = QVService(project_root)
    result = svc.analysis.get_band_structure_data(
        calculation_selector=calc_slug,
        step_selector=step_ulid,
    )
    
    # Verify structure
    assert "calculation" in result
    assert "step" in result
    assert "n_bands" in result
    assert "n_kpoints" in result
    assert "k_distances" in result
    assert "energies_ev" in result
    assert "high_symmetry_points" in result
    assert "units" in result
    
    # Verify data values
    assert result["calculation"] == calc_slug
    assert result["step"] == step_ulid
    assert result["n_bands"] == 4
    assert result["n_kpoints"] == 100
    assert len(result["k_distances"]) == 100
    assert len(result["energies_ev"]) == 4
    assert all(len(band) == 100 for band in result["energies_ev"])
    
    # Verify high-symmetry points were parsed
    high_sym_points = result["high_symmetry_points"]
    assert len(high_sym_points) > 0, "Should have parsed at least one high-symmetry point"
    
    # Verify point structure
    for pt in high_sym_points:
        assert "label" in pt
        assert "k_distance" in pt
        assert "k_coords" in pt
        assert isinstance(pt["k_distance"], (int, float))
        assert isinstance(pt["k_coords"], (list, tuple))
        assert len(pt["k_coords"]) == 3
    
    # Verify labels or coordinates exist (pymatgen best-effort or fallback)
    labels_found = any(pt["label"] for pt in high_sym_points)
    coords_found = any(pt["k_coords"] for pt in high_sym_points)
    assert labels_found or coords_found, "Should have either labels or coordinates for ticks"
    
    # Verify specific x coordinates from bands.out are present
    x_coords = [pt["k_distance"] for pt in high_sym_points]
    expected_x = [0.0000, 0.6124, 1.3195, 1.5695, 2.3195]
    for expected in expected_x:
        assert any(abs(x - expected) < 1e-6 for x in x_coords), f"Expected x coordinate {expected} not found"


def test_get_band_structure_data_graceful_missing_stdout(tmp_project_with_bands):
    """Test graceful handling when bands.out is missing."""
    fixture = tmp_project_with_bands
    project_root = fixture["project_root"]
    calc_slug = fixture["calc_slug"]
    step_ulid = fixture["step_ulid"]
    raw_dir = fixture["raw_dir"]
    
    # Remove bands.out
    bands_out = raw_dir / "bands.out"
    if bands_out.exists():
        bands_out.unlink()
    
    # Call the service method
    svc = QVService(project_root)
    result = svc.analysis.get_band_structure_data(
        calculation_selector=calc_slug,
        step_selector=step_ulid,
    )
    
    # Should still succeed with band data
    assert result["n_bands"] > 0
    assert result["n_kpoints"] > 0
    assert len(result["energies_ev"]) > 0
    
    # High-symmetry points should be empty or minimal
    high_sym_points = result.get("high_symmetry_points", [])
    # This is acceptable - plot should still render


def test_get_band_structure_data_missing_gnu(tmp_project_with_bands):
    """Test failure when .gnu file is missing (required file)."""
    fixture = tmp_project_with_bands
    project_root = fixture["project_root"]
    calc_slug = fixture["calc_slug"]
    step_ulid = fixture["step_ulid"]
    raw_dir = fixture["raw_dir"]
    
    # Remove .gnu file
    bands_gnu = raw_dir / "si.bands.dat.gnu"
    if bands_gnu.exists():
        bands_gnu.unlink()
    
    # Should raise APIError
    from quantumvitas.api import APIError
    
    svc = QVService(project_root)
    with pytest.raises(APIError) as exc_info:
        svc.analysis.get_band_structure_data(
            calculation_selector=calc_slug,
            step_selector=step_ulid,
        )
    
    error_msg = str(exc_info.value).lower()
    assert "missing" in error_msg or "not found" in error_msg


def test_get_band_structure_data_without_step_selector(tmp_project_with_bands):
    """Test that bands data can be loaded without step_selector (uses default selection)."""
    fixture = tmp_project_with_bands
    project_root = fixture["project_root"]
    calc_slug = fixture["calc_slug"]
    
    # Call without step_selector
    svc = QVService(project_root)
    result = svc.analysis.get_band_structure_data(
        calculation_selector=calc_slug,
        step_selector=None,
    )
    
    # Should still succeed
    assert result["n_bands"] > 0
    assert result["n_kpoints"] > 0
    
    # May or may not have high-symmetry points (depends on bands.out location)
    # But should not crash

