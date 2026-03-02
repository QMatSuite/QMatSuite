"""MACE convergence analysis provider.

Parses ``results.json`` produced by MACE scripts into a Convergence object.
For SCF: single-step evaluation (ML potentials have no SCF loop).
For relax: multi-step optimization trajectory from ``trajectory.jsonl``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.convergence.model import Convergence
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.parsers.registry import register_parser


def _parse_mace_convergence(raw_dir: Path) -> dict:
    """Parse MACE results.json and optional trajectory.jsonl into convergence data."""
    results_path = raw_dir / "results.json"
    traj_path = raw_dir / "trajectory.jsonl"

    scf_steps: List[int] = []
    scf_energies: List[float] = []
    scf_des: List[float] = []
    ionic_steps: List[int] = []
    ionic_energies: List[float] = []
    ionic_max_forces: List[float] = []
    converged = False
    source_files: List[Path] = []

    # Read results.json for final state
    if results_path.is_file():
        source_files.append(results_path)
        try:
            data = json.loads(results_path.read_text(encoding="utf-8"))
            converged = data.get("converged", data.get("success", False))
        except (OSError, json.JSONDecodeError):
            pass

    # Read trajectory.jsonl for per-step data (relax/md)
    if traj_path.is_file():
        source_files.append(traj_path)
        try:
            text = traj_path.read_text(encoding="utf-8")
            for i, line in enumerate(text.strip().splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    frame = json.loads(line)
                except json.JSONDecodeError:
                    continue
                energy = frame.get("energy_eV")
                if energy is not None:
                    ionic_steps.append(i)
                    ionic_energies.append(float(energy))
                    # SCF: each ionic step is also an SCF step for ML potentials
                    scf_steps.append(i)
                    scf_energies.append(float(energy))
                    if len(scf_energies) > 1:
                        scf_des.append(scf_energies[-1] - scf_energies[-2])
                    else:
                        scf_des.append(0.0)
                max_force = frame.get("max_force_eV_per_ang")
                if max_force is not None:
                    ionic_max_forces.append(float(max_force))
        except OSError:
            pass

    # If no trajectory data, use results.json single-point
    if not ionic_energies and results_path.is_file():
        try:
            data = json.loads(results_path.read_text(encoding="utf-8"))
            energy = data.get("total_energy_eV")
            if energy is not None:
                scf_steps = [0]
                scf_energies = [float(energy)]
                scf_des = [0.0]
                ionic_steps = [0]
                ionic_energies = [float(energy)]
                max_force = data.get("max_force_eV_per_ang")
                if max_force is not None:
                    ionic_max_forces = [float(max_force)]
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "ionic_max_forces": ionic_max_forces or None,
        "converged": converged,
        "source_files": source_files,
    }


@register_parser("mace", "convergence")
class MACEConvergenceProvider:
    """MACE convergence analysis provider."""

    engine = "mace"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        return (raw_dir / "results.json").is_file()

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        raw_dir = evidence.primary_raw_dir
        parsed = _parse_mace_convergence(raw_dir)

        source_files = [
            SourceFileStat.from_path(p, evidence.calc_dir)
            for p in parsed["source_files"]
        ]

        warnings: list[str] = []
        if not parsed["scf_energies"]:
            warnings.append("No energy data found in MACE output.")

        meta = AnalysisObjectMeta.create(
            object_type="convergence",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="mace_convergence",
            parser_version="1.0",
            warnings=warnings,
        )

        return Convergence(
            meta=meta,
            scf_step=np.array(parsed["scf_steps"], dtype=int),
            scf_energy=np.array(parsed["scf_energies"], dtype=float),
            scf_de=np.array(parsed["scf_des"], dtype=float),
            ionic_step=np.array(parsed["ionic_steps"], dtype=int),
            ionic_energy=np.array(parsed["ionic_energies"], dtype=float),
            ionic_max_force=(
                np.array(parsed["ionic_max_forces"], dtype=float)
                if parsed["ionic_max_forces"] is not None
                else None
            ),
            converged=parsed["converged"],
            n_ionic_steps=len(parsed["ionic_steps"]),
            algorithm="MACE-ML",
        )
