"""Tests for ABINIT input variable metadata catalog and access layer.

Validates the JSON catalog structure and the abinit_metadata.py access API.
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
    "integer", "real", "string",
    "array_int", "array_real",
}

VALID_CATEGORIES = {
    "basic", "structure", "kpoints", "scf", "relaxation", "dynamics",
    "spin", "dftu", "gw", "dfpt", "paw", "output", "parallel",
    "symmetry", "pseudo", "memory", "exchange_correlation", "dataset",
    "bse_tddft", "wannier", "developer",
    # Allow for eph as subcategory of dfpt
    "eph",
}

REQUIRED_FIELDS = {"name", "type", "category", "description", "status"}


@pytest.fixture(scope="module")
def raw_catalog() -> dict:
    """Load the raw JSON catalog."""
    data_path = resources.files("quantumvitas.drivers.abinit.data").joinpath(
        "abinit_tags.json"
    )
    with resources.as_file(data_path) as path:
        return json.loads(Path(path).read_text(encoding="utf-8"))


class TestABINITCatalogJSON:
    """Validate abinit_tags.json structure."""

    def test_json_loads_valid(self, raw_catalog):
        """JSON parses without error and has expected top-level keys."""
        assert "schema_version" in raw_catalog
        assert "tags" in raw_catalog
        assert raw_catalog["engine"] == "abinit"

    def test_tag_count_minimum(self, raw_catalog):
        """Catalog has 100+ tags."""
        assert len(raw_catalog["tags"]) >= 100

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
        """Tag key matches name field."""
        for key, tag in raw_catalog["tags"].items():
            assert tag["name"] == key, (
                f"Tag key {key} != name field {tag['name']}"
            )

    def test_core_tags_present(self, raw_catalog):
        """Essential ABINIT variables exist in catalog."""
        core_tags = [
            "ecut", "natom", "ntypat", "typat", "znucl", "acell", "rprim",
            "xred", "ngkpt", "nstep", "toldfe", "tolvrs", "ionmov", "optcell",
            "nsppol", "nband", "occopt", "iscf", "ixc", "rfphon", "optdriver",
        ]
        tags = raw_catalog["tags"]
        for tag in core_tags:
            assert tag in tags, f"Core tag {tag} missing from catalog"


# ──────────────────────────────────────────────────────────────────────────
# Metadata access layer
# ──────────────────────────────────────────────────────────────────────────


class TestMetadataAccessLayer:
    """Test abinit_metadata.py API."""

    def test_safe_load_metadata(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import safe_load_metadata
        data = safe_load_metadata()
        assert "tags" in data
        assert len(data["tags"]) >= 100

    def test_get_tag_info_ecut(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import get_tag_info
        info = get_tag_info("ecut")
        assert info is not None
        assert info["type"] == "real"
        assert "cutoff" in info["description"].lower()

    def test_get_tag_info_case_insensitive(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import get_tag_info
        info = get_tag_info("ECUT")
        assert info is not None
        assert info["name"] == "ecut"

    def test_get_tag_info_missing(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import get_tag_info
        info = get_tag_info("NONEXISTENT_TAG_XYZ")
        assert info is None

    def test_list_tags_all(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import list_tags
        tags = list_tags()
        assert len(tags) >= 100
        assert "ecut" in tags
        assert "ionmov" in tags

    def test_list_tags_by_category(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import list_tags
        structure_tags = list_tags(category="structure")
        assert len(structure_tags) >= 5
        assert "natom" in structure_tags
        assert "ecut" not in structure_tags

    def test_list_categories(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import list_categories
        cats = list_categories()
        assert len(cats) >= 10
        assert "structure" in cats
        assert "kpoints" in cats
        assert "gw" in cats

    def test_validate_params_all_valid(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import validate_params
        unknowns = validate_params({"ecut": 10, "nstep": 30, "toldfe": 1e-8})
        assert unknowns == []

    def test_validate_params_unknown_flagged(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import validate_params
        unknowns = validate_params({"ecut": 10, "fakeparam": 42})
        assert "fakeparam" in unknowns
        assert "ecut" not in unknowns

    def test_reload_metadata(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import (
            reload_metadata, safe_load_metadata,
        )
        reload_metadata()
        data = safe_load_metadata()
        assert len(data["tags"]) >= 100

    def test_metadata_debug_info(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import get_metadata_file_info
        info = get_metadata_file_info()
        assert "metadata_path_abs" in info
        assert "schema_version" in info

    def test_get_tag_type(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import get_tag_type
        assert get_tag_type("ecut") == "real"
        assert get_tag_type("nstep") == "integer"
        assert get_tag_type("ngkpt") == "array_int"
        assert get_tag_type("NONEXISTENT") is None

    def test_get_tag_default(self):
        from quantumvitas.drivers.abinit.data.abinit_metadata import get_tag_default
        assert get_tag_default("nstep") == "30"
        assert get_tag_default("NONEXISTENT") is None
