"""LAMMPS engine input specification for the universal writer/parser.

Two input files: in.lammps (parameters/commands) and structure.data (structure).
LAMMPS uses a command-stream syntax (F5): imperative, order-matters, positional args.

The parsed params dict carries a dual representation:
  - Flat semantic fields (units, pair_style, fixes, etc.) for SSOT queries
  - _commands list preserving the full command stream for faithful write-back
"""

from __future__ import annotations

import re
from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


# ---------------------------------------------------------------------------
# Number parsing helper
# ---------------------------------------------------------------------------

def _parse_number(s: str) -> int | float | str:
    """Try to parse a string as int, then float, else return as-is."""
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


# ---------------------------------------------------------------------------
# Script parser (Stage 4A)
# ---------------------------------------------------------------------------

# Commands whose flat value is last-wins scalar (args joined as string)
_SCALAR_COMMANDS = frozenset({
    "units", "atom_style", "dimension", "boundary",
    "pair_style", "bond_style", "angle_style", "dihedral_style",
    "improper_style", "kspace_style", "special_bonds",
    "neighbor", "neigh_modify", "thermo_style", "thermo_modify",
    "lattice", "velocity",
})

# Commands whose flat value is a number (last-wins)
_NUMBER_COMMANDS = frozenset({
    "thermo", "timestep",
})

# Commands that accumulate into a list (args joined as string)
_LIST_COMMANDS = frozenset({
    "pair_coeff", "bond_coeff", "angle_coeff",
    "dihedral_coeff", "improper_coeff", "mass",
})


