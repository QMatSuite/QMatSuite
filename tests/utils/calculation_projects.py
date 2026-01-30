"""
Helpers for scaffolding temporary calculation projects inside tests.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import yaml
from typing import Sequence, Dict, Any


def create_calculation_project(
    project_root: Path,
    calculation_id: str,
    steps: Sequence[Dict[str, Any]],
    source_dir: Path,
    pseudo_src: Path,
) -> Path:
    """
    Create a minimal project layout under ``project_root`` with a single calculation.

    Args:
        project_root: Destination directory (will be created/overwritten).
        calculation_id: Name of the calculation folder/id.
        input_files: Iterable of QE input filenames to copy into ``raw/``.
        reference_files: Mapping of step ids -> reference filename in ``reference/``.
        source_dir: Directory containing the source ``.in`` and reference files.
        pseudo_src: Directory containing pseudopotentials (copied into project).

    Returns:
        Path to the created project root.
    """

    if project_root.exists():
        shutil.rmtree(project_root)
    calculation_dir = project_root / "calculations" / calculation_id
    raw_dir = calculation_dir / "raw"
    reference_dir = calculation_dir / "reference"
    raw_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)

    for step in steps:
        input_name = step["input"]
        shutil.copy2(source_dir / input_name, raw_dir / input_name)
        reference_name = step.get("reference")
        if reference_name:
            dest = reference_dir / reference_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_dir / "reference" / reference_name, dest)

    # GUARD: Never use repo_root as project_root (tests must use tmp directories)
    from quantumvitas.core.pseudo_config import _find_quantumvitas_root
    repo_root = _find_quantumvitas_root()
    if repo_root and project_root.resolve() == repo_root.resolve():
        raise RuntimeError(
            f"BUG: create_calculation_project called with project_root=repo_root ({project_root}). "
            f"Tests must use a temp directory, not the repo root."
        )
    
    project_pseudo_dir = project_root / "pseudo"
    shutil.copytree(pseudo_src, project_pseudo_dir)

    # Extract structure from the first input file (SCF step typically has the structure)
    from quantumvitas.core.resources import generate_resource_id, meta_from_name
    from quantumvitas.io.parser.qe_parser import QEInputParser
    from quantumvitas.io.structure_io import structure_from_qe_input, write_structure
    
    structure_ulid = generate_resource_id()
    structures_dir = project_root / "structures"
    structures_dir.mkdir(parents=True, exist_ok=True)
    
    # Try to extract structure from the first step's input file
    structure_extracted = False
    if steps:
        first_input = raw_dir / steps[0]["input"]
        if first_input.exists():
            try:
                qe_input = QEInputParser.parse_file(first_input)
                structure = structure_from_qe_input(qe_input)
                structure_meta = meta_from_name("structure", name="test_structure", path="structures/test_structure.json")
                structure_meta.ulid = structure_ulid
                structure_path = structures_dir / "test_structure.json"
                write_structure(structure, structure_path, format="json", metadata=structure_meta)
                structure_extracted = True
            except Exception as e:
                print(f"Warning: Failed to extract structure from {first_input}: {e}")
    
    # Fallback to hardcoded structure if extraction failed
    if not structure_extracted:
        structure_meta = meta_from_name("structure", name="test_structure", path="structures/test_structure.json")
        structure_meta.ulid = structure_ulid
        from quantumvitas.io.structure_io import STRUCTURE_META_KEY, STRUCTURE_DATA_KEY
        import json
        structure_json = {
            STRUCTURE_META_KEY: structure_meta.to_dict(),
            STRUCTURE_DATA_KEY: {
                "@module": "pymatgen.core.structure",
                "@class": "Structure",
                "lattice": {"matrix": [[5.43, 0.0, 0.0], [0.0, 5.43, 0.0], [0.0, 0.0, 5.43]]},
                "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0.0, 0.0, 0.0]}],
            },
        }
        (structures_dir / "test_structure.json").write_text(json.dumps(structure_json, indent=2))
    
    # Generate calculation ULID (ID-only model)
    calculation_ulid = generate_resource_id()
    
    project_config = {
        "project": {"name": project_root.name},
        "calculations": [{"ulid": calculation_ulid, "path": f"calculations/{calculation_id}"}],  # Use ULID, not human-readable name
        "structures": [
            {
                "ulid": structure_ulid,
                "file": "structures/test_structure.json",
                "meta": structure_meta.to_dict(),
            }
        ],
        "settings": {},
    }
    (project_root / "project.qv.yml").write_text(
        yaml.safe_dump(project_config, sort_keys=False)
    )

    # Create step files with proper meta (ID-only model)
    from quantumvitas.core.resources import generate_resource_id, meta_from_name
    from quantumvitas.io.parser.qe_parser import QEInputParser
    from quantumvitas.calculation.importers import _build_step_spec_from_qe_input_data
    steps_dir = calculation_dir / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    
    step_entries = []
    for step in steps:
        step_id = step["ulid"]
        step_ulid = generate_resource_id()
        step_file = steps_dir / f"{step_id}.step.yaml"
        step_meta = meta_from_name("step", name=step_id, path=f"calculations/{calculation_id}/steps/{step_id}.step.yaml")
        step_meta.ulid = step_ulid
        
        # Parse the reference input file to extract QE parameters
        input_file = raw_dir / step["input"]
        parameters = {}
        cards = {}
        species_overrides = {}
        if input_file.exists():
            try:
                qe_input = QEInputParser.parse_file(input_file)
                # Extract parameters and cards WITHOUT applying defaults (preserve original)
                parameters, cards = _build_step_spec_from_qe_input_data(
                    qe_input, step_id, apply_defaults=False
                )
                
                # Extract species_overrides from ATOMIC_SPECIES card (if present)
                # This ensures pseudopotential filenames from original .in files are preserved
                # in step.yaml, so generation doesn't create placeholders
                from quantumvitas.io.model import QECardType
                from quantumvitas.core.pseudo import is_missing_pseudo_placeholder
                atomic_species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
                if atomic_species_card and atomic_species_card.data:
                    for row in atomic_species_card.data:
                        if isinstance(row, list) and len(row) >= 3:
                            element_symbol = str(row[0]).strip()
                            mass = row[1] if len(row) > 1 else None
                            pseudo_filename = str(row[2]).strip() if len(row) > 2 else None
                            
                            # Build species override
                            override = {}
                            if mass is not None:
                                try:
                                    override["mass"] = float(mass)
                                except (TypeError, ValueError):
                                    override["mass"] = mass
                            if pseudo_filename:
                                # Skip placeholder names (missing configuration)
                                if not is_missing_pseudo_placeholder(pseudo_filename):
                                    override["pseudopot"] = pseudo_filename
                            
                            if override:
                                species_overrides[element_symbol] = override
            except Exception as e:
                # If parsing fails, fall back to minimal spec
                print(f"Warning: Failed to parse {input_file}: {e}")
        
        # DAG model: Step YAML should NOT contain structure_ulid (inherits from calculation)
        # Convert step_id (e.g., "scf") to step_type_spec (e.g., "qe_scf")
        step_type_spec = step.get("step_type_spec", f"qe_{step_id}")  # Default to qe_<step_id>
        step_spec = {
            "meta": step_meta.to_dict(),
            "step_type_spec": step_type_spec,  # SPEC type (e.g., "qe_scf")
            # structure_ulid is NOT written to step YAML (DAG model)
        }
        # Add extracted parameters and cards if available
        if parameters:
            step_spec["parameters"] = parameters
        if cards:
            step_spec["cards"] = cards
        # Add extracted species_overrides if available (preserves pseudopotential filenames)
        if species_overrides:
            step_spec["species_overrides"] = species_overrides
        
        step_file.write_text(yaml.safe_dump(step_spec, sort_keys=False))
        
        # Create step entry with step_ulid (ULID)
        step_entry = {
            "step_ulid": step_ulid,
            "step_type_spec": step.get("step_type_spec", "qe_scf"),  # Default to qe_scf if not specified
            "input": step["input"],
        }
        if step.get("reference"):
            step_entry["reference"] = f"reference/{step['reference']}"
        step_entries.append(step_entry)
    
    # Build calculation-level species_map from all step species_overrides
    # This is required for project runs (enforcement: no fallback to step-level)
    calc_species_map = {}
    for step in steps:
        step_id = step["ulid"]
        step_file = steps_dir / f"{step_id}.step.yaml"
        if step_file.exists():
            try:
                step_data = yaml.safe_load(step_file.read_text())
                step_species_overrides = step_data.get("species_overrides", {})
                if step_species_overrides:
                    # Merge into calc-level species_map (last step wins for conflicts)
                    for element, override in step_species_overrides.items():
                        calc_species_map[element] = dict(override)  # Copy to avoid mutation
            except Exception:
                # If parsing fails, skip this step's species_overrides
                pass
    
    calculation_config = {
        "meta": {
            "ulid": calculation_ulid,
            "ulid": calculation_ulid,  # Backwards compat
            "name": calculation_id,  # Human-readable name
            "slug": calculation_id,
            "path": f"calculations/{calculation_id}",
            "kind": "calculation",
        },
        "mode": "strict",
        "calculation": {"working_dir": "raw"},
        "structure_ulid": structure_ulid,  # Calculation-level structure reference (ULID)
        "steps": step_entries,
    }
    
    # Add species_map if we collected any mappings (required for project runs)
    if calc_species_map:
        calculation_config["species_map"] = calc_species_map
    
    (calculation_dir / "calculation.yaml").write_text(
        yaml.safe_dump(calculation_config, sort_keys=False)
    )

    return project_root

