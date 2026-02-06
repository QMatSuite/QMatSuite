"""Siesta engine input specification for the universal writer.

Single combined file: {system_label}.fdf containing parameters + structure.
Dynamic filename resolved via get_input_spec(system_label=...).
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def _write_siesta_text(fragment: dict[str, Any]) -> str:
    """Write Siesta FDF text from combined params + structure.

    Delegates to the existing write_fdf function's logic but returns
    text instead of writing to a file, using the SSOT dict format.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    system_name = params.get("system_name", "system")
    system_label = params.get("system_label", "siesta")
    coord_format = params.get("coord_format", "Fractional")

    lines: list[str] = []

    # System identification
    lines.append(f"SystemName        {system_name}")
    lines.append(f"SystemLabel       {system_label}")
    lines.append("")

    # Lattice
    lattice = structure.get("lattice", [])
    if lattice:
        lines.append("LatticeConstant   1.0 Ang")
        lines.append("%block LatticeVectors")
        for vec in lattice:
            lines.append(f"  {vec[0]:16.10f}  {vec[1]:16.10f}  {vec[2]:16.10f}")
        lines.append("%endblock LatticeVectors")
        lines.append("")

    # Species
    species_list = structure.get("species", [])
    unique_species: list[str] = []
    for sp in species_list:
        if sp not in unique_species:
            unique_species.append(sp)

    if unique_species:
        lines.append(f"NumberOfSpecies    {len(unique_species)}")
        lines.append(f"NumberOfAtoms     {len(species_list)}")
        lines.append("")

        # Chemical species block (simplified — atomic numbers from symbol)
        lines.append("%block ChemicalSpeciesLabel")
        for i, sp in enumerate(unique_species, 1):
            # Simplified: use placeholder atomic number
            lines.append(f"  {i}  0  {sp}")
        lines.append("%endblock ChemicalSpeciesLabel")
        lines.append("")

    # Atomic coordinates
    frac_coords = structure.get("frac_coords", [])
    if frac_coords and species_list:
        lines.append(f"AtomicCoordinatesFormat  {coord_format}")
        lines.append("%block AtomicCoordinatesAndAtomicSpecies")
        for sp, fc in zip(species_list, frac_coords):
            sp_idx = unique_species.index(sp) + 1
            lines.append(
                f"  {fc[0]:16.10f}  {fc[1]:16.10f}  {fc[2]:16.10f}  {sp_idx}"
            )
        lines.append("%endblock AtomicCoordinatesAndAtomicSpecies")
        lines.append("")

    # Additional parameters
    skip_keys = {"system_name", "system_label", "coord_format"}
    for key, val in sorted(params.items()):
        if key in skip_keys:
            continue
        lines.append(f"{key}  {val}")

    return "\n".join(lines) + "\n"


def get_siesta_input_spec(**context: Any) -> EngineInputSpec:
    """Return the Siesta EngineInputSpec.

    Args:
        **context: May contain system_label for dynamic filename.
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
            params_in=(filename,),
        ),
    )
