"""
Step completion ("done") detection policy.

Centralized function for determining if a step has been completed successfully.
Used by both incremental run skip logic and runner advancement.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Step types that don't have "JOB DONE" markers but have other success indicators
# Wannier90 types are kept as hardcoded set since they're legacy and will be migrated later
WANNIER90_STEP_TYPES = {"w90_preproc", "w90_run", "pw2wannier90", "wannier90", "postw90"}


def is_vasp_step(step_type: str) -> bool:
    """Check if step type belongs to VASP."""
    import quantumvitas.drivers
    from quantumvitas.core.driver_registry import DriverRegistry
    
    if not DriverRegistry.is_step_type_registered(step_type):
        return False
    return DriverRegistry.get_engine_for_step_type(step_type) == "vasp"


def is_lammps_step(step_type: str) -> bool:
    """Check if step type belongs to LAMMPS."""
    import quantumvitas.drivers
    from quantumvitas.core.driver_registry import DriverRegistry
    
    if not DriverRegistry.is_step_type_registered(step_type):
        return False
    return DriverRegistry.get_engine_for_step_type(step_type) == "lammps"


def primary_output_path(calc_raw_dir: Path, step_kind: str, step_doc: Optional[dict] = None) -> Optional[Path]:
    """
    Determine the primary output file path for a step.
    
    Args:
        calc_raw_dir: Calculation raw directory (calc/raw)
        step_kind: Step type (e.g., "scf", "nscf", "w90_run")
        step_doc: Optional step document (for Wannier90 seedname extraction)
        
    Returns:
        Path to primary output file, or None if cannot be determined
    """
    step_kind_lower = step_kind.lower()
    
    if step_kind_lower in WANNIER90_STEP_TYPES:
        # Wannier90 steps: output is <seedname>.wout
        # Try to extract seedname from step doc or use default
        seedname = "wannier"
        if step_doc:
            # Check for seedname in parameters or input_name
            params = step_doc.get("parameters", {})
            input_name = step_doc.get("input_name")
            
            # Try to extract from input_name (e.g., "diamond.win" -> "diamond")
            if input_name:
                if input_name.endswith(".win"):
                    seedname = input_name[:-4]
                elif input_name.endswith(".in"):
                    seedname = Path(input_name).stem
            
            # Try from parameters (some steps might have seedname parameter)
            for section in params.values():
                if isinstance(section, dict) and "seedname" in section:
                    seedname = str(section["seedname"])
                    break
        
        output_path = calc_raw_dir / f"{seedname}.wout"
        return output_path if output_path.exists() else None
    
    # QE steps: output is typically <input_stem>.out
    # We need to guess the input filename based on step type
    # This is a heuristic - in practice, the runner knows the actual input file name
    # But for done checking, we can try common patterns
    
    # Common QE output patterns
    common_inputs = [
        f"{step_kind_lower}.in",
        f"{step_kind_lower}.pw.in",
        "scf.in",  # Fallback for scf steps
    ]
    
    for input_pattern in common_inputs:
        input_path = calc_raw_dir / input_pattern
        if input_path.exists():
            output_path = calc_raw_dir / f"{input_path.stem}.out"
            if output_path.exists():
                return output_path
    
    # If no input file found, try direct output pattern
    output_path = calc_raw_dir / f"{step_kind_lower}.out"
    if output_path.exists():
        return output_path
    
    return None


def is_step_done(calc_dir: Path, step_kind: str, calc_raw_dir: Optional[Path] = None, step_doc: Optional[dict] = None) -> bool:
    """
    Check if a step has been completed successfully.
    
    This is the SINGLE SOURCE OF TRUTH for step completion detection.
    Used by both incremental run skip logic and runner advancement.
    
    Default logic:
    - For QE steps: Primary .out file exists and contains "JOB DONE."
    - For Wannier90 steps: Primary .wout file exists (minimal check)
    
    Args:
        calc_dir: Calculation directory
        step_kind: Step type (e.g., "scf", "nscf", "w90_run")
        calc_raw_dir: Optional raw directory (defaults to calc_dir / "raw")
        step_doc: Optional step document (for extracting input/output info)
        
    Returns:
        True if step is done, False otherwise
    """
    if calc_raw_dir is None:
        calc_raw_dir = calc_dir / "raw"
    
    if not calc_raw_dir.exists():
        return False
    
    step_kind_lower = step_kind.lower()
    
    # VASP steps: check for OUTCAR and OSZICAR
    if is_vasp_step(step_kind_lower):
        # VASP: check for OUTCAR (primary output) and OSZICAR (iteration log)
        # VASP steps use step-specific workdirs: calc_raw_dir / step_ulid / OUTCAR
        
        # Try to get step_ulid from step_doc
        step_ulid = None
        if step_doc:
            # Check meta.id or step_id
            meta = step_doc.get("meta", {})
            step_ulid = meta.get("id") or step_doc.get("step_id")
        
        # If we have step_ulid, check in specific workdir
        if step_ulid:
            step_workdir = calc_raw_dir / step_ulid
            outcar_path = step_workdir / "OUTCAR"
            oszicar_path = step_workdir / "OSZICAR"
        else:
            # Fallback: check in calc_raw_dir root or find in subdirectories
            outcar_path = calc_raw_dir / "OUTCAR"
            oszicar_path = calc_raw_dir / "OSZICAR"
            
            if not outcar_path.exists():
                # Look for OUTCAR in step workdirs (calc_raw_dir / step_ulid / OUTCAR)
                for subdir in calc_raw_dir.iterdir():
                    if subdir.is_dir():
                        step_outcar = subdir / "OUTCAR"
                        if step_outcar.exists():
                            outcar_path = step_outcar
                            oszicar_path = subdir / "OSZICAR"
                            break
        
        if outcar_path.exists() and oszicar_path.exists():
            # Check if OUTCAR has energy (indicates successful completion)
            try:
                outcar_text = outcar_path.read_text()
                if "free  energy   TOTEN" in outcar_text:
                    logger.debug(f"Step {step_kind}: VASP output files exist and contain energy")
                    return True
            except Exception as e:
                logger.warning(f"Step {step_kind}: Error reading OUTCAR: {e}")
        
        logger.debug(f"Step {step_kind}: VASP output files not found or incomplete")
        return False
    
    # LAMMPS steps: check for log.lammps and step-specific outputs
    if is_lammps_step(step_kind_lower):
        # LAMMPS uses isolated workdirs: calc_raw_dir / step_ulid / log.lammps
        step_ulid = None
        if step_doc:
            meta = step_doc.get("meta", {})
            step_ulid = meta.get("id") or step_doc.get("step_id")
        
        if step_ulid:
            step_workdir = calc_raw_dir / step_ulid
            log_path = step_workdir / "log.lammps"
        else:
            # Fallback: look in calc_raw_dir root
            log_path = calc_raw_dir / "log.lammps"
            step_workdir = calc_raw_dir
        
        if not log_path.exists():
            logger.debug(f"Step {step_kind}: LAMMPS log file not found at {log_path}")
            return False
        
        # Check log for completion markers
        try:
            log_content = log_path.read_text()
            # LAMMPS prints timing info at end of successful run
            if "Total wall time" in log_content or "Loop time" in log_content:
                # For relax, also check final.data exists
                if step_kind_lower == "lammps_relax":
                    final_data = step_workdir / "final.data"
                    if not final_data.exists():
                        logger.debug(f"Step {step_kind}: final.data not found")
                        return False
                logger.debug(f"Step {step_kind}: LAMMPS completed successfully")
                return True
            else:
                logger.debug(f"Step {step_kind}: LAMMPS log incomplete (no timing info)")
                return False
        except Exception as e:
            logger.warning(f"Step {step_kind}: Error reading log: {e}")
            return False
    
    # Determine primary output file
    output_path = primary_output_path(calc_raw_dir, step_kind, step_doc)
    
    if output_path is None or not output_path.exists():
        logger.debug(f"Step {step_kind}: primary output file not found")
        return False
    
    # Check content based on step type
    if step_kind_lower in WANNIER90_STEP_TYPES:
        # Wannier90: just check file exists (minimal check)
        # Could enhance to check for "Exiting..." or specific completion markers
        logger.debug(f"Step {step_kind}: Wannier90 output exists: {output_path}")
        return True
    
    # QE steps: check for "JOB DONE" marker
    try:
        output_text = output_path.read_text()
        if "JOB DONE" in output_text:
            logger.debug(f"Step {step_kind}: JOB DONE found in {output_path}")
            return True
        else:
            logger.debug(f"Step {step_kind}: JOB DONE not found in {output_path}")
            return False
    except Exception as e:
        logger.warning(f"Step {step_kind}: Error reading output file {output_path}: {e}")
        return False

