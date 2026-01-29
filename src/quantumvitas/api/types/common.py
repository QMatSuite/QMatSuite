"""
Common DTO types.

This module provides shared DTO types used across multiple entity DTOs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from quantumvitas.api.types.base import BaseDTO


@dataclass
class CandidateSummary(BaseDTO):
    """
    Summary of an online structure candidate.

    API-owned DTO for online structure search results.
    """
    candidate_id: str = ""
    label: str = ""
    source: str = ""  # "optimade" or "cod"
    source_id: str = ""
    nsites: int = 0
    spacegroup: Optional[str] = None
    flags: List[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class MetaDTO(BaseDTO):
    """
    Common metadata for entities.

    All entity DTOs can include this for human-readable metadata.
    """
    id: str | None = None            # ULID identifier
    slug: str | None = None          # Human-readable identifier
    name: str | None = None          # Display name
    path: str | None = None          # Relative path within project
    description: str | None = None
    tags: list[str] | None = None
    created_at: str | None = None    # ISO datetime
    updated_at: str | None = None    # ISO datetime

