#!/usr/bin/env python3
"""
Extract QE parameter metadata from HTML docs with section hierarchy and metadata (schema v3).

V3 extends v2 with:
- Section tree (hierarchical) with supercard support (NEB BEGIN_* / END_*)
- Section-level descriptions
- Optionality classification (optional/required/conditional/none)
- Card structured fields (options, default_option, options_description, syntax, items)

This script scrapes Quantum ESPRESSO HTML documentation (e.g. INPUT_PW.html)
to extract parameter metadata including:
- parameter name
- type (CHARACTER, INTEGER, REAL, LOGICAL, etc.)
- default value (parsed from "Default:" row label)
- status (parsed from "Status:" row label)
- see_also (parsed from "See:" row label)
- allowed values / enums (from spans.flag, dl structures)
- free-text description (rendered from HTML structure)

Output: src/qmatsuite/data/qe_module_parameters.json (schema v3)

V3 ALGORITHM SUMMARY:
====================

1) Section Hierarchy Building:
   - Traverse all <h2> elements in document order
   - Classify section kind: namelist/card/supercard/line_of_input/other
   - Use stack to track open supercards (BEGIN_* pushes, END_* pops)
   - Build hierarchical tree: supercard → children → (namelist/card/...)
   - Attach sections to current supercard parent (if any) or module root

2) Section-Level Description Extraction:
   - Collect content after <h2> until first <h3> or parameter table
   - Render using render_description() (same as v3)
   - Store in section.description

3) Optionality Classification:
   - Analyze section.description for keywords
   - Rules: "if" → conditional; "optional" (not "required") → optional;
            "required" (not "optional") → required; both → conditional; else → none

4) Card Structured Fields:
   - options: Parse from header braces "{ ... }" or "Card's options:" row
   - default_option: Parse from "Default:" row
   - options_description: Parse <dl> blocks (option → description mapping)
   - syntax: Extract from <h3>Syntax:</h3> block
   - items: Extract from <h3>Description of items:</h3> block

5) V3 Parameter Extraction (preserved):
   - ToC-driven initialization + metadata fill + extras appended
   - All v3 logic intact (Default/Status/See parsing, enum extraction, indexing, etc.)

6) Output:
   - Write JSON with sort_keys=False to preserve insertion order
   - Schema version 3 with module.sections (hierarchical) and module.parameters (v2 logic)

V3 ALGORITHM SUMMARY:
====================

1) Inputs:
   - QE INPUT_*.html files (per module), parsed with BeautifulSoup

2) Stage 1: ToC-driven ordering
   - Extract section headings (namelist/card/other) and parameter names from the Table of Contents
   - Initialize ordered parameters list based on ToC traversal order
   - Preserve document order (no sorting)

3) Stage 2: Parameter metadata extraction from definition tables
   - Parse param raw name from table header <th>
   - Parse type from the first row <td>
   - Parse Default/Status/See by reading the LEFT-CELL label text, not row position
   - This fixes cases where "See:" appears before "Default:" (e.g., celldm parameter)

4) Enums:
   - Prefer extracting from <span class="flag"> inside <dl>/<dt> blocks
   - Fallback heuristics (quoted tokens, numeric options in <pre>) only when no flags present
   - Preserve quotes in enum values (e.g., 'debug', 'high')

5) Indexing detection:
   - Recognize bounded indexed pattern like "celldm(i), i=1,6"
   - Recognize symbolic bounds like "Hubbard_U(i), i=1,ntyp" (stores end_symbol)
   - Recognize simple "base(index)" as symbolic/unbounded indexing
   - Handle grouped indexed bases: "e1(i), e2(i), e3(i), i=1,3" -> expand to multiple params
   - Handle fixed-index expansions: "if_pos(1), if_pos(2), if_pos(3)" -> compress to single base
   - Handle multi-dimensional: "Hubbard_occ(ityp,i), (ityp,i) = (1,1) . . . (ntyp,3)"
   - Split grouped names like "A,B,C" into separate params (only if no parentheses)

6) Description renderer:
   - Render <pre> with preserved line breaks and dedent
   - Render <dl> into bullet-style lines
   - Normalize whitespace and collapse excessive blank lines (max 2 consecutive)
   - Handle <br>, inline tags (<a>, <i>, <b>, <span>)

7) Merge strategy:
   - Fill ToC params first (preserve order)
   - Second pass discovers additional params from tables not in ToC; append them at the end
   - Section attribution: for each table, find nearest previous h2/h3 matching "Namelist:" or "Card:"
   - This prevents "Description of items:" tables from being incorrectly attributed

8) Output:
   - Write JSON with sort_keys=False to preserve insertion order as encountered
   - Schema version 3 with optional status and see_also fields

Key improvements over v2:
- A) Better default/status/see parsing: reads left cell text, not row index
- B) Better enum extraction: prioritizes spans.flag, then dl structures
- C) Improved indexing support for array parameters (bounded, symbolic, multi-dimensional)
- D) Better description rendering: handles pre, dl, blockquote structure
- E) Schema version 3 with optional status and see_also fields
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
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
        return request.Request(url, headers={"User-Agent": "QMatSuite-DocExtractor/3.0"})
    
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


def parse_indexing_and_expand(raw_name: str, description_text: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parse indexing metadata for array-like parameters and expand grouped patterns.
    
    Handles all patterns:
    A) 1D bounded with numeric bounds: celldm(i), i=1,6
    B) 1D bounded with symbolic end: Hubbard_U(i), i=1,ntyp
    C) Grouped indexed bases: e1(i), e2(i), e3(i), i=1,3
    D) Fixed-index expansions: if_pos(1), if_pos(2), if_pos(3)
    E) Ellipsis form: atom(1) atom(2) ... atom(nat_todo)
    F) Multi-dimensional: Hubbard_occ(ityp,i), (ityp,i) = (1,1) . . . (ntyp,3)
    
    Returns:
        List of dicts, each with {"base_name": str, "indexing": dict|None}
        If parsing fails, returns single entry with base_name and raw_spec fallback.
    """
    raw_name = raw_name.strip()
    if not raw_name:
        return []
    
    # Pattern F: Multi-dimensional arrays
    # Example: "Hubbard_occ(ityp,i), (ityp,i) = (1,1) . . . (ntyp,3)"
    # Or: "starting_ns_eigenvalue(m,ispin,ityp), (m,ispin,ityp) = (1,1,1) . . . (2*lmax+1,nspin or npol,ntyp)"
    multi_match = re.search(
        r'^([A-Za-z0-9_]+)\(([^)]+)\)\s*,\s*\(([^)]+)\)\s*=\s*\(([^)]+)\)\s*\.\s*\.\s*\.\s*\(([^)]+)\)',
        raw_name,
        re.IGNORECASE
    )
    if multi_match:
        base_name = multi_match.group(1)
        index_names_str = multi_match.group(2)
        index_names = [name.strip() for name in index_names_str.split(',')]
        start_tuple_str = multi_match.group(4)
        end_tuple_str = multi_match.group(5)
        
        start_values = [v.strip() for v in start_tuple_str.split(',')]
        end_values = [v.strip() for v in end_tuple_str.split(',')]
        
        if len(index_names) == len(start_values) == len(end_values):
            base_normalized = normalize_param_name(base_name)
            if base_normalized:
                dims = []
                for i, idx_name in enumerate(index_names):
                    dim = {"name": idx_name}
                    try:
                        dim["start"] = int(start_values[i])
                    except ValueError:
                        dim["start"] = 1  # Default
                    
                    # Try to parse end as integer
                    try:
                        dim["end"] = int(end_values[i])
                    except ValueError:
                        # Symbolic or expression
                        dim["end"] = None
                        dim["end_symbol"] = end_values[i]
                        # Check if it's an expression
                        if any(op in end_values[i] for op in ['+', '-', '*', '/', '(', ')', 'or']):
                            dim["end_expr"] = end_values[i]
                    
                    dims.append(dim)
                
                return [{
                    "base_name": base_normalized,
                    "indexing": {
                        "kind": "multi",
                        "dims": dims,
                        "raw_spec": raw_name,
                        "keyword_pattern": f"{base_normalized}({{{','.join(index_names)}}})"
                    }
                }]
    
    # Pattern C: Grouped indexed bases with shared range
    # Example: "e1(i), e2(i), e3(i), i=1,3" or "e1(i), e2(i), i=1,3"
    grouped_match = re.search(
        r'^((?:[A-Za-z0-9_]+)\(([A-Za-z0-9_]+)\)\s*,\s*)+([A-Za-z0-9_]+)\(([A-Za-z0-9_]+)\)\s*,\s*\4\s*=\s*(\d+)\s*,\s*(\d+|[A-Za-z0-9_]+)',
        raw_name,
        re.IGNORECASE
    )
    if grouped_match:
        # Extract all base names
        base_pattern = r'([A-Za-z0-9_]+)\([A-Za-z0-9_]+\)'
        bases = re.findall(base_pattern, raw_name)
        index_name = grouped_match.group(2)  # Should be same for all
        start = int(grouped_match.group(5))
        end_str = grouped_match.group(6)
        
        result = []
        for base in bases:
            base_normalized = normalize_param_name(base)
            if base_normalized:
                indexing = {
                    "index_name": index_name,
                    "kind": "bounded",
                    "start": start,
                    "keyword_pattern": f"{base_normalized}({{{index_name}}})"
                }
                try:
                    indexing["end"] = int(end_str)
                except ValueError:
                    indexing["end"] = None
                    indexing["end_symbol"] = end_str
                indexing["raw_spec"] = raw_name
                result.append({"base_name": base_normalized, "indexing": indexing})
        
        if result:
            return result
    
    # Pattern D: Fixed-index expansions
    # Example: "if_pos(1), if_pos(2), if_pos(3)" or "constr(1), constr(2), constr(3), constr(4)"
    # Also handle space-separated: "xq(1) xq(2) xq(3)"
    fixed_indices_match = re.findall(r'([A-Za-z0-9_]+)\((\d+)\)', raw_name)
    if fixed_indices_match and len(fixed_indices_match) > 1:
        # Check if all have same base name
        base_names = [m[0] for m in fixed_indices_match]
        if len(set(base_names)) == 1:  # All same base
            base_name = base_names[0]
            indices = [int(m[1]) for m in fixed_indices_match]
            base_normalized = normalize_param_name(base_name)
            if base_normalized:
                # Check if consecutive starting at 1
                indices_sorted = sorted(indices)
                if indices_sorted == list(range(1, len(indices) + 1)):
                    # Consecutive 1..N
                    return [{
                        "base_name": base_normalized,
                        "indexing": {
                            "kind": "bounded",
                            "index_name": "i",
                            "start": 1,
                            "end": len(indices),
                            "keyword_pattern": f"{base_normalized}({{i}})",
                            "raw_spec": raw_name
                        }
                    }]
                else:
                    # Non-consecutive, store explicit indices
                    return [{
                        "base_name": base_normalized,
                        "indexing": {
                            "kind": "explicit",
                            "explicit_indices": indices,
                            "keyword_pattern": f"{base_normalized}({{i}})",
                            "raw_spec": raw_name
                        }
                    }]
    
    # Pattern E: Ellipsis form
    # Example: "atom(1) atom(2) ... atom(nat_todo)"
    ellipsis_match = re.search(
        r'^([A-Za-z0-9_]+)\((\d+)\)\s+[A-Za-z0-9_]+\(\d+\)\s+\.\.\.\s+[A-Za-z0-9_]+\(([A-Za-z0-9_]+)\)',
        raw_name,
        re.IGNORECASE
    )
    if ellipsis_match:
        base_name = ellipsis_match.group(1)
        start = int(ellipsis_match.group(2))
        end_symbol = ellipsis_match.group(3)
        base_normalized = normalize_param_name(base_name)
        if base_normalized:
            return [{
                "base_name": base_normalized,
                "indexing": {
                    "kind": "bounded",
                    "index_name": "i",
                    "start": start,
                    "end": None,
                    "end_symbol": end_symbol,
                    "keyword_pattern": f"{base_normalized}({{i}})",
                    "raw_spec": raw_name
                }
            }]
    
    # Pattern A: 1D bounded with numeric bounds
    # Example: "celldm(i), i=1,6"
    bounded_match = re.search(
        r'^\s*([A-Za-z0-9_]+)\(\s*([A-Za-z0-9_]+)\s*\)\s*,\s*\2\s*=\s*(\d+)\s*,\s*(\d+)\s*$',
        raw_name,
        re.IGNORECASE
    )
    if bounded_match:
        base_name = bounded_match.group(1)
        index_name = bounded_match.group(2)
        start = int(bounded_match.group(3))
        end = int(bounded_match.group(4))
        base_normalized = normalize_param_name(base_name)
        if base_normalized:
            return [{
                "base_name": base_normalized,
                "indexing": {
                    "index_name": index_name,
                    "kind": "bounded",
                    "start": start,
                    "end": end,
                    "keyword_pattern": f"{base_normalized}({{{index_name}}})"
                }
            }]
    
    # Pattern B: 1D bounded with symbolic end
    # Example: "Hubbard_U(i), i=1,ntyp" or "starting_magnetization(i), i=1,ntyp"
    bounded_symbolic_match = re.search(
        r'^\s*([A-Za-z0-9_]+)\(\s*([A-Za-z0-9_]+)\s*\)\s*,\s*\2\s*=\s*(\d+)\s*,\s*([A-Za-z0-9_]+)\s*$',
        raw_name,
        re.IGNORECASE
    )
    if bounded_symbolic_match:
        base_name = bounded_symbolic_match.group(1)
        index_name = bounded_symbolic_match.group(2)
        start = int(bounded_symbolic_match.group(3))
        end_symbol = bounded_symbolic_match.group(4)
        base_normalized = normalize_param_name(base_name)
        if base_normalized:
            return [{
                "base_name": base_normalized,
                "indexing": {
                    "index_name": index_name,
                    "kind": "bounded",
                    "start": start,
                    "end": None,
                    "end_symbol": end_symbol,
                    "keyword_pattern": f"{base_normalized}({{{index_name}}})",
                    "raw_spec": raw_name
                }
            }]
    
    # Pattern: Simple indexed without explicit bounds
    # Example: "alpha_mix(niter)"
    simple_indexed_match = re.search(
        r'^\s*([A-Za-z0-9_]+)\(\s*([A-Za-z0-9_]+)\s*\)\s*$',
        raw_name,
        re.IGNORECASE
    )
    if simple_indexed_match:
        base_name = simple_indexed_match.group(1)
        index_name = simple_indexed_match.group(2)
        base_normalized = normalize_param_name(base_name)
        if base_normalized:
            # Check description for hints
            is_unbounded = False
            end_symbol = None
            if description_text:
                desc_lower = description_text.lower()
                # Look for patterns like "i=1,ntyp" or "i=1,..."
                symbol_match = re.search(
                    rf"{re.escape(index_name)}\s*=\s*\d+\s*,\s*([A-Za-z0-9_]+)",
                    desc_lower
                )
                if symbol_match:
                    end_symbol = symbol_match.group(1)
                    is_unbounded = True
                elif (re.search(rf"{re.escape(index_name)}\s*=\s*\d+\s*,\s*\.\.\.", desc_lower) or
                      re.search(rf"{re.escape(index_name)}\s*is\s*(a\s+)?(positive\s+)?integer", desc_lower)):
                    is_unbounded = True
            
            # Check if index name suggests variable size
            size_var_patterns = [r"niter", r"ntyp", r"nat", r"nband", r"nspin", r"nfile"]
            for pattern in size_var_patterns:
                if re.search(pattern, index_name, re.IGNORECASE):
                    is_unbounded = True
                    if not end_symbol:
                        end_symbol = index_name
                    break
            
            if is_unbounded:
                indexing = {
                    "index_name": index_name,
                    "kind": "unbounded" if not end_symbol else "bounded",
                    "start": 1,
                    "end": None,
                    "keyword_pattern": f"{base_normalized}({{{index_name}}})"
                }
                if end_symbol:
                    indexing["end_symbol"] = end_symbol
                indexing["raw_spec"] = raw_name
                return [{"base_name": base_normalized, "indexing": indexing}]
            else:
                # Still return as unbounded if pattern matches
                return [{
                    "base_name": base_normalized,
                    "indexing": {
                        "index_name": index_name,
                        "kind": "unbounded",
                        "start": 1,
                        "end": None,
                        "keyword_pattern": f"{base_normalized}({{{index_name}}})",
                        "raw_spec": raw_name
                    }
                }]
    
    # Fallback: Any parameter with parentheses should NOT be dropped
    # Extract base name and store raw spec
    paren_match = re.search(r'^([A-Za-z0-9_]+)\(', raw_name)
    if paren_match:
        base_name = paren_match.group(1)
        base_normalized = normalize_param_name(base_name)
        if base_normalized:
            return [{
                "base_name": base_normalized,
                "indexing": {
                    "kind": "unknown",
                    "raw_spec": raw_name
                }
            }]
    
    # Not an indexed parameter - return as-is
    base_normalized = normalize_param_name(raw_name)
    if base_normalized:
        return [{"base_name": base_normalized, "indexing": None}]
    
    return []


