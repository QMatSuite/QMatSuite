"""
Centralized data models for QuantumVITAS resources.

All resources (project, calculation, step, structure) are represented as dataclasses.
YAML/JSON files are just the persistence format - not the primary representation.

This module provides:
- Dataclass models for each resource type
- load_* / save_* functions for YAML/JSON I/O
- Consistent meta fields (id, name, slug, path) across all resources
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from quantumvitas.core.resources import (
    ResourceMeta,
    ResourceKind,
    ensure_relative_path,
    generate_resource_id,
    slugify,
)


# ---------------------------------------------------------------------------
# Calculation Model
# ---------------------------------------------------------------------------


def _infer_engine_family_from_steps(steps: List["CalculationStepEntry"]) -> Optional[str]:
    """
    Infer engine_family from step types (backward compatibility recovery).
    
    This is best-effort only; no guarantees required.
    
    Args:
        steps: List of CalculationStepEntry objects
    
    Returns:
        Engine family identifier if all steps belong to one family, None otherwise
    """
    if not steps:
        return None
    
    # Map step types to engine families
    # Old step types (without prefix) are assumed to be QE
    step_type_to_family: Dict[str, str] = {}
    
    # QE step types (prefixed and legacy)
    qe_types = {"scf", "nscf", "relax", "vc-relax", "dos", "bands", "bands_pw", "ph", "q2r", "matdyn", "dynmat", 
                "pp", "projwfc", "md", "vc-md", "pw2wannier90", "custom"}
    for step_type in qe_types:
        step_type_to_family[step_type] = "qe"
        step_type_to_family[f"qe_{step_type}"] = "qe"
        # Handle legacy names
        if step_type == "vc-relax":
            step_type_to_family["qe_vc_relax"] = "qe"
        elif step_type == "bands_pw":
            step_type_to_family["qe_bands_pw"] = "qe"
        elif step_type == "vc-md":
            step_type_to_family["qe_vc_md"] = "qe"
    
    # Wannier90 step types
    w90_types = {"w90_preproc", "w90_run"}
    for step_type in w90_types:
        step_type_to_family[step_type] = "qe"  # w90 is part of qe family toolchain
    
    # PySCF step types
    pyscf_types = {"pyscf_scf"}
    for step_type in pyscf_types:
        step_type_to_family[step_type] = "pyscf"
    
    # Collect families from all steps
    families = set()
    for step in steps:
        step_type = step.step_type
        if step_type:
            family = step_type_to_family.get(step_type)
            if family:
                families.add(family)
            elif not step_type.startswith(("qe_", "w90_", "pyscf_")):
                # Legacy step type without prefix - assume QE
                families.add("qe")
    
    # Return single family if all steps belong to one family
    if len(families) == 1:
        return families.pop()
    
    # Mixed families or unknown - return None (will use default)
    return None


@dataclass
class CalculationStepEntry:
    """
    An entry in the calculation's step list.
    
    Cross-resource reference: step_id (ULID) is the ONLY allowed cross-resource field.
    All other fields (type, input, reference) are calculation-local metadata, not cross-references.
    
    The step file location is resolved via ResourceIndex using step_id, not stored here.
    """
    step_id: Optional[str] = None  # Canonical step reference (ULID from step meta) - REQUIRED
    type: Optional[str] = None  # Calculation-local metadata (step type for display/ordering) - stores PUBLIC type
    input: Optional[str] = None  # Calculation-local metadata (legacy input file reference)
    reference: Optional[str] = None  # Calculation-local metadata (reference file)
    
    # Legacy field removed - step_id (ULID) is the only identifier
    
    @property
    def step_type(self) -> Optional[str]:
        """
        Backward compatibility: step_type property returns the type field (public type).
        
        This allows code that expects step_type to continue working.
        """
        return self.type
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        Writes step_id (ULID) as the ONLY cross-resource reference.
        Does NOT write step_file (file location resolved via registry).
        Does not write legacy id field.
        """
        d: Dict[str, Any] = {}
        if self.step_id:
            d["step_id"] = self.step_id
        if self.type:
            d["type"] = self.type
        if self.input:
            d["input"] = self.input
        if self.reference:
            d["reference"] = self.reference
        # Do not write legacy "id" field
        # Do not write step_file (resolved via registry using step_id)
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: Optional[Path] = None) -> "CalculationStepEntry":
        """
        Create CalculationStepEntry from dictionary.
        
        This method only supports the DAG + ULID model. Legacy calculations
        (with step_file or non-ULID step_id) must be migrated first.
        
        Args:
            data: Dictionary containing step entry data
            project_root: Optional project root for error messages
        
        Raises:
            LegacyProjectError: If legacy fields are detected (step_file, non-ULID step_id)
        """
        from quantumvitas.core.exceptions import LegacyProjectError
        
        # New format: step_id (ULID) - REQUIRED
        step_id = data.get("step_id")
        
        # Detect legacy patterns
        has_step_file = "step_file" in data
        has_legacy_id = "id" in data and data.get("id") != step_id
        
        # Check if step_id is missing or not a ULID (26 chars starting with "01")
        is_ulid = step_id and len(step_id) == 26 and step_id.startswith("01")
        missing_or_invalid_step_id = not step_id or not is_ulid
        
        if has_step_file or has_legacy_id or missing_or_invalid_step_id:
            error_msg = "Legacy calculation step entry detected. "
            if has_step_file:
                error_msg += "Field 'step_file' is not supported (use step_id ULID instead). "
            if missing_or_invalid_step_id:
                error_msg += f"step_id must be a ULID (26 chars), got: {step_id}. "
            if has_legacy_id:
                error_msg += "Legacy 'id' field detected (use step_id ULID instead). "
            error_msg += "Please run the migration script to upgrade this calculation."
            
            if project_root:
                raise LegacyProjectError(project_root, error_msg)
            else:
                raise LegacyProjectError(Path.cwd(), error_msg)
        
        # Phase 2: Normalize machine type (qe_scf) to public type (scf) in type field
        step_type_raw = data.get("type")
        step_type_public = step_type_raw
        if step_type_raw:
            # If it's a machine type, convert to public type
            from quantumvitas.workflow.registry import get_registry
            registry = get_registry()
            spec = registry.get(step_type_raw)  # Accepts both public and machine types
            if spec:
                step_type_public = spec.public_type
        
        return cls(
            step_id=step_id,
            type=step_type_public,  # Store public type for backward compatibility
            input=data.get("input") or data.get("file"),
            reference=data.get("reference"),
            # Do not store legacy id field
        )


