"""
Generic Library Manager for pseudopotential libraries.

This module provides a generic interface for managing libraries (SSSP, PseudoDojo, etc.)
while wrapping existing library-specific implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from quantumvitas.core.pseudo_config import (
    PseudoConfig,
    load_pseudo_config,
    list_installed_sssp,
    download_sssp_library,
    download_all_sssp,
    install_sssp_from_seed,
    install_all_sssp_from_seed,
    import_seed_archives,
    get_sssp_library_path,
    get_sssp_seed_path,
    SSSPLibraryInfo,
    SeedArchiveInfo,
    list_seed_archives,
)


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
    """
    Get metadata for all supported libraries.
    
    Returns:
        List of LibraryMetadata objects
    """
    return [
        LibraryMetadata(
            id="sssp",
            name="SSSP",
            description="Standard Solid State Pseudopotentials",
            supported_variants=["precision", "efficiency"],
            default_variants=["precision"],  # Precision recommended
        ),
        # Future: Add PseudoDojo, etc.
    ]


def get_library_status(
    library_id: str,
    config: Optional[PseudoConfig] = None,
) -> Optional[LibraryStatus]:
    """
    Get status of a library (which variants are installed).
    
    Args:
        library_id: Library identifier (e.g., "sssp")
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        LibraryStatus or None if library_id not supported
    """
    if config is None:
        config = load_pseudo_config()
    
    if library_id == "sssp":
        return _get_sssp_status(config)
    
    return None


def _get_sssp_status(config: PseudoConfig) -> LibraryStatus:
    """
    Get SSSP library status by directly checking the filesystem.
    
    Detection rules:
    - precision installed iff <store_dir>/sssp/1.3.0/precision/library exists and contains at least 1 *.UPF
    - efficiency installed iff <store_dir>/sssp/1.3.0/efficiency/library exists and contains at least 1 *.UPF
    """
    if not config.store_dir:
        return LibraryStatus(
            library_id="sssp",
            name="SSSP",
            installed_variants=[],
            variant_statuses=[
                LibraryVariantStatus(variant="precision", installed=False, path_checked=None),
                LibraryVariantStatus(variant="efficiency", installed=False, path_checked=None),
            ],
            status="not_installed",
        )
    
    store_dir = Path(config.store_dir)
    version = "1.3.0"  # Latest version only for now
    
    # Directly check each variant's library directory
    variant_statuses: Dict[str, LibraryVariantStatus] = {}
    installed_variants: List[str] = []
    
    for variant in ["precision", "efficiency"]:
        # Build expected path: <store_dir>/sssp/1.3.0/{variant}/library
        lib_path = get_sssp_library_path(store_dir, version, variant)
        library_path = lib_path / "library"
        path_checked = str(library_path)
        
        installed = False
        file_count = 0
        size_bytes = None
        version_str = version
        
        # Check if library directory exists and has UPF files
        if library_path.exists() and library_path.is_dir():
            upf_files = list(library_path.glob("*.UPF")) + list(library_path.glob("*.upf"))
            file_count = len(upf_files)
            
            if file_count > 0:
                installed = True
                installed_variants.append(variant)
                
                # Compute size
                try:
                    size_bytes = sum(f.stat().st_size for f in library_path.rglob("*") if f.is_file())
                except Exception:
                    pass
        
        variant_statuses[variant] = LibraryVariantStatus(
            variant=variant,
            installed=installed,
            path=str(lib_path) if installed else None,
            file_count=file_count,
            size_bytes=size_bytes,
            version=version_str if installed else None,
            path_checked=path_checked,
        )
    
    # Determine overall status
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
    """
    Install a library with specified variants.
    
    Args:
        library_id: Library identifier (e.g., "sssp")
        variants: List of variant names to install (e.g., ["precision", "efficiency"])
        source: Installation source
        local_archive_paths: For source="local_archive", paths to archive files
        config: Optional PseudoConfig (loads if not provided)
        force: If True, download even if allow_download is False
        allow_download: Global setting for network downloads
        
    Returns:
        Dict with success, messages, errors, warnings
    """
    if config is None:
        config = load_pseudo_config()
    
    if library_id == "sssp":
        return _install_sssp(
            variants=variants,
            source=source,
            local_archive_paths=local_archive_paths,
            config=config,
            force=force,
            allow_download=allow_download,
        )
    
    return {
        "success": False,
        "errors": [f"Unsupported library: {library_id}"],
        "messages": [],
        "warnings": [],
    }


def _install_sssp(
    variants: List[str],
    source: str,
    local_archive_paths: Optional[List[str]],
    config: PseudoConfig,
    force: bool,
    allow_download: bool,
) -> Dict[str, Any]:
    """Install SSSP library variants."""
    if not config.store_dir:
        return {
            "success": False,
            "errors": ["Store directory not configured"],
            "messages": [],
            "warnings": [],
        }
    
    store_dir = Path(config.store_dir)
    seed_dir = Path(config.seed_dir) if config.seed_dir else None
    
    if source == "github_release":
        # Use existing download functions
        if len(variants) == 2 and "precision" in variants and "efficiency" in variants:
            # Install all
            return download_all_sssp(
                store_dir=store_dir,
                force=force,
                allow_download=allow_download,
                seed_dir=seed_dir,
            )
        else:
            # Install specific variants
            results = []
            for variant in variants:
                if variant not in ["precision", "efficiency"]:
                    continue
                result = download_sssp_library(
                    store_dir=store_dir,
                    flavor=variant,
                    version="1.3.0",
                    force=force,
                    allow_download=allow_download,
                    seed_dir=seed_dir,
                )
                results.append(result)
            
            # Combine results
            combined = {
                "success": all(r["success"] for r in results),
                "messages": [msg for r in results for msg in r.get("messages", [])],
                "errors": [err for r in results for err in r.get("errors", [])],
                "warnings": [warn for r in results for warn in r.get("warnings", [])],
            }
            return combined
    
    elif source == "local_archive":
        if not local_archive_paths:
            return {
                "success": False,
                "errors": ["No archive paths provided for local_archive source"],
                "messages": [],
                "warnings": [],
            }
        
        if not seed_dir:
            return {
                "success": False,
                "errors": ["Seed directory not configured (required for local archive import)"],
                "messages": [],
                "warnings": [],
            }
        
        # Import archives into seed
        import_result = import_seed_archives(seed_dir, [Path(p) for p in local_archive_paths])
        
        if import_result["errors"]:
            return {
                "success": False,
                "errors": import_result["errors"],
                "messages": import_result.get("imported", []),
                "warnings": import_result.get("skipped", []),
            }
        
        # Then install from seed
        return install_all_sssp_from_seed(seed_dir, store_dir)
    
    elif source == "seed":
        if not seed_dir:
            return {
                "success": False,
                "errors": ["Seed directory not configured"],
                "messages": [],
                "warnings": [],
            }
        
        # Install from seed
        if len(variants) == 2:
            return install_all_sssp_from_seed(seed_dir, store_dir)
        else:
            results = []
            for variant in variants:
                if variant not in ["precision", "efficiency"]:
                    continue
                result = install_sssp_from_seed(
                    seed_dir=seed_dir,
                    store_dir=store_dir,
                    version="1.3.0",
                    flavor=variant,
                )
                results.append(result)
            
            combined = {
                "success": all(r["success"] for r in results),
                "messages": [msg for r in results for msg in r.get("messages", [])],
                "errors": [err for r in results for err in r.get("errors", [])],
                "warnings": [],
            }
            return combined
    
    return {
        "success": False,
        "errors": [f"Unsupported source: {source}"],
        "messages": [],
        "warnings": [],
    }


def remove_library(
    library_id: str,
    variants: List[str],
    config: Optional[PseudoConfig] = None,
) -> Dict[str, Any]:
    """
    Remove library variants from store.
    
    Args:
        library_id: Library identifier
        variants: List of variant names to remove
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Dict with success, messages, errors
    """
    if config is None:
        config = load_pseudo_config()
    
    if not config.store_dir:
        return {
            "success": False,
            "errors": ["Store directory not configured"],
            "messages": [],
        }
    
    if library_id == "sssp":
        return _remove_sssp(variants, config)
    
    return {
        "success": False,
        "errors": [f"Unsupported library: {library_id}"],
        "messages": [],
    }


def _remove_sssp(variants: List[str], config: PseudoConfig) -> Dict[str, Any]:
    """Remove SSSP variants."""
    import shutil
    
    store_dir = Path(config.store_dir)
    removed = []
    errors = []
    
    for variant in variants:
        if variant not in ["precision", "efficiency"]:
            continue
        
        lib_path = get_sssp_library_path(store_dir, "1.3.0", variant)
        
        if lib_path.exists():
            try:
                shutil.rmtree(lib_path)
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
    """
    Repair library by re-extracting from seed cache.
    
    Args:
        library_id: Library identifier
        variants: List of variant names to repair
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Dict with success, messages, errors
    """
    if config is None:
        config = load_pseudo_config()
    
    if not config.seed_dir:
        return {
            "success": False,
            "errors": ["Seed directory not configured"],
            "messages": [],
        }
    
    if library_id == "sssp":
        return _repair_sssp(variants, config)
    
    return {
        "success": False,
        "errors": [f"Unsupported library: {library_id}"],
        "messages": [],
    }


def _repair_sssp(variants: List[str], config: PseudoConfig) -> Dict[str, Any]:
    """Repair SSSP by re-extracting from seed."""
    seed_dir = Path(config.seed_dir)
    store_dir = Path(config.store_dir)
    
    if not seed_dir.exists():
        return {
            "success": False,
            "errors": ["Seed directory does not exist"],
            "messages": [],
        }
    
    # Check if seed has archives
    seed_archives = list_seed_archives(seed_dir)
    if not seed_archives:
        return {
            "success": False,
            "errors": ["No archives found in seed cache"],
            "messages": [],
        }
    
    # Install from seed (re-extract)
    if len(variants) == 2:
        return install_all_sssp_from_seed(seed_dir, store_dir)
    else:
        results = []
        for variant in variants:
            if variant not in ["precision", "efficiency"]:
                continue
            result = install_sssp_from_seed(
                seed_dir=seed_dir,
                store_dir=store_dir,
                version="1.3.0",
                flavor=variant,
            )
            results.append(result)
        
        combined = {
            "success": all(r["success"] for r in results),
            "messages": [msg for r in results for msg in r.get("messages", [])],
            "errors": [err for r in results for err in r.get("errors", [])],
        }
        return combined


def compute_store_size(config: Optional[PseudoConfig] = None) -> Optional[int]:
    """
    Compute total size of store directory in bytes.
    
    Args:
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Total size in bytes, or None if store_dir not configured
    """
    if config is None:
        config = load_pseudo_config()
    
    if not config.store_dir:
        return None
    
    store_dir = Path(config.store_dir)
    if not store_dir.exists():
        return 0
    
    try:
        total = 0
        for file_path in store_dir.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
        return total
    except Exception:
        return None

