"""
Gate: Law EF3 — Companion Allowlist Routing.

materialize_public_step_key must use companion allowlist, not StepTypeRegistry first-match.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
GENERALIZED_STEPS_PATH = REPO_ROOT / "src" / "quantumvitas" / "workflow" / "generalized_steps.py"


def test_no_step_type_registry_in_materialize():
    """materialize_public_step_key must not use StepTypeRegistry for resolution."""
    text = GENERALIZED_STEPS_PATH.read_text(encoding="utf-8")

    # Find the materialize_public_step_key function body
    # Look for usage of registry.get() or get_registry() inside this function
    in_func = False
    violations = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if "def materialize_public_step_key" in line:
            in_func = True
            continue
        if in_func and line.strip() and not line[0].isspace() and not line.strip().startswith("#"):
            # Hit next top-level def/class — stop
            break
        if in_func:
            if "get_registry" in line or "registry.get(" in line:
                violations.append(f"  generalized_steps.py:{lineno}  {line.strip()}")

    assert not violations, (
        "EF3 violation — materialize_public_step_key still uses StepTypeRegistry:\n"
        + "\n".join(violations)
    )


def test_companion_routing_for_qe():
    """QE companion steps resolve through DriverRegistry, not first-match."""
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    # w90 is a companion of QE
    result = DriverRegistry.resolve_companion_step("qe", "wannierprep")
    assert result == "w90_wannierprep", f"Expected 'w90_wannierprep', got '{result}'"

    result = DriverRegistry.resolve_companion_step("qe", "wannier")
    assert result == "w90_wannier", f"Expected 'w90_wannier', got '{result}'"

    # qmcpack is a companion of QE
    result = DriverRegistry.resolve_companion_step("qe", "vmc")
    assert result == "qmcpack_vmc", f"Expected 'qmcpack_vmc', got '{result}'"

    # yambo is a companion of QE
    result = DriverRegistry.resolve_companion_step("qe", "setup")
    assert result == "yambo_setup", f"Expected 'yambo_setup', got '{result}'"


def test_no_companion_routing_for_vasp():
    """VASP has no companions. Companion steps should return None."""
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    result = DriverRegistry.resolve_companion_step("vasp", "wannierprep")
    assert result is None, f"Expected None for VASP+wannierprep, got '{result}'"

    result = DriverRegistry.resolve_companion_step("vasp", "vmc")
    assert result is None, f"Expected None for VASP+vmc, got '{result}'"


def test_base_steps_still_resolve():
    """Base engine steps still resolve normally through companion routing."""
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    assert DriverRegistry.resolve_companion_step("qe", "scf") == "qe_scf"
    assert DriverRegistry.resolve_companion_step("vasp", "scf") == "vasp_scf"
    assert DriverRegistry.resolve_companion_step("orca", "scf") == "orca_scf"

