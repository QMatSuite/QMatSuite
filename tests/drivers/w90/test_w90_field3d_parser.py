"""Tests for Wannier90 field3d parser/provider."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.field3d import Field3D
from qmatsuite.drivers.w90.parsers.field3d import W90Field3DProvider

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_w90_field3d"


def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["wannier"],
        engine_name="w90",
        evidence_steps=[],
    )


def test_can_parse_true() -> None:
    provider = W90Field3DProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false(tmp_path: Path) -> None:
    provider = W90Field3DProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_field3d() -> None:
    provider = W90Field3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Field3D)
    assert result.meta.object_type == "field3d"
    assert result.meta.engine_name == "w90"


def test_parse_grid_shape() -> None:
    provider = W90Field3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.grid_shape == (54, 54, 54)
    assert len(result.grid_data) == 157464


def test_parse_field_kind() -> None:
    provider = W90Field3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.field_kind == "mlwf_density"


def test_parse_discovered_files() -> None:
    provider = W90Field3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert len(result.discovered_files) == 2
    assert "diamond_00001.xsf" in result.discovered_files
    assert "diamond_00002.xsf" in result.discovered_files


def test_to_primitives_valid() -> None:
    provider = W90Field3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "field3d"
    assert "grid_data" not in canonical.arrays
    assert "preview_data" in canonical.arrays
    assert "lattice" in canonical.arrays


def test_grid_data_not_in_bundle() -> None:
    provider = W90Field3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.grid_data is not None
    canonical = result.to_primitives()
    assert "grid_data" not in canonical.arrays


def test_sha_deterministic() -> None:
    provider = W90Field3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
