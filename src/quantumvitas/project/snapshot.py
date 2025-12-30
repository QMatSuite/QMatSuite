"""
Project snapshot format for exporting and importing complete projects.

A snapshot is a single YAML file that contains all project metadata, structures,
calculations, and step specifications needed to recreate a project. Pseudopotential
filenames are preserved but file contents are NOT embedded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from quantumvitas.core.models import (
    ProjectModel,
    StructureModel,
    CalculationModel,
    load_project,
    load_structure_model,
    load_calculation,
    save_project,
    save_structure_model,
    save_calculation,
)
from quantumvitas.core.resources import (
    ResourceMeta,
    ensure_relative_path,
    generate_resource_id,
    slugify,
)
from quantumvitas.calculation.structure_steps import StructureStepSpec

# Structure file format constants
STRUCTURE_META_KEY = "__qv_meta__"
STRUCTURE_DATA_KEY = "structure"


@dataclass
class ProjectSnapshot:
    """
    Snapshot of a complete QuantumVITAS project.
    
    Contains all metadata, structures, calculations, and steps needed to
    recreate the project. ULIDs are preserved for reference but will be
    regenerated when materializing the project.
    
    The `meta` field (optional) contains demo-specific metadata for gallery display:
    - id: Demo identifier (e.g., "si_bands_demo")
    - title: Display title (e.g., "Silicon band structure")
    - subtitle: Short description (e.g., "SCF → NSCF → Bands")
    - tags: List of tags (e.g., ["bands", "Si", "PW", "tutorial"])
    - recommended_analysis: Default analysis type (e.g., "bands", "dos")
    - difficulty: Difficulty level (e.g., "beginner", "intermediate", "advanced")
    """
    version: int = 1
    project: Dict[str, Any] = field(default_factory=dict)
    structures: List[Dict[str, Any]] = field(default_factory=list)
    calculations: List[Dict[str, Any]] = field(default_factory=list)
    pseudo: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: Dict[str, Any] = {
            "version": self.version,
            "project": self.project,
            "structures": self.structures,
            "calculations": self.calculations,
        }
        if self.pseudo:
            result["pseudo"] = self.pseudo
        if self.extra:
            result["extra"] = self.extra
        if self.meta:
            result["meta"] = self.meta
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectSnapshot":
        """
        Create ProjectSnapshot from dictionary.
        
        Supports both old format (project/structures/calculations at top level)
        and new minimal format (snapshot_meta + files list).
        """
        # Check for new minimal format (snapshot_meta + files)
        if "snapshot_meta" in data and "files" in data:
            # New minimal format: convert files list to old format structure
            return cls._from_minimal_format(data)
        
        # Old format: project/structures/calculations at top level
        return cls(
            version=data.get("version", 1),
            project=data.get("project", {}),
            structures=data.get("structures", []),
            calculations=data.get("calculations", []),
            pseudo=data.get("pseudo"),
            extra=data.get("extra"),
            meta=data.get("meta"),
        )
    
    @classmethod
    def _from_minimal_format(cls, data: Dict[str, Any]) -> "ProjectSnapshot":
        """
        Convert new minimal snapshot format (snapshot_meta + files) to ProjectSnapshot.
        
        The minimal format has:
        - snapshot_meta: {version, created_at, ...}
        - files: [{path: "project.qv.yml", content: "..."}, ...]
        
        We need to parse the YAML content from files to reconstruct the old format structure.
        """
        import yaml
        
        snapshot_meta = data.get("snapshot_meta", {})
        files = data.get("files", [])
        
        # Build a map of file paths to content
        file_map: Dict[str, str] = {}
        for file_entry in files:
            path = file_entry.get("path", "")
            content = file_entry.get("content", "")
            if path and content:
                file_map[path] = content
        
        # Parse project.qv.yml to get project metadata
        project_data = {}
        if "project.qv.yml" in file_map:
            try:
                project_data = yaml.safe_load(file_map["project.qv.yml"]) or {}
            except Exception:
                project_data = {}
        
        # Parse structures
        structures_data = []
        for file_path, content in file_map.items():
            if file_path.startswith("structures/") and file_path.endswith(".json"):
                try:
                    import json
                    struct_data = json.loads(content)
                    # Extract meta if present
                    meta = struct_data.get("__qv_meta__", {})
                    # Extract structure data
                    structure_data = struct_data.get("structure", struct_data)
                    structures_data.append({
                        "meta": meta,
                        "data": structure_data,
                    })
                except Exception:
                    pass  # Skip malformed structure files
        
        # Parse calculations
        calculations_data = []
        for file_path, content in file_map.items():
            if file_path.endswith("/calculation.yaml"):
                try:
                    calculation_data = yaml.safe_load(content) or {}
                    # Extract steps from step files
                    calculation_dir = file_path.rsplit("/", 1)[0]
                    steps_data = []
                    for step_path, step_content in file_map.items():
                        if step_path.startswith(calculation_dir + "/steps/") and step_path.endswith(".step.yaml"):
                            try:
                                step_data = yaml.safe_load(step_content) or {}
                                steps_data.append(step_data)
                            except Exception:
                                pass
                    calculation_data["steps"] = steps_data
                    calculations_data.append(calculation_data)
                except Exception:
                    pass  # Skip malformed calculation files
        
        return cls(
            version=snapshot_meta.get("version", 1),
            project=project_data,
            structures=structures_data,
            calculations=calculations_data,
            pseudo=None,  # Pseudo files not embedded in minimal format
            extra=None,
            meta=snapshot_meta,  # Use snapshot_meta as meta
        )


def export_project_to_snapshot(project_root: Path) -> ProjectSnapshot:
    """
    Export a project directory to a ProjectSnapshot.
    
    Reads project.qv.yml, all structures, calculations, and step specs
    and packages them into a single snapshot object.
    
    Args:
        project_root: Path to project root directory
        
    Returns:
        ProjectSnapshot containing all project data
    """
    project_root = project_root.resolve()
    
    # Load project model
    project_model = load_project(project_root)
    
    # Export project metadata
    project_data = {
        "meta": project_model.meta.to_dict(),
        "settings": project_model.settings,
    }
    
    # Export structures
    # Use structure's meta.path (ID-only model) instead of legacy file field
    structures_data = []
    for struct_entry in project_model.structures:
        # Use meta.path (canonical) or fall back to legacy file field for location
        struct_path = project_root / (struct_entry.meta.path or struct_entry.file)
        if struct_path.exists():
            # Get structure data (pymatgen format)
            # Handle both __qv_meta__ wrapper and direct structure dict
            struct_file_data = json.loads(struct_path.read_text())
            if STRUCTURE_META_KEY in struct_file_data and STRUCTURE_DATA_KEY in struct_file_data:
                structure_data = struct_file_data[STRUCTURE_DATA_KEY]
            else:
                # Direct structure dict (remove meta if present)
                structure_data = {k: v for k, v in struct_file_data.items() if k not in ("meta", STRUCTURE_META_KEY)}
            
            # Use struct_entry.meta (from project.qv.yml) for name, as it has the correct name
            # The structure file might have name=slug if it was created with old format
            structures_data.append({
                "meta": struct_entry.meta.to_dict(),
                "data": structure_data,
            })
    
    # Export calculations and their steps
    # Use Project.open() and Calculation.from_yaml() to load calculations (DAG + ULID model only)
    from quantumvitas.project.model import Project
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.core.project_utils import load_project_config
    
    try:
        project = Project.open(project_root)
    except Exception:
        # Fall back to basic loading if Project.open() fails
        project = None
    
    # Load raw config to check for legacy name fields in calculation entries
    raw_config = load_project_config(project_root)
    # Build mapping from calculation ID to raw entry (handle calculation_id, id, and meta.id keys)
    raw_calculation_entries = {}
    for entry in raw_config.get("calculations", []):
        wf_id = entry.get("calculation_id") or entry.get("id") or (entry.get("meta") or {}).get("id")
        if wf_id:
            raw_calculation_entries[wf_id] = entry
    
    calculations_data = []
    for calculation_entry in project_model.calculations:
        calculation_path = project_root / calculation_entry.meta.path / "calculation.yaml"
        if not calculation_path.exists():
            continue
        
        calculation_dir = calculation_path.parent
        
        # Try to load via Calculation.from_yaml (with migration support) if project is available
        # Use inspection mode for snapshot export (no step materialization needed)
        if project:
            try:
                calculation = Calculation.from_yaml(calculation_dir, project, materialize_steps=False)
                # Extract calculation model data from the Calculation object
                calculation_model = load_calculation(calculation_path, project_root)
                # But use the actual Step objects from Calculation for step export
                calculation_steps = calculation.steps
            except Exception:
                # Fall back to basic load_calculation if Calculation.from_yaml fails
                calculation_model = load_calculation(calculation_path, project_root)
                calculation_steps = None
        else:
            # Fall back to basic loading
            calculation_model = load_calculation(calculation_path, project_root)
            calculation_steps = None
        
        # Export calculation metadata
        # Prefer name from raw project.qv.yml entry (legacy format) as it may have the correct human-readable name
        # calculation.yaml might have name=slug if it was created with old format
        # Use calculation_model.meta for other fields (slug, path) as calculation.yaml is the source of truth for those
        calculation_meta_dict = calculation_model.meta.to_dict()
        # Check raw project.qv.yml entry for legacy name field
        # Try both calculation_entry.meta.id and calculation_model.meta.id as keys
        raw_entry = raw_calculation_entries.get(calculation_entry.meta.id) or raw_calculation_entries.get(calculation_model.meta.id)
        legacy_name = None
        if raw_entry:
            # Check for legacy 'name' field at top level or in meta
            legacy_name = raw_entry.get("name") or (raw_entry.get("meta") or {}).get("name")
        # Also check calculation_entry.meta.name directly (might be set from registry)
        if not legacy_name:
            legacy_name = calculation_entry.meta.name
        # Override name with legacy name if it exists and is different from slug (preserves human-readable names)
        if legacy_name and legacy_name != calculation_model.meta.slug and legacy_name != calculation_model.meta.name:
            calculation_meta_dict["name"] = legacy_name
        # Preserve the calculation ID from calculation_entry if it's different (shouldn't happen, but be safe)
        if calculation_entry.meta.id and calculation_entry.meta.id != calculation_model.meta.id:
            calculation_meta_dict["id"] = calculation_entry.meta.id
        
        calculation_dict = {
            "meta": calculation_meta_dict,
            "mode": calculation_model.mode,
            "working_dir": calculation_model.working_dir,
            "steps": [],
        }
        # Export structure_id (canonical reference - ID only)
        # Do NOT export structure_name or structure selector (violates DAG + ID-only constitution)
        if calculation_model.structure_id:
            calculation_dict["structure_id"] = calculation_model.structure_id
        
        # Export species_map (calc-level pseudo mapping)
        # If species_map is already set on the calculation model, use it
        # Otherwise, we'll compute it from step-level species_overrides after collecting steps
        calc_species_map = calculation_model.species_map
        
        # Export each step
        # Strategy: Scan step files directly and export them, matching by ID when possible
        # This handles cases where calculation.yaml step_id doesn't match step file meta.id
        # Create resolver for legacy structure selector normalization
        from quantumvitas.core.resolution import make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        try:
            config = load_project_config(project_root)
            resolver = make_structure_selector_resolver(project_root, config=config)
        except Exception:
            resolver = None
        
        # Export steps in the order specified in calculation.yaml
        # Use calculation_model.steps to get the correct order (from calculation.yaml)
        steps_dir = calculation_dir / "steps"
        exported_step_ids = set()
        
        # Build a map of step_id -> step_file_path for quick lookup
        step_file_map = {}
        if steps_dir.exists():
            for step_file in steps_dir.glob("*.step.yaml"):
                try:
                    # Load step spec to get its ID
                    step_spec = StructureStepSpec.from_yaml(step_file, resolve_structure_selector=resolver)
                    step_id = step_spec.meta.id
                    step_file_map[step_id] = step_file
                except Exception:
                    # Skip step files that can't be loaded
                    continue
        
        # Export steps in the order from calculation.yaml
        # Use calculation_model.steps which preserves the order from calculation.yaml
        for step_entry in calculation_model.steps:
            step_id = step_entry.step_id  # DAG + ULID model: only step_id (ULID) is used
            if not step_id:
                continue
            
            # Find the step file for this step_id
            step_file = step_file_map.get(step_id)
            if not step_file:
                # Step file not found - skip this step
                continue
            
            # Skip if already exported (shouldn't happen, but be safe)
            if step_id in exported_step_ids:
                continue
            
            try:
                # Load step spec (DAG + ULID model: structure_id is already in spec)
                step_spec = StructureStepSpec.from_yaml(step_file, resolve_structure_selector=resolver)
                
                # Export step data (ID-only model: structure_id, no structure selector)
                step_dict = step_spec.to_dict()
                calculation_dict["steps"].append(step_dict)
                exported_step_ids.add(step_id)
            except Exception:
                # Skip step files that can't be loaded
                continue
        
        # If calc_species_map was not set from calculation model, compute it from step-level species_overrides
        # This migrates legacy projects to the new semantics on export
        if not calc_species_map and calculation_dict["steps"]:
            step_species_overrides_list = [step.get("species_overrides") for step in calculation_dict["steps"]]
            if any(step_species_overrides_list):
                from quantumvitas.core.models import migrate_species_overrides_to_calc
                # Create a temporary calc model for migration
                temp_calc = CalculationModel(
                    meta=ResourceMeta(id="temp", name="temp", slug="temp", path="temp", kind="calculation"),
                )
                temp_calc = migrate_species_overrides_to_calc(temp_calc, step_species_overrides_list)
                calc_species_map = temp_calc.species_map
        
        # Enhance species_map with sha256 and sha_family if missing (migration from legacy format)
        # This ensures exported snapshots have complete triplet: pseudo_basename + pseudo_sha256 + pseudo_sha_family
        if calc_species_map:
            from quantumvitas.core.pseudo_provenance import compute_sha256_file
            from quantumvitas.core.pseudo_libinfo import compute_sha_family_file
            
            # Try multiple locations for pseudo files
            project_pseudo_dir = project_root / "pseudo"
            
            # Try to find resources/pseudo directory
            # Method 1: Try to find repo root and check resources/pseudo
            repo_root = project_root
            resources_pseudo_dir = None
            while repo_root != repo_root.parent:
                candidate_resources = repo_root / "resources" / "pseudo"
                if candidate_resources.exists():
                    resources_pseudo_dir = candidate_resources
                    break
                # Check for repo markers
                if (repo_root / "pyproject.toml").exists() or (repo_root / "project.qv.yml").exists():
                    candidate_resources = repo_root / "resources" / "pseudo"
                    if candidate_resources.exists():
                        resources_pseudo_dir = candidate_resources
                    break
                repo_root = repo_root.parent
            
            # Method 2: Try using get_resources_dir if available
            if not resources_pseudo_dir:
                try:
                    from quantumvitas.core.resources import get_resources_dir
                    resources_base = get_resources_dir()
                    candidate_resources = resources_base / "pseudo"
                    if candidate_resources.exists():
                        resources_pseudo_dir = candidate_resources
                except (ImportError, AttributeError):
                    pass
            
            for element, entry in calc_species_map.items():
                if not isinstance(entry, dict):
                    continue
                
                # Get basename from entry
                basename = entry.get("pseudo_basename") or entry.get("pseudopot")
                if not basename:
                    continue
                
                # Check if sha256 or sha_family is missing
                has_sha256 = "pseudo_sha256" in entry and entry["pseudo_sha256"]
                has_sha_family = "pseudo_sha_family" in entry and entry["pseudo_sha_family"]
                
                # If either is missing, try to compute from file
                if not has_sha256 or not has_sha_family:
                    # Try project/pseudo first, then resources/pseudo
                    pseudo_file = None
                    if (project_pseudo_dir / basename).exists():
                        pseudo_file = project_pseudo_dir / basename
                    elif resources_pseudo_dir and resources_pseudo_dir.exists() and (resources_pseudo_dir / basename).exists():
                        pseudo_file = resources_pseudo_dir / basename
                    
                    if pseudo_file and pseudo_file.is_file():
                        try:
                            if not has_sha256:
                                entry["pseudo_sha256"] = compute_sha256_file(pseudo_file)
                            if not has_sha_family:
                                entry["pseudo_sha_family"] = compute_sha_family_file(pseudo_file)
                            # Also ensure pseudo_basename is set
                            if "pseudo_basename" not in entry:
                                entry["pseudo_basename"] = basename
                        except Exception:
                            # If computation fails, leave fields missing (will be filled at runtime)
                            pass
        
        # Add species_map to calculation dict (authoritative source of truth)
        if calc_species_map:
            calculation_dict["species_map"] = calc_species_map
        
        calculations_data.append(calculation_dict)
    
    # Export pseudo file list (filenames only, no content)
    pseudo_data = None
    pseudo_dir = project_root / "pseudo"
    if pseudo_dir.exists() and pseudo_dir.is_dir():
        pseudo_files = [p.name for p in pseudo_dir.iterdir() if p.is_file()]
        if pseudo_files:
            pseudo_data = {
                "directory": "pseudo",
                "files": sorted(pseudo_files),
            }
    
    return ProjectSnapshot(
        version=1,
        project=project_data,
        structures=structures_data,
        calculations=calculations_data,
        pseudo=pseudo_data,
    )


def materialize_project_from_snapshot(
    snapshot: ProjectSnapshot,
    parent_dir: Path,
    new_project_name: Optional[str] = None,
) -> Path:
    """
    Create a new project directory from a ProjectSnapshot.
    
    Generates new ULIDs for all resources and rewrites references
    to maintain consistency.
    
    Args:
        snapshot: ProjectSnapshot to materialize
        parent_dir: Directory where the new project will be created
        new_project_name: Optional name for the new project (defaults to snapshot name)
        
    Returns:
        Path to the new project root
    """
    parent_dir = parent_dir.resolve()
    
    # Determine project name and directory
    project_meta = snapshot.project.get("meta", {})
    original_name = project_meta.get("name", "project")
    project_name = new_project_name or original_name
    project_slug = slugify(project_name)
    
    # Find a unique directory name (add suffix if needed)
    project_dir = parent_dir / project_slug
    if project_dir.exists():
        # Directory exists - find unique name with suffix
        suffix = 2
        while True:
            candidate = parent_dir / f"{project_slug}-{suffix}"
            if not candidate.exists():
                project_dir = candidate
                project_name = f"{project_name}-{suffix}"
                project_slug = f"{project_slug}-{suffix}"
                break
            suffix += 1
            if suffix > 100:  # Safety limit
                raise RuntimeError(f"Could not find unique project name for {project_slug}")
    
    project_dir.mkdir(parents=True, exist_ok=False)
    
    # Build ULID mapping: old_id -> new_id
    id_mapping: Dict[str, str] = {}
    
    # Map project ID
    old_project_id = project_meta.get("id")
    if old_project_id:
        new_project_id = generate_resource_id()
        id_mapping[old_project_id] = new_project_id
    
    # Map structure IDs
    structure_slug_to_new_id: Dict[str, str] = {}
    for struct_data in snapshot.structures:
        struct_meta = struct_data.get("meta", {})
        old_struct_id = struct_meta.get("id")
        struct_slug = struct_meta.get("slug") or slugify(struct_meta.get("name", "structure"))
        
        if old_struct_id:
            new_struct_id = generate_resource_id()
            id_mapping[old_struct_id] = new_struct_id
            structure_slug_to_new_id[struct_slug] = new_struct_id
    
    # Map calculation IDs
    calculation_slug_to_new_id: Dict[str, str] = {}
    for calculation_data in snapshot.calculations:
        calculation_meta = calculation_data.get("meta", {})
        old_calculation_id = calculation_meta.get("id")
        calculation_slug = calculation_meta.get("slug") or slugify(calculation_meta.get("name", "calculation"))
        
        if old_calculation_id:
            new_calculation_id = generate_resource_id()
            id_mapping[old_calculation_id] = new_calculation_id
            calculation_slug_to_new_id[calculation_slug] = new_calculation_id
    
    # Map step IDs
    for calculation_data in snapshot.calculations:
        for step_data in calculation_data.get("steps", []):
            step_meta = step_data.get("meta", {})
            old_step_id = step_meta.get("id")
            if old_step_id:
                new_step_id = generate_resource_id()
                id_mapping[old_step_id] = new_step_id
    
    # Create project.qv.yml
    new_project_meta = ResourceMeta(
        id=new_project_id,
        name=project_name,
        slug=project_slug,
        path=".",
        kind="project",
    )
    
    project_model = ProjectModel(
        meta=new_project_meta,
        root=project_dir,
        structures=[],
        calculations=[],
        settings=snapshot.project.get("settings", {}),
    )
    
    # Create structures
    structures_dir = project_dir / "structures"
    structures_dir.mkdir(exist_ok=True)
    
    for struct_data in snapshot.structures:
        struct_meta = struct_data.get("meta", {})
        struct_name = struct_meta.get("name", "structure")
        struct_slug = struct_meta.get("slug") or slugify(struct_name)
        old_struct_id = struct_meta.get("id")
        new_struct_id = id_mapping.get(old_struct_id, generate_resource_id())
        
        # Create structure file
        struct_file = structures_dir / f"{struct_slug}.json"
        
        # Prepare structure JSON with meta wrapper
        structure_json = {
            STRUCTURE_META_KEY: {
                "id": new_struct_id,
                "name": struct_name,
                "slug": struct_slug,
                "path": f"structures/{struct_slug}.json",
                "kind": "structure",
            },
            STRUCTURE_DATA_KEY: struct_data.get("data", {}),
        }
        
        struct_file.write_text(json.dumps(structure_json, indent=2))
        
        # Add to project model
        from quantumvitas.core.models import StructureEntry
        struct_entry = StructureEntry(
            meta=ResourceMeta(
                id=new_struct_id,
                name=struct_name,
                slug=struct_slug,
                path=f"structures/{struct_slug}.json",
                kind="structure",
            ),
            file=f"structures/{struct_slug}.json",
            format="auto",
        )
        project_model.structures.append(struct_entry)
    
    # Create calculations and steps
    calculations_dir = project_dir / "calculations"
    calculations_dir.mkdir(exist_ok=True)
    
    for calculation_data in snapshot.calculations:
        calculation_meta = calculation_data.get("meta", {})
        calculation_name = calculation_meta.get("name") or calculation_meta.get("slug") or "calculation"
        calculation_slug = calculation_meta.get("slug") or slugify(calculation_name)
        old_calculation_id = calculation_meta.get("id")
        new_calculation_id = id_mapping.get(old_calculation_id, generate_resource_id())
        
        # Create calculation directory
        calculation_path = calculations_dir / calculation_slug
        calculation_path.mkdir(exist_ok=True)
        steps_dir = calculation_path / "steps"
        steps_dir.mkdir(exist_ok=True)
        (calculation_path / "raw").mkdir(exist_ok=True)
        
        # Resolve structure reference from snapshot
        # New format: structure_id (canonical)
        calculation_structure_id = calculation_data.get("structure_id")
        calculation_structure_name = calculation_data.get("structure_name")
        # Legacy format: structure selector
        calculation_structure_selector = calculation_data.get("structure")
        
        # If structure_id is present, map it to the new structure ID
        if calculation_structure_id:
            # Find the structure in the snapshot by old ID
            structure_found = False
            for struct_data in snapshot.structures:
                struct_meta = struct_data.get("meta", {})
                if struct_meta.get("id") == calculation_structure_id:
                    # Map to new structure ID
                    new_structure_id = id_mapping.get(calculation_structure_id)
                    if new_structure_id:
                        calculation_structure_id = new_structure_id
                        calculation_structure_name = struct_meta.get("name")
                    structure_found = True
                    break
            if not structure_found:
                # Structure ID not found in snapshot - this shouldn't happen, but handle gracefully
                calculation_structure_id = None
        
        # If only structure selector is present, try to resolve it to structure_id
        elif calculation_structure_selector:
            # Try to find structure by slug/name in the snapshot
            for struct_data in snapshot.structures:
                struct_meta = struct_data.get("meta", {})
                struct_slug = struct_meta.get("slug") or slugify(struct_meta.get("name", ""))
                struct_name = struct_meta.get("name", "")
                old_struct_id = struct_meta.get("id")
                
                if (struct_slug == calculation_structure_selector or 
                    struct_name.lower() == calculation_structure_selector.lower()):
                    # Found matching structure - use its new ID
                    if old_struct_id:
                        calculation_structure_id = id_mapping.get(old_struct_id)
                        calculation_structure_name = struct_name
                    break
        
        # Collect species_overrides from steps and migrate to calc-level species_map
        # This handles backwards compatibility: old snapshots with step-level species_overrides
        # are migrated to new calc-level species_map on materialization.
        step_species_overrides_list = []
        for step_data in calculation_data.get("steps", []):
            step_species_overrides_list.append(step_data.get("species_overrides"))
        
        # Migrate to calc-level species_map if needed
        # calculation_data may already have species_map if from a new-format snapshot
        calc_species_map = calculation_data.get("species_map")
        if not calc_species_map and step_species_overrides_list:
            from quantumvitas.core.models import migrate_species_overrides_to_calc
            # Create a temporary calc model for migration
            temp_calc_for_migration = CalculationModel(
                meta=ResourceMeta(
                    id=new_calculation_id,
                    name=calculation_name,
                    slug=calculation_slug,
                    path=f"calculations/{calculation_slug}",
                    kind="calculation",
                ),
            )
            temp_calc_for_migration = migrate_species_overrides_to_calc(
                temp_calc_for_migration, step_species_overrides_list
            )
            calc_species_map = temp_calc_for_migration.species_map
        
        # Clean up legacy pseudo_sha_token field if present (migration: sha_token → sha_family)
        # Remove pseudo_sha_token and ensure pseudo_sha_family is present
        if calc_species_map:
            for element, entry in calc_species_map.items():
                if not isinstance(entry, dict):
                    continue
                
                # Remove legacy pseudo_sha_token field if present
                if "pseudo_sha_token" in entry:
                    # Legacy field - remove it (sha_family should be used instead)
                    del entry["pseudo_sha_token"]
                
                # Note: We don't compute sha_family here during materialization
                # because pseudo files may not exist yet (they're resolved at runtime via Step0)
                # If sha_family is missing, it will be computed during Step0 refresh
        
        # Create calculation.yaml
        calculation_model = CalculationModel(
            meta=ResourceMeta(
                id=new_calculation_id,
                name=calculation_name,
                slug=calculation_slug,
                path=f"calculations/{calculation_slug}",
                kind="calculation",
            ),
            structure_id=calculation_structure_id,
            # structure_name and structure are in-memory only (not persisted to YAML)
            structure_name=calculation_structure_name,
            # structure selector field removed - use structure_id (ULID) only
            mode=calculation_data.get("mode", "normal"),
            working_dir=calculation_data.get("working_dir", "raw"),
            steps=[],
            species_map=calc_species_map,  # Calc-level pseudo mapping
        )
        
        # Create step files
        for step_data in calculation_data.get("steps", []):
            step_meta = step_data.get("meta", {})
            step_name = step_meta.get("name", step_data.get("step_type", "step"))
            step_slug = step_meta.get("slug") or slugify(step_name)
            old_step_id = step_meta.get("id")
            new_step_id = id_mapping.get(old_step_id, generate_resource_id())
            
            # Create step spec with new IDs
            # DAG + ID-only model: Step YAML must NOT contain structure_id or parent_calculation_id
            # Structure is resolved via calculation.structure_id at runtime
            # Parent calculation is implicit from step file location
            step_spec_dict = dict(step_data)
            
            # Remove structure_id and parent_calculation_id from dict (DAG invariant)
            step_spec_dict.pop("structure_id", None)
            step_spec_dict.pop("parent_calculation_id", None)
            step_spec_dict.pop("structure", None)  # Also remove legacy structure selector
            
            # Update meta with new IDs
            step_spec_dict["meta"] = {
                "id": new_step_id,
                "name": step_name,
                "slug": step_slug,
                "path": f"calculations/{calculation_slug}/steps/{step_slug}.step.yaml",
                "kind": "step",
            }
            
            # Create StructureStepSpec object to ensure proper serialization
            # This will strip any remaining structure_id/parent_calculation_id via to_dict()
            from quantumvitas.calculation.structure_steps import StructureStepSpec
            step_spec = StructureStepSpec.from_dict(step_spec_dict)
            
            # Write step file using to_dict() which enforces DAG invariants
            step_file = steps_dir / f"{step_slug}.step.yaml"
            step_file.write_text(yaml.safe_dump(step_spec.to_dict(), sort_keys=False))
            
            # Add to calculation steps list using step_id (ULID) from step meta
            from quantumvitas.core.models import CalculationStepEntry
            step_meta = step_spec_dict.get("meta", {})
            step_id = step_meta.get("id") or step_spec_dict.get("id")
            calculation_model.steps.append(CalculationStepEntry(
                step_id=step_id,  # Use ULID from step meta (canonical reference)
                type=step_data.get("step_type"),
                # step_file is NOT stored - step location resolved via registry using step_id
            ))
        
        # Save calculation.yaml
        save_calculation(calculation_model, calculation_path / "calculation.yaml")
        
        # Add to project model
        from quantumvitas.core.models import CalculationEntry
        calculation_entry = CalculationEntry(
            meta=ResourceMeta(
                id=new_calculation_id,
                name=calculation_name,
                slug=calculation_slug,
                path=f"calculations/{calculation_slug}",
                kind="calculation",
            ),
        )
        project_model.calculations.append(calculation_entry)
    
    # Save project.qv.yml
    save_project(project_model, project_dir)
    
    # Create pseudo directory only (empty) - pseudo files are resolved at RUN time only
    # Snapshots store pseudo filenames as metadata, but do NOT embed or copy content.
    # The runner resolves/copies needed pseudos into project/pseudo as part of execution closure.
    if snapshot.pseudo:
        pseudo_dir = project_dir / snapshot.pseudo.get("directory", "pseudo")
        pseudo_dir.mkdir(exist_ok=True)
        # NOTE: We intentionally do NOT download or copy pseudo files here.
        # Pseudo materialization happens at run time via the runner.
    
    return project_dir