@dataclass
class CalculationModel:
    """
    Data model for a calculation (calculation.yaml).
    
    All calculations have a meta section with id, name, slug, path.
    
    Structure references:
    - structure_id: ULID of the structure (canonical reference)
    - structure_name: Optional display name (cosmetic only, not used for resolution)
    
    Structure and engine metadata:
    - structure_kind: "periodic" | "molecule" (immutable once set)
    - engine_family: Engine family identifier (immutable once set, e.g., "qe", "pyscf")
      Used for workflow materialization (generalized → engine-specific steps)
    
    Pseudopotential mapping:
    - species_map: dict[element_symbol -> {pseudopot: str, mass: float?}]
      This is the authoritative source for pseudo mapping (not step-level).
    """
    meta: ResourceMeta
    structure_id: Optional[str] = None  # Canonical structure reference (ULID)
    structure_name: Optional[str] = None  # Optional display name (cosmetic)
    # Legacy structure selector field removed - use structure_id (ULID) only
    mode: str = "normal"
    working_dir: str = "raw"
    steps: List[CalculationStepEntry] = field(default_factory=list)
    # Phase 2: Structure and engine metadata (immutable once set)
    structure_kind: Optional[str] = None  # "periodic" | "molecule"
    engine_family: Optional[str] = None  # Engine family (e.g., "qe", "pyscf")
    # Calculation-level pseudopotential mapping: element -> {pseudopot, mass, pseudo_sha256, pseudo_sha_family, pseudo_basename}
    # This is the authoritative source of truth for pseudo mapping.
    # Step-level species_overrides are deprecated (used only for backwards compat on load).
    # Constitution: Each entry must store filename, sha256 (strict), sha_family (physical equivalence).
    # Step0 refreshes these fields after preparing project/pseudo.
    species_map: Optional[Dict[str, Dict[str, Any]]] = None
    
    @property
    def id(self) -> str:
        return self.meta.id
    
    @property
    def name(self) -> str:
        return self.meta.name
    
    @property
    def slug(self) -> str:
        return self.meta.slug
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        DAG + ID-only constitution:
        - structure_id: ULID only (canonical reference)
        - steps: step_id (ULID) only
        - species_map: element -> {pseudopot, mass} (calc-level authority)
        - Do NOT write structure_name (cosmetic only, not used for resolution)
        """
        result: Dict[str, Any] = {
            "meta": self.meta.to_dict(),
            "mode": self.mode,
            "working_dir": self.working_dir,
            "steps": [s.to_dict() for s in self.steps],
        }
        # Write structure_id (canonical reference - ID only)
        # Do NOT write structure_name (cosmetic only, not used for resolution)
        if self.structure_id:
            result["structure_id"] = self.structure_id
        # Phase 2: Write structure_kind and engine_family (immutable metadata)
        if self.structure_kind:
            result["structure_kind"] = self.structure_kind
        if self.engine_family:
            result["engine_family"] = self.engine_family
        # Write species_map (calculation-level pseudo mapping)
        if self.species_map:
            result["species_map"] = self.species_map
        return result
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        default_name: str = "Calculation",
        default_path: str = ".",
        resolve_structure_selector: Optional[callable] = None,  # DEPRECATED - no longer used
        project_root: Optional[Path] = None,  # Optional project root for error messages
    ) -> "CalculationModel":
        """
        Create CalculationModel from dictionary.
        
        This method only supports the DAG + ULID model. Legacy calculations
        (with structure selector instead of structure_id) must be migrated first.
        
        Args:
            data: Dictionary containing calculation data
            default_name: Default name if not in data
            default_path: Default path if not in data
            resolve_structure_selector: DEPRECATED - no longer used (legacy compatibility removed)
            project_root: Optional project root for error messages
        
        Raises:
            LegacyProjectError: If legacy fields are detected (structure selector without structure_id)
        """
        from quantumvitas.core.exceptions import LegacyProjectError
        
        # Handle calculation section (for working_dir)
        calculation_section = data.get("calculation", {})
        working_dir = data.get("working_dir") or calculation_section.get("working_dir", "raw")
        
        # New format: structure_id (canonical) - REQUIRED if structure is referenced
        structure_id = data.get("structure_id") or calculation_section.get("structure_id")
        structure_name = data.get("structure_name") or calculation_section.get("structure_name")
        
        # Legacy format: structure selector (NOT SUPPORTED)
        structure = data.get("structure") or calculation_section.get("structure")
        
        # Detect legacy pattern: structure selector without structure_id
        if structure and not structure_id:
            error_msg = (
                "Legacy calculation detected: has 'structure' selector but no 'structure_id' ULID. "
                "Please run the migration script to upgrade this calculation."
            )
            if project_root:
                raise LegacyProjectError(project_root, error_msg)
            else:
                raise LegacyProjectError(Path(default_path) if default_path else Path.cwd(), error_msg)
        
        # Build meta
        meta = ResourceMeta.from_dict(
            data.get("meta"),
            kind="calculation",
            default_name=data.get("id") or default_name,
            default_path=default_path,
        )
        
        # Parse steps with legacy detection
        effective_project_root = project_root if project_root else (Path(default_path) if default_path else Path.cwd())
        steps = [CalculationStepEntry.from_dict(s, project_root=effective_project_root) for s in data.get("steps", [])]
        
        # Load species_map (calculation-level pseudo mapping)
        species_map = data.get("species_map") or calculation_section.get("species_map")
        
        # Phase 3A: Load structure_kind and engine_family with best-effort recovery
        structure_kind = data.get("structure_kind")
        engine_family = data.get("engine_family")
        
        # Best-effort recovery: Infer from steps if missing
        if structure_kind is None or engine_family is None:
            from quantumvitas.core.calc_identity import infer_calculation_identity
            
            # Determine calc_dir for inference (uses step.yaml files if available)
            calc_dir = None
            if project_root:
                # Try to find calculation directory from meta.path
                meta_dict = data.get("meta", {})
                calc_path = meta_dict.get("path", default_path)
                if calc_path:
                    calc_dir = (project_root / calc_path).resolve() if project_root else Path(default_path)
            else:
                calc_dir = Path(default_path) if default_path else Path.cwd()
            
            if calc_dir and calc_dir.exists():
                try:
                    inferred_kind, inferred_family = infer_calculation_identity(calc_dir, steps)
                    if structure_kind is None and inferred_kind is not None:
                        structure_kind = inferred_kind
                    if engine_family is None and inferred_family is not None:
                        engine_family = inferred_family
                except Exception:
                    # Best-effort: if inference fails, continue with defaults
                    pass
        
        # Final defaults if still missing
        if engine_family is None:
            if structure_kind == "molecule":
                engine_family = "pyscf"
            else:
                engine_family = "qe"  # Default for periodic or unknown
        if structure_kind is None:
            if engine_family == "pyscf":
                structure_kind = "molecule"
            else:
                structure_kind = "periodic"  # Default for qe, w90, etc.
        
        return cls(
            meta=meta,
            structure_id=structure_id,
            structure_name=structure_name,
            mode=data.get("mode", "normal"),
            working_dir=working_dir,
            steps=steps,
            structure_kind=structure_kind,
            engine_family=engine_family,
            species_map=species_map,
        )
    
    # Legacy resolve_step_ids method removed - all steps must have step_id (ULID) at load time


def load_calculation(
    path: Path, 
    project_root: Optional[Path] = None,
    resolve_structure_selector: Optional[callable] = None,  # DEPRECATED - no longer used
) -> CalculationModel:
    """
    Load a CalculationModel from a calculation.yaml file.
    
    This function only supports the DAG + ULID model. Legacy calculations
    (with structure selector instead of structure_id) will raise LegacyProjectError.
    
    Args:
        path: Path to calculation.yaml or calculation directory
        project_root: Project root for relative path calculation and error messages
        resolve_structure_selector: DEPRECATED - no longer used (legacy compatibility removed)
        
    Returns:
        CalculationModel instance
        
    Raises:
        LegacyProjectError: If legacy fields are detected in the calculation
        FileNotFoundError: If calculation.yaml does not exist
    """
    if path.is_dir():
        path = path / "calculation.yaml"
    
    if not path.exists():
        raise FileNotFoundError(f"Calculation file not found: {path}")
    
    data = yaml.safe_load(path.read_text()) or {}
    
    # Default name and path
    calculation_dir = path.parent
    default_name = data.get("id") or calculation_dir.name
    
    if project_root:
        try:
            default_path = ensure_relative_path(calculation_dir, base=project_root)
        except ValueError:
            default_path = calculation_dir.name
    else:
        default_path = calculation_dir.name
    
    # Load calculation model - will raise LegacyProjectError if legacy fields detected
    model = CalculationModel.from_dict(
        data, 
        default_name=default_name, 
        default_path=default_path,
        project_root=project_root or calculation_dir,
    )
    
    # If structure_id exists but structure_name is missing, look it up for display
    if model.structure_id and not model.structure_name and project_root:
        try:
            from quantumvitas.core.resolution import resolve_structure
            from quantumvitas.core.project_utils import load_project_config
            config = load_project_config(project_root)
            resolved = resolve_structure(project_root, model.structure_id, config=config)
            model.structure_name = resolved.meta.name
        except Exception:
            # If lookup fails, structure_name remains None (cosmetic field)
            pass
    
    return model


def save_calculation(model: CalculationModel, path: Path) -> None:
    """
    Save a CalculationModel to a calculation.yaml file.
    
    Uses CalcDoc + yaml_io for Journal integration (per Constitution §11.1).
    
    Phase 3A: Enforces immutability of structure_kind and engine_family.
    These fields cannot be changed after initial creation (first write).
    
    Args:
        model: CalculationModel to save
        path: Path to calculation.yaml or calculation directory
        
    Raises:
        ValueError: If attempting to change structure_kind or engine_family
    """
    from quantumvitas.core.yamldoc import CalcDoc
    from quantumvitas.core.yaml_io import save_yaml_doc
    import yaml
    
    if path.is_dir():
        path = path / "calculation.yaml"
    
    # Phase 3A: Enforce immutability of structure_kind and engine_family
    # If calculation.yaml exists, check that identity fields haven't changed
    if path.exists():
        try:
            existing_data = yaml.safe_load(path.read_text()) or {}
        except Exception:
            # Best-effort: if we can't read existing file, allow save (will overwrite)
            # This handles cases where file is corrupted or permissions issue
            existing_data = {}
        
        existing_structure_kind = existing_data.get("structure_kind")
        existing_engine_family = existing_data.get("engine_family")
        
        # Only enforce if existing values are not None (already set)
        if existing_structure_kind is not None:
            if model.structure_kind is not None and model.structure_kind != existing_structure_kind:
                raise ValueError(
                    f"Cannot change structure_kind from '{existing_structure_kind}' to '{model.structure_kind}'. "
                    f"structure_kind is immutable after calculation creation."
                )
        
        if existing_engine_family is not None:
            if model.engine_family is not None and model.engine_family != existing_engine_family:
                raise ValueError(
                    f"Cannot change engine_family from '{existing_engine_family}' to '{model.engine_family}'. "
                    f"engine_family is immutable after calculation creation."
                )
    
    # Use CalcDoc + yaml_io (journaled)
    calc_doc = CalcDoc(model.to_dict())
    save_yaml_doc(calc_doc, path)


def migrate_species_overrides_to_calc(
    calculation: CalculationModel,
    step_species_overrides_list: List[Optional[Dict[str, Dict[str, Any]]]],
) -> CalculationModel:
    """
    Migrate step-level species_overrides to calculation-level species_map.
    
    This migration is applied when loading a calculation that has:
    - No species_map set yet
    - Steps with species_overrides
    
    Args:
        calculation: The CalculationModel to migrate
        step_species_overrides_list: List of species_overrides from each step in order
            (None for steps without species_overrides)
    
    Returns:
        Updated CalculationModel with species_map populated
        
    Raises:
        ValueError: If species_overrides conflict across steps (different pseudo for same element)
    """
    # If species_map already set, no migration needed
    if calculation.species_map:
        return calculation
    
    # Collect all species_overrides from steps
    merged_map: Dict[str, Dict[str, Any]] = {}
    
    for i, step_overrides in enumerate(step_species_overrides_list):
        if not step_overrides:
            continue
        
        for element, settings in step_overrides.items():
            if element not in merged_map:
                # First occurrence of this element
                merged_map[element] = dict(settings)  # Copy to avoid mutation
            else:
                # Check for conflicts
                existing = merged_map[element]
                for key in ["pseudopot", "mass"]:
                    if key in settings and key in existing:
                        new_val = settings[key]
                        old_val = existing[key]
                        # For mass, allow small floating point differences
                        if key == "mass":
                            try:
                                if abs(float(new_val) - float(old_val)) > 1e-6:
                                    raise ValueError(
                                        f"Conflicting mass for element {element}: "
                                        f"{old_val} (earlier step) vs {new_val} (step {i+1})"
                                    )
                            except (TypeError, ValueError):
                                # If conversion fails, do string comparison
                                if str(new_val) != str(old_val):
                                    raise ValueError(
                                        f"Conflicting mass for element {element}: "
                                        f"{old_val} (earlier step) vs {new_val} (step {i+1})"
                                    )
                        elif key == "pseudopot":
                            if str(new_val) != str(old_val):
                                raise ValueError(
                                    f"Conflicting pseudopotential mapping for element {element}: "
                                    f"'{old_val}' (earlier step) vs '{new_val}' (step {i+1}). "
                                    "All steps in a calculation must use the same pseudopotential for each element."
                                )
                    elif key in settings and key not in existing:
                        # New key not in existing, add it
                        existing[key] = settings[key]
    
    # Update calculation with migrated species_map
    if merged_map:
        calculation.species_map = merged_map
    
    return calculation


# ---------------------------------------------------------------------------
# Project Model (extends existing Project)
# ---------------------------------------------------------------------------


@dataclass
class StructureEntry:
    """A structure entry in project.qv.yml."""
    meta: ResourceMeta
    file: str
    format: str = "auto"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        DAG + ID-only model: Stores only structure_id (ULID) for cross-resource reference.
        No duplicated name/slug/path - structure's own meta lives in structure JSON file.
        No file path - structure location resolved via ResourceIndex using structure_id.
        """
        result = {
            "structure_id": self.meta.id,  # ID-only reference (ULID)
        }
        # Format is optional metadata, not a cross-reference
        if self.format != "auto":
            result["format"] = self.format
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: Path) -> "StructureEntry":
        """
        Create StructureEntry from dictionary.
        
        DAG + ID-only model: Requires structure_id (ULID).
        Structure file location is resolved via ResourceIndex using structure_id.
        """
        # structure_id (ULID) is required
        structure_id = data.get("structure_id")
        if not structure_id:
            structure_id = data.get("id")  # Fallback to 'id' field if structure_id missing
        
        # Extract name/slug/path from meta for display
        meta_dict = data.get("meta") or {}
        name = data.get("name") or meta_dict.get("name")
        file_path = data.get("file") or meta_dict.get("path")
        
        # If we have an ID, try to load meta from the structure file
        if structure_id:
            # Try to find structure file and load its meta
            structures_dir = project_root / "structures"
            if structures_dir.exists():
                for struct_file in structures_dir.glob("*.json"):
                    try:
                        import json
                        struct_data = json.loads(struct_file.read_text())
                        struct_meta_dict = struct_data.get("__qv_meta__") or struct_data.get("meta")
                        if struct_meta_dict and struct_meta_dict.get("id") == structure_id:
                            # Found matching structure file - use its meta
                            meta = ResourceMeta.from_dict(
                                struct_meta_dict,
                                kind="structure",
                                default_name=struct_meta_dict.get("name", "Structure"),
                                default_path=struct_meta_dict.get("path", f"structures/{struct_file.name}"),
                            )
                            return cls(
                                meta=meta,
                                file=meta.path,
                                format=data.get("format", "auto"),
                            )
                    except Exception:
                        continue
        
        # Fallback: legacy format or structure file not found
        # Use provided name/path or defaults
        if not name:
            name = "Structure"
        if not file_path:
            file_path = f"structures/{slugify(name)}.json"
        
        # Try to load meta from structure file if it exists
        struct_file = project_root / file_path
        if struct_file.exists():
            try:
                import json
                struct_data = json.loads(struct_file.read_text())
                struct_meta_dict = struct_data.get("__qv_meta__") or struct_data.get("meta")
                if struct_meta_dict:
                    meta = ResourceMeta.from_dict(
                        struct_meta_dict,
                        kind="structure",
                        default_name=name,
                        default_path=file_path,
                    )
                    return cls(meta=meta, file=file_path, format=data.get("format", "auto"))
            except Exception:
                pass
        
        # Last resort: create meta from provided/defaults
        meta = ResourceMeta(
            id=meta_dict.get("id") or structure_id or generate_resource_id(),
            name=name,
            slug=meta_dict.get("slug") or slugify(name),
            path=file_path,
            kind="structure",
        )
        
        return cls(
            meta=meta,
            file=file_path,
            format=data.get("format", "auto"),
        )


