"""Siesta FDF parser/writer.

Pure stdlib I/O helpers for the universal inputformat orchestrator.

- parse_fdf_text(text) -> {"params": ..., "structure": ...}
- write_fdf_text(fragment) -> canonical FDF text
"""

from __future__ import annotations

import math
import re
from typing import Any

_BOHR_TO_ANG = 0.529177210903

_Z_TO_SYMBOL = {
    1: "H", 2: "He", 3: "Li", 4: "Be", 5: "B", 6: "C", 7: "N", 8: "O",
    9: "F", 10: "Ne", 11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P",
    16: "S", 17: "Cl", 18: "Ar", 19: "K", 20: "Ca", 21: "Sc", 22: "Ti",
    23: "V", 24: "Cr", 25: "Mn", 26: "Fe", 27: "Co", 28: "Ni", 29: "Cu",
    30: "Zn", 31: "Ga", 32: "Ge", 33: "As", 34: "Se", 35: "Br", 36: "Kr",
}
_SYMBOL_TO_Z = {sym: z for z, sym in _Z_TO_SYMBOL.items()}


def _strip_comment(line: str) -> str:
    """Remove trailing # or ! comments."""
    out = line
    for marker in ("#", "!"):
        idx = out.find(marker)
        if idx >= 0:
            out = out[:idx]
    return out.strip()


