"""QMCPACK engine implementation."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from quantumvitas.core.engines.qmcpack_resolver import resolve_qmcpack_bin
from quantumvitas.core.public import StepResult
from quantumvitas.engine.base import Engine, EngineConfig

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation

logger = logging.getLogger(__name__)


class QmcpackEngine(Engine):
    """QMCPACK Quantum Monte Carlo engine."""

    name = "qmcpack"

    def __init__(self, config: Optional[EngineConfig] = None):
        super().__init__(config or EngineConfig(name="qmcpack"))
        self._qmcpack_bin: Optional[Path] = None

    @property
    def supported_presets(self) -> list[str]:
        """QMCPACK supports QMC method presets."""
        return ["qmc_method"]

    def _get_qmcpack_bin(self) -> Path:
        """Get QMCPACK binary path, caching result."""
        if self._qmcpack_bin is None:
            self._qmcpack_bin = resolve_qmcpack_bin()
        return self._qmcpack_bin

    def materialize_inputs(
        self,
        step,
        working_dir: Path,
        calculation: "Calculation",
    ) -> None:
        """
        Generate qmc_input.xml and stage supporting files.

        Args:
            step: Step or StructureStepSpec object
            working_dir: Working directory (will be created if needed)
            calculation: Calculation context
        """
        from quantumvitas.drivers.qmcpack.writer import (
            QMCPACKCell, QMCPACKSpecies, QMCPACKWavefunction,
            QMCPACKVMCParams, QMCPACKDMCParams, QMCPACKOptParams,
            write_vmc_input, write_vmc_dmc_input, write_wfopt_input,
        )

        working_dir.mkdir(parents=True, exist_ok=True)

        params = getattr(step, "parameters", None) or {}
        step_type_spec = getattr(step, "step_type_spec", None) or ""

        # Build case-insensitive lookup (StepDoc may uppercase keys like "cell" -> "CELL")
        params_lower = {k.lower(): v for k, v in params.items()}

        # Extract QMC-specific parameters
        cell_params = params_lower.get("cell", {})
        species_params = params_lower.get("species", [])
        wf_params = params_lower.get("wavefunction", {})
        project_id = params_lower.get("project_id", "qmc")

        # Build cell
        cell = QMCPACKCell(
            lattice=cell_params.get("lattice", [[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
            bconds=cell_params.get("bconds", "p p p"),
            lr_dim_cutoff=cell_params.get("lr_dim_cutoff", 15.0),
        )

        # Build species list
        species = []
        for sp in species_params:
            species.append(QMCPACKSpecies(
                symbol=sp["symbol"],
                charge=sp.get("charge", 0),
                valence=sp.get("valence", 0),
                atomic_number=sp.get("atomic_number", 0),
                mass=sp.get("mass", 1.0),
                positions=sp.get("positions", []),
                pseudo_file=sp.get("pseudo_file"),
            ))

        # Extract electron counts from top-level ELECTRONS field
        electrons = params_lower.get("electrons", {})
        num_up = electrons.get("u", wf_params.get("num_up", 0))
        num_down = electrons.get("d", wf_params.get("num_down", 0))

        # Build wavefunction
        wavefunction = QMCPACKWavefunction(
            href=wf_params.get("href", "wavefunction.h5"),
            tilematrix=wf_params.get("tilematrix", "1 0 0 0 1 0 0 0 1"),
            twistnum=wf_params.get("twistnum", 0),
            meshfactor=wf_params.get("meshfactor", 1.0),
            precision=wf_params.get("precision", "double"),
            num_up=num_up,
            num_down=num_down,
            num_orbitals=wf_params.get("num_orbitals", 0),
            j1_coeffs=wf_params.get("j1_coeffs"),
            j2_uu_coeffs=wf_params.get("j2_uu_coeffs"),
            j2_ud_coeffs=wf_params.get("j2_ud_coeffs"),
        )

        # Stage supporting files (h5, pseudo) — use lowered keys
        self._stage_supporting_files(params_lower, working_dir, calculation)

        output_path = working_dir / "qmc_input.xml"

        if step_type_spec == "qmcpack_vmc":
            vmc_p = params_lower.get("vmc", {})
            vmc_params = QMCPACKVMCParams(
                walkers=vmc_p.get("walkers", 1),
                blocks=vmc_p.get("blocks", 200),
                steps=vmc_p.get("steps", 10),
                substeps=vmc_p.get("substeps", 2),
                timestep=vmc_p.get("timestep", 0.3),
                warmupsteps=vmc_p.get("warmupsteps", 50),
            )
            write_vmc_input(output_path, project_id, cell, species, wavefunction, vmc_params)

        elif step_type_spec == "qmcpack_dmc":
            vmc_p = params_lower.get("vmc", {})
            vmc_params = QMCPACKVMCParams(
                walkers=vmc_p.get("walkers", 1),
                blocks=vmc_p.get("blocks", 50),
                steps=vmc_p.get("steps", 10),
                substeps=vmc_p.get("substeps", 2),
                timestep=vmc_p.get("timestep", 0.3),
                warmupsteps=vmc_p.get("warmupsteps", 50),
            )
            dmc_p = params_lower.get("dmc", {})
            dmc_params = QMCPACKDMCParams(
                targetwalkers=dmc_p.get("targetwalkers", 256),
                blocks=dmc_p.get("blocks", 100),
                steps=dmc_p.get("steps", 20),
                timestep=dmc_p.get("timestep", 0.005),
                warmupsteps=dmc_p.get("warmupsteps", 50),
                nonlocalmoves=dmc_p.get("nonlocalmoves", "yes"),
            )
            write_vmc_dmc_input(output_path, project_id, cell, species, wavefunction, vmc_params, dmc_params)

        elif step_type_spec == "qmcpack_wfopt":
            opt_p = params_lower.get("optimization", {})
            opt_params = QMCPACKOptParams(
                blocks=opt_p.get("blocks", 100),
                steps=opt_p.get("steps", 50),
                samples=opt_p.get("samples", 5000),
                warmupsteps=opt_p.get("warmupsteps", 100),
                timestep=opt_p.get("timestep", 0.05),
                minmethod=opt_p.get("minmethod", "adaptive"),
                num_loops=opt_p.get("num_loops", 3),
            )
            # Optional post-opt VMC production
            vmc_params = None
            if "vmc" in params_lower:
                vmc_p = params_lower["vmc"]
                vmc_params = QMCPACKVMCParams(
                    blocks=vmc_p.get("blocks", 200),
                    steps=vmc_p.get("steps", 10),
                )
            write_wfopt_input(output_path, project_id, cell, species, wavefunction, opt_params, vmc_params)

        else:
            raise ValueError(f"Unknown QMCPACK step type: {step_type_spec}")

        logger.info(f"Generated QMCPACK input: {output_path}")

    def _stage_supporting_files(
        self,
        params: dict,
        working_dir: Path,
        calculation: "Calculation",
    ) -> None:
        """Stage HDF5 wavefunction and pseudopotential files into workdir."""
        import shutil

        project_root = calculation.project.root if hasattr(calculation, "project") else Path.cwd()

        # Stage h5 file
        h5_file = params.get("wavefunction", {}).get("href")
        if h5_file:
            h5_src = project_root / h5_file if not Path(h5_file).is_absolute() else Path(h5_file)
            h5_dst = working_dir / Path(h5_file).name
            if h5_src.exists() and not h5_dst.exists():
                shutil.copy2(h5_src, h5_dst)
                logger.debug(f"Staged wavefunction: {h5_src} -> {h5_dst}")

        # Stage pseudo files
        for sp in params.get("species", []):
            pseudo_file = sp.get("pseudo_file")
            if pseudo_file:
                pseudo_src = project_root / pseudo_file if not Path(pseudo_file).is_absolute() else Path(pseudo_file)
                pseudo_dst = working_dir / Path(pseudo_file).name
                if pseudo_src.exists() and not pseudo_dst.exists():
                    shutil.copy2(pseudo_src, pseudo_dst)
                    logger.debug(f"Staged pseudo: {pseudo_src} -> {pseudo_dst}")

    def run_step(
        self,
        step_or_input,
        working_dir: Path | None = None,
        calculation: Optional["Calculation"] = None,
    ) -> StepResult:
        """Execute QMCPACK step."""
        from quantumvitas.engine.engine_input import EngineInput

        if isinstance(step_or_input, EngineInput):
            ei = step_or_input
            wd = ei.working_dir
            step_type = ei.step_type_spec
        else:
            step = step_or_input
            if working_dir is None:
                raise ValueError("working_dir is required for legacy step objects")
            wd = working_dir
            step_type = step.step_type_spec if hasattr(step, "step_type_spec") else ""

        qmcpack_bin = self._get_qmcpack_bin()

        cmd = [str(qmcpack_bin), "qmc_input.xml"]

        logger.info(f"Running QMCPACK: {' '.join(cmd)}")
        logger.info(f"Working directory: {wd}")

        result = subprocess.run(
            cmd,
            cwd=wd,
            capture_output=True,
            text=True,
        )

        error = None
        success = result.returncode == 0

        if result.returncode != 0:
            error = f"QMCPACK exited with code {result.returncode}"
            if result.stderr:
                error += f"\n{result.stderr[:500]}"

        # Check stdout for success message
        if success and "QMCPACK execution completed successfully" not in result.stdout:
            # QMCPACK might still have failed without non-zero exit code
            if "ERROR" in result.stdout.upper() or "FATAL" in result.stdout.upper():
                success = False
                error = "QMCPACK reported errors in stdout"

        input_file = wd / "qmc_input.xml"

        return StepResult(
            step_type_spec=step_type,
            input_file=input_file,
            success=success,
            error=error,
            output_file=input_file if input_file.exists() else None,
            return_code=result.returncode,
        )
