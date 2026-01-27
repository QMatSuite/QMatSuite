"""
API compatibility layer for daemon-specific imports.

This module re-exports kernel types that the daemon needs access to
but that aren't proper API types. This allows the daemon to import
from a sanctioned API-layer module instead of directly from kernel modules.

Note: This is a transitional pattern. Ideally, types like DisplayModeParams
should be defined in api/types/ and imported by the analysis module.
"""

# Re-export visualization types for daemon use
from quantumvitas.analysis.structure_viz import DisplayModeParams  # noqa: F401

__all__ = ["DisplayModeParams"]
