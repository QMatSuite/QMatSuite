"""QMCPACK input writer — temporary utility for exploration.

Generates QMCPACK XML input files from structured parameters.
This is a standalone utility for testing; will be deleted after
integration into src/qmatsuite/drivers/qmcpack/.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class QMCPACKCell:
    """Simulation cell definition."""
    lattice: list[list[float]]  # 3x3 in bohr
    bconds: str = "p p p"  # p=periodic, n=non-periodic
    lr_dim_cutoff: float = 15.0


@dataclass
class QMCPACKSpecies:
    """Ionic species definition."""
    symbol: str
    charge: int  # valence charge
    valence: int
    atomic_number: int
    mass: float
    positions: list[list[float]]  # in bohr
    pseudo_file: Optional[str] = None  # XML pseudo file path


@dataclass
class QMCPACKWavefunction:
    """Wavefunction specification."""
    href: str  # Path to HDF5 wavefunction file
    tilematrix: str = "1 0 0 0 1 0 0 0 1"
    twistnum: int = 0
    meshfactor: float = 1.0
    precision: str = "double"
    num_up: int = 0
    num_down: int = 0
    num_orbitals: int = 0
    # Jastrow parameters (optional, pre-optimized)
    j1_coeffs: Optional[dict[str, list[float]]] = None  # element -> coeffs
    j2_uu_coeffs: Optional[list[float]] = None
    j2_ud_coeffs: Optional[list[float]] = None


@dataclass
class QMCPACKVMCParams:
    """VMC calculation parameters."""
    blocks: int = 200
    steps: int = 10
    substeps: int = 2
    timestep: float = 0.3
    warmupsteps: int = 50
    usedrift: str = "yes"
    checkpoint: int = -1


@dataclass
class QMCPACKDMCParams:
    """DMC calculation parameters."""
    targetwalkers: int = 256
    blocks: int = 100
    steps: int = 20
    timestep: float = 0.005
    warmupsteps: int = 50
    nonlocalmoves: str = "yes"
    reconfiguration: str = "no"
    checkpoint: int = -1


@dataclass
class QMCPACKOptParams:
    """Wavefunction optimization parameters."""
    blocks: int = 100
    steps: int = 50
    samples: int = 5000
    warmupsteps: int = 100
    timestep: float = 0.05
    minmethod: str = "adaptive"
    max_relative_cost_change: float = 10.0
    max_param_change: float = 3.0
    shift_i: float = 0.01
    shift_s: float = 1.0
    num_loops: int = 3


def write_vmc_input(
    output_path: Path,
    project_id: str,
    cell: QMCPACKCell,
    species: list[QMCPACKSpecies],
    wavefunction: QMCPACKWavefunction,
    vmc_params: QMCPACKVMCParams,
) -> Path:
    """Write a QMCPACK VMC input XML file."""
    root = ET.Element("simulation")
    _add_project(root, project_id)
    qmcsystem = ET.SubElement(root, "qmcsystem")
    _add_simulationcell(qmcsystem, cell)
    _add_electron_particleset(qmcsystem, wavefunction.num_up, wavefunction.num_down)
    _add_ion_particleset(qmcsystem, species)
    _add_wavefunction(qmcsystem, wavefunction, species)
    _add_hamiltonian(qmcsystem, species)
    _add_vmc_section(root, vmc_params)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="   ")
    tree.write(output_path, xml_declaration=True, encoding="unicode")
    # Add newline at end
    with open(output_path, "a") as f:
        f.write("\n")
    return output_path


def write_vmc_dmc_input(
    output_path: Path,
    project_id: str,
    cell: QMCPACKCell,
    species: list[QMCPACKSpecies],
    wavefunction: QMCPACKWavefunction,
    vmc_params: QMCPACKVMCParams,
    dmc_params: QMCPACKDMCParams,
) -> Path:
    """Write a QMCPACK VMC+DMC input XML file."""
    root = ET.Element("simulation")
    _add_project(root, project_id)
    qmcsystem = ET.SubElement(root, "qmcsystem")
    _add_simulationcell(qmcsystem, cell)
    _add_electron_particleset(qmcsystem, wavefunction.num_up, wavefunction.num_down)
    _add_ion_particleset(qmcsystem, species)
    _add_wavefunction(qmcsystem, wavefunction, species)
    _add_hamiltonian(qmcsystem, species)
    _add_vmc_section(root, vmc_params)
    _add_dmc_section(root, dmc_params)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="   ")
    tree.write(output_path, xml_declaration=True, encoding="unicode")
    with open(output_path, "a") as f:
        f.write("\n")
    return output_path


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _add_project(root: ET.Element, project_id: str, series: int = 0):
    proj = ET.SubElement(root, "project", id=project_id, series=str(series))


def _add_simulationcell(parent: ET.Element, cell: QMCPACKCell):
    sc = ET.SubElement(parent, "simulationcell")
    lat = ET.SubElement(sc, "parameter", name="lattice", units="bohr")
    lat.text = "\n" + "\n".join(
        f"         {row[0]:16.8f} {row[1]:16.8f} {row[2]:16.8f}"
        for row in cell.lattice
    ) + "\n      "
    bc = ET.SubElement(sc, "parameter", name="bconds")
    bc.text = cell.bconds
    lr = ET.SubElement(sc, "parameter", name="LR_dim_cutoff")
    lr.text = str(cell.lr_dim_cutoff)


def _add_electron_particleset(parent: ET.Element, num_up: int, num_down: int):
    ps = ET.SubElement(parent, "particleset", name="e", random="yes")
    gu = ET.SubElement(ps, "group", name="u", size=str(num_up), mass="1.0")
    ET.SubElement(gu, "parameter", name="charge").text = "-1"
    ET.SubElement(gu, "parameter", name="mass").text = "1.0"
    gd = ET.SubElement(ps, "group", name="d", size=str(num_down), mass="1.0")
    ET.SubElement(gd, "parameter", name="charge").text = "-1"
    ET.SubElement(gd, "parameter", name="mass").text = "1.0"


def _add_ion_particleset(parent: ET.Element, species: list[QMCPACKSpecies]):
    ps = ET.SubElement(parent, "particleset", name="ion0")
    for sp in species:
        grp = ET.SubElement(ps, "group", name=sp.symbol,
                            size=str(len(sp.positions)),
                            mass=f"{sp.mass:.7f}")
        ET.SubElement(grp, "parameter", name="charge").text = str(sp.charge)
        ET.SubElement(grp, "parameter", name="valence").text = str(sp.valence)
        ET.SubElement(grp, "parameter", name="atomicnumber").text = str(sp.atomic_number)
        ET.SubElement(grp, "parameter", name="mass").text = f"{sp.mass:.7f}"
        att = ET.SubElement(grp, "attrib", name="position",
                            datatype="posArray", condition="0")
        att.text = "\n" + "\n".join(
            f"            {p[0]:16.8f} {p[1]:16.8f} {p[2]:16.8f}"
            for p in sp.positions
        ) + "\n         "


def _add_wavefunction(
    parent: ET.Element,
    wf: QMCPACKWavefunction,
    species: list[QMCPACKSpecies],
):
    wfn = ET.SubElement(parent, "wavefunction", name="psi0", target="e")
    # SPO collection from HDF5
    spo_coll = ET.SubElement(wfn, "sposet_collection",
                              type="bspline", href=wf.href,
                              tilematrix=wf.tilematrix,
                              twistnum=str(wf.twistnum),
                              source="ion0",
                              meshfactor=str(wf.meshfactor),
                              precision=wf.precision)
    ET.SubElement(spo_coll, "sposet", type="bspline", name="spo_ud",
                  size=str(wf.num_orbitals), spindataset="0")
    # Determinant set
    detset = ET.SubElement(wfn, "determinantset")
    slater = ET.SubElement(detset, "slaterdeterminant")
    ET.SubElement(slater, "determinant", sposet="spo_ud")
    ET.SubElement(slater, "determinant", sposet="spo_ud")

    # Jastrow factors
    if wf.j1_coeffs:
        j1 = ET.SubElement(wfn, "jastrow", type="One-Body", name="J1",
                           function="bspline", source="ion0", **{"print": "yes"})
        for elem, coeffs in wf.j1_coeffs.items():
            corr = ET.SubElement(j1, "correlation", elementType=elem,
                                  size=str(len(coeffs)), cusp="0.0")
            c = ET.SubElement(corr, "coefficients", id=f"e{elem}", type="Array")
            c.text = "\n" + " ".join(f"{v:.10f}" for v in coeffs) + "\n"

    if wf.j2_uu_coeffs and wf.j2_ud_coeffs:
        j2 = ET.SubElement(wfn, "jastrow", type="Two-Body", name="J2",
                           function="bspline", **{"print": "yes"})
        corr_uu = ET.SubElement(j2, "correlation", speciesA="u", speciesB="u",
                                 size=str(len(wf.j2_uu_coeffs)))
        c_uu = ET.SubElement(corr_uu, "coefficients", id="uu", type="Array")
        c_uu.text = "\n" + " ".join(f"{v:.10f}" for v in wf.j2_uu_coeffs) + "\n"

        corr_ud = ET.SubElement(j2, "correlation", speciesA="u", speciesB="d",
                                 size=str(len(wf.j2_ud_coeffs)))
        c_ud = ET.SubElement(corr_ud, "coefficients", id="ud", type="Array")
        c_ud.text = "\n" + " ".join(f"{v:.10f}" for v in wf.j2_ud_coeffs) + "\n"


def _add_hamiltonian(parent: ET.Element, species: list[QMCPACKSpecies]):
    ham = ET.SubElement(parent, "hamiltonian", name="h0", type="generic", target="e")
    ET.SubElement(ham, "pairpot", type="coulomb", name="ElecElec", source="e", target="e")
    ET.SubElement(ham, "pairpot", type="coulomb", name="IonIon", source="ion0", target="ion0")

    # Check if any species have pseudopotentials
    has_pseudo = any(sp.pseudo_file for sp in species)
    if has_pseudo:
        pp = ET.SubElement(ham, "pairpot", type="pseudo", name="PseudoPot",
                           source="ion0", wavefunction="psi0", format="xml")
        for sp in species:
            if sp.pseudo_file:
                ET.SubElement(pp, "pseudo", elementType=sp.symbol, href=sp.pseudo_file)


def _add_vmc_section(root: ET.Element, params: QMCPACKVMCParams):
    qmc = ET.SubElement(root, "qmc", method="vmc", move="pbyp")
    if params.checkpoint != 0:
        qmc.set("checkpoint", str(params.checkpoint))
    ET.SubElement(qmc, "estimator", name="LocalEnergy", hdf5="no")
    ET.SubElement(qmc, "parameter", name="blocks").text = str(params.blocks)
    ET.SubElement(qmc, "parameter", name="steps").text = str(params.steps)
    ET.SubElement(qmc, "parameter", name="substeps").text = str(params.substeps)
    ET.SubElement(qmc, "parameter", name="timestep").text = str(params.timestep)
    ET.SubElement(qmc, "parameter", name="warmupsteps").text = str(params.warmupsteps)


def _add_dmc_section(root: ET.Element, params: QMCPACKDMCParams):
    qmc = ET.SubElement(root, "qmc", method="dmc", move="pbyp")
    if params.checkpoint != 0:
        qmc.set("checkpoint", str(params.checkpoint))
    ET.SubElement(qmc, "estimator", name="LocalEnergy", hdf5="no")
    ET.SubElement(qmc, "parameter", name="targetwalkers").text = str(params.targetwalkers)
    ET.SubElement(qmc, "parameter", name="blocks").text = str(params.blocks)
    ET.SubElement(qmc, "parameter", name="steps").text = str(params.steps)
    ET.SubElement(qmc, "parameter", name="timestep").text = str(params.timestep)
    ET.SubElement(qmc, "parameter", name="warmupsteps").text = str(params.warmupsteps)
    ET.SubElement(qmc, "parameter", name="nonlocalmoves").text = params.nonlocalmoves
    ET.SubElement(qmc, "parameter", name="reconfiguration").text = params.reconfiguration


# ─────────────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=" * 60)
    print("QMCPACK Writer Self-Test")
    print("=" * 60)

    # Diamond C cell
    cell = QMCPACKCell(
        lattice=[
            [3.37316115, 3.37316115, 0.0],
            [0.0, 3.37316115, 3.37316115],
            [3.37316115, 0.0, 3.37316115],
        ],
        bconds="p p p",
    )

    carbon = QMCPACKSpecies(
        symbol="C",
        charge=4,
        valence=4,
        atomic_number=6,
        mass=21894.7135906,
        positions=[
            [0.0, 0.0, 0.0],
            [1.68658058, 1.68658058, 1.68658058],
        ],
        pseudo_file="C.BFD.xml",
    )

    wf = QMCPACKWavefunction(
        href="pwscf.pwscf.h5",
        num_up=4,
        num_down=4,
        num_orbitals=4,
        j1_coeffs={"C": [-0.2032, -0.1626, -0.1431, -0.1216, -0.0992, -0.0711, -0.0445, -0.0214]},
        j2_uu_coeffs=[0.2798, 0.2173, 0.1656, 0.1217, 0.0840, 0.0530, 0.0292, 0.0122],
        j2_ud_coeffs=[0.4631, 0.3564, 0.2588, 0.1829, 0.1234, 0.0771, 0.0415, 0.0169],
    )

    vmc = QMCPACKVMCParams(blocks=200, steps=10, timestep=0.3)
    dmc = QMCPACKDMCParams(targetwalkers=64, blocks=100, timestep=0.005)

    # Test VMC input
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="w") as f:
        vmc_path = Path(f.name)
    write_vmc_input(vmc_path, "test_vmc", cell, [carbon], wf, vmc)
    content = vmc_path.read_text()
    assert "<simulation>" in content
    assert 'method="vmc"' in content
    assert "C.BFD.xml" in content
    assert "pwscf.pwscf.h5" in content
    print(f"\n--- VMC input ({len(content)} chars) ---")
    print(content[:500] + "...\n")
    print("  VMC input: PASSED")
    vmc_path.unlink()

    # Test VMC+DMC input
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="w") as f:
        vmc_dmc_path = Path(f.name)
    write_vmc_dmc_input(vmc_dmc_path, "test_vmc_dmc", cell, [carbon], wf, vmc, dmc)
    content = vmc_dmc_path.read_text()
    assert 'method="vmc"' in content
    assert 'method="dmc"' in content
    print(f"--- VMC+DMC input ({len(content)} chars) ---")
    print("  VMC+DMC input: PASSED")
    vmc_dmc_path.unlink()

    print("\n" + "=" * 60)
    print("All writer tests PASSED")
    print("=" * 60)
