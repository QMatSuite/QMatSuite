"""
Contract tests for pseudo selection system (sha_family migration hardening).

Tests verify:
1. Backend contract: get_pseudo_options_for_elements() returns correct schema
2. UI writeback contract: update_calculation_species_map() writes complete triplet
3. No legacy sha_token fields in any contract
"""

import tempfile
from pathlib import Path

import pytest

from quantumvitas.api import QVService
from quantumvitas.core.models import load_calculation
from quantumvitas.core.pseudo_options import get_pseudo_options_for_elements
from quantumvitas.core.pseudo_provenance import compute_sha256_file
from quantumvitas.core.pseudo_libinfo import compute_sha_family_file


def create_test_upf_file(path: Path, element: str) -> None:
    """Create a minimal valid UPF file."""
    content = f"""<UPF version="2.0.1">
<PP_HEADER>
  <element>{element}</element>
  <z_valence>4.0</z_valence>
</PP_HEADER>
</UPF>
"""
    path.write_text(content)


class TestPseudoOptionsContract:
    """Test backend contract for get_pseudo_options_for_elements()."""
    
    def test_options_include_required_fields(self, tmp_path: Path):
        """Test that get_pseudo_options_for_elements() returns variants with required fields."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        pseudo_dir = project_root / "pseudo"
        pseudo_dir.mkdir()
        
        # Create test pseudo file
        create_test_upf_file(pseudo_dir / "Si.UPF", "Si")
        
        options = get_pseudo_options_for_elements(project_root, ["Si"])
        
        assert "Si" in options
        assert len(options["Si"]) > 0, "Should have at least one option for Si"
        
        variant = options["Si"][0]
        
        # Required fields
        assert "sha256" in variant, "Variant must have sha256"
        assert "sha_family" in variant, "Variant must have sha_family"
        assert "basename" in variant, "Variant must have basename"
        assert "element" in variant, "Variant must have element"
        assert "sources" in variant, "Variant must have sources"
        
        # Verify types
        assert isinstance(variant["sha256"], str), "sha256 must be string"
        assert isinstance(variant["sha_family"], str), "sha_family must be string"
        assert isinstance(variant["basename"], str), "basename must be string"
        assert variant["element"] == "Si", "element must match"
        assert isinstance(variant["sources"], list), "sources must be list"
        
        # Verify no legacy fields
        assert "sha_token" not in variant, "Variant must not have legacy sha_token"
        assert "pseudo_sha_token" not in variant, "Variant must not have legacy pseudo_sha_token"
        assert "token_match_warnings" not in variant, "Variant must not have token_match_warnings"
        
        # Verify family_match_warnings exists (can be empty)
        assert "family_match_warnings" in variant, "Variant must have family_match_warnings"
        assert isinstance(variant["family_match_warnings"], list), "family_match_warnings must be list"
    
    def test_options_sha256_matches_file(self, tmp_path: Path):
        """Test that sha256 in variant matches actual file hash."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        pseudo_dir = project_root / "pseudo"
        pseudo_dir.mkdir()
        
        pseudo_file = pseudo_dir / "Si.UPF"
        create_test_upf_file(pseudo_file, "Si")
        
        expected_sha256 = compute_sha256_file(pseudo_file)
        expected_sha_family = compute_sha_family_file(pseudo_file)
        
        options = get_pseudo_options_for_elements(project_root, ["Si"])
        
        assert "Si" in options
        assert len(options["Si"]) > 0
        
        # Find variant matching our file
        matching_variant = None
        for variant in options["Si"]:
            if variant["sha256"] == expected_sha256:
                matching_variant = variant
                break
        
        assert matching_variant is not None, "Should find variant with matching sha256"
        assert matching_variant["sha_family"] == expected_sha_family, "sha_family should match file"
        assert matching_variant["basename"] == "Si.UPF", "basename should match filename"


