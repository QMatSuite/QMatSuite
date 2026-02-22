"""Siesta engine input specification for the universal parser/writer.

Single combined file: ``{system_label}.fdf`` containing parameters + structure.
"""

from __future__ import annotations

from typing import Any

from qmatsuite.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def _parse_siesta_text(text: str) -> dict[str, Any]:
    """Delegate to FDF parser (lazy import)."""
    from qmatsuite.drivers.siesta.io.fdf import parse_fdf_text

    return parse_fdf_text(text)


def _write_siesta_text(fragment: dict[str, Any]) -> str:
    """Delegate to FDF writer (lazy import)."""
    from qmatsuite.drivers.siesta.io.fdf import write_fdf_text

    return write_fdf_text(fragment)


def get_siesta_input_spec(**context: Any) -> EngineInputSpec:
    """Return the Siesta EngineInputSpec.

    Args:
        **context: May contain ``system_label`` for dynamic filename.
    """
    system_label = context.get("system_label", "siesta")
    filename = f"{system_label}.fdf"

    return EngineInputSpec(
        engine_family="siesta",
        syntax_family="flat-keyval",
        input_files=(
            InputFileSpec(
                filename=filename,
                content_role="combined",
                description="Siesta FDF input file",
                custom_writer=_write_siesta_text,
                custom_parser=_parse_siesta_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="pseudopotentials",
                description="Siesta pseudopotential files (.psf/.psml)",
                staging_policy="copy",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=(filename,),
            kpoints_in=(filename,),
            params_in=(filename,),
        ),
    )


__all__ = [
    "get_siesta_input_spec",
    "_parse_siesta_text",
    "_write_siesta_text",
]
