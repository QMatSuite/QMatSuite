"""download_pseudo_library tool — download and install pseudopotential libraries."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def download_pseudo_library(
    library: str = "sssp",
    variant: str = "",
    version: str = "latest",
) -> dict:
    """Download and install a pseudopotential library from the QMatSuite asset repository.

    Currently supports SSSP (Standard Solid-State Pseudopotentials) for QE.
    Downloads are verified with SHA256 checksums before installation.

    After installation, use auto_resolve_species_map() to automatically select
    pseudopotentials for your calculation.

    Args:
        library: Library identifier (default: 'sssp').
        variant: Library variant — 'efficiency' (smaller cutoffs, faster) or
            'precision' (higher cutoffs, more accurate). Default: registry default.
        version: Library version. Default: '1.3.0'.
    """
    try:
        from quantumvitas.pseudo import PseudoRegistry, download_and_install

        # Validate library name exists in registry
        try:
            registry = PseudoRegistry()
            info = registry.resolve(library, variant, version)
        except ValueError as exc:
            available = registry.list_libraries()
            lib_names = [lib["library_key"] for lib in available]
            return make_error(
                "invalid_library",
                str(exc),
                context_hint=f"Available libraries: {', '.join(lib_names)}",
                suggestions=lib_names,
            )

        # Run the pipeline
        result = download_and_install(
            library=library,
            variant=variant,
            version=version,
        )

        if result.get("success"):
            return make_response(
                {
                    "library": result["library_key"],
                    "variant": result["variant"],
                    "version": result["version"],
                    "upf_count": result.get("upf_count", 0),
                    "install_dir": result.get("install_dir", ""),
                    "messages": result.get("messages", []),
                },
                context_hint=(
                    f"{result['library_key']} {result['variant']} installed. "
                    "Use auto_resolve_species_map(calc_ulid=...) "
                    "to auto-select pseudopotentials for your calculation."
                ),
            )
        else:
            errors = result.get("errors", [])
            messages = result.get("messages", [])
            return make_error(
                "download_failed",
                f"Download failed: {'; '.join(errors) if errors else 'unknown error'}",
                context_hint=(
                    "Check network connectivity. "
                    + (f"Progress: {'; '.join(messages)}" if messages else "")
                ),
            )

    except Exception as exc:
        return make_error(
            "download_error",
            f"Failed to download pseudo library: {exc}",
            context_hint="Check network connectivity and ensure ~/.qmatsuite/ is writable.",
        )
