#!/usr/bin/env python3
"""
Patch golden fixtures for GEN/SPEC convergence.
Uses registry SSOT for SPEC→GEN conversion. NO hardcoded mapping.
"""
import json
import sys
from pathlib import Path

# Add src to path for registry import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from qmatsuite.workflow.registry import normalize_step_type_to_public

GOLDEN_DIR = Path("tests/fixtures/golden_0873ebf/daemon")


def spec_to_gen(step_type_spec: str) -> str:
    """Convert SPEC to GEN using registry SSOT."""
    try:
        return normalize_step_type_to_public(step_type_spec)
    except (KeyError, ValueError):
        # Fallback for unknown types: strip engine prefix
        if "_" in step_type_spec:
            return step_type_spec.split("_", 1)[1]
        return step_type_spec


def patch_step(step: dict) -> bool:
    """Patch a step object. Returns True if modified."""
    modified = False

    # Rename step_type → step_type_spec + step_type_gen
    if "step_type" in step and "step_type_spec" not in step:
        spec_value = step.pop("step_type")
        step["step_type_spec"] = spec_value
        step["step_type_gen"] = spec_to_gen(spec_value)
        modified = True

    # Rename type → step_type_spec + step_type_gen
    if "type" in step and "step_type_spec" not in step:
        old_type = step.pop("type")
        if "_" in old_type:  # Already SPEC
            step["step_type_spec"] = old_type
            step["step_type_gen"] = spec_to_gen(old_type)
        else:  # GEN value - assume QE for golden fixtures
            step["step_type_gen"] = old_type
            step["step_type_spec"] = f"qe_{old_type}"
        modified = True

    # Rename id → ulid (only for normalized placeholders or 26-char ULIDs)
    if "id" in step:
        val = step["id"]
        if val == "<NORMALIZED_ID>" or (isinstance(val, str) and len(val) == 26 and val.isalnum()):
            step["ulid"] = step.pop("id")
            modified = True

    # Rename step_id → step_ulid
    if "step_id" in step:
        step["step_ulid"] = step.pop("step_id")
        modified = True

    return modified


def patch_recursive(data, depth=0) -> bool:
    """Recursively patch data structure."""
    modified = False

    if isinstance(data, dict):
        # Check if this looks like a step object
        if any(k in data for k in ("type", "step_type", "step_file", "parameters")):
            if patch_step(data):
                modified = True

        # Patch meta.id → meta.ulid
        if "meta" in data and isinstance(data["meta"], dict):
            meta = data["meta"]
            if "id" in meta:
                meta["ulid"] = meta.pop("id")
                modified = True

        # Rename parent_calculation_id → parent_calculation_ulid
        if "parent_calculation_id" in data:
            data["parent_calculation_ulid"] = data.pop("parent_calculation_id")
            modified = True

        # Recurse
        for value in list(data.values()):
            if isinstance(value, (dict, list)):
                if patch_recursive(value, depth + 1):
                    modified = True

    elif isinstance(data, list):
        for item in data:
            if patch_recursive(item, depth + 1):
                modified = True

    return modified


def main():
    if not GOLDEN_DIR.exists():
        print(f"Golden directory not found: {GOLDEN_DIR}")
        sys.exit(1)

    for path in sorted(GOLDEN_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)

        if patch_recursive(data):
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            print(f"Patched: {path.name}")
        else:
            print(f"No changes: {path.name}")


if __name__ == "__main__":
    main()
