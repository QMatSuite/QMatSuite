"""Wannier90 .win file parser and writer.

Parse: text -> dict(params, structure, diagnostics)
Write: dict(params, structure) -> text

Pure stdlib only — no kernel imports.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Known parameters (lowercase) — for diagnostic purposes
# ---------------------------------------------------------------------------
_KNOWN_SCALAR_KEYS: frozenset[str] = frozenset({
    # System
    "num_wann", "num_bands", "mp_grid", "gamma_only", "spinors",
    "shell_list", "search_shells", "skip_b1_tests", "kmesh_tol",
    # Projections
    "auto_projections",
    # Job control
    "postproc_setup", "exclude_bands", "select_projections",
    "restart", "iprint", "length_unit", "wvfn_formatted", "spin",
    "devel_flag", "timing_level", "optimisation", "translate_home_cell",
    "write_xyz", "write_vdw_data", "write_hr_diag",
    # Disentanglement
    "dis_win_min", "dis_win_max", "dis_froz_min", "dis_froz_max",
    "dis_num_iter", "dis_mix_ratio", "dis_conv_tol", "dis_conv_window",
    "dis_spheres_num", "dis_spheres_first_wann",
    # Wannierise
    "num_iter", "num_cg_steps", "conv_window", "conv_tol", "precond",
    "conv_noise_amp", "conv_noise_num", "num_dump_cycles",
    "num_print_cycles", "write_r2mn", "guiding_centres",
    "num_guide_cycles", "num_no_guide_iter", "trial_step", "fixed_step",
    "use_bloch_phases", "site_symmetry", "symmetrize_eps",
    "slwf_num", "slwf_constrain", "slwf_lambda",
    # Plot
    "wannier_plot", "wannier_plot_list", "wannier_plot_supercell",
    "wannier_plot_format", "wannier_plot_mode", "wannier_plot_spinor_mode",
    "wannier_plot_spinor_phase",
    "bands_plot", "bands_num_points", "bands_plot_format",
    "bands_plot_mode", "bands_plot_dim", "bands_plot_project",
    "fermi_surface_plot", "fermi_surface_num_points",
    "fermi_energy", "fermi_energy_min", "fermi_energy_max",
    "fermi_energy_step",
    "write_hr", "write_rmn", "write_bvec", "write_tb",
    "write_u_matrices", "hr_cutoff", "dist_cutoff", "dist_cutoff_mode",
    "dist_cutoff_hc",
    "one_dim_axis", "translation_centre_frac",
    "use_ws_distance", "ws_distance_tol", "ws_search_size",
    # Transport
    "transport", "transport_mode", "tran_win_min", "tran_win_max",
    "tran_energy_step", "tran_num_bb", "tran_num_ll", "tran_num_rr",
    "tran_num_cc", "tran_num_lc", "tran_num_cr",
    "tran_num_bandc", "tran_write_ht", "tran_read_ht",
    "tran_use_same_lead", "tran_group_threshold",
    "tran_num_cell_ll", "tran_num_cell_rr",
    # Postw90
    "berry", "berry_task", "berry_kmesh", "berry_curv_unit",
    "berry_curv_adpt_kmesh", "berry_curv_adpt_kmesh_thresh",
    "kubo_freq_min", "kubo_freq_max", "kubo_freq_step",
    "kubo_eigval_max", "kubo_adpt_smr", "kubo_adpt_smr_fac",
    "kubo_adpt_smr_max", "kubo_smr_fixed_en_width", "kubo_smr_type",
    "gyrotropic", "gyrotropic_task", "gyrotropic_kmesh",
    "gyrotropic_freq_min", "gyrotropic_freq_max", "gyrotropic_freq_step",
    "gyrotropic_smr_fixed_en_width", "gyrotropic_smr_type",
    "gyrotropic_eigval_max", "gyrotropic_band_list",
    "gyrotropic_degen_thresh",
    "kpath", "kpath_task", "kpath_bands_colour", "kpath_num_points",
    "kslice", "kslice_task", "kslice_2dkmesh",
    "kslice_corner", "kslice_b1", "kslice_b2",
    "boltz_calc_also_dos", "boltz_2d_dir_num",
    "boltz_dos_energy", "boltz_mu_min", "boltz_mu_max",
    "boltz_mu_step", "boltz_temp_min", "boltz_temp_max",
    "boltz_temp_step", "boltz_relax_time", "boltz_bandshift",
    "boltz_bandshift_firstband", "boltz_bandshift_energyshift",
    "smr_type", "adpt_smr", "adpt_smr_fac", "adpt_smr_max",
    "smr_fixed_en_width", "spin_decomp",
    "num_elec_per_state", "scissors_shift",
    "spin_axis_polar", "spin_axis_azimuth",
    "sc_eta", "sc_freq_scan", "sc_phase_conv",
    "shc_freq_scan", "shc_alpha", "shc_beta", "shc_gamma",
    "shc_bandshift", "shc_bandshift_firstband",
    "shc_bandshift_energyshift",
    "kdotp_num_bands",
    "transl_inv",
    "dos", "dos_task", "dos_kmesh", "dos_energy_min",
    "dos_energy_max", "dos_energy_step", "dos_project",
    "dos_smr_type", "dos_adpt_smr", "dos_adpt_smr_fac",
    "dos_adpt_smr_max", "dos_smr_fixed_en_width",
    "geninterp", "geninterp_alsofirstder", "geninterp_single_file",
    # Seedname (used in some contexts)
    "seedname",
    "wannier_plot_radius", "wannier_plot_scale",
    "fermi_surface_plot_format",
})

_KNOWN_BLOCKS: frozenset[str] = frozenset({
    "unit_cell_cart", "atoms_frac", "atoms_cart",
    "projections", "kpoints", "kpoint_path",
    "nnkpts", "exclude_bands", "dis_spheres", "slwf_centres",
})

_BOHR_TO_ANG = 0.529177210903


# ---------------------------------------------------------------------------
# Value parsing helpers
# ---------------------------------------------------------------------------

def _parse_value(raw: str) -> int | float | bool | str:
    """Parse a Wannier90 value string into a Python type."""
    s = raw.strip()

    # Boolean
    sl = s.lower()
    if sl in (".true.", "true", "t"):
        return True
    if sl in (".false.", "false", "f"):
        return False

    # Fortran-style float (1.0d0, 1.0D-6)
    if re.match(r"^[+-]?\d*\.?\d+[dD][+-]?\d+$", s):
        return float(s.lower().replace("d", "e"))

    # Integer
    try:
        return int(s)
    except ValueError:
        pass

    # Float
    try:
        return float(s)
    except ValueError:
        pass

    # String (strip optional quotes)
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        return s[1:-1]
    return s


def _parse_mp_grid(raw: str) -> list[int]:
    """Parse mp_grid value like '4 4 4' into [4, 4, 4]."""
    parts = raw.split()
    return [int(x) for x in parts[:3]]


# ---------------------------------------------------------------------------
# Block parsers
# ---------------------------------------------------------------------------

def _parse_unit_cell_block(lines: list[str]) -> dict[str, Any]:
    """Parse unit_cell_cart block -> lattice + units."""
    units = "ang"
    data_lines: list[list[float]] = []
    for line in lines:
        stripped = line.strip().lower()
        if stripped in ("bohr", "ang", "angstrom"):
            units = "bohr" if stripped == "bohr" else "ang"
        else:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    data_lines.append([float(x) for x in parts[:3]])
                except ValueError:
                    continue
    lattice = data_lines[:3] if len(data_lines) >= 3 else data_lines
    if units == "bohr":
        lattice = [[v * _BOHR_TO_ANG for v in row] for row in lattice]
    return {"lattice": lattice, "lattice_units": units}


def _parse_atoms_block(lines: list[str], fractional: bool) -> dict[str, Any]:
    """Parse atoms_frac or atoms_cart block."""
    units = "ang"
    species: list[str] = []
    coords: list[list[float]] = []
    for line in lines:
        stripped = line.strip().lower()
        if stripped in ("bohr", "ang", "angstrom"):
            units = "bohr" if stripped == "bohr" else "ang"
            continue
        parts = line.split()
        if len(parts) >= 4:
            try:
                species.append(parts[0])
                coords.append([float(x) for x in parts[1:4]])
            except ValueError:
                continue
    result: dict[str, Any] = {"species": species}
    if fractional:
        result["frac_coords"] = coords
    else:
        if units == "bohr":
            coords = [[v * _BOHR_TO_ANG for v in row] for row in coords]
        result["cart_coords"] = coords
    return result


def _parse_projections_block(lines: list[str]) -> list[str]:
    """Parse projections block -> list of projection strings."""
    projs: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            projs.append(stripped)
    return projs


def _parse_kpoints_block(lines: list[str]) -> dict[str, Any]:
    """Parse kpoints block -> dict with 'points' and optional 'weights'."""
    points: list[list[float]] = []
    weights: list[float] = []
    has_weights = False
    for line in lines:
        parts = line.split()
        if len(parts) >= 3:
            try:
                pt = [float(x) for x in parts[:3]]
                points.append(pt)
                if len(parts) >= 4:
                    weights.append(float(parts[3]))
                    has_weights = True
            except ValueError:
                continue
    result: dict[str, Any] = {"points": points}
    if has_weights and len(weights) == len(points):
        result["weights"] = weights
    return result


def _parse_kpoint_path_block(lines: list[str]) -> list[dict[str, Any]]:
    """Parse kpoint_path block -> list of path segments."""
    segments: list[dict[str, Any]] = []
    for line in lines:
        parts = line.split()
        # Format: Label1 x1 y1 z1 Label2 x2 y2 z2
        if len(parts) >= 8:
            try:
                seg = {
                    "start_label": parts[0],
                    "start": [float(x) for x in parts[1:4]],
                    "end_label": parts[4],
                    "end": [float(x) for x in parts[5:8]],
                }
                segments.append(seg)
            except (ValueError, IndexError):
                continue
    return segments


def _parse_exclude_bands_block(lines: list[str]) -> list[int]:
    """Parse exclude_bands block -> flat list of band indices."""
    bands: list[int] = []
    for line in lines:
        # Handle comma-separated and range syntax: 1-4, 6, 8-10
        for token in re.split(r"[,\s]+", line.strip()):
            if not token:
                continue
            m = re.match(r"(\d+)\s*-\s*(\d+)", token)
            if m:
                start, end = int(m.group(1)), int(m.group(2))
                bands.extend(range(start, end + 1))
            else:
                try:
                    bands.append(int(token))
                except ValueError:
                    continue
    return sorted(set(bands))


# ---------------------------------------------------------------------------
# Parser: parse_win_text
# ---------------------------------------------------------------------------

def parse_win_text(text: str) -> dict[str, Any]:
    """Parse a Wannier90 .win file into SSOT-compatible dict.

    Returns dict with 'params' and optionally 'structure' keys,
    suitable for the "combined" content_role merge in the universal parser.
    """
    lines = text.splitlines()
    params: dict[str, Any] = {}
    structure: dict[str, Any] = {}
    diagnostics: list[dict[str, Any]] = []

    i = 0
    while i < len(lines):
        raw_line = lines[i]

        # Strip comments (! and #)
        line = re.sub(r"[!#].*$", "", raw_line).strip()

        if not line:
            i += 1
            continue

        # Check for block start
        block_match = re.match(r"^begin\s+(\w+)", line, re.IGNORECASE)
        if block_match:
            block_name = block_match.group(1).lower()
            block_lines: list[str] = []
            i += 1
            while i < len(lines):
                bl = re.sub(r"[!#].*$", "", lines[i]).strip()
                if re.match(rf"^end\s+{re.escape(block_name)}\b", bl, re.IGNORECASE):
                    i += 1
                    break
                block_lines.append(bl)
                i += 1

            # Dispatch to block parser
            if block_name == "unit_cell_cart":
                cell_data = _parse_unit_cell_block(block_lines)
                structure.update(cell_data)
            elif block_name == "atoms_frac":
                atoms_data = _parse_atoms_block(block_lines, fractional=True)
                structure.update(atoms_data)
            elif block_name == "atoms_cart":
                atoms_data = _parse_atoms_block(block_lines, fractional=False)
                structure.update(atoms_data)
            elif block_name == "projections":
                params["projections"] = _parse_projections_block(block_lines)
            elif block_name == "kpoints":
                params["kpoints"] = _parse_kpoints_block(block_lines)
            elif block_name == "kpoint_path":
                params["kpoint_path"] = _parse_kpoint_path_block(block_lines)
            elif block_name == "exclude_bands":
                params["exclude_bands"] = _parse_exclude_bands_block(block_lines)
            elif block_name in _KNOWN_BLOCKS:
                # Known but not specially parsed — store raw
                params[block_name] = block_lines
            else:
                diagnostics.append({
                    "level": "warning",
                    "message": f"Unknown block: {block_name}",
                    "code": "unknown_block",
                })
                params[block_name] = block_lines
            continue

        # Key/value line: try separators =, :, or whitespace
        kv_match = re.match(r"^(\w+)\s*[=:]\s*(.+)$", line)
        if not kv_match:
            # Try space-separated (key value)
            kv_match = re.match(r"^(\w+)\s+(.+)$", line)
        if kv_match:
            key = kv_match.group(1).lower()
            raw_val = kv_match.group(2).strip()

            # Special handling for mp_grid
            if key == "mp_grid":
                params["mp_grid"] = _parse_mp_grid(raw_val)
            else:
                params[key] = _parse_value(raw_val)

            if key not in _KNOWN_SCALAR_KEYS:
                diagnostics.append({
                    "level": "warning",
                    "message": f"Unknown parameter: {key}",
                    "code": "unknown_parameter",
                    "line": i + 1,
                })
            i += 1
            continue

        # Unrecognized line
        if line:
            diagnostics.append({
                "level": "warning",
                "message": f"Unrecognized line: {line}",
                "code": "unrecognized_line",
                "line": i + 1,
            })
        i += 1

    result: dict[str, Any] = {"params": params}
    if structure:
        result["structure"] = structure
    if diagnostics:
        result["diagnostics"] = diagnostics
    return result


# ---------------------------------------------------------------------------
# Writer: write_win_text
# ---------------------------------------------------------------------------

def _format_value(val: Any) -> str:
    """Format a Python value for .win output."""
    if isinstance(val, bool):
        return ".true." if val else ".false."
    if isinstance(val, float):
        # Use compact representation; avoid unnecessary trailing zeros
        s = f"{val:.10g}"
        return s
    return str(val)


def write_win_text(fragment: dict[str, Any]) -> str:
    """Write Wannier90 .win text from combined params + structure.

    Generates canonical flat-keyval format with begin/end blocks.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    lines: list[str] = []

    # Keys that are written as blocks, not scalars
    block_keys = {
        "projections", "kpoints", "kpoint_path", "exclude_bands",
        "mp_grid", "nnkpts", "dis_spheres", "slwf_centres",
    }

    # 1. Scalar parameters (sorted alphabetically)
    for key, val in sorted(params.items()):
        if key in block_keys:
            continue
        if isinstance(val, (list, tuple, dict)):
            continue  # Blocks handled below
        lines.append(f"{key} = {_format_value(val)}")
    if lines:
        lines.append("")

    # 2. mp_grid (special: written as "mp_grid = N1 N2 N3")
    mp_grid = params.get("mp_grid")
    if mp_grid and isinstance(mp_grid, (list, tuple)) and len(mp_grid) >= 3:
        lines.append(f"mp_grid = {mp_grid[0]} {mp_grid[1]} {mp_grid[2]}")
        lines.append("")

    # 3. Unit cell
    lattice = structure.get("lattice", [])
    if lattice:
        lines.append("begin unit_cell_cart")
        lines.append("ang")
        for vec in lattice:
            lines.append(f"  {vec[0]:.10f}  {vec[1]:.10f}  {vec[2]:.10f}")
        lines.append("end unit_cell_cart")
        lines.append("")

    # 4. Atomic positions
    species = structure.get("species", [])
    frac_coords = structure.get("frac_coords", [])
    cart_coords = structure.get("cart_coords", [])
    if species and frac_coords:
        lines.append("begin atoms_frac")
        for sym, fc in zip(species, frac_coords):
            lines.append(f"  {sym}  {fc[0]:.10f}  {fc[1]:.10f}  {fc[2]:.10f}")
        lines.append("end atoms_frac")
        lines.append("")
    elif species and cart_coords:
        lines.append("begin atoms_cart")
        lines.append("ang")
        for sym, cc in zip(species, cart_coords):
            lines.append(f"  {sym}  {cc[0]:.10f}  {cc[1]:.10f}  {cc[2]:.10f}")
        lines.append("end atoms_cart")
        lines.append("")

    # 5. Projections block
    projections = params.get("projections", [])
    if projections and isinstance(projections, list):
        lines.append("begin projections")
        for proj in projections:
            lines.append(f"  {proj}")
        lines.append("end projections")
        lines.append("")

    # 6. kpoint_path block
    kpoint_path = params.get("kpoint_path", [])
    if kpoint_path and isinstance(kpoint_path, list):
        lines.append("begin kpoint_path")
        for seg in kpoint_path:
            if isinstance(seg, dict):
                sl = seg.get("start_label", "?")
                s = seg.get("start", [0, 0, 0])
                el = seg.get("end_label", "?")
                e = seg.get("end", [0, 0, 0])
                lines.append(
                    f"  {sl} {s[0]:.6f} {s[1]:.6f} {s[2]:.6f}  "
                    f"  {el} {e[0]:.6f} {e[1]:.6f} {e[2]:.6f}"
                )
        lines.append("end kpoint_path")
        lines.append("")

    # 7. exclude_bands block
    exclude_bands = params.get("exclude_bands", [])
    if exclude_bands and isinstance(exclude_bands, list):
        lines.append("begin exclude_bands")
        # Write as comma-separated on one line
        lines.append("  " + ", ".join(str(b) for b in exclude_bands))
        lines.append("end exclude_bands")
        lines.append("")

    # 8. kpoints block
    kpoints = params.get("kpoints")
    if isinstance(kpoints, dict) and "points" in kpoints:
        lines.append("begin kpoints")
        weights = kpoints.get("weights")
        for idx, pt in enumerate(kpoints["points"]):
            if weights and idx < len(weights):
                lines.append(
                    f"  {pt[0]:.10f}  {pt[1]:.10f}  {pt[2]:.10f}  {weights[idx]:.10e}"
                )
            else:
                lines.append(f"  {pt[0]:.10f}  {pt[1]:.10f}  {pt[2]:.10f}")
        lines.append("end kpoints")
        lines.append("")

    return "\n".join(lines) + "\n"
