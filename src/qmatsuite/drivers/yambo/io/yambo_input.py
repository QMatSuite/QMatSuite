"""Yambo input parser/writer (pure stdlib)."""

from __future__ import annotations

import re
from typing import Any

_NUM_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eEdD][+-]?\d+)?$")


def _parse_scalar_token(token: str) -> Any:
    s = token.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        return s[1:-1]
    if _NUM_RE.match(s):
        normalized = s.replace("D", "E").replace("d", "e")
        try:
            if "." not in normalized and "e" not in normalized.lower():
                return int(normalized)
            return float(normalized)
        except ValueError:
            return s
    return s


def _format_scalar_token(value: Any) -> str:
    if isinstance(value, str):
        if value == "":
            return ""
        if any(c.isspace() for c in value) or any(c in value for c in ('"', "'")):
            return f'"{value}"'
        if value.upper() in {"IP", "HARTREE", "ALDA", "LRC", "SEX", "ABS", "NONE"}:
            return f'"{value}"'
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6f}" if abs(value) < 1e4 else f"{value:.6e}"
    return str(value)


def _parse_rhs(rhs: str) -> Any:
    text = rhs.strip()
    if not text:
        return ""
    tokens = text.split()
    if len(tokens) == 1:
        return _parse_scalar_token(tokens[0])

    if len(tokens) >= 2:
        value_tokens = [_parse_scalar_token(t) for t in tokens[:-1]]
        unit_token = tokens[-1]
        if unit_token.isalpha() and all(isinstance(v, (int, float, str)) for v in value_tokens):
            value: Any
            if len(value_tokens) == 1:
                value = value_tokens[0]
            else:
                value = value_tokens
            return {"value": value, "unit": unit_token}

    return [_parse_scalar_token(t) for t in tokens]


def _format_rhs(value: Any) -> str:
    if isinstance(value, dict) and "value" in value and "unit" in value:
        val = value["value"]
        if isinstance(val, list):
            return " ".join(_format_scalar_token(v) for v in val) + f" {value['unit']}"
        return f"{_format_scalar_token(val)} {value['unit']}"
    if isinstance(value, list):
        return " ".join(_format_scalar_token(v) for v in value)
    return _format_scalar_token(value)


def _parse_block_row(line: str) -> list[Any]:
    parts = [p.strip() for p in line.split("|")]
    filtered = [p for p in parts if p]
    return [_parse_scalar_token(p) for p in filtered]


def parse_yambo_input_text(text: str) -> dict[str, Any]:
    """Parse a Yambo input text into a dict.

    Keys:
    - `runlevels`: ordered list of bare runlevel keywords
    - scalar variables (e.g. `Chimod`, `NGsBlkXp`)
    - block variables as list or list[list] (e.g. `BndsRnXp`)
    """
    params: dict[str, Any] = {}
    runlevels: list[str] = []

    current_block: str | None = None
    block_rows: list[list[Any]] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue

        if "#" in line:
            line = line.split("#", 1)[0].rstrip()
            if not line:
                continue

        if current_block is not None:
            if line == "%":
                if len(block_rows) == 1:
                    params[current_block] = block_rows[0]
                else:
                    params[current_block] = block_rows
                current_block = None
                block_rows = []
                continue
            block_rows.append(_parse_block_row(line))
            continue

        if line.startswith("%"):
            block_name = line[1:].strip()
            if block_name:
                current_block = block_name
                block_rows = []
            continue

        if "=" in line:
            key, rhs = line.split("=", 1)
            params[key.strip()] = _parse_rhs(rhs)
            continue

        token = line.strip()
        if token:
            runlevels.append(token)

    if current_block is not None:
        if len(block_rows) == 1:
            params[current_block] = block_rows[0]
        else:
            params[current_block] = block_rows

    if runlevels:
        params["runlevels"] = runlevels
    return params


def _as_block_rows(value: Any) -> list[list[Any]]:
    if isinstance(value, list):
        if not value:
            return [[]]
        if all(isinstance(v, list) for v in value):
            return value
        return [value]
    if isinstance(value, tuple):
        return [list(value)]
    return [[value]]


