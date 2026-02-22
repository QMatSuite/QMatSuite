"""
Unified resolver for precision preset context.

This module provides a single source of truth for resolving:
- Structure (lattice matrix)
- Species/pseudo mapping
- Pseudo cutoff lookup

Both apply and detect paths MUST use this resolver to ensure consistency.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from qmatsuite.core.models import CalculationModel, load_calculation
from qmatsuite.core.resolution import (
    resolve_structure,
    build_resource_index,
    SelectorNotFoundError,
)
from qmatsuite.core.project_utils import load_project_config
from qmatsuite.io.structure_io import read_structure
from qmatsuite.presets.precision import get_pseudo_index

if TYPE_CHECKING:
    from pymatgen.core import Structure as PMGStructure


class PrecisionContextError(Exception):
    """Raised when precision context cannot be resolved."""
    pass


@dataclass
class PrecisionContext:
    """Context needed for precision preset apply/detect."""
    
    structure: PMGStructure
    species_map: Dict[str, Dict[str, Any]]
    lattice_matrix: list[list[float]]
    calculation_dir: Path
    project_root: Path
    
    @property
    def pseudo_index(self):
        """Get pseudo index (cached)."""
        return get_pseudo_index(self.project_root)


def resolve_precision_context(
    calculation_dir: Path,
    project_root: Optional[Path] = None,
    calc_model: Optional[CalculationModel] = None,
) -> PrecisionContext:
    """
    Resolve all context needed for precision preset apply/detect.
    
    This is the SINGLE SOURCE OF TRUTH for precision context resolution.
    Both apply and detect paths MUST use this function.
    
    Args:
        calculation_dir: Path to calculation directory (contains calculation.yaml)
        project_root: Optional path to project root (derived from calculation_dir if None)
        calc_model: Optional pre-loaded CalculationModel (loaded if None)
        
    Returns:
        PrecisionContext with structure, species_map, lattice_matrix
        
    Raises:
        PrecisionContextError: If structure or species_map cannot be resolved
        FileNotFoundError: If calculation.yaml does not exist
    """
    calculation_dir = Path(calculation_dir).resolve()
    
    # Derive project_root if not provided
    if project_root is None:
        # Try to find project root by walking up from calculation_dir
        candidate = calculation_dir.parent
        while candidate != candidate.parent:  # Stop at filesystem root
            if (candidate / "project.qms.yml").exists():
                project_root = candidate
                break
            candidate = candidate.parent
        
        if project_root is None:
            raise PrecisionContextError(
                f"Could not find project root (project.qms.yml) from calculation_dir: {calculation_dir}"
            )
    else:
        project_root = Path(project_root).resolve()
    
    # Load calculation model if not provided
    if calc_model is None:
        calc_yaml_path = calculation_dir / "calculation.yaml"
        if not calc_yaml_path.exists():
            raise FileNotFoundError(
                f"Calculation file not found: {calc_yaml_path}"
            )
        try:
            calc_model = load_calculation(calc_yaml_path, project_root=project_root)
        except Exception as e:
            raise PrecisionContextError(
                f"Failed to load calculation: {e}"
            ) from e
    
    # Get species_map (required)
    species_map = calc_model.species_map
    if not species_map:
        raise PrecisionContextError(
            f"Calculation has no species_map: {calculation_dir}"
        )
    
    # Resolve structure (required)
    structure = None
    structure_ulid = calc_model.structure_ulid
    
    if not structure_ulid:
        raise PrecisionContextError(
            f"Calculation has no structure_ulid: {calculation_dir}"
        )
    
    try:
        # Build index and config
        index = build_resource_index(project_root)
        config = load_project_config(project_root)
        
        # Resolve structure using the same mechanism as other RPCs
        resolved = resolve_structure(
            project_root,
            structure_ulid,
            config=config,
            index=index,
        )
        
        # Read structure from resolved path
        structure = read_structure(resolved.absolute_path)
        
    except SelectorNotFoundError as e:
        raise PrecisionContextError(
            f"Structure not found: structure_ulid={structure_ulid}, "
            f"calculation_dir={calculation_dir}"
        ) from e
    except Exception as e:
        raise PrecisionContextError(
            f"Failed to load structure: structure_ulid={structure_ulid}, "
            f"calculation_dir={calculation_dir}, error={e}"
        ) from e
    
    if structure is None:
        raise PrecisionContextError(
            f"Structure is None after resolution: structure_ulid={structure_ulid}"
        )
    
    # Compute lattice matrix from structure
    lattice_matrix = [list(v) for v in structure.lattice.matrix]
    
    return PrecisionContext(
        structure=structure,
        species_map=species_map,
        lattice_matrix=lattice_matrix,
        calculation_dir=calculation_dir,
        project_root=project_root,
    )
