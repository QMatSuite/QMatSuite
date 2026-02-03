"""
Calculation 1: HF/cc-pVDZ → MP2/cc-pVDZ chain on water.

This demonstrates the SCF → post-SCF chain topology.
Psi4 Python API is used (not psithon text input).
"""
import psi4
import json
import os

# Setup
psi4.set_memory("500 MB")
psi4.set_num_threads(1)
psi4.core.set_output_file("scf_mp2_output.dat", False)

# Define molecule
h2o = psi4.geometry("""
    0 1
    O   0.000000   0.000000   0.117370
    H   0.000000   0.757160  -0.469480
    H   0.000000  -0.757160  -0.469480
""")

psi4.set_options({
    'basis': 'cc-pvdz',
    'scf_type': 'df',
    'reference': 'rhf',
    'e_convergence': 1e-10,
    'd_convergence': 1e-10,
})

# --- Step 1: SCF ---
print("=" * 60)
print("STEP 1: HF/cc-pVDZ SCF Energy")
print("=" * 60)

scf_e, scf_wfn = psi4.energy('scf', return_wfn=True)
print(f"SCF Energy:          {scf_e:.10f} Hartree")

# Extract SCF variables
scf_vars = {}
for key in ['SCF TOTAL ENERGY', 'HF TOTAL ENERGY', 'ONE-ELECTRON ENERGY',
            'TWO-ELECTRON ENERGY', 'NUCLEAR REPULSION ENERGY',
            'SCF DIPOLE X', 'SCF DIPOLE Y', 'SCF DIPOLE Z',
            'SCF ITERATIONS']:
    try:
        val = psi4.core.variable(key)
        scf_vars[key] = val
        print(f"  {key}: {val}")
    except Exception:
        pass

# Save wavefunction
scf_wfn.to_file("scf_wfn.npy")
print(f"Wavefunction saved to scf_wfn.npy")

# --- Step 2: MP2 (using SCF wavefunction) ---
print()
print("=" * 60)
print("STEP 2: MP2/cc-pVDZ (using SCF reference)")
print("=" * 60)

mp2_e, mp2_wfn = psi4.energy('mp2', ref_wfn=scf_wfn, return_wfn=True)
print(f"MP2 Total Energy:    {mp2_e:.10f} Hartree")

# Extract MP2 variables
mp2_vars = {}
for key in ['MP2 TOTAL ENERGY', 'MP2 CORRELATION ENERGY', 'MP2 SAME-SPIN CORRELATION ENERGY',
            'MP2 OPPOSITE-SPIN CORRELATION ENERGY', 'SCS-MP2 TOTAL ENERGY',
            'CURRENT ENERGY', 'CURRENT CORRELATION ENERGY']:
    try:
        val = psi4.core.variable(key)
        mp2_vars[key] = val
        print(f"  {key}: {val}")
    except Exception:
        pass

# Save MP2 wavefunction
mp2_wfn.to_file("mp2_wfn.npy")

# --- Collect all results ---
all_vars = {}
for k, v in psi4.core.variables().items():
    all_vars[k] = v

results = {
    "molecule": {
        "name": "water",
        "charge": 0,
        "multiplicity": 1,
        "natoms": h2o.natom(),
        "geometry_bohr": [[h2o.x(i), h2o.y(i), h2o.z(i)] for i in range(h2o.natom())],
    },
    "method_chain": ["scf", "mp2"],
    "basis": "cc-pvdz",
    "scf": {
        "energy": scf_e,
        "variables": scf_vars,
    },
    "mp2": {
        "energy": mp2_e,
        "variables": mp2_vars,
    },
    "all_variables": all_vars,
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print()
print("All results saved to results.json")
print(f"All variables ({len(all_vars)} total): {sorted(all_vars.keys())}")
