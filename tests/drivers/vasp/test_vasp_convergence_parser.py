"""Tests for VASP convergence parser/provider."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.convergence import Convergence
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.vasp.parsers.convergence import VASPConvergenceProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_vasp_convergence"


def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["scf"],
        engine_name="vasp",
        evidence_steps=[],
    )


def test_can_parse_true_when_oszicar_exists() -> None:
    provider = VASPConvergenceProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_oszicar(tmp_path: Path) -> None:
    provider = VASPConvergenceProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_convergence() -> None:
    provider = VASPConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Convergence)
    assert result.meta.object_type == "convergence"
    assert result.meta.engine_name == "vasp"


def test_parse_scf_count() -> None:
    """Verify correct number of SCF steps parsed."""
    provider = VASPConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    # 11 SCF steps in ionic step 1, 5 each in steps 2 and 3 = 21 total
    assert len(result.scf_step) == 21
    assert len(result.scf_energy) == 21
    assert len(result.scf_de) == 21


def test_parse_ionic_count() -> None:
    """Verify correct number of ionic steps parsed."""
    provider = VASPConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert len(result.ionic_step) == 3
    assert len(result.ionic_energy) == 3
    assert result.n_ionic_steps == 3


def test_parse_algorithm_detected() -> None:
    """Verify algorithm detection from SCF lines."""
    provider = VASPConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.algorithm == "DAV"


def test_parse_converged_flag() -> None:
    """Verify converged flag based on last SCF dE."""
    provider = VASPConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    # Last SCF dE is -0.19437556E-07 which is < 1e-4
    assert result.converged is True


def test_to_primitives_valid() -> None:
    """Verify to_primitives() produces valid CanonicalPrimitiveBundle."""
    provider = VASPConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "convergence"
    assert canonical.provenance_meta.engine_name == "vasp"
    assert "scf_energy" in canonical.arrays
    assert "ionic_energy" in canonical.arrays
    assert canonical.render_meta.extra["converged"] is True
    assert canonical.render_meta.extra["algorithm"] == "DAV"


def test_sha_deterministic() -> None:
    """Verify canonical SHA is deterministic."""
    provider = VASPConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2


def test_parse_md_oszicar() -> None:
    """Verify MD OSZICAR parsing with T= lines."""
    md_oszicar = FIXTURE_DIR / "OSZICAR_md"
    if not md_oszicar.exists():
        pytest.skip("OSZICAR_md fixture not found")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "OSZICAR").write_bytes(md_oszicar.read_bytes())

        provider = VASPConvergenceProvider()
        result = provider.parse(_make_evidence(tmp_path))
        assert isinstance(result, Convergence)
        assert result.n_ionic_steps == 3
        assert len(result.ionic_energy) == 3
        # MD energies from E= field
        assert result.ionic_energy[0] == pytest.approx(-10.586221, abs=1e-3)
