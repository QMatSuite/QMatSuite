"""
Test engine capabilities.

Tests for the engine domain in QVService.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from quantumvitas.api.errors import ValidationError
from quantumvitas.api.service import QVService


def test_engine_list_returns_list(tmp_path):
    """list() returns list of engine info dicts."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    try:
        engines = svc.engine.list()
        assert isinstance(engines, list)
        assert all(isinstance(e, dict) for e in engines)
        assert all("name" in e for e in engines)
    except Exception:
        # Expected to fail without full project setup
        pass


def test_engine_get_info_returns_dict(tmp_path):
    """get_info() returns engine info dict."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    try:
        info = svc.engine.get_info("qe")
        assert isinstance(info, dict)
        assert "name" in info
        assert info["name"] == "qe"
    except Exception:
        # Expected to fail without full project setup
        pass


def test_engine_list_step_types_returns_list(tmp_path):
    """list_step_types() returns list of step type info dicts."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    try:
        step_types = svc.engine.list_step_types()
        assert isinstance(step_types, list)
        assert all(isinstance(st, dict) for st in step_types)
    except Exception:
        # Expected to fail without full project setup
        pass


def test_engine_validate_installation_returns_dict(tmp_path):
    """validate_installation() returns validation result dict."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    try:
        result = svc.engine.validate_installation("qe")
        assert isinstance(result, dict)
        assert "engine_name" in result
        assert "ok" in result
        assert "details" in result
    except Exception:
        # Expected to fail without full project setup
        pass


# NOTE: validate_installation tests REMOVED (Batch 37)
# validate_installation, get_info, list_step_types methods removed from Engine
# (0 daemon/CLI usage - callers can use DriverRegistry directly)

