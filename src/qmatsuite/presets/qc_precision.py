"""
QC Precision ParamSpace Definition.

Defines the ParamSpace for QC (quantum chemistry) precision dimension.
Uses ir.qc dialect keys with PySCF-like names.

Keys:
- scf.conv_tol (float): SCF convergence tolerance
- scf.max_cycle (int): Maximum SCF iterations
- dft.grid_level (int, optional): DFT grid level (DFT only)
- engine.orca.scf.macro (string): ORCA engine-specific macro (e.g., "tightscf")

Profiles:
- LOW: Quick screening, relaxed convergence
- MED: Production quality, balanced accuracy/cost
- HIGH: High accuracy for forces, fine energy differences

Note: Uses Python native types (True/False for bools, not .true./.false. strings).
"""

from typing import Optional

from qmatsuite.presets.paramspace import (
    ParamSpace,
    ParamKey,
    Cell,
    parse_float,
    parse_int,
    canonicalize_float,
    canonicalize_int,
    canonicalize_string,
)


def build_qc_precision_paramspace() -> ParamSpace:
    """
    Build the ParamSpace for QC precision dimension.
    
    Keys use ir.qc dialect with shallow namespacing:
    - scf.conv_tol: SCF convergence tolerance (float)
    - scf.max_cycle: Maximum SCF iterations (int)
    - dft.grid_level: DFT grid level (int, optional; DFT only)
    - engine.orca.scf.macro: ORCA engine-specific macro (string, lower-case canonical)
    
    Profiles:
    - LOW: conv_tol=1e-6, max_cycle=50, grid_level=2 (if DFT), macro="normal"
    - MED: conv_tol=1e-8, max_cycle=100, grid_level=3 (if DFT), macro="normal"
    - HIGH: conv_tol=1e-10, max_cycle=200, grid_level=4 (if DFT), macro="tightscf"
    
    Note: dft.grid_level is optional and may be NOT_APPLICABLE for non-DFT calculations.
    """
    # IR keys (ir.qc dialect)
    key_scf_conv_tol = ParamKey(
        section="scf",
        key="conv_tol",
        parser=parse_float,
        canonicalizer=canonicalize_float,
        tolerance=1e-12,  # Absolute tolerance for float comparison
        default=None,  # No default - must be set by profile
    )
    
    key_scf_max_cycle = ParamKey(
        section="scf",
        key="max_cycle",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,  # No default - must be set by profile
    )
    
    key_dft_grid_level = ParamKey(
        section="dft",
        key="grid_level",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,  # Optional - may be NOT_APPLICABLE
    )
    
    # Engine-specific key (ORCA macro)
    key_orca_macro = ParamKey(
        section="engine.orca.scf",
        key="macro",
        parser=canonicalize_string,  # Parse and canonicalize in one step
        canonicalizer=canonicalize_string,
        default=None,  # No default - must be set by profile
    )
    
    keys = [key_scf_conv_tol, key_scf_max_cycle, key_dft_grid_level, key_orca_macro]
    
    profiles = {
        "LOW": {
            key_scf_conv_tol: Cell.VALUE(1e-6),
            key_scf_max_cycle: Cell.VALUE(50),
            key_dft_grid_level: Cell.VALUE(2),  # Present for DFT, may be NOT_APPLICABLE for non-DFT
            key_orca_macro: Cell.VALUE("normal"),
        },
        "MED": {
            key_scf_conv_tol: Cell.VALUE(1e-8),
            key_scf_max_cycle: Cell.VALUE(100),
            key_dft_grid_level: Cell.VALUE(3),  # Present for DFT, may be NOT_APPLICABLE for non-DFT
            key_orca_macro: Cell.VALUE("normal"),
        },
        "HIGH": {
            key_scf_conv_tol: Cell.VALUE(1e-10),
            key_scf_max_cycle: Cell.VALUE(200),
            key_dft_grid_level: Cell.VALUE(4),  # Present for DFT, may be NOT_APPLICABLE for non-DFT
            key_orca_macro: Cell.VALUE("tightscf"),
        },
    }
    
    return ParamSpace(
        name="qc_precision",
        keys=keys,
        profiles=profiles,
    )


# Module-level instance (cached)
_QC_PRECISION_PARAMSPACE: Optional[ParamSpace] = None


def get_qc_precision_paramspace() -> ParamSpace:
    """Get the QC Precision ParamSpace (singleton)."""
    global _QC_PRECISION_PARAMSPACE
    if _QC_PRECISION_PARAMSPACE is None:
        _QC_PRECISION_PARAMSPACE = build_qc_precision_paramspace()
    return _QC_PRECISION_PARAMSPACE

