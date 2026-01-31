"""
Gate: Underscore Ban (§4)

Constitution §4: engine_prefix and step_type_gen MUST NOT contain underscores.
If a string contains _, it is spec; otherwise, it is gen.

This gate enforces:
- All engine_prefix values (from PREFIX) have no underscores
- All step_type_gen values (from GenStepRegistry) have no underscores
"""

import pytest
from quantumvitas.workflow.gen_steps import GenStepRegistry
from quantumvitas.workflow.step_type_convert import ENGINE_PREFIXES


class TestUnderscoreBan:
    """Gate: No underscores in engine_prefix or step_type_gen."""

    def test_no_underscore_in_engine_prefixes(self):
        """All engine prefixes must not contain underscore."""
        violations = []
        for prefix in ENGINE_PREFIXES:
            if "_" in prefix:
                violations.append(f"Engine prefix '{prefix}' contains underscore")
        
        if violations:
            report = "\n\n=== ENGINE PREFIX UNDERSCORE VIOLATIONS ===\n"
            report += "\n".join(f"  - {v}" for v in violations)
            report += "\n\n=== END VIOLATIONS ===\n"
            pytest.fail(report)

    def test_no_underscore_in_gen_steps(self):
        """All gen step names must not contain underscore."""
        violations = []
        for gen in GenStepRegistry.GEN_STEPS:
            if "_" in gen:
                violations.append(f"GEN step '{gen}' contains underscore")
        
        if violations:
            report = "\n\n=== GEN STEP UNDERSCORE VIOLATIONS ===\n"
            report += "\n".join(f"  - {v}" for v in violations)
            report += "\n\n=== END VIOLATIONS ===\n"
            report += "\nFix: Rename gen steps to remove underscores (e.g., 'vc_md' -> 'md' with VC parameter).\n"
            pytest.fail(report)

