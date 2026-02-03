"""
Psi4 input writer — temporary utility for engine integration exploration.

Generates Psi4 Python scripts for execution. Unlike ORCA/QE which use
text input files, Psi4's primary mode is Python scripting. This writer
generates complete Python scripts that:

1. Set up psi4 environment (memory, threads, output file)
2. Define molecule geometry
3. Set calculation options
4. Execute the calculation chain
5. Extract results to results.json

Design: Since Psi4 is Python-native, the engine can call psi4 directly
in-process (like PySCF) OR generate a Python script for subprocess
execution (like ORCA with text input). We support both approaches.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MoleculeSpec:
    """Specification for a molecule."""
    atoms: List[dict]          # [{symbol: str, x: float, y: float, z: float}]
    charge: int = 0
    multiplicity: int = 1
    symmetry: Optional[str] = None  # None = auto, "c1" = no symmetry

    def to_psi4_geometry_string(self) -> str:
        """Generate psi4.geometry() input string."""
        lines = [f"    {self.charge} {self.multiplicity}"]
        for atom in self.atoms:
            lines.append(
                f"    {atom['symbol']:2s}  {atom['x']:14.8f}  {atom['y']:14.8f}  {atom['z']:14.8f}"
            )
        if self.symmetry:
            lines.append(f"    symmetry {self.symmetry}")
        return "\n".join(lines)


@dataclass
class Psi4StepSpec:
    """Specification for a single Psi4 calculation step."""
    step_type: str             # "scf", "mp2", "ccsd", "opt", "freq", "td"
    method: str = "scf"       # "scf", "hf", "b3lyp", "mp2", "ccsd", etc.
    basis: str = "cc-pvdz"
    options: Dict[str, Any] = field(default_factory=dict)
    # TD-specific
    td_states: int = 5
    td_triplets: str = "none"
    td_tda: bool = True


def write_psi4_chain_script(
    molecule: MoleculeSpec,
    steps: List[Psi4StepSpec],
    output_dir: Path,
    memory_mb: int = 500,
    nthreads: int = 1,
    output_filename: str = "output.dat",
    results_filename: str = "results.json",
) -> Path:
    """
    Generate a Python script that executes a psi4 calculation chain.

    Args:
        molecule: Molecule specification
        steps: List of calculation steps (chain)
        output_dir: Directory for output files
        memory_mb: Memory in MB
        nthreads: Number of threads
        output_filename: Name of psi4 output file
        results_filename: Name of JSON results file

    Returns:
        Path to generated script
    """
    script_lines = [
        '"""Auto-generated Psi4 calculation script."""',
        'import psi4',
        'import json',
        'import traceback',
        '',
        f'psi4.set_memory("{memory_mb} MB")',
        f'psi4.set_num_threads({nthreads})',
        f'psi4.core.set_output_file("{output_filename}", False)',
        '',
        '# --- Molecule ---',
        'mol = psi4.geometry("""',
        molecule.to_psi4_geometry_string(),
        '""")',
        '',
    ]

    # Collect all options from steps (merge)
    all_options = {}
    for step in steps:
        all_options.update(step.options)
    if steps:
        all_options.setdefault('basis', steps[0].basis)

    # Write options
    if all_options:
        script_lines.append('# --- Options ---')
        script_lines.append('psi4.set_options({')
        for k, v in all_options.items():
            if isinstance(v, str):
                script_lines.append(f"    '{k}': '{v}',")
            elif isinstance(v, bool):
                script_lines.append(f"    '{k}': {v},")
            else:
                script_lines.append(f"    '{k}': {v},")
        script_lines.append('})')
        script_lines.append('')

    # Write chain execution
    script_lines.append('# --- Execution Chain ---')
    script_lines.append('results = {}')
    script_lines.append('success = True')
    script_lines.append('error = None')
    script_lines.append('wfn = None')
    script_lines.append('')
    script_lines.append('try:')

    for i, step in enumerate(steps):
        step_var = f"step_{i}"
        indent = "    "

        if step.step_type == "scf":
            method_basis = f"'{step.method}/{step.basis}'" if step.basis not in all_options.get('basis', '') else f"'{step.method}'"
            script_lines.append(f'{indent}# Step {i}: SCF ({step.method}/{step.basis})')
            if i == 0:
                script_lines.append(f'{indent}e_{i}, wfn = psi4.energy({method_basis}, return_wfn=True)')
            else:
                script_lines.append(f'{indent}e_{i}, wfn = psi4.energy({method_basis}, ref_wfn=wfn, return_wfn=True)')
            script_lines.append(f'{indent}results["step_{i}"] = {{')
            script_lines.append(f'{indent}    "type": "scf",')
            script_lines.append(f'{indent}    "energy": e_{i},')
            script_lines.append(f'{indent}    "converged": True,')
            script_lines.append(f'{indent}    "variables": dict(psi4.core.variables()),')
            script_lines.append(f'{indent}}}')

        elif step.step_type == "mp2":
            script_lines.append(f'{indent}# Step {i}: MP2')
            ref = "ref_wfn=wfn, " if i > 0 else ""
            script_lines.append(f"{indent}e_{i}, wfn = psi4.energy('mp2', {ref}return_wfn=True)")
            script_lines.append(f'{indent}results["step_{i}"] = {{')
            script_lines.append(f'{indent}    "type": "mp2",')
            script_lines.append(f'{indent}    "energy": e_{i},')
            script_lines.append(f'{indent}    "mp2_correlation": psi4.core.variable("MP2 CORRELATION ENERGY"),')
            script_lines.append(f'{indent}    "variables": dict(psi4.core.variables()),')
            script_lines.append(f'{indent}}}')

        elif step.step_type == "ccsd":
            script_lines.append(f'{indent}# Step {i}: CCSD')
            ref = "ref_wfn=wfn, " if i > 0 else ""
            script_lines.append(f"{indent}e_{i}, wfn = psi4.energy('ccsd', {ref}return_wfn=True)")
            script_lines.append(f'{indent}results["step_{i}"] = {{')
            script_lines.append(f'{indent}    "type": "ccsd",')
            script_lines.append(f'{indent}    "energy": e_{i},')
            script_lines.append(f'{indent}    "variables": dict(psi4.core.variables()),')
            script_lines.append(f'{indent}}}')

        elif step.step_type in ("opt", "relax"):
            method_basis = f"'{step.method}/{step.basis}'"
            script_lines.append(f'{indent}# Step {i}: Geometry Optimization')
            script_lines.append(f'{indent}e_{i}, wfn = psi4.optimize({method_basis}, return_wfn=True)')
            script_lines.append(f'{indent}opt_mol = wfn.molecule()')
            script_lines.append(f'{indent}geom = []')
            script_lines.append(f'{indent}for a in range(opt_mol.natom()):')
            script_lines.append(f'{indent}    geom.append({{')
            script_lines.append(f'{indent}        "symbol": opt_mol.symbol(a),')
            script_lines.append(f'{indent}        "x": opt_mol.x(a) * psi4.constants.bohr2angstroms,')
            script_lines.append(f'{indent}        "y": opt_mol.y(a) * psi4.constants.bohr2angstroms,')
            script_lines.append(f'{indent}        "z": opt_mol.z(a) * psi4.constants.bohr2angstroms,')
            script_lines.append(f'{indent}    }})')
            script_lines.append(f'{indent}results["step_{i}"] = {{')
            script_lines.append(f'{indent}    "type": "opt",')
            script_lines.append(f'{indent}    "energy": e_{i},')
            script_lines.append(f'{indent}    "final_geometry": geom,')
            script_lines.append(f'{indent}    "variables": dict(psi4.core.variables()),')
            script_lines.append(f'{indent}}}')

        elif step.step_type == "freq":
            method_basis = f"'{step.method}/{step.basis}'"
            script_lines.append(f'{indent}# Step {i}: Frequency Analysis')
            script_lines.append(f'{indent}e_{i}, wfn = psi4.frequency({method_basis}, return_wfn=True)')
            script_lines.append(f'{indent}freqs = wfn.frequencies()')
            script_lines.append(f'{indent}freq_list = [freqs.get(j) for j in range(freqs.dim(0))]')
            script_lines.append(f'{indent}results["step_{i}"] = {{')
            script_lines.append(f'{indent}    "type": "freq",')
            script_lines.append(f'{indent}    "energy": e_{i},')
            script_lines.append(f'{indent}    "frequencies_cm1": freq_list,')
            script_lines.append(f'{indent}    "variables": dict(psi4.core.variables()),')
            script_lines.append(f'{indent}}}')

        elif step.step_type == "td":
            script_lines.append(f'{indent}# Step {i}: TDDFT')
            script_lines.append(f'{indent}from psi4.driver.procrouting.response.scf_response import tdscf_excitations')
            script_lines.append(f'{indent}if wfn is None:')
            script_lines.append(f'{indent}    raise RuntimeError("TDDFT requires a prior SCF wavefunction")')
            script_lines.append(f"{indent}td_res = tdscf_excitations(wfn, states={step.td_states}, triplets='{step.td_triplets}', tda={step.td_tda})")
            script_lines.append(f'{indent}excitations = []')
            script_lines.append(f'{indent}for j, state in enumerate(td_res):')
            script_lines.append(f'{indent}    exc_e = state["EXCITATION ENERGY"]')
            script_lines.append(f'{indent}    osc = state.get("LENGTH-GAUGE OSCILLATOR STRENGTH (LIN)", 0.0)')
            script_lines.append(f'{indent}    excitations.append({{"state": j+1, "energy_au": exc_e, "energy_ev": exc_e * 27.211386, "oscillator_strength": osc}})')
            script_lines.append(f'{indent}results["step_{i}"] = {{')
            script_lines.append(f'{indent}    "type": "td",')
            script_lines.append(f'{indent}    "excitations": excitations,')
            script_lines.append(f'{indent}    "variables": dict(psi4.core.variables()),')
            script_lines.append(f'{indent}}}')

        script_lines.append('')

    # Save wavefunction
    script_lines.append('    if wfn is not None:')
    script_lines.append('        wfn.to_file("wavefunction.npy")')
    script_lines.append('')

    # Error handling
    script_lines.append('except Exception as e:')
    script_lines.append('    success = False')
    script_lines.append('    error = f"{type(e).__name__}: {e}\\n{traceback.format_exc()[:500]}"')
    script_lines.append('')

    # Write results
    script_lines.append('# --- Write Results ---')
    script_lines.append('output = {')
    script_lines.append('    "success": success,')
    script_lines.append('    "error": error,')
    script_lines.append('    "steps": results,')
    script_lines.append('}')
    script_lines.append(f'with open("{results_filename}", "w") as f:')
    script_lines.append('    json.dump(output, f, indent=2, default=str)')
    script_lines.append('')

    # Write script
    script_path = output_dir / "psi4_input.py"
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path.write_text("\n".join(script_lines))
    return script_path


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Example: Generate SCF → MP2 chain script
    mol = MoleculeSpec(
        atoms=[
            {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.117},
            {"symbol": "H", "x": 0.0, "y": 0.757, "z": -0.469},
            {"symbol": "H", "x": 0.0, "y": -0.757, "z": -0.469},
        ],
        charge=0,
        multiplicity=1,
    )
    steps = [
        Psi4StepSpec(step_type="scf", method="scf", basis="cc-pvdz"),
        Psi4StepSpec(step_type="mp2", method="mp2", basis="cc-pvdz"),
    ]
    output_dir = Path("/tmp/psi4_test_gen")
    script = write_psi4_chain_script(mol, steps, output_dir)
    print(f"Generated script: {script}")
    print(script.read_text())
