"""
QuantumVITAS API - Stable public interface.

This module provides the public API for QuantumVITAS operations.
All frontends (CLI, daemon, Jupyter) should import from this module only.

PR0: Stub structure - maintains compatibility with existing _api_legacy.py
PR10: Migrating to new QVService from api.service
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# Import from existing _api_legacy.py for compatibility (PR0-PR9)
# This will be removed in PR10 after migration
import importlib.util

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

# PR10: Utility functions (pure functions, no service instance needed)
from quantumvitas.api.utils import (  # noqa: F401
    slugify,
    meta_from_name,
    ensure_relative_path,
    read_structure,
    write_structure,
    generate_unique_name_and_slug,
    list_calculation_templates,
    copy_calculation_template,
    copy_structure_template,
    extract_calculation_selector_from_entry,
    extract_structure_selector_from_entry,
)

# PR10: Canonical service acquisition helper
def get_service(project_root: Optional[Path | str] = None, **kwargs) -> "QVService":
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
    from quantumvitas.api.service import QVService as NewQVService
    from quantumvitas.core.project_utils import find_project_root
    
    if project_root is None:
        # Detect from current working directory
        project_root = find_project_root()
        if project_root is None:
            raise ValueError(
                "No project found. Current directory does not contain a project.qv.yml. "
                "Run 'qv init' to create a project, or specify --project."
            )
    
    return NewQVService(Path(project_root).resolve())

# Export new structure + legacy exports
# Note: __all__ from _api_legacy is also included via * import above
# QVService is already exported from _api_legacy
__all__ = [
    # Service (from _api_legacy for now)
    # "QVService",  # Already in _api_legacy.__all__
    "get_service",  # PR10: Canonical service acquisition helper
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
    # DTOs (PR2: Core DTOs complete)
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
    # Utilities (PR10: Pure functions for frontends)
    "slugify",
    "meta_from_name",
    "ensure_relative_path",
    "read_structure",
    "write_structure",
    "generate_resource_id",
    "generate_unique_name_and_slug",
    "list_calculation_templates",
    "copy_calculation_template",
    "copy_structure_template",
    "extract_calculation_selector_from_entry",
    "extract_structure_selector_from_entry",
    # Legacy exports (from _api_legacy) - will be removed in PR3-PR10
]

