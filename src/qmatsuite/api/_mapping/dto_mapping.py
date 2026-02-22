"""
Kernel to DTO mapping functions.

This module provides functions to map kernel objects to API DTOs.
PR3: Analysis mappings added.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qmatsuite.api.types.analysis import AnalysisRefDTO, AnalysisSummaryDTO
from qmatsuite.api.types.calculation import CalculationDTO, StepDTO
from qmatsuite.api.types.common import MetaDTO
from qmatsuite.api.types.structure import StructureDTO


def kernel_to_dto(kernel_obj: Any) -> Any:
    """
    Map kernel object to DTO.
    
    This is a generic mapper. Specific mappers are provided below.
    """
    raise NotImplementedError("Use specific mapping functions")


def analysis_summary_to_dto(
    calc_ulid: str,
    step_ulid: str,
    scf_data: dict[str, Any] | None = None,
) -> AnalysisSummaryDTO:
    """
    Map analysis data to AnalysisSummaryDTO.
    
    Args:
        calc_ulid: Calculation ULID
        step_ulid: Step ULID
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
        calc_ulid=calc_ulid,
        step_ulid=step_ulid,
        converged=converged,
        total_energy_ev=total_energy_ev,
        fermi_energy_ev=fermi_energy_ev,
        band_gap_ev=band_gap_ev,
        band_gap_type=band_gap_type,
        total_magnetization=total_magnetization,
        available_properties=available_properties if available_properties else None,
    )


def analysis_ref_to_dto(
    calc_ulid: str,
    step_ulid: str,
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
        calc_ulid: Calculation ULID
        step_ulid: Step ULID
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
        calc_ulid=calc_ulid,
        step_ulid=step_ulid,
        property_name=property_name,
        artifact_path=artifact_path,
        artifact_format=artifact_format,
        artifact_sha256=artifact_sha256,
        artifact_size_bytes=artifact_size_bytes,
        summary=summary,
        preview=preview,
    )


def structure_to_dto(
    struct_resolved: Any,  # ResolvedResource
    struct_model: Any,  # StructureModel
    pmg_structure: Any,  # PMGStructure
) -> StructureDTO:
    """
    Map structure data to StructureDTO.
    
    Args:
        struct_resolved: ResolvedResource for the structure
        struct_model: StructureModel with metadata
        pmg_structure: pymatgen Structure object
        
    Returns:
        StructureDTO (no coordinate arrays)
    """
    from datetime import datetime
    
    # Extract metadata
    meta = None
    if struct_model and struct_model.meta:
        meta = MetaDTO(
            ulid=struct_model.meta.ulid if hasattr(struct_model.meta, 'ulid') else None,
            slug=struct_model.meta.slug,
            name=struct_model.meta.name,
            path=struct_model.meta.path if hasattr(struct_model.meta, 'path') else None,
            description=getattr(struct_model.meta, 'description', None),
            tags=list(struct_model.meta.tags) if getattr(struct_model.meta, 'tags', None) else None,
            created_at=struct_model.meta.created_at.isoformat() if getattr(struct_model.meta, 'created_at', None) else None,
            updated_at=struct_model.meta.updated_at.isoformat() if getattr(struct_model.meta, 'updated_at', None) else None,
        )
    
    # Get structure ID
    structure_ulid = struct_resolved.meta.ulid if struct_resolved.meta else ""
    
    # Extract crystallographic data (if periodic)
    space_group = None
    point_group = None
    cell_volume_ang3 = None
    lattice_abc = None
    lattice_angles = None
    
    if hasattr(pmg_structure, "lattice"):
        # Periodic structure
        lattice = pmg_structure.lattice
        cell_volume_ang3 = float(lattice.volume)
        lattice_abc = list(lattice.abc)
        lattice_angles = list(lattice.angles)
        
        # Try to get space group (may not always be available)
        try:
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            analyzer = SpacegroupAnalyzer(pmg_structure)
            space_group = analyzer.get_space_group_symbol()
            point_group = analyzer.get_point_group_symbol()
        except Exception:
            # Space group analysis may fail, that's OK
            pass
    
    return StructureDTO(
        structure_ulid=structure_ulid,
        formula=pmg_structure.formula,
        num_atoms=len(pmg_structure),
        meta=meta,
        space_group=space_group,
        point_group=point_group,
        cell_volume_ang3=cell_volume_ang3,
        lattice_abc=lattice_abc,
        lattice_angles=lattice_angles,
    )


def _derive_step_status(step_obj: Any, calc_dir: Path) -> str:
    """
    Derive step status from step object and filesystem.
    
    Args:
        step_obj: Step object
        calc_dir: Calculation directory
        
    Returns:
        Status string: "pending", "running", "completed", "failed"
    """
    from qmatsuite.calculation.step_done import is_step_done
    from qmatsuite.calculation.types import StepStatus
    
    # Check if step is done
    step_type = step_obj.step_type_spec if hasattr(step_obj, 'step_type_spec') else None
    if step_type:
        raw_dir = calc_dir / "raw"
        if is_step_done(calc_dir, step_type, calc_raw_dir=raw_dir):
            # Check if there's an error (simplified - could check exit codes)
            return "completed"
    
    # Default to pending if we can't determine
    return "pending"


