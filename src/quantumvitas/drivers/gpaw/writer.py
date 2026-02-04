"""GPAW input writer.

Generates Python scripts that set up ASE Atoms + GPAW calculator
and execute the calculation. GPAW's "input file" is a Python script.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_gpaw_script(
    gen_type: str,
    params: dict[str, Any],
    output_path: Path,
    structure_file: str = "structure.json",
    restart_from: str | None = None,
) -> Path:
    """
    Generate a GPAW calculation Python script.

    Args:
        gen_type: Generalized step type (scf, nscf, bandspw, dos, relax, md).
        params: Step parameters dict.
        output_path: Path to write the generated script.
        structure_file: Path to structure file (relative to working dir).
        restart_from: Path to .gpw restart file for continuation.

    Returns:
        The output_path.
    """
    lines: list[str] = []
    lines.append('"""Auto-generated GPAW calculation script."""')
    lines.append("import json")
    lines.append("import numpy as np")
    lines.append("from pathlib import Path")
    lines.append("from ase import Atoms")
    lines.append("from ase.io import read, write")
    lines.append("")

    txt_file = params.get("txt_file", f"{gen_type}.txt")
    gpw_file = params.get("gpw_file", f"{gen_type}.gpw")

    if gen_type == "bandspw" and restart_from:
        _write_bands_script(lines, params, restart_from, txt_file, gpw_file)
    elif gen_type == "dos" and restart_from:
        _write_dos_script(lines, params, restart_from)
    else:
        _write_standard_script(
            lines, gen_type, params, structure_file, txt_file, gpw_file,
        )

    script = "\n".join(lines) + "\n"
    output_path.write_text(script)
    return output_path


def _write_bands_script(
    lines: list[str],
    params: dict[str, Any],
    restart_from: str,
    txt_file: str,
    gpw_file: str,
) -> None:
    """Generate band structure calculation script."""
    kpath = params.get("kpath", "GXWK")
    kpath_npoints = params.get("kpath_npoints", 60)
    bands_nbands = params.get("bands_nbands")

    lines.append("from gpaw import GPAW")
    lines.append("")

    fd_args = []
    if bands_nbands:
        fd_args.append(f"    nbands={bands_nbands},")
    fd_args.append("    symmetry='off',")
    fd_args.append(f"    kpts={{'path': '{kpath}', 'npoints': {kpath_npoints}}},")
    if params.get("convergence"):
        fd_args.append(f"    convergence={params['convergence']},")
    fd_args.append(f"    txt='{txt_file}',")

    lines.append(f"calc = GPAW('{restart_from}').fixed_density(")
    lines.extend(fd_args)
    lines.append(")")
    lines.append("")
    lines.append("bs = calc.band_structure()")
    lines.append("bs.write('bandstructure.json')")
    lines.append(f"calc.write('{gpw_file}')")
    lines.append("")
    lines.append("results = {")
    lines.append("    'reference_eV': float(bs.reference),")
    lines.append("    'energies_shape': list(bs.energies.shape),")
    lines.append("}")
    lines.append("with open('results.json', 'w') as f:")
    lines.append("    json.dump(results, f, indent=2)")


def _write_dos_script(
    lines: list[str],
    params: dict[str, Any],
    restart_from: str,
) -> None:
    """Generate DOS calculation script."""
    npts = params.get("dos_npts", 500)
    width = params.get("dos_width", 0.1)

    lines.append("from gpaw import GPAW")
    lines.append("from ase.dft.dos import DOS")
    lines.append(f"calc = GPAW('{restart_from}', txt=None)")
    lines.append(f"dos = DOS(calc, npts={npts}, width={width})")
    lines.append("energies = dos.get_energies()")
    lines.append("weights = dos.get_dos()")
    lines.append("")
    lines.append("dos_data = {")
    lines.append("    'energies_eV': energies.tolist(),")
    lines.append("    'dos': weights.tolist(),")
    lines.append("    'fermi_eV': float(calc.get_fermi_level()),")
    lines.append("}")
    lines.append("with open('dos.json', 'w') as f:")
    lines.append("    json.dump(dos_data, f, indent=2)")
    lines.append("")
    lines.append("results = {")
    lines.append("    'n_points': len(energies),")
    lines.append("    'fermi_eV': float(calc.get_fermi_level()),")
    lines.append("}")
    lines.append("with open('results.json', 'w') as f:")
    lines.append("    json.dump(results, f, indent=2)")


def _write_standard_script(
    lines: list[str],
    gen_type: str,
    params: dict[str, Any],
    structure_file: str,
    txt_file: str,
    gpw_file: str,
) -> None:
    """Generate standard SCF/NSCF/relax/MD script."""
    lines.append("from gpaw import GPAW, PW, FermiDirac")
    lines.append("")
    lines.append(f"atoms = read('{structure_file}')")
    lines.append("")

    mode = params.get("mode", "pw")
    ecut = params.get("ecut", 400.0)
    h = params.get("h", 0.2)
    xc = params.get("xc", "PBE")
    kpts = params.get("kpts")
    nbands = params.get("nbands")
    convergence = params.get("convergence")
    maxiter = params.get("maxiter", 333)
    occ_width = params.get("occupations_width", 0.1)
    spinpol = params.get("spinpol")
    charge = params.get("charge", 0.0)
    basis = params.get("basis")
    parallel = params.get("parallel")
    save_wf = params.get("save_wf", False)

    # Mode argument
    if mode == "pw":
        mode_str = f"PW({ecut})"
    elif mode == "lcao":
        mode_str = "'lcao'"
    else:
        mode_str = "'fd'"

    calc_args = [f"    mode={mode_str},"]
    calc_args.append(f"    xc='{xc}',")

    if kpts:
        calc_args.append(f"    kpts={kpts},")

    if convergence:
        calc_args.append(f"    convergence={convergence},")

    calc_args.append(f"    occupations=FermiDirac({occ_width}),")

    if nbands is not None:
        calc_args.append(f"    nbands={nbands},")

    calc_args.append(f"    maxiter={maxiter},")
    calc_args.append(f"    txt='{txt_file}',")

    if mode == "lcao" and basis:
        calc_args.append(f"    basis='{basis}',")

    if mode == "fd":
        calc_args.append(f"    h={h},")

    if spinpol is not None:
        calc_args.append(f"    spinpol={spinpol},")

    if charge != 0.0:
        calc_args.append(f"    charge={charge},")

    if parallel:
        calc_args.append(f"    parallel={parallel},")

    calc_args.append("    symmetry={'point_group': False},")

    lines.append("calc = GPAW(")
    lines.extend(calc_args)
    lines.append(")")
    lines.append("atoms.calc = calc")
    lines.append("")

    if gen_type == "relax":
        optimizer = params.get("optimizer", "BFGS")
        fmax = params.get("fmax", 0.05)
        relax_cell = params.get("relax_cell", False)

        lines.append(f"from ase.optimize import {optimizer}")
        if relax_cell:
            lines.append("from ase.filters import FrechetCellFilter")
            lines.append("filtered = FrechetCellFilter(atoms)")
            lines.append(
                f"opt = {optimizer}(filtered, trajectory='relax.traj', logfile='opt.log')"
            )
        else:
            lines.append(
                f"opt = {optimizer}(atoms, trajectory='relax.traj', logfile='opt.log')"
            )
        lines.append(f"opt.run(fmax={fmax})")
        lines.append("")
        lines.append("energy = atoms.get_potential_energy()")
        lines.append("forces = atoms.get_forces()")
    elif gen_type == "md":
        ensemble = params.get("md_ensemble", "NVE")
        timestep = params.get("md_timestep", 1.0)  # fs
        nsteps = params.get("md_nsteps", 100)
        temperature = params.get("md_temperature", 300)  # K

        if ensemble == "NVT":
            lines.append("from ase.md.langevin import Langevin")
            lines.append("from ase import units")
            lines.append(
                f"dyn = Langevin(atoms, {timestep} * units.fs, "
                f"temperature_K={temperature}, friction=0.01)"
            )
        else:
            lines.append("from ase.md.verlet import VelocityVerlet")
            lines.append("from ase import units")
            lines.append(f"dyn = VelocityVerlet(atoms, {timestep} * units.fs)")

        lines.append("from ase.io.trajectory import Trajectory")
        lines.append("traj = Trajectory('md.traj', 'w', atoms)")
        lines.append("dyn.attach(traj.write, interval=1)")
        lines.append(f"dyn.run({nsteps})")
        lines.append("traj.close()")
        lines.append("")
        lines.append("energy = atoms.get_potential_energy()")
        lines.append("forces = atoms.get_forces()")
    else:
        # SCF / NSCF
        lines.append("energy = atoms.get_potential_energy()")
        lines.append("forces = atoms.get_forces()")

    lines.append("")

    gpw_mode = ", mode='all'" if save_wf else ""
    lines.append(f"calc.write('{gpw_file}'{gpw_mode})")
    lines.append("")
    lines.append("results = {")
    lines.append("    'total_energy_eV': float(energy),")
    lines.append("    'fermi_level_eV': float(calc.get_fermi_level()),")
    lines.append("    'forces_eV_per_ang': forces.tolist(),")
    lines.append("    'n_bands': int(calc.get_number_of_bands()),")
    lines.append("    'n_spins': int(calc.get_number_of_spins()),")
    lines.append("    'converged': True,")
    lines.append("}")

    if gen_type == "relax":
        lines.append("results['n_opt_steps'] = opt.nsteps")
        lines.append("results['positions_ang'] = atoms.get_positions().tolist()")
        lines.append("results['cell'] = atoms.cell.tolist()")
        lines.append("write('relaxed_structure.json', atoms)")

    if gen_type == "md":
        lines.append(f"results['n_md_steps'] = {nsteps}")
        lines.append("results['positions_ang'] = atoms.get_positions().tolist()")

    lines.append("")
    lines.append("with open('results.json', 'w') as f:")
    lines.append("    json.dump(results, f, indent=2)")
    lines.append("")
    lines.append("print(f'Energy: {energy:.6f} eV')")
    lines.append("print('Done.')")
