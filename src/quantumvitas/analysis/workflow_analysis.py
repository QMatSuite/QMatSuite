"""
Generate high-level artifacts for a finished workflow.
"""

from __future__ import annotations

import json
from pathlib import Path

from quantumvitas.workflow.workflow import Workflow
from quantumvitas.workflow.results import WorkflowResult
from .dos import analyze_dos
from .bands import analyze_bands
from .energy import analyze_energies


def analyze_workflow(workflow: Workflow, result: WorkflowResult) -> None:
    results_dir = workflow.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)

    summary_path = results_dir / "summary.json"
    summary_path.write_text(json.dumps(result.to_dict(), indent=2))

    analyze_energies(workflow, result, results_dir)
    analyze_dos(workflow, result, results_dir)
    analyze_bands(workflow, result, results_dir)