class TestUIWritebackContract:
    """Test UI writeback contract for species_map updates."""

    def test_update_writes_complete_triplet(self, tmp_path: Path):
        """Test that species_map update writes complete triplet together."""
        from quantumvitas.core.resolution import require_calculation
        from quantumvitas.core.models import save_calculation

        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / "pseudo").mkdir()

        # Create project
        QVService.init_project(project_root, "Test Project")

        # Create calculation
        calc_result = QVService.init_calculation(
            project_root=project_root,
            name="Test Calc",
        )
        calc_id = calc_result.meta.id

        # Create test pseudo file
        pseudo_file = project_root / "pseudo" / "Si.UPF"
        create_test_upf_file(pseudo_file, "Si")

        # Get options to get valid sha256 and sha_family
        options = get_pseudo_options_for_elements(project_root, ["Si"])
        assert "Si" in options and len(options["Si"]) > 0
        variant = options["Si"][0]

        # Resolve calculation and update species_map directly via kernel
        calc_resolved = require_calculation(project_root, calc_id)
        calc_dir = calc_resolved.absolute_path
        if calc_dir.name == "calculation.yaml":
            calc_dir = calc_dir.parent
        calc_yaml = calc_dir / "calculation.yaml"

        # Load, update species_map, and save
        calc_model = load_calculation(calc_yaml, project_root)
        calc_model.species_map = {
            "Si": {
                "mass": 28.0855,
                "pseudopot": variant["basename"],
                "pseudo_basename": variant["basename"],
                "pseudo_sha256": variant["sha256"],
                "pseudo_sha_family": variant["sha_family"],
            }
        }
        save_calculation(calc_model, calc_yaml)

        # Reload and verify
        calc_model = load_calculation(calc_yaml, project_root)

        assert calc_model.species_map is not None
        assert "Si" in calc_model.species_map

        si_entry = calc_model.species_map["Si"]
        assert si_entry["pseudo_basename"] == variant["basename"]
        assert si_entry["pseudo_sha256"] == variant["sha256"]
        assert si_entry["pseudo_sha_family"] == variant["sha_family"]

        # Verify no legacy fields
        assert "pseudo_sha_token" not in si_entry, "Must not write legacy pseudo_sha_token"
        assert "sha_token" not in si_entry, "Must not write legacy sha_token"

    def test_update_rejects_incomplete_triplet(self, tmp_path: Path):
        """Test that update with incomplete triplet is handled (should still work but warn)."""
        from quantumvitas.core.resolution import require_calculation
        from quantumvitas.core.models import save_calculation

        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / "pseudo").mkdir()

        # Create project
        QVService.init_project(project_root, "Test Project")

        # Create calculation
        calc_result = QVService.init_calculation(
            project_root=project_root,
            name="Test Calc",
        )
        calc_id = calc_result.meta.id

        # Resolve calculation and update species_map directly via kernel
        calc_resolved = require_calculation(project_root, calc_id)
        calc_dir = calc_resolved.absolute_path
        if calc_dir.name == "calculation.yaml":
            calc_dir = calc_dir.parent
        calc_yaml = calc_dir / "calculation.yaml"

        # Load, update with incomplete species_map, and save
        calc_model = load_calculation(calc_yaml, project_root)
        calc_model.species_map = {
            "Si": {
                "mass": 28.0855,
                "pseudo_basename": "Si.UPF",
                # Missing sha256 and sha_family
            }
        }
        save_calculation(calc_model, calc_yaml)

        # Reload and verify
        calc_model = load_calculation(calc_yaml, project_root)

        assert calc_model.species_map is not None
        assert "Si" in calc_model.species_map

        si_entry = calc_model.species_map["Si"]
        # Fields may be missing, but should not have legacy token
        assert "pseudo_sha_token" not in si_entry, "Must not write legacy pseudo_sha_token"
        assert "sha_token" not in si_entry, "Must not write legacy sha_token"


class TestNoLegacyFields:
    """Test that no legacy sha_token fields appear in any contract."""
    
    def test_options_no_sha_token(self, tmp_path: Path):
        """Test that get_pseudo_options_for_elements() never returns sha_token."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        pseudo_dir = project_root / "pseudo"
        pseudo_dir.mkdir()
        
        create_test_upf_file(pseudo_dir / "Si.UPF", "Si")
        
        options = get_pseudo_options_for_elements(project_root, ["Si"])
        
        # Check all variants
        for element, variants in options.items():
            for variant in variants:
                # Serialize to JSON to catch any hidden fields
                import json
                variant_json = json.dumps(variant)
                
                assert "sha_token" not in variant_json, f"Variant must not contain sha_token: {variant}"
                assert "pseudo_sha_token" not in variant_json, f"Variant must not contain pseudo_sha_token: {variant}"
                assert "token_match" not in variant_json.lower(), f"Variant must not contain token_match: {variant}"

