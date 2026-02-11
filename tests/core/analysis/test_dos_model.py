"""Tests for DOS analysis model — PDOS series emission and spin-down flip."""
from __future__ import annotations

import numpy as np
import pytest

from quantumvitas.core.analysis.base import AnalysisObjectMeta
from quantumvitas.core.analysis.dos.model import DOS


def _make_meta(**overrides):
    defaults = dict(
        schema_version="1.0",
        object_type="dos",
        created_at="2024-01-01T00:00:00+00:00",
        run_ulid="01H0000000000000000000RUN1",
        calc_ulid="01H0000000000000000000CAL1",
        step_ulids=["01H0000000000000000000STP1"],
        gen_steps=["scf"],
        engine_name="test",
        source_files=[],
        parser_name="test_parser",
        parser_version="0.1",
        warnings=[],
    )
    defaults.update(overrides)
    return AnalysisObjectMeta(**defaults)


class TestTotalDOSSeries:
    """Total DOS series emission."""

    def test_non_spin_total_dos(self):
        energies = np.linspace(-5, 5, 100)
        total_dos = np.abs(np.sin(energies))
        dos = DOS(meta=_make_meta(), energies=energies, total_dos=total_dos)
        bundle = dos.to_primitives()
        assert len(bundle.series) == 1
        assert bundle.series[0].name == "Total DOS"
        np.testing.assert_array_almost_equal(bundle.series[0].y, total_dos)

    def test_spin_polarized_total_dos_down_flipped(self):
        energies = np.linspace(-5, 5, 50)
        up = np.abs(np.sin(energies))
        down = np.abs(np.cos(energies))
        total_dos = np.stack([up, down])
        dos = DOS(meta=_make_meta(), energies=energies, total_dos=total_dos)
        bundle = dos.to_primitives()

        # Find total DOS series
        total_series = [s for s in bundle.series if s.name in ("DOS up", "DOS down")]
        assert len(total_series) == 2

        up_series = next(s for s in total_series if s.name == "DOS up")
        down_series = next(s for s in total_series if s.name == "DOS down")

        # Up should be positive (unchanged)
        np.testing.assert_array_almost_equal(up_series.y, up)
        # Down should be flipped to negative
        np.testing.assert_array_almost_equal(down_series.y, -down)


class TestPDOSSeries:
    """PDOS series emission as individual Series1D entries."""

    def test_pdos_emits_per_atom_orbital_series(self):
        energies = np.linspace(-5, 5, 30)
        total_dos = np.abs(np.sin(energies))
        n_atoms, n_orbitals = 2, 3
        pdos = np.random.default_rng(42).random((n_atoms, 30, n_orbitals))
        atom_labels = ["Ti_1", "O_1"]
        orbital_labels = ["s", "px", "py"]

        dos = DOS(
            meta=_make_meta(),
            energies=energies,
            total_dos=total_dos,
            pdos=pdos,
            atom_labels=atom_labels,
            orbital_labels=orbital_labels,
        )
        bundle = dos.to_primitives()

        # 1 total + 2*3 PDOS = 7
        assert len(bundle.series) == 7

        pdos_names = [s.name for s in bundle.series if s.name != "Total DOS"]
        assert "Ti_1 s" in pdos_names
        assert "Ti_1 px" in pdos_names
        assert "Ti_1 py" in pdos_names
        assert "O_1 s" in pdos_names
        assert "O_1 px" in pdos_names
        assert "O_1 py" in pdos_names

    def test_pdos_series_name_pattern(self):
        """Series names follow '{atom_label} {orbital_label}' pattern."""
        energies = np.linspace(-5, 5, 20)
        total_dos = np.ones(20)
        pdos = np.ones((1, 20, 2))
        atom_labels = ["Sr_1"]
        orbital_labels = ["3d", "4s"]

        dos = DOS(
            meta=_make_meta(),
            energies=energies,
            total_dos=total_dos,
            pdos=pdos,
            atom_labels=atom_labels,
            orbital_labels=orbital_labels,
        )
        bundle = dos.to_primitives()
        names = [s.name for s in bundle.series]
        assert "Sr_1 3d" in names
        assert "Sr_1 4s" in names

    def test_pdos_default_labels_when_none(self):
        """When atom_labels/orbital_labels are None, use fallback names."""
        energies = np.linspace(-5, 5, 20)
        total_dos = np.ones(20)
        pdos = np.ones((2, 20, 2))

        dos = DOS(
            meta=_make_meta(),
            energies=energies,
            total_dos=total_dos,
            pdos=pdos,
        )
        bundle = dos.to_primitives()
        names = [s.name for s in bundle.series]
        assert "atom_0 orb_0" in names
        assert "atom_1 orb_1" in names

    def test_pdos_y_values_correct(self):
        """PDOS series y-values match the pdos array."""
        energies = np.linspace(-5, 5, 10)
        total_dos = np.ones(10)
        pdos = np.random.default_rng(99).random((1, 10, 1))

        dos = DOS(
            meta=_make_meta(),
            energies=energies,
            total_dos=total_dos,
            pdos=pdos,
            atom_labels=["Fe_1"],
            orbital_labels=["d"],
        )
        bundle = dos.to_primitives()
        pdos_series = next(s for s in bundle.series if s.name == "Fe_1 d")
        np.testing.assert_array_almost_equal(pdos_series.y, pdos[0, :, 0])

    def test_pdos_spin_polarized_series(self):
        """Spin-polarized DOS with PDOS emits both total (flipped down) and PDOS series."""
        energies = np.linspace(-5, 5, 20)
        up = np.ones(20)
        down = np.ones(20) * 0.5
        total_dos = np.stack([up, down])
        pdos = np.ones((1, 20, 1)) * 0.3

        dos = DOS(
            meta=_make_meta(),
            energies=energies,
            total_dos=total_dos,
            pdos=pdos,
            atom_labels=["Ni_1"],
            orbital_labels=["3d"],
        )
        bundle = dos.to_primitives()

        # 2 total (up, down) + 1 PDOS = 3
        assert len(bundle.series) == 3

        down_series = next(s for s in bundle.series if s.name == "DOS down")
        np.testing.assert_array_almost_equal(down_series.y, -down)

        pdos_series = next(s for s in bundle.series if s.name == "Ni_1 3d")
        np.testing.assert_array_almost_equal(pdos_series.y, np.ones(20) * 0.3)

    def test_no_pdos_no_extra_series(self):
        """When pdos is None, only total DOS series are emitted."""
        energies = np.linspace(-5, 5, 20)
        total_dos = np.ones(20)
        dos = DOS(meta=_make_meta(), energies=energies, total_dos=total_dos)
        bundle = dos.to_primitives()
        assert len(bundle.series) == 1

    def test_pdos_still_in_arrays(self):
        """PDOS raw array is still present in bundle.arrays for advanced consumers."""
        energies = np.linspace(-5, 5, 20)
        total_dos = np.ones(20)
        pdos = np.ones((2, 20, 3))

        dos = DOS(
            meta=_make_meta(),
            energies=energies,
            total_dos=total_dos,
            pdos=pdos,
            atom_labels=["A_1", "B_1"],
            orbital_labels=["s", "p", "d"],
        )
        bundle = dos.to_primitives()
        assert "pdos" in bundle.arrays
        np.testing.assert_array_almost_equal(bundle.arrays["pdos"], pdos)
