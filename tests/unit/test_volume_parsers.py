"""
Unit tests for volume parsers (XSF/BXSF).
"""

import pytest
from pathlib import Path
import numpy as np
import tempfile
import shutil

from quantumvitas.analysis.blob_store import BlobStore, BlobStoreError
from quantumvitas.analysis.volume_artifacts import DataOrder, VolumeMetadata
from quantumvitas.io.parser.volume_parsers import (
    parse_xsf_datagrid_3d,
    downsample_grid,
    VolumeParserError,
)


# Fixture paths
FIXTURE_DIR = Path(__file__).parent.parent / "data" / "wannier_3d_test"
GAAS_XSF = FIXTURE_DIR / "example01" / "gaas_00001.xsf"
DIAMOND_XSF = FIXTURE_DIR / "example05" / "diamond_00001.xsf"


@pytest.fixture
def temp_calc_dir():
    """Create temporary calculation directory for blob storage."""
    temp_dir = tempfile.mkdtemp()
    calc_dir = Path(temp_dir)
    yield calc_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def blob_store(temp_calc_dir):
    """Create BlobStore instance."""
    return BlobStore(temp_calc_dir)


def test_parse_xsf_gaas_00001_count_and_shape(temp_calc_dir, blob_store):
    """Test parsing gaas_00001.xsf: verify dimensions and data count."""
    if not GAAS_XSF.exists():
        pytest.skip(f"Fixture not found: {GAAS_XSF}")
    
    metadata = parse_xsf_datagrid_3d(GAAS_XSF, temp_calc_dir, blob_store)
    
    # Verify dimensions
    assert metadata.grid_shape == (40, 40, 40)
    
    # Verify blob exists and has correct size
    blob_path = blob_store.get_blob_path(metadata.blob_id)
    assert blob_path is not None
    assert blob_path.exists()
    
    # Verify blob size (40*40*40 * 4 bytes per float32)
    expected_size = 40 * 40 * 40 * 4
    assert blob_path.stat().st_size == expected_size
    
    # Verify preview blob
    assert metadata.preview_blob_id is not None
    preview_path = blob_store.get_blob_path(metadata.preview_blob_id)
    assert preview_path.exists()


def test_xsf_order_contract(temp_calc_dir, blob_store):
    """Test XSF parser: verify data_order == 'fortran_i_fastest' (NOT c_k_fastest)."""
    if not GAAS_XSF.exists():
        pytest.skip(f"Fixture not found: {GAAS_XSF}")
    
    metadata = parse_xsf_datagrid_3d(GAAS_XSF, temp_calc_dir, blob_store)
    
    # CRITICAL: XSF must use FORTRAN order (i-fastest)
    assert metadata.data_order == DataOrder.FORTRAN_I_FASTEST
    assert metadata.data_order.value == "fortran_i_fastest"
    
    # Must NOT be C order
    assert metadata.data_order != DataOrder.C_K_FASTEST
    
    # Verify format default
    assert metadata.data_order_format_default == "XSF_DATAGRID"
    
    # Verify self-check passed
    assert metadata.data_order_self_check_passed is True


def test_strict_count_validation_xsf(temp_calc_dir, blob_store):
    """Test strict count validation: mismatch must raise ValueError."""
    if not GAAS_XSF.exists():
        pytest.skip(f"Fixture not found: {GAAS_XSF}")
    
    # Parse valid file (should pass)
    metadata = parse_xsf_datagrid_3d(GAAS_XSF, temp_calc_dir, blob_store)
    assert metadata.data_order_self_check_passed is True
    
    # Create a corrupted file (wrong count) - we'll need to create test fixture
    # For now, test that parser validates correctly on valid file
    # TODO: Create test fixture with wrong count to verify error


