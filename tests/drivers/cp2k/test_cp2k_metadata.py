"""Tests for CP2K input keyword metadata catalog and access layer.

Validates the JSON catalog structure and the cp2k_metadata.py access API.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────────
# JSON catalog validation
# ──────────────────────────────────────────────────────────────────────────

VALID_TYPES = {
    "int", "float", "bool", "str", "enum", "array",
}

VALID_CATEGORIES = {
    "global", "method", "basis", "electronic", "spin", "grid", "qs",
    "scf", "xc", "kpoints", "print", "poisson", "tddft", "dftu",
    "structure", "geometry", "md", "band", "ls_scf", "admm",
    "rtp", "mm", "qmmm", "response", "constraint", "metadyn",
    "vibrational", "restart",
}

REQUIRED_FIELDS = {"name", "type", "category", "description"}


@pytest.fixture(scope="module")
def raw_catalog() -> dict:
    """Load the raw JSON catalog."""
    data_path = resources.files("quantumvitas.drivers.cp2k.data").joinpath(
        "cp2k_tags.json"
    )
    with resources.as_file(data_path) as path:
        return json.loads(Path(path).read_text(encoding="utf-8"))


class TestCP2KCatalogJSON:
    """Validate cp2k_tags.json structure."""

    def test_json_loads_valid(self, raw_catalog):
        """JSON parses without error and has expected top-level keys."""
        assert "schema_version" in raw_catalog
        assert "tags" in raw_catalog
        assert raw_catalog["engine"] == "cp2k"

    def test_schema_version(self, raw_catalog):
        """Schema version is 1."""
        assert raw_catalog["schema_version"] == 1

    def test_tag_count_minimum(self, raw_catalog):
        """Catalog has 150+ tags (major DFT engine)."""
        assert len(raw_catalog["tags"]) >= 150

    def test_required_fields_present(self, raw_catalog):
        """Every tag has the required fields."""
        for tag_path, tag in raw_catalog["tags"].items():
            missing = REQUIRED_FIELDS - set(tag.keys())
            assert not missing, f"Tag {tag_path} missing fields: {missing}"

    def test_type_enum_valid(self, raw_catalog):
        """Every tag type is in the valid set."""
        for tag_path, tag in raw_catalog["tags"].items():
            assert tag["type"] in VALID_TYPES, (
                f"Tag {tag_path} has invalid type: {tag['type']}"
            )

    def test_category_valid(self, raw_catalog):
        """Every tag category is in the valid set."""
        for tag_path, tag in raw_catalog["tags"].items():
            assert tag["category"] in VALID_CATEGORIES, (
                f"Tag {tag_path} has invalid category: {tag['category']}"
            )

    def test_section_path_format(self, raw_catalog):
        """Tag paths use / separator and are UPPERCASE."""
        for tag_path in raw_catalog["tags"]:
            assert tag_path == tag_path.upper(), (
                f"Tag path {tag_path} is not uppercase"
            )

    def test_core_tags_present(self, raw_catalog):
        """Essential CP2K keywords exist in catalog."""
        core_paths = [
            "GLOBAL/PROJECT",
            "GLOBAL/RUN_TYPE",
            "FORCE_EVAL/METHOD",
            "FORCE_EVAL/DFT/SCF/MAX_SCF",
            "FORCE_EVAL/DFT/SCF/EPS_SCF",
            "FORCE_EVAL/DFT/XC/XC_FUNCTIONAL",
            "FORCE_EVAL/DFT/MGRID/CUTOFF",
            "FORCE_EVAL/SUBSYS/CELL/A",
            "FORCE_EVAL/SUBSYS/KIND/BASIS_SET",
            "FORCE_EVAL/SUBSYS/KIND/POTENTIAL",
            "MOTION/GEO_OPT/OPTIMIZER",
            "MOTION/MD/ENSEMBLE",
            "MOTION/MD/STEPS",
        ]
        tags = raw_catalog["tags"]
        for path in core_paths:
            assert path in tags, f"Core tag {path} missing from catalog"

    def test_section_field_present(self, raw_catalog):
        """Every tag has a section field matching its path prefix."""
        for tag_path, tag in raw_catalog["tags"].items():
            assert "section" in tag, f"Tag {tag_path} missing section field"
            # Section should be the path prefix (path minus the last component)
            parts = tag_path.rsplit("/", 1)
            if len(parts) == 2:
                expected_section = parts[0]
                assert tag["section"] == expected_section, (
                    f"Tag {tag_path}: section={tag['section']} != {expected_section}"
                )


# ──────────────────────────────────────────────────────────────────────────
# Metadata access layer
# ──────────────────────────────────────────────────────────────────────────


class TestMetadataAccessLayer:
    """Test cp2k_metadata.py API."""

    def test_safe_load_metadata(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import safe_load_metadata
        data = safe_load_metadata()
        assert "tags" in data
        assert len(data["tags"]) >= 150

    def test_get_tag_info_by_path(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import get_tag_info
        info = get_tag_info("FORCE_EVAL/DFT/SCF/MAX_SCF")
        assert info is not None
        assert info["type"] == "int"

    def test_get_tag_info_case_insensitive(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import get_tag_info
        info = get_tag_info("global/run_type")
        assert info is not None
        assert info["name"] == "RUN_TYPE"

    def test_get_tag_info_missing(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import get_tag_info
        info = get_tag_info("NONEXISTENT/TAG/PATH")
        assert info is None

    def test_list_tags_all(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import list_tags
        tags = list_tags()
        assert len(tags) >= 150
        assert "GLOBAL/PROJECT" in tags

    def test_list_tags_by_category(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import list_tags
        scf_tags = list_tags(category="scf")
        assert len(scf_tags) >= 5
        assert any("SCF" in t for t in scf_tags)

    def test_list_categories(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import list_categories
        cats = list_categories()
        assert len(cats) >= 15
        assert "scf" in cats
        assert "structure" in cats
        assert "md" in cats
        assert "xc" in cats

    def test_validate_params_all_valid(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import validate_params
        unknowns = validate_params({
            "FORCE_EVAL/DFT/SCF/MAX_SCF": 100,
            "GLOBAL/PROJECT": "test",
        })
        assert unknowns == []

    def test_validate_params_bare_keyword_valid(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import validate_params
        # Bare keyword names should also be recognized
        unknowns = validate_params({"MAX_SCF": 100, "PROJECT": "test"})
        assert unknowns == []

    def test_validate_params_unknown_flagged(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import validate_params
        unknowns = validate_params({"GLOBAL/PROJECT": "x", "FAKE_PARAM": 42})
        assert "FAKE_PARAM" in unknowns
        assert "GLOBAL/PROJECT" not in unknowns

    def test_reload_metadata(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import (
            reload_metadata, safe_load_metadata,
        )
        reload_metadata()
        data = safe_load_metadata()
        assert len(data["tags"]) >= 150

    def test_metadata_debug_info(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import get_metadata_file_info
        info = get_metadata_file_info()
        assert "metadata_path_abs" in info
        assert "schema_version" in info

    def test_get_tag_type(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import get_tag_type
        assert get_tag_type("FORCE_EVAL/DFT/SCF/MAX_SCF") == "int"
        assert get_tag_type("FORCE_EVAL/DFT/SCF/EPS_SCF") == "float"
        assert get_tag_type("GLOBAL/RUN_TYPE") == "enum"
        assert get_tag_type("NONEXISTENT") is None

    def test_get_tag_default(self):
        from quantumvitas.drivers.cp2k.data.cp2k_metadata import get_tag_default
        assert get_tag_default("FORCE_EVAL/DFT/SCF/MAX_SCF") == "50"
        assert get_tag_default("NONEXISTENT") is None
