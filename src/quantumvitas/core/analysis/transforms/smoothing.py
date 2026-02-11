"""Running average smoothing transform for series data."""
from __future__ import annotations

import numpy as np

from quantumvitas.core.analysis.bundles import DerivedPrimitiveBundle
from quantumvitas.core.analysis.primitives import Series1D
from quantumvitas.core.analysis.transforms.base import (
    PrimitiveBundle,
    PrimitiveTransform,
    clone_bundle_for_transform,
)


class Smoothing(PrimitiveTransform):
    """Running average smoothing on series y-values."""

    name = "smoothing"
    version = "1.0"

    def __init__(self, window_size: int):
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self.window_size = window_size

    def validate(self, bundle: PrimitiveBundle) -> list[str]:
        if not bundle.series:
            return ["Bundle has no series; smoothing has no effect."]
        warnings = []
        for series in bundle.series:
            if len(series.y) < self.window_size:
                warnings.append(
                    f"Series '{series.name}' has {len(series.y)} points, "
                    f"less than window_size={self.window_size}."
                )
        return warnings

    def apply(self, bundle: PrimitiveBundle) -> DerivedPrimitiveBundle:
        result = clone_bundle_for_transform(bundle)
        kernel = np.ones(self.window_size) / self.window_size

        smoothed = []
        for series in bundle.series:
            if len(series.y) >= self.window_size:
                y_smooth = np.convolve(series.y, kernel, mode="valid")
                # Trim x to match
                trim = self.window_size - 1
                x_trimmed = series.x[trim // 2 : trim // 2 + len(y_smooth)]
                smoothed.append(Series1D(
                    x=x_trimmed,
                    y=y_smooth,
                    x_label=series.x_label,
                    y_label=series.y_label,
                    x_unit=series.x_unit,
                    y_unit=series.y_unit,
                    name=series.name,
                ))
            else:
                smoothed.append(Series1D(
                    x=np.array(series.x, copy=True),
                    y=np.array(series.y, copy=True),
                    x_label=series.x_label,
                    y_label=series.y_label,
                    x_unit=series.x_unit,
                    y_unit=series.y_unit,
                    name=series.name,
                ))

        result.series = smoothed
        result.transform_chain.append(
            self.to_record({"window_size": self.window_size})
        )
        return result
