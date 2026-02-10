"""Tests for ABINIT DOS parser/provider using real ABINIT fixture output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.abinit.parsers.dos import ABINITDOSProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_abinit_dos"
PDOS_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_abinit_pdos"


def test_can_parse_true_when_dos_exists() -> None:
    provider = ABINITDOSProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_dos(tmp_path: Path) -> None:
    provider = ABINITDOSProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_dos() -> None:
    provider = ABINITDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["dos"],
        engine_name="abinit",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert isinstance(dos, DOS)
    assert dos.meta.object_type == "dos"
    assert dos.meta.engine_name == "abinit"


def test_energies_count() -> None:
    provider = ABINITDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert len(dos.energies) == 1201


def test_energies_in_eV() -> None:
    provider = ABINITDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert dos.energies.max() > 10.0


def test_fermi_energy_present() -> None:
    provider = ABINITDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert dos.fermi_energy is not None
    assert dos.fermi_energy == pytest.approx(5.964, abs=0.1)


def test_energy_range_spans_fermi() -> None:
    provider = ABINITDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    if dos.fermi_energy is not None:
        assert dos.energies.min() <= dos.fermi_energy <= dos.energies.max()


def test_to_primitives_valid() -> None:
    provider = ABINITDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    canonical = dos.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "dos"
    assert canonical.render_meta.axis_labels["x"] == "Energy"
    assert canonical.render_meta.axis_labels["y"] == "DOS"
    assert canonical.provenance_meta.engine_name == "abinit"
    assert "energies" in canonical.arrays
    assert "total_dos" in canonical.arrays

    sha_one = compute_canonical_sha(canonical)
    sha_two = compute_canonical_sha(dos.to_primitives())
    assert len(sha_one) == 64
    assert sha_one == sha_two


# --- PDOS tests (prtdos 3 l-projected per-atom DOS) ---


def _parse_pdos() -> DOS:
    provider = ABINITDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=PDOS_FIXTURE_DIR,
        calc_dir=PDOS_FIXTURE_DIR.parent,
        run_ulid="01RUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["dos"],
        engine_name="abinit",
        evidence_steps=[],
    )
    return provider.parse(evidence)


def test_pdos_populated_when_dos_at_exists() -> None:
    dos = _parse_pdos()
    assert dos.pdos is not None


def test_pdos_shape() -> None:
    dos = _parse_pdos()
    assert dos.pdos is not None
    n_atoms, nedos, n_orbitals = dos.pdos.shape
    assert n_atoms == 2
    assert nedos == 1801
    assert n_orbitals == 5  # s, p, d, f, g (Si PAW)


def test_pdos_atom_labels() -> None:
    dos = _parse_pdos()
    assert dos.atom_labels is not None
    assert len(dos.atom_labels) == 2
    assert dos.atom_labels == ["atom_1", "atom_2"]


def test_pdos_orbital_labels() -> None:
    dos = _parse_pdos()
    assert dos.orbital_labels is not None
    assert all(label in ["s", "p", "d", "f", "g"] for label in dos.orbital_labels)


def test_pdos_energies_in_eV() -> None:
    dos = _parse_pdos()
    # Energy range should be in eV (not Hartree: Hartree values ~0.3-0.6)
    assert dos.energies.max() > 10.0
    assert dos.energies.min() < -5.0


def test_pdos_values_non_negative() -> None:
    dos = _parse_pdos()
    assert dos.pdos is not None
    assert np.all(dos.pdos >= 0.0)


def test_pdos_to_primitives_has_pdos() -> None:
    dos = _parse_pdos()
    bundle = dos.to_primitives()
    assert "pdos" in bundle.arrays
    assert "atom_labels" in bundle.arrays
    assert "orbital_labels" in bundle.arrays

