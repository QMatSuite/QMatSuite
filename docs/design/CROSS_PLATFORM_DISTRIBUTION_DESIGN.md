# Cross-Platform Distribution & Engine Management Design

**Status**: Design Document — substantially implemented as of v1.2.0 (engine mgmt, distribution, signing all complete; only qmatsuite-full bundling remains)
**Date**: 2026-02-25 (originally 2026-02-21)
**Author**: Distribution architecture for QMatSuite v2

### Implementation Status Summary

| Area | Status |
|------|--------|
| Path management (`paths.py` refactor) | ✅ v1.1.0 (Step 1) |
| PyPI publishing | ✅ v1.2.0 (Step 4) |
| Electron packaging (production builds, branding) | ✅ v1.2.0 (Steps 3-6) |
| Python runtime bundling (conda-pack in-app) | ✅ v1.2.0 (Step 8) |
| macOS code signing + notarization | ✅ v1.2.0 (Step 5) |
| Windows code signing (Azure Trusted Signing) | ✅ v1.2.0 (Step 5) |
| Engine registry (`engines.json`) | ✅ Implemented (engines.json CRUD, discovery, 6 source types) |
| Micromamba integration for engine management | ✅ Implemented (bootstrap, env create/remove, SHA256 verify) |
| Engine manager GUI | ✅ Implemented (install, uninstall, verify, configure-path, progress bar) |
| QE macOS binary portability (Step 7A) | ✅ Verified portable (2026-02-25, otool -L static analysis, 89 binaries clean) |
| qmatsuite-full release (QE + SSSP bundled) | 🔲 Not yet implemented |
| Auto-update | Partial (configured but has full-screen error when no release exists) |
| Linux AppImage | 🔲 Not yet implemented |

Detailed worklogs: `docs/history/worklogs/DISTRIBUTION_STEP*`

---

## Table of Contents

