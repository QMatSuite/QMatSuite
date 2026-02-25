# Engine Management Full-Stack Review

**Date**: 2026-02-24
**Reviewer**: Claude Code
**Scope**: Backend + Frontend engine management system
**Design Doc Reference**: `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` §3

---

## Executive Summary

The engine management system has been implemented **far beyond what the design doc anticipated**. At design time (2026-02-21), the gap analysis described engine management as "Large" gaps requiring new modules and data models. Three days later, a substantial implementation exists: a persistent `engines.json` registry, ENGINE_META for all 15 engines, micromamba bootstrap + conda environment creation, GitHub Release download with SHA256 verification, a full RPC layer with async job management, and a React GUI with install/uninstall/verify/configure-path functionality.

However, the "Download/Install does nothing" bug has multiple contributing causes. The primary issue is **inadequate progress feedback** — the UI shows only a text label ("install in progress...") with no progress bar, no download speed, and no ETA during what can be a 5-20 minute operation. Secondary issues include: (1) a **checksum filename mismatch** that silently skips SHA256 verification, (2) **no timeout on micromamba subprocess execution** allowing potential indefinite hangs, (3) the **JobManager single-worker bottleneck** that queues engine installs behind any running calculation, and (4) the **60-second RPC timeout** in the Electron main process which could cause the initial RPC call to fail if the job submission itself is slow.

The design doc's architecture has been faithfully implemented in its core concepts (6 source types, engines.json registry, ENGINE_META, micromamba integration, discovery flow). The remaining gaps are primarily in production readiness: no bundled engine support (full release), no QE version management UI, and incomplete error surfacing from background jobs.

---

## 1. Design Baseline

Extracted from `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` §3.1–§3.10:

### 1.1 Six Source Types (§3.3)

| Source | Description | Example |
|--------|------------|---------|
| `bundled` | Shipped with qmatsuite-full release | QE 7.5 in full release |
| `micromamba` | Installed via built-in conda manager | xTB, CP2K, PySCF, Psi4, GPAW |
| `github_release` | Downloaded from QMatSuite GitHub Releases | QE OpenMP/MPI variants |
| `system_path` | Found on system PATH via `shutil.which()` | Any engine via apt/brew |
| `user_path` | User-specified binary path | VASP, Gaussian (licensed) |
| `user_venv` | User-specified Python venv (Python engines only) | User's own PySCF venv |

### 1.2 engines.json Registry (§3.2)

JSON registry at `<app_data>/config/engines.json` tracking all installations with schema:
- `schema_version: 1`
- Per-engine: `installations[]` array + `active` installation ID
- Per-installation: `id`, `source`, `version`, `path`/`python_executable`, `required_binaries`, `env_vars`, `verified` timestamp

### 1.3 ENGINE_META (§3.4)

Static metadata dictionary for all 15 engines defining: `display_name`, `engine_type`, `required_binaries`, `optional_binaries`, `version_command`, `version_regex`, `conda_package`, `conda_channel`, `env_vars`, `bundleable`.

### 1.4 Discovery Flow (§3.5)

1. Load existing engines.json
2. Scan bundled: `<app_data>/engines/<engine>/<variant>/bin/`
3. Scan micromamba: `<app_data>/micromamba/envs/*/`
4. Scan system PATH: `shutil.which()` per engine
5. Merge with existing registry (keep user_path, add new, mark stale)
6. Version check each installation
7. Write updated engines.json

### 1.5 Micromamba Integration (§3.6)

Micromamba (~5MB static binary) for one-click engine installation. Supports 10 conda-installable engines (8 binary + 3 Python). Environment layout at `<app_data>/micromamba/envs/<engine>-<version>/`.

### 1.6 QE Version Management (§3.7)

Multiple QE versions coexist under `<app_data>/engines/qe/`. User can switch active version. Old versions persist for reproducibility.

### 1.7 Python Engine Subprocess Isolation (§3.8)

Python engines (PySCF, Psi4, GPAW) run in separate Python interpreters via subprocess. PYTHONPATH injection allows the engine's Python to import qmatsuite. Three source types: micromamba, user_venv, dev_fallback.

### 1.8 GitHub Release Download (§3.9)

1. Query GitHub API: `GET /repos/QMatSuite/qmatsuite-toolchain/releases`
2. Match platform + variant asset
3. Download to cache
4. Verify SHA256
5. Extract to `<app_data>/engines/qe/<install_id>/`
6. Register in engines.json

### 1.9 QE Resolver → Registry Migration (§3.10)

Replace QE-specific two-state resolver with unified registry lookup:
- State 1 (external) → `user_path` in engines.json
- State 2 (internal) → `bundled` or `micromamba` in engines.json

### 1.10 Gap Analysis at Design Time (§5)

The design doc identified these as "Large" gaps: engine discovery (unified registry), micromamba integration, Python bundling. "Medium" gaps: path management, Electron packaging, GUI engine manager panel.

