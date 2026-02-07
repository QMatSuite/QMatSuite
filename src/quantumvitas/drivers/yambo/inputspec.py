"""Yambo engine input specification for universal parser/writer."""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)

from .io.yambo_input import (
    build_bse_input_dict,
    build_gw_input_dict,
    build_ip_input_dict,
    parse_yambo_input_text,
    write_yambo_input_text,
)


def _write_yambo_text(params: dict[str, Any] | None) -> str:
    if not params:
        return ""

    # Already in canonical form.
    if any(k in params for k in ("runlevels", "Chimod", "BndsRnXp", "BSEBands", "BndsRnXd")):
        return write_yambo_input_text(params)

    gen_type = str(params.get("gen_type", "gw")).lower()
    if gen_type == "gw":
        return write_yambo_input_text(build_gw_input_dict(params))
    if gen_type == "bse":
        return write_yambo_input_text(build_bse_input_dict(params))
    if gen_type in {"optics", "ip"}:
        return write_yambo_input_text(build_ip_input_dict(params))

    return write_yambo_input_text(params)


def get_yambo_input_spec(**context: Any) -> EngineInputSpec:
    gen_type = str(context.get("gen_type", "gw")).lower()

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

    if gen_type == "ip":
        gen_type = "optics"

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
                custom_parser=parse_yambo_input_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="save_dir",
                description="SAVE directory from DFT/setup",
                staging_policy="symlink",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(params_in=(filename,)),
    )
