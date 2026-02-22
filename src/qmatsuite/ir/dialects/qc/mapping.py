"""
QC IR to Engine Mapping.

Maps IR keys (ir.qc dialect) to engine-specific parameter keys.
This module provides mappings for PySCF and ORCA engines.

IR keys use shallow namespacing: scf.conv_tol, scf.max_cycle, dft.grid_level
"""

from typing import Dict, Tuple, Any

# QC IR to PySCF mapping
# Maps IR key (section.key) -> (PySCF parameter path, value converter)
QC_IR_TO_PYSCF_MAPPING: Dict[str, Tuple[str, Any]] = {
    "scf.conv_tol": ("scf.conv_tol", lambda v: v),  # Direct mapping
    "scf.max_cycle": ("scf.max_cycle", lambda v: v),  # Direct mapping
    "dft.grid_level": ("dft.grid_level", lambda v: v),  # Direct mapping
}

# QC IR to ORCA mapping
# Maps IR key (section.key) -> (ORCA parameter path, value converter)
QC_IR_TO_ORCA_MAPPING: Dict[str, Tuple[str, Any]] = {
    "scf.conv_tol": ("scf.conv_tol", lambda v: v),  # Direct mapping
    "scf.max_cycle": ("scf.max_cycle", lambda v: v),  # Direct mapping
    "dft.grid_level": ("dft.grid_level", lambda v: v),  # Direct mapping
}

__all__ = ["QC_IR_TO_PYSCF_MAPPING", "QC_IR_TO_ORCA_MAPPING"]

