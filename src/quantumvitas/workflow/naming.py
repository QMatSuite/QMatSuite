"""
Centralized file naming conventions for QuantumVITAS workflows.

This module provides consistent naming patterns for:
- QE input files generated during workflow execution
- QE output files produced by calculations
- Analysis output files (plots, data)

The naming conventions are used by:
- workflow/workflow.py (when generating input files)
- analysis/parsers.py (when locating output files)
- cli/main.py (when auto-detecting files)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class WorkflowFileNaming:
    """
    Centralized naming conventions for workflow files.
    
    Handles file naming patterns for both generation and discovery.
    Each step type has a specific naming pattern that allows
    auto-detection during analysis.
    
    Example file patterns in a workflow's raw/ directory:
        scf.in, scf.out                    # SCF calculation (pw.x)
        nscf.in, nscf.out                  # NSCF calculation (pw.x)
        bands.in, bands.out                # Band structure (pw.x calc='bands')
        bandspp.bands.in, bandspp.bands.out  # bands.x post-processing
        dos.dos.in, dos.dos.out            # dos.x post-processing
        si.bands.dat, si.bands.dat.gnu     # Band data files (from bands.x)
        si.dos.dat                         # DOS data files (from dos.x)
    """
    
    # Post-processing step types that use their own executable (not pw.x)
    POST_PROCESSING_TYPES = frozenset({
        "dos", "bands", "pp", "projwfc", "ph", "q2r", 
        "matdyn", "dynmat", "sumpdos", "band_interpolation",
    })
    
    # pw.x calculation types
    PW_CALCULATION_TYPES = frozenset({
        "scf", "nscf", "relax", "vc-relax", "md", "vc-md", "bands_pw",
    })
    
    @classmethod
    def input_extension(cls, step_type: str) -> str:
        """
        Get appropriate input file extension for a step type.
        
        Post-processing steps get .<type>.in extension for clarity.
        pw.x steps get simple .in extension.
        """
        step_lower = step_type.lower()
        if step_lower in cls.POST_PROCESSING_TYPES:
            return f".{step_lower}.in"
        return ".in"
    
    @classmethod
    def output_extension(cls, step_type: str) -> str:
        """Get output file extension for a step type."""
        step_lower = step_type.lower()
        if step_lower in cls.POST_PROCESSING_TYPES:
            return f".{step_lower}.out"
        return ".out"
    
    @classmethod
    def input_filename(cls, step_id: str, step_type: str) -> str:
        """Generate input filename for a step."""
        ext = cls.input_extension(step_type)
        return f"{step_id}{ext}"
    
    @classmethod
    def output_filename(cls, step_id: str, step_type: str) -> str:
        """Generate expected output filename for a step."""
        ext = cls.output_extension(step_type)
        return f"{step_id}{ext}"


@dataclass
class BandAnalysisFiles:
    """
    Container for files needed for band structure analysis.
    
    All paths are resolved (absolute).
    """
    bands_gnu: Optional[Path] = None      # *.bands.dat.gnu - band energies
    bands_pp_out: Optional[Path] = None   # bands.x output - high-sym points
    pw_output: Optional[Path] = None      # pw.x output (scf/nscf/bands) - reciprocal lattice
    fermi_source: Optional[Path] = None   # File to extract Fermi energy from
    structure_file: Optional[Path] = None # Structure file for pymatgen labeling
    
    @property
    def has_minimum_files(self) -> bool:
        """Check if we have the minimum files for analysis."""
        return self.bands_gnu is not None
    
    @property
    def can_label_kpoints(self) -> bool:
        """Check if we can properly label k-points."""
        return self.bands_pp_out is not None and self.pw_output is not None
    
    def to_dict(self) -> Dict[str, Optional[str]]:
        """Convert to dict of string paths."""
        return {
            "bands_gnu": str(self.bands_gnu) if self.bands_gnu else None,
            "bands_pp_out": str(self.bands_pp_out) if self.bands_pp_out else None,
            "pw_output": str(self.pw_output) if self.pw_output else None,
            "fermi_source": str(self.fermi_source) if self.fermi_source else None,
            "structure_file": str(self.structure_file) if self.structure_file else None,
        }


def find_band_analysis_files(
    directory: Path,
    prefix: Optional[str] = None,
) -> BandAnalysisFiles:
    """
    Find band structure analysis files in a directory.
    
    Searches for:
    - bands.dat.gnu files (band energies in gnuplot format)
    - bands.x output files (high-symmetry point info)
    - pw.x output files (reciprocal lattice vectors, Fermi energy)
    - Structure files for pymatgen labeling
    
    Args:
        directory: Directory to search (typically workflow/raw/)
        prefix: Optional prefix to filter files (e.g., step id)
        
    Returns:
        BandAnalysisFiles with found files
    """
    result = BandAnalysisFiles()
    directory = Path(directory).resolve()
    
    if not directory.exists():
        return result
    
    # Preference order for each file type
    bands_gnu_candidates: List[Tuple[int, Path]] = []
    bands_pp_out_candidates: List[Tuple[int, Path]] = []
    nscf_out_candidates: List[Tuple[int, Path]] = []
    scf_out_candidates: List[Tuple[int, Path]] = []
    bands_pw_out_candidates: List[Tuple[int, Path]] = []
    
    for file in directory.iterdir():
        if not file.is_file():
            continue
        
        name = file.name.lower()
        
        # Filter by prefix if provided
        if prefix and not name.startswith(prefix.lower()):
            continue
        
        # Band data file (gnuplot format)
        if name.endswith('.dat.gnu') or 'bands.dat.gnu' in name:
            # Prefer files with 'bands' in name
            priority = 0 if 'bands' in name else 1
            bands_gnu_candidates.append((priority, file))
        
        # bands.x post-processing output (contains high-sym points)
        elif name.endswith('.out'):
            if '.bands.out' in name or 'bandspp' in name:
                priority = 0 if '.bands.out' in name else 1
                bands_pp_out_candidates.append((priority, file))
            elif 'nscf' in name:
                nscf_out_candidates.append((0, file))
            elif 'scf' in name and 'nscf' not in name:
                scf_out_candidates.append((0, file))
            # pw.x bands calculation output (calc='bands')
            elif 'bands' in name and '.bands.out' not in name and 'bandspp' not in name:
                bands_pw_out_candidates.append((0, file))
    
    # Select best candidate for each
    if bands_gnu_candidates:
        result.bands_gnu = sorted(bands_gnu_candidates)[0][1]
    
    if bands_pp_out_candidates:
        result.bands_pp_out = sorted(bands_pp_out_candidates)[0][1]
    
    # Prefer NSCF for Fermi energy (denser k-grid)
    if nscf_out_candidates:
        result.fermi_source = sorted(nscf_out_candidates)[0][1]
        result.pw_output = result.fermi_source
    elif scf_out_candidates:
        result.fermi_source = sorted(scf_out_candidates)[0][1]
        result.pw_output = result.fermi_source
    
    # If we have bands.x output but no pw.x output for lattice,
    # try the pw.x bands calculation output
    if result.pw_output is None and bands_pw_out_candidates:
        result.pw_output = sorted(bands_pw_out_candidates)[0][1]
    
    return result


def find_workflow_raw_dir(
    workflow_dir: Path,
    working_dir_name: str = "raw",
) -> Path:
    """
    Get the raw/working directory for a workflow.
    
    Args:
        workflow_dir: Path to workflow directory
        working_dir_name: Name of working directory (default: "raw")
        
    Returns:
        Path to raw directory (may not exist)
    """
    return workflow_dir / working_dir_name


def find_workflow_results_dir(
    workflow_dir: Path,
    results_dir_name: str = "results",
) -> Path:
    """
    Get the results directory for a workflow.
    
    Args:
        workflow_dir: Path to workflow directory
        results_dir_name: Name of results directory (default: "results")
        
    Returns:
        Path to results directory (may not exist)
    """
    return workflow_dir / results_dir_name

