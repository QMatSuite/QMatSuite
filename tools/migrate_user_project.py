#!/usr/bin/env python3
"""
Migrate user project YAML files to new field names.

IMPORTANT: calc.yaml `type` field contains GEN values ("scf").
           Must convert to SPEC values ("qe_scf") using registry SSOT.

Usage: python migrate_user_project.py /path/to/project
"""
import re
import sys
from pathlib import Path

import yaml

# Add src to path for registry import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from qmatsuite.workflow.registry import get_registry


def gen_to_spec(step_type_gen: str, engine: str = "qe") -> str:
    """Convert GEN to SPEC using registry SSOT."""
    registry = get_registry()
    spec = registry.get_for_engine(step_type_gen, engine)
    if spec:
        return spec.step_type_spec
    # Fallback: prepend engine prefix
    print(f"  Warning: Unknown step type '{step_type_gen}', using fallback")
    return f"{engine}_{step_type_gen}"


def migrate_step_yaml(path: Path) -> bool:
    """Migrate step.yaml file.

    step.yaml step_type field already contains SPEC values.
    Only need to rename the key, not convert the value.
    """
    content = path.read_text()
    modified = False

    # step_type → step_type_spec (value stays same, it's already SPEC)
    if re.search(r'^step_type:', content, re.MULTILINE) and 'step_type_spec:' not in content:
        content = re.sub(r'^step_type:', 'step_type_spec:', content, flags=re.MULTILINE)
        modified = True

    # meta block: id → ulid
    if re.search(r'^  id:', content, re.MULTILINE):
        content = re.sub(r'^(  )id:', r'\1ulid:', content, flags=re.MULTILINE)
        modified = True

    if modified:
        path.write_text(content)
    return modified


def migrate_calc_yaml(path: Path) -> bool:
    """Migrate calculation.yaml file.

    IMPORTANT: calc.yaml `type` field contains GEN values ("scf").
    Must convert to SPEC values ("qe_scf").
    """
    content = path.read_text()
    data = yaml.safe_load(content)
    if data is None:
        return False

    modified = False

    # Determine engine from calculation metadata (default to QE)
    engine = data.get("engine", "qe")

    for step in data.get("steps", []):
        # type (GEN) → step_type_spec (SPEC) - MUST CONVERT VALUE
        if "type" in step and "step_type_spec" not in step:
            old_gen = step.pop("type")
            # Convert GEN → SPEC using registry SSOT
            if "_" not in old_gen:  # GEN value (no underscore)
                step["step_type_spec"] = gen_to_spec(old_gen, engine)
            else:  # Already SPEC (has underscore)
                step["step_type_spec"] = old_gen
            modified = True

        # step_id → step_ulid
        if "step_id" in step and "step_ulid" not in step:
            step["step_ulid"] = step.pop("step_id")
            modified = True

    # meta.id → meta.ulid
    if "meta" in data and "id" in data["meta"] and "ulid" not in data["meta"]:
        data["meta"]["ulid"] = data["meta"].pop("id")
        modified = True

    if modified:
        path.write_text(yaml.safe_dump(data, sort_keys=False))
    return modified


def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate_user_project.py /path/to/project")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}")
        sys.exit(1)

    print(f"Migrating project: {project_dir}")
    print("Note: calc.yaml 'type' (GEN) will be converted to 'step_type_spec' (SPEC)")

    # Migrate calculation.yaml files
    for p in project_dir.rglob("calculation.yaml"):
        if migrate_calc_yaml(p):
            print(f"  Migrated: {p}")

    # Migrate step.yaml files
    for p in project_dir.rglob("*.step.yaml"):
        if migrate_step_yaml(p):
            print(f"  Migrated: {p}")

    print("Done.")


if __name__ == "__main__":
    main()

