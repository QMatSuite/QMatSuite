"""CP2K engine input specification for the universal writer.

Single combined file: input.inp in nested-section syntax.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def _write_cp2k_text(fragment: dict[str, Any]) -> str:
    """Write CP2K input text from combined params + structure.

    Generates &SECTION ... &END SECTION nested format.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    lines: list[str] = []

    # GLOBAL section
    global_params = params.get("GLOBAL", {})
    project_name = global_params.get("PROJECT", "calc")
    run_type = global_params.get("RUN_TYPE", "ENERGY")

    lines.append("&GLOBAL")
    lines.append(f"  PROJECT {project_name}")
    lines.append(f"  RUN_TYPE {run_type}")
    for k, v in sorted(global_params.items()):
        if k in ("PROJECT", "RUN_TYPE"):
            continue
        lines.append(f"  {k} {v}")
    lines.append("&END GLOBAL")
    lines.append("")

    # FORCE_EVAL section
    force_eval = params.get("FORCE_EVAL", {})
    lines.append("&FORCE_EVAL")
    lines.append(f"  METHOD {force_eval.get('METHOD', 'Quickstep')}")

    # DFT subsection
    dft = force_eval.get("DFT", params.get("DFT", {}))
    if dft:
        lines.append("  &DFT")
        for k, v in sorted(dft.items()):
            if isinstance(v, dict):
                continue  # Nested sections handled separately
            lines.append(f"    {k} {v}")

        # SCF subsection
        scf = dft.get("SCF", {})
        if scf:
            lines.append("    &SCF")
            for k, v in sorted(scf.items()):
                if isinstance(v, dict):
                    continue
                lines.append(f"      {k} {v}")
            lines.append("    &END SCF")

        # XC subsection
        xc = dft.get("XC", {})
        if xc:
            lines.append("    &XC")
            xc_func = xc.get("XC_FUNCTIONAL", "PBE")
            lines.append(f"      &XC_FUNCTIONAL {xc_func}")
            lines.append(f"      &END XC_FUNCTIONAL")
            lines.append("    &END XC")

        lines.append("  &END DFT")

    # SUBSYS section (structure)
    species = structure.get("species", [])
    frac_coords = structure.get("frac_coords", [])
    lattice = structure.get("lattice", [])

    lines.append("  &SUBSYS")

    if lattice:
        lines.append("    &CELL")
        labels = ["A", "B", "C"]
        for i, vec in enumerate(lattice):
            lines.append(
                f"      {labels[i]}  {vec[0]:.10f}  {vec[1]:.10f}  {vec[2]:.10f}"
            )
        lines.append("    &END CELL")

    if species and frac_coords:
        lines.append("    &COORD")
        lines.append("      SCALED .TRUE.")
        for sym, fc in zip(species, frac_coords):
            lines.append(
                f"      {sym}  {fc[0]:.10f}  {fc[1]:.10f}  {fc[2]:.10f}"
            )
        lines.append("    &END COORD")

    # KIND sections
    unique_species: list[str] = []
    for sp in species:
        if sp not in unique_species:
            unique_species.append(sp)

    kind_params = params.get("KIND", {})
    for sp in unique_species:
        sp_params = kind_params.get(sp, {})
        basis = sp_params.get("BASIS_SET", "DZVP-MOLOPT-SR-GTH")
        potential = sp_params.get("POTENTIAL", "GTH-PBE")
        lines.append(f"    &KIND {sp}")
        lines.append(f"      BASIS_SET {basis}")
        lines.append(f"      POTENTIAL {potential}")
        lines.append(f"    &END KIND")

    lines.append("  &END SUBSYS")
    lines.append("&END FORCE_EVAL")

    return "\n".join(lines) + "\n"


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
