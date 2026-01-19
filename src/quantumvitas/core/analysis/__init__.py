"""
Analysis Objects Framework.

Provides engine-agnostic canonical analysis objects (Trajectory, DOS, Bands, etc.)
parsed from raw engine outputs.
"""

from quantumvitas.core.analysis.base import (
    AnalysisObjectMeta,
    SourceFileStat,
)
from quantumvitas.core.analysis.primitives import (
    Series1D,
    GeometryFrame,
    GeometryFrames,
    Marker,
)
from quantumvitas.core.analysis.policy import (
    MaterializationPolicy,
    CacheConfig,
)
from quantumvitas.core.analysis.cache import (
    CacheManager,
    is_cache_stale,
)

__all__ = [
    "AnalysisObjectMeta",
    "SourceFileStat",
    "Series1D",
    "GeometryFrame",
    "GeometryFrames",
    "Marker",
    "MaterializationPolicy",
    "CacheConfig",
    "CacheManager",
    "is_cache_stale",
]

