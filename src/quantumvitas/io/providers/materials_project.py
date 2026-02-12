"""
Materials Project native API provider.

PR5: MP native API search with API key support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from mp_api.client import MPRester
    MP_API_AVAILABLE = True
except ImportError:
    MP_API_AVAILABLE = False

from quantumvitas.io.providers.optimade import Candidate

logger = logging.getLogger(__name__)


@dataclass
class MPSummaryDoc:
    """Materials Project summary document (from mp-api)."""
    material_id: str
    structure: Any  # pymatgen Structure
    band_gap: Optional[float] = None
    formation_energy_per_atom: Optional[float] = None
    energy_above_hull: Optional[float] = None
    is_stable: Optional[bool] = None
    symmetry: Optional[Dict[str, Any]] = None


def _mp_doc_to_candidate(doc: MPSummaryDoc) -> Candidate:
    """
    Convert MP summary document to Candidate.
    
    Args:
        doc: MP summary document
        
    Returns:
        Candidate object compatible with OPTIMADE provider
    """
    # Extract structure info
    structure = doc.structure
    
    # Get reduced formula from structure composition
    try:
        if hasattr(structure, 'composition'):
            reduced_formula = structure.composition.reduced_formula
        else:
            # Fallback: try to get formula from structure
            reduced_formula = str(structure.formula) if hasattr(structure, 'formula') else ""
    except Exception:
        reduced_formula = ""
    
    # Get number of sites
    try:
        nsites = len(structure)
    except Exception:
        nsites = 0
    
    # Extract space group from symmetry if available
    space_group_number = None
    if doc.symmetry:
        if isinstance(doc.symmetry, dict):
            space_group_number = doc.symmetry.get("number")
        elif hasattr(doc.symmetry, 'number'):
            space_group_number = doc.symmetry.number
    
    # Check for partial occupancy (simplified: check if any site has partial occupancy)
    has_partial_occupancy = False
    try:
        if hasattr(structure, 'sites'):
            for site in structure.sites:
                if hasattr(site, 'species'):
                    # Check if species has partial occupancies
                    # For pymatgen, species can be a Composition or Species
                    if hasattr(site.species, 'as_dict'):
                        species_dict = site.species.as_dict()
                        # Check if any occupancy value is less than 1.0
                        if isinstance(species_dict, dict):
                            for value in species_dict.values():
                                if isinstance(value, (int, float)) and 0 < value < 1.0:
                                    has_partial_occupancy = True
                                    break
                    elif hasattr(site.species, 'num_atoms'):
                        # For Composition objects, check if total is less than expected
                        # This is a simplified check
                        pass
    except Exception:
        # If we can't check, assume no partial occupancy
        pass
    
    # Build metadata with rich MP data
    metadata: Dict[str, Any] = {
        "material_id": doc.material_id,
        "provider": "mp-native",
    }
    if doc.band_gap is not None:
        metadata["band_gap"] = doc.band_gap
    if doc.formation_energy_per_atom is not None:
        metadata["formation_energy_per_atom"] = doc.formation_energy_per_atom
    if doc.energy_above_hull is not None:
        metadata["energy_above_hull"] = doc.energy_above_hull
    if doc.is_stable is not None:
        metadata["is_stable"] = doc.is_stable
    if doc.symmetry:
        metadata["symmetry"] = doc.symmetry
    
    return Candidate(
        entry_id=doc.material_id,
        provider_id="mp-native",
        reduced_formula=reduced_formula,
        nsites=nsites,
        space_group_number=space_group_number,
        has_partial_occupancy=has_partial_occupancy,
        metadata=metadata,
        score=0.0,  # Will be scored by ranking function
    )


def search_materials_project(
    query: str,
    api_key: str,
    max_results: int = 10,
) -> List[Candidate]:
    """
    Search Materials Project via native API (mp-api).
    
    Uses mp-api MPRester client to search by formula.
    
    Args:
        query: Chemical formula (e.g., "Si", "Fe2O3")
        api_key: MP API key
        max_results: Maximum number of results
        
    Returns:
        List of Candidate objects
        
    Raises:
        ValueError: If mp-api is not available or API key is invalid
    """
    if not MP_API_AVAILABLE:
        raise ValueError("mp-api package not available. Install with: pip install mp-api")
    
    if not api_key or not api_key.strip():
        raise ValueError("MP API key is required")
    
    try:
        with MPRester(api_key) as mpr:
            # Search by formula
            docs = mpr.summary.search(
                formula=query,
                num_results=max_results,
                fields=[
                    "material_id",
                    "structure",
                    "band_gap",
                    "formation_energy_per_atom",
                    "energy_above_hull",
                    "is_stable",
                    "symmetry",
                ],
            )
            
            # Convert to Candidate objects
            candidates = []
            for doc_dict in docs:
                # Convert dict to MPSummaryDoc-like object
                # mp-api returns dict-like objects, so we'll work with them directly
                material_id = doc_dict.get("material_id", "")
                structure = doc_dict.get("structure")
                
                if not structure or not material_id:
                    continue
                
                # Create a simple wrapper for compatibility
                doc = MPSummaryDoc(
                    material_id=material_id,
                    structure=structure,
                    band_gap=doc_dict.get("band_gap"),
                    formation_energy_per_atom=doc_dict.get("formation_energy_per_atom"),
                    energy_above_hull=doc_dict.get("energy_above_hull"),
                    is_stable=doc_dict.get("is_stable"),
                    symmetry=doc_dict.get("symmetry"),
                )
                
                candidate = _mp_doc_to_candidate(doc)
                candidates.append(candidate)
            
            return candidates
            
    except Exception as e:
        logger.error(f"MP native API search failed: {e}")
        # Check if it's an authentication error
        if "401" in str(e) or "Unauthorized" in str(e) or "Invalid API key" in str(e):
            raise ValueError(f"Invalid MP API key: {e}")
        raise ValueError(f"MP native API search failed: {e}")


def validate_api_key(api_key: str) -> bool:
    """
    Validate MP API key by making a test request.
    
    Args:
        api_key: MP API key to validate
        
    Returns:
        True if key is valid, False otherwise
    """
    if not MP_API_AVAILABLE:
        logger.warning("mp-api package not available, cannot validate key")
        return False
    
    if not api_key or not api_key.strip():
        return False
    
    try:
        with MPRester(api_key) as mpr:
            # Make a minimal test request (search for Si, limit 1)
            docs = mpr.summary.search(
                formula="Si",
                num_results=1,
                fields=["material_id"],
            )
            # If we get here without exception, key is valid
            return True
    except Exception as e:
        logger.warning(f"MP API key validation failed: {e}")
        return False

