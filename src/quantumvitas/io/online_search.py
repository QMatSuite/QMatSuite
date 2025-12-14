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


# Materials Cloud OPTIMADE endpoints (provider+database scoped)
# Try in order: mc3d-pbe-v1, mc3d-pbesol-v2, mc3d-pbesol-v1
OPTIMADE_BASES = [
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
                    "id": f"cod_{entry_id}",
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
                    "id": f"cod_{entry_id}",
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


def fetch_structure_from_optimade(base_url: str, entry_id: str) -> Optional[PMGStructure]:
    """
    Fetch full structure from OPTIMADE entry by ID.
    
    Args:
        base_url: OPTIMADE base URL (e.g., "https://optimade.materialscloud.org/main/mc3d-pbe-v1")
        entry_id: Structure entry ID
        
    Returns:
        pymatgen Structure object or None if fetch fails
    """
    if not REQUESTS_AVAILABLE:
        return None
    
    try:
        # Request full structure data including coordinates
        url = f"{base_url}/v1/structures/{entry_id}"
        # Don't specify response_fields - get all available fields
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        structure_data = data.get("data", {})
        
        if not structure_data:
            return None
        
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
        
        # Build species list for each site
        site_species = []
        for site_species_idx in species_at_sites:
            if isinstance(site_species_idx, list):
                # Multiple species per site (partial occupancy) - take first
                site_species_idx = site_species_idx[0] if site_species_idx else 0
            elif isinstance(site_species_idx, int):
                pass  # Already an index
            else:
                site_species_idx = 0
            
            if site_species_idx < len(species_list):
                species_info = species_list[site_species_idx]
                # Extract chemical symbol
                if isinstance(species_info, dict):
                    chem_symbols = species_info.get("chemical_symbols", [])
                    if chem_symbols:
                        site_species.append(chem_symbols[0])
                    else:
                        site_species.append("X")
                elif isinstance(species_info, str):
                    site_species.append(species_info)
                else:
                    site_species.append("X")
            else:
                site_species.append("X")
        
        # Ensure we have the same number of species as positions
        if len(site_species) != len(cartesian_positions):
            logger.warning(f"Species count ({len(site_species)}) != positions count ({len(cartesian_positions)})")
            # Pad or truncate to match
            if len(site_species) < len(cartesian_positions):
                site_species.extend(["X"] * (len(cartesian_positions) - len(site_species)))
            else:
                site_species = site_species[:len(cartesian_positions)]
        
        # Build structure
        from pymatgen.core import Lattice
        lattice = Lattice(lattice_vectors)
        structure = PMGStructure(lattice, site_species, cartesian_positions, coords_are_cartesian=True)
        
        return structure
        
    except Exception as e:
        logger.warning(f"Failed to fetch structure from OPTIMADE {base_url}/{entry_id}: {e}")
        return None


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
                entry_id = entry.get("id", "")
                
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
