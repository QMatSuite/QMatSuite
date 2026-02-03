"""
Calculation 3: HF/cc-pVDZ → TDDFT excited states on formaldehyde.

This demonstrates the SCF → TD chain topology.
Formaldehyde has characteristic n→π* and π→π* excitations.
"""
import psi4
import json

# Setup
psi4.set_memory("500 MB")
psi4.set_num_threads(1)
psi4.core.set_output_file("tddft_output.dat", False)

# Formaldehyde - has well-known excited states
h2co = psi4.geometry("""
    0 1
    C   0.000000   0.000000   0.000000
    O   0.000000   0.000000   1.203000
    H   0.000000   0.934200  -0.587000
    H   0.000000  -0.934200  -0.587000
    symmetry c1
""")

psi4.set_options({
    'basis': 'cc-pvdz',
    'scf_type': 'df',
    'reference': 'rhf',
    'save_jk': True,  # Required for TDDFT
    'tdscf_states': 5,  # Number of excited states
    'tdscf_tda': True,  # Tamm-Dancoff approximation
})

# --- Step 1: SCF ---
print("=" * 60)
print("STEP 1: HF/cc-pVDZ SCF on formaldehyde")
print("=" * 60)

scf_e, scf_wfn = psi4.energy('scf', return_wfn=True)
print(f"SCF Energy: {scf_e:.10f} Hartree")

# --- Step 2: TDDFT ---
print()
print("=" * 60)
print("STEP 2: TD-HF/cc-pVDZ Excited States")
print("=" * 60)

from psi4.driver.procrouting.response.scf_response import tdscf_excitations

res = tdscf_excitations(scf_wfn, states=5, triplets='none', tda=True)

# Parse TDDFT results
excitations = []
for i, state in enumerate(res):
    exc_energy_au = state["EXCITATION ENERGY"]
    exc_energy_ev = exc_energy_au * 27.211386  # Hartree to eV

    # Get oscillator strength from transition dipole
    tdm = state.get("LENGTH-GAUGE ELECTRIC DIPOLE TRANSITION MOMENT", None)
    if tdm is not None:
        osc_str = state.get("LENGTH-GAUGE OSCILLATOR STRENGTH (LIN)", 0.0)
    else:
        osc_str = 0.0

    excitations.append({
        "state": i + 1,
        "energy_au": exc_energy_au,
        "energy_ev": exc_energy_ev,
        "oscillator_strength": osc_str,
    })
    print(f"  State {i+1}: {exc_energy_ev:.4f} eV  f = {osc_str:.6f}")

# Collect all variables
all_vars = {}
for k, v in psi4.core.variables().items():
    all_vars[k] = v

results = {
    "molecule": "formaldehyde",
    "method_chain": ["scf", "td"],
    "basis": "cc-pvdz",
    "scf_energy": scf_e,
    "excitations": excitations,
    "all_variables": all_vars,
    "tddft_raw": [
        {k: (v if not hasattr(v, 'tolist') else v.tolist())
         for k, v in state.items()}
        for state in res
    ],
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print()
print("Results saved to results.json")
print(f"Output file: tddft_output.dat")
