"""
Generic pseudopotential archive installation and management.

This module provides generic functions for installing and managing
pseudopotential archives from MANIFEST_PSEUDO_SEED.json, independent
of specific library types (SSSP, PseudoDojo, etc.).

Key principles:
- Archives are stored in a canonical location: <install_root>/archives/<filename>
- Installation is verified by SHA256 checksum
- Seed cache stores archives only (never extracted content)
- All operations are idempotent
- Uses vendored MANIFEST_PSEUDO_SEED.json (no runtime GitHub fetches)
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from quantumvitas.core.pseudo_config import (
    PseudoConfig,
    load_pseudo_config,
    compute_sha256,
    get_ssl_context,
)
from quantumvitas.core.pseudo_libinfo import load_pseudo_libinfo_bundle
import urllib.request
import urllib.error
import socket


def get_pseudo_install_root(config: Optional[PseudoConfig] = None) -> Optional[Path]:
    """
    Get the root directory for installed pseudopotential archives.
    
    Uses store_dir from config, or returns None if not configured.
    
    Args:
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Path to install root, or None if not configured
    """
    if config is None:
        config = load_pseudo_config()
    
    if not config.store_dir:
        return None
    
    return Path(config.store_dir)


def get_archives_dir(install_root: Path) -> Path:
    """
    Get the archives directory within install root.
    
    Canonical layout: <install_root>/archives/
    
    Args:
        install_root: Root directory for pseudo installations
        
    Returns:
        Path to archives directory
    """
    return install_root / "archives"


def list_installed_archives(
    install_root: Optional[Path] = None,
    config: Optional[PseudoConfig] = None,
) -> Dict[str, str]:
    """
    List all installed archives with their SHA256 hashes.
    
    Scans <install_root>/archives/ for archive files (tar.gz, tgz, tar, zip).
    Computes SHA256 for each file.
    
    Args:
        install_root: Optional install root (uses config if not provided)
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Dict mapping archive_filename -> sha256
    """
    if install_root is None:
        install_root = get_pseudo_install_root(config)
        if install_root is None:
            return {}
    
    archives_dir = get_archives_dir(install_root)
    if not archives_dir.exists():
        return {}
    
    result: Dict[str, str] = {}
    archive_extensions = {".tar.gz", ".tgz", ".tar", ".zip"}
    
    for archive_file in archives_dir.iterdir():
        if not archive_file.is_file():
            continue
        
        if archive_file.suffix.lower() in archive_extensions or \
           archive_file.suffixes[-2:] == [".tar", ".gz"]:
            try:
                sha256 = compute_sha256(archive_file)
                result[archive_file.name] = sha256
            except Exception:
                # Skip files that can't be hashed
                continue
    
    return result


def check_archive_status(
    asset_name: str,
    expected_sha256: str,
    install_root: Optional[Path] = None,
    config: Optional[PseudoConfig] = None,
) -> Dict[str, Any]:
    """
    Check archive installation status with detailed result.
    
    Args:
        asset_name: Archive filename (e.g., "SSSP_1.3.0_PBE_efficiency.tar.gz")
        expected_sha256: Expected SHA256 hash from manifest
        install_root: Optional install root (uses config if not provided)
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Dict with:
        - installed: bool - True if exists and SHA256 matches
        - exists: bool - True if file exists
        - corrupt: bool - True if exists but SHA256 mismatch
        - actual_sha256: Optional[str] - Actual SHA256 if file exists
        - error: Optional[str] - Error message if check failed
    """
    result = {
        "installed": False,
        "exists": False,
        "corrupt": False,
        "actual_sha256": None,
        "error": None,
    }
    
    if install_root is None:
        install_root = get_pseudo_install_root(config)
        if install_root is None:
            return result
    
    archives_dir = get_archives_dir(install_root)
    archive_path = archives_dir / asset_name
    
    if not archive_path.exists() or not archive_path.is_file():
        return result
    
    result["exists"] = True
    
    try:
        actual_sha256 = compute_sha256(archive_path)
        result["actual_sha256"] = actual_sha256
        
        if actual_sha256.lower() == expected_sha256.lower():
            result["installed"] = True
        else:
            result["corrupt"] = True
            result["error"] = f"SHA256 mismatch: expected {expected_sha256[:16]}..., got {actual_sha256[:16]}..."
    except Exception as e:
        result["error"] = f"Failed to compute SHA256: {e}"
        result["corrupt"] = True
    
    return result


def is_archive_installed(
    asset_name: str,
    expected_sha256: str,
    install_root: Optional[Path] = None,
    config: Optional[PseudoConfig] = None,
) -> bool:
    """
    Check if an archive is installed and matches expected SHA256.
    
    Args:
        asset_name: Archive filename (e.g., "SSSP_1.3.0_PBE_efficiency.tar.gz")
        expected_sha256: Expected SHA256 hash from manifest
        install_root: Optional install root (uses config if not provided)
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        True if archive exists and SHA256 matches, False otherwise
    """
    status = check_archive_status(asset_name, expected_sha256, install_root, config)
    return status["installed"]


def install_archive(
    asset_url: str,
    asset_name: str,
    expected_sha256: str,
    expected_size: Optional[int] = None,
    install_root: Optional[Path] = None,
    config: Optional[PseudoConfig] = None,
) -> Dict[str, Any]:
    """
    Download and install an archive with SHA256 verification.
    
    This function:
    1. Downloads archive to temporary location
    2. Verifies SHA256 checksum
    3. Verifies size (if provided)
    4. Moves to canonical location atomically
    5. Is idempotent: if archive exists and matches, returns success without re-downloading
    
    IMPORTANT: This function should only be called from Settings/user-invoked code paths,
    not from runtime src/ code paths.
    
    Args:
        asset_url: URL to download archive from
        asset_name: Archive filename (e.g., "SSSP_1.3.0_PBE_efficiency.tar.gz")
        expected_sha256: Expected SHA256 hash from manifest
        expected_size: Optional expected file size in bytes
        install_root: Optional install root (uses config if not provided)
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Dict with success, messages, errors
    """
    result: Dict[str, Any] = {
        "success": False,
        "messages": [],
        "errors": [],
    }
    
    if install_root is None:
        install_root = get_pseudo_install_root(config)
        if install_root is None:
            result["errors"].append("Install root not configured (store_dir not set)")
            return result
    
    archives_dir = get_archives_dir(install_root)
    archive_path = archives_dir / asset_name
    
    # Check if already installed and matches
    if is_archive_installed(asset_name, expected_sha256, install_root, config):
        result["success"] = True
        result["messages"].append(f"Archive already installed: {asset_name}")
        return result
    
    # Create archives directory if needed
    try:
        archives_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        result["errors"].append(f"Failed to create archives directory: {e}")
        return result
    
    # Download to temporary location first
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(asset_name).suffix) as temp_file:
            temp_path = Path(temp_file.name)
        
        result["messages"].append(f"Downloading {asset_name} from {asset_url}...")
        
        # Download with SSL verification
        try:
            socket.setdefaulttimeout(120)
            with urllib.request.urlopen(asset_url, context=get_ssl_context()) as response:
                with open(temp_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
            socket.setdefaulttimeout(None)
        except urllib.error.URLError as e:
            socket.setdefaulttimeout(None)
            temp_path.unlink(missing_ok=True)
            result["errors"].append(f"Failed to download {asset_name}: {e}")
            return result
        except Exception as e:
            socket.setdefaulttimeout(None)
            temp_path.unlink(missing_ok=True)
            result["errors"].append(f"Download failed: {e}")
            return result
        
        # Verify size if provided
        if expected_size is not None:
            actual_size = temp_path.stat().st_size
            if actual_size != expected_size:
                temp_path.unlink()
                result["errors"].append(
                    f"Size mismatch: expected {expected_size} bytes, got {actual_size} bytes"
                )
                return result
        
        # Verify SHA256
        actual_sha256 = compute_sha256(temp_path)
        if actual_sha256.lower() != expected_sha256.lower():
            temp_path.unlink()
            result["errors"].append(
                f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}"
            )
            return result
        
        # Atomic move to final location
        # If existing file has wrong hash, replace it
        if archive_path.exists():
            try:
                archive_path.unlink()
            except Exception as e:
                result["errors"].append(f"Failed to remove existing archive: {e}")
                temp_path.unlink()
                return result
        
        shutil.move(str(temp_path), str(archive_path))
        result["success"] = True
        result["messages"].append(
            f"✓ Installed {asset_name} (SHA256: {expected_sha256[:16]}...)"
        )
        
    except Exception as e:
        result["errors"].append(f"Installation failed: {e}")
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
    
    return result


def get_seed_cache_dir(config: Optional[PseudoConfig] = None) -> Optional[Path]:
    """
    Get the seed cache directory.
    
    Args:
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Path to seed cache directory, or None if not configured
    """
    if config is None:
        config = load_pseudo_config()
    
    if not config.seed_dir:
        return None
    
    return Path(config.seed_dir)


def save_archive_to_seed_cache(
    archive_path: Path,
    library_name: str,
    version: str,
    asset_name: str,
    expected_sha256: str,
    config: Optional[PseudoConfig] = None,
) -> Dict[str, Any]:
    """
    Save an archive to seed cache with deterministic naming.
    
    Seed cache structure: <seed_dir>/<library_name>/<version>/<asset_name>
    
    Args:
        archive_path: Path to archive file (from install or user-provided)
        library_name: Library name (e.g., "sssp")
        version: Library version (e.g., "1.3.0")
        asset_name: Archive filename
        expected_sha256: Expected SHA256 for verification
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Dict with success, messages, errors
    """
    result: Dict[str, Any] = {
        "success": False,
        "messages": [],
        "errors": [],
    }
    
    seed_dir = get_seed_cache_dir(config)
    if seed_dir is None:
        result["errors"].append("Seed cache directory not configured")
        return result
    
    # Verify source archive SHA256
    try:
        actual_sha256 = compute_sha256(archive_path)
        if actual_sha256.lower() != expected_sha256.lower():
            result["errors"].append(
                f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}"
            )
            return result
    except Exception as e:
        result["errors"].append(f"Failed to verify source archive: {e}")
        return result
    
    # Build target path
    target_dir = seed_dir / library_name.lower() / version
    target_path = target_dir / asset_name
    
    # Check if already exists with correct hash
    if target_path.exists():
        try:
            existing_sha256 = compute_sha256(target_path)
            if existing_sha256.lower() == expected_sha256.lower():
                result["success"] = True
                result["messages"].append(f"Archive already in seed cache: {asset_name}")
                return result
        except Exception:
            pass
    
    # Create target directory
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        result["errors"].append(f"Failed to create seed cache directory: {e}")
        return result
    
    # Copy to seed cache
    try:
        shutil.copy2(archive_path, target_path)
        result["success"] = True
        result["messages"].append(f"Saved to seed cache: {target_path}")
    except Exception as e:
        result["errors"].append(f"Failed to copy to seed cache: {e}")
        return result
    
    return result


@dataclass
class ArchiveStatus:
    """Status of an archive from MANIFEST_PSEUDO_SEED.json."""
    asset_name: str
    relative_path: str
    sha256: str
    size_bytes: int
    library_name: str
    library_version: str
    xc: Optional[str] = None
    quality: Optional[str] = None
    type: Optional[str] = None
    relativistic: Optional[str] = None
    category: Optional[str] = None
    installed: bool = False
    corrupt: bool = False  # True if exists but SHA256 mismatch
    warning: Optional[str] = None  # Warning message (e.g., "needs reinstall")
    upstream_url: Optional[str] = None  # URL to download from GitHub release
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_name": self.asset_name,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "library_name": self.library_name,
            "library_version": self.library_version,
            "xc": self.xc,
            "quality": self.quality,
            "type": self.type,
            "relativistic": self.relativistic,
            "category": self.category,
            "installed": self.installed,
            "corrupt": self.corrupt,
            "warning": self.warning,
            "upstream_url": self.upstream_url,
        }


def load_manifest_archives() -> List[ArchiveStatus]:
    """
    Load all archive entries from vendored MANIFEST_PSEUDO_SEED.json.
    
    Only includes archive files (tar.gz, tgz, tar, zip), excludes JSON files.
    
    Returns:
        List of ArchiveStatus objects
    """
    bundle = load_pseudo_libinfo_bundle()
    manifest_data = bundle.manifest
    
    if not isinstance(manifest_data, dict) or "files" not in manifest_data:
        raise RuntimeError("MANIFEST_PSEUDO_SEED.json missing 'files' array")
    
    archives: List[ArchiveStatus] = []
    archive_extensions = {".tar.gz", ".tgz", ".tar", ".zip"}
    
    # Get release tag for building upstream URLs
    tag = bundle.tag
    base_url = f"https://github.com/QMatSuite/qmatsuite-assets/releases/download/{tag}"
    
    for entry in manifest_data["files"]:
        if not isinstance(entry, dict):
            continue
        
        relative_path = entry.get("relative_path", "")
        # Only include archive files, not .json cutoffs
        if not any(relative_path.endswith(ext) for ext in archive_extensions):
            continue
        
        asset_name = Path(relative_path).name
        upstream_url = f"{base_url}/{asset_name}"
        
        archive = ArchiveStatus(
            asset_name=asset_name,
            relative_path=relative_path,
            sha256=entry.get("sha256", ""),
            size_bytes=entry.get("size_bytes", 0),
            library_name=entry.get("library_name", ""),
            library_version=entry.get("library_version", ""),
            xc=entry.get("xc"),
            quality=entry.get("quality"),
            type=entry.get("type"),
            relativistic=entry.get("relativistic"),
            category=entry.get("category"),
            installed=False,  # Will be set by check_archives_status
            upstream_url=upstream_url,
        )
        archives.append(archive)
    
    return archives


def check_archives_status(
    archives: Optional[List[ArchiveStatus]] = None,
    install_root: Optional[Path] = None,
    config: Optional[PseudoConfig] = None,
) -> List[ArchiveStatus]:
    """
    Check installation status for a list of archives.
    
    Args:
        archives: Optional list of ArchiveStatus (loads from manifest if not provided)
        install_root: Optional install root (uses config if not provided)
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        List of ArchiveStatus with installed/corrupt/warning flags set
    """
    if archives is None:
        archives = load_manifest_archives()
    
    if install_root is None:
        install_root = get_pseudo_install_root(config)
    
    for archive in archives:
        if install_root:
            status = check_archive_status(
                archive.asset_name,
                archive.sha256,
                install_root,
                config,
            )
            archive.installed = status["installed"]
            archive.corrupt = status["corrupt"]
            if status["corrupt"]:
                archive.warning = status.get("error") or "Archive exists but SHA256 mismatch. Needs reinstall."
        else:
            archive.installed = False
            archive.corrupt = False
            archive.warning = None
    
    return archives

