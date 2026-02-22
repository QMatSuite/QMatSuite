# Cross-Platform Distribution & Engine Management Design

**Status**: Design Document (not yet implemented)
**Date**: 2026-02-21
**Author**: Distribution architecture for QMatSuite v2

---

## Table of Contents

1. [Distribution Channels](#1-distribution-channels) (incl. §1.5 Size Estimates, §1.6 Per-Platform Install)
2. [Cross-Platform File Layout](#2-cross-platform-file-layout)
3. [Engine Management](#3-engine-management)
4. [Python Backend Packaging](#4-python-backend-packaging-for-full-release) (Micromamba — final decision)
5. [Current State vs Design — Gap Analysis](#5-current-state-vs-design--gap-analysis)
6. [Roadmap](#6-roadmap)
7. [Code Signing Strategy](#7-code-signing-strategy)

---

## 1. Distribution Channels

Three distribution channels serve different user profiles:

| Channel | Target User | Contents | Platform |
|---------|------------|----------|----------|
| `pip install quantumvitas` | Jupyter / API / Agent users | Python backend only | All (Mac, Win, Linux) |
| GitHub Release: **qmatsuite-lite** | Users who want selective engine install | Electron app + Python backend + micromamba engine manager | Mac, Windows |
| GitHub Release: **qmatsuite-full** | Zero-friction QE users | lite + QE binary (OpenMP) + SSSP libraries | Mac, Windows |

### 1.1 `pip install quantumvitas`

**What's included:**
- `quantumvitas` Python package (CLI `qv`, daemon, MCP server, all 15 engine drivers)
- All Python dependencies (pymatgen, numpy, scipy, etc.)
- Bundled demo pseudopotentials in `resources/pseudo/`
- No GUI, no Electron, no bundled engines

**Installation:**
```bash
pip install quantumvitas           # Core
pip install quantumvitas[mcp]      # + MCP server (fastmcp)
pip install quantumvitas[all]      # + Materials Project API + MCP
```

**First-launch experience:**
1. User activates their conda/venv environment
2. `qv init project myproject` creates a project directory
3. `qv run calculation` uses engines from system PATH or `.qmatsuite/engines/`
4. MCP: `python -m quantumvitas.mcp.server` starts the MCP server for AI agent integration

**Platform support:**
- macOS (Intel + Apple Silicon): Full support
- Linux (x86_64): Full support — primary path for HPC users
- Windows: Full support via pip in a conda environment

**Current state:** `pyproject.toml` exists with `qv` entry point. Package installs from source with `pip install -e '.[dev,mcp]'`. Not yet published to PyPI.

### 1.2 GitHub Release: qmatsuite-lite

**What is lite?** The core product. Lite is for:
- Users who see a 400MB+ full download and prefer a smaller initial install
- Users who don't need QE (they use ORCA, VASP, Gaussian, etc.) and don't want QE binary + SSSP they'll never use
- Users who want to install engines selectively via the built-in package manager

Lite = Electron app + Python backend + micromamba binary. Full = lite + QE + SSSP.

**What's included:**
- Electron desktop application (React + Three.js GUI)
- Embedded Python environment (via micromamba, see §4)
- `quantumvitas` package pre-installed in the embedded Python
- Micromamba binary for one-click engine installation
- No engines pre-installed (user installs via built-in engine manager or configures their own)

**Installation:**
- **macOS**: Download `.dmg`, drag QMatSuite to Applications, launch
- **Windows**: Download `.exe` NSIS installer, install, launch from Start Menu

**First-launch experience:**
1. User launches QMatSuite
2. Welcome screen: "No engines detected. Install Quantum ESPRESSO?" (or skip to configure own engines)
3. User clicks "Install QE" → micromamba downloads QE (~200MB conda package) → registered in engine manager
4. Or: user configures path to existing VASP / ORCA / Gaussian installation
5. User creates project, imports structure (CIF drag-and-drop), configures calculation via GUI
6. Runs calculation using installed or configured engine

**Platform support:**
- macOS (Apple Silicon primary, Intel via Rosetta 2): `.dmg` release
- Windows (x64): NSIS installer
- Linux: AppImage (lower priority — most Linux users prefer `pip install`)

### 1.3 GitHub Release: qmatsuite-full

**What's included:**
- Everything in qmatsuite-lite
- Pre-bundled QE 7.5 binary — **OpenMP-only variant** (no MPI, smaller, zero-friction)
- SSSP pseudopotential library (efficiency variant, v1.3.0, ~80MB)

**Installation:**
- **macOS**: Download `.pkg` installer (~290MB), run, launch
- **Windows**: Download `.exe` NSIS installer (~290MB), install, launch

**First-launch experience (the "5-minute Si band structure" goal):**
1. User launches QMatSuite
2. Welcome screen shows "QE 7.5 ready" + "SSSP installed"
3. User clicks "New Project" → "Demo: Silicon Band Structure"
4. Demo loads with pre-configured Si structure, SCF + bands workflow, SSSP pseudopotentials
5. User clicks "Run" → QE runs → band structure plot appears
6. Total time: download (5 min on broadband) + 3 clicks + ~30 seconds of QE compute

**Platform support:**
- macOS (Apple Silicon native): `.pkg` installer with arm64 QE binary
- macOS (Intel): `.pkg` installer with x86_64 QE binary (or universal binary)
- Windows (x64): NSIS installer with QE from GitHub Releases

### 1.4 QE Binary — Dual Variant Strategy

For both Mac and Windows, two QE binary variants are provided as separate GitHub Release assets:

| Variant | Spec (Windows) | Spec (macOS arm64) | Notes |
|---------|---------------|-------------------|-------|
| **OpenMP-only** (default) | Intel oneAPI + MKL + OpenMP + HDF5 | GCC + Accelerate + OpenMP + HDF5 | No MPI, no network popup on Windows. Bundled in full release. |
| **MPI-enabled** | Intel oneAPI + MKL + MS-MPI + HDF5 | GCC + Accelerate + OpenMPI + HDF5 | For parallel scaling. Download via engine manager. |

Both variants include `pw2qmcpack` for QE→QMCPACK workflows.

**Default active**: OpenMP-only. Users can download and switch to MPI via engine manager. The MPI variant is a second GitHub Release asset, not bundled in the default installer.

**QE binary source:**
- Both variants compiled by [QMatSuite/qmatsuite-toolchain](https://github.com/QMatSuite/qmatsuite-toolchain) CI
- Windows OpenMP: Intel oneAPI + MKL (no MS-MPI dependency)
- Windows MPI: Intel oneAPI + MKL + MS-MPI, Microsoft Trusted-Signed
- macOS OpenMP: GCC + Accelerate (no OpenMPI dependency)
- macOS MPI: GCC + Accelerate + OpenMPI
- All releases: SHA256 checksums + GitHub Artifact Attestation
- Windows existing release: [QMatSuite/quantum-espresso-windows-exe](https://github.com/QMatSuite/quantum-espresso-windows-exe) (QE 7.5, MPI variant, ~400MB zip)

### 1.5 Download vs Installed Size

Download size is what users see first. All estimates use LZMA2 / zstd compression.

| Component | Installed Size | Compressed Size | Notes |
|-----------|---------------|----------------|-------|
| Electron shell (Chromium + asar) | ~200 MB | ~70 MB | Standard Electron overhead |
| micromamba binary | ~5 MB | ~5 MB | Already statically linked |
| Python 3.12 interpreter | ~40 MB | ~15 MB | In conda env tarball |
| quantumvitas + all deps | 348 MB | ~100 MB | Scientific Python stack compresses well |
| QE 7.5 OpenMP binary | ~150 MB | ~50 MB | Single-variant, no MPI |
| SSSP efficiency v1.3.0 | ~80 MB | ~30 MB | UPF pseudopotentials |

| Channel | Download Size | Installed Size |
|---------|--------------|---------------|
| **pip install quantumvitas** | ~45 MB (wheel) | ~348 MB |
| **qmatsuite-lite** | **~190 MB** | ~590 MB |
| **qmatsuite-full** | **~290 MB** | ~820 MB |

The full release at ~290 MB is comparable to VS Code (~100 MB download) + a moderate extension set, or MATLAB (~300 MB initial download).

### 1.6 Per-Platform Installation Behavior

#### 1.6.1 Windows (NSIS Installer)

**Both lite and full** use NSIS (Nullsoft Scriptable Install System).

**Install path**: `%LOCALAPPDATA%\QMatSuite\` — per-user, no UAC prompt. Follows the VS Code / Discord / Slack convention of per-user install to LocalAppData.

**Directory layout after install:**
```
%LOCALAPPDATA%\QMatSuite\
├── app\                           # Electron app files
│   ├── QMatSuite.exe              # Main executable
│   ├── resources\app.asar         # Electron app bundle
│   └── ...                        # Chromium DLLs, etc.
├── runtime\                       # Pre-created conda env (compressed tarball expanded at install)
│   ├── python.exe
│   ├── Lib\site-packages\
│   │   ├── quantumvitas\
│   │   ├── numpy\
│   │   └── ...
│   └── Scripts\
├── micromamba\                    # Engine manager
│   ├── micromamba.exe
│   ├── envs\                     # Engine environments
│   └── pkgs\                     # Package cache
├── engines\                      # (full only) Pre-bundled engines
│   └── qe\bundled-7.5\bin\
│       └── pw.exe
├── libraries\                    # (full only) Pseudopotentials
│   └── pseudo\SSSP\
├── config\
│   ├── settings.json
│   └── engines.json
└── logs\
```

**Install flow:**
1. User downloads `QMatSuite-Setup-x.y.z.exe` (~190 MB lite, ~290 MB full)
2. NSIS installer runs — no UAC prompt (per-user install)
3. Extracts Electron app to `%LOCALAPPDATA%\QMatSuite\app\`
4. Expands pre-created conda env tarball to `runtime\`
5. (full only) Extracts QE binary to `engines\qe\bundled-7.5\`
6. (full only) Extracts SSSP to `libraries\pseudo\SSSP\`
7. Creates Start Menu shortcut
8. On first launch: Electron finds `runtime\python.exe`, starts daemon

**Uninstall**: NSIS uninstaller in Add/Remove Programs. Removes `app\` and `runtime\`. Preserves `engines\`, `libraries\`, `config\` (user data). Option to remove everything.

#### 1.6.2 macOS Lite (DMG)

**Install path**: `/Applications/QMatSuite.app` (drag to Applications). User data at `~/Library/Application Support/QMatSuite/`.

**DMG contents:**
```
QMatSuite.dmg (~190 MB)
└── QMatSuite.app
    └── Contents/
        ├── MacOS/QMatSuite        # Electron main binary
        ├── Resources/
        │   ├── app.asar           # Electron app bundle
        │   └── runtime.tar.zst    # Compressed conda env (~115 MB)
        ├── Frameworks/            # Chromium frameworks
        └── Info.plist
```

**First-launch flow:**
1. User drags QMatSuite.app to Applications
2. On first launch, Electron detects no expanded runtime
3. Shows "Setting up QMatSuite..." with progress bar
4. Expands `runtime.tar.zst` to `~/Library/Application Support/QMatSuite/runtime/` (~30 seconds)
5. Verifies: `runtime/bin/python -c "import quantumvitas"`
6. Starts daemon from the expanded runtime

**Post-setup directory layout:**
```
~/Library/Application Support/QMatSuite/
├── runtime/                       # Expanded from app bundle
│   ├── bin/python3.12
│   └── lib/python3.12/site-packages/...
├── micromamba/
│   ├── bin/micromamba
│   └── envs/
├── engines/
├── libraries/
├── config/
│   ├── settings.json
│   └── engines.json
└── logs/
```

**Why DMG for lite**: Drag-to-install is the standard macOS experience for self-contained apps. The compressed conda env tarball inside the `.app` bundle keeps the drag-to-install experience clean.

#### 1.6.3 macOS Full (.pkg Installer)

**Install path**: Same as lite — `/Applications/QMatSuite.app` + `~/Library/Application Support/QMatSuite/`. The .pkg installer handles installing to multiple locations atomically.

**Why .pkg for full (not DMG)**: The full release needs to install files to multiple locations:
- The app bundle → `/Applications/QMatSuite.app`
- The expanded runtime → `~/Library/Application Support/QMatSuite/runtime/`
- QE binary → `~/Library/Application Support/QMatSuite/engines/qe/bundled-7.5/`
- SSSP → `~/Library/Application Support/QMatSuite/libraries/pseudo/SSSP/`

A DMG can only drag one `.app` to Applications. A `.pkg` installer can atomically install to all locations, provide progress feedback, and handle the conda env expansion during install (not first launch).

**Install flow:**
1. User downloads `QMatSuite-Full-x.y.z.pkg` (~290 MB)
2. macOS Installer.app runs (Gatekeeper checks Developer ID signature)
3. Installs QMatSuite.app to `/Applications/`
4. Expands runtime env to `~/Library/Application Support/QMatSuite/runtime/`
5. Installs QE to `~/Library/Application Support/QMatSuite/engines/qe/bundled-7.5/`
6. Installs SSSP to `~/Library/Application Support/QMatSuite/libraries/pseudo/SSSP/`
7. Registers in engines.json
8. On launch: Electron finds `runtime/bin/python`, starts daemon — QE ready immediately

**Key advantage over DMG for full**: No first-launch setup delay. Everything is ready on first launch ("5-minute Si band structure" goal).

#### 1.6.4 Linux

**Primary path**: `pip install quantumvitas` — Linux users typically have Python and conda/pip experience. No Electron distribution planned initially.

**AppImage** (deferred, lower priority): Self-contained single-file distribution. Would bundle Electron + Python runtime. ~200 MB. Deferred because most Linux HPC users prefer pip + their own Python environment.

---

## 2. Cross-Platform File Layout

### 2.1 Current State

All paths are anchored to the repository root via `src/quantumvitas/core/paths.py`:

```
<REPO_ROOT>/
├── .qmatsuite/                    # Persistent assets (gitignored)
│   ├── config/settings.json       # User settings
│   ├── engines/qe/<version>/bin/  # QE binaries
│   ├── seeds/pseudo/              # Offline pseudo seeds
│   ├── libraries/pseudo/SSSP/     # Installed SSSP
│   └── logs/                      # Runtime logs
├── .tmp/                          # Scratch space (gitignored)
│   ├── downloads/                 # Download cache
│   ├── unpack/                    # Extraction temp
│   ├── runs/                      # Calculation scratch
│   ├── probe/                     # Engine discovery probes
│   └── locks/                     # Concurrency locks
└── <user-projects>/               # User project directories (anywhere)
```

**Root discovery** (`paths.py:22-52`): Walks up from `__file__` looking for `pyproject.toml` + `src/quantumvitas/`. This only works when running from a git checkout or editable install.

**Problem**: After `pip install quantumvitas`, there is no `pyproject.toml` in the installed package — `get_repo_root()` raises `RuntimeError`. This must be solved for any distribution channel.

### 2.2 Target State

Separate three concerns:

| Concern | Contents | Persistence | Updated by |
|---------|----------|-------------|-----------|
| **App data** | Engines, pseudopotentials, micromamba, config | Persists across app updates | Engine manager, pseudo downloader |
| **Cache** | Downloads, extraction temp, build artifacts, locks | Deletable anytime | System temp cleanup |
| **User data** | Projects | User manages | User |

**Platform-specific locations:**

| Platform | App Data | Cache | User Data |
|----------|----------|-------|-----------|
| macOS (pip) | `~/.qmatsuite/` | System temp or `~/.qmatsuite/.tmp/` | User-chosen |
| macOS (Electron) | `~/Library/Application Support/QMatSuite/` | `~/Library/Caches/QMatSuite/` | User-chosen |
| Windows (pip) | `%USERPROFILE%\.qmatsuite\` | System temp | User-chosen |
| Windows (Electron) | `%LOCALAPPDATA%\QMatSuite\` | `%LOCALAPPDATA%\QMatSuite\cache\` | User-chosen |
| Linux (pip) | `~/.qmatsuite/` or `$XDG_DATA_HOME/qmatsuite/` | System temp | User-chosen |
| Dev (repo checkout) | `<REPO_ROOT>/.qmatsuite/` | `<REPO_ROOT>/.tmp/` | Anywhere |

### 2.3 Path Resolution Design

Replace the current `get_repo_root()`-based approach with an environment-aware resolution chain:

```python
# src/quantumvitas/core/paths.py — proposed design

import os
import sys
from pathlib import Path

def get_app_data_dir() -> Path:
    """
    Resolve the QMatSuite app data directory.

    Resolution order:
    1. QMATSUITE_HOME environment variable (explicit override)
    2. Dev mode: <repo_root>/.qmatsuite/ (if pyproject.toml + src/quantumvitas/ found)
    3. Electron mode: platform-appropriate Application Support / LOCALAPPDATA
    4. pip mode: ~/.qmatsuite/
    """
    # 1. Explicit override
    env_home = os.environ.get("QMATSUITE_HOME")
    if env_home:
        p = Path(env_home)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 2. Dev mode — walk up looking for repo markers
    repo_root = _try_find_repo_root()
    if repo_root is not None:
        p = repo_root / ".qmatsuite"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 3. Electron mode — check if running inside Electron bundle
    if _is_electron_bundle():
        return _electron_app_data_dir()

    # 4. pip mode — user home
    p = Path.home() / ".qmatsuite"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cache_dir() -> Path:
    """
    Resolve the QMatSuite cache directory (deletable anytime).

    Resolution order:
    1. QMATSUITE_CACHE environment variable
    2. Dev mode: <repo_root>/.tmp/
    3. Electron mode: platform cache directory
    4. pip mode: <app_data_dir>/.tmp/
    """
    env_cache = os.environ.get("QMATSUITE_CACHE")
    if env_cache:
        p = Path(env_cache)
        p.mkdir(parents=True, exist_ok=True)
        return p

    repo_root = _try_find_repo_root()
    if repo_root is not None:
        p = repo_root / ".tmp"
        p.mkdir(parents=True, exist_ok=True)
        return p

    if _is_electron_bundle():
        return _electron_cache_dir()

    p = get_app_data_dir() / ".tmp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_config_file() -> Path:
    """Get path to settings.json."""
    return get_app_data_dir() / "config" / "settings.json"


def _try_find_repo_root() -> Path | None:
    """Walk up from __file__ looking for pyproject.toml + src/quantumvitas/."""
    current = Path(__file__).parent
    for _ in range(10):  # Max 10 levels
        if (current / "pyproject.toml").exists() and (current / "src" / "quantumvitas").exists():
            return current.resolve()
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _is_electron_bundle() -> bool:
    """Check if running inside an Electron-bundled Python environment."""
    return os.environ.get("QMATSUITE_ELECTRON") == "1"


def _electron_app_data_dir() -> Path:
    """Platform-appropriate app data for Electron bundles."""
    if sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "QMatSuite"
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        p = Path(local_app_data) / "QMatSuite"
    else:
        # Linux XDG
        xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        p = Path(xdg) / "qmatsuite"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _electron_cache_dir() -> Path:
    """Platform-appropriate cache for Electron bundles."""
    if sys.platform == "darwin":
        p = Path.home() / "Library" / "Caches" / "QMatSuite"
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        p = Path(local_app_data) / "QMatSuite" / "cache"
    else:
        xdg = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
        p = Path(xdg) / "qmatsuite"
    p.mkdir(parents=True, exist_ok=True)
    return p
```

**App data directory structure** (same across all platforms):

```
<app_data_dir>/
├── config/
│   └── settings.json          # User settings
│   └── engines.json           # Engine registry (see §3)
├── engines/
│   ├── qe/
│   │   ├── bundled-7.5/bin/   # Bundled QE (full release only)
│   │   └── conda-7.5/bin/     # Micromamba-installed QE
│   ├── xtb/
│   │   └── conda-6.7.1/bin/   # Micromamba-installed xTB
│   ├── lammps/
│   │   └── conda-2024.1/bin/  # Micromamba-installed LAMMPS
│   └── vasp/
│       └── user/bin/          # User-provided VASP
├── libraries/
│   └── pseudo/
│       └── SSSP/
│           ├── efficiency/1.3.0/
│           └── precision/1.3.0/
├── seeds/
│   └── pseudo/                # Offline install seeds
├── micromamba/
│   ├── bin/micromamba          # Micromamba binary (~5MB)
│   └── envs/                  # Conda environments
│       ├── qe-7.5/
│       ├── xtb-6.7.1/
│       └── lammps-2024.1/
└── logs/
```

### 2.4 Migration Strategy

**Dev → Production**: The `QMATSUITE_HOME` env var and `_try_find_repo_root()` fallback means existing development workflows continue unchanged. The new path resolution only activates for pip-installed or Electron-bundled deployments.

**Backward compatibility**: The existing path helper functions (`home_engines_dir()`, `home_pseudo_libraries_dir()`, etc.) keep their signatures. Their implementations change from `get_repo_root() / ".qmatsuite" / ...` to `get_app_data_dir() / ...`.

**Key invariant**: App updates (Electron auto-update or `pip install --upgrade`) never touch `<app_data_dir>/engines/`, `<app_data_dir>/libraries/`, or user project directories.

---

## 3. Engine Management

### 3.1 Current State

**QE-only binary discovery** (the most mature engine):

The QE engine has a sophisticated two-state binary resolver (`drivers/qe/engine/qe_resolver.py`):

1. **State 1 (External)**: If `settings.qe.bin_dir` is set → validate and use that path
2. **State 2 (Internal)**: Auto-select from `.qmatsuite/engines/qe/**/bin/` (sort by mtime, pick newest)
3. **Fallback**: `shutil.which("pw.x")` on system PATH (deprecated)
4. **Error**: `RuntimeError` with actionable message

**Other engines**: No managed binary discovery.
- xTB: `subprocess.run(["xtb", ...])` — relies on system PATH. On `FileNotFoundError`, suggests `conda install -c conda-forge xtb`
- VASP: Handler gets engine from `engine_registry.get("vasp")` but binary resolution is similar to QE
- ORCA, Gaussian, etc.: Assume binary on PATH or user-configured path

**list_engines MCP tool**: Always reports `installed: True` for all 15 engines. The `installed_only` parameter is a no-op (deferred item L1).

### 3.2 Target State: Unified Engine Registry

A JSON registry file at `<app_data_dir>/config/engines.json` tracks all engine installations:

```json
{
  "schema_version": 1,
  "engines": {
    "qe": {
      "installations": [
        {
          "id": "bundled-7.5",
          "source": "bundled",
          "version": "7.5",
          "path": "<app_data_dir>/engines/qe/bundled-7.5/bin",
          "required_binaries": ["pw.x", "ph.x", "pp.x", "bands.x", "dos.x", "wannier90.x"],
          "verified": "2026-02-21T12:00:00Z",
          "env_vars": {}
        },
        {
          "id": "conda-7.5",
          "source": "micromamba",
          "version": "7.5",
          "path": "<app_data_dir>/micromamba/envs/qe-7.5/bin",
          "conda_env": "qe-7.5",
          "required_binaries": ["pw.x"],
          "verified": "2026-02-21T12:00:00Z",
          "env_vars": {}
        }
      ],
      "active": "bundled-7.5"
    },
    "vasp": {
      "installations": [
        {
          "id": "user-6.5",
          "source": "user_path",
          "version": "6.5.0",
          "path": "/opt/vasp/6.5.0/bin",
          "required_binaries": ["vasp_std"],
          "verified": "2026-02-20T10:00:00Z",
          "env_vars": {
            "VASP_PP_PATH": "/opt/vasp/potpaw_PBE.64"
          }
        }
      ],
      "active": "user-6.5"
    },
    "xtb": {
      "installations": [
        {
          "id": "conda-6.7.1",
          "source": "micromamba",
          "version": "6.7.1",
          "path": "<app_data_dir>/micromamba/envs/xtb-6.7.1/bin",
          "conda_env": "xtb-6.7.1",
          "required_binaries": ["xtb"],
          "verified": "2026-02-21T14:00:00Z",
          "env_vars": {}
        }
      ],
      "active": "conda-6.7.1"
    },
    "gaussian": {
      "installations": [
        {
          "id": "user-g16",
          "source": "user_path",
          "version": "16",
          "path": "/opt/gaussian/g16",
          "required_binaries": ["g16"],
          "verified": null,
          "env_vars": {
            "g16root": "/opt/gaussian",
            "GAUSS_SCRDIR": "/scratch/gaussian"
          }
        }
      ],
      "active": "user-g16"
    }
  }
}
```

### 3.3 Source Types

| Source | Description | Discovery | Example |
|--------|------------|-----------|---------|
| `bundled` | Shipped with qmatsuite-full release | Check `<app_data_dir>/engines/<engine>/bundled-*/bin/` | QE 7.5 in full release |
| `micromamba` | Installed via built-in conda manager | Check `<app_data_dir>/micromamba/envs/<env>/` | xTB, CP2K, PySCF, Psi4, GPAW |
| `github_release` | Downloaded from QMatSuite GitHub Releases | Check `<app_data_dir>/engines/<engine>/github-*/bin/` | QE OpenMP/MPI variants |
| `system_path` | Found on system PATH via `shutil.which()` | Scan PATH at discovery time | Any engine installed via apt/brew/manual |
| `user_path` | User-specified binary path | User configures in GUI or settings.json | VASP, Gaussian (licensed software) |
| `user_venv` | User-specified Python venv (Python engines only) | User configures path | User's own PySCF/Psi4/GPAW venv |

### 3.4 Engine Metadata

Each engine needs metadata for discovery and verification. Binary names verified from handler/recipe source code.

#### Binary Engine Metadata

```python
# src/quantumvitas/engine/engine_meta.py — proposed

ENGINE_META = {
    # --- Binary engines (subprocess calls to compiled executables) ---
    "qe": {
        "display_name": "Quantum ESPRESSO",
        "engine_type": "binary",
        "required_binaries": ["pw.x"],
        "optional_binaries": ["ph.x", "pp.x", "bands.x", "dos.x", "projwfc.x",
                              "wannier90.x", "pw2wannier90.x", "pw2qmcpack.x"],
        "version_command": ["pw.x", "--version"],
        "version_regex": r"v\.(\d+\.\d+)",
        "conda_package": "qe",
        "conda_channel": "conda-forge",
        "github_release": "QMatSuite/qmatsuite-toolchain",  # For pre-built binaries
        "env_vars": {},
        "bundleable": True,  # Shipped with qmatsuite-full
    },
    "vasp": {
        "display_name": "VASP",
        "engine_type": "binary",
        "required_binaries": ["vasp_std"],
        "optional_binaries": ["vasp_gam", "vasp_ncl"],
        "version_command": None,  # VASP doesn't have --version
        "conda_package": None,    # Licensed, not on conda
        "env_vars": {"VASP_PP_PATH": "Path to POTCAR library"},
        "bundleable": False,
    },
    "xtb": {
        "display_name": "xTB",
        "engine_type": "binary",
        "required_binaries": ["xtb"],
        "version_command": ["xtb", "--version"],
        "version_regex": r"xtb version (\S+)",
        "conda_package": "xtb",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
    },
    "lammps": {
        "display_name": "LAMMPS",
        "engine_type": "binary",
        "required_binaries": ["lmp"],
        "version_command": ["lmp", "-h"],
        "version_regex": r"LAMMPS \((\d+ \w+ \d+)\)",
        "conda_package": "lammps",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
    },
    "orca": {
        "display_name": "ORCA",
        "engine_type": "binary",
        "required_binaries": ["orca"],
        "version_command": None,  # ORCA doesn't support --version standalone
        "conda_package": None,    # Licensed, free for academics but manual download
        "env_vars": {},
        "bundleable": False,
    },
    "gaussian": {
        "display_name": "Gaussian",
        "engine_type": "binary",
        "required_binaries": ["g16"],
        "optional_binaries": ["g09"],
        "version_command": None,  # Licensed
        "conda_package": None,
        "env_vars": {"g16root": "Gaussian root directory", "GAUSS_SCRDIR": "Scratch directory"},
        "bundleable": False,
    },
    "abinit": {
        "display_name": "ABINIT",
        "engine_type": "binary",
        "required_binaries": ["abinit"],
        "version_command": ["abinit", "--version"],
        "version_regex": r"(\d+\.\d+\.\d+)",
        "conda_package": "abinit",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
    },
    "cp2k": {
        "display_name": "CP2K",
        "engine_type": "binary",
        "required_binaries": ["cp2k.ssmp"],
        "optional_binaries": ["cp2k.popt", "cp2k.psmp"],
        "version_command": ["cp2k.ssmp", "--version"],
        "version_regex": r"CP2K version (\S+)",
        "conda_package": "cp2k",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
    },
    "siesta": {
        "display_name": "Siesta",
        "engine_type": "binary",
        "required_binaries": ["siesta"],
        "version_command": ["siesta", "--version"],
        "conda_package": "siesta",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
    },
    "w90": {
        "display_name": "Wannier90",
        "engine_type": "binary",
        "required_binaries": ["wannier90.x"],
        "version_command": None,  # Parse header from wannier90.x output
        "conda_package": None,    # Bundled with QE conda package
        "env_vars": {},
        "bundleable": False,      # Comes with QE
    },
    "yambo": {
        "display_name": "Yambo",
        "engine_type": "binary",
        "required_binaries": ["yambo"],
        "optional_binaries": ["p2y"],
        "version_command": ["yambo", "-h"],
        "conda_package": None,    # Niche, user provides
        "env_vars": {},
        "bundleable": False,
    },
    "qmcpack": {
        "display_name": "QMCPACK",
        "engine_type": "binary",
        "required_binaries": ["qmcpack"],
        "version_command": None,
        "conda_package": "qmcpack",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
    },
    # --- Python engines (subprocess calls to Python interpreter) ---
    "pyscf": {
        "display_name": "PySCF",
        "engine_type": "python",
        "required_binaries": [],   # No binary — Python package
        "python_import": "pyscf",  # Module to test availability
        "version_command": "import pyscf; print(pyscf.__version__)",
        "conda_package": "pyscf",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
    },
    "psi4": {
        "display_name": "Psi4",
        "engine_type": "python",
        "required_binaries": [],
        "python_import": "psi4",
        "version_command": "import psi4; print(psi4.__version__)",
        "conda_package": "psi4",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
    },
    "gpaw": {
        "display_name": "GPAW",
        "engine_type": "python",
        "required_binaries": [],
        "python_import": "gpaw",
        "version_command": "import gpaw; print(gpaw.__version__)",
        "conda_package": "gpaw",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
    },
}
```

#### Engine Detection Table

Verified from handler/recipe source code — these are the exact names used in subprocess calls:

| Engine | Primary Exe (Unix) | Primary Exe (Windows) | Version Check | Source File |
|--------|-------------------|----------------------|---------------|------------|
| qe | `pw.x` | `pw.exe` | `pw.x --version` | `drivers/qe/engine/qe_engine.py:30` |
| vasp | `vasp_std` | `vasp_std.exe` | N/A | `drivers/vasp/recipe.py:73` |
| xtb | `xtb` | `xtb.exe` | `xtb --version` | `drivers/xtb/handler.py:109` |
| lammps | `lmp` | `lmp.exe` | `lmp -h` (parse header) | `drivers/lammps/recipe.py:74` |
| orca | `orca` | `orca.exe` | N/A | `drivers/orca/recipe.py:121` |
| gaussian | `g16` (or `g09`) | `g16.exe` | N/A | `drivers/gaussian/handler.py:37` |
| abinit | `abinit` | `abinit.exe` | `abinit --version` | `drivers/abinit/handler.py:38` |
| cp2k | `cp2k.ssmp` | `cp2k.ssmp.exe` | `cp2k.ssmp --version` | `drivers/cp2k/recipe.py:90` |
| siesta | `siesta` | `siesta.exe` | `siesta --version` | `drivers/siesta/handler.py:39` |
| w90 | `wannier90.x` | `wannier90.x.exe` | N/A (parse header) | `drivers/w90/recipe.py:51` |
| yambo | `yambo` | `yambo.exe` | `yambo -h` | `drivers/yambo/handler.py:38` |
| qmcpack | `qmcpack` | `qmcpack.exe` | N/A | `drivers/qmcpack/recipe.py:70` |
| pyscf | `python -c "import pyscf"` | (in micromamba env) | `python -c "print(pyscf.__version__)"` | `engine/pyscf_engine.py:100` |
| psi4 | `python -c "import psi4"` | (in micromamba env) | `python -c "print(psi4.__version__)"` | `engine/psi4_engine.py:83` |
| gpaw | `python -c "import gpaw"` | (in micromamba env) | `python -c "print(gpaw.__version__)"` | `drivers/gpaw/handler.py:126` |

Detection logic:
1. Check `engines.json` active path first
2. If no registry entry, fall back to `shutil.which()` on the primary exe (binary engines)
3. For Python engines: check if the registered micromamba env or user venv exists and the import succeeds

### 3.5 Discovery Flow

When the engine manager runs discovery (on app launch or user request):

```
1. Load existing engines.json (if present)
2. Scan bundled:
   - Check <app_data_dir>/engines/<engine>/bundled-*/bin/ for each engine
   - Verify required binaries exist
3. Scan micromamba environments:
   - List <app_data_dir>/micromamba/envs/*/
   - For each env, check if any engine binaries are present
   - Match against ENGINE_META required_binaries
4. Scan system PATH:
   - For each engine, shutil.which(required_binary)
   - If found, resolve symlinks, determine bin directory
5. Merge with existing registry:
   - Keep all user_path entries (never overwrite)
   - Add newly discovered bundled/micromamba/system_path entries
   - Remove entries whose paths no longer exist (mark as stale)
6. Version check each installation:
   - Run version_command if available
   - Parse version from output using version_regex
   - Update verified timestamp
7. Write updated engines.json
```

### 3.6 Micromamba Integration

**What**: QMatSuite ships with or auto-downloads [micromamba](https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html) (~5MB statically-linked binary) for one-click engine installation.

**Why micromamba** (not conda/mamba):
- Single static binary, no Python dependency
- No base environment overhead
- Fast solver (libmamba)
- Supports conda-forge channel (where QE, xTB, LAMMPS, CP2K, ABINIT, Siesta all have packages)

**Micromamba layout:**
```
<app_data_dir>/micromamba/
├── bin/
│   └── micromamba              # The binary itself (~5MB)
├── envs/
│   ├── qe-7.5/                # One env per engine version
│   │   ├── bin/pw.x
│   │   └── ...
│   ├── xtb-6.7.1/
│   │   ├── bin/xtb
│   │   └── ...
│   └── lammps-2024.1/
│       ├── bin/lmp
│       └── ...
└── pkgs/                       # Package cache (shared across envs)
```

**Installation flow** (user clicks "Install xTB" in GUI):
```
1. If micromamba binary not present:
   - Download from GitHub releases (~5MB)
   - Verify SHA256
   - Place in <app_data_dir>/micromamba/bin/
   - chmod +x (Unix)

2. Create environment:
   micromamba create -n xtb-6.7.1 \
     -c conda-forge \
     -r <app_data_dir>/micromamba \
     xtb=6.7.1 \
     --yes

3. Verify:
   <app_data_dir>/micromamba/envs/xtb-6.7.1/bin/xtb --version

4. Register in engines.json:
   {
     "id": "conda-6.7.1",
     "source": "micromamba",
     "version": "6.7.1",
     "path": "<app_data_dir>/micromamba/envs/xtb-6.7.1/bin",
     "conda_env": "xtb-6.7.1",
     "verified": "<now>"
   }
```

**Conda-installable binary engines** (from conda-forge):
| Engine | Package | Typical Size | Notes |
|--------|---------|-------------|-------|
| QE | `qe` | ~200MB | Full suite including pw.x, ph.x, etc. |
| xTB | `xtb` | ~30MB | Lightweight, fast install |
| LAMMPS | `lammps` | ~100MB | Many potentials included |
| CP2K | `cp2k` | ~300MB | Large, many dependencies |
| ABINIT | `abinit` | ~200MB | Full suite |
| Siesta | `siesta` | ~100MB | |
| Wannier90 | Part of QE | — | Bundled with QE conda package |
| QMCPACK | `qmcpack` | ~150MB | |

**Conda-installable Python engines** (each in own micromamba env):
| Engine | Package | Typical Size | Notes |
|--------|---------|-------------|-------|
| PySCF | `pyscf` | ~100MB | Molecular quantum chemistry |
| Psi4 | `psi4` | ~200MB | Molecular quantum chemistry |
| GPAW | `gpaw` | ~150MB | DFT with PAW / real-space grids |

Python engines are NOT dependencies of the main `quantumvitas` package. They each get their own micromamba environment (see §3.8 for details). Users can also point to an existing venv that has the package installed.

**Non-conda engines** (user must provide):
| Engine | Why | How to configure |
|--------|-----|-----------------|
| VASP | Licensed, not redistributable | User provides path in settings |
| ORCA | Free for academics, but manual download required | User provides path |
| Gaussian | Licensed commercial software | User provides path + g16root |
| Yambo | Niche | User provides path |

**GitHub Release engines** (pre-built binaries from QMatSuite repos):
| Engine | Repo | Variants | Notes |
|--------|------|---------|-------|
| QE | `qmatsuite-toolchain` | OpenMP-only, MPI-enabled | See §1.4 for dual variant strategy |

### 3.7 QE Version Management

QE is the primary bundled engine. Multiple versions can coexist:

```
<app_data_dir>/engines/qe/
├── bundled-7.5/bin/           # Shipped with qmatsuite-full
├── conda-7.5/bin/             # Installed via micromamba
└── conda-7.6/bin/             # User installed newer version
```

**When QMatSuite updates** (Electron auto-update):
1. New version includes `bundled-7.6/` QE binary
2. Old `bundled-7.5/` stays in place
3. User is prompted: "QE 7.6 is available. Switch active QE version?"
4. User can keep 7.5 for reproducibility or switch to 7.6
5. Old version can be deleted via engine manager to reclaim disk space

### 3.8 Python Engine Management (PySCF, Psi4, GPAW)

Python engines are NOT pip dependencies of `quantumvitas`. They are full engines managed by micromamba, each in their own conda environment or user-provided venv. The daemon process never imports them directly — all execution happens via subprocess.

**Architecture** (already implemented, verified from source code):

```
Daemon process (qmatsuite-runtime env)    Runner subprocess (engine env)
+-----------------------------------+     +---------------------------+
| PySCFEngine adapter               |     | engines/pyscf/runner.py   |
|   run_step_with_chain()           | --> |   import pyscf            |
|   - Writes job_chain.json         |     |   Run SCF/MP2/TDDFT       |
|   - subprocess.run(python, ...)   |     |   Write results.json      |
|   - Reads results.json            | <-- |                           |
+-----------------------------------+     +---------------------------+
     sys.executable ≠ engine python
     PYTHONPATH injected for quantumvitas
```

**How subprocess isolation works** (from `engine/psi4_engine.py:131-142`):

```python
def _get_runner_env(self) -> Dict[str, str]:
    """Inject PYTHONPATH so the engine's Python can import quantumvitas."""
    import quantumvitas
    env = os.environ.copy()
    # Add quantumvitas's site-packages to PYTHONPATH
    src_dir = str(Path(quantumvitas.__file__).parent.parent)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}:{existing}" if existing else src_dir
    return env
```

The runner subprocess uses the engine's Python interpreter (which has pyscf/psi4/gpaw) but gets `quantumvitas` via PYTHONPATH injection from the daemon's environment. This works for both dev mode and distribution.

**Three source types for Python engines:**

| Source | Python Executable | When Used |
|--------|------------------|-----------|
| **micromamba** | `<app_data>/micromamba/envs/pyscf-2.7/bin/python` | User installed via engine manager |
| **user_venv** | `/path/to/user/venv/bin/python` | User points to existing venv |
| **dev_fallback** | `sys.executable` | Developer's active venv has the package |

**engines.json registration for Python engines:**

```json
{
  "pyscf": {
    "installations": [
      {
        "id": "conda-2.7",
        "source": "micromamba",
        "version": "2.7.0",
        "python_executable": "<app_data>/micromamba/envs/pyscf-2.7/bin/python",
        "conda_env": "pyscf-2.7",
        "verified": "2026-02-21T12:00:00Z"
      },
      {
        "id": "user-venv",
        "source": "user_venv",
        "version": "2.6.2",
        "python_executable": "/home/user/my-chem-env/bin/python",
        "verified": "2026-02-21T14:00:00Z"
      }
    ],
    "active": "conda-2.7"
  }
}
```

**Dev mode compatibility:**

In dev mode, the developer's active venv typically has PySCF/Psi4 installed alongside quantumvitas. The engine adapters (`pyscf_engine.py`, `psi4_engine.py`) use `discover_engine()` which checks engines.json first, then falls back to `sys.executable`. This means:

1. **No engines.json**: Falls back to `sys.executable` (developer's venv) — existing behavior, no changes needed
2. **With engines.json**: Uses registered Python executable — production behavior
3. **PYTHONPATH injection**: Works in both modes because `quantumvitas.__file__` resolves correctly whether installed via `pip install -e .` (dev) or via pip in micromamba (production)

**Installation flow** (user clicks "Install PySCF" in GUI):

```
1. Ensure micromamba binary is present (see §3.6)
2. Create environment with Python + PySCF:
   micromamba create -n pyscf-2.7 \
     -c conda-forge \
     -r <app_data>/micromamba \
     python=3.12 pyscf=2.7 \
     --yes
3. Verify: <env>/bin/python -c "import pyscf; print(pyscf.__version__)"
4. Register in engines.json with python_executable pointing to env's Python
```

**User venv configuration** (user points to existing venv):

```
1. User provides path: /home/user/my-chem-env/
2. Detect Python: <path>/bin/python (Unix) or <path>/Scripts/python.exe (Windows)
3. Verify: <python> -c "import pyscf; print(pyscf.__version__)"
4. Register in engines.json with source="user_venv"
```

### 3.9 GitHub Release Download Mechanism

The engine manager needs TWO package sources:
1. **micromamba** (conda-forge) — for xTB, LAMMPS, CP2K, ABINIT, Siesta, PySCF, Psi4, GPAW, QMCPACK, and optionally QE
2. **GitHub Releases** — for QE pre-built binaries (OpenMP and MPI variants), signed and checksummed

**GitHub Release download flow:**

```
1. Query GitHub API:
   GET /repos/QMatSuite/qmatsuite-toolchain/releases/latest
   (or quantum-espresso-windows-exe for Windows)

2. Find asset matching platform + variant:
   - macOS arm64 OpenMP: qe-7.5-macos-arm64-openmp.tar.gz
   - macOS arm64 MPI:    qe-7.5-macos-arm64-mpi.tar.gz
   - Windows x64 OpenMP: qe-7.5-win-openmp.zip
   - Windows x64 MPI:    qe-7.5-win-oneapi-msmpi.zip

3. Download to <cache_dir>/downloads/

4. Verify SHA256 checksum (from .sha256 sidecar file in release assets)

5. Extract to <app_data>/engines/qe/github-7.5-openmp/bin/

6. Register in engines.json:
   {
     "id": "github-7.5-openmp",
     "source": "github_release",
     "version": "7.5",
     "path": "<app_data>/engines/qe/github-7.5-openmp/bin",
     "variant": "openmp",
     "release_url": "https://github.com/QMatSuite/.../releases/tag/v7.5",
     "verified": "<now>"
   }
```

This same mechanism extends to any future pre-built binary (Wannier90, QMCPACK, etc.).

**Source type summary** (updated from §3.3):

| Source | Description | Discovery | Example |
|--------|------------|-----------|---------|
| `bundled` | Shipped with qmatsuite-full | Check `<app_data>/engines/<engine>/bundled-*/bin/` | QE 7.5 in full release |
| `micromamba` | Installed via built-in conda manager | Check `<app_data>/micromamba/envs/<env>/` | xTB, CP2K, PySCF |
| `github_release` | Downloaded from QMatSuite GitHub Releases | Check `<app_data>/engines/<engine>/github-*/bin/` | QE OpenMP/MPI variants |
| `system_path` | Found on system PATH | `shutil.which()` at discovery time | Any engine via apt/brew |
| `user_path` | User-specified binary path | User configures in GUI or settings | VASP, Gaussian (licensed) |
| `user_venv` | User-specified Python venv (Python engines only) | User configures path | User's own PySCF venv |

### 3.10 Integration with Existing Code

The unified registry replaces the QE-specific two-state resolver while preserving the contract:

**Current flow** (QE only):
```
qe_resolver.resolve_qe_bin_dir()
  → State 1: settings.qe.bin_dir
  → State 2: find_internal_qe_bin_dir() (scan .qmatsuite/engines/qe/)
  → Error
```

**Target flow** (all engines):
```
engine_registry.get_active_installation(engine_family)
  → Look up engines.json for active installation
  → Return path + env_vars
  → If not found: raise EngineNotInstalledError with actionable message
```

The `qe_resolver.py` two-state model becomes a specialization of the general registry:
- State 1 (external) → `user_path` source type in engines.json
- State 2 (internal) → `bundled` or `micromamba` source type in engines.json

**Verification hook in handlers**: Each engine handler already catches `FileNotFoundError`. The registry adds a pre-flight check before subprocess invocation — verify the registered path still exists and the binary is executable.

---

## 4. Python Backend Packaging for Full Release

### 4.1 The Problem

The Electron app (qmatsuite-lite and qmatsuite-full) bundles a GUI that communicates with a Python daemon over JSON-RPC stdio. Currently, the daemon requires:

1. A Python 3.9+ interpreter
2. The `quantumvitas` package installed with all dependencies

Users of the `pip install` channel already have Python. But Electron GUI users should not need to install Python, pip, or manage virtual environments.

### 4.2 Dependency Audit Results

Full transitive closure: **74 packages, 348 MB installed**.

Investigation of the actual daemon import tree reveals:

**Heavy deps loaded at daemon startup** (due to module-level imports):
| Package | Size | Entry Point | Can Be Lazy? |
|---------|------|-------------|-------------|
| pymatgen | 19.2 MB | `core/structure_fingerprint.py:23`, `io/structure_io.py:16` | YES |
| matplotlib | 25.0 MB | `analysis/structure_viz.py:47` (via `api/utils.py:558`) | YES |
| scipy | 78.5 MB | Transitive via pymatgen | YES (if pymatgen lazy) |
| numpy | 19.9 MB | Ubiquitous direct usage | No |
| pandas | 45.6 MB | Transitive via pymatgen | YES (if pymatgen lazy) |
| plotly | 41.2 MB | Transitive via pymatgen | YES (if pymatgen lazy) |
| sympy | 38.2 MB | Transitive via scipy | YES (if scipy lazy) |

**Minimal startup set** (if heavy deps made lazy — only loaded on first structure operation):
| Package | Size | Notes |
|---------|------|-------|
| numpy | 19.9 MB | Unavoidable, used directly |
| PyYAML | 0.8 MB | SSOT parsing |
| typer | 0.4 MB | CLI |
| fastmcp | 3.2 MB | MCP server |
| quantumvitas | 17.5 MB | Source |
| msgpack, ulid-py, requests, certifi, portalocker | ~1.5 MB | Small deps |
| **Total** | **~43 MB** | vs 348 MB current |

**Dead dependencies** (NOT imported anywhere in `src/quantumvitas/`):
| Package | Size | Status |
|---------|------|--------|
| ase | 11.3 MB | Zero imports. Remove from `pyproject.toml`. |
| beautifulsoup4 | 0.8 MB | Zero imports. Remove from `pyproject.toml`. |

**PySCF optional extra**: Currently in `pyproject.toml` line 38-40 as optional pip dependency. Should be removed — PySCF is a micromamba-managed engine (§3.8), not a pip dependency.

### 4.3 Decision: Embedded Python via Micromamba

**Final decision**: Use micromamba to create a pre-built conda environment (`qmatsuite-runtime`) containing Python 3.12 + all dependencies. The installer ships this environment as a compressed tarball that is expanded at install time (full) or first launch (lite).

**Why micromamba wins:**
- Micromamba is already needed for engine management (xTB, LAMMPS, PySCF, etc.)
- One packaging system, not two — simpler build pipeline, simpler debugging
- Full Python environment: extensible (user can `pip install mp-api` into it)
- Clean update path: `pip install --upgrade quantumvitas` into existing env
- No anti-virus false positives (common with PyInstaller on Windows)
- No bundling complexity — conda packages handle all native dependencies (BLAS, LAPACK, etc.)
- Fast startup (~1s, native CPython)

**Runtime environment layout:**
```
<app_data>/runtime/                    # or micromamba/envs/qmatsuite-runtime/
├── bin/python3.12                     # Python interpreter
├── lib/python3.12/
│   └── site-packages/
│       ├── quantumvitas/              # Our package
│       ├── numpy/
│       ├── pymatgen/
│       └── ...
└── ...
```

**Build pipeline** (CI):
1. Create a clean micromamba environment with pinned deps
2. `pip install quantumvitas[mcp]` into the environment
3. Compress with `tar --zstd` → `runtime.tar.zst` (~115 MB)
4. Ship as part of the installer (NSIS / .pkg / .dmg app bundle)

**Pre-work (Phase 0, no dependencies):** Make pymatgen/matplotlib/scipy imports lazy. This improves daemon startup time from ~1-2s to ~200ms, benefiting all distribution channels including pip.

### 4.4 Future Alternatives (Reference Only)

These alternatives were evaluated and are documented for future reference. They are NOT the active plan.

#### PyInstaller (Feasibility: Medium)

Bundle `quantumvitas.daemon.server` into a single directory. Achieves ~250 MB bundle (vs ~350 MB conda env, both compressed to ~100-115 MB). All heavy deps (numpy, scipy, pymatgen, matplotlib) have well-maintained hooks. Main risks: anti-virus false positives on Windows, tight coupling (every Python update requires rebuild), no extensibility (can't `pip install` into a frozen bundle).

#### Nuitka Compiled Binary (Feasibility: Medium, Future Priority)

Compile Python to C and produce a native executable. If Nuitka matures sufficiently for the scientific Python stack, a compiled `quantumvitas-daemon` binary would be the ideal long-term solution: smallest size, fastest startup, no Python env needed. A priority 3 slot is reserved in `findPythonPath()` for this (see §4.5).

**Nuitka upgrade path** (non-breaking):
1. Build a Nuitka-compiled daemon binary in CI
2. Ship it alongside the conda runtime in the installer
3. `findPythonPath()` priority 3 checks for the compiled binary first
4. If found, use it; if not, fall back to conda runtime (priority 4)
5. Once Nuitka build is stable, remove conda runtime from installer

### 4.5 Electron + Embedded Python Integration

**First launch (qmatsuite-lite):**
1. Electron app starts
2. Detects compressed `runtime.tar.zst` in app bundle (macOS) or install dir (Windows)
3. Shows "Setting up QMatSuite..." with progress bar
4. Expands tarball to `<app_data>/runtime/` (~30 seconds)
5. Verifies: `<runtime>/bin/python -c "import quantumvitas; print(quantumvitas.__version__)"`
6. Starts daemon: `<runtime>/bin/python -m quantumvitas.daemon.server`

**First launch (qmatsuite-full):**
Runtime is already expanded by the installer (NSIS / .pkg). No first-launch delay.
- QE binary ready at `<app_data>/engines/qe/bundled-7.5/bin/`
- SSSP ready at `<app_data>/libraries/pseudo/SSSP/`
- Daemon starts immediately

**Electron `findPythonPath()` resolution chain:**

```typescript
function findPythonPath(): { path: string; found: boolean; source: string } {
  // Priority 1: QV_DAEMON_PYTHON override (explicit user/CI override)
  // Priority 2: .venv/bin/python (dev mode — repo checkout detected)
  // Priority 3: Nuitka compiled binary (future — reserved slot)
  //   Check <app_data>/bin/quantumvitas-daemon[.exe]
  // Priority 4: Micromamba runtime environment (production)
  const appDataDir = getAppDataDir();
  const runtimePython = isWindows
    ? path.join(appDataDir, 'runtime', 'python.exe')
    : path.join(appDataDir, 'runtime', 'bin', 'python');
  if (fs.existsSync(runtimePython)) {
    return { path: runtimePython, found: true, source: 'runtime env' };
  }
  // Priority 5: system python fallback (pip-installed quantumvitas)
}
```

### 4.6 Update Strategy

Three independent update dimensions:

| Dimension | Mechanism | Frequency | Affects |
|-----------|----------|-----------|---------|
| **quantumvitas package** | `pip install --upgrade quantumvitas` in runtime env | Per release | Python code only |
| **Python version** | New runtime tarball in Electron update | Yearly | Runtime env |
| **Electron shell** | `electron-updater` auto-update from GitHub Releases | Per release | GUI only |

**Updating `quantumvitas` package** (most common):
```bash
# Electron triggers this on update check:
<runtime>/bin/pip install --upgrade quantumvitas
# Or: download .whl from GitHub Release, pip install locally
```
This is the lightest update — only the Python package changes. No runtime rebuild, no Electron update needed.

**Updating Python version** (rare):
Ships as part of an Electron update that includes a new `runtime.tar.zst`. The old runtime is replaced. User data (engines, projects, config) is never touched.

**Updating Electron shell** (GUI changes):
Standard `electron-updater` with GitHub Releases. Downloads differential update, restarts app. Runtime env is NOT affected.

**Key invariant**: Updating any one dimension never touches the other two. Engines, pseudopotentials, and user projects are always preserved across all updates.

---

## 5. Current State vs Design — Gap Analysis

| Component | Current State | Target State | Gap |
|-----------|--------------|-------------|-----|
| **Engine discovery** | QE-only two-state resolver (`qe_resolver.py`). Other engines rely on system PATH. | Unified `engines.json` registry with 4 source types (bundled, micromamba, system_path, user_path) for all 15 engines | **Large** — new module, new data model, integration with all engine handlers |
| **Path management** | `paths.py` hardcodes `repo_root/.qmatsuite/` via `get_repo_root()` walk-up. Fails for pip-installed packages. | Platform-aware resolution chain (`QMATSUITE_HOME` → repo_root → Electron → `~/.qmatsuite/`) | **Medium** — refactor `paths.py`, add env var support, add Electron detection |
| **Micromamba** | Not integrated. xTB handler suggests `conda install` in error message but doesn't automate it. | Built-in conda manager: download micromamba, create envs, install engines, GUI integration | **Large** — new module, download + verify logic, GUI components |
| **pip install** | `pyproject.toml` exists with `qv` entry point. Installs from source. Not published to PyPI. `get_repo_root()` fails in installed mode. | Working `pip install quantumvitas` from PyPI. `paths.py` handles installed mode. | **Medium** — fix `paths.py`, add `package_data` for resources, publish to PyPI |
| **Electron packaging** | `electron-builder.json5` exists with placeholder values (`YourAppID`, `YourAppName`). No code signing, no auto-update. Builds `.dmg`/`.exe`/`.AppImage`. | Production Electron builds with proper appId, code signing, auto-update, QMatSuite branding | **Medium** — configuration + CI workflow, no architectural change |
| **Python bundling** | Not done. Electron assumes Python venv at `<project_root>/.venv/`. | Embedded Python via pre-built conda env. Electron finds `<app_data>/runtime/bin/python` | **Large** — first-launch setup flow, micromamba integration, Electron Python resolution |
| **QE binary (Windows)** | CI builds QE 7.5 in [qmatsuite-toolchain](https://github.com/QMatSuite/qmatsuite-toolchain). Releases distributed via [quantum-espresso-windows-exe](https://github.com/QMatSuite/quantum-espresso-windows-exe) (~400MB zip). | Bundled in qmatsuite-full Windows installer at `<app_data>/engines/qe/bundled-7.5/bin/` | **Small** — download + stage in installer; binary already exists |
| **QE binary (macOS)** | CI builds QE 7.5 for macOS in qmatsuite-toolchain (GCC + OpenMPI + FFTW3 + Accelerate). | Bundled in qmatsuite-full macOS `.pkg` at `<app_data>/engines/qe/bundled-7.5/bin/` | **Small** — similar to Windows; binary already built in CI |
| **SSSP bundling** | Downloaded at runtime via `download_pseudo_library` MCP tool / CLI. SSSP manifest in `resources/pseudo_libinfo/`. | Pre-bundled in qmatsuite-full installer. Runtime download for lite/pip. | **Small** — package SSSP files in installer alongside QE binary |
| **Auto-update** | Not implemented. No mechanism for Electron or pip updates. | Electron: `electron-updater` with GitHub Releases. pip: standard PyPI `pip install --upgrade`. | **Medium** — Electron auto-update configuration + release CI |
| **Engine setup GUI** | Not investigated in detail, but Electron GUI exists with full React + Three.js frontend. Daemon provides engine-related RPC commands. | Engine manager panel: show installed engines, install via micromamba, configure user_path, switch active version | **Medium** — new GUI panel, new daemon RPC commands for engine management |

---

## 6. Roadmap

### Phase 1: Foundation (everything else depends on this)

| # | Work Package | Complexity | Depends On |
|---|-------------|-----------|------------|
| 1.1 | Refactor `paths.py` to support `QMATSUITE_HOME` + platform-aware resolution | **M** | — |
| 1.2 | Fix `get_repo_root()` fallback for pip-installed packages (no `pyproject.toml`) | **S** | 1.1 |
| 1.3 | Add `package_data` for all non-`.json` resources (pseudo, demo YAMLs, knowledge .db) to `pyproject.toml` | **S** | — |
| 1.4 | Publish `quantumvitas` to PyPI (test → production) | **S** | 1.2, 1.3 |

### Phase 2: Engine Management (enables lite distribution)

| # | Work Package | Complexity | Depends On |
|---|-------------|-----------|------------|
| 2.1 | Design and implement `engines.json` registry module | **L** | 1.1 |
| 2.2 | Integrate registry with QE resolver (replace two-state with registry lookup) | **M** | 2.1 |
| 2.3 | Integrate registry with all other engine handlers | **M** | 2.1 |
| 2.4 | Implement `list_engines` real `installed` detection via registry | **S** | 2.1 |
| 2.5 | Micromamba download + environment management module | **L** | 1.1 |
| 2.6 | Daemon RPC commands for engine management (list, install, verify, set-active) | **M** | 2.1, 2.5 |
| 2.7 | GUI engine manager panel | **M** | 2.6 |

### Phase 3: Electron Distribution (enables first release)

| # | Work Package | Complexity | Depends On |
|---|-------------|-----------|------------|
| 3.1 | Configure `electron-builder.json5` with production values (appId, product name, icons) | **S** | — |
| 3.2 | First-launch setup flow: expand pre-built runtime tarball + micromamba bootstrap | **L** | 2.5 |
| 3.3 | Electron `findPythonPath()` — add micromamba runtime env lookup | **S** | 3.2 |
| 3.4 | macOS CI build workflow: `.dmg` (lite) + `.pkg` (full) via electron-builder | **M** | 3.1 |
| 3.5 | Windows NSIS installer CI build workflow | **M** | 3.1 |
| 3.6 | QE binary bundling in full-release installer (Mac arm64 + Windows x64) | **M** | 3.4, 3.5 |
| 3.7 | SSSP library bundling in full-release installer | **S** | 3.6 |
| 3.8 | macOS code signing (Developer ID + notarization) | **M** | 3.4 |
| 3.9 | Windows code signing (certificate or Trusted Signing) | **M** | 3.5 |

### Phase 4: Polish (post-launch)

| # | Work Package | Complexity | Depends On |
|---|-------------|-----------|------------|
| 4.1 | Electron auto-update via `electron-updater` + GitHub Releases | **M** | 3.4, 3.5 |
| 4.2 | Linux AppImage build (lower priority) | **S** | 3.1 |
| 4.3 | QE universal binary for macOS (arm64 + x86_64) | **M** | 3.6 |
| 4.4 | Engine update notification in GUI ("xTB 6.8.0 available, update?") | **S** | 2.7 |
| 4.5 | Offline installer variant (pre-pack micromamba envs for air-gapped HPC) | **L** | 2.5, 3.6 |
| 4.6 | Contributing guide for adding new engines to the registry | **S** | 2.1 |

### Phase 0: Pre-work (can be done immediately, no dependencies)

| # | Work Package | Complexity | Depends On |
|---|-------------|-----------|------------|
| 0.1 | Remove dead dependencies: `ase`, `beautifulsoup4` from `pyproject.toml` | **S** | — |
| 0.2 | Remove `pyscf` optional extra from `pyproject.toml` (micromamba-managed) | **S** | — |
| 0.3 | Make pymatgen/matplotlib/scipy imports lazy in `core/structure_fingerprint.py`, `core/structure_canonicalize.py`, `api/utils.py:558`, `analysis/structure_viz.py` | **M** | — |
| 0.4 | Add QE OpenMP-only CI workflow to qmatsuite-toolchain (no MPI variant) | **M** | — |

### Complexity Legend

| Size | Estimated Scope |
|------|----------------|
| **S** | < 1 day, single file or config change |
| **M** | 1–3 days, multiple files, moderate testing |
| **L** | 3–7 days, new module or significant refactor, extensive testing |
| **XL** | 1–2 weeks, major new subsystem |

---

## 7. Code Signing Strategy

**Principle**: Every distributed executable is signed. Container signatures (DMG, .pkg, NSIS) cover all bundled contents including third-party binaries.

### 7.1 Complete Signing Matrix

| Platform | Artifact | Signing Method | Covers Contents? | Status |
|----------|---------|---------------|-----------------|--------|
| macOS lite | `.dmg` installer | Apple Developer ID + notarization | Yes — all files inside DMG | Available |
| macOS lite | `QMatSuite.app` bundle | Apple Developer ID codesign | Yes — Frameworks, Resources, runtime tarball | Available |
| macOS lite | `micromamba` (in app bundle) | Covered by DMG + app signature | N/A (inside signed container) | Automatic |
| macOS lite | `runtime.tar.zst` (in app bundle) | Covered by DMG + app signature | N/A (inside signed container) | Automatic |
| macOS full | `.pkg` installer | Apple Developer ID + notarization | Yes — all payloads signed | Available |
| macOS full | QE binary (bundled) | Apple Developer ID codesign in .pkg | Yes | Needs CI |
| macOS full | SSSP files | Covered by .pkg signature | N/A (data files) | Automatic |
| macOS | micromamba (downloaded at runtime) | Ad-hoc sign after download | Self-only | Needs implementation |
| macOS | QE binary (GitHub Release download) | Ad-hoc sign after download | Self-only | Needs implementation |
| Windows | NSIS `.exe` installer | Microsoft Trusted Signing | Yes — all files inside installer | Available |
| Windows | `QMatSuite.exe` | Microsoft Trusted Signing | Self-only | Available |
| Windows | QE binary (bundled in NSIS) | Covered by NSIS signature | N/A (inside signed installer) | Automatic |
| Windows | QE binary (GitHub Release) | Microsoft Trusted Signing | Self-only | Done |
| Windows | micromamba.exe | Covered by NSIS signature (bundled) or unsigned (downloaded) | Bundled=covered, Downloaded=SHA256 only | Partial |
| Linux | PyPI wheel | N/A (pip verifies via PyPI TLS) | N/A | N/A |
| All | GitHub Release assets | SHA256 checksums + GitHub Artifact Attestation | Attestation covers build provenance | Available |

### 7.2 Third-Party Binary Signing

**micromamba**: Upstream releases from `mamba-org/micromamba-releases` are **NOT code-signed** (SHA256 only). On macOS, unsigned binaries trigger Gatekeeper warnings (Spyder issue #18661).

**Mitigation strategy:**
- **Bundled in installer**: Container signature covers it. macOS DMG/pkg signature and Windows NSIS signature protect bundled micromamba.
- **Downloaded at runtime** (engine manager auto-downloads): SHA256 verification on download. On macOS, ad-hoc sign after download: `codesign --force --sign - <micromamba_path>`.

**QE binary on macOS**: Same strategy. Bundled = covered by container signature. GitHub Release download = ad-hoc sign after download. Windows QE binaries from qmatsuite-toolchain are already Microsoft Trusted-Signed.

### 7.3 conda-forge Package Signing

conda-forge packages are **NOT cryptographically signed**. The `conda-content-trust` TUF framework exists in conda 4.10.1+ but conda-forge does not generate signatures. Package integrity relies on HTTPS transport security + repodata.json integrity.

**Implication**: For micromamba-installed engines, integrity = HTTPS + conda-forge infrastructure trust. This is the same trust model used by Jupyter, Spyder, and all conda-based scientific software.

### 7.4 Certificates

| Platform | Certificate | Program | Cost | Used For |
|----------|-----------|---------|------|----------|
| macOS | Apple Developer ID | Apple Developer Program | 99 USD/year | .app, .dmg, .pkg signing + notarization |
| Windows | Authenticode | Microsoft Trusted Signing | Available | .exe, NSIS installer signing |

---

## Appendix A: External Repository Reference

### QMatSuite/quantum-espresso-windows-exe

- **Purpose**: Distributes precompiled QE 7.5 Windows binaries (MPI variant)
- **Latest release**: `qe-7.5-win-oneapi-msmpi` (2025-12-23)
- **Asset**: `qe-7.5-win-oneapi-msmpi.zip` (400MB, 156 downloads)
- **Build**: Intel oneAPI + MKL + MS-MPI, Microsoft Trusted-Signed
- **Verification**: SHA256 checksums + GitHub Artifact Attestation
- **Future**: Will also host OpenMP-only variant (see §1.4)

### QMatSuite/qmatsuite-toolchain

- **Purpose**: CI build infrastructure for QE and Wannier90
- **Build matrix**: Ubuntu, macOS, Windows (MinGW + Intel oneAPI)
- **QE workflows**: `qe-linux-macos.yml`, `qe-windows-oneapi-msmpi.yml`, `qe-windows-mingw.yml`
- **Wannier90 workflows**: `wannier90-macos.yml`, `wannier90-ubuntu.yml`, `wannier90-windows-*.yml`
- **Latest release**: `qe-7.5-win-oneapi-msmpi-20251223-d409e9b`
- **115 commits**, PowerShell + Fortran + Python + CMake

### QMatSuite/QMatSuite (main repo)

- **CI workflow**: `.github/workflows/tests.yml`
  - Matrix: Ubuntu 22.04 + macOS 14, Python 3.12
  - Builds QE 7.5 from source (cached), stages to `.qmatsuite/engines/qe/managed:qe-7.5:<os>`
  - Runs pytest (5707 tests) + Playwright E2E (11 specs)
  - LAMMPS installed via apt/brew (system_path source type)

## Appendix B: Dependency Inventory (Measured)

Actual installed sizes measured from the project's `.venv/` (Python 3.12, macOS arm64):

### Direct Dependencies

| Package | Purpose | Size | C Extensions | Import Status |
|---------|---------|------|-------------|---------------|
| numpy 1.26.4 | Array operations | 19.9 MB | Yes (BLAS/LAPACK) | CORE — always loaded |
| scipy 1.17.0 | Scientific computing | 78.5 MB | Yes (Fortran) | Transitive via pymatgen; direct use lazy (1 place) |
| pymatgen 2024.10.3 | Materials science | 19.2 MB | Yes (via spglib) | CORE — module-level imports (can be made lazy) |
| matplotlib 3.10.8 | Plotting | 25.0 MB | Yes (Agg backend) | CORE — module-level import (can be made lazy) |
| ~~ase 3.27.0~~ | ~~Atomic simulation~~ | ~~11.3 MB~~ | ~~No~~ | **DEAD — remove** |
| plotext 5.3.2 | Terminal plotting | 0.7 MB | No | LAZY — MCP renderer only |
| PyYAML 6.0.3 | YAML parsing | 0.8 MB | Yes (C loader) | CORE |
| typer 0.21.1 | CLI framework | 0.4 MB | No | CORE |
| ~~beautifulsoup4 4.14.3~~ | ~~HTML parsing~~ | ~~0.8 MB~~ | ~~No~~ | **DEAD — remove** |
| ulid-py 1.1.0 | ULID generation | 0.2 MB | No | CORE |
| msgpack 1.1.2 | Binary serialization | 0.3 MB | Yes | CORE |
| requests 2.32.5 | HTTP client | 0.4 MB | No | CORE |
| certifi 2026.1.4 | TLS certificates | 0.3 MB | No | CORE |
| portalocker 2.10.1 | File locking | 0.1 MB | No | CORE |
| jinja2 3.1.6 | Template engine | 1.2 MB | No | LAZY — LAMMPS writer only |
| fastmcp 2.14.5 | MCP server | 3.2 MB | No | CORE (MCP mode) |

### Heavy Transitive Dependencies (>5 MB)

| Package | Pulled By | Size | Notes |
|---------|-----------|------|-------|
| pandas 45.6 MB | pymatgen | 45.6 MB | Lazy if pymatgen lazy |
| plotly 41.2 MB | pymatgen | 41.2 MB | Lazy if pymatgen lazy |
| sympy 38.2 MB | scipy | 38.2 MB | Lazy if scipy lazy |
| fonttools 14.7 MB | matplotlib | 14.7 MB | Lazy if matplotlib lazy |
| pillow 13.1 MB | matplotlib | 13.1 MB | Lazy if matplotlib lazy |
| networkx 10.9 MB | pymatgen | 10.9 MB | Lazy if pymatgen lazy |
| spglib 5.9 MB | pymatgen | 5.9 MB | Lazy if pymatgen lazy |

### Totals

| Metric | Value |
|--------|-------|
| Full transitive closure | 74 packages |
| Total installed size | 348.4 MB |
| Dead dependencies | 12.1 MB (ase + beautifulsoup4) |
| Savings if dead deps removed | 12.1 MB + transitive savings |
| Minimal startup set (if lazy) | ~43 MB |

All packages available on conda-forge, confirming micromamba approach viability.
