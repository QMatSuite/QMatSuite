"""
Helper functions for extracting and formatting kpoints for Wannier90 steps.

This module handles:
- Extracting kpoints from nscf step input files
- Canonicalizing kpoint coordinates
- Formatting kpoints for Wannier90 .win files
"""

from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np

from quantumvitas.io.parser.qe_parser import QEInputParser
from quantumvitas.io.model import QECardType


def extract_kpoints_from_qe_input(qe_input_file: Path) -> Optional[List[List[float]]]:
    """
    Extract kpoints list from a QE input file.
    
    Args:
        qe_input_file: Path to QE input file (e.g., nscf.in)
        
    Returns:
        List of kpoints [[kx, ky, kz], ...] in fractional coordinates, or None if not found.
        Order is preserved exactly as in the input file.
    """
    if not qe_input_file.exists():
        return None
    
    parser = QEInputParser()
    qe_input = parser.parse_file(qe_input_file)
    
    kpoints_card = qe_input.get_card(QECardType.K_POINTS)
    if not kpoints_card or not kpoints_card.data:
        return None
    
    # Handle different K_POINTS formats
    option = (kpoints_card.option or "").lower()
    
    if "automatic" in option:
        # Automatic mesh - cannot extract explicit kpoints
        return None
    
    if "crystal" in option or "tpiba" in option:
        # Explicit kpoints with count line
        data = kpoints_card.data
        if not data:
            return None
        
        # First line might be count (single integer) - skip it
        start_idx = 0
        if isinstance(data[0], (list, tuple)) and len(data[0]) == 1:
            start_idx = 1
        elif isinstance(data[0], (int, float)) and len(data) > 1:
            start_idx = 1
        
        kpoints = []
        for i in range(start_idx, len(data)):
            row = data[i]
            if isinstance(row, (list, tuple)) and len(row) >= 3:
                # Extract kx, ky, kz (ignore weight if present)
                kx, ky, kz = float(row[0]), float(row[1]), float(row[2])
                kpoints.append([kx, ky, kz])
        
        return kpoints if kpoints else None
    
    return None


def canonicalize_kpoint(kpt: List[float], tol: float = 1e-12) -> List[float]:
    """
    Canonicalize a kpoint coordinate (snap near 0 and 1).
    
    Args:
        kpt: [kx, ky, kz] in fractional coordinates
        tol: Tolerance for snapping
        
    Returns:
        Canonicalized [kx, ky, kz]
    """
    canonical = []
    for coord in kpt:
        # Snap to 0 if very close
        if abs(coord) < tol:
            canonical.append(0.0)
        # Snap to 0 if very close to 1 (wrap to 0)
        elif abs(coord - 1.0) < tol:
            canonical.append(0.0)
        # Snap to 0 if very close to -1 (wrap to 0)
        elif abs(coord + 1.0) < tol:
            canonical.append(0.0)
        else:
            canonical.append(float(coord))
    
    return canonical


def format_kpoint_for_w90(kpt: List[float]) -> str:
    """
    Format a kpoint for Wannier90 .win file with stable formatting.
    
    Args:
        kpt: [kx, ky, kz] in fractional coordinates
        
    Returns:
        Formatted string: "  kx  ky  kz" (with 10 decimal places, consistent spacing)
    """
    canonical = canonicalize_kpoint(kpt)
    return f"  {canonical[0]:10.10f}  {canonical[1]:10.10f}  {canonical[2]:10.10f}"


def find_nscf_input_file(calculation_dir: Path, working_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Find the nscf step input file in a calculation.
    
    Args:
        calculation_dir: Path to calculation directory
        working_dir: Optional working directory (where input files are materialized)
        
    Returns:
        Path to nscf input file if found, None otherwise
    """
    # Try to load calculation.yaml to find nscf step
    calc_yaml = calculation_dir / "calculation.yaml"
    if not calc_yaml.exists():
        return None
    
    try:
        import yaml
        calc_data = yaml.safe_load(calc_yaml.read_text()) or {}
        steps = calc_data.get("steps", [])
        
        # Find nscf step
        # calculation.yaml steps use step_type_gen (GEN layer) for workflow-level representation
        nscf_step = None
        for step_entry in steps:
            step_type_gen = step_entry.get("step_type_gen", "").lower()
            if step_type_gen == "nscf":
                nscf_step = step_entry
                break
        
        if not nscf_step:
            return None
        
        # Try to find nscf input file
        # Check working_dir first (where materialized files are)
        if working_dir:
            candidates = [
                working_dir / "nscf.in",
                working_dir / "nscf.scf",  # Some naming conventions
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate
        
        # Check calculation_dir/raw
        raw_dir = calculation_dir / "raw"
        if raw_dir.exists():
            candidates = [
                raw_dir / "nscf.in",
                raw_dir / "nscf.scf",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate
        
        # Try step input path from calculation.yaml
        step_input = nscf_step.get("input")
        if step_input:
            input_path = Path(step_input)
            if not input_path.is_absolute():
                if working_dir:
                    candidate = working_dir / input_path
                    if candidate.exists():
                        return candidate
                candidate = calculation_dir / input_path
                if candidate.exists():
                    return candidate
        
    except Exception:
        pass
    
    return None


def extract_kpoints_from_nscf_step(
    calculation_dir: Path,
    working_dir: Optional[Path] = None
) -> Optional[List[List[float]]]:
    """
    Extract kpoints from the nscf step input file, preserving order.
    
    Args:
        calculation_dir: Path to calculation directory
        working_dir: Optional working directory where input files are materialized
        
    Returns:
        List of kpoints [[kx, ky, kz], ...] in the exact order from nscf input, or None
    """
    nscf_input = find_nscf_input_file(calculation_dir, working_dir)
    if not nscf_input:
        return None
    
    return extract_kpoints_from_qe_input(nscf_input)

