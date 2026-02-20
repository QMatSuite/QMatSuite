"""
Pseudopotential configuration and management.

This module provides:
- PseudoConfig: Settings for pseudo store, seed, and downloads
- Resolution flow: resources/pseudo -> project -> installed libraries -> auto-download
- compute_sha256 / download_github_release_asset (used by pseudo.pipeline)

All OLD SSSP-specific functions (get_sssp_library_path, install_sssp_from_seed,
download_sssp_library, etc.) have been deleted.
Use quantumvitas.pseudo.pipeline.download_and_install() instead.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import ssl
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import certifi

from quantumvitas.core.paths import (
    home_pseudo_libraries_dir,
    home_pseudo_seeds_dir,
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
    """Find the quantumvitas package root for bundled resources.

    Uses importlib.resources (Python 3.9+) to locate the installed package,
    with a dev-mode fallback that walks up from __file__.

    Returns None if not found.
    """
    # 1. importlib.resources (works in wheel installs)
    try:
        import importlib.resources as _res

        pkg_anchor = _res.files("quantumvitas")
        # pkg_anchor is the quantumvitas package dir.
        # resources/pseudo lives two levels up: <repo>/resources/pseudo
        pkg_path = Path(str(pkg_anchor))
        repo_root = pkg_path.parent.parent  # src/../ -> repo root
        if (repo_root / "resources" / "pseudo").exists():
            return repo_root
    except Exception:
        pass

    # 2. Dev-mode fallback: walk up from __file__
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
            result.messages.append(f"Repo pseudo dir: {repo_pseudo}")
        else:
            result.warnings.append(f"Repo pseudo dir not found: {repo_pseudo}")
    else:
        result.warnings.append("Could not find quantumvitas repo root")

    # Check store_dir
    if config.store_dir:
        store_path = Path(config.store_dir)
        result.store_dir_exists = store_path.exists()

        if result.store_dir_exists:
            result.messages.append(f"Store dir exists: {store_path}")
            # Check writable
            try:
                test_file = store_path / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
                result.store_dir_writable = True
                result.messages.append("Store dir is writable")
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
            result.messages.append(f"Seed dir exists: {seed_path}")
            # Check for SSSP layout
            sssp_dir = seed_path / "sssp"
            if sssp_dir.exists():
                result.seed_has_sssp = True
                result.messages.append("Seed contains SSSP data")
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


# =============================================================================
# Utility functions (used by pseudo.pipeline)
# =============================================================================

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


# =============================================================================
# Resolution system (NEW — uses three-level directory walk)
# =============================================================================

@dataclass
class PseudoResolutionRequest:
    """Request to resolve pseudopotentials for a project."""
    project_root: Path
    elements: List[str]
    library: str = "sssp"
    version: str = "1.3.0"
    variant: str = "precision"


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


def _find_file_in_dir(directory: Path, exact_filename: str | None, element: str) -> Path | None:
    """Find a pseudo file in a directory using exact filename or tight glob fallback.

    Resolution order:
    1. Exact filename from index (if provided)
    2. Tight glob: ``{element}[._-]*.[Uu][Pp][Ff]`` -- matches ``Si.pbe-...UPF``
       but NOT ``Si`` matching ``Siesta`` etc.
    """
    if exact_filename:
        candidate = directory / exact_filename
        if candidate.exists():
            return candidate

    # Tight glob fallback -- element must be followed by a separator
    for pp_file in directory.glob(f"{element}[._-]*.[Uu][Pp][Ff]"):
        return pp_file
    return None


def _scan_installed_libraries(libraries_root: Path) -> list[dict]:
    """Three-level walk of NEW layout to discover installed libraries.

    Layout: ``<libraries_root>/<dir_name>/<variant>/<version>/head.json``

    Returns a list of dicts with keys:
        library_key, variant, version, upf_dir (Path), head (full dict).
    """
    results: list[dict] = []
    if not libraries_root.is_dir():
        return results

    for lib_dir in sorted(libraries_root.iterdir()):
        if not lib_dir.is_dir():
            continue
        for variant_dir in sorted(lib_dir.iterdir()):
            if not variant_dir.is_dir():
                continue
            for version_dir in sorted(variant_dir.iterdir()):
                if not version_dir.is_dir():
                    continue
                head_path = version_dir / "head.json"
                if not head_path.exists():
                    continue
                try:
                    head = json.loads(head_path.read_text())
                    results.append({
                        "library_key": head.get("library_key", lib_dir.name),
                        "variant": head.get("variant", variant_dir.name),
                        "version": head.get("version", version_dir.name),
                        "upf_dir": version_dir,
                        "head": head,
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
    return results


def resolve_project_pseudos(
    config: PseudoConfig,
    request: PseudoResolutionRequest,
) -> PseudoResolutionResult:
    """Resolve pseudopotentials for a project.

    Resolution order (deterministic, no loose globs):
    1. project pseudo dir -- check for exact filename or tight glob
    2. resources/pseudo -- committed bundled pseudos (for demos/tests)
    3. installed libraries -- three-level walk + deterministic index lookup
    4. auto-download via pipeline -- if no library found, download and retry
    5. not found -- error

    Uses ``resolve_element_from_index()`` from the vendored
    PSEUDO_FILE_INDEX.json for exact element->filename mapping.  This
    eliminates the ``C`` matching ``Cu`` bug from glob-based resolution.
    """
    from quantumvitas.pseudo.registry import resolve_element_from_index

    result = PseudoResolutionResult()

    project_pseudo_dir = request.project_root / "pseudo"
    result.project_pseudo_dir = str(project_pseudo_dir)

    repo_root = _find_quantumvitas_root()
    repo_pseudo_dir = repo_root / "resources" / "pseudo" if repo_root else None

    libraries_root = home_pseudo_libraries_dir()

    # Load cutoffs from NEW layout: companion JSON in install dir
    installed_libs = _scan_installed_libraries(libraries_root)
    for lib_info in installed_libs:
        upf_dir = lib_info["upf_dir"]
        # Try common cutoffs filenames
        for cutoffs_name in ("SSSP_1.3.0_PBE_precision.json",
                             "SSSP_1.3.0_PBE_efficiency.json",
                             "cutoffs.json"):
            cutoffs_path = upf_dir / cutoffs_name
            if cutoffs_path.exists():
                try:
                    cutoffs_data = json.loads(cutoffs_path.read_text())
                    for elem_data in cutoffs_data if isinstance(cutoffs_data, list) else []:
                        if "element" in elem_data:
                            elem = elem_data["element"]
                            if elem not in result.cutoffs:
                                result.cutoffs[elem] = {
                                    "ecutwfc": elem_data.get("cutoff_wfc", 0),
                                    "ecutrho": elem_data.get("cutoff_rho", 0),
                                }
                except Exception as e:
                    result.warnings.append(f"Failed to load cutoffs from {cutoffs_path}: {e}")
                break  # found one, stop searching

    # Ensure project pseudo dir exists
    project_pseudo_dir.mkdir(parents=True, exist_ok=True)

    # Pre-resolve the requested library's key/variant/version for index lookup.
    req_library_key = request.library.lower()
    req_variant = request.variant
    req_version = request.version

    for element in request.elements:
        found = False

        # Get exact filename from index for the requested library
        exact_filename = resolve_element_from_index(
            req_library_key, req_variant, req_version, element
        )

        # 1. Check project pseudo dir (already has the file?)
        pp_file = _find_file_in_dir(project_pseudo_dir, exact_filename, element)
        if pp_file is not None:
            result.mapping[element] = pp_file.name
            result.messages.append(f"{element}: Found in project ({pp_file.name})")
            found = True

        # 2. Check bundled resources/pseudo
        if not found and repo_pseudo_dir and repo_pseudo_dir.exists():
            pp_file = _find_file_in_dir(repo_pseudo_dir, exact_filename, element)
            if pp_file is not None:
                dest = project_pseudo_dir / pp_file.name
                shutil.copy(pp_file, dest)
                result.mapping[element] = pp_file.name
                result.messages.append(f"{element}: Copied from repo ({pp_file.name})")
                found = True

        # 3. Check installed libraries via three-level walk + index lookup
        if not found:
            # Prefer requested library match first, then fall back to any
            preferred: list[dict] = []
            fallback: list[dict] = []
            for lib_info in installed_libs:
                if lib_info["library_key"] == req_library_key:
                    # Further prefer matching variant/version
                    if (lib_info["variant"] == req_variant and
                            lib_info["version"] == req_version):
                        preferred.insert(0, lib_info)
                    else:
                        preferred.append(lib_info)
                else:
                    fallback.append(lib_info)

            for lib_info in preferred + fallback:
                upf_dir = lib_info["upf_dir"]
                lib_key = lib_info["library_key"]
                lib_variant = lib_info["variant"]
                lib_version = lib_info["version"]

                # Use index for exact filename in THIS library
                lib_filename = resolve_element_from_index(
                    lib_key, lib_variant, lib_version, element
                )
                if not lib_filename:
                    # Fallback: try the requested library's exact filename
                    lib_filename = exact_filename

                if lib_filename:
                    candidate = upf_dir / lib_filename
                    if candidate.exists():
                        dest = project_pseudo_dir / candidate.name
                        shutil.copy(candidate, dest)
                        result.mapping[element] = candidate.name
                        result.messages.append(
                            f"{element}: Copied from library "
                            f"{lib_key}/{lib_variant}/{lib_version} ({candidate.name})"
                        )
                        found = True
                        break

                # Tight glob fallback for this library dir
                pp_file = _find_file_in_dir(upf_dir, None, element)
                if pp_file is not None:
                    dest = project_pseudo_dir / pp_file.name
                    shutil.copy(pp_file, dest)
                    result.mapping[element] = pp_file.name
                    result.messages.append(
                        f"{element}: Copied from library "
                        f"{lib_key}/{lib_variant}/{lib_version} ({pp_file.name})"
                    )
                    found = True
                    break

        # 4. Auto-download via NEW pipeline if not found
        if not found:
            try:
                from quantumvitas.pseudo.pipeline import download_and_install

                result.messages.append(
                    f"{element}: Not found locally, attempting download of "
                    f"{req_library_key}/{req_variant}/{req_version}..."
                )
                dl_result = download_and_install(
                    library=req_library_key,
                    variant=req_variant,
                    version=req_version,
                )
                if dl_result.get("success"):
                    result.messages.append(
                        f"Installed {dl_result.get('upf_count', 0)} UPFs from download"
                    )
                    # Rescan and retry
                    installed_libs = _scan_installed_libraries(libraries_root)
                    for lib_info in installed_libs:
                        lib_filename = resolve_element_from_index(
                            lib_info["library_key"],
                            lib_info["variant"],
                            lib_info["version"],
                            element,
                        )
                        if lib_filename:
                            candidate = lib_info["upf_dir"] / lib_filename
                            if candidate.exists():
                                dest = project_pseudo_dir / candidate.name
                                shutil.copy(candidate, dest)
                                result.mapping[element] = candidate.name
                                result.messages.append(
                                    f"{element}: Copied after download ({candidate.name})"
                                )
                                found = True
                                break
            except Exception as e:
                result.warnings.append(f"{element}: Auto-download failed: {e}")

        # Not found
        if not found:
            result.errors.append(f"{element}: Not found in any location")
            result.success = False

    return result
