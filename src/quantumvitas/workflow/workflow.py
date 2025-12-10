"""
Workflow representation (loaded from workflow.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from quantumvitas.core.resources import ResourceMeta, ensure_relative_path
from quantumvitas.project.model import Project, StructureRef
from .types import StepMode, StepType
from .step import Step
from .io import WorkflowIO
from .structure_steps import StructureStepSpec, materialize_step_spec
from .naming import WorkflowFileNaming


@dataclass(slots=True)
class Workflow:
    id: str
    project: Project
    dir: Path
    mode: StepMode
    steps: List[Step]
    io: WorkflowIO
    structure: Optional[StructureRef] = None
    working_dir: Path = field(default_factory=Path)
    _structure_id: Optional[str] = field(default=None, init=False, repr=False)  # Cached structure_id from model

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
        Get structure_id from the workflow.
        
        DAG + ID-only model invariants:
        - Workflow holds structure_id (ULID) as the canonical structure reference.
        - Steps do NOT persist structure_id in their YAML (they inherit from workflow).
        - All cross-resource relationships go through IDs + registry.
        
        This property reads from the underlying workflow.yaml model.
        """
        # If cached, return it
        if self._structure_id is not None:
            return self._structure_id
        
        # Otherwise, load from workflow.yaml
        workflow_yaml = self.dir / "workflow.yaml"
        if workflow_yaml.exists():
            try:
                from quantumvitas.core.models import load_workflow
                wf_model = load_workflow(workflow_yaml, self.project.root)
                self._structure_id = wf_model.structure_id
                return self._structure_id
            except Exception:
                pass
        
        # Fallback: get from structure ref if available
        if self.structure:
            return self.structure.meta.id
        
        return None

    @classmethod
    def from_yaml(
        cls, 
        workflow_dir: Path, 
        project: Project,
        materialize_steps: bool = True,
    ) -> "Workflow":
        """
        Load workflow from workflow.yaml.
        
        DAG + ID-only model:
        - Workflow.yaml contains structure_id (ULID) pointing to structure resource.
        - Steps are referenced by step_id (ULID) in workflow.steps entries.
        - Step YAML files do NOT contain structure_id or parent_workflow_id.
        - Structure is resolved via workflow.structure_id at execution time.
        """
        workflow_yaml = workflow_dir / "workflow.yaml"
        if not workflow_yaml.exists():
            raise FileNotFoundError(f"workflow.yaml not found: {workflow_yaml}")

        data = yaml.safe_load(workflow_yaml.read_text())
        workflow_id = data.get("id", workflow_dir.name)
        mode = StepMode(data.get("mode", StepMode.NORMAL.value))

        workflow_meta = data.get("workflow", {})
        
        # Handle structure migration: structure → structure_id
        needs_migration = False
        structure_id = workflow_meta.get("structure_id") or data.get("structure_id")
        legacy_structure = workflow_meta.get("structure") or data.get("structure")
        
        # If structure_id is missing but legacy structure selector is present, resolve it
        if not structure_id and legacy_structure:
            try:
                from quantumvitas.core.resolution import make_structure_selector_resolver, resolve_structure
                from quantumvitas.core.project_utils import load_project_config
                config = load_project_config(project.root)
                resolver = make_structure_selector_resolver(project.root, config=config)
                structure_id = resolver(legacy_structure)
                needs_migration = True
            except Exception:
                # If resolution fails, try direct project.get_structure (for backwards compat)
                try:
                    structure_ref_temp = project.get_structure(legacy_structure)
                    structure_id = structure_ref_temp.meta.id
                    needs_migration = True
                except Exception:
                    # Keep legacy_structure for now (will fail later if structure is actually needed)
                    pass
        
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

        raw_subdir = workflow_meta.get("working_dir", "raw")
        working_dir = (workflow_dir / raw_subdir).resolve()

        # Build steps and track migration
        steps: List[Step] = []
        migrated_step_entries: List[dict] = []  # Track step entries that need migration
        
        for step_data in data.get("steps", []):
            if materialize_steps:
                # Execution mode: fully materialize steps (calls materialize_step_spec, requires pseudos)
                step, step_migrated = _build_step(step_data, workflow_dir, working_dir, project)
                steps.append(step)
                
                if step_migrated:
                    needs_migration = True
                    # Store the migrated step entry (with real ULID) for YAML rewrite
                    # Get the real ULID from the step's meta (which was set from spec.meta.id)
                    migrated_step_entries.append({
                        "step_id": step.meta.id,  # Real ULID from spec.meta.id (via legacy fallback)
                        "type": step_data.get("type") or (step.step_type.value if step.step_type else None),
                        "input": step_data.get("input"),
                        "reference": step_data.get("reference"),
                    })
                else:
                    # Step didn't need migration, but we still need to track it for the upgraded YAML
                    migrated_step_entries.append(None)  # Marker that this step didn't need migration
            else:
                # Inspection mode: create lightweight step objects without materialization
                # This avoids calling materialize_step_spec and ensure_qe_pseudos
                step, step_migrated = _build_step_inspection(step_data, workflow_dir, working_dir, project)
                steps.append(step)
                
                if step_migrated:
                    needs_migration = True
                    # Store the migrated step entry with the real ULID from step file
                    migrated_step_entries.append({
                        "step_id": step.meta.id,  # Real ULID from step file (via new_step_id)
                        "type": step_data.get("type") or (step.step_type.value if step.step_type else None),
                        "input": step_data.get("input"),
                        "reference": step_data.get("reference"),
                    })
                else:
                    migrated_step_entries.append(None)

        # Create workflow instance
        workflow = cls(
            id=workflow_id,
            project=project,
            dir=workflow_dir,
            mode=mode,
            steps=steps,
            io=WorkflowIO(workflow_dir, raw_subdir=raw_subdir),
            structure=structure_ref,
            working_dir=working_dir,
        )
        # Cache structure_id for quick access
        workflow._structure_id = structure_id
        
        # Auto-migration: write upgraded YAML back to disk if needed
        if needs_migration:
            # Build upgraded workflow data (ID-only schema)
            upgraded_data: dict = {
                "id": workflow_id,
                "mode": mode.value,
                "working_dir": raw_subdir,
            }
            
            # Add meta if present in original
            if "meta" in data:
                upgraded_data["meta"] = data["meta"]
            
            # Add structure_id (canonical reference - ID only)
            if structure_id:
                upgraded_data["structure_id"] = structure_id
                # Optionally add structure_name if we resolved it
                if structure_ref:
                    upgraded_data["structure_name"] = structure_ref.meta.name
            
            # Add steps (ID-only: step_id is ULID, no step_file)
            upgraded_steps = []
            for i, step_data_orig in enumerate(data.get("steps", [])):
                if i < len(migrated_step_entries) and migrated_step_entries[i] is not None:
                    # Use migrated entry (with real ULID from legacy fallback)
                    upgraded_steps.append(migrated_step_entries[i])
                else:
                    # Step didn't need migration, but ensure it's in ID-only format
                    # Use the step's actual meta.id (which should be a ULID if it was already migrated)
                    step_entry = {
                        "step_id": steps[i].meta.id if i < len(steps) else (step_data_orig.get("step_id") or step_data_orig.get("id")),
                    }
                    if step_data_orig.get("type"):
                        step_entry["type"] = step_data_orig["type"]
                    if step_data_orig.get("input"):
                        step_entry["input"] = step_data_orig["input"]
                    if step_data_orig.get("reference"):
                        step_entry["reference"] = step_data_orig["reference"]
                    # Do NOT write step_file (ID-only model)
                    upgraded_steps.append(step_entry)
            
            upgraded_data["steps"] = upgraded_steps
            
            # Write upgraded YAML back to disk
            workflow_yaml.write_text(yaml.safe_dump(upgraded_data, sort_keys=False))
        
        return workflow