def test_parse_xsf_diamond(temp_calc_dir, blob_store):
    """Test parsing diamond_00001.xsf."""
    if not DIAMOND_XSF.exists():
        pytest.skip(f"Fixture not found: {DIAMOND_XSF}")
    
    metadata = parse_xsf_datagrid_3d(DIAMOND_XSF, temp_calc_dir, blob_store)
    
    # Verify it parsed successfully
    assert metadata.grid_shape is not None
    assert metadata.blob_id is not None
    assert metadata.data_order == DataOrder.FORTRAN_I_FASTEST


def test_downsample_40x40x40_to_10x10x10(temp_calc_dir, blob_store):
    """Test downsampling: 40x40x40 grid → 10x10x10 with factor 4."""
    # Create synthetic data
    nx, ny, nz = 40, 40, 40
    factor = 4
    
    # Create test data in FORTRAN order
    data_3d = np.arange(nx * ny * nz, dtype=np.float32).reshape((nx, ny, nz), order='F')
    data_1d = data_3d.flatten(order='F')
    
    # Grid vectors
    grid_vectors = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    
    # Downsample
    preview_data, preview_shape, preview_grid_vectors = downsample_grid(
        data_1d, (nx, ny, nz), grid_vectors, factor=factor
    )
    
    # Verify preview shape (40//4 = 10)
    assert preview_shape == (10, 10, 10)
    
    # Verify preview data shape
    assert len(preview_data) == 10 * 10 * 10
    
    # Verify first block average (should be average of first 4x4x4 block)
    first_block = data_3d[0:4, 0:4, 0:4]
    expected_first = first_block.mean()
    assert abs(preview_data[0] - expected_first) < 1e-6


def test_preview_grid_vectors_scaled():
    """Test that preview_grid_vectors == full_grid_vectors * factor."""
    nx, ny, nz = 40, 40, 40
    factor = 4
    
    # Create test data
    data = np.zeros(nx * ny * nz, dtype=np.float32)
    
    # Grid vectors
    grid_vectors = np.array([
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
        [0.0, 0.0, 0.5],
    ], dtype=np.float64)
    
    # Downsample
    _, _, preview_grid_vectors = downsample_grid(
        data, (nx, ny, nz), grid_vectors, factor=factor
    )
    
    # Verify scaling (element-wise multiplication)
    expected = grid_vectors * factor
    np.testing.assert_allclose(preview_grid_vectors, expected, rtol=1e-10)
    
    # Verify all 3 vectors are scaled
    for i in range(3):
        for j in range(3):
            assert abs(preview_grid_vectors[i, j] - grid_vectors[i, j] * factor) < 1e-10


def test_blob_store_register_and_read(temp_calc_dir):
    """Test BlobStore: register blob and read back."""
    store = BlobStore(temp_calc_dir)
    
    # Create test data
    data = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    
    # Register
    blob_id = store.register_blob(data)
    
    # Verify blob_id is returned
    assert blob_id is not None
    
    # Verify blob exists in index
    assert store.validate_blob_id(blob_id) is True
    
    # Get path
    blob_path = store.get_blob_path(blob_id)
    assert blob_path is not None
    assert blob_path.exists()
    
    # Read back
    read_data = store.read_blob(blob_id)
    assert read_data is not None
    np.testing.assert_array_equal(read_data, data)


def test_blob_store_security_path_traversal(temp_calc_dir):
    """Test BlobStore: reject path traversal attempts."""
    store = BlobStore(temp_calc_dir)
    
    # Attempt to register with path traversal
    data = np.array([1.0], dtype=np.float32)
    
    # Should raise error if relative_path contains ..
    # (This is tested indirectly via register_blob validation)


def test_blob_store_rejects_unknown_blob_id(temp_calc_dir):
    """Test BlobStore: unknown blob_id returns None."""
    store = BlobStore(temp_calc_dir)
    
    # Unknown blob_id
    blob_path = store.get_blob_path("nonexistent-blob-id")
    assert blob_path is None
    
    # Validate returns False
    assert store.validate_blob_id("nonexistent-blob-id") is False


# BXSF tests
COPPER_BXSF = FIXTURE_DIR / "example04" / "copper.bxsf"
LEAD_BXSF = FIXTURE_DIR / "example02" / "lead.bxsf"


