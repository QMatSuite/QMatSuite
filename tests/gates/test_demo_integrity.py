"""
Gate: Law EF6 — Demo Integrity.

Every demo snapshot must have:
1. engine_family explicitly set on each calculation.
2. Every step's step_type_spec prefix matches engine_family or a companion engine.
"""
import yaml
from pathlib import Path
import pytest

DEMO_DIR = Path(__file__).parent.parent.parent / "resources" / "demo_projects"


def _load_demo(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _get_prefix(step_type_spec: str) -> str:
    """Extract engine prefix from step_type_spec."""
    if "_" in step_type_spec:
        return step_type_spec.split("_", 1)[0]
    return step_type_spec


def test_all_demos_have_engine_family():
    """Every demo calculation must have explicit engine_family."""
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    violations = []
    for yml_path in sorted(DEMO_DIR.glob("*.yml")):
        data = _load_demo(yml_path)
        for i, calc in enumerate(data.get("calculations", [])):
            ef = calc.get("engine_family")
            if ef is None:
                violations.append(f"  {yml_path.name}: calculations[{i}] missing engine_family")

    assert not violations, f"EF6 violation — demos missing engine_family:\n" + "\n".join(violations)


def test_demo_step_type_spec_matches_engine_family():
    """Every step's step_type_spec prefix must match engine_family or its companion engines."""
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    violations = []
    for yml_path in sorted(DEMO_DIR.glob("*.yml")):
        data = _load_demo(yml_path)
        for calc in data.get("calculations", []):
            ef = calc.get("engine_family")
            if ef is None:
                continue  # Caught by other test

            # Build allowed prefixes: engine_family + companions
            allowed_prefixes = {ef}
            if DriverRegistry.is_engine_registered(ef):
                driver = DriverRegistry.get_driver(ef)
                companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
                allowed_prefixes.update(companions)

            for step in calc.get("steps", []):
                spec = step.get("step_type_spec", "")
                prefix = _get_prefix(spec)
                if prefix not in allowed_prefixes:
                    step_name = step.get("meta", {}).get("name", "?")
                    violations.append(
                        f"  {yml_path.name}: step '{step_name}' has step_type_spec='{spec}' "
                        f"(prefix='{prefix}') but engine_family='{ef}' "
                        f"(allowed: {sorted(allowed_prefixes)})"
                    )

    assert not violations, f"EF6 violation — step_type_spec/engine_family mismatch:\n" + "\n".join(violations)

