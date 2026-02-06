"""VASP KPOINTS pure text <-> dict mapping.

Maps between KpointsSpec dict (SSOT-compatible) and VASP KPOINTS text.
Stdlib only — no pymatgen, no qmatsuite core imports.

KpointsSpec dict schema::

    Automatic mesh mode:
    {
        "mode": "automatic",
        "mesh": [nx, ny, nz],
        "shift": [sx, sy, sz],           # default [0, 0, 0]
        "centering": "Gamma",            # "Gamma" (default) or "Monkhorst-Pack"
    }

    Line mode (band path):
    {
        "mode": "line",
        "npoints": 40,
        "coord_type": "reciprocal",      # "reciprocal" (default) or "cartesian"
        "path": [
            {"start": [kx, ky, kz], "end": [kx, ky, kz],
             "start_label": "G", "end_label": "X"},
            ...
        ],
    }

    Explicit mode:
    {
        "mode": "explicit",
        "coord_type": "reciprocal",
        "kpoints": [[kx, ky, kz, weight], ...],
    }

Comments are stripped on parse. Writer produces clean canonical output.
"""

from __future__ import annotations

from typing import Any


def write_kpoints_text(kpoints: dict[str, Any]) -> str:
    """Write KPOINTS text from a KpointsSpec dict.

    Args:
        kpoints: Dict with ``mode`` and mode-specific fields.

    Returns:
        KPOINTS file content as a string.

    Raises:
        ValueError: If mode is unknown.
    """
    mode = kpoints.get("mode", "automatic")

    if mode == "automatic":
        return _write_automatic(kpoints)
    elif mode == "line":
        return _write_line(kpoints)
    elif mode == "explicit":
        return _write_explicit(kpoints)
    else:
        raise ValueError(f"Unknown KPOINTS mode: {mode!r}")


def parse_kpoints_text(text: str) -> dict[str, Any]:
    """Parse KPOINTS text into a KpointsSpec dict.

    Handles automatic (Gamma/MP), line-mode, and explicit k-point formats.
    Comments are stripped. Unknown content is silently dropped.

    Args:
        text: KPOINTS file content.

    Returns:
        KpointsSpec dict.

    Raises:
        ValueError: If the file is too short or unparseable.
    """
    lines = [l.strip() for l in text.strip().splitlines()]
    if len(lines) < 3:
        raise ValueError(
            f"KPOINTS too short: {len(lines)} lines (need >= 3)"
        )

    # Line 1: comment (ignored)
    # Line 2: number of k-points (0 = automatic mesh)
    nkpts = int(lines[1].split()[0])

    # Line 3: mode/type indicator
    mode_line = lines[2].strip()
    mode_char = mode_line[0].lower()

    if nkpts == 0:
        # Automatic mesh mode
        return _parse_automatic(lines, mode_line)
    elif mode_char == "l":
        # Line-mode
        return _parse_line(lines, nkpts)
    else:
        # Explicit k-points
        return _parse_explicit(lines, nkpts, mode_line)


# ---------------------------------------------------------------------------
# Writer helpers
# ---------------------------------------------------------------------------


def _write_automatic(kpoints: dict[str, Any]) -> str:
    mesh = kpoints.get("mesh", [4, 4, 4])
    shift = kpoints.get("shift", [0, 0, 0])
    centering = kpoints.get("centering", "Gamma")

    lines = [
        "Automatic",
        "0",
        centering,
        f"  {mesh[0]}  {mesh[1]}  {mesh[2]}",
        f"  {shift[0]}  {shift[1]}  {shift[2]}",
    ]
    return "\n".join(lines) + "\n"


