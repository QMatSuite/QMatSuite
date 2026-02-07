#!/usr/bin/env python3
"""
Migrate demo projects to step_type_spec with SPEC values.
Uses registry SSOT for GEN→SPEC conversion.
"""
import sys
from pathlib import Path

import yaml

# Add src to path for registry import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from quantumvitas.workflow.registry import get_registry


def gen_to_spec(step_type_gen: str, engine: str = "qe") -> str:
    """Convert GEN to SPEC using registry SSOT."""
    registry = get_registry()
    spec = registry.get_for_engine(step_type_gen, engine)
    if spec:
        return spec.step_type_spec
    # Fallback: prepend engine prefix
    return f"{engine}_{step_type_gen}"


def migrate_demo(path: Path) -> bool:
    content = path.read_text()
    data = yaml.safe_load(content)
    if data is None:
        return False

    modified = False

    for calc in data.get("calculations", []):
        engine = calc.get("engine", "qe")  # Default to QE
        for step in calc.get("steps", []):
            if "step_type" in step and "step_type_spec" not in step:
                old = step.pop("step_type")
                # Convert GEN to SPEC if needed
                if "_" not in old:
                    step["step_type_spec"] = gen_to_spec(old, engine)
                else:
                    step["step_type_spec"] = old
                modified = True

            # Rename meta.id → meta.ulid
            if "meta" in step and "id" in step["meta"]:
                step["meta"]["ulid"] = step["meta"].pop("id")
                modified = True

    if modified:
        path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    return modified


def main():
    repo_root = Path(__file__).resolve().parent.parent.parent
    demo_dir = repo_root / "resources" / "demo_projects"
    if not demo_dir.exists():
        print(f"Demo directory not found: {demo_dir}")
        return

    for p in sorted(demo_dir.glob("*.yml")):
        if migrate_demo(p):
            print(f"Migrated: {p}")
        else:
            print(f"No changes: {p}")


if __name__ == "__main__":
    main()