def _derive_calculation_status(calc_obj: Any) -> str:
    """
    Derive calculation status from steps.
    
    Args:
        calc_obj: Calculation object
        
    Returns:
        Status string: "pending", "running", "completed", "failed"
    """
    if not hasattr(calc_obj, 'steps') or not calc_obj.steps:
        return "pending"
    
    # Check step statuses
    has_running = False
    has_failed = False
    all_completed = True
    
    for step in calc_obj.steps:
        # Simplified status check - in reality would check step results
        # For now, assume pending if no results
        step_status = getattr(step, 'status', None)
        if step_status:
            if step_status == "running":
                has_running = True
            elif step_status == "failed":
                has_failed = True
            elif step_status != "completed":
                all_completed = False
        else:
            all_completed = False
    
    if has_failed:
        return "failed"
    elif has_running:
        return "running"
    elif all_completed:
        return "completed"
    else:
        return "pending"


def calculation_ref_to_dto(
    calc_resolved: Any,  # ResolvedResource
    rel_path: str,
) -> CalculationRefDTO:
    """
    Map calculation ResolvedResource to CalculationRefDTO.
    
    Args:
        calc_resolved: ResolvedResource for the calculation
        rel_path: Relative path from project root
        
    Returns:
        CalculationRefDTO
    """
    from qmatsuite.api.types.common import MetaDTO
    
    # Extract metadata (minimal)
    meta = None
    if calc_resolved.meta:
        meta = MetaDTO(
            slug=calc_resolved.meta.slug,
            name=calc_resolved.meta.name,
            description=getattr(calc_resolved.meta, 'description', None),
            tags=list(calc_resolved.meta.tags) if hasattr(calc_resolved.meta, 'tags') and calc_resolved.meta.tags else None,
            created_at=calc_resolved.meta.created_at.isoformat() if hasattr(calc_resolved.meta, 'created_at') and calc_resolved.meta.created_at else None,
            updated_at=calc_resolved.meta.updated_at.isoformat() if hasattr(calc_resolved.meta, 'updated_at') and calc_resolved.meta.updated_at else None,
        )
    
    # Get calculation ULID
    calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else ""
    
    return CalculationRefDTO(
        calc_ulid=calc_ulid,
        path=rel_path,
        meta=meta,
    )


def calculation_to_dto(
    calc_resolved: Any,  # ResolvedResource
    calc_model: Any,  # CalculationModel
    calc_obj: Any,  # Calculation
) -> CalculationDTO:
    """
    Map calculation data to CalculationDTO.
    
    Args:
        calc_resolved: ResolvedResource for the calculation
        calc_model: CalculationModel with metadata
        calc_obj: Calculation object with steps
        
    Returns:
        CalculationDTO
    """
    from datetime import datetime
    
    # Extract metadata
    meta = None
    if calc_model and calc_model.meta:
        meta = MetaDTO(
            slug=calc_model.meta.slug,
            name=calc_model.meta.name,
            description=getattr(calc_model.meta, 'description', None),
            tags=list(calc_model.meta.tags) if hasattr(calc_model.meta, 'tags') and calc_model.meta.tags else None,
            created_at=calc_model.meta.created_at.isoformat() if hasattr(calc_model.meta, 'created_at') and calc_model.meta.created_at else None,
            updated_at=calc_model.meta.updated_at.isoformat() if hasattr(calc_model.meta, 'updated_at') and calc_model.meta.updated_at else None,
        )
    
    # Get calculation ULID
    calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else ""
    
    # Get engine family
    engine = calc_model.engine_family if calc_model else None
    if not engine and hasattr(calc_obj, 'steps') and calc_obj.steps:
        # Try to infer from first step
        first_step = calc_obj.steps[0]
        if hasattr(first_step, 'engine'):
            engine = first_step.engine
        elif hasattr(first_step, 'step_type_spec'):
            # Extract engine from step_type_spec using canonical function
            from qmatsuite.workflow.step_type_convert import prefix_from, is_spec
            step_type_spec = first_step.step_type_spec
            if step_type_spec and is_spec(step_type_spec):
                engine = prefix_from(step_type_spec)
    
    # Derive status
    status = _derive_calculation_status(calc_obj)
    
    # Get step ULIDs and counts
    step_ulids = []
    step_count = 0
    completed_step_count = 0
    
    if hasattr(calc_obj, 'steps'):
        step_count = len(calc_obj.steps)
        for step in calc_obj.steps:
            # Step stores ULID in meta.ulid (ResourceMeta)
            step_ulid = None
            if hasattr(step, 'meta') and step.meta:
                step_ulid = step.meta.ulid
            if step_ulid:
                step_ulids.append(step_ulid)

            # Count completed steps (simplified)
            step_status = getattr(step, 'status', None)
            if step_status == "completed" or step_status == "success":
                completed_step_count += 1
    
    # Get structure ULID
    structure_ulid = calc_model.structure_ulid if hasattr(calc_model, 'structure_ulid') else None
    
    return CalculationDTO(
        calc_ulid=calc_ulid,
        engine=engine or "unknown",
        status=status,
        meta=meta,
        structure_ulid=structure_ulid,
        step_ulids=step_ulids if step_ulids else None,
        step_count=step_count if step_count > 0 else None,
        completed_step_count=completed_step_count if completed_step_count > 0 else None,
    )


