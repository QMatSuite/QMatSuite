"""Gaussian .gjf input file parser and writer.

Pure-function module with no kernel dependencies. Stdlib only.

Handles:
- Link0 commands (%mem, %nproc, %chk)
- Route section (#p method/basis keywords)
- Title section
- Charge/multiplicity
- Cartesian and Z-matrix geometry
- Parenthetical options: Opt=(Tight,MaxCycles=100), TD=(NStates=3)
- SCRF solvation: SCRF=(SMD,Solvent=Water)
- Blank-line-delimited section structure
- Link1 multi-job (--Link1-- separator)
"""

from __future__ import annotations

import re
from typing import Any


# Known method names (case-insensitive matching via upper())
_METHODS = frozenset([
    "HF", "B3LYP", "PBE0", "PBE1PBE", "M06-2X", "M062X", "WB97XD",
    "LC-WPBE", "CAM-B3LYP", "HSE06", "HSEHPBE", "BLYP", "PBE", "PBEPBE",
    "BP86", "TPSS", "TPSSTPSS", "LSDA", "B2PLYP", "B2PLYPD", "B2PLYPD3",
    "MPW2PLYP", "MP2", "MP3", "MP4", "MP5", "CCD", "CCSD", "CCSD(T)",
    "QCISD", "QCISD(T)", "BD", "BD(T)", "CID", "CISD", "CIS", "CIS(D)",
    "CASSCF", "GVB", "SAC-CI", "EOMCCSD", "AM1", "PM3", "PM6", "PM7",
    "MNDO", "MINDO3", "CNDO", "INDO", "ZINDO", "EXTENDEDHUCKEL", "HUCKEL",
    "DFTB", "DFTBA", "AMBER", "DREIDING", "UFF",
    "M06", "M06-L", "M06L", "M06-HF", "M06HF", "WB97X",
    "B3PW91", "MPW1PW91", "B97D", "B97D3", "N12", "MN12-L", "MN12L",
])

# Known basis set patterns
_BASIS_PATTERNS = frozenset([
    "STO-3G", "3-21G", "6-21G", "4-31G",
    "LANL2DZ", "LANL2MB", "SDD", "DGDZVP", "DGDZVP2",
    "CEP-4G", "CEP-31G", "CEP-121G", "GEN", "GENECP", "CHKBASIS",
    "D95", "D95V", "SHC",
])

_BASIS_PREFIXES = ("6-31", "6-311", "CC-PV", "AUG-CC-PV", "DEF2-")


def _is_basis_set(token: str) -> bool:
    """Check if token looks like a basis set name."""
    upper = token.upper().rstrip("*")
    if upper in _BASIS_PATTERNS:
        return True
    for prefix in _BASIS_PREFIXES:
        if upper.startswith(prefix):
            return True
    return False


def _is_method(token: str) -> bool:
    """Check if token is a known method (with optional R/U/RO prefix)."""
    upper = token.upper()
    if upper in _METHODS:
        return True
    # Strip R/U/RO prefix
    for prefix in ("RO", "R", "U"):
        if upper.startswith(prefix) and upper[len(prefix):] in _METHODS:
            return True
    return False


