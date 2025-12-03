"""
Band structure analysis utilities.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from quantumvitas.workflow.results import WorkflowResult
from quantumvitas.workflow.workflow import Workflow
from .parsers import (
    parse_bands_gnu,
    parse_scf_output,
    BandStructureData,
    HighSymmetryPoint,
    find_bands_files,
)
from .plotting import plot_bands, plot_band_with_dos, save_figure


def analyze_bands_file(
    bands_file: Path | str,
    symmetry_file: Optional[Path | str] = None,
    scf_file: Optional[Path | str] = None,
    fermi_energy: Optional[float] = None,
    shift_fermi: bool = True,
    output_dir: Optional[Path] = None,
    save_plot: bool = False,
    plot_format: str = "png",
    symmetry_labels: Optional[List[str]] = None,
) -> dict:
    """
    Analyze a band structure data file.
    
    Args:
        bands_file: Path to bands.dat.gnu file
        symmetry_file: Optional path to bands.x output (for high-symmetry points)
        scf_file: Optional path to SCF output file (for Fermi energy)
        fermi_energy: Fermi energy in eV (overrides extraction from files)
        shift_fermi: Shift energies to set Fermi at 0
        output_dir: Directory to save outputs
        save_plot: Whether to save a plot
        plot_format: Plot format (png, svg, pdf)
        symmetry_labels: Override labels for high-symmetry points
        
    Returns:
        Dictionary with band analysis results
    """
    bands_path = Path(bands_file)
    if not bands_path.exists():
        raise FileNotFoundError(f"Bands file not found: {bands_path}")
    
    # Get Fermi energy if not provided
    if fermi_energy is None and scf_file:
        scf_result = parse_scf_output(scf_file)
        fermi_energy = scf_result.fermi_energy
    
    # Parse band data
    band_data = parse_bands_gnu(
        bands_path,
        symmetry_file=symmetry_file,
        fermi_energy=fermi_energy,
    )
    
    # Calculate summary statistics
    energy_min = float(band_data.energies.min())
    energy_max = float(band_data.energies.max())
    
    # Estimate band gap if possible (very rough - proper method needs k-point info)
    band_gap = None
    if fermi_energy is not None:
        # Find highest occupied and lowest unoccupied bands
        below_fermi = band_data.energies[band_data.energies < fermi_energy]
        above_fermi = band_data.energies[band_data.energies > fermi_energy]
        if below_fermi.size > 0 and above_fermi.size > 0:
            vbm = below_fermi.max()
            cbm = above_fermi.min()
            band_gap = cbm - vbm
    
    result = {
        "file": str(bands_path),
        "n_bands": band_data.n_bands,
        "n_kpoints": band_data.n_kpoints,
        "energy_range_ev": [energy_min, energy_max],
        "fermi_energy_ev": fermi_energy,
        "estimated_band_gap_ev": band_gap,
        "n_high_symmetry_points": len(band_data.high_symmetry_points),
        "high_symmetry_labels": [pt.label for pt in band_data.high_symmetry_points],
    }
    
    # Save outputs if requested
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON summary
        (output_dir / "bands_analysis.json").write_text(
            json.dumps(result, indent=2)
        )
        
        # Save full data as JSON
        (output_dir / "bands_data.json").write_text(
            json.dumps(band_data.to_dict(), indent=2)
        )
        
        # Save plot
        if save_plot:
            fig, ax = plot_bands(
                band_data,
                shift_fermi=shift_fermi,
                symmetry_labels=symmetry_labels,
            )
            save_figure(fig, output_dir / f"bands.{plot_format}")
            result["plot_file"] = str(output_dir / f"bands.{plot_format}")
    
    return result


def analyze_bands(workflow: Workflow, result: WorkflowResult, results_dir: Path) -> None:
    """
    Locate band structure outputs and generate plots.
    
    Looks for bands.dat.gnu and bands.x output files in the workflow directory.
    """
    band_steps = [
        step for step in result.steps if step.step_type.value.startswith("bands")
    ]
    if not band_steps:
        return
    
    raw_dir = workflow.raw_dir if hasattr(workflow, 'raw_dir') else results_dir
    
    # Find Fermi energy from SCF/NSCF steps
    # Priority: nscf > scf (nscf uses denser k-grid for more accurate Fermi energy)
    fermi_energy = None
    scf_fermi = None
    nscf_fermi = None
    for step in result.steps:
        step_fermi = step.metrics.get("fermi_energy_ev")
        if step_fermi is not None:
            step_type = step.step_type.value.lower() if hasattr(step.step_type, 'value') else str(step.step_type).lower()
            if "nscf" in step_type:
                nscf_fermi = step_fermi
            elif "scf" in step_type:
                scf_fermi = step_fermi
    # Prefer NSCF Fermi energy over SCF
    fermi_energy = nscf_fermi if nscf_fermi is not None else scf_fermi
    
    bands_results = []
    
    for step in band_steps:
        step_id = step.step_id
        
        # Look for band files
        files = find_bands_files(raw_dir, prefix=step_id)
        
        # Also try without prefix
        if files['bands_gnu'] is None:
            files = find_bands_files(raw_dir)
        
        bands_file = files['bands_gnu']
        symmetry_file = files['bands_out']
        
        if bands_file and bands_file.exists():
            try:
                band_data = parse_bands_gnu(
                    bands_file,
                    symmetry_file=symmetry_file,
                    fermi_energy=fermi_energy,
                )
                
                # Save plot
                fig, ax = plot_bands(band_data, shift_fermi=True)
                plot_path = results_dir / f"{step_id}_bands.png"
                save_figure(fig, plot_path)
                
                # Save data JSON
                data_path = results_dir / f"{step_id}_bands_data.json"
                data_path.write_text(json.dumps(band_data.to_dict(), indent=2))
                
                bands_results.append({
                    "step_id": step_id,
                    "bands_file": str(bands_file),
                    "symmetry_file": str(symmetry_file) if symmetry_file else None,
                    "plot_file": str(plot_path),
                    "data_file": str(data_path),
                    "n_bands": band_data.n_bands,
                    "n_kpoints": band_data.n_kpoints,
                    "fermi_energy_ev": band_data.fermi_energy,
                    "high_symmetry_points": [pt.label for pt in band_data.high_symmetry_points],
                })
            except Exception as e:
                bands_results.append({
                    "step_id": step_id,
                    "bands_file": str(bands_file),
                    "error": str(e),
                })
    
    # Write summary
    summary_path = results_dir / "bands_analysis_summary.json"
    summary_path.write_text(json.dumps(bands_results, indent=2))
