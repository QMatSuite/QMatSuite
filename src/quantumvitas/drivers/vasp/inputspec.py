"""VASP engine input specification for the universal writer.

Declares INCAR, POSCAR, KPOINTS as input files and POTCAR as resource ref.
Custom writers delegate to existing pure I/O modules where available.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def _write_incar_text(params: dict[str, Any] | None) -> str:
    """Write INCAR text from a parameters dict.

    Pure function, stdlib only. Matches the output format of
    engine/vasp_writer.py:write_incar but operates on a dict and
    returns a string instead of writing to a file.
    """
    if not params:
        return ""

    lines: list[str] = []

    # SYSTEM tag first (conventional)
    if "SYSTEM" in params:
        lines.append(f"SYSTEM = {params['SYSTEM']}")
        lines.append("")

    for key, value in sorted(params.items()):
        if key == "SYSTEM":
            continue
        if isinstance(value, bool):
            value_str = ".TRUE." if value else ".FALSE."
        elif isinstance(value, (list, tuple)):
            value_str = " ".join(str(v) for v in value)
        else:
            value_str = str(value)
        lines.append(f"{key} = {value_str}")

    return "\n".join(lines) + "\n"


def _write_poscar_text(structure: dict[str, Any] | None) -> str:
    """Delegate to the pure POSCAR writer."""
    from quantumvitas.drivers.vasp.io.poscar import write_poscar_text
    if not structure:
        return ""
    return write_poscar_text(structure)


def _write_kpoints_text(params: dict[str, Any] | None) -> str:
    """Extract kpoints sub-dict from params and delegate to pure writer.

    Expects params to contain a "kpoints" key with a KpointsSpec dict.
    If no kpoints data, writes a default 4x4x4 Gamma-centered mesh.
    """
    from quantumvitas.drivers.vasp.io.kpoints import write_kpoints_text

    if not params:
        kpoints_dict: dict[str, Any] = {}
    elif isinstance(params, dict) and "kpoints" in params:
        kpoints_dict = params["kpoints"]
    else:
        # params IS the kpoints dict (direct dispatch)
        kpoints_dict = params

    # Default if empty
    if not kpoints_dict:
        kpoints_dict = {"mode": "automatic", "mesh": [4, 4, 4]}

    return write_kpoints_text(kpoints_dict)


def get_vasp_input_spec(**context: Any) -> EngineInputSpec:
    """Return the VASP EngineInputSpec.

    VASP has three input files (INCAR, POSCAR, KPOINTS) and one
    resource reference (POTCAR).

    Args:
        **context: Unused for VASP (filenames are fixed).

    Returns:
        EngineInputSpec for VASP.
    """
    return EngineInputSpec(
        engine_family="vasp",
        syntax_family="flat-keyval",
        input_files=(
            InputFileSpec(
                filename="INCAR",
                content_role="parameters",
                description="VASP calculation parameters",
                custom_writer=_write_incar_text,
            ),
            InputFileSpec(
                filename="POSCAR",
                content_role="structure",
                description="Crystal structure (Direct coordinates)",
                custom_writer=_write_poscar_text,
            ),
            InputFileSpec(
                filename="KPOINTS",
                content_role="kpoints",
                description="K-point mesh specification",
                custom_writer=_write_kpoints_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="potcar",
                description="POTCAR pseudopotential file (staged from library)",
                staging_policy="copy",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("POSCAR",),
            kpoints_in=("KPOINTS",),
            params_in=("INCAR",),
        ),
    )
