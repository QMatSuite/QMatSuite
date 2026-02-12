"""
Calculation representation (loaded from calculation.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from quantumvitas.core.public import ResourceMeta, ensure_relative_path
from quantumvitas.project.model import Project, StructureRef
from .types import StepMode
from .step import Step
from .io import CalculationIO
from .structure_steps import StructureStepSpec, materialize_step_spec
from .naming import CalculationFileNaming


@dataclass(slots=True)
class Calculation:
    ulid: str  # CANONICAL: renamed from id
    project: Project
    dir: Path
    mode: StepMode
    steps: List[Step]
    io: CalculationIO
    structure: Optional[StructureRef] = None
    working_dir: Path = field(default_factory=Path)
    _structure_ulid: Optional[str] = field(default=None, init=False, repr=False)  # Cached structure_ulid from model
    _species_map: Optional[Dict[str, Dict[str, Any]]] = field(default=None, init=False, repr=False)  # Cached species_map
    _potential_map: Optional[Dict[str, Dict[str, Any]]] = field(default=None, init=False, repr=False)  # Cached potential_map (LAMMPS)
    _engine_family: Optional[str] = field(default=None, init=False, repr=False)  # Cached engine_family from model

    @property
    def raw_dir(self) -> Path:
        return self.working_dir

    @property
    def reference_dir(self) -> Path:
        return self.io.reference_dir

    @property
    def results_dir(self) -> Path:
        return self.io.results_dir

    @property
    def structure_ulid(self) -> Optional[str]:
        """
        Get structure_ulid from the calculation.
        
        DAG + ID-only model invariants:
        - Calculation holds structure_ulid (ULID) as the canonical structure reference.
        - Steps do NOT persist structure_ulid in their YAML (they inherit from calculation).
        - All cross-resource relationships go through IDs + registry.
        
        This property reads from the underlying calculation.yaml model.
        """
        # If cached, return it
        if self._structure_ulid is not None:
            return self._structure_ulid
        
        # Otherwise, load from calculation.yaml
        calculation_yaml = self.dir / "calculation.yaml"
        if calculation_yaml.exists():
            try:
                from quantumvitas.core.public import load_calculation
                wf_model = load_calculation(calculation_yaml, self.project.root)
                self._structure_ulid = wf_model.structure_ulid
                return self._structure_ulid
            except Exception:
                pass
        
        # Fallback: get from structure ref if available
        if self.structure:
            return self.structure.meta.ulid
        
        return None

    @property
    def species_map(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Get species_map from the calculation.
        
        Species_map is the authoritative source for pseudopotential mappings:
        - element_symbol -> {pseudopot: str, mass: float}
        
        This property reads from the underlying calculation.yaml model.
        Falls back to None if not set (for backwards compatibility with old projects).
        """
        # If cached, return it
        if self._species_map is not None:
            return self._species_map
        
        # Otherwise, load from calculation.yaml
        calculation_yaml = self.dir / "calculation.yaml"
        if calculation_yaml.exists():
            try:
                from quantumvitas.core.public import load_calculation
                wf_model = load_calculation(calculation_yaml, self.project.root)
                self._species_map = wf_model.species_map
                return self._species_map
            except Exception:
                pass
        
        return None

    @property
    def potential_map(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Get potential_map from the calculation.
        
        LAMMPS-specific: Maps potential key to definition.
        - potential_key -> {style: str, file: str, elements: list, sha256: str}
        
        This property reads from the underlying calculation.yaml model.
        Falls back to None if not set (for backwards compatibility with non-LAMMPS calcs).
        """
        # If cached, return it
        if self._potential_map is not None:
            return self._potential_map
        
        # Otherwise, load from calculation.yaml
        calculation_yaml = self.dir / "calculation.yaml"
        if calculation_yaml.exists():
            try:
                from quantumvitas.core.public import load_calculation
                wf_model = load_calculation(calculation_yaml, self.project.root)
                self._potential_map = getattr(wf_model, "potential_map", None)
                return self._potential_map
            except Exception:
                pass
        
        return None

    @property
    def engine_family(self) -> Optional[str]:
        """
        Get engine_family from the calculation.
        
        Engine_family determines which engine is used for execution (e.g., "qe", "pyscf").
        
        This property reads from the underlying calculation.yaml model.
        Falls back to None if not set (for backwards compatibility with old projects).
        """
        # If cached, return it
        if self._engine_family is not None:
            return self._engine_family
        
        # Otherwise, load from calculation.yaml
        calculation_yaml = self.dir / "calculation.yaml"
        if calculation_yaml.exists():
            try:
                from quantumvitas.core.public import load_calculation
                wf_model = load_calculation(calculation_yaml, self.project.root)
                self._engine_family = wf_model.engine_family
                return self._engine_family
            except Exception:
                pass
        
        return None

    @classmethod
    def from_yaml(
        cls, 
        calculation_dir: Path, 
        project: Project,
        materialize_steps: bool = True,
    ) -> "Calculation":
        """
        Load calculation from calculation.yaml.
        
        DAG + ID-only model:
        - Calculation.yaml contains structure_ulid (ULID) pointing to structure resource.
        - Steps are referenced by step_ulid (ULID) in calculation.steps entries.
        - Step YAML files do NOT contain structure_ulid or parent_calculation_id.
        - Structure is resolved via calculation.structure_ulid at execution time.
        """
        calculation_yaml = calculation_dir / "calculation.yaml"
        if not calculation_yaml.exists():
            raise FileNotFoundError(f"calculation.yaml not found: {calculation_yaml}")

        from quantumvitas.core.public import CalcDoc
        data = CalcDoc.load(calculation_yaml).to_dict()
        calculation_id = data.get("ulid") or data.get("meta", {}).get("ulid") or calculation_dir.name
        mode = StepMode(data.get("mode", StepMode.NORMAL.value))

        calculation_meta = data.get("calculation", {})
        
        # Detect legacy structure selector (NOT SUPPORTED)
        from quantumvitas.core.public import LegacyProjectError
        
        structure_ulid = calculation_meta.get("structure_ulid") or data.get("structure_ulid")
        legacy_structure = calculation_meta.get("structure") or data.get("structure")
        
        # If structure_ulid is missing but legacy structure selector is present, raise error
        if not structure_ulid and legacy_structure:
            error_msg = (
                f"Legacy calculation detected at {calculation_dir}: has 'structure' selector but no 'structure_ulid' ULID. "
                f"Please run the migration script to upgrade this calculation."
            )
            raise LegacyProjectError(project.root, error_msg)
        
        structure_ref: Optional[StructureRef] = None
        if structure_ulid:
            try:
                # Try to resolve structure by ID (can be ULID, slug, or name)
                structure_ref = project.get_structure(structure_ulid)
            except Exception:
                # Try to resolve by ID if direct lookup fails
                for struct_ref in project.structures.values():
                    if struct_ref.meta.ulid == structure_ulid:
                        structure_ref = struct_ref
                        break

        raw_subdir = calculation_meta.get("working_dir", "raw")
        working_dir = (calculation_dir / raw_subdir).resolve()

        # Build steps (legacy calculations will raise LegacyProjectError)
        steps: List[Step] = []
        
        # Track step types to generate unique filenames (only number if duplicates exist)
        # Count is incremented inside _build_step_from_spec when generating filename
        step_type_counts: Dict[str, int] = {}  # step_type_gen -> count of steps with this type seen so far
        
        # Log materialization entry
        if materialize_steps:
            import logging
            logger = logging.getLogger(__name__)
            step_ulids = [step_data.get("step_ulid", "unknown") for step_data in data.get("steps", [])]
            logger.info(
                f"[MATERIALIZE_STEPS] ENTRY "
                f"calculation_dir={calculation_dir} "
                f"raw_dir={working_dir} "
                f"steps_to_materialize={step_ulids} "
                f"n_steps={len(step_ulids)}"
            )
        
        for step_data in data.get("steps", []):
            if materialize_steps:
                # Execution mode: fully materialize steps (calls materialize_step_spec, requires pseudos)
                # Pass step_type_counts to track duplicates (count is incremented inside _build_step_from_spec)
                step, _ = _build_step(
                    step_data, calculation_dir, working_dir, project, step_type_counts=step_type_counts
                )
                steps.append(step)
            else:
                # Inspection mode: create lightweight step objects without materialization
                # This avoids calling materialize_step_spec and ensure_qe_pseudos
                step, _ = _build_step_inspection(step_data, calculation_dir, working_dir, project)
                steps.append(step)

        # Create calculation instance
        calculation = cls(
            ulid=calculation_id,  # CANONICAL: renamed from id
            project=project,
            dir=calculation_dir,
            mode=mode,
            steps=steps,
            io=CalculationIO(calculation_dir, raw_subdir=raw_subdir),
            structure=structure_ref,
            working_dir=working_dir,
        )
        # Cache structure_ulid for quick access
        calculation._structure_ulid = structure_ulid
        
        # Phase 3A: Ensure calculation identity is set (best-effort recovery)
        from quantumvitas.core.public import ensure_calculation_identity
        ensure_calculation_identity(calculation_dir, project_root=project.root)
        
        # No auto-migration - legacy calculations raise LegacyProjectError during step building
        return calculation


def _build_step(
    step_data: dict,
    calculation_dir: Path,
    working_dir: Path,
    project: Project,
    step_type_counts: Optional[Dict[str, int]] = None,
) -> tuple[Step, bool]:
    """
    Build a Step from step_data in calculation.yaml.
    
    Uses step_ulid (ULID) to resolve step file via ResourceIndex.
    step_file is no longer stored in calculation.yaml - only step_ulid.
    
    Returns:
        Tuple of (Step, migrated_flag) where migrated_flag is True if legacy
        fallback path was used (indicating the calculation needs migration).
    """
    from quantumvitas.core.public import require_step, ResourceNotFoundError
    from quantumvitas.calculation.structure_steps import StructureStepSpec
    from quantumvitas.core.public import make_structure_selector_resolver
    from quantumvitas.core.public import load_project_config
    
    # Require step_ulid (ULID) - no legacy fallback
    from quantumvitas.core.public import LegacyProjectError
    
    step_ulid = step_data.get("step_ulid") or step_data.get("step_ulid")
    if not step_ulid:
        # Check for legacy fields
        has_legacy_id = "id" in step_data
        has_step_file = "step_file" in step_data
        if has_legacy_id or has_step_file:
            error_msg = (
                f"Legacy calculation step entry detected in {calculation_dir}: "
                f"missing 'step_ulid' ULID. "
            )
            if has_step_file:
                error_msg += "Field 'step_file' is not supported (use step_ulid ULID instead). "
            if has_legacy_id:
                error_msg += "Legacy 'id' field detected (use step_ulid ULID instead). "
            error_msg += "Please run the migration script to upgrade this calculation."
            raise LegacyProjectError(project.root, error_msg)
        else:
            raise ValueError(f"Step entry missing 'step_ulid' ULID: {step_data}")
    
    # Check if step_ulid is a valid ULID (26 chars starting with "01")
    is_ulid = len(step_ulid) == 26 and step_ulid.startswith("01")
    if not is_ulid:
        error_msg = (
            f"Legacy calculation step entry detected in {calculation_dir}: "
            f"step_ulid '{step_ulid}' is not a ULID (must be 26 chars starting with '01'). "
            f"Please run the migration script to upgrade this calculation."
        )
        raise LegacyProjectError(project.root, error_msg)
    
    # Check for legacy step_file field
    if "step_file" in step_data:
        error_msg = (
            f"Legacy calculation step entry detected in {calculation_dir}: "
            f"field 'step_file' is not supported (use step_ulid ULID instead). "
            f"Please run the migration script to upgrade this calculation."
        )
        raise LegacyProjectError(project.root, error_msg)
    
    # Resolve step via registry using ULID (needed to get step_type from step file)
    try:
        # Try to get calculation from project by matching directory
        calculation_ref = None
        for wf_ref in project.calculations.values():
            if wf_ref.absolute_path == calculation_dir:
                calculation_ref = wf_ref
                break

        if calculation_ref:
            # Use ULID for reliable resolution (slugs can collide with structures)
            calculation_selector = calculation_ref.meta.ulid or calculation_ref.meta.slug or calculation_ref.meta.name
        else:
            calculation_selector = calculation_dir.name

        step_resolved = require_step(project.root, calculation_selector, step_ulid)
        step_file_path = step_resolved.absolute_path
    except ResourceNotFoundError as e:
        error_msg = (
            f"Step '{step_ulid}' not found in registry. "
            f"This may indicate a legacy calculation that needs migration. "
            f"Please run the migration script to upgrade this calculation."
        )
        raise LegacyProjectError(project.root, error_msg) from e
    
    # Load step file to extract step_type if not in step_data
    step_file_data = {}
    if step_file_path.exists():
        try:
            from quantumvitas.core.public import StepDoc
            step_file_data = StepDoc.load(step_file_path).to_dict()
        except Exception:
            pass

    # Engine must be specified or inferred from step type
    engine_name = step_data.get("engine")
    if engine_name is None:
        # Try to infer from step type (from step_data or step file)
        # Check step_type_spec first (canonical), then type field
        step_type_spec = (step_data.get("step_type_spec") or step_file_data.get("step_type_spec") or
                     step_data.get("type") or step_file_data.get("type"))
        if step_type_spec:
            # First try workflow registry lookup (registry.get expects GEN)
            from quantumvitas.workflow.registry import get_registry
            from quantumvitas.workflow.step_type_convert import gen_from
            registry = get_registry()
            step_type_gen = gen_from(step_type_spec)  # Convert SPEC to GEN
            spec = registry.get(step_type_gen)
            if spec:
                engine_name = spec.engine

            # If registry lookup fails, try DriverRegistry materialization
            if engine_name is None:
                import quantumvitas.drivers
                from quantumvitas.core.public import DriverRegistry

                # Check if step_type_spec is already a machine type
                if DriverRegistry.is_step_type_registered(step_type_spec):
                    engine_name = DriverRegistry.get_engine_for_step_type(step_type_spec)
                else:
                    # Try materializing gen types (e.g., "scf" -> "qe_scf")
                    # Try all registered engine families
                    # step_type_gen already computed above
                    gen_type = step_type_gen
                    for engine_family in DriverRegistry.get_all_engines():
                        try:
                            materialized = DriverRegistry.materialize_step_type(engine_family, gen_type)
                            if materialized:
                                engine_name = engine_family
                                break
                        except Exception:
                            continue
        
        if engine_name is None:
            raise ValueError(
                f"Cannot determine engine for step '{step_ulid}'. "
                f"Specify 'engine' field in calculation.yaml or use a known step type."
            )
    
    input_path_value = step_data.get("input") or step_data.get("file")
    input_path: Optional[Path] = None
    existing_input_file: Optional[Path] = None
    if input_path_value:
        input_path = Path(input_path_value)
        if not input_path.is_absolute():
            parts = input_path.parts
            if parts and parts[0] == working_dir.name:
                if len(parts) == 1:
                    raise ValueError(
                        f"Step '{step_ulid}' input path must point to a file inside '{working_dir.name}'"
                    )
                input_path = Path(*parts[1:])
        
        # Resolve the full path to the existing input file
        if input_path:
            existing_input_file = (working_dir / input_path).resolve()
            if not existing_input_file.exists():
                # Try relative to calculation_dir instead
                existing_input_file = (calculation_dir / input_path).resolve()
                if not existing_input_file.exists():
                    existing_input_file = None

    options = step_data.get("options", step_data.get("params", {})) or {}
    reference_path = _resolve_reference_path(step_data.get("reference"), calculation_dir)

    # CONTRACT I1: Step ULID is the identity of a step resource.
    # Step ULID must NOT change after creation. Use step_resolved.meta (from step.yaml)
    # instead of building metadata from calculation.yaml step_data.
    step_meta = step_resolved.meta
    
    # Assert step_ulid from calculation.yaml matches step_meta.ulid from step.yaml
    # This ensures ULID consistency across calculation.yaml and step.yaml
    if step_meta.ulid != step_ulid:
        raise ValueError(
            f"Step ULID mismatch: calculation.yaml step_ulid='{step_ulid}' "
            f"does not match step.yaml meta.ulid='{step_meta.ulid}'. "
            f"This indicates a corrupted calculation or step file."
        )

    # Production run contract: never use existing_input_file for execution.
    # The input: field in calculation.yaml is import-only (legacy).
    # For production run, we always generate .in from step.yaml (YAML SSOT).
    # See docs/dev/exec-pipeline-ssot-contract.md for details.
    #
    # If existing_input_file is provided (legacy calculation.yaml with input: field),
    # ignore it for production run. This ensures production always uses YAML SSOT clean rewrite.
    step = _build_step_from_spec(
        step_ulid=step_ulid,  # Use ULID from calculation.yaml (must match step_meta.ulid)
        engine_name=engine_name,
        step_file=str(step_file_path.relative_to(calculation_dir)) if step_file_path.is_relative_to(calculation_dir) else step_file_path.name,
        calculation_dir=calculation_dir,
        working_dir=working_dir,
        project=project,
        options=options,
        reference=reference_path,
        step_meta=step_meta,
        existing_input_file=None,  # Ignore existing_input_file in production run (YAML SSOT)
    )
    
    return step, False  # No migration needed (legacy calculations raise errors)


def _build_step_inspection(
    step_data: dict,
    calculation_dir: Path,
    working_dir: Path,
    project: Project,
) -> tuple[Step, bool]:
    """
    Build a lightweight Step for inspection (no materialization).
    
    This function creates Step objects without calling materialize_step_spec
    or ensure_qe_pseudos, making it suitable for inspection/metadata APIs.
    
    Returns:
        Tuple of (Step, migrated_flag) where migrated_flag indicates if legacy
        fallback path was used.
    """
    from quantumvitas.core.public import ResourceMeta, generate_resource_id
    from quantumvitas.core.public import require_step, ResourceNotFoundError
    from quantumvitas.calculation.structure_steps import StructureStepSpec
    from quantumvitas.core.public import make_structure_selector_resolver
    from quantumvitas.core.public import load_project_config
    
    # Prefer step_ulid (ULID) - canonical reference, fall back to legacy step_ulid/id fields
    step_ulid = step_data.get("step_ulid") or step_data.get("step_ulid") or step_data.get("ulid")
    if not step_ulid:
        raise ValueError(f"Step entry missing both 'step_ulid' and 'id': {step_data}")
    
    # Resolve step file early to extract step_type if not in step_data
    step_file_data = {}
    try:
        calculation_ref = None
        for wf_ref in project.calculations.values():
            if wf_ref.absolute_path == calculation_dir:
                calculation_ref = wf_ref
                break
        
        if calculation_ref:
            calculation_selector = calculation_ref.meta.ulid or calculation_ref.meta.slug or calculation_ref.meta.name
        else:
            calculation_selector = calculation_dir.name
        
        step_resolved = require_step(project.root, calculation_selector, step_ulid)
        step_file_path = step_resolved.absolute_path
        
        # Load step file to extract step_type
        if step_file_path.exists():
            try:
                from quantumvitas.core.public import StepDoc
                step_file_data = StepDoc.load(step_file_path).to_dict()
            except Exception:
                pass
    except Exception:
        pass  # Fall through - will try to infer from step_data only
    
    # Engine must be specified or inferred from step type
    engine_name = step_data.get("engine")
    if engine_name is None:
        # Try to infer from step type (from step_data or step file)
        # Check step_type_spec first (canonical), then type field
        step_type_spec = (step_data.get("step_type_spec") or step_file_data.get("step_type_spec") or
                          step_data.get("type") or step_file_data.get("type"))
        if step_type_spec:
            # First try workflow registry lookup (registry.get expects GEN)
            from quantumvitas.workflow.registry import get_registry
            from quantumvitas.workflow.step_type_convert import gen_from
            registry = get_registry()
            step_type_gen = gen_from(step_type_spec)  # Convert SPEC to GEN
            spec = registry.get(step_type_gen)
            if spec:
                engine_name = spec.engine

            # If registry lookup fails, try DriverRegistry materialization
            if engine_name is None:
                import quantumvitas.drivers
                from quantumvitas.core.public import DriverRegistry

                # Check if step_type_spec is already a spec type
                if DriverRegistry.is_step_type_registered(step_type_spec):
                    engine_name = DriverRegistry.get_engine_for_step_type(step_type_spec)
                else:
                    # Try materializing gen types (e.g., "scf" -> "qe_scf")
                    # step_type_gen already computed above
                    gen_type = step_type_gen
                    for engine_family in DriverRegistry.get_all_engines():
                        try:
                            materialized = DriverRegistry.materialize_step_type(engine_family, gen_type)
                            if materialized:
                                engine_name = engine_family
                                break
                        except Exception:
                            continue
        
        if engine_name is None:
            raise ValueError(
                f"Cannot determine engine for step '{step_ulid}'. "
                f"Specify 'engine' field in calculation.yaml or use a known step type."
            )
    migrated = False
    step_meta: Optional[ResourceMeta] = None
    step_type_spec: Optional[str] = None
    input_path: Optional[Path] = None
    new_step_ulid = step_ulid  # Will be updated if legacy path is used
    
    # Check if step_ulid is a ULID (26 chars starting with "01")
    is_ulid = len(step_ulid) == 26 and step_ulid.startswith("01")
    
    # Try ID-first via registry (only if step_ulid is a ULID)
    if is_ulid:
        try:
            # Try to get calculation from project by matching directory
            calculation_ref = None
            for wf_ref in project.calculations.values():
                if wf_ref.absolute_path == calculation_dir:
                    calculation_ref = wf_ref
                    break
            
            if calculation_ref:
                calculation_selector = calculation_ref.meta.ulid or calculation_ref.meta.slug or calculation_ref.meta.name
            else:
                calculation_selector = calculation_dir.name
            
            step_resolved = require_step(project.root, calculation_selector, step_ulid)
            step_file_path = step_resolved.absolute_path
            step_meta = step_resolved.meta
            new_step_ulid = step_meta.ulid  # Use the ULID from registry
            
            # Load step spec just to get metadata (no materialization)
            try:
                config = load_project_config(project.root)
                resolver = make_structure_selector_resolver(project.root, config=config)
            except Exception:
                resolver = None
            
            spec = StructureStepSpec.from_yaml(
                step_file_path,
                resolve_structure_selector=resolver,
            )
            step_type_spec = spec.step_type_spec
        except ResourceNotFoundError:
            # ULID not found in registry - treat as legacy
            is_ulid = False
    
    # Legacy fallback: step_ulid is not a ULID or ULID not found
    if not is_ulid:
        # Legacy fallback: step_ulid might be a name, not a ULID
        migrated = True
        
        # Check for legacy step_file
        legacy_step_file = step_data.get("step_file")
        
        # If legacy_step_file is not specified, try to find step file by name
        if not legacy_step_file:
            candidate = (calculation_dir / "steps" / f"{step_ulid}.step.yaml").resolve()
            if candidate.exists():
                legacy_step_file = str(candidate.relative_to(calculation_dir))
        
        # If we have a legacy_step_file, load the step spec
        if legacy_step_file:
            step_file_path = (calculation_dir / legacy_step_file).resolve()
            if step_file_path.exists():
                try:
                    config = load_project_config(project.root)
                    resolver = make_structure_selector_resolver(project.root, config=config)
                except Exception:
                    resolver = None
                
                spec = StructureStepSpec.from_yaml(
                    step_file_path,
                    resolve_structure_selector=resolver,
                )
                step_meta = spec.meta  # This contains the ULID from the step file
                step_type_spec = spec.step_type_spec
                # Store the real ULID for migration
                new_step_ulid = step_meta.ulid
            else:
                # Create minimal meta if file doesn't exist
                step_meta = ResourceMeta(
                    ulid=generate_resource_id(),
                    name=step_ulid,
                    slug=step_ulid,
                    path=f"calculations/{calculation_dir.name}/steps/{step_ulid}.step.yaml",
                    kind="step",
                )
                step_type_spec= "custom"
        else:
            # Create minimal meta if no file found
            step_meta = ResourceMeta(
                ulid=generate_resource_id(),
                name=step_ulid,
                slug=step_ulid,
                path=f"calculations/{calculation_dir.name}/steps/{step_ulid}.step.yaml",
                kind="step",
            )
            step_type_spec= "custom"
    
    # Handle input path (if specified)
    input_path_value = step_data.get("input") or step_data.get("file")
    if input_path_value:
        input_path = Path(input_path_value)
        if not input_path.is_absolute():
            parts = input_path.parts
            if parts and parts[0] == working_dir.name:
                if len(parts) > 1:
                    input_path = Path(*parts[1:])
            input_path = (working_dir / input_path).resolve() if input_path else None
    
    # Handle reference path (if specified)
    reference_path: Optional[Path] = None
    reference_value = step_data.get("reference")
    if reference_value:
        reference_path = Path(reference_value)
        if not reference_path.is_absolute():
            reference_path = (calculation_dir / reference_path).resolve()
    
    # Create lightweight step (no materialization, no input file generation)
    # Use a dummy input file path if needed (won't be used in inspection mode)
    dummy_input = input_path or (working_dir / f"{step_ulid}.in")
    
    # step_meta should be set from spec above
    if not step_meta:
        # This should not happen if step was resolved correctly
        raise ValueError(f"Step meta not found for step_ulid '{step_ulid}'")
    
    return Step(
        meta=step_meta,
        input_file=dummy_input,
        engine=engine_name,
        step_type_spec=step_type_spec or "custom",
        options={},
        reference_output=reference_path,
    ), False  # No migration needed (legacy calculations raise errors)


def _build_step_from_spec(
    *,
    step_ulid: str,
    engine_name: str,
    step_file: str,
    calculation_dir: Path,
    working_dir: Path,
    project: Project,
    options: dict,
    reference: Optional[Path],
    step_meta: ResourceMeta,
    existing_input_file: Optional[Path] = None,
    step_type_counts: Optional[Dict[str, int]] = None,
) -> Step:
    """
    Build a Step from a step spec file.
    
    Args:
        existing_input_file: Optional path to an existing input file. If provided,
            pseudopotentials will be extracted from it and merged into the step spec's
            species_overrides before generating the new input file.
    """
    spec_path = Path(step_file)
    if not spec_path.is_absolute():
        spec_path = (calculation_dir / spec_path).resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"Step spec not found: {spec_path}")

    # Load step spec (no legacy structure selector resolution needed - DAG + ULID only)
    spec_preview = StructureStepSpec.from_yaml(
        spec_path,
        resolve_structure_selector=None,  # DAG + ULID model: structure_ulid is already in spec
    )
    
    # IMPORT-ONLY: If existing_input_file is provided, it's for import workflows only.
    # Production run never uses existing_input_file (see contract in exec-pipeline-ssot-contract.md).
    # This code path is kept for import workflows (e.g., build_step_spec_from_qe_input).
    if existing_input_file and existing_input_file.exists():
        try:
            from quantumvitas.io.parser.qe_parser import QEInputParser
            from quantumvitas.io.model import QECardType
            from quantumvitas.calculation.importers import _build_step_spec_from_qe_input_data
            from quantumvitas.io.structure_io import structure_from_qe_input, write_structure
            
            existing_qe_input = QEInputParser.parse_file(existing_input_file)
            
            # Extract structure from existing input file and update the structure JSON file
            # This ensures the structure matches what's in the input file (e.g., correct number of atoms)
            # Only do this for steps that have structure (not post-processing steps like dos/bands)
            if spec_preview.structure_ulid and project:
                try:
                    # Check if this input file has structure cards (ATOMIC_POSITIONS)
                    # Post-processing steps (dos, bands, etc.) don't have structure
                    from quantumvitas.io.model import QECardType
                    has_structure = existing_qe_input.get_card(QECardType.ATOMIC_POSITIONS) is not None
                    
                    if has_structure:
                        structure_from_input = structure_from_qe_input(existing_qe_input)
                        structure_ref = project.get_structure(spec_preview.structure_ulid)
                        structure_path = structure_ref.absolute_path
                        
                        # Update the structure file with the structure from the input file
                        # Preserve the existing metadata (id, name, slug, etc.)
                        from quantumvitas.io.structure_io import STRUCTURE_META_KEY
                        import json
                        
                        # Read existing structure to preserve metadata
                        if structure_path.exists():
                            existing_data = json.loads(structure_path.read_text())
                            existing_meta = existing_data.get(STRUCTURE_META_KEY, {})
                        else:
                            existing_meta = structure_ref.meta.to_dict() if hasattr(structure_ref, 'meta') else {}
                        
                        # Write updated structure with preserved metadata
                        write_structure(
                            structure_from_input,
                            structure_path,
                            format="json",
                            metadata=existing_meta,
                        )
                except Exception as struct_e:
                    # If structure update fails, log but continue (don't break the calculation)
                    # This is expected for post-processing steps that don't have structure
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Could not extract structure from {existing_input_file.name} (may be post-processing step): {struct_e}")
            
            # Extract all parameters and cards from the existing input file
            # Use apply_defaults=False to get only what's in the input file
            # Convert spec type to gen type for the function
            from quantumvitas.workflow.step_type_convert import gen_from
            step_type_gen = gen_from(spec_preview.step_type_spec) if spec_preview.step_type_spec else "scf"
            extracted_params, extracted_cards = _build_step_spec_from_qe_input_data(
                existing_qe_input,
                step_type_gen,
                apply_defaults=False,
            )
            
            # Merge extracted parameters into step spec (existing input takes precedence)
            if extracted_params:
                if not spec_preview.parameters:
                    spec_preview.parameters = {}
                # Merge each namelist section
                for section, params in extracted_params.items():
                    if section not in spec_preview.parameters:
                        spec_preview.parameters[section] = {}
                    spec_preview.parameters[section].update(params)
            
            # Merge extracted cards into step spec (existing input takes precedence)
            if extracted_cards:
                if not spec_preview.cards:
                    spec_preview.cards = {}
                spec_preview.cards.update(extracted_cards)
            
            # Extract pseudopotentials from ATOMIC_SPECIES card
            atomic_species_card = existing_qe_input.get_card(QECardType.ATOMIC_SPECIES)
            if atomic_species_card and atomic_species_card.data:
                extracted_overrides = {}
                for row in atomic_species_card.data:
                    if isinstance(row, list) and len(row) >= 3:
                        element_symbol = str(row[0]).strip()
                        pseudo_filename = str(row[2]).strip()
                        # Skip placeholder names (missing configuration) and old default pattern
                        from quantumvitas.core.public import is_missing_pseudo_placeholder
                        if pseudo_filename and not is_missing_pseudo_placeholder(pseudo_filename):
                            # Also skip old default pattern for backward compatibility
                            if pseudo_filename != f"{element_symbol}.upf":
                                extracted_overrides[element_symbol] = {
                                    "pseudopot": pseudo_filename,
                                }
                
                # Merge extracted overrides into step spec (extracted takes precedence)
                if extracted_overrides:
                    if not spec_preview.species_overrides:
                        spec_preview.species_overrides = {}
                    spec_preview.species_overrides.update(extracted_overrides)
        except Exception as e:
            # If extraction fails, log but continue (don't break the calculation)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to extract parameters from existing input file {existing_input_file}: {e}")
    
    # Generate human-readable filename based on step_type_gen
    # Use step_type_gen (e.g., "scf", "nscf") instead of ULID for readability
    # If multiple steps of same type exist, number them (e.g., "scf-1.in", "scf-2.in")
    if spec_preview.input_name:
        # Use explicit input_name if provided
        input_override = spec_preview.input_name
    else:
        # Generate filename from step_type_gen (naming functions use gen types)
        from quantumvitas.workflow.step_type_convert import gen_from
        step_type_gen = gen_from(spec_preview.step_type_spec) if spec_preview.step_type_spec else "scf"
        
        # Use step_type_counts to determine if we need numbering
        # Count how many steps of this type we've already processed
        if step_type_counts is not None:
            count = step_type_counts.get(step_type_gen, 0)
            # Increment count for this step type (will be used for next step of same type)
            step_type_counts[step_type_gen] = count + 1
            
            # If this is the first step of this type, use base name (e.g., "scf.in")
            # If there are already steps of this type, number it (e.g., "scf-1.in", "scf-2.in")
            if count == 0:
                # First occurrence - use base name
                ext = CalculationFileNaming.input_extension(step_type_gen)
                input_override = f"{step_type_gen}{ext}"
            else:
                # Duplicate step type - number it (count is already incremented, so use count)
                ext = CalculationFileNaming.input_extension(step_type_gen)
                input_override = f"{step_type_gen}-{count}{ext}"
        else:
            # Fallback: check working_dir for existing files (for backwards compatibility)
            input_override = CalculationFileNaming.input_filename(step_type_gen, working_dir=working_dir)
    generated_input, spec = materialize_step_spec(
        spec_preview,
        output_dir=working_dir,
        calculation_dir=calculation_dir,
        project=project,
        spec_path=spec_path,
        input_name=input_override,
        project_root=project.root if project else None,
    )

    step_type_spec = spec.step_type_spec

    # Ensure generated_input is a valid file path (not directory, not '.')
    if generated_input.exists() and generated_input.is_dir():
        raise ValueError(
            f"Generated input path is a directory: {generated_input}. "
            f"This should not happen - materialize_step_spec should create a file."
        )
    
    # Convert to relative path from working_dir if possible (for cleaner Step.input_file)
    # But keep absolute if not relative to working_dir
    try:
        input_file_rel = generated_input.relative_to(working_dir)
        # Use relative path only if it's a simple filename (not going up directories)
        if not any(part == '..' for part in input_file_rel.parts):
            input_file_value = working_dir / input_file_rel
        else:
            input_file_value = generated_input
    except ValueError:
        # Not relative to working_dir, use absolute path
        input_file_value = generated_input.resolve()

    return Step(
        meta=step_meta,
        input_file=input_file_value,
        engine=engine_name,
        step_type_spec=step_type_spec,
        options=options,
        reference_output=reference,
    )


def _resolve_reference_path(reference: Optional[str], calculation_dir: Path) -> Optional[Path]:
    if not reference:
        return None
    reference_path = Path(reference)
    if not reference_path.is_absolute():
        reference_path = (calculation_dir / reference_path).resolve()
    return reference_path


def _build_step_meta(
    *,
    step_data: dict,
    calculation_dir: Path,
    project: Project,
) -> ResourceMeta:
    name = step_data.get("name") or step_data.get("ulid") or "step"
    default_path = step_data.get("path") or _default_step_path(
        calculation_dir=calculation_dir, project=project, step_name=name
    )
    return ResourceMeta.from_dict(
        step_data.get("meta"),
        kind="step",
        default_name=name,
        default_path=default_path,
    )


def _default_step_path(*, calculation_dir: Path, project: Project, step_name: str) -> str:
    """
    Steps live under ``calculations/<id>/steps`` by default. This helper makes sure
    we keep the path relative to the project root.
    """
    base = calculation_dir
    try:
        calculation_rel = ensure_relative_path(base, base=project.root)
    except ValueError:
        calculation_rel = base.name
    return f"{calculation_rel.rstrip('/')}/steps/{step_name}"