def _write_line(kpoints: dict[str, Any]) -> str:
    npoints = kpoints.get("npoints", 40)
    coord_type = kpoints.get("coord_type", "reciprocal").capitalize()
    path = kpoints.get("path", [])

    lines = [
        "k-points along high symmetry path",
        str(npoints),
        "Line-mode",
        coord_type,
    ]

    for segment in path:
        start = segment["start"]
        end = segment["end"]
        start_label = segment.get("start_label", "")
        end_label = segment.get("end_label", "")

        sl = f"  ! {start_label}" if start_label else ""
        el = f"  ! {end_label}" if end_label else ""

        lines.append(
            f"  {start[0]:12.8f}  {start[1]:12.8f}  {start[2]:12.8f}{sl}"
        )
        lines.append(
            f"  {end[0]:12.8f}  {end[1]:12.8f}  {end[2]:12.8f}{el}"
        )
        lines.append("")  # blank line between segments

    return "\n".join(lines) + "\n"


def _write_explicit(kpoints: dict[str, Any]) -> str:
    coord_type = kpoints.get("coord_type", "reciprocal").capitalize()
    kpts = kpoints.get("kpoints", [])

    lines = [
        "Explicit k-points",
        str(len(kpts)),
        coord_type,
    ]

    for kpt in kpts:
        # kpt is [kx, ky, kz, weight]
        lines.append(
            f"  {kpt[0]:12.8f}  {kpt[1]:12.8f}  {kpt[2]:12.8f}  {kpt[3]:12.8f}"
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------


def _parse_automatic(
    lines: list[str], mode_line: str
) -> dict[str, Any]:
    """Parse automatic mesh KPOINTS."""
    mode_char = mode_line[0].lower()
    if mode_char == "g":
        centering = "Gamma"
    elif mode_char == "m":
        centering = "Monkhorst-Pack"
    else:
        centering = "Gamma"

    mesh = [4, 4, 4]
    shift = [0, 0, 0]

    if len(lines) > 3:
        mesh_parts = lines[3].split()
        if len(mesh_parts) >= 3:
            mesh = [int(mesh_parts[0]), int(mesh_parts[1]), int(mesh_parts[2])]

    if len(lines) > 4:
        shift_parts = lines[4].split()
        if len(shift_parts) >= 3:
            shift = [
                float(shift_parts[0]),
                float(shift_parts[1]),
                float(shift_parts[2]),
            ]

    return {
        "mode": "automatic",
        "mesh": mesh,
        "shift": shift,
        "centering": centering,
    }


def _parse_line(
    lines: list[str], npoints: int
) -> dict[str, Any]:
    """Parse line-mode KPOINTS."""
    # Line 4: coordinate type
    coord_type = "reciprocal"
    if len(lines) > 3:
        ct = lines[3].strip().lower()
        if ct.startswith("c") or ct.startswith("k"):
            coord_type = "cartesian"

    # Read k-point pairs (start/end per segment)
    path: list[dict[str, Any]] = []
    idx = 4
    start = None

    while idx < len(lines):
        line = lines[idx].strip()
        idx += 1

        if not line:
            continue

        # Parse k-point line: "kx ky kz  ! label" or "kx ky kz"
        parts = line.split("!")
        coords_part = parts[0].strip().split()
        label = parts[1].strip() if len(parts) > 1 else ""

        if len(coords_part) < 3:
            continue

        kpt = [float(coords_part[0]), float(coords_part[1]), float(coords_part[2])]

        if start is None:
            start = (kpt, label)
        else:
            path.append({
                "start": start[0],
                "end": kpt,
                "start_label": start[1],
                "end_label": label,
            })
            start = None

    return {
        "mode": "line",
        "npoints": npoints,
        "coord_type": coord_type,
        "path": path,
    }


def _parse_explicit(
    lines: list[str], nkpts: int, mode_line: str
) -> dict[str, Any]:
    """Parse explicit k-points."""
    ct = mode_line.strip().lower()
    if ct.startswith("c") or ct.startswith("k"):
        coord_type = "cartesian"
    else:
        coord_type = "reciprocal"

    kpoints: list[list[float]] = []
    for i in range(3, min(3 + nkpts, len(lines))):
        parts = lines[i].split("!")[0].strip().split()
        if len(parts) >= 4:
            kpoints.append([float(parts[j]) for j in range(4)])
        elif len(parts) == 3:
            kpoints.append([float(parts[j]) for j in range(3)] + [1.0])

    return {
        "mode": "explicit",
        "coord_type": coord_type,
        "kpoints": kpoints,
    }
