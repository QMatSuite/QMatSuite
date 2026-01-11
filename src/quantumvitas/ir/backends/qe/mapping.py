"""
IR ↔ QE adapter mapping.

Mechanical mapping between IR parameter names and QE parameter names (module/section/key).
This layer is explicitly QE-specific and separate from IR definitions.

In v0, IR base units align with QE (Ry, Bohr), so no unit conversion is performed.
Units are recorded explicitly in the mapping to keep the boundary clear.
"""

from typing import Any, Dict, Optional, Tuple


# IR → QE Mapping (for compilation)
# Maps: ir_key → (qe_module, qe_section, qe_key)
IR_TO_QE_MAPPING: Dict[str, Tuple[str, str, str]] = {
    # Magnetism dimension
    "nspin": ("pw", "SYSTEM", "nspin"),
    "noncolin": ("pw", "SYSTEM", "noncolin"),
    "lspinorb": ("pw", "SYSTEM", "lspinorb"),
    
    # OccupationsScheme dimension
    "occupations": ("pw", "SYSTEM", "occupations"),
    "smearing": ("pw", "SYSTEM", "smearing"),
    "degauss": ("pw", "SYSTEM", "degauss"),
    
    # Precision dimension
    "ecutwfc": ("pw", "SYSTEM", "ecutwfc"),
    "ecutrho": ("pw", "SYSTEM", "ecutrho"),
    "conv_thr": ("pw", "ELECTRONS", "conv_thr"),
    "K_POINTS": ("pw", "cards", "K_POINTS"),  # Special: card, not namelist
    
    # Convergence dimension
    "mixing_beta": ("pw", "ELECTRONS", "mixing_beta"),
    "electron_maxstep": ("pw", "ELECTRONS", "electron_maxstep"),
    "mixing_mode": ("pw", "ELECTRONS", "mixing_mode"),
    "mixing_ndim": ("pw", "ELECTRONS", "mixing_ndim"),
    "diagonalization": ("pw", "ELECTRONS", "diagonalization"),
    
    # Low-hanging additions
    "nbnd": ("pw", "SYSTEM", "nbnd"),
    "nosym": ("pw", "SYSTEM", "nosym"),
    "noinv": ("pw", "SYSTEM", "noinv"),
}


# QE → IR Mapping (for detection)
# Maps: (qe_module, qe_section, qe_key) → ir_key
QE_TO_IR_MAPPING: Dict[Tuple[str, str, str], str] = {
    # Reverse mapping (built from IR_TO_QE_MAPPING)
    **{(module, section, key): ir_key for ir_key, (module, section, key) in IR_TO_QE_MAPPING.items()}
}


# Unit mapping (v0: identity, but explicit boundary)
IR_UNIT_TO_QE_UNIT: Dict[str, str] = {
    "Ry": "Ry",  # Energy: IR=Ry, QE=Ry (no conversion)
    "Bohr": "Bohr",  # Length: IR=Bohr, QE=Bohr (no conversion)
}


def ir_to_qe_param(ir_key: str, ir_value: Any) -> Tuple[str, str, str, Any]:
    """
    Convert IR parameter to QE parameter.
    
    Args:
        ir_key: IR parameter key
        ir_value: IR parameter value
        
    Returns:
        Tuple of (qe_module, qe_section, qe_key, qe_value)
        qe_value is converted from IR value (e.g., Python bool -> QE string for booleans)
        
    Raises:
        KeyError: If ir_key not in mapping
    """
    if ir_key not in IR_TO_QE_MAPPING:
        raise KeyError(f"IR key '{ir_key}' not found in IR→QE mapping")
    
    qe_module, qe_section, qe_key = IR_TO_QE_MAPPING[ir_key]
    
    # Convert IR value to QE value
    # v0: No unit conversion (IR base units align with QE)
    # But boolean parameters must use QE string format (.true./.false.)
    qe_value = ir_value
    
    # Convert Python bool to QE string format for boolean parameters
    if isinstance(ir_value, bool):
        # QE boolean parameters that must use string format
        boolean_params = {"noncolin", "lspinorb", "nosym", "noinv"}
        if qe_key in boolean_params:
            qe_value = ".true." if ir_value else ".false."
    
    return (qe_module, qe_section, qe_key, qe_value)


