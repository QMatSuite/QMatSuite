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

