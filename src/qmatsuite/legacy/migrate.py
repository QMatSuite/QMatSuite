"""
Migration script for legacy QMatSuite projects.

This script migrates legacy projects (using structure/step_file fields)
to the new DAG + ULID model (structure_ulid/step_ulid ULIDs).

Usage:
    python -m qmatsuite.legacy.migrate <project_root>

Or from Python:
    from qmatsuite.legacy.migrate import migrate_legacy_project
    migrate_legacy_project(Path("/path/to/project"))
"""

from __future__ import annotations

import shutil
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from qmatsuite.core.resources import generate_resource_id, meta_from_name, slugify
from qmatsuite.core.project_utils import load_project_config, save_project_config
from qmatsuite.core.resolution import build_resource_index, resolve_structure
from qmatsuite.core.models import load_calculation, save_calculation, CalculationModel, CalculationStepEntry
from qmatsuite.calculation.structure_steps import StructureStepSpec


def migrate_legacy_project(project_root: Path) -> None:
    """
    Migrate a legacy QMatSuite project at project_root to the DAG + ULID layout.
    
    This function is intended for manual one-shot use by the developer.
    
    Migration steps:
    1. Backup original project.qms.yml and calculation.yaml files
    2. Ensure all structures have ULID meta.ulid
    3. For each calculation:
       - Ensure meta.ulid is a ULID
       - Ensure meta.slug exists
       - Convert structure selector to structure_ulid (ULID)
       - Convert step entries to use step_ulid (ULID)
    4. Remove legacy fields (structure, step_file) from YAML files
    
    Args:
        project_root: Path to the project root directory
        
    Raises:
        FileNotFoundError: If project.qms.yml is not found
        ValueError: If migration fails
    """
    project_root = Path(project_root).resolve()
    config_file = project_root / "project.qms.yml"
    
    if not config_file.exists():
        raise FileNotFoundError(f"project.qms.yml not found at {config_file}")
    
    print(f"Migrating project at {project_root}...")
    
    # Step 1: Backup original files
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = project_root / f".migration_backup_{timestamp}"
    backup_dir.mkdir(exist_ok=True)
    
    print(f"Creating backup in {backup_dir}...")
    shutil.copy2(config_file, backup_dir / "project.qms.yml")
    
    # Step 2: Load project config
    config = load_project_config(project_root)
    
    # Step 3: Migrate structures (ensure ULID meta.ulid)
    structures = config.get("structures", [])
    structures_dir = project_root / "structures"
    
    for struct_entry in structures:
        struct_file = struct_entry.get("file")
        if not struct_file:
            continue
        
        struct_path = (project_root / struct_file).resolve()
        if not struct_path.exists():
            continue
        
        # Load structure JSON to check/update meta
        try:
            import json
            struct_data = json.loads(struct_path.read_text())
            struct_meta_dict = struct_data.get("__qms_meta__") or struct_data.get("meta") or {}
            
            # Generate ULID if missing
            if not struct_meta_dict.get("ulid"):
                struct_meta_dict["ulid"] = generate_resource_id()
                struct_meta_dict.setdefault("name", Path(struct_file).stem)
                struct_meta_dict.setdefault("slug", slugify(struct_meta_dict["name"]))
                struct_meta_dict.setdefault("kind", "structure")
                struct_meta_dict.setdefault("path", struct_file)
                
                # Update structure file
                if "__qms_meta__" in struct_data:
                    struct_data["__qms_meta__"] = struct_meta_dict
                else:
                    struct_data["meta"] = struct_meta_dict
                
                struct_path.write_text(json.dumps(struct_data, indent=2))
                print(f"  Added ULID to structure: {struct_file}")
            
            # Update entry meta
            if "meta" not in struct_entry:
                struct_entry["meta"] = struct_meta_dict
            elif not struct_entry["meta"].get("ulid"):
                struct_entry["meta"]["ulid"] = struct_meta_dict["ulid"]
        except Exception as e:
            print(f"  Warning: Could not migrate structure {struct_file}: {e}")
    
    # Step 4: Migrate calculations
    calculations = config.get("calculations", [])
    calculations_dir = project_root / "calculations"
    
    for calculation_entry in calculations:
        calculation_path = calculation_entry.get("path")
        if not calculation_path:
            continue
        
        calculation_dir = (project_root / calculation_path).resolve()
        calculation_yaml = calculation_dir / "calculation.yaml"
        
        if not calculation_yaml.exists():
            print(f"  Warning: calculation.yaml not found at {calculation_yaml}")
            continue
        
        # Backup calculation.yaml
        shutil.copy2(calculation_yaml, backup_dir / f"{calculation_dir.name}_calculation.yaml")
        
        print(f"  Migrating calculation: {calculation_dir.name}")
        
        # Load calculation YAML
        try:
            wf_data = yaml.safe_load(calculation_yaml.read_text()) or {}  # EXC-003: legacy deletion scheduled 2026-05-01
        except Exception as e:
            print(f"    Error loading calculation.yaml: {e}")
            continue
        
        # Ensure calculation meta has ULID
        wf_meta = wf_data.get("meta", {})
        if not wf_meta.get("ulid"):
            wf_meta["ulid"] = generate_resource_id()
            wf_meta.setdefault("name", calculation_dir.name)
            wf_meta.setdefault("slug", slugify(wf_meta["name"]))
            wf_meta.setdefault("kind", "calculation")
            wf_meta.setdefault("path", calculation_path)
            wf_data["meta"] = wf_meta
            print(f"    Added ULID to calculation meta")
        
        # Convert structure selector to structure_ulid
        legacy_structure = wf_data.get("structure") or wf_data.get("calculation", {}).get("structure")
        if legacy_structure and not wf_data.get("structure_ulid"):
            try:
                # Resolve structure to get ULID
                index = build_resource_index(project_root)
                resolved = resolve_structure(project_root, legacy_structure, index=index)
                structure_ulid = resolved.meta.ulid
                
                wf_data["structure_ulid"] = structure_ulid
                print(f"    Converted structure selector '{legacy_structure}' to structure_ulid: {structure_ulid}")
            except Exception as e:
                print(f"    Warning: Could not resolve structure '{legacy_structure}': {e}")
        
        # Remove legacy structure fields
        wf_data.pop("structure", None)
        if "calculation" in wf_data:
            wf_data["calculation"].pop("structure", None)
            wf_data["calculation"].pop("structure_name", None)
        wf_data.pop("structure_name", None)
        
        # Migrate steps
        steps = wf_data.get("steps", [])
        steps_dir = calculation_dir / "steps"
        steps_dir.mkdir(exist_ok=True)
        
        for i, step_entry in enumerate(steps):
            step_ulid_ulid = step_entry.get("step_ulid")
            legacy_step_file = step_entry.get("step_file")
            legacy_id = step_entry.get("ulid")
            step_type = step_entry.get("type", "unknown")
            
            # If step_ulid is missing or not a ULID, we need to find/create the step file
            if not step_ulid_ulid or len(step_ulid_ulid) != 26 or not step_ulid_ulid.startswith("01"):
                # Try to find step file
                step_file_path = None
                
                if legacy_step_file:
                    step_file_path = (calculation_dir / legacy_step_file).resolve()
                elif legacy_id:
                    # Try legacy_id as filename
                    candidate = steps_dir / f"{legacy_id}.step.yaml"
                    if candidate.exists():
                        step_file_path = candidate
                
                # If step file exists, load it to get ULID
                if step_file_path and step_file_path.exists():
                    try:
                        spec = StructureStepSpec.from_yaml(step_file_path)
                        step_ulid_ulid = spec.meta.ulid
                        print(f"    Step {i+1}: Found ULID {step_ulid_ulid} from existing file")
                    except Exception as e:
                        print(f"    Step {i+1}: Warning: Could not load step file {step_file_path}: {e}")
                        step_ulid_ulid = None
                
                # If still no ULID, generate one and create minimal step file
                if not step_ulid_ulid:
                    step_ulid_ulid = generate_resource_id()
                    step_name = legacy_id or step_type or f"step_{i+1}"
                    step_slug = slugify(step_name)
                    step_filename = f"{step_slug}.step.yaml"
                    step_file_path = steps_dir / step_filename
                    
                    # Create minimal step spec
                    step_meta = meta_from_name(
                        "step",
                        name=step_name,
                        path=f"{calculation_path}/steps/{step_filename}",
                    )
                    step_meta.ulid = step_ulid_ulid
                    
                    minimal_spec = StructureStepSpec(
                        meta=step_meta,
                        step_type_spec=step_type or "scf",
                    )
                    
                    step_file_path.write_text(yaml.safe_dump(minimal_spec.to_dict(), sort_keys=False))  # EXC-003: legacy deletion scheduled 2026-05-01
                    print(f"    Step {i+1}: Created step file with ULID {step_ulid_ulid}")
            
            # Update step entry
            step_entry["step_ulid"] = step_ulid_ulid
            step_entry.pop("step_file", None)
            step_entry.pop("id", None)  # Remove legacy id field
        
        # Remove legacy fields from calculation data
        wf_data.pop("structure", None)
        wf_data.pop("structure_name", None)
        
        # Write migrated calculation.yaml
        calculation_yaml.write_text(yaml.safe_dump(wf_data, sort_keys=False))  # EXC-003: legacy deletion scheduled 2026-05-01
        print(f"    Saved migrated calculation.yaml")
    
    # Step 5: Save migrated project config
    save_project_config(project_root, config)
    print(f"Saved migrated project.qms.yml")
    
    print(f"\nMigration complete! Backup saved to {backup_dir}")
    print(f"You can now use this project with the current QMatSuite codebase.")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m qmatsuite.legacy.migrate <project_root>")
        sys.exit(1)
    
    project_root = Path(sys.argv[1]).resolve()
    migrate_legacy_project(project_root)
