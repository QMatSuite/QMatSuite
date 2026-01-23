"""
Kernel to API mapping utilities.

This module provides mapping functions to convert kernel objects to DTOs
and kernel exceptions to API errors.
"""

# Stub exports for PR0 - will be implemented in PR1/PR2
from quantumvitas.api._mapping.dto_mapping import kernel_to_dto  # noqa: F401
from quantumvitas.api._mapping.exc_mapping import map_kernel_exception  # noqa: F401

__all__ = [
    "kernel_to_dto",
    "map_kernel_exception",
]

