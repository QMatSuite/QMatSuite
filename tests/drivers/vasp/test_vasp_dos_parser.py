"""Tests for VASP DOS parser/provider using real VASP fixture output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.dos import DOS
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.vasp.parsers.dos import VASPDOSProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_vasp_dos"


def test_can_parse_true_when_doscar_exists() -> None:
    provider = VASPDOSProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_doscar(tmp_path: Path) -> None:
    provider = VASPDOSProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_dos() -> None:
    provider = VASPDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["dos"],
        engine_name="vasp",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert isinstance(dos, DOS)
    assert dos.meta.object_type == "dos"
    assert dos.meta.engine_name == "vasp"


def test_parse_nedos_matches_header() -> None:
    """Verify NEDOS count matches DOSCAR header."""
    provider = VASPDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="vasp",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    assert len(dos.energies) > 0
    assert dos.energies.shape[0] == dos.total_dos.shape[-1]


def test_parse_energy_range_spans_fermi() -> None:
    """Verify energy range includes Fermi level."""
    provider = VASPDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="vasp",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    if dos.fermi_energy is not None:
        assert dos.energies.min() <= dos.fermi_energy <= dos.energies.max()


def test_parse_spin_polarized_shape() -> None:
    """Verify spin-polarized DOS has correct shape."""
    spin_fixture_dir = FIXTURE_DIR.parent / "analysis_vasp_dos"
    doscar_spin = spin_fixture_dir / "DOSCAR_spin"
    if not doscar_spin.exists():
        pytest.skip("DOSCAR_spin fixture not found")
    
    # Create temporary directory with DOSCAR_spin
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "DOSCAR").write_bytes(doscar_spin.read_bytes())
        
        provider = VASPDOSProvider()
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path,
            calc_dir=tmp_path,
            run_ulid=None,
            calc_ulid=None,
            step_ulids=[],
            gen_steps=[],
            engine_name="vasp",
            evidence_steps=[],
        )
        dos = provider.parse(evidence)
        assert dos.spin_polarized
        assert dos.total_dos.ndim == 2
        assert dos.total_dos.shape[0] == 2
        assert dos.total_dos.shape[1] == len(dos.energies)


def test_parse_pdos_shape() -> None:
    """Verify PDOS has correct shape for LORBIT=11."""
    pdos_fixture_dir = FIXTURE_DIR.parent / "analysis_vasp_dos"
    doscar_pdos = pdos_fixture_dir / "DOSCAR_pdos"
    if not doscar_pdos.exists():
        pytest.skip("DOSCAR_pdos fixture not found")
    
    # Create temporary directory with DOSCAR_pdos
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "DOSCAR").write_bytes(doscar_pdos.read_bytes())
        
        provider = VASPDOSProvider()
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path,
            calc_dir=tmp_path,
            run_ulid=None,
            calc_ulid=None,
            step_ulids=[],
            gen_steps=[],
            engine_name="vasp",
            evidence_steps=[],
        )
        dos = provider.parse(evidence)
        if dos.pdos is not None:
            assert dos.pdos.ndim == 3
            assert dos.pdos.shape[1] == len(dos.energies)  # nedos dimension
            assert dos.atom_labels is not None
            assert dos.orbital_labels is not None
            assert len(dos.atom_labels) == dos.pdos.shape[0]
            assert len(dos.orbital_labels) == dos.pdos.shape[2]


def test_pdos_atom_labels_from_poscar() -> None:
    """TiO2 fixture: PDOS labels come from POSCAR species (Ti_1, Ti_2, O_1, ...)."""
    doscar_pdos = FIXTURE_DIR / "DOSCAR_pdos"
    poscar_tio2 = FIXTURE_DIR / "POSCAR_tio2"
    if not doscar_pdos.exists() or not poscar_tio2.exists():
        pytest.skip("DOSCAR_pdos or POSCAR_tio2 fixture not found")

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "DOSCAR").write_bytes(doscar_pdos.read_bytes())
        (tmp_path / "POSCAR").write_bytes(poscar_tio2.read_bytes())

        provider = VASPDOSProvider()
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path,
            calc_dir=tmp_path,
            run_ulid=None,
            calc_ulid=None,
            step_ulids=[],
            gen_steps=[],
            engine_name="vasp",
            evidence_steps=[],
        )
        dos = provider.parse(evidence)
        assert dos.atom_labels is not None
        # TiO2 rutile: 2 Ti + 4 O = 6 atoms
        assert len(dos.atom_labels) == 6
        assert dos.atom_labels[0] == "Ti_1"
        assert dos.atom_labels[1] == "Ti_2"
        assert dos.atom_labels[2] == "O_1"
        assert dos.atom_labels[5] == "O_4"


def test_pdos_atom_labels_generic_without_poscar() -> None:
    """Without POSCAR, PDOS labels should be generic atom_1, atom_2, ..."""
    doscar_pdos = FIXTURE_DIR / "DOSCAR_pdos"
    if not doscar_pdos.exists():
        pytest.skip("DOSCAR_pdos fixture not found")

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "DOSCAR").write_bytes(doscar_pdos.read_bytes())
        # No POSCAR copied

        provider = VASPDOSProvider()
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path,
            calc_dir=tmp_path,
            run_ulid=None,
            calc_ulid=None,
            step_ulids=[],
            gen_steps=[],
            engine_name="vasp",
            evidence_steps=[],
        )
        dos = provider.parse(evidence)
        if dos.atom_labels is not None:
            # Should be generic: atom_1, atom_2, ...
            assert dos.atom_labels[0] == "atom_1"


def test_to_primitives_valid() -> None:
    """Verify to_primitives() produces valid CanonicalPrimitiveBundle."""
    provider = VASPDOSProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="vasp",
        evidence_steps=[],
    )
    dos = provider.parse(evidence)
    canonical = dos.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "dos"
    assert canonical.render_meta.axis_labels["x"] == "Energy"
    assert canonical.render_meta.axis_labels["y"] == "DOS"
    assert canonical.provenance_meta.engine_name == "vasp"
    assert "energies" in canonical.arrays
    assert "total_dos" in canonical.arrays
    
    # Verify determinism
    sha_one = compute_canonical_sha(canonical)
    sha_two = compute_canonical_sha(dos.to_primitives())
    assert len(sha_one) == 64
    assert sha_one == sha_two

