"""Mean Square Displacement (MSD) transform for trajectory bundles."""
from __future__ import annotations

import numpy as np

from qmatsuite.core.analysis.bundles import DerivedPrimitiveBundle
from qmatsuite.core.analysis.primitives import Series1D
from qmatsuite.core.analysis.transforms.base import (
    PrimitiveBundle,
    PrimitiveTransform,
    clone_bundle_for_transform,
)


class MSD(PrimitiveTransform):
    """Compute mean square displacement vs time from trajectory frames.

    MSD(t) = <|r(t) - r(0)|^2> averaged over all atoms.
    """

    name = "msd"
    version = "1.0"

    def validate(self, bundle: PrimitiveBundle) -> list[str]:
        if bundle.geometry_frames is None:
            return ["Bundle has no geometry_frames; MSD cannot be computed."]
        if len(bundle.geometry_frames.frames) < 2:
            return ["Need at least 2 frames for MSD."]
        return []

    def apply(self, bundle: PrimitiveBundle) -> DerivedPrimitiveBundle:
        result = clone_bundle_for_transform(bundle)

        if bundle.geometry_frames is None or len(bundle.geometry_frames.frames) < 2:
            result.transform_chain.append(self.to_record({}))
            return result

        gf = bundle.geometry_frames
        ref_pos = gf.frames[0].positions  # (N, 3) reference positions
        n_frames = len(gf.frames)

        msd_values = np.zeros(n_frames, dtype=float)
        for i, frame in enumerate(gf.frames):
            displacement = frame.positions - ref_pos  # (N, 3)
            sq_disp = np.sum(displacement**2, axis=1)  # (N,)
            msd_values[i] = np.mean(sq_disp)

        # Time axis
        if gf.time is not None:
            time_axis = np.array(gf.time, copy=True)
        else:
            time_axis = np.arange(n_frames, dtype=float)

        msd_series = Series1D(
            x=time_axis,
            y=msd_values,
            x_label="Time",
            y_label="MSD",
            x_unit="fs",
            y_unit="A^2",
            name="MSD",
        )

        result.series = [msd_series]
        result.arrays["msd"] = msd_values
        result.transform_chain.append(self.to_record({}))
        return result
