"""MACE script template generator (stdlib only, P5 compliant).

Generates Python scripts that set up ASE Atoms + MACE calculator and execute
the calculation. MACE's "input file" is a Python script (like GPAW/PySCF).

Output files:
- results.json: Final results (energy, forces, stress, metadata)
- trajectory.jsonl: Trajectory frames for relax/md (one JSON object per line)
- final_structure.json: Final atomic structure (relax/md)
"""

from __future__ import annotations

import json
from typing import Any


def write_mace_script_text(
    gen_type: str,
    params: dict[str, Any],
    structure_file: str = "structure.json",
) -> str:
    """Generate a MACE calculation Python script.

    Args:
        gen_type: Generalized step type (scf, relax, md).
        params: Step parameters dict.
        structure_file: Path to structure file (relative to working dir).

    Returns:
        Python script text.
    """
    lines: list[str] = []
    lines.append('"""Auto-generated MACE calculation script."""')
    lines.append("import json")
    lines.append("import time")
    lines.append("import numpy as np")
    lines.append("from pathlib import Path")
    lines.append("from ase import Atoms")
    lines.append("")

    # Load structure
    lines.append(f"with open('{structure_file}') as _sf:")
    lines.append("    _struct = json.load(_sf)")
    lines.append("atoms = Atoms(")
    lines.append("    symbols=_struct['symbols'],")
    lines.append("    positions=_struct['positions'],")
    lines.append("    cell=_struct.get('cell'),")
    lines.append("    pbc=_struct.get('pbc', [True, True, True]),")
    lines.append(")")
    lines.append("")

    # Setup calculator
    _write_calculator_setup(lines, params)

    # Dispatch to gen_type
    if gen_type == "scf":
        _write_scf_body(lines, params)
    elif gen_type == "relax":
        _write_relax_body(lines, params)
    elif gen_type == "md":
        _write_md_body(lines, params)
    else:
        raise ValueError(f"Unknown gen_type: {gen_type!r}")

    return "\n".join(lines) + "\n"


def write_structure_json_text(structure: dict[str, Any] | None) -> str:
    """Convert StructureDoc to ASE-compatible JSON text.

    Args:
        structure: Dict with lattice/species/frac_coords or positions.

    Returns:
        JSON text for structure.json.
    """
    if not structure:
        return "{}"

    species = structure.get("species", [])
    lattice = structure.get("lattice")
    frac_coords = structure.get("frac_coords")
    positions = structure.get("positions")

    data: dict[str, Any] = {"symbols": species}

    if positions:
        data["positions"] = positions
    elif frac_coords and lattice:
        # Convert fractional to Cartesian
        import_lattice = [list(row) for row in lattice]
        cart = []
        for fc in frac_coords:
            x = sum(fc[j] * import_lattice[j][i] for j in range(3) for i in [0]) if False else 0
            pos = [
                sum(fc[j] * import_lattice[j][i] for j in range(3))
                for i in range(3)
            ]
            cart.append(pos)
        data["positions"] = cart
    else:
        data["positions"] = []

    if lattice:
        data["cell"] = [list(row) for row in lattice]

    data["pbc"] = [True, True, True] if lattice else [False, False, False]

    return json.dumps(data, indent=2) + "\n"


def _write_calculator_setup(lines: list[str], params: dict[str, Any]) -> None:
    """Generate calculator creation code."""
    model_type = params.get("model_type", "foundation")
    model_paths = params.get("model_paths")
    foundation_model = params.get("foundation_model", "mace_mp")
    model = params.get("model", "medium")
    device = params.get("device", "cpu")
    default_dtype = params.get("default_dtype", "float64")
    dispersion = params.get("dispersion", False)

    lines.append("# Setup MACE calculator")

    if model_type == "custom" and model_paths:
        lines.append("from mace.calculators import MACECalculator")
        calc_args = [f"    model_paths='{model_paths}',"]
        calc_args.append(f"    device='{device}',")
        calc_args.append(f"    default_dtype='{default_dtype}',")

        energy_units = params.get("energy_units_to_eV", 1.0)
        length_units = params.get("length_units_to_A", 1.0)
        if energy_units != 1.0:
            calc_args.append(f"    energy_units_to_eV={energy_units},")
        if length_units != 1.0:
            calc_args.append(f"    length_units_to_A={length_units},")

        lines.append("calc = MACECalculator(")
        lines.extend(calc_args)
        lines.append(")")
    else:
        if foundation_model == "mace_off":
            lines.append("from mace.calculators import mace_off")
            lines.append(f"calc = mace_off(model='{model}', device='{device}', default_dtype='{default_dtype}')")
        else:
            lines.append("from mace.calculators import mace_mp")
            calc_args = [
                f"model='{model}'",
                f"device='{device}'",
                f"default_dtype='{default_dtype}'",
            ]
            if dispersion:
                calc_args.append("dispersion=True")
            lines.append(f"calc = mace_mp({', '.join(calc_args)})")

    lines.append("atoms.calc = calc")
    lines.append("")
    lines.append("_start_time = time.time()")
    lines.append("")


