"""Yambo engine input specification for the universal writer.

Single file: {gen_type}.in for calculation steps (GW, BSE, optics).
Setup step has no input file (creates SAVE directory).
Dynamic filename resolved via get_input_spec(gen_type=...).
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def _write_yambo_text(params: dict[str, Any] | None) -> str:
    """Write Yambo input text from parameters.

    Delegates to existing writer module's dataclass-based approach
    when available, otherwise generates flat key-value format.
    """
    if not params:
        return ""

    gen_type = params.get("gen_type", "gw")

    try:
        if gen_type == "gw":
            from quantumvitas.drivers.yambo.writer import GWParams, write_gw_input
            import tempfile
            from pathlib import Path

            gw_params = GWParams(
                polarization_bands=tuple(params.get("polarization_bands", (1, 50))),
                self_energy_bands=tuple(params.get("self_energy_bands", (1, 50))),
                ngs_blk_xp=params.get("ngs_blk_xp", 1),
                kpt_range=tuple(params.get("kpt_range", (1, 1))),
                band_range=tuple(params.get("band_range", (1, 8))),
                dyson_solver=params.get("dyson_solver", "n"),
                gw_terminator=params.get("gw_terminator", "none"),
            )
            # Write to temp file and read back
            with tempfile.NamedTemporaryFile(mode="w", suffix=".in", delete=False) as f:
                tmp_path = Path(f.name)
            write_gw_input(tmp_path, gw_params)
            content = tmp_path.read_text()
            tmp_path.unlink()
            return content

        elif gen_type == "bse":
            from quantumvitas.drivers.yambo.writer import BSEParams, write_bse_input
            import tempfile
            from pathlib import Path

            bse_params = BSEParams(
                screening_bands=tuple(params.get("screening_bands", (1, 20))),
                bse_bands=tuple(params.get("bse_bands", (1, 8))),
                energy_steps=params.get("energy_steps", 200),
                bsk_mod=params.get("bsk_mod", "SEX"),
                bss_mod=params.get("bss_mod", "h"),
            )
            with tempfile.NamedTemporaryFile(mode="w", suffix=".in", delete=False) as f:
                tmp_path = Path(f.name)
            write_bse_input(tmp_path, bse_params)
            content = tmp_path.read_text()
            tmp_path.unlink()
            return content

        elif gen_type == "optics":
            from quantumvitas.drivers.yambo.writer import IPOpticsParams, write_ip_optics_input
            import tempfile
            from pathlib import Path

            ip_params = IPOpticsParams(
                bands=tuple(params.get("bands", (1, 50))),
                energy_steps=params.get("energy_steps", 100),
                chi_mod=params.get("chi_mod", "IP"),
            )
            with tempfile.NamedTemporaryFile(mode="w", suffix=".in", delete=False) as f:
                tmp_path = Path(f.name)
            write_ip_optics_input(tmp_path, ip_params)
            content = tmp_path.read_text()
            tmp_path.unlink()
            return content

    except ImportError:
        pass

    # Fallback: simple key-value
    lines = ["# Yambo input file", f"# Type: {gen_type}", ""]
    skip_keys = {"gen_type"}
    for k, v in sorted(params.items()):
        if k in skip_keys:
            continue
        lines.append(f"{k} = {v}")
    return "\n".join(lines) + "\n"


def get_yambo_input_spec(**context: Any) -> EngineInputSpec:
    """Return the Yambo EngineInputSpec.

    Args:
        **context: May contain gen_type for dynamic filename.
            Returns empty spec for setup steps (no input file).
    """
    gen_type = context.get("gen_type", "gw")

    # Setup step doesn't produce an input file
    if gen_type == "setup":
        return EngineInputSpec(
            engine_family="yambo",
            syntax_family="flat-keyval",
            input_files=(),
            resource_refs=(
                ResourceRefSpec(
                    name="save_dir",
                    description="SAVE directory from DFT preprocessing",
                    staging_policy="symlink",
                ),
            ),
        )

    filename = f"{gen_type}.in"

    return EngineInputSpec(
        engine_family="yambo",
        syntax_family="flat-keyval",
        input_files=(
            InputFileSpec(
                filename=filename,
                content_role="parameters",
                description=f"Yambo {gen_type} input file",
                custom_writer=_write_yambo_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="save_dir",
                description="SAVE directory from DFT/setup",
                staging_policy="symlink",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            params_in=(filename,),
        ),
    )
