"""
Energy summary utilities and lightweight parsing helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from quantumvitas.calculation.results import CalculationResult
from quantumvitas.calculation.calculation import Calculation
from .parsers import parse_scf_output, parse_scf_output_path, SCFResult


def extract_energy_metrics_from_text(text: str) -> Dict[str, float | None]:
    """
    Extract energy metrics from QE output text.
    
    Legacy function - prefer using parse_scf_output_text() for full parsing.
    
    Args:
        text: QE output text content (not a path)
    
    Returns:
        Dict with keys:
        - "total_energy_ry": Total energy in Rydberg
        - "fermi_energy_ev": Fermi energy in electronvolt (eV)
        
    Note: QE outputs Fermi energy in eV, not Ry.
    """
    from .parsers import parse_scf_output_text
    result = parse_scf_output_text(text)
    return {
        "total_energy_ry": result.total_energy,
        "fermi_energy_ev": result.fermi_energy,  # eV, not Ry!
    }


def analyze_energies(output_file: Path | str) -> dict:
    """
    Parse a QE output file and extract total/Fermi energies.
    
    Args:
        output_file: Path to QE output file
        
    Returns:
        Dictionary with energy metrics and file path
    """
    output_path = Path(output_file)
    if not output_path.exists():
        raise FileNotFoundError(output_path)

    result = parse_scf_output_path(output_path)
    return {
        "file": str(output_path),
        "total_energy_ry": result.total_energy,
        "fermi_energy_ev": result.fermi_energy,
        "converged": result.converged,
        "n_iterations": len(result.iterations),
        "homo_ev": result.homo,
        "lumo_ev": result.lumo,
        "band_gap_ev": result.band_gap,
    }


def analyze_scf_detailed(output_file: Path | str) -> SCFResult:
    """
    Parse QE output file and return full SCF result.
    
    Args:
        output_file: Path to QE output file
        
    Returns:
        SCFResult with all parsed data
    """
    output_path = Path(output_file)
    if not output_path.exists():
        raise FileNotFoundError(output_path)
    
    return parse_scf_output_path(output_path)


def summarize_calculation_energies(
    calculation: Calculation, result: CalculationResult, results_dir: Path
) -> None:
    """
    Extract total energy / Fermi energy metrics from each step result.
    """
    energies: List[Dict[str, object]] = []
    for step in result.steps:
        entry = {
            "step_id": step.step_ulid,
            "step_type_spec": step.step_type_spec if hasattr(step, "step_type_spec") else getattr(step, "step_type", None),
            "status": step.status.value,
            "total_energy_ry": step.metrics.get("total_energy_ry"),
            "fermi_energy_ev": step.metrics.get("fermi_energy_ev"),
        }
        energies.append(entry)

    (results_dir / "energies.json").write_text(json.dumps(energies, indent=2))
