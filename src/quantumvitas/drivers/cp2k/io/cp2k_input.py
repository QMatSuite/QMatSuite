"""CP2K input file parser and writer.

Handles the F3 nested-section format: ``&SECTION ... &END SECTION``.
Stdlib only — no kernel imports.

Key CP2K syntax features:
- Sections: ``&SECTION_NAME [default_keyword_value]`` / ``&END SECTION_NAME``
- Keywords: ``KEYWORD value`` (positional, no ``=`` sign)
- Comments: ``#`` or ``!`` to end of line
- Preprocessor: ``@SET``, ``@IF``, ``@ENDIF``, ``@INCLUDE``, ``${VAR}``
- Units: ``[unit]`` annotation before value (e.g. ``[angstrom] 5.0``)
- Case-insensitive keywords (canonicalized to UPPERCASE)
- Repeated sections (e.g. multiple ``&KIND`` blocks)
"""

from __future__ import annotations

import re
from typing import Any


# ── Parser ──────────────────────────────────────────────────────────────


def parse_cp2k_text(text: str) -> dict:
    """Parse CP2K input text into a combined params + structure dict.

    Returns:
        Dict with ``params`` and ``structure`` keys, suitable for the
        inputformat orchestrator's "combined" content_role.
    """
    lines = _strip_comments_and_preprocess(text)
    tree = _parse_sections(lines, 0, None)[0]

    # Extract structure from FORCE_EVAL/SUBSYS
    structure = _extract_structure(tree)
    params = _clean_params(tree)

    return {"params": params, "structure": structure}


def _strip_comments_and_preprocess(text: str) -> list[str]:
    """Strip comments and preprocessor directives, return clean lines."""
    result = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        # Skip empty lines
        if not line:
            continue
        # Skip preprocessor directives
        if line.startswith("@"):
            continue
        # Strip inline comments (# or !)
        # Be careful not to strip inside quoted strings
        cleaned = _strip_inline_comment(line)
        if cleaned:
            result.append(cleaned)
    return result


def _strip_inline_comment(line: str) -> str:
    """Strip inline comment (# or !) from a line, respecting quotes."""
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch in ("#", "!") and not in_single and not in_double:
            return line[:i].rstrip()
    return line


def _parse_sections(
    lines: list[str], start: int, end_name: str | None
) -> tuple[dict[str, Any], int]:
    """Recursively parse nested sections into a dict tree.

    Returns (tree_dict, next_line_index).

    For COORD sections, coordinate lines (element + 3 numbers) are stored
    as a ``_COORD_LINES`` list of ``[element, x, y, z]`` to preserve element
    case and handle duplicate species.
    """
    tree: dict[str, Any] = {}
    is_coord_section = end_name is not None and end_name.upper() == "COORD"
    coord_lines: list[list] = []
    i = start
    while i < len(lines):
        line = lines[i]
        upper = line.upper()

        # Section end
        if upper.startswith("&END"):
            if is_coord_section and coord_lines:
                tree["_COORD_LINES"] = coord_lines
            return tree, i + 1

        # Section start
        if line.startswith("&"):
            parts = line[1:].split(None, 1)
            section_name = parts[0].upper()
            default_keyword = parts[1].strip() if len(parts) > 1 else None

            child, i = _parse_sections(lines, i + 1, section_name)

            if default_keyword is not None:
                child["_DEFAULT_KEYWORD"] = default_keyword

            # Handle repeated sections (e.g. multiple &KIND blocks)
            if section_name in tree:
                existing = tree[section_name]
                if isinstance(existing, list):
                    existing.append(child)
                else:
                    tree[section_name] = [existing, child]
            else:
                tree[section_name] = child

            continue

        # In COORD sections, try to parse as coordinate line first
        if is_coord_section:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    # Preserve original element case
                    coord_lines.append([parts[0], x, y, z])
                    i += 1
                    continue
                except (ValueError, IndexError):
                    pass

        # Keyword-value line
        parts = line.split(None, 1)
        key = parts[0].upper()
        value = parts[1].strip() if len(parts) > 1 else ""

        # Coerce value
        coerced = _coerce_value(value)

        # Handle repeated keywords (append to list)
        if key in tree:
            existing = tree[key]
            if isinstance(existing, list) and not isinstance(existing, str):
                existing.append(coerced)
            else:
                tree[key] = [existing, coerced]
        else:
            tree[key] = coerced

        i += 1

    if is_coord_section and coord_lines:
        tree["_COORD_LINES"] = coord_lines
    return tree, i