def render_description(blockquote_tag) -> str:
    """
    Render description from blockquote HTML to clean text.
    
    Handles:
    - <pre> blocks: dedent, normalize newlines, compress blank lines
    - <dl> blocks: render as bullet lists
    - <br>: newline
    - Other inline tags: extract visible text only
    
    Returns:
        Clean description text with max 2 consecutive blank lines
    """
    if not blockquote_tag:
        return ""
    
    blocks = []
    
    # Traverse direct children of blockquote in order
    for child in blockquote_tag.children:
        if not hasattr(child, 'name'):
            continue
        
        if child.name == 'pre':
            # Extract text from <pre>
            pre_text = child.get_text()
            # Normalize newlines
            lines = pre_text.split('\n')
            # Dedent: compute min leading spaces among non-empty lines
            non_empty_lines = [line for line in lines if line.strip()]
            if non_empty_lines:
                min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
                lines = [line[min_indent:] if line.strip() else line for line in lines]
            # Rstrip trailing spaces per line
            lines = [line.rstrip() for line in lines]
            # Compress blank lines: replace 3+ consecutive blank lines with at most 2
            compressed = []
            blank_count = 0
            for line in lines:
                if not line.strip():
                    blank_count += 1
                    if blank_count <= 2:
                        compressed.append(line)
                else:
                    blank_count = 0
                    compressed.append(line)
            blocks.append('\n'.join(compressed))
        
        elif child.name == 'dl':
            # Render definition list as bullets
            dl_items = []
            for dt in child.find_all('dt'):
                dd = dt.find_next_sibling('dd')
                dt_text = dt.get_text(separator=" ", strip=True)
                # Remove trailing colons
                dt_text = re.sub(r":\s*$", "", dt_text)
                
                if dd:
                    # Check if dd contains <pre>
                    dd_pre = dd.find('pre')
                    if dd_pre:
                        dd_text = render_description(dd_pre.parent)  # Recursive for pre
                    else:
                        dd_text = dd.get_text(separator=" ", strip=True)
                    
                    # Format as bullet: "- {dt_text}: {dd_text}"
                    bullet = f"- {dt_text}: {dd_text}"
                    # If dd_text is multi-line, indent subsequent lines by 2 spaces
                    if '\n' in dd_text:
                        lines = bullet.split('\n')
                        bullet = lines[0] + '\n' + '\n'.join('  ' + line for line in lines[1:])
                    dl_items.append(bullet)
                else:
                    dl_items.append(f"- {dt_text}")
            
            if dl_items:
                blocks.append('\n'.join(dl_items))
        
        elif child.name == 'br':
            blocks.append('')
        
        elif child.name in ('a', 'i', 'b', 'span', 'tt'):
            # Inline tags: extract visible text only
            text = child.get_text(separator=" ", strip=True)
            if text:
                blocks.append(text)
        
        elif child.name in ('p', 'div'):
            # Block elements: extract text
            text = child.get_text(separator=" ", strip=True)
            if text:
                blocks.append(text)
    
    # Join blocks with newlines
    result = '\n'.join(blocks)
    
    # Trim leading/trailing blank lines
    result = result.strip('\n')
    
    # Collapse runs of whitespace-only lines to at most one blank line between paragraphs
    lines = result.split('\n')
    compressed = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank:
            if not prev_blank:
                compressed.append(line)
            prev_blank = True
        else:
            compressed.append(line)
            prev_blank = False
    
    result = '\n'.join(compressed)
    
    # Ensure no more than 2 consecutive blank lines anywhere
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result


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
    Extract parameter names from table of contents (like v1/v2 extractor).
    
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
            clean = re.sub(r"[^A-Z0-9_]", "_", section_text).strip()
            clean = re.sub(r"_+", "_", clean)
            clean = clean.strip("_")
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
    Extract metadata from a parameter table in the HTML (v3: improved parsing).
    
    Each parameter is structured as:
    <table>
      <tr><th>param_name</th><td>TYPE</td></tr>
      <tr><td>Default:</td><td>default_value</td></tr>  (or Status:, See:, etc.)
      <tr><td colspan="2"><blockquote>description with enum values</blockquote></td></tr>
    </table>
    
    v3 improvements:
    - A) Parse Default/Status/See by reading left cell text, not row index
    - B) Better enum extraction: prioritize spans.flag, then dl structures
    - D) Better description rendering: handle pre, dl, blockquote structure
    
    Args:
        param_table: BeautifulSoup table element for one parameter
        
    Returns:
        List of Dicts with keys: name (base name), type, default, status, see_also,
        description, enum, indexing (optional);
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
    
    # Check if type is in a nested table (some QE docs have this structure)
    nested_table = td_type.find("table")
    if nested_table:
        nested_first_row = nested_table.find_all("tr")
        if nested_first_row:
            nested_td = nested_first_row[0].find("td")
            if nested_td:
                td_type = nested_td  # Use the nested td for type extraction
    
    # Extract type - look for standard type keywords (INTEGER, REAL, CHARACTER, LOGICAL)
    type_text = ""
    found_block = False
    for item in td_type.children:
        if found_block:
            break
        if isinstance(item, str):
            text = item.strip()
            if text:
                type_text += text + " "
        elif hasattr(item, 'name'):
            # Stop at first nested table, blockquote, pre, or div
            if item.name in ('table', 'pre', 'blockquote', 'div'):
                found_block = True
                break
            # Get text from inline elements
            child_text = item.get_text(strip=True)
            if child_text:
                type_text += child_text + " "
    
    type_text = type_text.strip()
    
    # Look for type pattern
    type_match = re.search(
        rf'{re.escape(param_name_raw)}\s*(INTEGER|REAL|CHARACTER|LOGICAL)',
        type_text,
        re.IGNORECASE
    )
    if not type_match:
        # Try without parameter name prefix (just find first TYPE keyword)
        type_match = re.search(r'\b(INTEGER|REAL|CHARACTER|LOGICAL)\b', type_text, re.IGNORECASE)
    
    if type_match:
        param_type = type_match.group(1).upper()
    else:
        # Last resort: get all text and search in first 500 chars
        all_text = td_type.get_text(separator=" ", strip=True)
        type_match = re.search(r'\b(INTEGER|REAL|CHARACTER|LOGICAL)\b', all_text[:500], re.IGNORECASE)
        if type_match:
            param_type = type_match.group(1).upper()
        else:
            param_type = "UNKNOWN"
    
    if not param_name_raw:
        return None
    
    # v3 IMPROVEMENT A: Parse Default/Status/See by reading left cell text, not row index
    default_value = None
    status_value = None
    see_also_value = None
    
    # Scan all rows after row 0
    for row in rows[1:]:
        tds = row.find_all("td")
        if len(tds) >= 2:
            left_cell = tds[0]
            right_cell = tds[1]
            left_text = left_cell.get_text(strip=True).lower()
            
            # Check for label rows by left cell text
            if "default:" in left_text:
                default_text = right_cell.get_text(strip=True)
                if default_text and default_text.lower() != "none":
                    default_value = default_text
            
            elif "status:" in left_text:
                status_text = right_cell.get_text(strip=True)
                if status_text:
                    status_value = status_text
            
            elif "see:" in left_text:
                # See can be text or list of <a> links
                see_links = right_cell.find_all("a")
                if see_links:
                    see_also_value = [link.get_text(strip=True) for link in see_links]
                else:
                    see_text = right_cell.get_text(strip=True)
                    if see_text:
                        see_also_value = see_text
    
    # Extract description blockquote (needed for indexing detection and enum extraction)
    description = None
    blockquote = param_table.find("blockquote")
    if blockquote:
        # v3 IMPROVEMENT D: Use improved description renderer
        description = render_description(blockquote)
    
    # v3 IMPROVEMENT B: Better enum extraction - prioritize spans.flag, then dl structures
    enum_values = []
    
    if blockquote:
        # Strategy 1: Look for spans with class="flag" (highest priority)
        flag_spans = blockquote.find_all("span", class_="flag")
        if flag_spans:
            for span in flag_spans:
                flag_text = span.get_text(strip=True)
                if flag_text and flag_text not in enum_values:
                    enum_values.append(flag_text)
        
        # Strategy 2: Check definition lists (<dl><dt><tt>value</tt></dt>)
        if not enum_values:
            for dl in blockquote.find_all("dl"):
                dt_values = []
                for dt in dl.find_all("dt"):
                    # Look for spans.flag within dt
                    dt_flags = dt.find_all("span", class_="flag")
                    if dt_flags:
                        for flag_span in dt_flags:
                            flag_text = flag_span.get_text(strip=True)
                            if flag_text:
                                dt_values.append(flag_text)
                    else:
                        # Fallback: check tt element
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
        
        # Strategy 3: Fallback heuristics (only if no flags or dl found)
        if not enum_values and description:
            desc_text = description
            
            # For INTEGER: look for lines starting with integers
            if param_type and "INTEGER" in param_type.upper():
                lines = desc_text.split('\n')
                line_start_ints = []
                for line in lines:
                    match = re.match(r'^\s*(-?\d+)\s+', line)
                    if match:
                        int_val = match.group(1)
                        if int_val not in line_start_ints:
                            line_start_ints.append(int_val)
                
                if len(line_start_ints) >= 2:
                    enum_values.extend(line_start_ints)
            
            # For CHARACTER: look for quoted tokens in text
            elif param_type and "CHARACTER" in param_type.upper():
                # Look for patterns like: 'scf' 'nscf' ...
                quoted_pattern = r"(['\"])([^'\"]{1,50})\1"
                matches = re.finditer(quoted_pattern, desc_text)
                quoted_vals = []
                for match in matches:
                    val = match.group(0)  # Includes quotes
                    if val not in quoted_vals:
                        quoted_vals.append(val)
                
                if len(quoted_vals) >= 2:
                    enum_values.extend(quoted_vals)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_enum_values = []
    for v in enum_values:
        if v not in seen:
            seen.add(v)
            unique_enum_values.append(v)
    enum_values = unique_enum_values
    
    # Limit enum size
    max_enum_size = 20 if param_type and "CHARACTER" in param_type.upper() else 50
    if len(enum_values) > max_enum_size:
        enum_values = []
    
    # v3 IMPROVEMENT C: Improved indexing support with expansion
    expanded_params = parse_indexing_and_expand(param_name_raw, description)
    
    if expanded_params:
        # Return one entry per expanded base parameter
        result = []
        for exp in expanded_params:
            base_name = exp.get("base_name")
            indexing_info = exp.get("indexing")
            
            if not base_name:
                continue
            
            param_dict = {
                "name": base_name,
                "type": param_type,
                "default": default_value,
                "status": status_value,
                "see_also": see_also_value,
                "enum": enum_values if enum_values else None,
                "description": description,
            }
            
            if indexing_info:
                param_dict["indexing"] = indexing_info
            
            result.append(param_dict)
        
        if result:
            return result
    
    # Fallback: Check if this is a grouped parameter (like "A,B,C,cosAB,cosAC,cosBC")
    # Only if no parentheses (indexed params are handled above)
    if "(" not in param_name_raw and "," in param_name_raw:
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
                        "status": status_value,
                        "see_also": see_also_value,
                        "enum": enum_values if enum_values else None,
                        "description": description,
                    })
            return result if result else None
    
    # Regular single parameter (fallback)
    base_name = normalize_param_name(param_name_raw)
    if not base_name:
        return None
    
    return [{
        "name": base_name,
        "type": param_type,
        "default": default_value,
        "status": status_value,
        "see_also": see_also_value,
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
                                "status": None,
                                "see_also": None,
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


def classify_section_kind_and_name(h2_element) -> Tuple[str, str]:
    """
    Classify section kind and extract name from h2 element.
    
    Returns:
        (kind, name) where:
        - kind: "namelist" | "card" | "supercard" | "line_of_input" | "other"
        - name: section name (e.g., "&CONTROL", "K_POINTS", "BEGIN_PATH_INPUT")
    """
    header_text = h2_element.get_text(" ", strip=True)
    header_text_normalized = " ".join(header_text.split())  # Normalize whitespace
    
    # Check for Namelist (handle "Namelist: & NAME" with space after &)
    namelist_match = re.search(r"Namelist:\s*&?\s*([A-Za-z0-9_]+)", header_text_normalized, re.IGNORECASE)
    if namelist_match:
        name = "&" + namelist_match.group(1).upper()
        return ("namelist", name)
    
    # Check for Card
    card_match = re.search(r"Card:\s*([A-Za-z0-9_]+)", header_text_normalized, re.IGNORECASE)
    if card_match:
        card_name = card_match.group(1).upper()
        # Extract options from braces if present: "Card: NAME { opt1 | opt2 }"
        return ("card", card_name)
    
    # Check for Line-of-input
    line_match = re.search(r"Line-of-input:\s*([A-Za-z0-9_]+)", header_text_normalized, re.IGNORECASE)
    if line_match:
        return ("line_of_input", line_match.group(1).upper())
    
    # Check for supercard (BEGIN_* or END_*)
    if "BEGIN_" in header_text_normalized or "END_" in header_text_normalized:
        # Extract BEGIN_* or END_* token
        supercard_match = re.search(r"(BEGIN_[A-Za-z0-9_]+|END_[A-Za-z0-9_]+)", header_text_normalized)
        if supercard_match:
            return ("supercard", supercard_match.group(1).upper())
    
    # Fallback: other
    return ("other", header_text_normalized.upper()[:64])


def extract_section_description(h2_element, soup: BeautifulSoup) -> Optional[str]:
    """
    Extract section-level description from content after h2 until first h3 or parameter table.
    
    The structure is typically:
    <table>
      <tr><th><h2>Namelist: &NAME</h2></th></tr>
      <tr><td>
        <table>
          <tr><td>
            <p><b>Description text here</b></p>  <!-- This is what we want -->
            <a name="param">...</a><table>...</table>  <!-- Parameter table - stop here -->
          </td></tr>
        </table>
      </td></tr>
    </table>
    
    Args:
        h2_element: The h2 element for the section
        soup: BeautifulSoup object (for finding next elements)
        
    Returns:
        Rendered description text, or None if no description found
    """
    # Find the block_root (the outer table containing the section)
    block_root = h2_element.find_parent("table")
    if not block_root:
        return None
    
    # Find the <td> in the row after the h2's row
    tr_with_h2 = h2_element.find_parent("tr")
    if not tr_with_h2:
        return None
    
    next_tr = tr_with_h2.find_next_sibling("tr")
    if not next_tr:
        return None
    
    content_td = next_tr.find("td")
    if not content_td:
        return None
    
    # Find nested table inside content_td (fallback to content_td if missing)
    nested_table = content_td.find("table")
    if nested_table:
        # Find the <td> inside nested_table (fallback to content_td if missing)
        nested_td = nested_table.find("td")
        if not nested_td:
            nested_td = content_td
    else:
        # Fallback: use content_td directly or first <td> within it
        nested_td = content_td.find("td") or content_td
    
    # Collect content elements from nested_td until we hit a parameter table or h3
    content_elements = []
    
    for child in nested_td.children:
        if not hasattr(child, 'name'):
            continue
        
        # Stop at h3
        if child.name == "h3":
            break
        
        # Stop at parameter-definition table
        # Improved detection: check if td contains a type token (INTEGER, REAL, CHARACTER, LOGICAL)
        if child.name == "table":
            rows = child.find_all("tr")
            if len(rows) >= 2:
                first_row = rows[0]
                th = first_row.find("th")
                td_type = first_row.find("td")
                if th and td_type:
                    th_text = th.get_text(strip=True).lower()
                    td_text = td_type.get_text(strip=True).lower()
                    
                    # Whitelist for metadata tables (case-insensitive, apostrophe-tolerant)
                    th_text_norm = re.sub(r"'", "", th_text)  # Remove apostrophes for matching
                    is_metadata_table = (
                        th_text in ["card's options:", "default:", "status:", "see:", "see also:"] or
                        "card" in th_text_norm and "options" in th_text_norm or
                        "default" in th_text or
                        "status" in th_text or
                        "see" in th_text
                    )
                    
                    # Only stop if this looks like a parameter-definition table
                    # (td contains "type" or a known type token, and it's not a metadata table)
                    is_type_cell = (
                        td_text == "type" or
                        any(token in td_text for token in ["integer", "real", "character", "logical"])
                    )
                    
                    if is_type_cell and not is_metadata_table:
                        # This is a parameter table - stop here
                        break
        
        # Collect content elements
        if child.name in ["p", "blockquote", "pre", "dl", "div"]:
            content_elements.append(child)
    
    if not content_elements:
        return None
    
    # Render all collected elements
    rendered_parts = []
    for elem in content_elements:
        if elem.name == "blockquote":
            # Use render_description for blockquotes
            rendered = render_description(elem)
            if rendered:
                rendered_parts.append(rendered)
        elif elem.name == "pre":
            pre_text = elem.get_text()
            lines = pre_text.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            if non_empty_lines:
                min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
                lines = [line[min_indent:] if line.strip() else line for line in lines]
            lines = [line.rstrip() for line in lines]
            rendered_parts.append('\n'.join(lines))
        elif elem.name == "p":
            text = elem.get_text(separator=" ", strip=True)
            if text:
                rendered_parts.append(text)
        elif elem.name == "dl":
            # Render as bullets
            for dt in elem.find_all("dt"):
                dd = dt.find_next_sibling("dd")
                dt_text = dt.get_text(separator=" ", strip=True)
                dt_text = re.sub(r":\s*$", "", dt_text)
                if dd:
                    dd_text = dd.get_text(separator=" ", strip=True)
                    rendered_parts.append(f"- {dt_text}: {dd_text}")
                else:
                    rendered_parts.append(f"- {dt_text}")
        else:
            text = elem.get_text(separator=" ", strip=True)
            if text:
                rendered_parts.append(text)
    
    result = '\n'.join(rendered_parts)
    result = result.strip()
    
    # Collapse excessive blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result if result else None


def classify_optionality(description: Optional[str]) -> Dict[str, Any]:
    """
    Classify section optionality based on description text.
    
    Rules (case-insensitive, word-boundary matching to avoid false positives):
    - If description contains word "if" -> "conditional"
    - Else if contains word "optional" and NOT "required" -> "optional"
    - Else if contains word "required" and NOT "optional" -> "required"
    - Else if contains BOTH "required" and "optional" -> "conditional"
    - Else -> "none"
    
    Returns:
        Dict with keys: optionality, optionality_source, optionality_raw_snippet
    """
    if not description:
        return {
            "optionality": "none",
            "optionality_source": "description",
        }
    
    desc_lower = description.lower()
    
    # Use word boundaries to avoid false positives (e.g., "diff", "interface")
    has_if = bool(re.search(r"\bif\b", desc_lower))
    has_optional = bool(re.search(r"\boptional\b", desc_lower))
    has_required = bool(re.search(r"\brequired\b", desc_lower))
    
    if has_if:
        optionality = "conditional"
    elif has_optional and not has_required:
        optionality = "optional"
    elif has_required and not has_optional:
        optionality = "required"
    elif has_required and has_optional:
        optionality = "conditional"
    else:
        optionality = "none"
    
    result = {
        "optionality": optionality,
        "optionality_source": "description",
    }
    
    # Extract a snippet containing the relevant keywords
    if optionality != "none":
        # First try: scan line-by-line for better context
        lines = description.split("\n")
        for line in lines:
            line_lower = line.lower()
            if (optionality == "conditional" and re.search(r"\bif\b", line_lower)) or \
               (optionality == "optional" and re.search(r"\boptional\b", line_lower)) or \
               (optionality == "required" and re.search(r"\brequired\b", line_lower)):
                snippet = line.strip()
                # Collapse whitespace
                snippet = re.sub(r'\s+', ' ', snippet)
                result["optionality_raw_snippet"] = snippet
                return result
        
        # Fallback: sentence split (original logic)
        sentences = re.split(r'[.!?]\s+', description)
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if (optionality == "conditional" and re.search(r"\bif\b", sentence_lower)) or \
               (optionality == "optional" and re.search(r"\boptional\b", sentence_lower)) or \
               (optionality == "required" and re.search(r"\brequired\b", sentence_lower)):
                snippet = sentence.strip()
                snippet = re.sub(r'\s+', ' ', snippet)
                result["optionality_raw_snippet"] = snippet
                break
    
    return result


def extract_card_structured_fields(h2_element, soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Extract structured fields for card sections.
    
    Extracts:
    - options: List from header braces "{ ... }" or "Card's options:" row
    - default_option: From "Default:" row
    - options_description: Mapping from <dl> blocks
    - syntax: From <h3>Syntax:</h3> block
    - items: From <h3>Description of items:</h3> block
    
    Returns:
        Dict with card.* fields (only includes fields that were found)
    """
    result: Dict[str, Any] = {}
    
    # Extract options from header
    header_text = h2_element.get_text(" ", strip=True)
    options_match = re.search(r"\{([^}]+)\}", header_text)
    if options_match:
        options_text = options_match.group(1)
        options = [opt.strip() for opt in options_text.split("|") if opt.strip()]
        if options:
            result["options"] = options
    
    # Locate nested content root (same logic as extract_section_description for consistency)
    tr_with_h2 = h2_element.find_parent("tr")
    if not tr_with_h2:
        return result
    
    next_tr = tr_with_h2.find_next_sibling("tr")
    if not next_tr:
        return result
    
    content_td = next_tr.find("td")
    if not content_td:
        return result
    
    # Find nested table (fallback to content_td if missing)
    nested_table = content_td.find("table")
    if nested_table:
        nested_td = nested_table.find("td") or content_td
    else:
        nested_td = content_td.find("td") or content_td
    
    # Traverse nested_td in document order to find structured fields
    found_syntax = False
    found_items = False
    current = nested_td
    
    # Iterate through children of nested_td
    for child in nested_td.children:
        if not hasattr(child, 'name'):
            continue
        
        # Extract options from "Card's options:" row (case-insensitive, apostrophe-tolerant)
        if child.name == "table" and not result.get("options"):
            rows = child.find_all("tr")
            for row in rows:
                th = row.find("th")
                if th:
                    th_text_norm = th.get_text(" ", strip=True).lower()
                    th_text_norm_no_apos = re.sub(r"'", "", th_text_norm)
                    # Match "card's options" or "card options" (case-insensitive, apostrophe-tolerant)
                    if ("card" in th_text_norm_no_apos and "options" in th_text_norm_no_apos) or \
                       ("card's options" in th_text_norm):
                        td = row.find("td")
                        if td:
                            # Extract spans.flag or text
                            flags = td.find_all("span", class_="flag")
                            if flags:
                                options = [flag.get_text(strip=True) for flag in flags]
                                result["options"] = options
                            else:
                                options_text = td.get_text(strip=True)
                                options = [opt.strip() for opt in options_text.split("|") if opt.strip()]
                                if options:
                                    result["options"] = options
        
        # Extract default_option from "Default:" row
        if child.name == "table" and "default_option" not in result:
            rows = child.find_all("tr")
            for row in rows:
                th = row.find("th")
                if th and "default:" in th.get_text().lower():
                    td = row.find("td")
                    if td:
                        default_text = td.get_text(strip=True)
                        if default_text and default_text.lower() != "none":
                            result["default_option"] = default_text
        
        # Extract syntax from <h3>Syntax:</h3>
        if child.name == "h3" and "syntax" in child.get_text().lower() and not found_syntax:
            found_syntax = True
            syntax_parts = []
            syntax_elem = child.next_sibling
            while syntax_elem is not None:
                if not hasattr(syntax_elem, 'name'):
                    syntax_elem = syntax_elem.next_sibling
                    continue
                
                # Stop at next h3
                if syntax_elem.name == "h3":
                    break
                
                # Extract from <div class="syntax"><table>
                if syntax_elem.name == "blockquote":
                    syntax_div = syntax_elem.find("div", class_="syntax")
                    if syntax_div:
                        syntax_table = syntax_div.find("table")
                        if syntax_table:
                            # Render table as tab-separated lines
                            rows = syntax_table.find_all("tr")
                            for row in rows:
                                cells = row.find_all(["td", "th"])
                                cell_texts = [cell.get_text(strip=True) for cell in cells]
                                if any(cell_texts):
                                    syntax_parts.append("\t".join(cell_texts))
                    # Fallback: look for <pre> in blockquote
                    if not syntax_parts:
                        pre_elem = syntax_elem.find("pre")
                        if pre_elem:
                            pre_text = pre_elem.get_text("\n")
                            # Normalize whitespace lightly
                            lines = [line.rstrip() for line in pre_text.split("\n")]
                            pre_text = "\n".join(lines).strip()
                            if pre_text:
                                syntax_parts.append(pre_text)
                # Also check for <pre> immediately after h3
                elif syntax_elem.name == "pre" and not syntax_parts:
                    pre_text = syntax_elem.get_text("\n")
                    lines = [line.rstrip() for line in pre_text.split("\n")]
                    pre_text = "\n".join(lines).strip()
                    if pre_text:
                        syntax_parts.append(pre_text)
                
                syntax_elem = syntax_elem.next_sibling
            
            if syntax_parts:
                result["syntax"] = "\n".join(syntax_parts)
        
        # Extract items from <h3>Description of items:</h3>
        if child.name == "h3" and "description of items" in child.get_text().lower() and not found_items:
            found_items = True
            items = []
            # Search forward until next <h3> and collect parameter-definition tables
            search_elem = child.next_sibling
            while search_elem is not None:
                if not hasattr(search_elem, 'name'):
                    search_elem = search_elem.next_sibling
                    continue
                
                # Stop at next h3
                if search_elem.name == "h3":
                    break
                
                # Look for parameter tables (in blockquote or directly)
                if search_elem.name == "blockquote":
                    item_tables = search_elem.find_all("table")
                elif search_elem.name == "table":
                    item_tables = [search_elem]
                else:
                    item_tables = []
                
                for table in item_tables:
                    rows = table.find_all("tr")
                    if len(rows) >= 2:
                        first_row = rows[0]
                        th = first_row.find("th")
                        td_type = first_row.find("td")
                        if th and td_type:
                            # Check if this is a parameter-definition table
                            td_text = td_type.get_text(strip=True).lower()
                            is_type_cell = (
                                td_text == "type" or
                                any(token in td_text for token in ["integer", "real", "character", "logical"])
                            )
                            if is_type_cell:
                                # This is a parameter table - extract metadata
                                meta_list = extract_parameter_metadata_from_table(table)
                                if meta_list:
                                    items.extend(meta_list)
                
                search_elem = search_elem.next_sibling
            
            if items:
                result["items"] = items
        
        # Extract options_description from <dl> blocks
        if child.name == "dl" and "options_description" not in result:
            options_desc: Dict[str, str] = {}
            for dt in current.find_all("dt"):
                dd = dt.find_next_sibling("dd")
                # Extract option key(s) from dt (often spans.flag)
                flags = dt.find_all("span", class_="flag")
                if flags:
                    option_keys = [flag.get_text(strip=True) for flag in flags]
                else:
                    tt = dt.find("tt")
                    if tt:
                        option_text = tt.get_text(strip=True)
                        # Remove trailing colons and split by comma
                        option_text = re.sub(r":\s*$", "", option_text)
                        option_keys = [opt.strip() for opt in option_text.split(",") if opt.strip()]
                    else:
                        option_keys = [dt.get_text(strip=True)]
                
                if dd:
                    dd_text = render_description(dd) if dd.find("pre") or dd.find("blockquote") else dd.get_text(separator=" ", strip=True)
                    for key in option_keys:
                        if key:
                            options_desc[key] = dd_text
            
            if options_desc:
                result["options_description"] = options_desc
        
    return result


def parse_module_doc(module_name: str, html_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """
    Parse QE HTML documentation and extract rich parameter metadata (v3).
    
    V3 ALGORITHM (preserves document order, no sorting):
    ====================================================
    
    Stage 1: ToC-driven initialization
    - Extract section headings and parameter names from Table of Contents
    - Initialize parameters dict in ToC traversal order
    - For each section, create parameter entries with minimal metadata
    
    Stage 2: Metadata extraction from definition tables
    - Traverse all h2/h3/table elements in document order
    - For each table, find nearest previous h2/h3 matching "Namelist:" or "Card:"
    - Extract full metadata (type, default, status, see_also, enum, description, indexing)
    - Update existing ToC params or append new ones discovered in tables
    
    Stage 3: Order preservation
    - Build ordered_parameters dict: first all ToC params (in order), then extras
    
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
                    "namelist": "&CONTROL",
                    "name": "calculation",
                    "type": "CHARACTER",
                    "default": "'scf'",
                    "status": null,
                    "see_also": null,
                    "enum": ["'scf'", "'nscf'", ...],
                    "description": "..."
                },
                ...
            }
        }
    """
    html_content = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "html.parser")
    
    # V4: Build section hierarchy first (before parameter extraction)
    # 
    # HIERARCHY BUILDING ALGORITHM:
    # - Traverse all <h2> elements in document order (no sorting)
    # - Classify each section: namelist/card/supercard/line_of_input/other
    # - Use a stack to track open supercards (BEGIN_* pushes, END_* pops)
    # - Attach sections to current top supercard (if any) or module root
    # - This preserves document order and creates proper nesting for NEB supercards
    #
    # ORDERING PRESERVATION:
    # - All sections processed in document order (soup.find_all("h2") order)
    # - Children appended in order encountered
    # - No sorting applied anywhere
    #
    sections_tree: List[Dict[str, Any]] = []
    supercard_stack: List[Dict[str, Any]] = []  # Stack of open supercards
    
    all_h2_elements = soup.find_all("h2")
    
    for h2 in all_h2_elements:
        kind, name = classify_section_kind_and_name(h2)
        
        # Skip END_* (they just close supercards)
        if kind == "supercard" and name.startswith("END_"):
            # Pop matching BEGIN_* from stack
            if supercard_stack:
                # Match by suffix: BEGIN_X <-> END_X
                end_suffix = name[4:]  # Remove "END_"
                for i in range(len(supercard_stack) - 1, -1, -1):
                    begin_name = supercard_stack[i]["name"]
                    if begin_name.startswith("BEGIN_") and begin_name[6:] == end_suffix:
                        # Found match - pop everything from this point
                        supercard_stack = supercard_stack[:i]
                        break
            continue
        
        # Extract section description
        # SECTION DESCRIPTION EXTRACTION:
        # - Collects content after <h2> until first <h3> or parameter table
        # - Content is in nested table structure: <tr><td><table><tr><td><p>...</p></td></tr></table></td></tr>
        # - Renders using same render_description() logic as v3
        section_description = extract_section_description(h2, soup)
        
        # Classify optionality
        # OPTIONALITY CLASSIFICATION RULES (case-insensitive):
        # - "if" → conditional
        # - "optional" (not "required") → optional
        # - "required" (not "optional") → required
        # - both "required" and "optional" → conditional
        # - else → none
        optionality_info = classify_optionality(section_description)
        
        # Build section node
        section_node: Dict[str, Any] = {
            "kind": kind,
            "name": name,
            "description": section_description,
            "optionality": optionality_info["optionality"],
            "optionality_source": optionality_info["optionality_source"],
            "children": [],
        }
        
        if "optionality_raw_snippet" in optionality_info:
            section_node["optionality_raw_snippet"] = optionality_info["optionality_raw_snippet"]
        
        # Extract card structured fields if this is a card
        # CARD STRUCTURED FIELDS:
        # - options: from header braces "{ ... }" or "Card's options:" row
        # - default_option: from "Default:" row
        # - options_description: from <dl> blocks (option → description mapping)
        # - syntax: from <h3>Syntax:</h3> block
        # - items: from <h3>Description of items:</h3> block (NOT merged into module.parameters)
        if kind == "card":
            card_fields = extract_card_structured_fields(h2, soup)
            section_node.update(card_fields)
        
        # Attach to parent (current top supercard if any, else module root)
        if supercard_stack:
            # Attach to current top supercard
            supercard_stack[-1]["children"].append(section_node)
        else:
            # Attach to module root
            sections_tree.append(section_node)
        
        # If this is a BEGIN_* supercard, push it onto stack
        if kind == "supercard" and name.startswith("BEGIN_"):
            supercard_stack.append(section_node)
    
    if verbose:
        print(f"[{module_name}] Built section hierarchy: {len(sections_tree)} root sections")
        # Count total sections including nested
        def count_sections(sections):
            total = len(sections)
            for sec in sections:
                if sec.get("children"):
                    total += count_sections(sec["children"])
            return total
        total_sections = count_sections(sections_tree)
        print(f"[{module_name}] Total sections (including nested): {total_sections}")
    
    # STAGE 1: Extract ToC parameter names - use this for ordering and validation (V3 logic preserved)
    toc_params = extract_toc_parameters(html_content)
    
    # Build doc URL
    doc_name = module_name.upper().replace("-", "_")
    doc_url = DEFAULT_PATTERN.format(name=doc_name)
    
    # STAGE 1: FIRST PASS - Extract ALL parameters from ToC (preserves document order)
    # Initialize parameters dict with ToC order; metadata will be filled in Stage 2
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
        for param_name in toc_param_set:
            # Normalize parameter name to v1 style (base name for arrays)
            base_name = get_base_param_name(param_name) or normalize_param_name(param_name)
            if not base_name:
                continue
            
            key = f"{section_name}.{base_name}"
            parameters[key] = {
                "namelist": section_name,
                "name": base_name,
                "type": None,  # Will be filled in second pass if found in HTML tables
                "default": None,
                "status": None,
                "see_also": None,
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
                        "status": card_param_meta.get("status"),
                        "see_also": card_param_meta.get("see_also"),
                        "enum": card_param_meta.get("enum"),
                        "description": card_param_meta.get("description"),
                    })
    
    if verbose:
        print(f"[{module_name}] Initialized {len(parameters)} parameters from ToC")
    
    # STAGE 2: SECOND PASS - Find metadata for parameters in detailed sections (HTML tables)
    # Match ToC parameters with their detailed descriptions to fill in metadata
    # Strategy: for each table, find the nearest previous h2/h3 that matches Namelist:/Card: pattern
    # This prevents "Description of items:" tables from being incorrectly attributed
    all_elements = soup.find_all(["h2", "h3", "table"])
    
    for i, element in enumerate(all_elements):
        # Check if this is a parameter table
        if element.name == "table":
            # Find the nearest previous h2/h3 that matches Namelist:/Card: pattern
            section_for_table = None
            for j in range(i - 1, -1, -1):
                prev_elem = all_elements[j]
                if prev_elem.name in ["h2", "h3"]:
                    heading_text = prev_elem.get_text()
                    # Look for "Namelist: &NAME" pattern
                    namelist_match = re.search(r"Namelist:\s*(&[A-Za-z0-9_]+)", heading_text, re.IGNORECASE)
                    if namelist_match:
                        section_for_table = namelist_match.group(1).upper()
                        break
                    
                    # Look for "Card: NAME" pattern (cards don't have & prefix)
                    card_match = re.search(r"Card:\s*([A-Za-z0-9_]+)", heading_text, re.IGNORECASE)
                    if card_match:
                        section_for_table = card_match.group(1).upper()  # NO & prefix for card sections
                        break
            
            # Only process table if we found a valid section (ignore tables under "Description of items:" etc.)
            if not section_for_table:
                continue
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
                    if param_name_candidate and type_candidate:
                        # This is a parameter table - extract metadata (may return multiple parameters)
                        meta_list = extract_parameter_metadata_from_table(element)
                        if meta_list:
                            # Handle expanded parameters (array/grouped)
                            for meta in meta_list:
                                if meta and meta.get("name"):
                                    param_name = meta["name"]  # Base name (v1-style, e.g., "celldm")
                                    key = f"{section_for_table}.{param_name}"
                                    
                                    # Update existing parameter (from ToC) with metadata, or add if not found
                                    if key in parameters:
                                        # Update with metadata (including indexing if present)
                                        update_dict = {
                                            "type": meta.get("type"),
                                            "default": meta.get("default"),
                                            "status": meta.get("status"),
                                            "see_also": meta.get("see_also"),
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
                                            "namelist": section_for_table,
                                            "name": param_name,
                                            "type": meta.get("type"),
                                            "default": meta.get("default"),
                                            "status": meta.get("status"),
                                            "see_also": meta.get("see_also"),
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
    
    # STAGE 3: Build ordered parameters dict to preserve ToC order (no sorting)
    ordered_parameters: Dict[str, Dict[str, Any]] = {}
    
    # First, add all parameters in ToC order (preserves document insertion order)
    for section_name, toc_param_list in toc_params.items():
        for param_name in toc_param_list:
            base_name = get_base_param_name(param_name) or normalize_param_name(param_name)
            if not base_name:
                continue
            key = f"{section_name}.{base_name}"
            if key in parameters:
                ordered_parameters[key] = parameters[key]
    
    # Then, add any parameters found in second pass that weren't in ToC (append at end)
    for key, param in parameters.items():
        if key not in ordered_parameters:
            ordered_parameters[key] = param
    
    # V3: Build result with sections tree and parameters
    result = {
        "doc_url": doc_url,
        "sections": sections_tree,  # V3: hierarchical section tree
        "parameters": ordered_parameters,  # V3 logic preserved
    }
    
    # Add card metadata if any was found (for backward compatibility)
    if card_metadata:
        result["card_metadata"] = card_metadata
        if verbose:
            print(f"[{module_name}] Found metadata for {len(card_metadata)} card sections")
    
    return result


def load_module_specs(
    names: Optional[List[str]], use_pattern_only: bool
) -> List[ModuleSpec]:
    """Load module specs (reused from v1/v2)."""
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
        description="Extract QE parameter metadata from HTML docs (schema v3 with section hierarchy)."
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
        default=Path(__file__).parent.parent / "src" / "qmatsuite" / "data" / "qe_module_parameters.json",
        help="Output path for v3 JSON file",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(__file__).parent.parent / ".tmp" / "qe_docs",
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
        "schema_version": 3,
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
    params_with_status = 0
    params_with_see_also = 0
    
    for module_name, module_data in payload["modules"].items():
        params = module_data.get("parameters", {})
        for key, param in params.items():
            if "indexing" in param:
                params_with_indexing += 1
                if len(indexing_examples) < 5:
                    indexing_examples.append({
                        "module": module_name,
                        "key": key,
                        "name": param.get("name"),
                        "indexing": param.get("indexing"),
                    })
            if param.get("status"):
                params_with_status += 1
            if param.get("see_also"):
                params_with_see_also += 1
    
    # Count sections
    total_sections = 0
    sections_with_description = 0
    sections_with_optionality = 0
    cards_with_options = 0
    
    for module_name, module_data in payload["modules"].items():
        sections = module_data.get("sections", [])
        def count_and_analyze(sections_list):
            nonlocal total_sections, sections_with_description, sections_with_optionality, cards_with_options
            for sec in sections_list:
                total_sections += 1
                if sec.get("description"):
                    sections_with_description += 1
                if sec.get("optionality") != "none":
                    sections_with_optionality += 1
                if sec.get("kind") == "card" and sec.get("options"):
                    cards_with_options += 1
                if sec.get("children"):
                    count_and_analyze(sec["children"])
        count_and_analyze(sections)
    
    sys.stdout.write(
        f"[extract_v3] Generated schema v3 for {len(results)} modules, {total_params} parameters total.\n"
    )
    sys.stdout.write(
        f"[extract_v3] Total sections (hierarchical): {total_sections}\n"
    )
    sys.stdout.write(
        f"[extract_v3] Sections with description: {sections_with_description}\n"
    )
    sys.stdout.write(
        f"[extract_v3] Sections with optionality: {sections_with_optionality}\n"
    )
    sys.stdout.write(
        f"[extract_v3] Cards with options: {cards_with_options}\n"
    )
    sys.stdout.write(
        f"[extract_v3] Parameters with indexing metadata: {params_with_indexing}\n"
    )
    sys.stdout.write(
        f"[extract_v3] Parameters with status: {params_with_status}\n"
    )
    sys.stdout.write(
        f"[extract_v3] Parameters with see_also: {params_with_see_also}\n"
    )
    sys.stdout.write(
        f"[extract_v3] Output written to {args.output}\n"
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
    
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
