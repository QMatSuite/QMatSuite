"""
Analysis Objects Framework.

Provides engine-agnostic canonical analysis objects (Trajectory, DOS, Bands, etc.)
parsed from raw engine outputs.
"""

from quantumvitas.core.analysis.base import (
    AnalysisObjectMeta,
    SourceFileStat,
)
from quantumvitas.core.analysis.band_structure import (
    BandStructure,
    HighSymPoint,
)
from quantumvitas.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    DerivedPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
    TransformRecord,
)
from quantumvitas.core.analysis.capability import (
    AnalysisCapability,
    CapabilityMatch,
    find_contiguous_match,
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
from quantumvitas.core.analysis.transforms import (
    EnergyCrop,
    FermiShift,
    PrimitiveTransform,
)

__all__ = [
    "AnalysisObjectMeta",
    "SourceFileStat",
    "BandStructure",
    "HighSymPoint",
    "RenderMeta",
    "ProvenanceMeta",
    "TransformRecord",
    "CanonicalPrimitiveBundle",
    "DerivedPrimitiveBundle",
    "AnalysisCapability",
    "CapabilityMatch",
    "find_contiguous_match",
    "Series1D",
    "GeometryFrame",
    "GeometryFrames",
    "Marker",
    "MaterializationPolicy",
    "CacheConfig",
    "PrimitiveTransform",
    "FermiShift",
    "EnergyCrop",
]