def _write_scf_body(lines: list[str], params: dict[str, Any]) -> None:
    """Generate SCF (single-point) calculation body."""
    compute_stress = params.get("compute_stress", True)

    lines.append("# Single-point calculation")
    lines.append("energy = atoms.get_potential_energy()")
    lines.append("forces = atoms.get_forces()")
    if compute_stress:
        lines.append("stress = atoms.get_stress(voigt=True)  # 6-element Voigt")
    lines.append("")
    lines.append("_wall_time = time.time() - _start_time")
    lines.append("")
    lines.append("results = {")
    lines.append("    'calc_type': 'scf',")
    lines.append("    'success': True,")
    lines.append("    'total_energy_eV': float(energy),")
    lines.append("    'energy_per_atom_eV': float(energy) / len(atoms),")
    lines.append("    'forces_eV_per_ang': forces.tolist(),")
    lines.append("    'max_force_eV_per_ang': float(np.max(np.linalg.norm(forces, axis=1))),")
    if compute_stress:
        lines.append("    'stress_eV_per_ang3': stress.tolist(),")
    lines.append("    'n_atoms': len(atoms),")
    lines.append(f"    'model_name': '{params.get('model', 'medium')}',")
    lines.append("    'converged': True,")
    lines.append("    'wall_time_s': _wall_time,")
    lines.append("    'final_species': atoms.get_chemical_symbols(),")
    lines.append("    'final_positions': atoms.get_positions().tolist(),")
    lines.append("    'final_cell': atoms.cell.tolist(),")
    lines.append("}")
    lines.append("")
    _write_results_output(lines, params)


