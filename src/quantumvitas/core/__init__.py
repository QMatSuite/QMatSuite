"""Core modules for QuantumVITAS.

This package contains:
- engines: QE engine implementations
- resolution: Centralized selector → resource resolution
- context: PWD context helpers for CLI
- resources: ResourceMeta and related utilities
- models: Dataclass models with load/save for all resources
- project_utils: Project configuration helpers
- templates: Template copying utilities
- paths: Path utilities for .qmatsuite/ and .tmp/
- settings: Global settings management
"""

from . import engines
from . import resolution
from . import context
from . import resources
from . import models
from . import project_utils
from . import templates
from . import paths
from . import settings

__all__ = [
    "engines",
    "resolution",
    "context",
    "resources",
    "models",
    "project_utils",
    "templates",
    "paths",
    "settings",
]

