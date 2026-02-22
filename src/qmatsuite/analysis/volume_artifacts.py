"""
Volume artifact data structures and metadata contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np


class DataOrder(str, Enum):
    """Data ordering conventions for volumetric grids."""
    FORTRAN_I_FASTEST = "fortran_i_fastest"  # FORTRAN/column-major: i varies fastest
    C_K_FASTEST = "c_k_fastest"              # C/row-major: k varies fastest


@dataclass
class VolumeMetadata:
    """
    Metadata contract for volumetric data artifacts.
    
    Follows strict contract from PLAN_V2 and FIXTURE_FILE_REVIEW.
    """
    # Grid dimensions (required)
    grid_shape: Tuple[int, int, int]  # (nx, ny, nz)
    
    # Coordinate system (required)
    coordinate_system: Literal["real-space", "reciprocal-space"]
    
    # Spatial information (required)
    origin_cart: np.ndarray  # (3,) float64, in length_units
    grid_vectors_cart: np.ndarray  # (3, 3) float64, voxel step vectors in length_units
    
    # Data ordering (CRITICAL, required)
    data_order: DataOrder  # Enum: FORTRAN_I_FASTEST or C_K_FASTEST
    data_order_format_default: str  # Format name (e.g., "XSF_DATAGRID", "BXSF_BANDGRID")
    data_order_self_check_passed: bool  # Whether count validation passed
    
    # Blob references (required)
    blob_id: str  # Full resolution blob
    
    # Optional fields (with defaults)
    lattice_vectors_cart: Optional[np.ndarray] = None  # (3, 3) float64, crystal lattice (for structure overlay)
    length_units: str = "Å"  # Length unit (Å, 1/Å, etc.)
    value_units: str = "arbitrary"  # Value unit (arbitrary, eV, etc.)
    reciprocal_convention: Optional[str] = None  # For reciprocal space: "2pi" or "unknown"
    preview_blob_id: Optional[str] = None  # Preview blob (downsampled)
    preview_downsample_factor: Optional[int] = None  # Factor used for preview (e.g., 4)
    preview_grid_shape: Optional[Tuple[int, int, int]] = None  # Preview blob dimensions (must match preview_blob_id data length)
    
    # Statistics (optional, computed during parse)
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_mean: Optional[float] = None
    
    # Structure information (optional, for overlay)
    structure_atoms: Optional[List[Dict[str, any]]] = None  # List of {element, position} dicts
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to JSON-serializable dictionary."""
        result = {
            "grid_shape": list(self.grid_shape),
            "coordinate_system": self.coordinate_system,
            "origin_cart": self.origin_cart.tolist(),
            "grid_vectors_cart": self.grid_vectors_cart.tolist(),
            "data_order": self.data_order.value,
            "data_order_format_default": self.data_order_format_default,
            "data_order_self_check_passed": self.data_order_self_check_passed,
            "length_units": self.length_units,
            "value_units": self.value_units,
            "blob_id": self.blob_id,
        }
        
        if self.lattice_vectors_cart is not None:
            result["lattice_vectors_cart"] = self.lattice_vectors_cart.tolist()
        
        if self.reciprocal_convention is not None:
            result["reciprocal_convention"] = self.reciprocal_convention
        
        if self.preview_blob_id is not None:
            result["preview_blob_id"] = self.preview_blob_id
            result["preview_downsample_factor"] = self.preview_downsample_factor
            if self.preview_grid_shape is not None:
                result["preview_grid_shape"] = list(self.preview_grid_shape)
        
        if self.value_min is not None:
            result["value_min"] = self.value_min
            result["value_max"] = self.value_max
            result["value_mean"] = self.value_mean
        
        if self.structure_atoms is not None:
            result["structure_atoms"] = self.structure_atoms
        
        return result