def _parse_lammps_script_text(text: str) -> dict[str, Any]:
    """Parse LAMMPS input script text into params dict.

    Returns a dict with:
      - Flat semantic fields for key commands
      - _commands: list of {cmd, args} preserving order
      - _variables: dict of variable definitions
      - _includes: list of included filenames
    """
    if not text or not text.strip():
        return {"_commands": [], "_variables": {}, "_includes": []}

    # Step 1: Join continuation lines (& at end)
    joined = _join_continuation_lines(text)

    # Step 2-4: Parse line by line
    commands: list[dict[str, Any]] = []
    variables: dict[str, str] = {}
    includes: list[str] = []
    params: dict[str, Any] = {}

    # Accumulating lists
    pair_coeffs: list[str] = []
    bond_coeffs: list[str] = []
    angle_coeffs: list[str] = []
    dihedral_coeffs: list[str] = []
    improper_coeffs: list[str] = []
    masses: list[str] = []
    fixes: list[dict[str, str]] = []
    computes: list[dict[str, str]] = []

    for line in joined.splitlines():
        # Strip comments (# to end of line)
        comment_pos = line.find("#")
        if comment_pos >= 0:
            line = line[:comment_pos]

        stripped = line.strip()
        if not stripped:
            continue

        # Tokenize: split on whitespace
        tokens = stripped.split()
        cmd = tokens[0]
        args = tokens[1:]

        # Record command in stream
        commands.append({"cmd": cmd, "args": list(args)})

        # --- Flat extraction ---

        # variable definitions
        if cmd == "variable" and len(args) >= 2:
            var_name = args[0]
            variables[var_name] = " ".join(args[1:])
            continue

        # include directives
        if cmd == "include" and args:
            includes.append(args[0])
            continue

        # Scalar commands (last-wins, args joined)
        if cmd in _SCALAR_COMMANDS:
            if cmd == "dimension" and args:
                params[cmd] = _parse_number(args[0])
            elif cmd == "boundary" and len(args) >= 3:
                params[cmd] = " ".join(args[:3])
            else:
                params[cmd] = " ".join(args)
            continue

        # Number commands (last-wins, first arg as number)
        if cmd in _NUMBER_COMMANDS and args:
            params[cmd] = _parse_number(args[0])
            continue

        # List-accumulating commands
        if cmd == "pair_coeff":
            pair_coeffs.append(" ".join(args))
            continue
        if cmd == "bond_coeff":
            bond_coeffs.append(" ".join(args))
            continue
        if cmd == "angle_coeff":
            angle_coeffs.append(" ".join(args))
            continue
        if cmd == "dihedral_coeff":
            dihedral_coeffs.append(" ".join(args))
            continue
        if cmd == "improper_coeff":
            improper_coeffs.append(" ".join(args))
            continue
        if cmd == "mass":
            masses.append(" ".join(args))
            continue

        # fix: id group style args...
        if cmd == "fix" and len(args) >= 3:
            fixes.append({
                "fix_id": args[0],
                "group": args[1],
                "style": args[2],
                "args": " ".join(args[3:]),
            })
            continue

        # unfix: remove by fix_id (update fixes list)
        if cmd == "unfix" and args:
            target = args[0]
            fixes = [f for f in fixes if f["fix_id"] != target]
            continue

        # compute: compute_id group style args...
        if cmd == "compute" and len(args) >= 3:
            computes.append({
                "compute_id": args[0],
                "group": args[1],
                "style": args[2],
                "args": " ".join(args[3:]),
            })
            continue

        # uncompute: remove by compute_id
        if cmd == "uncompute" and args:
            target = args[0]
            computes = [c for c in computes if c["compute_id"] != target]
            continue

        # run / minimize (last-wins)
        if cmd == "run" and args:
            params["run"] = _parse_number(args[0])
            continue
        if cmd == "minimize":
            params["minimize"] = " ".join(args)
            continue
        if cmd == "min_style" and args:
            params["min_style"] = args[0]
            continue

        # read_data / read_restart
        if cmd == "read_data" and args:
            params["data_file"] = args[0]
            continue
        if cmd == "read_restart" and args:
            params["restart_file"] = args[0]
            continue

    # Assign accumulated lists
    if pair_coeffs:
        params["pair_coeff"] = pair_coeffs
    if bond_coeffs:
        params["bond_coeff"] = bond_coeffs
    if angle_coeffs:
        params["angle_coeff"] = angle_coeffs
    if dihedral_coeffs:
        params["dihedral_coeff"] = dihedral_coeffs
    if improper_coeffs:
        params["improper_coeff"] = improper_coeffs
    if masses:
        params["masses"] = masses
    if fixes:
        params["fixes"] = fixes
    if computes:
        params["computes"] = computes

    # Internal metadata
    params["_commands"] = commands
    params["_variables"] = variables
    params["_includes"] = includes

    return params


def _join_continuation_lines(text: str) -> str:
    """Join lines ending with & (LAMMPS line continuation)."""
    result_lines: list[str] = []
    buffer = ""
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.endswith("&"):
            # Remove the & and accumulate
            buffer += stripped[:-1] + " "
        else:
            if buffer:
                buffer += stripped
                result_lines.append(buffer)
                buffer = ""
            else:
                result_lines.append(line)
    # Flush any remaining buffer
    if buffer:
        result_lines.append(buffer)
    return "\n".join(result_lines)


# ---------------------------------------------------------------------------
# Data file parser (Stage 4B)
# ---------------------------------------------------------------------------

