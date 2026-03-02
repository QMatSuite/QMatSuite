"""Tests for MACE metadata access layer."""

from __future__ import annotations

import pytest

from qmatsuite.drivers.mace.data.mace_metadata import (
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


class TestMACEMetadataLoading:
    def test_safe_load_metadata(self):
        data = safe_load_metadata()
        assert data["schema_version"] == 1
        assert data["engine"] == "mace"
        assert "tags" in data

    def test_schema_version(self):
        data = safe_load_metadata()
        assert data["schema_version"] == 1

    def test_tag_count(self):
        tags = list_tags()
        assert len(tags) >= 30, f"Expected at least 30 tags, got {len(tags)}"

    def test_reload_metadata(self):
        reload_metadata()
        data = safe_load_metadata()
        assert data["engine"] == "mace"


class TestMACETagInfo:
    def test_get_model_tag(self):
        info = get_tag_info("model")
        assert info is not None
        assert info["type"] == "enum"
        assert info["default"] == "medium"
        assert info["category"] == "model"

    def test_get_device_tag(self):
        info = get_tag_info("device")
        assert info is not None
        assert info["type"] == "enum"
        assert info["default"] == "cpu"

    def test_get_optimizer_tag(self):
        info = get_tag_info("optimizer")
        assert info is not None
        assert info["default"] == "BFGS"

    def test_get_fmax_tag(self):
        info = get_tag_info("fmax")
        assert info is not None
        assert info["type"] == "float"
        assert info["default"] == 0.05

    def test_get_md_ensemble_tag(self):
        info = get_tag_info("md_ensemble")
        assert info is not None
        assert info["default"] == "NVT"

    def test_get_nonexistent_tag(self):
        info = get_tag_info("nonexistent_tag_xyz")
        assert info is None

    def test_case_insensitive_lookup(self):
        info = get_tag_info("MODEL")
        assert info is not None
        assert info["name"] == "model"


class TestMACETagTypes:
    def test_get_tag_type(self):
        assert get_tag_type("model") == "enum"
        assert get_tag_type("fmax") == "float"
        assert get_tag_type("max_steps") == "integer"
        assert get_tag_type("dispersion") == "boolean"

    def test_get_tag_default(self):
        assert get_tag_default("model") == "medium"
        assert get_tag_default("device") == "cpu"
        assert get_tag_default("fmax") == 0.05

    def test_nonexistent_type(self):
        assert get_tag_type("nonexistent") is None
        assert get_tag_default("nonexistent") is None


class TestMACECategories:
    def test_list_categories(self):
        cats = list_categories()
        assert len(cats) >= 5
        assert "model" in cats
        assert "device" in cats
        assert "optimizer" in cats
        assert "md_ensemble" in cats

    def test_list_tags_by_category(self):
        model_tags = list_tags(category="model")
        assert len(model_tags) >= 2
        assert "model" in model_tags

    def test_list_all_tags(self):
        all_tags = list_tags()
        assert len(all_tags) >= 30


class TestMACEValidation:
    def test_validate_known_params(self):
        unknown = validate_params({"model": "medium", "fmax": 0.01})
        assert unknown == []

    def test_validate_unknown_params(self):
        unknown = validate_params({"bogus_param": 42, "model": "medium"})
        assert "bogus_param" in unknown

    def test_validate_skip_underscore(self):
        unknown = validate_params({"_internal": True, "bogus": 1})
        assert "_internal" not in unknown
        assert "bogus" in unknown


class TestMACEMetadataFileInfo:
    def test_file_info(self):
        info = get_metadata_file_info()
        assert "metadata_path_abs" in info
        assert "schema_version" in info
        assert info["schema_version"] == 1
