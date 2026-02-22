"""Tests for Siesta DOS parser/provider using real Siesta fixture output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.dos import DOS
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.siesta.parsers.dos import SiestaDOSProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_siesta_dos"


def test_can_parse_true_when_dos_exists() -> None:
    provider = SiestaDOSProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_dos(tmp_path: Path) -> None:
    provider = SiestaDOSProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_dos() -> None:
    provider = SiestaDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["dos"],
        engine_name="siesta",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert isinstance(dos, DOS)
    assert dos.meta.object_type == "dos"
    assert dos.meta.engine_name == "siesta"


def test_energies_count() -> None:
    provider = SiestaDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert len(dos.energies) == 500


def test_fermi_energy_present() -> None:
    provider = SiestaDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert dos.fermi_energy == pytest.approx(-4.487, abs=0.01)


def test_pdos_shape() -> None:
    provider = SiestaDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    if dos.pdos is not None:
        assert dos.pdos.shape == (2, 500, 3)


def test_pdos_atom_labels() -> None:
    provider = SiestaDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    if dos.atom_labels is not None:
        assert dos.atom_labels == ["Si_1", "Si_2"]


def test_pdos_orbital_labels() -> None:
    provider = SiestaDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    if dos.orbital_labels is not None:
        assert dos.orbital_labels == ["s", "p", "d"]


def test_total_dos_nonnegative() -> None:
    provider = SiestaDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert np.all(dos.total_dos >= 0)


def test_to_primitives_valid() -> None:
    provider = SiestaDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    canonical = dos.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "dos"
    assert canonical.render_meta.axis_labels["x"] == "Energy"
    assert canonical.render_meta.axis_labels["y"] == "DOS"
    assert canonical.provenance_meta.engine_name == "siesta"
    assert "energies" in canonical.arrays
    assert "total_dos" in canonical.arrays

    sha_one = compute_canonical_sha(canonical)
    sha_two = compute_canonical_sha(dos.to_primitives())
    assert len(sha_one) == 64
    assert sha_one == sha_two

