"""
PubChem molecule search provider.

PR4: PubChem search, SDF parsing, and molecule structure support.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from pymatgen.core import Molecule as PMGMolecule
    PYMATGEN_AVAILABLE = True
except ImportError:
    PYMATGEN_AVAILABLE = False

logger = logging.getLogger(__name__)

# PubChem API base URL
PUBCHEM_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Rate limiting: 200ms delay between requests (PubChem limit: 5 req/sec)
PUBCHEM_RATE_LIMIT_DELAY = 0.2

# Last request timestamp (for rate limiting)
_last_request_time: float = 0.0


@dataclass
class PubChemCandidate:
    """PubChem molecule candidate (internal model)."""
    cid: str  # PubChem Compound ID
    name: str  # Compound name
    formula: str  # Molecular formula
    molecule: Optional[PMGMolecule] = None  # Parsed molecule structure (if fetched)
    metadata: Dict[str, Any] = field(default_factory=dict)  # PubChem metadata


def _rate_limit() -> None:
    """Enforce PubChem rate limiting (200ms delay)."""
    global _last_request_time
    current_time = time.time()
    elapsed = current_time - _last_request_time
    if elapsed < PUBCHEM_RATE_LIMIT_DELAY:
        time.sleep(PUBCHEM_RATE_LIMIT_DELAY - elapsed)
    _last_request_time = time.time()


def search_by_name(query: str, max_results: int = 10) -> List[str]:
    """
    Search PubChem by compound name.
    
    Args:
        query: Compound name (e.g., "caffeine", "aspirin")
        max_results: Maximum number of CIDs to return
        
    Returns:
        List of PubChem CIDs (strings)
    """
    if not REQUESTS_AVAILABLE:
        logger.warning("requests library not available, skipping PubChem search")
        return []
    
    _rate_limit()
    
    try:
        url = f"{PUBCHEM_BASE_URL}/compound/name/{query}/cids/JSON"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 404:
            # Not found - return empty (caller can try formula search)
            return []
        
        response.raise_for_status()
        data = response.json()
        
        # Extract CIDs
        cids = data.get("IdentifierList", {}).get("CID", [])
        # Convert to strings and limit
        cid_strings = [str(cid) for cid in cids[:max_results]]
        
        logger.info(f"PubChem name search for '{query}' returned {len(cid_strings)} CIDs")
        return cid_strings
        
    except Exception as e:
        logger.warning(f"PubChem name search failed: {e}")
        return []


def _poll_pubchem_listkey(list_key: str, max_results: int, max_polls: int = 10, poll_interval: float = 2.0) -> List[str]:
    """
    Poll PubChem for async formula search results.

    PubChem formula searches return HTTP 202 with a ListKey.
    We must poll until the results are ready or we time out.
    """
    if not REQUESTS_AVAILABLE:
        return []

    poll_url = f"{PUBCHEM_BASE_URL}/compound/listkey/{list_key}/cids/JSON"
    for attempt in range(max_polls):
        time.sleep(poll_interval)
        _rate_limit()
        try:
            resp = requests.get(poll_url, timeout=10)
            if resp.status_code == 202:
                # Still processing
                continue
            if resp.status_code == 404:
                logger.warning(f"PubChem listkey {list_key} not found (expired?)")
                return []
            resp.raise_for_status()
            data = resp.json()
            cids = data.get("IdentifierList", {}).get("CID", [])
            return [str(cid) for cid in cids[:max_results]]
        except Exception as e:
            logger.warning(f"PubChem listkey poll attempt {attempt + 1} failed: {e}")

    logger.warning(f"PubChem listkey {list_key} timed out after {max_polls} polls")
    return []


def search_by_formula(query: str, max_results: int = 10) -> List[str]:
    """
    Search PubChem by molecular formula.
    
    Args:
        query: Molecular formula (e.g., "C8H10N4O2", "C6H6")
        max_results: Maximum number of CIDs to return
        
    Returns:
        List of PubChem CIDs (strings)
    """
    if not REQUESTS_AVAILABLE:
        logger.warning("requests library not available, skipping PubChem search")
        return []
    
    _rate_limit()
    
    try:
        url = f"{PUBCHEM_BASE_URL}/compound/formula/{query}/cids/JSON"
        response = requests.get(url, timeout=10)

        if response.status_code == 404:
            return []

        # PubChem formula search is async — 202 means "still processing"
        if response.status_code == 202:
            data = response.json()
            list_key = data.get("Waiting", {}).get("ListKey")
            if list_key:
                cids = _poll_pubchem_listkey(list_key, max_results)
                return cids
            return []

        response.raise_for_status()
        data = response.json()

        # Extract CIDs
        cids = data.get("IdentifierList", {}).get("CID", [])
        cid_strings = [str(cid) for cid in cids[:max_results]]

        logger.info(f"PubChem formula search for '{query}' returned {len(cid_strings)} CIDs")
        return cid_strings

    except Exception as e:
        logger.warning(f"PubChem formula search failed: {e}")
        return []


def fetch_3d_sdf(cid: str) -> Optional[str]:
    """
    Fetch 3D SDF record for a PubChem CID.
    
    Args:
        cid: PubChem Compound ID
        
    Returns:
        SDF content as string, or None if not available
    """
    if not REQUESTS_AVAILABLE:
        return None
    
    _rate_limit()
    
    try:
        url = f"{PUBCHEM_BASE_URL}/compound/cid/{cid}/record/SDF"
        params = {"record_type": "3d"}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 404:
            logger.debug(f"PubChem CID {cid} has no 3D SDF")
            return None
        
        response.raise_for_status()
        return response.text
        
    except Exception as e:
        logger.warning(f"Failed to fetch PubChem SDF for CID {cid}: {e}")
        return None


def parse_sdf_to_molecule(sdf_content: str, cid: str) -> Optional[PMGMolecule]:
    """
    Parse SDF content to pymatgen Molecule.
    
    Args:
        sdf_content: SDF file content (string)
        cid: PubChem CID (for error messages)
        
    Returns:
        pymatgen Molecule, or None if parsing fails
    """
    if not PYMATGEN_AVAILABLE:
        logger.warning("pymatgen not available, cannot parse SDF")
        return None
    
    try:
        # Try pymatgen's SDF parser
        molecule = PMGMolecule.from_str(sdf_content, fmt="sdf")
        return molecule
    except Exception as e:
        logger.warning(f"Failed to parse SDF for CID {cid}: {e}")
        # Fallback: manual parsing (simplified)
        try:
            return _parse_sdf_manual(sdf_content)
        except Exception as e2:
            logger.warning(f"Manual SDF parsing also failed for CID {cid}: {e2}")
            return None


def _parse_sdf_manual(sdf_content: str) -> PMGMolecule:
    """
    Manual SDF parsing (fallback if pymatgen fails).
    
    Parses MOL block format:
    ```
    HEADER
    COMMENT
    COUNTS LINE: " 15 14  0  0  0  0  0  0  0  0999 V2000"
    ATOM LINES: "    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0"
    BOND LINES: ...
    ```
    """
    lines = sdf_content.split('\n')

    # SDF MOL block layout (V2000):
    #   Line 0: molecule name
    #   Line 1: program/timestamp
    #   Line 2: comment (often blank)
    #   Line 3: counts line  "aaabbblllfffcccsssxxxrrrpppiiimmmvvvvvv"
    #   Lines 4..(4+num_atoms-1): atom block
    #   Bond block follows
    counts_idx = 3
    if counts_idx >= len(lines):
        raise ValueError("SDF too short — missing counts line")

    counts_line = lines[counts_idx]
    parts = counts_line.split()
    if len(parts) < 2:
        raise ValueError(f"Invalid SDF counts line: {counts_line!r}")

    num_atoms = int(parts[0])
    num_bonds = int(parts[1])

    # Parse atom lines (start immediately after counts line)
    atoms_start = counts_idx + 1
    species = []
    coords = []
    
    for i in range(num_atoms):
        line_idx = atoms_start + i
        if line_idx >= len(lines):
            break
        
        line = lines[line_idx]
        # Format: "  x.xxxx  y.yyyy  z.zzzz Elem ..."
        parts = line.split()
        if len(parts) < 4:
            continue
        
        try:
            x = float(parts[0])
            y = float(parts[1])
            z = float(parts[2])
            element = parts[3]
            
            species.append(element)
            coords.append([x, y, z])
        except (ValueError, IndexError):
            continue
    
    if not species:
        raise ValueError("No atoms found in SDF")
    
    # Create Molecule
    molecule = PMGMolecule(species, coords)
    return molecule


def search_pubchem(
    query: str,
    max_results: int = 10,
) -> List[PubChemCandidate]:
    """
    Search PubChem for molecules.
    
    Strategy:
    1. Try name search first (more specific)
    2. If no results, try formula search
    3. For each CID, fetch 3D SDF and parse to molecule
    
    Args:
        query: Compound name or formula
        max_results: Maximum number of results
        
    Returns:
        List of PubChemCandidate (with parsed molecules if 3D SDF available)
    """
    candidates = []
    
    # Try name search first
    cids = search_by_name(query, max_results=max_results)
    
    # If no results, try formula search
    if not cids:
        cids = search_by_formula(query, max_results=max_results)
    
    # Fetch 3D SDF for each CID
    for cid in cids:
        sdf_content = fetch_3d_sdf(cid)
        if not sdf_content:
            # Skip if no 3D SDF available
            logger.debug(f"Skipping CID {cid} - no 3D SDF available")
            continue
        
        # Parse SDF to molecule
        molecule = parse_sdf_to_molecule(sdf_content, cid)
        if not molecule:
            continue
        
        # Extract metadata from SDF (simplified - just formula for now)
        formula = molecule.composition.formula
        
        candidate = PubChemCandidate(
            cid=cid,
            name=query,  # Use query as name (could be enhanced with PubChem name lookup)
            formula=formula,
            molecule=molecule,
            metadata={"sdf_cid": cid},
        )
        candidates.append(candidate)
    
    return candidates