def _build_step(
    step_data: dict,
    workflow_dir: Path,
    working_dir: Path,
    project: Project,
) -> tuple[Step, bool]:
    """
    Build a Step from step_data in workflow.yaml.
    
    Uses step_id (ULID) to resolve step file via ResourceIndex.
    step_file is no longer stored in workflow.yaml - only step_id.
    
    Returns:
        Tuple of (Step, migrated_flag) where migrated_flag is True if legacy
        fallback path was used (indicating the workflow needs migration).
    """
    from quantumvitas.core.resolution import require_step, ResourceNotFoundError
    from quantumvitas.workflow.structure_steps import StructureStepSpec
    from quantumvitas.core.resolution import make_structure_selector_resolver
    from quantumvitas.core.project_utils import load_project_config
    
    # Prefer step_id (ULID) - canonical reference, fall back to legacy id field
    step_id = step_data.get("step_id") or step_data.get("id")
    if not step_id:
        raise ValueError(f"Step entry missing both 'step_id' and 'id': {step_data}")
    
    engine_name = step_data.get("engine", "qe")
    migrated = False
    new_step_id = step_id  # Will be updated if legacy path is used
    
    # Check if step_id is a ULID (26 chars starting with "01")
    is_ulid = len(step_id) == 26 and step_id.startswith("01")
    
    # Try ID-first via registry (only if step_id is a ULID)
    if is_ulid:
        try:
            # Try to get workflow from project by matching directory
            workflow_ref = None
            for wf_ref in project.workflows.values():
                if wf_ref.absolute_path == workflow_dir:
                    workflow_ref = wf_ref
                    break
            
            if workflow_ref:
                workflow_selector = workflow_ref.meta.slug or workflow_ref.meta.name
            else:
                workflow_selector = workflow_dir.name
            
            step_resolved = require_step(project.root, workflow_selector, step_id)
            step_file_path = step_resolved.absolute_path
            new_step_id = step_resolved.meta.id  # Use the ULID from registry
            # Normal path: step_id is a real ULID, no migration needed
        except ResourceNotFoundError:
            # ULID not found in registry - treat as legacy
            is_ulid = False
    
    # Legacy fallback: step_id is not a ULID or ULID not found
    if not is_ulid:
        # Legacy fallback: step_id might be a name, not a ULID
        migrated = True
        
        # Check for legacy step_file
        legacy_step_file = step_data.get("step_file")
        
        # If legacy_step_file is not specified, try to find step file by:
        # 1. Try step_id as filename (if it's a name like "scf")
        # 2. Scan all step files and match by ULID in meta.id
        if not legacy_step_file:
            # First try: step_id as filename (legacy: id is name)
            candidate = (workflow_dir / "steps" / f"{step_id}.step.yaml").resolve()
            if candidate.exists():
                legacy_step_file = str(candidate.relative_to(workflow_dir))
            else:
                # Second try: scan step files and match by ULID
                steps_dir = workflow_dir / "steps"
                if steps_dir.exists():
                    for step_file in steps_dir.glob("*.step.yaml"):
                        try:
                            step_data_file = yaml.safe_load(step_file.read_text()) or {}
                            step_meta = step_data_file.get("meta", {})
                            if step_meta.get("id") == step_id:
                                legacy_step_file = str(step_file.relative_to(workflow_dir))
                                break
                        except Exception:
                            continue
        
        # If we have a legacy_step_file, load the step directly
        if legacy_step_file:
            step_file_path = (workflow_dir / legacy_step_file).resolve()
            if not step_file_path.exists():
                raise ValueError(f"Step '{step_id}' file not found at {step_file_path}")
            
            # Load step spec with resolver for legacy structure selector normalization
            try:
                config = load_project_config(project.root)
                resolver = make_structure_selector_resolver(project.root, config=config)
            except Exception:
                resolver = None
            
            spec = StructureStepSpec.from_yaml(
                step_file_path,
                resolve_structure_selector=resolver,
            )
            # Here spec.meta.id is the real ULID for this step
            new_step_id = spec.meta.id
        else:
            # No registry entry, no legacy path: real error
            raise ValueError(
                f"Step '{step_id}' not found in registry and no legacy step_file/candidate found"
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
                        f"Step '{step_id}' input path must point to a file inside '{working_dir.name}'"
                    )
                input_path = Path(*parts[1:])
        
        # Resolve the full path to the existing input file
        if input_path:
            existing_input_file = (working_dir / input_path).resolve()
            if not existing_input_file.exists():
                # Try relative to workflow_dir instead
                existing_input_file = (workflow_dir / input_path).resolve()
                if not existing_input_file.exists():
                    existing_input_file = None

    options = step_data.get("options", step_data.get("params", {})) or {}
    reference_path = _resolve_reference_path(step_data.get("reference"), workflow_dir)

    step_meta = _build_step_meta(
        step_data=step_data,
        workflow_dir=workflow_dir,
        project=project,
    )

    # Always build from spec file (step_file_path resolved via registry or legacy fallback)
    # Use new_step_id (real ULID) for the step, not the original step_id (which might be a name)
    # Pass existing_input_file so pseudopotentials can be extracted from it
    step = _build_step_from_spec(
        step_id=new_step_id,  # Use real ULID from spec.meta.id if legacy path was used
        engine_name=engine_name,
        step_file=str(step_file_path.relative_to(workflow_dir)) if step_file_path.is_relative_to(workflow_dir) else step_file_path.name,
        workflow_dir=workflow_dir,
        working_dir=working_dir,
        project=project,
        options=options,
        reference=reference_path,
        step_meta=step_meta,
        existing_input_file=existing_input_file,
    )
    
    return step, migrated


