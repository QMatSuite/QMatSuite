"""QE IR backend: IR ↔ QE parameter mapping."""

from quantumvitas.drivers.qe.ir.mapping import (
    IR_TO_QE_MAPPING,
    QE_TO_IR_MAPPING,
    CLASS_A_TYPES,
    IR_UNIT_TO_QE_UNIT,
    ir_to_qe_param,
    qe_to_ir_param,
    ir_patch_to_qe_patch,
    ir_params_to_qe_params,
    qe_yaml_to_ir_yaml,
    validate_ir_qe_mapping,
    is_class_a_key,
    get_class_a_type,
)

# Re-export mapping module for backward compatibility
from quantumvitas.drivers.qe.ir import mapping

__all__ = [
    "IR_TO_QE_MAPPING",
    "QE_TO_IR_MAPPING",
    "CLASS_A_TYPES",
    "IR_UNIT_TO_QE_UNIT",
    "ir_to_qe_param",
    "qe_to_ir_param",
    "ir_patch_to_qe_patch",
    "ir_params_to_qe_params",
    "qe_yaml_to_ir_yaml",
    "validate_ir_qe_mapping",
    "is_class_a_key",
    "get_class_a_type",
    "mapping",
]
