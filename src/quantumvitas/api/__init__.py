"""
QuantumVITAS API - Stable public interface.

This module provides the public API for QuantumVITAS operations.
All frontends (CLI, daemon, Jupyter) should import from this module only.

PR0: Stub structure - maintains compatibility with existing _api_legacy.py
"""

from __future__ import annotations

# Import from existing _api_legacy.py for compatibility (PR0)
# This will be gradually migrated in subsequent PRs
import importlib.util
from pathlib import Path

# Load _api_legacy module
_api_legacy_path = Path(__file__).parent.parent / "_api_legacy.py"
spec = importlib.util.spec_from_file_location("quantumvitas._api_legacy", _api_legacy_path)
_api_legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_api_legacy)

# Re-export everything from _api_legacy for compatibility
# PR0: Freeze growth - no new re-exports allowed
# PR1-PR10: Gradually remove re-exports
from quantumvitas._api_legacy import *  # noqa: F401, F403

# Explicitly import symbols that are in _api_legacy but not in __all__
# (These are imported in _api_legacy but not listed in __all__)
from quantumvitas._api_legacy import (  # noqa: F401
    LegacyProjectError,
    CandidateSummary,
    QECardType,
    QEModule,
    QEInputParser,
    DOSData,
    StructureStepSpec,
)

# Also export new API structure (PR1: Error infrastructure complete)
# NOTE: QVService comes from _api_legacy for now (PR0)
# The stub in api.service will replace it in PR2+
from quantumvitas.api.errors import (  # noqa: F401
    APIError,
    NotFoundError,
    AmbiguousError,
    ValidationError,
    ConflictError,
    EngineError,
    ConfigError,
    FilesystemError,
    InternalError,
)
from quantumvitas.api.types import BaseDTO, ErrorDTO  # noqa: F401

# Export new structure + legacy exports
# Note: __all__ from _api_legacy is also included via * import above
# QVService is already exported from _api_legacy
__all__ = [
    # Service (from _api_legacy for now)
    # "QVService",  # Already in _api_legacy.__all__
    # Errors (PR1: Complete)
    "APIError",
    "NotFoundError",
    "AmbiguousError",
    "ValidationError",
    "ConflictError",
    "EngineError",
    "ConfigError",
    "FilesystemError",
    "InternalError",
    # DTOs (PR1: ErrorDTO complete)
    "BaseDTO",
    "ErrorDTO",
    # Legacy exports (from _api_legacy) - will be removed in PR2-PR10
]

