"""
Calc 2: Si bulk SCF -> Band Structure -> DOS (multi-step topology).
Demonstrates the fixed_density() chaining mechanism.
"""
import json
import numpy as np
from pathlib import Path
from ase.build import bulk
from gpaw import GPAW, PW, FermiDirac

# ===== STEP 1: Ground state SCF =====
print("=" * 60)
print("STEP 1: Ground state SCF")
print("=" * 60)

si = bulk('Si', 'diamond', a=5.43)

calc_gs = GPAW(
    mode=PW(300),
    xc='PBE',
    kpts=(6, 6, 6),
    convergence={
        'energy': 0.0005,
        'density': 1e-4,
        'eigenstates': 4e-8,
    },
    occupations=FermiDirac(0.05),
    nbands=-4,
    maxiter=100,
    txt='gs.txt',
    symmetry={'point_group': False},
)

si.calc = calc_gs
energy = si.get_potential_energy()
print(f"Ground state energy: {energy:.6f} eV")

# Save ground state
calc_gs.write('gs.gpw')
calc_gs.write('gs_wf.gpw', mode='all')

# ===== STEP 2: Band structure (fixed density) =====
print("\n" + "=" * 60)
print("STEP 2: Band structure (fixed density)")
print("=" * 60)

# Reload and compute bands with fixed density
calc_bs = GPAW('gs.gpw').fixed_density(
    nbands=16,
    symmetry='off',
    kpts={'path': 'GXWKL', 'npoints': 60},
    convergence={'bands': 8},
    txt='bands.txt',
)

bs = calc_bs.band_structure()
bs.write('bandstructure.json')

# Extract band structure data manually
energies = bs.energies  # shape: (nspins, nkpts, nbands)
reference = bs.reference  # Fermi level

print(f"Band structure computed: {energies.shape}")
print(f"Reference energy (Fermi): {reference:.4f} eV")

# Save bands calc
calc_bs.write('bands.gpw')

# ===== STEP 3: DOS (from ground state) =====
print("\n" + "=" * 60)
print("STEP 3: DOS calculation")
print("=" * 60)

from ase.dft.dos import DOS

calc_dos = GPAW('gs.gpw', txt=None)
dos = DOS(calc_dos, npts=500, width=0.1)
energies_dos = dos.get_energies()
weights_dos = dos.get_dos()

print(f"DOS computed: {len(energies_dos)} points")
print(f"Energy range: [{energies_dos[0]:.2f}, {energies_dos[-1]:.2f}] eV")

# ===== Save all results =====
results = {
    'scf': {
        'total_energy_eV': energy,
        'fermi_level_eV': calc_gs.get_fermi_level(),
        'n_bands': calc_gs.get_number_of_bands(),
        'n_kpoints': len(calc_gs.get_ibz_k_points()),
    },
    'bands': {
        'shape': list(energies.shape) if hasattr(energies, 'shape') else None,
        'reference_eV': reference,
        'n_kpoints_path': energies.shape[1] if hasattr(energies, 'shape') else None,
        'n_bands': energies.shape[2] if hasattr(energies, 'shape') else None,
    },
    'dos': {
        'n_points': len(energies_dos),
        'energy_min_eV': float(energies_dos[0]),
        'energy_max_eV': float(energies_dos[-1]),
        'integral': float(np.trapezoid(weights_dos, energies_dos)),
    },
}

with open('results.json', 'w') as f:
    json.dump(results, f, indent=2)

# Save DOS data
dos_data = {
    'energies_eV': energies_dos.tolist(),
    'dos': weights_dos.tolist(),
    'fermi_eV': float(calc_gs.get_fermi_level()),
}
with open('dos.json', 'w') as f:
    json.dump(dos_data, f, indent=2)

print("\nDone! Files written: gs.txt, bands.txt, gs.gpw, gs_wf.gpw,")
print("  bands.gpw, bandstructure.json, results.json, dos.json")
