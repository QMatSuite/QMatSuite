"""
Calculation analysis utilities (parsers, plotting, and structure visualization).

Exports are resolved lazily so importing ``qmatsuite.analysis`` does not
eagerly import heavy visualization stacks (matplotlib/pymatgen).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
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
    # Structure visualization
    "visualize_structure",
    "plot_structure_3d",
    "detect_bonds",
    "build_bonds",
    "generate_boundary_atoms",
    "make_supercell",
    "StructurePlotOptions",
    "StructureVisualizationResult",
    "Bond",
    "BoundaryAtom",
]

_EXPORT_MAP = {
    # parsers
    "SCFResult": ("qmatsuite.analysis.parsers", "SCFResult"),
    "SCFIteration": ("qmatsuite.analysis.parsers", "SCFIteration"),
    "DOSData": ("qmatsuite.analysis.parsers", "DOSData"),
    "BandStructureData": ("qmatsuite.analysis.parsers", "BandStructureData"),
    "HighSymmetryPoint": ("qmatsuite.analysis.parsers", "HighSymmetryPoint"),
    "parse_scf_output": ("qmatsuite.analysis.parsers", "parse_scf_output"),
    "parse_dos_data": ("qmatsuite.analysis.parsers", "parse_dos_data"),
    "parse_bands_gnu": ("qmatsuite.analysis.parsers", "parse_bands_gnu"),
    "parse_fermi_from_scf_output": ("qmatsuite.analysis.parsers", "parse_fermi_from_scf_output"),
    "find_bands_files": ("qmatsuite.analysis.parsers", "find_bands_files"),
    "find_dos_files": ("qmatsuite.analysis.parsers", "find_dos_files"),
    # plotting
    "plot_dos": ("qmatsuite.analysis.plotting", "plot_dos"),
    "plot_dos_comparison": ("qmatsuite.analysis.plotting", "plot_dos_comparison"),
    "plot_bands": ("qmatsuite.analysis.plotting", "plot_bands"),
    "plot_bands_comparison": ("qmatsuite.analysis.plotting", "plot_bands_comparison"),
    "plot_band_with_dos": ("qmatsuite.analysis.plotting", "plot_band_with_dos"),
    "plot_scf_convergence": ("qmatsuite.analysis.plotting", "plot_scf_convergence"),
    "save_figure": ("qmatsuite.analysis.plotting", "save_figure"),
    # kpath
    "KPathSegment": ("qmatsuite.analysis.kpath", "KPathSegment"),
    "KPathResult": ("qmatsuite.analysis.kpath", "KPathResult"),
    "generate_kpath": ("qmatsuite.analysis.kpath", "generate_kpath"),
    "kpath_to_qe_input_data": ("qmatsuite.analysis.kpath", "kpath_to_qe_input_data"),
    # structure_viz
    "visualize_structure": ("qmatsuite.analysis.structure_viz", "visualize_structure"),
    "plot_structure_3d": ("qmatsuite.analysis.structure_viz", "plot_structure_3d"),
    "detect_bonds": ("qmatsuite.analysis.structure_viz", "detect_bonds"),
    "build_bonds": ("qmatsuite.analysis.structure_viz", "build_bonds"),
    "generate_boundary_atoms": ("qmatsuite.analysis.structure_viz", "generate_boundary_atoms"),
    "make_supercell": ("qmatsuite.analysis.structure_viz", "make_supercell"),
    "StructurePlotOptions": ("qmatsuite.analysis.structure_viz", "StructurePlotOptions"),
    "StructureVisualizationResult": ("qmatsuite.analysis.structure_viz", "StructureVisualizationResult"),
    "Bond": ("qmatsuite.analysis.structure_viz", "Bond"),
    "BoundaryAtom": ("qmatsuite.analysis.structure_viz", "BoundaryAtom"),
}


def __getattr__(name: str) -> Any:
    """Lazily load exported analysis symbols."""
    target = _EXPORT_MAP.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = target
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Expose lazy exports in interactive inspection."""
    return sorted(set(globals()) | set(__all__))
