"""
Integration tests for relax structure save functionality (idempotency).
"""

import pytest
import yaml
import json
from pathlib import Path
from qmatsuite.api import QMSService
from qmatsuite.calculation.structure_steps import StructureStepSpec
from qmatsuite.core.resources import meta_from_name, generate_resource_id


def test_save_relax_structure_ulidempotency(tmp_path: Path):
    """Test that save_relax_final_structure is idempotent (returns same ULID on repeated calls)."""

    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create minimal project structure
    (project_root / "structures").mkdir()
    (project_root / "calculations").mkdir()
    
    # Create project config
    project_config = {
        "project": {
            "name": "Test Project",
            "meta": {
                "ulid": generate_resource_id(),
                "name": "Test Project",
                "slug": "test-project",
                "path": ".",
                "kind": "project",
            },
        },
        "structures": [],
        "calculations": [],
    }
    (project_root / "project.qms.yml").write_text(yaml.safe_dump(project_config))
    
    # Create a parent structure
    parent_structure_ulid = generate_resource_id()
    parent_structure_path = project_root / "structures" / "si-bulk.json"
    parent_structure_data = {
        "__qms_meta__": {
            "ulid": parent_structure_ulid,
            "name": "Si bulk",
            "slug": "si-bulk",
            "path": "structures/si-bulk.json",
            "kind": "structure",
        },
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {
            "matrix": [[5.431, 0, 0], [0, 5.431, 0], [0, 0, 5.431]],
        },
        "sites": [
            {
                "species": [{"element": "Si", "occu": 1}],
                "abc": [0.0, 0.0, 0.0],
            },
            {
                "species": [{"element": "Si", "occu": 1}],
                "abc": [0.25, 0.25, 0.25],
            },
        ],
    }
    parent_structure_path.write_text(json.dumps(parent_structure_data, indent=2))
    project_config["structures"].append({"structure_ulid": parent_structure_ulid})
    (project_root / "project.qms.yml").write_text(yaml.safe_dump(project_config))
    
    # Create a calculation with a relax step
    calc_id = generate_resource_id()
    calc_dir = project_root / "calculations" / "relax-test"
    calc_dir.mkdir()
    (calc_dir / "steps").mkdir()
    
    step_id = generate_resource_id()
    step_path = calc_dir / "steps" / "relax.step.yaml"
    
    step_meta = meta_from_name("step", name="relax", path=f"calculations/relax-test/steps/relax.step.yaml")
    step_meta.ulid = step_id  # Set the ULID to match step_id in calculation.yaml
    step_spec = StructureStepSpec(
        meta=step_meta,
        structure="si-bulk",  # Legacy selector
        structure_ulid=parent_structure_ulid,
        step_type_spec="qe_relax",
        parameters={},
    )
    step_path.write_text(yaml.safe_dump(step_spec.to_dict(), sort_keys=False))
    
    calc_config = {
        "ulid": calc_id,
        "meta": {
            "ulid": calc_id,
            "name": "relax-test",
            "slug": "relax-test",
            "path": "calculations/relax-test",
            "kind": "calculation",
        },
        "calculation": {
            "structure_ulid": parent_structure_ulid,
            "working_dir": "raw",
        },
        "steps": [
            {"step_ulid": step_id},
        ],
    }
    (calc_dir / "calculation.yaml").write_text(yaml.safe_dump(calc_config))
    project_config["calculations"].append({
        "meta": {
            "ulid": calc_id,
            "name": "relax-test",
            "slug": "relax-test",
            "path": "calculations/relax-test",
            "kind": "calculation",
        }
    })
    (project_root / "project.qms.yml").write_text(yaml.safe_dump(project_config))
    
    # Create mock output file with final coordinates
    raw_dir = calc_dir / "raw"
    raw_dir.mkdir()
    # Create the output file with the GEN step type name (relax.out)
    # The API code uses GEN step types for file naming
    output_file = raw_dir / "relax.out"
    output_file.write_text("""
Begin final coordinates
CELL_PARAMETERS (alat= 14.00000000)
  -0.371818187   0.000000000   0.371818187
   0.000000000   0.371818187   0.371818187
  -0.371818187   0.371818187   0.000000000
ATOMIC_POSITIONS (alat)
Si       0.000000000   0.000000000   0.000000000
Si       0.185909094   0.185909094   0.185909094
End final coordinates
""")
    
    # First call: should create structure
    svc = QMSService(project_root)
    result1 = svc.structure.save_relax_final_structure(
        calculation_selector="relax-test",
        step_selector=step_id,
        parent_structure_ulid=parent_structure_ulid,
        slug_hint="relaxed",
    )
    
    assert result1["structure_ulid"] is not None
    assert result1["already_exists"] is False
    
    structure_ulid_1 = result1["structure_ulid"]
    
    # Verify structure file was created (should be 2 files: parent + new relaxed structure)
    structure_files = list((project_root / "structures").glob("*.json"))
    assert len(structure_files) == 2  # si-bulk.json (parent) + relaxed.json (new)
    
    # Verify the new structure file exists and has the correct ULID
    new_structure_file = project_root / "structures" / "relaxed.json"
    assert new_structure_file.exists()
    new_structure_data = json.loads(new_structure_file.read_text())
    assert new_structure_data["__qms_meta__"]["ulid"] == structure_ulid_1
    
    # Verify step YAML was updated with produced_structure_ulid
    step_data = yaml.safe_load(step_path.read_text())
    assert step_data.get("produced_structure_ulid") == structure_ulid_1
    
    # Second call: should return existing structure (idempotent)
    result2 = svc.structure.save_relax_final_structure(
        calculation_selector="relax-test",
        step_selector=step_id,
        parent_structure_ulid=parent_structure_ulid,
        slug_hint="relaxed",
    )
    
    assert result2["structure_ulid"] == structure_ulid_1
    assert result2["already_exists"] is True
    
    # Verify no new structure file was created (still 2 files: parent + relaxed)
    structure_files_after = list((project_root / "structures").glob("*.json"))
    assert len(structure_files_after) == 2  # si-bulk.json (parent) + relaxed.json (same as before)