@dataclass
class CalculationEntry:
    """A calculation entry in project.qv.yml."""
    meta: ResourceMeta
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.
        
        DAG + ID-only model: Stores only calculation_id (ULID) for cross-resource reference.
        No duplicated name/slug/path - calculation's own meta lives in calculation.yaml.
        No path - calculation location resolved via ResourceIndex using calculation_id.
        """
        return {
            "calculation_id": self.meta.id,  # ID-only reference (ULID)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: Path) -> "CalculationEntry":
        """
        Create CalculationEntry from dictionary.
        
        DAG + ID-only model: Requires calculation_id (ULID).
        Calculation file location is resolved via ResourceIndex using calculation_id.
        """
        # calculation_id (ULID) is required
        calculation_id = data.get("calculation_id")
        if not calculation_id:
            calculation_id = data.get("id")  # Fallback to 'id' field if calculation_id missing
        
        # Extract name/slug/path from meta for display
        meta_dict = data.get("meta") or {}
        name = data.get("name") or meta_dict.get("name")
        path = data.get("path") or meta_dict.get("path")
        
        # If we have an ID, try to load meta from calculation.yaml
        if calculation_id:
            # Try to find calculation.yaml and load its meta
            calculations_dir = project_root / "calculations"
            if calculations_dir.exists():
                for calculation_dir in calculations_dir.iterdir():
                    if not calculation_dir.is_dir():
                        continue
                    calculation_yaml = calculation_dir / "calculation.yaml"
                    if calculation_yaml.exists():
                        try:
                            import yaml
                            wf_data = yaml.safe_load(calculation_yaml.read_text()) or {}
                            wf_meta_dict = wf_data.get("meta", {})
                            if wf_meta_dict and wf_meta_dict.get("id") == calculation_id:
                                # Found matching calculation - use its meta
                                # But prefer name from entry (project.qv.yml) if it exists and is different from slug
                                entry_name = data.get("name") or meta_dict.get("name")
                                default_name = entry_name if entry_name and entry_name != wf_meta_dict.get("slug") else wf_meta_dict.get("name", "Calculation")
                                meta = ResourceMeta.from_dict(
                                    wf_meta_dict,
                                    kind="calculation",
                                    default_name=default_name,
                                    default_path=wf_meta_dict.get("path", f"calculations/{calculation_dir.name}"),
                                )
                                # Override with entry name if it's different from slug (preserves human-readable names)
                                if entry_name and entry_name != meta.slug:
                                    meta.name = entry_name
                                return cls(meta=meta)
                        except Exception:
                            continue
        
        # Fallback: legacy format or calculation.yaml not found
        # Use provided name/path or defaults
        if not name:
            name = "Calculation"
        if not path:
            path = f"calculations/{slugify(name)}"
        
        # Try to load meta from calculation.yaml if it exists
        calculation_yaml = project_root / path / "calculation.yaml"
        if calculation_yaml.exists():
            try:
                import yaml
                wf_data = yaml.safe_load(calculation_yaml.read_text()) or {}
                wf_meta_dict = wf_data.get("meta", {})
                if wf_meta_dict:
                    # Prefer name from entry (project.qv.yml) over calculation.yaml if entry has a human-readable name
                    entry_name = data.get("name") or meta_dict.get("name")
                    default_name = entry_name if entry_name and entry_name != wf_meta_dict.get("slug") else (name or wf_meta_dict.get("name", "Calculation"))
                    meta = ResourceMeta.from_dict(
                        wf_meta_dict,
                        kind="calculation",
                        default_name=default_name,
                        default_path=path,
                    )
                    # Override with entry name if it's different from slug (preserves human-readable names)
                    if entry_name and entry_name != meta.slug:
                        meta.name = entry_name
                    return cls(meta=meta)
            except Exception:
                pass
        
        # Last resort: create meta from provided/defaults
        meta = ResourceMeta(
            id=meta_dict.get("id") or calculation_id or generate_resource_id(),
            name=name,
            slug=meta_dict.get("slug") or slugify(name),
            path=path,
            kind="calculation",
        )
        
        return cls(meta=meta)


@dataclass
class ProjectModel:
    """
    Data model for a project (project.qv.yml).
    """
    meta: ResourceMeta
    root: Path
    structures: List[StructureEntry] = field(default_factory=list)
    calculations: List[CalculationEntry] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def id(self) -> str:
        return self.meta.id
    
    @property
    def name(self) -> str:
        return self.meta.name
    
    @property
    def slug(self) -> str:
        return self.meta.slug
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "project": {
                "name": self.meta.name,
                "meta": self.meta.to_dict(),
            },
            "settings": self.settings,
            "structures": [s.to_dict() for s in self.structures],
            "calculations": [w.to_dict() for w in self.calculations],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], root: Path) -> "ProjectModel":
        """Create ProjectModel from dictionary."""
        project_section = data.get("project", {})
        
        # Build meta
        meta = ResourceMeta.from_dict(
            project_section.get("meta"),
            kind="project",
            default_name=project_section.get("name") or root.name,
            default_path=".",
        )
        
        # Parse structures
        structures = [
            StructureEntry.from_dict(s, root) 
            for s in data.get("structures", [])
        ]
        
        # Parse calculations
        calculations = [
            CalculationEntry.from_dict(w, root)
            for w in data.get("calculations", [])
        ]
        
        return cls(
            meta=meta,
            root=root,
            structures=structures,
            calculations=calculations,
            settings=data.get("settings", {}),
        )
    
    def get_structure_by_selector(self, selector: str) -> Optional[StructureEntry]:
        """Find structure by ULID, slug, or name."""
        selector_lower = selector.lower()
        for s in self.structures:
            if s.meta.id == selector:  # ULID exact match
                return s
            if s.meta.slug == selector_lower:
                return s
            if s.meta.name.lower() == selector_lower:
                return s
        return None
    
    def get_calculation_by_selector(self, selector: str) -> Optional[CalculationEntry]:
        """Find calculation by ULID, slug, or name."""
        selector_lower = selector.lower()
        for w in self.calculations:
            if w.meta.id == selector:  # ULID exact match
                return w
            if w.meta.slug == selector_lower:
                return w
            if w.meta.name.lower() == selector_lower:
                return w
        return None


def load_project(path: Path) -> ProjectModel:
    """
    Load a ProjectModel from project.qv.yml.
    
    Args:
        path: Path to project root or project.qv.yml
        
    Returns:
        ProjectModel instance
    """
    if path.is_file():
        project_root = path.parent
        config_file = path
    else:
        project_root = path
        config_file = path / "project.qv.yml"
    
    if not config_file.exists():
        raise FileNotFoundError(f"project.qv.yml not found: {config_file}")
    
    data = yaml.safe_load(config_file.read_text()) or {}
    return ProjectModel.from_dict(data, project_root.resolve())


def save_project(model: ProjectModel, path: Optional[Path] = None) -> None:
    """
    Save a ProjectModel to project.qv.yml.
    
    Args:
        model: ProjectModel to save
        path: Path to project root (defaults to model.root)
    """
    root = path or model.root
    config_file = root / "project.qv.yml"
    config_file.write_text(yaml.safe_dump(model.to_dict(), sort_keys=False))


# ---------------------------------------------------------------------------
# Structure Model (for structure JSON files)
# ---------------------------------------------------------------------------


@dataclass
class StructureModel:
    """
    Data model for a structure file.
    
    The structure data itself is stored in pymatgen format,
    but we add a meta section for consistent identification.
    """
    meta: ResourceMeta
    data: Dict[str, Any]  # pymatgen structure dict
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = dict(self.data)
        result["meta"] = self.meta.to_dict()
        return result
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        default_name: str = "Structure",
        default_path: str = "structures/structure.json",
    ) -> "StructureModel":
        """Create StructureModel from dictionary."""
        # Check for both "meta" and "__qv_meta__" (structure file format)
        meta_dict = data.get("meta") or data.get("__qv_meta__")
        meta = ResourceMeta.from_dict(
            meta_dict,
            kind="structure",
            default_name=default_name,
            default_path=default_path,
        )
        
        # Remove meta from data to get pure structure
        structure_data = {k: v for k, v in data.items() if k not in ("meta", "__qv_meta__", "structure")}
        # If structure is wrapped in "structure" key, use that
        if "structure" in data and isinstance(data["structure"], dict):
            structure_data = data["structure"]
        
        return cls(meta=meta, data=structure_data)


def load_structure_model(path: Path, project_root: Optional[Path] = None) -> StructureModel:
    """
    Load a StructureModel from a JSON file.
    
    Args:
        path: Path to structure JSON file
        project_root: Project root for relative path calculation
        
    Returns:
        StructureModel instance
    """
    import json
    
    if not path.exists():
        raise FileNotFoundError(f"Structure file not found: {path}")
    
    data = json.loads(path.read_text())
    
    default_name = path.stem
    if project_root:
        try:
            default_path = ensure_relative_path(path, base=project_root)
        except ValueError:
            default_path = f"structures/{path.name}"
    else:
        default_path = f"structures/{path.name}"
    
    return StructureModel.from_dict(data, default_name=default_name, default_path=default_path)


def save_structure_model(model: StructureModel, path: Path) -> None:
    """
    Save a StructureModel to a JSON file.
    
    Args:
        model: StructureModel to save
        path: Path to output JSON file
    """
    import json
    
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.to_dict(), indent=2))


# ---------------------------------------------------------------------------
# Convenience functions for ensuring meta exists
# ---------------------------------------------------------------------------


def ensure_calculation_meta(
    calculation_dir: Path,
    project_root: Path,
    name: Optional[str] = None,
    calculation_id: Optional[str] = None,
) -> ResourceMeta:
    """
    Ensure a calculation has proper meta, creating/updating if needed.
    
    Returns the meta that should be used.
    """
    calculation_yaml = calculation_dir / "calculation.yaml"
    
    # Compute defaults
    default_name = name or calculation_dir.name
    default_slug = slugify(default_name)
    try:
        default_path = ensure_relative_path(calculation_dir, base=project_root)
    except ValueError:
        default_path = f"calculations/{default_slug}"
    
    # Load existing or create new
    if calculation_yaml.exists():
        model = load_calculation(calculation_yaml, project_root)
        # Ensure all fields are populated
        if not model.meta.id or len(model.meta.id) != 26:
            model.meta = ResourceMeta(
                id=calculation_id or generate_resource_id(),
                name=model.meta.name or default_name,
                slug=model.meta.slug or default_slug,
                path=model.meta.path or default_path,
                kind="calculation",
            )
            save_calculation(model, calculation_yaml)
        return model.meta
    else:
        # Create new
        meta = ResourceMeta(
            id=calculation_id or generate_resource_id(),
            name=default_name,
            slug=default_slug,
            path=default_path,
            kind="calculation",
        )
        model = CalculationModel(meta=meta)
        save_calculation(model, calculation_yaml)
        return meta

