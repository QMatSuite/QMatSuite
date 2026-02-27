"""Engine installation orchestration for conda/micromamba and release assets."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import shutil
import ssl
import subprocess
import tarfile
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import certifi

from qmatsuite.core.paths import get_app_data_dir

from .engine_meta import ENGINE_META, get_detection_binaries
from .engine_registry import EngineRegistry
from .micromamba import create_env, remove_env
from .version_probe import run_version_probe

logger = logging.getLogger(__name__)

QE_RELEASE_REPO = "QMatSuite/qmatsuite-toolchain"
PYTHON_ENGINE_BASE_SPEC = "python=3.12"


Installation = Dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _app_dir(app_data_dir: Optional[Path]) -> Path:
    return Path(app_data_dir or get_app_data_dir()).expanduser().resolve()


def _registry_for(app_data_dir: Path) -> EngineRegistry:
    return EngineRegistry(registry_path=app_data_dir / "config" / "engines.json")


def _download_binary(url: str, output_path: Path, on_progress=None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, context=_ssl_context(), timeout=180) as response:
        total = None
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                total = int(content_length)
            except (ValueError, TypeError):
                pass

        downloaded = 0
        chunk_size = 65536  # 64 KB
        with output_path.open("wb") as fh:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                fh.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(bytes_downloaded=downloaded, bytes_total=total)


def _download_text(url: str) -> str:
    with urllib.request.urlopen(url, context=_ssl_context(), timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def _compute_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _parse_sha256(text: str) -> str:
    token = (text or "").strip().split()[0]
    if len(token) != 64:
        raise RuntimeError(f"Invalid SHA256 checksum payload: {text!r}")
    return token.lower()


def _binary_name_variants(binary_name: str) -> List[str]:
    out = [binary_name]
    if binary_name.endswith(".x"):
        out.append(binary_name.replace(".x", ".exe"))
        out.append(f"{binary_name}.exe")
    elif binary_name.endswith(".exe"):
        out.append(binary_name.replace(".exe", ""))
    else:
        out.append(f"{binary_name}.exe")

    unique: List[str] = []
    seen = set()
    for name in out:
        if name not in seen:
            unique.append(name)
            seen.add(name)
    return unique


def _find_python_executable(env_dir: Path) -> Optional[Path]:
    candidates = [
        env_dir / "bin" / "python",
        env_dir / "bin" / "python3",
        env_dir / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _env_bin_dir(env_dir: Path) -> Path:
    unix_bin = env_dir / "bin"
    if unix_bin.is_dir():
        return unix_bin
    win_bin = env_dir / "Scripts"
    if win_bin.is_dir():
        return win_bin
    return unix_bin


def _resolve_binary(bin_dir: Path, binary_name: str) -> Optional[Path]:
    if not bin_dir.is_dir():
        return None
    for variant in _binary_name_variants(binary_name):
        candidate = bin_dir / variant
        if candidate.is_file():
            return candidate
    return None


def _detect_binary_version(engine_family: str, resolved_binary: Path) -> Optional[str]:
    meta = ENGINE_META[engine_family]
    version_command = meta.get("version_command")
    if not isinstance(version_command, list) or not version_command:
        return None

    command = list(version_command)
    command[0] = str(resolved_binary)
    result = run_version_probe(command, timeout=15)
    if result is None:
        return None

    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    if not output:
        return None

    regex = meta.get("version_regex")
    if isinstance(regex, str):
        match = re.search(regex, output)
        if match:
            return match.group(1)

    if result.returncode != 0:
        return None

    return output.splitlines()[0].strip() if output else None


def _verify_binary_engine(engine_family: str, bin_dir: Path) -> Tuple[str, Optional[str]]:
    meta = ENGINE_META[engine_family]
    has_version_command = bool(meta.get("version_command"))
    for binary_name in get_detection_binaries(engine_family):
        resolved = _resolve_binary(bin_dir, binary_name)
        if resolved:
            version = _detect_binary_version(engine_family, resolved)
            if has_version_command and version is None:
                raise RuntimeError(
                    f"Version probe failed for {engine_family} binary: {resolved}"
                )
            return binary_name, version
    raise RuntimeError(f"No required executable detected for {engine_family} in {bin_dir}")


def _verify_python_engine(python_executable: Path, module_name: str) -> str:
    if not module_name:
        raise RuntimeError("python engine metadata missing python_import module")

    result = subprocess.run(
        [str(python_executable), "-c", f"import {module_name}; print({module_name}.__version__)"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"Verification failed for Python engine module '{module_name}' with {python_executable}: {stderr}"
        )

    version = (result.stdout or "").strip()
    return version or "unknown"


def _pip_install_requirements(python_executable: Path, requirements: dict[str, str]) -> None:
    """Install pip packages into a conda environment's Python."""
    if not requirements:
        return
    pip_packages = list(requirements.keys())
    result = subprocess.run(
        [str(python_executable), "-m", "pip", "install", "--no-input", *pip_packages],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pip install failed for {pip_packages}: {(result.stderr or '').strip()}")


def _verify_pip_requirements(python_executable: Path, requirements: dict[str, str]) -> None:
    """Verify all pip requirements are importable."""
    for pip_name, import_name in requirements.items():
        result = subprocess.run(
            [str(python_executable), "-c", f"import {import_name}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pip dep '{pip_name}' (import: {import_name}) not importable")


def _normalize_engine(engine_family: str) -> str:
    family = (engine_family or "").strip().lower()
    if family not in ENGINE_META:
        raise ValueError(f"Unknown engine family: {engine_family}")
    return family


def _sanitize_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    token = token.strip("-.")
    return token or "latest"


def _build_conda_env_name(engine_family: str, version: Optional[str]) -> str:
    suffix = _sanitize_token(version or "latest")
    return f"{engine_family}-{suffix}"


def _version_hint_from_name(name: str) -> Optional[str]:
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", name)
    return match.group(1) if match else None


def _variant_hint_from_name(name: str) -> Optional[str]:
    lowered = name.lower()
    if "openmp" in lowered:
        return "openmp"
    if "mpi" in lowered:
        return "mpi"
    return None


def _release_url_from_asset_url(asset_url: str) -> Optional[str]:
    marker = "/releases/download/"
    if marker not in asset_url:
        return None

    prefix, rest = asset_url.split(marker, 1)
    parts = rest.split("/", 1)
    if len(parts) != 2:
        return None
    tag = parts[0]
    return f"{prefix}/releases/tag/{tag}"


def _find_binary_in_tree(root: Path, engine_family: str) -> Tuple[Path, str]:
    candidates: List[Path] = []
    valid_names = set()
    for binary_name in get_detection_binaries(engine_family):
        valid_names.update(_binary_name_variants(binary_name))

    for file_path in root.rglob("*"):
        if file_path.is_file() and file_path.name in valid_names:
            candidates.append(file_path)

    if not candidates:
        raise RuntimeError(f"No {engine_family} binary found in extracted payload: {root}")

    candidates.sort(key=lambda p: (0 if "bin" in p.parts else 1, len(p.parts), str(p)))
    selected = candidates[0]
    return selected.parent, selected.name


def _parse_checksums_txt(text: str, target_filename: str) -> Optional[str]:
    """Parse a ``checksums.txt`` (sha256sum output format) and return the hash for *target_filename*.

    Each line is expected to be ``<64-char-hex>  <filename>`` (two-space separator).
    Returns ``None`` when the file is not found or the text is empty/malformed.
    """
    if not text:
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)  # split on whitespace, max 2 tokens
        if len(parts) != 2:
            continue
        digest, fname = parts
        # Strip leading '*' that some sha256sum implementations prepend to binary-mode filenames
        fname = fname.lstrip("*").strip()
        if len(digest) != 64:
            continue
        if fname == target_filename:
            return digest.lower()
    return None


def _verify_sha256(
    asset_path: Path,
    expected_hash: Optional[str] = None,
    checksum_url: Optional[str] = None,
) -> None:
    """Verify SHA256 of *asset_path* against *expected_hash* or a remote checksum URL.

    Priority: direct *expected_hash* > download from *checksum_url* > warn and return.
    On mismatch the bad file is deleted and ``RuntimeError`` is raised.
    """
    expected: Optional[str] = None

    if expected_hash:
        expected = expected_hash.strip().lower()
    elif checksum_url:
        checksum_text = _download_text(checksum_url)
        expected = _parse_sha256(checksum_text)

    if not expected:
        logger.warning("No checksum available for %s — skipping verification", asset_path.name)
        return

    actual = _compute_sha256(asset_path)
    if expected != actual.lower():
        try:
            asset_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise RuntimeError(
            f"Checksum mismatch for {asset_path.name}: expected {expected}, got {actual}"
        )


def resolve_qe_github_release_asset(
    version: Optional[str] = None,
    variant: str = "openmp",
) -> Dict[str, str]:
    """Resolve QE GitHub release asset URL for current platform.

    Strategy:
    - Always read releases from QMatSuite/qmatsuite-toolchain.
    - Map host platform to a concrete QE variant string.
    - Find the latest release whose tag starts with ``qe-<version>-<variant>-``.
    - Require exact zip asset match: ``qe-<version>-<variant>.zip``.
    """
    normalized_variant = (variant or "openmp").strip().lower()
    if normalized_variant not in {"openmp", "mpi"}:
        raise ValueError("variant must be one of: openmp, mpi")

    system = platform.system().lower()
    machine = platform.machine().lower()
    qe_version = (version or "7.5").strip().lstrip("v")
    if not qe_version:
        qe_version = "7.5"

    platform_variant: Optional[str]
    if system == "windows" and machine in {"amd64", "x86_64"}:
        # Toolchain Windows artifacts are published as oneAPI+MSMPI bundles.
        platform_variant = "win-oneapi-msmpi"
    elif system == "darwin" and machine in {"arm64", "aarch64"}:
        platform_variant = f"macos-arm64-{normalized_variant}"
    elif system == "darwin" and machine in {"x86_64", "amd64"}:
        platform_variant = f"macos-x64-{normalized_variant}"
    elif system == "linux" and machine in {"x86_64", "amd64"}:
        platform_variant = f"linux-x64-{normalized_variant}"
    else:
        platform_variant = None

    if not platform_variant:
        raise RuntimeError(f"No QE GitHub binary mapping for platform {system}/{machine}")

    repo = QE_RELEASE_REPO
    tag_prefix = f"qe-{qe_version}-{platform_variant}"
    asset_name = f"{tag_prefix}.zip"
    api_url = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    payload = json.loads(_download_text(api_url))
    releases = payload if isinstance(payload, list) else []
    if not releases:
        raise RuntimeError(f"No releases available in {repo}")

    for release in releases:
        if not isinstance(release, dict):
            continue
        release_tag = str(release.get("tag_name") or "")
        if not (release_tag == tag_prefix or release_tag.startswith(f"{tag_prefix}-")):
            continue

        assets = release.get("assets")
        if not isinstance(assets, list):
            continue

        zip_asset: Optional[Dict[str, Any]] = None
        checksum_asset: Optional[Dict[str, Any]] = None
        checksums_txt_asset: Optional[Dict[str, Any]] = None
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            if name == asset_name:
                zip_asset = asset
            elif name == f"{asset_name}.sha256":
                checksum_asset = asset
            elif name == "checksums.txt":
                checksums_txt_asset = asset

        if not zip_asset:
            continue

        asset_url = str(zip_asset.get("browser_download_url") or "")
        if not asset_url:
            continue

        checksum_url = ""
        if checksum_asset:
            checksum_url = str(checksum_asset.get("browser_download_url") or "")

        # Try to extract expected_sha256 from checksums.txt if no per-asset .sha256
        expected_sha256: Optional[str] = None
        if not checksum_url and checksums_txt_asset:
            checksums_txt_url = str(checksums_txt_asset.get("browser_download_url") or "")
            if checksums_txt_url:
                try:
                    checksums_text = _download_text(checksums_txt_url)
                    expected_sha256 = _parse_checksums_txt(checksums_text, asset_name)
                except Exception as exc:
                    logger.warning("Failed to fetch checksums.txt: %s", exc)

        release_url = str(release.get("html_url") or _release_url_from_asset_url(asset_url) or "")
        result: Dict[str, Any] = {
            "asset_url": asset_url,
            "asset_name": asset_name,
            "checksum_url": checksum_url,
            "release_url": release_url,
            "release_tag": release_tag,
            "variant": platform_variant,
            "repo": repo,
        }
        if expected_sha256:
            result["expected_sha256"] = expected_sha256
        return result

    raise RuntimeError(
        "No QE release asset found for "
        f"platform={system}/{machine} in {repo} "
        f"(tag prefix='{tag_prefix}', asset='{asset_name}')"
    )


def install_engine_conda(
    engine_family: str,
    version: str | None = None,
    app_data_dir: Path | None = None,
    on_progress=None,
) -> Installation:
    """Install an engine via micromamba and register it in engines.json."""
    family = _normalize_engine(engine_family)
    meta = ENGINE_META[family]
    conda_package = meta.get("conda_package")
    if not conda_package:
        raise ValueError(f"Engine '{family}' has no conda package; use register_engine for manual setup.")

    app_dir = _app_dir(app_data_dir)
    app_dir.mkdir(parents=True, exist_ok=True)

    env_name = _build_conda_env_name(family, version)
    package_spec = str(conda_package)
    if version:
        package_spec = f"{package_spec}={version}"

    packages = [package_spec]
    if meta.get("engine_type") == "python":
        packages = [PYTHON_ENGINE_BASE_SPEC, package_spec]

    channels = [str(meta.get("conda_channel") or "conda-forge")]

    if on_progress:
        on_progress(stage="Bootstrapping micromamba")

    env_created = False
    try:
        if on_progress:
            on_progress(stage="Installing via conda")
        env_dir = create_env(env_name, packages, channels, app_dir, on_progress=on_progress)
        env_created = True

        if on_progress:
            on_progress(stage="Verifying installation")

        installation: Installation
        detected_version: Optional[str] = None

        if meta.get("engine_type") == "python":
            pyexe = _find_python_executable(env_dir)
            if not pyexe:
                raise RuntimeError(f"Python executable not found in environment: {env_dir}")
            detected_version = _verify_python_engine(pyexe, str(meta.get("python_import") or ""))
            pip_reqs = meta.get("pip_requirements", {})
            if pip_reqs:
                if on_progress:
                    on_progress(stage="Installing pip requirements")
                _pip_install_requirements(pyexe, pip_reqs)
                _verify_pip_requirements(pyexe, pip_reqs)
            installation = {
                "id": "",
                "source": "micromamba",
                "version": detected_version or version,
                "python_executable": str(pyexe),
                "conda_env": env_name,
                "env_vars": {},
                "verified": _utc_now_iso(),
            }
        else:
            bin_dir = _env_bin_dir(env_dir)
            binary_name, detected_version = _verify_binary_engine(family, bin_dir)
            installation = {
                "id": "",
                "source": "micromamba",
                "version": detected_version or version,
                "path": str(bin_dir),
                "conda_env": env_name,
                "required_binaries": [binary_name],
                "env_vars": {},
                "verified": _utc_now_iso(),
            }

        if not installation.get("version"):
            installation["version"] = version or "unknown"

        install_id = f"conda-{installation['version']}" if installation.get("version") else f"conda-{env_name}"
        installation["id"] = install_id

        if on_progress:
            on_progress(stage="Registering")

        registry = _registry_for(app_dir)
        registry.add_installation(family, installation)
        registry.set_active(family, install_id)
        return installation

    except Exception:
        if env_created:
            try:
                remove_env(env_name, app_dir)
            except Exception as cleanup_exc:
                logger.warning("Failed to cleanup micromamba env '%s': %s", env_name, cleanup_exc)
        raise


def install_engine_github_release(
    engine_family: str,
    asset_url: str,
    checksum_url: str | None = None,
    expected_sha256: str | None = None,
    app_data_dir: Path | None = None,
    on_progress=None,
) -> Installation:
    """Install an engine from a GitHub release asset and register it."""
    family = _normalize_engine(engine_family)
    if ENGINE_META[family].get("engine_type") != "binary":
        raise ValueError(f"GitHub release installation is only supported for binary engines: {family}")

    app_dir = _app_dir(app_data_dir)
    downloads_dir = app_dir / ".tmp" / "downloads"
    unpack_dir = app_dir / ".tmp" / "unpack" / f"{family}-{uuid.uuid4().hex}"
    asset_name = Path(urllib.parse.urlparse(asset_url).path).name or f"{family}-asset"
    asset_path = downloads_dir / asset_name

    downloads_dir.mkdir(parents=True, exist_ok=True)
    unpack_dir.mkdir(parents=True, exist_ok=True)

    if on_progress:
        on_progress(stage="Downloading")
    _download_binary(asset_url, asset_path, on_progress=on_progress)

    if on_progress:
        on_progress(stage="Verifying checksum")
    checksum = (checksum_url or "").strip() or None
    _verify_sha256(asset_path, expected_hash=expected_sha256, checksum_url=checksum)

    if on_progress:
        on_progress(stage="Extracting")

    if zipfile.is_zipfile(asset_path):
        with zipfile.ZipFile(asset_path) as archive:
            archive.extractall(unpack_dir)
    elif tarfile.is_tarfile(asset_path):
        with tarfile.open(asset_path) as archive:
            archive.extractall(unpack_dir)
    else:
        # Treat as direct executable payload.
        binary_name = get_detection_binaries(family)[0]
        bin_dir = unpack_dir / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        target = bin_dir / binary_name
        shutil.copy2(asset_path, target)
        if platform.system() != "Windows":
            target.chmod(0o755)

    source_bin_dir, detected_binary_name = _find_binary_in_tree(unpack_dir, family)

    version_hint = _version_hint_from_name(asset_name) or "unknown"
    variant = _variant_hint_from_name(asset_name)
    install_suffix = version_hint if not variant else f"{version_hint}-{variant}"
    install_id = f"github-{install_suffix}"

    target_root = app_dir / "engines" / family / install_id
    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(unpack_dir, target_root)

    final_bin_dir, _ = _find_binary_in_tree(target_root, family)
    if platform.system() != "Windows" and final_bin_dir.is_dir():
        for entry in final_bin_dir.iterdir():
            if entry.is_file():
                entry.chmod(entry.stat().st_mode | 0o111)

    # Strip macOS quarantine xattr (Gatekeeper blocks unsigned binaries)
    if platform.system() == "Darwin":
        try:
            subprocess.run(
                ["xattr", "-dr", "com.apple.quarantine", str(target_root)],
                capture_output=True,
            )
        except FileNotFoundError:
            pass  # xattr not available, skip

    if on_progress:
        on_progress(stage="Registering")

    installation: Installation = {
        "id": install_id,
        "source": "github_release",
        "version": version_hint,
        "path": str(final_bin_dir),
        "required_binaries": [detected_binary_name],
        "env_vars": {},
        "verified": _utc_now_iso(),
    }

    release_url = _release_url_from_asset_url(asset_url)
    if release_url:
        installation["release_url"] = release_url
    if variant:
        installation["variant"] = variant

    registry = _registry_for(app_dir)
    registry.add_installation(family, installation)
    registry.set_active(family, install_id)
    return installation


def uninstall_engine(
    engine_family: str,
    installation_id: str,
    app_data_dir: Path | None = None,
) -> None:
    """Uninstall an engine installation and deregister it from engines.json."""
    family = _normalize_engine(engine_family)
    app_dir = _app_dir(app_data_dir)
    registry = _registry_for(app_dir)

    installation = None
    for entry in registry.list_installations(family):
        if entry.get("id") == installation_id:
            installation = entry
            break
    if installation is None:
        raise ValueError(f"Installation '{installation_id}' not found for engine '{family}'")

    source = str(installation.get("source") or "")
    if source == "micromamba":
        conda_env = installation.get("conda_env")
        if conda_env:
            remove_env(str(conda_env), app_dir)
    elif source in {"github_release", "bundled"}:
        path = Path(str(installation.get("path") or "")).expanduser()
        candidate = path.parent if path.name.lower() in {"bin", "scripts"} else path
        try:
            candidate = candidate.resolve()
        except Exception:
            candidate = candidate

        engines_root = (app_dir / "engines").resolve()
        if candidate.exists() and (candidate == engines_root or engines_root in candidate.parents):
            shutil.rmtree(candidate, ignore_errors=True)

    registry.remove_installation(family, installation_id)


def list_installable_engines() -> List[Dict[str, Any]]:
    """Return installation methods available per engine family."""
    rows: List[Dict[str, Any]] = []
    for family in sorted(ENGINE_META):
        meta = ENGINE_META[family]
        methods: List[str] = []
        if meta.get("conda_package"):
            methods.append("conda")
        if family == "qe":
            methods.append("github_release")

        rows.append(
            {
                "engine": family,
                "display_name": meta.get("display_name") or family,
                "engine_type": meta.get("engine_type") or "binary",
                "install_methods": methods,
                "conda_package": meta.get("conda_package"),
                "conda_channel": meta.get("conda_channel"),
                "manual_only": not methods,
            }
        )
    return rows


__all__ = [
    "install_engine_conda",
    "install_engine_github_release",
    "uninstall_engine",
    "list_installable_engines",
    "resolve_qe_github_release_asset",
]
