"""xTB engine input specification for the universal parser/writer.

xTB uses:
- ``input.xyz`` for structure
- optional ``xcontrol.inp`` for advanced settings (MD/constraints/scan)
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import EngineInputSpec, InputFileSpec, SSOTMappingSpec

from .io.xtb_input import (
    parse_xcontrol_text,
    parse_xyz_text,
    write_xcontrol_text,
    write_xyz_text,
)


def get_xtb_input_spec(**context: Any) -> EngineInputSpec:
    """Return the xTB EngineInputSpec."""
    return EngineInputSpec(
        engine_family="xtb",
        syntax_family="dollar-flag",
        input_files=(
            InputFileSpec(
                filename="input.xyz",
                content_role="structure",
                description="XYZ coordinate file",
                custom_writer=write_xyz_text,
                custom_parser=parse_xyz_text,
            ),
            InputFileSpec(
                filename="xcontrol.inp",
                content_role="parameters",
                description="Optional xcontrol input file",
                optional=True,
                custom_writer=write_xcontrol_text,
                custom_parser=parse_xcontrol_text,
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("input.xyz",),
            params_in=("xcontrol.inp",),
        ),
    )
