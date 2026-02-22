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
    *,
    severity: str = "error",
    diagnostics: list[dict[str, Any]] | None = None,
    suggested_fixes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a standard error envelope.

    Returns ``{"status": "error", "error_type": ..., "message": ..., ...}``.

    New keyword-only fields (backward-compatible — existing callers unaffected):

    * *severity*: ``"error"`` (default), ``"warning"``, or ``"info"``.
    * *diagnostics*: per-parameter issues, e.g.
      ``[{"param": "ENCUT", "issue": "must be positive"}]``.
    * *suggested_fixes*: machine-actionable fix hints, e.g.
      ``[{"action": "set_parameters", "params": {"ENCUT": 520}}]``.
    """
    envelope: dict[str, Any] = {
        "status": "error",
        "error_type": error_type,
        "message": message,
        "severity": severity,
        "context_hint": context_hint,
        "suggestions": suggestions if suggestions is not None else [],
    }
    if diagnostics is not None:
        envelope["diagnostics"] = diagnostics
    if suggested_fixes is not None:
        envelope["suggested_fixes"] = suggested_fixes
    return envelope
