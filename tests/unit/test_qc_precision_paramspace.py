"""
Tests for QC Precision ParamSpace.

Verifies that QC precision ParamSpace works correctly with roundtrip tests.
"""

import pytest

from quantumvitas.presets.qc_precision import (
    get_qc_precision_paramspace,
    build_qc_precision_paramspace,
)
from quantumvitas.presets.paramspace import match_profile, compile_profile_patch
from quantumvitas.presets.dimensions import PrecisionOption, DIMENSION_QC_PRECISION
from quantumvitas.presets.spaces_registry import (
    SPACES,
    detect_dimension,
    compile_dimension_patch,
    PROFILE_TO_ENUM,
    ENUM_TO_PROFILE,
)


def test_qc_precision_paramspace_exists():
    """Test that QC precision ParamSpace can be created."""
    space = get_qc_precision_paramspace()
    assert space is not None
    assert space.name == "qc_precision"
    assert len(space.keys) == 4  # scf.conv_tol, scf.max_cycle, dft.grid_level, engine.orca.scf.macro
    assert len(space.profiles) == 3  # LOW, MED, HIGH


def test_qc_precision_profiles_exist():
    """Test that all profiles (LOW, MED, HIGH) exist."""
    space = get_qc_precision_paramspace()
    assert "LOW" in space.profiles
    assert "MED" in space.profiles
    assert "HIGH" in space.profiles


def test_qc_precision_profile_values():
    """Test that profile values are correct."""
    space = get_qc_precision_paramspace()
    
    # Find keys
    key_conv_tol = next(k for k in space.keys if k.key == "conv_tol")
    key_max_cycle = next(k for k in space.keys if k.key == "max_cycle")
    key_grid_level = next(k for k in space.keys if k.key == "grid_level")
    key_macro = next(k for k in space.keys if k.key == "macro")
    
    # Check LOW profile
    low_profile = space.profiles["LOW"]
    assert low_profile[key_conv_tol].value == 1e-6
    assert low_profile[key_max_cycle].value == 50
    assert low_profile[key_grid_level].value == 2
    assert low_profile[key_macro].value == "normal"
    
    # Check MED profile
    med_profile = space.profiles["MED"]
    assert med_profile[key_conv_tol].value == 1e-8
    assert med_profile[key_max_cycle].value == 100
    assert med_profile[key_grid_level].value == 3
    assert med_profile[key_macro].value == "normal"
    
    # Check HIGH profile
    high_profile = space.profiles["HIGH"]
    assert high_profile[key_conv_tol].value == 1e-10
    assert high_profile[key_max_cycle].value == 200
    assert high_profile[key_grid_level].value == 4
    assert high_profile[key_macro].value == "tightscf"


def test_qc_precision_registered_in_spaces():
    """Test that QC precision is registered in SPACES registry."""
    assert DIMENSION_QC_PRECISION in SPACES
    assert SPACES[DIMENSION_QC_PRECISION].name == "qc_precision"


def test_qc_precision_profile_mappings():
    """Test that profile-to-enum mappings exist."""
    assert DIMENSION_QC_PRECISION in PROFILE_TO_ENUM
    assert DIMENSION_QC_PRECISION in ENUM_TO_PROFILE
    
    profile_to_enum = PROFILE_TO_ENUM[DIMENSION_QC_PRECISION]
    enum_to_profile = ENUM_TO_PROFILE[DIMENSION_QC_PRECISION]
    
    assert "LOW" in profile_to_enum
    assert "MED" in profile_to_enum
    assert "HIGH" in profile_to_enum
    
    assert profile_to_enum["LOW"] == PrecisionOption.LOW
    assert profile_to_enum["MED"] == PrecisionOption.MED
    assert profile_to_enum["HIGH"] == PrecisionOption.HIGH
    
    assert enum_to_profile[PrecisionOption.LOW] == "LOW"
    assert enum_to_profile[PrecisionOption.MED] == "MED"
    assert enum_to_profile[PrecisionOption.HIGH] == "HIGH"


