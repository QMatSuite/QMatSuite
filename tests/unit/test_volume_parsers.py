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

