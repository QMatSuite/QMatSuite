"""Siesta output parser.

Parses Siesta output files (.out, .EIG, .FA, .STRUCT_OUT, .XV,
FORCE_STRESS, OUTVARS.yml, .MDE, .PDOS.xml, .DOS) and extracts
structured data.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def parse_main_output(out_path: Path) -> dict[str, Any]:
    """Parse the main Siesta .out file.

    Extracts total energy, Fermi energy, SCF convergence, forces,
    stress tensor, system metadata.
    """
    text = out_path.read_text()
    result: dict[str, Any] = {}

    # System label
    m = re.search(r"reinit: System Label:\s+(\S+)", text)
    result["system_label"] = m.group(1) if m else None

    # Number of atoms (Siesta 5.x format: "initatomlists: Number of atoms, orbitals, and projectors:  N ...")
    m = re.search(r"Number of atoms, orbitals, and projectors:\s+(\d+)", text)
    if not m:
        m = re.search(r"Number of atoms\s*[=:]\s*(\d+)", text)
    result["n_atoms"] = int(m.group(1)) if m else None

    # Number of species (Siesta 5.x format: "redata: Number of Atomic Species  =  N")
    m = re.search(r"Number of Atomic Species\s*=\s*(\d+)", text)
    if not m:
        m = re.search(r"Number of species\s*[=:]\s*(\d+)", text)
    result["n_species"] = int(m.group(1)) if m else None

    # SCF history: parse "scf:" lines
    scf_lines = re.findall(
        r"scf:\s+(\d+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)"
        r"\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)",
        text,
    )
    scf_history = []
    for sl in scf_lines:
        scf_history.append({
            "iter": int(sl[0]),
            "Eharris": float(sl[1]),
            "E_KS": float(sl[2]),
            "FreeEng": float(sl[3]),
            "dDmax": float(sl[4]),
            "Ef": float(sl[5]),
            "dHmax": float(sl[6]),
        })
    result["scf_history"] = scf_history
    result["n_scf_iterations"] = len(scf_history)

    # SCF convergence
    result["scf_converged"] = "SCF Convergence" in text

    # Total energy
    m = re.search(r"siesta:\s+E_KS\(eV\)\s+=\s+([-\d.]+)", text)
    result["total_energy_eV"] = float(m.group(1)) if m else None

    # Fermi energy
    m = re.search(r"siesta:\s+Fermi\s+=\s+([-\d.E+]+)", text)
    result["fermi_energy_eV"] = float(m.group(1)) if m else None

    # Forces (last occurrence)
    force_blocks = re.findall(
        r"siesta: Atomic forces \(eV/Ang\):\n"
        r"((?:siesta:\s+\d+\s+[-\d.E+]+\s+[-\d.E+]+\s+[-\d.E+]+\n)+)",
        text,
    )
    if force_blocks:
        forces = []
        for line in force_blocks[-1].strip().split("\n"):
            parts = line.split()
            forces.append([float(parts[2]), float(parts[3]), float(parts[4])])
        result["forces_ev_ang"] = forces

    # Stress tensor
    m = re.search(
        r"siesta: Stress tensor \(static\) \(eV/Ang\*\*3\):\n"
        r"siesta:\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)\n"
        r"siesta:\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)\n"
        r"siesta:\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)",
        text,
    )
    if m:
        result["stress_ev_ang3"] = [
            [float(m.group(i)) for i in range(1, 4)],
            [float(m.group(i)) for i in range(4, 7)],
            [float(m.group(i)) for i in range(7, 10)],
        ]

    # Normal exit
    result["normal_exit"] = "Job completed" in text

    return result


def parse_eig_file(eig_path: Path) -> dict[str, Any]:
    """Parse Siesta .EIG file (eigenvalues per k-point)."""
    lines = eig_path.read_text().strip().split("\n")
    result: dict[str, Any] = {}

    result["fermi_energy_eV"] = float(lines[0].strip())

    header = lines[1].strip().split()
    result["n_bands"] = int(header[0])
    result["n_spin"] = int(header[1])
    result["n_kpoints"] = int(header[2])

    eigenvalues: dict[int, list[float]] = {}
    current_kpt = None
    current_eigs: list[float] = []

    for line in lines[2:]:
        tokens = line.split()
        if not tokens:
            continue
        try:
            kpt_idx = int(tokens[0])
            if current_kpt is not None:
                eigenvalues[current_kpt] = current_eigs
            current_kpt = kpt_idx
            current_eigs = [float(t) for t in tokens[1:]]
        except ValueError:
            current_eigs.extend(float(t) for t in tokens)

    if current_kpt is not None:
        eigenvalues[current_kpt] = current_eigs

    result["eigenvalues"] = eigenvalues
    return result


def parse_fa_file(fa_path: Path) -> dict[str, Any]:
    """Parse Siesta .FA file (forces on atoms in eV/Ang)."""
    lines = fa_path.read_text().strip().split("\n")
    n_atoms = int(lines[0].strip())
    forces = []
    for line in lines[1:]:
        tokens = line.split()
        if len(tokens) >= 4:
            forces.append([float(tokens[1]), float(tokens[2]), float(tokens[3])])
    return {"n_atoms": n_atoms, "forces_ev_ang": forces}


def parse_struct_out(struct_path: Path) -> dict[str, Any]:
    """Parse Siesta .STRUCT_OUT file (final structure)."""
    lines = struct_path.read_text().strip().split("\n")

    lattice = []
    for i in range(3):
        tokens = lines[i].split()
        lattice.append([float(t) for t in tokens])

    n_atoms = int(lines[3].strip())

    atoms = []
    for line in lines[4:4 + n_atoms]:
        tokens = line.split()
        atoms.append({
            "species_index": int(tokens[0]),
            "atomic_number": int(tokens[1]),
            "position": [float(tokens[2]), float(tokens[3]), float(tokens[4])],
        })

    return {"lattice_vectors_ang": lattice, "n_atoms": n_atoms, "atoms": atoms}


def parse_force_stress(fs_path: Path) -> dict[str, Any]:
    """Parse Siesta FORCE_STRESS file."""
    lines = fs_path.read_text().strip().split("\n")

    total_energy = float(lines[0].strip())

    stress = []
    for i in range(1, 4):
        tokens = lines[i].split()
        stress.append([float(t) for t in tokens])

    n_atoms = int(lines[4].strip())

    forces = []
    for line in lines[5:5 + n_atoms]:
        tokens = line.split()
        forces.append({
            "species_index": int(tokens[0]),
            "atomic_number": int(tokens[1]),
            "force": [float(tokens[2]), float(tokens[3]), float(tokens[4])],
            "label": tokens[5] if len(tokens) > 5 else None,
        })

    return {
        "total_energy": total_energy,
        "stress_tensor": stress,
        "n_atoms": n_atoms,
        "forces": forces,
    }


def parse_mde_file(mde_path: Path) -> dict[str, Any]:
    """Parse Siesta .MDE file (MD/relaxation trajectory)."""
    lines = mde_path.read_text().strip().split("\n")
    trajectory = []
    for line in lines:
        if line.startswith("#"):
            continue
        tokens = line.split()
        if len(tokens) >= 6:
            trajectory.append({
                "step": int(tokens[0]),
                "temperature_K": float(tokens[1]),
                "E_KS_eV": float(tokens[2]),
                "E_tot_eV": float(tokens[3]),
                "volume_ang3": float(tokens[4]),
                "pressure_kbar": float(tokens[5]),
            })
    return {"trajectory": trajectory, "n_steps": len(trajectory)}


def parse_dos_file(dos_path: Path) -> dict[str, Any]:
    """Parse Siesta .DOS file (energy vs DOS)."""
    lines = dos_path.read_text().strip().split("\n")
    energies = []
    dos_values = []
    for line in lines:
        tokens = line.split()
        if len(tokens) >= 2:
            try:
                energies.append(float(tokens[0]))
                dos_values.append(float(tokens[1]))
            except ValueError:
                continue
    return {"energies_eV": energies, "dos": dos_values, "n_points": len(energies)}


def parse_pdos_xml(pdos_path: Path) -> dict[str, Any]:
    """Parse Siesta .PDOS.xml file (projected DOS per orbital)."""
    tree = ET.parse(pdos_path)
    root = tree.getroot()

    nspin = int(root.find("nspin").text.strip())
    norbitals = int(root.find("norbitals").text.strip())
    fermi_energy = float(root.find("fermi_energy").text.strip())

    energy_text = root.find("energy_values").text.strip()
    energies = [float(x) for x in energy_text.split()]

    orbitals = []
    for orb in root.findall("orbital"):
        orb_info = dict(orb.attrib)
        data_text = orb.find("data").text.strip()
        data = [float(x) for x in data_text.split()]
        orb_info["data"] = data
        orbitals.append(orb_info)

    return {
        "nspin": nspin,
        "norbitals": norbitals,
        "fermi_energy_eV": fermi_energy,
        "energies_eV": energies,
        "orbitals": orbitals,
        "n_energy_points": len(energies),
    }


def parse_outvars_yml(yml_path: Path) -> dict[str, Any]:
    """Parse Siesta OUTVARS.yml file (energy decomposition)."""
    text = yml_path.read_text()
    result: dict[str, Any] = {}

    energy_keys = [
        "Ebs", "Eions", "Ena", "Ekin", "Enl", "Eso",
        "DEna", "DUscf", "Exc", "Eharris", "Etot", "FreeEng",
    ]
    for key in energy_keys:
        m = re.search(rf"{key}:\s+([-\d.E+]+)", text)
        if m:
            result[key] = float(m.group(1))

    return result


def check_normal_exit(workdir: Path) -> bool:
    """Check if Siesta completed normally (0_NORMAL_EXIT marker file)."""
    return (workdir / "0_NORMAL_EXIT").exists()


def parse_siesta_workdir(workdir: Path, system_label: str) -> dict[str, Any]:
    """Parse all available Siesta output files from a working directory.

    Args:
        workdir: Path to the Siesta working directory
        system_label: The SystemLabel used in the calculation

    Returns:
        Comprehensive dict with all parsed data
    """
    result: dict[str, Any] = {
        "system_label": system_label,
        "workdir": str(workdir),
        "normal_exit": check_normal_exit(workdir),
    }

    out_file = workdir / f"{system_label}.out"
    if out_file.exists():
        result["main_output"] = parse_main_output(out_file)

    eig_file = workdir / f"{system_label}.EIG"
    if eig_file.exists():
        result["eigenvalues"] = parse_eig_file(eig_file)

    fa_file = workdir / f"{system_label}.FA"
    if fa_file.exists():
        result["forces"] = parse_fa_file(fa_file)

    struct_file = workdir / f"{system_label}.STRUCT_OUT"
    if struct_file.exists():
        result["final_structure"] = parse_struct_out(struct_file)

    fs_file = workdir / "FORCE_STRESS"
    if fs_file.exists():
        result["force_stress"] = parse_force_stress(fs_file)

    yml_file = workdir / "OUTVARS.yml"
    if yml_file.exists():
        result["outvars"] = parse_outvars_yml(yml_file)

    mde_file = workdir / f"{system_label}.MDE"
    if mde_file.exists():
        result["trajectory"] = parse_mde_file(mde_file)

    dos_file = workdir / f"{system_label}.DOS"
    if dos_file.exists():
        result["dos"] = parse_dos_file(dos_file)

    pdos_file = workdir / f"{system_label}.PDOS.xml"
    if pdos_file.exists():
        result["pdos"] = parse_pdos_xml(pdos_file)

    return result
