"""
DOS analysis utilities.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from quantumvitas.calculation.public import CalculationResult, Calculation
from .parsers import parse_dos_data, parse_scf_output, DOSData
from .plotting import plot_dos, save_figure


def analyze_dos_file(
    dos_file: Path | str,
    scf_file: Optional[Path | str] = None,
    shift_fermi: bool = True,
    output_dir: Optional[Path] = None,
    save_plot: bool = False,
    plot_format: str = "png",
) -> dict:
    """
    Analyze a DOS data file.
    
    Args:
        dos_file: Path to DOS .dat file
        scf_file: Optional path to SCF output file (for Fermi energy if not in DOS header)
        shift_fermi: Shift energies to set Fermi at 0
        output_dir: Directory to save outputs (plots, JSON)
        save_plot: Whether to save a plot
        plot_format: Plot format (png, svg, pdf)
        
    Returns:
        Dictionary with DOS analysis results
    """
    dos_path = Path(dos_file)
    if not dos_path.exists():
        raise FileNotFoundError(f"DOS file not found: {dos_path}")
    
    # Parse DOS data
    dos_data = parse_dos_data(dos_path)
    
    # If Fermi energy not in DOS file, try SCF output
    if dos_data.fermi_energy is None and scf_file:
        scf_result = parse_scf_output(scf_file)
        dos_data = DOSData(
            energies=dos_data.energies,
            dos=dos_data.dos,
            idos=dos_data.idos,
            fermi_energy=scf_result.fermi_energy,
        )
    
    # Calculate summary statistics
    result = {
        "file": str(dos_path),
        "n_points": len(dos_data.energies),
        "energy_range": [float(dos_data.energies.min()), float(dos_data.energies.max())],
        "fermi_energy_ev": dos_data.fermi_energy,
        "max_dos": float(dos_data.dos.max()),
    }
    
    # Save outputs if requested
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON summary
        (output_dir / "dos_analysis.json").write_text(
            json.dumps(result, indent=2)
        )
        
        # Save full data as JSON
        (output_dir / "dos_data.json").write_text(
            json.dumps(dos_data.to_dict(), indent=2)
        )
        
        # Save plot
        if save_plot:
            fig, ax = plot_dos(dos_data, shift_fermi=shift_fermi)
            save_figure(fig, output_dir / f"dos.{plot_format}")
            result["plot_file"] = str(output_dir / f"dos.{plot_format}")
    
    return result


def analyze_dos(calculation: Calculation, result: CalculationResult, results_dir: Path) -> None:
    """
    Locate DOS outputs in ``calculation.raw_dir`` and write processed artifacts.
    
    Looks for DOS .dat files in the calculation output directory and processes them.
    """
    dos_steps = [step for step in result.steps if step.step_type_spec and step.step_type_spec.startswith("dos")]
    if not dos_steps:
        return
    
    # Look for DOS data files
    raw_dir = calculation.raw_dir if hasattr(calculation, 'raw_dir') else results_dir
    
    # Find Fermi energy from SCF/NSCF steps if available
    fermi_energy = None
    for step in result.steps:
        if step.metrics.get("fermi_energy_ev"):
            # QE reports Fermi energy in eV
            fermi_energy = step.metrics.get("fermi_energy_ev")
            break
    
    dos_results = []
    
    for step in dos_steps:
        # Look for DOS files associated with this step
        step_ulid = step.step_ulid
        
        # Common naming patterns
        possible_dos_files = [
            raw_dir / f"{step_ulid}.dos.dat",
            raw_dir / f"{step_ulid}_dos.dat",
            raw_dir / "dos.dat",
            raw_dir / f"{calculation.meta.slug}.dos.dat",
        ]
        
        for dos_file in possible_dos_files:
            if dos_file.exists():
                try:
                    dos_data = parse_dos_data(dos_file)
                    
                    # Use found Fermi energy if DOS file doesn't have one
                    if dos_data.fermi_energy is None and fermi_energy is not None:
                        dos_data = DOSData(
                            energies=dos_data.energies,
                            dos=dos_data.dos,
                            idos=dos_data.idos,
                            fermi_energy=fermi_energy,
                        )
                    
                    # Save plot
                    fig, ax = plot_dos(dos_data, shift_fermi=True)
                    plot_path = results_dir / f"{step_ulid}_dos.png"
                    save_figure(fig, plot_path)
                    
                    # Save data JSON
                    data_path = results_dir / f"{step_ulid}_dos_data.json"
                    data_path.write_text(json.dumps(dos_data.to_dict(), indent=2))
                    
                    dos_results.append({
                        "step_ulid": step_ulid,
                        "dos_file": str(dos_file),
                        "plot_file": str(plot_path),
                        "data_file": str(data_path),
                        "fermi_energy_ev": dos_data.fermi_energy,
                        "n_points": len(dos_data.energies),
                    })
                    break
                except Exception as e:
                    dos_results.append({
                        "step_ulid": step_ulid,
                        "dos_file": str(dos_file),
                        "error": str(e),
                    })
                    break
    
    # Write summary
    summary_path = results_dir / "dos_analysis_summary.json"
    summary_path.write_text(json.dumps(dos_results, indent=2))
