"""
Guard tests to prevent .true./.false. strings in IR/YAML.

Per spec-ir-bool-canonicalization.md:
- IR patches must use Python bool
- YAML must store native true/false
- Only QE .in output should have .true./.false.
"""

import pytest


def _scan_for_qe_bool_strings(obj, path=""):
    """Recursively scan dict/list for .true./.false. strings."""
    forbidden = {".true.", ".false."}
    errors = []
    
    if isinstance(obj, dict):
        for k, v in obj.items():
            errors.extend(_scan_for_qe_bool_strings(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            errors.extend(_scan_for_qe_bool_strings(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        if obj.lower().strip() in forbidden:
            errors.append(f"{path}: found forbidden string {obj!r}")
    
    return errors


class TestIRPatchHasNoBoolStrings:
    """IR patches from ParamSpace must not contain .true./.false. strings."""
    
    def test_magnetism_profiles_use_python_bool(self):
        from quantumvitas.presets.paramspace import (
            get_magnetism_paramspace,
            compile_profile_patch,
        )
        space = get_magnetism_paramspace()
        yaml_tree = {}  # Empty YAML tree for compilation
        for profile_name in space.profiles:
            patch, _ = compile_profile_patch(space, profile_name, yaml_tree)
            errors = _scan_for_qe_bool_strings(patch)
            assert not errors, f"Profile {profile_name}: {errors}"
    
    def test_precision_profiles_use_python_bool(self):
        from quantumvitas.presets.precision_variants import build_precision_pw_default_space
        from quantumvitas.presets.paramspace import compile_profile_patch
        space = build_precision_pw_default_space()
        yaml_tree = {}  # Empty YAML tree for compilation
        for profile_name in space.profiles:
            patch, _ = compile_profile_patch(space, profile_name, yaml_tree)
            errors = _scan_for_qe_bool_strings(patch)
            assert not errors, f"Profile {profile_name}: {errors}"
    
    def test_occupations_scheme_profiles_use_python_bool(self):
        from quantumvitas.presets.paramspace import (
            get_occupations_scheme_paramspace,
            compile_profile_patch,
        )
        space = get_occupations_scheme_paramspace()
        yaml_tree = {}  # Empty YAML tree for compilation
        for profile_name in space.profiles:
            patch, _ = compile_profile_patch(space, profile_name, yaml_tree)
            errors = _scan_for_qe_bool_strings(patch)
            assert not errors, f"Profile {profile_name}: {errors}"
    
    def test_convergence_profiles_use_python_bool(self):
        from quantumvitas.presets.paramspace import (
            get_convergence_paramspace,
            compile_profile_patch,
        )
        space = get_convergence_paramspace()
        yaml_tree = {}  # Empty YAML tree for compilation
        for profile_name in space.profiles:
            patch, _ = compile_profile_patch(space, profile_name, yaml_tree)
            errors = _scan_for_qe_bool_strings(patch)
            assert not errors, f"Profile {profile_name}: {errors}"


class TestQEOutputHasFortranBools:
    """QE .in output must use .true./.false. for booleans."""

    def test_qe_generator_converts_bool_to_fortran(self):
        from quantumvitas.io.generator.qe_generator import QEInputGenerator

        assert QEInputGenerator.format_value(True) == ".true."
        assert QEInputGenerator.format_value(False) == ".false."
    
    def test_string_preserved_verbatim(self):
        """String values are quoted but preserved."""
        from quantumvitas.io.generator.qe_generator import QEInputGenerator
        
        assert QEInputGenerator.format_value("gaussian") == "'gaussian'"
        assert QEInputGenerator.format_value("Gaussian") == "'Gaussian'"  # Case preserved
    
    def test_string_dot_true_normalized_to_fortran_bool(self):
        """String '.true.' is normalized to unquoted Fortran logical."""
        from quantumvitas.io.generator.qe_generator import QEInputGenerator

        result = QEInputGenerator.format_value(".true.")
        assert result == ".true."

    def test_string_dot_false_normalized_to_fortran_bool(self):
        """String '.false.' is normalized to unquoted Fortran logical."""
        from quantumvitas.io.generator.qe_generator import QEInputGenerator

        result = QEInputGenerator.format_value("'.false.'")
        assert result == ".false."
    
    def test_int_not_quoted(self):
        """Integer values are not quoted."""
        from quantumvitas.io.generator.qe_generator import QEInputGenerator
        
        assert QEInputGenerator.format_value(50) == "50"
    
    def test_float_not_quoted(self):
        """Float values are not quoted."""
        from quantumvitas.io.generator.qe_generator import QEInputGenerator
        
        assert QEInputGenerator.format_value(1.0e-6) == "1e-06"
