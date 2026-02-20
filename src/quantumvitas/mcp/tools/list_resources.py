"""list_available_resources tool — discover available pseudopotentials and potentials."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response

# Engines that don't need external resource files at all.
_BUILTIN_ENGINES = {"xtb", "orca", "gaussian", "psi4", "pyscf", "gpaw"}

# Engines that need resources but discovery is not yet automated.
_UNMANAGED_RESOURCE_ENGINES = {"cp2k", "w90", "qmcpack", "yambo", "siesta", "abinit"}


@mcp.tool
def list_available_resources(
    engine: str,
    elements: list[str] | None = None,
) -> dict:
    """List available pseudopotentials or potentials for an engine.

    For QE: returns available pseudopotential files per element from
    internal resources, project pseudos, and installed SSSP libraries.
    For VASP: returns available POTCAR variants.
    For LAMMPS: returns available potential files.
    For xTB/ORCA/Gaussian/Psi4/PySCF/GPAW: no external resources needed.

    Args:
        engine: Engine family identifier (e.g. 'qe', 'vasp', 'lammps').
        elements: Optional list of element symbols to filter by.
            For QE, defaults to common elements available in internal pseudos.
    """
    import quantumvitas.drivers  # noqa: F401 — trigger registration
    from quantumvitas.core.driver_registry import DriverRegistry

    known_engines = sorted(DriverRegistry.get_all_engines())
    if engine not in known_engines:
        return make_error(
            "unknown_engine",
            f"Engine '{engine}' is not registered.",
            suggestions=known_engines,
        )

    if engine in _BUILTIN_ENGINES:
        return make_response(
            {
                "engine": engine,
                "resources_needed": False,
                "note": (
                    f"Engine '{engine}' uses built-in basis sets or methods. "
                    "No external pseudopotential or potential files required."
                ),
            },
            context_hint=f"Proceed directly with create_calculation(engine='{engine}', ...).",
        )

    if engine in _UNMANAGED_RESOURCE_ENGINES:
        return make_response(
            {
                "engine": engine,
                "resources_needed": True,
                "managed": False,
                "note": (
                    f"Engine '{engine}' requires external resources (pseudopotentials "
                    "or basis sets), but automated discovery is not yet available. "
                    "Set species_map manually after creating the calculation."
                ),
            },
            context_hint=(
                f"Create the calculation first, then use "
                f"set_species_map() to configure pseudopotentials manually."
            ),
        )

    # --- QE ---
    if engine == "qe":
        return _list_qe_resources(elements)

    # --- VASP ---
    if engine == "vasp":
        return _list_vasp_resources(elements)

    # --- LAMMPS ---
    if engine == "lammps":
        return _list_lammps_resources()

    return make_error(
        "unsupported",
        f"Resource listing not implemented for engine '{engine}'.",
    )


def _list_qe_resources(elements: list[str] | None) -> dict:
    """List available QE pseudopotentials."""
    from quantumvitas.core.paths import home_pseudo_libraries_dir
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    if not elements:
        # Default to common elements available in internal resources
        elements = ["Si", "Al", "C", "H", "O", "Fe", "Cu", "Li", "He"]

    # Discover installed libraries via shared utility
    installed_libraries: list[dict] = []
    try:
        from quantumvitas.pseudo.layout import iter_installed_libraries
        from quantumvitas.pseudo.registry import resolve_element_from_index

        libraries_root = home_pseudo_libraries_dir()
        for lib in iter_installed_libraries(libraries_root):
            upf_count = sum(
                1
                for f in lib.install_dir.iterdir()
                if f.suffix.lower() == ".upf"
            )

            # Check which requested elements are available
            available_elements: list[str] = []
            if lib.library_key and elements:
                for elem in elements:
                    fname = resolve_element_from_index(
                        lib.library_key, lib.variant, lib.version, elem
                    )
                    if fname:
                        available_elements.append(elem)

            lib_info: dict = {
                "name": lib.install_dir.parent.parent.name,
                "variant": lib.variant,
                "version": lib.version,
                "upf_count": upf_count,
            }
            if available_elements:
                lib_info["available_elements"] = available_elements
            installed_libraries.append(lib_info)
    except Exception:
        pass

    try:
        options = svc.project.get_pseudo_options(elements)
        # Summarise: for each element, count variants and show first few names
        summary: dict = {}
        total_installed = 0
        for elem, variants in options.items():
            names = [v.get("basename", v.get("filename", "?")) for v in variants[:5]]
            n_installed = sum(
                1 for v in variants
                if v.get("availability", {}).get("any_installed")
            )
            total_installed += n_installed
            summary[elem] = {
                "n_variants": len(variants),
                "n_installed": n_installed,
                "examples": names,
            }

        has_any = total_installed > 0 or len(installed_libraries) > 0

        hint = (
            "Use auto_resolve_species_map(calc_ulid=...) to auto-select "
            "pseudopotentials, or set_species_map() to choose manually."
        )
        if not has_any:
            hint = (
                "No pseudo libraries installed. "
                "Use download_pseudo_library(library='sssp') to install SSSP first, "
                "then auto_resolve_species_map() to auto-select."
            )

        return make_response(
            {
                "engine": "qe",
                "resources_needed": True,
                "managed": True,
                "any_installed": has_any,
                "installed_libraries": installed_libraries,
                "elements": summary,
            },
            context_hint=hint,
        )
    except Exception as exc:
        return make_error(
            "discovery_failed",
            f"Failed to discover QE pseudopotentials: {exc}",
            context_hint="Ensure the project is initialised and pseudo libraries are available.",
        )


def _list_vasp_resources(elements: list[str] | None) -> dict:
    """List available VASP POTCAR variants."""
    try:
        from quantumvitas.drivers.vasp.engine.vasp_potcar import list_available_potcars

        variants = list_available_potcars(functional="PBE")
        if elements:
            # Filter: keep variants whose name starts with one of the elements
            filtered = []
            for v in variants:
                for elem in elements:
                    if v == elem or v.startswith(elem + "_"):
                        filtered.append(v)
                        break
            variants = filtered

        return make_response(
            {
                "engine": "vasp",
                "resources_needed": True,
                "managed": True,
                "functional": "PBE",
                "n_variants": len(variants),
                "variants": variants,
            },
            context_hint=(
                "Use set_species_map() with POTCAR variant names to configure. "
                "Example: {\"Si\": {\"pseudopot\": \"Si\"}}"
            ),
        )
    except Exception as exc:
        return make_error(
            "discovery_failed",
            f"Failed to discover VASP POTCARs: {exc}",
            context_hint="Ensure VASP POTCAR library is installed.",
        )


def _list_lammps_resources() -> dict:
    """List available LAMMPS potential files."""
    try:
        from quantumvitas.drivers.lammps.engine.lammps_potential import (
            get_default_potential_root,
        )

        root = get_default_potential_root()
        if root is None or not root.is_dir():
            return make_response(
                {
                    "engine": "lammps",
                    "resources_needed": True,
                    "managed": True,
                    "potential_root": None,
                    "n_files": 0,
                    "note": "No LAMMPS potential directory found.",
                },
                context_hint=(
                    "Set LAMMPS_POTENTIALS environment variable or place potential "
                    "files in .qmatsuite/engines/lammps/potentials/."
                ),
            )

        # List potential files
        files = sorted(f.name for f in root.iterdir() if f.is_file())
        return make_response(
            {
                "engine": "lammps",
                "resources_needed": True,
                "managed": True,
                "potential_root": str(root),
                "n_files": len(files),
                "files": files[:50],  # cap at 50 for readability
            },
            context_hint=(
                "LAMMPS potential files are referenced in input scripts. "
                "No species_map needed for LAMMPS."
            ),
        )
    except Exception as exc:
        return make_error(
            "discovery_failed",
            f"Failed to discover LAMMPS potentials: {exc}",
        )
