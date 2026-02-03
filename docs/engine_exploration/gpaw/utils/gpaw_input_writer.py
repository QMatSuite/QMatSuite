"""
GPAW Input Writer Utility (temporary, for integration planning).

Unlike traditional DFT codes (QE, VASP), GPAW does not use text-based input files.
Instead, it uses Python scripts as input. This writer generates Python scripts
that set up ASE Atoms + GPAW calculator and execute the calculation.

This is the key architectural difference: GPAW's "input file" is a Python script.
"""
from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GPAWStepParams:
    """Parameters for a single GPAW calculation step."""

    # Step identity
    step_type_gen: str  # "scf", "bands", "dos", "relax", "md", "nscf"
    step_type_spec: str  # "gpaw_scf", "gpaw_bands", etc.

    # Calculation mode
    mode: str = "pw"  # "fd", "pw", "lcao"
    ecut: float = 400.0  # PW cutoff in eV (only for pw mode)
    h: float = 0.2  # Grid spacing in Angstrom (for fd/lcao modes)
    basis: str | None = None  # LCAO basis set (e.g., "dzp")

    # Exchange-correlation
    xc: str = "PBE"

    # K-points
    kpts: tuple[int, int, int] | dict[str, Any] | None = None

    # Electronic
    nbands: int | None = None  # None = auto, negative = N extra
    convergence: dict[str, float] = field(default_factory=dict)
    maxiter: int = 333
    occupations_name: str = "fermi-dirac"
    occupations_width: float = 0.1  # eV
    spinpol: bool | None = None
    charge: float = 0.0

    # Relaxation params (only for step_type_gen == "relax")
    optimizer: str = "BFGS"  # BFGS, LBFGS, FIRE
    fmax: float = 0.01  # eV/Ang
    relax_cell: bool = False  # Whether to relax cell shape/volume

    # Band structure params (only for step_type_gen == "bands")
    kpath: str | None = None  # e.g., "GXWKL"
    kpath_npoints: int = 60
    bands_nbands: int | None = None  # Number of bands for band structure

    # Output
    txt_file: str = "output.txt"  # Log file name
    gpw_file: str = "calc.gpw"  # Restart file name
    save_wf: bool = False  # Save wave functions in .gpw

    # Parallel
    parallel: dict[str, int] | None = None

    # Extra engine-specific parameters (raw dict for pass-through)
    extra_params: dict[str, Any] = field(default_factory=dict)


