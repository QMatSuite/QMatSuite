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
    assert hasattr(pw, "ir_params_to_qe_params")
    assert hasattr(pw, "ir_to_qe_param")
    assert hasattr(pw, "qe_to_ir_param")
    assert hasattr(pw, "qe_yaml_to_ir_yaml")
    
    # Verify these are the same as backends/qe
    from quantumvitas.ir.backends.qe.mapping import (
        IR_TO_QE_MAPPING as QE_IR_TO_QE_MAPPING,
    )
    
    assert pw.IR_TO_QE_MAPPING is QE_IR_TO_QE_MAPPING


def test_qc_dialect_imports():
    """Test that qc dialect can be imported and has expected parameters."""
    from quantumvitas.ir.dialects import qc
    
    assert qc is not None
    assert hasattr(qc, "parameters")
    
    # Verify QC_IR_PARAMETERS exists and has expected keys
    from quantumvitas.ir.dialects.qc.parameters import QC_IR_PARAMETERS
    
    assert QC_IR_PARAMETERS is not None
    assert isinstance(QC_IR_PARAMETERS, dict)
    
    # Expected QC precision keys
    expected_keys = ["scf.conv_tol", "scf.max_cycle", "dft.grid_level"]
    for key in expected_keys:
        assert key in QC_IR_PARAMETERS, f"Expected key '{key}' not found in QC_IR_PARAMETERS"
        
        # Verify schema: type, description, default should be present
        param_def = QC_IR_PARAMETERS[key]
        assert "type" in param_def, f"Key '{key}' missing 'type' field"
        assert "description" in param_def, f"Key '{key}' missing 'description' field"
        assert "default" in param_def, f"Key '{key}' missing 'default' field"
        
        # Verify type is a Python type
        assert isinstance(param_def["type"], type), f"Key '{key}' 'type' should be a Python type"
        assert isinstance(param_def["description"], str), f"Key '{key}' 'description' should be a string"


def test_dialect_import_from_top_level():
    """Test that dialects can be imported from ir module."""
    from quantumvitas.ir import dialects
    
    # Test direct import path
    from quantumvitas.ir.dialects import pw, qc
    
    assert pw is not None
    assert qc is not None


def test_pw_dialect_functionality():
    """Test that pw dialect functions work correctly."""
    from quantumvitas.ir.dialects.pw import ir_to_qe_param
    
    # Test ir_to_qe_param function (booleans stay as bool)
    qe_module, qe_section, qe_key, qe_value = ir_to_qe_param("noncolin", True)
    assert qe_module == "pw"
    assert qe_section == "SYSTEM"
    assert qe_key == "noncolin"
    assert qe_value is True  # Boolean stays as bool, not converted to string


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

