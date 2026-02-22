"""Tests for CP2K DOS parser/provider using real CP2K fixture output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.dos import DOS
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.cp2k.parsers.dos import CP2KDOSProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_cp2k_dos"


def test_can_parse_true_when_pdos_exists() -> None:
    provider = CP2KDOSProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_pdos(tmp_path: Path) -> None:
    provider = CP2KDOSProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_dos() -> None:
    provider = CP2KDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["dos"],
        engine_name="cp2k",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert isinstance(dos, DOS)
    assert dos.meta.object_type == "dos"
    assert dos.meta.engine_name == "cp2k"


def test_energies_count() -> None:
    provider = CP2KDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert len(dos.energies) == 8


def test_fermi_energy_from_out() -> None:
    provider = CP2KDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert dos.fermi_energy == pytest.approx(7.715, abs=0.1)


def test_pdos_shape() -> None:
    provider = CP2KDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    if dos.pdos is not None:
        assert dos.pdos.shape == (1, 8, 9)


def test_pdos_atom_labels() -> None:
    provider = CP2KDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    if dos.atom_labels is not None:
        assert dos.atom_labels == ["Si_1"]


def test_pdos_orbital_labels() -> None:
    provider = CP2KDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    if dos.orbital_labels is not None:
        assert dos.orbital_labels == ["s", "py", "pz", "px", "d-2", "d-1", "d0", "d+1", "d+2"]


def test_to_primitives_valid() -> None:
    provider = CP2KDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    canonical = dos.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "dos"
    assert canonical.render_meta.axis_labels["x"] == "Energy"
    assert canonical.render_meta.axis_labels["y"] == "DOS"
    assert canonical.provenance_meta.engine_name == "cp2k"
    assert "energies" in canonical.arrays
    assert "total_dos" in canonical.arrays

    sha_one = compute_canonical_sha(canonical)
    sha_two = compute_canonical_sha(dos.to_primitives())
    assert len(sha_one) == 64
    assert sha_one == sha_two

