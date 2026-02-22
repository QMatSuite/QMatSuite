"""ABINIT engine input specification for the universal writer.

Single combined file: {step_prefix}.abi containing structure + parameters.
Dynamic filename resolved via get_input_spec(step_prefix=...).

I/O functions delegated to io/abinit_input.py (Phase B1 extraction).
"""

from __future__ import annotations

from typing import Any

from qmatsuite.drivers.abinit.io.abinit_input import (
    parse_abinit_text as _parse_abinit_text,
    write_abinit_text as _write_abinit_text,
)
from qmatsuite.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def get_abinit_input_spec(**context: Any) -> EngineInputSpec:
    """Return the ABINIT EngineInputSpec.

    Args:
        **context: May contain step_prefix for dynamic filename.
    """
    step_prefix = context.get("step_prefix", "run")
    filename = f"{step_prefix}.abi"

    return EngineInputSpec(
        engine_family="abinit",
        syntax_family="flat-keyval",
        input_files=(
            InputFileSpec(
                filename=filename,
                content_role="combined",
                description="ABINIT input file",
                custom_writer=_write_abinit_text,
                custom_parser=_parse_abinit_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="pseudopotentials",
                description="ABINIT pseudopotential files",
                staging_policy="reference",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=(filename,),
            kpoints_in=(filename,),
            params_in=(filename,),
        ),
    )
