"""xTB input parser/writer.

Pure stdlib module for xTB input files:
- XYZ coordinate files
- xcontrol files (optional advanced settings)
"""

from __future__ import annotations

from typing import Any


def _frac_to_cart(frac: list[float], lattice: list[list[float]]) -> list[float]:
    return [
        frac[0] * lattice[0][0] + frac[1] * lattice[1][0] + frac[2] * lattice[2][0],
        frac[0] * lattice[0][1] + frac[1] * lattice[1][1] + frac[2] * lattice[2][1],
        frac[0] * lattice[0][2] + frac[1] * lattice[1][2] + frac[2] * lattice[2][2],
    ]


def write_xyz_text(structure: dict[str, Any] | None) -> str:
    """Write an XYZ file from structure dict.

    Supported structure keys:
    - species + cart_coords
    - species + frac_coords + lattice
    - optional comment
    """
    if not structure:
        return ""

    species = structure.get("species", [])
    comment = str(structure.get("comment", ""))
    cart_coords = structure.get("cart_coords") or []
    frac_coords = structure.get("frac_coords") or []
    lattice = structure.get("lattice") or []

    if not cart_coords and frac_coords and lattice:
        cart_coords = [_frac_to_cart(fc, lattice) for fc in frac_coords]

    n_atoms = min(len(species), len(cart_coords))
    lines = [str(n_atoms), comment]
    for sym, cc in zip(species[:n_atoms], cart_coords[:n_atoms]):
        lines.append(f"{sym:>2s}  {cc[0]:16.10f}  {cc[1]:16.10f}  {cc[2]:16.10f}")
    return "\n".join(lines) + "\n"


def parse_xyz_text(text: str) -> dict[str, Any]:
    """Parse XYZ text into structure dict with Cartesian coordinates."""
    stripped = text.strip()
    if not stripped:
        return {}

    lines = stripped.splitlines()
    if len(lines) < 2:
        return {}

    try:
        n_atoms = int(lines[0].strip())
    except ValueError:
        return {}

    comment = lines[1].strip()
    species: list[str] = []
    cart_coords: list[list[float]] = []

    for line in lines[2 : 2 + n_atoms]:
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            species.append(parts[0])
            cart_coords.append([
                float(parts[1]),
                float(parts[2]),
                float(parts[3]),
            ])
        except ValueError:
            continue

    return {
        "comment": comment,
        "species": species,
        "cart_coords": cart_coords,
    }


def _format_xcontrol_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _parse_xcontrol_scalar(raw: str) -> Any:
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        if "." not in raw and "e" not in lower:
            return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def write_xcontrol_text(params: dict[str, Any] | None) -> str:
    """Write xcontrol text from params.

    Expects params to contain either:
    - xcontrol: {block_name: {key: value}}
    - xcontrol_blocks: {block_name: {key: value}}
    """
    if not params:
        return ""

    blocks = params.get("xcontrol") or params.get("xcontrol_blocks")
    if not blocks:
        return ""

    lines: list[str] = []
    for block_name, block_value in blocks.items():
        lines.append(f"${block_name}")
        if isinstance(block_value, dict):
            for key, value in block_value.items():
                lines.append(f"   {key}={_format_xcontrol_scalar(value)}")
        elif isinstance(block_value, list):
            for item in block_value:
                lines.append(f"   {item}")
        elif block_value is not None:
            lines.append(f"   {_format_xcontrol_scalar(block_value)}")
        lines.append("$end")
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def parse_xcontrol_text(text: str) -> dict[str, Any]:
    """Parse xcontrol text into params dict: {"xcontrol": {...}}."""
    blocks: dict[str, Any] = {}
    current_block: str | None = None
    current_values: dict[str, Any] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("$") and line.lower() != "$end":
            current_block = line[1:].strip()
            current_values = {}
            continue

        if line.lower() == "$end":
            if current_block is not None:
                blocks[current_block] = dict(current_values)
            current_block = None
            current_values = {}
            continue

        if current_block is None:
            continue

        if "=" in line:
            key, value = line.split("=", 1)
            current_values[key.strip()] = _parse_xcontrol_scalar(value.strip())
        else:
            current_values[line] = True

    if not blocks:
        return {}
    return {"xcontrol": blocks}
