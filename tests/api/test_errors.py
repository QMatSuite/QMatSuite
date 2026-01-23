"""
Test API error hierarchy and DTO conversion.

Tests for the API error classes and their conversion to ErrorDTO.
"""

import json

import pytest

from quantumvitas.api.errors import (
    APIError,
    AmbiguousError,
    ConfigError,
    ConflictError,
    EngineError,
    FilesystemError,
    InternalError,
    NotFoundError,
    ValidationError,
)
from quantumvitas.api.types.error import ErrorDTO


def test_error_dto_required_fields():
    """ErrorDTO has all required fields."""
    err = NotFoundError(
        message="Calculation 'si-scf' not found",
        context={"selector": "si-scf", "resource_type": "calculation"}
    )
    dto = err.to_dto()
    d = dto.to_dict()
    
    assert d["type"] == "NotFoundError"
    assert d["code"] == "NOT_FOUND"
    assert d["message"] == "Calculation 'si-scf' not found"
    assert d["retryable"] is False
    assert "context" in d
    assert d["context"]["selector"] == "si-scf"
    assert d["context"]["resource_type"] == "calculation"


def test_error_dto_json_serializable():
    """ErrorDTO.to_dict() is JSON-serializable."""
    err = NotFoundError(
        message="Test message",
        context={"selector": "x", "resource_type": "calculation"}
    )
    dto = err.to_dto()
    d = dto.to_dict()
    
    # Must not raise
    json_str = json.dumps(d)
    assert json_str
    # Round-trip test
    loaded = json.loads(json_str)
    assert loaded["code"] == "NOT_FOUND"


def test_not_found_error():
    """NotFoundError has correct code and retryable."""
    err = NotFoundError(
        message="Not found",
        context={"selector": "x", "resource_type": "calculation"}
    )
    assert err.code == "NOT_FOUND"
    assert err.retryable is False
    dto = err.to_dto()
    assert dto.code == "NOT_FOUND"


def test_ambiguous_error():
    """AmbiguousError has correct code."""
    err = AmbiguousError(
        message="Multiple matches",
        context={
            "selector": "si-",
            "matches": ["si-scf", "si-relax"],
            "resource_type": "calculation"
        }
    )
    assert err.code == "AMBIGUOUS_SELECTOR"
    assert err.retryable is False


def test_validation_error_default():
    """ValidationError defaults to VALIDATION_FAILED."""
    err = ValidationError(
        message="Invalid value",
        context={"field": "ecutwfc", "value": -10}
    )
    assert err.code == "VALIDATION_FAILED"
    dto = err.to_dto()
    assert dto.code == "VALIDATION_FAILED"


def test_validation_error_invalid_selector():
    """ValidationError can use INVALID_SELECTOR code."""
    err = ValidationError(
        message="Invalid selector",
        code="INVALID_SELECTOR",
        context={"selector": "", "reason": "empty string"}
    )
    assert err.code == "INVALID_SELECTOR"
    dto = err.to_dto()
    assert dto.code == "INVALID_SELECTOR"


def test_conflict_error_edit_lock():
    """ConflictError can use EDIT_LOCK_HELD code."""
    err = ConflictError(
        message="Lock held",
        code="EDIT_LOCK_HELD",
        context={"calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234"}
    )
    assert err.code == "EDIT_LOCK_HELD"
    assert err.retryable is True


def test_conflict_error_run_lock():
    """ConflictError can use RUN_LOCK_HELD code."""
    err = ConflictError(
        message="Calculation running",
        code="RUN_LOCK_HELD",
        context={"calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234", "run_id": "01HX7YPVK8DQNZPMJ4GHABCDEF"}
    )
    assert err.code == "RUN_LOCK_HELD"
    assert err.retryable is True


def test_engine_error_default():
    """EngineError defaults to ENGINE_EXEC_FAILED."""
    err = EngineError(
        message="Engine failed",
        context={"engine": "qe", "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234"}
    )
    assert err.code == "ENGINE_EXEC_FAILED"
    assert err.retryable is True


def test_engine_error_parse_failed():
    """EngineError can use ENGINE_OUTPUT_PARSE_FAILED code."""
    err = EngineError(
        message="Parse failed",
        code="ENGINE_OUTPUT_PARSE_FAILED",
        retryable=False,
        context={"engine": "qe", "parser": "xml"}
    )
    assert err.code == "ENGINE_OUTPUT_PARSE_FAILED"
    assert err.retryable is False


def test_engine_error_not_available():
    """EngineError can use ENGINE_NOT_AVAILABLE code."""
    err = EngineError(
        message="Engine not found",
        code="ENGINE_NOT_AVAILABLE",
        context={"engine": "qe", "executable": "pw.x"}
    )
    assert err.code == "ENGINE_NOT_AVAILABLE"
    assert err.retryable is True


def test_config_error_ssot_missing():
    """ConfigError can use PROJECT_SSOT_MISSING code."""
    err = ConfigError(
        message="Missing SSOT",
        code="PROJECT_SSOT_MISSING",
        context={"missing_key": "species_map", "expected_path": "project.qv.yml"}
    )
    assert err.code == "PROJECT_SSOT_MISSING"
    assert err.retryable is False


def test_config_error_mode_mismatch():
    """ConfigError can use MODE_MISMATCH code."""
    err = ConfigError(
        message="Mode mismatch",
        code="MODE_MISMATCH",
        context={"expected_mode": "project", "actual_mode": "legacy", "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234"}
    )
    assert err.code == "MODE_MISMATCH"
    assert err.retryable is False


def test_filesystem_error():
    """FilesystemError has correct code."""
    err = FilesystemError(
        message="Permission denied",
        retryable=False,
        context={"operation": "write", "path": "/tmp/file", "reason": "permission denied"}
    )
    assert err.code == "FILESYSTEM_ERROR"
    assert err.retryable is False


def test_internal_error():
    """InternalError has correct code."""
    err = InternalError(
        message="Unexpected error",
        context={"trace_id": "tr-20260123-143000-abc123"}
    )
    assert err.code == "INTERNAL_ERROR"
    assert err.retryable is False


def test_error_dto_with_hint():
    """ErrorDTO includes hint if provided."""
    err = NotFoundError(
        message="Not found",
        hint="Did you mean 'si-scf'?",
        context={"selector": "si-scff", "resource_type": "calculation"}
    )
    dto = err.to_dto()
    d = dto.to_dict()
    assert d["hint"] == "Did you mean 'si-scf'?"


def test_error_dto_with_cause():
    """ErrorDTO includes cause (debug-only)."""
    err = InternalError(
        message="Unexpected error",
        context={"trace_id": "tr-123"},
        cause={"origin": "kernel", "class": "KeyError", "message": "missing key"}
    )
    dto = err.to_dto()
    d = dto.to_dict()
    assert "cause" in d
    assert d["cause"]["origin"] == "kernel"


def test_error_dto_optional_fields_none():
    """ErrorDTO omits None optional fields."""
    err = NotFoundError(
        message="Not found",
        context={"selector": "x", "resource_type": "calculation"}
    )
    dto = err.to_dto()
    d = dto.to_dict()
    # Current implementation omits None values
    assert "hint" not in d or d["hint"] is None
    assert "cause" not in d or d["cause"] is None

