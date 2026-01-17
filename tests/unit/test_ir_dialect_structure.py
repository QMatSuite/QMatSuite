"""
Tests for IR dialect directory structure.

Verifies that dialect modules can be imported and basic structure exists.
"""

import pytest


def test_dialects_module_imports():
    """Test that dialects module can be imported."""
    from quantumvitas.ir import dialects
    
    assert dialects is not None
    assert hasattr(dialects, "pw")
    assert hasattr(dialects, "qc")


def test_pw_dialect_imports():
    """Test that pw dialect can be imported and re-exports work."""
    from quantumvitas.ir.dialects import pw
    
    # Verify main exports exist
    assert hasattr(pw, "mapping")
    assert hasattr(pw, "IR_TO_QE_MAPPING")
    assert hasattr(pw, "QE_TO_IR_MAPPING")
    assert hasattr(pw, "ir_bool")
    assert hasattr(pw, "ir_params_to_qe_params")
    assert hasattr(pw, "ir_to_qe_param")
    assert hasattr(pw, "qe_to_ir_param")
    assert hasattr(pw, "qe_yaml_to_ir_yaml")
    
    # Verify these are the same as backends/qe
    from quantumvitas.ir.backends.qe.mapping import (
        IR_TO_QE_MAPPING as QE_IR_TO_QE_MAPPING,
        ir_bool as qe_ir_bool,
    )
    
    assert pw.IR_TO_QE_MAPPING is QE_IR_TO_QE_MAPPING
    assert pw.ir_bool is qe_ir_bool


def test_qc_dialect_imports():
    """Test that qc dialect can be imported."""
    from quantumvitas.ir.dialects import qc
    
    assert qc is not None
    assert hasattr(qc, "parameters")
    
    # Verify QC_IR_PARAMETERS exists and is empty (for now)
    from quantumvitas.ir.dialects.qc.parameters import QC_IR_PARAMETERS
    
    assert QC_IR_PARAMETERS is not None
    assert isinstance(QC_IR_PARAMETERS, dict)
    assert len(QC_IR_PARAMETERS) == 0  # Empty initially, will be populated in PR2


def test_dialect_import_from_top_level():
    """Test that dialects can be imported from ir module."""
    from quantumvitas.ir import dialects
    
    # Test direct import path
    from quantumvitas.ir.dialects import pw, qc
    
    assert pw is not None
    assert qc is not None


def test_pw_dialect_functionality():
    """Test that pw dialect functions work correctly."""
    from quantumvitas.ir.dialects.pw import ir_bool
    
    # Test ir_bool function
    assert ir_bool(True) == ".true."
    assert ir_bool(False) == ".false."
    assert ir_bool(".true.") == ".true."
    assert ir_bool(".false.") == ".false."


def test_dialect_separation():
    """Test that pw and qc dialects are separate namespaces."""
    from quantumvitas.ir.dialects import pw, qc
    
    # They should be different modules
    assert pw is not qc
    assert pw.__name__ != qc.__name__
    
    # pw should have QE-specific exports
    assert hasattr(pw, "IR_TO_QE_MAPPING")
    
    # qc should have QC-specific structure
    assert hasattr(qc, "parameters")

