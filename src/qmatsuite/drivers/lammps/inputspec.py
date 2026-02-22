"""LAMMPS engine input specification for the universal writer/parser.

Two input files: in.lammps (parameters/commands) and structure.data (structure).
LAMMPS uses a command-stream syntax (F5): imperative, order-matters, positional args.

All parse/write logic is in io/script.py and io/data.py. This module only
wires them into the EngineInputSpec.
"""

from __future__ import annotations

from typing import Any

from qmatsuite.drivers.lammps.io.data import (
    parse_lammps_data_text,
    write_lammps_data_text,
)
from qmatsuite.drivers.lammps.io.script import (
    parse_lammps_script_text,
    write_lammps_script_text,
)
from qmatsuite.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def get_lammps_input_spec(**context: Any) -> EngineInputSpec:
    """Return the LAMMPS EngineInputSpec."""
    return EngineInputSpec(
        engine_family="lammps",
        syntax_family="command-stream",
        input_files=(
            InputFileSpec(
                filename="in.lammps",
                content_role="parameters",
                description="LAMMPS input script",
                custom_writer=write_lammps_script_text,
                custom_parser=parse_lammps_script_text,
            ),
            InputFileSpec(
                filename="structure.data",
                content_role="structure",
                description="LAMMPS data file (atomic positions)",
                custom_writer=write_lammps_data_text,
                custom_parser=parse_lammps_data_text,
                optional=True,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="potentials",
                description="Force-field potential files (.eam, .tersoff, etc.)",
                staging_policy="copy",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("structure.data",),
            params_in=("in.lammps",),
        ),
    )