def _coerce_value(raw: str) -> Any:
    """Coerce a string value to Python type."""
    if not raw:
        return ""

    # Strip unit annotation: [unit] value -> value
    unit_match = re.match(r"\[[\w./]+\]\s*(.*)", raw)
    if unit_match:
        raw = unit_match.group(1)

    upper = raw.upper().strip()

    # Booleans
    if upper in (".TRUE.", "TRUE", "T", "YES", ".T."):
        return True
    if upper in (".FALSE.", "FALSE", "F", "NO", ".F."):
        return False

    # Try integer
    try:
        return int(raw)
    except ValueError:
        pass

    # Try float
    try:
        return float(raw)
    except ValueError:
        pass

    # Multi-value: try splitting on whitespace
    tokens = raw.split()
    if len(tokens) > 1:
        coerced_tokens = []
        for t in tokens:
            try:
                coerced_tokens.append(int(t))
            except ValueError:
                try:
                    coerced_tokens.append(float(t))
                except ValueError:
                    coerced_tokens.append(t)
        return coerced_tokens

    return raw


def _extract_structure(tree: dict) -> dict | None:
    """Extract structure information from the parsed tree.

    Looks for FORCE_EVAL/SUBSYS/CELL and FORCE_EVAL/SUBSYS/COORD.
    """
    force_eval = tree.get("FORCE_EVAL", {})
    if isinstance(force_eval, list):
        force_eval = force_eval[0]
    subsys = force_eval.get("SUBSYS", {})
    if not subsys:
        return None

    result: dict[str, Any] = {}

    # Cell
    cell = subsys.get("CELL", {})
    if cell:
        lattice = _extract_lattice(cell)
        if lattice:
            result["lattice"] = lattice

    # Coordinates
    coord = subsys.get("COORD", {})
    if coord:
        species, coords, is_scaled = _extract_coords(coord)
        if species:
            result["species"] = species
            if is_scaled:
                result["frac_coords"] = coords
            else:
                result["cart_coords"] = coords

    # Comment from project name
    global_sec = tree.get("GLOBAL", {})
    project = global_sec.get("PROJECT", "")
    if project:
        result["comment"] = str(project)

    return result if result else None


def _extract_lattice(cell: dict) -> list[list[float]] | None:
    """Extract 3x3 lattice matrix from CELL section."""
    # Try explicit vectors A, B, C
    a_vec = cell.get("A")
    b_vec = cell.get("B")
    c_vec = cell.get("C")

    if a_vec is not None and b_vec is not None and c_vec is not None:
        return [_to_float_list(a_vec), _to_float_list(b_vec), _to_float_list(c_vec)]

    # Try ABC shorthand (orthorhombic): ABC a b c
    abc = cell.get("ABC")
    if abc is not None:
        vals = _to_float_list(abc)
        if len(vals) >= 3:
            return [
                [vals[0], 0.0, 0.0],
                [0.0, vals[1], 0.0],
                [0.0, 0.0, vals[2]],
            ]

    return None


def _to_float_list(val: Any) -> list[float]:
    """Convert value (list, str, or scalar) to list of floats."""
    if isinstance(val, list):
        return [float(v) for v in val]
    if isinstance(val, (int, float)):
        return [float(val)]
    # String: split and convert
    return [float(x) for x in str(val).split()]


def _extract_coords(coord: dict) -> tuple[list[str], list[list[float]], bool]:
    """Extract species and coordinates from COORD section.

    Returns (species, coords, is_scaled).
    Uses ``_COORD_LINES`` list produced by the parser for faithful
    element case preservation and duplicate-species handling.
    """
    is_scaled = False
    scaled_val = coord.get("SCALED")
    if scaled_val is True:
        is_scaled = True

    species: list[str] = []
    coords: list[list[float]] = []

    # Primary: use _COORD_LINES list (new parser format)
    coord_lines = coord.get("_COORD_LINES", [])
    for entry in coord_lines:
        # entry = [element, x, y, z]
        species.append(entry[0])
        coords.append([float(entry[1]), float(entry[2]), float(entry[3])])

    return species, coords, is_scaled


def _clean_params(tree: dict) -> dict:
    """Remove structure data from the params tree (keep only parameters)."""
    result = {}
    for key, val in tree.items():
        if key == "FORCE_EVAL":
            fe = val if not isinstance(val, list) else val[0]
            cleaned_fe = {}
            for fk, fv in fe.items():
                if fk == "SUBSYS":
                    # Keep KIND sections but remove CELL, COORD, TOPOLOGY
                    subsys = fv if not isinstance(fv, list) else fv[0]
                    kind_data = subsys.get("KIND")
                    if kind_data is not None:
                        cleaned_fe["KIND"] = kind_data
                else:
                    cleaned_fe[fk] = fv
            result["FORCE_EVAL"] = cleaned_fe
        else:
            result[key] = val
    return result