def qe_to_ir_param(qe_module: str, qe_section: str, qe_key: str, qe_value: Any) -> Tuple[str, Any]:
    """
    Convert QE parameter to IR parameter.
    
    Args:
        qe_module: QE module (e.g., "pw")
        qe_section: QE section (e.g., "SYSTEM", "ELECTRONS", "cards")
        qe_key: QE parameter key
        qe_value: QE parameter value
    
    Returns:
        Tuple of (ir_key, ir_value)
        ir_value is normalized (QE booleans → Python booleans, etc.)
    
    Raises:
        KeyError: If (qe_module, qe_section, qe_key) not in mapping
    """
    key = (qe_module, qe_section, qe_key)
    if key not in QE_TO_IR_MAPPING:
        raise KeyError(f"QE parameter '{qe_module}/{qe_section}/{qe_key}' not found in QE→IR mapping")
    
    ir_key = QE_TO_IR_MAPPING[key]
    
    # Normalize QE value to IR value
    ir_value = _normalize_qe_value_to_ir(qe_key, qe_value)
    
    return (ir_key, ir_value)


def _normalize_qe_value_to_ir(qe_key: str, qe_value: Any) -> Any:
    """
    Normalize QE value to IR value.
    
    In v0, mainly handles boolean conversion (.true./.false. → True/False).
    Other values pass through unchanged.
    """
    # Boolean parameters: normalize QE strings to Python bool
    boolean_params = {"noncolin", "lspinorb", "nosym", "noinv"}
    if qe_key in boolean_params:
        if isinstance(qe_value, bool):
            return qe_value
        if isinstance(qe_value, str):
            lower = qe_value.lower().strip()
            if lower in (".true.", "true", "t", ".t."):
                return True
            if lower in (".false.", "false", "f", ".f."):
                return False
        # Numeric: 0 = False, non-zero = True
        if isinstance(qe_value, (int, float)):
            return bool(qe_value)
        return False
    
    # v0: No unit conversion for other types (IR base units align with QE)
    return qe_value