def parse_route_keywords(route_text: str) -> dict[str, Any]:
    """Parse route section text into structured params.

    Handles:
    - method/basis (e.g., "B3LYP/6-31G*")
    - Parenthetical options: Opt=(Tight,MaxCycles=100), TD=(NStates=3)
    - SCRF=(SMD,Solvent=Water)
    - Standalone keywords: Freq, NMR, Scan, etc.
    """
    params: dict[str, Any] = {}
    extra_route: list[str] = []

    # Remove # prefix and verbosity flags
    route_text = re.sub(r"^#[pPnNtT]?\s*", "", route_text.strip())

    # Tokenize: split by whitespace but keep parenthetical groups together
    tokens = re.findall(r"[^\s]+(?:\([^)]*\))?", route_text)

    for tok in tokens:
        # Method/basis combo: B3LYP/6-31G*
        if "/" in tok and "=" not in tok.split("/")[0]:
            parts = tok.split("/", 1)
            if _is_method(parts[0]):
                params["method"] = parts[0]
                params["basis"] = parts[1]
                continue

        # Extract base keyword and options
        base = tok.split("(")[0].split("=")[0]
        base_upper = base.upper()

        # Job type keywords with options
        if base_upper == "OPT":
            if "(" in tok:
                opts_str = tok[tok.index("(") + 1 : tok.rindex(")")]
                opt_opts = [o.strip() for o in opts_str.split(",")]
                for opt in opt_opts:
                    if opt.upper() == "TIGHT":
                        params["opt_tight"] = True
                    elif "=" in opt:
                        k, v = opt.split("=", 1)
                        params[f"opt_{k.lower()}"] = v
                    else:
                        params.setdefault("opt_options", []).append(opt)
            elif "=" in tok:
                # Handle Opt=Tight (without parentheses)
                val = tok.split("=", 1)[1]
                if val.upper() == "TIGHT":
                    params["opt_tight"] = True
                else:
                    params[f"opt_{val.lower()}"] = True
            params["gen_type"] = "relax"
            continue

        if base_upper == "FREQ":
            if "gen_type" not in params:
                params["gen_type"] = "freq"
            else:
                # Combined Opt Freq
                params["gen_type"] = "relax"
                params["freq"] = True
            continue

        if base_upper == "TD":
            params["gen_type"] = "td"
            if "(" in tok:
                opts_str = tok[tok.index("(") + 1 : tok.rindex(")")]
                for opt in opts_str.split(","):
                    opt = opt.strip()
                    if "=" in opt:
                        k, v = opt.split("=", 1)
                        if k.upper() == "NSTATES":
                            params["td_nstates"] = int(v)
                        else:
                            params[f"td_{k.lower()}"] = v
            continue

        if base_upper == "SCRF":
            if "(" in tok:
                opts_str = tok[tok.index("(") + 1 : tok.rindex(")")]
                for opt in opts_str.split(","):
                    opt = opt.strip()
                    if "=" in opt:
                        k, v = opt.split("=", 1)
                        params[f"scrf_{k.lower()}"] = v
                    else:
                        params["scrf_model"] = opt
            continue

        if base_upper == "SCF":
            if "(" in tok:
                opts_str = tok[tok.index("(") + 1 : tok.rindex(")")]
                for opt in opts_str.split(","):
                    opt = opt.strip()
                    if "=" in opt:
                        k, v = opt.split("=", 1)
                        params[f"scf_{k.lower()}"] = v
                    else:
                        params.setdefault("scf_options", []).append(opt)
            continue

        if base_upper in ("SCAN", "NMR", "STABLE", "FORCE", "VOLUME",
                          "IRC", "ADMP", "BOMD", "POLAR"):
            params["gen_type"] = base.lower()
            if "(" in tok:
                opts_str = tok[tok.index("(") + 1 : tok.rindex(")")]
                for opt in opts_str.split(","):
                    opt = opt.strip()
                    if "=" in opt:
                        k, v = opt.split("=", 1)
                        params[f"{base.lower()}_{k.lower()}"] = v
            continue

        if base_upper == "EMPIRICALDISPERSION":
            if "(" in tok or "=" in tok:
                val = tok.split("=", 1)[1] if "=" in tok else tok[tok.index("(") + 1 : tok.rindex(")")]
                params["dispersion"] = val
            continue

        if base_upper in ("NOSYMM", "SYMMETRY"):
            params["nosymm"] = base_upper == "NOSYMM"
            continue

        if base_upper == "INTEGRAL":
            if "(" in tok:
                opts_str = tok[tok.index("(") + 1 : tok.rindex(")")]
                params["integral_grid"] = opts_str
            elif "=" in tok:
                params["integral_grid"] = tok.split("=", 1)[1]
            continue

        # Composite methods
        if base_upper in ("G1", "G2", "G2MP2", "G3", "G3MP2", "G3B3",
                          "G3MP2B3", "G4", "G4MP2", "CBS-QB3", "CBS-4M",
                          "CBS-APNO", "W1U", "W1BD", "W1RO"):
            params["method"] = base
            params["gen_type"] = "composite"
            continue

        # Standalone method (no basis required for semi-empirical/MM)
        if _is_method(tok):
            params["method"] = tok
            continue

        # Standalone basis set
        if _is_basis_set(tok):
            params["basis"] = tok
            continue

        # Everything else: extra route keyword
        extra_route.append(tok)

    if extra_route:
        params["extra_route"] = extra_route

    return params


