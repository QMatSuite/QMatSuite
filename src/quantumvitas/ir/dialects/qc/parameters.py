"""
QC IR Parameters Registry.

Defines IR parameters for the QC (quantum chemistry) dialect.
Keys use shallow namespacing (one dot level): e.g., scf.conv_tol, scf.max_cycle.

This registry is initially empty; will be populated in PR2 with QC precision preset keys.
"""

from typing import Dict, Any

# QC IR Parameters Registry (initially empty)
# Will be populated in PR2 with: scf.conv_tol, scf.max_cycle, dft.grid_level
QC_IR_PARAMETERS: Dict[str, Dict[str, Any]] = {}

__all__ = ["QC_IR_PARAMETERS"]

