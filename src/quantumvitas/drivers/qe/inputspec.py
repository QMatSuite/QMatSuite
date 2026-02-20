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


def _parse_qe_text(text: str) -> dict[str, Any]:
    """Parse QE input text and return params + structure in StructureDoc format.

    Uses the full QE parser infrastructure including ibrav lattice reconstruction.

    Returns dict with:
        params: nested dict of namelists (e.g., {"CONTROL": {...}, "SYSTEM": {...}})
        structure: StructureDoc dict or None (e.g., {lattice, species, frac_coords})
    """
    from quantumvitas.drivers.qe.io.model import QECardType
    from quantumvitas.drivers.qe.io.parser import QEInputParser

    qe_input = QEInputParser.parse_string(text)

    # Extract params from namelists
    params: dict[str, Any] = {}
    for nl in qe_input.namelists:
        params[nl.name.upper()] = dict(nl.parameters)

    # Extract structure using the full QE infrastructure (handles ibrav, alat, etc.)
    structure = None
    positions_card = qe_input.get_card(QECardType.ATOMIC_POSITIONS)

    if positions_card and positions_card.data:
        try:
            from quantumvitas.drivers.qe.io.structure_io import structure_from_qe_input

            pmg_struct = structure_from_qe_input(qe_input)
            # Convert to plain Python types (no numpy) for clean YAML serialization
            lattice = [[float(x) for x in v] for v in pmg_struct.lattice.matrix]
            species = [str(s) for s in pmg_struct.species]
            frac_coords = [[float(x) for x in c] for c in pmg_struct.frac_coords]
            structure = {
                "lattice": lattice,
                "species": species,
                "frac_coords": frac_coords,
            }
        except Exception:
            pass  # If structure extraction fails, return None

    # Extract QE cards (K_POINTS, etc.) — needed for faithful roundtrip
    cards: dict[str, dict[str, Any]] = {}
    kpoints_card = qe_input.get_card(QECardType.K_POINTS)
    if kpoints_card and kpoints_card.data:
        kp: dict[str, Any] = {}
        if kpoints_card.option:
            kp["option"] = kpoints_card.option
        kp["data"] = kpoints_card.data
        cards["K_POINTS"] = kp

    result: dict[str, Any] = {"params": params, "structure": structure}
    if cards:
        result["cards"] = cards
    return result


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
        kp_option = kpoints.get("option", "").lower() if isinstance(kpoints.get("option"), str) else ""
        kp_data = kpoints.get("data", [])

        if kp_option == "gamma":
            lines.append("K_POINTS {gamma}")
        elif kp_option in ("crystal_b", "crystal_c", "tpiba_b", "tpiba_c") and kp_data:
            lines.append(f"K_POINTS {{{kp_option}}}")
            lines.append(f"  {len(kp_data)}")
            for row in kp_data:
                if isinstance(row, (list, tuple)) and len(row) >= 4:
                    lines.append(f"  {row[0]:.10f}  {row[1]:.10f}  {row[2]:.10f}  {int(row[3])}")
                elif isinstance(row, (list, tuple)) and len(row) >= 3:
                    lines.append(f"  {row[0]:.10f}  {row[1]:.10f}  {row[2]:.10f}")
        elif kp_option in ("tpiba", "crystal") and kp_data:
            lines.append(f"K_POINTS {{{kp_option}}}")
            lines.append(f"  {len(kp_data)}")
            for row in kp_data:
                if isinstance(row, (list, tuple)) and len(row) >= 4:
                    lines.append(f"  {row[0]:.10f}  {row[1]:.10f}  {row[2]:.10f}  {row[3]:.10f}")
        else:
            # automatic (default)
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
                custom_parser=_parse_qe_text,
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
