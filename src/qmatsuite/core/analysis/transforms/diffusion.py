"""Diffusion coefficient from MSD slope."""
from __future__ import annotations

import numpy as np

from qmatsuite.core.analysis.bundles import DerivedPrimitiveBundle
from qmatsuite.core.analysis.transforms.base import (
    PrimitiveBundle,
    PrimitiveTransform,
    clone_bundle_for_transform,
)


class DiffusionCoefficient(PrimitiveTransform):
    """Compute diffusion coefficient D from MSD slope.

    D = slope / 6 for 3D diffusion (Einstein relation).
    Linear fit of MSD(t) in the specified time window.
    """

    name = "diffusion_coefficient"
    version = "1.0"

    def __init__(self, fit_start: float | None = None, fit_end: float | None = None):
        self.fit_start = fit_start
        self.fit_end = fit_end

    def validate(self, bundle: PrimitiveBundle) -> list[str]:
        if "msd" not in bundle.arrays:
            return ["Bundle has no 'msd' array; run MSD transform first."]
        msd_series = [s for s in bundle.series if s.name == "MSD"]
        if not msd_series:
            return ["Bundle has no MSD series."]
        return []

    def apply(self, bundle: PrimitiveBundle) -> DerivedPrimitiveBundle:
        result = clone_bundle_for_transform(bundle)

        msd_series = [s for s in bundle.series if s.name == "MSD"]
        if not msd_series:
            result.transform_chain.append(self.to_record(self._params()))
            return result

        time = msd_series[0].x
        msd = msd_series[0].y

        # Apply fit window
        mask = np.ones(len(time), dtype=bool)
        if self.fit_start is not None:
            mask &= time >= self.fit_start
        if self.fit_end is not None:
            mask &= time <= self.fit_end

        t_fit = time[mask]
        msd_fit = msd[mask]

        if len(t_fit) < 2:
            result.arrays["diffusion_coefficient"] = np.array([0.0])
            result.transform_chain.append(self.to_record(self._params()))
            return result

        # Linear fit: MSD = slope * t + intercept
        coeffs = np.polyfit(t_fit, msd_fit, 1)
        slope = coeffs[0]

        # D = slope / 6 (3D Einstein relation)
        # MSD in A^2, time in fs → D in A^2/fs
        diffusion_coeff = slope / 6.0

        result.arrays["diffusion_coefficient"] = np.array([diffusion_coeff])
        result.arrays["msd_slope"] = np.array([slope])
        result.transform_chain.append(self.to_record(self._params()))
        return result

    def _params(self) -> dict:
        return {"fit_start": self.fit_start, "fit_end": self.fit_end}
