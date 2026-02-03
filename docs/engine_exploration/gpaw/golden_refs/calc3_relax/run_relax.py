"""
Calc 3: H2O molecule geometry relaxation (relax topology).
Demonstrates ASE optimizer + GPAW forces.
"""
import json
import numpy as np
from ase import Atoms
from ase.optimize import BFGS
from gpaw import GPAW

# Build H2O with slightly wrong geometry
h2o = Atoms('H2O',
            positions=[
                [0.0, 0.0, 0.0],    # O
                [0.96, 0.0, 0.0],   # H (slightly long)
                [-0.24, 0.93, 0.0], # H (slightly wrong angle)
            ])
h2o.center(vacuum=4.0)

# Use FD mode for molecules (no PBC needed)
calc = GPAW(
    mode='fd',
    h=0.25,                     # Grid spacing
    xc='PBE',
    convergence={
        'energy': 0.0005,
        'density': 1e-4,
    },
    maxiter=100,
    txt='relax.txt',
)

h2o.calc = calc

# Run relaxation with BFGS optimizer
opt = BFGS(h2o, trajectory='relax.traj', logfile='opt.log')
opt.run(fmax=0.05)

# Get final results
energy = h2o.get_potential_energy()
forces = h2o.get_forces()
positions = h2o.get_positions()

print(f"Final energy: {energy:.6f} eV")
print(f"Max force: {np.max(np.abs(forces)):.6f} eV/Ang")
print(f"Final positions:\n{positions}")

# Calculate bond lengths and angle
d_OH1 = np.linalg.norm(positions[1] - positions[0])
d_OH2 = np.linalg.norm(positions[2] - positions[0])
v1 = positions[1] - positions[0]
v2 = positions[2] - positions[0]
cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
angle = np.degrees(np.arccos(cos_angle))

print(f"\nO-H bond lengths: {d_OH1:.4f}, {d_OH2:.4f} Ang")
print(f"H-O-H angle: {angle:.2f} degrees")

# Save restart file
calc.write('h2o_relaxed.gpw')

# Save results
results = {
    'total_energy_eV': energy,
    'max_force_eV_per_ang': float(np.max(np.abs(forces))),
    'forces_eV_per_ang': forces.tolist(),
    'positions_ang': positions.tolist(),
    'symbols': list(h2o.get_chemical_symbols()),
    'cell': h2o.cell.tolist(),
    'pbc': h2o.pbc.tolist(),
    'oh_bond_1_ang': d_OH1,
    'oh_bond_2_ang': d_OH2,
    'hoh_angle_deg': angle,
    'n_opt_steps': opt.nsteps,
}

with open('results.json', 'w') as f:
    json.dump(results, f, indent=2)

# Read trajectory to get optimization history
from ase.io import read
traj = read('relax.traj', index=':')
opt_history = []
for i, atoms in enumerate(traj):
    e = atoms.get_potential_energy()
    f = atoms.get_forces()
    fmax = np.max(np.linalg.norm(f, axis=1))
    opt_history.append({
        'step': i,
        'energy_eV': e,
        'fmax_eV_per_ang': float(fmax),
    })

with open('opt_history.json', 'w') as f:
    json.dump(opt_history, f, indent=2)

print("\nDone! Files: relax.txt, relax.traj, opt.log, h2o_relaxed.gpw,")
print("  results.json, opt_history.json")