def _parse_geometry(
    geom_lines: list[str],
    species: list[str],
    cart_coords: list[list[float]],
    params: dict[str, Any],
) -> None:
    """Parse geometry lines (Cartesian or Z-matrix).

    Populates species and cart_coords lists in-place.
    For Z-matrix, sets params["zmatrix"] to the raw Z-matrix data.
    """
    if not geom_lines:
        return

    # Detect format: Cartesian has 4 columns (element x y z),
    # Z-matrix has variable column count
    first_parts = geom_lines[0].split()

    is_cartesian = False
    if len(first_parts) >= 4:
        # Try to parse as Cartesian: Element X Y Z
        try:
            float(first_parts[1])
            float(first_parts[2])
            float(first_parts[3])
            is_cartesian = True
        except (ValueError, IndexError):
            pass

    if is_cartesian:
        for line in geom_lines:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    species.append(parts[0])
                    cart_coords.append([
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3]),
                    ])
                except ValueError:
                    continue
    else:
        # Z-matrix format
        zmatrix_entries: list[dict[str, Any]] = []
        for line in geom_lines:
            parts = line.split()
            if not parts:
                continue
            elem = parts[0]
            species.append(elem)
            entry: dict[str, Any] = {"element": elem}
            if len(parts) >= 3:
                entry["bond_atom"] = parts[1]
                entry["bond_length"] = parts[2]
            if len(parts) >= 5:
                entry["angle_atom"] = parts[3]
                entry["angle"] = parts[4]
            if len(parts) >= 7:
                entry["dihedral_atom"] = parts[5]
                entry["dihedral"] = parts[6]
            zmatrix_entries.append(entry)

        params["zmatrix"] = zmatrix_entries
        # For Z-matrix, cart_coords stays empty (not converted)
        # since that requires trigonometric evaluation


def parse_gaussian_text(text: str) -> dict[str, Any]:
    """Parse Gaussian .gjf input text into combined params + structure dict.

    Handles the full Gaussian input format:
    - Link0 commands (%mem, %nproc, %chk)
    - Route section (# prefix, can span multiple lines)
    - Title section (free text)
    - Charge/multiplicity line
    - Cartesian coordinates
    - Z-matrix with variables
    - Blank-line section delimiters
    - Link1 multi-job (--Link1-- separator) -- parses first job only

    Returns:
        {"params": {...}, "structure": {"species": [...], "cart_coords": [...]}}
    """
    params: dict[str, Any] = {}
    species: list[str] = []
    cart_coords: list[list[float]] = []

    # Split on Link1 separator — only parse first job
    jobs = re.split(r"^--Link1--\s*$", text, flags=re.MULTILINE)
    first_job = jobs[0]
    if len(jobs) > 1:
        params["link1_jobs"] = len(jobs)

    lines = first_job.splitlines()

    # Phase 1: Extract Link0 commands (% prefix lines at top)
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("%"):
            key_val = line[1:]
            if "=" in key_val:
                key, val = key_val.split("=", 1)
                key_lower = key.lower().strip()
                val = val.strip()
                if key_lower in ("mem",):
                    params["mem"] = val
                elif key_lower in ("nproc", "nprocshared"):
                    params["nproc"] = int(val) if val.isdigit() else val
                elif key_lower == "chk":
                    params["chk_name"] = val
                elif key_lower == "oldchk":
                    params["oldchk"] = val
                elif key_lower == "rwf":
                    params["rwf"] = val
                else:
                    params[f"link0_{key_lower}"] = val
            else:
                # Valueless Link0 like %Save, %NoSave
                params[f"link0_{key_val.lower().strip()}"] = True
            i += 1
            continue
        break  # First non-blank, non-% line = start of route

    # Phase 2: Route section (starts with #, can span multiple lines until blank)
    route_lines: list[str] = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            break  # Blank line terminates route
        route_lines.append(stripped)
        i += 1

    if route_lines:
        route_text = " ".join(route_lines)
        route_params = parse_route_keywords(route_text)
        params.update(route_params)

    # Phase 3: Title section (until blank line)
    title_lines: list[str] = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            break
        title_lines.append(stripped)
        i += 1

    if title_lines:
        params["title"] = " ".join(title_lines)

    # Phase 4: Charge/multiplicity line
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                params["charge"] = int(parts[0])
                params["multiplicity"] = int(parts[1])
            except ValueError:
                pass
        i += 1
        break

    # Phase 5: Geometry section (until blank line)
    # Could be Cartesian or Z-matrix
    geom_lines: list[str] = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            break
        geom_lines.append(stripped)
        i += 1

    if geom_lines:
        _parse_geometry(geom_lines, species, cart_coords, params)

    # Phase 6: Z-matrix variables (if Z-matrix was used)
    if "zmatrix" in params:
        var_lines: list[str] = []
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                i += 1
                break
            var_lines.append(stripped)
            i += 1
        if var_lines:
            zmat_vars = {}
            for vl in var_lines:
                if "=" in vl:
                    vname, vval = vl.split("=", 1)
                    vname = vname.strip()
                    vval_parts = vval.strip().split()
                    try:
                        zmat_vars[vname] = float(vval_parts[0])
                    except (ValueError, IndexError):
                        zmat_vars[vname] = vval.strip()
                    # Scan specification: R1=1.07 5 0.05
                    if len(vval_parts) == 3:
                        try:
                            zmat_vars[f"{vname}_scan_steps"] = int(vval_parts[1])
                            zmat_vars[f"{vname}_scan_step_size"] = float(vval_parts[2])
                        except ValueError:
                            pass
            params["zmatrix_variables"] = zmat_vars

    # Build structure
    structure: dict[str, Any] = {}
    if species:
        structure["species"] = species
        structure["cart_coords"] = cart_coords

    return {"params": params, "structure": structure}


