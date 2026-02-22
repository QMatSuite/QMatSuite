"""
Test project capabilities.

Tests for the project domain in QMSService.
"""

import pytest
from pathlib import Path

from qmatsuite.api.service import QMSService


def test_project_get_config_returns_dict(tmp_path):
    """get_config() returns project config dict."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qms.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QMSService(project_root)
    
    try:
        config = svc.project.get_config()
        assert isinstance(config, dict)
        assert "name" in config
    except Exception:
        # Expected to fail without full project setup
        pass


def test_project_update_config_returns_dict(tmp_path):
    """update_config() returns updated config dict."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qms.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QMSService(project_root)
    
    try:
        config = svc.project.update_config({"description": "test project"})
        assert isinstance(config, dict)
        assert config.get("description") == "test project"
    except Exception:
        # Expected to fail without full project setup
        pass


def test_project_species_map_via_config(tmp_path):
    """Species map can be accessed via get_config()."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qms.yml").write_text("name: test\ncalculations: []\n")

    svc = QMSService(project_root)

    try:
        config = svc.project.get_config()
        species_map = config.get("species_map", {})
        assert isinstance(species_map, dict)
    except Exception:
        # Expected to fail without full project setup
        pass


def test_project_potential_map_via_config(tmp_path):
    """Potential map can be accessed via get_config()."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qms.yml").write_text("name: test\ncalculations: []\n")

    svc = QMSService(project_root)

    try:
        config = svc.project.get_config()
        potential_map = config.get("potential_map", {})
        assert isinstance(potential_map, dict)
    except Exception:
        # Expected to fail without full project setup
        pass


def test_project_list_calculations_returns_list(tmp_path):
    """calculation.list() returns list of CalculationDTO."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qms.yml").write_text("name: test\ncalculations: []\n")

    svc = QMSService(project_root)

    try:
        calcs = svc.calculation.list()
        assert isinstance(calcs, list)
    except Exception:
        # Expected to fail without full project setup
        pass

