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
from quantumvitas.api.types.calculation import CalculationDTO, CalculationRefDTO, StepDTO
from quantumvitas.api.types.run import RunResultDTO
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
                ValidationError: If ref is invalid or missing required fields
                NotFoundError: If artifact file not found
                APIError: For other errors
            """
            try:
                from quantumvitas.api.errors import ValidationError, NotFoundError
                from pathlib import Path
                
                # Validate input
                if ref is None:
                    raise ValidationError(
                        "AnalysisRefDTO cannot be None",
                        code="VALIDATION_FAILED",
                        context={"ref": None}
                    )
                
                if not ref.artifact_path:
                    raise ValidationError(
                        "AnalysisRefDTO missing artifact_path",
                        code="VALIDATION_FAILED",
                        context={"ref": ref.to_dict() if hasattr(ref, 'to_dict') else str(ref)}
                    )
                
                # Resolve artifact path (relative to project root)
                artifact_path = Path(self._service.project_root) / ref.artifact_path
                artifact_path = artifact_path.resolve()
                
                # Security check: ensure path is within project root
                try:
                    artifact_path.relative_to(Path(self._service.project_root).resolve())
                except ValueError:
                    raise ValidationError(
                        f"Artifact path outside project root: {ref.artifact_path}",
                        code="VALIDATION_FAILED",
                        context={"artifact_path": ref.artifact_path}
                    )
                
                # Check if file exists
                if not artifact_path.exists():
                    raise NotFoundError(
                        f"Artifact not found: {ref.artifact_path}",
                        context={
                            "artifact_path": ref.artifact_path,
                            "resolved_path": str(artifact_path)
                        }
                    )
                
                # Load based on format
                artifact_format = ref.artifact_format.lower() if ref.artifact_format else "json"
                
                if artifact_format == "json":
                    import json
                    try:
                        data = json.loads(artifact_path.read_text())
                        # Remove metadata if present
                        data.pop("_artifact_meta", None)
                        return data
                    except json.JSONDecodeError as e:
                        from quantumvitas.api.errors import InternalError
                        raise InternalError(
                            f"Failed to parse JSON artifact: {e}",
                            context={"artifact_path": ref.artifact_path}
                        )
                
                elif artifact_format == "npz":
                    try:
                        import numpy as np
                        data = np.load(str(artifact_path))
                        # Convert to dict (arrays remain as numpy arrays)
                        result = {key: data[key] for key in data.keys()}
                        data.close()
                        return result
                    except Exception as e:
                        from quantumvitas.api.errors import InternalError
                        raise InternalError(
                            f"Failed to load NPZ artifact: {e}",
                            context={"artifact_path": ref.artifact_path}
                        )
                
                elif artifact_format == "hdf5":
                    # HDF5 support would require h5py
                    # For now, raise an error indicating it's not yet implemented
                    from quantumvitas.api.errors import InternalError
                    raise InternalError(
                        f"HDF5 format not yet supported: {artifact_format}",
                        context={"artifact_path": ref.artifact_path, "format": artifact_format}
                    )
                
                else:
                    from quantumvitas.api.errors import ValidationError
                    raise ValidationError(
                        f"Unsupported artifact format: {artifact_format}",
                        code="VALIDATION_FAILED",
                        context={"artifact_format": artifact_format, "supported": ["json", "npz"]}
                    )
                    
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def analyze_band(
            self,
            bands_file: Path | None = None,
            calculation_selector: str | None = None,
            symmetry_file: Path | None = None,
            scf_file: Path | None = None,
            fermi_energy: float | None = None,
            plot: bool = False,
            output_dir: Path | None = None,
            plot_format: str = "png",
            energy_range: tuple[float, float] | None = None,
            shift_fermi: bool = True,
        ) -> dict:
            """
            Analyze band structure data.

            Args:
                bands_file: Path to bands.dat.gnu file (auto-detected if calculation provided)
                calculation_selector: Calculation selector to auto-locate files
                symmetry_file: Path to bands.x output with high-symmetry points
                scf_file: Path to pw.x output (NSCF/SCF) for Fermi energy and reciprocal lattice
                fermi_energy: Override Fermi energy in eV
                plot: If True, generate band structure plot
                output_dir: Directory for output files (None for auto-detect)
                plot_format: Plot format (png, svg, pdf)
                energy_range: Energy range for plot (min, max) in eV
                shift_fermi: If True, shift energies to Fermi level

            Returns:
                Dict with band analysis results
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                return LegacyService.analyze_band(
                    project_root=self._service.project_root,
                    bands_file=bands_file,
                    calculation_selector=calculation_selector,
                    symmetry_file=symmetry_file,
                    scf_file=scf_file,
                    fermi_energy=fermi_energy,
                    plot=plot,
                    output_dir=output_dir,
                    plot_format=plot_format,
                    energy_range=energy_range,
                    shift_fermi=shift_fermi,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def analyze_dos(
            self,
            dos_file: Path,
            fermi_energy: float | None = None,
            scf_file: Path | None = None,
            plot: bool = False,
            output_dir: Path | None = None,
            plot_format: str = "png",
            energy_range: tuple[float, float] | None = None,
            shift_fermi: bool = True,
        ) -> dict:
            """
            Analyze DOS data file.

            Args:
                dos_file: Path to DOS data file (.dat)
                fermi_energy: Override Fermi energy in eV
                scf_file: Path to SCF/NSCF output to extract Fermi energy
                plot: If True, generate DOS plot
                output_dir: Directory for output files (None for auto-detect)
                plot_format: Plot format (png, svg, pdf)
                energy_range: Energy range for plot (min, max) in eV
                shift_fermi: If True, shift energies to Fermi level

            Returns:
                Dict with DOS analysis results
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                return LegacyService.analyze_dos(
                    project_root=self._service.project_root,
                    dos_file=dos_file,
                    fermi_energy=fermi_energy,
                    scf_file=scf_file,
                    plot=plot,
                    output_dir=output_dir,
                    plot_format=plot_format,
                    energy_range=energy_range,
                    shift_fermi=shift_fermi,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_band_structure_data(
            self,
            calculation_selector: str,
            step_selector: str | None = None,
        ) -> dict:
            """
            Get band structure data for plotting in GUI.

            Args:
                calculation_selector: Calculation selector
                step_selector: Optional step selector

            Returns:
                Dict with band energies, k-distances, high-symmetry points, and Fermi energy
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                return LegacyService.get_band_structure_data(
                    project_root=self._service.project_root,
                    calculation_selector=calculation_selector,
                    step_selector=step_selector,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_scf_convergence_data(
            self,
            calculation_selector: str,
            step_selector: str,
        ) -> dict:
            """
            Get SCF convergence data for a specific step in a calculation.

            Args:
                calculation_selector: Calculation selector
                step_selector: Step selector

            Returns:
                Dict with SCF convergence data (iterations, energies, etc.)
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                return LegacyService.get_scf_convergence_data(
                    project_root=self._service.project_root,
                    calculation_selector=calculation_selector,
                    step_selector=step_selector,
                )
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
        
        def require_ref(self, selector: str, config: dict | None = None) -> Any:
            """
            Resolve structure selector to ResolvedResource (for internal use).
            
            Args:
                selector: Structure selector (ULID, slug, name, or path)
                config: Optional project config (for backward compatibility)
                
            Returns:
                ResolvedResource (kernel type, not DTO)
                
            Raises:
                APIError: If structure not found
            """
            try:
                from quantumvitas.core.resolution import require_structure
                return require_structure(self._service.project_root, selector)
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
        
        def import_file(
            self,
            source: Path | str,
            name: str | None = None,
            format: str = "auto",
        ) -> StructureDTO:
            """
            Import a structure file into the project.
            
            Args:
                source: Path to source structure file
                name: Optional name for the structure (defaults to filename stem)
                format: File format hint ("auto" to detect)
                
            Returns:
                StructureDTO for the imported structure
                
            Raises:
                APIError: If import fails
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                from quantumvitas.core.resolution import ResolvedResource
                
                # Use legacy import_structure
                source_path = Path(source).resolve()
                struct_resolved = LegacyService.import_structure(
                    project_root=self._service.project_root,
                    source=source_path,
                    name=name,
                    format=format,
                )
                
                # Build StructureDTO from resolved resource
                from quantumvitas.core.models import load_structure_model
                from quantumvitas.io.structure_io import read_structure
                
                struct_model = load_structure_model(struct_resolved.absolute_path, self._service.project_root)
                pmg_structure = read_structure(struct_resolved.absolute_path)
                
                return structure_to_dto(
                    struct_resolved=struct_resolved,
                    struct_model=struct_model,
                    pmg_structure=pmg_structure,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_vis_data(
            self,
            selector: str,
            supercell: tuple[int, int, int] = (1, 1, 1),
            repeat_boundary: bool = False,
            display_mode: str = "primitive",
            box_bounds: tuple[float, float, float, float, float, float] | None = None,
        ) -> dict:
            """
            Get pure visualization data for a structure (no matplotlib).

            Returns all data needed for 3D rendering in a GUI:
            - Lattice vectors and parameters
            - Atom positions (Cartesian and fractional)
            - Element information and colors
            - Detected bonds

            Args:
                selector: Structure selector (name/slug/path)
                supercell: Tuple of (a, b, c) supercell scaling factors (for supercell mode)
                repeat_boundary: If True, include periodic images at boundaries
                display_mode: One of "primitive", "supercell", "conventional", "box"
                box_bounds: For box mode: (xmin, xmax, ymin, ymax, zmin, zmax)

            Returns:
                Dict with all visualization data (JSON-serializable)
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                return LegacyService.get_structure_vis_data(
                    project_root=self._service.project_root,
                    selector=selector,
                    supercell=supercell,
                    repeat_boundary=repeat_boundary,
                    display_mode=display_mode,
                    box_bounds=box_bounds,
                )
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
        
        def require_ref(self, selector: str, config: dict | None = None) -> Any:
            """
            Resolve calculation selector to ResolvedResource (for internal use).
            
            Args:
                selector: Calculation selector (ULID, slug, name, or path)
                config: Optional project config (for backward compatibility)
                
            Returns:
                ResolvedResource (kernel type, not DTO)
                
            Raises:
                APIError: If calculation not found
            """
            try:
                from quantumvitas.core.resolution import require_calculation
                return require_calculation(self._service.project_root, selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def require_step_ref(
            self,
            calc_selector: str,
            step_selector: str,
            config: dict | None = None,
        ) -> Any:
            """
            Resolve step selector to ResolvedResource (for internal use).
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector (ULID, slug, name, or index)
                config: Optional project config (for backward compatibility)
                
            Returns:
                ResolvedResource (kernel type, not DTO)
                
            Raises:
                APIError: If calculation or step not found
            """
            try:
                from quantumvitas.core.resolution import require_step
                return require_step(self._service.project_root, calc_selector, step_selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def resolve_enclosing_path(self, path: Path | None = None) -> CalculationRefDTO | None:
            """
            Resolve calculation that encloses the given path.
            
            Args:
                path: Path to check (defaults to current working directory)
                
            Returns:
                CalculationRefDTO if found, None otherwise
            """
            try:
                from quantumvitas.core.project_utils import find_enclosing_calculation
                from quantumvitas.api.utils import ensure_relative_path, extract_calculation_selector_from_entry
                from quantumvitas.api._mapping.dto_mapping import calculation_ref_to_dto
                
                if path is None:
                    path = Path.cwd()
                path = Path(path).resolve()
                
                config = self._service.project.get_config()
                entry = find_enclosing_calculation(self._service.project_root, config, start=path)
                
                if entry is None:
                    return None
                
                # Extract selector from entry and resolve to get path
                selector = extract_calculation_selector_from_entry(entry)
                if not selector:
                    return None
                
                # Resolve to get ResolvedResource with path
                calc_resolved = self.require_ref(selector)
                
                # Get calculation directory path
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Get relative path
                rel_path = ensure_relative_path(calc_dir, base=self._service.project_root)
                
                # Build CalculationRefDTO
                return calculation_ref_to_dto(calc_resolved, rel_path)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                # Return None on any error (not found)
                return None
        
        def require_enclosing(self, path: Path | None = None) -> CalculationRefDTO:
            """
            Require calculation that encloses the given path.
            
            Args:
                path: Path to check (defaults to current working directory)
                
            Returns:
                CalculationRefDTO
                
            Raises:
                NotFoundError: If no calculation encloses the path
            """
            result = self.resolve_enclosing_path(path)
            if result is None:
                from quantumvitas.api.errors import NotFoundError
                path_str = str(path) if path else "current directory"
                raise NotFoundError(
                    f"No calculation found enclosing {path_str}",
                    context={"path": str(path) if path else None}
                )
            return result
        
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
            Update step parameters by modifying the step YAML file.

            Args:
                calc_selector: Calculation selector
                step_selector: Step selector
                params: Parameters to update. Can contain:
                    - 'parameters': dict of QE namelist parameters
                    - 'cards': dict of QE card data
                    - 'species_overrides': dict of species-specific overrides
                    - Any other step-level keys

            Returns:
                Updated StepDTO

            Raises:
                APIError: If calculation or step not found
            """
            try:
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.core.yamldoc import StepDoc
                from quantumvitas.workflow.step_factory import save_step_doc
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                from quantumvitas.calculation.step import Step
                from quantumvitas.core.resources import ResourceMeta
                from quantumvitas.core.resolution import ResolvedResource
                import logging

                # Resolve calculation and step
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                step_resolved = require_step(
                    self._service.project_root,
                    calc_selector,
                    step_selector
                )

                # Get step path
                step_path = step_resolved.absolute_path

                # Load as StepDoc
                step_doc = StepDoc.load(step_path)

                # Apply updates via StepDoc API
                for key, value in params.items():
                    if value is not None:
                        if key in ("parameters", "cards", "species_overrides"):
                            # Use apply_patch for nested dicts (deep merge)
                            step_doc.apply_patch({key: value})
                        else:
                            step_doc.set([key], value)

                # Save via factory (journaled) - warnings are logged
                warnings = save_step_doc(step_doc, step_path)
                if warnings:
                    logger = logging.getLogger(__name__)
                    for warning in warnings:
                        logger.warning(warning)

                # Get calculation directory for step_to_dto
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path

                # Get calc_id
                calc_id = calc_resolved.meta.id if calc_resolved.meta else ""

                # Re-read step file for fresh data
                import yaml
                step_data = yaml.safe_load(step_path.read_text())
                step_meta_dict = step_data.get("meta", {})
                step_meta = ResourceMeta.from_dict(
                    step_meta_dict,
                    kind="step",
                    default_name=step_selector,
                    default_path=str(step_path.relative_to(self._service.project_root))
                )

                # Create updated ResolvedResource
                step_resolved_updated = ResolvedResource(
                    meta=step_meta,
                    entry={},
                    absolute_path=step_path
                )

                # Get step_type and engine from registry
                from quantumvitas.workflow.registry import get_registry
                registry = get_registry()
                machine_step_type = step_data.get("step_type", "scf")
                step_spec = registry.get(machine_step_type)
                engine = step_spec.engine if step_spec else "qe"

                # Create minimal Step object
                step_obj = Step(
                    meta=step_meta,
                    input_file=step_path,
                    engine=engine,
                    step_type=machine_step_type,
                )

                # Build StepDTO
                return step_to_dto(
                    step_resolved=step_resolved_updated,
                    step_obj=step_obj,
                    calc_id=calc_id,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def duplicate(
            self,
            selector: str,
            *,
            new_name: str | None = None,
            new_slug: str | None = None,
        ) -> CalculationDTO:
            """
            Duplicate a calculation.
            
            Copies SSOT files (calculation.yaml, step.yaml) and raw/ directory.
            Does NOT copy outdir/, .history/, or other execution artifacts.
            
            Args:
                selector: Calculation selector
                new_name: Optional name for the duplicate (defaults to "{original_name}_copy")
                new_slug: Optional slug for the duplicate (defaults to slugified new_name)
                
            Returns:
                CalculationDTO for the duplicate
                
            Raises:
                NotFoundError: If calculation not found
                ConflictError: If new_slug already exists
                APIError: For other duplication failures
            """
            try:
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                from quantumvitas.core.resources import generate_resource_id
                from quantumvitas.core.project_utils import slugify, load_project_config, save_project_config
                from quantumvitas.core.templates import _copy_calculation_from_path
                from quantumvitas.core.resolution import ResolvedResource
                
                # Resolve and load original calculation
                calc_resolved = require_calculation(self._service.project_root, selector)
                
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Generate new ID and determine name/slug
                new_id = generate_resource_id()
                if new_name is None:
                    new_name = f"{calc_model.meta.name}_copy"
                if new_slug is None:
                    new_slug = slugify(new_name)
                
                # Check for slug conflict
                new_path = f"calculations/{new_slug}"
                new_dir = self._service.project_root / new_path
                if new_dir.exists():
                    from quantumvitas.api.errors import ConflictError
                    raise ConflictError(
                        f"Calculation with slug '{new_slug}' already exists",
                        context={"new_slug": new_slug, "new_path": new_path}
                    )
                
                # Use existing copy function which handles SSOT + raw/ only
                # This copies: calculation.yaml, steps/*.step.yaml, raw/ (if exists)
                # Does NOT copy: outdir/, .history/, or other execution artifacts
                # Note: _copy_calculation_from_path derives slug from name, so if new_slug
                # is provided, we need to pass a name that will slugify to new_slug, or
                # manually update the slug after copying
                new_calc_yaml, _, _ = _copy_calculation_from_path(
                    source_path=calc_dir,
                    dest_dir=new_dir,
                    project_root=self._service.project_root,
                    new_name=new_name,  # Will be used for both name and slug derivation
                    calculation_ulid=new_id,
                )
                
                # If new_slug was explicitly provided and differs from slugified name,
                # update the calculation.yaml to use the explicit slug
                if new_slug != slugify(new_name):
                    import yaml
                    calc_data = yaml.safe_load(new_calc_yaml.read_text())
                    calc_data["meta"]["slug"] = new_slug
                    calc_data["meta"]["path"] = f"calculations/{new_slug}"
                    new_calc_yaml.write_text(yaml.safe_dump(calc_data, sort_keys=False, default_flow_style=False))
                    
                    # Also need to rename the directory if slug changed
                    expected_dir = self._service.project_root / f"calculations/{new_slug}"
                    if new_dir != expected_dir:
                        new_dir.rename(expected_dir)
                        new_dir = expected_dir
                        new_calc_yaml = expected_dir / "calculation.yaml"
                
                # Reload model
                new_calc_model = load_calculation(new_calc_yaml, self._service.project_root)
                
                # Add to project config
                config = load_project_config(self._service.project_root)
                calculations = config.setdefault("calculations", [])
                # Check if already in config (shouldn't be, but be safe)
                if not any(c.get("calculation_id") == new_id for c in calculations):
                    calculations.append({"calculation_id": new_id})
                save_project_config(self._service.project_root, config)
                
                # Build ResolvedResource
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
            *,
            name: str | None = None,
            params: dict | None = None,
        ) -> StepDTO:
            """
            Add a step to a calculation.
            
            Args:
                calc_selector: Calculation selector
                step_type: Step type (e.g., "scf", "nscf", "qe_scf" - accepts both public and machine types)
                name: Optional step name (defaults to step_type)
                params: Optional parameter overrides (applied via apply_patch, respects managed keys)
                
            Returns:
                StepDTO for the new step
                
            Raises:
                NotFoundError: If calculation not found
                ValidationError: If step_type is invalid or unmapped
                APIError: For other step creation failures
            """
            try:
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                from quantumvitas.workflow.step_factory import create_and_save_step
                from quantumvitas.workflow.registry import get_registry
                from quantumvitas.core.resources import generate_resource_id
                import yaml
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Get calculation ULID
                calc_id = calc_resolved.meta.id if calc_resolved.meta else ""
                
                # Get structure_id from calculation
                structure_id = calc_model.structure_id if calc_model else None
                
                # Determine step name
                step_name = name or step_type
                
                # Validate step_type and get public type for calculation.yaml
                registry = get_registry()
                spec = registry.get(step_type)
                if not spec:
                    # Unknown step_type
                    from quantumvitas.api.errors import ValidationError
                    raise ValidationError(
                        f"Unknown step type: {step_type}",
                        code="VALIDATION_FAILED",
                        context={"step_type": step_type}
                    )
                
                # Use public_type for calculation.yaml (registry.get() accepts both public and machine types)
                public_step_type = spec.public_type
                
                # Create steps directory
                steps_dir = calc_dir / "steps"
                steps_dir.mkdir(parents=True, exist_ok=True)

                # Generate unique slug (deduplicate against existing step files)
                from quantumvitas.core.resources import slugify
                base_slug = slugify(step_name)
                unique_slug = base_slug
                suffix = 1
                while (steps_dir / f"{unique_slug}.step.yaml").exists():
                    unique_slug = f"{base_slug}-{suffix}"
                    suffix += 1

                # Use unique_slug as name (step factory uses name for slug)
                unique_name = unique_slug if unique_slug != base_slug else step_name

                # Create and save step using canonical factory
                # Factory handles step_type mapping (accepts both public and machine types)
                step_path = create_and_save_step(
                    step_type=step_type,  # Factory handles GEN->SPEC mapping internally
                    name=unique_name,
                    steps_dir=steps_dir,
                    structure_id=structure_id,
                    parent_calculation_id=calc_id,
                    overrides=params,  # apply_patch will be called inside create_step_doc
                )
                
                # Read step file to get step_id
                step_data = yaml.safe_load(step_path.read_text())
                step_id = step_data.get("meta", {}).get("id")
                if not step_id:
                    from quantumvitas.api.errors import InternalError
                    raise InternalError(
                        "Step created but missing ULID in meta",
                        context={"step_path": str(step_path)}
                    )
                
                # Add step to calculation.yaml steps array
                # Use public_type for calculation.yaml (calculation.yaml stores public types)
                from quantumvitas.core.models import CalculationStepEntry
                step_entry = CalculationStepEntry(
                    step_id=step_id,
                    type=public_step_type,  # Public type for calculation.yaml
                )
                
                # Update calculation model
                if not hasattr(calc_model, 'steps') or calc_model.steps is None:
                    calc_model.steps = []
                calc_model.steps.append(step_entry)
                
                # Save calculation.yaml
                save_calculation(calc_model, calc_yaml)
                
                # Build ResolvedResource and Step object from step_data for DTO
                # (We don't resolve via require_step because ResourceIndex may not be updated yet)
                from quantumvitas.core.resources import ResourceMeta
                from quantumvitas.core.resolution import ResolvedResource
                from quantumvitas.calculation.step import Step
                
                step_meta_dict = step_data.get("meta", {})
                step_meta = ResourceMeta.from_dict(
                    step_meta_dict,
                    kind="step",
                    default_name=step_name,
                    default_path=str(step_path.relative_to(self._service.project_root))
                )
                step_resolved = ResolvedResource(
                    meta=step_meta,
                    entry={},  # Empty entry - step not in project config
                    absolute_path=step_path
                )
                
                # Get step_type from step_data (machine type)
                machine_step_type = step_data.get("step_type", public_step_type)
                # Get engine from registry
                step_spec = registry.get(machine_step_type)
                engine = step_spec.engine if step_spec else "qe"
                # Create minimal Step object
                step_obj = Step(
                    meta=step_meta,
                    input_file=step_path,  # Placeholder - not used for DTO
                    engine=engine,
                    step_type=machine_step_type,
                )
                
                # Build StepDTO
                return step_to_dto(
                    step_resolved=step_resolved,
                    step_obj=step_obj,
                    calc_id=calc_id,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def remove_step(self, calc_selector: str, step_selector: str) -> None:
            """
            Remove a step from a calculation.
            
            Removes step from calculation.yaml steps array and moves step file to trash.
            Handles ghost steps (missing files) gracefully.
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector (ULID)
                
            Raises:
                NotFoundError: If calculation or step not found in calculation.yaml
                APIError: For other removal failures
            """
            try:
                from quantumvitas.core.resolution import require_calculation, require_step, ResourceNotFoundError
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.core.project_utils import load_project_config, move_to_trash
                from quantumvitas.core.resolution import make_structure_selector_resolver
                import yaml
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                    calc_yaml = calc_resolved.absolute_path
                else:
                    calc_dir = calc_resolved.absolute_path
                    calc_yaml = calc_dir / "calculation.yaml"
                
                # Load calculation model
                config = load_project_config(self._service.project_root)
                resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                calc_model = load_calculation(calc_yaml, project_root=self._service.project_root, resolve_structure_selector=resolver)
                
                # Find step in calculation.yaml steps array
                step_id = step_selector
                step_entry = None
                for entry in calc_model.steps:
                    if entry.step_id == step_id:
                        step_entry = entry
                        break
                
                if step_entry is None:
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Step '{step_selector}' not found in calculation",
                        context={"calc_selector": calc_selector, "step_selector": step_selector}
                    )
                
                # Remove step entry from calculation model
                calc_model.steps = [e for e in calc_model.steps if e.step_id != step_id]
                
                # Save calculation.yaml
                save_calculation(calc_model, calc_yaml)
                
                # Try to move step file to trash (handle ghost steps gracefully)
                trash_dir = (self._service.project_root / "trash").resolve()
                try:
                    step_resolved = require_step(
                        self._service.project_root,
                        calc_selector,
                        step_selector
                    )
                    step_path = step_resolved.absolute_path
                    if step_path.exists():
                        move_to_trash(step_path, trash_dir)
                except (ResourceNotFoundError, FileNotFoundError):
                    # Ghost step - file already missing, just continue
                    pass
                
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
    
    @property
    def calculation(self) -> Calculation:
        """Access calculation capabilities."""
        return QVService.Calculation(self)
    
    # Run domain (PR7)
    class Run:
        """Run/execution capabilities."""
        
        def __init__(self, service: QVService):
            self._service = service
        
        def run_calculation(
            self,
            calc_selector: str,
            steps: list[str] | None = None,
        ) -> RunResultDTO:
            """
            Run a calculation.
            
            Args:
                calc_selector: Calculation selector
                steps: Optional list of step selectors to run (None = all steps)
                
            Returns:
                RunResultDTO
                
            Raises:
                APIError: If calculation not found or run fails
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                from quantumvitas.core.resolution import require_calculation
                
                # Resolve calculation to get calc_id
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                calc_id = calc_resolved.meta.id if calc_resolved.meta else ""
                
                # Use legacy run_calculation
                result_dict = LegacyService.run_calculation(
                    project_root=self._service.project_root,
                    calculation_selector=calc_selector,
                    strict=False,
                    verbose=False,
                    run_mode="incremental",
                )
                
                # Map to RunResultDTO
                return self._result_dict_to_dto(result_dict, calc_id)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def run_step(
            self,
            calc_selector: str,
            step_selector: str,
        ) -> RunResultDTO:
            """
            Run a single step.
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector
                
            Returns:
                RunResultDTO
                
            Raises:
                APIError: If calculation or step not found or run fails
            """
            try:
                from quantumvitas._api_legacy import QVService as LegacyService
                from quantumvitas.core.resolution import require_calculation
                
                # Resolve calculation to get calc_id
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                calc_id = calc_resolved.meta.id if calc_resolved.meta else ""
                
                # Use legacy run_step
                result_dict = LegacyService.run_step(
                    project_root=self._service.project_root,
                    calculation_selector=calc_selector,
                    step_selector=step_selector,
                    verbose=False,
                )
                
                # Map to RunResultDTO
                return self._result_dict_to_dto(result_dict, calc_id)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_status(self, run_id: str) -> RunResultDTO:
            """
            Get run status by run_id.
            
            Note: This is a simplified implementation. In a full system,
            this would query job history or a job manager.
            
            Args:
                run_id: Run ID (ULID)
                
            Returns:
                RunResultDTO
                
            Raises:
                APIError: If run not found
            """
            try:
                from quantumvitas.api.errors import NotFoundError
                
                # Simplified: For now, we can't easily get run status without JobManager
                # This would need to query calculation history or job manager
                # For now, raise not found
                raise NotFoundError(
                    f"Run status lookup not yet implemented for run_id: {run_id}",
                    context={"run_id": run_id}
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def cancel(self, run_id: str) -> RunResultDTO:
            """
            Cancel a running job.
            
            Attempts to cancel a job via JobManager if available (daemon context).
            If JobManager is not available, attempts to find run info from history
            and returns appropriate status.
            
            Args:
                run_id: Run ID (ULID)
                
            Returns:
                RunResultDTO with cancelled status (or current status if already terminal)
                
            Raises:
                NotFoundError: If run not found
                EngineError: If cancellation fails (e.g., job already running)
            """
            try:
                from quantumvitas.api.errors import NotFoundError, EngineError
                from quantumvitas.history.storage import ProjectHistory
                from quantumvitas.history.run_revision import load_run_revision
                
                # Try to access JobManager if available (daemon context)
                # Check for thread-local or context variable
                job_manager = None
                try:
                    import threading
                    # Check if there's a thread-local job manager
                    if hasattr(threading.current_thread(), 'job_manager'):
                        job_manager = threading.current_thread().job_manager
                except Exception:
                    pass
                
                # If JobManager is available, use it to cancel
                if job_manager is not None:
                    job = job_manager.get_job(run_id)
                    if job is None:
                        raise NotFoundError(
                            f"Run not found: {run_id}",
                            context={"run_id": run_id}
                        )
                    
                    # Attempt cancellation
                    cancelled = job_manager.cancel_job(run_id)
                    
                    # Get updated job status
                    job = job_manager.get_job(run_id)
                    if job is None:
                        raise NotFoundError(
                            f"Run not found after cancellation attempt: {run_id}",
                            context={"run_id": run_id}
                        )
                    
                    # Convert job to RunResultDTO
                    status_map = {
                        "pending": "submitted",
                        "running": "running",
                        "completed": "completed",
                        "failed": "failed",
                        "cancelled": "cancelled",
                    }
                    status = status_map.get(job.status.value, "submitted")
                    
                    # Extract calc_id from job params or result
                    calc_id = ""
                    if job.params:
                        calc_id = job.params.get("calc_id", job.params.get("calc_selector", ""))
                    if not calc_id and job.result:
                        calc_id = job.result.get("calc_id", "")
                    
                    # Extract step_ids
                    step_ids = []
                    if job.steps:
                        step_ids = [s.get("step_id", "") for s in job.steps if s.get("step_id")]
                    
                    # Format timestamps
                    started_at = job.started_at.isoformat() if job.started_at else None
                    completed_at = job.completed_at.isoformat() if job.completed_at else None
                    
                    # Calculate duration if both timestamps available
                    duration_seconds = None
                    if job.started_at and job.completed_at:
                        duration_seconds = (job.completed_at - job.started_at).total_seconds()
                    
                    # Build error DTO if failed
                    error = None
                    if status == "failed" and job.error:
                        from quantumvitas.api.types.error import ErrorDTO
                        error = ErrorDTO(
                            type="RunError",
                            code="RUN_FAILED",
                            message=job.error,
                            retryable=True,
                        )
                    
                    return RunResultDTO(
                        run_id=run_id,
                        calc_id=calc_id,
                        status=status,
                        step_ids=step_ids,
                        started_at=started_at,
                        completed_at=completed_at,
                        duration_seconds=duration_seconds,
                        exit_code=None,
                        log_path=job.output_file,
                        error=error,
                    )
                
                # If JobManager not available, try to find run in history
                history = ProjectHistory(self._service.project_root)
                run_dir = history.get_run_dir(run_id)
                
                if run_dir is None:
                    raise NotFoundError(
                        f"Run not found: {run_id}",
                        context={"run_id": run_id}
                    )
                
                # Load run revision to get status
                try:
                    revision = load_run_revision(run_dir)
                    
                    # Check if run is already terminal
                    if revision.status in ["completed", "failed", "cancelled"]:
                        # Return current status (can't cancel already terminal runs)
                        status_map = {
                            "completed": "completed",
                            "failed": "failed",
                            "cancelled": "cancelled",
                        }
                        status = status_map.get(revision.status, "completed")
                    else:
                        # Run is active but we can't cancel without JobManager
                        # Return current status with hint that cancellation requires daemon
                        status = "running"  # or "submitted" depending on revision.status
                    
                    return RunResultDTO(
                        run_id=run_id,
                        calc_id=revision.calc_id,
                        status=status,
                        step_ids=revision.step_ids or [],
                        started_at=revision.started_at,
                        completed_at=revision.finished_at,
                        duration_seconds=None,  # Would need to calculate from timestamps
                        exit_code=None,
                        log_path=revision.working_dir,
                        error=None,
                    )
                except Exception as e:
                    # If we can't load revision, still raise NotFoundError
                    raise NotFoundError(
                        f"Run not found or inaccessible: {run_id}",
                        context={"run_id": run_id}
                    ) from e
                    
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list_runs(
            self,
            calc_selector: str | None = None,
            status: str | None = None,
        ) -> list[RunResultDTO]:
            """
            List runs, optionally filtered.
            
            Note: This is a simplified implementation. In a full system,
            this would query job history or a job manager.
            
            Args:
                calc_selector: Optional calculation selector filter
                status: Optional status filter
                
            Returns:
                List of RunResultDTO
            """
            try:
                # Simplified: For now, return empty list
                # This would need to query calculation history or job manager
                return []
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def _result_dict_to_dto(self, result_dict: dict, calc_id: str) -> RunResultDTO:
            """Convert legacy result dict to RunResultDTO."""
            from quantumvitas.api.types.error import ErrorDTO
            
            # Extract step IDs
            step_ids = []
            if "steps" in result_dict:
                step_ids = [s.get("step_id", "") for s in result_dict["steps"] if s.get("step_id")]
            
            # Map status
            status_map = {
                "success": "completed",
                "failed": "failed",
                "pending": "submitted",
                "running": "running",
            }
            status = status_map.get(result_dict.get("status", "").lower(), "submitted")
            
            # Extract timing (if available)
            started_at = None
            completed_at = None
            duration_seconds = None
            
            # Extract error if failed
            error = None
            if status == "failed":
                error_msg = result_dict.get("error") or "Run failed"
                error = ErrorDTO(
                    type="RunError",
                    code="RUN_FAILED",
                    message=error_msg,
                    retryable=True,
                )
            
            return RunResultDTO(
                run_id=result_dict.get("run_id", ""),
                calc_id=calc_id,
                status=status,
                step_ids=step_ids,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                exit_code=None,
                log_path=result_dict.get("io_dir"),
                error=error,
            )
    
    @property
    def run(self) -> Run:
        """Access run capabilities."""
        return QVService.Run(self)
    
    # Project domain (PR8)
    class Project:
        """Project capabilities."""
        
        def __init__(self, service: QVService):
            self._service = service
        
        def get_config(self) -> dict:
            """
            Get project configuration.
            
            Returns:
                Project configuration dict
                
            Raises:
                APIError: If project invalid
            """
            try:
                from quantumvitas.core.project_utils import load_project_config
                return load_project_config(self._service.project_root)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def update_config(self, patch: dict) -> dict:
            """
            Update project configuration.
            
            Args:
                patch: Dict with config updates (merged into existing config)
                
            Returns:
                Updated project configuration dict
                
            Raises:
                APIError: If project invalid or update fails
            """
            try:
                from quantumvitas.core.project_utils import load_project_config, save_project_config
                
                # Load current config
                config = load_project_config(self._service.project_root)
                
                # Merge patch into config
                config.update(patch)
                
                # Save updated config
                save_project_config(self._service.project_root, config)
                
                return config
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_species_map(self) -> dict:
            """
            Get project species mapping.
            
            Returns:
                Species mapping dict (element -> pseudo info)
                
            Raises:
                APIError: If project invalid
            """
            try:
                from quantumvitas.core.project_utils import load_project_config
                
                config = load_project_config(self._service.project_root)
                
                # Extract species_map from config (if present)
                # This is typically at the project level or in calculation.yaml
                # For now, return empty dict if not found
                return config.get("species_map", {})
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_potential_map(self) -> dict:
            """
            Get project potential mapping (for LAMMPS).
            
            Returns:
                Potential mapping dict
                
            Raises:
                APIError: If project invalid
            """
            try:
                from quantumvitas.core.project_utils import load_project_config
                
                config = load_project_config(self._service.project_root)
                
                # Extract potential_map from config (if present)
                return config.get("potential_map", {})
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def build_resource_index(self) -> Any:
            """
            Build resource index for project (for internal use).
            
            Returns:
                ResourceIndex (kernel type)
                
            Raises:
                APIError: If project invalid
            """
            try:
                from quantumvitas.core.resolution import build_resource_index
                return build_resource_index(self._service.project_root)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list_calculations(self) -> list[CalculationDTO]:
            """
            List all calculations in project.
            
            Returns:
                List of CalculationDTO
                
            Raises:
                APIError: If project invalid
            """
            try:
                # Delegate to calculation.list()
                return self._service.calculation.list()
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def collect_slugs(self, entries: list[dict], *, exclude: dict | None = None) -> list[str]:
            """
            Collect all slugs from a list of structure or calculation entries.
            
            Args:
                entries: List of entry dicts
                exclude: Optional entry to exclude from collection
                
            Returns:
                List of slug strings
            """
            try:
                from quantumvitas.core.project_utils import collect_slugs as _collect_slugs
                return _collect_slugs(entries, exclude=exclude, project_root=self._service.project_root)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def apply_structure_rename(
            self,
            entry: dict,
            new_name: str | None = None,
            new_slug: str | None = None,
            new_path: Path | None = None,
            config: dict | None = None,
        ) -> None:
            """
            Apply a rename operation to a structure entry.
            
            Args:
                entry: Structure entry dict
                new_name: Optional new name
                new_slug: Optional new slug
                new_path: Optional new path
                config: Optional project config (avoids reloading if provided)
            """
            if config is None:
                config = self.get_config()
            
            from quantumvitas.core.project_utils import apply_structure_rename as _apply_structure_rename
            _apply_structure_rename(
                project_root=self._service.project_root,
                config=config,
                entry=entry,
                new_name=new_name,
                new_slug=new_slug,
                new_path=new_path,
            )
        
        def apply_calculation_rename(
            self,
            entry: dict,
            new_name: str | None = None,
            new_slug: str | None = None,
            new_path: Path | None = None,
            config: dict | None = None,
        ) -> None:
            """
            Apply a rename operation to a calculation entry.
            
            Args:
                entry: Calculation entry dict
                new_name: Optional new name
                new_slug: Optional new slug
                new_path: Optional new path
                config: Optional project config (avoids reloading if provided)
            """
            if config is None:
                config = self.get_config()
            
            from quantumvitas.core.project_utils import apply_calculation_rename as _apply_calculation_rename
            _apply_calculation_rename(
                project_root=self._service.project_root,
                config=config,
                entry=entry,
                new_name=new_name,
                new_slug=new_slug,
                new_path=new_path,
            )
    
    @property
    def project(self) -> Project:
        """Access project capabilities."""
        return QVService.Project(self)
    
    # Engine domain (PR9)
    class Engine:
        """Engine discovery capabilities."""
        
        def __init__(self, service: QVService):
            self._service = service
        
        def list(self) -> list[dict]:
            """
            List all available engines.
            
            Returns:
                List of engine info dicts
            """
            try:
                from quantumvitas.engine.registry import create_default_registry
                
                registry = create_default_registry()
                engines = []
                
                for engine_name in registry.list_engines():
                    engine = registry.get(engine_name)
                    engines.append({
                        "name": engine_name,
                        "supported_presets": getattr(engine, "supported_presets", []),
                    })
                
                return engines
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_info(self, engine_name: str) -> dict:
            """
            Get information about a specific engine.
            
            Args:
                engine_name: Engine name (e.g., "qe", "pyscf")
                
            Returns:
                Engine info dict
                
            Raises:
                APIError: If engine not found
            """
            try:
                from quantumvitas.engine.registry import create_default_registry
                from quantumvitas.api.errors import NotFoundError
                
                registry = create_default_registry()
                
                if not registry.has(engine_name):
                    raise NotFoundError(
                        f"Engine not found: {engine_name}",
                        context={"engine_name": engine_name}
                    )
                
                engine = registry.get(engine_name)
                
                info = {
                    "name": engine_name,
                    "supported_presets": getattr(engine, "supported_presets", []),
                }
                
                # Add version if available
                if hasattr(engine, "version") and engine.version:
                    info["version"] = engine.version
                
                # Add executable path if available
                if hasattr(engine, "executable"):
                    try:
                        info["executable"] = str(engine.executable)
                    except Exception:
                        pass
                
                return info
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list_step_types(self, engine_name: str | None = None) -> list[dict]:
            """
            List step types, optionally filtered by engine.
            
            Args:
                engine_name: Optional engine name filter
                
            Returns:
                List of step type info dicts
            """
            try:
                from quantumvitas.workflow.generalized_steps import get_supported_generalized_steps
                from quantumvitas.workflow.registry import get_registry
                
                if engine_name:
                    # Get step types for specific engine
                    step_types = get_supported_generalized_steps(engine_name)
                    return [{"name": st, "engine": engine_name} for st in step_types]
                else:
                    # Get all step types from registry
                    registry = get_registry()
                    step_types = []
                    for step_name in registry.list_step_types():
                        # Get engines that support this step
                        from quantumvitas.workflow.generalized_steps import get_engine_families_for_step
                        engines = get_engine_families_for_step(step_name)
                        step_types.append({
                            "name": step_name,
                            "engines": engines,
                        })
                    return step_types
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def validate_installation(self, engine_name: str) -> dict:
            """
            Validate engine installation.
            
            Args:
                engine_name: Engine name (e.g., "qe", "vasp", "orca")
                
            Returns:
                Validation result dict with schema:
                - engine_name: str
                - ok: bool
                - details: dict (always present; may be empty)
                - version: str | None (optional)
                - binary: str | None (optional)
                - message: str | None (optional)
                - warnings: list[str] | None (optional)
                
            Raises:
                ValidationError: If engine_name is unknown (invalid input)
                APIError: For other errors
            """
            try:
                from quantumvitas.api.errors import ValidationError
                from quantumvitas.core.driver_registry import DriverRegistry
                from quantumvitas.core.driver_exceptions import UnknownEngineError
                
                # Get driver from registry (canonical source)
                try:
                    driver = DriverRegistry.get_driver(engine_name)
                except UnknownEngineError:
                    # Unknown engine is a validation error (invalid input)
                    raise ValidationError(
                        f"Unknown engine: {engine_name}",
                        code="VALIDATION_FAILED",
                        context={"engine_name": engine_name}
                    )
                
                # Initialize result with required fields
                result = {
                    "engine_name": engine_name,
                    "ok": False,
                    "details": {},
                }
                
                # Engine-specific validation hooks
                warnings = []
                
                if engine_name == "qe":
                    # QE validation: check if binary directory can be resolved
                    try:
                        from quantumvitas.drivers.qe.engine.qe_resolver import resolve_qe_bin_dir
                        from pathlib import Path
                        
                        bin_dir = resolve_qe_bin_dir()
                        result["ok"] = True
                        result["binary"] = str(bin_dir)
                        result["details"]["bin_dir"] = str(bin_dir)
                        result["details"]["mode"] = "external"  # or "internal" - simplified
                        
                        # Try to get version if available
                        try:
                            from quantumvitas.drivers.qe.engine.qe_diagnostics import diagnose_qe_resolution
                            report = diagnose_qe_resolution()
                            if report.version:
                                result["version"] = report.version
                        except Exception:
                            pass
                            
                    except RuntimeError as e:
                        # QE not found or invalid
                        result["ok"] = False
                        result["message"] = str(e)
                        result["details"]["error"] = str(e)
                    except Exception as e:
                        # Other errors during validation
                        result["ok"] = False
                        result["message"] = f"Validation error: {e}"
                        result["details"]["error"] = str(e)
                        warnings.append(f"Unexpected error during QE validation: {e}")
                
                elif engine_name == "orca":
                    # ORCA validation: check if binary can be found
                    try:
                        from quantumvitas.core.engines.orca_resolver import resolve_orca_bin, get_orca_version
                        from pathlib import Path
                        
                        orca_bin = resolve_orca_bin()
                        result["ok"] = True
                        result["binary"] = str(orca_bin)
                        result["details"]["binary"] = str(orca_bin)
                        
                        # Try to get version
                        version = get_orca_version(orca_bin)
                        if version:
                            result["version"] = version
                    except RuntimeError as e:
                        # ORCA not found
                        result["ok"] = False
                        result["message"] = str(e)
                        result["details"]["error"] = str(e)
                    except Exception as e:
                        result["ok"] = False
                        result["message"] = f"Validation error: {e}"
                        result["details"]["error"] = str(e)
                
                elif engine_name in ["pyscf", "cp2k", "lammps", "vasp"]:
                    # For engines without specific validation hooks, return ok=True
                    # with note that validation is not implemented
                    result["ok"] = True
                    result["details"]["note"] = "Engine is registered; validation hook not implemented"
                    result["message"] = "Engine registered successfully"
                
                else:
                    # Unknown engine (shouldn't happen if DriverRegistry is correct)
                    # But if it does, return ok=True with note
                    result["ok"] = True
                    result["details"]["note"] = "Engine is registered; no validation hook available"
                    result["message"] = "Engine registered successfully"
                
                # Add warnings if any
                if warnings:
                    result["warnings"] = warnings
                
                return result
                
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
    
    @property
    def engine(self) -> Engine:
        """Access engine capabilities."""
        return QVService.Engine(self)
    
    # -------------------------------------------------------------------------
    # Static methods (backwards compatibility)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def init_project(
        target_dir: Path | str,
        name: str | None = None,
        template: str | None = None,
    ) -> Path:
        """
        Initialize a new QuantumVITAS project.
        
        This is a backwards-compatibility wrapper for the legacy QVService.init_project().
        It creates a new project directory with project.qv.yml and standard subdirectories.
        
        Args:
            target_dir: Directory to create the project in
            name: Project name (defaults to directory name)
            template: Optional template name (deprecated, not used)
            
        Returns:
            Path to project root
            
        Raises:
            ValueError: If target_dir is inside an existing project
            APIError: If project creation fails
        """
        try:
            from quantumvitas.core.context import detect_enclosing_project
            from quantumvitas.core.project_utils import save_project_config
            from quantumvitas.core.resources import generate_resource_id, slugify
            
            target_dir = Path(target_dir).resolve()
            
            # Check if target_dir is inside an existing project
            enclosing_project = detect_enclosing_project(target_dir)
            if enclosing_project:
                raise ValueError(
                    f"Cannot create a new project inside an existing QuantumVITAS project. "
                    f"The selected folder is inside a project at: {enclosing_project}. "
                    f"Please choose a parent folder above your current project directory."
                )
            
            target_dir.mkdir(parents=True, exist_ok=True)
            
            project_name = name or target_dir.name
            project_slug = slugify(project_name)
            project_id = generate_resource_id()
            
            config = {
                "project": {
                    "name": project_name,
                    "meta": {
                        "id": project_id,
                        "name": project_name,
                        "slug": project_slug,
                        "path": ".",
                        "kind": "project",
                    },
                },
                "structures": [],
                "calculations": [],
            }
            
            save_project_config(target_dir, config)
            
            # Create standard directories
            (target_dir / "structures").mkdir(exist_ok=True)
            (target_dir / "calculations").mkdir(exist_ok=True)
            (target_dir / "pseudo").mkdir(exist_ok=True)
            (target_dir / "trash").mkdir(exist_ok=True)
            
            return target_dir
            
        except Exception as e:
            if isinstance(e, (ValueError, APIError)):
                raise
            raise map_kernel_exception(e)
    
    @staticmethod
    def get_settings() -> dict[str, Any]:
        """
        Get global QMatSuite settings.
        
        This is a backwards-compatibility wrapper for the legacy QVService.get_settings().
        Returns global settings from .qmatsuite/config/settings.json with safe defaults.
        
        Returns:
            Dict with settings:
            - version: int
            - qe: dict with "bin_dir" (str | None)
            - debug_resolution: bool
            - max_concurrent_calcs: int
            - analysis_cache_enabled: bool
        """
        try:
            from quantumvitas.core.settings import load_settings
            
            settings = load_settings()
            return {
                "version": settings.version,
                "qe": {
                    "bin_dir": settings.qe.bin_dir,
                },
                "debug_resolution": settings.debug_resolution,
                "max_concurrent_calcs": settings.max_concurrent_calcs,
                "analysis_cache_enabled": settings.analysis_cache_enabled,
            }
        except Exception as e:
            if isinstance(e, APIError):
                raise
            # If loading fails, return safe defaults (matches load_settings behavior)
            # This ensures the daemon can still start even if settings file is corrupted
            return {
                "version": 1,
                "qe": {
                    "bin_dir": None,
                },
                "debug_resolution": False,
                "max_concurrent_calcs": 2,
                "analysis_cache_enabled": True,
            }
    
    @staticmethod
    def get_workflow_service() -> Any:
        """
        Get workflow service instance.
        
        Returns:
            WorkflowService instance
        """
        from quantumvitas.workflow.templates import get_workflow_service as _get_workflow_service
        return _get_workflow_service()
    
    @staticmethod
    def get_project_summary(project_root: Path | str) -> dict[str, Any]:
        """
        Get a high-level summary of a project.
        
        This is a backwards-compatibility wrapper for the legacy QVService.get_project_summary().
        
        Args:
            project_root: Project root path
            
        Returns:
            Dict with project name, id, structure count, calculation count, etc.
        """
        try:
            from quantumvitas.core.project_utils import load_project_config
            from quantumvitas.core.resolution import list_structures, list_calculations
            
            project_root = Path(project_root).resolve()
            config = load_project_config(project_root)
            
            project_info = config.get("project", {})
            meta = project_info.get("meta", {})
            structures = config.get("structures", [])
            calculations = config.get("calculations", [])
            
            # Use registry to resolve structure/calculation names (ID-only model)
            structure_names = []
            try:
                resolved_structures = list_structures(project_root)
                structure_names = [res.meta.name for res in resolved_structures]
            except Exception:
                # Fallback: try to get names from structure entries if they have meta
                structure_names = [
                    s.get("meta", {}).get("name") or s.get("name", "?")
                    for s in structures
                ]
            
            calculation_names = []
            try:
                resolved_calculations = list_calculations(project_root)
                calculation_names = [res.meta.name for res in resolved_calculations]
            except Exception:
                # Fallback: try to get names from calculation entries if they have meta
                calculation_names = [
                    w.get("meta", {}).get("name") or w.get("name", "?")
                    for w in calculations
                ]
            
            return {
                "id": meta.get("id"),
                "name": project_info.get("name") or meta.get("name") or project_root.name,
                "slug": meta.get("slug"),
                "path": str(project_root),
                "n_structures": len(structures),
                "n_calculations": len(calculations),
                "structure_names": structure_names,
                "calculation_names": calculation_names,
            }
        except Exception as e:
            if isinstance(e, APIError):
                raise
            raise map_kernel_exception(e)
    
    @staticmethod
    def list_structures_data(project_root: Path | str) -> list[dict[str, Any]]:
        """
        List all structures as JSON-serializable dicts.
        
        This is a backwards-compatibility wrapper for the legacy QVService.list_structures_data().
        
        Args:
            project_root: Project root path
            
        Returns:
            List of dicts, each with id, name, slug, path, and structure metadata
        """
        try:
            from quantumvitas.core.resolution import list_structures
            from quantumvitas.io.structure_io import read_structure
            
            project_root = Path(project_root).resolve()
            resolved_list = list_structures(project_root)
            
            result = []
            for res in resolved_list:
                entry = {
                    "id": res.meta.id,
                    "name": res.meta.name,
                    "slug": res.meta.slug,
                    "path": res.meta.path,
                    "absolute_path": str(res.absolute_path),
                }
                
                # Try to add structure metadata (formula, n_atoms, etc.)
                try:
                    if res.absolute_path.exists():
                        struct = read_structure(res.absolute_path)
                        entry["formula"] = struct.composition.reduced_formula
                        entry["n_atoms"] = len(struct)
                        entry["n_species"] = len(struct.composition.elements)
                        entry["lattice_type"] = struct.lattice.pbc.__class__.__name__ if hasattr(struct.lattice, 'pbc') else "3D"
                        # Lattice parameters
                        latt = struct.lattice
                        entry["lattice_params"] = {
                            "a": float(latt.a),
                            "b": float(latt.b),
                            "c": float(latt.c),
                            "alpha": float(latt.alpha),
                            "beta": float(latt.beta),
                            "gamma": float(latt.gamma),
                            "volume": float(latt.volume),
                        }
                except Exception:
                    pass  # Structure metadata is optional
                
                result.append(entry)
            
            return result
        except Exception as e:
            if isinstance(e, APIError):
                raise
            raise map_kernel_exception(e)
    
    @staticmethod
    def list_calculations_data(project_root: Path | str) -> list[dict[str, Any]]:
        """
        List all calculations as JSON-serializable dicts.
        
        This is a backwards-compatibility wrapper for the legacy QVService.list_calculations_data().
        Uses Project.open() and Calculation.from_yaml() to ensure legacy calculations
        are automatically migrated to the ID-only model.
        
        Args:
            project_root: Project root path
            
        Returns:
            List of dicts, each with calculation metadata and step info
        """
        try:
            from quantumvitas.core.resolution import list_calculations
            from quantumvitas.project.model import Project
            from quantumvitas.calculation.calculation import Calculation
            
            project_root = Path(project_root).resolve()
            
            # Use list_calculations to get all calculations (more reliable than Project.open())
            resolved_list = list_calculations(project_root)
            
            # Try to open project for additional metadata (optional)
            project = None
            try:
                project = Project.open(project_root)
            except Exception:
                pass  # Project.open() is optional for metadata
            
            result = []
            for res in resolved_list:
                entry = {
                    "id": res.meta.id,
                    "name": res.meta.name,
                    "slug": res.meta.slug,
                    "path": res.meta.path,
                    "absolute_path": str(res.absolute_path),
                    "mode": "normal",  # Default mode (will be overridden if calculation loads successfully)
                    "n_steps": 0,  # Default (will be overridden if calculation loads successfully)
                    "steps": [],  # Default (will be overridden if calculation loads successfully)
                }
                
                # Try to load calculation with migration support (inspection mode)
                # This uses Calculation.from_yaml() which handles legacy step entries
                try:
                    if res.absolute_path.exists() and project is not None:
                        calculation = Calculation.from_yaml(res.absolute_path, project, materialize_steps=False)
                        
                        # Extract structure info
                        if calculation.structure:
                            entry["structure"] = calculation.structure.meta.name if hasattr(calculation.structure, 'meta') else str(calculation.structure)
                            entry["structure_id"] = calculation.structure.meta.id if hasattr(calculation.structure, 'meta') else None
                        else:
                            entry["structure"] = None
                            entry["structure_id"] = None
                        
                        # Ensure mode is always present (default to "normal" if not set)
                        entry["mode"] = calculation.mode.value if hasattr(calculation.mode, 'value') else (str(calculation.mode) if calculation.mode else "normal")
                        entry["n_steps"] = len(calculation.steps)
                        
                        # Extract step info from actual Step objects (which have ULID meta.id)
                        entry["steps"] = [
                            {
                                "step_id": step.meta.id,  # ULID (canonical reference)
                                "id": step.meta.id,  # Also include as 'id' for backwards compatibility in API response
                                "type": step.step_type,
                            }
                            for step in calculation.steps
                        ]
                except Exception:
                    pass  # Calculation metadata is optional
                
                result.append(entry)
            
            return result
        except Exception as e:
            if isinstance(e, APIError):
                raise
            raise map_kernel_exception(e)
    
    @staticmethod
    def init_calculation(
        project_root: Path | str,
        name: str,
        structure_selector: str | None = None,
        template: str | None = None,
        *,
        index: Any = None,
        config: dict | None = None,
    ) -> Any:
        """
        Create a new calculation.
        
        This is a backwards-compatibility wrapper for the legacy QVService.init_calculation().
        
        Args:
            project_root: Project root path
            name: Calculation name
            structure_selector: Optional structure selector for calculation
            template: Optional template name
            index: Optional resource index (for performance)
            config: Optional project config (for performance)
            
        Returns:
            ResolvedResource for the new calculation
        """
        try:
            from quantumvitas.core.project_utils import load_project_config, save_project_config
            from quantumvitas.core.resources import generate_resource_id, slugify
            from quantumvitas.core.resolution import resolve_structure, build_resource_index
            import yaml
            
            project_root = Path(project_root).resolve()
            
            # Load project config
            if config is None:
                config = load_project_config(project_root)
            
            calculations = config.setdefault("calculations", [])
            
            # Collect existing slugs
            existing_slugs = {calc.get("meta", {}).get("slug") or calc.get("slug") for calc in calculations if calc.get("meta", {}).get("slug") or calc.get("slug")}
            
            # Generate unique name and slug
            base_slug = slugify(name)
            final_slug = base_slug
            counter = 1
            while final_slug in existing_slugs:
                final_slug = f"{base_slug}-{counter}"
                counter += 1
            
            final_name = name
            
            # Generate calculation ID
            calc_id = generate_resource_id()
            
            # Create calculation directory
            calc_dir = project_root / "calculations" / final_slug
            calc_dir.mkdir(parents=True, exist_ok=True)
            
            # Create calculation.yaml
            calc_yaml = calc_dir / "calculation.yaml"
            calc_data = {
                "meta": {
                    "id": calc_id,
                    "name": final_name,
                    "slug": final_slug,
                    "path": f"calculations/{final_slug}",
                    "kind": "calculation",
                },
                "steps": [],
            }
            
            # Add structure reference if provided
            if structure_selector:
                if index is None:
                    index = build_resource_index(project_root)
                struct_resolved = resolve_structure(project_root, structure_selector, index=index)
                calc_data["structure_id"] = struct_resolved.meta.id
            
            # Write calculation.yaml
            with open(calc_yaml, "w", encoding="utf-8") as f:
                yaml.dump(calc_data, f, default_flow_style=False, sort_keys=False)
            
            # Add to project config
            calc_entry = {
                "meta": {
                    "id": calc_id,
                    "name": final_name,
                    "slug": final_slug,
                    "path": f"calculations/{final_slug}",
                    "kind": "calculation",
                }
            }
            calculations.append(calc_entry)
            save_project_config(project_root, config)
            
            # Return ResolvedResource
            from quantumvitas.core.resolution import ResolvedResource
            from quantumvitas.core.resources import ResourceMeta
            
            meta = ResourceMeta(
                id=calc_id,
                name=final_name,
                slug=final_slug,
                path=f"calculations/{final_slug}",
                kind="calculation",
            )
            
            # absolute_path must point to the calculation directory, not the file
            return ResolvedResource(
                meta=meta,
                entry=calc_entry,
                absolute_path=calc_dir,
            )
        except Exception as e:
            if isinstance(e, APIError):
                raise
            raise map_kernel_exception(e)
    
    @staticmethod
    def run_calculation(
        project_root: Path | str,
        calculation_selector: str,
        strict: bool = False,
        verbose: bool = False,
        *,
        index: Any = None,
        config: dict | None = None,
        run_id: str | None = None,
        run_mode: str = "incremental",
    ) -> dict[str, Any]:
        """
        Run all steps in a calculation.
        
        This is a backwards-compatibility wrapper for the legacy QVService.run_calculation().
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            strict: If True, fail on first error
            verbose: If True, print detailed output
            index: Optional resource index (for performance)
            config: Optional project config (for performance)
            run_id: External run ID to use (e.g., job_id from JobManager)
            run_mode: Run mode ("incremental" or "full", default "incremental")
            
        Returns:
            Dict with run results
        """
        try:
            from quantumvitas._api_legacy import QVService as LegacyService
            
            project_root = Path(project_root).resolve()
            
            # Use legacy implementation
            return LegacyService.run_calculation(
                project_root=project_root,
                calculation_selector=calculation_selector,
                strict=strict,
                verbose=verbose,
                index=index,
                config=config,
                run_id=run_id,
                run_mode=run_mode,
            )
        except Exception as e:
            if isinstance(e, APIError):
                raise
            raise map_kernel_exception(e)
    
    @staticmethod
    def import_structure(
        project_root: Path | str,
        source: Path | str,
        name: str | None = None,
        format: str = "auto",
        *,
        index: Any = None,
        dedup_by_fingerprint: bool = False,
    ) -> Any:
        """
        Import a structure file into the project.
        
        This is a backwards-compatibility wrapper for the legacy QVService.import_structure().
        
        Args:
            project_root: Project root path
            source: Path to source file (CIF, QE input, JSON, etc.)
            name: Name for the structure (defaults to filename stem)
            format: File format hint
            index: Optional resource index for registry update
            dedup_by_fingerprint: If True, reuse existing structure with same content fingerprint
        
        Returns:
            ResolvedResource for the imported structure
        """
        try:
            from quantumvitas._api_legacy import QVService as LegacyService
            
            project_root = Path(project_root).resolve()
            source = Path(source).resolve()
            
            # Use legacy implementation
            return LegacyService.import_structure(
                project_root=project_root,
                source=source,
                name=name,
                format=format,
                index=index,
                dedup_by_fingerprint=dedup_by_fingerprint,
            )
        except Exception as e:
            if isinstance(e, APIError):
                raise
            raise map_kernel_exception(e)
    
    @staticmethod
    def configure_species_map(
        project_root: Path | str,
        calculation: str,
        *,
        from_qe_input: Path | str | None = None,
        set_entries: list[tuple[str, float, str]] | None = None,
        merge: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """
        Configure calculation-level species_map.
        
        This is a backwards-compatibility wrapper for the legacy QVService.configure_species_map().
        Uses the shared API from quantumvitas.calculation.species_config.
        
        Args:
            project_root: Project root directory
            calculation: Calculation selector (id/name/slug/path)
            from_qe_input: Optional QE input file to extract ATOMIC_SPECIES from
            set_entries: Optional list of explicit (element, mass, pseudopot) triples
            merge: If True (default), merge with existing species_map. If False, replace.
            
        Returns:
            Updated species_map dictionary (element -> {mass, pseudopot, ...})
        """
        try:
            from quantumvitas.calculation.species_config import configure_species_map as _configure_species_map
            
            project_root = Path(project_root).resolve()
            if from_qe_input:
                from_qe_input = Path(from_qe_input).resolve()
            
            # Use shared API
            return _configure_species_map(
                project_root=project_root,
                calculation=calculation,
                from_qe_input=from_qe_input,
                set_entries=set_entries,
                merge=merge,
            )
        except Exception as e:
            if isinstance(e, APIError):
                raise
            # Map ValueError to ValidationError for API consistency
            if isinstance(e, ValueError):
                from quantumvitas.api.errors import ValidationError
                raise ValidationError(
                    str(e),
                    code="VALIDATION_FAILED",
                    context={"calculation": calculation}
                )
            raise map_kernel_exception(e)
    
    @staticmethod
    def extract_calculation_selector_from_entry(entry: dict[str, Any]) -> str | None:
        """
        Extract a calculation selector from a project.qv.yml entry.
        
        This is a backwards-compatibility wrapper for the legacy QVService.extract_calculation_selector_from_entry().
        
        Args:
            entry: Calculation entry dict from project.qv.yml
            
        Returns:
            Selector string (ULID, slug, or name) or None if no valid selector found
        """
        from quantumvitas.api.utils import extract_calculation_selector_from_entry as _extract
        return _extract(entry)
    
    @staticmethod
    def get_default_step_params(step_type: str) -> dict[str, Any]:
        """
        Get default parameters for a step type.
        
        This is a backwards-compatibility wrapper for the legacy QVService.get_default_step_params().
        
        Args:
            step_type: Step type (e.g., "qe_scf", "qe_nscf", "scf", "nscf")
            
        Returns:
            Dict with "parameters", "cards", and "species_overrides" keys.
            Returns empty dicts if step_type is not recognized.
        """
        from quantumvitas.calculation.step_defaults import get_default_step_params as _get_default_step_params
        return _get_default_step_params(step_type)
