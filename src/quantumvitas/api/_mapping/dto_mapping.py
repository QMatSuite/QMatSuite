"""
Kernel to DTO mapping functions.

This module provides functions to map kernel objects to API DTOs.
PR3: Analysis mappings added.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.api.types.analysis import AnalysisRefDTO, AnalysisSummaryDTO


def kernel_to_dto(kernel_obj: Any) -> Any:
    """
    Map kernel object to DTO.
    
    This is a generic mapper. Specific mappers are provided below.
    """
    raise NotImplementedError("Use specific mapping functions")


def analysis_summary_to_dto(
    calc_id: str,
    step_id: str,
    scf_data: dict[str, Any] | None = None,
) -> AnalysisSummaryDTO:
    """
    Map analysis data to AnalysisSummaryDTO.
    
    Args:
        calc_id: Calculation ULID
        step_id: Step ULID
        scf_data: Optional SCF analysis data from artifact
        
    Returns:
        AnalysisSummaryDTO
    """
    # Extract summary data from SCF artifact if available
    converged = None
    total_energy_ev = None
    fermi_energy_ev = None
    band_gap_ev = None
    band_gap_type = None
    total_magnetization = None
    available_properties = []
    
    if scf_data:
        converged = scf_data.get("converged", False)
        
        # Convert energy from Ry to eV if needed
        total_energy_ry = scf_data.get("total_energy_ry")
        if total_energy_ry is not None:
            total_energy_ev = total_energy_ry * 13.6056980659  # Ry to eV
        
        fermi_energy_ev = scf_data.get("fermi_energy_ev")
        
        # Check for band gap in summary if available
        band_gap_ev = scf_data.get("estimated_band_gap_ev")
        if band_gap_ev is not None:
            band_gap_type = "indirect"  # Default, could be improved
        
        # Check which properties are available
        # This is a simplified check - in reality we'd check for all artifact types
        if scf_data:
            available_properties.append("scf")
    
    return AnalysisSummaryDTO(
        calc_id=calc_id,
        step_id=step_id,
        converged=converged,
        total_energy_ev=total_energy_ev,
        fermi_energy_ev=fermi_energy_ev,
        band_gap_ev=band_gap_ev,
        band_gap_type=band_gap_type,
        total_magnetization=total_magnetization,
        available_properties=available_properties if available_properties else None,
    )


def analysis_ref_to_dto(
    calc_id: str,
    step_id: str,
    property_name: str,
    artifact_path: str,
    artifact_format: str,
    artifact_sha256: str,
    artifact_size_bytes: int,
    artifact_data: dict[str, Any],
) -> AnalysisRefDTO:
    """
    Map analysis artifact to AnalysisRefDTO.
    
    Args:
        calc_id: Calculation ULID
        step_id: Step ULID
        property_name: Property name (e.g., "band_structure", "dos")
        artifact_path: Relative path to artifact file
        artifact_format: Artifact format ("json", "hdf5", etc.)
        artifact_sha256: SHA256 hash of artifact
        artifact_size_bytes: Size of artifact in bytes
        artifact_data: Full artifact data (for summary extraction)
        
    Returns:
        AnalysisRefDTO
    """
    # Extract summary (scalars only, no arrays)
    summary: dict[str, Any] = {}
    preview: dict[str, Any] | None = None
    
    # Remove metadata
    clean_data = {k: v for k, v in artifact_data.items() if not k.startswith("_")}
    
    if property_name == "band_structure":
        # Extract scalars only
        summary["n_bands"] = clean_data.get("n_bands", 0)
        summary["n_kpoints"] = clean_data.get("n_kpoints", 0)
        summary["fermi_energy_ev"] = clean_data.get("fermi_energy_ev")
        summary["band_gap_ev"] = clean_data.get("estimated_band_gap_ev")
        
        # Preview: small subset of k-point labels
        high_sym_points = clean_data.get("high_symmetry_points", [])
        if high_sym_points:
            preview = {
                "kpoint_labels": [pt.get("label", "") for pt in high_sym_points[:10]],  # Limit to 10
                "kpoint_indices": [pt.get("index", 0) for pt in high_sym_points[:10]],
            }
    elif property_name == "dos":
        summary["n_points"] = clean_data.get("n_points", 0)
        summary["fermi_energy_ev"] = clean_data.get("fermi_energy_ev")
        energy_range = clean_data.get("energy_range_ev", [])
        if energy_range:
            summary["energy_min_ev"] = energy_range[0] if len(energy_range) > 0 else None
            summary["energy_max_ev"] = energy_range[1] if len(energy_range) > 1 else None
    elif property_name == "scf":
        summary["converged"] = clean_data.get("converged", False)
        summary["n_iterations"] = len(clean_data.get("iterations", []))
        summary["total_energy_ry"] = clean_data.get("total_energy_ry")
        summary["fermi_energy_ev"] = clean_data.get("fermi_energy_ev")
        summary["n_electrons"] = clean_data.get("n_electrons")
        summary["n_kpoints"] = clean_data.get("n_kpoints")
    
    return AnalysisRefDTO(
        calc_id=calc_id,
        step_id=step_id,
        property_name=property_name,
        artifact_path=artifact_path,
        artifact_format=artifact_format,
        artifact_sha256=artifact_sha256,
        artifact_size_bytes=artifact_size_bytes,
        summary=summary,
        preview=preview,
    )
