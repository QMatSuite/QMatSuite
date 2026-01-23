"""
API error hierarchy.

This module defines the API-owned error classes.
All API errors must inherit from APIError and implement to_dto().
"""

from __future__ import annotations

from typing import Any

from quantumvitas.api.types.error import ErrorDTO


class APIError(Exception):
    """
    Base exception for all API errors.
    
    All API errors must:
    - Have a stable error code
    - Be convertible to ErrorDTO via to_dto()
    - Include context for programmatic handling
    """
    
    # Error code (must be set by subclasses)
    code: str = "INTERNAL_ERROR"
    
    # Default retryable flag (can be overridden)
    retryable: bool = False
    
    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        cause: dict[str, Any] | None = None,
    ):
        """
        Initialize API error.
        
        Args:
            message: Human-readable error message
            hint: Optional hint for user (e.g., "Did you mean 'x'?")
            context: Optional context dict (stable keys per error code)
            cause: Optional debug-only cause dict (NOT stable)
        """
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.context = context or {}
        self.cause = cause
    
    def to_dto(self) -> ErrorDTO:
        """
        Convert error to ErrorDTO.
        
        Returns:
            ErrorDTO with all fields populated
        """
        return ErrorDTO(
            type=type(self).__name__,
            code=self.code,
            message=self.message,
            retryable=self.retryable,
            hint=self.hint,
            context=self.context if self.context else None,
            cause=self.cause,
        )


# Resolution errors

class NotFoundError(APIError):
    """Raised when a resource cannot be found."""
    code = "NOT_FOUND"
    retryable = False


class AmbiguousError(APIError):
    """Raised when a selector matches multiple resources."""
    code = "AMBIGUOUS_SELECTOR"
    retryable = False


# Input validation errors

class ValidationError(APIError):
    """
    Raised when input validation fails.
    
    Can use code "VALIDATION_FAILED" or "INVALID_SELECTOR" depending on context.
    """
    code = "VALIDATION_FAILED"
    retryable = False
    
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        cause: dict[str, Any] | None = None,
    ):
        """
        Initialize validation error.
        
        Args:
            message: Error message
            code: Optional error code override ("VALIDATION_FAILED" or "INVALID_SELECTOR")
            hint: Optional hint
            context: Optional context
            cause: Optional debug-only cause
        """
        super().__init__(message, hint=hint, context=context, cause=cause)
        if code:
            self.code = code


# Concurrency errors

class ConflictError(APIError):
    """
    Raised when a resource conflict occurs (lock held, etc.).
    
    Can use code "EDIT_LOCK_HELD" or "RUN_LOCK_HELD".
    """
    code = "EDIT_LOCK_HELD"
    retryable = True
    
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        cause: dict[str, Any] | None = None,
    ):
        """
        Initialize conflict error.
        
        Args:
            message: Error message
            code: Error code ("EDIT_LOCK_HELD" or "RUN_LOCK_HELD")
            hint: Optional hint
            context: Optional context
            cause: Optional debug-only cause
        """
        super().__init__(message, hint=hint, context=context, cause=cause)
        if code:
            self.code = code


# Execution errors

class EngineError(APIError):
    """
    Raised when engine execution fails.
    
    Can use codes:
    - "ENGINE_EXEC_FAILED"
    - "ENGINE_OUTPUT_PARSE_FAILED"
    - "ENGINE_NOT_AVAILABLE"
    """
    code = "ENGINE_EXEC_FAILED"
    retryable = True  # Default, can be overridden
    
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        retryable: bool | None = None,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        cause: dict[str, Any] | None = None,
    ):
        """
        Initialize engine error.
        
        Args:
            message: Error message
            code: Error code (default: "ENGINE_EXEC_FAILED")
            retryable: Whether retry may succeed (default: True)
            hint: Optional hint
            context: Optional context
            cause: Optional debug-only cause
        """
        super().__init__(message, hint=hint, context=context, cause=cause)
        if code:
            self.code = code
        if retryable is not None:
            self.retryable = retryable


# Configuration errors

class ConfigError(APIError):
    """
    Raised when project configuration is invalid.
    
    Can use codes:
    - "PROJECT_SSOT_MISSING"
    - "MODE_MISMATCH"
    """
    code = "PROJECT_SSOT_MISSING"
    retryable = False
    
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        cause: dict[str, Any] | None = None,
    ):
        """
        Initialize config error.
        
        Args:
            message: Error message
            code: Error code ("PROJECT_SSOT_MISSING" or "MODE_MISMATCH")
            hint: Optional hint
            context: Optional context
            cause: Optional debug-only cause
        """
        super().__init__(message, hint=hint, context=context, cause=cause)
        if code:
            self.code = code


# System errors

class FilesystemError(APIError):
    """Raised when filesystem operations fail."""
    code = "FILESYSTEM_ERROR"
    retryable = True  # Depends on cause, can be overridden
    
    def __init__(
        self,
        message: str,
        *,
        retryable: bool | None = None,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        cause: dict[str, Any] | None = None,
    ):
        """
        Initialize filesystem error.
        
        Args:
            message: Error message
            retryable: Whether retry may succeed (default: True, but depends on cause)
            hint: Optional hint
            context: Optional context
            cause: Optional debug-only cause
        """
        super().__init__(message, hint=hint, context=context, cause=cause)
        if retryable is not None:
            self.retryable = retryable


class InternalError(APIError):
    """Raised for unexpected internal errors."""
    code = "INTERNAL_ERROR"
    retryable = False
