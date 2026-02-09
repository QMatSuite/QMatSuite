"""Tests for GPAW DOS parser/provider using real GPAW fixture output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.gpaw.parsers.dos import GPAWDOSProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_gpaw_dos"


def test_can_parse_true_when_dos_json_exists() -> None:
    provider = GPAWDOSProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_dos_json(tmp_path: Path) -> None:
    provider = GPAWDOSProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_dos() -> None:
    provider = GPAWDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["dos"],
        engine_name="gpaw",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert isinstance(dos, DOS)
    assert dos.meta.object_type == "dos"
    assert dos.meta.engine_name == "gpaw"


def test_energies_count() -> None:
    provider = GPAWDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="gpaw",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert len(dos.energies) == 301


def test_fermi_energy_present() -> None:
    provider = GPAWDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="gpaw",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert dos.fermi_energy == pytest.approx(5.358, abs=0.01)


def test_energy_range_spans_fermi() -> None:
    provider = GPAWDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="gpaw",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    if dos.fermi_energy is not None:
        assert dos.energies.min() <= dos.fermi_energy <= dos.energies.max()


def test_total_dos_nonnegative() -> None:
    provider = GPAWDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="gpaw",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert np.all(dos.total_dos >= 0)


def test_no_pdos() -> None:
    provider = GPAWDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="gpaw",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert dos.pdos is None


def test_to_primitives_valid() -> None:
    provider = GPAWDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="gpaw",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    canonical = dos.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "dos"
    assert canonical.render_meta.axis_labels["x"] == "Energy"
    assert canonical.render_meta.axis_labels["y"] == "DOS"
    assert canonical.provenance_meta.engine_name == "gpaw"
    assert "energies" in canonical.arrays
    assert "total_dos" in canonical.arrays

    sha_one = compute_canonical_sha(canonical)
    sha_two = compute_canonical_sha(dos.to_primitives())
    assert len(sha_one) == 64
    assert sha_one == sha_two

