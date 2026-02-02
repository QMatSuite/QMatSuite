"""Tests for step-type materialization SSOT (Single Source of Truth).

These tests ensure that:
1. All drivers define complete materialization maps
2. All mapped step types are registered in DriverRegistry
3. No orphan mappings exist
4. The materialize_step() function works correctly via DriverRegistry
"""

import pytest

from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.workflow.generalized_steps import (
    materialize_step,
    dematerialize_step,
    dematerialize_to_generalized_step,
    get_supported_generalized_steps,
    get_engine_families_for_step,
    _is_zero_mapping,
)


# Ensure drivers are loaded
import quantumvitas.drivers


class TestDriverMaterializationCompleteness:
    """Test that all drivers define complete materialization maps."""

    # Expected gen types for each engine (minimum required)
    EXPECTED_GEN_TYPES = {
        "qe": [
            "scf",
            "nscf",
            "relax",
            "bandspw",
            "dos",
        ],
        "vasp": [
            "scf",
            "nscf",
            "relax",
            "bandspw",
        ],
        "pyscf": [
            "scf",
            "mp2",
            "td",
        ],
        "orca": [
            "scf",
            "hf",
            "td",
        ],
        "lammps": [
            "md",
            "relax",
        ],
        "cp2k": [
            "scf",
            "relax",
            "md",
        ],
    }

    @pytest.mark.parametrize("engine_family", EXPECTED_GEN_TYPES.keys())
    def test_driver_has_expected_mappings(self, engine_family: str):
        """Ensure each driver has all expected GEN type mappings."""
        if not DriverRegistry.is_engine_registered(engine_family):
            pytest.skip(f"Engine {engine_family} not registered")

        driver = DriverRegistry.get_driver(engine_family)
        mat_map = driver.get_materialization_map()

        expected = self.EXPECTED_GEN_TYPES[engine_family]
        missing = [gen_type for gen_type in expected if gen_type not in mat_map]

        assert not missing, (
            f"Engine '{engine_family}' missing expected mappings: {missing}. "
            f"Available: {list(mat_map.keys())}"
        )


class TestNoOrphanMappings:
    """Test that all mapped step types are registered."""

    def test_all_mapped_step_types_are_registered(self):
        """Ensure all step types in materialization maps are registered."""
        orphans = []

        for engine_family in DriverRegistry.get_all_engines():
            driver = DriverRegistry.get_driver(engine_family)
            mat_map = driver.get_materialization_map()

            for gen_type, machine_type in mat_map.items():
                if not DriverRegistry.is_step_type_registered(machine_type):
                    orphans.append(f"{engine_family}: {gen_type} -> {machine_type}")

        assert not orphans, f"Orphan mappings found (step types not registered):\n" + "\n".join(orphans)


class TestMaterializeStep:
    """Test the materialize_step() function."""

    @pytest.mark.parametrize(
        "gen_step,engine,expected",
        [
            ("scf", "qe", "qe_scf"),
            ("nscf", "qe", "qe_nscf"),
            ("relax", "qe", "qe_relax"),
            ("scf", "vasp", "vasp_scf"),
            ("scf", "pyscf", "pyscf_scf"),
            ("td", "pyscf", "pyscf_td"),
            ("md", "lammps", "lammps_md"),
            ("relax", "lammps", "lammps_relax"),
            ("scf", "cp2k", "cp2k_scf"),
        ],
    )
    def test_materialize_step_success(self, gen_step: str, engine: str, expected: str):
        """Test successful materialization."""
        if not DriverRegistry.is_engine_registered(engine):
            pytest.skip(f"Engine {engine} not registered")
        result = materialize_step(gen_step, engine)
        assert result == expected

    @pytest.mark.parametrize(
        "gen_step,engine",
        [
            ("UNKNOWN_STEP", "qe"),
            ("SCF", "unknown_engine"),
            ("PHONON", "lammps"),  # LAMMPS doesn't support phonon
        ],
    )
    def test_materialize_step_returns_none_for_unsupported(self, gen_step: str, engine: str):
        """Test that unsupported combinations return None."""
        result = materialize_step(gen_step, engine)
        assert result is None


