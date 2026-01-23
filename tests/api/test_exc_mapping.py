"""
Test kernel exception to API error mapping.

Tests for the map_kernel_exception function.
"""

import pytest

from quantumvitas.api._mapping.exc_mapping import map_kernel_exception
from quantumvitas.api.errors import (
    AmbiguousError,
    ConfigError,
    ConflictError,
    EngineError,
    FilesystemError,
    InternalError,
    NotFoundError,
    ValidationError,
)


def test_calculation_not_found_maps_correctly():
    """ResourceNotFoundError → NOT_FOUND."""
    from quantumvitas.core.resolution import ResourceNotFoundError
    
    kernel_exc = ResourceNotFoundError(
        kind="calculation",
        selector="si-scf",
        project_root=None
    )
    api_err = map_kernel_exception(kernel_exc)
    
    assert isinstance(api_err, NotFoundError)
    assert api_err.code == "NOT_FOUND"
    assert api_err.context["resource_type"] == "calculation"
    assert api_err.context["selector"] == "si-scf"
    assert "trace_id" in api_err.cause


def test_ambiguous_selector_maps_correctly():
    """AmbiguousSelectorError → AMBIGUOUS_SELECTOR."""
    from quantumvitas.core.resolution import AmbiguousSelectorError
    
    kernel_exc = AmbiguousSelectorError("si-", ["si-scf", "si-relax"])
    api_err = map_kernel_exception(kernel_exc)
    
    assert isinstance(api_err, AmbiguousError)
    assert api_err.code == "AMBIGUOUS_SELECTOR"
    # AmbiguousSelectorError stores args in exception args
    assert api_err.context["selector"] == "si-"
    assert api_err.context["matches"] == ["si-scf", "si-relax"]


def test_validation_error_maps_correctly():
    """ValidationError → VALIDATION_FAILED."""
    from quantumvitas.core.param_validation import ValidationError as KernelValidationError
    
    kernel_exc = KernelValidationError("Invalid value for ecutwfc")
    api_err = map_kernel_exception(kernel_exc)
    
    assert isinstance(api_err, ValidationError)
    assert api_err.code == "VALIDATION_FAILED"
    assert "field" in api_err.context


def test_value_error_maps_to_validation():
    """ValueError → VALIDATION_FAILED or INVALID_SELECTOR."""
    # Generic ValueError
    api_err = map_kernel_exception(ValueError("Invalid parameter"))
    assert isinstance(api_err, ValidationError)
    
    # Selector-related ValueError
    api_err2 = map_kernel_exception(ValueError("Invalid selector: empty"))
    assert isinstance(api_err2, ValidationError)
    assert api_err2.code == "INVALID_SELECTOR"


def test_type_error_maps_to_validation():
    """TypeError → VALIDATION_FAILED."""
    api_err = map_kernel_exception(TypeError("Expected int, got str"))
    assert isinstance(api_err, ValidationError)
    assert api_err.code == "VALIDATION_FAILED"


def test_calculation_lock_error_maps_correctly():
    """CalculationLockError → EDIT_LOCK_HELD or RUN_LOCK_HELD."""
    from quantumvitas.core.locking import CalculationLockError
    
    # Edit lock (default)
    kernel_exc = CalculationLockError("Calculation is being edited")
    api_err = map_kernel_exception(kernel_exc)
    
    assert isinstance(api_err, ConflictError)
    # Default to EDIT_LOCK_HELD if message doesn't contain "running"
    assert api_err.code in ("EDIT_LOCK_HELD", "RUN_LOCK_HELD")
    assert api_err.retryable is True


def test_permission_error_maps_to_filesystem():
    """PermissionError → FILESYSTEM_ERROR."""
    # PermissionError doesn't take keyword args in Python
    perm_err = PermissionError("Permission denied")
    perm_err.filename = "/tmp/file"  # Set attribute directly
    api_err = map_kernel_exception(perm_err)
    assert isinstance(api_err, FilesystemError)
    assert api_err.code == "FILESYSTEM_ERROR"
    assert api_err.retryable is False
    assert "path" in api_err.context or "operation" in api_err.context


def test_os_error_maps_to_filesystem():
    """OSError → FILESYSTEM_ERROR."""
    import errno
    
    # Disk full (retryable)
    disk_full = OSError("No space left on device")
    disk_full.errno = errno.ENOSPC
    api_err = map_kernel_exception(disk_full)
    assert isinstance(api_err, FilesystemError)
    assert api_err.retryable is True
    
    # Other OSError (not retryable by default)
    other = OSError("File not found")
    other.errno = errno.ENOENT
    api_err2 = map_kernel_exception(other)
    assert isinstance(api_err2, FilesystemError)
    assert api_err2.retryable is False


def test_project_config_error_maps_correctly():
    """ProjectConfigError → PROJECT_SSOT_MISSING."""
    from quantumvitas.core.project_utils import ProjectConfigError
    
    kernel_exc = ProjectConfigError("Missing species_map")
    api_err = map_kernel_exception(kernel_exc)
    
    assert isinstance(api_err, ConfigError)
    assert api_err.code == "PROJECT_SSOT_MISSING"
    assert "missing_key" in api_err.context


def test_unknown_exception_maps_to_internal():
    """Unknown exceptions → INTERNAL_ERROR with trace_id."""
    api_err = map_kernel_exception(RuntimeError("unexpected"))
    assert isinstance(api_err, InternalError)
    assert api_err.code == "INTERNAL_ERROR"
    assert "trace_id" in api_err.context
    assert "trace_id" in api_err.cause


def test_assertion_error_maps_to_internal():
    """AssertionError → INTERNAL_ERROR."""
    api_err = map_kernel_exception(AssertionError("Unexpected assertion"))
    assert isinstance(api_err, InternalError)
    assert api_err.code == "INTERNAL_ERROR"


def test_mapping_includes_trace_id():
    """All mapped errors include trace_id in cause."""
    from quantumvitas.core.resolution import ResourceNotFoundError
    
    kernel_exc = ResourceNotFoundError(kind="calculation", selector="x")
    api_err = map_kernel_exception(kernel_exc)
    
    assert api_err.cause is not None
    assert "trace_id" in api_err.cause
    assert api_err.cause["trace_id"].startswith("tr-")


def test_mapping_preserves_context():
    """Mapping preserves relevant context from kernel exceptions."""
    from quantumvitas.core.resolution import ResourceNotFoundError
    
    kernel_exc = ResourceNotFoundError(
        kind="step",
        selector="step-1",
        id="01HX7YPVK8DQNZPMJ4GHAB1234"
    )
    api_err = map_kernel_exception(kernel_exc)
    
    assert api_err.context["resource_type"] == "step"
    assert api_err.context["selector"] == "step-1"