def _parse_lammps_data_text(text: str) -> dict[str, Any]:
    """Parse LAMMPS data file text into a structure dict.

    Returns a StructureDoc-compatible dict with:
      lattice, species, frac_coords, cart_coords, comment,
      _masses, _n_types, _n_atoms
    """
    if not text or not text.strip():
        return {}

    lines = text.splitlines()
    comment = ""
    n_atoms = 0
    n_types = 0
    xlo, xhi = 0.0, 0.0
    ylo, yhi = 0.0, 0.0
    zlo, zhi = 0.0, 0.0
    xy, xz, yz = 0.0, 0.0, 0.0
    has_tilt = False
    masses: dict[int, float] = {}
    atoms_raw: list[list[str]] = []

    # Track current section
    section = "header"
    i = 0

    # First non-blank non-comment line is the comment/title
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            comment = stripped
            break
        if stripped.startswith("#"):
            comment = stripped.lstrip("# ")
            break

    while i < len(lines):
        line = lines[i].strip()

        # Empty line or comment in header
        if not line:
            i += 1
            continue

        # --- Header parsing ---
        if section == "header":
            # N atoms
            m = re.match(r"(\d+)\s+atoms\b", line)
            if m:
                n_atoms = int(m.group(1))
                i += 1
                continue
            # N atom types
            m = re.match(r"(\d+)\s+atom types\b", line)
            if m:
                n_types = int(m.group(1))
                i += 1
                continue
            # xlo xhi
            m = re.match(
                r"([\d.eE+-]+)\s+([\d.eE+-]+)\s+xlo\s+xhi", line
            )
            if m:
                xlo, xhi = float(m.group(1)), float(m.group(2))
                i += 1
                continue
            # ylo yhi
            m = re.match(
                r"([\d.eE+-]+)\s+([\d.eE+-]+)\s+ylo\s+yhi", line
            )
            if m:
                ylo, yhi = float(m.group(1)), float(m.group(2))
                i += 1
                continue
            # zlo zhi
            m = re.match(
                r"([\d.eE+-]+)\s+([\d.eE+-]+)\s+zlo\s+zhi", line
            )
            if m:
                zlo, zhi = float(m.group(1)), float(m.group(2))
                i += 1
                continue
            # xy xz yz tilt factors
            m = re.match(
                r"([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+xy\s+xz\s+yz",
                line,
            )
            if m:
                xy = float(m.group(1))
                xz = float(m.group(2))
                yz = float(m.group(3))
                has_tilt = True
                i += 1
                continue

        # --- Section headers ---
        if line == "Masses":
            section = "masses"
            i += 1
            continue
        if line.startswith("Atoms"):
            section = "atoms"
            i += 1
            continue
        # Other sections we skip
        if line in (
            "Velocities", "Bonds", "Angles", "Dihedrals", "Impropers",
            "Pair Coeffs", "Bond Coeffs", "Angle Coeffs",
            "Dihedral Coeffs", "Improper Coeffs",
        ):
            section = "skip"
            i += 1
            continue

        # --- Masses section ---
        if section == "masses":
            parts = line.split()
            if len(parts) >= 2:
                try:
                    type_id = int(parts[0])
                    mass_val = float(parts[1])
                    masses[type_id] = mass_val
                except ValueError:
                    # Not a mass line; must be a new section header
                    section = "header"
                    continue
            i += 1
            continue

        # --- Atoms section ---
        if section == "atoms":
            # Skip comment lines within Atoms
            if line.startswith("#"):
                i += 1
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    int(parts[0])  # atom ID check
                    atoms_raw.append(parts)
                except ValueError:
                    # New section header
                    section = "header"
                    continue
            i += 1
            continue

        # --- Skip section ---
        if section == "skip":
            parts = line.split()
            if parts:
                try:
                    int(parts[0])
                    i += 1
                    continue
                except ValueError:
                    section = "header"
                    continue

        i += 1

    # Build lattice from box bounds
    lx = xhi - xlo
    ly = yhi - ylo
    lz = zhi - zlo
    if has_tilt:
        lattice = [[lx, 0.0, 0.0], [xy, ly, 0.0], [xz, yz, lz]]
    else:
        lattice = [[lx, 0.0, 0.0], [0.0, ly, 0.0], [0.0, 0.0, lz]]

    # Parse atom coordinates
    species: list[str] = []
    cart_coords: list[list[float]] = []

    for parts in atoms_raw:
        ncols = len(parts)
        if ncols >= 5:
            # Determine format: atomic (5), charge (6), full (7+)
            if ncols == 5:
                # id type x y z
                type_id = parts[1]
                x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
            elif ncols == 6:
                # id type q x y z
                type_id = parts[1]
                x, y, z = float(parts[3]), float(parts[4]), float(parts[5])
            else:
                # id mol type q x y z (full style, 7+ cols)
                type_id = parts[2]
                x, y, z = float(parts[4]), float(parts[5]), float(parts[6])
            species.append(type_id)
            cart_coords.append([x, y, z])

    # Compute fractional coordinates (Cartesian -> fractional via lattice inverse)
    frac_coords: list[list[float]] = []
    if lattice and cart_coords:
        frac_coords = _cart_to_frac(cart_coords, lattice)

    result: dict[str, Any] = {
        "comment": comment,
    }
    if lattice and any(v != 0 for row in lattice for v in row):
        result["lattice"] = lattice
    if species:
        result["species"] = species
    if frac_coords:
        result["frac_coords"] = frac_coords
    if cart_coords:
        result["cart_coords"] = cart_coords
    if masses:
        result["_masses"] = masses
    if n_types:
        result["_n_types"] = n_types

    return result


