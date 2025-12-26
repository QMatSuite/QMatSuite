"""
Pseudopotential configuration and management.

This module provides:
- PseudoConfig: Settings for pseudo store, seed, and downloads
- PseudoStore: Manager for SSSP installation and resolution
- Resolution flow: repo/pseudo → project → store → seed → download
"""

from __future__ import annotations

import json
import logging
import shutil
import tarfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


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
        store_dir: Global pseudo store directory (default: repo/temp/pseudo)
        seed_dir: Seed directory for offline installation (default: repo/temp/assets/pseudo_seed)
        allow_download: Whether to allow network downloads (default: False)
    """
    store_dir: str = ""
    seed_dir: str = ""
    allow_download: bool = False
    
    @classmethod
    def get_default_store_dir(cls) -> str:
        """Get default store directory path."""
        root = _find_quantumvitas_root()
        if root:
            return str(root / "temp" / "pseudo")
        return ""
    
    @classmethod
    def get_default_seed_dir(cls) -> str:
        """Get default seed directory path."""
        root = _find_quantumvitas_root()
        if root:
            return str(root / "temp" / "assets" / "pseudo_seed")
        return ""
    
    @classmethod
    def with_defaults(cls) -> "PseudoConfig":
        """Create a config with default values."""
        return cls(
            store_dir=cls.get_default_store_dir(),
            seed_dir=cls.get_default_seed_dir(),
            allow_download=False,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PseudoConfig":
        """Create from dict, applying defaults for missing fields."""
        defaults = cls.with_defaults()
        return cls(
            store_dir=data.get("store_dir") or defaults.store_dir,
            seed_dir=data.get("seed_dir") or defaults.seed_dir,
            allow_download=data.get("allow_download", defaults.allow_download),
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
    
    # Check repo/pseudo (always should exist)
    repo_root = _find_quantumvitas_root()
    if repo_root:
        repo_pseudo = repo_root / "pseudo"
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
# SSSP Download Functions (Network)
# =============================================================================

# Materials Cloud SSSP URLs
SSSP_BASE_URL = "https://archive.materialscloud.org/record/file?record_id=1732&filename="
SSSP_LIBRARY_FILES = {
    # Version 1.3.0
    ("1.3.0", "efficiency"): {
        "archive": "SSSP_1.3.0_PBE_efficiency.tar.gz",
        "cutoffs": "SSSP_1.3.0_PBE_efficiency.json",
    },
    ("1.3.0", "precision"): {
        "archive": "SSSP_1.3.0_PBE_precision.tar.gz",
        "cutoffs": "SSSP_1.3.0_PBE_precision.json",
    },
}

# Minimum file sizes for sanity check (bytes)
MIN_ARCHIVE_SIZE = 10 * 1024 * 1024  # 10 MB
MIN_CUTOFFS_SIZE = 1000  # 1 KB


def download_sssp_library(
    store_dir: Path,
    flavor: str,
    version: str = "1.3.0",
    force: bool = False,
    allow_download: bool = True,
) -> Dict[str, Any]:
    """
    Download SSSP library from Materials Cloud and install into store.
    
    Args:
        store_dir: Path to pseudo store directory
        flavor: "efficiency" or "precision"
        version: SSSP version (default: "1.3.0")
        force: If True, download even if allow_download is False (one-shot confirm)
        allow_download: Global setting; if False and force is False, skip download
        
    Returns:
        Dict with success, messages, errors, and installed library info
    """
    import urllib.request
    import urllib.error
    import socket
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
    
    # Validate flavor/version
    key = (version, flavor)
    if key not in SSSP_LIBRARY_FILES:
        result["errors"].append(f"Unknown SSSP library: {version}/{flavor}")
        return result
    
    files = SSSP_LIBRARY_FILES[key]
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
    
    result["messages"].append(f"Downloading SSSP {version} {flavor}...")
    
    # Download files to temp dir first
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Download archive
        archive_name = files["archive"]
        archive_url = SSSP_BASE_URL + archive_name
        archive_temp = temp_path / archive_name
        
        try:
            result["messages"].append(f"Downloading {archive_name}...")
            socket.setdefaulttimeout(60)
            urllib.request.urlretrieve(archive_url, archive_temp)
            socket.setdefaulttimeout(None)
            
            # Verify size
            if archive_temp.stat().st_size < MIN_ARCHIVE_SIZE:
                result["errors"].append(f"Downloaded archive too small ({archive_temp.stat().st_size} bytes)")
                return result
            
            result["files_downloaded"].append(archive_name)
            result["messages"].append(f"Downloaded {archive_name} ({archive_temp.stat().st_size // 1024 // 1024} MB)")
        except Exception as e:
            socket.setdefaulttimeout(None)
            result["errors"].append(f"Failed to download {archive_name}: {e}")
            return result
        
        # Download cutoffs
        cutoffs_name = files["cutoffs"]
        cutoffs_url = SSSP_BASE_URL + cutoffs_name
        cutoffs_temp = temp_path / cutoffs_name
        
        try:
            result["messages"].append(f"Downloading {cutoffs_name}...")
            socket.setdefaulttimeout(30)
            urllib.request.urlretrieve(cutoffs_url, cutoffs_temp)
            socket.setdefaulttimeout(None)
            
            # Verify JSON is valid
            if cutoffs_temp.stat().st_size < MIN_CUTOFFS_SIZE:
                result["warnings"].append(f"Cutoffs file seems small ({cutoffs_temp.stat().st_size} bytes)")
            
            try:
                json.loads(cutoffs_temp.read_text())
                result["files_downloaded"].append(cutoffs_name)
                result["messages"].append(f"Downloaded {cutoffs_name}")
            except json.JSONDecodeError as e:
                result["warnings"].append(f"Cutoffs JSON invalid: {e}")
        except Exception as e:
            socket.setdefaulttimeout(None)
            result["warnings"].append(f"Failed to download cutoffs: {e}")
        
        # Extract archive
        try:
            result["messages"].append("Extracting UPF files...")
            # Verify tar can be opened (handle corrupted downloads)
            try:
                with tarfile.open(archive_temp, "r:gz") as tar:
                    # Test that tar is valid by getting members
                    tar.getmembers()
            except (tarfile.TarError, OSError, EOFError) as e:
                # Corrupted tar - delete and report error
                result["errors"].append(f"Downloaded archive is corrupted (tar open failed: {e}). Please retry download.")
                try:
                    archive_temp.unlink()  # Delete corrupted file
                    result["messages"].append("Deleted corrupted archive file")
                except Exception:
                    pass
                return result
            
            # Tar is valid, proceed with extraction
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
        
        # Copy cutoffs if downloaded
        if cutoffs_temp.exists():
            try:
                shutil.copy(cutoffs_temp, store_path / "cutoffs.json")
                result["messages"].append("Installed cutoffs.json")
            except Exception as e:
                result["warnings"].append(f"Failed to copy cutoffs: {e}")
    
    # Create manifest
    manifest = {
        "library": "sssp",
        "version": version,
        "flavor": flavor,
        "source": "download",
        "source_url": SSSP_BASE_URL,
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
        result["messages"].append(f"Successfully installed SSSP {version} {flavor}")
    
    return result


def download_all_sssp(
    store_dir: Path,
    force: bool = False,
    allow_download: bool = True,
) -> Dict[str, Any]:
    """
    Download all supported SSSP libraries.
    
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
    
    for (version, flavor) in SSSP_LIBRARY_FILES.keys():
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
    1. repo/pseudo (committed; always available for demos/tests)
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
    repo_pseudo_dir = repo_root / "pseudo" if repo_root else None
    
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

