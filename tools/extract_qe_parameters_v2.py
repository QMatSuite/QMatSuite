#!/usr/bin/env python3
"""
Extract QE parameter metadata from HTML docs with rich metadata (schema v2).

This script scrapes Quantum ESPRESSO HTML documentation (e.g. INPUT_PW.html)
to extract parameter metadata including:
- parameter name
- type (CHARACTER, INTEGER, REAL, LOGICAL, etc.)
- default value
- allowed values / enums
- free-text description

Output: src/quantumvitas/data/qe_module_parameters.json (schema v2)

This replaces the v1→v2 converter; it directly generates v2 schema from HTML.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib import error, request

from bs4 import BeautifulSoup  # type: ignore

# Import v1 extractor utilities and shared normalization
import sys
from pathlib import Path
tools_dir = Path(__file__).parent
sys.path.insert(0, str(tools_dir))
try:
    from extract_qe_parameters_v1 import DEFAULT_MODULES, ModuleSpec, build_request, fetch_html
except ImportError:
    # Fallback: define locally if import fails
    from dataclasses import dataclass, field
    from typing import List
    from urllib import request
    
    @dataclass
    class ModuleSpec:
        name: str
        doc_url: Optional[str] = None
        doc_name: Optional[str] = None
        aliases: List[str] = field(default_factory=list)
    
    DEFAULT_MODULES: List[ModuleSpec] = [
        ModuleSpec("pw"), ModuleSpec("ph"), ModuleSpec("q2r"), ModuleSpec("matdyn"),
        ModuleSpec("pp"), ModuleSpec("bands"), ModuleSpec("dos"), ModuleSpec("projwfc"),
        ModuleSpec("neb"), ModuleSpec("cp"), ModuleSpec("ld1"), ModuleSpec("hp"),
        ModuleSpec("pwcond"), ModuleSpec("postahc"), ModuleSpec("dynmat"),
        ModuleSpec("oscdft_et"), ModuleSpec("oscdft_pp"), ModuleSpec("band_interpolation"),
        ModuleSpec("cppp"), ModuleSpec("d3hess"), ModuleSpec("ppacf"), ModuleSpec("pprism"),
    ]
    
    def build_request(url: str) -> request.Request:
        return request.Request(url, headers={"User-Agent": "QuantumVITAS-DocExtractor/2.0"})
    
    def fetch_html(url: str) -> str:
        with request.urlopen(build_request(url), timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")

# Import shared normalization utilities (after tools_dir is in path)
try:
    from qe_parameter_normalization import (
        normalize_param_name,
        extract_array_indexing_info,
        get_base_param_name,
    )
except ImportError:
    # Fallback if module not found (shouldn't happen in normal usage)
    def normalize_param_name(text: str) -> Optional[str]:
        if not text:
            return None
        candidate = text.strip()
        candidate = re.sub(r"\s+", "_", candidate)
        if not candidate or len(candidate) < 2 or len(candidate) > 80:
            return None
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate):
            return None
        return candidate
    
    def extract_array_indexing_info(param_name_raw: str, description: Optional[str] = None) -> Optional[dict]:
        bounded_match = re.search(
            r'\b([A-Za-z0-9_]+)\(([a-z]+)\)\s*,\s*\2\s*=\s*(\d+)\s*,\s*(\d+)\b',
            param_name_raw,
            re.IGNORECASE
        )
        if bounded_match:
            base_name = bounded_match.group(1)
            index_name = bounded_match.group(2)
            start = int(bounded_match.group(3))
            end = int(bounded_match.group(4))
            return {
                "index_name": index_name,
                "kind": "bounded",
                "start": start,
                "end": end,
                "keyword_pattern": f"{base_name}({{{index_name}}})"
            }
        
        unbounded_match = re.search(
            r'\b([A-Za-z0-9_]+)\(([a-z]+)\)\b',
            param_name_raw,
            re.IGNORECASE
        )
        if unbounded_match:
            base_name = unbounded_match.group(1)
            index_name = unbounded_match.group(2)
            if description:
                desc_lower = description.lower()
                if (re.search(rf"{re.escape(index_name)}\s*=\s*\d+\s*,\s*\.\.\.", desc_lower) or
                    re.search(rf"{re.escape(index_name)}\s*is\s*(a\s+)?(positive\s+)?integer", desc_lower) or
                    re.search(rf"{re.escape(index_name)}\s*=\s*\d+\s*,\s*[a-z_]+", desc_lower)):
                    return {
                        "index_name": index_name,
                        "kind": "unbounded",
                        "start": 1,
                        "end": None,
                        "keyword_pattern": f"{base_name}({{{index_name}}})"
                    }
        return None
    
    def get_base_param_name(param_name_raw: str) -> Optional[str]:
        base_match = re.search(r'\b([A-Za-z0-9_]+)\([a-z]+\)', param_name_raw, re.IGNORECASE)
        if base_match:
            return normalize_param_name(base_match.group(1))
        if "," in param_name_raw and not "(" in param_name_raw:
            return None
        return normalize_param_name(param_name_raw)

DEFAULT_PATTERN = "https://www.quantum-espresso.org/Doc/INPUT_{name}.html"


@dataclass
class ParameterMetadata:
    """Rich metadata for a single parameter."""
    namelist: str  # e.g., "&CONTROL"
    name: str  # e.g., "calculation"
    type: Optional[str] = None  # e.g., "CHARACTER", "INTEGER", "REAL"
    default: Optional[str] = None  # e.g., "'scf'", "1.0D-4", etc.
    enum: Optional[List[str]] = None  # e.g., ["'scf'", "'nscf'", "'bands'"]
    description: Optional[str] = None  # Free-text description


def download_doc(module_name: str, cache_dir: Path, pattern: str, use_cache: bool, verbose: bool = False) -> Path:
    """
    Download QE documentation HTML for a module.
    
    Args:
        module_name: Module name (e.g., "pw")
        cache_dir: Directory to cache HTML files
        pattern: URL pattern with {name} placeholder
        use_cache: If True and file exists, skip download
        verbose: Print status messages
        
    Returns:
        Path to the cached HTML file
    """
    # Build URL: replace {name} with uppercase module name
    doc_name = module_name.upper().replace("-", "_")
    url = pattern.format(name=doc_name)
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"INPUT_{doc_name}.html"
    
    if use_cache and cache_file.exists():
        if verbose:
            print(f"[{module_name}] Using cached: {cache_file}")
        return cache_file
    
    if verbose:
        print(f"[{module_name}] Downloading: {url}")
    
    try:
        html_content = fetch_html(url)
        cache_file.write_text(html_content, encoding="utf-8")
        if verbose:
            print(f"[{module_name}] Saved to: {cache_file}")
    except error.URLError as exc:
        if verbose:
            print(f"[{module_name}] Download failed: {exc}", file=sys.stderr)
        raise
    
    return cache_file


def extract_toc_parameters(html: str) -> Dict[str, List[str]]:
    """
    Extract parameter names from table of contents (like v1 extractor).
    
    Returns:
        Dict mapping section names to lists of parameter names (preserving ToC order).
        Namelist sections have '&' prefix (e.g., "&CONTROL"), 
        card sections do NOT have '&' prefix (e.g., "K_POINTS").
    """
    soup = BeautifulSoup(html, "html.parser")
    sections: Dict[str, List[str]] = {}
    
    for node in soup.find_all(["p", "h3"]):
        if node.name == "h3":
            heading = node.get_text(" ", strip=True).lower()
            if "introduction" in heading:
                break
            continue
        if node.name != "p":
            continue
        anchor = node.find("a")
        if not anchor:
            continue
        
        section_text = anchor.get_text(" ", strip=True)
        # Normalize section name: look for &NAME pattern first (namelists)
        section_match = re.search(r"&[A-Za-z0-9_]+", section_text)
        if section_match:
            # Namelist sections have & prefix - keep it
            section_name = section_match.group(0).upper()
        else:
            # Card sections don't have & prefix - normalize like v1 extractor (NO & prefix)
            # First, try to preserve existing underscores and convert to uppercase
            # Replace non-alphanumeric (except underscore) with underscore, then collapse multiple underscores
            clean = re.sub(r"[^A-Z0-9_]", "_", section_text).strip()
            # Collapse multiple underscores into single underscore
            clean = re.sub(r"_+", "_", clean)
            # Remove leading/trailing underscores
            clean = clean.strip("_")
            # Convert to uppercase
            clean = clean.upper()
            if clean and len(clean) <= 64:
                section_name = clean  # NO & prefix for card sections
            else:
                continue
        
        # Find parameter links in the following blockquote
        sibling = node.next_sibling
        while sibling is not None and getattr(sibling, "name", None) is None:
            sibling = sibling.next_sibling
        if sibling is None or sibling.name != "blockquote":
            continue
        
        # Use list to preserve order (left to right, top to bottom)
        params = []
        seen_params = set()  # Track seen params to avoid duplicates while preserving order
        for link in sibling.find_all("a"):
            param_text = link.get_text(" ", strip=True)
            # Normalize parameter name (same as v1) - but keep case-sensitive
            param_candidate = re.sub(r"\s+", "_", param_text).strip()
            # Filter out section-like names
            lowered = param_candidate.lower()
            if lowered.startswith(("namelist", "card", "input_", "section", "table")):
                continue
            if param_candidate and 2 <= len(param_candidate) <= 80:
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", param_candidate):
                    # Keep case-sensitive: X != x
                    # Add to list if not already seen (preserve first occurrence order)
                    if param_candidate not in seen_params:
                        params.append(param_candidate)
                        seen_params.add(param_candidate)
        
        if params:
            # Initialize list if section doesn't exist, then extend
            if section_name not in sections:
                sections[section_name] = []
            sections[section_name].extend(params)
    
    return sections


def split_grouped_parameters(param_name: str) -> List[str]:
    """
    Split grouped parameters like "A,B,C,cosAB,cosAC,cosBC" into individual names.
    
    This handles parameters that are documented together but are actually separate.
    Note: Array parameters like "celldm(i), i=1,6" should NOT be split - they are
    stored as a single base name with indexing metadata.
    
    Examples:
        "A,B,C,cosAB,cosAC,cosBC" -> ["A", "B", "C", "cosAB", "cosAC", "cosBC"]
        "nr1,nr2,nr3" -> ["nr1", "nr2", "nr3"]
        "celldm(i), i=1,6" -> ["celldm(i), i=1,6"] (not split - handled separately)
        "calculation" -> ["calculation"]
    
    Returns:
        List of parameter names (may be single element if not grouped)
    """
    # Don't split if it contains array notation
    if "(" in param_name and ")" in param_name:
        return [param_name]
    
    # Split comma-separated list
    if "," in param_name:
        parts = [p.strip() for p in param_name.split(",")]
        # Filter out invalid parts
        valid_parts = [p for p in parts if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", p)]
        if len(valid_parts) > 1:
            return valid_parts
    
    # Not grouped
    return [param_name]


def extract_parameter_metadata_from_table(param_table) -> Optional[List[Dict[str, Any]]]:
    """
    Extract metadata from a parameter table in the HTML.
    
    Each parameter is structured as:
    <table>
      <tr><th>param_name</th><td>TYPE</td></tr>
      <tr><td>Default:</td><td>default_value</td></tr>
      <tr><td colspan="2"><blockquote>description with enum values</blockquote></td></tr>
    </table>
    
    For array parameters like "celldm(i), i=1,6", this returns a single entry with
    the base name "celldm" and indexing metadata.
    
    For grouped parameters like "A,B,C,cosAB,cosAC,cosBC", this returns multiple
    entries (one per parameter).
    
    Args:
        param_table: BeautifulSoup table element for one parameter
        
    Returns:
        List of Dicts with keys: name (base name), type, default, description, enum, indexing (optional);
        or None if parsing fails.
    """
    rows = param_table.find_all("tr")
    if len(rows) < 2:
        return None
    
    # First row: parameter name and type
    first_row = rows[0]
    th = first_row.find("th")
    td_type = first_row.find("td")
    if not th or not td_type:
        return None
    
    param_name_raw = th.get_text(strip=True)
    # Extract type - look for standard type keywords (INTEGER, REAL, CHARACTER, LOGICAL)
    # Sometimes the type cell contains extra text, so extract just the type keyword
    type_text = td_type.get_text(strip=True)
    type_match = re.search(r'\b(INTEGER|REAL|CHARACTER|LOGICAL)\b', type_text, re.IGNORECASE)
    if type_match:
        param_type = type_match.group(1).upper()
    else:
        param_type = type_text  # Fallback to full text if no standard type found
    
    if not param_name_raw:
        return None
    
    # Second row: Default value
    default_value = None
    if len(rows) >= 2:
        second_row = rows[1]
        default_td = second_row.find_all("td")
        if len(default_td) >= 2:
            default_text = default_td[1].get_text(strip=True)
            if default_text and default_text.lower() != "none":
                default_value = default_text
    
    # Extract description first (needed for indexing detection and enum extraction)
    description = None
    blockquote = param_table.find("blockquote")
    if blockquote:
        # Get full text from blockquote for enum extraction (preserve line breaks)
        # We'll use this for both description and enum detection
        description = blockquote.get_text(separator="\n", strip=False)
    
    # Extract enum values based on type
    enum_values = []
    
    # Strategy: Look for enum patterns in description text
    # For INTEGER: look for whitespace-separated integers like "0 1 2 3 -3"
    # For CHARACTER: look for comma-separated quoted strings like "'high','medium','low'"
    
    if description:
        desc_text = description
        
        # Check if parameter type is INTEGER - look for integer enum patterns
        if param_type and "INTEGER" in param_type.upper():
            # Strategy 1: Look for lines starting with integers (like ibrav: "0          free", "1          cubic P")
            # This pattern is common in QE docs where each enum value is on its own line
            lines = desc_text.split('\n')
            line_start_ints = []
            for line in lines:
                # Pattern: line starts with optional whitespace, then integer (possibly negative), then whitespace/description
                # Also handle cases where integer might be followed by more whitespace and text
                match = re.match(r'^\s*(-?\d+)\s+', line)
                if match:
                    int_val = match.group(1)
                    if int_val not in line_start_ints:
                        line_start_ints.append(int_val)
            
            # If we found multiple lines starting with integers, it's likely an enum
            if len(line_start_ints) >= 2:
                enum_values.extend(line_start_ints)
            
            # Strategy 2: Look for whitespace-separated integers in a single line like "0 1 2 3 -3"
            if not enum_values:
                # Pattern: whitespace-separated integers like "0 1 2 3 -3" or "0, 1, 2, 3"
                integer_enum_patterns = [
                    r'\b(-?\d+)\s+(-?\d+)(?:\s+(-?\d+))+(?:\s+\.\.\.)?',  # "0 1 2 3" (at least 2 integers)
                    r'\b(-?\d+)\s*,\s*(-?\d+)(?:\s*,\s*(-?\d+))+(?:\s*,\s*\.\.\.)?',  # "0, 1, 2, 3" (at least 2 integers)
                ]
                
                for pattern in integer_enum_patterns:
                    matches = re.finditer(pattern, desc_text)
                    for match in matches:
                        # Extract all integers from this match
                        full_match = match.group(0)
                        ints = re.findall(r'-?\d+', full_match)
                        if len(ints) >= 2:  # At least 2 integers
                            enum_values.extend(ints)
                            break  # Use first match
                    if enum_values:
                        break
        
        # Check if parameter type is CHARACTER - look for quoted string enum patterns
        elif param_type and "CHARACTER" in param_type.upper():
            # Pattern: comma-separated quoted strings like "'high','medium','low'"
            # Look for patterns like: 'value1','value2','value3' or "value1","value2","value3"
            quoted_enum_pattern = r"(['\"])([^'\"]{1,50})\1(?:\s*,\s*(['\"])([^'\"]{1,50})\3)*"
            matches = re.finditer(quoted_enum_pattern, desc_text)
            
            for match in matches:
                # Extract all quoted values from this match
                full_match = match.group(0)
                # Split by comma and extract quoted values
                quoted_values = re.findall(r"(['\"])([^'\"]{1,50})\1", full_match)
                
                if quoted_values:
                    # Check if first item is a quoted string
                    first_quote_char = quoted_values[0][0]
                    # All should use same quote character
                    if all(q[0] == first_quote_char for q in quoted_values):
                        # Extract values (with quotes preserved)
                        values = [f"{q[0]}{q[1]}{q[0]}" for q in quoted_values]
                        if len(values) >= 2:  # At least 2 values to be an enum
                            enum_values.extend(values)
                            break  # Use first match
        
        # Also check definition lists (<dl><dt><tt>value</tt></dt>) for both types
        if blockquote and not enum_values:
            for dl in blockquote.find_all("dl"):
                dt_values = []
                for dt in dl.find_all("dt"):
                    tt = dt.find("tt")
                    if tt:
                        enum_text = tt.get_text(strip=True)
                        # Remove trailing colons
                        enum_text = re.sub(r":\s*$", "", enum_text)
                        if enum_text and 1 <= len(enum_text) <= 50:
                            dt_values.append(enum_text)
                
                # Check if all values in definition list are same type
                if dt_values:
                    # Check if first is integer
                    if param_type and "INTEGER" in param_type.upper():
                        if all(re.match(r'^-?\d+$', v.strip()) for v in dt_values):
                            enum_values.extend(dt_values)
                    # Check if first is quoted string
                    elif param_type and "CHARACTER" in param_type.upper():
                        if all(re.match(r"^['\"].*['\"]$", v.strip()) for v in dt_values):
                            enum_values.extend(dt_values)
                    # If type unknown, check if all are same pattern
                    else:
                        first_pattern = None
                        all_match = True
                        for v in dt_values:
                            v_clean = v.strip()
                            if re.match(r'^-?\d+$', v_clean):
                                pattern = 'integer'
                            elif re.match(r"^['\"].*['\"]$", v_clean):
                                pattern = 'quoted'
                            else:
                                all_match = False
                                break
                            
                            if first_pattern is None:
                                first_pattern = pattern
                            elif first_pattern != pattern:
                                all_match = False
                                break
                        
                        if all_match and first_pattern and len(dt_values) >= 2:
                            enum_values.extend(dt_values)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_enum_values = []
    for v in enum_values:
        if v not in seen:
            seen.add(v)
            unique_enum_values.append(v)
    enum_values = unique_enum_values
    
    # Limit enum size
    if len(enum_values) > 50:
        enum_values = enum_values[:50]
    
    # If too many, probably not an enum list (might be general description text)
    # But allow more for integer enums (like ibrav with many values)
    max_enum_size = 20 if param_type and "CHARACTER" in param_type.upper() else 50
    if len(enum_values) > max_enum_size:
        enum_values = []
    
    # Check if this is an array parameter (like "celldm(i), i=1,6")
    indexing_info = extract_array_indexing_info(param_name_raw, description)
    
    if indexing_info:
        # Array parameter: store as single base name with indexing metadata
        base_name = get_base_param_name(param_name_raw)
        if not base_name:
            return None
        
        return [{
            "name": base_name,  # v1-style base name (e.g., "celldm")
            "type": param_type,
            "default": default_value,
            "enum": enum_values if enum_values else None,
            "description": description,
            "indexing": indexing_info,
        }]
    
    # Check if this is a grouped parameter (like "A,B,C,cosAB,cosAC,cosBC")
    grouped_names = split_grouped_parameters(param_name_raw)
    
    if len(grouped_names) > 1:
        # Grouped parameters: return one entry per parameter
        result = []
        for grouped_name in grouped_names:
            base_name = normalize_param_name(grouped_name)
            if base_name:
                result.append({
                    "name": base_name,
                    "type": param_type,
                    "default": default_value,
                    "enum": enum_values if enum_values else None,
                    "description": description,
                })
        return result if result else None
    
    # Regular single parameter
    base_name = normalize_param_name(param_name_raw)
    if not base_name:
        return None
    
    return [{
        "name": base_name,
        "type": param_type,
        "default": default_value,
        "enum": enum_values if enum_values else None,
        "description": description,
    }]


def extract_card_metadata(soup: BeautifulSoup, card_name: str) -> Optional[Dict[str, Any]]:
    """
    Extract metadata for a card section (e.g., K_POINTS).
    
    Cards are documented with:
    - Card: NAME { option1 | option2 | ... }
    - Default: option
    - Description of each option
    
    Args:
        soup: BeautifulSoup object of the HTML
        card_name: Name of the card (e.g., "K_POINTS")
        
    Returns:
        Dict with keys: name, type (enum of options), default, description, enum (list of options);
        or None if not found
    """
    # Search for "Card: CARD_NAME" pattern
    card_pattern = re.compile(rf"Card:\s*{re.escape(card_name)}", re.IGNORECASE)
    
    for elem in soup.find_all(["h2", "h3", "p"]):
        text = elem.get_text()
        if card_pattern.search(text):
            # Found card section - extract metadata
            # Look for options in braces: { option1 | option2 | ... }
            options_match = re.search(r"\{([^}]+)\}", text)
            options = []
            if options_match:
                options_text = options_match.group(1)
                # Split by | and clean
                options = [opt.strip() for opt in options_text.split("|") if opt.strip()]
            
            # Look for default value
            default = None
            # Search in following elements for "Default:" pattern
            next_elem = elem.next_sibling
            search_count = 0
            while next_elem and search_count < 10:
                if hasattr(next_elem, 'get_text'):
                    next_text = next_elem.get_text()
                    default_match = re.search(r"Default:\s*([^\n]+)", next_text, re.IGNORECASE)
                    if default_match:
                        default = default_match.group(1).strip()
                        break
                next_elem = next_elem.next_sibling
                search_count += 1
            
            # Extract description from following text
            description = None
            desc_parts = []
            next_elem = elem.next_sibling
            search_count = 0
            while next_elem and search_count < 20:
                if hasattr(next_elem, 'get_text'):
                    next_text = next_elem.get_text(strip=True)
                    # Stop if we hit another card or namelist
                    if re.search(r"Card:\s*[A-Z_]+|Namelist:\s*&[A-Z_]+", next_text, re.IGNORECASE):
                        break
                    if next_text and len(next_text) > 20:
                        desc_parts.append(next_text)
                next_elem = next_elem.next_sibling
                search_count += 1
            
            if desc_parts:
                description = " ".join(desc_parts[:5]).strip()  # Limit to first 5 parts
            
            if options or default or description:
                return {
                    "name": card_name,
                    "type": "CHARACTER" if options else None,
                    "default": default,
                    "enum": options if options else None,
                    "description": description,
                }
    
    return None


def extract_card_parameter_metadata(soup: BeautifulSoup, card_name: str, param_name: str) -> Optional[Dict[str, Any]]:
    """
    Extract metadata for a parameter within a card section.
    
    Card parameters are documented in tables or definition lists within the card section.
    
    Args:
        soup: BeautifulSoup object of the HTML
        card_name: Name of the card (e.g., "K_POINTS")
        param_name: Name of the parameter (e.g., "nks")
        
    Returns:
        Dict with keys: name, type, default, description, enum; or None if not found
    """
    # Find the card section first
    card_pattern = re.compile(rf"Card:\s*{re.escape(card_name)}", re.IGNORECASE)
    card_elem = None
    
    for elem in soup.find_all(["h2", "h3", "p"]):
        if card_pattern.search(elem.get_text()):
            card_elem = elem
            break
    
    if not card_elem:
        return None
    
    # Search for parameter in tables or definition lists after the card heading
    # Look for parameter name in following elements
    next_elem = card_elem.next_sibling
    search_count = 0
    
    while next_elem and search_count < 50:
        if hasattr(next_elem, 'name'):
            # Check if this is a table with the parameter
            if next_elem.name == "table":
                rows = next_elem.find_all("tr")
                for row in rows:
                    th = row.find("th")
                    if th and param_name.lower() in th.get_text().lower():
                        # Found parameter table - extract metadata
                        meta_list = extract_parameter_metadata_from_table(next_elem)
                        if meta_list:
                            for meta in meta_list:
                                if meta and meta.get("name") and param_name.lower() == meta.get("name").lower():
                                    return meta
            
            # Check if this is a definition list
            elif next_elem.name == "dl":
                for dt in next_elem.find_all("dt"):
                    if param_name.lower() in dt.get_text().lower():
                        # Found parameter in definition list
                        dd = dt.find_next_sibling("dd")
                        if dd:
                            desc_text = dd.get_text(strip=True)
                            # Try to extract type from description
                            type_match = re.search(r"\b(INTEGER|REAL|CHARACTER|LOGICAL)\b", desc_text, re.IGNORECASE)
                            param_type = type_match.group(1).upper() if type_match else None
                            
                            return {
                                "name": param_name,
                                "type": param_type,
                                "default": None,
                                "enum": None,
                                "description": desc_text,
                            }
            
            # Stop if we hit another card or namelist
            if next_elem.name in ["h2", "h3"]:
                next_text = next_elem.get_text()
                if re.search(r"Card:\s*[A-Z_]+|Namelist:\s*&[A-Z_]+", next_text, re.IGNORECASE):
                    break
        
        next_elem = next_elem.next_sibling
        search_count += 1
    
    return None


def parse_module_doc(module_name: str, html_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """
    Parse QE HTML documentation and extract rich parameter metadata.
    
    Args:
        module_name: Module name (e.g., "pw")
        html_path: Path to HTML file
        verbose: Print diagnostic information
        
    Returns:
        Dict with structure:
        {
            "doc_url": "...",
            "parameters": {
                "&CONTROL.calculation": {
                    "namelist": "&CONTROL",  # Namelist sections have & prefix
                    "name": "calculation",
                    "type": "CHARACTER",
                    "default": "'scf'",
                    "enum": ["'scf'", "'nscf'", ...],
                    "description": "..."
                },
                ...
            }
        }
    """
    html_content = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Extract ToC parameter names - use this for card sections and validation
    toc_params = extract_toc_parameters(html_content)
    
    # Build doc URL
    doc_name = module_name.upper().replace("-", "_")
    doc_url = DEFAULT_PATTERN.format(name=doc_name)
    
    # FIRST PASS: Extract ALL parameters from ToC (like v1 extractor)
    # This gives us the complete list of all parameters - both namelist and card sections
    parameters: Dict[str, Dict[str, Any]] = {}
    card_metadata: Dict[str, Dict[str, Any]] = {}  # Store card-level metadata
    
    for section_name, toc_param_set in toc_params.items():
        # Check if this is a card section (no & prefix)
        is_card = not section_name.startswith("&")
        
        if is_card:
            # Extract card-level metadata
            card_meta = extract_card_metadata(soup, section_name)
            if card_meta:
                card_metadata[section_name] = card_meta
                if verbose:
                    print(f"[{module_name}] Found card metadata for {section_name}: {len(card_meta.get('enum', []))} options")
        
        # Preserve ToC order when initializing parameters
        for param_name in toc_param_set:  # toc_param_set is now a list, preserving order
            # Normalize parameter name to v1 style (base name for arrays)
            # For array parameters in ToC, they might appear as "celldm" or "celldm(i)"
            # We want to store as base name "celldm" to match v1
            base_name = get_base_param_name(param_name) or normalize_param_name(param_name)
            if not base_name:
                continue
            
            key = f"{section_name}.{base_name}"
            parameters[key] = {
                "namelist": section_name,
                "name": base_name,  # v1-style base name
                "type": None,  # Will be filled in second pass if found in HTML tables
                "default": None,
                "enum": None,
                "description": None,
            }
            
            # For card parameters, try to extract metadata from card section
            if is_card:
                card_param_meta = extract_card_parameter_metadata(soup, section_name, param_name)
                if card_param_meta:
                    parameters[key].update({
                        "type": card_param_meta.get("type"),
                        "default": card_param_meta.get("default"),
                        "enum": card_param_meta.get("enum"),
                        "description": card_param_meta.get("description"),
                    })
    
    if verbose:
        print(f"[{module_name}] Initialized {len(parameters)} parameters from ToC")
    
    # SECOND PASS: Find metadata for parameters in detailed sections (HTML tables)
    # Match ToC parameters with their detailed descriptions to fill in metadata
    current_section = None
    
    # Strategy: iterate through all elements, track current section, find parameter tables
    for element in soup.find_all(["h2", "h3", "table"]):
        # Check if this is a namelist heading
        if element.name in ["h2", "h3"]:
            heading_text = element.get_text()
            # Look for "Namelist: &NAME" pattern
            namelist_match = re.search(r"Namelist:\s*(&[A-Za-z0-9_]+)", heading_text, re.IGNORECASE)
            if namelist_match:
                current_section = namelist_match.group(1).upper()
                if verbose:
                    print(f"[{module_name}] Found namelist section: {current_section}")
                continue
            
            # Look for "Card: NAME" pattern (cards don't have & prefix - keep it that way)
            card_match = re.search(r"Card:\s*([A-Za-z0-9_]+)", heading_text, re.IGNORECASE)
            if card_match:
                card_name = card_match.group(1).upper()
                current_section = card_name  # NO & prefix for card sections
                if verbose:
                    print(f"[{module_name}] Found card section: {current_section}")
                continue
        
        # Check if this is a parameter table
        if element.name == "table" and current_section:
            # Parameter tables have a specific structure: first row has <th> with param name, <td> with type
            rows = element.find_all("tr")
            if len(rows) >= 2:
                first_row = rows[0]
                th = first_row.find("th")
                td_type = first_row.find("td")
                
                # Check if this looks like a parameter table (has <th> with param name, <td> with type)
                if th and td_type:
                    param_name_candidate = th.get_text(strip=True)
                    type_candidate = td_type.get_text(strip=True)
                    
                    # Check if this looks like a parameter table (has type like CHARACTER, INTEGER, etc.)
                    # Note: param_name_candidate might be array notation like "celldm(i), i=1,6" or grouped like "A,B,C"
                    if param_name_candidate and type_candidate:
                        # This is a parameter table - extract metadata (may return multiple parameters)
                        meta_list = extract_parameter_metadata_from_table(element)
                        if meta_list:
                            # Handle expanded parameters (array/grouped)
                            for meta in meta_list:
                                if meta and meta.get("name"):
                                    param_name = meta["name"]  # Base name (v1-style, e.g., "celldm")
                                    key = f"{current_section}.{param_name}"
                                    
                                    # Update existing parameter (from ToC) with metadata, or add if not found
                                    if key in parameters:
                                        # Update with metadata (including indexing if present)
                                        update_dict = {
                                            "type": meta.get("type"),
                                            "default": meta.get("default"),
                                            "enum": meta.get("enum"),
                                            "description": meta.get("description"),
                                        }
                                        # Add indexing if present
                                        if "indexing" in meta:
                                            update_dict["indexing"] = meta["indexing"]
                                        parameters[key].update(update_dict)
                                    else:
                                        # Parameter not in ToC but found in table - add it anyway
                                        param_dict = {
                                            "namelist": current_section,
                                            "name": param_name,
                                            "type": meta.get("type"),
                                            "default": meta.get("default"),
                                            "enum": meta.get("enum"),
                                            "description": meta.get("description"),
                                        }
                                        # Add indexing if present
                                        if "indexing" in meta:
                                            param_dict["indexing"] = meta["indexing"]
                                        parameters[key] = param_dict
    
    if verbose:
        sections_found = len(set(k.split(".", 1)[0] for k in parameters.keys()))
        print(f"[{module_name}] Found {len(parameters)} parameters in {sections_found} sections")
        
        # Check against ToC
        toc_total = sum(len(params) for params in toc_params.values())
        missing_from_toc = []
        for section, params in toc_params.items():
            for param in params:
                key = f"{section}.{param}"
                if key not in parameters:
                    missing_from_toc.append((section, param))
        
        if missing_from_toc:
            if verbose:
                print(f"[{module_name}] Warning: {len(missing_from_toc)} ToC params not found in detailed sections (showing first 5):")
                for section, param in missing_from_toc[:5]:
                    print(f"  - {section}.{param}")
        if len(parameters) < toc_total * 0.8:  # If we found less than 80% of ToC params
            print(f"[{module_name}] Warning: Found {len(parameters)} params, ToC lists {toc_total} ({len(parameters)*100//toc_total if toc_total > 0 else 0}%)")
    
    # Create ordered parameters dict to preserve ToC order
    # Python 3.7+ dicts preserve insertion order, but we need to ensure
    # parameters are in ToC order, with any new parameters from second pass appended
    ordered_parameters: Dict[str, Dict[str, Any]] = {}
    
    # First, add all parameters in ToC order
    for section_name, toc_param_list in toc_params.items():
        for param_name in toc_param_list:
            base_name = get_base_param_name(param_name) or normalize_param_name(param_name)
            if not base_name:
                continue
            key = f"{section_name}.{base_name}"
            if key in parameters:
                ordered_parameters[key] = parameters[key]
    
    # Then, add any parameters found in second pass that weren't in ToC
    for key, param in parameters.items():
        if key not in ordered_parameters:
            ordered_parameters[key] = param
    
    result = {
        "doc_url": doc_url,
        "parameters": ordered_parameters,
    }
    
    # Add card metadata if any was found
    if card_metadata:
        result["card_metadata"] = card_metadata
        if verbose:
            print(f"[{module_name}] Found metadata for {len(card_metadata)} card sections")
    
    return result


def load_module_specs(
    names: Optional[List[str]], use_pattern_only: bool
) -> List[ModuleSpec]:
    """Load module specs (reused from v1)."""
    base = {spec.name.lower(): spec for spec in DEFAULT_MODULES}
    if not names:
        return list(base.values())
    specs = []
    for name in names:
        key = name.lower()
        if key in base and not use_pattern_only:
            specs.append(base[key])
        else:
            specs.append(ModuleSpec(name=key))
    return specs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract QE parameter metadata from HTML docs (schema v2 with rich metadata)."
    )
    parser.add_argument(
        "--modules",
        nargs="*",
        help="Limit extraction to specific module names (default: all 22 modules)",
    )
    parser.add_argument(
        "--pattern",
        default=DEFAULT_PATTERN,
        help=f"Format string for documentation URLs (default: {DEFAULT_PATTERN})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "src" / "quantumvitas" / "data" / "qe_module_parameters.json",
        help="Output path for v2 JSON file",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(__file__).parent.parent / "temp" / "qe_docs",
        help="Directory to cache HTML files",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use cached HTML files if available (skip download)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed diagnostic information",
    )
    parser.add_argument(
        "--validate-against-legacy",
        action="store_true",
        help="After generation, validate against legacy v1 snapshot",
    )
    args = parser.parse_args()
    
    specs = load_module_specs(args.modules, False)
    results: Dict[str, Dict[str, Any]] = {}
    failures: Dict[str, str] = {}
    
    for spec in specs:
        try:
            html_path = download_doc(
                spec.name,
                args.cache_dir,
                args.pattern,
                args.use_cache,
                args.verbose,
            )
            module_data = parse_module_doc(spec.name, html_path, args.verbose)
            results[spec.name] = module_data
        except Exception as exc:
            failures[spec.name] = str(exc)
            if args.verbose:
                print(f"[{spec.name}] Failed: {exc}", file=sys.stderr)
    
    if failures:
        sys.stderr.write("Some modules could not be processed:\n")
        for name, reason in failures.items():
            sys.stderr.write(f"  - {name}: {reason}\n")
    
    # Build final JSON structure
    payload: Dict[str, Any] = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "doc_pattern": args.pattern,
        "modules": {},
    }
    
    for module_name, module_data in results.items():
        payload["modules"][module_name] = module_data
    
    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2 if args.pretty else None, sort_keys=False)
        handle.write("\n")
    
    total_params = sum(len(mod.get("parameters", {})) for mod in payload["modules"].values())
    
    # Count parameters with indexing metadata
    params_with_indexing = 0
    indexing_examples = []
    
    for module_name, module_data in payload["modules"].items():
        params = module_data.get("parameters", {})
        for key, param in params.items():
            if "indexing" in param:
                params_with_indexing += 1
                if len(indexing_examples) < 5:  # Collect first 5 examples
                    indexing_examples.append({
                        "module": module_name,
                        "key": key,
                        "name": param.get("name"),
                        "indexing": param.get("indexing"),
                    })
    
    sys.stdout.write(
        f"[extract_v2] Generated schema v2 for {len(results)} modules, {total_params} parameters total.\n"
    )
    sys.stdout.write(
        f"[extract_v2] Parameters with indexing metadata: {params_with_indexing}\n"
    )
    sys.stdout.write(
        f"[extract_v2] Output written to {args.output}\n"
    )
    
    # Print indexing examples
    if indexing_examples:
        sys.stdout.write("\n=== INDEXING METADATA EXAMPLES ===\n")
        for ex in indexing_examples:
            idx = ex["indexing"]
            sys.stdout.write(f"\n{ex['module']}.{ex['key']}:\n")
            sys.stdout.write(f"  name: {ex['name']}\n")
            sys.stdout.write(f"  indexing:\n")
            sys.stdout.write(f"    kind: {idx.get('kind')}\n")
            sys.stdout.write(f"    index_name: {idx.get('index_name')}\n")
            sys.stdout.write(f"    start: {idx.get('start')}\n")
            sys.stdout.write(f"    end: {idx.get('end')}\n")
            sys.stdout.write(f"    keyword_pattern: {idx.get('keyword_pattern')}\n")
    
    # Optional validation against legacy
    if args.validate_against_legacy:
        legacy_path = args.output.parent / "qe_module_parameters.legacy.json"
        if legacy_path.exists():
            sys.stdout.write(f"[extract_v2] Validating against legacy snapshot: {legacy_path}\n")
            # Run comparison script as subprocess
            import subprocess
            result = subprocess.run(
                ["python3", str(Path(__file__).parent / "compare_qe_parameter_maps.py")],
                capture_output=True,
                text=True,
            )
            sys.stdout.write(result.stdout)
            if result.returncode != 0:
                sys.stderr.write(result.stderr)
    
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