def step_to_dto(
    step_resolved: Any,  # ResolvedResource
    step_obj: Any,  # Step
    calc_ulid: str,
) -> StepDTO:
    """
    Map step data to StepDTO.
    
    Args:
        step_resolved: ResolvedResource for the step
        step_obj: Step object
        calc_ulid: Parent calculation ULID
        
    Returns:
        StepDTO
    """
    from datetime import datetime
    from qmatsuite.api import get_step_type_gen
    
    # Extract metadata
    meta = None
    if step_resolved.meta:
        # ResourceMeta only has id, name, slug, path, kind
        # Optional fields (description, tags, created_at, updated_at) may not exist
        meta = MetaDTO(
            ulid=step_resolved.meta.ulid,
            slug=step_resolved.meta.slug,
            name=step_resolved.meta.name,
            path=getattr(step_resolved.meta, 'path', None),
            description=getattr(step_resolved.meta, 'description', None),
            tags=list(step_resolved.meta.tags) if hasattr(step_resolved.meta, 'tags') and step_resolved.meta.tags else None,
            created_at=step_resolved.meta.created_at.isoformat() if hasattr(step_resolved.meta, 'created_at') and step_resolved.meta.created_at else None,
            updated_at=step_resolved.meta.updated_at.isoformat() if hasattr(step_resolved.meta, 'updated_at') and step_resolved.meta.updated_at else None,
        )
    
    # Get step ULID
    step_ulid = step_resolved.meta.ulid if step_resolved.meta else ""
    
    # Get step type (SPEC)
    step_type_spec = step_obj.step_type_spec if hasattr(step_obj, 'step_type_spec') else "unknown"
    
    # Convert to GEN using registry SSOT
    step_type_gen = None
    if step_type_spec and step_type_spec != "unknown":
        try:
            step_type_gen = get_step_type_gen(step_type_spec)
        except (KeyError, ValueError):
            pass
    
    # Derive status (simplified - would check step results in full implementation)
    status = "pending"
    if hasattr(step_obj, 'status'):
        status_val = step_obj.status
        if isinstance(status_val, str):
            status = status_val
        elif hasattr(status_val, 'value'):
            status = status_val.value
    
    # Get execution details (if available from step results)
    started_at = None
    completed_at = None
    duration_seconds = None
    exit_code = None
    error_message = None
    
    # In a full implementation, we'd check step results/history for these
    # For now, leave them as None
    
    return StepDTO(
        step_ulid=step_ulid,
        calc_ulid=calc_ulid,
        step_type_spec=step_type_spec,
        status=status,
        step_type_gen=step_type_gen,
        meta=meta,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=duration_seconds,
        exit_code=exit_code,
        error_message=error_message,
    )


def step_to_dict(step_dto: StepDTO) -> dict[str, Any]:
    """
    Convert StepDTO to dictionary for daemon responses.

    Args:
        step_dto: StepDTO to convert

    Returns:
        Dictionary representation of the step
    """
    result = {
        "ulid": step_dto.step_ulid,  # Backwards compat field for GUI
        "step_ulid": step_dto.step_ulid,
        "calc_ulid": step_dto.calc_ulid,
        "step_type_spec": step_dto.step_type_spec,
        "step_type_gen": step_dto.step_type_gen,  # Never fallback to step_type_spec - they're semantically different
        "status": step_dto.status,
    }

    # Add optional metadata
    if step_dto.meta:
        result["meta"] = {
            "slug": step_dto.meta.slug,
            "name": step_dto.meta.name,
        }
        if step_dto.meta.description:
            result["meta"]["description"] = step_dto.meta.description
        if step_dto.meta.tags:
            result["meta"]["tags"] = step_dto.meta.tags
        if step_dto.meta.created_at:
            result["meta"]["created_at"] = step_dto.meta.created_at
        if step_dto.meta.updated_at:
            result["meta"]["updated_at"] = step_dto.meta.updated_at

    # Add optional execution details
    if step_dto.started_at:
        result["started_at"] = step_dto.started_at
    if step_dto.completed_at:
        result["completed_at"] = step_dto.completed_at
    if step_dto.duration_seconds is not None:
        result["duration_seconds"] = step_dto.duration_seconds
    if step_dto.exit_code is not None:
        result["exit_code"] = step_dto.exit_code
    if step_dto.error_message:
        result["error_message"] = step_dto.error_message

    return result
