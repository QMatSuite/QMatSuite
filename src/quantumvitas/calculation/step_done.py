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
WANNIER90_STEP_TYPES = {"w90_preproc", "w90_run", "pw2wannier90", "wannier90", "postw90"}


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

