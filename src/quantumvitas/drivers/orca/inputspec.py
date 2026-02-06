"""ORCA engine input specification for the universal writer.

Single combined file: {basename}.inp containing keywords + geometry block.
Dynamic filename resolved via get_input_spec(basename=...).
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    SSOTMappingSpec,
)


def _format_block_value(value: Any) -> str:
    """Format a value for ORCA block output."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write_orca_text(fragment: dict[str, Any]) -> str:
    """Write ORCA input text from combined params + structure.

    Generates keyword-line + geometry block format.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    lines: list[str] = []

    # Build keyword line
    kw_parts: list[str] = []
    method = params.get("method", "HF")
    basis = params.get("basis", "def2-SVP")
    kw_parts.append(method)
    kw_parts.append(basis)

    keywords = params.get("keywords", [])
    if keywords:
        kw_parts.extend(keywords)

    # Add CPCM solvation if present (and not already in keywords)
    solvation = params.get("solvation")
    if solvation:
        cpcm_kw = f"CPCM({solvation})"
        if cpcm_kw not in kw_parts and cpcm_kw.upper() not in [k.upper() for k in kw_parts]:
            kw_parts.append(cpcm_kw)

    lines.append(f"! {' '.join(kw_parts)}")

    # %pal block (multi-line format)
    nprocs = params.get("nprocs")
    if nprocs and nprocs > 1:
        lines.append("%pal")
        lines.append(f"  nprocs {nprocs}")
        lines.append("end")

    # %maxcore
    maxcore = params.get("maxcore")
    if maxcore:
        lines.append(f"%maxcore {maxcore}")

    # Extra blocks (e.g., %scf, %tddft, %geom, %casscf)
    # Skip 'pal' block since we handle it separately above
    extra_blocks = params.get("blocks", {})
    for block_name, block_params in extra_blocks.items():
        if block_name == "pal":
            continue  # Already handled above
        lines.append(f"%{block_name}")
        for k, v in block_params.items():
            formatted_val = _format_block_value(v)
            # Handle array syntax (keys containing '[')
            if "[" in k or "=" in str(v):
                lines.append(f"  {k} = {formatted_val}")
            else:
                lines.append(f"  {k} {formatted_val}")
        lines.append("end")

    lines.append("")

    # Geometry block
    charge = params.get("charge", 0)
    multiplicity = params.get("multiplicity", 1)
    lines.append(f"* xyz {charge} {multiplicity}")

    species_list = structure.get("species", [])
    # Support both cart_coords and frac_coords
    cart_coords = structure.get("cart_coords", [])
    frac_coords = structure.get("frac_coords", [])
    lattice = structure.get("lattice", [])

    if cart_coords:
        # Use Cartesian coords directly
        for sym, cc in zip(species_list, cart_coords):
            lines.append(f"  {sym:2s}  {cc[0]:14.8f}  {cc[1]:14.8f}  {cc[2]:14.8f}")
    elif frac_coords and lattice:
        # Convert fractional to Cartesian
        for sym, fc in zip(species_list, frac_coords):
            x = fc[0] * lattice[0][0] + fc[1] * lattice[1][0] + fc[2] * lattice[2][0]
            y = fc[0] * lattice[0][1] + fc[1] * lattice[1][1] + fc[2] * lattice[2][1]
            z = fc[0] * lattice[0][2] + fc[1] * lattice[1][2] + fc[2] * lattice[2][2]
            lines.append(f"  {sym:2s}  {x:14.8f}  {y:14.8f}  {z:14.8f}")
    elif frac_coords:
        # Fractional without lattice - treat as Cartesian
        for sym, fc in zip(species_list, frac_coords):
            lines.append(f"  {sym:2s}  {fc[0]:14.8f}  {fc[1]:14.8f}  {fc[2]:14.8f}")

    lines.append("*")
    lines.append("")

    return "\n".join(lines) + "\n"


# Known ORCA functionals (method names)
_FUNCTIONALS = frozenset([
    # Pure GGA
    "BP86", "BLYP", "PBE", "OLYP", "TPSS", "M06L", "B97D", "B97D3",
    # Hybrid GGA
    "B3LYP", "PBE0", "B3PW91", "BHANDHLYP", "BHandHLYP",
    "B1LYP", "B3P86", "O3LYP", "X3LYP", "B97",
    # Hybrid meta-GGA
    "M06", "M062X", "M06-2X", "TPSSh", "TPSS0",
    # Range-separated
    "WB97", "WB97X", "WB97X-D3", "WB97X-D3BJ", "WB97X-D4",
    "CAM-B3LYP", "LC-BLYP", "LC-PBE", "wB97", "wB97X",
    # Double-hybrid
    "B2PLYP", "B2PLYP-D3", "RI-B2PLYP", "mPW2PLYP", "PWPB95",
    # Wavefunction methods
    "HF", "MP2", "RI-MP2", "SCS-MP2", "OO-SCS-MP2",
    "CCSD", "CCSD(T)", "DLPNO-CCSD", "DLPNO-CCSD(T)",
    "CASSCF", "NEVPT2", "MRCI",
])

# Known basis set patterns
_BASIS_PREFIXES = ("DEF2-", "CC-", "AUG-CC-", "6-31", "6-311", "STO-", "PC-", "APC-")


def _is_basis_set(token: str) -> bool:
    """Check if token looks like a basis set name."""
    upper = token.upper()
    for prefix in _BASIS_PREFIXES:
        if upper.startswith(prefix):
            return True
    # Also match auxiliary basis sets like DEF2/J
    if "/" in token and any(upper.startswith(p) for p in _BASIS_PREFIXES):
        return True
    return False


def _is_functional(token: str) -> bool:
    """Check if token is a known DFT functional or method."""
    upper = token.upper()
    # Exact match
    if upper in _FUNCTIONALS:
        return True
    # Handle variants like B3LYP/G, B3LYP-D3, etc.
    base = upper.split("/")[0].split("-D")[0]
    return base in _FUNCTIONALS


def _parse_bool(value: str) -> bool | str:
    """Convert string to bool if it's a boolean value, else return as-is."""
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    return value


