"""Fermi-level shift transform."""
from __future__ import annotations

from typing import Any

import numpy as np

from qmatsuite.core.analysis.bundles import DerivedPrimitiveBundle
from qmatsuite.core.analysis.primitives import Series1D
from qmatsuite.core.analysis.transforms.base import (
    PrimitiveBundle,
    PrimitiveTransform,
    clone_bundle_for_transform,
)


def _is_energy_key(key: str) -> bool:
    key_l = key.lower()
    return "energy" in key_l or "eigenvalue" in key_l


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, np.integer, np.floating))


def _shift_energy_like(value: Any, shift: float, *, key: str = "") -> Any:
    is_energy_context = _is_energy_key(key)

    if isinstance(value, dict):
        return {
            child_key: _shift_energy_like(child_value, shift, key=child_key)
            for child_key, child_value in value.items()
        }

    if isinstance(value, np.ndarray):
        if is_energy_context:
            return np.array(value, copy=True) - shift
        return np.array(value, copy=True)

    if isinstance(value, list):
        if is_energy_context and all(_is_number(item) for item in value):
            return [float(item) - shift for item in value]
        return [_shift_energy_like(item, shift) for item in value]

    if isinstance(value, tuple):
        if is_energy_context and all(_is_number(item) for item in value):
            return [float(item) - shift for item in value]
        return [_shift_energy_like(item, shift) for item in value]

    if is_energy_context and _is_number(value):
        return float(value) - shift

    return value


class FermiShift(PrimitiveTransform):
    """Shift energy values by the bundle reference energy."""

    name = "fermi_shift"
    version = "1.0"

    def validate(self, bundle: PrimitiveBundle) -> list[str]:
        if bundle.render_meta.reference_energy is None:
            return ["No reference_energy in RenderMeta; applying zero shift."]
        return []

    def apply(self, bundle: PrimitiveBundle) -> DerivedPrimitiveBundle:
        result = clone_bundle_for_transform(bundle)
        shift = float(bundle.render_meta.reference_energy or 0.0)

        result.series = [
            Series1D(
                x=np.array(series.x, copy=True),
                y=np.array(series.y, copy=True) - shift,
                x_label=series.x_label,
                y_label=series.y_label,
                x_unit=series.x_unit,
                y_unit=series.y_unit,
                name=series.name,
            )
            for series in bundle.series
        ]

        result.arrays = {
            key: _shift_energy_like(value, shift, key=key)
            for key, value in bundle.arrays.items()
        }
        result.render_meta.reference_energy = 0.0
        result.transform_chain.append(self.to_record({}))
        return result