def _write_relax_body(lines: list[str], params: dict[str, Any]) -> None:
    """Generate relaxation body."""
    optimizer = params.get("optimizer", "BFGS")
    fmax = params.get("fmax", 0.05)
    max_steps = params.get("max_steps", 500)
    relax_cell = params.get("relax_cell", False)
    cell_filter = params.get("cell_filter", "FrechetCellFilter")
    traj_file = params.get("opt_trajectory", "trajectory.jsonl")

    lines.append("# Geometry optimization")
    lines.append(f"from ase.optimize import {optimizer}")
    lines.append("")

    # Trajectory callback for JSONL output
    lines.append(f"_traj_file = open('{traj_file}', 'w')")
    lines.append("_frame_idx = 0")
    lines.append("")
    lines.append("def _write_traj_frame():")
    lines.append("    global _frame_idx")
    lines.append("    frame = {")
    lines.append("        'frame_index': _frame_idx,")
    lines.append("        'energy_eV': float(atoms.get_potential_energy()),")
    lines.append("        'forces_eV_per_ang': atoms.get_forces().tolist(),")
    lines.append("        'max_force_eV_per_ang': float(np.max(np.linalg.norm(atoms.get_forces(), axis=1))),")
    lines.append("        'positions': atoms.get_positions().tolist(),")
    lines.append("        'species': atoms.get_chemical_symbols(),")
    lines.append("        'cell': atoms.cell.tolist(),")
    lines.append("    }")
    lines.append("    _traj_file.write(json.dumps(frame) + '\\n')")
    lines.append("    _frame_idx += 1")
    lines.append("")

    if relax_cell:
        lines.append(f"from ase.filters import {cell_filter}")
        hp = params.get("hydrostatic_strain", False)
        sp = params.get("scalar_pressure", 0.0)
        filter_args = ["atoms"]
        if hp:
            filter_args.append("hydrostatic_strain=True")
        if sp != 0.0:
            filter_args.append(f"scalar_pressure={sp}")
        cf = params.get("cell_factor")
        if cf is not None:
            filter_args.append(f"cell_factor={cf}")
        lines.append(f"filtered = {cell_filter}({', '.join(filter_args)})")
        lines.append(f"opt = {optimizer}(filtered, logfile='opt.log')")
    else:
        lines.append(f"opt = {optimizer}(atoms, logfile='opt.log')")

    lines.append("opt.attach(_write_traj_frame)")
    lines.append("_write_traj_frame()  # Write initial frame")
    lines.append(f"opt.run(fmax={fmax}, steps={max_steps})")
    lines.append("_traj_file.close()")
    lines.append("")

    lines.append("energy = atoms.get_potential_energy()")
    lines.append("forces = atoms.get_forces()")
    lines.append("_wall_time = time.time() - _start_time")
    lines.append("")

    # Write final structure
    lines.append("final_struct = {")
    lines.append("    'symbols': atoms.get_chemical_symbols(),")
    lines.append("    'positions': atoms.get_positions().tolist(),")
    lines.append("    'cell': atoms.cell.tolist(),")
    lines.append("    'pbc': [bool(x) for x in atoms.pbc],")
    lines.append("}")
    lines.append("with open('final_structure.json', 'w') as f:")
    lines.append("    json.dump(final_struct, f, indent=2)")
    lines.append("")

    lines.append("results = {")
    lines.append("    'calc_type': 'relax',")
    lines.append("    'success': True,")
    lines.append("    'total_energy_eV': float(energy),")
    lines.append("    'energy_per_atom_eV': float(energy) / len(atoms),")
    lines.append("    'forces_eV_per_ang': forces.tolist(),")
    lines.append("    'max_force_eV_per_ang': float(np.max(np.linalg.norm(forces, axis=1))),")
    lines.append(f"    'converged': float(np.max(np.linalg.norm(forces, axis=1))) <= {fmax},")
    lines.append("    'n_opt_steps': opt.nsteps,")
    lines.append("    'n_atoms': len(atoms),")
    lines.append(f"    'model_name': '{params.get('model', 'medium')}',")
    lines.append("    'wall_time_s': _wall_time,")
    lines.append("    'final_species': atoms.get_chemical_symbols(),")
    lines.append("    'final_positions': atoms.get_positions().tolist(),")
    lines.append("    'final_cell': atoms.cell.tolist(),")
    lines.append("}")
    lines.append("")
    _write_results_output(lines, params)


