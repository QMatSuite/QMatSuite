"""
Plotting functions for QE analysis data.

This module provides matplotlib-based plotting for:
- DOS (Density of States)
- Band structures
- SCF convergence

All plotting functions accept parsed data objects from the parsers module.
They are designed to work with non-GUI backends for headless environments.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple, Union

import numpy as np

from .parsers import BandStructureData, DOSData, SCFResult

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure


# =============================================================================
# Color schemes and styling
# =============================================================================

# Modern color palette
COLORS = {
    'primary': '#2563eb',     # Blue
    'secondary': '#10b981',   # Emerald
    'accent': '#f59e0b',      # Amber
    'dark': '#1f2937',        # Gray-800
    'light': '#f3f4f6',       # Gray-100
    'red': '#ef4444',
    'purple': '#8b5cf6',
}

DEFAULT_STYLE = {
    'figure.figsize': (8, 6),
    'figure.dpi': 100,
    'axes.labelsize': 12,
    'axes.titlesize': 14,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'lines.linewidth': 1.5,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--',
}


def apply_style():
    """Apply default plotting style."""
    plt = _get_pyplot()
    plt.rcParams.update(DEFAULT_STYLE)


def _get_pyplot():
    """Import matplotlib lazily to avoid startup cost for non-plotting paths."""
    import matplotlib

    # Use non-GUI backend by default for headless compatibility.
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


# =============================================================================
# DOS Plotting
# =============================================================================

def plot_dos(
    dos_data: DOSData,
    ax: Optional[Axes] = None,
    shift_fermi: bool = True,
    show_fermi: bool = True,
    energy_range: Optional[Tuple[float, float]] = None,
    color: str = COLORS['primary'],
    fill: bool = True,
    fill_alpha: float = 0.3,
    label: Optional[str] = None,
    **kwargs,
) -> Tuple[Figure, Axes]:
    """
    Plot density of states.
    
    Args:
        dos_data: Parsed DOS data
        ax: Matplotlib axes (creates new figure if None)
        shift_fermi: Shift energies so Fermi level is at 0
        show_fermi: Show vertical line at Fermi energy
        energy_range: (Emin, Emax) to display
        color: Line color
        fill: Fill area under curve
        fill_alpha: Fill transparency
        label: Legend label
        **kwargs: Additional arguments passed to plot()
        
    Returns:
        (Figure, Axes) tuple
    """
    plt = _get_pyplot()
    apply_style()
    
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()
    
    # Prepare data
    data = dos_data.shift_to_fermi() if shift_fermi and dos_data.fermi_energy else dos_data
    energies = data.energies
    dos = data.dos
    
    # Apply energy range filter
    if energy_range:
        mask = (energies >= energy_range[0]) & (energies <= energy_range[1])
        energies = energies[mask]
        dos = dos[mask]
    
    # Plot DOS
    line, = ax.plot(energies, dos, color=color, label=label, **kwargs)
    
    if fill:
        ax.fill_between(energies, 0, dos, color=color, alpha=fill_alpha)
    
    # Show Fermi level
    if show_fermi:
        fermi_pos = 0 if shift_fermi else (dos_data.fermi_energy or 0)
        ax.axvline(x=fermi_pos, color=COLORS['red'], linestyle='--', 
                   linewidth=1, alpha=0.8, label='$E_F$')
    
    # Labels
    xlabel = "Energy - $E_F$ (eV)" if shift_fermi else "Energy (eV)"
    ax.set_xlabel(xlabel)
    ax.set_ylabel("DOS (states/eV)")
    ax.set_title("Density of States")
    
    # Set x limits
    if energy_range:
        ax.set_xlim(energy_range)
    
    # Y starts at 0
    ax.set_ylim(bottom=0)
    
    if label:
        ax.legend()
    
    fig.tight_layout()
    return fig, ax


def plot_dos_comparison(
    dos_list: Sequence[DOSData],
    labels: Sequence[str],
    ax: Optional[Axes] = None,
    shift_fermi: bool = True,
    energy_range: Optional[Tuple[float, float]] = None,
    colors: Optional[Sequence[str]] = None,
) -> Tuple[Figure, Axes]:
    """
    Plot multiple DOS curves for comparison.
    
    Args:
        dos_list: List of DOSData objects
        labels: Labels for each DOS
        ax: Matplotlib axes
        shift_fermi: Shift energies so Fermi is at 0
        energy_range: (Emin, Emax) to display
        colors: Optional list of colors for each curve
        
    Returns:
        (Figure, Axes) tuple
    """
    plt = _get_pyplot()
    apply_style()
    
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()
    
    if colors is None:
        colors = [COLORS['primary'], COLORS['secondary'], COLORS['accent'], 
                  COLORS['purple'], COLORS['red']]
    
    for i, (dos_data, label) in enumerate(zip(dos_list, labels)):
        color = colors[i % len(colors)]
        plot_dos(dos_data, ax=ax, shift_fermi=shift_fermi, show_fermi=(i == 0),
                 energy_range=energy_range, color=color, fill=False, label=label)
    
    ax.legend()
    fig.tight_layout()
    return fig, ax


# =============================================================================
# Band Structure Plotting
# =============================================================================

def plot_bands(
    band_data: BandStructureData,
    ax: Optional[Axes] = None,
    shift_fermi: bool = True,
    show_fermi: bool = True,
    energy_range: Optional[Tuple[float, float]] = None,
    color: str = COLORS['primary'],
    show_symmetry_lines: bool = True,
    symmetry_labels: Optional[List[str]] = None,
    linewidth: float = 1.0,
    **kwargs,
) -> Tuple[Figure, Axes]:
    """
    Plot electronic band structure.
    
    Args:
        band_data: Parsed band structure data
        ax: Matplotlib axes (creates new figure if None)
        shift_fermi: Shift energies so Fermi level is at 0
        show_fermi: Show horizontal line at Fermi energy
        energy_range: (Emin, Emax) to display
        color: Band line color
        show_symmetry_lines: Draw vertical lines at high-symmetry points
        symmetry_labels: Override labels for high-symmetry points
        linewidth: Line width for bands
        **kwargs: Additional arguments passed to plot()
        
    Returns:
        (Figure, Axes) tuple
    """
    plt = _get_pyplot()
    apply_style()
    
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()
    
    # Prepare data
    data = band_data.shift_to_fermi() if shift_fermi and band_data.fermi_energy else band_data
    k_distances = data.k_distances
    energies = data.energies
    
    # Plot each band
    for i, band in enumerate(energies):
        # Only add label to first band for legend
        label = kwargs.pop('label', None) if i == 0 else None
        ax.plot(k_distances, band, color=color, linewidth=linewidth, 
                label=label, **kwargs)
    
    # Show Fermi level
    if show_fermi:
        fermi_pos = 0 if shift_fermi else (band_data.fermi_energy or 0)
        ax.axhline(y=fermi_pos, color=COLORS['red'], linestyle='--', 
                   linewidth=1, alpha=0.8, label='$E_F$')
    
    # High-symmetry point vertical lines and labels
    if show_symmetry_lines and data.high_symmetry_points:
        labels = symmetry_labels or [pt.label for pt in data.high_symmetry_points]
        positions = [pt.k_distance for pt in data.high_symmetry_points]
        
        for pos in positions:
            ax.axvline(x=pos, color=COLORS['dark'], linestyle='-', 
                       linewidth=0.5, alpha=0.5)
        
        # Set x-tick labels at high-symmetry points
        ax.set_xticks(positions)
        ax.set_xticklabels(labels)
    
    # Labels
    ylabel = "Energy - $E_F$ (eV)" if shift_fermi else "Energy (eV)"
    ax.set_ylabel(ylabel)
    ax.set_xlabel("")  # k-path usually labeled with symmetry points
    ax.set_title("Electronic Band Structure")
    
    # Set limits
    ax.set_xlim(k_distances.min(), k_distances.max())
    if energy_range:
        ax.set_ylim(energy_range)
    
    fig.tight_layout()
    return fig, ax


def plot_bands_comparison(
    band_list: Sequence[BandStructureData],
    labels: Sequence[str],
    ax: Optional[Axes] = None,
    shift_fermi: bool = True,
    energy_range: Optional[Tuple[float, float]] = None,
    colors: Optional[Sequence[str]] = None,
) -> Tuple[Figure, Axes]:
    """
    Plot multiple band structures for comparison.
    
    Args:
        band_list: List of BandStructureData objects
        labels: Labels for each band structure
        ax: Matplotlib axes
        shift_fermi: Shift energies so Fermi is at 0
        energy_range: (Emin, Emax) to display
        colors: Optional list of colors
        
    Returns:
        (Figure, Axes) tuple
    """
    plt = _get_pyplot()
    apply_style()
    
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()
    
    if colors is None:
        colors = [COLORS['primary'], COLORS['secondary'], COLORS['accent'], 
                  COLORS['purple'], COLORS['red']]
    
    for i, (band_data, label) in enumerate(zip(band_list, labels)):
        color = colors[i % len(colors)]
        # Only show symmetry lines for first band structure
        show_sym = (i == 0)
        show_fermi_line = (i == 0)
        plot_bands(band_data, ax=ax, shift_fermi=shift_fermi, 
                   show_fermi=show_fermi_line, show_symmetry_lines=show_sym,
                   energy_range=energy_range, color=color, label=label)
    
    ax.legend()
    fig.tight_layout()
    return fig, ax


def plot_band_with_dos(
    band_data: BandStructureData,
    dos_data: DOSData,
    shift_fermi: bool = True,
    energy_range: Optional[Tuple[float, float]] = None,
    band_color: str = COLORS['primary'],
    dos_color: str = COLORS['secondary'],
    figsize: Tuple[float, float] = (10, 6),
    dos_width_ratio: float = 0.3,
) -> Tuple[Figure, Tuple[Axes, Axes]]:
    """
    Plot band structure with DOS side panel.
    
    Args:
        band_data: Band structure data
        dos_data: DOS data
        shift_fermi: Shift energies so Fermi is at 0
        energy_range: (Emin, Emax) for both plots
        band_color: Color for band lines
        dos_color: Color for DOS curve
        figsize: Figure size
        dos_width_ratio: Width ratio of DOS panel relative to bands
        
    Returns:
        (Figure, (band_axes, dos_axes)) tuple
    """
    plt = _get_pyplot()
    apply_style()
    
    # Create figure with gridspec for unequal widths
    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(1, 2, width_ratios=[1, dos_width_ratio], wspace=0.05)
    ax_bands = fig.add_subplot(gs[0])
    ax_dos = fig.add_subplot(gs[1], sharey=ax_bands)
    
    # Plot bands
    plot_bands(band_data, ax=ax_bands, shift_fermi=shift_fermi, 
               energy_range=energy_range, color=band_color)
    
    # Plot DOS (horizontal - swap x and y)
    data = dos_data.shift_to_fermi() if shift_fermi and dos_data.fermi_energy else dos_data
    
    ax_dos.plot(data.dos, data.energies, color=dos_color, linewidth=1.5)
    ax_dos.fill_betweenx(data.energies, 0, data.dos, color=dos_color, alpha=0.3)
    
    # Fermi line on DOS panel
    fermi_pos = 0 if shift_fermi else (dos_data.fermi_energy or 0)
    ax_dos.axhline(y=fermi_pos, color=COLORS['red'], linestyle='--', 
                   linewidth=1, alpha=0.8)
    
    # Style DOS panel
    ax_dos.set_xlabel("DOS")
    ax_dos.set_ylabel("")
    ax_dos.yaxis.set_visible(False)
    ax_dos.set_xlim(left=0)
    
    if energy_range:
        ax_bands.set_ylim(energy_range)
        ax_dos.set_ylim(energy_range)
    
    fig.suptitle("Electronic Structure", fontsize=14)
    fig.tight_layout()
    
    return fig, (ax_bands, ax_dos)


# =============================================================================
# SCF Convergence Plotting
# =============================================================================

def plot_scf_convergence(
    scf_result: SCFResult,
    ax: Optional[Axes] = None,
    show_energy: bool = True,
    show_accuracy: bool = True,
    log_accuracy: bool = True,
) -> Tuple[Figure, Axes]:
    """
    Plot SCF convergence (energy and/or accuracy vs iteration).
    
    Args:
        scf_result: Parsed SCF result
        ax: Matplotlib axes
        show_energy: Plot total energy
        show_accuracy: Plot SCF accuracy
        log_accuracy: Use log scale for accuracy
        
    Returns:
        (Figure, Axes) tuple
    """
    plt = _get_pyplot()
    apply_style()
    
    if not scf_result.iterations:
        raise ValueError("No SCF iterations to plot")
    
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()
    
    iterations = [it.iteration for it in scf_result.iterations]
    
    if show_energy and show_accuracy:
        # Dual y-axis plot
        ax2 = ax.twinx()
        
        # Energy on left axis
        energies = [it.total_energy for it in scf_result.iterations]
        ax.plot(iterations, energies, color=COLORS['primary'], marker='o', 
                markersize=4, label='Total Energy')
        ax.set_ylabel("Total Energy (Ry)", color=COLORS['primary'])
        ax.tick_params(axis='y', labelcolor=COLORS['primary'])
        
        # Accuracy on right axis
        accuracies = [it.scf_accuracy for it in scf_result.iterations]
        ax2.plot(iterations, accuracies, color=COLORS['secondary'], marker='s', 
                 markersize=4, label='SCF Accuracy')
        ax2.set_ylabel("SCF Accuracy (Ry)", color=COLORS['secondary'])
        ax2.tick_params(axis='y', labelcolor=COLORS['secondary'])
        if log_accuracy:
            ax2.set_yscale('log')
        
        # Combined legend
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        
    elif show_energy:
        energies = [it.total_energy for it in scf_result.iterations]
        ax.plot(iterations, energies, color=COLORS['primary'], marker='o', 
                markersize=4, label='Total Energy')
        ax.set_ylabel("Total Energy (Ry)")
        ax.legend()
        
    elif show_accuracy:
        accuracies = [it.scf_accuracy for it in scf_result.iterations]
        ax.plot(iterations, accuracies, color=COLORS['secondary'], marker='s', 
                markersize=4, label='SCF Accuracy')
        ax.set_ylabel("SCF Accuracy (Ry)")
        if log_accuracy:
            ax.set_yscale('log')
        ax.legend()
    
    ax.set_xlabel("SCF Iteration")
    ax.set_title("SCF Convergence")
    ax.set_xticks(iterations)
    
    fig.tight_layout()
    return fig, ax


# =============================================================================
# Saving utilities
# =============================================================================

def save_figure(
    fig: Figure,
    path: Union[Path, str],
    dpi: int = 150,
    formats: Optional[List[str]] = None,
    **kwargs,
) -> List[Path]:
    """
    Save figure to file(s).
    
    Args:
        fig: Matplotlib figure
        path: Output path (extension determines format, or use formats list)
        dpi: Resolution for raster formats
        formats: List of formats to save (e.g., ['png', 'svg', 'pdf'])
        **kwargs: Additional arguments to savefig
        
    Returns:
        List of saved file paths
    """
    path = Path(path)
    saved_paths: List[Path] = []
    
    if formats:
        for fmt in formats:
            out_path = path.with_suffix(f'.{fmt}')
            fig.savefig(out_path, dpi=dpi, bbox_inches='tight', **kwargs)
            saved_paths.append(out_path)
    else:
        fig.savefig(path, dpi=dpi, bbox_inches='tight', **kwargs)
        saved_paths.append(path)
    
    return saved_paths
