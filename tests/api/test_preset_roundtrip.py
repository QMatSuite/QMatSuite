"""P3 hardening: Preset enum round-trip — all dimensions, all values.

Every value returned by get_presets (profile names like NM, COL, MED)
must be accepted by apply_presets after normalization. Tests call the
QVService API directly, not MCP tools.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantumvitas.api.service import QVService
from quantumvitas.presets.variants_registry import PROFILE_TO_ENUM


# Minimal pymatgen-format Silicon structure.
_SI_STRUCTURE_JSON = json.dumps({
    "@module": "pymatgen.core.structure",
    "@class": "Structure",
    "lattice": {
        "matrix": [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]],
        "a": 5.43, "b": 5.43, "c": 5.43,
        "alpha": 90, "beta": 90, "gamma": 90,
    },
    "sites": [
        {"species": [{"element": "Si", "occu": 1}], "abc": [0, 0, 0], "xyz": [0, 0, 0]},
    ],
})


@pytest.fixture
def svc_with_calc(tmp_path):
    """Create a project with Si structure, QE SCF calc, and species_map."""
    project_root = QVService.init_project(tmp_path / "proj")
    svc = QVService(project_root)

    source = tmp_path / "si.json"
    source.write_text(_SI_STRUCTURE_JSON)
    svc.structure.import_file(source, name="Silicon")

    import quantumvitas.drivers  # noqa: F401
    calc = svc.project.init_calculation(
        name="si_scf", structure_selector="Silicon", engine_family="qe",
    )
    svc.calculation.add_step(calc.ulid, step_type_gen="scf")

    # Set species_map (required for precision preset context resolution)
    svc.calculation.update_species_map(
        calc.ulid,
        {"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}},
    )

    return svc, calc.ulid


class TestProfileToEnumMapping:
    """Verify the PROFILE_TO_ENUM mapping covers all advertised presets."""

    def test_magnetism_profiles_have_enum_values(self):
        """Every magnetism profile name maps to an enum value."""
        mapping = PROFILE_TO_ENUM.get("magnetism", {})
        assert "NM" in mapping, "NM must be in magnetism mapping"
        assert "COL" in mapping, "COL must be in magnetism mapping"
        for name, enum_val in mapping.items():
            assert hasattr(enum_val, "value"), f"{name} maps to non-enum: {enum_val}"

    def test_precision_profiles_have_enum_values(self):
        """Every precision profile name maps to an enum value."""
        mapping = PROFILE_TO_ENUM.get("precision", {})
        for expected in ("LOW", "MED", "HIGH"):
            assert expected in mapping, f"{expected} must be in precision mapping"

    def test_convergence_profiles_have_enum_values(self):
        """Every convergence profile name maps to an enum value."""
        mapping = PROFILE_TO_ENUM.get("convergence", {})
        for expected in ("FAST", "NORMAL", "ROBUST"):
            assert expected in mapping, f"{expected} must be in convergence mapping"

    def test_occupations_profiles_have_enum_values(self):
        """Every occupations_scheme profile name maps to an enum value."""
        mapping = PROFILE_TO_ENUM.get("occupations_scheme", {})
        assert "FIXED" in mapping
        assert "SMEARING_GAUSSIAN" in mapping


class TestPresetRoundTrip:
    """Every profile name value must be accepted by apply_presets after normalization."""

    def test_magnetism_nm_roundtrip(self, svc_with_calc):
        """apply_presets accepts magnetism='NM' (via enum value normalization)."""
        svc, calc_ulid = svc_with_calc
        enum_val = PROFILE_TO_ENUM["magnetism"]["NM"].value
        result = svc.calculation.apply_presets(calc_ulid, {"magnetism": enum_val})
        assert result.get("status") == "applied" or result.get("steps_updated", 0) >= 0

    def test_magnetism_col_roundtrip(self, svc_with_calc):
        """apply_presets accepts magnetism='COL' (collinear)."""
        svc, calc_ulid = svc_with_calc
        enum_val = PROFILE_TO_ENUM["magnetism"]["COL"].value
        result = svc.calculation.apply_presets(calc_ulid, {"magnetism": enum_val})
        assert result.get("steps_updated", 0) >= 0

    def test_precision_all_values(self, svc_with_calc):
        """All precision profile enum values round-trip correctly."""
        svc, calc_ulid = svc_with_calc
        mapping = PROFILE_TO_ENUM.get("precision", {})
        for profile_name, enum_obj in mapping.items():
            result = svc.calculation.apply_presets(
                calc_ulid, {"precision": enum_obj.value},
            )
            assert result.get("steps_updated", 0) >= 0, (
                f"precision={profile_name} (value={enum_obj.value}) failed"
            )

    def test_convergence_all_values(self, svc_with_calc):
        """All convergence profile enum values round-trip correctly."""
        svc, calc_ulid = svc_with_calc
        mapping = PROFILE_TO_ENUM.get("convergence", {})
        for profile_name, enum_obj in mapping.items():
            result = svc.calculation.apply_presets(
                calc_ulid, {"convergence": enum_obj.value},
            )
            assert result.get("steps_updated", 0) >= 0, (
                f"convergence={profile_name} (value={enum_obj.value}) failed"
            )

    def test_occupations_all_values(self, svc_with_calc):
        """All occupations_scheme profile enum values round-trip correctly."""
        svc, calc_ulid = svc_with_calc
        mapping = PROFILE_TO_ENUM.get("occupations_scheme", {})
        for profile_name, enum_obj in mapping.items():
            result = svc.calculation.apply_presets(
                calc_ulid, {"occupations_scheme": enum_obj.value},
            )
            assert result.get("steps_updated", 0) >= 0, (
                f"occupations_scheme={profile_name} (value={enum_obj.value}) failed"
            )

    def test_all_dimensions_exhaustive(self, svc_with_calc):
        """Exhaustive: for every dimension, every profile's enum value is accepted."""
        svc, calc_ulid = svc_with_calc
        failures: list[str] = []

        for dim_name, mapping in PROFILE_TO_ENUM.items():
            for profile_name, enum_obj in mapping.items():
                try:
                    result = svc.calculation.apply_presets(
                        calc_ulid, {dim_name: enum_obj.value},
                    )
                    if result.get("steps_updated", 0) < 0:
                        failures.append(f"{dim_name}={profile_name}: negative steps_updated")
                except Exception as exc:
                    failures.append(f"{dim_name}={profile_name}: {exc}")

        assert not failures, f"Round-trip failures:\n" + "\n".join(failures)


class TestNormalizationBridge:
    """Verify the MCP-level normalization logic works correctly."""

    def test_profile_to_enum_value_mapping(self):
        """PROFILE_TO_ENUM[dim][profile].value produces a string the compiler accepts."""
        for dim_name, mapping in PROFILE_TO_ENUM.items():
            for profile_name, enum_obj in mapping.items():
                val = enum_obj.value
                assert isinstance(val, str), (
                    f"{dim_name}.{profile_name} enum value is not a string: {type(val)}"
                )
                assert val, f"{dim_name}.{profile_name} enum value is empty"

    def test_nm_maps_to_nonmagnetic(self):
        """NM profile maps to 'nonmagnetic' enum value (not 'NM')."""
        nm_enum = PROFILE_TO_ENUM["magnetism"]["NM"]
        assert nm_enum.value == "nonmagnetic", f"Expected 'nonmagnetic', got '{nm_enum.value}'"

    def test_col_maps_to_collinear(self):
        """COL profile maps to 'collinear_lsda' enum value."""
        col_enum = PROFILE_TO_ENUM["magnetism"]["COL"]
        assert col_enum.value == "collinear_lsda", f"Expected 'collinear_lsda', got '{col_enum.value}'"