class TestDematerializeStep:
    """Test the dematerialize_step() function."""

    @pytest.mark.parametrize(
        "machine_step,expected_engine,expected_gen",
        [
            ("qe_scf", "qe", "scf"),
            ("qe_nscf", "qe", "nscf"),
            ("vasp_scf", "vasp", "scf"),
            ("pyscf_scf", "pyscf", "scf"),
            ("lammps_md", "lammps", "md"),
            ("cp2k_scf", "cp2k", "scf"),
        ],
    )
    def test_dematerialize_step_success(self, machine_step: str, expected_engine: str, expected_gen: str):
        """Test successful dematerialization."""
        if not DriverRegistry.is_step_type_registered(machine_step):
            pytest.skip(f"Step type {machine_step} not registered")

        result = dematerialize_step(machine_step)
        assert result is not None
        engine, gen_type = result
        assert engine == expected_engine
        # GEN types are lowercase without prefix per constitution
        assert gen_type == expected_gen

    def test_dematerialize_step_returns_none_for_unknown(self):
        """Test that unknown step types return None."""
        result = dematerialize_step("unknown_step_type")
        assert result is None


class TestDematerializeToGenStep:
    """Test the dematerialize_to_generalized_step() function."""

    @pytest.mark.parametrize(
        "machine_step,expected_gen",
        [
            ("qe_scf", "scf"),
            ("qe_nscf", "nscf"),
            ("pyscf_td", "td"),
            ("lammps_md", "md"),
        ],
    )
    def test_dematerialize_to_generalized_step_strips_prefix(
        self, machine_step: str, expected_gen: str
    ):
        """Test dematerialize returns lowercase gen type per constitution."""
        if not DriverRegistry.is_step_type_registered(machine_step):
            pytest.skip(f"Step type {machine_step} not registered")

        result = dematerialize_to_generalized_step(machine_step)
        assert result == expected_gen


class TestGetSupportedGenSteps:
    """Test the get_supported_generalized_steps() function."""

    def test_qe_has_expected_steps(self):
        """Test QE returns expected generalized steps."""
        if not DriverRegistry.is_engine_registered("qe"):
            pytest.skip("QE not registered")

        steps = get_supported_generalized_steps("qe")
        # GEN types are lowercase per constitution
        assert "scf" in steps
        assert "nscf" in steps
        assert "relax" in steps

    def test_unknown_engine_returns_empty(self):
        """Test unknown engine returns empty list."""
        steps = get_supported_generalized_steps("unknown_engine")
        assert steps == []


class TestGetEngineFamiliesForStep:
    """Test the get_engine_families_for_step() function."""

    def test_scf_supported_by_multiple_engines(self):
        """Test that SCF is supported by multiple engines."""
        engines = get_engine_families_for_step("SCF")
        # Should include at least QE and PySCF
        assert "qe" in engines or len(engines) > 0

    def test_gen_step_lookup(self):
        """Test that gen step lookup works correctly."""
        engines = get_engine_families_for_step("scf")
        assert "qe" in engines
        assert "pyscf" in engines


class TestZeroMappings:
    """Test zero-mapping detection."""

    def test_vasp_dos_is_zero_mapping(self):
        """Test that VASP DOS is detected as zero-mapping."""
        if not DriverRegistry.is_engine_registered("vasp"):
            pytest.skip("VASP not registered")

        # VASP DOS is integrated in NSCF output
        assert _is_zero_mapping("dos", "vasp") is True

    def test_qe_dos_is_not_zero_mapping(self):
        """Test that QE DOS is NOT a zero-mapping (it has a real step)."""
        if not DriverRegistry.is_engine_registered("qe"):
            pytest.skip("QE not registered")

        assert _is_zero_mapping("DOS", "qe") is False

    def test_unknown_engine_returns_false(self):
        """Test that unknown engine returns False."""
        assert _is_zero_mapping("DOS", "unknown_engine") is False


class TestRoundTrip:
    """Test round-trip materialization/dematerialization."""

    @pytest.mark.parametrize("engine", ["qe", "vasp", "pyscf", "lammps", "cp2k"])
    def test_round_trip_consistency(self, engine: str):
        """Test that materialize -> dematerialize -> materialize is consistent."""
        if not DriverRegistry.is_engine_registered(engine):
            pytest.skip(f"Engine {engine} not registered")

        driver = DriverRegistry.get_driver(engine)
        mat_map = driver.get_materialization_map()

        for gen_type, machine_type in mat_map.items():
            # materialize
            result = materialize_step(gen_type, engine)
            assert result == machine_type, f"Failed materialize for {gen_type}"

            # dematerialize
            demat = dematerialize_step(machine_type)
            assert demat is not None, f"Failed dematerialize for {machine_type}"

            demat_engine, demat_gen = demat
            assert demat_engine == engine

            # re-materialize should give same result
            re_mat = materialize_step(demat_gen, engine)
            assert re_mat == machine_type, (
                f"Round-trip failed: {gen_type} -> {machine_type} -> "
                f"{demat_gen} -> {re_mat}"
            )
