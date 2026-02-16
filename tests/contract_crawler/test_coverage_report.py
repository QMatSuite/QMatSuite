"""Tests for coverage report generation and validation."""

import json
import pytest
from pathlib import Path

from tests.contract_crawler.report_coverage import generate_coverage_report
from tests.contract_crawler.introspection import get_all_rpc_methods


def test_coverage_report_structure():
    """Coverage report has correct structure."""
    report = generate_coverage_report()
    
    # Check top-level keys
    assert "generated_at" in report
    assert "summary" in report
    assert "gui_missing_methods" in report
    assert "methods" in report
    
    # Check summary structure
    summary = report["summary"]
    required_summary_keys = [
        "total_methods", "covered_auto", "covered_recipe",
        "not_covered", "exempt", "gui_total", "gui_covered",
        "gui_exempt", "gui_missing_count",
    ]
    for key in required_summary_keys:
        assert key in summary, f"Missing summary key: {key}"
        assert isinstance(summary[key], int), f"Summary key {key} must be int"
    
    # Check methods structure
    assert isinstance(report["methods"], list)
    assert len(report["methods"]) > 0


def test_all_methods_in_report():
    """All introspected methods appear exactly once in report."""
    all_methods = {m.name for m in get_all_rpc_methods()}
    report = generate_coverage_report()
    
    report_methods = {m["method_name"] for m in report["methods"]}
    
    missing = all_methods - report_methods
    extra = report_methods - all_methods
    
    assert not missing, f"Methods missing from report: {missing}"
    assert not extra, f"Extra methods in report: {extra}"


def test_no_duplicate_methods_in_report():
    """Each method appears exactly once in coverage report."""
    report = generate_coverage_report()

    seen = set()
    for method in report["methods"]:
        name = method["method_name"]
        assert name not in seen, f"Duplicate method in report: {name}"
        seen.add(name)


def test_source_values():
    """Sources are only from allowed set."""
    report = generate_coverage_report()
    
    allowed_sources = {"auto_crawler", "recipe", None}
    
    for method in report["methods"]:
        source = method["source"]
        assert source in allowed_sources, f"Invalid source for {method['method_name']}: {source}"


def test_gui_missing_methods_present():
    """gui_missing_methods list is present and contains only strings."""
    report = generate_coverage_report()
    
    assert "gui_missing_methods" in report
    assert isinstance(report["gui_missing_methods"], list)
    
    for method in report["gui_missing_methods"]:
        assert isinstance(method, str), f"GUI missing method must be string: {method}"
        assert " " not in method, f"GUI missing method must not contain spaces: {method}"


def test_coverage_status_values():
    """Coverage status values are from allowed set."""
    report = generate_coverage_report()
    
    allowed_statuses = {"covered_recipe", "not_covered", "exempt"}
    
    for method in report["methods"]:
        status = method["coverage_status"]
        assert status in allowed_statuses, f"Invalid coverage_status for {method['method_name']}: {status}"