def _build_step_inspection(
    step_data: dict,
    workflow_dir: Path,
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
    from quantumvitas.workflow.structure_steps import StructureStepSpec
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
            # Try to get workflow from project by matching directory
            workflow_ref = None
            for wf_ref in project.workflows.values():
                if wf_ref.absolute_path == workflow_dir:
                    workflow_ref = wf_ref
                    break
            
            if workflow_ref:
                workflow_selector = workflow_ref.meta.slug or workflow_ref.meta.name
            else:
                workflow_selector = workflow_dir.name
            
            step_resolved = require_step(project.root, workflow_selector, step_id)
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
            candidate = (workflow_dir / "steps" / f"{step_id}.step.yaml").resolve()
            if candidate.exists():
                legacy_step_file = str(candidate.relative_to(workflow_dir))
        
        # If we have a legacy_step_file, load the step spec
        if legacy_step_file:
            step_file_path = (workflow_dir / legacy_step_file).resolve()
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
                    path=f"workflows/{workflow_dir.name}/steps/{step_id}.step.yaml",
                    kind="step",
                )
                step_type = StepType.CUSTOM
        else:
            # Create minimal meta if no file found
            step_meta = ResourceMeta(
                id=generate_resource_id(),
                name=step_id,
                slug=step_id,
                path=f"workflows/{workflow_dir.name}/steps/{step_id}.step.yaml",
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
            reference_path = (workflow_dir / reference_path).resolve()
    
    # Create lightweight step (no materialization, no input file generation)
    # Use a dummy input file path if needed (won't be used in inspection mode)
    dummy_input = input_path or (working_dir / f"{step_id}.in")
    
    # Ensure step_meta has the correct ULID (from step file if migrated, or generated if not)
    if not step_meta:
        step_meta = ResourceMeta(
            id=new_step_id,  # Use new_step_id (which is step_id if not migrated, or ULID if migrated)
            name=step_id,
            slug=step_id,
            path=f"workflows/{workflow_dir.name}/steps/{step_id}.step.yaml",
            kind="step",
        )
    else:
        # Ensure step_meta.id is set to the correct ULID (new_step_id)
        step_meta.id = new_step_id
    
    return Step(
        meta=step_meta,
        input_file=dummy_input,
        engine=engine_name,
        step_type=step_type or StepType.CUSTOM,
        options={},
        reference_output=reference_path,
    ), migrated


def _build_step_from_spec(
    *,
    step_id: str,
    engine_name: str,
    step_file: str,
    workflow_dir: Path,
    working_dir: Path,
    project: Project,
    options: dict,
    reference: Optional[Path],
    step_meta: ResourceMeta,
    existing_input_file: Optional[Path] = None,
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
        spec_path = (workflow_dir / spec_path).resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"Step spec not found: {spec_path}")

    # Create resolver for legacy structure selector normalization
    resolve_structure_selector = None
    if project:
        try:
            from quantumvitas.core.resolution import make_structure_selector_resolver
            from quantumvitas.core.project_utils import load_project_config
            config = load_project_config(project.root)
            resolve_structure_selector = make_structure_selector_resolver(project.root, config=config)
        except Exception:
            pass

    spec_preview = StructureStepSpec.from_yaml(
        spec_path,
        resolve_structure_selector=resolve_structure_selector,
    )
    
    # If there's an existing input file, extract structure, parameters, cards, and pseudopotentials from it
    # and merge them into the step spec (existing input takes precedence over step spec defaults)
    if existing_input_file and existing_input_file.exists():
        try:
            from quantumvitas.io.parser.qe_parser import QEInputParser
            from quantumvitas.io.model import QECardType
            from quantumvitas.workflow.importers import _build_step_spec_from_qe_input_data
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
                    # If structure update fails, log but continue (don't break the workflow)
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
            # If extraction fails, log but continue (don't break the workflow)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to extract parameters from existing input file {existing_input_file}: {e}")
    
    # Use proper file naming: {structure_slug}.{step_slug}.in
    # Get structure slug from project
    structure_slug = None
    if project and spec_preview.structure_id:
        try:
            structure_ref = project.get_structure(spec_preview.structure_id)
            structure_slug = structure_ref.meta.slug or structure_ref.meta.name
        except Exception:
            pass
    
    # Use step slug from step meta
    step_slug = spec_preview.meta.slug or spec_preview.meta.name or step_id
    
    # Generate filename: {structure_slug}.{step_slug}.in (or fallback to step_id)
    if structure_slug and step_slug:
        ext = WorkflowFileNaming.input_extension(spec_preview.step_type or "scf")
        input_override = spec_preview.input_name or f"{structure_slug}.{step_slug}{ext}"
    else:
        # Fallback to step_id if we can't get structure/step slugs
        input_override = spec_preview.input_name or WorkflowFileNaming.input_filename(step_id, spec_preview.step_type)
    generated_input, spec = materialize_step_spec(
        spec_preview,
        output_dir=working_dir,
        workflow_dir=workflow_dir,
        project=project,
        spec_path=spec_path,
        input_name=input_override,
        project_root=project.root if project else None,
    )

    step_type = _coerce_step_type(spec.step_type)

    return Step(
        meta=step_meta,
        input_file=generated_input,
        engine=engine_name,
        step_type=step_type,
        options=options,
        reference_output=reference,
    )


def _coerce_step_type(raw: Optional[str]) -> Optional[StepType]:
    if not raw:
        return None
    try:
        return StepType(raw)
    except ValueError:
        return StepType.CUSTOM


def _resolve_reference_path(reference: Optional[str], workflow_dir: Path) -> Optional[Path]:
    if not reference:
        return None
    reference_path = Path(reference)
    if not reference_path.is_absolute():
        reference_path = (workflow_dir / reference_path).resolve()
    return reference_path


def _build_step_meta(
    *,
    step_data: dict,
    workflow_dir: Path,
    project: Project,
) -> ResourceMeta:
    name = step_data.get("name") or step_data.get("id") or "step"
    default_path = step_data.get("path") or _default_step_path(
        workflow_dir=workflow_dir, project=project, step_name=name
    )
    return ResourceMeta.from_dict(
        step_data.get("meta"),
        kind="step",
        default_name=name,
        default_path=default_path,
    )


def _default_step_path(*, workflow_dir: Path, project: Project, step_name: str) -> str:
    """
    Steps live under ``workflows/<id>/steps`` by default. This helper makes sure
    we keep the path relative to the project root.
    """
    base = workflow_dir
    try:
        workflow_rel = ensure_relative_path(base, base=project.root)
    except ValueError:
        workflow_rel = base.name
    return f"{workflow_rel.rstrip('/')}/steps/{step_name}"

