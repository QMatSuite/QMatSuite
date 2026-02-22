"""LAMMPS input script parser and writer.

Pure stdlib module — no kernel imports. Handles the command-stream
(F5) syntax: imperative, order-matters, positional arguments.

Parsed params dict carries a dual representation:
  - Flat semantic fields (units, pair_style, fixes, etc.) for SSOT queries
  - _commands list preserving the full command stream for faithful write-back
"""

from __future__ import annotations

from typing import Any


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
# Script parser
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


def parse_lammps_script_text(text: str) -> dict[str, Any]:
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
    joined = join_continuation_lines(text)

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


def join_continuation_lines(text: str) -> str:
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
# Writer — enhanced with stream mode
# ---------------------------------------------------------------------------

def write_lammps_script_text(params: dict[str, Any] | None) -> str:
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
