"""
High-level project abstractions.

The project layer manages structures, workflows, and shared resources on disk.
"""

from .model import Project, ProjectSettings, StructureRef, WorkflowRef
from .storage import ProjectStorage

__all__ = [
    "Project",
    "ProjectSettings",
    "StructureRef",
    "WorkflowRef",
    "ProjectStorage",
]

