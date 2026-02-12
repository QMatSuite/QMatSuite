"""
Online structure search DTOs.

This module provides DTOs for online structure search operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from quantumvitas.api.types.base import BaseDTO


@dataclass
class SourceConfigDTO(BaseDTO):
    """Source configuration (provider enable/disable, ordering)."""
    optimade_provider_ids: Optional[List[str]] = None  # If None, use settings defaults
    pubchem_enabled: Optional[bool] = None  # If None, use settings default
    materials_project_enabled: Optional[bool] = None  # If None, use settings default


@dataclass
class CandidateDTO(BaseDTO):
    """Online structure candidate (search result)."""
    candidate_id: str
    label: str  # Display label (e.g., "Si (2 sites)")
    source: str  # Provider ID (e.g., "mp", "cod", "pubchem")
    source_id: str  # Provider-specific ID
    structure_type: Literal["crystal", "molecule"]
    formula: str
    nsites: int
    spacegroup: Optional[str] = None  # For crystals
    providers: List[str] = field(default_factory=list)  # Aggregated: ["mp", "cod", "oqmd"]
    score: float = 0.0
    flags: List[str] = field(default_factory=list)  # e.g., ["experimental", "partial_occ"]
    metadata: Dict[str, Any] = field(default_factory=dict)  # Provider-specific metadata


@dataclass
class SearchResultDTO(BaseDTO):
    """Search results."""
    session_id: str
    candidates: List[CandidateDTO]
    providers_queried: List[str]  # Provider IDs that were queried
    partial: bool  # True if some providers timed out
    query: str
    mode: str


@dataclass
class StructureRefDTO(BaseDTO):
    """Reference to an online structure (for 2-step fetch)."""
    session_id: Optional[str] = None
    candidate_id: Optional[str] = None
    direct_ref: Optional[Dict[str, Any]] = None  # Provider-specific ref


@dataclass
class StructureDocDTO(BaseDTO):
    """Full structure document (crystal or molecule)."""
    structure_type: Literal["crystal", "molecule"]
    formula: str
    atoms: List[Dict[str, Any]]  # [{"element": "Si", "coords": [x, y, z], ...}]
    provenance: Dict[str, Any] = field(default_factory=dict)  # Provider metadata
    lattice: Optional[List[List[float]]] = None  # 3x3 matrix for crystals, None for molecules
    pbc: Optional[List[bool]] = None  # [True, True, True] for crystals, [False, False, False] for molecules


@dataclass
class ProviderInfoDTO(BaseDTO):
    """Provider information."""
    id: str  # Provider ID (e.g., "mp", "cod", "pubchem")
    name: str  # Display name
    enabled: bool
    base_url: Optional[str] = None  # OPTIMADE base URL (if applicable)
    structure_count: Optional[int] = None
    requires_api_key: bool = False


@dataclass
class ProviderListDTO(BaseDTO):
    """List of available providers."""
    optimade_providers: List[ProviderInfoDTO]
    pubchem_enabled: bool
    materials_project_enabled: bool
    materials_project_has_key: bool  # True if API key is configured


@dataclass
class ProviderPatchDTO(BaseDTO):
    """Patch for a single provider."""
    id: str
    enabled: bool


@dataclass
class MaterialsProjectPatchDTO(BaseDTO):
    """Patch for Materials Project settings."""
    enabled: Optional[bool] = None
    api_key: Optional[str] = None


@dataclass
class OnlineSourcesPatchDTO(BaseDTO):
    """Patch for online structure sources settings."""
    optimade_providers: Optional[List[ProviderPatchDTO]] = None
    pubchem_enabled: Optional[bool] = None
    materials_project: Optional[MaterialsProjectPatchDTO] = None
    timeout_seconds: Optional[float] = None
    max_results_per_provider: Optional[int] = None
    max_total_results: Optional[int] = None


@dataclass
class MaterialsProjectConfigDTO(BaseDTO):
    """Materials Project configuration."""
    enabled: bool
    has_key: bool  # True if API key is configured (key value not returned for security)


@dataclass
class OnlineSourcesSettingsDTO(BaseDTO):
    """Current online structure sources settings (returned after patch)."""
    optimade_providers: List[ProviderInfoDTO]
    pubchem_enabled: bool
    materials_project: MaterialsProjectConfigDTO
    timeout_seconds: float
    max_results_per_provider: int
    max_total_results: int