def write_yambo_input_text(params: dict[str, Any] | None) -> str:
    """Write canonical Yambo input text from params dict."""
    if not params:
        return ""

    lines: list[str] = []

    runlevels = params.get("runlevels") or params.get("_runlevels") or []
    if isinstance(runlevels, (list, tuple)):
        for rl in runlevels:
            lines.append(str(rl))

    ignore_keys = {"runlevels", "_runlevels", "gen_type"}
    scalar_keys: list[str] = []
    block_keys: list[str] = []

    for key in params:
        if key in ignore_keys or key.startswith("_"):
            continue
        value = params[key]
        if isinstance(value, (list, tuple)):
            block_keys.append(key)
        else:
            scalar_keys.append(key)

    for key in sorted(scalar_keys):
        lines.append(f"{key}= {_format_rhs(params[key])}")

    for key in sorted(block_keys):
        rows = _as_block_rows(params[key])
        lines.append(f"% {key}")
        for row in rows:
            row_text = " | ".join(_format_scalar_token(v) for v in row)
            lines.append(f" {row_text} |")
        lines.append("%")

    return "\n".join(lines).rstrip() + "\n"


def build_gw_input_dict(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "runlevels": ["HF_and_locXC", "gw0", "ppa", "el_el_corr", "dyson", "em1d"],
        "Chimod": "HARTREE",
        "BndsRnXp": list(params.get("polarization_bands", (1, 50))),
        "NGsBlkXp": {"value": params.get("ngs_blk_xp", 1), "unit": "RL"},
        "LongDrXp": list(params.get("long_dr_xp", (1.0, 0.0, 0.0))),
        "PPAPntXp": {"value": params.get("ppa_energy", 27.21138), "unit": "eV"},
        "GbndRnge": list(params.get("self_energy_bands", (1, 50))),
        "GTermKind": str(params.get("gw_terminator", "none")),
        "DysSolver": str(params.get("dyson_solver", "n")),
        "QPkrange": [
            int(params.get("kpt_range", (1, 1))[0]),
            int(params.get("kpt_range", (1, 1))[1]),
            int(params.get("band_range", (1, 8))[0]),
            int(params.get("band_range", (1, 8))[1]),
        ],
    }


def build_bse_input_dict(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "runlevels": ["optics", "bss", "bse", "em1s", "dipoles"],
        "BSKmod": str(params.get("bsk_mod", "SEX")),
        "BSEmod": str(params.get("bse_mod", "resonant")),
        "BSSmod": str(params.get("bss_mod", "h")),
        "Chimod": "HARTREE",
        "BndsRnXs": list(params.get("screening_bands", (1, 20))),
        "NGsBlkXs": {"value": params.get("ngs_blk_xs", 1), "unit": "RL"},
        "LongDrXs": list(params.get("long_dr_xs", (1.0, 0.0, 0.0))),
        "BSENGexx": {"value": params.get("bse_ngexx", 0), "unit": "RL"},
        "BSENGBlk": {"value": params.get("bse_ngblk", 1), "unit": "RL"},
        "BSEQptR": [1, 1],
        "BSEBands": list(params.get("bse_bands", (1, 8))),
        "BEnRange": [0.0, 10.0, "eV"],
        "BDmRange": [0.1, 0.1, "eV"],
        "BEnSteps": int(params.get("energy_steps", 200)),
        "BLongDir": list(params.get("long_dr_bse", (1.0, 0.0, 0.0))),
        "BSEprop": str(params.get("bse_prop", "abs")),
        "BSHayTrs": float(params.get("haydock_threshold", -0.02)),
    }
    qp_db = params.get("qp_db")
    if qp_db:
        out["KfnQPdb"] = str(qp_db)
    return out


def build_ip_input_dict(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "runlevels": ["optics", "chi", "dipoles"],
        "Chimod": str(params.get("chi_mod", "IP")),
        "QpntsRXd": list(params.get("qpoints", (1, 1))),
        "BndsRnXd": list(params.get("bands", (1, 50))),
        "EnRngeXd": [0.0, 10.0, "eV"],
        "DmRngeXd": [0.1, 0.1, "eV"],
        "ETStpsXd": int(params.get("energy_steps", 100)),
        "LongDrXd": list(params.get("long_dr_xd", (1.0, 0.0, 0.0))),
    }
    if "LRC_alpha" in params:
        out["LRC_alpha"] = float(params["LRC_alpha"])
    if "FxcGRLc" in params:
        out["FxcGRLc"] = float(params["FxcGRLc"])
    return out
