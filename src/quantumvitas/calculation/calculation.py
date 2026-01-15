"""
Calculation representation (loaded from calculation.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from quantumvitas.core.resources import ResourceMeta, ensure_relative_path
from quantumvitas.project.model import Project, StructureRef
from .types import StepMode, StepType
from .step import Step
from .io import CalculationIO
from .structure_steps import StructureStepSpec, materialize_step_spec
from .naming import CalculationFileNaming


@dataclass(slots=True)
class Calculation:
    id: str
    project: Project
    dir: Path
    mode: StepMode
    steps: List[Step]
    io: CalculationIO
    structure: Optional[StructureRef] = None
    working_dir: Path = field(default_factory=Path)
    _structure_id: Optional[str] = field(default=None, init=False, repr=False)  # Cached structure_id from model
    _species_map: Optional[Dict[str, Dict[str, Any]]] = field(default=None, init=False, repr=False)  # Cached species_map
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
    def structure_id(self) -> Optional[str]:
        """
        Get structure_id from the calculation.
        
        DAG + ID-only model invariants:
        - Calculation holds structure_id (ULID) as the canonical structure reference.
        - Steps do NOT persist structure_id in their YAML (they inherit from calculation).
        - All cross-resource relationships go through IDs + registry.
        
        This property reads from the underlying calculation.yaml model.
        """
        # If cached, return it
        if self._structure_id is not None:
            return self._structure_id
        
        # Otherwise, load from calculation.yaml
        calculation_yaml = self.dir / "calculation.yaml"
        if calculation_yaml.exists():
            try:
                from quantumvitas.core.models import load_calculation
                wf_model = load_calculation(calculation_yaml, self.project.root)
                self._structure_id = wf_model.structure_id
                return self._structure_id
            except Exception:
                pass
        
        # Fallback: get from structure ref if available
        if self.structure:
            return self.structure.meta.id
        
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
                from quantumvitas.core.models import load_calculation
                wf_model = load_calculation(calculation_yaml, self.project.root)
                self._species_map = wf_model.species_map
                return self._species_map
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
                from quantumvitas.core.models import load_calculation
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
        - Calculation.yaml contains structure_id (ULID) pointing to structure resource.
        - Steps are referenced by step_id (ULID) in calculation.steps entries.
        - Step YAML files do NOT contain structure_id or parent_calculation_id.
        - Structure is resolved via calculation.structure_id at execution time.
        """
        calculation_yaml = calculation_dir / "calculation.yaml"
        if not calculation_yaml.exists():
            raise FileNotFoundError(f"calculation.yaml not found: {calculation_yaml}")

        data = yaml.safe_load(calculation_yaml.read_text())
        calculation_id = data.get("id", calculation_dir.name)
        mode = StepMode(data.get("mode", StepMode.NORMAL.value))

        calculation_meta = data.get("calculation", {})
        
        # Detect legacy structure selector (NOT SUPPORTED)
        from quantumvitas.core.exceptions import LegacyProjectError
        
        structure_id = calculation_meta.get("structure_id") or data.get("structure_id")
        legacy_structure = calculation_meta.get("structure") or data.get("structure")
        
        # If structure_id is missing but legacy structure selector is present, raise error
        if not structure_id and legacy_structure:
            error_msg = (
                f"Legacy calculation detected at {calculation_dir}: has 'structure' selector but no 'structure_id' ULID. "
                f"Please run the migration script to upgrade this calculation."
            )
            raise LegacyProjectError(project.root, error_msg)
        
        structure_ref: Optional[StructureRef] = None
        if structure_id:
            try:
                # Try to resolve structure by ID (can be ULID, slug, or name)
                structure_ref = project.get_structure(structure_id)
            except Exception:
                # Try to resolve by ID if direct lookup fails
                for struct_ref in project.structures.values():
                    if struct_ref.meta.id == structure_id:
                        structure_ref = struct_ref
                        break

        raw_subdir = calculation_meta.get("working_dir", "raw")
        working_dir = (calculation_dir / raw_subdir).resolve()

        # Build steps (legacy calculations will raise LegacyProjectError)
        steps: List[Step] = []
        
        # Track step types to generate unique filenames (only number if duplicates exist)
        # Count is incremented inside _build_step_from_spec when generating filename
        step_type_counts: Dict[str, int] = {}  # step_type -> count of steps with this type seen so far
        
        # Log materialization entry
        if materialize_steps:
            import logging
            logger = logging.getLogger(__name__)
            step_ids = [step_data.get("step_id", "unknown") for step_data in data.get("steps", [])]
            logger.info(
                f"[MATERIALIZE_STEPS] ENTRY "
                f"calculation_dir={calculation_dir} "
                f"raw_dir={working_dir} "
                f"steps_to_materialize={step_ids} "
                f"n_steps={len(step_ids)}"
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
            id=calculation_id,
            project=project,
            dir=calculation_dir,
            mode=mode,
            steps=steps,
            io=CalculationIO(calculation_dir, raw_subdir=raw_subdir),
            structure=structure_ref,
            working_dir=working_dir,
        )
        # Cache structure_id for quick access
        calculation._structure_id = structure_id
        
        # Phase 3A: Ensure calculation identity is set (best-effort recovery)
        from quantumvitas.core.calc_identity import ensure_calculation_identity
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
    
    Uses step_id (ULID) to resolve step file via ResourceIndex.
    step_file is no longer stored in calculation.yaml - only step_id.
    
    Returns:
        Tuple of (Step, migrated_flag) where migrated_flag is True if legacy
        fallback path was used (indicating the calculation needs migration).
    """
    from quantumvitas.core.resolution import require_step, ResourceNotFoundError
    from quantumvitas.calculation.structure_steps import StructureStepSpec
    from quantumvitas.core.resolution import make_structure_selector_resolver
    from quantumvitas.core.project_utils import load_project_config
    
    # Require step_id (ULID) - no legacy fallback
    from quantumvitas.core.exceptions import LegacyProjectError
    
    step_id = step_data.get("step_id")
    if not step_id:
        # Check for legacy fields
        has_legacy_id = "id" in step_data
        has_step_file = "step_file" in step_data
        if has_legacy_id or has_step_file:
            error_msg = (
                f"Legacy calculation step entry detected in {calculation_dir}: "
                f"missing 'step_id' ULID. "
            )
            if has_step_file:
                error_msg += "Field 'step_file' is not supported (use step_id ULID instead). "
            if has_legacy_id:
                error_msg += "Legacy 'id' field detected (use step_id ULID instead). "
            error_msg += "Please run the migration script to upgrade this calculation."
            raise LegacyProjectError(project.root, error_msg)
        else:
            raise ValueError(f"Step entry missing 'step_id' ULID: {step_data}")
    
    # Check if step_id is a valid ULID (26 chars starting with "01")
    is_ulid = len(step_id) == 26 and step_id.startswith("01")
    if not is_ulid:
        error_msg = (
            f"Legacy calculation step entry detected in {calculation_dir}: "
            f"step_id '{step_id}' is not a ULID (must be 26 chars starting with '01'). "
            f"Please run the migration script to upgrade this calculation."
        )
        raise LegacyProjectError(project.root, error_msg)
    
    # Check for legacy step_file field
    if "step_file" in step_data:
        error_msg = (
            f"Legacy calculation step entry detected in {calculation_dir}: "
            f"field 'step_file' is not supported (use step_id ULID instead). "
            f"Please run the migration script to upgrade this calculation."
        )
        raise LegacyProjectError(project.root, error_msg)
    
    engine_name = step_data.get("engine", "qe")
    
    # Resolve step via registry using ULID
    try:
        # Try to get calculation from project by matching directory
        calculation_ref = None
        for wf_ref in project.calculations.values():
            if wf_ref.absolute_path == calculation_dir:
                calculation_ref = wf_ref
                break
        
        if calculation_ref:
            calculation_selector = calculation_ref.meta.slug or calculation_ref.meta.name
        else:
            calculation_selector = calculation_dir.name
        
        step_resolved = require_step(project.root, calculation_selector, step_id)
        step_file_path = step_resolved.absolute_path
    except ResourceNotFoundError as e:
        error_msg = (
            f"Step '{step_id}' not found in registry. "
            f"This may indicate a legacy calculation that needs migration. "
            f"Please run the migration script to upgrade this calculation."
        )
        raise LegacyProjectError(project.root, error_msg) from e
    
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
                        f"Step '{step_id}' input path must point to a file inside '{working_dir.name}'"
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
    
    # Assert step_id from calculation.yaml matches step_meta.id from step.yaml
    # This ensures ULID consistency across calculation.yaml and step.yaml
    if step_meta.id != step_id:
        raise ValueError(
            f"Step ULID mismatch: calculation.yaml step_id='{step_id}' "
            f"does not match step.yaml meta.id='{step_meta.id}'. "
            f"This indicates a corrupted calculation or step file."
        )

    # Build from spec file (step_file_path resolved via registry)
    # Pass existing_input_file so pseudopotentials can be extracted from it
    step = _build_step_from_spec(
        step_id=step_id,  # Use ULID from calculation.yaml (must match step_meta.id)
        engine_name=engine_name,
        step_file=str(step_file_path.relative_to(calculation_dir)) if step_file_path.is_relative_to(calculation_dir) else step_file_path.name,
        calculation_dir=calculation_dir,
        working_dir=working_dir,
        project=project,
        options=options,
        reference=reference_path,
        step_meta=step_meta,
        existing_input_file=existing_input_file,
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
    from quantumvitas.core.resources import ResourceMeta, generate_resource_id
    from quantumvitas.core.resolution import require_step, ResourceNotFoundError
    from quantumvitas.calculation.structure_steps import StructureStepSpec
    from quantumvitas.core.resolution import make_structure_selector_resolver
    from quantumvitas.core.project_utils import load_project_config
    
    # Prefer step_id (ULID) - canonical reference, fall back to legacy id field
    step_id = step_data.get("step_id") or step_data.get("id")
    if not step_id:
        raise ValueError(f"Step entry missing both 'step_id' and 'id': {step_data}")
    
    engine_name = step_data.get("engine", "qe")
    migrated = False
    step_meta: Optional[ResourceMeta] = None
    step_type: Optional[StepType] = None
    input_path: Optional[Path] = None
    new_step_id = step_id  # Will be updated if legacy path is used
    
    # Check if step_id is a ULID (26 chars starting with "01")
    is_ulid = len(step_id) == 26 and step_id.startswith("01")
    
    # Try ID-first via registry (only if step_id is a ULID)
    if is_ulid:
        try:
            # Try to get calculation from project by matching directory
            calculation_ref = None
            for wf_ref in project.calculations.values():
                if wf_ref.absolute_path == calculation_dir:
                    calculation_ref = wf_ref
                    break
            
            if calculation_ref:
                calculation_selector = calculation_ref.meta.slug or calculation_ref.meta.name
            else:
                calculation_selector = calculation_dir.name
            
            step_resolved = require_step(project.root, calculation_selector, step_id)
            step_file_path = step_resolved.absolute_path
            step_meta = step_resolved.meta
            new_step_id = step_meta.id  # Use the ULID from registry
            
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
            step_type = _coerce_step_type(spec.step_type)
        except ResourceNotFoundError:
            # ULID not found in registry - treat as legacy
            is_ulid = False
    
    # Legacy fallback: step_id is not a ULID or ULID not found
    if not is_ulid:
        # Legacy fallback: step_id might be a name, not a ULID
        migrated = True
        
        # Check for legacy step_file
        legacy_step_file = step_data.get("step_file")
        
        # If legacy_step_file is not specified, try to find step file by name
        if not legacy_step_file:
            candidate = (calculation_dir / "steps" / f"{step_id}.step.yaml").resolve()
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
                step_type = _coerce_step_type(spec.step_type)
                # Store the real ULID for migration
                new_step_id = step_meta.id
            else:
                # Create minimal meta if file doesn't exist
                step_meta = ResourceMeta(
                    id=generate_resource_id(),
                    name=step_id,
                    slug=step_id,
                    path=f"calculations/{calculation_dir.name}/steps/{step_id}.step.yaml",
                    kind="step",
                )
                step_type = StepType.CUSTOM
        else:
            # Create minimal meta if no file found
            step_meta = ResourceMeta(
                id=generate_resource_id(),
                name=step_id,
                slug=step_id,
                path=f"calculations/{calculation_dir.name}/steps/{step_id}.step.yaml",
                kind="step",
            )
            step_type = StepType.CUSTOM
    
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
    dummy_input = input_path or (working_dir / f"{step_id}.in")
    
    # step_meta should be set from spec above
    if not step_meta:
        # This should not happen if step was resolved correctly
        raise ValueError(f"Step meta not found for step_id '{step_id}'")
    
    return Step(
        meta=step_meta,
        input_file=dummy_input,
        engine=engine_name,
        step_type=step_type or StepType.CUSTOM,
        options={},
        reference_output=reference_path,
    ), False  # No migration needed (legacy calculations raise errors)


def _build_step_from_spec(
    *,
    step_id: str,
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
        resolve_structure_selector=None,  # DAG + ULID model: structure_id is already in spec
    )
    
    # If there's an existing input file, extract structure, parameters, cards, and pseudopotentials from it
    # and merge them into the step spec (existing input takes precedence over step spec defaults)
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
            if spec_preview.structure_id and project:
                try:
                    # Check if this input file has structure cards (ATOMIC_POSITIONS)
                    # Post-processing steps (dos, bands, etc.) don't have structure
                    from quantumvitas.io.model import QECardType
                    has_structure = existing_qe_input.get_card(QECardType.ATOMIC_POSITIONS) is not None
                    
                    if has_structure:
                        structure_from_input = structure_from_qe_input(existing_qe_input)
                        structure_ref = project.get_structure(spec_preview.structure_id)
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
            extracted_params, extracted_cards = _build_step_spec_from_qe_input_data(
                existing_qe_input,
                spec_preview.step_type or "scf",
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
                        from quantumvitas.core.pseudo import is_missing_pseudo_placeholder
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
    
    # Generate human-readable filename based on step_type
    # Use step_type (e.g., "scf", "nscf") instead of ULID for readability
    # If multiple steps of same type exist, number them (e.g., "scf-1.in", "scf-2.in")
    if spec_preview.input_name:
        # Use explicit input_name if provided
        input_override = spec_preview.input_name
    else:
        # Generate filename from step_type
        step_type = spec_preview.step_type or "scf"
        
        # Use step_type_counts to determine if we need numbering
        # Count how many steps of this type we've already processed
        if step_type_counts is not None:
            count = step_type_counts.get(step_type, 0)
            # Increment count for this step type (will be used for next step of same type)
            step_type_counts[step_type] = count + 1
            
            # If this is the first step of this type, use base name (e.g., "scf.in")
            # If there are already steps of this type, number it (e.g., "scf-1.in", "scf-2.in")
            if count == 0:
                # First occurrence - use base name
                ext = CalculationFileNaming.input_extension(step_type)
                input_override = f"{step_type}{ext}"
            else:
                # Duplicate step type - number it (count is already incremented, so use count)
                ext = CalculationFileNaming.input_extension(step_type)
                input_override = f"{step_type}-{count}{ext}"
        else:
            # Fallback: check working_dir for existing files (for backwards compatibility)
            input_override = CalculationFileNaming.input_filename(step_type, working_dir=working_dir)
    generated_input, spec = materialize_step_spec(
        spec_preview,
        output_dir=working_dir,
        calculation_dir=calculation_dir,
        project=project,
        spec_path=spec_path,
        input_name=input_override,
        project_root=project.root if project else None,
    )

    step_type = _coerce_step_type(spec.step_type)

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
        step_type=step_type,
        options=options,
        reference_output=reference,
    )


def _coerce_step_type(raw: Optional[str]) -> Optional[StepType]:
    """
    Coerce a step type string to StepType enum.

    Handles both GEN types (e.g., "scf") and SPEC types (e.g., "qe_scf")
    by using registry lookup to convert SPEC to GEN when needed.
    """
    if not raw:
        return None

    # Try direct conversion (works for GEN types like "scf")
    try:
        return StepType(raw)
    except ValueError:
        pass

    # If direct conversion failed, try registry lookup for SPEC types
    # SPEC type like "qe_scf" -> public_type "scf" -> StepType.SCF
    try:
        from quantumvitas.workflow.registry import get_registry
        reg = get_registry()
        spec = reg.get(str(raw))
        if spec and spec.public_type:
            return StepType(spec.public_type)
    except Exception:
        pass

    return StepType.CUSTOM


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
    name = step_data.get("name") or step_data.get("id") or "step"
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

