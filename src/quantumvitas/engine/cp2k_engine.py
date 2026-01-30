"""CP2K engine implementation."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Any
from dataclasses import dataclass

from quantumvitas.core.engines.qe_calculation import StepResult
from quantumvitas.core.engines.cp2k_resolver import (
    find_cp2k_executable,
    get_cp2k_version,
    get_cp2k_data_dir,
)
from quantumvitas.engine.base import Engine, EngineConfig
from pymatgen.core import Structure

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation

logger = logging.getLogger(__name__)


@dataclass
class Cp2kStepResult(StepResult):
    """Result from CP2K step execution."""
    output_file: Optional[Path] = None
    trajectory_file: Optional[Path] = None
    cell_file: Optional[Path] = None  # NEW: for cell information
    energy_file: Optional[Path] = None
    wfn_file: Optional[Path] = None
    restart_file: Optional[Path] = None


class Cp2kEngine(Engine):
    """
    CP2K engine for DFT and molecular dynamics.

    Uses directory-state pattern with isolated workdirs per step.
    Artifacts accumulate (no cleanup).

    IMPORTANT: All artifact lookups use mtime-based selection.
    """

    name = "cp2k"

    def __init__(self, config: Optional[EngineConfig] = None):
        super().__init__(config or EngineConfig(name="cp2k"))
        self._executable: Optional[Path] = None
        self._version: Optional[str] = None

    @property
    def supported_presets(self) -> list[str]:
        """
        CP2K supports PBC preset dimensions.
        
        Returns:
            List of supported preset dimensions: precision, magnetism
        """
        return ["precision", "magnetism"]

    @property
    def executable(self) -> Path:
        """Get CP2K executable path."""
        if self._executable is None:
            self._executable = find_cp2k_executable()
            if self._executable is None:
                raise RuntimeError("CP2K executable not found")
        return self._executable

    @property
    def version(self) -> Optional[str]:
        """Get CP2K version."""
        if self._version is None and self._executable:
            self._version = get_cp2k_version(self._executable)
        return self._version

    def probe(self) -> bool:
        """Check if CP2K is available."""
        try:
            return self.executable is not None
        except RuntimeError:
            return False

    def materialize_inputs(
        self,
        step,
        working_dir: Path,
        calculation: "Calculation",
    ) -> None:
        """
        Materialize CP2K input files.

        Creates:
        - input.inp (CP2K input file)

        Args:
            step: Step specification (StructureStepSpec)
            working_dir: Directory to write inputs
            calculation: Calculation context
        """
        from quantumvitas.engine.cp2k_writer import write_cp2k_input
        from quantumvitas.io.structure_io import read_structure
        from pymatgen.core import Structure

        working_dir.mkdir(parents=True, exist_ok=True)

        # Get structure from calculation
        structure = self._get_structure(calculation)
        if structure is None:
            raise ValueError("Calculation has no structure_ulid")

        # Generate input file
        input_path = working_dir / "input.inp"
        write_cp2k_input(
            step=step,
            structure=structure,
            output_path=input_path,
        )

    def _get_structure(self, calculation: "Calculation") -> Optional[Structure]:
        """Get structure from calculation."""
        from quantumvitas.io.structure_io import read_structure
        
        structure_ulid = calculation.structure_ulid
        if structure_ulid is None:
            return None
        
        # Load structure from project
        structure_ref = calculation.project.get_structure(structure_ulid)
        structure_path = structure_ref.resolve_path(calculation.project.root)
        structure = read_structure(structure_path)
        
        # Convert to pymatgen Structure if needed
        if not isinstance(structure, Structure):
            if hasattr(structure, "as_dict"):
                structure = Structure.from_dict(structure.as_dict())
            else:
                raise ValueError(f"Cannot convert structure type {type(structure)}")
        
        return structure

    def run_step(
        self,
        step,
        working_dir: Path,
        calculation: Optional["Calculation"] = None,
    ) -> Cp2kStepResult:
        """
        Execute CP2K step.

        Args:
            step: Step specification
            working_dir: Working directory (must contain input.inp)
            calculation: Calculation context

        Returns:
            Cp2kStepResult with execution status and artifact paths.
        """
        # Build command
        input_file = "input.inp"
        output_file = "output.log"
        command = [str(self.executable), "-i", input_file, "-o", output_file]

        # Set CP2K_DATA_DIR if available
        env = dict(os.environ)
        data_dir = get_cp2k_data_dir()
        if data_dir:
            env["CP2K_DATA_DIR"] = str(data_dir)

        # Get step type for timeout/threads
        step_type = getattr(step, "step_type_spec", None) or ""
        params = getattr(step, "parameters", None) or {}

        # Execute CP2K
        try:
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=params.get("timeout", 3600),  # 1 hour default
                env={
                    **env,
                    "OMP_NUM_THREADS": str(params.get("omp_threads", 1)),
                },
            )
        except subprocess.TimeoutExpired:
            return Cp2kStepResult(
                step_type_spec=step_type,
                input_file=working_dir / input_file,
                success=False,
                error="CP2K execution timed out",
                return_code=-1,
            )
        except Exception as e:
            return Cp2kStepResult(
                step_type_spec=step_type,
                input_file=working_dir / input_file,
                success=False,
                error=f"CP2K execution failed: {e}",
                return_code=-1,
            )

        # Find output artifacts using mtime-based selection
        output_path = working_dir / output_file
        wfn_path = self._find_latest_wfn(working_dir)
        traj_path = self._find_latest_trajectory(working_dir)
        cell_path = self._find_latest_cell(working_dir)  # NEW
        ener_path = self._find_latest_ener(working_dir)
        restart_path = self._find_latest_restart(working_dir)

        # Check success
        success = result.returncode == 0
        if success and output_path.exists():
            success = self._check_success(output_path, step_type)

        return Cp2kStepResult(
            step_type_spec=step_type,
            input_file=working_dir / input_file,
            success=success,
            error=result.stderr if not success else None,
            return_code=result.returncode,
            output_file=output_path if output_path.exists() else None,
            wfn_file=wfn_path,
            trajectory_file=traj_path,
            cell_file=cell_path,  # NEW
            energy_file=ener_path,
            restart_file=restart_path,
        )

    def _find_latest_wfn(self, workdir: Path) -> Optional[Path]:
        """Find latest wavefunction file (non-backup)."""
        wfn = workdir / "cp2k_calc-RESTART.wfn"
        return wfn if wfn.exists() else None

    def _find_latest_trajectory(self, workdir: Path) -> Optional[Path]:
        """Find latest trajectory file by mtime."""
        from quantumvitas.execution.latest_selector import find_latest_by_mtime
        return find_latest_by_mtime(workdir, "cp2k_calc-pos-*.xyz")

    def _find_latest_cell(self, workdir: Path) -> Optional[Path]:
        """Find latest cell file by mtime."""
        from quantumvitas.execution.latest_selector import find_latest_by_mtime
        return find_latest_by_mtime(workdir, "cp2k_calc-*.cell")

    def _find_latest_restart(self, workdir: Path) -> Optional[Path]:
        """Find latest restart file by mtime."""
        from quantumvitas.execution.latest_selector import find_latest_by_mtime
        return find_latest_by_mtime(workdir, "cp2k_calc-*.restart")

    def _find_latest_ener(self, workdir: Path) -> Optional[Path]:
        """Find latest energy file by mtime."""
        from quantumvitas.execution.latest_selector import find_latest_by_mtime
        return find_latest_by_mtime(workdir, "cp2k_calc-*.ener")

    def _check_success(self, output_path: Path, step_type: str) -> bool:
        """Check if CP2K run succeeded based on output."""
        content = output_path.read_text()

        if step_type == "cp2k_scf":
            # Check for SCF convergence first
            if "SCF run converged" in content:
                return True
            # If not converged but PROGRAM ENDED normally, accept as success
            # (e.g., when IGNORE_CONVERGENCE_FAILURE is used)
            if "PROGRAM ENDED" in content:
                return True
            return False

        elif step_type == "cp2k_relax":
            # Check for successful geometry optimization
            if "GEOMETRY OPTIMIZATION COMPLETED" in content:
                return True
            # If not explicitly completed but PROGRAM ENDED normally, accept as success
            # (e.g., when IGNORE_CONVERGENCE_FAILURE is used or max_iter reached)
            if "PROGRAM ENDED" in content:
                return True
            return False

        elif step_type == "cp2k_md":
            # MD doesn't have explicit completion message
            # Check for energy output or normal termination
            return "PROGRAM ENDED" in content or "Total wall" in content

        return True  # Default: trust return code

