"""Centralized engine discovery — single SSOT for engine availability.

This module provides a unified engine discovery function used by both
the runner (preflight) and tests (skip logic). Each engine has a probe
definition describing how to find it. The discovery function applies a
tiered search strategy:

1. Bundled: .qmatsuite/engines/<engine>/<variant>/bin/*
2. Python import (Python-native engines): subprocess isolation
3. Conda environments
4. Environment variables
5. System PATH (shutil.which)
6. Homebrew (macOS)
7. Shell profile PATH parsing
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EngineProbe:
    """Describes how to locate a specific engine on the system."""

    engine_name: str
    binary_names: List[str] = field(default_factory=list)
    python_module: Optional[str] = None
    env_vars: List[str] = field(default_factory=list)
    brew_name: Optional[str] = None
    conda_package: Optional[str] = None
    # If the binary is bundled inside another engine's directory
    # e.g. wannier90.x ships inside .qmatsuite/engines/qe/*/bin/
    bundled_under: Optional[str] = None


@dataclass
class EngineDiscoveryResult:
    """Result of an engine discovery attempt."""

    engine_name: str
    available: bool
    executable_path: Optional[Path] = None
    version: Optional[str] = None
    source: Optional[str] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Static probe registry (one entry per engine)
# ---------------------------------------------------------------------------

_ENGINE_PROBES: Dict[str, EngineProbe] = {
    "qe": EngineProbe(
        engine_name="qe",
        binary_names=["pw.x"],
        env_vars=["QE_HOME"],
    ),
    "vasp": EngineProbe(
        engine_name="vasp",
        binary_names=["vasp_std", "vasp_gam", "vasp_ncl"],
        env_vars=["VASP_HOME"],
    ),
    "cp2k": EngineProbe(
        engine_name="cp2k",
        binary_names=[
            "cp2k.psmp",
            "cp2k.popt",
            "cp2k.ssmp",
            "cp2k.sopt",
            "cp2k",
        ],
        env_vars=["CP2K_EXECUTABLE", "CP2K_HOME", "CP2K_BIN"],
        brew_name="cp2k",
    ),
    "lammps": EngineProbe(
        engine_name="lammps",
        binary_names=["lmp_serial", "lmp_mpi", "lmp"],
        env_vars=["QMATS_LAMMPS_BIN"],
        brew_name="lammps",
    ),
    "orca": EngineProbe(
        engine_name="orca",
        binary_names=["orca"],
        env_vars=["ORCA_HOME"],
    ),
    "qmcpack": EngineProbe(
        engine_name="qmcpack",
        binary_names=["qmcpack"],
        env_vars=["QMATS_QMCPACK_BIN"],
    ),
    "pyscf": EngineProbe(
        engine_name="pyscf",
        python_module="pyscf",
    ),
    "psi4": EngineProbe(
        engine_name="psi4",
        python_module="psi4",
        conda_package="psi4",
    ),
    "gpaw": EngineProbe(
        engine_name="gpaw",
        python_module="gpaw",
    ),
    "w90": EngineProbe(
        engine_name="w90",
        binary_names=["wannier90.x", "wannier90"],
        env_vars=["W90_HOME"],
        bundled_under="qe",  # wannier90.x ships inside QE: .qmatsuite/engines/qe/*/bin/
    ),
    "siesta": EngineProbe(
        engine_name="siesta",
        binary_names=["siesta"],
        conda_package="siesta",
    ),
    "xtb": EngineProbe(
        engine_name="xtb",
        binary_names=["xtb"],
        conda_package="xtb",
    ),
    "yambo": EngineProbe(
        engine_name="yambo",
        binary_names=["yambo", "p2y", "ypp"],
        env_vars=["YAMBO_HOME"],
    ),
    "abinit": EngineProbe(
        engine_name="abinit",
        binary_names=["abinit"],
        env_vars=["ABINIT_HOME", "ABI_HOME"],
        brew_name="abinit",
    ),
    "gaussian": EngineProbe(
        engine_name="gaussian",
        binary_names=["g16", "g09", "g03"],
        env_vars=["g16root", "g09root", "g03root", "GAUSS_EXEDIR"],
    ),
}

# Shell profile files to parse (in priority order)
_SHELL_PROFILES = [
    ".zshrc",
    ".zprofile",
    ".zshenv",
    ".bashrc",
    ".bash_profile",
    ".profile",
]

# Cache to avoid repeated discovery
_discovery_cache: Dict[str, EngineDiscoveryResult] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_repo_root() -> Optional[Path]:
    """Auto-detect the repo/project root by walking up from CWD or package location.

    Looks for markers: ``.qmatsuite/engines/`` directory, ``project.qv.yml``,
    or ``pyproject.toml`` (for dev checkout).

    Tries CWD first, then falls back to walking up from the ``quantumvitas``
    package installation path (handles test environments where CWD is a tmpdir).
    """
    start_points = [Path.cwd().resolve()]

    # Fallback: walk up from the quantumvitas package directory
    # (handles conftest fixtures that change CWD to tmpdir)
    pkg_dir = Path(__file__).resolve().parent  # core/engines/
    start_points.append(pkg_dir)

    for start in start_points:
        current = start
        for _ in range(20):  # safety limit
            if (current / ".qmatsuite" / "engines").is_dir():
                return current
            if (current / "project.qv.yml").is_file():
                return current
            if (current / "pyproject.toml").is_file() and (current / "src").is_dir():
                return current
            parent = current.parent
            if parent == current:
                break
            current = parent
    return None


# ---------------------------------------------------------------------------
# Internal search functions
# ---------------------------------------------------------------------------


def _search_bundled(
    probe: EngineProbe,
    project_root: Optional[Path],
) -> Optional[EngineDiscoveryResult]:
    """Tier 1: Search .qmatsuite/engines/<engine>/<variant>/bin/*.

    Also searches inside a parent engine's directory if ``bundled_under``
    is set (e.g. wannier90.x inside .qmatsuite/engines/qe/*/bin/).
    """
    # Collect engine subdirectory names to search
    engine_dirs = [probe.engine_name]
    if probe.bundled_under:
        engine_dirs.append(probe.bundled_under)

    search_bases: List[Path] = []

    # If a project_root is explicitly provided, search only that root.
    # This keeps discovery deterministic in tests that pass isolated tmp roots.
    if project_root:
        search_bases.append(project_root / ".qmatsuite" / "engines")
    else:
        # No explicit project root: use managed app-data engines location.
        try:
            from quantumvitas.core.paths import home_engines_dir

            managed_base = home_engines_dir()
            search_bases.append(managed_base)
        except Exception:
            pass

    for base in search_bases:
        for engine_dir_name in engine_dirs:
            root = base / engine_dir_name
            if not root.is_dir():
                continue
            # Sort variants in reverse (newest/highest version first)
            for variant_dir in sorted(root.iterdir(), reverse=True):
                if not variant_dir.is_dir():
                    continue
                # Check bin/ subdirectory first (standard layout)
                bin_dir = variant_dir / "bin"
                if bin_dir.is_dir():
                    for binary_name in probe.binary_names:
                        candidate = bin_dir / binary_name
                        if candidate.is_file():
                            return EngineDiscoveryResult(
                                engine_name=probe.engine_name,
                                available=True,
                                executable_path=candidate,
                                source="bundled",
                            )
                # Also check directly in variant dir (ORCA layout)
                for binary_name in probe.binary_names:
                    candidate = variant_dir / binary_name
                    if candidate.is_file():
                        return EngineDiscoveryResult(
                            engine_name=probe.engine_name,
                            available=True,
                            executable_path=candidate,
                            source="bundled",
                        )
                # Check variant / binary_name / binary_name (Gaussian layout)
                for binary_name in probe.binary_names:
                    candidate = variant_dir / binary_name / binary_name
                    if candidate.is_file():
                        return EngineDiscoveryResult(
                            engine_name=probe.engine_name,
                            available=True,
                            executable_path=candidate,
                            source="bundled",
                        )
    return None


def _search_python_import(
    probe: EngineProbe,
) -> Optional[EngineDiscoveryResult]:
    """Tier 2: Python import check via subprocess (avoids import shadowing)."""
    if not probe.python_module:
        return None
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import {probe.python_module}; print({probe.python_module}.__version__)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return EngineDiscoveryResult(
                engine_name=probe.engine_name,
                available=True,
                executable_path=Path(sys.executable),
                version=version,
                source="python_import",
            )
    except (subprocess.TimeoutExpired, Exception):
        pass
    return None


def _search_conda(probe: EngineProbe) -> Optional[EngineDiscoveryResult]:
    """Tier 3: Check conda environments.

    Strategy:
    1. Find conda base prefix from $CONDA_PREFIX or known locations
    2. For Python packages: try importing with conda base's python
    3. For binary packages: check $CONDA_PREFIX/bin/
    """
    if not probe.conda_package:
        return None

    # Find conda base prefix
    conda_prefix = os.environ.get("CONDA_PREFIX")
    conda_base_candidates = []
    if conda_prefix:
        conda_base_candidates.append(Path(conda_prefix))
    # Common conda base locations
    for base_path in [
        Path.home() / "miniforge3",
        Path.home() / "miniconda3",
        Path.home() / "anaconda3",
        Path("/opt/homebrew/Caskroom/miniforge/base"),
        Path("/opt/homebrew/Caskroom/miniconda/base"),
    ]:
        if base_path.is_dir() and base_path not in conda_base_candidates:
            conda_base_candidates.append(base_path)

    # For Python packages: try importing with conda base's python
    if probe.python_module:
        for conda_base in conda_base_candidates:
            conda_python = conda_base / "bin" / "python"
            if not conda_python.is_file():
                continue
            try:
                result = subprocess.run(
                    [
                        str(conda_python),
                        "-c",
                        f"import {probe.python_module}; print({probe.python_module}.__version__)",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    return EngineDiscoveryResult(
                        engine_name=probe.engine_name,
                        available=True,
                        executable_path=conda_python,
                        version=version,
                        source="conda",
                    )
            except (subprocess.TimeoutExpired, Exception):
                continue

    # For binary packages: check conda prefix/bin/
    for conda_base in conda_base_candidates:
        bin_dir = conda_base / "bin"
        if not bin_dir.is_dir():
            continue
        for binary_name in probe.binary_names:
            candidate = bin_dir / binary_name
            if candidate.is_file():
                return EngineDiscoveryResult(
                    engine_name=probe.engine_name,
                    available=True,
                    executable_path=candidate,
                    source="conda",
                )

    return None


def _search_env_var(probe: EngineProbe) -> Optional[EngineDiscoveryResult]:
    """Tier 4: Check environment variables."""
    for env_var in probe.env_vars:
        env_val = os.environ.get(env_var)
        if not env_val:
            continue
        env_path = Path(env_val)
        # If it points directly to a file (binary)
        if env_path.is_file() and os.access(env_path, os.X_OK):
            return EngineDiscoveryResult(
                engine_name=probe.engine_name,
                available=True,
                executable_path=env_path,
                source="env_var",
            )
        # If it points to a directory, look for binaries inside
        if env_path.is_dir():
            for binary_name in probe.binary_names:
                candidate = env_path / binary_name
                if candidate.is_file():
                    return EngineDiscoveryResult(
                        engine_name=probe.engine_name,
                        available=True,
                        executable_path=candidate,
                        source="env_var",
                    )
                # Also check bin/ subdirectory
                candidate = env_path / "bin" / binary_name
                if candidate.is_file():
                    return EngineDiscoveryResult(
                        engine_name=probe.engine_name,
                        available=True,
                        executable_path=candidate,
                        source="env_var",
                    )
                # Also check binary_name/ subdirectory (Gaussian layout: g09root/g09/g09)
                candidate = env_path / binary_name / binary_name
                if candidate.is_file():
                    return EngineDiscoveryResult(
                        engine_name=probe.engine_name,
                        available=True,
                        executable_path=candidate,
                        source="env_var",
                    )
    return None


def _search_system_path(
    probe: EngineProbe,
) -> Optional[EngineDiscoveryResult]:
    """Tier 5: Check system PATH via shutil.which."""
    for binary_name in probe.binary_names:
        found = shutil.which(binary_name)
        if found:
            return EngineDiscoveryResult(
                engine_name=probe.engine_name,
                available=True,
                executable_path=Path(found),
                source="path",
            )
    return None


def _search_homebrew(probe: EngineProbe) -> Optional[EngineDiscoveryResult]:
    """Tier 6: Check Homebrew (macOS)."""
    if not probe.brew_name:
        return None
    if sys.platform != "darwin":
        return None

    # Try brew --prefix
    try:
        result = subprocess.run(
            ["brew", "--prefix", probe.brew_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            prefix = Path(result.stdout.strip())
            bin_dir = prefix / "bin"
            if bin_dir.is_dir():
                for binary_name in probe.binary_names:
                    candidate = bin_dir / binary_name
                    if candidate.is_file():
                        return EngineDiscoveryResult(
                            engine_name=probe.engine_name,
                            available=True,
                            executable_path=candidate,
                            source="homebrew",
                        )
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass

    # Fallback: hardcoded Homebrew paths
    for brew_prefix in [Path("/opt/homebrew"), Path("/usr/local")]:
        bin_dir = brew_prefix / "bin"
        if not bin_dir.is_dir():
            continue
        for binary_name in probe.binary_names:
            candidate = bin_dir / binary_name
            if candidate.is_file():
                return EngineDiscoveryResult(
                    engine_name=probe.engine_name,
                    available=True,
                    executable_path=candidate,
                    source="homebrew",
                )

    return None


def _extract_paths_from_shell_profiles() -> List[Path]:
    """Extract PATH directories from shell profile files."""
    extra_paths: List[Path] = []
    home = Path.home()

    for profile_name in _SHELL_PROFILES:
        profile_path = home / profile_name
        if not profile_path.is_file():
            continue
        try:
            content = profile_path.read_text(errors="replace")
            # Match export PATH="...:$PATH" or PATH=...:$PATH patterns
            for match in re.finditer(
                r'(?:export\s+)?PATH\s*=\s*["\']?([^"\'$\n]+)', content
            ):
                raw_paths = match.group(1)
                for segment in raw_paths.split(":"):
                    segment = segment.strip()
                    if not segment or segment.startswith("$"):
                        continue
                    # Expand ~ if present
                    expanded = Path(os.path.expanduser(segment))
                    if expanded.is_dir():
                        extra_paths.append(expanded)
        except Exception:
            continue

    return extra_paths


def _search_shell_profiles(
    probe: EngineProbe,
) -> Optional[EngineDiscoveryResult]:
    """Tier 7: Search PATH entries from shell profiles."""
    if not probe.binary_names:
        return None

    extra_paths = _extract_paths_from_shell_profiles()
    for dir_path in extra_paths:
        for binary_name in probe.binary_names:
            candidate = dir_path / binary_name
            if candidate.is_file():
                return EngineDiscoveryResult(
                    engine_name=probe.engine_name,
                    available=True,
                    executable_path=candidate,
                    source="shell_profile",
                )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_engine(
    engine_name: str,
    project_root: Optional[Path] = None,
    *,
    use_cache: bool = True,
    require_current_python: bool = False,
) -> EngineDiscoveryResult:
    """Discover whether an engine is available on this system.

    This is the **single SSOT function** for engine availability.
    Both the runner (preflight) and tests (skip logic) call this.

    Search order:
        1. Bundled (.qmatsuite/engines/)
        2. Python import via subprocess (Python-native engines)
        3. Conda environments
        4. Environment variables
        5. System PATH
        6. Homebrew (macOS)
        7. Shell profile PATH entries

    Args:
        engine_name: Engine identifier (e.g. "qe", "cp2k", "psi4").
        project_root: Optional project root for bundled engine search.
        use_cache: If True, return cached result if available.
        require_current_python: If True and the engine is Python-native
            (has ``python_module``), only report available if importable
            from the *current* Python interpreter. This is needed for
            tests that directly ``import <module>`` rather than using
            subprocess execution. Conda/external Python checks are
            skipped in this mode.

    Returns:
        EngineDiscoveryResult with availability status.
    """
    # Auto-detect project root if not provided
    if project_root is None:
        project_root = _find_repo_root()

    cache_key = f"{engine_name}:{project_root or ''}:rcp={require_current_python}"
    if use_cache and cache_key in _discovery_cache:
        return _discovery_cache[cache_key]

    probe = _ENGINE_PROBES.get(engine_name)
    if probe is None:
        result = EngineDiscoveryResult(
            engine_name=engine_name,
            available=False,
            reason=f"Unknown engine '{engine_name}'. "
            f"Known engines: {', '.join(sorted(_ENGINE_PROBES))}",
        )
        _discovery_cache[cache_key] = result
        return result

    # Build search tiers based on mode
    if require_current_python and probe.python_module:
        # Only check current Python — skip conda and other external tiers
        search_tiers = [
            ("python_import", lambda: _search_python_import(probe)),
        ]
    else:
        # Full search — all tiers
        search_tiers = [
            ("bundled", lambda: _search_bundled(probe, project_root)),
            ("python_import", lambda: _search_python_import(probe)),
            ("conda", lambda: _search_conda(probe)),
            ("env_var", lambda: _search_env_var(probe)),
            ("path", lambda: _search_system_path(probe)),
            ("homebrew", lambda: _search_homebrew(probe)),
            ("shell_profile", lambda: _search_shell_profiles(probe)),
        ]

    for tier_name, search_fn in search_tiers:
        try:
            found = search_fn()
            if found is not None:
                logger.debug(
                    "Engine '%s' found via %s: %s",
                    engine_name,
                    tier_name,
                    found.executable_path or found.version,
                )
                _discovery_cache[cache_key] = found
                return found
        except Exception as exc:
            logger.debug(
                "Engine '%s' search tier '%s' failed: %s",
                engine_name,
                tier_name,
                exc,
            )

    # Not found in any tier
    checked = []
    if probe.binary_names:
        checked.append(f"binaries: {', '.join(probe.binary_names)}")
    if probe.python_module:
        checked.append(f"Python module: {probe.python_module}")
    if probe.env_vars:
        checked.append(f"env vars: {', '.join(probe.env_vars)}")
    if probe.brew_name:
        checked.append(f"Homebrew: {probe.brew_name}")
    if probe.conda_package:
        checked.append(f"Conda: {probe.conda_package}")

    result = EngineDiscoveryResult(
        engine_name=engine_name,
        available=False,
        reason=f"Engine '{engine_name}' not found. Checked: {'; '.join(checked)}",
    )
    _discovery_cache[cache_key] = result
    return result


def is_engine_available(
    engine_name: str,
    project_root: Optional[Path] = None,
    *,
    require_current_python: bool = False,
) -> bool:
    """Check if an engine is available on this system.

    Convenience wrapper around :func:`discover_engine`.
    This is the function tests should use for skip logic.

    Args:
        engine_name: Engine identifier.
        project_root: Optional project root.
        require_current_python: If True and engine is Python-native,
            only return True if importable from current interpreter.
            Use this when test code does ``import <module>`` directly.
    """
    return discover_engine(
        engine_name,
        project_root,
        require_current_python=require_current_python,
    ).available


def discover_all_engines(
    project_root: Optional[Path] = None,
) -> Dict[str, EngineDiscoveryResult]:
    """Discover all registered engines.

    Returns:
        Dict mapping engine_name to EngineDiscoveryResult.
    """
    return {
        name: discover_engine(name, project_root)
        for name in _ENGINE_PROBES
    }


def clear_discovery_cache() -> None:
    """Clear the discovery cache. Useful in tests."""
    _discovery_cache.clear()


def get_registered_engine_names() -> List[str]:
    """Return sorted list of all engine names with probes defined."""
    return sorted(_ENGINE_PROBES)
