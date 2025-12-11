#!/usr/bin/env python3
"""
Shared parameter name normalization utilities for v1 and v2 extractors.

This module provides functions to normalize parameter names consistently
across both extractors, ensuring v2 uses the same base names as v1.
"""

import re
from typing import Optional


def normalize_param_name(text: str) -> Optional[str]:
    """
    Normalize parameter name to match v1 extractor behavior.
    
    This is the same logic as extract_qe_parameters_v1.normalize_param_name().
    It ensures v2 extractor produces the same parameter names as v1.
    
    Args:
        text: Raw parameter name text from HTML
        
    Returns:
        Normalized parameter name, or None if invalid
        
    Examples:
        "celldm(i), i=1,6" -> "celldm" (base name only)
        "alpha_mix" -> "alpha_mix"
        "A,B,C" -> None (grouped, should be split first)
    """
    if not text:
        return None
    candidate = text.strip()
    candidate = re.sub(r"\s+", "_", candidate)
    if not candidate:
        return None
    lowered = candidate.lower()
    if lowered.startswith(("namelist", "card", "input_", "section", "table")):
        return None
    if len(candidate) < 2 or len(candidate) > 80:
        return None
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate):
        return None
    return candidate


def extract_array_indexing_info(param_name_raw: str, description: Optional[str] = None) -> Optional[dict]:
    """
    Extract indexing metadata for array-like parameters.
    
    Detects patterns like:
    - "celldm(i), i=1,6" -> bounded array (start=1, end=6)
    - "alpha_mix(i)" -> unbounded array (start=1, end=None)
    
    Args:
        param_name_raw: Raw parameter name from HTML (e.g., "celldm(i), i=1,6")
        description: Optional description text for additional hints
        
    Returns:
        Dict with indexing metadata, or None if not an array parameter.
        Structure:
        {
            "index_name": "i",
            "kind": "bounded" | "unbounded",
            "start": int,
            "end": int | None,
            "keyword_pattern": str
        }
    """
    # Pattern 1: Bounded array like "celldm(i), i=1,6"
    # Must have explicit numeric bounds (e.g., i=1,6)
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
    
    # Pattern 2: Unbounded array like "alpha_mix(i)" or "london_c6(i), i=1,ntyp"
    # Check for array notation first (removed word boundaries to handle underscores)
    unbounded_match = re.search(
        r'([A-Za-z0-9_]+)\(([a-z]+)\)',
        param_name_raw,
        re.IGNORECASE
    )
    if unbounded_match and not bounded_match:  # Only if not already matched as bounded
            base_name = unbounded_match.group(1)
            index_name = unbounded_match.group(2)
            
            # Check if param_name_raw contains variable-size hints like "i=1,ntyp" or "i=1,niter"
            # This is the primary indicator for unbounded arrays
            var_match = re.search(rf"{re.escape(index_name)}\s*=\s*\d+\s*,\s*([a-z_]+)", param_name_raw, re.IGNORECASE)
            if var_match:
                var_name = var_match.group(1)
                # If the variable name matches common size variable patterns, it's unbounded
                size_var_patterns = [r"niter", r"ntyp", r"nat", r"nband", r"nspin"]
                for pattern in size_var_patterns:
                    if re.search(pattern, var_name, re.IGNORECASE):
                        return {
                            "index_name": index_name,
                            "kind": "unbounded",
                            "start": 1,
                            "end": None,
                            "keyword_pattern": f"{base_name}({{{index_name}}})"
                        }
            
            # Check description for hints about unbounded nature
            is_unbounded = False
            if description:
                desc_lower = description.lower()
                # Look for hints like:
                # - "i = 1, 2, ..." or "i=1,2,..."
                # - "i is a positive integer" or "i is an integer"
                # - "i=1,ntyp" or "i=1,niter" (variable-size arrays)
                # - "for each iteration" or "for each i" (suggests iteration-based)
                if (re.search(rf"{re.escape(index_name)}\s*=\s*\d+\s*,\s*\.\.\.", desc_lower) or
                    re.search(rf"{re.escape(index_name)}\s*is\s*(a\s+)?(positive\s+)?integer", desc_lower) or
                    re.search(rf"{re.escape(index_name)}\s*=\s*\d+\s*,\s*[a-z_]+", desc_lower) or
                    re.search(rf"{re.escape(index_name)}\s*=\s*\d+\s*,\s*{re.escape(index_name)}", desc_lower) or
                    re.search(r"for\s+each\s+(iteration|i\b)", desc_lower)):
                    is_unbounded = True
            
            # Also check if index name itself matches a common size variable pattern
            # e.g., "alpha_mix(niter)" - niter is the index name and suggests unbounded
            if not is_unbounded:
                size_var_patterns = [r"niter", r"ntyp", r"nat", r"nband", r"nspin"]
                for pattern in size_var_patterns:
                    if re.search(pattern, index_name, re.IGNORECASE):
                        is_unbounded = True
                        break
            
            # If we found the pattern but no explicit bounds in the name itself,
            # and description suggests unbounded or index name suggests variable size, assume unbounded
            if is_unbounded:
                return {
                    "index_name": index_name,
                    "kind": "unbounded",
                    "start": 1,
                    "end": None,
                    "keyword_pattern": f"{base_name}({{{index_name}}})"
                }
    
    return None


def get_base_param_name(param_name_raw: str) -> Optional[str]:
    """
    Extract base parameter name from raw HTML text, handling array notation.
    
    Examples:
        "celldm(i), i=1,6" -> "celldm"
        "alpha_mix(i)" -> "alpha_mix"
        "calculation" -> "calculation"
        "A,B,C" -> None (grouped, should be handled separately)
    
    Args:
        param_name_raw: Raw parameter name from HTML
        
    Returns:
        Base parameter name (normalized), or None if invalid
    """
    # Remove array notation: "celldm(i), i=1,6" -> "celldm"
    # Pattern: name(i), i=1,6 or name(i)
    base_match = re.search(r'\b([A-Za-z0-9_]+)\([a-z]+\)', param_name_raw, re.IGNORECASE)
    if base_match:
        base_name = base_match.group(1)
        return normalize_param_name(base_name)
    
    # For grouped parameters like "A,B,C", return None (should be split)
    if "," in param_name_raw and not "(" in param_name_raw:
        return None
    
    # Regular parameter name
    return normalize_param_name(param_name_raw)
