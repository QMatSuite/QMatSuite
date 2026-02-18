"""Standard response envelope for all MCP tool results."""

from __future__ import annotations

from typing import Any


def make_response(
    data: dict[str, Any],
    context_hint: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Wrap *data* in the standard QMatSuite MCP envelope.

    Returns ``{"data": ..., "context_hint": ..., "warnings": [...]}``.
    """
    return {
        "data": data,
        "context_hint": context_hint,
        "warnings": warnings if warnings is not None else [],
    }