def test_qc_precision_compile_profile_patch():
    """Test that compiling a profile produces the expected patch."""
    space = get_qc_precision_paramspace()
    step_yaml = {}  # Empty YAML
    
    # Compile LOW profile
    patch, deletions = compile_profile_patch(space, "LOW", step_yaml, explicit_defaults=True)
    
    assert "scf" in patch
    assert "dft" in patch
    assert "engine.orca.scf" in patch
    
    assert patch["scf"]["conv_tol"] == 1e-6
    assert patch["scf"]["max_cycle"] == 50
    assert patch["dft"]["grid_level"] == 2
    assert patch["engine.orca.scf"]["macro"] == "normal"
    
    # Compile HIGH profile
    patch, deletions = compile_profile_patch(space, "HIGH", step_yaml, explicit_defaults=True)
    
    assert patch["scf"]["conv_tol"] == 1e-10
    assert patch["scf"]["max_cycle"] == 200
    assert patch["dft"]["grid_level"] == 4
    assert patch["engine.orca.scf"]["macro"] == "tightscf"


def test_qc_precision_match_profile():
    """Test that matching works correctly."""
    space = get_qc_precision_paramspace()
    
    # Create YAML matching LOW profile
    step_yaml = {
        "scf": {
            "conv_tol": 1e-6,
            "max_cycle": 50,
        },
        "dft": {
            "grid_level": 2,
        },
        "engine.orca.scf": {
            "macro": "normal",
        },
    }
    
    matched = match_profile(space, step_yaml)
    assert matched == "LOW"
    
    # Create YAML matching HIGH profile
    step_yaml = {
        "scf": {
            "conv_tol": 1e-10,
            "max_cycle": 200,
        },
        "dft": {
            "grid_level": 4,
        },
        "engine.orca.scf": {
            "macro": "tightscf",
        },
    }
    
    matched = match_profile(space, step_yaml)
    assert matched == "HIGH"


def test_qc_precision_roundtrip():
    """Test roundtrip: compile -> match -> same profile."""
    space = get_qc_precision_paramspace()
    
    for profile_name in ["LOW", "MED", "HIGH"]:
        # Compile profile
        step_yaml = {}
        patch, deletions = compile_profile_patch(space, profile_name, step_yaml, explicit_defaults=True)
        
        # Apply patch to step_yaml
        for section, params in patch.items():
            if section not in step_yaml:
                step_yaml[section] = {}
            step_yaml[section].update(params)
        
        # Match should return same profile
        matched = match_profile(space, step_yaml)
        assert matched == profile_name, f"Roundtrip failed for {profile_name}"


def test_qc_precision_detect_dimension():
    """Test detect_dimension API for qc_precision."""
    step_yaml = {
        "scf": {
            "conv_tol": 1e-8,
            "max_cycle": 100,
        },
        "dft": {
            "grid_level": 3,
        },
        "engine.orca.scf": {
            "macro": "normal",
        },
    }
    
    detected = detect_dimension(DIMENSION_QC_PRECISION, step_yaml)
    assert detected == PrecisionOption.MED


def test_qc_precision_compile_dimension_patch():
    """Test compile_dimension_patch API for qc_precision."""
    step_yaml = {}
    
    patch, deletions = compile_dimension_patch(
        DIMENSION_QC_PRECISION,
        PrecisionOption.HIGH,
        step_yaml,
        explicit_defaults=True,
    )
    
    assert "scf" in patch
    assert patch["scf"]["conv_tol"] == 1e-10
    assert patch["scf"]["max_cycle"] == 200
    assert patch["dft"]["grid_level"] == 4
    assert patch["engine.orca.scf"]["macro"] == "tightscf"


def test_qc_precision_uses_python_native_types():
    """Test that QC precision uses Python native types (not .true./.false. strings)."""
    space = get_qc_precision_paramspace()
    step_yaml = {}
    
    patch, deletions = compile_profile_patch(space, "LOW", step_yaml, explicit_defaults=True)
    
    # All values should be Python native types
    assert isinstance(patch["scf"]["conv_tol"], float)
    assert isinstance(patch["scf"]["max_cycle"], int)
    assert isinstance(patch["dft"]["grid_level"], int)
    assert isinstance(patch["engine.orca.scf"]["macro"], str)
    
    # No .true./.false. strings should appear
    patch_str = str(patch)
    assert ".true." not in patch_str
    assert ".false." not in patch_str

