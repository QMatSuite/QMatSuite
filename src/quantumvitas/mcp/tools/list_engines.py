"""list_engines tool — discover available computation engines."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_response

# Syntax family mapping (engine_family -> human label).
# Derived from the inputformat design doc's 8 families.
_SYNTAX_FAMILIES: dict[str, str] = {
    "qe": "F1: namelist-card",
    "abinit": "F1: namelist-card",
    "siesta": "F2: fdf key-value",
    "cp2k": "F3: nested-section",
    "orca": "F4: keyword-block",
    "gaussian": "F4: keyword-block",
    "lammps": "F5: command-stream",
    "qmcpack": "F6: XML",
    "vasp": "F7: multi-file flat",
    "w90": "F7: multi-file flat",
    "yambo": "F7: multi-file flat",
    "xtb": "F8: CLI-flag",
    "gpaw": "Python script",
    "psi4": "Python script",
    "pyscf": "Python script",
}


def _count_parameters(engine: str) -> int:
    """Count parameter tags for an engine. Returns 0 if no metadata."""
    try:
        if engine == "qe":
            from quantumvitas.drivers.qe.data.qe_metadata import (
                _iter_params,
                list_supported_modules,
            )
            total = 0
            for mod in list_supported_modules():
                total += len(_iter_params(mod))
            return total

        # Standard tag-based engines
        _TAG_ENGINES = {
            "vasp", "abinit", "cp2k", "w90", "xtb", "yambo", "qmcpack",
        }
        _KEYWORD_ENGINES = {"orca", "gaussian"}
        _COMMAND_ENGINES = {"lammps"}

        if engine in _TAG_ENGINES:
            meta_mod = __import__(
                f"quantumvitas.drivers.{engine}.data.{engine}_metadata",
                fromlist=["safe_load_metadata"],
            )
            data = meta_mod.safe_load_metadata()
            return len(data.get("tags", {}))

        if engine in _KEYWORD_ENGINES:
            meta_mod = __import__(
                f"quantumvitas.drivers.{engine}.data.{engine}_metadata",
                fromlist=["safe_load_metadata"],
            )
            data = meta_mod.safe_load_metadata()
            return len(data.get("keywords", {}))

        if engine in _COMMAND_ENGINES:
            meta_mod = __import__(
                f"quantumvitas.drivers.{engine}.data.{engine}_metadata",
                fromlist=["safe_load_metadata"],
            )
            data = meta_mod.safe_load_metadata()
            return len(data.get("commands", {}))

    except Exception:
        pass
    return 0


@mcp.tool
def list_engines(installed_only: bool = False) -> dict:
    """List all available computation engines with their capabilities.

    Returns engine metadata including display name, supported step types,
    capabilities, parameter count, and syntax family.

    Args:
        installed_only: Reserved for future use. Currently all registered
            engines are returned.
    """
    import quantumvitas.drivers  # noqa: F401 — trigger registration
    from quantumvitas.core.driver_registry import DriverRegistry

    engines_out: list[dict] = []
    for family in sorted(DriverRegistry.get_all_engines()):
        driver = DriverRegistry.get_driver(family)
        gen_steps = sorted(driver.SUPPORTED_GEN_STEPS) if hasattr(driver, "SUPPORTED_GEN_STEPS") else []
        engines_out.append({
            "engine": family,
            "display_name": driver.display_name,
            "supported_gen_steps": gen_steps,
            "capabilities": sorted(driver.get_capabilities()),
            "parameter_count": _count_parameters(family),
            "syntax_family": _SYNTAX_FAMILIES.get(family, "unknown"),
            "installed": True,
        })

    return make_response(
        {"engines": engines_out, "total": len(engines_out)},
        context_hint="Use list_workflows(engine='...') to see available workflows for a specific engine.",
    )
