"""
Generate high-level artifacts for a finished calculation.
"""

from __future__ import annotations

import json
from pathlib import Path

from quantumvitas.calculation.public import Calculation, CalculationResult
from .dos import analyze_dos
from .bands import analyze_bands
from .energy import summarize_calculation_energies


def analyze_calculation(calculation: Calculation, result: CalculationResult) -> None:
    results_dir = calculation.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)

    summary_path = results_dir / "summary.json"
    summary_path.write_text(json.dumps(result.to_dict(), indent=2))

    summarize_calculation_energies(calculation, result, results_dir)
    analyze_dos(calculation, result, results_dir)
    analyze_bands(calculation, result, results_dir)

