"""
IR ↔ QE adapter mapping.

Mechanical mapping between IR parameter names and QE parameter names (module/section/key).
This layer is explicitly QE-specific and separate from IR definitions.

In v0, IR base units align with QE (Ry, Bohr), so no unit conversion is performed.
Units are recorded explicitly in the mapping to keep the boundary clear.
"""

from typing import Any, Dict, Optional, Tuple


# Class A Key Type Registry
# Maps (SECTION, key) → expected_type for strict-typed parameters
CLASS_A_TYPES: Dict[Tuple[str, str], str] = {
    # Magnetism dimension
    ("SYSTEM", "nspin"): "int",
    ("SYSTEM", "noncolin"): "bool",
    ("SYSTEM", "lspinorb"): "bool",
    # OccupationsScheme dimension
    ("SYSTEM", "occupations"): "str",
    ("SYSTEM", "smearing"): "str",
    ("SYSTEM", "degauss"): "float",
    # Precision dimension
    ("SYSTEM", "ecutwfc"): "float",
    ("SYSTEM", "ecutrho"): "float",
    ("ELECTRONS", "conv_thr"): "float",
    # Convergence dimension
    ("ELECTRONS", "mixing_beta"): "float",
    ("ELECTRONS", "electron_maxstep"): "int",
    ("ELECTRONS", "mixing_mode"): "str",
    ("ELECTRONS", "mixing_ndim"): "int",
    ("ELECTRONS", "diagonalization"): "str",
    # Other IR-mapped keys
    ("SYSTEM", "nbnd"): "int",
    ("SYSTEM", "nosym"): "bool",
    ("SYSTEM", "noinv"): "bool",
}


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
        qe_value remains as Python bool. QE writer converts to .true./.false. at output.
        
    Raises:
        KeyError: If ir_key not in mapping
    """
    if ir_key not in IR_TO_QE_MAPPING:
        raise KeyError(f"IR key '{ir_key}' not found in IR→QE mapping")
    
    qe_module, qe_section, qe_key = IR_TO_QE_MAPPING[ir_key]
    
    # Convert IR value to QE value
    # v0: No unit conversion (IR base units align with QE)
    # Boolean values remain as Python bool. QE writer converts at output.
    qe_value = ir_value
    
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


def ir_params_to_qe_params(ir_params: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Convert IR parameters dict to QE parameters dict (with value serialization).
    
    This function handles the structure used by apply_presets_to_step:
    {
        "parameters": {
            "SYSTEM": {ir_key: ir_value, ...},
            "ELECTRONS": {ir_key: ir_value, ...}
        },
        "cards": {ir_key: ir_value, ...}
    }
    
    Converts to QE format:
    {
        "parameters": {
            "SYSTEM": {qe_key: qe_value, ...},  # qe_value serialized (bool -> ".true."/".false.")
            "ELECTRONS": {qe_key: qe_value, ...}
        },
        "cards": {qe_key: qe_value, ...}
    }
    
    Args:
        ir_params: IR parameters dict with "parameters" and/or "cards" keys
        
    Returns:
        QE parameters dict with serialized values (bool -> ".true."/".false.")
    """
    qe_params: Dict[str, Dict[str, Any]] = {}
    
    # Process "parameters" section (contains SYSTEM, ELECTRONS, etc.)
    if "parameters" in ir_params:
        qe_params["parameters"] = {}
        for section_name, section_params in ir_params["parameters"].items():
            if not isinstance(section_params, dict):
                continue
            
            qe_section_params = {}
            for ir_key, ir_value in section_params.items():
                # Handle None (deletion marker)
                if ir_value is None:
                    # For deletions, try to convert key but keep None
                    try:
                        qe_module, qe_section, qe_key, _ = ir_to_qe_param(ir_key, None)
                        # Verify section matches
                        if qe_section == section_name:
                            qe_section_params[qe_key] = None
                        else:
                            # Section mismatch - keep original key (should not happen in v0)
                            qe_section_params[ir_key] = None
                    except KeyError:
                        # IR key not in mapping - keep as-is
                        qe_section_params[ir_key] = None
                else:
                    # Convert IR key/value to QE key/value
                    try:
                        qe_module, qe_section, qe_key, qe_value = ir_to_qe_param(ir_key, ir_value)
                        # Verify section matches
                        if qe_section == section_name:
                            qe_section_params[qe_key] = qe_value
                        else:
                            # Section mismatch - use original key (should not happen in v0)
                            qe_section_params[ir_key] = qe_value
                    except KeyError:
                        # IR key not in mapping - keep as-is (non-IR parameters)
                        qe_section_params[ir_key] = ir_value
            
            if qe_section_params:
                qe_params["parameters"][section_name] = qe_section_params
    
    # Process "cards" section
    if "cards" in ir_params:
        qe_params["cards"] = {}
        cards_params = ir_params["cards"]
        if isinstance(cards_params, dict):
            for ir_key, ir_value in cards_params.items():
                # Handle None (deletion marker)
                if ir_value is None:
                    qe_params["cards"][ir_key] = None
                else:
                    # For cards, try to convert via mapping
                    try:
                        qe_module, qe_section, qe_key, qe_value = ir_to_qe_param(ir_key, ir_value)
                        # Cards should map to "cards" section
                        if qe_section == "cards":
                            qe_params["cards"][qe_key] = qe_value
                        else:
                            # Section mismatch - keep original key
                            qe_params["cards"][ir_key] = ir_value
                    except KeyError:
                        # IR key not in mapping - keep as-is (non-IR cards like K_POINTS)
                        qe_params["cards"][ir_key] = ir_value
    
    return qe_params


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


def is_class_a_key(section: str, key: str) -> bool:
    """
    Check if (section, key) is a Class A (strict-typed) key.
    
    Class A keys are those that:
    1. Are listed in IR_TO_QE_MAPPING, OR
    2. Are owned by any ParamSpace (ParamKey definitions)
    
    Args:
        section: YAML section name (e.g., "SYSTEM", "ELECTRONS")
        key: Parameter key name
        
    Returns:
        True if the key is Class A (strict-typed), False otherwise
    """
    section_upper = section.upper()
    key_lower = key.lower()
    
    # Check CLASS_A_TYPES registry
    if (section_upper, key_lower) in CLASS_A_TYPES:
        return True
    if (section_upper, key) in CLASS_A_TYPES:
        return True
    
    # Check IR mapping (by key name)
    if key_lower in IR_TO_QE_MAPPING:
        return True
    
    # Check IR mapping (by full tuple match)
    for _, (_, sec, k) in IR_TO_QE_MAPPING.items():
        if sec.upper() == section_upper and k.lower() == key_lower:
            return True
    
    return False


def get_class_a_type(section: str, key: str) -> Optional[str]:
    """
    Get expected type for Class A key, or None if not Class A.
    
    Args:
        section: YAML section name (e.g., "SYSTEM", "ELECTRONS")
        key: Parameter key name
        
    Returns:
        Expected type string: 'bool', 'int', 'float', 'str', or None if not Class A
    """
    section_upper = section.upper()
    key_lower = key.lower()
    
    # Check CLASS_A_TYPES registry
    type_str = CLASS_A_TYPES.get((section_upper, key_lower))
    if type_str:
        return type_str
    
    type_str = CLASS_A_TYPES.get((section_upper, key))
    if type_str:
        return type_str
    
    # If in IR mapping but not in type registry, return None
    # (caller should handle this case)
    return None


# Validate mapping on import
validate_ir_qe_mapping()

