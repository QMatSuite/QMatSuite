"""
Pseudopotential configuration and management.

This module provides:
- PseudoConfig: Settings for pseudo store, seed, and downloads
- PseudoStore: Manager for SSSP installation and resolution
- Resolution flow: resources/pseudo → project → store → seed → download
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import ssl
import tarfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import certifi

from quantumvitas.core.paths import (
    home_pseudo_libraries_dir,
    home_pseudo_seeds_dir,
    tmp_downloads_dir,
    tmp_unpack_dir,
)

logger = logging.getLogger(__name__)

# Centralized SSL context using certifi CA bundle for production-grade HTTPS
# This ensures SSL verification works across all platforms (macOS, Linux, Windows)
# without requiring system CA certificate installation
# Lazy-loaded to avoid import-time permission errors
_SSL_CONTEXT = None

def get_ssl_context() -> ssl.SSLContext:
    """Get or create the SSL context with certifi CA bundle."""
    global _SSL_CONTEXT
    if _SSL_CONTEXT is None:
        _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
    return _SSL_CONTEXT

# Export as SSL_CONTEXT for convenience (it's a function that returns the context)
SSL_CONTEXT = get_ssl_context

# GitHub release configuration
GITHUB_REPO_OWNER = "QMatSuite"
GITHUB_REPO_NAME = "qmatsuite-assets"
GITHUB_RELEASE_TAG = "assets-2025-12-26"
GITHUB_RELEASE_BASE_URL = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/download/{GITHUB_RELEASE_TAG}"


def _find_quantumvitas_root() -> Optional[Path]:
    """
    Find the quantumvitas root directory (containing src/quantumvitas).
    
    Returns None if not found.
    """
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "src" / "quantumvitas").exists():
            return current
        current = current.parent
    return None


@dataclass
class PseudoConfig:
    """
    Pseudopotential configuration settings.
    
    These are user-level settings, NOT stored in git.
    Persisted in a user config file outside of project directories.
    
    Attributes:
        store_dir: Global pseudo store directory (default: .qmatsuite/libraries/pseudo)
        seed_dir: Seed directory for offline installation (default: .qmatsuite/seeds/pseudo)
        allow_download: Whether to allow network downloads (default: False)
        network_pseudo_base_url: Base URL for QE pseudopotential downloads (default: QE official)
        legacy_tables_base_url: Base URL for QE legacy tables (default: QE official)
    """
    store_dir: str = ""
    seed_dir: str = ""
    allow_download: bool = False
    network_pseudo_base_url: str = "https://pseudopotentials.quantum-espresso.org/upf_files"
    legacy_tables_base_url: str = "https://pseudopotentials.quantum-espresso.org/legacy_tables"
    
    @classmethod
    def get_default_store_dir(cls) -> str:
        """Get default store directory path (.qmatsuite/libraries/pseudo)."""
        try:
            return str(home_pseudo_libraries_dir())
        except Exception:
            return ""
    
    @classmethod
    def get_default_seed_dir(cls) -> str:
        """Get default seed directory path (.qmatsuite/seeds/pseudo)."""
        try:
            return str(home_pseudo_seeds_dir())
        except Exception:
            return ""
    
    @classmethod
    def with_defaults(cls) -> "PseudoConfig":
        """Create a config with default values."""
        return cls(
            store_dir=cls.get_default_store_dir(),
            seed_dir=cls.get_default_seed_dir(),
            allow_download=False,
            network_pseudo_base_url="https://pseudopotentials.quantum-espresso.org/upf_files",
            legacy_tables_base_url="https://pseudopotentials.quantum-espresso.org/legacy_tables",
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PseudoConfig":
        """Create from dict, applying defaults for missing fields."""
        defaults = cls.with_defaults()
        return cls(
            store_dir=data.get("store_dir") or defaults.store_dir,
            seed_dir=data.get("seed_dir") or defaults.seed_dir,
            allow_download=data.get("allow_download", defaults.allow_download),
            network_pseudo_base_url=data.get("network_pseudo_base_url") or defaults.network_pseudo_base_url,
            legacy_tables_base_url=data.get("legacy_tables_base_url") or defaults.legacy_tables_base_url,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return asdict(self)


def get_user_config_path() -> Path:
    """
    Get path to user config file.
    
    On macOS: ~/Library/Application Support/QuantumVITAS/config.json
    On Linux: ~/.config/quantumvitas/config.json
    On Windows: %APPDATA%/QuantumVITAS/config.json
    """
    import platform
    
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "QuantumVITAS"
    elif system == "Windows":
        appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        base = appdata / "QuantumVITAS"
    else:
        # Linux and others
        base = Path.home() / ".config" / "quantumvitas"
    
    return base / "config.json"


import os


def load_pseudo_config() -> PseudoConfig:
    """
    Load pseudo config from user config file.
    
    Returns config with defaults if file doesn't exist or has errors.
    """
    config_path = get_user_config_path()
    
    if not config_path.exists():
        return PseudoConfig.with_defaults()
    
    try:
        data = json.loads(config_path.read_text())
        pseudo_data = data.get("pseudo", {})
        return PseudoConfig.from_dict(pseudo_data)
    except Exception as e:
        logger.warning(f"Failed to load pseudo config: {e}")
        return PseudoConfig.with_defaults()


def save_pseudo_config(config: PseudoConfig) -> None:
    """
    Save pseudo config to user config file.
    
    Preserves other settings in the config file.
    """
    config_path = get_user_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing config
    existing: Dict[str, Any] = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
        except Exception:
            pass
    
    # Update pseudo section
    existing["pseudo"] = config.to_dict()
    
    # Save
    config_path.write_text(json.dumps(existing, indent=2))
    logger.info(f"Saved pseudo config to {config_path}")


@dataclass
class ValidationResult:
    """Result of validating pseudo configuration."""
    ok: bool = True
    repo_pseudo_exists: bool = False
    store_dir_exists: bool = False
    store_dir_writable: bool = False
    seed_dir_exists: bool = False
    seed_has_sssp: bool = False
    messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def validate_pseudo_config(config: PseudoConfig) -> ValidationResult:
    """
    Validate pseudo configuration.
    
    Checks:
    - repo/pseudo exists (committed pseudos for demos/tests)
    - store_dir exists or can be created + writable
    - seed_dir exists (optional) + if exists, contains expected seed layout
    """
    result = ValidationResult()
    
    # Check resources/pseudo (always should exist)
    repo_root = _find_quantumvitas_root()
    if repo_root:
        repo_pseudo = repo_root / "resources" / "pseudo"
        result.repo_pseudo_exists = repo_pseudo.exists()
        if result.repo_pseudo_exists:
            result.messages.append(f"✓ Repo pseudo dir: {repo_pseudo}")
        else:
            result.warnings.append(f"Repo pseudo dir not found: {repo_pseudo}")
    else:
        result.warnings.append("Could not find quantumvitas repo root")
    
    # Check store_dir
    if config.store_dir:
        store_path = Path(config.store_dir)
        result.store_dir_exists = store_path.exists()
        
        if result.store_dir_exists:
            result.messages.append(f"✓ Store dir exists: {store_path}")
            # Check writable
            try:
                test_file = store_path / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
                result.store_dir_writable = True
                result.messages.append("✓ Store dir is writable")
            except Exception as e:
                result.store_dir_writable = False
                result.errors.append(f"Store dir not writable: {e}")
                result.ok = False
        else:
            # Check if parent exists and is writable
            parent = store_path.parent
            if parent.exists():
                try:
                    test_file = parent / ".write_test_pseudo"
                    test_file.write_text("test")
                    test_file.unlink()
                    result.store_dir_writable = True
                    result.messages.append(f"Store dir does not exist but can be created: {store_path}")
                except Exception as e:
                    result.store_dir_writable = False
                    result.errors.append(f"Cannot create store dir: {e}")
                    result.ok = False
            else:
                result.messages.append(f"Store dir does not exist: {store_path}")
    else:
        result.errors.append("Store dir not configured")
        result.ok = False
    
    # Check seed_dir
    if config.seed_dir:
        seed_path = Path(config.seed_dir)
        result.seed_dir_exists = seed_path.exists()
        
        if result.seed_dir_exists:
            result.messages.append(f"✓ Seed dir exists: {seed_path}")
            # Check for SSSP layout
            sssp_dir = seed_path / "sssp"
            if sssp_dir.exists():
                result.seed_has_sssp = True
                result.messages.append("✓ Seed contains SSSP data")
            else:
                result.warnings.append("Seed dir exists but no SSSP data found")
        else:
            result.messages.append(f"Seed dir does not exist: {seed_path} (optional)")
    else:
        result.messages.append("Seed dir not configured (optional)")
    
    return result


def init_pseudo_dirs(config: PseudoConfig) -> Dict[str, Any]:
    """
    Initialize pseudo directories.
    
    Creates store_dir and seed_dir parent paths if they don't exist.
    """
    results: Dict[str, Any] = {
        "store_dir_created": False,
        "seed_dir_created": False,
        "messages": [],
        "errors": [],
    }
    
    if config.store_dir:
        store_path = Path(config.store_dir)
        try:
            store_path.mkdir(parents=True, exist_ok=True)
            results["store_dir_created"] = True
            results["messages"].append(f"Created store dir: {store_path}")
        except Exception as e:
            results["errors"].append(f"Failed to create store dir: {e}")
    
    if config.seed_dir:
        seed_path = Path(config.seed_dir)
        try:
            seed_path.mkdir(parents=True, exist_ok=True)
            results["seed_dir_created"] = True
            results["messages"].append(f"Created seed dir: {seed_path}")
        except Exception as e:
            results["errors"].append(f"Failed to create seed dir: {e}")
    
    return results


# SSSP storage layout constants
SSSP_VERSIONS = ["1.3.0", "1.2.1", "1.2.0"]
SSSP_FLAVORS = ["efficiency", "precision"]


@dataclass
class SSSPLibraryInfo:
    """Information about an installed SSSP library."""
    version: str
    flavor: str
    installed: bool = False
    path: Optional[Path] = None
    file_count: int = 0
    has_cutoffs: bool = False
    has_manifest: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.path:
            d["path"] = str(self.path)
        return d


def get_sssp_library_path(store_dir: Path, version: str, flavor: str) -> Path:
    """
    Get path to SSSP library in store.
    
    Layout: ${store_dir}/sssp/${version}/${flavor}/
    """
    return store_dir / "sssp" / version / flavor


def get_sssp_seed_path(seed_dir: Path, version: str, flavor: str) -> Path:
    """
    Get path to SSSP seed files.
    
    Layout: ${seed_dir}/sssp/${version}/${flavor}/
    """
    return seed_dir / "sssp" / version / flavor


def list_installed_sssp(store_dir: Path) -> List[SSSPLibraryInfo]:
    """List all installed SSSP libraries in store.
    
    Returns only libraries that are actually installed (have UPF files).
    """
    results = []
    
    for version in SSSP_VERSIONS:
        for flavor in SSSP_FLAVORS:
            lib_path = get_sssp_library_path(store_dir, version, flavor)
            library_path = lib_path / "library"
            
            # Only include if library directory exists and has UPF files
            if library_path.exists():
                upf_files = list(library_path.glob("*.UPF")) + list(library_path.glob("*.upf"))
                if len(upf_files) > 0:
                    info = SSSPLibraryInfo(
                        version=version,
                        flavor=flavor,
                        installed=True,
                        path=lib_path,
                        file_count=len(upf_files),
                        has_cutoffs=(lib_path / "cutoffs.json").exists(),
                        has_manifest=(lib_path / "manifest.json").exists(),
                    )
                    results.append(info)
    
    return results


@dataclass
class SeedArchiveInfo:
    """Information about a seed archive."""
    filename: str
    path: Path
    size_bytes: int
    sha256: Optional[str] = None
    version: Optional[str] = None
    flavor: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["path"] = str(self.path)
        return d


def list_seed_archives(seed_dir: Path) -> List[SeedArchiveInfo]:
    """
    List all SSSP archives in seed directory.
    
    Scans seed_dir/sssp/{version}/{flavor}/ for *.tar.gz files.
    """
    results = []
    
    if not seed_dir.exists():
        return results
    
    seed_sssp_dir = seed_dir / "sssp"
    if not seed_sssp_dir.exists():
        return results
    
    for version_dir in seed_sssp_dir.iterdir():
        if not version_dir.is_dir():
            continue
        
        version = version_dir.name
        for flavor_dir in version_dir.iterdir():
            if not flavor_dir.is_dir():
                continue
            
            flavor = flavor_dir.name
            
            # Find tar.gz archives
            archives = list(flavor_dir.glob("*.tar.gz")) + list(flavor_dir.glob("*.tgz"))
            for archive_path in archives:
                try:
                    size = archive_path.stat().st_size
                    # Try to extract SHA256 from filename if present
                    sha256 = None
                    filename = archive_path.name
                    # Format: SSSP_{version}_{flavor}_{sha256_prefix}.tar.gz
                    if "_" in filename:
                        parts = filename.replace(".tar.gz", "").replace(".tgz", "").split("_")
                        if len(parts) >= 4 and len(parts[3]) >= 16:
                            sha256 = parts[3][:64] if len(parts[3]) >= 64 else None
                    
                    info = SeedArchiveInfo(
                        filename=filename,
                        path=archive_path,
                        size_bytes=size,
                        sha256=sha256,
                        version=version,
                        flavor=flavor,
                    )
                    results.append(info)
                except Exception:
                    continue
    
    return results


def import_seed_archives(
    seed_dir: Path,
    archive_paths: List[Path],
) -> Dict[str, Any]:
    """
    Import seed archives (tar/zip) into seed_dir with SHA256 deduplication.
    
    Args:
        seed_dir: Seed directory to import into
        archive_paths: List of archive file paths to import
        
    Returns:
        Dict with:
        - imported: List of successfully imported filenames
        - skipped: List of files skipped (duplicates or invalid)
        - errors: List of error messages
    """
    import hashlib
    
    result: Dict[str, Any] = {
        "imported": [],
        "skipped": [],
        "errors": [],
    }
    
    if not seed_dir:
        result["errors"].append("Seed directory not configured")
        return result
    
    seed_dir = Path(seed_dir)
    seed_dir.mkdir(parents=True, exist_ok=True)
    
    # Build SHA256 index of existing archives for deduplication
    existing_hashes: Dict[str, Path] = {}
    for existing_archive in seed_dir.rglob("*.tar.gz"):
        try:
            sha256 = compute_sha256(existing_archive)
            existing_hashes[sha256] = existing_archive
        except Exception:
            pass
    
    for existing_archive in seed_dir.rglob("*.tgz"):
        try:
            sha256 = compute_sha256(existing_archive)
            existing_hashes[sha256] = existing_archive
        except Exception:
            pass
    
    for archive_path in archive_paths:
        archive_path = Path(archive_path)
        
        if not archive_path.exists():
            result["errors"].append(f"File not found: {archive_path}")
            continue
        
        # Validate it's a tar.gz or tgz
        if not (archive_path.suffix == ".gz" and archive_path.name.endswith((".tar.gz", ".tgz"))):
            result["skipped"].append(f"{archive_path.name}: Not a tar.gz archive")
            continue
        
        try:
            # Compute SHA256
            sha256 = compute_sha256(archive_path)
            
            # Check for duplicate
            if sha256 in existing_hashes:
                result["skipped"].append(f"{archive_path.name}: Already exists (SHA256: {sha256[:16]}...)")
                continue
            
            # Try to determine version/flavor from filename or manifest
            # For now, use a generic location - user can organize manually
            # Or we could try to extract from archive metadata
            version = "1.3.0"  # Default
            flavor = "unknown"
            
            # Try to guess from filename
            name_lower = archive_path.name.lower()
            if "efficiency" in name_lower:
                flavor = "efficiency"
            elif "precision" in name_lower:
                flavor = "precision"
            
            # Save to seed_dir/sssp/{version}/{flavor}/
            seed_path = get_sssp_seed_path(seed_dir, version, flavor)
            seed_path.mkdir(parents=True, exist_ok=True)
            
            # Use deterministic naming: SSSP_{version}_{flavor}_{sha256_prefix}.tar.gz
            sha256_prefix = sha256[:16]
            seed_archive_name = f"SSSP_{version}_{flavor}_{sha256_prefix}.tar.gz"
            seed_archive_path = seed_path / seed_archive_name
            
            # Copy file
            shutil.copy2(archive_path, seed_archive_path)
            existing_hashes[sha256] = seed_archive_path
            
            result["imported"].append({
                "original": archive_path.name,
                "saved_as": seed_archive_name,
                "sha256": sha256,
                "version": version,
                "flavor": flavor,
            })
        except Exception as e:
            result["errors"].append(f"{archive_path.name}: {e}")
    
    return result


def install_sssp_from_seed(
    seed_dir: Path,
    store_dir: Path,
    version: str = "1.3.0",
    flavor: str = "efficiency",
) -> Dict[str, Any]:
    """
    Install SSSP library from seed to store.
    
    This is an offline operation - no network access.
    
    Seed layout: ${seed_dir}/sssp/${version}/${flavor}/
      - *.tar.gz (SSSP archive with UPF files)
      - *.json (cutoffs file)
    
    Store layout: ${store_dir}/sssp/${version}/${flavor}/
      - library/ (extracted UPF files)
      - cutoffs.json (copied from seed)
      - manifest.json (installation metadata)
    
    Returns result dict with success, messages, errors.
    """
    result: Dict[str, Any] = {
        "success": False,
        "version": version,
        "flavor": flavor,
        "files_installed": 0,
        "messages": [],
        "errors": [],
    }
    
    seed_path = get_sssp_seed_path(seed_dir, version, flavor)
    store_path = get_sssp_library_path(store_dir, version, flavor)
    library_path = store_path / "library"
    
    if not seed_path.exists():
        result["errors"].append(f"Seed path not found: {seed_path}")
        return result
    
    # Find tar.gz archive
    archives = list(seed_path.glob("*.tar.gz")) + list(seed_path.glob("*.tgz"))
    if not archives:
        result["errors"].append(f"No archive found in seed: {seed_path}")
        return result
    
    archive_path = archives[0]
    result["messages"].append(f"Found archive: {archive_path.name}")
    
    # Create store directory
    try:
        library_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        result["errors"].append(f"Failed to create library directory: {e}")
        return result
    
    # Extract archive
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            # Extract only UPF files
            for member in tar.getmembers():
                if member.name.endswith((".UPF", ".upf")):
                    # Extract to library directory with flat structure
                    member_name = Path(member.name).name
                    target_path = library_path / member_name
                    
                    # Read and write (handles nested directories in archive)
                    extracted = tar.extractfile(member)
                    if extracted:
                        target_path.write_bytes(extracted.read())
                        result["files_installed"] += 1
        
        result["messages"].append(f"Extracted {result['files_installed']} UPF files")
    except Exception as e:
        result["errors"].append(f"Failed to extract archive: {e}")
        return result
    
    # Copy cutoffs.json if present
    cutoff_files = list(seed_path.glob("*cutoff*.json")) + list(seed_path.glob("*cutoffs*.json"))
    if cutoff_files:
        try:
            shutil.copy(cutoff_files[0], store_path / "cutoffs.json")
            result["messages"].append(f"Copied cutoffs from: {cutoff_files[0].name}")
        except Exception as e:
            result["errors"].append(f"Failed to copy cutoffs: {e}")
    
    # Create manifest
    manifest = {
        "library": "sssp",
        "version": version,
        "flavor": flavor,
        "source": "seed",
        "source_archive": archive_path.name,
        "files_installed": result["files_installed"],
        "installed_at": __import__("datetime").datetime.now().isoformat(),
    }
    
    try:
        (store_path / "manifest.json").write_text(json.dumps(manifest, indent=2))
        result["messages"].append("Created manifest.json")
    except Exception as e:
        result["errors"].append(f"Failed to create manifest: {e}")
    
    result["success"] = result["files_installed"] > 0
    return result


def install_all_sssp_from_seed(seed_dir: Path, store_dir: Path) -> Dict[str, Any]:
    """
    Install all available SSSP libraries from seed to store.
    
    Scans seed directory for available versions/flavors and installs each.
    """
    result: Dict[str, Any] = {
        "success": True,
        "installed": [],
        "skipped": [],
        "failed": [],
        "messages": [],
    }
    
    sssp_seed = seed_dir / "sssp"
    if not sssp_seed.exists():
        result["success"] = False
        result["messages"].append(f"No SSSP seed found at: {sssp_seed}")
        return result
    
    # Scan for available versions/flavors
    for version_dir in sssp_seed.iterdir():
        if not version_dir.is_dir():
            continue
        version = version_dir.name
        
        for flavor_dir in version_dir.iterdir():
            if not flavor_dir.is_dir():
                continue
            flavor = flavor_dir.name
            
            # Check if already installed
            store_path = get_sssp_library_path(store_dir, version, flavor)
            if (store_path / "library").exists():
                result["skipped"].append({"version": version, "flavor": flavor})
                continue
            
            # Install
            install_result = install_sssp_from_seed(seed_dir, store_dir, version, flavor)
            
            if install_result["success"]:
                result["installed"].append({
                    "version": version,
                    "flavor": flavor,
                    "files": install_result["files_installed"],
                })
            else:
                result["failed"].append({
                    "version": version,
                    "flavor": flavor,
                    "errors": install_result["errors"],
                })
                result["success"] = False
    
    result["messages"].append(f"Installed: {len(result['installed'])}, Skipped: {len(result['skipped'])}, Failed: {len(result['failed'])}")
    return result


# =============================================================================
# Manifest and Download Functions (GitHub Release)
# =============================================================================

@dataclass
class ManifestEntry:
    """A single entry from MANIFEST_PSEUDO_SEED.json."""
    relative_path: str
    size_bytes: int
    sha256: str
    category: str
    library_name: str
    library_version: str
    xc: str
    quality: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManifestEntry":
        """Create from dictionary."""
        return cls(
            relative_path=data["relative_path"],
            size_bytes=data["size_bytes"],
            sha256=data["sha256"],
            category=data["category"],
            library_name=data["library_name"],
            library_version=data["library_version"],
            xc=data["xc"],
            quality=data["quality"],
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


def fetch_manifest() -> List[ManifestEntry]:
    """
    Fetch and parse MANIFEST_PSEUDO_SEED.json from GitHub release.
    
    Returns:
        List of ManifestEntry objects
        
    Raises:
        Exception: If manifest cannot be fetched or parsed
    """
    import urllib.request
    import urllib.error
    import socket
    
    manifest_url = f"{GITHUB_RELEASE_BASE_URL}/MANIFEST_PSEUDO_SEED.json"
    
    try:
        socket.setdefaulttimeout(30)
        with urllib.request.urlopen(manifest_url, context=get_ssl_context()) as response:
            if response.status != 200:
                raise Exception(f"Failed to fetch manifest: HTTP {response.status}")
            content = response.read().decode('utf-8')
            data = json.loads(content)
        socket.setdefaulttimeout(None)
    except urllib.error.URLError as e:
        socket.setdefaulttimeout(None)
        raise Exception(f"Failed to fetch manifest from GitHub: {e}") from e
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse manifest JSON: {e}") from e
    
    # Parse entries
    entries = []
    if isinstance(data, list):
        # Manifest is a list of entries
        for item in data:
            if isinstance(item, dict):
                entries.append(ManifestEntry.from_dict(item))
    elif isinstance(data, dict):
        # Manifest structure: {"generated_at": ..., "schema_version": ..., "files": [...]}
        if "files" in data:
            for item in data["files"]:
                if isinstance(item, dict):
                    entries.append(ManifestEntry.from_dict(item))
        elif "entries" in data:
            # Legacy format with "entries" key
            for item in data["entries"]:
                if isinstance(item, dict):
                    entries.append(ManifestEntry.from_dict(item))
        else:
            # Single entry dict? Unlikely but handle it
            entries.append(ManifestEntry.from_dict(data))
    else:
        raise Exception(f"Unexpected manifest format: expected list or dict, got {type(data)}")
    
    if len(entries) == 0:
        raise Exception("Manifest contains no entries")
    
    return entries


def select_sssp_entries(
    manifest: List[ManifestEntry],
    version: str = "1.3.0",
    xc: str = "pbe",
) -> Dict[Tuple[str, str], List[ManifestEntry]]:
    """
    Select SSSP entries from manifest matching criteria.
    
    Args:
        manifest: List of all manifest entries
        version: Library version (default: "1.3.0")
        xc: Exchange-correlation functional (default: "pbe")
        
    Returns:
        Dict mapping (version, quality) -> [tar.gz entry, json entry]
    """
    result: Dict[Tuple[str, str], List[ManifestEntry]] = {}
    
    for entry in manifest:
        if (entry.category == "sssp" and
            entry.library_version == version and
            entry.xc == xc and
            entry.quality in ["efficiency", "precision"]):
            
            key = (entry.library_version, entry.quality)
            if key not in result:
                result[key] = []
            
            # Determine file type from relative_path
            if entry.relative_path.endswith(".tar.gz"):
                result[key].insert(0, entry)  # Archive first
            elif entry.relative_path.endswith(".json"):
                result[key].append(entry)  # JSON second
    
    # Verify each entry has both tar.gz and json
    for key, entries in result.items():
        has_tar = any(e.relative_path.endswith(".tar.gz") for e in entries)
        has_json = any(e.relative_path.endswith(".json") for e in entries)
        if not has_tar or not has_json:
            raise Exception(
                f"Incomplete SSSP entry for {key}: "
                f"has_tar={has_tar}, has_json={has_json}"
            )
    
    return result


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def download_github_release_asset(
    asset_name: str,
    output_path: Path,
    expected_size: Optional[int] = None,
    expected_sha256: Optional[str] = None,
) -> None:
    """
    Download an asset from GitHub release and verify integrity.
    
    Args:
        asset_name: Name of the asset file (e.g., "SSSP_1.3.0_PBE_efficiency.tar.gz")
        output_path: Path where to save the file
        expected_size: Optional expected file size in bytes
        expected_sha256: Optional expected SHA256 hash
        
    Raises:
        Exception: If download fails, size mismatch, or checksum mismatch
    """
    import urllib.request
    import urllib.error
    import socket
    
    asset_url = f"{GITHUB_RELEASE_BASE_URL}/{asset_name}"
    
    try:
        socket.setdefaulttimeout(120)  # Longer timeout for large files
        # Use urlopen with SSL context for proper certificate verification
        with urllib.request.urlopen(asset_url, context=get_ssl_context()) as response:
            with open(output_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
        socket.setdefaulttimeout(None)
    except urllib.error.URLError as e:
        socket.setdefaulttimeout(None)
        raise Exception(f"Failed to download {asset_name} from GitHub: {e}") from e
    except Exception as e:
        socket.setdefaulttimeout(None)
        raise Exception(f"Failed to download {asset_name}: {e}") from e
    
    # Verify size if provided
    if expected_size is not None:
        actual_size = output_path.stat().st_size
        if actual_size != expected_size:
            output_path.unlink()  # Delete mismatched file
            raise Exception(
                f"Size mismatch for {asset_name}: "
                f"expected {expected_size} bytes, got {actual_size} bytes"
            )
    
    # Verify SHA256 if provided
    if expected_sha256 is not None:
        actual_sha256 = compute_sha256(output_path)
        if actual_sha256.lower() != expected_sha256.lower():
            output_path.unlink()  # Delete mismatched file
            raise Exception(
                f"SHA256 mismatch for {asset_name}: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )


def download_sssp_library(
    store_dir: Path,
    flavor: str,
    version: str = "1.3.0",
    force: bool = False,
    allow_download: bool = True,
    seed_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Download SSSP library from GitHub release and install into store.
    
    Uses manifest-driven approach:
    1. Fetch MANIFEST_PSEUDO_SEED.json from GitHub release
    2. Select entries matching version/flavor/xc criteria
    3. Download tar.gz and json files
    4. Verify SHA256 checksums
    5. Extract and install only after verification passes
    
    Args:
        store_dir: Path to pseudo store directory
        flavor: "efficiency" or "precision"
        version: SSSP version (default: "1.3.0")
        force: If True, download even if allow_download is False (one-shot confirm)
        allow_download: Global setting; if False and force is False, skip download
        
    Returns:
        Dict with success, messages, errors, and installed library info
    """
    import tempfile
    
    result: Dict[str, Any] = {
        "success": False,
        "version": version,
        "flavor": flavor,
        "files_downloaded": [],
        "files_installed": 0,
        "messages": [],
        "errors": [],
        "warnings": [],
    }
    
    # Check if download is allowed
    if not allow_download and not force:
        result["errors"].append("Downloads not allowed. Enable 'Allow Network Downloads' or confirm to proceed.")
        return result
    
    # Validate flavor
    if flavor not in ["efficiency", "precision"]:
        result["errors"].append(f"Invalid flavor: {flavor} (must be 'efficiency' or 'precision')")
        return result
    
    store_path = get_sssp_library_path(store_dir, version, flavor)
    library_path = store_path / "library"
    
    # Check if already installed
    if library_path.exists() and len(list(library_path.glob("*.UPF"))) > 0:
        result["warnings"].append(f"Library already installed at {store_path}")
        result["success"] = True
        return result
    
    # Create directories
    try:
        store_path.mkdir(parents=True, exist_ok=True)
        library_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        result["errors"].append(f"Failed to create directories: {e}")
        return result
    
    result["messages"].append(f"Fetching manifest from GitHub release...")
    
    # Step 1: Fetch manifest
    try:
        manifest_entries = fetch_manifest()
        result["messages"].append(f"Fetched manifest with {len(manifest_entries)} entries")
    except Exception as e:
        result["errors"].append(f"Failed to fetch manifest: {e}")
        return result
    
    # Step 2: Select SSSP entries
    try:
        sssp_entries = select_sssp_entries(manifest_entries, version=version, xc="pbe")
        key = (version, flavor)
        if key not in sssp_entries:
            result["errors"].append(
                f"No SSSP entries found for version={version}, flavor={flavor}, xc=pbe in manifest"
            )
            return result
        
        selected = sssp_entries[key]
        # Should have exactly 2 entries: tar.gz and json
        if len(selected) != 2:
            result["errors"].append(
                f"Expected 2 manifest entries (tar.gz + json), got {len(selected)}"
            )
            return result
        
        # Identify archive and cutoffs entries
        archive_entry = next(e for e in selected if e.relative_path.endswith(".tar.gz"))
        cutoffs_entry = next(e for e in selected if e.relative_path.endswith(".json"))
        
        result["messages"].append(
            f"Selected entries: {archive_entry.relative_path} ({archive_entry.size_bytes // 1024 // 1024} MB), "
            f"{cutoffs_entry.relative_path}"
        )
    except Exception as e:
        result["errors"].append(f"Failed to select SSSP entries from manifest: {e}")
        return result
    
    # Step 3: Download files to .tmp/downloads/ with verification
    result["messages"].append(f"Downloading SSSP {version} {flavor} from GitHub release...")
    
    # Use .tmp/downloads/ as base for temporary downloads
    downloads_base = tmp_downloads_dir()
    with tempfile.TemporaryDirectory(prefix="sssp_download_", dir=str(downloads_base)) as temp_dir:
        temp_path = Path(temp_dir)
        
        # Download archive with verification
        archive_name = Path(archive_entry.relative_path).name
        archive_temp = temp_path / archive_name
        
        try:
            result["messages"].append(f"Downloading {archive_name}...")
            download_github_release_asset(
                asset_name=archive_name,
                output_path=archive_temp,
                expected_size=archive_entry.size_bytes,
                expected_sha256=archive_entry.sha256,
            )
            result["files_downloaded"].append(archive_name)
            result["messages"].append(
                f"✓ Downloaded and verified {archive_name} "
                f"({archive_entry.size_bytes // 1024 // 1024} MB, SHA256: {archive_entry.sha256[:16]}...)"
            )
        except Exception as e:
            result["errors"].append(f"Failed to download or verify {archive_name}: {e}")
            return result
        
        # Download cutoffs with verification
        cutoffs_name = Path(cutoffs_entry.relative_path).name
        cutoffs_temp = temp_path / cutoffs_name
        
        try:
            result["messages"].append(f"Downloading {cutoffs_name}...")
            download_github_release_asset(
                asset_name=cutoffs_name,
                output_path=cutoffs_temp,
                expected_size=cutoffs_entry.size_bytes,
                expected_sha256=cutoffs_entry.sha256,
            )
            result["files_downloaded"].append(cutoffs_name)
            result["messages"].append(
                f"✓ Downloaded and verified {cutoffs_name} "
                f"(SHA256: {cutoffs_entry.sha256[:16]}...)"
            )
        except Exception as e:
            result["errors"].append(f"Failed to download or verify {cutoffs_name}: {e}")
            return result
        
        # Step 4: Extract archive (only after verification passes)
        try:
            result["messages"].append("Extracting UPF files...")
            # Verify tar can be opened
            try:
                with tarfile.open(archive_temp, "r:gz") as tar:
                    tar.getmembers()  # Test that tar is valid
            except (tarfile.TarError, OSError, EOFError) as e:
                result["errors"].append(
                    f"Downloaded archive is corrupted (tar open failed: {e}). "
                    f"Checksum passed but tar is invalid. Please report this issue."
                )
                return result
            
            # Extract UPF files
            with tarfile.open(archive_temp, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith((".UPF", ".upf")):
                        member_name = Path(member.name).name
                        target_path = library_path / member_name
                        extracted = tar.extractfile(member)
                        if extracted:
                            target_path.write_bytes(extracted.read())
                            result["files_installed"] += 1
            
            result["messages"].append(f"Extracted {result['files_installed']} UPF files")
        except Exception as e:
            result["errors"].append(f"Failed to extract archive: {e}")
            return result
        
        # Step 5: Save archive to seed_dir for disaster recovery (if seed_dir provided)
        if seed_dir:
            try:
                seed_path = get_sssp_seed_path(seed_dir, version, flavor)
                seed_path.mkdir(parents=True, exist_ok=True)
                
                # Save archive with deterministic name based on SHA256
                # Format: SSSP_{version}_{flavor}_{sha256_prefix}.tar.gz
                sha256_prefix = archive_entry.sha256[:16]
                seed_archive_name = f"SSSP_{version}_{flavor}_{sha256_prefix}.tar.gz"
                seed_archive_path = seed_path / seed_archive_name
                
                # Only copy if not already exists (dedup by SHA256)
                if not seed_archive_path.exists():
                    shutil.copy(archive_temp, seed_archive_path)
                    result["messages"].append(f"Saved archive to seed cache: {seed_archive_name}")
                else:
                    result["messages"].append(f"Archive already in seed cache: {seed_archive_name}")
                
                # Save cutoffs JSON to seed
                seed_cutoffs_path = seed_path / cutoffs_name
                if not seed_cutoffs_path.exists():
                    shutil.copy(cutoffs_temp, seed_cutoffs_path)
                    result["messages"].append(f"Saved cutoffs to seed cache")
            except Exception as e:
                # Don't fail the download if seed save fails, just warn
                result["warnings"].append(f"Failed to save to seed cache: {e}")
        
        # Step 6: Copy cutoffs JSON to store
        try:
            shutil.copy(cutoffs_temp, store_path / "cutoffs.json")
            result["messages"].append("Installed cutoffs.json")
        except Exception as e:
            result["errors"].append(f"Failed to copy cutoffs: {e}")
            return result
    
    # Step 7: Create installation manifest
    manifest = {
        "library": "sssp",
        "version": version,
        "flavor": flavor,
        "source": "github_release",
        "source_release": GITHUB_RELEASE_TAG,
        "source_repo": f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}",
        "manifest_sha256": {
            "archive": archive_entry.sha256,
            "cutoffs": cutoffs_entry.sha256,
        },
        "files_downloaded": result["files_downloaded"],
        "files_installed": result["files_installed"],
        "installed_at": __import__("datetime").datetime.now().isoformat(),
    }
    
    try:
        (store_path / "manifest.json").write_text(json.dumps(manifest, indent=2))
        result["messages"].append("Created manifest.json")
    except Exception as e:
        result["warnings"].append(f"Failed to create manifest: {e}")
    
    result["success"] = result["files_installed"] > 0
    if result["success"]:
        result["messages"].append(f"Successfully installed SSSP {version} {flavor} from GitHub release")
    
    return result


