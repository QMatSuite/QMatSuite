"""
QC IR Parameters Registry.

Defines IR parameters for the QC (quantum chemistry) dialect.
Keys use shallow namespacing (one dot level): e.g., scf.conv_tol, scf.max_cycle.

IR parameters for QC precision preset:
- scf.conv_tol: SCF convergence tolerance (float)
- scf.max_cycle: Maximum SCF iterations (int)
- dft.grid_level: DFT grid level (int, optional; DFT only)
"""

from typing import Dict, Any

# QC IR Parameters Registry
# Keys are structured as "section.key" for shallow namespacing
QC_IR_PARAMETERS: Dict[str, Dict[str, Any]] = {
    "scf.conv_tol": {
        "type": float,
        "description": "SCF convergence tolerance",
        "default": None,  # No default - must be set by profile
    },
    "scf.max_cycle": {
        "type": int,
        "description": "Maximum SCF iterations",
        "default": None,  # No default - must be set by profile
    },
    "dft.grid_level": {
        "type": int,
        "description": "DFT grid level (optional, DFT only)",
        "default": None,  # Optional - may be NOT_APPLICABLE for non-DFT
    },
}

__all__ = ["QC_IR_PARAMETERS"]

