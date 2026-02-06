"""QE engine input specification for the universal writer.

Single combined file: {gen_type}.in containing namelists + cards.
Dynamic filename resolved via get_input_spec(gen_type=...).
Custom writer delegates to existing QEInputGenerator.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def _write_qe_text(fragment: dict[str, Any]) -> str:
    """Write QE input text from combined params + structure.

    Generates Fortran-namelist format directly. Full QE generation
    using QEInputGenerator is deferred to a future phase when the
    SSOT→QEInput mapping is formalized.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}
    return _write_qe_text_direct(params, structure)


def _write_qe_text_direct(
    params: dict[str, Any], structure: dict[str, Any]
) -> str:
    """Write QE input text directly (no QE IO module dependency)."""
    lines: list[str] = []

    # Namelists
    for nl_name in ("CONTROL", "SYSTEM", "ELECTRONS", "IONS", "CELL"):
        nl_params = params.get(nl_name, params.get(nl_name.lower(), {}))
        if nl_params:
            lines.append(f"&{nl_name}")
            for k, v in sorted(nl_params.items()):
                if isinstance(v, bool):
                    v_str = ".true." if v else ".false."
                elif isinstance(v, str):
                    v_str = f"'{v}'"
                else:
                    v_str = str(v)
                lines.append(f"    {k} = {v_str},")
            lines.append("/")

    # Cards
    species = structure.get("species", [])
    frac_coords = structure.get("frac_coords", [])
    lattice = structure.get("lattice", [])

    if species:
        unique_sp: list[str] = []
        for sp in species:
            if sp not in unique_sp:
                unique_sp.append(sp)

        lines.append("ATOMIC_SPECIES")
        for sp in unique_sp:
            pseudo = params.get("pseudo", {}).get(sp, f"{sp}.UPF")
            lines.append(f"  {sp}  1.0  {pseudo}")

    if frac_coords:
        lines.append("ATOMIC_POSITIONS (crystal)")
        for sym, fc in zip(species, frac_coords):
            lines.append(f"  {sym}  {fc[0]:.10f}  {fc[1]:.10f}  {fc[2]:.10f}")

    if lattice:
        lines.append("CELL_PARAMETERS (angstrom)")
        for vec in lattice:
            lines.append(f"  {vec[0]:.10f}  {vec[1]:.10f}  {vec[2]:.10f}")

    kpoints = params.get("kpoints", {})
    if kpoints:
        mesh = kpoints.get("mesh", kpoints.get("grid", [4, 4, 4]))
        shift = kpoints.get("shift", [0, 0, 0])
        lines.append("K_POINTS (automatic)")
        lines.append(f"  {mesh[0]} {mesh[1]} {mesh[2]}  {shift[0]} {shift[1]} {shift[2]}")

    return "\n".join(lines) + "\n"


def get_qe_input_spec(**context: Any) -> EngineInputSpec:
    """Return the QE EngineInputSpec.

    Args:
        **context: May contain gen_type for dynamic filename (default "pw").
    """
    gen_type = context.get("gen_type", "pw")
    filename = f"{gen_type}.in"

    return EngineInputSpec(
        engine_family="qe",
        syntax_family="fortran-namelist",
        input_files=(
            InputFileSpec(
                filename=filename,
                content_role="combined",
                description="QE input file (namelists + cards)",
                custom_writer=_write_qe_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="pseudopotentials",
                description="QE pseudopotential files (.UPF)",
                staging_policy="copy",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=(filename,),
            kpoints_in=(filename,),
            params_in=(filename,),
        ),
    )
