"""
Analysis DTOs.

This module provides DTOs for analysis results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quantumvitas.api.types.base import BaseDTO


@dataclass
class AnalysisRefDTO(BaseDTO):
    """
    Reference to large analysis data (NOT embedded).
    
    Use this for large arrays/data that should be loaded on-demand.
    """
    # Identity
    calc_ulid: str
    step_ulid: str
    property_name: str        # "band_structure", "dos", "trajectory"

    # Artifact reference
    artifact_path: str
    artifact_format: str      # "hdf5", "npz", "json"
    artifact_sha256: str
    artifact_size_bytes: int

    # Summary (always present, small)
    summary: dict[str, Any]   # Property-specific scalars

    # Preview (optional, small)
    preview: dict[str, Any] | None = None


@dataclass
class AnalysisSummaryDTO(BaseDTO):
    """
    Quick analysis overview (no large data).
    """
    # Identity
    calc_ulid: str
    step_ulid: str

    # Status
    converged: bool | None = None

    # Key results (scalars only)
    total_energy_ev: float | None = None
    fermi_energy_ev: float | None = None
    band_gap_ev: float | None = None
    band_gap_type: str | None = None  # "direct", "indirect", "metal"
    total_magnetization: float | None = None

    # Available for detailed fetch
    available_properties: list[str] | None = None

