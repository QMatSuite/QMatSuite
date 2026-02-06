"""QMCPACK engine input specification for the universal writer.

Single combined file: qmc_input.xml in XML format.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def _write_qmcpack_text(fragment: dict[str, Any]) -> str:
    """Write QMCPACK XML input text from combined params + structure.

    Generates a minimal QMCPACK XML input. Full generation uses
    the existing QMCPACK writer module's dataclass-based approach.
    """
    import xml.etree.ElementTree as ET

    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    root = ET.Element("simulation")

    # Project
    project_id = params.get("project_id", "qmcpack_calc")
    proj = ET.SubElement(root, "project", id=project_id, series="0")

    qmcsystem = ET.SubElement(root, "qmcsystem")

    # Simulation cell
    lattice = structure.get("lattice", [])
    if lattice:
        sc = ET.SubElement(qmcsystem, "simulationcell")
        lat_el = ET.SubElement(sc, "parameter", name="lattice", units="angstrom")
        lat_text = "\n" + "\n".join(
            f"    {v[0]:16.8f} {v[1]:16.8f} {v[2]:16.8f}"
            for v in lattice
        ) + "\n  "
        lat_el.text = lat_text
        bc = ET.SubElement(sc, "parameter", name="bconds")
        bc.text = params.get("bconds", "p p p")

    # Ion particleset (positions)
    species = structure.get("species", [])
    frac_coords = structure.get("frac_coords", [])
    if species and frac_coords:
        ions = ET.SubElement(qmcsystem, "particleset", name="ion0")

        unique_species: list[str] = []
        for sp in species:
            if sp not in unique_species:
                unique_species.append(sp)

        for sp in unique_species:
            sp_coords = [
                frac_coords[i] for i, s in enumerate(species) if s == sp
            ]
            group = ET.SubElement(ions, "group", name=sp, size=str(len(sp_coords)))
            pos_el = ET.SubElement(group, "attrib", name="position", datatype="posArray")
            pos_text = "\n" + "\n".join(
                f"      {c[0]:.8f}  {c[1]:.8f}  {c[2]:.8f}"
                for c in sp_coords
            ) + "\n    "
            pos_el.text = pos_text

    # QMC section
    qmc_type = params.get("qmc_type", "vmc")
    qmc_method = params.get("method", "vmc")
    qmc = ET.SubElement(root, "qmc", method=qmc_method, move="pbyp")
    for pname in ("walkers", "blocks", "steps", "substeps",
                   "timestep", "warmupsteps"):
        val = params.get(pname)
        if val is not None:
            p_el = ET.SubElement(qmc, "parameter", name=pname)
            p_el.text = str(val)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")

    import io
    buf = io.StringIO()
    tree.write(buf, xml_declaration=True, encoding="unicode")
    return buf.getvalue() + "\n"


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
