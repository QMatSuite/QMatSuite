"""Backward-compatible Yambo input writer wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .io.yambo_input import (
    build_bse_input_dict,
    build_gw_input_dict,
    build_ip_input_dict,
    write_yambo_input_text,
)


@dataclass
class GWParams:
    polarization_bands: tuple[int, int] = (1, 50)
    self_energy_bands: tuple[int, int] = (1, 50)
    ngs_blk_xp: int = 1
    ngs_blk_xp_unit: str = "RL"
    exx_rl_vcs: int = 0
    vxc_rl_vcs: int = 0
    ppa_energy: float = 27.21138
    dyson_solver: str = "n"
    gw_terminator: str = "none"
    kpt_range: tuple[int, int] = (1, 1)
    band_range: tuple[int, int] = (1, 1)
    long_dr: tuple[float, float, float] = (1.0, 0.0, 0.0)


@dataclass
class BSEParams:
    screening_bands: tuple[int, int] = (1, 50)
    ngs_blk_xs: int = 1
    ngs_blk_xs_unit: str = "RL"
    bse_bands: tuple[int, int] = (1, 50)
    bse_ngexx: int = 0
    bse_ngblk: int = 1
    bsk_mod: str = "SEX"
    bse_mod: str = "resonant"
    bss_mod: str = "h"
    energy_range: tuple[float, float] = (0.0, 10.0)
    damping: tuple[float, float] = (0.1, 0.1)
    energy_steps: int = 200
    haydock_threshold: float = -0.02
    long_dr: tuple[float, float, float] = (1.0, 0.0, 0.0)
    bse_prop: str = "abs"
    qp_db: str = ""


@dataclass
class IPOpticsParams:
    bands: tuple[int, int] = (1, 50)
    ngs_blk: int = 1
    ngs_blk_unit: str = "RL"
    energy_range: tuple[float, float] = (0.0, 10.0)
    damping: tuple[float, float] = (0.1, 0.1)
    energy_steps: int = 200
    long_dr: tuple[float, float, float] = (1.0, 0.0, 0.0)
    chi_mod: str = "IP"


def write_gw_input(filepath: Path, params: GWParams) -> None:
    payload = build_gw_input_dict(
        {
            "polarization_bands": params.polarization_bands,
            "self_energy_bands": params.self_energy_bands,
            "ngs_blk_xp": params.ngs_blk_xp,
            "ppa_energy": params.ppa_energy,
            "dyson_solver": params.dyson_solver,
            "gw_terminator": params.gw_terminator,
            "kpt_range": params.kpt_range,
            "band_range": params.band_range,
            "long_dr_xp": params.long_dr,
        }
    )
    if params.exx_rl_vcs:
        payload["EXXRLvcs"] = {"value": params.exx_rl_vcs, "unit": params.ngs_blk_xp_unit}
    if params.vxc_rl_vcs:
        payload["VXCRLvcs"] = {"value": params.vxc_rl_vcs, "unit": params.ngs_blk_xp_unit}
    filepath.write_text(write_yambo_input_text(payload), encoding="utf-8")


def write_bse_input(filepath: Path, params: BSEParams) -> None:
    payload = build_bse_input_dict(
        {
            "screening_bands": params.screening_bands,
            "ngs_blk_xs": params.ngs_blk_xs,
            "bse_bands": params.bse_bands,
            "bse_ngexx": params.bse_ngexx,
            "bse_ngblk": params.bse_ngblk,
            "bsk_mod": params.bsk_mod,
            "bse_mod": params.bse_mod,
            "bss_mod": params.bss_mod,
            "energy_steps": params.energy_steps,
            "haydock_threshold": params.haydock_threshold,
            "bse_prop": params.bse_prop,
            "long_dr_bse": params.long_dr,
            "qp_db": params.qp_db,
        }
    )
    filepath.write_text(write_yambo_input_text(payload), encoding="utf-8")


def write_ip_optics_input(filepath: Path, params: IPOpticsParams) -> None:
    payload = build_ip_input_dict(
        {
            "bands": params.bands,
            "energy_steps": params.energy_steps,
            "chi_mod": params.chi_mod,
            "long_dr_xd": params.long_dr,
        }
    )
    filepath.write_text(write_yambo_input_text(payload), encoding="utf-8")
