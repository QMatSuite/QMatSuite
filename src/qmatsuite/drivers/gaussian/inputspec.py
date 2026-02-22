"""Gaussian engine input specification for the universal writer.

Single combined file: input.gjf containing parameters + geometry.
Delegates all I/O to io/gaussian_input.py (no inline writing/parsing).
"""

from __future__ import annotations

from typing import Any

from qmatsuite.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)

from .io.gaussian_input import (
    parse_gaussian_text,
    parse_route_keywords,
    write_gaussian_text,
)

# Re-export for backward compatibility with existing tests
_write_gaussian_text = write_gaussian_text
_parse_gaussian_text = parse_gaussian_text
_parse_route_keywords = parse_route_keywords


def get_gaussian_input_spec(**context: Any) -> EngineInputSpec:
    """Return the Gaussian EngineInputSpec."""
    return EngineInputSpec(
        engine_family="gaussian",
        syntax_family="keyword-block",
        input_files=(
            InputFileSpec(
                filename="input.gjf",
                content_role="combined",
                description="Gaussian input file (route + geometry)",
                custom_writer=write_gaussian_text,
                custom_parser=parse_gaussian_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="checkpoint",
                description="Checkpoint file (.chk) for restart",
                staging_policy="copy",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("input.gjf",),
            params_in=("input.gjf",),
        ),
    )
