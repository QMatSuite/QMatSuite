"""
Volume file parsers for XSF and BXSF formats.

Parsers follow XCrySDen official specification:
- XSF DATAGRID_3D: FORTRAN/column-major order (i-fastest)
- BXSF BANDGRID_3D: C/row-major order (k-fastest)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from qmatsuite.analysis.blob_store import BlobStore
from qmatsuite.analysis.volume_artifacts import DataOrder, VolumeMetadata


class VolumeParserError(Exception):
    """Error in volume parsing."""
    pass


def parse_xsf_datagrid_3d(
    path: Path,
    calc_dir: Path,
    blob_store: BlobStore,
    preview_factor: int = 4,
) -> VolumeMetadata:
    """
    Parse XSF DATAGRID_3D block and create volume artifact.
    
    Supports variants:
    - BEGIN_BLOCK_DATAGRID3D / BEGIN_DATAGRID_3D
    - BEGIN_DATAGRID_3D_UNKNOWN
    
    Args:
        path: Path to XSF file
        calc_dir: Calculation directory for blob storage
        blob_store: BlobStore instance
        preview_factor: Downsampling factor for preview (default 4)
        
    Returns:
        VolumeMetadata instance
        
    Raises:
        VolumeParserError: If parsing fails or count validation fails
    """
    path = Path(path).resolve()
    if not path.exists():
        raise VolumeParserError(f"File not found: {path}")
    
    content = path.read_text()
    lines = content.splitlines()
    
    # Find DATAGRID block
    datagrid_start = None
    datagrid_variant = None
    
    for i, line in enumerate(lines):
        if "BEGIN_DATAGRID_3D_UNKNOWN" in line:
            datagrid_start = i
            datagrid_variant = "UNKNOWN"
            break
        elif "BEGIN_DATAGRID_3D" in line and "BEGIN_BLOCK_DATAGRID3D" not in line:
            datagrid_start = i
            datagrid_variant = "STANDARD"
            break
        elif "BEGIN_BLOCK_DATAGRID3D" in line:
            # Continue to find BEGIN_DATAGRID_3D inside block
            continue
    
    if datagrid_start is None:
        raise VolumeParserError("DATAGRID_3D block not found in XSF file")
    
    # Parse header (skip BEGIN line)
    header_idx = datagrid_start + 1
    if header_idx >= len(lines):
        raise VolumeParserError("DATAGRID_3D block is empty")
    
    # Skip optional label line (e.g., "3D_field")
    # Check if next line is dimensions or a label
    dim_line_idx = header_idx
    dim_line = lines[dim_line_idx].strip()
    if not re.match(r'^\s*\d+\s+\d+\s+\d+\s*$', dim_line):
        # Skip label line
        dim_line_idx += 1
        if dim_line_idx >= len(lines):
            raise VolumeParserError("DATAGRID_3D dimensions not found")
        dim_line = lines[dim_line_idx].strip()
    
    # Parse dimensions
    dim_match = re.match(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s*$', dim_line)
    if not dim_match:
        raise VolumeParserError(f"Invalid dimensions line: {dim_line}")
    nx, ny, nz = int(dim_match.group(1)), int(dim_match.group(2)), int(dim_match.group(3))
    
    # Parse origin
    origin_idx = dim_line_idx + 1
    if origin_idx >= len(lines):
        raise VolumeParserError("Origin line not found")
    origin_line = lines[origin_idx].strip()
    origin_values = re.findall(r'-?\d+\.\d+', origin_line)
    if len(origin_values) != 3:
        raise VolumeParserError(f"Invalid origin line: {origin_line}")
    origin = np.array([float(v) for v in origin_values], dtype=np.float64)
    
    # Parse grid vectors (3 lines)
    grid_vectors = np.zeros((3, 3), dtype=np.float64)
    for i in range(3):
        vec_idx = origin_idx + 1 + i
        if vec_idx >= len(lines):
            raise VolumeParserError(f"Grid vector {i+1} not found")
        vec_line = lines[vec_idx].strip()
        vec_values = re.findall(r'-?\d+\.\d+', vec_line)
        if len(vec_values) != 3:
            raise VolumeParserError(f"Invalid grid vector line {i+1}: {vec_line}")
        grid_vectors[i] = [float(v) for v in vec_values]
    
    # Data starts after grid vectors
    data_start_idx = origin_idx + 4
    
    # Find END marker
    end_idx = None
    for i in range(data_start_idx, len(lines)):
        if "END_DATAGRID_3D" in lines[i] or "END_BLOCK_DATAGRID3D" in lines[i]:
            end_idx = i
            break
    
    if end_idx is None:
        raise VolumeParserError("END_DATAGRID_3D marker not found")
    
    # Read data values (token stream)
    expected_count = nx * ny * nz
    data_values = []
    
    # Token pattern: matches floating point numbers (including scientific notation)
    token_pattern = re.compile(r'-?\d+\.\d+E[+-]\d+|-\d+\.\d+|\d+\.\d+|-?\d+\.\d+E[+-]?\d+')
    
    for i in range(data_start_idx, end_idx):
        line = lines[i]
        # Extract all tokens from line
        tokens = token_pattern.findall(line)
        data_values.extend([float(t) for t in tokens])
    
    # STRICT count validation
    actual_count = len(data_values)
    if actual_count != expected_count:
        raise VolumeParserError(
            f"Data count mismatch: expected {expected_count} values (nx={nx}*ny={ny}*nz={nz}), "
            f"got {actual_count}. Possible data_order issue or file corruption."
        )
    
    # Convert to numpy array (FORTRAN order: i-fastest)
    # Data is already in FORTRAN order from file
    data_array = np.array(data_values, dtype=np.float32)
    
    # Compute statistics
    value_min = float(data_array.min())
    value_max = float(data_array.max())
    value_mean = float(data_array.mean())
    
    # Register full blob
    blob_id = blob_store.register_blob(data_array)
    
    # Generate preview (downsample)
    preview_data, preview_shape, preview_grid_vectors = downsample_grid(
        data_array, (nx, ny, nz), grid_vectors, factor=preview_factor
    )
    preview_blob_id = blob_store.register_blob(preview_data, suffix="_preview")
    
    # Parse structure (optional, for overlay)
    structure_atoms = _parse_xsf_structure(lines)
    
    # Parse lattice vectors (from PRIMVEC)
    lattice_vectors = _parse_xsf_lattice_vectors(lines)
    
    # Create metadata
    metadata = VolumeMetadata(
        grid_shape=(nx, ny, nz),
        coordinate_system="real-space",
        origin_cart=origin,
        grid_vectors_cart=grid_vectors,
        lattice_vectors_cart=lattice_vectors,
        data_order=DataOrder.FORTRAN_I_FASTEST,
        data_order_format_default="XSF_DATAGRID",
        data_order_self_check_passed=True,
        length_units="Å",
        value_units="arbitrary",
        blob_id=blob_id,
        preview_blob_id=preview_blob_id,
        preview_downsample_factor=preview_factor,
        preview_grid_shape=preview_shape,  # Store preview dimensions
        value_min=value_min,
        value_max=value_max,
        value_mean=value_mean,
        structure_atoms=structure_atoms,
    )
    
    return metadata


def _parse_xsf_structure(lines: List[str]) -> Optional[List[Dict[str, any]]]:
    """Parse atomic structure from XSF PRIMCOORD block."""
    atoms = []
    in_primcoord = False
    
    for line in lines:
        if "PRIMCOORD" in line:
            in_primcoord = True
            # Next line is N_atoms N_dummy
            continue
        if in_primcoord:
            if not line.strip() or line.strip().startswith("#"):
                continue
            # Check if this is the atom count line
            if re.match(r'^\s*\d+\s+\d+\s*$', line.strip()):
                continue
            # Atom line: element x y z
            parts = line.split()
            if len(parts) >= 4:
                try:
                    element = parts[0]
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    atoms.append({
                        "element": element,
                        "position": [x, y, z],
                    })
                except (ValueError, IndexError):
                    break
            else:
                break
    
    return atoms if atoms else None


def _parse_xsf_lattice_vectors(lines: List[str]) -> Optional[np.ndarray]:
    """Parse lattice vectors from XSF PRIMVEC block."""
    lattice = np.zeros((3, 3), dtype=np.float64)
    in_primvec = False
    row_idx = 0
    
    for line in lines:
        if "PRIMVEC" in line:
            in_primvec = True
            continue
        if in_primvec:
            if row_idx >= 3:
                break
            values = re.findall(r'-?\d+\.\d+', line)
            if len(values) == 3:
                lattice[row_idx] = [float(v) for v in values]
                row_idx += 1
            elif line.strip() and not line.strip().startswith("#"):
                # Non-vector line, stop
                break
    
    return lattice if row_idx == 3 else None


def downsample_grid(
    data: np.ndarray,
    grid_shape: Tuple[int, int, int],
    grid_vectors_cart: np.ndarray,
    factor: int = 4,
) -> Tuple[np.ndarray, Tuple[int, int, int], np.ndarray]:
    """
    Downsample volumetric grid by block averaging.
    
    Args:
        data: 1D array in FORTRAN order (i-fastest) or C order (k-fastest)
        grid_shape: (nx, ny, nz) original shape
        grid_vectors_cart: (3, 3) grid vectors
        factor: Downsampling factor (each dimension divided by factor)
        
    Returns:
        (downsampled_data, preview_shape, preview_grid_vectors)
    """
    nx, ny, nz = grid_shape
    
    # Downsampled dimensions (floor division)
    nx_preview = nx // factor
    ny_preview = ny // factor
    nz_preview = nz // factor
    
    preview_shape = (nx_preview, ny_preview, nz_preview)
    
    # Reshape data (assuming FORTRAN order for now - data_order should be passed if needed)
    # For MVP, assume FORTRAN order
    data_3d = data.reshape(grid_shape, order='F')  # FORTRAN order
    
    # Block average
    preview_data_3d = np.zeros(preview_shape, dtype=np.float32)
    
    for i_preview in range(nx_preview):
        for j_preview in range(ny_preview):
            for k_preview in range(nz_preview):
                # Block boundaries
                i_start = i_preview * factor
                i_end = min((i_preview + 1) * factor, nx)
                j_start = j_preview * factor
                j_end = min((j_preview + 1) * factor, ny)
                k_start = k_preview * factor
                k_end = min((k_preview + 1) * factor, nz)
                
                # Average block
                block = data_3d[i_start:i_end, j_start:j_end, k_start:k_end]
                preview_data_3d[i_preview, j_preview, k_preview] = block.mean()
    
    # Flatten back to FORTRAN order
    preview_data = preview_data_3d.flatten(order='F')
    
    # Scale grid vectors
    preview_grid_vectors = grid_vectors_cart * factor
    
    return preview_data, preview_shape, preview_grid_vectors


def parse_bxsf_bandgrid_3d(
    path: Path,
    calc_dir: Path,
    blob_store: BlobStore,
    band_index: int = 1,
    preview_factor: int = 4,
) -> Dict[str, any]:
    """
    Parse BXSF BANDGRID_3D block and create Fermi surface artifact.
    
    Supports lazy band loading: scans file to record band offsets,
    then seeks to specific band data on demand.
    
    Args:
        path: Path to BXSF file
        calc_dir: Calculation directory for blob storage
        blob_store: BlobStore instance
        band_index: Band index to extract (1-indexed, default 1)
        preview_factor: Downsampling factor for preview (default 4)
        
    Returns:
        Dict with metadata and blob IDs
        
    Raises:
        VolumeParserError: If parsing fails or count validation fails
    """
    path = Path(path).resolve()
    if not path.exists():
        raise VolumeParserError(f"File not found: {path}")
    
    # Scan file for band offsets (lazy loading preparation)
    band_offsets = _scan_bxsf_band_offsets(path)
    
    if band_index not in band_offsets:
        raise VolumeParserError(f"Band {band_index} not found in BXSF file")
    
    # Parse header (Fermi Energy, grid dimensions, etc.)
    header_info = _parse_bxsf_header(path)
    
    nx, ny, nz = header_info["grid_shape"]
    nbands = header_info["nbands"]
    fermi_energy = header_info["fermi_energy"]
    origin = header_info["origin"]
    reciprocal_vectors = header_info["reciprocal_vectors"]
    
    # Read specific band data (lazy: seek to offset)
    band_data = _read_bxsf_band_data(path, band_offsets[band_index], nx, ny, nz, band_index)
    
    # STRICT count validation
    expected_count = nx * ny * nz
    actual_count = len(band_data)
    if actual_count != expected_count:
        raise VolumeParserError(
            f"Band {band_index} data count mismatch: expected {expected_count} "
            f"(nx={nx}*ny={ny}*nz={nz}), got {actual_count}. "
            f"Possible data_order issue or file corruption."
        )
    
    # Convert to numpy array (C order: k-fastest)
    data_array = np.array(band_data, dtype=np.float32)
    
    # Compute statistics
    value_min = float(data_array.min())
    value_max = float(data_array.max())
    value_mean = float(data_array.mean())
    
    # Register full blob
    blob_id = blob_store.register_blob(data_array)
    
    # Generate preview (downsample)
    # Note: BXSF uses C order, so reshape with order='C'
    preview_data, preview_shape, preview_grid_vectors = downsample_grid_c_order(
        data_array, (nx, ny, nz), reciprocal_vectors, factor=preview_factor
    )
    preview_blob_id = blob_store.register_blob(preview_data, suffix="_preview")
    
    # Create metadata
    metadata = VolumeMetadata(
        grid_shape=(nx, ny, nz),
        coordinate_system="reciprocal-space",
        origin_cart=origin,
        grid_vectors_cart=reciprocal_vectors,  # For BXSF, grid_vectors = reciprocal_vectors
        data_order=DataOrder.C_K_FASTEST,
        data_order_format_default="BXSF_BANDGRID",
        data_order_self_check_passed=True,
        length_units="1/Å",
        reciprocal_convention="2pi",  # Typical for Wannier90
        value_units="eV",
        blob_id=blob_id,
        preview_blob_id=preview_blob_id,
        preview_downsample_factor=preview_factor,
        preview_grid_shape=preview_shape,  # Store preview dimensions
        value_min=value_min,
        value_max=value_max,
        value_mean=value_mean,
    )
    
    return {
        "artifact_id": f"bxsf_band_{band_index}",
        "kind": "fermi_surface",
        "metadata": metadata.to_dict(),
        "blob_id": blob_id,
        "preview_blob_id": preview_blob_id,
        "n_bands": nbands,
        "band_indices": list(band_offsets.keys()),
        "band_index": band_index,
        "fermi_energy": fermi_energy,
        "band_offsets": band_offsets,  # For lazy loading future bands
    }


def _scan_bxsf_band_offsets(path: Path) -> Dict[int, int]:
    """
    Scan BXSF file to record file positions for each band.
    
    Returns:
        Dict mapping band_index -> file_offset (bytes)
    """
    band_offsets = {}
    
    with open(path, 'rb') as f:
        content = f.read().decode('utf-8', errors='ignore')
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            if line.strip().startswith("BAND:"):
                # Extract band number
                match = re.match(r'BAND:\s*(\d+)', line.strip())
                if match:
                    band_num = int(match.group(1))
                    # Calculate approximate offset (line start)
                    # This is approximate; for precise offset, need to count bytes
                    # For MVP, we'll use line numbers and recalculate on read
                    band_offsets[band_num] = i + 1  # Store line number (will convert to byte offset on read)
    
    return band_offsets


def _parse_bxsf_header(path: Path) -> Dict[str, any]:
    """Parse BXSF header (Fermi Energy, grid dimensions, reciprocal vectors)."""
    content = path.read_text()
    lines = content.splitlines()
    
    # Parse Fermi Energy from BEGIN_INFO
    fermi_energy = None
    in_info = False
    for line in lines:
        if "BEGIN_INFO" in line:
            in_info = True
            continue
        if "END_INFO" in line:
            in_info = False
            continue
        if in_info and "Fermi Energy" in line:
            match = re.search(r'Fermi Energy:\s*([0-9.+-E]+)', line)
            if match:
                fermi_energy = float(match.group(1))
    
    # Parse BANDGRID header
    in_bandgrid = False
    grid_shape = None
    nbands = None
    origin = None
    reciprocal_vectors = None
    
    for i, line in enumerate(lines):
        if "BEGIN_BANDGRID_3D_fermi" in line:
            in_bandgrid = True
            continue
        if in_bandgrid:
            # nbands line
            if nbands is None and re.match(r'^\s*\d+\s*$', line.strip()):
                nbands = int(line.strip())
                continue
            # grid shape line
            if grid_shape is None:
                match = re.match(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s*$', line.strip())
                if match:
                    grid_shape = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
                    continue
            # origin line
            if origin is None and re.match(r'^\s*[0-9.-]+\s+[0-9.-]+\s+[0-9.-]+\s*$', line.strip()):
                origin_vals = re.findall(r'-?\d+\.\d+', line.strip())
                if len(origin_vals) == 3:
                    origin = np.array([float(v) for v in origin_vals], dtype=np.float64)
                    continue
            # reciprocal vectors (3 lines after origin)
            if origin is not None and reciprocal_vectors is None:
                vec_lines = []
                vec_start_idx = None
                for j in range(i, min(i+10, len(lines))):
                    if re.match(r'^\s*-?\d+\.\d+\s+-?\d+\.\d+\s+-?\d+\.\d+\s*$', lines[j].strip()):
                        if vec_start_idx is None:
                            vec_start_idx = j
                        vec_lines.append(lines[j].strip())
                        if len(vec_lines) == 3:
                            reciprocal_vectors = np.zeros((3, 3), dtype=np.float64)
                            for k, vec_line in enumerate(vec_lines):
                                vals = re.findall(r'-?\d+\.\d+', vec_line)
                                if len(vals) == 3:
                                    reciprocal_vectors[k] = [float(v) for v in vals]
                            break
                if reciprocal_vectors is not None:
                    break
    
    if grid_shape is None or nbands is None or origin is None or reciprocal_vectors is None:
        raise VolumeParserError("Failed to parse BXSF header")
    
    return {
        "grid_shape": grid_shape,
        "nbands": nbands,
        "fermi_energy": fermi_energy,
        "origin": origin,
        "reciprocal_vectors": reciprocal_vectors,
    }


def _read_bxsf_band_data(
    path: Path,
    band_line_offset: int,
    nx: int,
    ny: int,
    nz: int,
    band_index: int,
) -> List[float]:
    """
    Read data for a specific band from BXSF file.
    
    Args:
        path: Path to BXSF file
        band_line_offset: Line number where band starts (1-indexed)
        nx, ny, nz: Grid dimensions
        band_index: Band index (for error messages)
        
    Returns:
        List of float values (C order: k-fastest)
    """
    content = path.read_text()
    lines = content.splitlines()
    
    # Find band marker
    data_start_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f"BAND:") and i + 1 >= band_line_offset:
            match = re.match(r'BAND:\s*(\d+)', line.strip())
            if match and int(match.group(1)) == band_index:
                data_start_idx = i + 1
                break
    
    if data_start_idx is None:
        raise VolumeParserError(f"Band {band_index} marker not found at expected line")
    
    # Read data values (token stream)
    expected_count = nx * ny * nz
    data_values = []
    
    token_pattern = re.compile(r'-?\d+\.\d+E[+-]\d+|-\d+\.\d+|\d+\.\d+|-?\d+\.\d+E[+-]?\d+')
    
    # Read until we have enough values or hit next BAND marker
    for i in range(data_start_idx, len(lines)):
        line = lines[i]
        if line.strip().startswith("BAND:"):
            break
        tokens = token_pattern.findall(line)
        data_values.extend([float(t) for t in tokens])
        if len(data_values) >= expected_count:
            break
    
    # Truncate to expected count (in case we read too many)
    if len(data_values) > expected_count:
        data_values = data_values[:expected_count]
    
    return data_values


def downsample_grid_c_order(
    data: np.ndarray,
    grid_shape: Tuple[int, int, int],
    grid_vectors_cart: np.ndarray,
    factor: int = 4,
) -> Tuple[np.ndarray, Tuple[int, int, int], np.ndarray]:
    """
    Downsample volumetric grid (C order version for BXSF).
    
    Same as downsample_grid but uses C order (k-fastest) for reshaping.
    """
    nx, ny, nz = grid_shape
    
    nx_preview = nx // factor
    ny_preview = ny // factor
    nz_preview = nz // factor
    
    preview_shape = (nx_preview, ny_preview, nz_preview)
    
    # Reshape with C order (k-fastest)
    data_3d = data.reshape(grid_shape, order='C')
    
    # Block average (same as FORTRAN version)
    preview_data_3d = np.zeros(preview_shape, dtype=np.float32)
    
    for i_preview in range(nx_preview):
        for j_preview in range(ny_preview):
            for k_preview in range(nz_preview):
                i_start = i_preview * factor
                i_end = min((i_preview + 1) * factor, nx)
                j_start = j_preview * factor
                j_end = min((j_preview + 1) * factor, ny)
                k_start = k_preview * factor
                k_end = min((k_preview + 1) * factor, nz)
                
                block = data_3d[i_start:i_end, j_start:j_end, k_start:k_end]
                preview_data_3d[i_preview, j_preview, k_preview] = block.mean()
    
    # Flatten back to C order
    preview_data = preview_data_3d.flatten(order='C')
    
    # Scale grid vectors
    preview_grid_vectors = grid_vectors_cart * factor
    
    return preview_data, preview_shape, preview_grid_vectors