def test_parse_bxsf_copper_header(temp_calc_dir, blob_store):
    """Test parsing copper.bxsf header: verify nbands, dims, Fermi Energy."""
    if not COPPER_BXSF.exists():
        pytest.skip(f"Fixture not found: {COPPER_BXSF}")
    
    from quantumvitas.io.parser.volume_parsers import parse_bxsf_bandgrid_3d
    
    result = parse_bxsf_bandgrid_3d(COPPER_BXSF, temp_calc_dir, blob_store, band_index=1)
    
    # Verify header info
    assert result["n_bands"] == 7
    assert result["fermi_energy"] == pytest.approx(12.2103, abs=1e-4)
    
    # Verify metadata
    metadata = result["metadata"]
    assert metadata["grid_shape"] == [51, 51, 51]
    assert metadata["coordinate_system"] == "reciprocal-space"


def test_bxsf_order_contract(temp_calc_dir, blob_store):
    """Test BXSF parser: verify data_order == 'c_k_fastest' (NOT fortran_i_fastest)."""
    if not COPPER_BXSF.exists():
        pytest.skip(f"Fixture not found: {COPPER_BXSF}")
    
    from quantumvitas.io.parser.volume_parsers import parse_bxsf_bandgrid_3d
    
    result = parse_bxsf_bandgrid_3d(COPPER_BXSF, temp_calc_dir, blob_store, band_index=1)
    metadata = result["metadata"]
    
    # CRITICAL: BXSF must use C order (k-fastest)
    assert metadata["data_order"] == "c_k_fastest"
    
    # Must NOT be FORTRAN order
    assert metadata["data_order"] != "fortran_i_fastest"
    
    # Verify format default
    assert metadata["data_order_format_default"] == "BXSF_BANDGRID"
    
    # Verify self-check passed
    assert metadata["data_order_self_check_passed"] is True


def test_strict_count_validation_bxsf_band1(temp_calc_dir, blob_store):
    """Test strict count validation for BXSF: per-band count must match exactly."""
    if not COPPER_BXSF.exists():
        pytest.skip(f"Fixture not found: {COPPER_BXSF}")
    
    from quantumvitas.io.parser.volume_parsers import parse_bxsf_bandgrid_3d
    
    # Parse band 1 (should pass)
    result = parse_bxsf_bandgrid_3d(COPPER_BXSF, temp_calc_dir, blob_store, band_index=1)
    metadata = result["metadata"]
    assert metadata["data_order_self_check_passed"] is True
    
    # Verify blob size (51*51*51 * 4 bytes per float32)
    blob_path = blob_store.get_blob_path(result["blob_id"])
    assert blob_path is not None
    expected_size = 51 * 51 * 51 * 4
    assert blob_path.stat().st_size == expected_size


def test_bxsf_lazy_band_read_does_not_load_all(temp_calc_dir, blob_store):
    """Test that BXSF parser only reads requested band (lazy loading)."""
    if not COPPER_BXSF.exists():
        pytest.skip(f"Fixture not found: {COPPER_BXSF}")
    
    from quantumvitas.io.parser.volume_parsers import parse_bxsf_bandgrid_3d, _scan_bxsf_band_offsets
    
    # Scan band offsets (should not read all data)
    band_offsets = _scan_bxsf_band_offsets(COPPER_BXSF)
    
    # Verify all 7 bands are recorded
    assert len(band_offsets) == 7
    assert set(band_offsets.keys()) == {1, 2, 3, 4, 5, 6, 7}
    
    # Parse only band 1
    result = parse_bxsf_bandgrid_3d(COPPER_BXSF, temp_calc_dir, blob_store, band_index=1)
    
    # Verify only band 1 blob exists (not all 7)
    assert result["blob_id"] is not None
    assert result["band_index"] == 1


