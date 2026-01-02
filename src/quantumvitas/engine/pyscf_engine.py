"""
PySCF engine adapter for molecular quantum chemistry calculations.

This module provides a Python-native engine for PySCF calculations.
Unlike QE, PySCF runs directly in Python without subprocess execution.

PySCF is an optional dependency. Calculations will fail gracefully
with a clear error message if PySCF is not installed.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .base import Engine, EngineConfig, StepResult


def _check_pyscf_available() -> bool:
    """Check if PySCF is importable."""
    try:
        import pyscf
        return True
    except ImportError:
        return False


class PySCFEngine(Engine):
    """
    PySCF engine adapter.
    
    Provides Python-native execution of molecular quantum chemistry
    calculations using PySCF:
    - Hartree-Fock (RHF, UHF, ROHF)
    - DFT (RKS, UKS, ROKS)
    
    Key differences from QE:
    - No subprocess execution (direct Python API)
    - No input files (parameters from step.yml)
    - Outputs results.json (not text output)
    """
    
    name = "pyscf"
    
    def __init__(self, config: Optional[EngineConfig] = None):
        """
        Initialize PySCF engine.
        
        Args:
            config: Optional engine configuration (mostly unused for PySCF)
        """
        super().__init__(config or EngineConfig(name="pyscf"))
        self._pyscf_available = _check_pyscf_available()
    
    @property
    def pyscf_available(self) -> bool:
        """Check if PySCF is available for calculations."""
        return self._pyscf_available
    
    def run_step(self, step, working_dir: Path) -> StepResult:
        """
        Run a PySCF calculation step.
        
        Args:
            step: Step object with parameters attribute
            working_dir: Working directory for output files
            
        Returns:
            StepResult with calculation results
        """
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if PySCF is available
        if not self._pyscf_available:
            return StepResult(
                step_type="pyscf_scf",
                input_file=working_dir / "pyscf_input.py",
                success=False,
                error=(
                    "PySCF is not installed. Please install with:\n"
                    "  pip install pyscf\n\n"
                    "Or with optional dependencies:\n"
                    "  pip install quantumvitas[pyscf]"
                ),
                execution_time=0.0,
            )
        
        # Extract parameters from step
        if hasattr(step, 'parameters'):
            params = step.parameters
        elif isinstance(step, dict):
            params = step.get('parameters', step)
        else:
            params = {}
        
        # Determine step type
        step_type = "pyscf_scf"
        if hasattr(step, 'step_type'):
            step_type_attr = step.step_type
            if hasattr(step_type_attr, 'value'):
                step_type = step_type_attr.value
            else:
                step_type = str(step_type_attr)
        elif hasattr(step, 'type'):
            step_type = step.type
        
        # Run appropriate calculation
        if step_type in ("pyscf_scf", "pyscf_rhf", "pyscf_uhf", "pyscf_rks", "pyscf_uks"):
            return self._run_scf(params, working_dir)
        else:
            return StepResult(
                step_type=step_type,
                input_file=working_dir / "pyscf_input.py",
                success=False,
                error=f"Unknown PySCF step type: {step_type}",
                execution_time=0.0,
            )
    
    def _run_scf(self, params: Dict[str, Any], working_dir: Path) -> StepResult:
        """
        Run PySCF SCF (HF or DFT) calculation.
        
        Args:
            params: Calculation parameters
            working_dir: Working directory for output
            
        Returns:
            StepResult with SCF results
        """
        start_time = time.time()
        
        # Import PySCF modules
        try:
            from pyscf import gto, scf, dft
        except ImportError as e:
            return StepResult(
                step_type="pyscf_scf",
                input_file=working_dir / "pyscf_input.py",
                success=False,
                error=f"Failed to import PySCF: {e}",
                execution_time=time.time() - start_time,
            )
        
        # Build molecule
        try:
            mol = self._build_mole(params)
        except Exception as e:
            return StepResult(
                step_type="pyscf_scf",
                input_file=working_dir / "pyscf_input.py",
                success=False,
                error=f"Failed to build molecule: {e}",
                execution_time=time.time() - start_time,
            )
        
        # Setup SCF/DFT method
        method = params.get("method", "rhf").lower()
        xc = params.get("xc", "pbe")
        
        try:
            if method in ("rhf", "hf"):
                mf = scf.RHF(mol)
            elif method == "uhf":
                mf = scf.UHF(mol)
            elif method == "rohf":
                mf = scf.ROHF(mol)
            elif method in ("rks", "dft"):
                mf = dft.RKS(mol)
                mf.xc = xc
            elif method == "uks":
                mf = dft.UKS(mol)
                mf.xc = xc
            elif method == "roks":
                mf = dft.ROKS(mol)
                mf.xc = xc
            else:
                return StepResult(
                    step_type="pyscf_scf",
                    input_file=working_dir / "pyscf_input.py",
                    success=False,
                    error=f"Unknown method: {method}. Use rhf, uhf, rohf, rks, uks, or roks.",
                    execution_time=time.time() - start_time,
                )
        except Exception as e:
            return StepResult(
                step_type="pyscf_scf",
                input_file=working_dir / "pyscf_input.py",
                success=False,
                error=f"Failed to setup SCF: {e}",
                execution_time=time.time() - start_time,
            )
        
        # Convergence settings
        mf.max_cycle = params.get("max_cycle", 50)
        mf.conv_tol = params.get("conv_tol", 1e-9)
        
        # Optional: verbosity (write to log file)
        log_file = working_dir / "pyscf.log"
        mf.verbose = params.get("verbose", 4)
        mf.stdout = open(log_file, 'w')
        
        # Run SCF
        try:
            energy = mf.kernel()
            converged = mf.converged
        except Exception as e:
            mf.stdout.close()
            return StepResult(
                step_type="pyscf_scf",
                input_file=working_dir / "pyscf_input.py",
                success=False,
                error=f"SCF calculation failed: {e}",
                execution_time=time.time() - start_time,
            )
        finally:
            if hasattr(mf.stdout, 'close'):
                mf.stdout.close()
        
        # Extract results
        results = self._extract_scf_results(mf, mol, energy, converged)
        
        # Add method info
        results["method"] = method
        if method in ("rks", "uks", "roks", "dft"):
            results["xc_functional"] = xc
        results["basis"] = params.get("basis", "sto-3g")
        
        # Write results.json
        results_file = working_dir / "results.json"
        try:
            results_file.write_text(json.dumps(results, indent=2))
        except Exception as e:
            # Non-fatal: continue even if we can't write results
            pass
        
        # Generate input script for reproducibility
        self._write_input_script(params, working_dir)
        
        return StepResult(
            step_type="pyscf_scf",
            input_file=working_dir / "pyscf_input.py",
            output_file=results_file,
            success=converged,
            return_code=0 if converged else 1,
            stdout=log_file.read_text() if log_file.exists() else "",
            stderr="",
            error=None if converged else "SCF did not converge",
            execution_time=time.time() - start_time,
            parsed_output=results,
        )
    
    def _build_mole(self, params: Dict[str, Any]):
        """
        Build PySCF Mole object from parameters.
        
        Args:
            params: Dictionary with atoms, basis, charge, spin, unit
            
        Returns:
            pyscf.gto.Mole object
        """
        from pyscf import gto
        
        atoms = params.get("atoms", [])
        unit = params.get("unit", "Angstrom")
        charge = params.get("charge", 0)
        spin = params.get("spin", 0)  # 2S (number of unpaired electrons)
        basis = params.get("basis", "sto-3g")
        
        # Build atom string for PySCF
        # PySCF accepts: "O 0 0 0; H 0 0.757 0.587; H 0 -0.757 0.587"
        atom_lines = []
        for atom in atoms:
            element = atom.get("element", atom.get("symbol", "X"))
            
            # Handle different coordinate formats
            if "coords" in atom:
                coords = atom["coords"]
                x, y, z = coords[0], coords[1], coords[2]
            else:
                x = atom.get("x", 0.0)
                y = atom.get("y", 0.0)
                z = atom.get("z", 0.0)
            
            atom_lines.append(f"{element} {x} {y} {z}")
        
        atom_str = "; ".join(atom_lines)
        
        mol = gto.Mole()
        mol.atom = atom_str
        mol.basis = basis
        mol.charge = charge
        mol.spin = spin
        mol.unit = unit
        mol.build()
        
        return mol
    
    def _extract_scf_results(
        self, 
        mf, 
        mol, 
        energy: float, 
        converged: bool
    ) -> Dict[str, Any]:
        """
        Extract results from completed SCF calculation.
        
        Args:
            mf: PySCF SCF object
            mol: PySCF Mole object
            energy: Total energy (Hartree)
            converged: Whether SCF converged
            
        Returns:
            Dictionary with results
        """
        import numpy as np
        
        results = {
            "energy": float(energy),
            "energy_unit": "Hartree",
            "converged": converged,
            "n_electrons": mol.nelectron,
            "n_atoms": mol.natm,
        }
        
        # MO energies and occupations
        try:
            mo_energy = mf.mo_energy
            mo_occ = mf.mo_occ
            
            # Handle unrestricted case (alpha/beta separate)
            if isinstance(mo_energy, (list, tuple)) or (hasattr(mo_energy, 'ndim') and mo_energy.ndim == 2):
                # Unrestricted: [alpha, beta]
                if hasattr(mo_energy[0], 'tolist'):
                    results["mo_energies_alpha"] = mo_energy[0].tolist()
                    results["mo_energies_beta"] = mo_energy[1].tolist()
                    results["mo_occupations_alpha"] = mo_occ[0].tolist()
                    results["mo_occupations_beta"] = mo_occ[1].tolist()
                else:
                    results["mo_energies_alpha"] = list(mo_energy[0])
                    results["mo_energies_beta"] = list(mo_energy[1])
                    results["mo_occupations_alpha"] = list(mo_occ[0])
                    results["mo_occupations_beta"] = list(mo_occ[1])
                
                # HOMO/LUMO for alpha
                alpha_e = np.array(results["mo_energies_alpha"])
                alpha_occ = np.array(results["mo_occupations_alpha"])
                homo_idx = int(np.where(alpha_occ > 0)[0][-1]) if np.any(alpha_occ > 0) else None
                lumo_idx = int(np.where(alpha_occ == 0)[0][0]) if np.any(alpha_occ == 0) else None
                
                results["homo_index_alpha"] = homo_idx
                results["lumo_index_alpha"] = lumo_idx
                if homo_idx is not None:
                    results["homo_energy_alpha"] = float(alpha_e[homo_idx])
                if lumo_idx is not None:
                    results["lumo_energy_alpha"] = float(alpha_e[lumo_idx])
                if homo_idx is not None and lumo_idx is not None:
                    gap = float(alpha_e[lumo_idx] - alpha_e[homo_idx])
                    results["gap_alpha"] = gap
                    results["gap_alpha_ev"] = gap * 27.2114
            else:
                # Restricted
                if hasattr(mo_energy, 'tolist'):
                    results["mo_energies"] = mo_energy.tolist()
                    results["mo_occupations"] = mo_occ.tolist()
                else:
                    results["mo_energies"] = list(mo_energy)
                    results["mo_occupations"] = list(mo_occ)
                
                # Find HOMO/LUMO
                mo_e = np.array(results["mo_energies"])
                mo_o = np.array(results["mo_occupations"])
                
                homo_idx = None
                lumo_idx = None
                for i, occ in enumerate(mo_o):
                    if occ > 0:
                        homo_idx = i
                    elif lumo_idx is None and homo_idx is not None:
                        lumo_idx = i
                        break
                
                results["homo_index"] = homo_idx
                results["lumo_index"] = lumo_idx
                
                if homo_idx is not None:
                    results["homo_energy"] = float(mo_e[homo_idx])
                if lumo_idx is not None:
                    results["lumo_energy"] = float(mo_e[lumo_idx])
                if homo_idx is not None and lumo_idx is not None:
                    gap = float(mo_e[lumo_idx] - mo_e[homo_idx])
                    results["gap"] = gap
                    results["gap_ev"] = gap * 27.2114  # Hartree to eV
        except Exception:
            # MO extraction failed, continue without it
            pass
        
        # Dipole moment (if available)
        try:
            dipole = mf.dip_moment(verbose=0)
            if hasattr(dipole, 'tolist'):
                results["dipole_moment"] = dipole.tolist()
            else:
                results["dipole_moment"] = list(dipole)
            results["dipole_moment_unit"] = "Debye"
        except Exception:
            pass
        
        # Mulliken charges (if available)
        try:
            from pyscf import lo
            mulliken = mf.mulliken_pop(verbose=0)
            if len(mulliken) >= 2:
                charges = mulliken[1]
                if hasattr(charges, 'tolist'):
                    results["mulliken_charges"] = charges.tolist()
                else:
                    results["mulliken_charges"] = list(charges)
        except Exception:
            pass
        
        return results
    
    def _write_input_script(self, params: Dict[str, Any], working_dir: Path) -> None:
        """
        Write a Python script that reproduces the calculation.
        
        Useful for debugging and reproducibility.
        """
        script_lines = [
            "#!/usr/bin/env python",
            '"""',
            "PySCF input script generated by QMatSuite.",
            "Run with: python pyscf_input.py",
            '"""',
            "",
            "from pyscf import gto, scf, dft",
            "",
            "# Build molecule",
            "mol = gto.Mole()",
        ]
        
        # Atom string
        atoms = params.get("atoms", [])
        atom_lines = []
        for atom in atoms:
            element = atom.get("element", atom.get("symbol", "X"))
            if "coords" in atom:
                coords = atom["coords"]
                x, y, z = coords[0], coords[1], coords[2]
            else:
                x = atom.get("x", 0.0)
                y = atom.get("y", 0.0)
                z = atom.get("z", 0.0)
            atom_lines.append(f"    {element} {x} {y} {z}")
        
        script_lines.append("mol.atom = '''")
        script_lines.extend(atom_lines)
        script_lines.append("'''")
        
        script_lines.append(f"mol.basis = '{params.get('basis', 'sto-3g')}'")
        script_lines.append(f"mol.charge = {params.get('charge', 0)}")
        script_lines.append(f"mol.spin = {params.get('spin', 0)}")
        script_lines.append(f"mol.unit = '{params.get('unit', 'Angstrom')}'")
        script_lines.append("mol.build()")
        script_lines.append("")
        
        # Method setup
        method = params.get("method", "rhf").lower()
        xc = params.get("xc", "pbe")
        
        if method in ("rhf", "hf"):
            script_lines.append("mf = scf.RHF(mol)")
        elif method == "uhf":
            script_lines.append("mf = scf.UHF(mol)")
        elif method == "rohf":
            script_lines.append("mf = scf.ROHF(mol)")
        elif method in ("rks", "dft"):
            script_lines.append("mf = dft.RKS(mol)")
            script_lines.append(f"mf.xc = '{xc}'")
        elif method == "uks":
            script_lines.append("mf = dft.UKS(mol)")
            script_lines.append(f"mf.xc = '{xc}'")
        elif method == "roks":
            script_lines.append("mf = dft.ROKS(mol)")
            script_lines.append(f"mf.xc = '{xc}'")
        
        script_lines.append(f"mf.max_cycle = {params.get('max_cycle', 50)}")
        script_lines.append(f"mf.conv_tol = {params.get('conv_tol', 1e-9)}")
        script_lines.append("")
        script_lines.append("# Run calculation")
        script_lines.append("energy = mf.kernel()")
        script_lines.append("")
        script_lines.append("# Print results")
        script_lines.append("print(f'Total energy: {energy:.10f} Hartree')")
        script_lines.append("print(f'Converged: {mf.converged}')")
        script_lines.append("")
        script_lines.append("# HOMO/LUMO")
        script_lines.append("mo_e = mf.mo_energy")
        script_lines.append("mo_occ = mf.mo_occ")
        script_lines.append("homo_idx = None")
        script_lines.append("lumo_idx = None")
        script_lines.append("for i, occ in enumerate(mo_occ):")
        script_lines.append("    if occ > 0:")
        script_lines.append("        homo_idx = i")
        script_lines.append("    elif lumo_idx is None and homo_idx is not None:")
        script_lines.append("        lumo_idx = i")
        script_lines.append("        break")
        script_lines.append("")
        script_lines.append("if homo_idx is not None and lumo_idx is not None:")
        script_lines.append("    gap = mo_e[lumo_idx] - mo_e[homo_idx]")
        script_lines.append("    print(f'HOMO: {mo_e[homo_idx]:.6f} Ha ({mo_e[homo_idx]*27.2114:.3f} eV)')")
        script_lines.append("    print(f'LUMO: {mo_e[lumo_idx]:.6f} Ha ({mo_e[lumo_idx]*27.2114:.3f} eV)')")
        script_lines.append("    print(f'Gap: {gap:.6f} Ha ({gap*27.2114:.3f} eV)')")
        
        script_path = working_dir / "pyscf_input.py"
        script_path.write_text("\n".join(script_lines) + "\n")

