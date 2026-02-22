"""Frame slicing transform for trajectory bundles."""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from qmatsuite.core.analysis.bundles import DerivedPrimitiveBundle
from qmatsuite.core.analysis.primitives import GeometryFrames, Series1D
from qmatsuite.core.analysis.transforms.base import (
    PrimitiveBundle,
    PrimitiveTransform,
    clone_bundle_for_transform,
)


class FrameSlice(PrimitiveTransform):
    """Subset trajectory frames by index slice."""

    name = "frame_slice"
    version = "1.0"

    def __init__(self, start: int | None = None, stop: int | None = None, step: int | None = None):
        self.start = start
        self.stop = stop
        self.step = step

    def validate(self, bundle: PrimitiveBundle) -> list[str]:
        if bundle.geometry_frames is None:
            return ["Bundle has no geometry_frames; frame slicing has no effect."]
        return []

    def apply(self, bundle: PrimitiveBundle) -> DerivedPrimitiveBundle:
        result = clone_bundle_for_transform(bundle)
        s = slice(self.start, self.stop, self.step)

        if result.geometry_frames is not None:
            gf = result.geometry_frames
            result.geometry_frames = GeometryFrames(
                frames=gf.frames[s],
                time=gf.time[s] if gf.time is not None else None,
                iteration=gf.iteration[s] if gf.iteration is not None else None,
                image_indices=gf.image_indices[s] if gf.image_indices is not None else None,
            )

            # Trim series to match frame count
            n_frames = len(result.geometry_frames.frames)
            trimmed = []
            for series in result.series:
                if len(series.x) == len(bundle.geometry_frames.frames):
                    trimmed.append(Series1D(
                        x=series.x[s],
                        y=series.y[s],
                        x_label=series.x_label,
                        y_label=series.y_label,
                        x_unit=series.x_unit,
                        y_unit=series.y_unit,
                        name=series.name,
                    ))
                else:
                    trimmed.append(series)
            result.series = trimmed

        result.transform_chain.append(
            self.to_record({"start": self.start, "stop": self.stop, "step": self.step})
        )
        return result
