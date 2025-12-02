"""
Workflow analysis utilities (DOS, bands, energy summaries).

This module provides:
- Parsers for QE output files (SCF, DOS, Bands)
- Matplotlib-based plotting functions
- Data structures for analysis results
- K-path generation for band structure calculations
"""

from .workflow_analysis import analyze_workflow
from .parsers import (
    # Data classes
    SCFResult,
    SCFIteration,
    DOSData,
    BandStructureData,
    HighSymmetryPoint,
    # Parsers
    parse_scf_output,
    parse_dos_data,
    parse_bands_gnu,
    parse_fermi_from_scf_output,
    # File finders
    find_bands_files,
    find_dos_files,
)
from .plotting import (
    plot_dos,
    plot_dos_comparison,
    plot_bands,
    plot_bands_comparison,
    plot_band_with_dos,
    plot_scf_convergence,
    save_figure,
)
from .kpath import (
    KPathSegment,
    KPathResult,
    generate_kpath,
    kpath_to_qe_input_data,
)

__all__ = [
    # Workflow analysis
    "analyze_workflow",
    # Data classes
    "SCFResult",
    "SCFIteration",
    "DOSData",
    "BandStructureData",
    "HighSymmetryPoint",
    # Parsers
    "parse_scf_output",
    "parse_dos_data",
    "parse_bands_gnu",
    "parse_fermi_from_scf_output",
    # File finders
    "find_bands_files",
    "find_dos_files",
    # Plotting
    "plot_dos",
    "plot_dos_comparison",
    "plot_bands",
    "plot_bands_comparison",
    "plot_band_with_dos",
    "plot_scf_convergence",
    "save_figure",
    # K-path generation
    "KPathSegment",
    "KPathResult",
    "generate_kpath",
    "kpath_to_qe_input_data",
]