def _write_md_body(lines: list[str], params: dict[str, Any]) -> None:
    """Generate MD body."""
    ensemble = params.get("md_ensemble", "NVT")
    timestep = params.get("md_timestep", 1.0)
    nsteps = params.get("md_nsteps", 1000)
    temperature = params.get("md_temperature", 300.0)
    friction = params.get("md_friction", 0.01)
    log_interval = params.get("md_log_interval", 10)
    traj_file = params.get("md_trajectory", "trajectory.jsonl")
    init_temp = params.get("md_init_temperature", temperature)

    lines.append("# Molecular dynamics")
    lines.append("from ase import units")
    lines.append("from ase.md.velocitydistribution import MaxwellBoltzmannDistribution")
    lines.append("")

    # Initialize velocities
    lines.append(f"MaxwellBoltzmannDistribution(atoms, temperature_K={init_temp})")
    lines.append("")

    # Setup dynamics
    if ensemble == "NVT":
        lines.append("from ase.md.langevin import Langevin")
        lines.append(
            f"dyn = Langevin(atoms, {timestep} * units.fs, "
            f"temperature_K={temperature}, friction={friction})"
        )
    elif ensemble == "NPT":
        pressure = params.get("npt_pressure", 1.01325)
        ttime = params.get("npt_ttime", 25.0)
        pfactor = params.get("npt_pfactor")
        lines.append("from ase.md.npt import NPT")
        npt_args = [
            "atoms",
            f"{timestep} * units.fs",
            f"temperature_K={temperature}",
        ]
        npt_args.append(f"externalstress={pressure} * units.bar")
        npt_args.append(f"ttime={ttime} * units.fs")
        if pfactor is not None:
            npt_args.append(f"pfactor={pfactor}")
        mask = params.get("npt_mask")
        if mask:
            npt_args.append(f"mask={mask}")
        lines.append(f"dyn = NPT({', '.join(npt_args)})")
    else:
        # NVE
        lines.append("from ase.md.verlet import VelocityVerlet")
        lines.append(f"dyn = VelocityVerlet(atoms, {timestep} * units.fs)")

    lines.append("")

    # Trajectory callback
    lines.append(f"_traj_file = open('{traj_file}', 'w')")
    lines.append("_frame_idx = 0")
    lines.append(f"_log_interval = {log_interval}")
    lines.append("_step_counter = 0")
    lines.append("")
    lines.append("def _write_md_frame():")
    lines.append("    global _frame_idx, _step_counter")
    lines.append("    if _step_counter % _log_interval == 0:")
    lines.append("        e_pot = float(atoms.get_potential_energy())")
    lines.append("        e_kin = float(atoms.get_kinetic_energy())")
    lines.append("        temp = float(e_kin / (1.5 * units.kB * len(atoms)))")
    lines.append("        frame = {")
    lines.append("            'frame_index': _frame_idx,")
    lines.append(f"            'time_fs': _step_counter * {timestep},")
    lines.append("            'energy_eV': e_pot,")
    lines.append("            'kinetic_energy_eV': e_kin,")
    lines.append("            'temperature_K': temp,")
    lines.append("            'forces_eV_per_ang': atoms.get_forces().tolist(),")
    lines.append("            'positions': atoms.get_positions().tolist(),")
    lines.append("            'species': atoms.get_chemical_symbols(),")
    lines.append("            'cell': atoms.cell.tolist(),")
    lines.append("        }")
    lines.append("        _traj_file.write(json.dumps(frame) + '\\n')")
    lines.append("        _frame_idx += 1")
    lines.append("    _step_counter += 1")
    lines.append("")

    lines.append("dyn.attach(_write_md_frame, interval=1)")
    lines.append("_write_md_frame()  # Write initial frame")
    lines.append(f"dyn.run({nsteps})")
    lines.append("_traj_file.close()")
    lines.append("")

    lines.append("energy = atoms.get_potential_energy()")
    lines.append("_wall_time = time.time() - _start_time")
    lines.append("")

    # Write final structure
    lines.append("final_struct = {")
    lines.append("    'symbols': atoms.get_chemical_symbols(),")
    lines.append("    'positions': atoms.get_positions().tolist(),")
    lines.append("    'cell': atoms.cell.tolist(),")
    lines.append("    'pbc': [bool(x) for x in atoms.pbc],")
    lines.append("}")
    lines.append("with open('final_structure.json', 'w') as f:")
    lines.append("    json.dump(final_struct, f, indent=2)")
    lines.append("")

    lines.append("results = {")
    lines.append("    'calc_type': 'md',")
    lines.append("    'success': True,")
    lines.append("    'total_energy_eV': float(energy),")
    lines.append("    'energy_per_atom_eV': float(energy) / len(atoms),")
    lines.append(f"    'n_md_steps': {nsteps},")
    lines.append(f"    'md_ensemble': '{ensemble}',")
    lines.append(f"    'md_temperature_K': {temperature},")
    lines.append(f"    'md_timestep_fs': {timestep},")
    lines.append("    'n_atoms': len(atoms),")
    lines.append(f"    'model_name': '{params.get('model', 'medium')}',")
    lines.append("    'wall_time_s': _wall_time,")
    lines.append("    'final_species': atoms.get_chemical_symbols(),")
    lines.append("    'final_positions': atoms.get_positions().tolist(),")
    lines.append("    'final_cell': atoms.cell.tolist(),")
    lines.append("}")
    lines.append("")
    _write_results_output(lines, params)


def _write_results_output(lines: list[str], params: dict[str, Any]) -> None:
    """Write results.json output."""
    results_file = params.get("results_file", "results.json")
    lines.append(f"with open('{results_file}', 'w') as f:")
    lines.append("    json.dump(results, f, indent=2)")
    lines.append("")
    lines.append("print(f\"Energy: {results['total_energy_eV']:.6f} eV\")")
    lines.append("print('Done.')")
