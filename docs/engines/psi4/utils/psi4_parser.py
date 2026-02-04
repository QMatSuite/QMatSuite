"""
Psi4 output parser — temporary utility for engine integration exploration.

This parser extracts results from Psi4 using the Python API's variable system
(the preferred approach) and falls back to text output parsing when needed.

Design decision: Psi4 is Python-native, so the primary strategy is to use
`psi4.core.variables()` to get all computed quantities as a dict. Text parsing
is only needed for the .dat output file (e.g., for optimization trajectory).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Psi4SCFResult:
    """Parsed SCF result."""
    energy: float                      # Total SCF energy (Hartree)
    converged: bool = True
    n_iterations: int = 0
    nuclear_repulsion_energy: float = 0.0
    one_electron_energy: float = 0.0
    two_electron_energy: float = 0.0
    dipole: Optional[List[float]] = None  # [x, y, z] in Debye
    method: str = "scf"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Psi4MP2Result:
    """Parsed MP2 result."""
    total_energy: float
    correlation_energy: float = 0.0
    reference_energy: float = 0.0
    same_spin_energy: float = 0.0
    opposite_spin_energy: float = 0.0
    scs_total_energy: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Psi4OptResult:
    """Parsed geometry optimization result."""
    energy: float                      # Final energy (Hartree)
    converged: bool = True
    n_steps: int = 0
    final_geometry: Optional[List[dict]] = None  # [{symbol, x, y, z}, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Psi4FreqResult:
    """Parsed frequency result."""
    energy: float
    frequencies_cm1: List[float] = field(default_factory=list)
    zpve: float = 0.0                 # Zero-point vibrational energy (Hartree)
    thermal_energy: float = 0.0       # Thermal energy correction (Hartree)
    enthalpy_correction: float = 0.0
    gibbs_correction: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Psi4TDResult:
    """Parsed TDDFT/TDA result."""
    scf_energy: float
    excitations: List[dict] = field(default_factory=list)
    # Each excitation: {state, energy_au, energy_ev, oscillator_strength}

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Python API-based parser (preferred)
# ---------------------------------------------------------------------------

def parse_from_variables(variables: Dict[str, Any], calc_type: str) -> dict:
    """
    Parse results from psi4.core.variables() dict.

    This is the PREFERRED parsing method because it uses structured data
    from psi4's internal variable system rather than text scraping.

    Args:
        variables: Dict from psi4.core.variables()
        calc_type: One of "scf", "mp2", "ccsd", "opt", "freq", "td"

    Returns:
        Parsed result dict
    """
    result = {
        "calc_type": calc_type,
        "success": True,
    }

    # Common fields
    if "CURRENT ENERGY" in variables:
        result["energy"] = variables["CURRENT ENERGY"]
    if "NUCLEAR REPULSION ENERGY" in variables:
        result["nuclear_repulsion_energy"] = variables["NUCLEAR REPULSION ENERGY"]

    if calc_type == "scf":
        result.update(_parse_scf_vars(variables))
    elif calc_type == "mp2":
        result.update(_parse_mp2_vars(variables))
    elif calc_type == "ccsd":
        result.update(_parse_ccsd_vars(variables))
    elif calc_type == "freq":
        result.update(_parse_freq_vars(variables))

    return result


def _parse_scf_vars(v: Dict[str, Any]) -> dict:
    """Extract SCF-specific variables."""
    d = {}
    if "SCF TOTAL ENERGY" in v:
        d["scf_energy"] = v["SCF TOTAL ENERGY"]
    if "HF TOTAL ENERGY" in v:
        d["hf_energy"] = v["HF TOTAL ENERGY"]
    if "SCF ITERATIONS" in v:
        d["n_iterations"] = int(v["SCF ITERATIONS"])
    if "ONE-ELECTRON ENERGY" in v:
        d["one_electron_energy"] = v["ONE-ELECTRON ENERGY"]
    if "TWO-ELECTRON ENERGY" in v:
        d["two_electron_energy"] = v["TWO-ELECTRON ENERGY"]
    if "SCF DIPOLE" in v:
        d["dipole"] = v["SCF DIPOLE"]
    return d


def _parse_mp2_vars(v: Dict[str, Any]) -> dict:
    """Extract MP2-specific variables."""
    d = {}
    if "MP2 TOTAL ENERGY" in v:
        d["mp2_total_energy"] = v["MP2 TOTAL ENERGY"]
    if "MP2 CORRELATION ENERGY" in v:
        d["mp2_correlation_energy"] = v["MP2 CORRELATION ENERGY"]
    if "MP2 SAME-SPIN CORRELATION ENERGY" in v:
        d["mp2_same_spin_energy"] = v["MP2 SAME-SPIN CORRELATION ENERGY"]
    if "MP2 OPPOSITE-SPIN CORRELATION ENERGY" in v:
        d["mp2_opposite_spin_energy"] = v["MP2 OPPOSITE-SPIN CORRELATION ENERGY"]
    if "SCS-MP2 TOTAL ENERGY" in v:
        d["scs_mp2_total_energy"] = v["SCS-MP2 TOTAL ENERGY"]
    return d


def _parse_ccsd_vars(v: Dict[str, Any]) -> dict:
    """Extract CCSD-specific variables."""
    d = {}
    if "CCSD TOTAL ENERGY" in v:
        d["ccsd_total_energy"] = v["CCSD TOTAL ENERGY"]
    if "CCSD CORRELATION ENERGY" in v:
        d["ccsd_correlation_energy"] = v["CCSD CORRELATION ENERGY"]
    if "(T) CORRECTION ENERGY" in v:
        d["t_correction_energy"] = v["(T) CORRECTION ENERGY"]
    if "CCSD(T) TOTAL ENERGY" in v:
        d["ccsd_t_total_energy"] = v["CCSD(T) TOTAL ENERGY"]
    return d


def _parse_freq_vars(v: Dict[str, Any]) -> dict:
    """Extract frequency-specific variables."""
    d = {}
    if "ZPVE" in v:
        d["zpve"] = v["ZPVE"]
    if "THERMAL ENERGY CORRECTION" in v:
        d["thermal_energy_correction"] = v["THERMAL ENERGY CORRECTION"]
    if "ENTHALPY CORRECTION" in v:
        d["enthalpy_correction"] = v["ENTHALPY CORRECTION"]
    if "GIBBS FREE ENERGY CORRECTION" in v:
        d["gibbs_correction"] = v["GIBBS FREE ENERGY CORRECTION"]
    return d


# ---------------------------------------------------------------------------
# Text output file parser (fallback / complementary)
# ---------------------------------------------------------------------------

def parse_output_file(filepath: Path) -> dict:
    """
    Parse a Psi4 .dat output file for key quantities.

    This is a FALLBACK parser for when Python API results aren't available
    (e.g., parsing existing output files from command-line runs).

    Returns dict with extracted quantities.
    """
    text = filepath.read_text(errors="replace")
    result = {
        "success": "Psi4 exiting successfully" in text or "beer" in text.lower(),
        "error": None,
    }

    # SCF energy
    scf_matches = re.findall(
        r'@(?:DF-)?(?:R|U|RO)(?:HF|KS)\s+Final Energy:\s+(-?\d+\.\d+)',
        text
    )
    if not scf_matches:
        # Alternative pattern
        scf_matches = re.findall(
            r'Total Energy\s*=\s+(-?\d+\.\d+)',
            text
        )
    if scf_matches:
        result["scf_energy"] = float(scf_matches[-1])

    # SCF iterations
    iter_matches = re.findall(r'@DF-R(?:HF|KS) iter\s+(\d+):', text)
    if iter_matches:
        result["scf_iterations"] = int(iter_matches[-1])

    # SCF convergence
    result["scf_converged"] = "Energy and wave function converged" in text

    # MP2 energy
    mp2_match = re.search(
        r'DF-MP2.*?Total Energy\s+=\s+(-?\d+\.\d+)',
        text, re.DOTALL
    )
    if mp2_match:
        result["mp2_total_energy"] = float(mp2_match.group(1))

    mp2_corr_match = re.search(
        r'Correlation Energy\s+=\s+(-?\d+\.\d+)',
        text
    )
    if mp2_corr_match:
        result["mp2_correlation_energy"] = float(mp2_corr_match.group(1))

    # CCSD energy
    ccsd_match = re.search(r'CCSD total energy\s+=\s+(-?\d+\.\d+)', text)
    if ccsd_match:
        result["ccsd_total_energy"] = float(ccsd_match.group(1))

    # Optimization convergence
    if "Optimization complete!" in text:
        result["optimization_converged"] = True
        # Count optimization steps
        opt_steps = re.findall(r'~?\n\s+\d+\s+(-?\d+\.\d+)', text)
        if opt_steps:
            result["optimization_steps"] = len(opt_steps)
            result["optimization_final_energy"] = float(opt_steps[-1])

    # Frequencies
    freq_matches = re.findall(r'Freq\s+\[cm\^-1\]\s+([\d.\s-]+)', text)
    if freq_matches:
        freqs = []
        for block in freq_matches:
            for val in block.split():
                try:
                    freqs.append(float(val))
                except ValueError:
                    pass
        result["frequencies_cm1"] = freqs

    # ZPVE
    zpve_match = re.search(
        r'Vibrational ZPVE\s+[\d.]+\s+\[kcal/mol\]\s+[\d.]+\s+\[kJ/mol\]\s+([\d.]+)\s+\[Eh\]',
        text
    )
    if zpve_match:
        result["zpve_hartree"] = float(zpve_match.group(1))

    # Thermochemistry
    for key, pattern in [
        ("thermal_energy_hartree", r'Total E.*?at\s+[\d.]+\s+\[K\]\s+(-?\d+\.\d+)\s+\[Eh\]'),
        ("enthalpy_hartree", r'Total H.*?at\s+[\d.]+\s+\[K\]\s+(-?\d+\.\d+)\s+\[Eh\]'),
        ("gibbs_hartree", r'Total G.*?at\s+[\d.]+\s+\[K\]\s+(-?\d+\.\d+)\s+\[Eh\]'),
    ]:
        m = re.search(pattern, text)
        if m:
            result[key] = float(m.group(1))

    # Nuclear repulsion
    nuc_match = re.search(r'Nuclear repulsion =\s+([\d.]+)', text)
    if nuc_match:
        result["nuclear_repulsion_energy"] = float(nuc_match.group(1))

    # Geometry (last occurrence)
    geom_matches = list(re.finditer(
        r'Geometry \(in Angstrom\).*?(?:---+\n)(.*?)(?:\n\n|\Z)',
        text, re.DOTALL
    ))
    if geom_matches:
        geom_text = geom_matches[-1].group(1)
        atoms = []
        for line in geom_text.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    atoms.append({
                        "symbol": parts[0],
                        "x": float(parts[1]),
                        "y": float(parts[2]),
                        "z": float(parts[3]),
                    })
                except (ValueError, IndexError):
                    pass
        if atoms:
            result["geometry"] = atoms

    return result


# ---------------------------------------------------------------------------
# JSON results parser
# ---------------------------------------------------------------------------

def parse_results_json(filepath: Path) -> dict:
    """Parse a results.json file produced by our calculation scripts."""
    with open(filepath) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Test the parser
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python psi4_parser.py <output_file.dat>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)

    result = parse_output_file(filepath)
    print(json.dumps(result, indent=2, default=str))
