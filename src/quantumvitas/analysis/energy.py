"""
Energy summary utilities and lightweight parsing helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from quantumvitas.workflow.results import WorkflowResult
from quantumvitas.workflow.workflow import Workflow


def analyze_energies(output_file: Path | str) -> dict:
    """
    Parse a QE output file and extract total/Fermi energies.
    """
    output_path = Path(output_file)
    if not output_path.exists():
        raise FileNotFoundError(output_path)

    total_energy = None
    fermi_energy = None
    for line in output_path.read_text().splitlines():
        if "!" in line and "total energy" in line:
            try:
                total_energy = float(line.split("=")[-1].split()[0])
            except Exception:
                continue
        lower = line.lower()
        if "fermi energy" in lower:
            try:
                fermi_energy = float(line.split("=")[-1].split()[0])
            except Exception:
                continue
    return {
        "file": str(output_path),
        "total_energy_ry": total_energy,
        "fermi_energy_ry": fermi_energy,
    }


def summarize_workflow_energies(
    workflow: Workflow, result: WorkflowResult, results_dir: Path
) -> None:
    """
    Extract total energy / Fermi energy metrics from each step result.
    """
    energies: List[Dict[str, object]] = []
    for step in result.steps:
        entry = {
            "step_id": step.step_id,
            "step_type": step.step_type.value,
            "status": step.status.value,
            "total_energy": step.metrics.get("total_energy"),
            "fermi_energy": step.metrics.get("fermi_energy"),
        }
        energies.append(entry)

    (results_dir / "energies.json").write_text(json.dumps(energies, indent=2))