def ir_patch_to_qe_patch(ir_patch: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Convert IR patch to QE patch.
    
    IR patch structure: {ir_section: {ir_key: ir_value}}
    QE patch structure: {qe_section: {qe_key: qe_value}}
    
    Args:
        ir_patch: IR patch dict (IR section -> IR key -> IR value)
        
    Returns:
        QE patch dict (QE section -> QE key -> QE value)
    """
    qe_patch: Dict[str, Dict[str, Any]] = {}
    
    for ir_section, ir_params in ir_patch.items():
        if not isinstance(ir_params, dict):
            # Skip non-dict sections (should not happen, but handle gracefully)
            continue
        
        for ir_key, ir_value in ir_params.items():
            try:
                qe_module, qe_section, qe_key, qe_value = ir_to_qe_param(ir_key, ir_value)
                
                if qe_section not in qe_patch:
                    qe_patch[qe_section] = {}
                qe_patch[qe_section][qe_key] = qe_value
            except KeyError:
                # IR key not in mapping - skip (should not happen in v0, but handle gracefully)
                # This can happen for non-IR parameters that might be in the patch
                continue
    
    return qe_patch


def qe_yaml_to_ir_yaml(qe_yaml: Dict[str, Dict[str, Any]], qe_module: str = "pw") -> Dict[str, Dict[str, Any]]:
    """
    Convert QE YAML to IR YAML.
    
    QE YAML structure: {qe_section: {qe_key: qe_value}}
    IR YAML structure: {ir_section: {ir_key: ir_value}}
    
    In v0, IR sections == QE sections (because IR is QE-equivalent).
    Only keys are converted (via explicit mapping).
    
    Args:
        qe_yaml: QE YAML dict (QE section -> QE key -> QE value)
        qe_module: QE module (default: "pw")
        
    Returns:
        IR YAML dict (IR section -> IR key -> IR value)
        Only IR parameters are included; non-IR parameters are skipped
    """
    # Defensive check: ensure qe_yaml is a dict
    if not isinstance(qe_yaml, dict):
        raise TypeError(f"qe_yaml must be a dict, got {type(qe_yaml)}")
    
    # Backward compatibility: Handle top-level K_POINTS_CARD
    # Some callers/tests still use K_POINTS_CARD at top level (legacy format)
    # Inject it into canonical location (cards.K_POINTS) if not already present
    if "K_POINTS_CARD" in qe_yaml:
        # Create a shallow copy to avoid mutating the input
        qe_yaml = dict(qe_yaml)
        if "cards" not in qe_yaml:
            qe_yaml["cards"] = {}
        # Only set if cards.K_POINTS doesn't already exist (canonical format takes precedence)
        if "K_POINTS" not in qe_yaml["cards"]:
            qe_yaml["cards"]["K_POINTS"] = qe_yaml["K_POINTS_CARD"]
        # Remove K_POINTS_CARD from top level to avoid processing it as a section
        del qe_yaml["K_POINTS_CARD"]
    
    ir_yaml: Dict[str, Dict[str, Any]] = {}
    
    for qe_section, qe_params in qe_yaml.items():
        # Normalize section name to uppercase for case-insensitive handling
        # In v0, IR sections == QE sections (uppercase)
        ir_section = qe_section.upper()
        
        if ir_section not in ir_yaml:
            ir_yaml[ir_section] = {}
        
        # Defensive check: ensure qe_params is a dict
        if not isinstance(qe_params, dict):
            # Skip non-dict sections (should not happen, but handle gracefully)
            continue
        
        # Normalize section name for mapping lookup (mapping uses uppercase for namelists, lowercase for cards)
        # For namelist sections (CONTROL, SYSTEM, ELECTRONS, etc.), use uppercase
        # For card sections (cards), use lowercase
        if ir_section in ("CONTROL", "SYSTEM", "ELECTRONS", "IONS", "CELL"):
            qe_section_for_mapping = ir_section  # Use uppercase for namelists
        else:
            qe_section_for_mapping = qe_section  # Use original case for cards
        for qe_key, qe_value in qe_params.items():
            try:
                # Try to find IR key for this QE parameter (use normalized section name)
                ir_key, ir_value = qe_to_ir_param(qe_module, qe_section_for_mapping, qe_key, qe_value)
                ir_yaml[ir_section][ir_key] = ir_value
            except KeyError:
                # No IR mapping for this QE parameter - skip (non-IR parameter)
                # This allows step.yaml to contain non-IR parameters
                continue
            except Exception:
                # Skip on error (non-IR parameter or mapping issue)
                continue
    
    return ir_yaml


def validate_ir_qe_mapping() -> None:
    """
    Validate IR↔QE mapping is complete and reversible.
    
    Raises:
        ValueError: If mapping is invalid
    """
    # Check all IR keys have QE mappings
    for ir_key in IR_TO_QE_MAPPING.keys():
        if ir_key not in IR_TO_QE_MAPPING:
            raise ValueError(f"IR key '{ir_key}' missing from IR→QE mapping")
    
    # Check reverse mapping is complete
    for qe_key_tuple, ir_key in QE_TO_IR_MAPPING.items():
        if ir_key not in IR_TO_QE_MAPPING:
            raise ValueError(f"QE→IR mapping points to unknown IR key '{ir_key}'")
        
        expected_qe = IR_TO_QE_MAPPING[ir_key]
        if qe_key_tuple != expected_qe:
            raise ValueError(
                f"QE→IR mapping inconsistent: "
                f"{qe_key_tuple} → {ir_key} but IR→QE says {ir_key} → {expected_qe}"
            )
    
    # Check all IR→QE mappings have reverse mappings
    for ir_key, qe_tuple in IR_TO_QE_MAPPING.items():
        if qe_tuple not in QE_TO_IR_MAPPING:
            raise ValueError(f"IR→QE mapping '{ir_key} → {qe_tuple}' missing reverse mapping")
        
        reverse_ir_key = QE_TO_IR_MAPPING[qe_tuple]
        if reverse_ir_key != ir_key:
            raise ValueError(
                f"Reverse mapping inconsistent: "
                f"{ir_key} → {qe_tuple} → {reverse_ir_key}"
            )


# Validate mapping on import
validate_ir_qe_mapping()

