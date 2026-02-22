"""Tests for VASP INCAR metadata catalog and access layer.

Validates the JSON catalog structure and the vasp_metadata.py access API.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────────
# JSON catalog validation (Step 1)
# ──────────────────────────────────────────────────────────────────────────

VALID_TYPES = {
    "INTEGER", "REAL", "LOGICAL", "CHARACTER",
    "INTEGER_ARRAY", "REAL_ARRAY", "CHARACTER_ARRAY",
}

VALID_CATEGORIES = {
    "electronic", "ionic", "output", "symmetry", "xc",
    "magnetism", "parallelization", "hybrid", "vdw",
    "gw", "response", "wannier", "ml",
}

REQUIRED_FIELDS = {"name", "type", "default", "category", "description", "status"}


@pytest.fixture(scope="module")
def raw_catalog() -> dict:
    """Load the raw JSON catalog."""
    data_path = resources.files("qmatsuite.drivers.vasp.data").joinpath(
        "vasp_incar_tags.json"
    )
    with resources.as_file(data_path) as path:
        return json.loads(Path(path).read_text(encoding="utf-8"))


class TestINCARCatalogJSON:
    """Validate vasp_incar_tags.json structure."""

    def test_json_loads_valid(self, raw_catalog):
        """JSON parses without error and has expected top-level keys."""
        assert "schema_version" in raw_catalog
        assert "tags" in raw_catalog
        assert raw_catalog["engine"] == "vasp"

    def test_tag_count_minimum(self, raw_catalog):
        """Catalog has 200+ tags."""
        assert len(raw_catalog["tags"]) >= 200

    def test_required_fields_present(self, raw_catalog):
        """Every tag has the required fields."""
        for tag_name, tag in raw_catalog["tags"].items():
            missing = REQUIRED_FIELDS - set(tag.keys())
            assert not missing, f"Tag {tag_name} missing fields: {missing}"

    def test_type_enum_valid(self, raw_catalog):
        """Every tag type is in the valid set."""
        for tag_name, tag in raw_catalog["tags"].items():
            assert tag["type"] in VALID_TYPES, (
                f"Tag {tag_name} has invalid type: {tag['type']}"
            )

    def test_category_valid(self, raw_catalog):
        """Every tag category is in the valid set."""
        for tag_name, tag in raw_catalog["tags"].items():
            assert tag["category"] in VALID_CATEGORIES, (
                f"Tag {tag_name} has invalid category: {tag['category']}"
            )

    def test_no_duplicate_tags(self, raw_catalog):
        """No duplicate tag names (JSON keys are unique by spec)."""
        # Double-check by comparing name field to key
        for key, tag in raw_catalog["tags"].items():
            assert tag["name"] == key, (
                f"Tag key {key} != name field {tag['name']}"
            )


# ──────────────────────────────────────────────────────────────────────────
# Metadata access layer (Step 2)
# ──────────────────────────────────────────────────────────────────────────


class TestMetadataAccessLayer:
    """Test vasp_metadata.py API."""

    def test_safe_load_metadata(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import safe_load_metadata
        data = safe_load_metadata()
        assert "tags" in data
        assert len(data["tags"]) >= 200

    def test_get_tag_info_encut(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import get_tag_info
        info = get_tag_info("ENCUT")
        assert info is not None
        assert info["type"] == "REAL"
        assert info["category"] == "electronic"

    def test_get_tag_info_case_insensitive(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import get_tag_info
        info = get_tag_info("encut")
        assert info is not None
        assert info["name"] == "ENCUT"

    def test_get_tag_info_missing(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import get_tag_info
        info = get_tag_info("NONEXISTENT_TAG_XYZ")
        assert info is None

    def test_list_tags_all(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import list_tags
        tags = list_tags()
        assert len(tags) >= 200
        assert "ENCUT" in tags
        assert "NSW" in tags

    def test_list_tags_by_category(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import list_tags
        electronic_tags = list_tags(category="electronic")
        assert len(electronic_tags) >= 20
        assert "ENCUT" in electronic_tags
        assert "NSW" not in electronic_tags  # ionic

    def test_list_categories(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import list_categories
        cats = list_categories()
        assert len(cats) >= 10
        assert "electronic" in cats
        assert "ionic" in cats
        assert "gw" in cats

    def test_validate_incar_all_valid(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import validate_incar_params
        unknowns = validate_incar_params({"ENCUT": 300, "NSW": 0, "ISMEAR": 0})
        assert unknowns == []

    def test_validate_incar_unknown_flagged(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import validate_incar_params
        unknowns = validate_incar_params({"ENCUT": 300, "FAKEPARAM": 42})
        assert "FAKEPARAM" in unknowns
        assert "ENCUT" not in unknowns

    def test_reload_metadata(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import (
            reload_metadata, safe_load_metadata,
        )
        reload_metadata()
        data = safe_load_metadata()
        assert len(data["tags"]) >= 200

    def test_metadata_debug_info(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import get_metadata_file_info
        info = get_metadata_file_info()
        assert "metadata_path_abs" in info
        assert "schema_version" in info

    def test_get_tag_type(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import get_tag_type
        assert get_tag_type("ENCUT") == "REAL"
        assert get_tag_type("NSW") == "INTEGER"
        assert get_tag_type("LCHARG") == "LOGICAL"
        assert get_tag_type("NONEXISTENT") is None

    def test_get_tag_default(self):
        from qmatsuite.drivers.vasp.data.vasp_metadata import get_tag_default
        assert get_tag_default("ISMEAR") == "1"
        assert get_tag_default("NONEXISTENT") is None