def _cart_to_frac(
    cart_coords: list[list[float]], lattice: list[list[float]]
) -> list[list[float]]:
    """Convert Cartesian to fractional coordinates via 3x3 lattice inverse."""
    # Lattice matrix L where rows are lattice vectors
    a = lattice[0]
    b = lattice[1]
    c = lattice[2]

    # Determinant
    det = (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )
    if abs(det) < 1e-30:
        return [[0.0, 0.0, 0.0]] * len(cart_coords)

    inv_det = 1.0 / det

    # Inverse matrix (transposed cofactors / det)
    inv = [
        [
            (b[1] * c[2] - b[2] * c[1]) * inv_det,
            (a[2] * c[1] - a[1] * c[2]) * inv_det,
            (a[1] * b[2] - a[2] * b[1]) * inv_det,
        ],
        [
            (b[2] * c[0] - b[0] * c[2]) * inv_det,
            (a[0] * c[2] - a[2] * c[0]) * inv_det,
            (a[2] * b[0] - a[0] * b[2]) * inv_det,
        ],
        [
            (b[0] * c[1] - b[1] * c[0]) * inv_det,
            (a[1] * c[0] - a[0] * c[1]) * inv_det,
            (a[0] * b[1] - a[1] * b[0]) * inv_det,
        ],
    ]

    fracs = []
    for xyz in cart_coords:
        fx = inv[0][0] * xyz[0] + inv[0][1] * xyz[1] + inv[0][2] * xyz[2]
        fy = inv[1][0] * xyz[0] + inv[1][1] * xyz[1] + inv[1][2] * xyz[2]
        fz = inv[2][0] * xyz[0] + inv[2][1] * xyz[1] + inv[2][2] * xyz[2]
        fracs.append([fx, fy, fz])

    return fracs


# ---------------------------------------------------------------------------
# Writer (Stage 4C) — enhanced with stream mode
# ---------------------------------------------------------------------------

def _write_lammps_script_text(params: dict[str, Any] | None) -> str:
    """Write LAMMPS input script text from parameters.

    Two modes:
      - Stream mode: if _commands is present, emit commands in order.
      - Template mode: generate from flat fields (existing behavior).
    """
    if not params:
        return ""

    if "_commands" in params:
        return _write_from_commands(params)

    return _write_from_flat(params)


def _write_from_commands(params: dict[str, Any]) -> str:
    """Emit LAMMPS input from the _commands list (faithful write-back)."""
    commands = params.get("_commands", [])
    if not commands:
        return ""

    lines: list[str] = []
    for entry in commands:
        cmd = entry["cmd"]
        args = entry.get("args", [])
        if args:
            lines.append(f"{cmd}\t\t{' '.join(str(a) for a in args)}")
        else:
            lines.append(cmd)

    return "\n".join(lines) + "\n"