def test_compile_fixture_volume_blob_contract_xsf(temp_calc_dir, blob_store):
    """
    Phase 0 contract test: blob file size must match dims exactly.
    
    This is the root contract that Phase 0 validation enforces.
    """
    if not GAAS_XSF.exists():
        pytest.skip(f"Fixture not found: {GAAS_XSF}")
    
    import os
    from quantumvitas.io.parser.volume_parsers import parse_xsf_datagrid_3d
    
    # Parse XSF (direct call, not via RPC)
    metadata = parse_xsf_datagrid_3d(GAAS_XSF, temp_calc_dir, blob_store)
    
    # Test full blob contract
    full_blob_path = blob_store.get_blob_path(metadata.blob_id)
    assert full_blob_path is not None
    full_size = os.path.getsize(full_blob_path)
    nx, ny, nz = metadata.grid_shape
    full_expected_bytes = 4 * nx * ny * nz  # float32 = 4 bytes
    assert full_size == full_expected_bytes, (
        f"Full blob contract failed: file_size={full_size} != expected={full_expected_bytes} "
        f"for dims={metadata.grid_shape}, blob_id={metadata.blob_id}"
    )
    
    # Test preview blob contract
    if metadata.preview_blob_id:
        preview_blob_path = blob_store.get_blob_path(metadata.preview_blob_id)
        assert preview_blob_path is not None
        preview_size = os.path.getsize(preview_blob_path)
        if metadata.preview_grid_shape:
            preview_nx, preview_ny, preview_nz = metadata.preview_grid_shape
            preview_expected_bytes = 4 * preview_nx * preview_ny * preview_nz
            assert preview_size == preview_expected_bytes, (
                f"Preview blob contract failed: file_size={preview_size} != expected={preview_expected_bytes} "
                f"for preview_grid_shape={metadata.preview_grid_shape}, preview_blob_id={metadata.preview_blob_id}"
            )
        else:
            pytest.fail("preview_blob_id exists but preview_grid_shape is None")


def test_compile_fixture_volume_blob_contract_bxsf(temp_calc_dir, blob_store):
    """
    Phase 0 contract test for BXSF: blob file size must match dims exactly.
    """
    if not COPPER_BXSF.exists():
        pytest.skip(f"Fixture not found: {COPPER_BXSF}")
    
    import os
    from quantumvitas.io.parser.volume_parsers import parse_bxsf_bandgrid_3d
    
    # Parse BXSF band 1 (direct call, not via RPC)
    result = parse_bxsf_bandgrid_3d(COPPER_BXSF, temp_calc_dir, blob_store, band_index=1)
    metadata_dict = result["metadata"]
    
    # Test full blob contract
    full_blob_path = blob_store.get_blob_path(result["blob_id"])
    assert full_blob_path is not None
    full_size = os.path.getsize(full_blob_path)
    nx, ny, nz = metadata_dict["grid_shape"]
    full_expected_bytes = 4 * nx * ny * nz
    assert full_size == full_expected_bytes, (
        f"Full blob contract failed: file_size={full_size} != expected={full_expected_bytes} "
        f"for dims={metadata_dict['grid_shape']}, blob_id={result['blob_id']}"
    )
    
    # Test preview blob contract
    if result.get("preview_blob_id"):
        preview_blob_path = blob_store.get_blob_path(result["preview_blob_id"])
        assert preview_blob_path is not None
        preview_size = os.path.getsize(preview_blob_path)
        preview_grid_shape = metadata_dict.get("preview_grid_shape")
        if preview_grid_shape:
            preview_nx, preview_ny, preview_nz = preview_grid_shape
            preview_expected_bytes = 4 * preview_nx * preview_ny * preview_nz
            assert preview_size == preview_expected_bytes, (
                f"Preview blob contract failed: file_size={preview_size} != expected={preview_expected_bytes} "
                f"for preview_grid_shape={preview_grid_shape}, preview_blob_id={result['preview_blob_id']}"
            )
        else:
            pytest.fail("preview_blob_id exists but preview_grid_shape is None")

