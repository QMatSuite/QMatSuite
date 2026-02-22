"""
Enforcement tests for ParamSpace registry systemization.

Per Constitution 10.7:
- All preset dimensions must be registered in SPACES registry
- All compiler/detector functions must be thin wrappers
- No dimension-specific logic outside ParamSpace declarations

This module enforces:
(A) Registry completeness
(B) Thin wrapper enforcement via inspect
(C) No-legacy-symbol / forbidden-pattern scan
"""

import inspect
import re
from pathlib import Path

import pytest

from qmatsuite.presets.spaces_registry import SPACES
from qmatsuite.presets import (
    compile_magnetism,
    compile_occupations_scheme,
    detect_magnetism,
    detect_occupations_scheme,
)
from qmatsuite.presets.compiler import compile_precision
from qmatsuite.presets.detector import detect_precision


# Expected dimensions (must match integration/receivers usage)
EXPECTED_DIMENSIONS = [
    "occupations_scheme",
    "magnetism",
    "precision",
    "qc_precision",
    "convergence",
]


class TestRegistryCompleteness:
    """Test that registry is complete and correct."""
    
    def test_all_expected_dimensions_in_registry(self):
        """All expected dimensions must be present in SPACES."""
        for dimension in EXPECTED_DIMENSIONS:
            assert dimension in SPACES, (
                f"Dimension '{dimension}' not found in SPACES registry. "
                f"Registry has: {list(SPACES.keys())}"
            )
    
    def test_registry_values_are_paramspaces(self):
        """All SPACES values must be ParamSpace objects."""
        from qmatsuite.presets.paramspace import ParamSpace
        
        for dimension, space in SPACES.items():
            assert isinstance(space, ParamSpace), (
                f"SPACES['{dimension}'] is not a ParamSpace object, got {type(space)}"
            )
    
    def test_no_extra_dimensions_in_registry(self):
        """Registry should not have unexpected dimensions (warn if present)."""
        unexpected = set(SPACES.keys()) - set(EXPECTED_DIMENSIONS)
        if unexpected:
            pytest.fail(
                f"Registry contains unexpected dimensions: {unexpected}. "
                f"Either add them to EXPECTED_DIMENSIONS or remove from registry."
            )


class TestThinWrapperEnforcement:
    """Test that compiler/detector functions are thin wrappers."""
    
    def _count_non_comment_lines(self, source: str) -> int:
        """Count non-empty, non-comment lines in function body."""
        lines = source.split('\n')
        count = 0
        in_docstring = False
        for line in lines:
            stripped = line.strip()
            # Skip empty lines
            if not stripped:
                continue
            # Skip docstrings
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            # Skip comments
            if stripped.startswith('#'):
                continue
            # Skip function definition line
            if stripped.startswith('def '):
                continue
            count += 1
        return count
    
    def test_compile_magnetism_is_thin_wrapper(self):
        """compile_magnetism must be a thin wrapper calling registry."""
        source = inspect.getsource(compile_magnetism)
        assert "compile_dimension_patch" in source or "spaces_registry" in source
        line_count = self._count_non_comment_lines(source)
        assert line_count <= 15, (
            f"compile_magnetism has {line_count} non-comment lines (max 15). "
            f"This suggests dimension-specific logic was reintroduced."
        )
    
    def test_compile_occupations_scheme_is_thin_wrapper(self):
        """compile_occupations_scheme must be a thin wrapper calling registry."""
        source = inspect.getsource(compile_occupations_scheme)
        assert "compile_dimension_patch" in source or "spaces_registry" in source
        line_count = self._count_non_comment_lines(source)
        assert line_count <= 15, (
            f"compile_occupations_scheme has {line_count} non-comment lines (max 15). "
            f"This suggests dimension-specific logic was reintroduced."
        )
    
    def test_compile_precision_is_thin_wrapper(self):
        """compile_precision must be a thin wrapper calling registry."""
        source = inspect.getsource(compile_precision)
        assert "compile_dimension_patch" in source or "spaces_registry" in source
        line_count = self._count_non_comment_lines(source)
        # Precision has many parameters (ecutwfc, ecutrho, conv_thr, nk1-3, sk1-3) so allow more lines
        assert line_count <= 35, (
            f"compile_precision has {line_count} non-comment lines (max 35). "
            f"This suggests dimension-specific logic was reintroduced."
        )
    
    def test_detect_magnetism_is_thin_wrapper(self):
        """detect_magnetism must be a thin wrapper calling registry."""
        source = inspect.getsource(detect_magnetism)
        assert "detect_dimension" in source or "spaces_registry" in source
        line_count = self._count_non_comment_lines(source)
        # Allow slightly more for edge case handling
        assert line_count <= 20, (
            f"detect_magnetism has {line_count} non-comment lines (max 20). "
            f"This suggests dimension-specific logic was reintroduced."
        )
    
    def test_detect_occupations_scheme_is_thin_wrapper(self):
        """detect_occupations_scheme must be a thin wrapper calling registry."""
        source = inspect.getsource(detect_occupations_scheme)
        assert "detect_dimension" in source or "spaces_registry" in source
        line_count = self._count_non_comment_lines(source)
        assert line_count <= 15, (
            f"detect_occupations_scheme has {line_count} non-comment lines (max 15). "
            f"This suggests dimension-specific logic was reintroduced."
        )
    
    def test_detect_precision_is_thin_wrapper(self):
        """detect_precision must be a thin wrapper calling registry."""
        source = inspect.getsource(detect_precision)
        assert "detect_dimension" in source or "spaces_registry" in source
        line_count = self._count_non_comment_lines(source)
        assert line_count <= 15, (
            f"detect_precision has {line_count} non-comment lines (max 15). "
            f"This suggests dimension-specific logic was reintroduced."
        )


