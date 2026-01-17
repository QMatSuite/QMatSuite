"""
IR PW Dialect (Plane-Wave with Periodic Boundary Conditions).

This dialect represents plane-wave basis calculations with periodic boundary conditions.
In v0, this is QE-equivalent (mostly same names as QE keys).

This module re-exports from `ir.backends.qe` as a v0 alias for backward compatibility.
Future versions may introduce a dedicated PW dialect structure.
"""

# v0 alias: re-export from backends/qe
from quantumvitas.ir.backends.qe import mapping
from quantumvitas.ir.backends.qe.mapping import (
    IR_TO_QE_MAPPING,
    QE_TO_IR_MAPPING,
    ir_params_to_qe_params,
    ir_to_qe_param,
    qe_to_ir_param,
    qe_yaml_to_ir_yaml,
)

__all__ = [
    "mapping",
    "IR_TO_QE_MAPPING",
    "QE_TO_IR_MAPPING",
    "ir_params_to_qe_params",
    "ir_to_qe_param",
    "qe_to_ir_param",
    "qe_yaml_to_ir_yaml",
]