def _write_from_flat(params: dict[str, Any]) -> str:
    """Generate LAMMPS input script from flat parameter fields."""
    lines: list[str] = []
    lines.append("# LAMMPS input script")
    lines.append("# Generated by QMatSuite")
    lines.append("")

    # Units and dimensions
    lines.append(f"units           {params.get('units', 'metal')}")
    if "dimension" in params:
        lines.append(f"dimension       {params['dimension']}")
    lines.append(f"atom_style      {params.get('atom_style', 'atomic')}")
    lines.append(f"boundary        {params.get('boundary', 'p p p')}")
    lines.append("")

    # Lattice / geometry (if inline)
    if "lattice" in params:
        lines.append(f"lattice         {params['lattice']}")

    # Read data / restart
    if "restart_file" in params:
        lines.append(f"read_restart    {params['restart_file']}")
    elif "data_file" in params:
        lines.append(f"read_data       {params['data_file']}")
    else:
        lines.append(f"read_data       structure.data")
    lines.append("")

    # Masses
    for mass_str in params.get("masses", []):
        lines.append(f"mass            {mass_str}")
    if params.get("masses"):
        lines.append("")

    # Pair style
    pair_style = params.get("pair_style", "")
    if pair_style:
        lines.append(f"pair_style      {pair_style}")
        pair_coeffs = params.get("pair_coeff", [])
        if isinstance(pair_coeffs, str):
            pair_coeffs = [pair_coeffs]
        for pc in pair_coeffs:
            lines.append(f"pair_coeff      {pc}")
        lines.append("")

    # Bonded styles
    for style_cmd in ("bond_style", "angle_style", "dihedral_style", "improper_style"):
        if style_cmd in params:
            lines.append(f"{style_cmd:16s}{params[style_cmd]}")
    for coeff_cmd in ("bond_coeff", "angle_coeff", "dihedral_coeff", "improper_coeff"):
        for cv in params.get(coeff_cmd, []):
            lines.append(f"{coeff_cmd:16s}{cv}")

    # Kspace
    if "kspace_style" in params:
        lines.append(f"kspace_style    {params['kspace_style']}")

    # Special bonds
    if "special_bonds" in params:
        lines.append(f"special_bonds   {params['special_bonds']}")

    # Neighbor
    if "neighbor" in params:
        lines.append(f"neighbor        {params['neighbor']}")
    if "neigh_modify" in params:
        lines.append(f"neigh_modify    {params['neigh_modify']}")
    lines.append("")

    # Velocity
    if "velocity" in params:
        lines.append(f"velocity        {params['velocity']}")
        lines.append("")

    # Fixes
    for fix in params.get("fixes", []):
        fix_line = f"fix             {fix['fix_id']} {fix['group']} {fix['style']}"
        if fix.get("args"):
            fix_line += f" {fix['args']}"
        lines.append(fix_line)

    # Computes
    for comp in params.get("computes", []):
        comp_line = f"compute         {comp['compute_id']} {comp['group']} {comp['style']}"
        if comp.get("args"):
            comp_line += f" {comp['args']}"
        lines.append(comp_line)

    lines.append("")

    # Output
    if "thermo_style" in params:
        lines.append(f"thermo_style    {params['thermo_style']}")
    if "thermo_modify" in params:
        lines.append(f"thermo_modify   {params['thermo_modify']}")
    if "thermo" in params:
        lines.append(f"thermo          {params['thermo']}")

    # Timestep
    if "timestep" in params:
        lines.append(f"timestep        {params['timestep']}")

    # Run / minimize
    if "min_style" in params:
        lines.append(f"min_style       {params['min_style']}")
    if "minimize" in params:
        lines.append(f"minimize        {params['minimize']}")
    elif "run" in params:
        lines.append(f"run             {params['run']}")

    return "\n".join(lines) + "\n"