---

## 2. Backend: Engine Registry & Resolution

### 2.1 Three Registry Layers

The codebase has three distinct registry systems:

| Layer | Module | Purpose | Persistence |
|-------|--------|---------|-------------|
| **Distribution Registry** | `src/qmatsuite/core/engines/engine_registry.py` | Track installations & active selection | `engines.json` |
| **Driver Registry** | `src/qmatsuite/core/driver_registry.py` | Map engines to driver code (handlers, recipes) | In-memory singleton |
| **Legacy Simple Registry** | `src/qmatsuite/engine/registry.py` | Minimal in-memory engine list | None |

The Distribution Registry is the new one designed in §3.2. The Driver Registry is the existing kernel infrastructure. The Legacy Registry is unused legacy code.

### 2.2 Distribution Engine Registry

**File**: `src/qmatsuite/core/engines/engine_registry.py` (672 lines)

**Schema**: Matches design doc exactly.
```json
{
  "schema_version": 1,
  "engines": {
    "<family>": {
      "installations": [...],
      "active": "<installation_id>"
    }
  }
}
```

**Key implementation details**:
- Registry path: `<app_data>/config/engines.json` (line 96)
- Active source priority (lines 22-29): `user_path > user_venv > bundled > micromamba > github_release > system_path`
- Discovery scanners (lines 337-461): `_scan_bundled()`, `_scan_micromamba()`, `_scan_system_path()`
- Binary resolution (lines 56-69): Cross-platform variant handling (`.x` ↔ `.exe` ↔ `.x.exe`)

### 2.3 Path Resolution

**File**: `src/qmatsuite/core/paths.py` (233 lines)

`get_app_data_dir()` (lines 94-115) implements the design doc's resolution chain exactly:
1. `QMATSUITE_HOME` env var
2. Dev mode (repo root + `.qmatsuite/`)
3. Electron mode (`QMATSUITE_ELECTRON=1` → platform app-data dir)
4. Fallback (`~/.qmatsuite/`)

`get_cache_dir()` (lines 118-139): Parallel chain for scratch/cache.

**Status**: Fully implemented as designed. The old `get_repo_root()` still exists but `get_app_data_dir()` provides the platform-aware fallback.

### 2.4 Engine Metadata

**File**: `src/qmatsuite/core/engines/engine_meta.py` (268 lines)

All 15 engines defined in `ENGINE_META` dictionary. Fields match design doc plus two additions:
- `primary_binary_unix` / `primary_binary_windows` (platform-specific binary names)
- `binary_detection_order` (for engines with multiple binary variants like CP2K)

Helper functions: `get_platform_primary_binary()` (line 238), `get_detection_binaries()` (line 246).

### 2.5 Settings

**File**: `src/qmatsuite/core/settings.py` (198 lines)

Settings stored in `<app_data>/config/settings.json`. The `QEConfig.bin_dir` field provides backward compatibility with the two-state QE resolver. Settings and engine registry are separate files (not merged).

### 2.6 list_engines Real Installed Detection

**File**: `src/qmatsuite/api/engines.py` (lines 56-91)

`list_engines()` now performs real detection:
1. Runs `EngineRegistry.discover(persist=False)` — scans bundled, micromamba, system_path
2. For each engine, checks active installation. If active and not stale → installed
3. Falls back to `_engine_installed_via_fallback()` (line 44): Python import check or `shutil.which()`

**Status**: No longer always-true. Real detection implemented. The design doc's §3.1 noted this was a deferred item (L1) — now resolved.

### 2.7 QE Resolver Integration

**File**: `src/qmatsuite/drivers/qe/engine/qe_resolver.py` (239 lines)