def write_gaussian_text(fragment: dict[str, Any]) -> str:
    """Write Gaussian .gjf text from combined params + structure.

    Pure-function writer. Generates a minimal Gaussian input file
    from SSOT data without requiring pymatgen at write time.

    Args:
        fragment: {"params": {...}, "structure": {...}} where structure
            has lattice/species/frac_coords (or cart_coords).
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    method = params.get("method", "HF")
    basis = params.get("basis", "STO-3G")
    charge = params.get("charge", 0)
    multiplicity = params.get("multiplicity", 1)
    mem = params.get("mem", "500MB")
    nproc = params.get("nproc", 1)
    gen_type = params.get("gen_type", "scf")
    title = params.get("title", "Gaussian calculation")
    td_nstates = params.get("td_nstates", 3)
    opt_tight = params.get("opt_tight", False)
    chk_name = params.get("chk_name", "calc.chk")

    lines: list[str] = []

    # Link0 commands
    lines.append(f"%mem={mem}")
    lines.append(f"%nproc={nproc}")
    lines.append(f"%chk={chk_name}")

    # Route line
    route = f"#p {method}/{basis}"
    if gen_type == "relax":
        route += " Opt=Tight" if opt_tight else " Opt"
    elif gen_type == "freq":
        route += " Freq"
    elif gen_type == "td":
        route += f" TD=(NStates={td_nstates})"

    # Append extra route keywords if present
    extra_route = params.get("extra_route", [])
    if extra_route:
        route += " " + " ".join(extra_route)

    lines.append(route)
    lines.append("")
    lines.append(title)
    lines.append("")
    lines.append(f"{charge} {multiplicity}")

    # Coordinates: use Cartesian from structure
    species = structure.get("species", [])
    lattice = structure.get("lattice", [])
    frac_coords = structure.get("frac_coords", [])
    cart_coords = structure.get("cart_coords", [])

    if cart_coords:
        for sym, pos in zip(species, cart_coords):
            lines.append(f"{sym:2s}  {pos[0]:12.6f}  {pos[1]:12.6f}  {pos[2]:12.6f}")
    elif frac_coords and lattice:
        # Convert fractional to Cartesian
        for sym, fc in zip(species, frac_coords):
            x = fc[0] * lattice[0][0] + fc[1] * lattice[1][0] + fc[2] * lattice[2][0]
            y = fc[0] * lattice[0][1] + fc[1] * lattice[1][1] + fc[2] * lattice[2][1]
            z = fc[0] * lattice[0][2] + fc[1] * lattice[1][2] + fc[2] * lattice[2][2]
            lines.append(f"{sym:2s}  {x:12.6f}  {y:12.6f}  {z:12.6f}")

    lines.append("")  # Required trailing blank line
    return "\n".join(lines) + "\n"
