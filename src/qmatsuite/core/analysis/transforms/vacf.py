"""Velocity Autocorrelation Function (VACF) transform for trajectory bundles."""
from __future__ import annotations

import numpy as np

from qmatsuite.core.analysis.bundles import DerivedPrimitiveBundle
from qmatsuite.core.analysis.primitives import Series1D
from qmatsuite.core.analysis.transforms.base import (
    PrimitiveBundle,
    PrimitiveTransform,
    clone_bundle_for_transform,
)


class VACF(PrimitiveTransform):
    """Compute velocity autocorrelation function from trajectory frames.

    C(t) = <v(0) . v(t)> / <v(0) . v(0)>
    averaged over all atoms.
    """

    name = "vacf"
    version = "1.0"

    def validate(self, bundle: PrimitiveBundle) -> list[str]:
        if bundle.geometry_frames is None:
            return ["Bundle has no geometry_frames; VACF cannot be computed."]
        warnings = []
        has_vel = any(
            f.velocities is not None for f in bundle.geometry_frames.frames
        )
        if not has_vel:
            warnings.append("No velocity data in frames; VACF cannot be computed.")
        return warnings

    def apply(self, bundle: PrimitiveBundle) -> DerivedPrimitiveBundle:
        result = clone_bundle_for_transform(bundle)

        if bundle.geometry_frames is None:
            result.transform_chain.append(self.to_record({}))
            return result

        gf = bundle.geometry_frames
        n_frames = len(gf.frames)

        # Check velocity data
        velocities = []
        for frame in gf.frames:
            if frame.velocities is not None:
                velocities.append(frame.velocities)
            else:
                result.transform_chain.append(self.to_record({}))
                return result

        # velocities[t] has shape (N, 3)
        v0 = velocities[0]  # reference velocities
        v0_dot_v0 = np.mean(np.sum(v0 * v0, axis=1))

        vacf_values = np.zeros(n_frames, dtype=float)
        for t in range(n_frames):
            vt = velocities[t]
            vacf_values[t] = np.mean(np.sum(v0 * vt, axis=1))

        # Normalize
        if v0_dot_v0 > 0:
            vacf_values /= v0_dot_v0

        # Time axis
        if gf.time is not None:
            time_axis = np.array(gf.time, copy=True) - gf.time[0]
        else:
            time_axis = np.arange(n_frames, dtype=float)

        vacf_series = Series1D(
            x=time_axis,
            y=vacf_values,
            x_label="Lag Time",
            y_label="VACF",
            x_unit="fs",
            y_unit="",
            name="VACF",
        )

        result.series = [vacf_series]
        result.arrays["vacf"] = vacf_values
        result.transform_chain.append(self.to_record({}))
        return result
