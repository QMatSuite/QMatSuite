"""Wannier90 engine input specification for the universal parser/writer.

Single combined file: wannier90.win containing parameters + structure.
Parser and writer are in io/win.py; this module wires them into InputSpec.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def _parse_win_text(text: str) -> dict[str, Any]:
    """Delegate to io/win.py parser (lazy import)."""
    from quantumvitas.drivers.w90.io.win import parse_win_text

    return parse_win_text(text)


def _write_win_text(fragment: dict[str, Any]) -> str:
    """Delegate to io/win.py writer (lazy import)."""
    from quantumvitas.drivers.w90.io.win import write_win_text

    return write_win_text(fragment)


def get_w90_input_spec(**context: Any) -> EngineInputSpec:
    """Return the Wannier90 EngineInputSpec."""
    return EngineInputSpec(
        engine_family="w90",
        syntax_family="flat-keyval",
        input_files=(
            InputFileSpec(
                filename="wannier90.win",
                content_role="combined",
                description="Wannier90 input file",
                custom_writer=_write_win_text,
                custom_parser=_parse_win_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="amn_mmn_eig",
                description="Wannier90 prerequisites (.amn, .mmn, .eig from DFT)",
                staging_policy="symlink",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("wannier90.win",),
            kpoints_in=("wannier90.win",),
            params_in=("wannier90.win",),
        ),
    )
