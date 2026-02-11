"""Tests for VASP field3d parser/provider."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.field3d import Field3D
from quantumvitas.drivers.vasp.parsers.field3d import VASPField3DProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_vasp_field3d"


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


def test_can_parse_true_when_chgcar_exists() -> None:
    provider = VASPField3DProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_nothing(tmp_path: Path) -> None:
    provider = VASPField3DProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_field3d() -> None:
    provider = VASPField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Field3D)
    assert result.meta.object_type == "field3d"
    assert result.meta.engine_name == "vasp"


def test_parse_grid_shape() -> None:
    """Verify 4x4x4 grid shape from fixture."""
    provider = VASPField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.grid_shape == (4, 4, 4)
    assert len(result.grid_data) == 64


def test_parse_data_order() -> None:
    """Verify FORTRAN i-fastest data order metadata."""
    provider = VASPField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    vol_meta = canonical.render_meta.extra["volume_metadata"]
    assert vol_meta["data_order"] == "fortran_i_fastest"


def test_parse_field_kind_chgcar() -> None:
    """Verify field_kind is charge_density for CHGCAR."""
    provider = VASPField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.field_kind == "charge_density"


def test_parse_field_kind_locpot() -> None:
    """Verify field_kind is potential when LOCPOT is the primary file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Only copy LOCPOT (no CHGCAR)
        shutil.copy(FIXTURE_DIR / "LOCPOT", tmp_path / "LOCPOT")

        provider = VASPField3DProvider()
        result = provider.parse(_make_evidence(tmp_path))
        assert result.field_kind == "potential"


def test_parse_discovered_files() -> None:
    """Verify both CHGCAR and LOCPOT are discovered."""
    provider = VASPField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert "CHGCAR" in result.discovered_files
    assert "LOCPOT" in result.discovered_files


def test_to_primitives_valid() -> None:
    """Verify to_primitives() produces valid CanonicalPrimitiveBundle."""
    provider = VASPField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "field3d"
    assert canonical.provenance_meta.engine_name == "vasp"
    assert "grid_data" not in canonical.arrays  # primitive-by-reference: no full grid
    assert "preview_data" in canonical.arrays
    assert "lattice" in canonical.arrays

    # Verify volume metadata
    vol_meta = canonical.render_meta.extra["volume_metadata"]
    assert vol_meta["grid_shape"] == [4, 4, 4]
    assert vol_meta["coordinate_system"] == "real-space"
    assert vol_meta["value_min"] is not None
    assert vol_meta["value_max"] is not None
    assert vol_meta["value_mean"] is not None


def test_preview_dimensions() -> None:
    """Verify preview downsampling produces correct shape."""
    provider = VASPField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    vol_meta = canonical.render_meta.extra["volume_metadata"]
    # 4x4x4 with factor=4 -> 1x1x1
    assert vol_meta["preview_grid_shape"] == [1, 1, 1]
    assert len(canonical.arrays["preview_data"]) == 1


def test_grid_data_not_in_bundle() -> None:
    """Gate: grid_data must be absent from bundle but present on Field3D."""
    provider = VASPField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    # Full grid is on the object
    assert result.grid_data is not None
    assert len(result.grid_data) == 64
    # But NOT in the canonical bundle
    canonical = result.to_primitives()
    assert "grid_data" not in canonical.arrays


def test_volume_metadata_grid_info() -> None:
    """Verify grid metadata (nbytes/dtype/available) in volume_metadata."""
    provider = VASPField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    vol_meta = canonical.render_meta.extra["volume_metadata"]
    assert vol_meta["grid_data_available"] is True
    assert vol_meta["grid_data_dtype"] == "float64"
    assert vol_meta["grid_data_nbytes"] == 64 * 8  # 64 floats * 8 bytes


def test_sha_deterministic() -> None:
    """Verify canonical SHA is deterministic."""
    provider = VASPField3DProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