1. [Distribution Channels](#1-distribution-channels) (incl. §1.5 Size Estimates, §1.6 Per-Platform Install)
2. [Cross-Platform File Layout](#2-cross-platform-file-layout)
3. [Engine Management](#3-engine-management)
4. [Python Backend Packaging](#4-python-backend-packaging-for-full-release)
5. [Build & Release Workflow](#5-build--release-workflow)
6. [Current State vs Design — Gap Analysis](#6-current-state-vs-design--gap-analysis)
7. [Roadmap](#7-roadmap)
8. [Code Signing Strategy](#8-code-signing-strategy)

---

## 1. Distribution Channels

Three distribution channels serve different user profiles:

| Channel | Target User | Contents | Platform | Status |
|---------|------------|----------|----------|--------|
| `pip install qmatsuite` | Jupyter / API / Agent users | Python backend only | All (Mac, Win, Linux) | ✅ v1.2.0 |
| GitHub Release: **qmatsuite-lite** | Users who want selective engine install | Electron app + Python runtime (conda-pack) | Mac arm64, Windows x64 | ✅ v1.2.0 |
| GitHub Release: **qmatsuite-full** | Zero-friction QE users | lite + QE binary (OpenMP) + SSSP libraries | Mac, Windows | 🔲 Planned |

### 1.1 `pip install qmatsuite`

✅ Implemented in v1.2.0

**What's included:**
- `qmatsuite` Python package (CLI `qms`, daemon, MCP server, all 15 engine drivers)
- All Python dependencies (pymatgen, numpy, scipy, etc.)
- Bundled demo pseudopotentials in `resources/pseudo/`
- MCP server and mp-api integration
- No GUI, no Electron, no bundled engines

**Installation:**
```bash
pip install qmatsuite           # Core package (includes MCP + mp-api)
```

**First-launch experience:**
1. User activates their conda/venv environment
2. `qms init project myproject` creates a project directory
3. `qms run calculation` uses engines from system PATH or `.qmatsuite/engines/`
4. MCP: `python -m qmatsuite.mcp.server` starts the MCP server for AI agent integration

**Platform support:**
- macOS (Intel + Apple Silicon): Full support
- Linux (x86_64): Full support — primary path for HPC users
- Windows: Full support via pip in a conda environment

**Current state:** v1.2.0 published on PyPI. `pip install qmatsuite` works. 6514 tests passing.

### 1.2 GitHub Release: qmatsuite-lite

✅ Implemented in v1.2.0 (macOS arm64 DMG, Windows x64 NSIS)

**What is lite?** The core product. Lite is for:
- Users who see a 400MB+ full download and prefer a smaller initial install
- Users who don't need QE (they use ORCA, VASP, Gaussian, etc.) and don't want QE binary + SSSP they'll never use
- Users who want to install engines selectively (engine manager GUI planned, not yet implemented)

Lite = Electron app + Python runtime (bundled via conda-pack as uncompressed directory inside the app). Engine management is fully implemented — users can install engines via the built-in engine manager (micromamba one-click install for conda-forge engines, GitHub Release download for QE, or configure custom paths for licensed engines like VASP/Gaussian). (Updated 2026-02-25)

**What's included:**
- Electron desktop application (React + Three.js GUI)
- Embedded Python environment (via conda-pack, bundled as directory inside the app)
- `qmatsuite` package pre-installed in the embedded Python
- Built-in engine manager with micromamba integration for one-click install
- No engines pre-installed (user installs via engine manager or configures own paths)

**Installation:**
- **macOS arm64**: Download `.dmg`, drag QMatSuite to Applications, launch
- **Windows x64**: Download `.exe` NSIS installer, install, launch from Start Menu

**First-launch experience (v1.2.0):**
1. User launches QMatSuite
2. `ensureRuntimeReady()` checks for `.conda-unpacked` marker
3. If first launch: runs conda-unpack to fix paths (few seconds, no UI overlay)
4. Daemon starts immediately using bundled Python runtime
5. User can configure engine paths manually via settings

**Platform support:**
- macOS (Apple Silicon): `.dmg` release (arm64 only). Intel (x64) planned as separate DMG (not universal binary — see §7 note).
- Windows (x64): NSIS installer
- Linux: AppImage (lower priority — most Linux users prefer `pip install`)

### 1.3 GitHub Release: qmatsuite-full

🔲 Not yet implemented. Engine management (§3) is complete; this only needs QE binary bundling + SSSP packaging into the installer.

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
- macOS (Intel): `.pkg` installer with x86_64 QE binary (separate build, not universal binary)
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

**Current status** (Updated 2026-02-25): The toolchain repo has CI workflows for both variants. Windows binaries are working and signed. macOS OpenMP variant is **fully portable** (Step 7A complete — verified via `otool -L` static analysis on 2026-02-25). All 89 Mach-O binaries link only against `@executable_path/../lib/` (4 bundled dylibs: libgfortran.5, libquadmath.0, libgcc_s.1.1, libfftw3.3), `/System/Library/Frameworks/Accelerate.framework`, and `/usr/lib/libSystem.B.dylib`. Zero Homebrew/MacPorts/user-path references. Latest toolchain release: `qe-7.5-macos-arm64-openmp-20260223-10d20bf`.

### 1.5 Download vs Installed Size

Updated with measured values from v1.2.0. (Updated 2026-02-24)

| Component | Installed Size | Notes |
|-----------|---------------|-------|
| Electron shell (Chromium + asar) | ~200 MB | Standard Electron overhead |
| Python runtime (conda-pack, stripped) | ~526 MB | After stripping `__pycache__`, tests, docs, `.a` files |
| Runtime file count | ~20,379 | Down from ~39,763 pre-strip |
| DMG compressed size | 284 MB | UDZO compression |

| Channel | Download Size | Installed Size | Status |
|---------|--------------|---------------|--------|
| **pip install qmatsuite** | ~45 MB (wheel) | ~348 MB | ✅ v1.2.0 |
| **qmatsuite-lite (macOS arm64)** | **284 MB** (DMG) | **~982 MB** | ✅ v1.2.0 |
| **qmatsuite-lite (Windows x64)** | TBD (NSIS) | TBD | ✅ v1.2.0 (CI ready, pending first release trigger) |
| **qmatsuite-full** | ~400-500 MB est. | ~1.2 GB est. | 🔲 Planned |

**Size note** (Updated 2026-02-24): The installed size is ~982 MB because the runtime is bundled as an uncompressed directory inside the `.app` bundle (no separate extraction to `~/Library/Application Support/`). Total disk usage is actually LOWER than the original design (~982 MB vs ~1.3 GB) because there is no duplicate storage (compressed in app + extracted in AppData). The DMG at 284 MB is smaller than v1.1.0's 296 MB thanks to runtime stripping.

### 1.6 Per-Platform Installation Behavior

#### 1.6.1 Windows (NSIS Installer)

✅ Implemented in v1.2.0 (Updated 2026-02-24)

**Both lite and full** use NSIS (Nullsoft Scriptable Install System).

**Install path**: `%LOCALAPPDATA%\Programs\QMatSuite\` — per-user, no UAC prompt. Follows the VS Code / Discord / Slack convention of per-user install to LocalAppData. (This is the electron-builder default for NSIS `perMachine: false`.)

**Directory layout after install:**
```
%LOCALAPPDATA%\Programs\QMatSuite\
├── QMatSuite.exe              # Electron main executable
├── resources\
│   ├── app.asar               # Electron app bundle
│   └── runtime\               # Python environment (uncompressed, conda-pack)
│       ├── python.exe
│       ├── Lib\site-packages\qmatsuite\
│       └── Scripts\
│           └── conda-unpack   # Run once during NSIS install
├── ...                        # Chromium DLLs
└── Uninstall QMatSuite.exe    # NSIS uninstaller
```

**App data directory** (engines, config, logs — persists across updates):
```
%LOCALAPPDATA%\QMatSuite\
├── engines\                   # (future) Engine installations
├── config\
│   ├── settings.json
│   └── engines.json           # ✅ Engine registry (CRUD, discovery, 6 source types)
└── logs\
```

**Install flow (v1.2.0):**
1. User downloads `QMatSuite-Windows-x.y.z.exe` (~TBD MB)
2. NSIS installer runs — no UAC prompt (per-user install)
3. Extracts Electron app + runtime directory to `%LOCALAPPDATA%\Programs\QMatSuite\`
4. Runtime directory is placed directly by NSIS (no tarball extraction needed)
5. NSIS `customInstall` hook runs `python.exe Scripts\conda-unpack` to patch hardcoded CI paths
6. Writes `.conda-unpacked` marker file in runtime directory
7. Creates Start Menu shortcut and desktop shortcut
8. On first launch: Electron finds `resources\runtime\python.exe`, starts daemon immediately

**Code signing**: Azure Trusted Signing signs exe, dll, AND pyd files (`files-folder-filter: exe,dll,pyd`). ~394 signable files total per release. Azure Trusted Signing Basic plan: $9.99/month, 5,000 signatures/month included.

**Uninstall**: NSIS uninstaller in Add/Remove Programs. Removes app directory. Preserves `%LOCALAPPDATA%\QMatSuite\` (engines, config — user data). Option to remove everything.

#### 1.6.2 macOS Lite (DMG)

✅ Implemented in v1.2.0 — architecture significantly changed from original design. (Updated 2026-02-24)

**Install path**: `/Applications/QMatSuite.app` (drag to Applications). User data at `~/Library/Application Support/QMatSuite/`.

**DMG contents:**
```
QMatSuite.dmg (284 MB)
└── QMatSuite.app
    └── Contents/
        ├── MacOS/QMatSuite        # Electron main binary
        ├── Resources/
        │   ├── app.asar           # Electron app bundle
        │   └── runtime/           # Python environment (uncompressed, conda-pack)
        │       ├── bin/python3.12
        │       └── lib/python3.12/site-packages/...
        ├── Frameworks/            # Chromium frameworks
        └── Info.plist
```

**Architecture change from original design:** The original design bundled a compressed `runtime.tar.zst` inside the app and extracted it to `~/Library/Application Support/QMatSuite/runtime/` on first launch (10-30 second delay with progress overlay). The v1.2.0 implementation bundles the runtime as an **uncompressed directory** directly inside the `.app` bundle via electron-builder's `extraResources`. This eliminates the first-launch delay entirely.

**conda-pack and conda-unpack:** The runtime is built using `conda-pack`, which creates relocatable Python environments. `conda-pack` produces a tarball with the environment; CI extracts it and strips non-essential files, then electron-builder bundles the resulting directory. On first launch, `conda-unpack` runs to patch text files (shebangs, `.pc` files, OpenSSL config paths) to match the actual install location. Python itself works without conda-unpack (CPython auto-detects `sys.prefix` from its physical location), so the Python binary can run the conda-unpack script.

**Runtime stripping:** CI strips the following from the runtime before bundling to reduce file count and size:
- `__pycache__/` directories, `*.pyc`, `*.pyo` files
- `*.a` static library files
- `tests/` and `test/` directories inside site-packages
- `share/man`, `share/doc`, `share/gtk-doc`, `share/info`
- Result: ~39,763 → ~20,379 files, ~860 MB → ~526 MB

**First-launch flow (v1.2.0):**
1. User drags QMatSuite.app to Applications
2. On first launch, `ensureRuntimeReady()` checks for `.conda-unpacked` marker file in the runtime directory
3. If marker absent: runs `bin/python3.12 bin/conda-unpack` (few seconds, no UI overlay)
4. Writes `.conda-unpacked` marker to prevent re-running
5. Verifies: `runtime/bin/python3.12 -c "import qmatsuite"`
6. Starts daemon from the in-app runtime

**Code signing detail:** 409 Mach-O files in the app bundle:
- 25 executables in `runtime/bin/` (python3.12, openssl, bzip2, etc.)
- 60 `.dylib` files (libpython3.12, libssl, libcrypto, ICU, ncurses, etc.)
- 77 `.so` stdlib extensions (lib-dynload: `_ssl`, `_hashlib`, etc.)
- 217 `.so` site-packages extensions (scipy 109, pandas 45, numpy 19, matplotlib 9, PIL 8, etc.)
- 15 Electron framework binaries

electron-builder signs all Mach-O files with `--deep` codesign when `CSC_NAME` is set. CI sets `ulimit -n 65536` to avoid EMFILE errors during signing (macOS default is 256).

**Notarization:** Submitted async via `xcrun notarytool submit` (without `--wait`). DMG uploaded to GitHub Release immediately. Notarization completes in background. Stapling deferred (online users unaffected; offline users can right-click → Open).

**App data directory** (persists across updates, NOT inside the .app bundle):
```
~/Library/Application Support/QMatSuite/
├── engines/                      # ✅ Engine installations (managed, github_release, user_path)
├── config/
│   ├── settings.json
│   └── engines.json              # ✅ Engine registry (CRUD, discovery, 6 source types)
└── logs/
```

#### 1.6.3 macOS Full (.pkg Installer)

🔲 Not yet implemented. Engine management (§3) is complete; this only needs QE binary + SSSP bundling into a `.pkg` installer.

**Install path**: Same as lite — `/Applications/QMatSuite.app` + `~/Library/Application Support/QMatSuite/`. The .pkg installer handles installing to multiple locations atomically.

**Note** (Updated 2026-02-24): The runtime-in-app architecture from lite applies here too — the `.pkg` would install the `.app` bundle with `runtime/` directory inside, plus QE binaries and SSSP to `~/Library/Application Support/QMatSuite/`.

**Why .pkg for full (not DMG)**: The full release needs to install files to multiple locations:
- The app bundle → `/Applications/QMatSuite.app`
- QE binary → `~/Library/Application Support/QMatSuite/engines/qe/bundled-7.5/`
- SSSP → `~/Library/Application Support/QMatSuite/libraries/pseudo/SSSP/`

A DMG can only drag one `.app` to Applications. A `.pkg` installer can atomically install to all locations, provide progress feedback, and register engines during install.

**Install flow:**
1. User downloads `QMatSuite-Full-x.y.z.pkg` (~400-500 MB est.)
2. macOS Installer.app runs (Gatekeeper checks Developer ID signature)
3. Installs QMatSuite.app to `/Applications/` (includes runtime inside)
4. Installs QE to `~/Library/Application Support/QMatSuite/engines/qe/bundled-7.5/`
5. Installs SSSP to `~/Library/Application Support/QMatSuite/libraries/pseudo/SSSP/`
6. Registers in engines.json
7. On launch: Electron finds in-app runtime, starts daemon — QE ready immediately

#### 1.6.4 Linux

**Primary path**: `pip install qmatsuite` — Linux users typically have Python and conda/pip experience. No Electron distribution planned initially.

**AppImage** (deferred, lower priority): Self-contained single-file distribution. Would bundle Electron + Python runtime. ~200 MB. Deferred because most Linux HPC users prefer pip + their own Python environment.

---

## 2. Cross-Platform File Layout

### 2.1 Current State

✅ Refactored in v1.1.0 (Step 1). (Updated 2026-02-24)

`src/qmatsuite/core/paths.py` provides environment-aware path resolution supporting dev mode, Electron mode, and pip-installed mode. The old `get_repo_root()` issue (failing for pip-installed packages) is solved.

```
<REPO_ROOT>/                           # Dev mode layout
├── .qmatsuite/                        # Persistent assets (gitignored)
│   ├── config/settings.json           # User settings
│   ├── engines/qe/<version>/bin/      # QE binaries
│   ├── seeds/pseudo/                  # Offline pseudo seeds
│   ├── libraries/pseudo/SSSP/         # Installed SSSP
│   └── logs/                          # Runtime logs
├── .tmp/                              # Scratch space (gitignored)
│   ├── downloads/                     # Download cache
│   ├── unpack/                        # Extraction temp
│   ├── runs/                          # Calculation scratch
│   ├── probe/                         # Engine discovery probes
│   └── locks/                         # Concurrency locks
└── <user-projects>/                   # User project directories (anywhere)
```

### 2.2 Target State

✅ Implemented (Step 1). Three concerns are separated:

| Concern | Contents | Persistence | Updated by |
|---------|----------|-------------|-----------|
| **App data** | Engines, pseudopotentials, micromamba, config | Persists across app updates | Engine manager, pseudo downloader |
| **Cache** | Downloads, extraction temp, build artifacts, locks | Deletable anytime | System temp cleanup |
| **User data** | Projects | User manages | User |

**Platform-specific locations:**

| Platform | App Data | Cache | User Data | Status |
|----------|----------|-------|-----------|--------|
| macOS (pip) | `~/.qmatsuite/` | System temp or `~/.qmatsuite/.tmp/` | User-chosen | ✅ |
| macOS (Electron) | `~/Library/Application Support/QMatSuite/` | `~/Library/Caches/QMatSuite/` | User-chosen | ✅ |
| Windows (pip) | `%USERPROFILE%\.qmatsuite\` | System temp | User-chosen | ✅ |
| Windows (Electron) | `%LOCALAPPDATA%\QMatSuite\` | `%LOCALAPPDATA%\QMatSuite\cache\` | User-chosen | ✅ |
| Linux (pip) | `~/.qmatsuite/` or `$XDG_DATA_HOME/qmatsuite/` | System temp | User-chosen | ✅ |
| Dev (repo checkout) | `<REPO_ROOT>/.qmatsuite/` | `<REPO_ROOT>/.tmp/` | Anywhere | ✅ |

**Note** (Updated 2026-02-24): The Python runtime lives INSIDE the app bundle (not in app data). Engines, config, and logs go to app data. This separation means app updates replace the runtime but never touch user data.

### 2.3 Path Resolution Design

✅ Implemented in `src/qmatsuite/core/paths.py` (Step 1). (Updated 2026-02-24)

The implemented resolution chain matches the original design:

```python
# src/qmatsuite/core/paths.py — implemented

def get_app_data_dir() -> Path:
    """
    Resolve the QMatSuite app data directory.

    Resolution order:
    1. QMATSUITE_HOME environment variable (explicit override)
    2. Dev mode: <repo_root>/.qmatsuite/ (if pyproject.toml + src/qmatsuite/ found)
    3. Electron mode: platform-appropriate Application Support / LOCALAPPDATA
    4. pip mode: ~/.qmatsuite/
    """
    ...

def get_cache_dir() -> Path:
    """
    Resolution order:
    1. QMATSUITE_CACHE environment variable
    2. Dev mode: <repo_root>/.tmp/
    3. Electron mode: platform cache directory
    4. pip mode: <app_data_dir>/.tmp/
    """
    ...
```

Electron detection uses `QMATSUITE_ELECTRON=1` environment variable, set by `main.ts` when spawning the daemon.

**App data directory structure** (same across all platforms):

```
<app_data_dir>/
├── config/
│   └── settings.json          # User settings
│   └── engines.json           # ✅ Engine registry (see §3) — implemented
├── engines/
│   ├── qe/
│   │   ├── bundled-7.5/bin/   # (future) Bundled QE (full release only)
│   │   └── conda-7.5/bin/     # (future) Micromamba-installed QE
│   ├── xtb/
│   │   └── conda-6.7.1/bin/   # (future) Micromamba-installed xTB
│   └── vasp/
│       └── user/bin/          # User-provided VASP
├── libraries/
│   └── pseudo/
│       └── SSSP/
├── seeds/
│   └── pseudo/                # Offline install seeds
├── micromamba/                 # ✅ Implemented (bootstrap, envs, SHA256 verify)
│   ├── bin/micromamba
│   └── envs/
└── logs/
```

### 2.4 Migration Strategy

**Dev → Production**: The `QMATSUITE_HOME` env var and `_try_find_repo_root()` fallback means existing development workflows continue unchanged. The new path resolution only activates for pip-installed or Electron-bundled deployments.

**Backward compatibility**: The existing path helper functions (`home_engines_dir()`, `home_pseudo_libraries_dir()`, etc.) keep their signatures. Their implementations change from `get_repo_root() / ".qmatsuite" / ...` to `get_app_data_dir() / ...`.

**Key invariant**: App updates (Electron auto-update or `pip install --upgrade`) never touch `<app_data_dir>/engines/`, `<app_data_dir>/libraries/`, or user project directories.

---

## 3. Engine Management

✅ **Fully implemented.** The unified `engines.json` registry, 8-tier discovery, micromamba integration, daemon RPC endpoints, and GUI engine manager panel are all operational (4,270 LOC across 22 files). Verified against each Phase 2 roadmap item on 2026-02-25. (Updated 2026-02-25)

### 3.1 Implementation Status (Phase 2 Verification)

| Roadmap Item | Status | Key Implementation |
|---|---|---|
| 2.1 `engines.json` registry | ✅ Done | `core/engines/engine_registry.py` (672 LOC) — `EngineRegistry` class with load/save/add/remove/list/get_active/set_active, atomic `.json.tmp` writes, schema versioning |
| 2.2 QE resolver integration | ✅ Done | `drivers/qe/engine/qe_resolver.py` — `_resolve_qe_bin_dir_from_registry()` does registry-first lookup, falls back to legacy two-state |
| 2.3 All engine handlers | ✅ Done | All 15 engine handlers use `engine_registry.get(family)` for binary lookup — no engine-specific path imports in handlers |
| 2.4 `list_engines` real detection | ✅ Done | `api/engines.py:list_engines()` — uses registry discovery + fallback detection (importlib for Python engines, shutil.which for binaries) |
| 2.5 Micromamba integration | ✅ Done | `core/engines/micromamba.py` (344 LOC) — platform-aware download, SHA256 verify, ad-hoc codesign (macOS), create_env/remove_env/list_envs |
| 2.6 Daemon RPC endpoints | ✅ Done | `daemon/server.py` — 10 RPC handlers: engine.list, engine.verify, engine.set_active, engine.register_path, engine.unregister, engine.install, engine.uninstall, engine.list_installable, list_engine_families, set_engine_family |
| 2.7 GUI engine manager | ✅ Done | `gui/src/components/panels/SettingsPanel.tsx:EngineManagementSection` — install/uninstall with progress bar, verify, configure-path, switch active, real-time job polling |

### 3.2 Unified Engine Registry

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
# src/qmatsuite/engine/engine_meta.py — proposed

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
        "github_release": "QMatSuite/qmatsuite-toolchain",
        "env_vars": {},
        "bundleable": True,
    },
    "vasp": {
        "display_name": "VASP",
        "engine_type": "binary",
        "required_binaries": ["vasp_std"],
        "optional_binaries": ["vasp_gam", "vasp_ncl"],
        "version_command": None,
        "conda_package": None,
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
        "version_command": None,
        "conda_package": None,
        "env_vars": {},
        "bundleable": False,
    },
    "gaussian": {
        "display_name": "Gaussian",
        "engine_type": "binary",
        "required_binaries": ["g16"],
        "optional_binaries": ["g09"],
        "version_command": None,
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
        "version_command": None,
        "conda_package": None,
        "env_vars": {},
        "bundleable": False,
    },
    "yambo": {
        "display_name": "Yambo",
        "engine_type": "binary",
        "required_binaries": ["yambo"],
        "optional_binaries": ["p2y"],
        "version_command": ["yambo", "-h"],
        "conda_package": None,
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
        "required_binaries": [],
        "python_import": "pyscf",
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

✅ Implemented in `core/engines/discovery.py` (729 LOC). When the engine manager runs discovery (on app launch or user request):

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

✅ Implemented. See `src/qmatsuite/core/engines/micromamba.py`.

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

Python engines are NOT dependencies of the main `qmatsuite` package. They each get their own micromamba environment (see §3.8 for details). Users can also point to an existing venv that has the package installed.

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

**Auto-source selection** (`source="auto"` in `install_engine()`):

When the user clicks "Install" without specifying a source, the selection logic is:

| Engine | Platform | Selected source | Rationale |
|--------|----------|----------------|-----------|
| QE | macOS (arm64, x64) | `github_release` | Signed, platform-optimized toolchain binary |
| QE | Windows x64 | `github_release` | Same — pre-built OneAPI+MSMPI binary |
| QE | Linux x64 | `conda` | No toolchain release for Linux yet |
| xTB, LAMMPS, CP2K, etc. | Any | `conda` | conda-forge packages via micromamba |
| VASP, ORCA, Gaussian, Yambo | Any | Error | User must provide path ("Configure Path") |

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

Python engines are NOT pip dependencies of `qmatsuite`. They are full engines managed by micromamba, each in their own conda environment or user-provided venv. The daemon process never imports them directly — all execution happens via subprocess.

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
     sys.executable != engine python
     PYTHONPATH injected for qmatsuite
```

**How subprocess isolation works** (from `engine/psi4_engine.py:131-142`):

```python
def _get_runner_env(self) -> Dict[str, str]:
    """Inject PYTHONPATH so the engine's Python can import qmatsuite."""
    import qmatsuite
    env = os.environ.copy()
    src_dir = str(Path(qmatsuite.__file__).parent.parent)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}:{existing}" if existing else src_dir
    return env
```

The runner subprocess uses the engine's Python interpreter (which has pyscf/psi4/gpaw) but gets `qmatsuite` via PYTHONPATH injection from the daemon's environment.

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

In dev mode, the developer's active venv typically has PySCF/Psi4 installed alongside qmatsuite. The engine adapters use `discover_engine()` which checks engines.json first, then falls back to `sys.executable`. This means:

1. **No engines.json**: Falls back to `sys.executable` (developer's venv) — existing behavior
2. **With engines.json**: Uses registered Python executable — production behavior
3. **PYTHONPATH injection**: Works in both modes

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

4. Verify SHA256 checksum:
   - Primary: `checksums.txt` (standard `sha256sum` output format: `<hash>  <filename>`).
     Toolchain releases publish this file; the engine installer parses it to
     extract per-asset hashes.
   - Fallback: per-asset `.sha256` sidecar files (used by micromamba releases).
   - If neither exists, a warning is logged and verification is skipped.

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

### 3.10 Integration with Existing Code

The unified registry augments the QE resolver with a registry-first lookup, evolving from a two-state to a **three-state** model:

**QE resolver (three-state, as implemented):**
```
qe_resolver.resolve_qe_bin_dir()
  -> State 1 (Registry):  EngineRegistry.get_active("qe")         — highest priority
  -> State 2 (Settings):  settings.qe.bin_dir                     — backward compatibility
  -> State 3 (Auto-scan): find_internal_qe_bin_dir()              — legacy fallback
       scans .qmatsuite/engines/qe/**/bin/
  -> Error
```

**Other engines** follow a simpler two-tier pattern:
```
resolve_active_binary("<engine>", binary_name="<binary>")
  -> Tier 1 (Registry): EngineRegistry.get_active("<engine>")
  -> Tier 2 (Fallback):  shutil.which("<binary>")
```

**Verification hook in handlers**: Each engine handler already catches `FileNotFoundError`. The registry adds a pre-flight check before subprocess invocation — verify the registered path still exists and the binary is executable.

### 3.11 Install Progress Reporting

Engine installation is async via the `JobManager` (single-worker `ThreadPoolExecutor`). The frontend polls `get_job_status` every 2 seconds. Jobs report progress through these fields on the `Job` dataclass:

| Field | Type | Description |
|-------|------|-------------|
| `progress_pct` | `float \| None` | Overall completion percentage (0–100) |
| `progress_bytes` | `int \| None` | Bytes downloaded so far |
| `progress_total` | `int \| None` | Total expected bytes |
| `progress_stage` | `str \| None` | Human-readable stage label (e.g., "Bootstrapping micromamba", "Installing xTB via conda") |

Download phases (GitHub Release binary, micromamba bootstrap) report byte-level progress via an `on_progress` callback that updates the job's fields. Conda install phases stream `micromamba create` subprocess stdout line-by-line as `log_line` events — the last line is exposed as `last_log_line`. The frontend renders a determinate progress bar when `progress_pct` is available, falling back to an indeterminate animation when only stage info is present.

---

## 4. Python Backend Packaging for Full Release

### 4.1 The Problem

The Electron app (qmatsuite-lite and qmatsuite-full) bundles a GUI that communicates with a Python daemon over JSON-RPC stdio. Currently, the daemon requires:

1. A Python 3.9+ interpreter
2. The `qmatsuite` package installed with all dependencies

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
| qmatsuite | 17.5 MB | Source |
| msgpack, ulid-py, requests, certifi, portalocker | ~1.5 MB | Small deps |
| **Total** | **~43 MB** | vs 348 MB current |

**Dead dependencies** (removed in v1.2.0):
| Package | Size | Status |
|---------|------|--------|
| ~~beautifulsoup4~~ | ~~0.8 MB~~ | ✅ Removed |

**Note**: `ase` was previously listed as removed here, but it is intentionally kept as a lazy import for the trajectory parser. See Appendix B.

**PySCF optional extra**: ✅ Removed from `pyproject.toml`. PySCF is a micromamba-managed engine (§3.8), not a pip dependency.

### 4.3 Decision: Embedded Python via conda-pack

✅ Implemented in v1.2.0 (Step 8). (Updated 2026-02-24)

**Final decision**: Use **conda-pack** to create a relocatable Python environment containing Python 3.12 + all dependencies. The environment is bundled as an **uncompressed directory** inside the app via electron-builder's `extraResources`. On first launch, `conda-unpack` patches paths for the target machine.

**Architecture change from original design:** The original design used micromamba to create the environment + zstd-compressed tarball that was expanded at install time (full) or first launch (lite, with 10-30 second delay and progress overlay). The implemented approach eliminates the first-launch delay entirely by bundling the runtime as a plain directory. No zstd compression, no micromamba needed for runtime creation, no extraction overlay.

**Why conda-pack:**
- Creates fully relocatable Python environments
- `conda-unpack` script patches shebangs, `.pc` files, and OpenSSL config paths
- CPython auto-detects `sys.prefix` from its physical location, so Python works even before conda-unpack runs
- Well-established tool (conda-forge, 1M+ downloads)
- No anti-virus false positives (common with PyInstaller on Windows)
- No bundling complexity — conda packages handle all native dependencies (BLAS, LAPACK, etc.)
- Fast startup (~1s, native CPython)

**Runtime environment layout (v1.2.0):**
```
macOS:   QMatSuite.app/Contents/Resources/runtime/
Windows: <install_dir>/resources/runtime/
```

The runtime is INSIDE the app bundle, not in `<app_data>/runtime/` as originally designed. This means app updates atomically replace the runtime.

**Build pipeline (CI) — implemented:**
```
1. CI creates conda environment (micromamba create -p runtime-env python=3.12 pip)
2. pip install qmatsuite==1.2.0 from PyPI into the environment
3. conda-pack packages the environment as a relocatable tarball
4. Extract tarball to gui/runtime/
5. DO NOT run conda-unpack in CI (paths would be wrong on user machine)
6. Strip: remove __pycache__/, *.pyc, *.pyo, *.a, tests/, share/man|doc|info
7. electron-builder bundles gui/runtime/ as extraResources
8. On target machine: conda-unpack patches paths on first launch (macOS)
   or during NSIS install (Windows)
```

**Strip results:**
| Metric | Before strip | After strip |
|--------|-------------|-------------|
| Runtime directory | 860 MB | 526 MB |
| File count | 39,763 | 20,379 |
| DMG size | 372 MB | 284 MB |

**Pre-work (Phase 0, completed):** ✅ Dead dependency removed (beautifulsoup4); ase intentionally kept (lazy, traj parser). Some lazy imports done (Step 1). Full lazy import optimization is partially done.

### 4.4 Future Alternatives (Reference Only)

These alternatives were evaluated and are documented for future reference. They are NOT the active plan.

#### PyInstaller (Feasibility: Medium)

Bundle `qmatsuite.daemon.server` into a single directory. Achieves ~250 MB bundle (vs ~350 MB conda env, both compressed to ~100-115 MB). All heavy deps (numpy, scipy, pymatgen, matplotlib) have well-maintained hooks. Main risks: anti-virus false positives on Windows, tight coupling (every Python update requires rebuild), no extensibility (can't `pip install` into a frozen bundle).

#### Nuitka Compiled Binary (Feasibility: Medium, Future Priority)

Compile Python to C and produce a native executable. If Nuitka matures sufficiently for the scientific Python stack, a compiled `qmatsuite-daemon` binary would be the ideal long-term solution: smallest size, fastest startup, no Python env needed. A priority 3 slot is reserved in `findPythonPath()` for this (see §4.5).

**Nuitka upgrade path** (non-breaking):
1. Build a Nuitka-compiled daemon binary in CI
2. Ship it alongside the conda runtime in the installer
3. `findPythonPath()` priority 3 checks for the compiled binary first
4. If found, use it; if not, fall back to conda runtime (priority 4)
5. Once Nuitka build is stable, remove conda runtime from installer

### 4.5 Electron + Embedded Python Integration

✅ Implemented in v1.2.0 (Step 8). (Updated 2026-02-24)

**First launch (v1.2.0):**
1. Electron app starts
2. `ensureRuntimeReady()` checks for `.conda-unpacked` marker in runtime directory
3. If marker absent: runs `python3.12 bin/conda-unpack` (macOS) or `python.exe Scripts\conda-unpack` (Windows) — takes a few seconds, no UI overlay
4. Writes `.conda-unpacked` marker to prevent re-running
5. Verifies: `<runtime>/bin/python -c "import qmatsuite; print(qmatsuite.__version__)"`
6. Starts daemon: `<runtime>/bin/python -m qmatsuite.daemon.server`

**Subsequent launches**: Marker exists, daemon starts immediately.

**Electron `findPythonPath()` resolution chain (v1.2.0):**

```typescript
function findPythonPath(): { path: string; found: boolean; source: string } {
  // Priority 1: QMS_DAEMON_PYTHON override (explicit user/CI override)
  // Priority 2: .venv/bin/python (dev mode — repo checkout detected)
  // Priority 3: (Reserved for Nuitka compiled binary — future)
  // Priority 4: In-app runtime (packaged mode)
  //   macOS:   process.resourcesPath/runtime/bin/python3.12
  //   Windows: process.resourcesPath/runtime/python.exe
  // Priority 5: AppData runtime (legacy migration from v1.1.0)
  //   macOS:   ~/Library/Application Support/QMatSuite/runtime/bin/python
  //   Windows: %LOCALAPPDATA%/QMatSuite/runtime/python.exe
  // Priority 6: system python fallback (pip-installed qmatsuite)
}
```

**Key change from original design:** Priority 4 now looks in `process.resourcesPath/runtime/` (inside the app bundle), not in `<app_data>/runtime/`. Priority 5 is a migration fallback for users upgrading from v1.1.0 who may still have an extracted runtime in AppData.

### 4.6 Update Strategy

Three independent update dimensions:

| Dimension | Mechanism | Frequency | Affects |
|-----------|----------|-----------|---------|
| **qmatsuite package** | Full Electron update (new .app with new runtime) | Per release | Python code + runtime |
| **Python version** | Full Electron update (new runtime in app) | Yearly | Runtime env |
| **Electron shell** | `electron-updater` auto-update from GitHub Releases | Per release | GUI + runtime (since runtime is in-app) |

**Update strategy change** (Updated 2026-02-24): Since the runtime is now inside the `.app` bundle, updating `qmatsuite` package requires a full Electron update (new .app with new runtime). The original design allowed independent `pip install --upgrade qmatsuite` into the extracted runtime. The current approach trades that flexibility for zero first-launch delay and simpler architecture. In-app pip upgrade is still technically possible but not yet implemented.

**Key invariant**: Updating the app never touches `<app_data_dir>/engines/`, `<app_data_dir>/libraries/`, or user project directories. Engines, pseudopotentials, and projects persist across all app updates.

---

## 5. Build & Release Workflow

✅ Implemented in v1.2.0. (Added 2026-02-24)

### 5.1 CI Workflows

| Workflow | File | Trigger | Output |
|----------|------|---------|--------|
| Python tests | `tests.yml` | Push/PR | Test results (6514 tests) |
| PyPI release | `release-pip.yml` | Manual (version + target) | Package on TestPyPI or PyPI |
| Build runtime | `build-runtime-dir.yml` | Manual | conda-pack runtime directory artifact |
| macOS release | `release-macos.yml` | Manual (version + sign + notarize flags) | Signed+notarized DMG on GitHub Releases |
| Windows release | `release-windows.yml` | Manual (version + sign flag) | Signed NSIS installer on GitHub Releases |

### 5.2 Release Sequence

```
1. Bump version in pyproject.toml + gui/package.json
2. Commit, tag (v1.2.0), push
3. Trigger PyPI release → testpypi first → verify → pypi
4. Trigger macOS release (depends on PyPI — CI installs qmatsuite from PyPI)
5. Trigger Windows release (same dependency)
6. macOS and Windows can run in parallel
```

### 5.3 macOS Release Pipeline Detail

```
Checkout → Node 20 → Python 3.12 → micromamba
→ Build runtime environment (micromamba create + pip install qmatsuite)
→ conda-pack → extract tarball → strip files (NO conda-unpack in CI)
→ npm ci → npm run build:e2e
→ electron-builder --mac dmg --arm64
  (unsigned: CSC_IDENTITY_AUTO_DISCOVERY=false)
  (signed: CSC_NAME="Developer Name (TeamID)")
  ulimit -n 65536 before build
→ Notarize: xcrun notarytool submit (async, no --wait)
→ Upload artifact → Upload to GitHub Release (if versioned)
```

### 5.4 Windows Release Pipeline Detail

```
Checkout → Node 20 → Python 3.12 → micromamba
→ Build runtime environment (micromamba create + pip install qmatsuite)
→ conda-pack → extract tarball (relative paths!) → strip files
→ npm ci → npm run build:e2e
→ electron-builder --win nsis --x64
  (CSC_IDENTITY_AUTO_DISCOVERY=false — signing is post-build)
→ Azure Login (OIDC)
→ Azure Trusted Signing (files-folder-filter: exe,dll,pyd, recurse: true)
→ Upload artifact → Upload to GitHub Release (if versioned)
```

---

## 6. Current State vs Design — Gap Analysis

(Updated 2026-02-24)

| Component | Status | Current State | Target State | Gap |
|-----------|--------|--------------|-------------|-----|
| **Path management** | ✅ Done (Step 1) | Platform-aware resolution chain in `paths.py` | — | Complete |
| **pip install** | ✅ Done (Step 4, v1.2.0) | v1.2.0 on PyPI, 6514 tests passing | — | Complete |
| **Electron packaging** | ✅ Done (Steps 3-6) | Production builds with branding, icons, proper appId | — | Complete |
| **Python bundling** | ✅ Done (Step 8) | conda-pack runtime as directory in app, 284 MB DMG | — | Complete |
| **Code signing (macOS)** | ✅ Done (Step 5) | Developer ID + notarization, 409 Mach-O files signed | — | Complete |
| **Code signing (Windows)** | ✅ Done (Step 5) | Azure Trusted Signing, exe+dll+pyd, ~394 files | — | Complete |
| **QE binary (Windows)** | Partial | Binary exists + signed in toolchain repo | Bundled in full installer | Needs full release (§1.3) |
| **QE binary (macOS)** | ✅ Portable | CI builds, dylib bundling verified portable (2026-02-25 static analysis) | Bundled in full installer | Only needs full-release packaging |
| **Auto-update** | Partial | electron-updater configured | Working auto-update | Full-screen error when no release exists (bug to fix) |
| **Engine discovery** | ✅ Done | Unified `engines.json` for all 15 engines, 8-tier discovery | — | Complete (`core/engines/engine_registry.py`, 672 LOC) |
| **Micromamba** | ✅ Done | Bootstrap, create/remove envs, SHA256 verify, ad-hoc codesign | — | Complete (`core/engines/micromamba.py`, 344 LOC) |
| **Engine setup GUI** | ✅ Done | Full install/uninstall/verify/configure-path GUI with progress | — | Complete (`SettingsPanel.tsx:EngineManagementSection`) |
| **SSSP bundling** | 🔲 Not started | Runtime download via MCP/CLI | Pre-bundled in full installer | Small — package in installer |

---

## 7. Roadmap

### Phase 0: Pre-work (can be done immediately, no dependencies)

| # | Work Package | Complexity | Status |
|---|-------------|-----------|--------|
| 0.1 | Remove dead dependency `beautifulsoup4` from `pyproject.toml` (ase kept — lazy, traj parser) | **S** | ✅ Done (v1.1.0) |
| 0.2 | Remove `pyscf` optional extra from `pyproject.toml` (micromamba-managed) | **S** | ✅ Done (v1.1.0) |
| 0.3 | Make pymatgen/matplotlib/scipy imports lazy | **M** | Partial (some lazy imports done in Step 1) |
| 0.4 | Add QE OpenMP-only CI workflow to qmatsuite-toolchain (no MPI variant) | **M** | ✅ Done (toolchain has workflows, macOS dylib bundling verified portable 2026-02-25) |

### Phase 1: Foundation (everything else depends on this)

| # | Work Package | Complexity | Status |
|---|-------------|-----------|--------|
| 1.1 | Refactor `paths.py` to support `QMATSUITE_HOME` + platform-aware resolution | **M** | ✅ Done (Step 1, v1.1.0) |
| 1.2 | Fix `get_repo_root()` fallback for pip-installed packages | **S** | ✅ Done (Step 1) |
| 1.3 | Add `package_data` for all non-`.json` resources to `pyproject.toml` | **S** | ✅ Done |
| 1.4 | Publish `qmatsuite` to PyPI (test → production) | **S** | ✅ Done (Step 4, v1.2.0) |

### Phase 2: Engine Management (enables lite distribution)

| # | Work Package | Complexity | Status |
|---|-------------|-----------|--------|
| 2.1 | Design and implement `engines.json` registry module | **L** | ✅ Done — `core/engines/engine_registry.py` (672 LOC) |
| 2.2 | Integrate registry with QE resolver (replace two-state with registry lookup) | **M** | ✅ Done — `_resolve_qe_bin_dir_from_registry()` in qe_resolver.py |
| 2.3 | Integrate registry with all other engine handlers | **M** | ✅ Done — all 15 handlers use `engine_registry.get(family)` |
| 2.4 | Implement `list_engines` real `installed` detection via registry | **S** | ✅ Done — `api/engines.py:list_engines()` with registry + fallback |
| 2.5 | Micromamba download + environment management module | **L** | ✅ Done — `core/engines/micromamba.py` (344 LOC) |
| 2.6 | Daemon RPC commands for engine management (list, install, verify, set-active) | **M** | ✅ Done — 10 RPC handlers in daemon/server.py |
| 2.7 | GUI engine manager panel | **M** | ✅ Done — `SettingsPanel.tsx:EngineManagementSection` |

### Phase 3: Electron Distribution (enables first release)

| # | Work Package | Complexity | Status |
|---|-------------|-----------|--------|
| 3.1 | Configure `electron-builder.json5` with production values (appId, product name, icons) | **S** | ✅ Done (Step 3, v1.2.0) |
| 3.2 | Runtime bundling: conda-pack directory in app (originally: expand pre-built runtime tarball) | **L** | ✅ Done (Step 8 — conda-pack, not micromamba bootstrap) |
| 3.3 | Electron `findPythonPath()` — add in-app runtime lookup | **S** | ✅ Done (Step 2) |
| 3.4 | macOS CI build workflow: `.dmg` (lite) via electron-builder | **M** | ✅ Done (Step 5) |
| 3.5 | Windows NSIS installer CI build workflow | **M** | ✅ Done (Step 5) |
| 3.6 | QE binary bundling in full-release installer (Mac arm64 + Windows x64) | **M** | 🔲 Not started |
| 3.7 | SSSP library bundling in full-release installer | **S** | 🔲 Not started |
| 3.8 | macOS code signing (Developer ID + notarization) | **M** | ✅ Done (Step 5) |
| 3.9 | Windows code signing (Azure Trusted Signing) | **M** | ✅ Done (Step 5) |

### Phase 4: Polish (post-launch)

| # | Work Package | Complexity | Status |
|---|-------------|-----------|--------|
| 4.1 | Electron auto-update via `electron-updater` + GitHub Releases | **M** | Partial (configured but has full-screen error bug) |
| 4.2 | Linux AppImage build (lower priority) | **S** | 🔲 Not started |
| 4.3 | macOS Intel (x64) DMG — separate build, not universal binary | **M** | 🔲 Not started |
| 4.4 | Engine update notification in GUI ("xTB 6.8.0 available, update?") | **S** | 🔲 Not started |
| 4.5 | Offline installer variant (pre-pack micromamba envs for air-gapped HPC) | **L** | 🔲 Not started |
| 4.6 | Contributing guide for adding new engines to the registry | **S** | 🔲 Not started |

### Complexity Legend

| Size | Estimated Scope |
|------|----------------|
| **S** | < 1 day, single file or config change |
| **M** | 1-3 days, multiple files, moderate testing |
| **L** | 3-7 days, new module or significant refactor, extensive testing |
| **XL** | 1-2 weeks, major new subsystem |

---

## 8. Code Signing Strategy

**Principle**: Every distributed executable is signed. Container signatures (DMG, .pkg, NSIS) cover all bundled contents including third-party binaries.

### 8.1 Complete Signing Matrix

(Updated 2026-02-24 with measured values from v1.2.0)

| Platform | Artifact | Signing Method | Details | Status |
|----------|---------|---------------|---------|--------|
| macOS lite | `.dmg` installer (284 MB) | Apple Developer ID + notarization | UDZO compressed | ✅ v1.2.0 |
| macOS lite | `QMatSuite.app` bundle | Apple Developer ID `--deep` codesign | 409 Mach-O files individually signed (25 exe + 60 dylib + 77 stdlib .so + 217 site-packages .so + 15 Electron) | ✅ v1.2.0 |
| macOS full | `.pkg` installer | Apple Developer ID + notarization | Includes QE binary + SSSP | 🔲 Planned |
| macOS | micromamba (downloaded at runtime) | Ad-hoc sign after download | Self-only | 🔲 Not started |
| macOS | QE binary (GitHub Release download) | Ad-hoc sign after download | Self-only | 🔲 Not started |
| Windows | NSIS `.exe` installer | Microsoft Trusted Signing | Outer installer signed | ✅ v1.2.0 |
| Windows | All exe + dll + pyd in `win-unpacked/` | Microsoft Trusted Signing (`files-folder-filter: exe,dll,pyd`) | ~394 files signed recursively | ✅ v1.2.0 |
| Windows | QE binary (GitHub Release) | Microsoft Trusted Signing | Self-only | Done (toolchain repo) |
| Linux | PyPI wheel | N/A (pip verifies via PyPI TLS) | N/A | N/A |
| All | GitHub Release assets | SHA256 checksums + GitHub Artifact Attestation | Build provenance | Available |

**macOS signing count:** 409 Mach-O files, 0 unsigned. `ulimit -n 65536` set in CI to avoid EMFILE during signing.

**Windows signing count:** ~394 files (exe + dll + pyd). Azure Trusted Signing Basic: $9.99/month, 5,000 signatures/month. ~394 operations per release, well within quota.

### 8.2 Third-Party Binary Signing

**micromamba**: Upstream releases from `mamba-org/micromamba-releases` are **NOT code-signed** (SHA256 only). On macOS, unsigned binaries trigger Gatekeeper warnings (Spyder issue #18661).

**Mitigation strategy:**
- **Bundled in installer**: Container signature covers it. macOS DMG/pkg signature and Windows NSIS signature protect bundled micromamba.
- **Downloaded at runtime** (engine manager auto-downloads): SHA256 verification on download. On macOS, ad-hoc sign after download: `codesign --force --sign - <micromamba_path>`.

**QE binary on macOS**: Same strategy. Bundled = covered by container signature. GitHub Release download = ad-hoc sign after download. Windows QE binaries from qmatsuite-toolchain are already Microsoft Trusted-Signed.

### 8.3 conda-forge Package Signing

conda-forge packages are **NOT cryptographically signed**. The `conda-content-trust` TUF framework exists in conda 4.10.1+ but conda-forge does not generate signatures. Package integrity relies on HTTPS transport security + repodata.json integrity.

**Implication**: For micromamba-installed engines, integrity = HTTPS + conda-forge infrastructure trust. This is the same trust model used by Jupyter, Spyder, and all conda-based scientific software.

### 8.4 Certificates

| Platform | Certificate | Program | Cost | Used For |
|----------|-----------|---------|------|----------|
| macOS | Apple Developer ID | Apple Developer Program | 99 USD/year | .app, .dmg, .pkg signing + notarization |
| Windows | Authenticode | Microsoft Trusted Signing Basic | **$9.99/month** | .exe, .dll, .pyd, NSIS installer signing |

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
- **Latest release**: `qe-7.5-macos-arm64-openmp-20260223-10d20bf` (macOS arm64 OpenMP, verified portable)
- **115 commits**, PowerShell + Fortran + Python + CMake

### QMatSuite/QMatSuite (main repo)

- **Current version**: v1.2.0 (Updated 2026-02-24)
- **CI workflow**: `.github/workflows/tests.yml`
  - Matrix: Ubuntu 22.04 + macOS 14, Python 3.12
  - Builds QE 7.5 from source (cached), stages to `.qmatsuite/engines/qe/managed:qe-7.5:<os>`
  - Runs pytest (**6514 tests**) + Playwright E2E (**20 tests**)
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
| ase 3.27.0 | Atomic simulation (traj parser) | 11.3 MB | No | LAZY — trajectory I/O only |
| plotext 5.3.2 | Terminal plotting | 0.7 MB | No | LAZY — MCP renderer only |
| PyYAML 6.0.3 | YAML parsing | 0.8 MB | Yes (C loader) | CORE |
| typer 0.21.1 | CLI framework | 0.4 MB | No | CORE |
| ~~beautifulsoup4 4.14.3~~ | ~~HTML parsing~~ | ~~0.8 MB~~ | ~~No~~ | ✅ **Removed in v1.1.0** |
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
| ~~Dead dependencies~~ | ✅ Removed (beautifulsoup4); ase kept as lazy (traj parser) |
| Minimal startup set (if lazy) | ~43 MB |

All packages available on conda-forge, confirming conda-pack approach viability.
