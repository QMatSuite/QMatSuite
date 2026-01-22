"""
QuantumVITAS - Quantum Visualization Interactive Toolkit for Ab-initio Simulations

A modern Python-based GUI and calculation engine for Quantum ESPRESSO and related codes.
"""

from __future__ import annotations

import dataclasses
import sys
from typing import Any, Callable

__version__ = "1.0.1"
__author__ = "Haonan Huang"


def _make_dataclass_compat() -> None:
    """
    Python 3.9 does not support ``@dataclass(slots=True)``. The codebase prefers
    slotted dataclasses for memory/perf improvements, so we gracefully drop the
    ``slots`` argument when running on older interpreters instead of crashing.
    """

    if sys.version_info >= (3, 10):
        return

    original_dataclass = dataclasses.dataclass

    def compat_dataclass(
        *args: Any,
        **kwargs: Any,
    ) -> Callable[[type], type]:
        if "slots" in kwargs:
            kwargs = dict(kwargs)
            kwargs.pop("slots", None)
        return original_dataclass(*args, **kwargs)

    dataclasses.dataclass = compat_dataclass  # type: ignore[assignment]


_make_dataclass_compat()

# Public API exports
from .project.model import Project, ProjectSettings, StructureRef, CalculationRef
from .calculation.calculation import Calculation
from .calculation.runner import CalculationRunner
from .api import QVService

__all__ = [
    "Project",
    "ProjectSettings",
    "StructureRef",
    "CalculationRef",
    "Calculation",
    "CalculationRunner",
    "QVService",
]

