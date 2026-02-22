"""
Kernel exception to API error mapping.

This module provides functions to map kernel exceptions to API errors.
This is the SINGLE SOURCE OF TRUTH for exception mapping.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from qmatsuite.api.errors import (
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


def map_kernel_exception(exc: Exception) -> APIError:
    """
    Map kernel exception to API error.
    
    This is the SINGLE SOURCE OF TRUTH for exception mapping.
    All kernel exceptions must be mapped here.
    
    Args:
        exc: Kernel exception to map
        
    Returns:
        APIError with appropriate code and context
    """
    trace_id = _generate_trace_id()
    
    # Resolution errors
    if isinstance(exc, _get_kernel_class("ResourceNotFoundError")):
        return NotFoundError(
            message=str(exc),
            context={
                "selector": getattr(exc, "selector", None) or "",
                "resource_type": getattr(exc, "kind", "resource"),
                "suggestions": getattr(exc, "suggestions", None),
            },
            cause=_make_cause(exc, trace_id),
        )
    
    if isinstance(exc, _get_kernel_class("SelectorNotFoundError")):
        return NotFoundError(
            message=str(exc),
            context={
                "selector": getattr(exc, "selector", ""),
                "resource_type": "resource",
            },
            cause=_make_cause(exc, trace_id),
        )
    
    # Registry out of sync
    if isinstance(exc, _get_kernel_class("RegistryOutOfSyncError")):
        return ConfigError(
            message=str(exc),
            code="REGISTRY_OUT_OF_SYNC",
            context={
                "expected_path": getattr(exc, "expected_path", None),
                "issue": getattr(exc, "issue", "registry_mismatch"),
            },
            cause=_make_cause(exc, trace_id),
        )
    
    # Ambiguous selector
    if isinstance(exc, _get_kernel_class("AmbiguousSelectorError")):
        # AmbiguousSelectorError is a ValueError, extract info from args if available
        selector = ""
        matches = []
        if hasattr(exc, "args") and len(exc.args) >= 1:
            selector = str(exc.args[0])
        if hasattr(exc, "args") and len(exc.args) >= 2:
            matches = list(exc.args[1]) if isinstance(exc.args[1], (list, tuple)) else []
        return AmbiguousError(
            message=str(exc),
            context={
                "selector": selector,
                "matches": matches,
                "resource_type": getattr(exc, "resource_type", "resource"),
            },
            cause=_make_cause(exc, trace_id),
        )
    
    # Invalid selector
    if isinstance(exc, _get_kernel_class("InvalidSelectorError")):
        return ValidationError(
            message=str(exc),
            code="INVALID_SELECTOR",
            context={
                "selector": getattr(exc, "selector", ""),
                "reason": str(exc),
                "expected_format": getattr(exc, "expected_format", None),
            },
            cause=_make_cause(exc, trace_id),
        )
    
    # Config errors (check before ValueError since ProjectConfigError is a ValueError)
    if isinstance(exc, _get_kernel_class("ProjectConfigError")):
        return ConfigError(
            message=str(exc),
            code="PROJECT_SSOT_MISSING",
            context={
                "missing_key": getattr(exc, "missing_key", "unknown"),
                "expected_path": getattr(exc, "expected_path", ""),
            },
            cause=_make_cause(exc, trace_id),
        )
    
    if isinstance(exc, _get_kernel_class("ModeMismatchError")):
        return ConfigError(
            message=str(exc),
            code="MODE_MISMATCH",
            context={
                "expected_mode": getattr(exc, "expected_mode", ""),
                "actual_mode": getattr(exc, "actual_mode", ""),
                "calc_ulid": getattr(exc, "calc_id", ""),
            },
            cause=_make_cause(exc, trace_id),
        )
    
    # Validation errors
    if isinstance(exc, _get_kernel_class("ValidationError")):
        return ValidationError(
            message=str(exc),
            code="VALIDATION_FAILED",
            context={
                "field": getattr(exc, "field", "unknown"),
                "value": str(getattr(exc, "value", "")),
                "constraint": getattr(exc, "constraint", "validation_failed"),
            },
            cause=_make_cause(exc, trace_id),
        )
    
    # Python built-in validation errors (check after specific kernel errors)
    if isinstance(exc, ValueError):
        # Check if it's a selector-related ValueError
        msg = str(exc).lower()
        if "selector" in msg or "invalid" in msg:
            return ValidationError(
                message=str(exc),
                code="INVALID_SELECTOR",
                context={"reason": str(exc)},
                cause=_make_cause(exc, trace_id),
            )
        return ValidationError(
            message=str(exc),
            code="VALIDATION_FAILED",
            context={"reason": str(exc)},
            cause=_make_cause(exc, trace_id),
        )
    
    if isinstance(exc, TypeError):
        return ValidationError(
            message=str(exc),
            code="VALIDATION_FAILED",
            context={"reason": str(exc)},
            cause=_make_cause(exc, trace_id),
        )
    
    # Lock errors
    if isinstance(exc, _get_kernel_class("CalculationLockError")):
        # Determine if it's edit lock or run lock based on message/path
        msg = str(exc).lower()
        if "running" in msg or "run" in msg:
            return ConflictError(
                message=str(exc),
                code="RUN_LOCK_HELD",
                context={
                    "calc_ulid": getattr(exc, "calc_id", ""),
                    "run_ulid": getattr(exc, "run_id", ""),
                },
                cause=_make_cause(exc, trace_id),
            )
        else:
            return ConflictError(
                message=str(exc),
                code="EDIT_LOCK_HELD",
                context={
                    "calc_ulid": getattr(exc, "calc_id", ""),
                    "holder": getattr(exc, "holder", None),
                    "since": getattr(exc, "since", None),
                },
                cause=_make_cause(exc, trace_id),
            )
    
    # Engine errors
    if isinstance(exc, _get_kernel_class("EngineExecutionError")):
        return EngineError(
            message=str(exc),
            code="ENGINE_EXEC_FAILED",
            retryable=True,
            context={
                "engine": getattr(exc, "engine", "unknown"),
                "calc_ulid": getattr(exc, "calc_id", ""),
                "step_ulid": getattr(exc, "step_ulid", ""),
                "exit_code": getattr(exc, "exit_code", -1),
                "log_path": str(getattr(exc, "log_path", "")) if hasattr(exc, "log_path") else None,
            },
            cause=_make_cause(exc, trace_id),
        )
    
    if isinstance(exc, _get_kernel_class("OutputParseError")):
        return EngineError(
            message=str(exc),
            code="ENGINE_OUTPUT_PARSE_FAILED",
            retryable=False,
            context={
                "engine": getattr(exc, "engine", "unknown"),
                "calc_ulid": getattr(exc, "calc_id", ""),
                "step_ulid": getattr(exc, "step_ulid", ""),
                "parser": getattr(exc, "parser", "unknown"),
                "file_path": str(getattr(exc, "file_path", "")) if hasattr(exc, "file_path") else None,
            },
            cause=_make_cause(exc, trace_id),
        )
    
    if isinstance(exc, _get_kernel_class("EngineNotFoundError")):
        return EngineError(
            message=str(exc),
            code="ENGINE_NOT_AVAILABLE",
            retryable=True,
            context={
                "engine": getattr(exc, "engine", "unknown"),
                "executable": getattr(exc, "executable", ""),
            },
            cause=_make_cause(exc, trace_id),
        )
    
    # Filesystem errors
    if isinstance(exc, PermissionError):
        return FilesystemError(
            message=str(exc),
            retryable=False,
            context={
                "operation": "permission_check",
                "path": str(getattr(exc, "filename", "")),
                "reason": "permission denied",
            },
            cause=_make_cause(exc, trace_id),
        )
    
    if isinstance(exc, (OSError, IOError)):
        # Check if it's a disk full error
        errno = getattr(exc, "errno", None)
        retryable = errno == 28  # ENOSPC (disk full)
        
        return FilesystemError(
            message=str(exc),
            retryable=retryable,
            context={
                "operation": getattr(exc, "operation", "filesystem"),
                "path": str(getattr(exc, "filename", "")),
                "reason": str(exc),
                "errno": errno,
            },
            cause=_make_cause(exc, trace_id),
        )
    
    # Fallback: internal error
    return InternalError(
        message="Unexpected error",
        context={"trace_id": trace_id},
        cause=_make_cause(exc, trace_id),
    )


def _generate_trace_id() -> str:
    """Generate a unique trace ID for error tracking."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"tr-{ts}-{uuid.uuid4().hex[:6]}"


