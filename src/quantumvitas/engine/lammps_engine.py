"""LAMMPS engine implementation."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from pymatgen.core import Structure

from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
from quantumvitas.core.engines.qe_calculation import StepResult
from quantumvitas.engine.base import Engine, EngineConfig
from quantumvitas.engine.lammps_potentials import (
    stage_potentials,
    validate_custom_script_assets,
    StagedPotentials,
)
from quantumvitas.engine.lammps_writer import (
    render_lammps_template,
    get_template_for_step_type,
    build_template_context,
)
from quantumvitas.io.lammps_data import write_lammps_data
from quantumvitas.io.structure_io import read_structure

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.calculation.step import Step

logger = logging.getLogger(__name__)


def _format_dir_listing(dir_path: Path, max_items: int = 200) -> str:
    """
    Format directory listing with file sizes and mtimes for debug output.
    
    Args:
        dir_path: Directory to list
        max_items: Maximum number of items to list
        
    Returns:
        Formatted string with file info
    """
    if not dir_path.exists():
        return f"<directory does not exist: {dir_path}>"
    
    if not dir_path.is_dir():
        return f"<not a directory: {dir_path}>"
    
    try:
        items = sorted(dir_path.iterdir())
        if len(items) > max_items:
            items = items[:max_items]
            truncated = True
        else:
            truncated = False
        
        lines = []
        for item in items:
            try:
                stat = item.stat()
                size = stat.st_size
                mtime = stat.st_mtime
                item_type = "DIR" if item.is_dir() else "FILE"
                lines.append(f"  {item_type:4s} {item.name:50s} size={size:10d} mtime={mtime:.3f}")
            except Exception as e:
                lines.append(f"  ERR  {item.name:50s} (stat failed: {e})")
        
        result = "\n".join(lines)
        if truncated:
            total_count = len(list(dir_path.iterdir()))
            result += f"\n  ... (truncated, showing first {max_items} of {total_count} items)"
        
        return result
    except Exception as e:
        return f"<listing failed: {e}>"


class LammpsEngine(Engine):
    """LAMMPS classical molecular dynamics engine."""

    name = "lammps"

    def __init__(self, config: Optional[EngineConfig] = None):
        super().__init__(config or EngineConfig(name="lammps"))
        self._lammps_bin: Optional[Path] = None

    @property
    def supported_presets(self) -> list[str]:
        """
        LAMMPS supports classical simulation presets.
        
        Note: Does not support DFT-specific dimensions like 'precision' or 'magnetism'.
        
        Returns:
            List of supported preset dimensions: classical_ensemble, potential_type
        """
        return ["classical_ensemble", "potential_type"]

    def _get_lammps_bin(self, variant: str = "serial") -> Path:
        """Get LAMMPS binary path, caching result."""
        if self._lammps_bin is None:
            self._lammps_bin = resolve_lammps_bin(variant)
        return self._lammps_bin

    def materialize_inputs(
        self,
        step,  # Can be Step or StructureStepSpec
        working_dir: Path,
        calculation: "Calculation",
    ) -> None:
        """
        Generate in.lammps, structure.data, stage potentials.
        
        Args:
            step: Step or StructureStepSpec object (must have step_type and parameters)
            working_dir: Working directory (will be created if needed)
            calculation: Calculation context
        """
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Get parameters from step spec
        # StructureStepSpec has .parameters as a dict
        # Step dataclass doesn't have parameters (need to load from step.yaml)
        params = getattr(step, "parameters", None) or {}
        step_type = getattr(step, "step_type", None) or ""
        
        # Validate custom_script assets if present
        validate_custom_script_assets(params)
        
        # Handle restart_from
        restart_file = None
        if "restart_from" in params:
            restart_file = self._resolve_restart_artifact(
                step=step,
                calculation=calculation,
            )
        
        # Get structure (unless restart_from)
        structure = None
        if not restart_file:
            structure = self._get_structure(calculation)
            if structure is None:
                raise ValueError("Calculation has no structure_id and restart_from not specified")
            
            # Write structure.data
            step_ulid = step.meta.id if hasattr(step, "meta") and hasattr(step.meta, "id") else ""
            atom_style = params.get("atom_style", "atomic")
            write_lammps_data(
                structure=structure,
                path=working_dir / "structure.data",
                atom_style=atom_style,
                step_ulid=step_ulid,
            )
        
        # Handle custom_script mode
        if "custom_script" in params:
            self._materialize_custom_script(
                step=step,
                working_dir=working_dir,
                calculation=calculation,
                structure=structure,
            )
            return
        
        # Template-based generation
        # Get potential configuration
        potential_ref = params.get("potential")
        if not potential_ref:
            raise ValueError("potential not specified in step parameters")
        
        potentials_dir = working_dir / "potentials"
        if structure is None:
            # For restart, we still need structure for element mapping
            # Try to get from calculation
            structure = self._get_structure(calculation)
            if structure is None:
                # Fallback: use a minimal structure (will be overridden by restart)
                # This is a workaround - ideally restart should include structure info
                logger.warning("No structure available for restart step, using placeholder")
                from pymatgen.core import Lattice, Structure
                structure = Structure(
                    lattice=Lattice.cubic(10.0),
                    species=["H"],
                    coords=[[0, 0, 0]],
                )
        
        # Check if potential is inline (dict) or reference (string)
        if isinstance(potential_ref, dict):
            # Inline potential definition (e.g., LJ)
            # No external files to stage
            pair_style_block = self._build_inline_pair_style(potential_ref, params, structure)
            staged_potentials = None
        else:
            # Reference to potential in potential_map
            staged_potentials = stage_potentials(
                calculation=calculation,
                potential_ref=potential_ref,
                target_dir=potentials_dir,
                structure=structure,
            )
        
        # Generate input script
        template_name = get_template_for_step_type(step_type)
        
        # Adjust template for ensemble
        if step_type == "lammps_md":
            ensemble = params.get("ensemble", "nvt")
            if ensemble == "npt":
                template_name = "md_npt.in.j2"
            elif ensemble == "nve":
                template_name = "md_nve.in.j2"
            else:
                template_name = "md_nvt.in.j2"
        
        # Get pair_style_block from staged potentials or inline definition
        if staged_potentials:
            pair_style_block = staged_potentials.pair_style_block
        # else: pair_style_block was already set from inline definition
        
        context = build_template_context(
            step=step,
            calculation=calculation,
            pair_style_block=pair_style_block,
            restart_file=str(restart_file) if restart_file else None,
        )
        
        script_content = render_lammps_template(template_name, context)
        
        # Write input script
        (working_dir / "in.lammps").write_text(script_content)
        logger.debug(f"Generated LAMMPS input script: {working_dir / 'in.lammps'}")

    def _get_structure(self, calculation: "Calculation") -> Optional[Structure]:
        """Get structure from calculation."""
        structure_id = calculation.structure_id
        if structure_id is None:
            return None
        
        # Load structure from project
        structure_ref = calculation.project.get_structure(structure_id)
        structure_path = structure_ref.resolve_path(calculation.project.root)
        structure = read_structure(structure_path)
        
        # Convert to pymatgen Structure if needed
        if not isinstance(structure, Structure):
            if hasattr(structure, "as_dict"):
                structure = Structure.from_dict(structure.as_dict())
            else:
                raise ValueError(f"Cannot convert structure type {type(structure)}")
        
        return structure

    def _build_inline_pair_style(
        self,
        potential_def: dict,
        params: dict,
        structure: Structure,
    ) -> str:
        """
        Build pair_style/pair_coeff commands from inline potential definition.
        
        Used for simple potentials like LJ that don't require external files.
        
        Args:
            potential_def: Inline potential dict from step parameters
            params: Full step parameters
            structure: Structure for element/type mapping
        
        Returns:
            Multi-line string with pair_style and pair_coeff commands
        """
        style = potential_def.get("style")
        if not style:
            raise ValueError("Inline potential missing 'style' field")
        
        cutoff = potential_def.get("cutoff", 10.0)
        
        lines = []
        
        # Build pair_style line
        if "/" in style:
            # Style with options, e.g., "lj/cut"
            lines.append(f"pair_style {style} {cutoff}")
        else:
            lines.append(f"pair_style {style}")
        
        # Build pair_coeff lines from params
        pair_params = potential_def.get("params", {})
        if pair_params:
            # params is dict like {"1 1": "1.0 1.0"}
            for type_pair, coeff_str in pair_params.items():
                lines.append(f"pair_coeff {type_pair} {coeff_str}")
        else:
            # Default: pair_coeff * * for all types
            lines.append("pair_coeff * *")
        
        # Handle LJ system setup from params (masses, type labels)
        lj_system = params.get("lj_system", {})
        mass_lines = []
        if lj_system:
            masses = lj_system.get("masses", {})
            for type_id, mass in masses.items():
                mass_lines.append(f"mass {type_id} {mass}")
        
        # Combine: masses come before pair_style
        result_lines = mass_lines + lines
        
        return "\n".join(result_lines)

    def _resolve_restart_artifact(
        self,
        step: "Step",
        calculation: "Calculation",
    ) -> Path:
        """
        Resolve restart_from reference to actual file.
        
        Rules (per constitution):
        - Must reference same-calc upstream step
        - Cross-calc forbidden → hard error
        - Missing artifact → hard error (no auto-run)
        
        Search order:
        1. restart.bin (preferred - includes velocities)
        2. final.data (fallback - structure only)
        
        Returns:
            Path to restart file
        
        Raises:
            ValueError: Cross-calc reference
            FileNotFoundError: Artifact not found
        """
        params = step.parameters if hasattr(step, "parameters") else {}
        restart_from = params.get("restart_from")
        if not restart_from:
            raise ValueError("restart_from not specified")
        
        # Find referenced step in calculation
        # restart_from can be step ULID, slug, or index
        ref_step = None
        for calc_step in calculation.steps:
            if (
                (hasattr(calc_step, "meta") and calc_step.meta.id == restart_from)
                or (hasattr(calc_step, "meta") and hasattr(calc_step.meta, "slug") and calc_step.meta.slug == restart_from)
                or str(calc_step) == restart_from
            ):
                ref_step = calc_step
                break
        
        if ref_step is None:
            raise ValueError(f"restart_from references unknown step: {restart_from}")
        
        # Find artifact in reference step's workdir
        ref_step_ulid = ref_step.meta.id if hasattr(ref_step, "meta") and hasattr(ref_step.meta, "id") else ""
        if not ref_step_ulid:
            raise ValueError(f"Reference step has no ULID")
        
        ref_workdir = calculation.io.raw_dir / ref_step_ulid
        
        # Debug: Log search context
        print(f"[LAMMPS-DEBUG] resolve_restart_artifact: step_ulid={step.meta.id if hasattr(step, 'meta') else 'unknown'}, "
              f"restart_from={restart_from}, upstream_step_ulid={ref_step_ulid}")
        print(f"[LAMMPS-DEBUG] resolve_restart_artifact: calculation.raw_dir={calculation.io.raw_dir}, "
              f"ref_workdir={ref_workdir}")
        print(f"[LAMMPS-DEBUG] resolve_restart_artifact: looking for restart.bin|restart.*.bin|final.data in {ref_workdir}")
        
        # Search for restart.bin first
        restart_bin = ref_workdir / "restart.bin"
        if restart_bin.exists():
            print(f"[LAMMPS-DEBUG] resolve_restart_artifact: found restart.bin at {restart_bin}")
            return restart_bin
        
        # Try restart.*.bin pattern
        restart_patterns = list(ref_workdir.glob("restart.*.bin"))
        if restart_patterns:
            # Use the most recent one
            selected = max(restart_patterns, key=lambda p: p.stat().st_mtime)
            print(f"[LAMMPS-DEBUG] resolve_restart_artifact: found restart.*.bin pattern, selected {selected} "
                  f"(from {len(restart_patterns)} matches)")
            return selected
        
        # Fallback to final.data
        final_data = ref_workdir / "final.data"
        if final_data.exists():
            print(f"[LAMMPS-DEBUG] resolve_restart_artifact: found final.data at {final_data}")
            return final_data
        
        # Artifact not found - print detailed diagnostics
        print(f"[LAMMPS-DEBUG] resolve_restart_artifact: FAILED - no artifact found")
        print(f"[LAMMPS-DEBUG] resolve_restart_artifact: expected files: restart.bin, restart.*.bin, final.data")
        print(f"[LAMMPS-DEBUG] resolve_restart_artifact: search path (absolute): {ref_workdir.resolve()}")
        print(f"[LAMMPS-DEBUG] resolve_restart_artifact: directory exists: {ref_workdir.exists()}")
        
        if ref_workdir.exists():
            print(f"[LAMMPS-DEBUG] resolve_restart_artifact: contents of {ref_workdir}:")
            print(_format_dir_listing(ref_workdir, max_items=200))
            
            # Also check for any .bin or .data files
            all_bin_files = list(ref_workdir.glob("*.bin"))
            all_data_files = list(ref_workdir.glob("*.data"))
            if all_bin_files:
                print(f"[LAMMPS-DEBUG] resolve_restart_artifact: found {len(all_bin_files)} .bin files (not matching restart*):")
                for f in all_bin_files[:10]:  # Limit to 10
                    print(f"  - {f.name}")
            if all_data_files:
                print(f"[LAMMPS-DEBUG] resolve_restart_artifact: found {len(all_data_files)} .data files:")
                for f in all_data_files[:10]:  # Limit to 10
                    print(f"  - {f.name}")
        else:
            # Directory doesn't exist - check parent
            parent_dir = ref_workdir.parent
            print(f"[LAMMPS-DEBUG] resolve_restart_artifact: ref_workdir does not exist, checking parent: {parent_dir}")
            if parent_dir.exists():
                print(f"[LAMMPS-DEBUG] resolve_restart_artifact: parent directory contents:")
                print(_format_dir_listing(parent_dir, max_items=50))
        
        raise FileNotFoundError(
            f"No restart artifact found for step {restart_from}. "
            f"Expected restart.bin or final.data in {ref_workdir}"
        )

    def _materialize_custom_script(
        self,
        step: "Step",
        working_dir: Path,
        calculation: "Calculation",
        structure: Optional[Structure],
    ) -> None:
        """
        Materialize custom script mode.
        
        Args:
            step: Step object
            working_dir: Working directory
            calculation: Calculation context
            structure: Structure (if available, for structure.data generation)
        """
        params = step.parameters if hasattr(step, "parameters") else {}
        custom_script = params.get("custom_script", {})
        mode = custom_script.get("mode", "override")
        
        # Generate structure.data if structure available
        if structure:
            step_ulid = step.meta.id if hasattr(step, "meta") and hasattr(step.meta, "id") else ""
            atom_style = params.get("atom_style", "atomic")
            write_lammps_data(
                structure=structure,
                path=working_dir / "structure.data",
                atom_style=atom_style,
                step_ulid=step_ulid,
            )
        
        # Stage required assets
        assets = params.get("assets", {})
        required_files = assets.get("required_files", [])
        
        if required_files:
            potentials_dir = working_dir / "potentials"
            potentials_dir.mkdir(parents=True, exist_ok=True)
            
            project_root = calculation.project.root if hasattr(calculation, "project") else Path.cwd()
            
            for file_ref in required_files:
                # file_ref can be relative to project root or absolute
                src_path = project_root / file_ref if not Path(file_ref).is_absolute() else Path(file_ref)
                if not src_path.exists():
                    raise FileNotFoundError(f"Required asset file not found: {src_path}")
                
                dst_path = potentials_dir / src_path.name
                import shutil
                shutil.copy2(src_path, dst_path)
                logger.debug(f"Staged custom script asset: {src_path} -> {dst_path}")
        
        # Write custom script
        if mode == "override":
            script_content = custom_script.get("content", "")
            if not script_content:
                raise ValueError("custom_script.override mode requires content")
            (working_dir / "in.lammps").write_text(script_content)
        elif mode == "extend":
            # For extend mode, we'd need to generate base template and inject
            # For now, raise NotImplementedError (can be implemented later)
            raise NotImplementedError("custom_script.extend mode not yet implemented")
        else:
            raise ValueError(f"Unknown custom_script mode: {mode}")

    def run_step(
        self,
        step: "Step",
        working_dir: Path,
        calculation: Optional["Calculation"] = None,
    ) -> StepResult:
        """
        Execute LAMMPS step.
        
        Args:
            step: Step object
            working_dir: Working directory with input files
            calculation: Optional calculation context
        
        Returns:
            StepResult with success status and output file paths
        """
        import subprocess
        
        lmp_bin = self._get_lammps_bin()
        
        cmd = [
            str(lmp_bin),
            "-in", "in.lammps",
            "-log", "log.lammps",
            "-screen", "none",
        ]
        
        logger.info(f"Running LAMMPS: {' '.join(cmd)}")
        logger.info(f"Working directory: {working_dir}")
        
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        
        # Check for errors
        log_path = working_dir / "log.lammps"
        error = None
        if result.returncode != 0:
            error = f"LAMMPS exited with code {result.returncode}"
            if log_path.exists():
                log_content = log_path.read_text()
                # Extract ERROR lines
                error_lines = [l for l in log_content.splitlines() if "ERROR" in l.upper()]
                if error_lines:
                    error += f"\n{error_lines[0]}"
        
        # Also check log for errors even if return code is 0
        if log_path.exists():
            log_content = log_path.read_text()
            if "ERROR" in log_content.upper():
                error_lines = [l for l in log_content.splitlines() if "ERROR" in l.upper()]
                if error_lines:
                    error = f"LAMMPS reported errors:\n" + "\n".join(error_lines[:5])
        
        return StepResult(
            step_type=step.step_type if hasattr(step, "step_type") else "",
            input_file=working_dir / "in.lammps",
            success=(result.returncode == 0 and error is None),
            error=error,
            output_file=log_path if log_path.exists() else None,
            return_code=result.returncode,
        )

