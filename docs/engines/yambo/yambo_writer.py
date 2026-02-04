"""
Yambo input file writer utilities.

Generates yambo input files from structured Python parameters.
Yambo input format has three constructs:
  1. Runlevel flags (bare keywords)
  2. Scalar variables: Name= value unit  # comment
  3. Block variables: % Name / val1 | val2 | / %

Important: Yambo normally generates its own input files via `yambo -F file.in`.
This writer is for programmatic generation in QMatSuite workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union


# ---------------------------------------------------------------------------
# Input parameter types
# ---------------------------------------------------------------------------

@dataclass
class RunLevel:
    """A yambo runlevel flag (bare keyword in input)."""
    name: str
    comment: str = ""


@dataclass
class ScalarVar:
    """A yambo scalar variable: Name= value unit."""
    name: str
    value: Union[int, float, str]
    unit: str = ""
    comment: str = ""


@dataclass
class BlockVar:
    """A yambo block variable: % Name ... %"""
    name: str
    rows: list[list[Union[int, float, str]]]
    comment: str = ""


@dataclass
class CommentedFlag:
    """A commented-out runlevel (disabled)."""
    name: str
    comment: str = ""


# ---------------------------------------------------------------------------
# Calculation type presets
# ---------------------------------------------------------------------------

@dataclass
class GWParams:
    """Parameters for a G0W0 PPA calculation."""
    # Bands
    polarization_bands: tuple[int, int] = (1, 50)
    self_energy_bands: tuple[int, int] = (1, 50)
    # Convergence
    ngs_blk_xp: int = 1               # Response block size [RL]
    ngs_blk_xp_unit: str = "RL"
    exx_rl_vcs: int = 0               # Exchange RL components (0 = auto)
    vxc_rl_vcs: int = 0               # XC potential RL components (0 = auto)
    # PPA
    ppa_energy: float = 27.21138      # PPA imaginary energy [eV]
    # Solver
    dyson_solver: str = "n"           # n=Newton, s=secant, g=Green
    gw_terminator: str = "none"       # none, BG, BRS
    # QP range
    kpt_range: tuple[int, int] = (1, 1)
    band_range: tuple[int, int] = (1, 1)
    # Electric field direction
    long_dr: tuple[float, float, float] = (1.0, 0.0, 0.0)


@dataclass
class BSEParams:
    """Parameters for a BSE calculation."""
    # Screening bands
    screening_bands: tuple[int, int] = (1, 50)
    ngs_blk_xs: int = 1
    ngs_blk_xs_unit: str = "RL"
    # BSE
    bse_bands: tuple[int, int] = (1, 50)
    bse_ngexx: int = 0                # Exchange components (0 = auto)
    bse_ngblk: int = 1                # Screened interaction block [RL]
    # Kernel and solver
    bsk_mod: str = "SEX"              # IP/Hartree/HF/ALDA/SEX
    bse_mod: str = "resonant"         # resonant/coupling/retarded
    bss_mod: str = "h"                # h=Haydock, d=diag, i=inversion
    # Spectrum
    energy_range: tuple[float, float] = (0.0, 10.0)
    damping: tuple[float, float] = (0.1, 0.1)
    energy_steps: int = 200
    # Haydock
    haydock_threshold: float = -0.02
    # Electric field direction
    long_dr: tuple[float, float, float] = (1.0, 0.0, 0.0)
    # Absorption type
    bse_prop: str = "abs"
    # QP corrections database
    qp_db: str = ""                   # e.g. "E < gw_run/ndb.QP"


@dataclass
class IPOpticsParams:
    """Parameters for IP (independent-particle) optics."""
    bands: tuple[int, int] = (1, 50)
    ngs_blk: int = 1
    ngs_blk_unit: str = "RL"
    energy_range: tuple[float, float] = (0.0, 10.0)
    damping: tuple[float, float] = (0.1, 0.1)
    energy_steps: int = 200
    long_dr: tuple[float, float, float] = (1.0, 0.0, 0.0)
    chi_mod: str = "IP"               # IP, HARTREE, ALDA, LRC


# ---------------------------------------------------------------------------
# Writer functions
# ---------------------------------------------------------------------------

def _format_value(val: Union[int, float, str]) -> str:
    """Format a value for yambo input."""
    if isinstance(val, str):
        return f'"{val}"'
    elif isinstance(val, int):
        return str(val)
    elif isinstance(val, float):
        return f"{val:.6f}" if val != int(val) else f"{val:.1f}"
    return str(val)


def _format_scalar(var: ScalarVar, width: int = 30) -> str:
    """Format a scalar variable line."""
    val_str = _format_value(var.value)
    unit_str = f"  {var.unit}" if var.unit else ""
    base = f"{var.name}= {val_str}{unit_str}"
    if var.comment:
        return f"{base:<{width}}# {var.comment}"
    return base


def _format_block(var: BlockVar) -> str:
    """Format a block variable."""
    lines = [f"% {var.name}"]
    for row in var.rows:
        row_str = " | ".join(f" {_format_value(v)} " for v in row)
        lines.append(f" {row_str}|")
    if var.comment:
        lines[-1] += f"        # {var.comment}"
    lines.append("%")
    return "\n".join(lines)


def write_gw_input(filepath: Path, params: GWParams) -> None:
    """Write a G0W0 PPA input file."""
    lines = [
        "# G0W0 PPA calculation — generated by QMatSuite",
        "#",
        "HF_and_locXC                     # [R] Hartree-Fock",
        "gw0                              # [R] GW approximation",
        "ppa                              # [R][Xp] Plasmon Pole Approximation",
        "el_el_corr                       # [R] Electron-Electron Correlation",
        "dyson                            # [R] Dyson Equation solver",
        "em1d                             # [R][X] Dynamically Screened Interaction",
    ]

    if params.exx_rl_vcs > 0:
        lines.append(f"EXXRLvcs= {params.exx_rl_vcs:>6}            RL    "
                      "# [XX] Exchange RL components")
    if params.vxc_rl_vcs > 0:
        lines.append(f"VXCRLvcs= {params.vxc_rl_vcs:>6}            RL    "
                      "# [XC] XCpotential RL components")

    lines.append(f'Chimod= "HARTREE"                # [X] Screening approximation')
    lines.append("% BndsRnXp")
    lines.append(f"   {params.polarization_bands[0]} | {params.polarization_bands[1]:>3} |"
                 "                         # [Xp] Polarization function bands")
    lines.append("%")
    lines.append(f"NGsBlkXp= {params.ngs_blk_xp:<6}            {params.ngs_blk_xp_unit}"
                 "    # [Xp] Response block size")
    lines.append("% LongDrXp")
    lines.append(f" {params.long_dr[0]:.6f} | {params.long_dr[1]:.6f} | "
                 f"{params.long_dr[2]:.6f} |        # [Xp] [cc] Electric Field")
    lines.append("%")
    lines.append(f"PPAPntXp= {params.ppa_energy:<11}    eV    # [Xp] PPA imaginary energy")
    lines.append("% GbndRnge")
    lines.append(f"   {params.self_energy_bands[0]} | {params.self_energy_bands[1]:>3} |"
                 "                         # [GW] G[W] bands range")
    lines.append("%")
    lines.append(f'GTermKind= "{params.gw_terminator}"'
                 '                # [GW] GW terminator')
    lines.append(f'DysSolver= "{params.dyson_solver}"'
                 '                   # [GW] Dyson Equation solver')
    lines.append("%QPkrange                        "
                 "# [GW] QP generalized Kpoint/Band indices")
    lines.append(f"{params.kpt_range[0]}|{params.kpt_range[1]}|"
                 f"{params.band_range[0]}|{params.band_range[1]}|")
    lines.append("%")

    filepath.write_text("\n".join(lines) + "\n")


def write_bse_input(filepath: Path, params: BSEParams) -> None:
    """Write a BSE input file (with static screening)."""
    lines = [
        "# BSE calculation — generated by QMatSuite",
        "#",
        "optics                           # [R] Linear Response optical properties",
        "bss                              # [R] BSE solver",
        "bse                              # [R][BSE] Bethe Salpeter Equation",
        "em1s                             # [R][Xs] Static Screening",
        "dipoles                          # [R] Oscillator strengths",
    ]

    lines.append(f'BSKmod= "{params.bsk_mod}"'
                 '                    # [BSE] Kernel approximation')
    lines.append(f'BSEmod= "{params.bse_mod}"'
                 '               # [BSE] resonant/coupling')
    lines.append(f'BSSmod= "{params.bss_mod}"'
                 '                      # [BSS] Solver')
    lines.append(f'Chimod= "HARTREE"                # [X] Screening approximation')

    # Static screening parameters
    lines.append("% BndsRnXs")
    lines.append(f"   {params.screening_bands[0]} | {params.screening_bands[1]:>3} |"
                 "                         # [Xs] Polarization function bands")
    lines.append("%")
    lines.append(f"NGsBlkXs= {params.ngs_blk_xs:<6}            {params.ngs_blk_xs_unit}"
                 "    # [Xs] Response block size")
    lines.append("% LongDrXs")
    lines.append(f" {params.long_dr[0]:.6f} | {params.long_dr[1]:.6f} | "
                 f"{params.long_dr[2]:.6f} |        # [Xs] [cc] Electric Field")
    lines.append("%")

    if params.bse_ngexx > 0:
        lines.append(f"BSENGexx= {params.bse_ngexx:>6}            RL    "
                      "# [BSK] Exchange components")
    lines.append(f"BSENGBlk= {params.bse_ngblk:<6}            RL    "
                 "# [BSK] Screened interaction block size")

    lines.append("% BSEQptR")
    lines.append(" 1 | 1 |                             # [BSK] Transferred momenta range")
    lines.append("%")
    lines.append("% BSEBands")
    lines.append(f"   {params.bse_bands[0]} | {params.bse_bands[1]:>3} |"
                 "                         # [BSK] Bands range")
    lines.append("%")
    lines.append("% BEnRange")
    lines.append(f"  {params.energy_range[0]:.5f} | {params.energy_range[1]:.5f} |"
                 "         eV    # [BSS] Energy range")
    lines.append("%")
    lines.append("% BDmRange")
    lines.append(f" {params.damping[0]:.6f} | {params.damping[1]:.6f} |"
                 "         eV    # [BSS] Damping range")
    lines.append("%")
    lines.append(f"BEnSteps= {params.energy_steps:<6}              "
                 "# [BSS] Energy steps")
    lines.append("% BLongDir")
    lines.append(f" {params.long_dr[0]:.6f} | {params.long_dr[1]:.6f} | "
                 f"{params.long_dr[2]:.6f} |        # [BSS] [cc] Electric Field direction")
    lines.append("%")
    lines.append(f'BSEprop= "{params.bse_prop}"'
                 '                   # [BSS] absorption/jdos/kerr')
    lines.append(f"BSHayTrs= {params.haydock_threshold:.6f}"
                 "               # [BSS] Haydock threshold")

    if params.qp_db:
        lines.append(f'KfnQPdb= "{params.qp_db}"'
                     '  # [EXTQP BSK BSS] QP corrections database')

    filepath.write_text("\n".join(lines) + "\n")


def write_ip_optics_input(filepath: Path, params: IPOpticsParams) -> None:
    """Write an IP optics input file."""
    lines = [
        "# IP Optics calculation — generated by QMatSuite",
        "#",
        "optics                           # [R] Linear Response optical properties",
        "chi                              # [R][X] IP Response function",
        "dipoles                          # [R] Oscillator strengths",
    ]

    lines.append(f'Chimod= "{params.chi_mod}"'
                 '                    # [X] IP/Hartree/ALDA/LRC')
    lines.append("% ChiEnRnge")
    lines.append(f"  {params.energy_range[0]:.5f} | {params.energy_range[1]:.5f} |"
                 "         eV    # [X] Energy range")
    lines.append("%")
    lines.append("% ChiDmRnge")
    lines.append(f" {params.damping[0]:.6f} | {params.damping[1]:.6f} |"
                 "         eV    # [X] Damping range")
    lines.append("%")
    lines.append(f"ChiEnStps= {params.energy_steps:<6}              "
                 "# [X] Energy steps")
    lines.append("% BndsRnXd")
    lines.append(f"   {params.bands[0]} | {params.bands[1]:>3} |"
                 "                         # [X] Bands range")
    lines.append("%")
    lines.append(f"NGsBlkXd= {params.ngs_blk:<6}            {params.ngs_blk_unit}"
                 "    # [X] Response block size")
    lines.append("% LongDrXd")
    lines.append(f" {params.long_dr[0]:.6f} | {params.long_dr[1]:.6f} | "
                 f"{params.long_dr[2]:.6f} |        # [X] [cc] Electric Field")
    lines.append("%")

    filepath.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Generic input builder
# ---------------------------------------------------------------------------

def build_input(
    runlevels: list[RunLevel],
    scalars: list[ScalarVar],
    blocks: list[BlockVar],
    commented: Optional[list[CommentedFlag]] = None,
) -> str:
    """Build a generic yambo input file from structured components."""
    lines = []

    # Runlevels
    for rl in runlevels:
        if rl.comment:
            lines.append(f"{rl.name:<35}# {rl.comment}")
        else:
            lines.append(rl.name)

    # Commented-out flags
    if commented:
        for cf in commented:
            if cf.comment:
                lines.append(f"#{cf.name:<34}# {cf.comment}")
            else:
                lines.append(f"#{cf.name}")

    # Scalars
    for sv in scalars:
        lines.append(_format_scalar(sv))

    # Blocks
    for bv in blocks:
        lines.append(_format_block(bv))

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pathlib import Path

    out_dir = Path(__file__).parent / "golden_refs" / "inputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Test GW writer
    gw = GWParams(
        polarization_bands=(1, 50),
        self_energy_bands=(1, 50),
        ngs_blk_xp=1,
        kpt_range=(1, 10),
        band_range=(3, 6),
    )
    write_gw_input(out_dir / "gw_generated.in", gw)
    print(f"Wrote: {out_dir / 'gw_generated.in'}")

    # Test BSE writer
    bse = BSEParams(
        screening_bands=(1, 20),
        bse_bands=(3, 6),
        bse_ngexx=839,
        energy_steps=200,
    )
    write_bse_input(out_dir / "bse_generated.in", bse)
    print(f"Wrote: {out_dir / 'bse_generated.in'}")

    # Test IP optics writer
    ip = IPOpticsParams(bands=(1, 50), energy_steps=200)
    write_ip_optics_input(out_dir / "ip_generated.in", ip)
    print(f"Wrote: {out_dir / 'ip_generated.in'}")
