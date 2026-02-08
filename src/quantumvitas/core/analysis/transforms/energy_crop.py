"""Energy window crop transform."""
from __future__ import annotations

import numpy as np

from quantumvitas.core.analysis.bundles import DerivedPrimitiveBundle
from quantumvitas.core.analysis.primitives import Series1D
from quantumvitas.core.analysis.transforms.base import (
    PrimitiveBundle,
    PrimitiveTransform,
    clone_bundle_for_transform,
)


def _looks_like_energy_axis(label: str, unit: str) -> bool:
    label_l = label.strip().lower()
    unit_l = unit.strip().lower().replace(" ", "")
    if "energy" in label_l:
        return True
    return unit_l in {"ev", "hartree", "ry"}


def _series_energy_axis(series: Series1D) -> str:
    if _looks_like_energy_axis(series.x_label, series.x_unit):
        return "x"
    if _looks_like_energy_axis(series.y_label, series.y_unit):
        return "y"
    # Bands use energy on y by convention.
    return "y"


class EnergyCrop(PrimitiveTransform):
    """Trim series data to an energy window."""

    name = "energy_crop"
    version = "1.0"

    def __init__(self, emin: float, emax: float):
        self.emin = float(emin)
        self.emax = float(emax)
        if self.emin > self.emax:
            raise ValueError("emin must be <= emax")

    def validate(self, bundle: PrimitiveBundle) -> list[str]:
        if not bundle.series:
            return ["Bundle has no series; energy crop has no effect."]
        return []

    def apply(self, bundle: PrimitiveBundle) -> DerivedPrimitiveBundle:
        result = clone_bundle_for_transform(bundle)

        cropped_series = []
        for series in bundle.series:
            axis = _series_energy_axis(series)
            x_values = np.array(series.x, copy=True)
            y_values = np.array(series.y, copy=True)

            energy_values = x_values if axis == "x" else y_values
            mask = (energy_values >= self.emin) & (energy_values <= self.emax)

            cropped_series.append(
                Series1D(
                    x=x_values[mask],
                    y=y_values[mask],
                    x_label=series.x_label,
                    y_label=series.y_label,
                    x_unit=series.x_unit,
                    y_unit=series.y_unit,
                    name=series.name,
                )
            )

        result.series = cropped_series
        result.transform_chain.append(
            self.to_record({"emin": self.emin, "emax": self.emax})
        )
        return result