def download_all_sssp(
    store_dir: Path,
    force: bool = False,
    allow_download: bool = True,
    seed_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Download all supported SSSP libraries from GitHub release.
    
    Uses manifest to determine which libraries are available.
    Currently supports: SSSP 1.3.0 PBE efficiency and precision.
    
    Args:
        store_dir: Path to pseudo store directory
        force: If True, download even if allow_download is False
        allow_download: Global setting
        
    Returns:
        Dict with success, installed, skipped, failed lists
    """
    result: Dict[str, Any] = {
        "success": True,
        "installed": [],
        "skipped": [],
        "failed": [],
        "messages": [],
    }
    
    # Fetch manifest once to get available libraries
    try:
        manifest_entries = fetch_manifest()
        sssp_entries = select_sssp_entries(manifest_entries, version="1.3.0", xc="pbe")
        result["messages"].append(f"Found {len(sssp_entries)} SSSP libraries in manifest")
    except Exception as e:
        result["success"] = False
        result["failed"].append({
            "version": "1.3.0",
            "flavor": "all",
            "errors": [f"Failed to fetch manifest: {e}"],
        })
        result["messages"].append(f"Failed to fetch manifest: {e}")
        return result
    
    # Download each library from manifest
    for (version, flavor) in sssp_entries.keys():
        # Check if already installed
        lib_path = get_sssp_library_path(store_dir, version, flavor) / "library"
        if lib_path.exists() and len(list(lib_path.glob("*.UPF"))) > 0:
            result["skipped"].append({"version": version, "flavor": flavor})
            continue
        
        # Download
        download_result = download_sssp_library(
            store_dir=store_dir,
            flavor=flavor,
            version=version,
            force=force,
            allow_download=allow_download,
            seed_dir=seed_dir,
        )
        
        if download_result["success"]:
            result["installed"].append({
                "version": version,
                "flavor": flavor,
                "files": download_result["files_installed"],
            })
        else:
            result["failed"].append({
                "version": version,
                "flavor": flavor,
                "errors": download_result["errors"],
            })
            result["success"] = False
    
    result["messages"].append(
        f"Downloaded: {len(result['installed'])}, "
        f"Skipped: {len(result['skipped'])}, "
        f"Failed: {len(result['failed'])}"
    )
    return result


@dataclass
class PseudoResolutionRequest:
    """Request to resolve pseudopotentials for a project."""
    project_root: Path
    elements: List[str]
    library: str = "sssp"
    version: str = "1.3.0"
    flavor: str = "efficiency"


@dataclass 
class PseudoResolutionResult:
    """Result of pseudopotential resolution."""
    success: bool = True
    mapping: Dict[str, str] = field(default_factory=dict)  # element -> filename
    cutoffs: Dict[str, Dict[str, float]] = field(default_factory=dict)  # element -> {ecutwfc, ecutrho}
    project_pseudo_dir: str = ""
    messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def resolve_project_pseudos(
    config: PseudoConfig,
    request: PseudoResolutionRequest,
) -> PseudoResolutionResult:
    """
    Resolve pseudopotentials for a project.
    
    Resolution order:
    1. resources/pseudo (committed; always available for demos/tests)
    2. project pseudos folder (project-local copies; reproducibility)
    3. global pseudo store (store_dir)
    4. seed (seed_dir) - install to store if found
    5. if allowed, download → install into store → copy into project
    
    Args:
        config: Pseudo configuration with store/seed paths
        request: Resolution request with project and elements
    
    Returns:
        PseudoResolutionResult with mapping and cutoffs
    """
    result = PseudoResolutionResult()
    
    project_pseudo_dir = request.project_root / "pseudo"
    result.project_pseudo_dir = str(project_pseudo_dir)
    
    repo_root = _find_quantumvitas_root()
    repo_pseudo_dir = repo_root / "resources" / "pseudo" if repo_root else None
    
    store_dir = Path(config.store_dir) if config.store_dir else None
    seed_dir = Path(config.seed_dir) if config.seed_dir else None
    
    # Get library path in store
    library_path = None
    if store_dir:
        lib_base = get_sssp_library_path(store_dir, request.version, request.flavor)
        library_path = lib_base / "library"
        
        # Load cutoffs if available
        cutoffs_path = lib_base / "cutoffs.json"
        if cutoffs_path.exists():
            try:
                cutoffs_data = json.loads(cutoffs_path.read_text())
                # SSSP cutoffs format varies - try to extract
                for elem_data in cutoffs_data if isinstance(cutoffs_data, list) else []:
                    if "element" in elem_data:
                        elem = elem_data["element"]
                        result.cutoffs[elem] = {
                            "ecutwfc": elem_data.get("cutoff_wfc", 0),
                            "ecutrho": elem_data.get("cutoff_rho", 0),
                        }
            except Exception as e:
                result.warnings.append(f"Failed to load cutoffs: {e}")
    
    # Ensure project pseudo dir exists
    project_pseudo_dir.mkdir(parents=True, exist_ok=True)
    
    for element in request.elements:
        found = False
        
        # 1. Check project pseudo dir
        for pp_file in project_pseudo_dir.glob(f"{element}*.UPF"):
            result.mapping[element] = pp_file.name
            result.messages.append(f"{element}: Found in project ({pp_file.name})")
            found = True
            break
        if found:
            continue
        
        for pp_file in project_pseudo_dir.glob(f"{element}*.upf"):
            result.mapping[element] = pp_file.name
            result.messages.append(f"{element}: Found in project ({pp_file.name})")
            found = True
            break
        if found:
            continue
        
        # 2. Check repo/pseudo
        if repo_pseudo_dir and repo_pseudo_dir.exists():
            for pp_file in repo_pseudo_dir.glob(f"{element}*.UPF"):
                # Copy to project
                dest = project_pseudo_dir / pp_file.name
                shutil.copy(pp_file, dest)
                result.mapping[element] = pp_file.name
                result.messages.append(f"{element}: Copied from repo ({pp_file.name})")
                found = True
                break
            if found:
                continue
            
            for pp_file in repo_pseudo_dir.glob(f"{element}*.upf"):
                dest = project_pseudo_dir / pp_file.name
                shutil.copy(pp_file, dest)
                result.mapping[element] = pp_file.name
                result.messages.append(f"{element}: Copied from repo ({pp_file.name})")
                found = True
                break
            if found:
                continue
        
        # 3. Check store library
        if library_path and library_path.exists():
            for pp_file in library_path.glob(f"{element}*.UPF"):
                # Copy to project
                dest = project_pseudo_dir / pp_file.name
                shutil.copy(pp_file, dest)
                result.mapping[element] = pp_file.name
                result.messages.append(f"{element}: Copied from store ({pp_file.name})")
                found = True
                break
            if found:
                continue
            
            for pp_file in library_path.glob(f"{element}*.upf"):
                dest = project_pseudo_dir / pp_file.name
                shutil.copy(pp_file, dest)
                result.mapping[element] = pp_file.name
                result.messages.append(f"{element}: Copied from store ({pp_file.name})")
                found = True
                break
            if found:
                continue
        
        # 3b. Search new library layout: libraries/pseudo/<Library>/head.json
        if not found and store_dir:
            libraries_root = Path(store_dir)
            if libraries_root.is_dir():
                for lib_dir in libraries_root.iterdir():
                    if not lib_dir.is_dir():
                        continue
                    head_path = lib_dir / "head.json"
                    if not head_path.exists():
                        continue
                    try:
                        head = json.loads(head_path.read_text())
                        upf_dir = lib_dir / head["variant"] / head["version"]
                        if not upf_dir.is_dir():
                            continue
                        for pp_file in upf_dir.glob(f"{element}*.UPF"):
                            dest = project_pseudo_dir / pp_file.name
                            shutil.copy(pp_file, dest)
                            result.mapping[element] = pp_file.name
                            result.messages.append(
                                f"{element}: Copied from library {lib_dir.name} ({pp_file.name})"
                            )
                            found = True
                            break
                        if not found:
                            for pp_file in upf_dir.glob(f"{element}*.upf"):
                                dest = project_pseudo_dir / pp_file.name
                                shutil.copy(pp_file, dest)
                                result.mapping[element] = pp_file.name
                                result.messages.append(
                                    f"{element}: Copied from library {lib_dir.name} ({pp_file.name})"
                                )
                                found = True
                                break
                    except (json.JSONDecodeError, KeyError):
                        continue
                    if found:
                        break
            if found:
                continue

        # 4. Try to install from seed if library not present
        if seed_dir and not (library_path and library_path.exists()):
            seed_path = get_sssp_seed_path(seed_dir, request.version, request.flavor)
            if seed_path.exists():
                result.messages.append(f"Installing SSSP {request.version}/{request.flavor} from seed...")
                install_result = install_sssp_from_seed(
                    seed_dir, store_dir, request.version, request.flavor
                )
                if install_result["success"]:
                    result.messages.append(f"Installed {install_result['files_installed']} files from seed")
                    # Retry from store
                    if library_path and library_path.exists():
                        for pp_file in library_path.glob(f"{element}*.UPF"):
                            dest = project_pseudo_dir / pp_file.name
                            shutil.copy(pp_file, dest)
                            result.mapping[element] = pp_file.name
                            result.messages.append(f"{element}: Copied from store ({pp_file.name})")
                            found = True
                            break
                        if found:
                            continue
                        for pp_file in library_path.glob(f"{element}*.upf"):
                            dest = project_pseudo_dir / pp_file.name
                            shutil.copy(pp_file, dest)
                            result.mapping[element] = pp_file.name
                            result.messages.append(f"{element}: Copied from store ({pp_file.name})")
                            found = True
                            break
                        if found:
                            continue
        
        # 5. Download if allowed (TODO - stubbed for now)
        if config.allow_download and not found:
            result.warnings.append(f"{element}: Download not yet implemented")
        
        # Not found
        if not found:
            result.errors.append(f"{element}: Not found in any location")
            result.success = False
    
    return result

