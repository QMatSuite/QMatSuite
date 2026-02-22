"""
High-level project abstractions.

The project layer manages structures, calculations, and shared resources on disk.
"""

from .model import Project, ProjectSettings, StructureRef, CalculationRef
from .storage import ProjectStorage

__all__ = [
    "Project",
    "ProjectSettings",
    "StructureRef",
    "CalculationRef",
    "ProjectStorage",
]

