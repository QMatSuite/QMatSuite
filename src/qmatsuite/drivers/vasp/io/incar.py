"""VASP INCAR pure text <-> dict parser and writer.

Maps VASP INCAR text (TAG = VALUE format) to a flat parameter dict.
Stdlib only — no pymatgen, no qmatsuite core imports.

Handles:
- KEY = VALUE lines (= separator, whitespace tolerant)
- Semicolon-separated multi-tag lines (ISMEAR = 0 ; SIGMA = 0.1)
- Fortran booleans (.TRUE., .FALSE.)
- Comments (! and #) — preserved inside SYSTEM tag values
- Multi-value tags (space-separated lists, N*VALUE expansion)
- Continuation lines (backslash at end of line)
- Trailing semicolons

Writer always produces uppercase keys. Parser normalises to uppercase.
"""

from __future__ import annotations

import re
from typing import Any


def parse_incar_text(text: str) -> dict[str, Any]:
    """Parse INCAR text into a parameters dict.

    Args:
        text: INCAR file content.

    Returns:
        Dict of parameter name -> value. Keys are uppercase.
        Values are coerced: int, float, bool, str, or list.
    """
    if not text.strip():
        return {}

    # Join continuation lines (ending with \)
    joined = re.sub(r"\\\s*\n", " ", text)

    result: dict[str, Any] = {}

    for raw_line in joined.splitlines():
        # Strip inline comments: ! or # (but not inside SYSTEM value)
        line = _strip_comment(raw_line)
        line = line.strip()
        if not line:
            continue

        # Split on ; for multi-tag lines
        segments = line.split(";")
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            if "=" not in segment:
                continue

            # Split on first = only
            key_part, _, val_part = segment.partition("=")
            key = key_part.strip().upper()
            raw_val = val_part.strip()

            if not key:
                continue

            result[key] = _coerce_value(raw_val)

    return result


def _strip_comment(line: str) -> str:
    """Strip inline comments from an INCAR line.

    Comments start with ! or #. However, for SYSTEM (and other string
    tags), these characters inside the value should be preserved.
    Heuristic: if the line contains '=', only strip ! or # that appear
    before the '=' (leading comments) — for SYSTEM specifically, we
    preserve everything after the '=' since it is a string value.
    For non-SYSTEM tags, strip from the first ! or # after '='.
    """
    # Check if this is a SYSTEM tag (special case: value may contain ! or #)
    stripped = line.lstrip()
    if "=" in stripped:
        key_part = stripped.split("=", 1)[0].strip().upper()
        if key_part == "SYSTEM":
            # Preserve entire value for SYSTEM — no comment stripping
            return line

    # Normal case: strip from first ! or #
    for i, ch in enumerate(line):
        if ch in ("!", "#"):
            return line[:i]
    return line


def _coerce_value(raw: str) -> Any:
    """Coerce a raw INCAR value string to a Python type.

    Rules:
    - .TRUE./.FALSE. (case-insensitive) → bool
    - Integer pattern → int
    - Float pattern (handles d exponent) → float
    - Space-separated multi-values → list (handles N*VALUE expansion)
    - Everything else → str
    """
    raw = raw.strip()
    if not raw:
        return ""

    # Remove trailing comma (some INCAR files have it)
    if raw.endswith(","):
        raw = raw[:-1].rstrip()

    # Boolean
    lower = raw.lower()
    if lower in (".true.", "true", "t"):
        return True
    if lower in (".false.", "false", "f"):
        return False

    # Try single value first
    tokens = raw.split()
    if len(tokens) == 1:
        return _coerce_single(tokens[0])

    # Multi-value: check if all tokens are numeric (or N*VALUE)
    # If any token is non-numeric, return the original string
    expanded: list[Any] = []
    all_numeric = True
    for tok in tokens:
        if "*" in tok:
            parts = tok.split("*", 1)
            try:
                count = int(parts[0])
                val = _coerce_single(parts[1])
                if isinstance(val, str):
                    all_numeric = False
                    break
                expanded.extend([val] * count)
                continue
            except (ValueError, IndexError):
                all_numeric = False
                break
        val = _coerce_single(tok)
        if isinstance(val, str):
            all_numeric = False
            break
        expanded.append(val)

    if not all_numeric:
        return raw

    return expanded


def _coerce_single(s: str) -> Any:
    """Coerce a single token to int, float, bool, or str."""
    s = s.strip()
    if not s:
        return s

    # Boolean
    lower = s.lower()
    if lower in (".true.", "true", "t"):
        return True
    if lower in (".false.", "false", "f"):
        return False

    # Fortran D exponent
    if "d" in lower and not lower.startswith("d"):
        try:
            return float(lower.replace("d", "e"))
        except ValueError:
            pass

    # Float (has . or e)
    if "." in s or "e" in s.lower():
        try:
            return float(s)
        except ValueError:
            pass

    # Integer
    try:
        return int(s)
    except ValueError:
        pass

    return s


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def write_incar_text(params: dict[str, Any] | None) -> str:
    """Write INCAR text from a parameters dict.

    Pure function, stdlib only. Produces canonical INCAR output:
    SYSTEM tag first, then remaining keys in sorted order.

    Args:
        params: Dict of parameter name -> value. Keys should be uppercase.

    Returns:
        INCAR file content as string.
    """
    if not params:
        return ""

    lines: list[str] = []

    # SYSTEM tag first (conventional)
    if "SYSTEM" in params:
        lines.append(f"SYSTEM = {params['SYSTEM']}")
        lines.append("")

    for key, value in sorted(params.items()):
        if key == "SYSTEM":
            continue
        if isinstance(value, dict):
            continue  # Skip nested dicts (e.g., kpoints goes to KPOINTS file)
        if isinstance(value, bool):
            value_str = ".TRUE." if value else ".FALSE."
        elif isinstance(value, (list, tuple)):
            value_str = " ".join(str(v) for v in value)
        else:
            value_str = str(value)
        lines.append(f"{key} = {value_str}")

    return "\n".join(lines) + "\n"
