"""download_pseudo_library tool — download and install pseudopotential libraries."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response

_VALID_FLAVORS = frozenset({"efficiency", "precision"})


@mcp.tool
def download_pseudo_library(
    flavor: str = "efficiency",
    version: str = "1.3.0",
) -> dict:
    """Download and install a pseudopotential library from the QMatSuite asset repository.

    Currently supports SSSP (Standard Solid-State Pseudopotentials) for QE.
    Downloads are verified with SHA256 checksums before installation.

    After installation, use auto_resolve_species_map() to automatically select
    pseudopotentials for your calculation.

    Args:
        flavor: Library flavor — 'efficiency' (smaller cutoffs, faster) or
            'precision' (higher cutoffs, more accurate). Default: 'efficiency'.
        version: Library version. Default: '1.3.0'.
    """
    if flavor not in _VALID_FLAVORS:
        return make_error(
            "invalid_flavor",
            f"Invalid flavor '{flavor}'. Must be one of: {', '.join(sorted(_VALID_FLAVORS))}.",
            context_hint="Use flavor='efficiency' for faster calculations or 'precision' for higher accuracy.",
        )

    try:
        from pathlib import Path

        from quantumvitas.core.pseudo_config import (
            download_sssp_library,
            load_pseudo_config,
        )

        config = load_pseudo_config()
        store_dir = Path(config.store_dir) if config.store_dir else None
        seed_dir = Path(config.seed_dir) if config.seed_dir else None

        if store_dir is None:
            # Use default store directory
            from quantumvitas.core.pseudo_config import PseudoConfig

            default_store = PseudoConfig.get_default_store_dir()
            if default_store:
                store_dir = Path(default_store)
            else:
                return make_error(
                    "no_store_dir",
                    "Could not determine pseudo store directory.",
                    context_hint="Set store_dir in pseudo config or ensure ~/.qmatsuite/ is writable.",
                )

        result = download_sssp_library(
            store_dir=store_dir,
            flavor=flavor,
            version=version,
            force=True,
            allow_download=True,
            seed_dir=seed_dir,
        )

        if result.get("success"):
            return make_response(
                {
                    "library": "sssp",
                    "flavor": flavor,
                    "version": version,
                    "files_installed": result.get("files_installed", 0),
                    "messages": result.get("messages", []),
                },
                context_hint=(
                    "SSSP library installed. Use auto_resolve_species_map(calc_ulid=...) "
                    "to auto-select pseudopotentials for your calculation."
                ),
            )
        else:
            errors = result.get("errors", [])
            messages = result.get("messages", [])
            return make_error(
                "download_failed",
                f"SSSP download failed: {'; '.join(errors) if errors else 'unknown error'}",
                context_hint=(
                    "Check network connectivity. "
                    + (f"Messages: {'; '.join(messages)}" if messages else "")
                ),
            )

    except Exception as exc:
        return make_error(
            "download_error",
            f"Failed to download pseudo library: {exc}",
            context_hint="Check network connectivity and ensure ~/.qmatsuite/ is writable.",
        )