class TestNoLegacySymbols:
    """Test that no legacy symbols or forbidden patterns exist."""
    
    def test_no_detect_precision_strict(self):
        """detect_precision_strict must not exist."""
        presets_dir = Path(__file__).parent.parent.parent / "src" / "qmatsuite" / "presets"
        
        forbidden_patterns = [
            r"def\s+detect_precision_strict\s*\(",
        ]
        
        for py_file in presets_dir.glob("*.py"):
            content = py_file.read_text()
            for pattern in forbidden_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    # Check if it's just in a comment
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line) and not line.strip().startswith('#'):
                            pytest.fail(
                                f"Forbidden pattern '{pattern}' found in {py_file.name}:{i+1}\n"
                                f"Line: {line}"
                            )
    
    def test_no_heuristic_conv_thr_med(self):
        """No heuristic 'conv_thr missing => return MED' logic."""
        presets_dir = Path(__file__).parent.parent.parent / "src" / "qmatsuite" / "presets"
        
        forbidden_patterns = [
            r"conv_thr.*is\s+None.*return.*MED",
            r"conv_thr.*None.*PrecisionOption\.MED",
            r"if\s+conv_thr\s+is\s+None:.*return.*MED",
        ]
        
        for py_file in presets_dir.glob("*.py"):
            content = py_file.read_text()
            for pattern in forbidden_patterns:
                if re.search(pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL):
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE) and not line.strip().startswith('#'):
                            pytest.fail(
                                f"Forbidden heuristic pattern found in {py_file.name}:{i+1}\n"
                                f"Line: {line}"
                            )
    
    def test_no_precision_config_legacy(self):
        """PRECISION_CONFIGS and PrecisionConfig must not exist."""
        presets_dir = Path(__file__).parent.parent.parent / "src" / "qmatsuite" / "presets"
        
        for py_file in presets_dir.glob("*.py"):
            content = py_file.read_text()
            
            if "PRECISION_CONFIGS" in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "PRECISION_CONFIGS" in line and not line.strip().startswith('#'):
                        pytest.fail(
                            f"PRECISION_CONFIGS found in {py_file.name}:{i+1}\n"
                            f"Line: {line}"
                        )
            
            if "class PrecisionConfig" in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "class PrecisionConfig" in line and not line.strip().startswith('#'):
                        pytest.fail(
                            f"PrecisionConfig class found in {py_file.name}:{i+1}\n"
                            f"Line: {line}"
                        )

