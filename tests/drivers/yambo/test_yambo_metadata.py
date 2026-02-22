"""Tests for Yambo metadata catalog and access layer."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest

from qmatsuite.drivers.yambo.data.yambo_metadata import (
    get_metadata_file_info,
    get_tag_default,
    get_tag_info,
    get_tag_type,
    list_categories,
    list_tags,
    reload_metadata,
    safe_load_metadata,
    validate_params,
)

REQUIRED_FIELDS = {"name", "type", "category", "description", "status"}


@pytest.fixture(scope="module")
def raw_catalog() -> dict:
    data_path = resources.files("qmatsuite.drivers.yambo.data").joinpath(
        "yambo_tags.json"
    )
    with resources.as_file(data_path) as path:
        return json.loads(Path(path).read_text(encoding="utf-8"))


class TestYamboCatalogJSON:
    def test_json_loads(self, raw_catalog):
        assert raw_catalog["engine"] == "yambo"
        assert raw_catalog["schema_version"] == 1
        assert "tags" in raw_catalog

    def test_tag_count_minimum(self, raw_catalog):
        # Specialized engine floor from playbook: 50+
        assert len(raw_catalog["tags"]) >= 50

    def test_required_fields(self, raw_catalog):
        for tag_name, tag in raw_catalog["tags"].items():
            missing = REQUIRED_FIELDS - set(tag)
            assert not missing, f"Tag {tag_name} missing fields: {missing}"

    def test_tag_key_matches_name(self, raw_catalog):
        for key, tag in raw_catalog["tags"].items():
            assert tag["name"] == key


class TestYamboMetadataAccess:
    def test_safe_load_metadata(self):
        data = safe_load_metadata()
        assert "tags" in data
        assert len(data["tags"]) >= 50

    def test_get_tag_info_case_insensitive(self):
        assert get_tag_info("chimod") is not None
        assert get_tag_info("ChImOd") is not None

    def test_list_tags(self):
        tags = list_tags()
        assert "Chimod" in tags
        assert len(tags) >= 50

    def test_list_categories(self):
        cats = list_categories()
        assert isinstance(cats, list)
        assert len(cats) > 0

    def test_validate_params(self):
        unknown = validate_params({"Chimod": "IP", "NotARealTag": 1})
        assert "NotARealTag" in unknown
        assert "Chimod" not in unknown

    def test_type_and_default_helpers(self):
        assert get_tag_type("Chimod") is not None
        default = get_tag_default("Chimod")
        assert default is None or isinstance(
            default, (str, int, float, bool, list, dict)
        )

    def test_reload_and_debug_info(self):
        reload_metadata()
        data = safe_load_metadata()
        assert "tags" in data
        info = get_metadata_file_info()
        assert "metadata_path_abs" in info
        assert "schema_version" in info
