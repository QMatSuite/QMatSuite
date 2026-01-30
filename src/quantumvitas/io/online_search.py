"""
Online structure search via OPTIMADE and COD.

Primary: Materials Cloud OPTIMADE endpoint
Fallback: COD via pymatgen.ext.cod.COD
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from pymatgen.core import Composition, Structure as PMGStructure
from pymatgen.core.periodic_table import Element

try:
    from pymatgen.ext.cod import COD
    COD_AVAILABLE = True
except ImportError:
    COD_AVAILABLE = False

# Import CandidateSummary from cache module to avoid duplication
from quantumvitas.io.online_cache import CandidateSummary

logger = logging.getLogger(__name__)


# OPTIMADE endpoints (try in order until one succeeds)
# Primary: Materials Project (fast, reliable, comprehensive)
# Fallbacks: Materials Cloud databases (mc3d-pbe-v1, mc3d-pbesol-v2, mc3d-pbesol-v1)
OPTIMADE_BASES = [
    "https://optimade.materialsproject.org",
    "https://optimade.materialscloud.org/main/mc3d-pbe-v1",
    "https://optimade.materialscloud.org/main/mc3d-pbesol-v2",
    "https://optimade.materialscloud.org/main/mc3d-pbesol-v1",
]

# Default base (first in list)
OPTIMADE_DEFAULT_BASE = OPTIMADE_BASES[0]


def normalize_formula(formula: str) -> str:
    """
    Normalize chemical formula for OPTIMADE search.
    
    Handles case-insensitive input and capitalizes element symbols properly.
    
    Examples:
        "Si" -> "Si"
        "si" -> "Si"
        "MoS2" -> "MoS2"
        "mos2" -> "MoS2"
        "SiO2" -> "SiO2"
        "Si O2" -> "SiO2"
    """
    # Remove spaces
    formula = re.sub(r'\s+', '', formula)
    # Basic validation - should contain at least one letter
    if not re.search(r'[A-Za-z]', formula):
        raise ValueError(f"Invalid formula: {formula}")
    
    # Capitalize first letter of each element symbol
    # Pattern: element symbol (1-2 letters) followed by optional number
    # This handles: Si, MoS2, SiO2, etc.
    def capitalize_element(match):
        elem = match.group(1)
        num = match.group(2) if match.group(2) else ""
        # Capitalize first letter, lowercase second if present
        if len(elem) == 1:
            elem = elem.upper()
        elif len(elem) == 2:
            elem = elem[0].upper() + elem[1].lower()
        return elem + num
    
    # Match element symbols (1-2 letters) followed by optional numbers
    formula = re.sub(r'([A-Za-z]{1,2})(\d*)', capitalize_element, formula)
    
    return formula


def reduce_formula(formula: str) -> str:
    """
    Reduce formula to standard form (e.g., "Si2O4" -> "SiO2").
    
    Uses pymatgen Composition for reduction.
    Handles case-insensitive input by normalizing first.
    """
    try:
        # Normalize case first
        normalized = normalize_formula(formula)
        comp = Composition(normalized)
        return comp.reduced_formula
    except Exception as e:
        logger.warning(f"Failed to reduce formula {formula}: {e}")
        # Try to return normalized version even if reduction fails
        try:
            return normalize_formula(formula)
        except Exception:
            return formula


def search_optimade(query: str, max_results: int = 10) -> tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Search Materials Cloud OPTIMADE endpoint.
    
    Tries multiple bases in order until one succeeds.
    
    Args:
        query: Chemical formula (e.g., "Si", "MoS2")
        max_results: Maximum number of results
        
    Returns:
        (base_url, entries) tuple where:
        - base_url: The base URL that succeeded (None if all failed)
        - entries: List of structure entry IDs and metadata from OPTIMADE
    """
    if not REQUESTS_AVAILABLE:
        logger.warning("requests library not available, skipping OPTIMADE search")
        return None, []
    
    # Normalize and reduce formula
    normalized = normalize_formula(query)
    reduced = reduce_formula(normalized)
    
    # OPTIMADE filter: chemical_formula_reduced
    filter_value = f'chemical_formula_reduced="{reduced}"'
    
    # Try each base URL in order
    for base_url in OPTIMADE_BASES:
        try:
            url = f"{base_url}/v1/structures"
            params = {
                "filter": filter_value,
                "page_limit": min(max_results, 100),  # OPTIMADE limit
                # Remove response_fields - parse only what exists
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            # If 404, try next base
            if response.status_code == 404:
                logger.debug(f"OPTIMADE base {base_url} returned 404, trying next")
                continue
            
            response.raise_for_status()
            
            data = response.json()
            entries = data.get("data", [])
            
            logger.info(f"OPTIMADE search for '{query}' at {base_url} returned {len(entries)} results")
            return base_url, entries
            
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                logger.debug(f"OPTIMADE base {base_url} returned 404, trying next")
                continue
            logger.warning(f"OPTIMADE search failed at {base_url}: {e}")
            continue
        except Exception as e:
            logger.warning(f"OPTIMADE search failed at {base_url}: {e}")
            continue
    
    logger.warning(f"All OPTIMADE bases failed for query '{query}'")
    return None, []


def search_cod(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Search COD (Crystallography Open Database) via pymatgen.
    
    Args:
        query: Chemical formula
        max_results: Maximum number of results
        
    Returns:
        List of structure entries from COD
    """
    if not COD_AVAILABLE:
        logger.warning("pymatgen.ext.cod not available, skipping COD search")
        return []
    
    try:
        normalized = normalize_formula(query)
        reduced = reduce_formula(normalized)
        
        cod = COD()
        
        # Try get_structure_by_formula first (single result, faster)
        try:
            structure = cod.get_structure_by_formula(reduced)
            if structure:
                formula = structure.composition.reduced_formula
                # Generate a candidate entry ID
                entry_id = f"cod_formula_{reduced}"
                return [{
                    "ulid": f"cod_{entry_id}",
                    "entry_id": entry_id,
                    "structure": structure,
                    "formula": formula,
                    "nsites": len(structure),
                    "source": "cod",
                }]
        except AttributeError:
            # get_structure_by_formula not available in this COD version
            pass
        except Exception as e:
            # Other errors (e.g., MySQL not available)
            logger.debug(f"COD get_structure_by_formula failed: {e}")
            pass
        
        # Use query() - note: COD.query() does NOT accept max_results parameter
        # Query returns list of (entry_id, structure) tuples
        try:
            results = cod.query(reduced)
        except (FileNotFoundError, OSError) as e:
            # COD requires MySQL database file - if not available, skip COD
            logger.warning(f"COD database not available (MySQL file missing): {e}")
            return []
        except Exception as e:
            logger.warning(f"COD query failed: {e}")
            return []
        
        # Slice results in Python (limit to small cap <= 10)
        entries = []
        for entry_id, structure in results[:min(max_results, 10)]:
            try:
                # Convert to dict-like format for consistency
                formula = structure.composition.reduced_formula
                entries.append({
                    "ulid": f"cod_{entry_id}",
                    "entry_id": str(entry_id),
                    "structure": structure,
                    "formula": formula,
                    "nsites": len(structure),
                    "source": "cod",
                })
            except Exception as e:
                logger.warning(f"Failed to process COD entry {entry_id}: {e}")
                continue
        
        logger.info(f"COD search for '{query}' returned {len(entries)} results")
        return entries
        
    except Exception as e:
        logger.warning(f"COD search failed: {e}")
        return []


def score_candidate(
    structure: PMGStructure,
    source: str,
    formula_query: str,
    entry_data: Optional[Dict[str, Any]] = None,
) -> tuple[float, List[str]]:
    """
    Score a candidate structure.
    
    Returns:
        (score, flags) tuple where:
        - score: Higher is better (0.0 to 1.0+)
        - flags: List of flag strings (e.g., ["partial_occ", "large_cell"])
    """
    flags = []
    score = 1.0
    
    # Check formula match
    try:
        comp = structure.composition
        reduced_formula = comp.reduced_formula
        query_reduced = reduce_formula(formula_query)
        
        if reduced_formula != query_reduced:
            flags.append("formula_mismatch")
            score -= 0.5  # Strong penalty but don't drop completely
    except Exception:
        flags.append("formula_parse_error")
        score -= 0.3
    
    # Check for partial occupancy / disorder
    has_partial_occ = False
    for site in structure:
        if hasattr(site, 'species') and hasattr(site.species, 'as_dict'):
            species_dict = site.species.as_dict()
            for elem, occ in species_dict.items():
                if occ < 0.99:  # Allow small floating point errors
                    has_partial_occ = True
                    break
            if has_partial_occ:
                break
    
    if has_partial_occ:
        flags.append("partial_occ")
        score -= 0.4  # Strong penalty
    
    # Check size (nsites > 200 gets penalty)
    nsites = len(structure)
    if nsites > 200:
        flags.append("large_cell")
        score -= 0.2
    
    # Bonus for fewer sites (simpler structures preferred)
    if nsites < 50:
        score += 0.1
    elif nsites < 20:
        score += 0.2
    
    # Bonus for space group (if available)
    if entry_data:
        spacegroup = entry_data.get("spacegroup")
        if spacegroup:
            score += 0.05
            # Store spacegroup in entry_data for later use
            entry_data["_spacegroup"] = spacegroup
    
    # Small bonus for OPTIMADE as primary source
    if source == "optimade":
        score += 0.05
    
    # Ensure score is non-negative
    score = max(0.0, score)
    
    return score, flags


def fetch_structure_from_optimade(
    base_url: str, 
    entry_id: str
) -> tuple[Optional[PMGStructure], Optional[Dict[str, Any]]]:
    """
    Fetch full structure from OPTIMADE entry by ID.
    
    Args:
        base_url: OPTIMADE base URL (e.g., "https://optimade.materialscloud.org/main/mc3d-pbe-v1")
        entry_id: Structure entry ID
        
    Returns:
        (structure, raw_data) tuple where:
        - structure: pymatgen Structure object or None if fetch fails
        - raw_data: Full OPTIMADE response data (for provenance) or None
    """
    if not REQUESTS_AVAILABLE:
        return None, None
    
    try:
        # Request full structure data including coordinates
        url = f"{base_url}/v1/structures/{entry_id}"
        # Don't specify response_fields - get all available fields
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        structure_data = data.get("data", {})
        
        if not structure_data:
            return None, None
        
        # OPTIMADE structure data is in data.attributes
        attrs = structure_data.get("attributes", {})
        
        # Get lattice vectors
        lattice_vectors = attrs.get("lattice_vectors", [])
        if not lattice_vectors or len(lattice_vectors) != 3:
            return None
        
        # Get species and positions
        species_at_sites = attrs.get("species_at_sites", [])
        species_list = attrs.get("species", [])
        cartesian_positions = attrs.get("cartesian_site_positions", [])
        
        if not species_at_sites or not cartesian_positions:
            return None
        
        # Validate lengths match
        if len(species_at_sites) != len(cartesian_positions):
            logger.error(
                f"OPTIMADE structure mismatch: species_at_sites length ({len(species_at_sites)}) "
                f"!= cartesian_site_positions length ({len(cartesian_positions)})"
            )
            return None
        
        # Build species list for each site
        # species_at_sites can be:
        # 1. List of element symbols directly: ["Mo", "S", "S"]
        # 2. List of indices into species array: [0, 1, 1]
        # 3. List of lists (partial occupancy): [[0], [1], [1]]
        site_species = []
        for i, site_species_data in enumerate(species_at_sites):
            element_symbol = None
            
            # Handle list of lists (partial occupancy) - take first
            if isinstance(site_species_data, list):
                if len(site_species_data) == 0:
                    element_symbol = "X"
                else:
                    site_species_data = site_species_data[0]  # Take first species
            
            # Check if it's a direct element symbol (string)
            if isinstance(site_species_data, str):
                element_symbol = site_species_data
            # Check if it's an index (int) into species_list
            elif isinstance(site_species_data, int):
                if site_species_data < len(species_list):
                    species_info = species_list[site_species_data]
                    # Extract chemical symbol from species info
                    if isinstance(species_info, dict):
                        chem_symbols = species_info.get("chemical_symbols", [])
                        if chem_symbols:
                            element_symbol = chem_symbols[0]
                        else:
                            element_symbol = "X"
                    elif isinstance(species_info, str):
                        element_symbol = species_info
                    else:
                        element_symbol = "X"
                else:
                    element_symbol = "X"
            else:
                element_symbol = "X"
            
            if not element_symbol:
                element_symbol = "X"
            
            site_species.append(element_symbol)
        
        # Build structure
        from pymatgen.core import Lattice
        import numpy as np
        
        # Validate lattice is invertible
        lattice_matrix = np.array(lattice_vectors)
        if lattice_matrix.shape != (3, 3):
            logger.error(f"OPTIMADE lattice_vectors must be 3x3, got shape {lattice_matrix.shape}")
            return None, None
        
        # Check if lattice is invertible (determinant != 0)
        det = np.linalg.det(lattice_matrix)
        if abs(det) < 1e-10:
            logger.error(f"OPTIMADE lattice_vectors matrix is singular (det={det}), cannot compute fractional coordinates")
            return None, None
        
        lattice = Lattice(lattice_vectors)
        structure = PMGStructure(lattice, site_species, cartesian_positions, coords_are_cartesian=True)
        
        # Verify fractional coordinates are reasonable (most should be in [0,1) or close)
        # This is a sanity check that the conversion worked correctly
        frac_coords = structure.frac_coords
        if len(frac_coords) > 0:
            # Check that at least some coords are in reasonable range (not all wildly large)
            frac_abs_max = np.abs(frac_coords).max()
            if frac_abs_max > 100:
                logger.warning(
                    f"OPTIMADE fractional coordinates seem unreasonable (max abs={frac_abs_max:.2f}). "
                    f"This may indicate a coordinate system mismatch."
                )
        
        # Return structure and full raw data for provenance
        return structure, data
        
    except Exception as e:
        logger.warning(f"Failed to fetch structure from OPTIMADE {base_url}/{entry_id}: {e}")
        return None, None


def _get_nested_value(obj: Any, path: str) -> Any:
    """Get nested value by dot-separated path."""
    if obj is None:
        return None
    parts = path.split('.')
    current = obj
    for part in parts:
        if current is None or not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _get_first_available(obj: Any, keys: List[str]) -> Any:
    """Get first available value from a list of keys (dot-separated paths)."""
    if obj is None:
        return None
    for key in keys:
        value = _get_nested_value(obj, key)
        if value is not None and value != '':
            return value
    return None


def resolve_overview_fields(
    structure: PMGStructure,
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Resolve the Overview fields used by the GUI Details panel using the same priority rules.
    
    This mirrors the frontend mapping logic in StructureDetailPanel.tsx.
    
    Args:
        structure: pymatgen Structure object
        provenance: Provenance dict from extract_provenance()
        
    Returns:
        Dict with keys:
        - formula: str (resolved using priority)
        - nsites: int (resolved using priority)
        - species: List[str] (unique species symbols)
        - spacegroup_international: str | None
        - spacegroup_number: int | None
        - bravais_lattice: str | None
        - dimensionality: str | None (e.g., "3D")
        - partial_occupancies: bool | None
        - created: str | None
        - modified: str | None
        - optimade_id: str | None
        - aiida_uuid: str | None
        - provider: str | None
        - database: str | None
        - source_name: str | None
        
    Any missing optional fields are None. Result is JSON-safe.
    """
    result: Dict[str, Any] = {}
    
    # Formula priority: structure.composition.reduced_formula as baseline,
    # but prefer provenance if available
    formula = structure.composition.reduced_formula
    prov_formula = _get_first_available(provenance, [
        'extras.formula_hill',
        'extras.formula_hill_compact',
        'attributes.chemical_formula_reduced',
        'attributes.chemical_formula_descriptive',
    ])
    if prov_formula:
        formula = str(prov_formula)
    result["formula"] = formula
    
    # nsites priority: provenance extras/attributes, fallback to structure
    nsites = _get_first_available(provenance, [
        'extras.number_of_sites',
        'attributes.nsites',
    ])
    if nsites is None:
        nsites = structure.num_sites
    else:
        nsites = int(nsites) if isinstance(nsites, (int, float, str)) else structure.num_sites
    result["nsites"] = nsites
    
    # Species: from structure (unique)
    species_set = set()
    for site in structure:
        species_set.add(str(site.specie))
    result["species"] = sorted(list(species_set))
    
    # Space group: priority extras.spacegroup_international, then attributes fallbacks
    spacegroup_symbol = _get_first_available(provenance, [
        'extras.spacegroup_international',
        'attributes.space_group_symbol',
        'attributes.spacegroup_international',
    ])
    result["spacegroup_international"] = str(spacegroup_symbol) if spacegroup_symbol else None
    
    spacegroup_number = _get_first_available(provenance, [
        'extras.spacegroup_number',
        'attributes.space_group_number',
    ])
    if spacegroup_number is not None:
        try:
            result["spacegroup_number"] = int(spacegroup_number)
        except (ValueError, TypeError):
            result["spacegroup_number"] = None
    else:
        result["spacegroup_number"] = None
    
    # Bravais lattice
    bravais = _get_first_available(provenance, [
        'extras.bravais_lattice_extended',
        'extras.bravais_lattice',
    ])
    result["bravais_lattice"] = str(bravais) if bravais else None
    
    # Dimensionality
    dim = _get_first_available(provenance, [
        'attributes.dimensionality',
        'extras.dimensionality',
    ])
    if dim is not None:
        result["dimensionality"] = f"{dim}D" if isinstance(dim, (int, float)) else str(dim)
    else:
        result["dimensionality"] = None
    
    # Partial occupancies
    partial_occ = _get_first_available(provenance, ['extras.partial_occupancies'])
    if partial_occ is not None:
        if isinstance(partial_occ, bool):
            result["partial_occupancies"] = partial_occ
        elif isinstance(partial_occ, str):
            result["partial_occupancies"] = partial_occ.lower() in ('true', 'yes', '1')
        else:
            result["partial_occupancies"] = bool(partial_occ)
    else:
        # Check structure_features for disorder
        features = _get_first_available(provenance, ['attributes.structure_features'])
        if isinstance(features, list):
            has_disorder = any(
                isinstance(f, str) and 'disorder' in f.lower()
                for f in features
            )
            result["partial_occupancies"] = has_disorder if has_disorder else None
        else:
            result["partial_occupancies"] = None
    
    # Timestamps
    result["created"] = provenance.get("created") or _get_nested_value(provenance, 'raw.ctime')
    result["modified"] = provenance.get("modified") or _get_nested_value(provenance, 'raw.mtime')
    
    # Identifiers
    result["optimade_id"] = provenance.get("optimade_id")
    result["aiida_uuid"] = provenance.get("aiida_uuid") or _get_nested_value(provenance, 'raw.uuid') or _get_nested_value(provenance, 'attributes.uuid')
    
    # Source metadata
    result["provider"] = provenance.get("provider")
    result["database"] = provenance.get("database")
    result["source_name"] = provenance.get("source_name")
    
    return result


def extract_provenance(
    *,
    provider: str,
    database: str,
    base_url: str,
    optimade_id: str,
    attributes: Dict[str, Any],
    raw: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extract provenance metadata from OPTIMADE/AiiDA response.
    
    Returns JSON-safe provenance dict with keys used by Details panel.
    This matches the field mapping rules used by the frontend Details panel.
    
    Args:
        provider: Provider name (e.g., "main", "archive")
        database: Database name (e.g., "mc3d-pbe-v1")
        base_url: OPTIMADE base URL
        optimade_id: Structure entry ID
        attributes: OPTIMADE attributes dict (from data.attributes)
        raw: Full OPTIMADE response (optional, for raw block)
        
    Returns:
        Provenance dict with keys:
        - source_name: str
        - provider: str
        - database: str
        - base_url: str
        - optimade_id: str
        - aiida_uuid: str | None
        - created: str | None
        - modified: str | None
        - owner: str | None
        - node_type: str | None
        - extras: dict (from attributes.extras)
        - attributes: dict (full attributes)
        - raw: dict | None (full raw response if provided)
    """
    # Extract provider info from raw response meta if available
    provider_name = "Materials Cloud OPTIMADE"
    # Use the provided provider parameter (from base URL parsing) as the primary source
    # Only use raw meta.provider.prefix as fallback if provider parameter is not set
    provider_prefix = provider
    if raw and isinstance(raw, dict):
        meta = raw.get("meta", {})
        if isinstance(meta, dict):
            provider_info = meta.get("provider")
            if isinstance(provider_info, dict):
                provider_name = provider_info.get("name", provider_name)
                # Only use prefix from raw if provider parameter was not provided or is "unknown"
                if not provider_prefix or provider_prefix == "unknown":
                    provider_prefix = provider_info.get("prefix", provider_prefix)
    
    # Database should come from base_url parsing (already provided), but ensure it's correct
    # If database is "unknown", try to extract from base_url
    if database == "unknown" and base_url:
        parts = base_url.rstrip("/").split("/")
        if len(parts) >= 1:
            # Extract database slug from URL (e.g., mc3d-pbe-v1 from .../main/mc3d-pbe-v1)
            potential_db = parts[-1]
            if potential_db and potential_db not in ["v1", "structures"]:
                database = potential_db
    
    provenance = {
        "source_name": provider_name,
        "provider": provider_prefix,
        "database": database,
        "base_url": base_url,
        "optimade_id": optimade_id,
        "aiida_uuid": attributes.get("uuid") or None,
        "created": attributes.get("ctime") or None,
        "modified": attributes.get("mtime") or None,
        "owner": attributes.get("owner") or None,
        "node_type": attributes.get("node_type") or None,
        "extras": attributes.get("extras") or {},
        "attributes": attributes,  # Full OPTIMADE attributes
    }
    
    if raw is not None:
        provenance["raw"] = raw
    
    # Remove None values for JSON safety
    provenance = {k: v for k, v in provenance.items() if v is not None}
    
    return provenance


def search_online_structures(
    query: str,
    max_results: int = 10,
) -> tuple[str, List[CandidateSummary], List[Optional[PMGStructure]], Optional[str]]:
    """
    Search online structures (OPTIMADE primary, COD fallback).
    
    Uses 2-step approach for OPTIMADE:
    Step 1: Search returns IDs + metadata (no full structure)
    Step 2: Full structures are fetched later via structure_get_online_candidate
    
    Args:
        query: Chemical formula (e.g., "Si", "MoS2")
        max_results: Maximum number of results
        
    Returns:
        (source_summary, candidates, structures, optimade_base) tuple where:
        - source_summary: "optimade", "cod", or "optimade+cod"
        - candidates: List of candidate summaries (with metadata)
        - structures: List of structure objects (None for OPTIMADE entries that need fetching)
        - optimade_base: OPTIMADE base URL if used (None otherwise)
    """
    candidates = []
    structures = []
    source_summary = ""
    optimade_base = None
    
    # Try OPTIMADE first
    base_url, optimade_entries = search_optimade(query, max_results=max_results)
    
    if base_url and optimade_entries:
        optimade_base = base_url
        source_summary = "optimade"
        
        for idx, entry in enumerate(optimade_entries[:max_results]):
            try:
                # OPTIMADE payload is in data[i].attributes
                attrs = entry.get("attributes", {})
                entry_id = entry.get("ulid", "")
                
                if not entry_id:
                    continue
                
                # Extract available metadata
                reduced_formula = attrs.get("chemical_formula_reduced", "?")
                nsites = attrs.get("nsites")
                structure_features = attrs.get("structure_features", [])
                spacegroup_info = attrs.get("spacegroup", {})
                spacegroup = None
                if isinstance(spacegroup_info, dict):
                    spacegroup = spacegroup_info.get("symbol") or spacegroup_info.get("it_number")
                elif isinstance(spacegroup_info, str):
                    spacegroup = spacegroup_info
                
                # For now, don't fetch full structure (2-step approach)
                # Structure will be fetched when candidate is selected
                structure = None
                
                # Create entry data for scoring (minimal)
                entry_data = {
                    "nsites": nsites,
                    "spacegroup": spacegroup,
                    "structure_features": structure_features,
                }
                
                # Create candidate summary (without full structure for now)
                # We'll score later when structure is fetched
                candidate_id = f"opt_{entry_id}"
                candidate = CandidateSummary(
                    candidate_id=candidate_id,
                    label=f"{reduced_formula} ({nsites or '?'} sites)" if nsites else reduced_formula,
                    source="optimade",
                    source_id=entry_id,
                    nsites=nsites or 0,
                    spacegroup=spacegroup,
                    flags=[],  # Will be computed when structure is fetched
                    score=1.0,  # Default score, will be recomputed
                )
                
                # Store base URL in candidate metadata (via source_id format)
                # We'll need to pass base_url separately to fetch function
                candidates.append(candidate)
                structures.append(None)  # Structure fetched later
                
            except Exception as e:
                logger.warning(f"Failed to process OPTIMADE entry {idx}: {e}")
                continue
    
    # Fallback to COD if OPTIMADE returned no results
    if not candidates:
        cod_entries = search_cod(query, max_results=max_results)
        
        if cod_entries:
            source_summary = "cod"
            for idx, entry in enumerate(cod_entries[:max_results]):
                try:
                    structure = entry.get("structure")
                    if structure is None:
                        continue
                    
                    # Score candidate
                    score, flags = score_candidate(structure, "cod", query, entry)
                    
                    # Skip if formula mismatch (hard filter)
                    if "formula_mismatch" in flags:
                        continue
                    
                    # Create candidate summary
                    formula = entry.get("formula", "?")
                    nsites = entry.get("nsites", len(structure))
                    
                    candidate_id = f"cod_{entry.get('entry_id', idx)}"
                    candidate = CandidateSummary(
                        candidate_id=candidate_id,
                        label=f"{formula} ({nsites} sites)",
                        source="cod",
                        source_id=entry.get("entry_id", ""),
                        nsites=nsites,
                        flags=flags,
                        score=score,
                    )
                    
                    candidates.append(candidate)
                    structures.append(structure)
                    
                except Exception as e:
                    logger.warning(f"Failed to process COD entry {idx}: {e}")
                    continue
    else:
        # OPTIMADE had results, but we might supplement with COD if needed
        if len(candidates) < max_results:
            cod_entries = search_cod(query, max_results=max_results - len(candidates))
            source_summary = "optimade+cod"
            
            for idx, entry in enumerate(cod_entries[:max_results - len(candidates)]):
                try:
                    structure = entry.get("structure")
                    if structure is None:
                        continue
                    
                    # Score candidate
                    score, flags = score_candidate(structure, "cod", query, entry)
                    
                    # Skip if formula mismatch
                    if "formula_mismatch" in flags:
                        continue
                    
                    # Create candidate summary
                    formula = entry.get("formula", "?")
                    nsites = entry.get("nsites", len(structure))
                    
                    candidate_id = f"cod_{entry.get('entry_id', len(candidates) + idx)}"
                    candidate = CandidateSummary(
                        candidate_id=candidate_id,
                        label=f"{formula} ({nsites} sites)",
                        source="cod",
                        source_id=entry.get("entry_id", ""),
                        nsites=nsites,
                        flags=flags,
                        score=score,
                    )
                    
                    candidates.append(candidate)
                    structures.append(structure)
                    
                except Exception as e:
                    logger.warning(f"Failed to process COD entry {idx}: {e}")
                    continue
    
    # For COD entries, score them now (they have structures)
    # For OPTIMADE entries, structures are None and will be scored when fetched
    scored_candidates = []
    scored_structures = []
    
    for candidate, structure in zip(candidates, structures):
        if structure is not None:
            # COD entry - score now
            score, flags = score_candidate(structure, candidate.source, query, {})
            if "formula_mismatch" in flags:
                continue  # Skip formula mismatches
            candidate.score = score
            candidate.flags = flags
            scored_candidates.append(candidate)
            scored_structures.append(structure)
        else:
            # OPTIMADE entry - will be scored when structure is fetched
            scored_candidates.append(candidate)
            scored_structures.append(None)
    
    # Sort by score (descending) - OPTIMADE entries with default score will sort lower
    scored_pairs = list(zip(scored_candidates, scored_structures))
    scored_pairs.sort(key=lambda x: x[0].score, reverse=True)
    final_candidates, final_structures = zip(*scored_pairs) if scored_pairs else ([], [])
    
    # Update ranks
    for rank, candidate in enumerate(final_candidates):
        candidate.candidate_id = f"{candidate.source}_{rank}_{candidate.source_id}"
    
    return source_summary or "none", list(final_candidates)[:max_results], list(final_structures)[:max_results], optimade_base
