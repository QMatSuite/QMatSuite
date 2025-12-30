"""
Unit tests for demo snapshot pseudo field migration (sha_token → sha_family).

Verifies that demo generation scripts produce snapshots with:
- pseudo_sha_family (not pseudo_sha_token)
- Complete triplet: pseudo_basename + pseudo_sha256 + pseudo_sha_family (when pseudo is selected)
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from quantumvitas.project.snapshot import (
    export_project_to_snapshot,
    materialize_project_from_snapshot,
)


@pytest.fixture
def project2_bands_path() -> Path:
    """Path to project2_bands example (bands calculations)."""
    return Path(__file__).parent.parent / "data" / "project_examples" / "project2_bands"


@pytest.fixture
def project1_path() -> Path:
    """Path to project1 example (DOS calculation)."""
    return Path(__file__).parent.parent / "data" / "project_examples" / "project1"


def scan_calculations_for_pseudo_fields(snapshot_dict: dict) -> dict:
    """
    Scan all calculations in snapshot for pseudo fields.
    
    Returns:
        Dict mapping calculation_name -> {
            "has_species_map": bool,
            "elements_with_pseudo": List[str],
            "fields_by_element": Dict[str, Dict[str, bool]],  # element -> {has_sha256, has_sha_family, has_sha_token, has_basename}
        }
    """
    result = {}
    
    for calc_data in snapshot_dict.get("calculations", []):
        calc_name = calc_data.get("meta", {}).get("name", "unknown")
        species_map = calc_data.get("species_map")
        
        if not species_map:
            result[calc_name] = {
                "has_species_map": False,
                "elements_with_pseudo": [],
                "fields_by_element": {},
            }
            continue
        
        elements_with_pseudo = []
        fields_by_element = {}
        
        for element, entry in species_map.items():
            if not isinstance(entry, dict):
                continue
            
            # Check if this element has any pseudo-related fields
            has_pseudopot = "pseudopot" in entry and entry["pseudopot"]
            has_basename = "pseudo_basename" in entry and entry["pseudo_basename"]
            has_sha256 = "pseudo_sha256" in entry and entry["pseudo_sha256"]
            has_sha_family = "pseudo_sha_family" in entry and entry["pseudo_sha_family"]
            has_sha_token = "pseudo_sha_token" in entry  # Legacy field - should NOT exist
            
            if has_pseudopot or has_basename or has_sha256 or has_sha_family:
                elements_with_pseudo.append(element)
                fields_by_element[element] = {
                    "has_sha256": bool(has_sha256),
                    "has_sha_family": bool(has_sha_family),
                    "has_sha_token": bool(has_sha_token),
                    "has_basename": bool(has_basename),
                    "has_pseudopot": bool(has_pseudopot),
                }
        
        result[calc_name] = {
            "has_species_map": True,
            "elements_with_pseudo": elements_with_pseudo,
            "fields_by_element": fields_by_element,
        }
    
    return result


class TestDemoSnapshotPseudoFamily:
    """Test that demo snapshots use pseudo_sha_family (not pseudo_sha_token)."""
    
    def test_export_project2_bands_has_sha_family(self, project2_bands_path: Path):
        """Test that exporting project2_bands produces snapshot with pseudo_sha_family."""
        snapshot = export_project_to_snapshot(project2_bands_path)
        snapshot_dict = snapshot.to_dict()
        
        scan_result = scan_calculations_for_pseudo_fields(snapshot_dict)
        
        # Should have at least one calculation with species_map
        assert len(scan_result) > 0, "Snapshot should have at least one calculation"
        
        for calc_name, info in scan_result.items():
            if not info["has_species_map"]:
                continue  # Skip calculations without pseudo
            
            # If calculation has pseudo selections, verify fields
            if info["elements_with_pseudo"]:
                for element in info["elements_with_pseudo"]:
                    fields = info["fields_by_element"][element]
                    
                    # Must NOT have pseudo_sha_token (legacy field)
                    assert not fields["has_sha_token"], \
                        f"Calculation '{calc_name}' element '{element}' has legacy pseudo_sha_token field"
                    
                    # If has sha256 or basename, must also have sha_family
                    if fields["has_sha256"] or fields["has_basename"] or fields["has_pseudopot"]:
                        assert fields["has_sha_family"], \
                            f"Calculation '{calc_name}' element '{element}' has pseudo selection but missing pseudo_sha_family"
    
    def test_export_project1_has_sha_family(self, project1_path: Path):
        """Test that exporting project1 produces snapshot with pseudo_sha_family."""
        snapshot = export_project_to_snapshot(project1_path)
        snapshot_dict = snapshot.to_dict()
        
        scan_result = scan_calculations_for_pseudo_fields(snapshot_dict)
        
        # Should have at least one calculation
        assert len(scan_result) > 0, "Snapshot should have at least one calculation"
        
        for calc_name, info in scan_result.items():
            if not info["has_species_map"]:
                continue
            
            if info["elements_with_pseudo"]:
                for element in info["elements_with_pseudo"]:
                    fields = info["fields_by_element"][element]
                    
                    # Must NOT have pseudo_sha_token
                    assert not fields["has_sha_token"], \
                        f"Calculation '{calc_name}' element '{element}' has legacy pseudo_sha_token field"
                    
                    # If has pseudo selection, must have sha_family
                    if fields["has_sha256"] or fields["has_basename"] or fields["has_pseudopot"]:
                        assert fields["has_sha_family"], \
                            f"Calculation '{calc_name}' element '{element}' has pseudo selection but missing pseudo_sha_family"
    
    def test_materialize_removes_sha_token(self, project2_bands_path: Path, tmp_path: Path):
        """Test that materializing from snapshot removes pseudo_sha_token if present."""
        # Export snapshot
        snapshot = export_project_to_snapshot(project2_bands_path)
        snapshot_dict = snapshot.to_dict()
        
        # Manually inject legacy pseudo_sha_token field to test migration
        for calc_data in snapshot_dict["calculations"]:
            species_map = calc_data.get("species_map")
            if species_map:
                for element, entry in species_map.items():
                    if isinstance(entry, dict) and "pseudo_sha_family" in entry:
                        # Add legacy field
                        entry["pseudo_sha_token"] = entry["pseudo_sha_family"]  # Use same value for test
        
        # Create snapshot from modified dict
        modified_snapshot = snapshot.__class__.from_dict(snapshot_dict)
        
        # Materialize
        new_project_root = materialize_project_from_snapshot(
            snapshot=modified_snapshot,
            parent_dir=tmp_path,
            new_project_name="Migration Test",
        )
        
        # Load calculation YAML directly and verify pseudo_sha_token is removed
        import yaml
        
        calc_dirs = list((new_project_root / "calculations").iterdir())
        assert len(calc_dirs) > 0, "Materialized project should have calculations"
        
        for calc_dir in calc_dirs:
            calc_yaml = calc_dir / "calculation.yaml"
            if not calc_yaml.exists():
                continue
            
            # Read YAML directly to check for pseudo_sha_token
            calc_data = yaml.safe_load(calc_yaml.read_text())
            species_map = calc_data.get("species_map")
            if species_map:
                for element, entry in species_map.items():
                    if isinstance(entry, dict):
                        # Must NOT have pseudo_sha_token
                        assert "pseudo_sha_token" not in entry, \
                            f"Materialized calculation '{calc_dir.name}' element '{element}' still has pseudo_sha_token"
    
    def test_snapshot_yaml_no_sha_token(self, project2_bands_path: Path, tmp_path: Path):
        """Test that snapshot YAML file does not contain pseudo_sha_token."""
        snapshot = export_project_to_snapshot(project2_bands_path)
        snapshot_dict = snapshot.to_dict()
        
        # Write to YAML and read back
        snapshot_yaml = tmp_path / "test_snapshot.yml"
        import yaml
        snapshot_yaml.write_text(yaml.safe_dump(snapshot_dict, sort_keys=False))
        
        # Read YAML as text and search for pseudo_sha_token
        yaml_text = snapshot_yaml.read_text()
        
        # Count occurrences of pseudo_sha_token
        token_count = yaml_text.count("pseudo_sha_token")
        assert token_count == 0, \
            f"Snapshot YAML contains {token_count} occurrences of pseudo_sha_token (should be 0)"
        
        # Verify pseudo_sha_family exists if species_map has pseudo selections
        yaml_data = yaml.safe_load(yaml_text)
        scan_result = scan_calculations_for_pseudo_fields(yaml_data)
        
        for calc_name, info in scan_result.items():
            if info["elements_with_pseudo"]:
                for element in info["elements_with_pseudo"]:
                    fields = info["fields_by_element"][element]
                    if fields["has_sha256"] or fields["has_basename"] or fields["has_pseudopot"]:
                        assert fields["has_sha_family"], \
                            f"Calculation '{calc_name}' element '{element}' missing pseudo_sha_family in YAML"

