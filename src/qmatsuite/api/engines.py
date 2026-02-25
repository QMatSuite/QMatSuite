"""API-facing engine registry operations for daemon/CLI/MCP callers."""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qmatsuite.core.engines.engine_meta import (
    ENGINE_META,
    get_platform_primary_binary,
)
from qmatsuite.core.engines.engine_installer import (
    install_engine_conda,
    install_engine_github_release,
    list_installable_engines as _list_installable_engines_kernel,
    resolve_qe_github_release_asset,
    uninstall_engine as uninstall_engine_kernel,
)
from qmatsuite.core.engines.engine_registry import EngineRegistry


# Platforms for which we publish pre-built QE binaries via qmatsuite-toolchain.
_QE_TOOLCHAIN_PLATFORMS: set[tuple[str, str]] = {
    ("darwin", "arm64"),
    ("darwin", "aarch64"),
    ("darwin", "x86_64"),
    ("darwin", "amd64"),
    ("windows", "amd64"),
    ("windows", "x86_64"),
}


def _qe_github_release_available() -> bool:
    """Return True if a QE toolchain binary is published for the current platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    return (system, machine) in _QE_TOOLCHAIN_PLATFORMS


def _make_user_installation_id(prefix: str, seed: str) -> str:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def _check_python_import_current(module_name: str) -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module_name}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return False
    return result.returncode == 0


def _engine_installed_via_fallback(engine_family: str) -> bool:
    meta = ENGINE_META[engine_family]
    if meta.get("engine_type") == "python":
        module_name = str(meta.get("python_import") or "")
        return bool(module_name) and _check_python_import_current(module_name)

    primary = get_platform_primary_binary(engine_family)
    if not primary:
        return False
    return shutil.which(primary) is not None


def list_engines(installed_only: bool = False) -> List[Dict[str, Any]]:
    """Return install status for all engines with registry-first detection."""
    registry = EngineRegistry()
    data = registry.discover(persist=False)
    engines = data.get("engines", {})

    out: List[Dict[str, Any]] = []
    for engine_family in sorted(ENGINE_META):
        entry = engines.get(engine_family, {})
        installations = list(entry.get("installations") or [])
        active_id = entry.get("active")
        active = next((inst for inst in installations if inst.get("id") == active_id), None)

        installed = False
        source = None
        if active and not active.get("stale", False):
            installed = True
            source = active.get("source")
        else:
            installed = _engine_installed_via_fallback(engine_family)
            source = "fallback" if installed else None

        if installed_only and not installed:
            continue

        out.append(
            {
                "engine": engine_family,
                "installed": installed,
                "active_installation_id": active_id,
                "active_source": source,
                "active": active,
                "installations": installations,
            }
        )
    return out


def get_active_engine(engine_family: str) -> Optional[Dict[str, Any]]:
    """Return active installation entry for an engine family."""
    registry = EngineRegistry()
    return registry.get_active(engine_family)


def set_active_engine(engine_family: str, installation_id: str) -> bool:
    """Switch active installation for an engine family."""
    registry = EngineRegistry()
    return registry.set_active(engine_family, installation_id)


def verify_engine(engine_family: str) -> Tuple[bool, str]:
    """Verify the currently active installation for an engine."""
    registry = EngineRegistry()
    return registry.verify_engine(engine_family)


def register_engine(
    engine_family: str,
    path: str | Path,
    source: str,
    env_vars: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Register a user-provided engine installation and set it active."""
    if engine_family not in ENGINE_META:
        raise ValueError(f"Unknown engine family: {engine_family}")

    registry = EngineRegistry()
    meta = ENGINE_META[engine_family]
    src = str(source)
    src_path = Path(path).expanduser().resolve()
    env = dict(env_vars or {})

    if meta.get("engine_type") == "python":
        pyexe = src_path
        if src_path.is_dir():
            candidates = [
                src_path / "bin" / "python",
                src_path / "bin" / "python3",
                src_path / "Scripts" / "python.exe",
            ]
            pyexe = next((c for c in candidates if c.is_file()), src_path)
        if not pyexe.is_file():
            raise ValueError(f"Python executable not found for {engine_family}: {src_path}")
        installation = {
            "id": _make_user_installation_id("user", f"{engine_family}:{pyexe}"),
            "source": src if src in {"user_venv", "micromamba"} else "user_venv",
            "python_executable": str(pyexe),
            "env_vars": env,
        }
    else:
        primary = get_platform_primary_binary(engine_family)
        required = [primary] if primary else list(meta.get("required_binaries") or [])
        installation = {
            "id": _make_user_installation_id("user", f"{engine_family}:{src_path}"),
            "source": src if src in {"user_path", "system_path", "bundled", "github_release"} else "user_path",
            "path": str(src_path),
            "required_binaries": required,
            "env_vars": env,
        }

    registry.add_installation(engine_family, installation)
    registry.set_active(engine_family, installation["id"])
    return installation


