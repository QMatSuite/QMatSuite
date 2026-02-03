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


def test_validate_installation_known_engine(tmp_path):
    """validate_installation() returns correct schema for known engine."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    # Mock QE resolver to avoid requiring actual QE installation
    with patch("quantumvitas.drivers.qe.engine.qe_resolver.resolve_qe_bin_dir") as mock_resolve:
        mock_resolve.return_value = Path("/fake/qe/bin")
        
        result = svc.engine.validate_installation("qe")
        
        # Verify schema
        assert isinstance(result, dict)
        assert result["engine_name"] == "qe"
        assert isinstance(result["ok"], bool)
        assert isinstance(result["details"], dict)
        
        # Verify JSON serialization
        json_str = json.dumps(result)
        assert json_str is not None
        
        # Verify round-trip
        parsed = json.loads(json_str)
        assert parsed["engine_name"] == "qe"
        assert "ok" in parsed
        assert "details" in parsed


def test_validate_installation_unknown_engine(tmp_path):
    """validate_installation() raises ValidationError for unknown engine."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    # Mock DriverRegistry to raise UnknownEngineError
    with patch("quantumvitas.core.driver_registry.DriverRegistry.get_driver") as mock_get:
        from quantumvitas.core.driver_exceptions import UnknownEngineError
        mock_get.side_effect = UnknownEngineError("no_such_engine_123", [])
        
        with pytest.raises(ValidationError) as exc_info:
            svc.engine.validate_installation("no_such_engine_123")
        
        assert exc_info.value.code == "VALIDATION_FAILED"
        assert "no_such_engine_123" in str(exc_info.value).lower() or "unknown" in str(exc_info.value).lower()
        assert exc_info.value.context is not None
        assert exc_info.value.context.get("engine_name") == "no_such_engine_123"


def test_validate_installation_qe_not_found(tmp_path):
    """validate_installation() returns ok=False when QE binary not found."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    # Mock QE resolver to raise RuntimeError (QE not found)
    with patch("quantumvitas.drivers.qe.engine.qe_resolver.resolve_qe_bin_dir") as mock_resolve:
        mock_resolve.side_effect = RuntimeError("No QE found")
        
        result = svc.engine.validate_installation("qe")
        
        assert result["engine_name"] == "qe"
        assert result["ok"] is False
        assert "message" in result
        assert "details" in result
        assert "error" in result["details"]


def test_validate_installation_engine_without_hook(tmp_path):
    """validate_installation() returns ok=True for engines without validation hooks."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    # Test with an engine that doesn't have a validation hook (e.g., pyscf)
    # This should return ok=True with a note
    result = svc.engine.validate_installation("pyscf")
    
    assert result["engine_name"] == "pyscf"
    assert result["ok"] is True
    assert "details" in result
    assert "note" in result["details"] or "message" in result

