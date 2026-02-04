"""
Calc 1: Si bulk SCF ground state calculation (single-step topology).
Uses PW mode with PBE functional.
"""
import json
from pathlib import Path
from ase.build import bulk
from gpaw import GPAW, PW, FermiDirac

# Build Si diamond structure
si = bulk('Si', 'diamond', a=5.43)

# Set up GPAW calculator
calc = GPAW(
    mode=PW(300),               # Plane-wave cutoff 300 eV
    xc='PBE',                   # PBE functional
    kpts=(4, 4, 4),             # 4x4x4 k-point grid
    convergence={
        'energy': 0.0005,       # eV/electron
        'density': 1e-4,
        'eigenstates': 4e-8,
    },
    occupations=FermiDirac(0.1),
    nbands=-4,                  # 4 extra bands
    maxiter=100,
    txt='scf.txt',              # Log file
    symmetry={'point_group': False},
)

si.calc = calc

# Run SCF
energy = si.get_potential_energy()
forces = si.get_forces()
fermi = calc.get_fermi_level()

print(f"Total energy: {energy:.6f} eV")
print(f"Fermi level: {fermi:.6f} eV")
print(f"Forces (max component): {abs(forces).max():.6f} eV/Ang")

# Get eigenvalues at Gamma
eigs_gamma = calc.get_eigenvalues(kpt=0, spin=0)
print(f"Eigenvalues at Gamma: {eigs_gamma}")

# Get k-point info
nkpts = len(calc.get_ibz_k_points())
print(f"Number of irreducible k-points: {nkpts}")

# Write restart file (without wavefunctions for size)
calc.write('si_scf.gpw')
# Write with wavefunctions for band structure follow-up
calc.write('si_scf_wf.gpw', mode='all')

# Save results to JSON for parser testing
results = {
    'total_energy_eV': energy,
    'fermi_level_eV': fermi,
    'forces_eV_per_ang': forces.tolist(),
    'eigenvalues_gamma': eigs_gamma.tolist(),
    'n_irreducible_kpoints': nkpts,
    'n_bands': calc.get_number_of_bands(),
    'n_spins': calc.get_number_of_spins(),
    'cell': si.cell.tolist(),
    'positions': si.positions.tolist(),
    'symbols': list(si.get_chemical_symbols()),
    'pbc': si.pbc.tolist(),
}

with open('results.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\nDone! Files written: scf.txt, si_scf.gpw, si_scf_wf.gpw, results.json")