def unregister_engine(engine_family: str, installation_id: str) -> bool:
    """Remove a registered installation entry."""
    registry = EngineRegistry()
    return registry.remove_installation(engine_family, installation_id)


def install_engine(
    engine_family: str,
    version: str | None = None,
    source: str = "auto",
    on_progress=None,
) -> Dict[str, Any]:
    """
    Install an engine via conda/micromamba or GitHub release.

    Args:
        engine_family: Engine family key (e.g. ``xtb``)
        version: Optional version string
        source: ``auto`` | ``conda`` | ``github_release``
        on_progress: Optional callback receiving keyword progress events.
    """
    family = (engine_family or "").strip().lower()
    if family not in ENGINE_META:
        raise ValueError(f"Unknown engine family: {engine_family}")

    selected_source = (source or "auto").strip().lower()
    if selected_source == "auto":
        if family == "qe" and _qe_github_release_available():
            # Prefer signed, platform-optimized toolchain binary on macOS/Windows.
            selected_source = "github_release"
        elif ENGINE_META[family].get("conda_package"):
            selected_source = "conda"
        elif family == "qe":
            # Fallback for platforms without toolchain binaries (e.g. Linux).
            selected_source = "github_release"
        else:
            raise ValueError(
                f"Engine '{family}' has no automatic installer. Use register_engine(path=...) instead."
            )

    if selected_source == "conda":
        installation = install_engine_conda(family, version=version, on_progress=on_progress)
    elif selected_source == "github_release":
        if family != "qe":
            raise ValueError(
                f"GitHub release installer is currently supported for QE only (got '{family}')."
            )
        release_asset = resolve_qe_github_release_asset(version=version, variant="openmp")
        installation = install_engine_github_release(
            family,
            asset_url=release_asset["asset_url"],
            checksum_url=release_asset.get("checksum_url") or None,
            expected_sha256=release_asset.get("expected_sha256"),
            on_progress=on_progress,
        )
    else:
        raise ValueError(
            "Invalid source. Expected one of: auto, conda, github_release"
        )

    return {
        "engine": family,
        "source": selected_source,
        "installation": installation,
    }


def uninstall_engine(engine_family: str, installation_id: str) -> Dict[str, Any]:
    """Uninstall an engine installation by installation ID."""
    family = (engine_family or "").strip().lower()
    if family not in ENGINE_META:
        raise ValueError(f"Unknown engine family: {engine_family}")
    uninstall_engine_kernel(family, installation_id)
    return {
        "engine": family,
        "installation_id": installation_id,
        "removed": True,
    }


def list_installable_engines() -> List[Dict[str, Any]]:
    """Return engine families with available install methods."""
    return _list_installable_engines_kernel()


def get_bundled_qe_staging_status() -> Optional[str]:
    """Return bundled QE staging status for Electron full variant.

    Returns None (lite/non-Electron), "ready", "staging", or "staging_incomplete".
    """
    from qmatsuite.core.engines.bundled_staging import check_bundled_qe_status

    return check_bundled_qe_status()


def get_bundled_sssp_staging_status() -> Optional[str]:
    """Return bundled SSSP staging status for Electron full variant.

    Returns None (lite/non-Electron), "ready", "staging", or "staging_incomplete".
    """
    from qmatsuite.core.engines.bundled_staging import check_bundled_sssp_status

    return check_bundled_sssp_status()


__all__ = [
    "list_engines",
    "get_active_engine",
    "set_active_engine",
    "verify_engine",
    "register_engine",
    "unregister_engine",
    "install_engine",
    "uninstall_engine",
    "list_installable_engines",
    "get_bundled_qe_staging_status",
    "get_bundled_sssp_staging_status",
]
