"""Tests for QE bands analysis provider."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.band_structure import BandStructure
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.qe.parsers.bands import QEBandsProvider


REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_BANDS_DIR = REPO_ROOT / "tests" / "data" / "analysis_bands"
TEST_SCF_DIR = REPO_ROOT / "tests" / "data" / "calculation_bands" / "reference_out"


def _prepare_provider_raw_dir(tmp_path: Path) -> Path:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(TEST_BANDS_DIR / "si.bands.dat.gnu", raw_dir / "si.bands.dat.gnu")
    shutil.copy2(TEST_BANDS_DIR / "si.3_bands.pp.out", raw_dir / "si.3_bands.pp.out")
    shutil.copy2(TEST_SCF_DIR / "si.1_nscf.out", raw_dir / "si.1_nscf.out")
    return raw_dir


def _prepare_fatbands_raw_dir(tmp_path: Path) -> Path:
    """Set up raw dir with fatbands (projwfc_up) fixture files."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(TEST_BANDS_DIR / "si_fatbands.bands.dat.gnu", raw_dir / "si.bands.dat.gnu")
    shutil.copy2(TEST_BANDS_DIR / "si_fatbands.bands.pp.out", raw_dir / "si.bands.pp.out")
    shutil.copy2(TEST_BANDS_DIR / "si_fatbands.nscf.out", raw_dir / "si.nscf.out")
    shutil.copy2(TEST_BANDS_DIR / "si_bands.projwfc_up", raw_dir / "si_bands.projwfc_up")
    return raw_dir


def test_can_parse_true_when_bands_gnu_present() -> None:
    provider = QEBandsProvider()
    assert provider.can_parse(TEST_BANDS_DIR)


def test_can_parse_false_for_empty_dir(tmp_path: Path) -> None:
    provider = QEBandsProvider()
    assert provider.can_parse(tmp_path) is False


def test_parse_returns_band_structure(tmp_path: Path) -> None:
    raw_dir = _prepare_provider_raw_dir(tmp_path)
    provider = QEBandsProvider()

    evidence = EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=tmp_path,
        run_ulid="01RUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP1"],
        gen_steps=["bandspw"],
        engine_name="qe",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)

    assert isinstance(band_structure, BandStructure)
    assert band_structure.n_kpoints == 91
    assert band_structure.n_bands == 8
    assert band_structure.fermi_energy == pytest.approx(6.133, abs=1e-6)
    assert len(band_structure.high_symmetry_points) > 0


def test_parse_sets_metadata_fields(tmp_path: Path) -> None:
    raw_dir = _prepare_provider_raw_dir(tmp_path)
    provider = QEBandsProvider()

    evidence = EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=tmp_path,
        run_ulid="01RUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP1"],
        gen_steps=["bandspw"],
        engine_name="qe",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)

    meta = band_structure.meta
    assert meta.engine_name == "qe"
    assert meta.parser_name == "qe_bands"
    assert meta.object_type == "bands"
    assert meta.step_ulids == ["01STEP1"]
    assert meta.gen_steps == ["bandspw"]
    source_paths = {item.path for item in meta.source_files}
    assert "raw/si.bands.dat.gnu" in source_paths
    assert "raw/si.3_bands.pp.out" in source_paths
    assert "raw/si.1_nscf.out" in source_paths


def test_parse_to_primitives_roundtrip_json(tmp_path: Path) -> None:
    raw_dir = _prepare_provider_raw_dir(tmp_path)
    provider = QEBandsProvider()

    evidence = EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=tmp_path,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="qe",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    payload = band_structure.to_primitives().to_dict()
    restored = json.loads(json.dumps(payload))

    assert restored["bundle_kind"] == "canonical"
    assert restored["object_type"] == "bands"
    assert "render_meta" in restored
    assert "provenance_meta" in restored


def test_provider_is_deterministic_for_identical_input(tmp_path: Path) -> None:
    raw_dir = _prepare_provider_raw_dir(tmp_path)
    provider = QEBandsProvider()

    evidence = EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=tmp_path,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="qe",
        evidence_steps=[],
    )
    first = provider.parse(evidence).to_primitives().to_dict()
    second = provider.parse(evidence).to_primitives().to_dict()

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# --- Fatbands (projwfc_up) tests ---


def _parse_fatbands(tmp_path: Path) -> BandStructure:
    raw_dir = _prepare_fatbands_raw_dir(tmp_path)
    provider = QEBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=tmp_path,
        run_ulid="01RUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP1"],
        gen_steps=["bandspw"],
        engine_name="qe",
        evidence_steps=[],
    )
    return provider.parse(evidence)


def test_projections_populated_when_projwfc_up_exists(tmp_path: Path) -> None:
    bs = _parse_fatbands(tmp_path)
    assert bs.projections is not None


def test_projections_shape(tmp_path: Path) -> None:
    bs = _parse_fatbands(tmp_path)
    assert bs.projections is not None
    assert bs.projections.shape == (bs.n_kpoints, bs.n_bands, 2, 2)
    assert bs.n_kpoints == 41
    assert bs.n_bands == 8


def test_projection_labels_atoms(tmp_path: Path) -> None:
    bs = _parse_fatbands(tmp_path)
    assert bs.projection_labels is not None
    atoms = bs.projection_labels["atoms"]
    assert atoms == ["Si_1", "Si_2"]


def test_projection_labels_orbitals(tmp_path: Path) -> None:
    bs = _parse_fatbands(tmp_path)
    assert bs.projection_labels is not None
    orbitals = bs.projection_labels["orbitals"]
    assert orbitals == ["s", "p"]


def test_projections_values_reasonable(tmp_path: Path) -> None:
    bs = _parse_fatbands(tmp_path)
    assert bs.projections is not None
    assert np.all(bs.projections >= 0.0)
    assert np.all(bs.projections <= 1.0)
    # Sum of projections per band should be close to 1 (within atomic spheres)
    band_sums = bs.projections.sum(axis=(2, 3))  # (n_kpoints, n_bands)
    assert np.all(band_sums <= 1.5)  # generous upper bound


def test_to_primitives_has_projections(tmp_path: Path) -> None:
    bs = _parse_fatbands(tmp_path)
    bundle = bs.to_primitives()
    assert "projections" in bundle.arrays
    assert "projection_labels" in bundle.arrays


def test_to_primitives_fatband_hint(tmp_path: Path) -> None:
    bs = _parse_fatbands(tmp_path)
    bundle = bs.to_primitives()
    assert bundle.render_meta.extra.get("fatband_display_hint") == "width"
    assert bundle.render_meta.extra.get("has_projections") is True
