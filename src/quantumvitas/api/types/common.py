"""
Common DTO types.

This module provides shared DTO types used across multiple entity DTOs.
"""

from __future__ import annotations

from dataclasses import dataclass

from quantumvitas.api.types.base import BaseDTO


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

