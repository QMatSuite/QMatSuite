"""
Kernel to API mapping utilities.

This module provides mapping functions to convert kernel objects to DTOs
and kernel exceptions to API errors.
"""

# PR5: Calculation mappings added
from qmatsuite.api._mapping.dto_mapping import (
    kernel_to_dto,
    analysis_summary_to_dto,
    analysis_ref_to_dto,
    structure_to_dto,
    calculation_to_dto,
    step_to_dto,
)  # noqa: F401
from qmatsuite.api._mapping.exc_mapping import map_kernel_exception  # noqa: F401

__all__ = [
    "kernel_to_dto",
    "map_kernel_exception",
    "analysis_summary_to_dto",
    "analysis_ref_to_dto",
    "structure_to_dto",
    "calculation_to_dto",
    "step_to_dto",
]

