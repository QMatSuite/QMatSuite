"""
Gate tests for Step Type Constitution.

These tests enforce the naming invariants from STEP_TYPE_CONSTITUTION_REVIEW.md.

NOTE: Some tests are marked with @pytest.mark.skip during migration phase.
They will be unskipped as renames are completed.
"""

import pytest
from qmatsuite.workflow.gen_steps import GenStepRegistry
from qmatsuite.workflow.step_type_convert import (
    spec_from, gen_from, prefix_from, is_spec, is_gen, ENGINE_PREFIXES
)


class TestGenStepRegistry:
    """Gate tests for GenStepRegistry."""

    def test_registry_not_empty(self):
        """Registry must have steps defined."""
        assert len(GenStepRegistry.GEN_STEPS) > 0

    def test_common_gen_steps_present(self):
        """Common GEN steps must be in registry."""
        required = {"scf", "nscf", "relax", "dos", "bands", "md"}
        for gen in required:
            assert GenStepRegistry.is_valid(gen), f"'{gen}' missing from registry"


class TestStepTypeConvert:
    """Gate tests for spec↔gen conversion functions."""

    def test_spec_from_creates_correct_format(self):
        """spec_from creates {prefix}_{gen}."""
        assert spec_from("qe", "scf") == "qe_scf"
        assert spec_from("vasp", "relax") == "vasp_relax"
        assert spec_from("w90", "wannier") == "w90_wannier"

    def test_gen_from_extracts_gen(self):
        """gen_from extracts gen from spec."""
        assert gen_from("qe_scf") == "scf"
        assert gen_from("vasp_relax") == "relax"
        assert gen_from("pyscf_mp2") == "mp2"
        assert gen_from("w90_wannier") == "wannier"

    def test_gen_from_passthrough_for_gen(self):
        """gen_from returns gen as-is."""
        assert gen_from("scf") == "scf"
        assert gen_from("relax") == "relax"

    def test_prefix_from_extracts_prefix(self):
        """prefix_from extracts engine prefix."""
        assert prefix_from("qe_scf") == "qe"
        assert prefix_from("vasp_relax") == "vasp"
        assert prefix_from("w90_wannier") == "w90"

    def test_prefix_from_raises_for_gen(self):
        """prefix_from raises for non-SPEC input."""
        with pytest.raises(ValueError):
            prefix_from("scf")

    def test_is_spec_detects_underscore(self):
        """is_spec returns True for strings with underscore."""
        assert is_spec("qe_scf") is True
        assert is_spec("scf") is False

    def test_is_gen_detects_no_underscore(self):
        """is_gen returns True for strings without underscore."""
        assert is_gen("scf") is True
        assert is_gen("qe_scf") is False

    def test_roundtrip_conversion(self):
        """spec_from and gen_from are inverses."""
        for prefix in ["qe", "vasp", "pyscf", "w90"]:
            for gen in ["scf", "relax", "dos"]:
                spec = spec_from(prefix, gen)
                assert gen_from(spec) == gen
                assert prefix_from(spec) == prefix


class TestEnginePrefixes:
    """Gate tests for engine prefixes."""

    def test_no_underscore_in_prefixes(self):
        """No engine prefix should contain underscore."""
        for prefix in ENGINE_PREFIXES:
            assert "_" not in prefix, f"Prefix '{prefix}' contains underscore"

    def test_known_engines_present(self):
        """Known engines must be in prefix list."""
        required = {"qe", "vasp", "pyscf", "orca", "lammps", "cp2k", "w90"}
        for prefix in required:
            assert prefix in ENGINE_PREFIXES, f"'{prefix}' missing from ENGINE_PREFIXES"


# =============================================================================
# MIGRATION GATES - Skipped during migration, unskipped when renames complete
# =============================================================================

class TestNoUnderscoreInGenSteps:
    """Gate: No underscore in GEN steps (Constitution Law 1)."""

    def test_no_underscore_in_gen_registry(self):
        """All GEN steps must not contain underscore."""
        for gen in GenStepRegistry.GEN_STEPS:
            assert "_" not in gen, f"GEN '{gen}' contains underscore (FORBIDDEN)"


class TestWannier90EngineOwnership:
    """Gate: Wannier90 steps owned by w90 engine, not qe."""

    def test_wannierprep_owned_by_w90(self):
        """wannierprep must be owned by w90 engine."""
        from qmatsuite.workflow.registry import get_registry
        registry = get_registry()
        # get() expects GEN type, not SPEC type
        spec = registry.get("wannierprep")
        assert spec is not None, "wannierprep must be registered"
        assert spec.step_type_spec == "w90_wannierprep", f"wannierprep must have spec type w90_wannierprep, got {spec.step_type_spec}"
        assert spec.engine == "w90", f"wannierprep must be owned by w90 engine, got {spec.engine}"

    def test_wannier_owned_by_w90(self):
        """wannier must be owned by w90 engine."""
        from qmatsuite.workflow.registry import get_registry
        registry = get_registry()
        # get() expects GEN type, not SPEC type
        spec = registry.get("wannier")
        assert spec is not None, "wannier must be registered"
        assert spec.step_type_spec == "w90_wannier", f"wannier must have spec type w90_wannier, got {spec.step_type_spec}"
        assert spec.engine == "w90", f"wannier must be owned by w90 engine, got {spec.engine}"

    def test_pw2wannier_owned_by_qe(self):
        """pw2wannier must be owned by qe engine (not w90)."""
        from qmatsuite.workflow.registry import get_registry
        registry = get_registry()
        # get() expects GEN type, not SPEC type
        spec = registry.get("pw2wannier")
        assert spec is not None, "pw2wannier must be registered"
        assert spec.step_type_spec == "qe_pw2wannier", f"pw2wannier must have spec type qe_pw2wannier, got {spec.step_type_spec}"
        assert spec.engine == "qe", f"pw2wannier must be owned by qe engine, got {spec.engine}"

