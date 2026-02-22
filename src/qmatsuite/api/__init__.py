"""
QMatSuite API - Stable public interface.

This module provides the public API for QMatSuite operations.
All frontends (CLI, daemon, Jupyter) should import from this module only.

PR10: Final API surface - no _api_legacy, minimal exports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# PR10: Import QMSService from api.service (no _api_legacy)
from qmatsuite.api.service import QMSService  # noqa: F401

# PR10: Error infrastructure (PR1: Complete)
from qmatsuite.api.errors import (  # noqa: F401
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

# Compatibility alias for legacy code (frontends/cli still uses this)
QMSServiceError = APIError  # noqa: F401

# PR10: Core DTOs (PR2: Complete)
from qmatsuite.api.types import (  # noqa: F401
    BaseDTO,
    ErrorDTO,
    MetaDTO,
    CalculationDTO,
    CalculationRefDTO,
    StepDTO,
    StructureDTO,
    RunResultDTO,
    AnalysisRefDTO,
    AnalysisSummaryDTO,
    # Online search types (API-owned DTO)
    CandidateSummary,
)

# PR10: Canonical service acquisition helper
def get_service(project_root: Optional[Path | str] = None, **kwargs) -> QMSService:
    """
    Get a QMSService instance for a project.
    
    This is the canonical way for frontends (CLI, daemon, tests) to acquire
    a QMSService instance. It handles project root detection if not provided.
    
    Args:
        project_root: Optional project root path. If None, detects from cwd.
        **kwargs: Additional arguments (reserved for future use)
        
    Returns:
        QMSService instance
        
    Raises:
        ValueError: If project root cannot be determined or is invalid
    """
    from qmatsuite.core.project_utils import find_project_root
    
    if project_root is None:
        # Detect from current working directory
        project_root = find_project_root()
        if project_root is None:
            raise ValueError(
                "No project found. Current directory does not contain a project.qms.yml. "
                "Run 'qms init' to create a project, or specify --project."
            )
    
    return QMSService(Path(project_root).resolve())


def get_step_type_gen(step_type_spec: str) -> str:
    """Convert SPEC to GEN via registry SSOT.

    Args:
        step_type_spec: Engine-prefixed type (e.g., "qe_scf")

    Returns:
        Engine-agnostic type (e.g., "scf")

    Raises:
        KeyError: If step_type_spec is not in registry
    """
    from qmatsuite.workflow.registry import normalize_step_type_to_gen
    return normalize_step_type_to_gen(step_type_spec)

# PR10: Minimal exports - only service, errors, and DTOs
# Utilities are available via qmatsuite.api.utils.*
__all__ = [
    # Service
    "QMSService",
    "get_service",
    "get_step_type_gen",
    # Errors
    "APIError",
    "NotFoundError",
    "AmbiguousError",
    "ValidationError",
    "ConflictError",
    "EngineError",
    "ConfigError",
    "FilesystemError",
    "InternalError",
    # DTOs
    "BaseDTO",
    "ErrorDTO",
    "MetaDTO",
    "CalculationDTO",
    "CalculationRefDTO",
    "StepDTO",
    "StructureDTO",
    "RunResultDTO",
    "AnalysisRefDTO",
    "AnalysisSummaryDTO",
    # Online search
    "CandidateSummary",
]

