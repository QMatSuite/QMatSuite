"""Wannier90 recipe for input staging.

This module handles preparation of Wannier90 input files.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from quantumvitas.execution.recipes import BaseRecipe
from quantumvitas.execution.job_graph import Job, JobGraph

if TYPE_CHECKING:
    from quantumvitas.calculation.step import Step

logger = logging.getLogger(__name__)


class W90Recipe(BaseRecipe):
    """Recipe for staging Wannier90 inputs.

    Handles:
    - .win file generation
    - Artifact staging from preprocessing
    - Projection definitions
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """Materialize jobs for Wannier90 steps."""
        from quantumvitas.workflow.registry import get_registry

        if not steps:
            return JobGraph(jobs=[])

        registry = get_registry()
        jobs: List[Job] = []

        for step in steps:
            step_type = step.step_type
            spec = registry.get(step_type) if step_type else None

            job_id = step.meta.id
            working_dir = calc_raw_dir / step.meta.id

            # Wannier90 command
            command = ["wannier90.x", "wannier90"]

            input_files = [working_dir / "wannier90.win"]
            expected_outputs = [working_dir / "wannier90.wout"]

            step_sha = self._get_step_sha(step, step_shas)

            deps = []
            if len(jobs) > 0:
                deps = [jobs[-1].id]

            job = Job(
                id=job_id,
                step_ids=[step.meta.id],
                working_dir=working_dir,
                command=command,
                input_files=input_files,
                expected_outputs=expected_outputs,
                deps=deps,
                fingerprint=step_sha,
                metadata={
                    "engine": "w90",
                    "spec_step_type": spec.step_type_spec if spec else None,
                    "public_type": "postprocess",
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)

    def stage(self, workdir: Path, config: dict[str, Any]) -> None:
        """Stage Wannier90 inputs.

        Args:
            workdir: Working directory
            config: Step configuration
        """
        # Generate .win file
        win_content = self._generate_win_file(config)
        seedname = config.get('seedname', 'wannier90')
        win_path = workdir / f"{seedname}.win"
        win_path.write_text(win_content)
        logger.info(f"Generated .win file: {win_path}")

    def _generate_win_file(self, config: dict[str, Any]) -> str:
        """Generate Wannier90 .win input file.

        Args:
            config: Step configuration with W90 parameters

        Returns:
            Content of .win file
        """
        lines = []

        # Basic parameters
        if "num_wann" in config:
            lines.append(f"num_wann = {config['num_wann']}")

        if "num_bands" in config:
            lines.append(f"num_bands = {config['num_bands']}")

        # Disentanglement window
        if "dis_win_min" in config:
            lines.append(f"dis_win_min = {config['dis_win_min']}")
        if "dis_win_max" in config:
            lines.append(f"dis_win_max = {config['dis_win_max']}")
        if "dis_froz_min" in config:
            lines.append(f"dis_froz_min = {config['dis_froz_min']}")
        if "dis_froz_max" in config:
            lines.append(f"dis_froz_max = {config['dis_froz_max']}")

        # k-point mesh
        if "mp_grid" in config:
            mp = config["mp_grid"]
            lines.append(f"mp_grid = {mp[0]} {mp[1]} {mp[2]}")

        # Projections
        if "projections" in config:
            lines.append("")
            lines.append("begin projections")
            for proj in config["projections"]:
                lines.append(f"  {proj}")
            lines.append("end projections")

        # Unit cell
        if "unit_cell" in config:
            lines.append("")
            lines.append("begin unit_cell_cart")
            for vec in config["unit_cell"]:
                lines.append(f"  {vec[0]:.10f} {vec[1]:.10f} {vec[2]:.10f}")
            lines.append("end unit_cell_cart")

        # Atoms
        if "atoms" in config:
            lines.append("")
            lines.append("begin atoms_frac")
            for atom in config["atoms"]:
                symbol = atom["symbol"]
                pos = atom["position"]
                lines.append(f"  {symbol} {pos[0]:.10f} {pos[1]:.10f} {pos[2]:.10f}")
            lines.append("end atoms_frac")

        # k-points (if explicit)
        if "kpoints" in config:
            lines.append("")
            lines.append("begin kpoints")
            for kpt in config["kpoints"]:
                lines.append(f"  {kpt[0]:.10f} {kpt[1]:.10f} {kpt[2]:.10f}")
            lines.append("end kpoints")

        return "\n".join(lines)