def write_gpaw_script(
    params: GPAWStepParams,
    structure_file: str | None = None,
    structure_dict: dict[str, Any] | None = None,
    output_path: Path | None = None,
    restart_from: str | None = None,
) -> str:
    """
    Generate a GPAW calculation Python script.

    Args:
        params: Step parameters.
        structure_file: Path to structure file (e.g., "structure.json", "POSCAR").
        structure_dict: Inline structure definition (cell, positions, symbols, pbc).
        output_path: If provided, write the script to this path.
        restart_from: Path to .gpw restart file for continuation.

    Returns:
        The generated Python script as a string.
    """
    lines: list[str] = []
    lines.append('"""Auto-generated GPAW calculation script."""')
    lines.append("import json")
    lines.append("import numpy as np")
    lines.append("from pathlib import Path")
    lines.append("from ase import Atoms")
    lines.append("from ase.io import read, write")
    lines.append("")

    # --- Structure setup ---
    if restart_from:
        lines.append(f"from gpaw import GPAW, restart")
        lines.append(f"atoms, calc_restart = restart('{restart_from}', txt=None)")
    elif structure_file:
        lines.append(f"atoms = read('{structure_file}')")
    elif structure_dict:
        cell_str = json.dumps(structure_dict["cell"])
        pos_str = json.dumps(structure_dict["positions"])
        sym_str = json.dumps(structure_dict["symbols"])
        pbc_str = json.dumps(structure_dict.get("pbc", [True, True, True]))
        lines.append(f"atoms = Atoms(")
        lines.append(f"    symbols={sym_str},")
        lines.append(f"    positions={pos_str},")
        lines.append(f"    cell={cell_str},")
        lines.append(f"    pbc={pbc_str},")
        lines.append(f")")
    else:
        lines.append("# ERROR: No structure source specified")
        lines.append("raise ValueError('No structure source')")

    lines.append("")

    # --- Calculator setup ---
    if params.step_type_gen == "bands" and restart_from:
        # Band structure uses fixed_density from restart
        lines.append(f"from gpaw import GPAW")
        fd_args = []
        if params.bands_nbands:
            fd_args.append(f"    nbands={params.bands_nbands},")
        fd_args.append("    symmetry='off',")
        if params.kpath:
            fd_args.append(
                f"    kpts={{'path': '{params.kpath}', 'npoints': {params.kpath_npoints}}},"
            )
        if params.convergence:
            fd_args.append(f"    convergence={params.convergence},")
        fd_args.append(f"    txt='{params.txt_file}',")

        lines.append(f"calc = GPAW('{restart_from}').fixed_density(")
        lines.extend(fd_args)
        lines.append(")")
        lines.append("")
        lines.append("bs = calc.band_structure()")
        lines.append("bs.write('bandstructure.json')")
        lines.append(f"calc.write('{params.gpw_file}')")
        lines.append("")
        lines.append("# Save results")
        lines.append("results = {")
        lines.append("    'reference_eV': float(bs.reference),")
        lines.append("    'energies_shape': list(bs.energies.shape),")
        lines.append("}")
        lines.append("with open('results.json', 'w') as f:")
        lines.append("    json.dump(results, f, indent=2)")

    elif params.step_type_gen == "dos" and restart_from:
        # DOS from restart
        lines.append("from gpaw import GPAW")
        lines.append("from ase.dft.dos import DOS")
        lines.append(f"calc = GPAW('{restart_from}', txt=None)")
        lines.append(f"dos = DOS(calc, npts=500, width=0.1)")
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

    else:
        # Standard SCF / NSCF / Relax / MD
        lines.append("from gpaw import GPAW, PW, FermiDirac")
        lines.append("")

        # Build mode argument
        if params.mode == "pw":
            mode_str = f"PW({params.ecut})"
        elif params.mode == "lcao":
            mode_str = "'lcao'"
        else:
            mode_str = "'fd'"

        # Build calculator
        calc_args = [f"    mode={mode_str},"]
        calc_args.append(f"    xc='{params.xc}',")

        if params.kpts:
            if isinstance(params.kpts, tuple):
                calc_args.append(f"    kpts={params.kpts},")
            else:
                calc_args.append(f"    kpts={params.kpts},")

        if params.convergence:
            calc_args.append(f"    convergence={params.convergence},")

        calc_args.append(
            f"    occupations=FermiDirac({params.occupations_width}),"
        )

        if params.nbands is not None:
            calc_args.append(f"    nbands={params.nbands},")

        calc_args.append(f"    maxiter={params.maxiter},")
        calc_args.append(f"    txt='{params.txt_file}',")

        if params.mode == "lcao" and params.basis:
            calc_args.append(f"    basis='{params.basis}',")

        if params.mode == "fd":
            calc_args.append(f"    h={params.h},")

        if params.spinpol is not None:
            calc_args.append(f"    spinpol={params.spinpol},")

        if params.charge != 0.0:
            calc_args.append(f"    charge={params.charge},")

        if params.parallel:
            calc_args.append(f"    parallel={params.parallel},")

        # Extra params
        for k, v in params.extra_params.items():
            calc_args.append(f"    {k}={repr(v)},")

        # Symmetry off for band structure follow-up compatibility
        calc_args.append("    symmetry={'point_group': False},")

        lines.append("calc = GPAW(")
        lines.extend(calc_args)
        lines.append(")")
        lines.append("atoms.calc = calc")
        lines.append("")

        if params.step_type_gen == "relax":
            # Relaxation
            lines.append(f"from ase.optimize import {params.optimizer}")
            if params.relax_cell:
                lines.append("from ase.filters import FrechetCellFilter")
                lines.append("filtered = FrechetCellFilter(atoms)")
                lines.append(
                    f"opt = {params.optimizer}(filtered, trajectory='relax.traj', logfile='opt.log')"
                )
            else:
                lines.append(
                    f"opt = {params.optimizer}(atoms, trajectory='relax.traj', logfile='opt.log')"
                )
            lines.append(f"opt.run(fmax={params.fmax})")
            lines.append("")
            lines.append("energy = atoms.get_potential_energy()")
            lines.append("forces = atoms.get_forces()")
        else:
            # SCF / NSCF
            lines.append("energy = atoms.get_potential_energy()")
            lines.append("forces = atoms.get_forces()")

        lines.append("")

        # Save results
        gpw_mode = "mode='all'" if params.save_wf else ""
        lines.append(f"calc.write('{params.gpw_file}'{', ' + gpw_mode if gpw_mode else ''})")
        lines.append("")
        lines.append("# Save structured results")
        lines.append("results = {")
        lines.append("    'total_energy_eV': float(energy),")
        lines.append("    'fermi_level_eV': float(calc.get_fermi_level()),")
        lines.append("    'forces_eV_per_ang': forces.tolist(),")
        lines.append("    'n_bands': int(calc.get_number_of_bands()),")
        lines.append("    'n_spins': int(calc.get_number_of_spins()),")
        lines.append("    'converged': True,")
        lines.append("}")

        if params.step_type_gen == "relax":
            lines.append("results['n_opt_steps'] = opt.nsteps")
            lines.append("results['positions_ang'] = atoms.get_positions().tolist()")
            lines.append("results['cell'] = atoms.cell.tolist()")
            lines.append("# Write relaxed structure")
            lines.append("write('relaxed_structure.json', atoms)")

        lines.append("")
        lines.append("with open('results.json', 'w') as f:")
        lines.append("    json.dump(results, f, indent=2)")
        lines.append("")
        lines.append("print(f'Energy: {energy:.6f} eV')")
        lines.append("print('Done.')")

    script = "\n".join(lines) + "\n"

    if output_path:
        output_path.write_text(script)

    return script


