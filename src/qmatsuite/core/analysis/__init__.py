"""
Analysis Objects Framework.

Provides engine-agnostic canonical analysis objects (Trajectory, DOS, Bands, etc.)
parsed from raw engine outputs.
"""

from qmatsuite.core.analysis.base import (
    AnalysisObjectMeta,
    SourceFileStat,
)
from qmatsuite.core.analysis.band_structure import (
    BandStructure,
    HighSymPoint,
)
from qmatsuite.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    DerivedPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
    TransformRecord,
)
from qmatsuite.core.analysis.capability import (
    AnalysisCapability,
    CapabilityMatch,
    find_contiguous_match,
)
from qmatsuite.core.analysis.primitives import (
    Series1D,
    GeometryFrame,
    GeometryFrames,
    Marker,
)
from qmatsuite.core.analysis.policy import (
    MaterializationPolicy,
    CacheConfig,
)
from qmatsuite.core.analysis.transforms import (
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
