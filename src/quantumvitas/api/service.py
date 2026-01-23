"""
QVService: Main API service class.

This module provides the QVService class which is the primary entry point
for all API operations.
"""

from __future__ import annotations

from pathlib import Path

from quantumvitas.api._mapping.dto_mapping import analysis_summary_to_dto, analysis_ref_to_dto
from quantumvitas.api._mapping.exc_mapping import map_kernel_exception
from quantumvitas.api.errors import APIError
from quantumvitas.api.types.analysis import AnalysisRefDTO, AnalysisSummaryDTO


class QVService:
    """
    Service layer for QuantumVITAS operations.
    
    PR3: Analysis capabilities added.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize QVService with a project root.
        
        Args:
            project_root: Path to project root (directory containing project.qv.yml)
        """
        self.project_root = Path(project_root).resolve()
        # Stub: minimal validation
        if not (self.project_root / "project.qv.yml").exists():
            raise ValueError(f"Not a project: {self.project_root}")
    
    # Analysis domain (PR3)
    class Analysis:
        """Analysis capabilities."""
        
        def __init__(self, service: QVService):
            self._service = service
        
        def get_summary(
            self,
            calc_selector: str,
            step_selector: str,
        ) -> AnalysisSummaryDTO:
            """
            Get analysis summary for a calculation step.
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector
                
            Returns:
                AnalysisSummaryDTO with summary data
                
            Raises:
                APIError: If calculation/step not found or analysis fails
            """
            try:
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.analysis.artifacts import read_artifact, AnalysisType
                from quantumvitas.calculation.naming import find_calculation_raw_dir
                
                # Resolve calculation and step
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                step_resolved = require_step(
                    self._service.project_root,
                    calc_selector,
                    step_selector
                )
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Try to get SCF analysis for summary
                scf_data = read_artifact(calc_dir, AnalysisType.SCF)
                
                # Build summary DTO
                return analysis_summary_to_dto(
                    calc_id=calc_resolved.meta.id if calc_resolved.meta else "",
                    step_id=step_resolved.meta.id if step_resolved.meta else "",
                    scf_data=scf_data,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list_properties(
            self,
            calc_selector: str,
            step_selector: str,
        ) -> list[str]:
            """
            List available analysis properties for a calculation step.
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector
                
            Returns:
                List of property names (e.g., ["scf", "dos", "bands"])
                
            Raises:
                APIError: If calculation/step not found
            """
            try:
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.analysis.artifacts import artifact_exists, AnalysisType
                
                # Resolve calculation and step
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                step_resolved = require_step(
                    self._service.project_root,
                    calc_selector,
                    step_selector
                )
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Check which artifacts exist
                properties = []
                for analysis_type in AnalysisType:
                    if artifact_exists(calc_dir, analysis_type):
                        properties.append(analysis_type.value)
                
                return properties
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_property_ref(
            self,
            calc_selector: str,
            step_selector: str,
            property_name: str,
        ) -> AnalysisRefDTO:
            """
            Get reference to large analysis data (not embedded).
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector
                property_name: Property name (e.g., "band_structure", "dos")
                
            Returns:
                AnalysisRefDTO with artifact reference
                
            Raises:
                APIError: If calculation/step not found or property not available
            """
            try:
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.analysis.artifacts import (
                    get_artifact_path,
                    read_artifact,
                    AnalysisType,
                )
                import hashlib
                
                # Resolve calculation and step
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                step_resolved = require_step(
                    self._service.project_root,
                    calc_selector,
                    step_selector
                )
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Map property name to analysis type
                analysis_type_map = {
                    "band_structure": AnalysisType.BANDS,
                    "dos": AnalysisType.DOS,
                    "scf": AnalysisType.SCF,
                }
                
                if property_name not in analysis_type_map:
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Unknown property: {property_name}",
                        context={"property_name": property_name, "available": list(analysis_type_map.keys())}
                    )
                
                analysis_type = analysis_type_map[property_name]
                artifact_path = get_artifact_path(calc_dir, analysis_type)
                
                if not artifact_path.exists():
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Analysis artifact not found: {property_name}",
                        context={"property_name": property_name, "calc_dir": str(calc_dir)}
                    )
                
                # Read artifact for summary
                artifact_data = read_artifact(calc_dir, analysis_type)
                if not artifact_data:
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Failed to read analysis artifact: {property_name}",
                        context={"property_name": property_name}
                    )
                
                # Compute artifact hash and size
                artifact_bytes = artifact_path.read_bytes()
                artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
                artifact_size = len(artifact_bytes)
                
                # Build reference DTO
                return analysis_ref_to_dto(
                    calc_id=calc_resolved.meta.id if calc_resolved.meta else "",
                    step_id=step_resolved.meta.id if step_resolved.meta else "",
                    property_name=property_name,
                    artifact_path=str(artifact_path.relative_to(self._service.project_root)),
                    artifact_format="json",
                    artifact_sha256=artifact_sha256,
                    artifact_size_bytes=artifact_size,
                    artifact_data=artifact_data,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def load_artifact(self, ref: AnalysisRefDTO) -> dict:
            """
            Load full artifact data (Jupyter-only, returns numpy arrays).
            
            Args:
                ref: AnalysisRefDTO reference
                
            Returns:
                Dict with full data (may include numpy arrays)
                
            Raises:
                APIError: If artifact cannot be loaded
            """
            try:
                artifact_path = self._service.project_root / ref.artifact_path
                
                if not artifact_path.exists():
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Artifact not found: {ref.artifact_path}",
                        context={"artifact_path": ref.artifact_path}
                    )
                
                import json
                data = json.loads(artifact_path.read_text())
                
                # Remove metadata
                data.pop("_artifact_meta", None)
                
                return data
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
    
    @property
    def analysis(self) -> Analysis:
        """Access analysis capabilities."""
        return QVService.Analysis(self)
