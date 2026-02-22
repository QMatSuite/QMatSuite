"""Tests for Gaussian metadata access layer.

Validates the gaussian_metadata.py module (cached JSON loading,
keyword lookup, basis set listing, validation).
"""

from __future__ import annotations

import pytest

from qmatsuite.drivers.gaussian.data.gaussian_metadata import (
    get_keyword_info,
    get_link0_info,
    get_metadata_file_info,
    list_builtin_basis_sets,
    list_categories,
    list_keywords,
    reload_metadata,
    safe_load_metadata,
    validate_route_keywords,
)


class TestMetadataLoading:
    """Test JSON loading and caching."""

    def test_load_metadata(self):
        data = safe_load_metadata()
        assert data["schema_version"] == 1
        assert data["engine"] == "gaussian"
        assert "keywords" in data

    def test_schema_version(self):
        data = safe_load_metadata()
        assert data["schema_version"] == 1

    def test_reload_metadata(self):
        reload_metadata()
        data = safe_load_metadata()
        assert data["schema_version"] == 1

    def test_metadata_file_info(self):
        info = get_metadata_file_info()
        assert info["schema_version"] == 1
        assert info["metadata_path_abs"] is not None


class TestKeywordLookup:
    """Test keyword info retrieval."""

    def test_b3lyp(self):
        info = get_keyword_info("B3LYP")
        assert info is not None
        assert info["kind"] == "method"
        assert "description" in info

    def test_hf(self):
        info = get_keyword_info("HF")
        assert info is not None
        assert info["kind"] == "method"

    def test_mp2(self):
        info = get_keyword_info("MP2")
        assert info is not None
        assert info["kind"] == "method"
        assert "options" in info

    def test_opt(self):
        info = get_keyword_info("Opt")
        assert info is not None
        assert info["kind"] == "job_type"
        assert "options" in info

    def test_td(self):
        info = get_keyword_info("TD")
        assert info is not None
        assert info["kind"] == "property"

    def test_scrf(self):
        info = get_keyword_info("SCRF")
        assert info is not None
        assert "models" in info

    def test_case_insensitive(self):
        info1 = get_keyword_info("B3LYP")
        info2 = get_keyword_info("b3lyp")
        assert info1 is not None
        assert info2 is not None
        assert info1["description"] == info2["description"]

    def test_alias_lookup(self):
        info = get_keyword_info("PBE1PBE")
        assert info is not None
        # PBE1PBE is an alias for PBE0
        assert "Perdew-Burke-Ernzerhof" in info["description"]

    def test_unknown_keyword(self):
        info = get_keyword_info("FakeKeyword123")
        assert info is None


class TestListFunctions:
    """Test listing functions."""

    def test_list_all_keywords(self):
        kws = list_keywords()
        assert len(kws) > 50
        assert "HF" in kws
        assert "B3LYP" in kws
        assert "Opt" in kws

    def test_list_methods(self):
        methods = list_keywords(category="method")
        assert "HF" in methods
        assert "B3LYP" in methods
        assert "MP2" in methods
        assert "Opt" not in methods

    def test_list_job_types(self):
        jobs = list_keywords(category="job_type")
        assert "Opt" in jobs
        assert "Freq" in jobs
        assert "Scan" in jobs

    def test_list_categories(self):
        cats = list_categories()
        assert "method" in cats
        assert "job_type" in cats
        assert "property" in cats
        assert "solvation" in cats

    def test_list_basis_sets(self):
        basis = list_builtin_basis_sets()
        assert len(basis) > 20
        assert "STO-3G" in basis
        assert "6-31G" in basis
        assert "cc-pVDZ" in basis
        assert "def2-SVP" in basis
        assert "LANL2DZ" in basis


class TestLink0Lookup:
    """Test Link0 directive lookup."""

    def test_mem_directive(self):
        info = get_link0_info("%Mem")
        assert info is not None
        assert "Memory" in info["description"]

    def test_chk_directive(self):
        info = get_link0_info("Chk")
        assert info is not None

    def test_nproc_directive(self):
        info = get_link0_info("%NProcShared")
        assert info is not None

    def test_unknown_directive(self):
        info = get_link0_info("FakeDirective")
        assert info is None


class TestValidation:
    """Test route keyword validation."""

    def test_all_known(self):
        unknown = validate_route_keywords(["B3LYP", "Opt", "Freq", "TD"])
        assert unknown == []

    def test_unknown_detected(self):
        unknown = validate_route_keywords(["B3LYP", "Opt", "FakeKeyword"])
        assert "FakeKeyword" in unknown

    def test_method_basis_skipped(self):
        unknown = validate_route_keywords(["B3LYP/6-31G*"])
        assert unknown == []

    def test_parenthetical_skipped(self):
        unknown = validate_route_keywords(["Opt=(Tight)", "TD=(NStates=3)"])
        assert unknown == []

    def test_prefixed_methods(self):
        unknown = validate_route_keywords(["RHF", "UHF", "ROHF"])
        assert unknown == []
