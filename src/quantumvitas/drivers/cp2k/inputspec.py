"""CP2K engine input specification for the universal writer.

Single combined file: input.inp in nested-section syntax.
I/O functions delegated to io/cp2k_input.py (Phase B1 extraction).
"""

from __future__ import annotations

from typing import Any

from quantumvitas.drivers.cp2k.io.cp2k_input import (
    parse_cp2k_text as _parse_cp2k_text,
    write_cp2k_text as _write_cp2k_text,
)
from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def get_cp2k_input_spec(**context: Any) -> EngineInputSpec:
    """Return the CP2K EngineInputSpec."""
    return EngineInputSpec(
        engine_family="cp2k",
        syntax_family="nested-section",
        input_files=(
            InputFileSpec(
                filename="input.inp",
                content_role="combined",
                description="CP2K input file",
                custom_writer=_write_cp2k_text,
                custom_parser=_parse_cp2k_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="basis_sets",
                description="Basis set and potential files",
                staging_policy="reference",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("input.inp",),
            params_in=("input.inp",),
        ),
    )
