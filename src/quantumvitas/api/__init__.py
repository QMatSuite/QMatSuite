"""
QuantumVITAS API - Stable public interface.

This module provides the public API for QuantumVITAS operations.
All frontends (CLI, daemon, Jupyter) should import from this module only.

PR10: Final API surface - no _api_legacy, minimal exports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# PR10: Import QVService from api.service (no _api_legacy)
from quantumvitas.api.service import QVService  # noqa: F401

# PR10: Error infrastructure (PR1: Complete)
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

# PR10: Core DTOs (PR2: Complete)
from quantumvitas.api.types import (  # noqa: F401
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
)

# PR10: Canonical service acquisition helper
def get_service(project_root: Optional[Path | str] = None, **kwargs) -> QVService:
    """
    Get a QVService instance for a project.
    
    This is the canonical way for frontends (CLI, daemon, tests) to acquire
    a QVService instance. It handles project root detection if not provided.
    
    Args:
        project_root: Optional project root path. If None, detects from cwd.
        **kwargs: Additional arguments (reserved for future use)
        
    Returns:
        QVService instance
        
    Raises:
        ValueError: If project root cannot be determined or is invalid
    """
    from quantumvitas.core.project_utils import find_project_root
    
    if project_root is None:
        # Detect from current working directory
        project_root = find_project_root()
        if project_root is None:
            raise ValueError(
                "No project found. Current directory does not contain a project.qv.yml. "
                "Run 'qv init' to create a project, or specify --project."
            )
    
    return QVService(Path(project_root).resolve())

# PR10: Minimal exports - only service, errors, and DTOs
# Utilities are available via quantumvitas.api.utils.*
__all__ = [
    # Service
    "QVService",
    "get_service",
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
]