def _parse_value(value_str: str) -> Any:
    """Parse a value string into appropriate Python type."""
    # Boolean
    lower = value_str.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    # Integer
    try:
        return int(value_str)
    except ValueError:
        pass
    # Float
    try:
        return float(value_str)
    except ValueError:
        pass
    # String (as-is)
    return value_str


def _parse_orca_text(text: str) -> dict[str, Any]:
    """Parse ORCA input text into combined params + structure dict.

    Handles:
    - ! keyword lines (method, basis, extra keywords)
    - %pal nprocs N end — parallel settings (single or multi-line)
    - %maxcore N — memory per core
    - %block ... end — arbitrary named blocks
    - * xyz charge mult ... * — geometry block (Cartesian)
    - CPCM(solvent) on keyword line
    - Boolean values (true/false)
    - Array syntax in blocks (e.g., weights[0] = 1,1,1,1)

    Returns:
        {"params": {...}, "structure": {"species": [...], "cart_coords": [...]}}
    """
    params: dict[str, Any] = {}
    species: list[str] = []
    cart_coords: list[list[float]] = []

    lines = text.splitlines()
    i = 0

    # Collect all keyword lines (ORCA allows multiple ! lines)
    all_keywords: list[str] = []

    while i < len(lines):
        line = lines[i].strip()

        # Empty line
        if not line:
            i += 1
            continue

        # Comment line
        if line.startswith("#"):
            i += 1
            continue

        # Keyword line - collect tokens
        if line.startswith("!"):
            tokens = line[1:].split()
            all_keywords.extend(tokens)
            i += 1
            continue

        # %maxcore (single-line only)
        if line.lower().startswith("%maxcore"):
            tokens = line.split()
            if len(tokens) >= 2:
                params["maxcore"] = _parse_value(tokens[1])
            i += 1
            continue

        # Generic %block ... end (including %pal)
        if line.startswith("%"):
            block_name = line[1:].split()[0]
            # Check for single-line block: %blockname ... end
            if "end" in line.lower():
                # Single-line block
                tokens = line.split()
                block_params: dict[str, Any] = {}
                for j in range(1, len(tokens) - 1):  # skip %blockname and 'end'
                    if tokens[j].lower() != "end":
                        # Try to parse key-value pairs
                        if j + 1 < len(tokens) and tokens[j + 1].lower() != "end":
                            block_params[tokens[j]] = _parse_value(tokens[j + 1])
                if "blocks" not in params:
                    params["blocks"] = {}
                params["blocks"][block_name] = block_params
                i += 1
            else:
                # Multi-line block
                block_params = {}
                i += 1
                while i < len(lines):
                    bline = lines[i].strip()
                    if bline.lower() == "end":
                        i += 1
                        break
                    if not bline or bline.startswith("#"):
                        i += 1
                        continue

                    # Handle array syntax: key[idx] = value or key = value
                    if "=" in bline:
                        key_part, val_part = bline.split("=", 1)
                        key = key_part.strip()
                        val = val_part.strip()
                        block_params[key] = val
                    else:
                        parts = bline.split(None, 1)
                        if len(parts) == 2:
                            block_params[parts[0]] = _parse_value(parts[1])
                        elif len(parts) == 1:
                            block_params[parts[0]] = True
                    i += 1

                if "blocks" not in params:
                    params["blocks"] = {}
                params["blocks"][block_name] = block_params
            continue

        # Geometry block: * xyz charge mult ... *
        if line.startswith("*") and len(line) > 1:
            tokens = line[1:].strip().split()
            if tokens and tokens[0].lower() == "xyz" and len(tokens) >= 3:
                try:
                    params["charge"] = int(tokens[1])
                    params["multiplicity"] = int(tokens[2])
                except ValueError:
                    pass
                i += 1
                # Read atom lines until closing *
                while i < len(lines):
                    aline = lines[i].strip()
                    if aline == "*":
                        i += 1
                        break
                    if not aline:
                        i += 1
                        continue
                    parts = aline.split()
                    if len(parts) >= 4:
                        species.append(parts[0])
                        try:
                            cart_coords.append([
                                float(parts[1]),
                                float(parts[2]),
                                float(parts[3]),
                            ])
                        except ValueError:
                            pass
                    i += 1
                continue

        i += 1

    # Process collected keywords to extract method, basis, etc.
    if all_keywords:
        method = None
        basis = None
        extra_keywords: list[str] = []
        solvation = None

        for kw in all_keywords:
            # Check for CPCM(solvent) pattern
            if kw.upper().startswith("CPCM(") and kw.endswith(")"):
                solvation = kw[5:-1]  # Extract solvent name
                extra_keywords.append(kw)
                continue

            # Identify functional (method)
            if method is None and _is_functional(kw):
                method = kw
                continue

            # Identify basis set
            if basis is None and _is_basis_set(kw):
                basis = kw
                continue

            # Everything else goes to keywords
            extra_keywords.append(kw)

        if method:
            params["method"] = method
        if basis:
            params["basis"] = basis
        if extra_keywords:
            params["keywords"] = extra_keywords
        if solvation:
            params["solvation"] = solvation

    # Extract nprocs from %pal block if present
    if "blocks" in params and "pal" in params["blocks"]:
        pal_block = params["blocks"]["pal"]
        if "nprocs" in pal_block:
            params["nprocs"] = pal_block["nprocs"]

    structure: dict[str, Any] = {}
    if species:
        structure["species"] = species
        structure["cart_coords"] = cart_coords

    return {"params": params, "structure": structure}


def get_orca_input_spec(**context: Any) -> EngineInputSpec:
    """Return the ORCA EngineInputSpec.

    Args:
        **context: May contain basename for dynamic filename.
    """
    basename = context.get("basename", "orca_calc")
    filename = f"{basename}.inp"

    return EngineInputSpec(
        engine_family="orca",
        syntax_family="keyword-block",
        input_files=(
            InputFileSpec(
                filename=filename,
                content_role="combined",
                description="ORCA input file (keywords + geometry)",
                custom_writer=_write_orca_text,
                custom_parser=_parse_orca_text,
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=(filename,),
            params_in=(filename,),
        ),
    )
