"""Tests for ABINIT field3d parser/provider."""
from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.field3d import Field3D
from qmatsuite.drivers.abinit.parsers.field3d import ABINITField3DProvider

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_abinit_field3d"


def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["scf"],
        engine_name="abinit",
        evidence_steps=[],
    )


def test_can_parse_true() -> None:
    provider = ABINITField3DProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false(tmp_path: Path) -> None:
    provider = ABINITField3DProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_field3d() -> None:
    provider = ABINITField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Field3D)
    assert result.meta.object_type == "field3d"
    assert result.meta.engine_name == "abinit"


def test_parse_grid_shape() -> None:
    provider = ABINITField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.grid_shape == (20, 20, 20)
    assert len(result.grid_data) == 8000


def test_parse_field_kind() -> None:
    provider = ABINITField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.field_kind == "charge_density"


def test_to_primitives_valid() -> None:
    provider = ABINITField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "field3d"
    assert "grid_data" not in canonical.arrays
    assert "preview_data" in canonical.arrays


def test_grid_data_not_in_bundle() -> None:
    provider = ABINITField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert "grid_data" not in canonical.arrays


def test_sha_deterministic() -> None:
    provider = ABINITField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert sha1 == sha2
