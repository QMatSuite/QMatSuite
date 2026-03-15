"""
QMatSuite - Quantum Materials Suite

A modern Python-based GUI and calculation engine for Quantum ESPRESSO and related codes.
"""

from __future__ import annotations

import dataclasses
import importlib
import sys
from typing import Any, Callable

__version__ = "1.2.5"
__author__ = "QMatSuite Developers"


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

# Only QMSService is imported eagerly (needed by daemon).
# All other public names are lazy-loaded on first access.
from .api import QMSService

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "Project": (".project.model", "Project"),
    "ProjectSettings": (".project.model", "ProjectSettings"),
    "StructureRef": (".project.model", "StructureRef"),
    "CalculationRef": (".project.model", "CalculationRef"),
    "Calculation": (".calculation.calculation", "Calculation"),
    "CalculationRunner": (".calculation.runner", "CalculationRunner"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path, __name__)
        value = getattr(module, attr)
        # Cache on the module so __getattr__ is not called again
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Project",
    "ProjectSettings",
    "StructureRef",
    "CalculationRef",
    "Calculation",
    "CalculationRunner",
    "QMSService",
]