def _write_lammps_data_text(structure: dict[str, Any] | None) -> str:
    """Write LAMMPS data file text from structure dict.

    Generates a basic LAMMPS data file in 'atomic' style.
    """
    if not structure:
        return ""

    species = structure.get("species", [])
    frac_coords = structure.get("frac_coords", [])
    cart_coords = structure.get("cart_coords", [])
    lattice = structure.get("lattice", [])
    comment = structure.get("comment", "LAMMPS data file")

    unique_species: list[str] = []
    for sp in species:
        if sp not in unique_species:
            unique_species.append(sp)

    n_atoms = len(species)
    n_types = len(unique_species)

    lines: list[str] = []
    lines.append(f"# {comment}")
    lines.append("")
    lines.append(f"{n_atoms} atoms")
    lines.append(f"{n_types} atom types")
    lines.append("")

    # Box bounds
    if lattice:
        ax = lattice[0][0]
        by = lattice[1][1]
        cz = lattice[2][2]
        bx = lattice[1][0]
        cx = lattice[2][0]
        cy = lattice[2][1]
        lines.append(f"0.0 {ax:.10f} xlo xhi")
        lines.append(f"0.0 {by:.10f} ylo yhi")
        lines.append(f"0.0 {cz:.10f} zlo zhi")
        if abs(bx) > 1e-10 or abs(cx) > 1e-10 or abs(cy) > 1e-10:
            lines.append(f"{bx:.10f} {cx:.10f} {cy:.10f} xy xz yz")
    lines.append("")

    # Masses (if available)
    mass_map = structure.get("_masses", {})
    if mass_map:
        lines.append("Masses")
        lines.append("")
        for tid in sorted(mass_map.keys()):
            lines.append(f"{tid} {mass_map[tid]}")
        lines.append("")

    # Atoms section (atomic style: id type x y z)
    lines.append("Atoms")
    lines.append("")

    # Prefer cart_coords if available; otherwise convert from frac_coords
    if cart_coords:
        for i, (sym, cc) in enumerate(zip(species, cart_coords), 1):
            type_id = unique_species.index(sym) + 1
            lines.append(
                f"{i} {type_id} {cc[0]:.10f} {cc[1]:.10f} {cc[2]:.10f}"
            )
    elif frac_coords and lattice:
        for i, (sym, fc) in enumerate(zip(species, frac_coords), 1):
            type_id = unique_species.index(sym) + 1
            x = (
                fc[0] * lattice[0][0]
                + fc[1] * lattice[1][0]
                + fc[2] * lattice[2][0]
            )
            y = (
                fc[0] * lattice[0][1]
                + fc[1] * lattice[1][1]
                + fc[2] * lattice[2][1]
            )
            z = (
                fc[0] * lattice[0][2]
                + fc[1] * lattice[1][2]
                + fc[2] * lattice[2][2]
            )
            lines.append(f"{i} {type_id} {x:.10f} {y:.10f} {z:.10f}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# EngineInputSpec (Stage 4D) — wired with parsers
# ---------------------------------------------------------------------------

def get_lammps_input_spec(**context: Any) -> EngineInputSpec:
    """Return the LAMMPS EngineInputSpec."""
    return EngineInputSpec(
        engine_family="lammps",
        syntax_family="command-stream",
        input_files=(
            InputFileSpec(
                filename="in.lammps",
                content_role="parameters",
                description="LAMMPS input script",
                custom_writer=_write_lammps_script_text,
                custom_parser=_parse_lammps_script_text,
            ),
            InputFileSpec(
                filename="structure.data",
                content_role="structure",
                description="LAMMPS data file (atomic positions)",
                custom_writer=_write_lammps_data_text,
                custom_parser=_parse_lammps_data_text,
                optional=True,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="potentials",
                description="Force-field potential files (.eam, .tersoff, etc.)",
                staging_policy="copy",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("structure.data",),
            params_in=("in.lammps",),
        ),
    )
