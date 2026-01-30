"""Gate 0: No silent fallbacks tests.

These tests MUST FAIL before the fix and PASS after.
"""

import pytest
import re
from pathlib import Path

# Get project root (parent of tests/)
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestNoSilentQEFallback:
    """Verify QE fallback removed from calc_identity.py."""

    def test_no_qe_fallback_pattern(self):
        """The specific QE fallback pattern must not exist."""
        source = (PROJECT_ROOT / "src/quantumvitas/core/calc_identity.py").read_text()

        # This exact pattern is the dangerous fallback
        # It should NOT be in the code after the fix
        dangerous_pattern = r'else:\s*\n\s*#.*\n\s*families\.add\("qe"\)'

        matches = re.findall(dangerous_pattern, source, re.MULTILINE)
        assert len(matches) == 0, (
            "Silent QE fallback still exists in calc_identity.py.\n"
            "The pattern 'else: ... families.add(\"qe\")' must be removed."
        )

    def test_unknown_type_returns_none_not_qe(self):
        """Unknown type should return None, not 'qe'."""
        from quantumvitas.core.calc_identity import _infer_engine_family_from_spec_types

        result = _infer_engine_family_from_spec_types(["totally_unknown_xyz_123"])

        # After fix: should be None (not "qe")
        assert result is None, (
            f"Unknown step type returned '{result}' instead of None. "
            "Silent fallback still active."
        )


class TestNoDefaultEngineInCalculation:
    """Verify no .get('engine', 'qe') defaults."""

    def test_no_default_engine_qe_pattern(self):
        """No .get('engine', 'qe') in calculation loading."""
        source = (PROJECT_ROOT / "src/quantumvitas/calculation/calculation.py").read_text()

        pattern = r'\.get\(["\']engine["\'],\s*["\']qe["\']\)'
        matches = re.findall(pattern, source)

        assert len(matches) == 0, (
            f"Found {len(matches)} instances of .get('engine', 'qe') "
            "in calculation.py. These must be removed."
        )


class TestNoRecipeFallback:
    """Verify recipe selection has no QE fallback."""

    def test_no_qerecipe_default(self):
        """get_recipe_for_engine should not default to QERecipe."""
        source = (PROJECT_ROOT / "src/quantumvitas/execution/recipes.py").read_text()

        # Pattern: .get(..., QERecipe) or default=QERecipe
        patterns = [
            r'\.get\([^)]+,\s*QERecipe\)',
            r'return.*QERecipe\s*#.*default',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, source)
            assert len(matches) == 0, (
                f"Found QERecipe fallback pattern in recipes.py"
            )

