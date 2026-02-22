"""GPAW output parser.

Parses GPAW calculation results from:
- results.json (primary, no GPAW dependency)
- {gen_type}.txt text logs (fallback, regex-based)
- bandstructure.json (ASE BandStructure format)
- dos.json (DOS data)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def parse_results_json(path: Path) -> dict[str, Any]:
    """Parse results.json written by the generated GPAW script.

    This is the primary parser. No GPAW dependency needed.
    """
    data = json.loads(path.read_text())
    return data


def parse_bandstructure_json(path: Path) -> dict[str, Any]:
    """Parse bandstructure.json (ASE BandStructure.write() format)."""
    data = json.loads(path.read_text())
    return data


def parse_dos_json(path: Path) -> dict[str, Any]:
    """Parse dos.json."""
    data = json.loads(path.read_text())
    return data


def parse_gpaw_txt(path: Path) -> dict[str, Any]:
    """Parse GPAW text log file (regex-based fallback, no GPAW dependency).

    Extracts convergence info, energies, Fermi level, band gap,
    forces, SCF iterations, memory usage from the .txt output.
    """
    text = path.read_text()
    result: dict[str, Any] = {}

    # Convergence
    converged_match = re.search(r"Converged after (\d+) iterations", text)
    if converged_match:
        result["converged"] = True
        result["n_iterations"] = int(converged_match.group(1))
    elif "Did not converge" in text:
        result["converged"] = False

    # Total energy (extrapolated)
    energy_match = re.search(
        r"Extrapolated:\s+([-\d.]+)", text
    )
    if energy_match:
        result["total_energy_eV"] = float(energy_match.group(1))

    # Free energy
    free_match = re.search(r"Free energy:\s+([-\d.]+)", text)
    if free_match:
        result["free_energy_eV"] = float(free_match.group(1))

    # Fermi level
    fermi_match = re.search(r"Fermi level:\s+([-\d.]+)", text)
    if fermi_match:
        result["fermi_level_eV"] = float(fermi_match.group(1))

    # Band gap
    gap_match = re.search(
        r"Band gap:\s+([\d.]+)\s+eV", text
    )
    if gap_match:
        result["band_gap_eV"] = float(gap_match.group(1))

    # Memory
    mem_match = re.search(r"Memory usage:\s+([\d.]+)\s+MiB", text)
    if mem_match:
        result["memory_mib"] = float(mem_match.group(1))

    return result
