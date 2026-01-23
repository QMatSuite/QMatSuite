"""
QVService: Main API service class.

This module provides the QVService class which is the primary entry point
for all API operations.
"""

from __future__ import annotations

from pathlib import Path

from quantumvitas.api._mapping.dto_mapping import (
    analysis_summary_to_dto,
    analysis_ref_to_dto,
    structure_to_dto,
    calculation_to_dto,
    step_to_dto,
)
from quantumvitas.api._mapping.exc_mapping import map_kernel_exception
from quantumvitas.api.errors import APIError
from quantumvitas.api.types.analysis import AnalysisRefDTO, AnalysisSummaryDTO
from quantumvitas.api.types.calculation import CalculationDTO, StepDTO
from quantumvitas.api.types.structure import StructureDTO


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
    
    # Structure domain (PR4)
    class Structure:
        """Structure capabilities."""
        
        def __init__(self, service: QVService):
            self._service = service
        
        def get(self, selector: str) -> StructureDTO:
            """
            Get structure by selector.
            
            Args:
                selector: Structure selector (ULID, slug, name, or path)
                
            Returns:
                StructureDTO (no coordinate arrays)
                
            Raises:
                APIError: If structure not found
            """
            try:
                from quantumvitas.core.resolution import require_structure
                from quantumvitas.core.models import load_structure_model
                from quantumvitas.io.structure_io import read_structure
                
                # Resolve structure
                struct_resolved = require_structure(self._service.project_root, selector)
                
                # Load structure file
                struct_path = struct_resolved.absolute_path
                if not struct_path.exists():
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Structure file not found: {struct_path}",
                        context={"selector": selector, "path": str(struct_path)}
                    )
                
                # Load structure model for metadata
                struct_model = load_structure_model(struct_path, self._service.project_root)
                
                # Load pymatgen structure for crystallographic data
                pmg_structure = read_structure(struct_path)
                
                # Build StructureDTO
                return structure_to_dto(
                    struct_resolved=struct_resolved,
                    struct_model=struct_model,
                    pmg_structure=pmg_structure,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list(self, project_selector: str | None = None) -> list[StructureDTO]:
            """
            List all structures in project.
            
            Args:
                project_selector: Unused (for future multi-project support)
                
            Returns:
                List of StructureDTO
                
            Raises:
                APIError: If project invalid
            """
            try:
                from quantumvitas.core.resolution import list_structures
                from quantumvitas.core.models import load_structure_model
                from quantumvitas.io.structure_io import read_structure
                
                # List all structures
                struct_resolved_list = list_structures(self._service.project_root)
                
                results = []
                for struct_resolved in struct_resolved_list:
                    try:
                        struct_path = struct_resolved.absolute_path
                        if not struct_path.exists():
                            continue
                        
                        # Load structure model and pymatgen structure
                        struct_model = load_structure_model(struct_path, self._service.project_root)
                        pmg_structure = read_structure(struct_path)
                        
                        # Build StructureDTO
                        dto = structure_to_dto(
                            struct_resolved=struct_resolved,
                            struct_model=struct_model,
                            pmg_structure=pmg_structure,
                        )
                        results.append(dto)
                    except Exception:
                        # Skip structures that can't be loaded
                        continue
                
                return results
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_atoms(self, selector: str) -> dict:
            """
            Get full atomic coordinates (Jupyter-only).
            
            Args:
                selector: Structure selector
                
            Returns:
                Dict with full atomic data (positions, species, etc.)
                
            Raises:
                APIError: If structure not found
            """
            try:
                from quantumvitas.core.resolution import require_structure
                from quantumvitas.io.structure_io import read_structure
                
                # Resolve and load structure
                struct_resolved = require_structure(self._service.project_root, selector)
                struct_path = struct_resolved.absolute_path
                
                if not struct_path.exists():
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Structure file not found: {struct_path}",
                        context={"selector": selector}
                    )
                
                pmg_structure = read_structure(struct_path)
                
                # Extract full atomic data
                positions = pmg_structure.cart_coords.tolist()
                species = [str(site.specie) for site in pmg_structure]
                
                result = {
                    "positions": positions,
                    "species": species,
                    "num_atoms": len(pmg_structure),
                }
                
                # Add lattice if periodic
                if hasattr(pmg_structure, "lattice"):
                    result["lattice"] = pmg_structure.lattice.matrix.tolist()
                    result["lattice_abc"] = pmg_structure.lattice.abc
                    result["lattice_angles"] = pmg_structure.lattice.angles
                
                return result
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def visualize(self, selector: str, format: str = "json") -> dict:
            """
            Get structure visualization data.
            
            Args:
                selector: Structure selector
                format: Output format ("json" for data, "png"/"svg" for images)
                
            Returns:
                Dict with visualization data
                
            Raises:
                APIError: If structure not found
            """
            try:
                from quantumvitas.core.resolution import require_structure
                from quantumvitas.io.structure_io import read_structure
                from quantumvitas.analysis.structure_viz import visualize_structure
                
                # Resolve and load structure
                struct_resolved = require_structure(self._service.project_root, selector)
                struct_path = struct_resolved.absolute_path
                
                if not struct_path.exists():
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Structure file not found: {struct_path}",
                        context={"selector": selector}
                    )
                
                pmg_structure = read_structure(struct_path)
                
                # Generate visualization
                if format == "json":
                    # Return JSON-serializable visualization data
                    # For now, return basic structure info for visualization
                    # Full visualization would require the structure_viz module
                    return {
                        "structure_id": struct_resolved.meta.id if struct_resolved.meta else "",
                        "num_atoms": len(pmg_structure),
                        "formula": pmg_structure.formula,
                    }
                else:
                    # For image formats, use the visualization function
                    # This is a simplified version - full implementation would generate images
                    result = visualize_structure(
                        structure=pmg_structure,
                        output_path=None,  # Don't save, just get data
                        plot_format=format,
                    )
                    return {
                        "structure_id": struct_resolved.meta.id if struct_resolved.meta else "",
                        "n_atoms": result.n_atoms if hasattr(result, "n_atoms") else len(pmg_structure),
                        "format": format,
                    }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
    
    @property
    def structure(self) -> Structure:
        """Access structure capabilities."""
        return QVService.Structure(self)
    
    # Calculation domain (PR5)
    class Calculation:
        """Calculation read capabilities."""
        
        def __init__(self, service: QVService):
            self._service = service
        
        def get(self, selector: str) -> CalculationDTO:
            """
            Get calculation by selector.
            
            Args:
                selector: Calculation selector (ULID, slug, name, or path)
                
            Returns:
                CalculationDTO
                
            Raises:
                APIError: If calculation not found
            """
            try:
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Load calculation model
                calc_yaml = calc_dir / "calculation.yaml"
                if not calc_yaml.exists():
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Calculation file not found: {calc_yaml}",
                        context={"selector": selector, "path": str(calc_dir)}
                    )
                
                project = Project.open(self._service.project_root)
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Load full Calculation object for step info
                from quantumvitas.calculation.calculation import Calculation
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # Build CalculationDTO
                return calculation_to_dto(
                    calc_resolved=calc_resolved,
                    calc_model=calc_model,
                    calc_obj=calc_obj,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list(self, project_selector: str | None = None, status: str | None = None) -> list[CalculationDTO]:
            """
            List calculations in project.
            
            Args:
                project_selector: Unused (for future multi-project support)
                status: Optional status filter (pending, running, completed, failed)
                
            Returns:
                List of CalculationDTO
                
            Raises:
                APIError: If project invalid
            """
            try:
                from quantumvitas.core.resolution import list_calculations
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                
                # List all calculations
                calc_resolved_list = list_calculations(self._service.project_root)
                
                project = Project.open(self._service.project_root)
                results = []
                
                for calc_resolved in calc_resolved_list:
                    try:
                        # Get calculation directory
                        if calc_resolved.absolute_path.name == "calculation.yaml":
                            calc_dir = calc_resolved.absolute_path.parent
                        else:
                            calc_dir = calc_resolved.absolute_path
                        
                        calc_yaml = calc_dir / "calculation.yaml"
                        if not calc_yaml.exists():
                            continue
                        
                        # Load calculation model and object
                        calc_model = load_calculation(calc_yaml, self._service.project_root)
                        calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                        
                        # Build CalculationDTO
                        dto = calculation_to_dto(
                            calc_resolved=calc_resolved,
                            calc_model=calc_model,
                            calc_obj=calc_obj,
                        )
                        
                        # Filter by status if requested
                        if status is None or dto.status == status:
                            results.append(dto)
                    except Exception:
                        # Skip calculations that can't be loaded
                        continue
                
                return results
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_step(self, calc_selector: str, step_selector: str) -> StepDTO:
            """
            Get step by selectors.
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector (ULID, slug, name, or index)
                
            Returns:
                StepDTO
                
            Raises:
                APIError: If calculation or step not found
            """
            try:
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                
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
                
                # Load calculation to get step info
                project = Project.open(self._service.project_root)
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # Find matching step
                step_obj = None
                for step in calc_obj.steps:
                    if step.id == step_resolved.meta.id if step_resolved.meta else None:
                        step_obj = step
                        break
                
                if step_obj is None:
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Step not found in calculation",
                        context={"calc_selector": calc_selector, "step_selector": step_selector}
                    )
                
                # Build StepDTO
                return step_to_dto(
                    step_resolved=step_resolved,
                    step_obj=step_obj,
                    calc_id=calc_resolved.meta.id if calc_resolved.meta else "",
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list_steps(self, calc_selector: str) -> list[StepDTO]:
            """
            List all steps in a calculation.
            
            Args:
                calc_selector: Calculation selector
                
            Returns:
                List of StepDTO
                
            Raises:
                APIError: If calculation not found
            """
            try:
                from quantumvitas.core.resolution import require_calculation, list_steps
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Load calculation to get steps
                project = Project.open(self._service.project_root)
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # List step resources
                step_resolved_list = list_steps(self._service.project_root, calc_selector)
                
                # Build step ID to step object mapping
                step_map = {step.id: step for step in calc_obj.steps}
                
                results = []
                calc_id = calc_resolved.meta.id if calc_resolved.meta else ""
                
                for step_resolved in step_resolved_list:
                    try:
                        step_id = step_resolved.meta.id if step_resolved.meta else None
                        step_obj = step_map.get(step_id) if step_id else None
                        
                        if step_obj:
                            dto = step_to_dto(
                                step_resolved=step_resolved,
                                step_obj=step_obj,
                                calc_id=calc_id,
                            )
                            results.append(dto)
                    except Exception:
                        # Skip steps that can't be loaded
                        continue
                
                return results
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_effective_params(self, calc_selector: str) -> dict:
            """
            Get effective parameters for a calculation (merged params).
            
            Args:
                calc_selector: Calculation selector
                
            Returns:
                Dict with effective parameters for each step
                
            Raises:
                APIError: If calculation not found
            """
            try:
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                from quantumvitas.calculation.step_defaults import get_default_step_params
                
                # Resolve and load calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                project = Project.open(self._service.project_root)
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # Build effective params for each step
                effective_params = {}
                
                for step in calc_obj.steps:
                    step_id = step.id
                    step_type = step.step_type if hasattr(step, 'step_type') else None
                    
                    if not step_type:
                        continue
                    
                    # Get defaults for step type
                    defaults = get_default_step_params(step_type)
                    
                    # Get step params (if available)
                    step_params = {}
                    if hasattr(step, 'parameters') and step.parameters:
                        step_params = step.parameters.copy() if isinstance(step.parameters, dict) else {}
                    
                    # Merge: defaults first, then step params override
                    merged = {}
                    for section in set(list(defaults.get("parameters", {}).keys()) + list(step_params.keys())):
                        merged[section] = dict(defaults.get("parameters", {}).get(section, {}))
                        merged[section].update(step_params.get(section, {}))
                    
                    effective_params[step_id] = {
                        "step_type": step_type,
                        "parameters": merged,
                        "cards": defaults.get("cards", {}),
                    }
                
                return effective_params
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
    
        def create(
            self,
            engine: str,
            name: str | None = None,
            structure_selector: str | None = None,
            **kwargs
        ) -> CalculationDTO:
            """
            Create a new calculation.
            
            Args:
                engine: Engine family (e.g., "qe", "pyscf")
                name: Optional calculation name
                structure_selector: Optional structure selector
                **kwargs: Additional options (template, structure_kind, etc.)
                
            Returns:
                CalculationDTO for the new calculation
                
            Raises:
                APIError: If creation fails
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                
                # Use legacy init_calculation for now
                template = kwargs.get("template")
                calc_resolved = LegacyService.init_calculation(
                    project_root=self._service.project_root,
                    name=name or f"{engine}_calculation",
                    structure_selector=structure_selector,
                    template=template,
                )
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Load calculation model and object
                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                project = Project.open(self._service.project_root)
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # Build CalculationDTO
                return calculation_to_dto(
                    calc_resolved=calc_resolved,
                    calc_model=calc_model,
                    calc_obj=calc_obj,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def update_meta(self, selector: str, **meta_kwargs) -> CalculationDTO:
            """
            Update calculation metadata.
            
            Args:
                selector: Calculation selector
                **meta_kwargs: Metadata fields to update (name, description, tags, etc.)
                
            Returns:
                Updated CalculationDTO
                
            Raises:
                APIError: If calculation not found or update fails
            """
            try:
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Load calculation model
                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Update metadata
                if "name" in meta_kwargs:
                    calc_model.meta.name = meta_kwargs["name"]
                if "description" in meta_kwargs:
                    calc_model.meta.description = meta_kwargs["description"]
                if "tags" in meta_kwargs:
                    calc_model.meta.tags = set(meta_kwargs["tags"]) if meta_kwargs["tags"] else set()
                
                # Save updated model
                save_calculation(calc_model, calc_dir)
                
                # Reload calculation object
                project = Project.open(self._service.project_root)
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # Rebuild resolved resource with updated meta
                from quantumvitas.core.resolution import ResolvedResource
                calc_resolved = ResolvedResource(
                    meta=calc_model.meta,
                    entry=calc_resolved.entry,
                    absolute_path=calc_dir,
                )
                
                # Build CalculationDTO
                return calculation_to_dto(
                    calc_resolved=calc_resolved,
                    calc_model=calc_model,
                    calc_obj=calc_obj,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def update_step_params(
            self,
            calc_selector: str,
            step_selector: str,
            params: dict
        ) -> StepDTO:
            """
            Update step parameters.
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector
                params: Parameters to update
                
            Returns:
                Updated StepDTO
                
            Raises:
                APIError: If calculation or step not found
            """
            try:
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                
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
                
                # Load calculation model
                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Find and update step entry
                step_id = step_resolved.meta.id if step_resolved.meta else None
                step_entry = None
                for entry in calc_model.steps:
                    if entry.step_id == step_id:
                        step_entry = entry
                        break
                
                if step_entry is None:
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Step not found in calculation",
                        context={"calc_selector": calc_selector, "step_selector": step_selector}
                    )
                
                # Update step parameters (simplified - would need to merge with existing params)
                # For now, just update the step entry's options
                if hasattr(step_entry, 'options'):
                    step_entry.options.update(params)
                
                # Save updated model
                save_calculation(calc_model, calc_dir)
                
                # Reload calculation object
                project = Project.open(self._service.project_root)
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # Find matching step
                step_obj = None
                for step in calc_obj.steps:
                    if step.id == step_id:
                        step_obj = step
                        break
                
                if step_obj is None:
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Step not found after update",
                        context={"calc_selector": calc_selector, "step_selector": step_selector}
                    )
                
                # Build StepDTO
                return step_to_dto(
                    step_resolved=step_resolved,
                    step_obj=step_obj,
                    calc_id=calc_resolved.meta.id if calc_resolved.meta else "",
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def duplicate(self, selector: str, new_name: str | None = None) -> CalculationDTO:
            """
            Duplicate a calculation.
            
            Args:
                selector: Calculation selector
                new_name: Optional name for the duplicate
                
            Returns:
                CalculationDTO for the duplicate
                
            Raises:
                APIError: If calculation not found or duplication fails
            """
            try:
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                from quantumvitas.core.resources import generate_resource_id
                from quantumvitas.core.project_utils import slugify
                import shutil
                import yaml
                
                # Resolve and load original calculation
                calc_resolved = require_calculation(self._service.project_root, selector)
                
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Generate new ID and name
                new_id = generate_resource_id()
                new_name = new_name or f"{calc_model.meta.name}_copy"
                new_slug = slugify(new_name)
                new_path = f"calculations/{new_slug}"
                new_dir = self._service.project_root / new_path
                
                # Copy calculation directory
                if new_dir.exists():
                    from quantumvitas.api.errors import ConflictError
                    raise ConflictError(f"Calculation already exists: {new_slug}")
                
                shutil.copytree(calc_dir, new_dir)
                
                # Update calculation.yaml with new meta
                new_calc_yaml = new_dir / "calculation.yaml"
                calc_data = yaml.safe_load(new_calc_yaml.read_text())
                calc_data["meta"]["id"] = new_id
                calc_data["meta"]["name"] = new_name
                calc_data["meta"]["slug"] = new_slug
                calc_data["meta"]["path"] = new_path
                new_calc_yaml.write_text(yaml.safe_dump(calc_data, sort_keys=False))
                
                # Reload model
                new_calc_model = load_calculation(new_calc_yaml, self._service.project_root)
                
                # Add to project config
                from quantumvitas.core.project_utils import load_project_config, save_project_config
                config = load_project_config(self._service.project_root)
                calculations = config.setdefault("calculations", [])
                calculations.append({"calculation_id": new_id})
                save_project_config(self._service.project_root, config)
                
                # Build ResolvedResource
                from quantumvitas.core.resolution import ResolvedResource
                new_calc_resolved = ResolvedResource(
                    meta=new_calc_model.meta,
                    entry={"calculation_id": new_id},
                    absolute_path=new_dir,
                )
                
                # Load calculation object
                project = Project.open(self._service.project_root)
                new_calc_obj = Calculation.from_yaml(new_dir, project, materialize_steps=False)
                
                # Build CalculationDTO
                return calculation_to_dto(
                    calc_resolved=new_calc_resolved,
                    calc_model=new_calc_model,
                    calc_obj=new_calc_obj,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def delete(self, selector: str) -> None:
            """
            Delete a calculation.
            
            Args:
                selector: Calculation selector
                
            Raises:
                APIError: If calculation not found or deletion fails
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                
                # Use legacy delete_calculation
                LegacyService.delete_calculation(
                    project_root=self._service.project_root,
                    calculation_ulid=selector,  # Assumes selector is ULID
                    force=False,
                    cascade=False,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def add_step(
            self,
            calc_selector: str,
            step_type: str,
            **params
        ) -> StepDTO:
            """
            Add a step to a calculation.
            
            Args:
                calc_selector: Calculation selector
                step_type: Step type (e.g., "qe_scf", "qe_nscf")
                **params: Step parameters
                
            Returns:
                StepDTO for the new step
                
            Raises:
                APIError: If calculation not found or step creation fails
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                
                # Use legacy init_step
                name = params.pop("name", None)
                structure_selector = params.pop("structure_selector", None)
                
                step_resolved = LegacyService.init_step(
                    project_root=self._service.project_root,
                    calculation_selector=calc_selector,
                    step_type=step_type,
                    name=name,
                    structure_selector=structure_selector,
                )
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Load calculation object to find step
                project = Project.open(self._service.project_root)
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # Find matching step
                step_id = step_resolved.meta.id if step_resolved.meta else None
                step_obj = None
                for step in calc_obj.steps:
                    if step.id == step_id:
                        step_obj = step
                        break
                
                if step_obj is None:
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Step not found after creation",
                        context={"calc_selector": calc_selector, "step_selector": step_id}
                    )
                
                # Build StepDTO
                return step_to_dto(
                    step_resolved=step_resolved,
                    step_obj=step_obj,
                    calc_id=calc_resolved.meta.id if calc_resolved.meta else "",
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def remove_step(self, calc_selector: str, step_selector: str) -> None:
            """
            Remove a step from a calculation.
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector
                
            Raises:
                APIError: If calculation or step not found
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                
                # Use legacy delete_step_from_calculation
                LegacyService.delete_step_from_calculation(
                    project_root=self._service.project_root,
                    calculation_selector=calc_selector,
                    step_selector=step_selector,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
    
    @property
    def calculation(self) -> Calculation:
        """Access calculation capabilities."""
        return QVService.Calculation(self)
