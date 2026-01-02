"""
Debug flag helpers for conditional logging.

Provides a centralized way to check if specific debug features are enabled.
All debug flags are stored in QMatSuiteSettings and can be toggled via UI.
"""
from __future__ import annotations

from quantumvitas.core.settings import load_settings


def is_resolution_debug_enabled() -> bool:
    """
    Check if resolution/addressing debug logs are enabled.
    
    When enabled, emits detailed trace logs for:
    - Resource resolution (ULID vs slug, expected_kind filtering)
    - Step detail loading (calculation.steps entries, step entry found)
    - Workflow detection (per-step tracing, type resolution)
    - RPC boundary logging (UI-provided identifiers, ULID detection)
    
    Returns:
        True if debug_resolution flag is enabled in settings, False otherwise
    """
    settings = load_settings()
    return settings.debug_resolution

