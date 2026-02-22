"""Base contract for primitive transforms."""
from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Union

import numpy as np

from qmatsuite.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    DerivedPrimitiveBundle,
    TransformRecord,
)
from qmatsuite.core.analysis.primitives import Series1D

PrimitiveBundle = Union[CanonicalPrimitiveBundle, DerivedPrimitiveBundle]


def clone_bundle_for_transform(bundle: PrimitiveBundle) -> DerivedPrimitiveBundle:
    """Create a detached derived bundle copy used as transform output."""
    transform_chain = []
    if isinstance(bundle, DerivedPrimitiveBundle):
        transform_chain = [
            TransformRecord(
                transform_name=record.transform_name,
                parameters=deepcopy(record.parameters),
            )
            for record in bundle.transform_chain
        ]

    return DerivedPrimitiveBundle(
        object_type=bundle.object_type,
        render_meta=deepcopy(bundle.render_meta),
        provenance_meta=deepcopy(bundle.provenance_meta),
        series=[
            Series1D(
                x=np.array(series.x, copy=True),
                y=np.array(series.y, copy=True),
                x_label=series.x_label,
                y_label=series.y_label,
                x_unit=series.x_unit,
                y_unit=series.y_unit,
                name=series.name,
            )
            for series in bundle.series
        ],
        geometry_frames=deepcopy(bundle.geometry_frames),
        arrays=deepcopy(bundle.arrays),
        transform_chain=transform_chain,
    )


class PrimitiveTransform(ABC):
    """Abstract transform from canonical/derived primitive bundles to derived."""

    name: str = ""
    version: str = "1.0"

    @abstractmethod
    def apply(self, bundle: PrimitiveBundle) -> DerivedPrimitiveBundle:
        """Transform a bundle. MUST return a DerivedPrimitiveBundle."""

    def validate(self, bundle: PrimitiveBundle) -> list[str]:
        """Pre-checks. Returns list of warnings (empty = valid)."""
        return []

    def to_record(self, parameters: dict[str, Any]) -> TransformRecord:
        return TransformRecord(transform_name=self.name, parameters=parameters)

