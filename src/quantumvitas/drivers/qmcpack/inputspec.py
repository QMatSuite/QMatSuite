"""QMCPACK engine input specification for the universal writer/parser.

Single combined file: qmc_input.xml in XML format (syntax family F6).
Parser and writer are in io/qmcpack_xml.py (pure stdlib module).
This module wires them into the inputformat EngineInputSpec.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)

# Import parse/write functions from io module — no inline writing per playbook Phase 4
from quantumvitas.drivers.qmcpack.io.qmcpack_xml import (
    _extract_resource_refs,
    _parse_pos_array,
    _parse_string_array,
    parse_qmcpack_text as _parse_qmcpack_text,
    write_qmcpack_text as _write_qmcpack_text,
)


def get_qmcpack_input_spec(**context: Any) -> EngineInputSpec:
    """Return the QMCPACK EngineInputSpec."""
    return EngineInputSpec(
        engine_family="qmcpack",
        syntax_family="xml",
        input_files=(
            InputFileSpec(
                filename="qmc_input.xml",
                content_role="combined",
                description="QMCPACK XML input file",
                custom_writer=_write_qmcpack_text,
                custom_parser=_parse_qmcpack_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="wavefunction",
                description="HDF5 wavefunction file from DFT",
                staging_policy="symlink",
            ),
            ResourceRefSpec(
                name="pseudopotentials",
                description="XML pseudopotential files",
                staging_policy="copy",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("qmc_input.xml",),
            params_in=("qmc_input.xml",),
        ),
    )
