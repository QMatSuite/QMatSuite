"""Standard response envelope for all MCP tool results."""

from __future__ import annotations

from typing import Any


def make_response(
    data: dict[str, Any],
    context_hint: str | None = None,
    warnings: list[str] | None = None,
    status: str = "success",
) -> dict[str, Any]:
    """Wrap *data* in the standard QMatSuite MCP envelope.

    Returns ``{"status": ..., "data": ..., "context_hint": ..., "warnings": [...]}``.
    """
    return {
        "status": status,
        "data": data,
        "context_hint": context_hint,
        "warnings": warnings if warnings is not None else [],
    }


def make_error(
    error_type: str,
    message: str,
    context_hint: str | None = None,
    suggestions: list[str] | None = None,
) -> dict[str, Any]:
    """Build a standard error envelope.

    Returns ``{"status": "error", "error_type": ..., "message": ..., ...}``.
    """
    return {
        "status": "error",
        "error_type": error_type,
        "message": message,
        "context_hint": context_hint,
        "suggestions": suggestions if suggestions is not None else [],
    }
