"""VASP reference step resolution.

This module handles finding reference steps for continuation.
For now, it delegates to the existing reference_resolver module.
"""

from qmatsuite.execution.reference_resolver import find_reference_scf

__all__ = ["find_reference_scf"]

