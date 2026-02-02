"""
Unit tests for registry step type handling.

Per constitution, there are NO step type aliases.
- Only canonical GEN types exist (e.g., "relax", "scf", "md")
- VC (variable-cell) is a PARAMETER for relax/md, NOT a separate step type
- No vc-relax, opt, geomopt, vcrelax, qe_vc_relax, etc.
"""

import warnings

from quantumvitas.workflow.registry import (
    get_registry,
    normalize_step_type,
    STEP_TYPE_ALIASES,
)


class TestStepTypeNormalization:
    """Test step type normalization behavior."""

    def test_no_aliases_exist(self):
        """No step type aliases exist - use canonical GEN types directly.

        Per constitution, there are no aliases. Code MUST use "relax" directly.
        VC is a parameter, not a step type.
        """
        assert STEP_TYPE_ALIASES == {}

    def test_canonical_types_unchanged(self):
        """Canonical GEN types are returned unchanged."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # No warnings expected
            assert normalize_step_type("relax") == "relax"
            assert normalize_step_type("scf") == "scf"
            assert normalize_step_type("md") == "md"
            assert normalize_step_type("nscf") == "nscf"
            assert normalize_step_type("bands") == "bands"

    def test_spec_types_unchanged(self):
        """SPEC types are returned unchanged (normalize only handles GEN)."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # No warnings expected
            assert normalize_step_type("qe_relax") == "qe_relax"
            assert normalize_step_type("qe_scf") == "qe_scf"
            assert normalize_step_type("vasp_relax") == "vasp_relax"

    def test_empty_string_unchanged(self):
        """Empty string is returned unchanged."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert normalize_step_type("") == ""

    def test_registry_lookup_by_gen(self):
        """Registry lookup works with GEN types."""
        registry = get_registry()

        # relax should find qe_relax spec (default engine)
        spec = registry.get("relax")
        assert spec is not None
        assert spec.step_type_gen == "relax"

        # scf should find qe_scf spec
        spec = registry.get("scf")
        assert spec is not None
        assert spec.step_type_gen == "scf"
