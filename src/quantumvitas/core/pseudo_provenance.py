"""
Pseudo provenance recognition (Stage A).

Given a pseudopotential file path, compute sha256, sha_token, and element,
then attempt to match it to the pseudo libinfo index to identify its source
library and archive.

This is a read-only recognition system - no side effects, no file modifications.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from quantumvitas.core.pseudo_libinfo import (
    compute_sha256_bytes,
    compute_sha_token_file,
    load_pseudo_libinfo_bundle,
)


@dataclass
class PseudoOccurrenceRef:
    """Reference to a pseudo occurrence in a library archive."""
    
    archive_name: str
    archive_sha256: str
    library_name: Optional[str]
    category: Optional[str]
    library_version: Optional[str]
    xc: Optional[str]
    quality: Optional[str]
    type: Optional[str]
    relativistic: Optional[str]
    path_in_archive: str
    basename: str


@dataclass
class PseudoProvenanceResult:
    """Result of pseudo provenance recognition."""
    
    path: str
    element: Optional[str]
    basename: str
    sha256: str
    sha_token: str
    match_kind: str  # "sha256", "sha_token", or "none"
    matches: List[PseudoOccurrenceRef]
    warnings: List[str]


def compute_sha256_file(path: Path) -> str:
    """
    Compute SHA256 hash of a file (raw bytes).
    
    Args:
        path: Path to file
        
    Returns:
        Hexadecimal SHA256 hash string
    """
    data = path.read_bytes()
    return compute_sha256_bytes(data)


def parse_element_from_upf_text(text: str) -> Optional[str]:
    """
    Parse element symbol from UPF file text.
    
    Handles:
    - UPF v2: <PP_HEADER ... element="Br" ...>
    - UPF legacy: in <PP_INFO> block line like "  Al   Element"
    - Fallback: filename prefix (e.g., "Si.upf", "C.pbe-...UPF")
    
    Args:
        text: UPF file content as text
        
    Returns:
        Normalized element symbol (first letter upper, second lower if exists),
        or None if not found
    """
    # Try UPF v2: <PP_HEADER ... element="X" ...>
    # Pattern: element="X " or element="X"
    pp_header_pattern = r'<PP_HEADER[^>]*element=["\']([A-Za-z]{1,2})'
    match = re.search(pp_header_pattern, text, re.IGNORECASE)
    if match:
        element = match.group(1).strip()
        if element:
            return _normalize_element(element)
    
    # Try legacy UPF: in <PP_INFO> section, look for "Element: X" or "  X   Element"
    pp_info_pattern = r'<PP_INFO>.*?</PP_INFO>'
    pp_info_match = re.search(pp_info_pattern, text, re.IGNORECASE | re.DOTALL)
    if pp_info_match:
        pp_info_text = pp_info_match.group(0)
        # Look for "Element: X" pattern
        element_pattern1 = r'Element:\s*([A-Za-z]{1,2})'
        match = re.search(element_pattern1, pp_info_text, re.IGNORECASE)
        if match:
            element = match.group(1).strip()
            if element:
                return _normalize_element(element)
        
        # Look for "  X   Element" pattern (whitespace-separated)
        element_pattern2 = r'^\s*([A-Za-z]{1,2})\s+Element\s*$'
        for line in pp_info_text.split('\n'):
            match = re.match(element_pattern2, line, re.IGNORECASE)
            if match:
                element = match.group(1).strip()
                if element:
                    return _normalize_element(element)
    
    return None


def _normalize_element(element: str) -> str:
    """
    Normalize element symbol: first letter upper, second lower if exists.
    
    Args:
        element: Raw element string
        
    Returns:
        Normalized element (e.g., "H", "Si", "Br")
    """
    if not element:
        return element
    element = element.strip()
    if len(element) == 1:
        return element.upper()
    elif len(element) == 2:
        return element[0].upper() + element[1].lower()
    else:
        # For longer strings, take first two chars
        return element[0].upper() + element[1].lower() if len(element) > 1 else element.upper()


def _extract_element_from_filename(basename: str) -> Optional[str]:
    """
    Extract element from filename as fallback.
    
    Patterns:
    - "Si.upf" -> "Si"
    - "C.pbe-...UPF" -> "C"
    - "Al.pz-vbc.UPF" -> "Al"
    
    Args:
        basename: Filename (e.g., "Si.pbe-n-rrkjus_psl.1.0.0.UPF")
        
    Returns:
        Element symbol if found, None otherwise
    """
    # Remove extension
    name = basename.rsplit('.', 1)[0] if '.' in basename else basename
    
    # Try to match element at start (1-2 letters followed by dot or dash)
    match = re.match(r'^([A-Za-z]{1,2})[\.\-]', name)
    if match:
        element = match.group(1)
        return _normalize_element(element)
    
    # If no dot/dash, check if entire name is 1-2 letters
    if len(name) <= 2 and name.isalpha():
        return _normalize_element(name)
    
    return None


def _build_sha_token_index(bundle) -> Dict[str, List[Dict]]:
    """
    Build reverse index: sha_token -> list of file entries.
    
    Args:
        bundle: PseudoLibInfoBundle
        
    Returns:
        Dict mapping sha_token to list of file entries from index
    """
    sha_token_index: Dict[str, List[Dict]] = {}
    
    files = bundle.index.get("files", [])
    for file_entry in files:
        sha_token = file_entry.get("sha_token")
        if sha_token:
            if sha_token not in sha_token_index:
                sha_token_index[sha_token] = []
            sha_token_index[sha_token].append(file_entry)
    
    return sha_token_index


def _build_occurrences_index(bundle) -> Dict[str, List[Dict]]:
    """
    Build index: sha256 -> list of occurrences.
    
    Args:
        bundle: PseudoLibInfoBundle
        
    Returns:
        Dict mapping sha256 to list of occurrence entries
    """
    occurrences_index: Dict[str, List[Dict]] = {}
    
    occurrences = bundle.index.get("occurrences", [])
    for occ in occurrences:
        sha256 = occ.get("sha256")
        if sha256:
            if sha256 not in occurrences_index:
                occurrences_index[sha256] = []
            occurrences_index[sha256].append(occ)
    
    return occurrences_index


def _create_occurrence_ref(occ: Dict, file_entry: Dict) -> PseudoOccurrenceRef:
    """
    Create PseudoOccurrenceRef from occurrence and file entry.
    
    Args:
        occ: Occurrence dict from index
        file_entry: File entry dict from index (for basename)
        
    Returns:
        PseudoOccurrenceRef
    """
    archive = occ.get("archive", {})
    library = occ.get("library", {})
    
    # Get basename from file_entry or path_in_archive
    basename = occ.get("path_in_archive", "").split("/")[-1]
    if not basename and file_entry.get("basenames"):
        basename = file_entry["basenames"][0]
    
    return PseudoOccurrenceRef(
        archive_name=archive.get("name", ""),
        archive_sha256=archive.get("sha256", ""),
        library_name=library.get("library_name"),
        category=library.get("category"),
        library_version=library.get("library_version"),
        xc=library.get("xc"),
        quality=library.get("quality"),
        type=library.get("type"),
        relativistic=library.get("relativistic"),
        path_in_archive=occ.get("path_in_archive", basename),
        basename=basename,
    )


def resolve_pseudo_provenance(
    path: Path,
    *,
    repo_root: Optional[Path] = None
) -> PseudoProvenanceResult:
    """
    Resolve pseudo provenance by matching against libinfo index.
    
    Args:
        path: Path to pseudo file
        repo_root: Optional repository root (for testing with tmp bundles)
        
    Returns:
        PseudoProvenanceResult with match information
    """
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Pseudo file not found: {path}")
    
    basename = path.name
    
    # Load bundle
    bundle = load_pseudo_libinfo_bundle(repo_root=repo_root)
    
    # Compute hashes
    sha256 = compute_sha256_file(path)
    sha_token = compute_sha_token_file(path)
    
    # Parse element from file
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        element = parse_element_from_upf_text(text)
    except Exception:
        element = None
    
    # Fallback to filename if file parsing failed
    if element is None:
        element = _extract_element_from_filename(basename)
    
    warnings: List[str] = []
    
    # Check element consistency
    filename_element = _extract_element_from_filename(basename)
    if element and filename_element and element != filename_element:
        warnings.append(
            f"Element mismatch: parsed from file='{element}', "
            f"filename suggests='{filename_element}'"
        )
    
    # Build indices
    occurrences_index = _build_occurrences_index(bundle)
    sha_token_index = _build_sha_token_index(bundle)
    
    # Lookup by sha256 first (primary match)
    matches: List[PseudoOccurrenceRef] = []
    match_kind = "none"
    
    if sha256 in occurrences_index:
        match_kind = "sha256"
        # Find corresponding file entry for basenames
        files = bundle.index.get("files", [])
        file_entry_map = {f.get("sha256"): f for f in files}
        file_entry = file_entry_map.get(sha256)
        
        for occ in occurrences_index[sha256]:
            ref = _create_occurrence_ref(occ, file_entry or {})
            matches.append(ref)
    
    # Fallback to sha_token match (secondary match)
    elif sha_token in sha_token_index:
        match_kind = "sha_token"
        # Find all file entries with this sha_token
        file_entries = sha_token_index[sha_token]
        
        # For each file entry, find occurrences
        for file_entry in file_entries:
            file_sha256 = file_entry.get("sha256")
            if file_sha256 and file_sha256 in occurrences_index:
                for occ in occurrences_index[file_sha256]:
                    ref = _create_occurrence_ref(occ, file_entry)
                    matches.append(ref)
    
    return PseudoProvenanceResult(
        path=str(path),
        element=element,
        basename=basename,
        sha256=sha256,
        sha_token=sha_token,
        match_kind=match_kind,
        matches=matches,
        warnings=warnings,
    )

