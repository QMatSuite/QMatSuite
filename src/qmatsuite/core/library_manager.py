"""
Generic Library Manager for pseudopotential libraries.

Uses the NEW pipeline (qmatsuite.pseudo.pipeline) exclusively.
All OLD SSSP-specific functions have been removed.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from qmatsuite.core.pseudo_config import (
    PseudoConfig,
    load_pseudo_config,
)
from qmatsuite.core.paths import home_pseudo_libraries_dir


@dataclass
class LibraryMetadata:
    """Metadata about a supported library."""
    id: str
    name: str
    description: str
    supported_variants: List[str]
    default_variants: List[str]  # Recommended variants to install

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LibraryVariantStatus:
    """Status of a specific library variant."""
    variant: str
    installed: bool
    path: Optional[str] = None
    file_count: int = 0
    size_bytes: Optional[int] = None
    version: Optional[str] = None
    path_checked: Optional[str] = None  # For debugging

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LibraryStatus:
    """Status of a library (all variants)."""
    library_id: str
    name: str
    installed_variants: List[str]
    variant_statuses: List[LibraryVariantStatus]
    status: Literal["installed", "not_installed", "partial"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "library_id": self.library_id,
            "name": self.name,
            "installed_variants": self.installed_variants,
            "variant_statuses": [v.to_dict() for v in self.variant_statuses],
            "status": self.status,
        }


def get_supported_libraries() -> List[LibraryMetadata]:
    """Get metadata for all supported libraries."""
    return [
        LibraryMetadata(
            id="sssp",
            name="SSSP",
            description="Standard Solid State Pseudopotentials",
            supported_variants=["precision", "efficiency"],
            default_variants=["precision"],
        ),
    ]


def _scan_installed_for_library(
    libraries_root: Path, library_dir_name: str
) -> List[dict]:
    """Scan installed variants/versions for a specific library.

    Returns list of dicts with variant, version, upf_count, size_bytes, path.
    """
    from qmatsuite.pseudo.layout import iter_installed_libraries

    results: List[dict] = []
    for lib in iter_installed_libraries(libraries_root):
        if lib.install_dir.parent.parent.name != library_dir_name:
            continue
        upf_count = sum(
            1 for f in lib.install_dir.iterdir()
            if f.suffix.lower() == ".upf"
        )
        size_bytes = None
        if upf_count > 0:
            try:
                size_bytes = sum(
                    f.stat().st_size for f in lib.install_dir.rglob("*")
                    if f.is_file()
                )
            except Exception:
                pass

        results.append({
            "variant": lib.variant,
            "version": lib.version,
            "upf_count": upf_count,
            "size_bytes": size_bytes,
            "path": lib.install_dir,
        })
    return results


def get_library_status(
    library_id: str,
    config: Optional[PseudoConfig] = None,
) -> Optional[LibraryStatus]:
    """Get status of a library (which variants are installed)."""
    if config is None:
        config = load_pseudo_config()

    if library_id == "sssp":
        return _get_sssp_status(config)

    return None


def _get_sssp_status(config: PseudoConfig) -> LibraryStatus:
    """Get SSSP library status via three-level walk of NEW layout.

    Scans .qmatsuite/libraries/pseudo/SSSP/ for installed variants.
    """
    libraries_root = home_pseudo_libraries_dir()
    installs = _scan_installed_for_library(libraries_root, "SSSP")

    variant_statuses: Dict[str, LibraryVariantStatus] = {}
    installed_variants: List[str] = []

    for variant in ["precision", "efficiency"]:
        # Find matching install
        match = next(
            (i for i in installs if i["variant"] == variant),
            None,
        )
        if match and match["upf_count"] > 0:
            installed_variants.append(variant)
            variant_statuses[variant] = LibraryVariantStatus(
                variant=variant,
                installed=True,
                path=str(match["path"]),
                file_count=match["upf_count"],
                size_bytes=match["size_bytes"],
                version=match["version"],
                path_checked=str(match["path"]),
            )
        else:
            variant_statuses[variant] = LibraryVariantStatus(
                variant=variant,
                installed=False,
                path_checked=str(libraries_root / "SSSP" / variant) if libraries_root.is_dir() else None,
            )

    if len(installed_variants) == 0:
        status = "not_installed"
    elif len(installed_variants) == 2:
        status = "installed"
    else:
        status = "partial"

    return LibraryStatus(
        library_id="sssp",
        name="SSSP",
        installed_variants=installed_variants,
        variant_statuses=list(variant_statuses.values()),
        status=status,
    )


def install_library(
    library_id: str,
    variants: List[str],
    source: Literal["github_release", "local_archive", "seed"] = "github_release",
    local_archive_paths: Optional[List[str]] = None,
    config: Optional[PseudoConfig] = None,
    force: bool = False,
    allow_download: bool = True,
) -> Dict[str, Any]:
    """Install a library with specified variants using NEW pipeline."""
    if config is None:
        config = load_pseudo_config()

    if library_id == "sssp":
        return _install_sssp(variants=variants, config=config)

    return {
        "success": False,
        "errors": [f"Unsupported library: {library_id}"],
        "messages": [],
        "warnings": [],
    }


def _install_sssp(variants: List[str], config: PseudoConfig) -> Dict[str, Any]:
    """Install SSSP library variants using NEW pipeline."""
    from qmatsuite.pseudo.pipeline import download_and_install

    results_list = []
    for variant in variants:
        if variant not in ["precision", "efficiency"]:
            continue
        result = download_and_install(
            library="sssp",
            variant=variant,
            version="1.3.0",
        )
        results_list.append(result)

    if not results_list:
        return {
            "success": False,
            "errors": ["No valid variants specified"],
            "messages": [],
            "warnings": [],
        }

    return {
        "success": all(r.get("success") for r in results_list),
        "messages": [msg for r in results_list for msg in r.get("messages", [])],
        "errors": [err for r in results_list for err in r.get("errors", [])],
        "warnings": [],
    }


def remove_library(
    library_id: str,
    variants: List[str],
    config: Optional[PseudoConfig] = None,
) -> Dict[str, Any]:
    """Remove library variants from store."""
    if config is None:
        config = load_pseudo_config()

    if library_id == "sssp":
        return _remove_sssp(variants)

    return {
        "success": False,
        "errors": [f"Unsupported library: {library_id}"],
        "messages": [],
    }


def _remove_sssp(variants: List[str]) -> Dict[str, Any]:
    """Remove SSSP variants from NEW layout."""
    libraries_root = home_pseudo_libraries_dir()
    removed = []
    errors = []

    for variant in variants:
        if variant not in ["precision", "efficiency"]:
            continue

        # NEW layout: SSSP/<variant>/
        variant_dir = libraries_root / "SSSP" / variant
        if variant_dir.exists():
            try:
                shutil.rmtree(variant_dir)
                removed.append(variant)
            except Exception as e:
                errors.append(f"Failed to remove {variant}: {e}")
        else:
            errors.append(f"{variant} not installed")

    return {
        "success": len(removed) > 0 and len(errors) == 0,
        "messages": [f"Removed: {', '.join(removed)}"] if removed else [],
        "errors": errors,
    }


def repair_library(
    library_id: str,
    variants: List[str],
    config: Optional[PseudoConfig] = None,
) -> Dict[str, Any]:
    """Repair library by re-downloading via NEW pipeline."""
    if config is None:
        config = load_pseudo_config()

    if library_id == "sssp":
        return _repair_sssp(variants)

    return {
        "success": False,
        "errors": [f"Unsupported library: {library_id}"],
        "messages": [],
    }


def _repair_sssp(variants: List[str]) -> Dict[str, Any]:
    """Repair SSSP by deleting and re-downloading."""
    from qmatsuite.pseudo.pipeline import download_and_install

    libraries_root = home_pseudo_libraries_dir()
    results_list = []

    for variant in variants:
        if variant not in ["precision", "efficiency"]:
            continue

        # Delete existing install
        variant_dir = libraries_root / "SSSP" / variant
        if variant_dir.exists():
            shutil.rmtree(variant_dir, ignore_errors=True)

        # Re-download
        result = download_and_install(
            library="sssp",
            variant=variant,
            version="1.3.0",
        )
        results_list.append(result)

    if not results_list:
        return {
            "success": False,
            "errors": ["No valid variants specified"],
            "messages": [],
        }

    return {
        "success": all(r.get("success") for r in results_list),
        "messages": [msg for r in results_list for msg in r.get("messages", [])],
        "errors": [err for r in results_list for err in r.get("errors", [])],
    }


def compute_store_size(config: Optional[PseudoConfig] = None) -> Optional[int]:
    """Compute total size of store directory in bytes."""
    libraries_root = home_pseudo_libraries_dir()
    if not libraries_root.exists():
        return 0

    try:
        total = 0
        for file_path in libraries_root.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
        return total
    except Exception:
        return None
