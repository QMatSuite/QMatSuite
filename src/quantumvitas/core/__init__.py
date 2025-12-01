"""Core modules for QuantumVITAS.

This package contains:
- engines: QE engine implementations
- resolution: Centralized selector → resource resolution
- context: PWD context helpers for CLI
- resources: ResourceMeta and related utilities
- project_utils: Project configuration helpers
- templates: Template copying utilities
"""

from . import engines
from . import resolution
from . import context
from . import resources
from . import project_utils
from . import templates

__all__ = [
    "engines",
    "resolution",
    "context",
    "resources",
    "project_utils",
    "templates",
]

