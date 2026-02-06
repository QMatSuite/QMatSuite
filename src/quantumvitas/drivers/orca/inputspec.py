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


def _write_orca_text(fragment: dict[str, Any]) -> str:
    """Write ORCA input text from combined params + structure.

    Generates keyword-line + geometry block format.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    lines: list[str] = []

    # Keyword line
    method = params.get("method", "HF")
    basis = params.get("basis", "def2-SVP")
    keywords = params.get("keywords", [])
    extra_kw = " ".join(keywords) if keywords else ""
    lines.append(f"! {method} {basis} {extra_kw}".rstrip())

    # Additional blocks (%pal, %maxcore, etc.)
    nprocs = params.get("nprocs")
    if nprocs and nprocs > 1:
        lines.append(f"%pal nprocs {nprocs} end")

    maxcore = params.get("maxcore")
    if maxcore:
        lines.append(f"%maxcore {maxcore}")

    # Extra blocks (e.g., %scf, %tddft)
    extra_blocks = params.get("blocks", {})
    for block_name, block_params in extra_blocks.items():
        lines.append(f"%{block_name}")
        for k, v in block_params.items():
            lines.append(f"  {k} {v}")
        lines.append("end")

    lines.append("")

    # Geometry block
    charge = params.get("charge", 0)
    multiplicity = params.get("multiplicity", 1)
    lines.append(f"* xyz {charge} {multiplicity}")

    species = structure.get("species", [])
    frac_coords = structure.get("frac_coords", [])
    lattice = structure.get("lattice", [])

    # Convert fractional to Cartesian
    for sym, fc in zip(species, frac_coords):
        if lattice:
            x = fc[0] * lattice[0][0] + fc[1] * lattice[1][0] + fc[2] * lattice[2][0]
            y = fc[0] * lattice[0][1] + fc[1] * lattice[1][1] + fc[2] * lattice[2][1]
            z = fc[0] * lattice[0][2] + fc[1] * lattice[1][2] + fc[2] * lattice[2][2]
        else:
            x, y, z = fc[0], fc[1], fc[2]
        lines.append(f"  {sym:2s}  {x:14.8f}  {y:14.8f}  {z:14.8f}")

    lines.append("*")
    lines.append("")

    return "\n".join(lines) + "\n"


def _parse_orca_text(text: str) -> dict[str, Any]:
    """Parse ORCA input text into combined params + structure dict.

    Handles:
    - ! keyword lines (method, basis, extra keywords)
    - %pal nprocs N end — parallel settings
    - %maxcore N — memory per core
    - %block ... end — arbitrary named blocks
    - * xyz charge mult ... * — geometry block (Cartesian)

    Returns:
        {"params": {...}, "structure": {"species": [...], "cart_coords": [...]}}
    """
    params: dict[str, Any] = {}
    species: list[str] = []
    cart_coords: list[list[float]] = []

    lines = text.splitlines()
    i = 0
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

        # Keyword line
        if line.startswith("!"):
            tokens = line[1:].split()
            if len(tokens) >= 1:
                params["method"] = tokens[0]
            if len(tokens) >= 2:
                params["basis"] = tokens[1]
            if len(tokens) > 2:
                params["keywords"] = tokens[2:]
            i += 1
            continue

        # %pal block (single-line: %pal nprocs N end)
        if line.lower().startswith("%pal"):
            tokens = line.split()
            for j in range(len(tokens) - 1):
                if tokens[j].lower() == "nprocs":
                    try:
                        params["nprocs"] = int(tokens[j + 1])
                    except (ValueError, IndexError):
                        pass
            i += 1
            continue

        # %maxcore
        if line.lower().startswith("%maxcore"):
            tokens = line.split()
            if len(tokens) >= 2:
                try:
                    params["maxcore"] = int(tokens[1])
                except ValueError:
                    params["maxcore"] = tokens[1]
            i += 1
            continue

        # Generic %block ... end
        if line.startswith("%") and not line.lower().startswith("%pal") and not line.lower().startswith("%maxcore"):
            block_name = line[1:].split()[0]
            block_params: dict[str, Any] = {}
            i += 1
            while i < len(lines):
                bline = lines[i].strip()
                if bline.lower() == "end":
                    i += 1
                    break
                parts = bline.split(None, 1)
                if len(parts) == 2:
                    try:
                        block_params[parts[0]] = int(parts[1])
                    except ValueError:
                        try:
                            block_params[parts[0]] = float(parts[1])
                        except ValueError:
                            block_params[parts[0]] = parts[1]
                elif len(parts) == 1:
                    block_params[parts[0]] = True
                i += 1
            else:
                pass  # no "end" found
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
