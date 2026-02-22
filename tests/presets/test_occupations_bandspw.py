"""
Tests that occupations_scheme preset applies to bandspw step type.

Bug: OCCUPATIONS_SCHEME_VARIANT excluded "bandspw" from applies_to_step_types,
causing inconsistent Fermi level between SCF and bandspw for metals.
Fix: Added "bandspw" to applies_to_step_types.
"""

import pytest
import yaml

from qmatsuite.presets.dimensions import (
    OccupationsSchemeOption,
    MagnetismOption,
)
from qmatsuite.presets.variants_registry import (
    get_variant,
    compile_dimension_patch_for_step,
    OCCUPATIONS_SCHEME_VARIANT,
)


class TestOccupationsSchemeBandspw:
    """Verify occupations_scheme variant applies to bandspw."""

    def test_variant_includes_bandspw(self):
        """bandspw must be in OCCUPATIONS_SCHEME_VARIANT.applies_to_step_types."""
        assert "bandspw" in OCCUPATIONS_SCHEME_VARIANT.applies_to_step_types

    def test_get_variant_returns_variant_for_bandspw(self):
        """get_variant('occupations_scheme', 'bandspw') must NOT return None."""
        variant = get_variant("occupations_scheme", "bandspw")
        assert variant is not None
        assert variant.name == "OCCUPATIONS_SCHEME_PW"

    def test_compile_smearing_gaussian_for_bandspw(self):
        """Compiling SMEARING_GAUSSIAN for bandspw must produce occupations + smearing."""
        step_yaml = {"SYSTEM": {"ecutwfc": 50}}
        patch, deletions = compile_dimension_patch_for_step(
            "occupations_scheme",
            OccupationsSchemeOption.SMEARING_GAUSSIAN,
            "bandspw",
            step_yaml,
        )
        assert "SYSTEM" in patch
        assert patch["SYSTEM"]["occupations"] == "smearing"
        assert patch["SYSTEM"]["smearing"] == "gaussian"

    def test_compile_fixed_for_bandspw(self):
        """Compiling FIXED for bandspw must produce occupations=fixed."""
        step_yaml = {"SYSTEM": {"ecutwfc": 50}}
        patch, deletions = compile_dimension_patch_for_step(
            "occupations_scheme",
            OccupationsSchemeOption.FIXED,
            "bandspw",
            step_yaml,
        )
        assert "SYSTEM" in patch
        assert patch["SYSTEM"]["occupations"] == "fixed"

    def test_scf_and_bandspw_get_same_occupations(self):
        """SCF and bandspw must get the same occupations from the same preset."""
        step_yaml = {"SYSTEM": {"ecutwfc": 50}}
        option = OccupationsSchemeOption.SMEARING_GAUSSIAN

        scf_patch, _ = compile_dimension_patch_for_step(
            "occupations_scheme", option, "scf", step_yaml,
        )
        bandspw_patch, _ = compile_dimension_patch_for_step(
            "occupations_scheme", option, "bandspw", step_yaml,
        )

        assert scf_patch["SYSTEM"]["occupations"] == bandspw_patch["SYSTEM"]["occupations"]
        assert scf_patch["SYSTEM"]["smearing"] == bandspw_patch["SYSTEM"]["smearing"]

    def test_bands_postprocess_not_affected(self):
        """bands (post-processing, bands.x) must NOT get occupations preset."""
        variant = get_variant("occupations_scheme", "bands")
        assert variant is None, "bands.x post-processing step should not have occupations variant"

    def test_apply_presets_to_bandspw_step_file(self, tmp_path):
        """Full integration: apply_presets_to_step writes occupations to bandspw step."""
        from qmatsuite.presets.integration import apply_presets_to_step

        step_path = tmp_path / "test.step.yaml"
        initial_content = {
            "step_type_gen": "bandspw",
            "parameters": {
                "SYSTEM": {"ecutwfc": 50},
                "CONTROL": {"calculation": "bands"},
            },
        }
        step_path.write_text(yaml.safe_dump(initial_content))

        options = {
            "occupations_scheme": OccupationsSchemeOption.SMEARING_GAUSSIAN,
        }
        apply_presets_to_step(step_path, options, validate_physics=False)

        result = yaml.safe_load(step_path.read_text())
        system = result["parameters"]["SYSTEM"]
        assert system["occupations"] == "smearing"
        assert system["smearing"] == "gaussian"

    def test_all_pw_steps_covered(self):
        """All pw.x gen step types must be in occupations_scheme variant."""
        pw_steps = {"scf", "nscf", "bandspw", "relax", "md"}
        for step in pw_steps:
            variant = get_variant("occupations_scheme", step)
            assert variant is not None, (
                f"occupations_scheme variant missing for pw.x step '{step}'"
            )
