"""Tests for QE bands analysis provider."""

import json
import shutil
from pathlib import Path

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
