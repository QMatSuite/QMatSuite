"""VASP engine implementation."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
from quantumvitas.core.public import StepResult
from pymatgen.core import Structure
from quantumvitas.io.structure_io import read_structure
from quantumvitas.engine.base import Engine, EngineConfig
from quantumvitas.engine.vasp_writer import (
    write_poscar,
    write_incar,
    write_kpoints,
    write_potcar,
)

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.calculation.step import Step

logger = logging.getLogger(__name__)


class VaspEngine(Engine):
    """VASP engine implementation."""

    name = "vasp"

    def __init__(self, config: Optional[EngineConfig] = None):
        super().__init__(config or EngineConfig(name="vasp"))
        self._vasp_bin: Optional[Path] = None

    @property
    def supported_presets(self) -> list[str]:
        """
        VASP engine supports PBC preset dimensions.
        
        Returns:
            List of supported preset dimensions: precision, magnetism, occupations_scheme
        """
        return ["precision", "magnetism", "occupations_scheme"]

    def _get_vasp_bin(self, variant: str = "std") -> Path:
        """Get VASP binary path, caching result."""
        if self._vasp_bin is None:
            self._vasp_bin = resolve_vasp_bin(variant)
        return self._vasp_bin

    def materialize_inputs(
        self,
        step: "Step",
        working_dir: Path,
        calculation: "Calculation",
    ) -> None:
        """
        Materialize VASP input files (POSCAR, INCAR, KPOINTS, POTCAR) into working_dir.
        
        Args:
            step: Step object
            working_dir: Working directory (will be created if needed)
            calculation: Calculation context
        """
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Get structure from calculation
        structure_ulid = calculation.structure_ulid
        if structure_ulid is None:
            raise ValueError("Calculation has no structure_ulid")
        
        # Load structure from project
        structure_ref = calculation.project.get_structure(structure_ulid)
        structure_path = structure_ref.resolve_path(calculation.project.root)
        structure = read_structure(structure_path)
        
        # Convert to pymatgen Structure if needed
        if not isinstance(structure, Structure):
            # Assume structure has as_dict() or similar
            if hasattr(structure, "as_dict"):
                structure = Structure.from_dict(structure.as_dict())
            else:
                raise ValueError(f"Cannot convert structure type {type(structure)}")
        
        # Write POSCAR
        write_poscar(structure, working_dir / "POSCAR")
        
        # Get INCAR parameters from step
        incar_params = self._get_incar_params(step)
        write_incar(incar_params, working_dir / "INCAR")
        
        # Get KPOINTS parameters from step
        kpoints_params = self._get_kpoints_params(step)
        write_kpoints(kpoints_params, working_dir / "KPOINTS")
        
        # Write POTCAR
        species_map = calculation.species_map or {}
        potcar_type = self._get_potcar_type(step)
        write_potcar(structure, species_map, working_dir / "POTCAR", potcar_type)
    
    def _get_incar_params(self, step: "Step") -> dict[str, Any]:
        """Extract INCAR parameters from step."""
        # Get from step.parameters or step.options
        params = {}
        
        if hasattr(step, "parameters") and step.parameters:
            # Check for engine_params.vasp.incar
            if isinstance(step.parameters, dict):
                vasp_params = step.parameters.get("engine_params", {}).get("vasp", {})
                params.update(vasp_params.get("incar", {}))
        
        # Set defaults based on step type (SPEC type)
        step_type_spec = getattr(step, "step_type_spec", None)

        if step_type_spec == "vasp_bandspw":
            # Bands calculation: read charge density from CHGCAR
            if "ICHARG" not in params:
                params["ICHARG"] = 11
            if "SYSTEM" not in params:
                params["SYSTEM"] = "VASP bands calculation"
        elif step_type_spec == "vasp_dos":
            # DOS calculation: read charge density from CHGCAR, use tetrahedron method
            if "ICHARG" not in params:
                params["ICHARG"] = 11
            if "ISMEAR" not in params:
                params["ISMEAR"] = -5
            if "SYSTEM" not in params:
                params["SYSTEM"] = "VASP DOS calculation"
        else:
            # Defaults for SCF
            if not params:
                params = {
                    "SYSTEM": "VASP calculation",
                    "ISTART": 0,
                    "ICHARG": 2,
                    "ENCUT": 240,
                    "ISMEAR": 0,
                    "SIGMA": 0.1,
                    "IBRION": -1,
                    "NSW": 0,
                    "LWAVE": True,
                    "LCHARG": True,
                }
            else:
                # Ensure defaults for SCF if not set
                if "ISTART" not in params:
                    params["ISTART"] = 0
                if "ICHARG" not in params:
                    params["ICHARG"] = 2
                if "ENCUT" not in params:
                    params["ENCUT"] = 240
                if "ISMEAR" not in params:
                    params["ISMEAR"] = 0
                if "SIGMA" not in params:
                    params["SIGMA"] = 0.1
                if "IBRION" not in params:
                    params["IBRION"] = -1
                if "NSW" not in params:
                    params["NSW"] = 0
                if "LWAVE" not in params:
                    params["LWAVE"] = True
                if "LCHARG" not in params:
                    params["LCHARG"] = True
        
        return params
    
    def _get_kpoints_params(self, step: "Step") -> dict[str, Any]:
        """Extract KPOINTS parameters from step."""
        # Get from step.parameters
        params = {}
        
        if hasattr(step, "parameters") and step.parameters:
            if isinstance(step.parameters, dict):
                vasp_params = step.parameters.get("engine_params", {}).get("vasp", {})
                params.update(vasp_params.get("kpoints", {}))
        
        # Defaults: automatic mesh
        if not params:
            params = {
                "mode": "automatic",
                "mesh": [4, 4, 4],
                "shift": [0, 0, 0],
            }
        
        return params
    
    def _get_potcar_type(self, step: "Step") -> str:
        """Get POTCAR type from step (default: PBE)."""
        if hasattr(step, "parameters") and step.parameters:
            if isinstance(step.parameters, dict):
                vasp_params = step.parameters.get("engine_params", {}).get("vasp", {})
                return vasp_params.get("potcar_type", "PBE")
        return "PBE"
    
    def run_step(
        self,
        step_or_input,
        working_dir: Path | None = None,
        calculation: Optional["Calculation"] = None,
    ) -> StepResult:
        """Run VASP step.

        Accepts either an ``EngineInput`` or the legacy ``(step, working_dir)`` pair.
        """
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
            step_type = step.step_type_spec if hasattr(step, "step_type_spec") else "vasp_scf"

        # Get VASP binary
        vasp_bin = self._get_vasp_bin("std")

        # Change to working directory and run
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(wd)

            # Run VASP
            result = subprocess.run(
                [str(vasp_bin)],
                capture_output=True,
                text=True,
                timeout=None,
            )

            # Check outputs
            outcar = wd / "OUTCAR"

            success = result.returncode == 0 and outcar.exists()
            error = None
            if not success:
                error = f"VASP exited with code {result.returncode}"
                if result.stderr:
                    error += f"\n{result.stderr[:500]}"

            input_file = wd / "INCAR"

            return StepResult(
                step_type_spec=step_type,
                input_file=input_file,
                success=success,
                error=error,
                output_file=outcar if outcar.exists() else None,
                return_code=result.returncode,
            )
        finally:
            os.chdir(old_cwd)

