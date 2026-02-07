"""Tests for Wannier90 parameter metadata catalog and access layer.

Validates the JSON catalog structure and the w90_metadata.py access API.
Follows the VASP test_vasp_metadata.py pattern.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────────
# JSON catalog validation (Phase 1)
# ──────────────────────────────────────────────────────────────────────────

VALID_TYPES = {
    "INTEGER", "REAL", "LOGICAL", "CHARACTER",
}

VALID_CATEGORIES = {
    "disentanglement", "job_control", "plot", "postw90",
    "system", "transport", "wannierise",
}

VALID_KINDS = {"scalar", "block", "list"}

REQUIRED_FIELDS = {"name", "type", "category", "description", "status"}


@pytest.fixture(scope="module")
def raw_catalog() -> dict:
    """Load the raw JSON catalog."""
    data_path = resources.files("quantumvitas.drivers.w90.data").joinpath(
        "w90_tags.json"
    )
    with resources.as_file(data_path) as path:
        return json.loads(Path(path).read_text(encoding="utf-8"))


class TestW90CatalogJSON:
    """Validate w90_tags.json structure."""

    def test_json_loads_valid(self, raw_catalog):
        """JSON parses without error and has expected top-level keys."""
        assert "schema_version" in raw_catalog
        assert "tags" in raw_catalog
        assert raw_catalog["engine"] == "w90"

    def test_schema_version(self, raw_catalog):
        """Schema version is 1."""
        assert raw_catalog["schema_version"] == 1

    def test_tag_count_minimum(self, raw_catalog):
        """Catalog has 50+ tags (specialized engine minimum per playbook)."""
        assert len(raw_catalog["tags"]) >= 50

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

    def test_kind_valid(self, raw_catalog):
        """Every tag with a kind field has a valid value."""
        for tag_name, tag in raw_catalog["tags"].items():
            if "kind" in tag:
                assert tag["kind"] in VALID_KINDS, (
                    f"Tag {tag_name} has invalid kind: {tag['kind']}"
                )

    def test_no_duplicate_tags(self, raw_catalog):
        """Tag name field matches its key."""
        for key, tag in raw_catalog["tags"].items():
            assert tag["name"] == key, (
                f"Tag key {key} != name field {tag['name']}"
            )

    def test_all_names_lowercase(self, raw_catalog):
        """W90 tags are stored in lowercase."""
        for key in raw_catalog["tags"]:
            assert key == key.lower(), f"Tag key {key} is not lowercase"

    def test_has_essential_tags(self, raw_catalog):
        """Catalog includes the most commonly used W90 parameters."""
        essential = [
            "num_wann", "num_bands", "num_iter",
            "dis_win_max", "dis_froz_max", "dis_num_iter",
            "mp_grid", "spinors", "guiding_centres",
            "wannier_plot", "bands_plot", "berry",
        ]
        tags = raw_catalog["tags"]
        for tag in essential:
            assert tag in tags, f"Essential tag {tag} missing from catalog"


# ──────────────────────────────────────────────────────────────────────────
# Metadata access layer (Phase 2)
# ──────────────────────────────────────────────────────────────────────────


class TestW90MetadataAccessLayer:
    """Test w90_metadata.py API."""

    def test_safe_load_metadata(self):
        from quantumvitas.drivers.w90.data.w90_metadata import safe_load_metadata
        data = safe_load_metadata()
        assert "tags" in data
        assert len(data["tags"]) >= 50

    def test_get_tag_info_num_wann(self):
        from quantumvitas.drivers.w90.data.w90_metadata import get_tag_info
        info = get_tag_info("num_wann")
        assert info is not None
        assert info["type"] == "INTEGER"
        assert info["category"] == "system"

    def test_get_tag_info_case_insensitive(self):
        from quantumvitas.drivers.w90.data.w90_metadata import get_tag_info
        info = get_tag_info("NUM_WANN")
        assert info is not None
        assert info["name"] == "num_wann"

    def test_get_tag_info_missing(self):
        from quantumvitas.drivers.w90.data.w90_metadata import get_tag_info
        info = get_tag_info("NONEXISTENT_TAG_XYZ")
        assert info is None

    def test_list_tags_all(self):
        from quantumvitas.drivers.w90.data.w90_metadata import list_tags
        tags = list_tags()
        assert len(tags) >= 50
        assert "num_wann" in tags
        assert "num_iter" in tags

    def test_list_tags_by_category(self):
        from quantumvitas.drivers.w90.data.w90_metadata import list_tags
        dis_tags = list_tags(category="disentanglement")
        assert len(dis_tags) >= 5
        assert "dis_win_max" in dis_tags
        assert "num_wann" not in dis_tags  # system, not disentanglement

    def test_list_categories(self):
        from quantumvitas.drivers.w90.data.w90_metadata import list_categories
        cats = list_categories()
        assert len(cats) >= 5
        assert "system" in cats
        assert "disentanglement" in cats
        assert "wannierise" in cats

    def test_validate_params_all_valid(self):
        from quantumvitas.drivers.w90.data.w90_metadata import validate_params
        unknowns = validate_params({"num_wann": 4, "num_iter": 20, "spinors": True})
        assert unknowns == []

    def test_validate_params_unknown_flagged(self):
        from quantumvitas.drivers.w90.data.w90_metadata import validate_params
        unknowns = validate_params({"num_wann": 4, "fakeparam": 42})
        assert "fakeparam" in unknowns
        assert "num_wann" not in unknowns

    def test_reload_metadata(self):
        from quantumvitas.drivers.w90.data.w90_metadata import (
            reload_metadata, safe_load_metadata,
        )
        reload_metadata()
        data = safe_load_metadata()
        assert len(data["tags"]) >= 50

    def test_metadata_debug_info(self):
        from quantumvitas.drivers.w90.data.w90_metadata import get_metadata_file_info
        info = get_metadata_file_info()
        assert "metadata_path_abs" in info
        assert "schema_version" in info

    def test_get_tag_type(self):
        from quantumvitas.drivers.w90.data.w90_metadata import get_tag_type
        assert get_tag_type("num_wann") == "INTEGER"
        assert get_tag_type("dis_win_max") == "REAL"
        assert get_tag_type("spinors") == "LOGICAL"
        assert get_tag_type("NONEXISTENT") is None

    def test_get_tag_default(self):
        from quantumvitas.drivers.w90.data.w90_metadata import get_tag_default
        # num_wann has no default
        assert get_tag_default("num_wann") is None
        assert get_tag_default("NONEXISTENT") is None