# --- Test the writer ---
if __name__ == "__main__":
    # Test 1: SCF script
    params_scf = GPAWStepParams(
        step_type_gen="scf",
        step_type_spec="gpaw_scf",
        mode="pw",
        ecut=300,
        xc="PBE",
        kpts=(4, 4, 4),
        nbands=-4,
        convergence={"energy": 0.0005, "density": 1e-4},
        txt_file="scf.txt",
        gpw_file="scf.gpw",
    )
    script = write_gpaw_script(
        params_scf,
        structure_dict={
            "symbols": ["Si", "Si"],
            "positions": [[0, 0, 0], [1.3575, 1.3575, 1.3575]],
            "cell": [[0, 2.715, 2.715], [2.715, 0, 2.715], [2.715, 2.715, 0]],
            "pbc": [True, True, True],
        },
    )
    print("=== SCF Script ===")
    print(script)
    print()

    # Test 2: Band structure script (from restart)
    params_bands = GPAWStepParams(
        step_type_gen="bands",
        step_type_spec="gpaw_bands",
        kpath="GXWKL",
        kpath_npoints=60,
        bands_nbands=16,
        convergence={"bands": 8},
        txt_file="bands.txt",
        gpw_file="bands.gpw",
    )
    script = write_gpaw_script(params_bands, restart_from="scf.gpw")
    print("=== Bands Script ===")
    print(script)
    print()

    # Test 3: Relax script
    params_relax = GPAWStepParams(
        step_type_gen="relax",
        step_type_spec="gpaw_relax",
        mode="fd",
        h=0.2,
        xc="PBE",
        optimizer="BFGS",
        fmax=0.05,
        txt_file="relax.txt",
        gpw_file="relaxed.gpw",
    )
    script = write_gpaw_script(
        params_relax,
        structure_file="structure.json",
    )
    print("=== Relax Script ===")
    print(script)
