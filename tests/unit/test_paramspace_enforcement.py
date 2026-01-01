"""
Enforcement tests for ParamSpace-only regime.

Per Constitution 10.7:
- All preset dimensions must use ParamSpace framework
- No legacy heuristic detection code
- No backward compatibility hacks

This module enforces:
(A) No-legacy-symbols test: scans for forbidden patterns
(B) Delegation test: verifies all detectors/compilers delegate to ParamSpace
"""

import inspect
import ast
import re
from pathlib import Path

import pytest

from quantumvitas.presets import (
    compile_magnetism,
    compile_occupations_scheme,
    detect_magnetism,
    detect_occupations_scheme,
)
from quantumvitas.presets.compiler import compile_precision
from quantumvitas.presets.detector import detect_precision
from quantumvitas.presets.paramspace import (
    get_magnetism_paramspace,
    get_occupations_scheme_paramspace,
    get_precision_paramspace,
)


class TestNoLegacySymbols:
    """Test that no legacy symbols exist in presets code."""
    
    def test_no_detect_precision_strict(self):
        """detect_precision_strict must not exist."""
        presets_dir = Path(__file__).parent.parent.parent / "src" / "quantumvitas" / "presets"
        
        forbidden_patterns = [
            r"def\s+detect_precision_strict\s*\(",
            r"detect_precision_strict\s*\(",
        ]
        
        for py_file in presets_dir.glob("*.py"):
            content = py_file.read_text()
            for pattern in forbidden_patterns:
                matches = re.findall(pattern, content)
                # Allow comments mentioning the function
                if matches:
                    # Check if it's just in a comment
                    lines = content.split('\n')
                    for line in lines:
                        if re.search(pattern, line) and not line.strip().startswith('#'):
                            pytest.fail(
                                f"Forbidden pattern '{pattern}' found in {py_file.name}:{lines.index(line)+1}\n"
                                f"Line: {line}"
                            )
    
    def test_no_heuristic_conv_thr_med(self):
        """No heuristic 'conv_thr missing → return MED' logic."""
        presets_dir = Path(__file__).parent.parent.parent / "src" / "quantumvitas" / "presets"
        
        forbidden_patterns = [
            r"conv_thr.*is\s+None.*return.*MED",
            r"conv_thr.*None.*PrecisionOption\.MED",
            r"if\s+conv_thr\s+is\s+None:.*return.*MED",
        ]
        
        for py_file in presets_dir.glob("*.py"):
            content = py_file.read_text()
            for pattern in forbidden_patterns:
                # Check for pattern (case-insensitive, multiline)
                if re.search(pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL):
                    # Allow in comments
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE) and not line.strip().startswith('#'):
                            pytest.fail(
                                f"Forbidden heuristic pattern found in {py_file.name}:{i+1}\n"
                                f"Line: {line}"
                            )
    
    def test_no_precision_config_legacy(self):
        """PRECISION_CONFIGS and PrecisionConfig must not exist."""
        presets_dir = Path(__file__).parent.parent.parent / "src" / "quantumvitas" / "presets"
        
        for py_file in presets_dir.glob("*.py"):
            content = py_file.read_text()
            
            # Check for PRECISION_CONFIGS (not in comments)
            if "PRECISION_CONFIGS" in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "PRECISION_CONFIGS" in line and not line.strip().startswith('#'):
                        pytest.fail(
                            f"PRECISION_CONFIGS found in {py_file.name}:{i+1}\n"
                            f"Line: {line}"
                        )
            
            # Check for PrecisionConfig class definition (not in comments)
            if "class PrecisionConfig" in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "class PrecisionConfig" in line and not line.strip().startswith('#'):
                        pytest.fail(
                            f"PrecisionConfig class found in {py_file.name}:{i+1}\n"
                            f"Line: {line}"
                        )


class TestParamSpaceDelegation:
    """Test that all detectors/compilers delegate to ParamSpace."""
    
    def test_compile_magnetism_delegates(self):
        """compile_magnetism must delegate to ParamSpace."""
        source = inspect.getsource(compile_magnetism)
        assert "get_magnetism_paramspace" in source or "compile_dimension_patch" in source or "spaces_registry" in source or "ParamSpace" in source
    
    def test_compile_occupations_scheme_delegates(self):
        """compile_occupations_scheme must delegate to ParamSpace."""
        source = inspect.getsource(compile_occupations_scheme)
        assert "get_occupations_scheme_paramspace" in source or "compile_profile_patch" in source or "ParamSpace" in source
    
    def test_compile_precision_delegates(self):
        """compile_precision must delegate to ParamSpace."""
        source = inspect.getsource(compile_precision)
        assert "get_precision_paramspace" in source or "ParamSpace" in source
    
    def test_detect_magnetism_delegates(self):
        """detect_magnetism must delegate to ParamSpace."""
        source = inspect.getsource(detect_magnetism)
        assert "get_magnetism_paramspace" in source or "detect_dimension" in source or "spaces_registry" in source or "ParamSpace" in source
    
    def test_detect_occupations_scheme_delegates(self):
        """detect_occupations_scheme must delegate to ParamSpace via variants."""
        source = inspect.getsource(detect_occupations_scheme)
        assert "variants_registry" in source or "detect_dimension_for_step" in source or "ParamSpace" in source
    
    def test_detect_precision_delegates(self):
        """detect_precision must delegate to ParamSpace."""
        source = inspect.getsource(detect_precision)
        assert "match_precision_profile" in source or "ParamSpace" in source
    
    def test_all_paramspaces_exist(self):
        """All ParamSpace singletons must be accessible."""
        assert get_magnetism_paramspace() is not None
        assert get_occupations_scheme_paramspace() is not None
        assert get_precision_paramspace() is not None

