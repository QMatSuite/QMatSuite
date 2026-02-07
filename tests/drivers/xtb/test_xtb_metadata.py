"""Tests for xTB metadata catalog and access layer."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from quantumvitas.drivers.xtb.data.xtb_metadata import (
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


def _raw_catalog() -> dict:
    data_path = resources.files("quantumvitas.drivers.xtb.data").joinpath("xtb_tags.json")
    with resources.as_file(data_path) as path:
        return json.loads(Path(path).read_text(encoding="utf-8"))


class TestXTBCatalogJSON:
    def test_catalog_loads(self):
        raw = _raw_catalog()
        assert raw["schema_version"] == 1
        assert raw["engine"] == "xtb"
        assert "tags" in raw

    def test_tag_count_minimum(self):
        raw = _raw_catalog()
        assert len(raw["tags"]) >= 50

    def test_required_fields(self):
        raw = _raw_catalog()
        required = {"name", "type", "default", "category", "description", "status"}
        for tag_name, info in raw["tags"].items():
            assert required.issubset(info), f"Missing fields for {tag_name}"


class TestXTBMetadataAPI:
    def test_safe_load(self):
        data = safe_load_metadata()
        assert data["engine"] == "xtb"
        assert len(data["tags"]) >= 50

    def test_reload(self):
        reload_metadata()
        data = safe_load_metadata()
        assert data["schema_version"] == 1

    def test_get_tag_info_case_insensitive(self):
        assert get_tag_info("--gfn") is not None
        assert get_tag_info("--GFN") is not None

    def test_get_tag_info_missing(self):
        assert get_tag_info("--missing-flag") is None

    def test_list_tags(self):
        tags = list_tags()
        assert "--gfn" in tags
        assert "--opt" in tags

    def test_list_tags_by_category(self):
        runtype = list_tags(category="runtype")
        assert "--sp" in runtype
        assert "--opt" in runtype

    def test_list_categories(self):
        cats = list_categories()
        assert "runtype" in cats
        assert "method" in cats

    def test_validate_params(self):
        unknown = validate_params({"--gfn": 2, "--not-real": True})
        assert "--not-real" in unknown
        assert "--gfn" not in unknown

    def test_get_tag_type_default(self):
        assert get_tag_type("--gfn") == "integer"
        assert get_tag_default("--gfn") == 2

    def test_metadata_file_info(self):
        info = get_metadata_file_info()
        assert "schema_version" in info
        assert info["schema_version"] == 1
