"""
Calculation 2: B3LYP/6-31G* geometry optimization + frequency on water.

This demonstrates the relax → freq topology.
"""
import psi4
import json
import numpy as np

# Setup
psi4.set_memory("500 MB")
psi4.set_num_threads(1)
psi4.core.set_output_file("opt_freq_output.dat", False)

# Define molecule (slightly distorted for optimization)
h2o = psi4.geometry("""
    0 1
    O   0.000000   0.000000   0.120000
    H   0.000000   0.800000  -0.450000
    H   0.000000  -0.800000  -0.450000
""")

psi4.set_options({
    'basis': '6-31g*',
    'scf_type': 'df',
    'reference': 'rhf',
    'geom_maxiter': 50,
    'g_convergence': 'gau_tight',
})

# --- Step 1: Geometry Optimization ---
print("=" * 60)
print("STEP 1: B3LYP/6-31G* Geometry Optimization")
print("=" * 60)

opt_e, opt_wfn = psi4.optimize('b3lyp/6-31g*', return_wfn=True)
print(f"Optimized Energy: {opt_e:.10f} Hartree")

# Get optimized geometry
opt_mol = opt_wfn.molecule()
print(f"Optimized geometry (Angstrom):")
geom_ang = []
for i in range(opt_mol.natom()):
    x = opt_mol.x(i) * psi4.constants.bohr2angstroms
    y = opt_mol.y(i) * psi4.constants.bohr2angstroms
    z = opt_mol.z(i) * psi4.constants.bohr2angstroms
    sym = opt_mol.symbol(i)
    print(f"  {sym}  {x:12.8f}  {y:12.8f}  {z:12.8f}")
    geom_ang.append({"symbol": sym, "x": x, "y": y, "z": z})

# Collect optimization variables
opt_vars = {}
for key in ['CURRENT ENERGY', 'SCF TOTAL ENERGY', 'NUCLEAR REPULSION ENERGY']:
    try:
        opt_vars[key] = psi4.core.variable(key)
    except Exception:
        pass

# Save wavefunction
opt_wfn.to_file("opt_wfn.npy")

# --- Step 2: Frequency Analysis ---
print()
print("=" * 60)
print("STEP 2: B3LYP/6-31G* Frequency Analysis")
print("=" * 60)

# Use optimized wavefunction as reference
psi4.core.clean_variables()
freq_e, freq_wfn = psi4.frequency('b3lyp/6-31g*', return_wfn=True)
print(f"Frequency Energy: {freq_e:.10f} Hartree")

# Extract frequencies
freqs = freq_wfn.frequencies()
freq_list = []
print("Vibrational Frequencies (cm^-1):")
for i in range(freqs.dim(0)):
    f = freqs.get(i)
    freq_list.append(f)
    print(f"  Mode {i+1}: {f:.2f}")

# Collect all variables after frequency
freq_vars = {}
for k, v in psi4.core.variables().items():
    freq_vars[k] = v

# Thermochemistry
thermo_keys = ['ZPVE', 'THERMAL ENERGY CORRECTION',
               'ENTHALPY CORRECTION', 'GIBBS FREE ENERGY CORRECTION']
thermo = {}
for key in thermo_keys:
    try:
        thermo[key] = psi4.core.variable(key)
        print(f"  {key}: {thermo[key]:.6f}")
    except Exception:
        pass

# Save results
results = {
    "molecule": "water",
    "method": "b3lyp",
    "basis": "6-31g*",
    "optimization": {
        "energy": opt_e,
        "optimized_geometry_angstrom": geom_ang,
        "variables": opt_vars,
    },
    "frequency": {
        "energy": freq_e,
        "frequencies_cm1": freq_list,
        "thermochemistry": thermo,
    },
    "all_variables": freq_vars,
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print()
print("All results saved to results.json")