def _coerce_scalar(token: str) -> Any:
    t = token.strip()
    if not t:
        return ""

    low = t.lower()
    if low in {"t", ".true.", "true", "yes"}:
        return True
    if low in {"f", ".false.", "false", "no"}:
        return False

    # Fortran exponent style (e.g., 1.d-4).
    if re.match(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)[dD][+-]?\d+$", t):
        return float(t.replace("D", "e").replace("d", "e"))

    if re.match(r"^[+-]?\d+$", t):
        try:
            return int(t)
        except ValueError:
            return t

    if re.match(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$", t):
        try:
            return float(t)
        except ValueError:
            return t

    return t


def _coerce_tokens(tokens: list[str]) -> Any:
    """Coerce value tokens for non-block key-value lines."""
    if not tokens:
        return ""

    if len(tokens) == 1:
        return _coerce_scalar(tokens[0])

    # Keep numeric+unit pairs as one string (e.g. "200 Ry", "0.02 eV/Ang").
    if isinstance(_coerce_scalar(tokens[0]), (int, float)):
        if any(ch.isalpha() for ch in "".join(tokens[1:])):
            return " ".join(tokens)

    coerced = [_coerce_scalar(tok) for tok in tokens]
    if all(isinstance(v, (int, float, bool)) for v in coerced):
        return coerced

    return " ".join(tokens)


def _as_bool_token(value: Any) -> str:
    if isinstance(value, bool):
        return "T" if value else "F"
    return str(value)


def _as_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.match(r"^[\s]*([+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eEdD][+-]?\d+)?)", value)
        if m:
            raw = m.group(1).replace("D", "e").replace("d", "e")
            try:
                return float(raw)
            except ValueError:
                return None
    return None


def _extract_number_and_unit(value: Any) -> tuple[float | None, str]:
    """Extract leading numeric value and optional unit token."""
    if isinstance(value, (int, float)):
        return float(value), ""
    if isinstance(value, str):
        m = re.match(
            r"^\s*([+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eEdD][+-]?\d+)?)\s*([A-Za-z/._-]+)?",
            value,
        )
        if m:
            raw = m.group(1).replace("D", "e").replace("d", "e")
            try:
                num = float(raw)
            except ValueError:
                return None, ""
            unit = m.group(2) or ""
            return num, unit
    return None, ""


def _det3(mat: list[list[float]]) -> float:
    a = mat
    return (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )


def _mat_inv3(mat: list[list[float]]) -> list[list[float]]:
    det = _det3(mat)
    if abs(det) < 1e-16:
        raise ValueError("Singular lattice matrix")

    a = mat
    inv = [[0.0, 0.0, 0.0] for _ in range(3)]
    inv[0][0] = (a[1][1] * a[2][2] - a[1][2] * a[2][1]) / det
    inv[0][1] = (a[0][2] * a[2][1] - a[0][1] * a[2][2]) / det
    inv[0][2] = (a[0][1] * a[1][2] - a[0][2] * a[1][1]) / det
    inv[1][0] = (a[1][2] * a[2][0] - a[1][0] * a[2][2]) / det
    inv[1][1] = (a[0][0] * a[2][2] - a[0][2] * a[2][0]) / det
    inv[1][2] = (a[0][2] * a[1][0] - a[0][0] * a[1][2]) / det
    inv[2][0] = (a[1][0] * a[2][1] - a[1][1] * a[2][0]) / det
    inv[2][1] = (a[0][1] * a[2][0] - a[0][0] * a[2][1]) / det
    inv[2][2] = (a[0][0] * a[1][1] - a[0][1] * a[1][0]) / det
    return inv


def _mat_vec(mat: list[list[float]], vec: list[float]) -> list[float]:
    return [
        mat[0][0] * vec[0] + mat[0][1] * vec[1] + mat[0][2] * vec[2],
        mat[1][0] * vec[0] + mat[1][1] * vec[1] + mat[1][2] * vec[2],
        mat[2][0] * vec[0] + mat[2][1] * vec[1] + mat[2][2] * vec[2],
    ]


def parse_fdf_text(text: str) -> dict[str, Any]:
    """Parse Siesta FDF text into params + structure."""
    params: dict[str, Any] = {}
    structure: dict[str, Any] = {}

    species_map: dict[int, str] = {}
    z_map: dict[str, int] = {}
    lattice_vectors: list[list[float]] | None = None
    lattice_constant = 1.0
    lattice_constant_unit = "Ang"
    coord_format = "Ang"
    coord_rows: list[tuple[list[float], int]] = []

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = _strip_comment(raw)
        i += 1

        if not line:
            continue

        m_block = re.match(r"^%block\s+(\S+)", line, flags=re.IGNORECASE)
        if m_block:
            block_name = m_block.group(1)
            block_name_low = block_name.lower()
            block_lines: list[str] = []

            while i < len(lines):
                next_line_raw = lines[i]
                next_line = _strip_comment(next_line_raw)
                i += 1
                if re.match(r"^%endblock\b", next_line, flags=re.IGNORECASE):
                    break
                if next_line:
                    block_lines.append(next_line)

            if block_name_low == "chemicalspecieslabel":
                for bl in block_lines:
                    toks = bl.split()
                    if len(toks) < 3:
                        continue
                    try:
                        idx = int(toks[0])
                        z = int(float(toks[1]))
                    except ValueError:
                        continue
                    label = toks[2]
                    if not label and z in _Z_TO_SYMBOL:
                        label = _Z_TO_SYMBOL[z]
                    species_map[idx] = label
                    z_map[label] = z

            elif block_name_low == "latticevectors":
                parsed: list[list[float]] = []
                for bl in block_lines:
                    toks = bl.split()
                    if len(toks) < 3:
                        continue
                    try:
                        parsed.append([float(toks[0]), float(toks[1]), float(toks[2])])
                    except ValueError:
                        continue
                if len(parsed) >= 3:
                    lattice_vectors = parsed[:3]

            elif block_name_low == "atomiccoordinatesandatomicspecies":
                for bl in block_lines:
                    toks = bl.split()
                    if len(toks) < 4:
                        continue
                    try:
                        xyz = [float(toks[0]), float(toks[1]), float(toks[2])]
                        sidx = int(float(toks[3]))
                    except ValueError:
                        continue
                    coord_rows.append((xyz, sidx))

            elif block_name_low == "kgrid_monkhorst_pack":
                rows: list[list[float | int]] = []
                for bl in block_lines:
                    toks = bl.split()
                    if len(toks) < 3:
                        continue
                    row: list[float | int] = []
                    for tok in toks[:4]:
                        c = _coerce_scalar(tok)
                        row.append(c if isinstance(c, (int, float)) else tok)
                    rows.append(row)
                params["kgrid"] = rows

            elif block_name_low == "projecteddensityofstates":
                vals: list[str] = []
                for bl in block_lines:
                    vals.extend(bl.split())
                if vals:
                    if len(vals) >= 4:
                        npt = _coerce_scalar(vals[3])
                        params["ProjectedDensityOfStates"] = {
                            "emin": _coerce_scalar(vals[0]),
                            "emax": _coerce_scalar(vals[1]),
                            "sigma": _coerce_scalar(vals[2]),
                            "npoints": int(npt) if isinstance(npt, (int, float)) else npt,
                            "unit": vals[4] if len(vals) >= 5 else "eV",
                        }
                    else:
                        params["ProjectedDensityOfStates"] = " ".join(vals)

            elif block_name_low == "bandlines":
                bands: list[dict[str, Any]] = []
                for bl in block_lines:
                    toks = bl.split()
                    if len(toks) < 5:
                        continue
                    try:
                        bands.append({
                            "npoints": int(float(toks[0])),
                            "kx": float(toks[1]),
                            "ky": float(toks[2]),
                            "kz": float(toks[3]),
                            "label": toks[4],
                        })
                    except ValueError:
                        continue
                params["BandLines"] = bands

            else:
                # Keep unknown blocks as a raw list for non-lossy semantic roundtrip.
                params[block_name] = block_lines

            continue

        # Scalar line: "Key value" or "Key = value"
        if "=" in line:
            key, raw_val = line.split("=", 1)
            key = key.strip()
            tokens = raw_val.strip().split()
        else:
            toks = line.split()
            if len(toks) < 2:
                params[toks[0]] = True
                continue
            key = toks[0]
            tokens = toks[1:]

        val = _coerce_tokens(tokens)
        params[key] = val

        if key.lower() == "latticeconstant":
            n = _as_number(val)
            if n is not None:
                lattice_constant = n
                if isinstance(val, str):
                    parts = val.split()
                    if len(parts) >= 2:
                        lattice_constant_unit = parts[1]
                elif isinstance(tokens, list) and len(tokens) >= 2:
                    lattice_constant_unit = tokens[1]

        if key.lower() == "atomiccoordinatesformat":
            coord_format = str(val)

    # Build structure
    if lattice_vectors is not None:
        scale = lattice_constant
        unit_low = lattice_constant_unit.lower()
        if unit_low.startswith("bohr"):
            scale *= _BOHR_TO_ANG
        structure["lattice"] = [[scale * c for c in row] for row in lattice_vectors]

    if coord_rows:
        species: list[str] = []
        coords: list[list[float]] = []
        for xyz, sidx in coord_rows:
            species.append(species_map.get(sidx, f"Type{sidx}"))
            coords.append(xyz)
        structure["species"] = species

        fmt = coord_format.strip().lower()
        if fmt in {"fractional", "scaledcartesian", "scaled"}:
            structure["frac_coords"] = coords
        elif fmt.startswith("bohr"):
            structure["cart_coords"] = [[_BOHR_TO_ANG * x for x in row] for row in coords]
        else:
            structure["cart_coords"] = coords

    if z_map:
        params["znucl"] = dict(z_map)

    # Add normalized aliases for common keys used by driver-side helper code.
    for src, alias in (("SystemName", "system_name"), ("SystemLabel", "system_label")):
        if src in params and alias not in params:
            params[alias] = params[src]

    return {"params": params, "structure": structure}


def _param_get(params: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in params:
            return params[key]
    return default


def write_fdf_text(fragment: dict[str, Any]) -> str:
    """Write canonical FDF text from {params, structure}."""
    params = dict(fragment.get("params") or {})
    structure = dict(fragment.get("structure") or {})

    system_name = _param_get(params, "system_name", "SystemName", default="system")
    system_label = _param_get(params, "system_label", "SystemLabel", default="siesta")

    # Work with a local mutable copy while preserving caller data.
    out_params = dict(params)

    lines: list[str] = []
    lines.append(f"SystemName        {system_name}")
    lines.append(f"SystemLabel       {system_label}")
    lines.append("")

    # Structure: species + coordinates.
    species = list(structure.get("species") or [])
    frac_coords = structure.get("frac_coords")
    cart_coords = structure.get("cart_coords")

    # Normalize species ordering while preserving first appearance.
    uniq_species: list[str] = []
    for sp in species:
        if sp not in uniq_species:
            uniq_species.append(sp)

    if species:
        lines.append(f"NumberOfAtoms     {len(species)}")
        lines.append(f"NumberOfSpecies   {len(uniq_species)}")
        lines.append("")

        znucl = out_params.get("znucl") if isinstance(out_params.get("znucl"), dict) else {}
        lines.append("%block ChemicalSpeciesLabel")
        for idx, sp in enumerate(uniq_species, 1):
            z = int(znucl.get(sp, _SYMBOL_TO_Z.get(sp, 0)))
            lines.append(f" {idx}  {z}  {sp}")
        lines.append("%endblock ChemicalSpeciesLabel")
        lines.append("")

    lattice = structure.get("lattice")
    if isinstance(lattice, list) and len(lattice) == 3:
        lc_raw = _param_get(out_params, "LatticeConstant", "lattice_constant")
        lc_num, lc_unit = _extract_number_and_unit(lc_raw)
        if lc_num is None or abs(lc_num) < 1e-16:
            lc_num = 1.0
            lc_unit = "Ang"
        if not lc_unit:
            lc_unit = "Ang"

        # Convert lattice constant to Angstrom scaling basis.
        lc_scale_ang = lc_num
        if lc_unit.lower().startswith("bohr"):
            lc_scale_ang *= _BOHR_TO_ANG

        lines.append(f"LatticeConstant   {lc_num:.12g} {lc_unit}")
        lines.append("%block LatticeVectors")
        for row in lattice:
            lines.append(
                "  "
                + f"{float(row[0]) / lc_scale_ang:.10f}  "
                + f"{float(row[1]) / lc_scale_ang:.10f}  "
                + f"{float(row[2]) / lc_scale_ang:.10f}"
            )
        lines.append("%endblock LatticeVectors")
        lines.append("")

    explicit_coord = _param_get(
        out_params,
        "AtomicCoordinatesFormat",
        "atomic_coordinates_format",
        default=None,
    )
    coord_format = str(explicit_coord) if explicit_coord is not None else ("Fractional" if frac_coords else "Ang")

    coords_to_write: list[list[float]] = []
    if frac_coords:
        coords_to_write = [[float(v) for v in row[:3]] for row in frac_coords]
    elif cart_coords:
        coords_to_write = [[float(v) for v in row[:3]] for row in cart_coords]

    if species and coords_to_write and len(coords_to_write) == len(species):
        lines.append(f"AtomicCoordinatesFormat  {coord_format}")
        lines.append("%block AtomicCoordinatesAndAtomicSpecies")
        sp_index = {sp: i + 1 for i, sp in enumerate(uniq_species)}
        for sp, xyz in zip(species, coords_to_write):
            lines.append(
                f"  {xyz[0]:.10f}  {xyz[1]:.10f}  {xyz[2]:.10f}  {sp_index.get(sp, 1)}"
            )
        lines.append("%endblock AtomicCoordinatesAndAtomicSpecies")
        lines.append("")

    # Prevent duplicate emission for already materialized fields.
    for consumed in (
        "system_name",
        "SystemName",
        "system_label",
        "SystemLabel",
        "LatticeConstant",
        "lattice_constant",
        "NumberOfAtoms",
        "number_of_atoms",
        "NumberOfSpecies",
        "number_of_species",
        "AtomicCoordinatesFormat",
        "atomic_coordinates_format",
        "znucl",
    ):
        out_params.pop(consumed, None)

    # Emit scalar params first (except handled block-like fields).
    block_keys = {
        "kgrid",
        "kgrid_Monkhorst_Pack",
        "ProjectedDensityOfStates",
        "BandLines",
        "BandLinesScale",
    }

    unknown_blocks: dict[str, list[str]] = {}

    for key in sorted(out_params.keys(), key=str.lower):
        if key in block_keys:
            continue
        value = out_params[key]

        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            # Unknown block payload retained by parser.
            unknown_blocks[key] = value
            continue

        if isinstance(value, bool):
            val_str = _as_bool_token(value)
        elif isinstance(value, (int, float)):
            # Keep ints as ints and floats compact.
            if isinstance(value, bool):
                val_str = _as_bool_token(value)
            elif isinstance(value, int):
                val_str = str(value)
            else:
                val_str = f"{value:.12g}"
        elif isinstance(value, list):
            val_str = " ".join(str(x) for x in value)
        elif isinstance(value, dict):
            # Unknown nested dict: skip to avoid emitting invalid FDF lines.
            continue
        else:
            val_str = str(value)

        lines.append(f"{key}   {val_str}")

    if lines and lines[-1] != "":
        lines.append("")

    # Known blocks in canonical order.
    kgrid = out_params.get("kgrid") or out_params.get("kgrid_Monkhorst_Pack")
    if isinstance(kgrid, list) and kgrid:
        lines.append("%block kgrid_Monkhorst_Pack")
        for row in kgrid:
            if isinstance(row, (list, tuple)):
                parts = [str(x) for x in row]
                if len(parts) == 3:
                    parts.append("0.0")
                lines.append("  " + "  ".join(parts[:4]))
        lines.append("%endblock kgrid_Monkhorst_Pack")
        lines.append("")

    pdos = out_params.get("ProjectedDensityOfStates")
    if pdos is not None:
        lines.append("%block ProjectedDensityOfStates")
        if isinstance(pdos, dict):
            unit = pdos.get("unit", "eV")
            line = (
                f"  {pdos.get('emin', -20.0)}  {pdos.get('emax', 10.0)}  "
                f"{pdos.get('sigma', 0.1)}  {pdos.get('npoints', 500)}  {unit}"
            )
            lines.append(line)
        elif isinstance(pdos, list):
            lines.append("  " + "  ".join(str(v) for v in pdos))
        else:
            lines.append("  " + str(pdos))
        lines.append("%endblock ProjectedDensityOfStates")
        lines.append("")

    band_scale = out_params.get("BandLinesScale")
    if band_scale is not None:
        lines.append(f"BandLinesScale   {band_scale}")

    band_lines = out_params.get("BandLines")
    if isinstance(band_lines, list) and band_lines:
        lines.append("%block BandLines")
        for item in band_lines:
            if isinstance(item, dict):
                lines.append(
                    f" {int(item.get('npoints', 1))}  {float(item.get('kx', 0.0)):.6f}"
                    f"  {float(item.get('ky', 0.0)):.6f}  {float(item.get('kz', 0.0)):.6f}"
                    f"  {item.get('label', 'K')}"
                )
            elif isinstance(item, (list, tuple)) and len(item) >= 5:
                lines.append(
                    f" {int(float(item[0]))}  {float(item[1]):.6f}  {float(item[2]):.6f}"
                    f"  {float(item[3]):.6f}  {item[4]}"
                )
            else:
                lines.append(" " + str(item))
        lines.append("%endblock BandLines")
        lines.append("")

    # Unknown blocks are emitted last to preserve non-lossy semantics.
    for bname in sorted(unknown_blocks.keys(), key=str.lower):
        lines.append(f"%block {bname}")
        for row in unknown_blocks[bname]:
            lines.append(" " + row)
        lines.append(f"%endblock {bname}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["parse_fdf_text", "write_fdf_text"]