The QE resolver now has a **three-state** model (evolved from the design doc's two-state):
1. **State 1 (Registry)**: `EngineRegistry.get_active("qe")` — NEW, highest priority (line 193-199)
2. **State 2 (External)**: `settings.qe.bin_dir` — existing settings path (line 211-219)
3. **State 3 (Internal)**: `find_internal_qe_bin_dir()` — auto-scan `.qmatsuite/engines/qe/**/bin` (line 221-229)

The registry is checked first, then falls through to the legacy two-state model. This preserves backward compatibility while enabling the new registry.

### 2.8 Other Engine Binary Resolution

Other engines follow a consistent pattern:

**Registry-first, graceful fallback:**
```python
try:
    from qmatsuite.core.engines.engine_registry import resolve_active_binary
    resolved = resolve_active_binary("<engine>", binary_name="<binary>")
    if resolved and resolved.is_file():
        return str(resolved)
except Exception:
    pass
# Fallback to shutil.which() or bare name
```

Verified in:
- xTB: `drivers/xtb/recipe.py` (lines 79-87) — resolves at materialization time
- Siesta: `drivers/siesta/handler.py` (lines 37-51) — resolves at execution time
- ABINIT: Similar pattern to Siesta

### 2.9 Version Probing

**File**: `src/qmatsuite/core/engines/version_probe.py` (47 lines)

Safe version detection using isolated temp directories. Prevents QE from creating transient files (CRASH, input_tmp.in) in the CWD. Enforces timeouts (default 10s, configurable).

---

## 3. Backend: QE GitHub Release Download

### 3.1 Download Implementation

**File**: `src/qmatsuite/core/engines/engine_installer.py` (604 lines)

**GitHub repo**: `QMatSuite/qmatsuite-toolchain` (line 34, constant `QE_RELEASE_REPO`)

**Platform mapping** (lines 289-309):

| Platform | Constructed variant string |
|----------|--------------------------|
| Windows x64 | `win-oneapi-msmpi` |
| macOS arm64 | `macos-arm64-openmp` (or `mpi`) |
| macOS x64 | `macos-x64-openmp` (or `mpi`) |
| Linux x64 | `linux-x64-openmp` (or `mpi`) |

**Asset selection logic** (lines 311-362):
1. Constructs `tag_prefix = f"qe-{version}-{platform_variant}"` (e.g., `qe-7.5-macos-arm64-openmp`)
2. Queries GitHub API: `GET /repos/QMatSuite/qmatsuite-toolchain/releases?per_page=100`
3. Finds first release where `tag_name == tag_prefix` or `tag_name.startswith(f"{tag_prefix}-")`
4. Within that release, finds asset matching `f"{tag_prefix}.zip"`
5. Also looks for `f"{tag_prefix}.zip.sha256"` for checksum

### 3.2 Actual Toolchain Releases

Fetched from `https://github.com/QMatSuite/qmatsuite-toolchain/releases`:

| Tag | Asset | Size | Date |
|-----|-------|------|------|
| `qe-7.5-macos-arm64-openmp-20260223-10d20bf` | `qe-7.5-macos-arm64-openmp.zip` | 179 MB | 2026-02-23 |
| `qe-7.5-win-oneapi-msmpi-20251223-d409e9b` | `qe-7.5-win-oneapi-msmpi.zip` | 382 MB | 2025-12-23 |
| `qe-7.5-win-oneapi-msmpi-libxc-20251223-a04eb07` | `qe-7.5-win-oneapi-msmpi-libxc.zip` | 389 MB | 2025-12-23 |

All releases include `checksums.txt` (NOT `<asset>.sha256`).

### 3.3 Quantum ESPRESSO Windows EXE Repo

Fetched from `https://github.com/QMatSuite/quantum-espresso-windows-exe/releases`:

| Tag | Asset | Size | Downloads |
|-----|-------|------|-----------|
| `qe-7.5-win-oneapi-msmpi` | `qe-7.5-win-oneapi-msmpi.zip` | 382 MB | 163 |

Mirror of toolchain Release 2 with simplified tag (no date/SHA suffix). Same file, same checksums.

### 3.4 Asset Naming Match Analysis

**Tag matching**: Code constructs `tag_prefix = "qe-7.5-macos-arm64-openmp"`. Actual tag is `qe-7.5-macos-arm64-openmp-20260223-10d20bf`. The code checks `tag.startswith(f"{tag_prefix}-")` (line 324) → **MATCHES** ✓

**Asset matching**: Code looks for `qe-7.5-macos-arm64-openmp.zip`. Actual asset is `qe-7.5-macos-arm64-openmp.zip` → **MATCHES** ✓

**Windows matching**: Code constructs `tag_prefix = "qe-7.5-win-oneapi-msmpi"`. Actual tag is `qe-7.5-win-oneapi-msmpi-20251223-d409e9b`. Starts with prefix → **MATCHES** ✓

### 3.5 BUG: Checksum Filename Mismatch

**Severity: HIGH (security)**

The code at line 339 looks for a checksum asset named `f"{asset_name}.sha256"`:
- Expected: `qe-7.5-macos-arm64-openmp.zip.sha256`
- Actual: `checksums.txt`

Since no asset matches `*.sha256`, `checksum_asset` is `None`, `checksum_url` is empty string `""`, and `_verify_or_download_sha256()` (line 262-264) returns immediately because `not checksum_url` evaluates to `True`.

**Result**: SHA256 verification is silently skipped for all QE GitHub Release downloads. Downloads proceed without integrity verification.

### 3.6 Download Robustness Assessment

| Concern | Status | Detail |
|---------|--------|--------|
| Asset discovery | Regex + prefix match | Robust — handles date-suffixed tags |
| GitHub rate limiting | No handling | `_download_text()` uses plain urllib; 60 req/hr unauthenticated limit |
| Download interruption | No resume support | Full re-download on retry; no partial file cleanup |
| SHA256 verification | **Silently skipped** | Checksum filename mismatch (see §3.5) |
| Post-download registration | Implemented | Writes to engines.json + sets active |
| Extraction path | Correct | `<app_data>/engines/qe/github-<version>-<variant>/` matches resolver scan |

### 3.7 Auto-Source Selection Subtlety

**File**: `src/qmatsuite/api/engines.py` (lines 185-193)

When user clicks "Install" with `source: "auto"`, the selection logic is:
```python
if ENGINE_META[family].get("conda_package"):
    selected_source = "conda"
elif family == "qe":
    selected_source = "github_release"
```

Since QE has `conda_package: "qe"` in ENGINE_META, **the auto source always selects conda for QE**, not github_release. The GitHub Release download path only activates when explicitly requested with `source="github_release"`.

This means the default QE install flow is: micromamba bootstrap → conda-forge download (~200MB QE package). The pre-built GitHub Release binary (which is signed, checksummed, and platform-optimized) is NOT used by default.

---

## 4. Backend: Micromamba Engine Installation

### 4.1 Micromamba Module

**File**: `src/qmatsuite/core/engines/micromamba.py` (256 lines)

**Micromamba binary**: Downloaded from `mamba-org/micromamba-releases` tag `2.5.0-2` (line 25).

**Platform assets** (lines 45-69):

| Platform | Asset Name |
|----------|-----------|
| macOS arm64 | `micromamba-osx-arm64` |
| macOS x64 | `micromamba-osx-64` |
| Linux x64 | `micromamba-linux-64` |
| Linux arm64 | `micromamba-linux-aarch64` |
| Windows x64 | `micromamba-win-64.exe` |

**Bootstrap flow** (`ensure_micromamba()`, lines 131-178):
1. Check if `<app_data>/micromamba/bin/micromamba` exists → return if yes
2. Download binary to temp `.download` file
3. Download SHA256 checksum, verify → proper `<asset>.sha256` naming used here
4. Stage to `.staged` file
5. macOS: ad-hoc codesign (`codesign --force --sign -`)
6. Move to final path

**SHA256 verification for micromamba**: Correctly implemented. Micromamba releases DO publish `<asset>.sha256` sidecar files.

### 4.2 Conda Environment Creation

**Function**: `create_env()` (lines 204-223)

```python
run_micromamba(["create", "--yes", "--name", env_name, "-c", channel, *packages], app_data_dir)
```

For Python engines, adds `python=3.12` to the package list.

**Environment path**: `<app_data>/micromamba/envs/<engine>-<sanitized_version>/`

### 4.3 BUG: No Timeout on micromamba create

**Severity: HIGH (reliability)**

The `run_micromamba()` function (line 181-201) calls `subprocess.run()` with no `timeout` parameter. Conda package resolution and download can hang indefinitely if:
- conda-forge CDN is slow or unreachable
- Package resolver encounters a conflict
- Network connection stalls

The `_download_binary()` function in micromamba.py has `timeout=120` (socket timeout for micromamba binary download), but the actual `micromamba create` command has no timeout. This can cause engine install jobs to stay in "running" state forever.

### 4.4 Python Engines (PySCF, Psi4, GPAW)

Subprocess isolation is implemented as designed in §3.8:
- Each Python engine gets its own micromamba environment with `python=3.12 + <package>`
- Verification via `python -c "import <module>; print(<module>.__version__)"`
- PYTHONPATH injection in engine adapters for qmatsuite imports

The three source types (micromamba, user_venv, dev_fallback) are all supported via the registry.

---

## 5. Backend: BYOE (Bring Your Own Engine)

### 5.1 User-Configured Paths

**RPC method**: `engine.register_path` (daemon/server.py lines 1444-1472)

**Flow**:
1. User provides `engine_family` + `path` (absolute directory containing binary)
2. Backend validates: for binary engines, checks `required_binaries` exist in path
3. For Python engines, finds Python executable in the directory/venv
4. Registers in engines.json with `source: "user_path"` or `source: "user_venv"`
5. Sets as active installation

**GUI support**: "Configure Path" button in SettingsPanel.tsx (line 704-711) opens a directory picker via Electron's `dialog.showOpenDialog()`, then calls `engine.register_path`.

### 5.2 System PATH Discovery

System PATH discovery via `shutil.which()` is implemented in the registry's `_scan_system_path()` method (engine_registry.py lines 440-461). It runs during discovery (on demand, not on startup).

All 15 engines support system PATH fallback — it's the lowest-priority source type.

---

## 6. Frontend: Engine Management UI

### 6.1 Components

**Primary component**: `gui/src/components/panels/SettingsPanel.tsx` (1615 lines)

The `EngineManagementSection` component (lines 367-743) renders:
- Engine list with install status, version, source type
- "Install" button for engines with auto-install methods (conda/github_release)
- "Configure Path" button for manual BYOE
- "Verify" button to test current installation
- "Uninstall" button (only for micromamba/github_release installations)
- Installation selector dropdown (when multiple installations exist)

**State management**: React `useState` hooks (no Redux/Zustand):
- `engineRows`: Current engine status from `engine.list` RPC
- `installableRows`: Available install methods from `engine.list_installable` RPC
- `pendingJobs`: Active install/uninstall operations keyed by engine name
- `rowNotices`: Success/error messages per engine row

### 6.2 Download/Install UI Flow

1. **User clicks "Install"** (line 694-701) → calls `handleInstall(engine)` (line 477)
2. **Immediate UI update**: Button changes to "Installing...", pending job set to `__pending__`
3. **RPC call**: `qms.installEngine(engine, { async: true, source: 'auto' })` (line 483)
4. **Backend returns**: `{ job_id: "...", status: "pending" }` immediately
5. **Polling starts**: `useEffect` hook polls `get_job_status` every 2 seconds (line 463-465)
6. **Progress display**: Shows `pending.message` text ("install in progress...") (line 662-664)
7. **Completion**: On job `completed`/`failed`, refreshes engine data and shows notice

### 6.3 Progress Feedback Gap

**This is a key contributor to the bug.** The progress UI consists of:
- Button text: "Installing..." (no spinner animation)
- Row text: `pending.message` which is one of:
  - "Starting install..." (initial)
  - "Install queued..." (after job_id received)
  - "install in progress..." (during execution, from line 443)
  - The last log line from the job (but engine install jobs don't write output files)

**Missing**: No progress bar, no download percentage, no file size indicator, no ETA. For a 200MB download that can take 5-20 minutes, this provides minimal user feedback.

### 6.4 RPC Client

**File**: `gui/src/hooks/useQMSClient.ts`

Engine-related methods:
| Method | RPC | Purpose |
|--------|-----|---------|
| `listEngines()` | `engine.list` | Get all engines with status |
| `listInstallableEngines()` | `engine.list_installable` | Get available install methods |
| `installEngine()` | `engine.install` | Start async install |
| `uninstallEngine()` | `engine.uninstall` | Start async uninstall |
| `verifyEngine()` | `engine.verify` | Test current installation |
| `setActiveEngineInstallation()` | `engine.set_active` | Switch active version |
| `registerEnginePath()` | `engine.register_path` | Register user path |

---

## 7. RPC/API Layer

### 7.1 Complete RPC Endpoint Inventory

**File**: `src/qmatsuite/daemon/server.py`

| Method | Handler | Lines | Async | Progress |
|--------|---------|-------|-------|----------|
| `engine.list` | `_handle_engine_list` | 1398-1408 | No | N/A |
| `engine.list_installable` | `_handle_engine_list_installable` | 1391-1396 | No | N/A |
| `engine.verify` | `_handle_engine_verify` | 1410-1420 | No | N/A |
| `engine.set_active` | `_handle_engine_set_active` | 1422-1442 | No | N/A |
| `engine.register_path` | `_handle_engine_register_path` | 1444-1472 | No | N/A |
| `engine.unregister` | `_handle_engine_unregister` | 1474-1494 | No | N/A |
| `engine.install` | `_handle_engine_install` | 1496-1534 | Yes (default) | Via job polling |
| `engine.uninstall` | `_handle_engine_uninstall` | 1536-1580 | Yes (default) | Via job polling |
| `engine.path` | alias for `engine.register_path` | — | No | N/A |

### 7.2 Async Job Management

**File**: `src/qmatsuite/daemon/jobs.py` (708 lines)

`JobManager` uses `ThreadPoolExecutor(max_workers=1)` for sequential execution. Jobs track:
- Status: `pending → running → completed/failed/cancelled`
- Timestamps: `created_at`, `started_at`, `completed_at`
- Output: `result`, `error`, `error_traceback`, `last_log_line`

**Critical limitation**: `max_workers=1` means only one job runs at a time. If a calculation is running, engine install waits in queue. This is by design (prevents resource contention) but can confuse users.

### 7.3 Complete Lifecycle Sequence

```
USER CLICKS "Install QE"
  ↓
SettingsPanel.tsx: handleInstall("qe")
  ↓
useQMSClient: call('engine.install', {engine_family:'qe', async:true, source:'auto'})
  ↓
preload.ts: ipcRenderer.invoke('qms-request', {id, type:'engine.install', payload})
  ↓
main.ts: ipcMain.handle('qms-request') → sendDaemonRequest()
  ↓
DAEMON STDIN: {"id":"req-...","type":"engine.install","payload":{...}}\n
  ↓
server.py: _handle_engine_install() → job_manager.submit(install_wrapper)
  ↓
DAEMON STDOUT: {"id":"req-...","ok":true,"data":{"job_id":"...","status":"pending"}}\n
  ↓
main.ts: handleDaemonLine() → resolve pending promise
  ↓
SettingsPanel.tsx: setPendingJobs({qe: {jobId, action:'install', message:'Install queued...'}})
  ↓
[BACKGROUND THREAD in daemon]
  install_wrapper() → api.install_engine("qe", source="auto")
    → selected_source = "conda" (QE has conda_package)
    → micromamba.ensure_micromamba()     [downloads ~5MB micromamba if needed]
    → micromamba.create_env("qe-latest", ["qe"], ["conda-forge"])
      → subprocess.run(["micromamba", "create", ...])   [downloads ~200MB QE]
    → _verify_binary_engine("qe", bin_dir)
    → EngineRegistry.add_installation() + set_active()
  ↓
[POLLING every 2 seconds]
  SettingsPanel.tsx: qms.call('get_job_status', {job_id})
    → job.status: "running", last_log_line: null
    → UI shows: "install in progress..."
  ↓
[JOB COMPLETES]
  job.status = "completed", job.result = {engine:'qe', source:'conda', installation:{...}}
  ↓
  SettingsPanel.tsx: detects completion → refreshEngineData() → UI updates
```

---

## 8. Download Bug Analysis

### Root Cause Hypotheses

#### H1: Inadequate Progress Feedback (CONFIRMED — PRIMARY)

**Evidence**:
- `engine_installer.py:_download_binary()` (line 57-61) uses blocking `urllib.request.urlopen()` with `shutil.copyfileobj()` — no progress callback
- `micromamba.py:run_micromamba()` (line 181-201) uses blocking `subprocess.run()` — no stdout streaming
- `jobs.py:Job.output_file` is `None` for engine install jobs — no log file to tail
- `jobs.py:Job.last_log_line` stays `None` throughout the install — nothing to show
- Frontend shows only static text "install in progress..." with no visual progress indicator

**Impact**: User sees "install in progress..." for 5-20 minutes with no indication that anything is actually happening. No download speed, no percentage, no bytes transferred. This matches the bug description exactly: "no progress bar, no status feedback."

#### H2: Checksum Filename Mismatch (CONFIRMED — SECURITY)

**Evidence**:
- `engine_installer.py` line 339: looks for `f"{asset_name}.sha256"` (e.g., `qe-7.5-macos-arm64-openmp.zip.sha256`)
- Actual GitHub releases publish `checksums.txt`, not `<asset>.sha256`
- `checksum_asset` is always `None`, `checksum_url` is always `""`
- `_verify_or_download_sha256()` (line 262-264): `if not checksum_url: return` → verification silently skipped

**Impact**: All QE GitHub Release downloads proceed without SHA256 verification. Not a functional blocker but a security gap.

#### H3: No Timeout on micromamba subprocess (CONFIRMED — RELIABILITY)

**Evidence**:
- `micromamba.py:run_micromamba()` (line 200-201): `subprocess.run(full_cmd, env=env, **kwargs)` with no `timeout` parameter
- Conda package resolution can stall on slow networks, mirror issues, or solver conflicts
- If `micromamba create` hangs, the job stays in "running" state indefinitely

**Impact**: Potential indefinite hang. User sees "install in progress..." forever. Matches the bug description: "After waiting a long time, the engine never transitions to 'installed' state."

#### H4: JobManager Single-Worker Queue (CONTRIBUTING)

**Evidence**:
- `jobs.py` line 130: `ThreadPoolExecutor(max_workers=1)`
- If a calculation is already running, engine install stays "pending"
- Frontend shows "Install queued..." but user may not understand why

**Impact**: If a long-running calculation is in progress, engine install doesn't start until it finishes. This could explain "nothing happens" if the user doesn't realize a job is already running.

#### H5: 60-Second RPC Timeout (UNLIKELY)

**Evidence**:
- `main.ts` line 103: `REQUEST_TIMEOUT_MS = 60000`
- The `engine.install` RPC with `async: true` returns immediately (just submits to job queue)
- Timeout would only affect the initial submission, not the download itself

**Impact**: Unlikely to be triggered for async installs. Could be triggered for sync installs (`async: false`), but the frontend always uses `async: true`.

#### H6: Platform-Specific Download Failure (POSSIBLE)

**Evidence**:
- No Linux QE binary exists in toolchain releases
- macOS x64 (Intel) QE binary doesn't exist as GitHub Release (only arm64)
- The `resolve_qe_github_release_asset()` would raise `RuntimeError` for these platforms
- But `source: "auto"` selects conda (not github_release), so this path isn't used by default

**Impact**: If a user explicitly selects github_release source on an unsupported platform, the install fails. But the default "auto" flow uses conda, so this is unlikely.

#### H7: GitHub API Rate Limiting (POSSIBLE)

**Evidence**:
- `engine_installer.py:_download_text()` (line 64-66) uses unauthenticated GitHub API requests
- Rate limit: 60 requests/hour for unauthenticated users
- If user has been making other GitHub API requests (or other apps are), the API call could fail
- No retry logic or rate-limit detection

**Impact**: Could cause the GitHub release asset lookup to fail. Would result in a job failure, which the frontend should display as an error notice. Only affects github_release source, not conda.

### Summary of Root Causes

| # | Hypothesis | Confidence | Severity | Impact |
|---|-----------|------------|----------|--------|
| H1 | No progress feedback | **Confirmed** | **CRITICAL** | User thinks nothing is happening |
| H2 | Checksum filename mismatch | **Confirmed** | HIGH | SHA256 verification silently skipped |
| H3 | No micromamba timeout | **Confirmed** | HIGH | Potential indefinite hang |
| H4 | Single-worker queue | **Contributing** | MEDIUM | Install delayed by running jobs |
| H5 | 60s RPC timeout | **Unlikely** | LOW | Only for sync calls |
| H6 | Platform mismatch | **Possible** | LOW | Only for explicit github_release |
| H7 | GitHub rate limiting | **Possible** | LOW | Only for github_release source |

---

## 9. Design vs. Implementation Gap Analysis

| Design Doc Feature | Section | Implementation Status | Gap Description | Severity |
|---|---|---|---|---|
| Unified engines.json registry | §3.2 | **Implemented** | Full CRUD + persistence at `<app_data>/config/engines.json` | — |
| ENGINE_META metadata | §3.4 | **Implemented** | All 15 engines, all fields, plus platform-specific extensions | — |
| Discovery flow (6 source types) | §3.5 | **Implemented** | bundled + micromamba + system_path scanners. user_path/user_venv via register. github_release via manual download. | — |
| Micromamba integration | §3.6 | **Implemented** | Bootstrap, env creation, env removal, SHA256 verification, macOS ad-hoc signing | No timeout on `micromamba create` |
| QE version management | §3.7 | **Partially implemented** | Multiple installs tracked in registry, active switching via RPC. No GUI for version management, no "QE 7.6 available" prompts | MEDIUM |
| Python engine subprocess isolation | §3.8 | **Implemented** | micromamba env creation, python_executable tracking, PYTHONPATH injection in engine adapters | — |
| GitHub Release download | §3.9 | **Implemented** | API query, platform mapping, download, extraction, registration. Checksum file naming bug. | HIGH (checksum) |
| QE resolver → registry migration | §3.10 | **Implemented** | Three-state model: registry → settings → auto-scan. Registry is highest priority. | — |
| GUI engine manager panel | §5 gap table | **Implemented** | Install, uninstall, verify, configure path, set active. No progress bar. | CRITICAL (UX) |
| list_engines real installed detection | §3.1 | **Implemented** | Registry-first detection with fallback to shutil.which/python import | — |
| Bundled engine support | §3.3 | **Not implemented** | `_scan_bundled()` scanner exists but no bundling in installer | LOW (pre-release) |
| `get_app_data_dir()` platform-aware | §2.3 | **Implemented** | Full resolution chain: env var → repo root → Electron → home dir | — |
| Electron `findPythonPath()` | §4.5 | **Partially implemented** | Priority 1-5 chain exists. No Nuitka slot (reserved). No micromamba runtime lookup. | MEDIUM |
| Auto source selects conda for QE | — | **Implementation choice** | Design implies GitHub Release is primary for QE; code defaults to conda | MEDIUM (design drift) |

---

## 10. Recommendations

### Immediate Fixes (needed to make download/install functional)

1. **Add download progress reporting to engine install jobs**
   - Modify `_download_binary()` in engine_installer.py to stream with a callback that updates job progress
   - Add a `progress` field to `Job` dataclass (percentage, bytes downloaded, total bytes)
   - Expose progress in `get_job_status` response
   - Frontend: render a progress bar in `engine-manager-row__progress` div
   - *This is the single highest-impact fix for the reported bug*

2. **Add timeout to `run_micromamba()` calls**
   - Add `timeout=900` (15 minutes) to `subprocess.run()` in `micromamba.py:run_micromamba()`
   - Handle `subprocess.TimeoutExpired` by cleaning up partial environment and failing the job
   - Prevents indefinite hangs

3. **Fix checksum filename mismatch**
   - In `resolve_qe_github_release_asset()` line 339, also check for `checksums.txt` asset
   - Parse `checksums.txt` to find the line matching the target asset name
   - Alternatively, publish per-asset `.sha256` sidecar files in toolchain CI

### Short-Term Improvements (needed before release)

4. **Add stdout/stderr streaming from micromamba to job logs**
   - Modify `run_micromamba()` to use `subprocess.Popen()` with stdout/stderr piping
   - Write micromamba output to a log file accessible via `job.output_file`
   - Frontend already polls `last_log_line` — this would show conda resolution/download progress

5. **Show queue position when jobs are blocked**
   - When JobManager has a running job and a new install is pending, return queue position in `get_job_status`
   - Frontend: show "Waiting for <running_job> to complete (queue position: 1)"

6. **Add GitHub API authentication**
   - Support `GITHUB_TOKEN` environment variable for authenticated API requests
   - Increases rate limit from 60 to 5000 requests/hour
   - Add rate-limit detection and retry-after handling

7. **Add download resume support**
   - Use `Range` header for partial downloads
   - Keep partial files in download cache
   - Resume from where interrupted

### Architecture Alignment (bring implementation closer to design)

8. **Default QE install to github_release, not conda**
   - The pre-built QE binary from toolchain is signed, platform-optimized, and known-good
   - Conda-forge QE may have different build options, different linked libraries
   - Change `install_engine()` to prefer `github_release` for QE when `source="auto"`
   - Fall back to conda only if no GitHub release matches the platform

9. **Implement bundled engine scanning**
   - The `_scan_bundled()` method in engine_registry.py exists but needs a bundling mechanism
   - For qmatsuite-full: include QE binary in installer, register as `source: "bundled"` during first launch

10. **Add Nuitka/compiled daemon priority in findPythonPath()**
    - Priority 3 slot is reserved but not implemented
    - Low priority — implement when Nuitka build is available

### Design Doc Updates

11. **Update §3.9 to note actual checksum naming**: Document that releases publish `checksums.txt`, not per-asset `.sha256` files

12. **Update §3.10 to reflect three-state model**: The resolver now has registry → settings → auto-scan (three states, not two)

13. **Add progress reporting design**: §3 should specify the progress reporting mechanism for long-running installs (job polling with progress fields)

14. **Document auto-source selection logic**: §3.6/§3.9 should clarify that conda is preferred over github_release for engines that support both

---

## Appendix: Files Examined

### Backend — Core Engine Infrastructure
| File | Lines Examined | Purpose |
|------|---------------|---------|
| `src/qmatsuite/core/engines/engine_registry.py` | 1-672 (full) | Distribution engine registry |
| `src/qmatsuite/core/engines/engine_meta.py` | 1-268 (full) | Static engine metadata |
| `src/qmatsuite/core/engines/engine_installer.py` | 1-604 (full) | Install/uninstall orchestration |
| `src/qmatsuite/core/engines/micromamba.py` | 1-256 (full) | Micromamba binary management |
| `src/qmatsuite/core/engines/version_probe.py` | 1-47 (full) | Safe version detection |
| `src/qmatsuite/core/engines/discovery.py` | 1-300+ | Tiered discovery system |
| `src/qmatsuite/core/paths.py` | 1-233 (full) | Path resolution |
| `src/qmatsuite/core/settings.py` | 1-198 (full) | Settings management |
| `src/qmatsuite/core/driver_registry.py` | 1-300+ | Driver-to-engine mapping |
| `src/qmatsuite/engine/registry.py` | 1-95 | Legacy simple registry |

### Backend — API & Daemon
| File | Lines Examined | Purpose |
|------|---------------|---------|
| `src/qmatsuite/api/engines.py` | 1-249 (full) | API-facing engine operations |
| `src/qmatsuite/daemon/server.py` | 214-255, 1391-1580, 4157-4230 | RPC handlers |
| `src/qmatsuite/daemon/jobs.py` | 1-708 (full) | Background job manager |

### Backend — QE Engine
| File | Lines Examined | Purpose |
|------|---------------|---------|
| `src/qmatsuite/drivers/qe/engine/qe_resolver.py` | 1-239 (full) | QE binary resolution |
| `src/qmatsuite/drivers/qe/engine/qe_engine.py` | 100-232 | QE engine instance |

### Backend — Other Engine Handlers
| File | Lines Examined | Purpose |
|------|---------------|---------|
| `src/qmatsuite/drivers/xtb/recipe.py` | 79-87 | xTB binary resolution |
| `src/qmatsuite/drivers/siesta/handler.py` | 37-51 | Siesta binary resolution |

### Frontend
| File | Lines Examined | Purpose |
|------|---------------|---------|
| `gui/src/components/panels/SettingsPanel.tsx` | 360-810 | Engine management UI |
| `gui/src/hooks/useQMSClient.ts` | 408-468 | RPC client |
| `gui/electron/main.ts` | 40-103, 402-450, 474-700, 775-807 | Electron main process |
| `gui/electron/preload.ts` | 1-317 | IPC bridge |

### External
| Resource | Method | Purpose |
|----------|--------|---------|
| `github.com/QMatSuite/qmatsuite-toolchain/releases` | WebFetch + GitHub API | Release asset inventory |
| `github.com/QMatSuite/quantum-espresso-windows-exe/releases` | WebFetch + GitHub API | Mirror release inventory |

### Design Doc
| File | Sections | Purpose |
|------|----------|---------|
| `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` | §1-§7 (full, 1499 lines) | Design baseline |
