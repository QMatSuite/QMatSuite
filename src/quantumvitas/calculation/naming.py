"""
Centralized file naming conventions for QuantumVITAS calculations.

This module provides consistent naming patterns for:
- QE input files generated during calculation execution
- QE output files produced by calculations
- Analysis output files (plots, data)

The naming conventions are used by:
- calculation/calculation.py (when generating input files)
- analysis/parsers.py (when locating output files)
- cli/main.py (when auto-detecting files)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class CalculationFileNaming:
    """
    Centralized naming conventions for calculation files.
    
    Handles file naming patterns for both generation and discovery.
    Each step type has a specific naming pattern that allows
    auto-detection during analysis.
    
    Example file patterns in a calculation's raw/ directory:
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
        "pw2wannier",  # pw2wannier90.x uses pw2wan.in / pw2wan.out naming
    })
    
    # pw.x calculation types
    PW_CALCULATION_TYPES = frozenset({
        "scf", "nscf", "relax", "vc-relax", "md", "vc-md", "bandspw",
    })
    
    @classmethod
    def input_extension(cls, step_type_gen: str) -> str:
        """
        Get appropriate input file extension for a step type.
        
        Post-processing steps get .<type>.in extension for clarity.
        pw.x steps get simple .in extension.
        Special case: pw2wannier uses .in (not .pw2wannier.in) for brevity.
        """
        step_lower = step_type_gen.lower()
        if step_lower == "pw2wannier":
            # Special case: use .in (pw2wan.in) instead of .pw2wannier.in
            return ".in"
        if step_lower in cls.POST_PROCESSING_TYPES:
            return f".{step_lower}.in"
        return ".in"
    
    @classmethod
    def output_extension(cls, step_type_gen: str) -> str:
        """Get output file extension for a step type."""
        step_lower = step_type_gen.lower()
        if step_lower == "pw2wannier":
            # Special case: use .out (pw2wan.out) instead of .pw2wannier.out
            return ".out"
        if step_lower in cls.POST_PROCESSING_TYPES:
            return f".{step_lower}.out"
        return ".out"
    
    @classmethod
    def input_filename(cls, step_type_gen: str, working_dir: Optional[Path] = None) -> str:
        """
        Generate human-readable input filename for a step based on step_type_gen.
        
        Uses step_type_gen (e.g., "scf", "nscf") instead of ULID for human readability.
        If multiple steps of the same type exist, numbers them (e.g., "scf-1.in", "scf-2.in").
        
        Args:
            step_type_gen: Gen step type (e.g., "scf", "nscf", "dos")
            working_dir: Optional working directory to check for existing files
            
        Returns:
            Filename like "scf.in" or "scf-1.in" if duplicates exist
        """
        step_lower = step_type_gen.lower()
        if step_lower == "pw2wannier":
            # Special case: use "pw2wan.in" instead of "pw2wannier.in"
            return "pw2wan.in"
        
        ext = cls.input_extension(step_type_gen)
        base_name = f"{step_type_gen}{ext}"
        
        # If working_dir is provided, check for duplicates and number them
        if working_dir and working_dir.exists():
            base_stem = step_type_gen
            existing_files = list(working_dir.glob(f"{base_stem}*{ext}"))
            
            # Count how many files with this step_type already exist
            # Files can be: step_type.in, step_type-1.in, step_type-2.in, etc.
            existing_numbers = set()
            for file in existing_files:
                stem = file.stem
                if stem == base_stem:
                    existing_numbers.add(0)  # Base name exists
                elif stem.startswith(f"{base_stem}-"):
                    # Try to extract number from "step_type-N"
                    suffix = stem[len(f"{base_stem}-"):]
                    try:
                        num = int(suffix)
                        existing_numbers.add(num)
                    except ValueError:
                        pass
            
            # If base name exists or we have numbered versions, add a number
            if existing_numbers:
                # Find the next available number
                next_num = 1
                while next_num in existing_numbers:
                    next_num += 1
                base_name = f"{base_stem}-{next_num}{ext}"
        
        return base_name
    
    @classmethod
    def output_filename(cls, step_type_gen: str, working_dir: Optional[Path] = None) -> str:
        """
        Generate expected output filename for a step based on step_type_gen.
        
        Uses step_type_gen (e.g., "scf", "nscf") instead of ULID for human readability.
        If multiple steps of the same type exist, numbers them (e.g., "scf-1.out", "scf-2.out").
        
        Args:
            step_type_gen: Gen step type (e.g., "scf", "nscf", "dos")
            working_dir: Optional working directory to check for existing files
            
        Returns:
            Filename like "scf.out" or "scf-1.out" if duplicates exist
        """
        ext = cls.output_extension(step_type_gen)
        base_name = f"{step_type_gen}{ext}"
        
        # If working_dir is provided, check for duplicates and number them
        if working_dir and working_dir.exists():
            base_stem = step_type_gen
            existing_files = list(working_dir.glob(f"{base_stem}*{ext}"))
            
            # Count how many files with this step_type_gen already exist
            existing_numbers = set()
            for file in existing_files:
                stem = file.stem
                if stem == base_stem:
                    existing_numbers.add(0)  # Base name exists
                elif stem.startswith(f"{base_stem}-"):
                    # Try to extract number from "step_type-N"
                    suffix = stem[len(f"{base_stem}-"):]
                    try:
                        num = int(suffix)
                        existing_numbers.add(num)
                    except ValueError:
                        pass
            
            # If base name exists or we have numbered versions, add a number
            if existing_numbers:
                # Find the next available number
                next_num = 1
                while next_num in existing_numbers:
                    next_num += 1
                base_name = f"{base_stem}-{next_num}{ext}"
        
        return base_name


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
        directory: Directory to search (typically calculation/raw/)
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
    bandspw_out_candidates: List[Tuple[int, Path]] = []
    
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
                bandspw_out_candidates.append((0, file))
    
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
    if result.pw_output is None and bandspw_out_candidates:
        result.pw_output = sorted(bandspw_out_candidates)[0][1]
    
    return result


def find_calculation_raw_dir(
    calculation_dir: Path,
    working_dir_name: str = "raw",
) -> Path:
    """
    Get the raw/working directory for a calculation.
    
    Args:
        calculation_dir: Path to calculation directory
        working_dir_name: Name of working directory (default: "raw")
        
    Returns:
        Path to raw directory (may not exist)
    """
    return calculation_dir / working_dir_name


def find_calculation_results_dir(
    calculation_dir: Path,
    results_dir_name: str = "results",
) -> Path:
    """
    Get the results directory for a calculation.
    
    Args:
        calculation_dir: Path to calculation directory
        results_dir_name: Name of results directory (default: "results")
        
    Returns:
        Path to results directory (may not exist)
    """
    return calculation_dir / results_dir_name

