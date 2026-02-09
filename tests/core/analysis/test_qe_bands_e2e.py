"""End-to-end QE bands analysis pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path

from quantumvitas.core.analysis.band_structure import BandStructure
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.orchestrator import run_post_run_analysis
from quantumvitas.core.analysis.transforms.fermi_shift import FermiShift
from quantumvitas.drivers.qe.driver import QEDriver
from quantumvitas.drivers.qe.parsers.bands import QEBandsProvider


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_qe_bands_end_to_end() -> None:
    """
    Full pipeline: QE raw artifacts -> BandStructure -> canonical -> derived transform.
    """
    raw_dir = REPO_ROOT / "tests" / "data" / "analysis_bands"
    calc_dir = raw_dir.parent

    provider = QEBandsProvider()
    assert provider.can_parse(raw_dir)

    evidence = EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=calc_dir,
        run_ulid="01RUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP1"],
        gen_steps=["bandspw"],
        engine_name="qe",
        evidence_steps=[],
    )
    band_struct = provider.parse(evidence)
    assert isinstance(band_struct, BandStructure)
    assert band_struct.meta.object_type == "bands"
    assert band_struct.n_kpoints > 0
    assert band_struct.n_bands > 0

    canonical = band_struct.to_primitives()
    assert canonical.bundle_kind == "canonical"
    assert canonical.object_type == "bands"
    assert len(canonical.render_meta.markers) > 0
    assert canonical.provenance_meta.engine_name == "qe"

    canonical2 = band_struct.to_primitives()
    assert json.dumps(canonical.to_dict(), sort_keys=True) == json.dumps(
        canonical2.to_dict(), sort_keys=True
    )

    derived = FermiShift().apply(canonical)
    assert derived.bundle_kind == "derived"
    assert len(derived.transform_chain) == 1
    assert derived.transform_chain[0].transform_name == "fermi_shift"

    bundle_json = json.dumps(canonical.to_dict())
    assert "created_at" not in bundle_json


def test_qe_bands_orchestrator_integration() -> None:
    """Kernel orchestrator wires capabilities to QE bands provider."""
    raw_dir = REPO_ROOT / "tests" / "data" / "analysis_bands"
    driver = QEDriver()
    ordered_gen_steps = [("01STEP1", "bandspw", raw_dir)]

    results = run_post_run_analysis(
        engine="qe",
        driver=driver,
        ordered_gen_steps=ordered_gen_steps,
        run_ulid="01RUN",
        calc_ulid="01CALC",
        calc_dir=raw_dir.parent,
    )

    assert len(results) >= 1
    bands_result = next(row for row in results if row["object_type"] == "bands")
    assert bands_result["canonical"].bundle_kind == "canonical"