def _make_cause(exc: Exception, trace_id: str) -> dict[str, Any]:
    """
    Create cause dict for debug-only error information.
    
    Args:
        exc: Original exception
        trace_id: Trace ID for correlation
        
    Returns:
        Cause dict (NOT stable structure)
    """
    return {
        "origin": "kernel",
        "class": type(exc).__name__,
        "message": str(exc),
        "trace_id": trace_id,
    }


def _get_kernel_class(class_name: str) -> type:
    """
    Dynamically import and return kernel exception class.
    
    This avoids circular imports and allows graceful handling
    if kernel classes are refactored.
    
    Args:
        class_name: Name of exception class
        
    Returns:
        Exception class or a dummy class that never matches
    """
    # Map of kernel exception names to their modules
    kernel_exceptions = {
        "ResourceNotFoundError": ("qmatsuite.core.resolution", "ResourceNotFoundError"),
        "SelectorNotFoundError": ("qmatsuite.core.resolution", "SelectorNotFoundError"),
        "AmbiguousSelectorError": ("qmatsuite.core.resolution", "AmbiguousSelectorError"),
        "InvalidSelectorError": ("qmatsuite.core.resolution", "InvalidSelectorError"),
        "RegistryOutOfSyncError": ("qmatsuite.core.resolution", "RegistryOutOfSyncError"),
        "ValidationError": ("qmatsuite.core.param_validation", "ValidationError"),
        "CalculationLockError": ("qmatsuite.core.locking", "CalculationLockError"),
        "EngineExecutionError": ("qmatsuite.core.driver_exceptions", "DriverError"),  # Fallback
        "OutputParseError": ("qmatsuite.core.driver_exceptions", "DriverError"),  # Fallback
        "EngineNotFoundError": ("qmatsuite.core.driver_exceptions", "UnknownEngineError"),
        "ProjectConfigError": ("qmatsuite.core.project_utils", "ProjectConfigError"),
        "ModeMismatchError": ("qmatsuite.core.project_utils", "ProjectConfigError"),  # Fallback
        # QMSServiceError removed - no longer exists after _api_legacy purge
        # Legacy exception handling preserved via fallback to InternalError
    }
    
    if class_name not in kernel_exceptions:
        # Return a dummy class that never matches isinstance checks
        class DummyException(Exception):
            pass
        return DummyException
    
    module_name, actual_class_name = kernel_exceptions[class_name]
    
    try:
        module = __import__(module_name, fromlist=[actual_class_name])
        return getattr(module, actual_class_name)
    except (ImportError, AttributeError):
        # Return a dummy class if import fails
        class DummyException(Exception):
            pass
        return DummyException