# ── Writer ──────────────────────────────────────────────────────────────


def write_cp2k_text(fragment: dict[str, Any]) -> str:
    """Write CP2K input text from combined params + structure dict.

    Generates canonical ``&SECTION ... &END SECTION`` nested format.

    Args:
        fragment: Dict with ``params`` and optionally ``structure`` keys.

    Returns:
        CP2K input file text.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    lines: list[str] = []

    # GLOBAL section
    _write_global(lines, params)

    # FORCE_EVAL section
    _write_force_eval(lines, params, structure)

    # MOTION section (if present)
    motion = params.get("MOTION", {})
    if motion:
        _write_section(lines, "MOTION", motion, indent=0)

    # EXT_RESTART section (if present)
    ext_restart = params.get("EXT_RESTART", {})
    if ext_restart:
        _write_section(lines, "EXT_RESTART", ext_restart, indent=0)

    return "\n".join(lines) + "\n"


def _write_global(lines: list[str], params: dict) -> None:
    """Write the &GLOBAL section."""
    global_params = params.get("GLOBAL", {})
    project_name = global_params.get("PROJECT", "calc")
    run_type = global_params.get("RUN_TYPE", "ENERGY")

    lines.append("&GLOBAL")
    lines.append(f"  PROJECT {project_name}")
    lines.append(f"  RUN_TYPE {run_type}")
    for k, v in sorted(global_params.items()):
        if k in ("PROJECT", "RUN_TYPE"):
            continue
        lines.append(f"  {k} {_format_value(v)}")
    lines.append("&END GLOBAL")
    lines.append("")


def _write_force_eval(lines: list[str], params: dict, structure: dict) -> None:
    """Write the &FORCE_EVAL section with DFT and SUBSYS."""
    force_eval = params.get("FORCE_EVAL", {})
    method = force_eval.get("METHOD", "Quickstep")

    lines.append("&FORCE_EVAL")
    lines.append(f"  METHOD {method}")

    # Write FORCE_EVAL-level keywords (non-dict, non-METHOD)
    for k, v in sorted(force_eval.items()):
        if k in ("METHOD", "DFT", "SUBSYS", "KIND", "MM", "QMMM", "PROPERTIES",
                  "PRINT"):
            continue
        if not isinstance(v, dict) and not isinstance(v, list):
            lines.append(f"  {k} {_format_value(v)}")

    # DFT subsection
    dft = force_eval.get("DFT", {})
    if dft:
        _write_dft(lines, dft, indent=1)

    # MM subsection (if present)
    mm = force_eval.get("MM")
    if mm:
        _write_section(lines, "MM", mm, indent=1)

    # QMMM subsection (if present)
    qmmm = force_eval.get("QMMM")
    if qmmm:
        _write_section(lines, "QMMM", qmmm, indent=1)

    # PROPERTIES subsection (if present)
    properties = force_eval.get("PROPERTIES")
    if properties:
        _write_section(lines, "PROPERTIES", properties, indent=1)

    # PRINT subsection (if present)
    fe_print = force_eval.get("PRINT")
    if fe_print:
        _write_section(lines, "PRINT", fe_print, indent=1)

    # SUBSYS section (structure)
    _write_subsys(lines, params, structure, indent=1)

    lines.append("&END FORCE_EVAL")


def _write_dft(lines: list[str], dft: dict, indent: int = 1) -> None:
    """Write the &DFT subsection."""
    prefix = "  " * indent
    lines.append(f"{prefix}&DFT")

    # Simple keywords
    for k, v in sorted(dft.items()):
        if isinstance(v, dict):
            continue
        if isinstance(v, list) and any(isinstance(x, dict) for x in v):
            continue
        lines.append(f"{prefix}  {k} {_format_value(v)}")

    # Nested subsections
    subsection_order = [
        "MGRID", "QS", "SCF", "XC", "POISSON", "KPOINTS", "LS_SCF",
        "AUXILIARY_DENSITY_MATRIX_METHOD", "DFT_PLUS_U", "TDDFPT",
        "REAL_TIME_PROPAGATION", "LOCALIZE", "PRINT",
    ]
    for sec_name in subsection_order:
        sec_data = dft.get(sec_name)
        if sec_data:
            _write_section(lines, sec_name, sec_data, indent=indent + 1)

    # Any remaining dict subsections not in the order list
    written = set(subsection_order)
    for k, v in sorted(dft.items()):
        if k not in written and isinstance(v, dict):
            _write_section(lines, k, v, indent=indent + 1)

    lines.append(f"{prefix}&END DFT")


def _write_subsys(
    lines: list[str], params: dict, structure: dict, indent: int = 1
) -> None:
    """Write the &SUBSYS section containing cell, coords, and kind info."""
    prefix = "  " * indent
    lines.append(f"{prefix}&SUBSYS")

    species = structure.get("species", [])
    frac_coords = structure.get("frac_coords", [])
    cart_coords = structure.get("cart_coords", [])
    lattice = structure.get("lattice", [])

    # CELL
    if lattice:
        lines.append(f"{prefix}  &CELL")
        labels = ["A", "B", "C"]
        for i, vec in enumerate(lattice):
            lines.append(
                f"{prefix}    {labels[i]}  {vec[0]:.10f}  {vec[1]:.10f}  {vec[2]:.10f}"
            )
        lines.append(f"{prefix}  &END CELL")

    # COORD
    coords = frac_coords or cart_coords
    is_scaled = bool(frac_coords)
    if species and coords:
        lines.append(f"{prefix}  &COORD")
        if is_scaled:
            lines.append(f"{prefix}    SCALED .TRUE.")
        for sym, c in zip(species, coords):
            lines.append(
                f"{prefix}    {sym}  {c[0]:.10f}  {c[1]:.10f}  {c[2]:.10f}"
            )
        lines.append(f"{prefix}  &END COORD")

    # KIND sections
    force_eval = params.get("FORCE_EVAL", {})
    kind_data = force_eval.get("KIND", params.get("KIND", {}))

    if isinstance(kind_data, list):
        # List of KIND dicts (from parser)
        for kd in kind_data:
            element = kd.get("_DEFAULT_KEYWORD", "X")
            lines.append(f"{prefix}  &KIND {element}")
            for k, v in sorted(kd.items()):
                if k == "_DEFAULT_KEYWORD":
                    continue
                if isinstance(v, dict):
                    _write_section(lines, k, v, indent=indent + 2)
                else:
                    lines.append(f"{prefix}    {k} {_format_value(v)}")
            lines.append(f"{prefix}  &END KIND")
    elif isinstance(kind_data, dict):
        # Dict keyed by element (from writer convention)
        unique_species: list[str] = []
        for sp in species:
            if sp not in unique_species:
                unique_species.append(sp)

        for sp in unique_species:
            sp_params = kind_data.get(sp, {})
            basis = sp_params.get("BASIS_SET", "DZVP-MOLOPT-SR-GTH")
            potential = sp_params.get("POTENTIAL", "GTH-PBE")
            lines.append(f"{prefix}  &KIND {sp}")
            lines.append(f"{prefix}    BASIS_SET {basis}")
            lines.append(f"{prefix}    POTENTIAL {potential}")
            # Additional per-kind params
            for k, v in sorted(sp_params.items()):
                if k in ("BASIS_SET", "POTENTIAL"):
                    continue
                if isinstance(v, dict):
                    _write_section(lines, k, v, indent=indent + 2)
                else:
                    lines.append(f"{prefix}    {k} {_format_value(v)}")
            lines.append(f"{prefix}  &END KIND")

    lines.append(f"{prefix}&END SUBSYS")


def _write_section(
    lines: list[str], name: str, content: dict, indent: int = 0
) -> None:
    """Write a generic nested CP2K section."""
    prefix = "  " * indent

    # Handle section default keyword
    default_kw = content.get("_DEFAULT_KEYWORD", "")
    if default_kw:
        lines.append(f"{prefix}&{name} {default_kw}")
    else:
        lines.append(f"{prefix}&{name}")

    for key, val in sorted(content.items()):
        if key == "_DEFAULT_KEYWORD":
            continue

        if isinstance(val, dict):
            _write_section(lines, key, val, indent=indent + 1)
        elif isinstance(val, list):
            # Check if it's a list of dicts (repeated sections)
            if val and isinstance(val[0], dict):
                for item in val:
                    _write_section(lines, key, item, indent=indent + 1)
            else:
                lines.append(f"{prefix}  {key} {_format_value(val)}")
        else:
            lines.append(f"{prefix}  {key} {_format_value(val)}")

    lines.append(f"{prefix}&END {name}")


def _format_value(val: Any) -> str:
    """Format a Python value for CP2K input."""
    if isinstance(val, bool):
        return ".TRUE." if val else ".FALSE."
    if isinstance(val, list):
        return " ".join(_format_value(v) for v in val)
    if isinstance(val, float):
        # Use compact representation
        if val == int(val) and abs(val) < 1e15:
            return f"{val:.1f}"
        return f"{val}"
    return str(val)
