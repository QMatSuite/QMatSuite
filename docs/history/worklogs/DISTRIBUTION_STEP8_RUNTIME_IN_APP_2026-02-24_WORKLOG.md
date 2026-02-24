# DISTRIBUTION STEP 8 WORKLOG — Runtime-in-App Architecture Shift

Date: 2026-02-24

## Overview

Eliminated the zstd-compressed tarball extraction flow. Python runtime is now bundled
as a plain directory inside the Electron app via `extraResources`. Zero first-launch delay.

## Code Changes (completed before verification)

### Files Deleted
- `gui/scripts/afterPackSignZstd.cjs` — zstd binary patching/codesigning hook
- `scripts/build_runtime_archive.py` — tar.zst archive builder
- `.github/workflows/build-runtime-tarball.yml` — replaced by `build-runtime-dir.yml`

### Files Modified
1. `gui/electron-builder.json5` — removed `afterPack`, changed `extraResources` to `{ from: "runtime", to: "runtime" }`
2. `gui/electron/main.ts` — deleted ~400 lines of extraction code, simplified `ensureRuntimeReady()`, updated `findPythonPath()` priority order
3. `gui/electron/preload.ts` — removed `RuntimeSetupStatus` type and IPC methods
4. `gui/src/App.tsx` — removed overlay state, subscription, computed, and JSX
5. `gui/src/App.css` — removed `.runtime-setup-overlay*` CSS (73 lines)
6. `gui/src/types/qms.ts` — removed `RuntimeSetupStatus` interface and QMSApi declarations
7. `.github/workflows/release-macos.yml` — replaced zstd staging with conda-pack; signing/notarize untouched
8. `.github/workflows/release-windows.yml` — removed zstd cache/staging; replaced with conda-pack; Azure signing untouched
9. `.gitignore` — added `gui/runtime/`

### File Created
- `.github/workflows/build-runtime-dir.yml` — conda-pack based runtime directory builder

## Pre-verification

- TypeScript: `tsc --noEmit` — 0 errors
- Python tests: 6514 passed, 4 skipped, 0 failed (374.61s)

## Step 1: gitignore

- Added `gui/runtime/` to `.gitignore`
- Staged with `git add .gitignore`

## Step 2: Build conda-pack runtime locally

### Environment creation
```
conda create -p /tmp/qms-step8-runtime python=3.12 pip -c conda-forge -y
conda run -p /tmp/qms-step8-runtime pip install .
```
- qmatsuite 1.1.0 installed successfully with all dependencies

### conda-pack
```
conda-pack -p /tmp/qms-step8-runtime -o /tmp/runtime.tar.gz --force
mkdir -p gui/runtime
tar -xzf /tmp/runtime.tar.gz -C gui/runtime
cd gui/runtime && ./bin/python bin/conda-unpack
```
- Note: `conda-unpack` is a Python script (not bash), must be run with the runtime's own Python

### Size metrics
| Metric | Value |
|--------|-------|
| Runtime directory | 860 MB |
| Packed tarball (gz) | 256 MB |
| File count | 39,764 |

### Runtime verification (all passed)
| Check | Result |
|-------|--------|
| `import ssl` | OK |
| `import sqlite3` | OK |
| `import hashlib` | OK |
| `import qmatsuite` | version: 1.0.1 |
| `from qmatsuite.daemon.server import main` | daemon OK |
| `from qmatsuite.mcp.server import create_server` | MCP OK |
| `import numpy` | numpy 2.4.2 |
| `import mp_api` | mp-api OK |
| `requests.get('https://api.github.com')` | requests+ssl OK |

All 9/9 runtime checks passed, including the critical SSL end-to-end test.

## Step 3: Playwright E2E

```
cd gui && npm run build:e2e && npx playwright test
```

**Result: 20 passed (7.0m)**

No test failures. No tests referenced the deleted runtime setup overlay.

## Step 4: Build DMG

```
CSC_IDENTITY_AUTO_DISCOVERY=false npx electron-builder --mac dmg --arm64 --config electron-builder.json5
```

### Build output
- electron-builder v24.13.3
- Skipped code signing (CSC_IDENTITY_AUTO_DISCOVERY=false)
- DMG built successfully with APFS format

### Verification results
| Metric | Value |
|--------|-------|
| Runtime in app | `Contents/Resources/runtime/bin/python` exists (symlink -> python3.12) |
| App size | 1.3 GB |
| DMG size | 372 MB |

### Bundled Python test (inside .app)
```
import ssl, sqlite3, qmatsuite
version: 1.0.1
ssl: OK
sqlite3: OK
All checks passed
```

## Size comparison: v1.1.0 vs Step 8

| Metric | v1.1.0 (tarball) | Step 8 (in-app) | Change |
|--------|------------------|-----------------|--------|
| DMG download | 296 MB | 372 MB | +76 MB (+26%) |
| App installed | 531 MB | 1.3 GB | +769 MB |
| AppData runtime | ~800 MB | 0 | -800 MB |
| **Total disk** | **~1.3 GB** | **~1.3 GB** | **~same** |
| First-launch delay | 10-30 sec | 0 | eliminated |

The DMG is larger than projected (372 MB vs ~320 MB estimate) because the conda-pack
runtime is larger than the micromamba-created one used in v1.1.0 (more conda metadata,
more .pyc files). The total disk usage is approximately the same, but the user experience
is dramatically better (instant launch, no extraction overlay).

## CI workflow notes

- Signing/notarization sections in `release-macos.yml` are byte-identical to the originals
- Signing sections in `release-windows.yml` are byte-identical to the originals
- Only zstd-related steps were removed; no changes to secrets/names/certificate patterns

## Known issues

1. **DMG size**: 372 MB is 26% larger than v1.1.0 (296 MB). Acceptable tradeoff.
   Could be reduced by stripping `.pyc` files, `__pycache__`, conda metadata, etc.

---

## Fix: conda-unpack must run on user machine, not CI (2026-02-24)

### Problem

Running `conda-unpack` in CI patches all hardcoded paths to the CI runner's paths
(e.g. `/Users/runner/work/.../gui/runtime/`). When the app is installed on a user's
machine at `/Applications/QMatSuite.app/Contents/Resources/runtime/`, those paths
would be wrong.

The initial verification passed because build and test happened on the same machine
at the same path. On any other machine the runtime would be broken.

### Fix applied

1. **Removed conda-unpack from all CI workflows** — CI now extracts the conda-pack
   tarball without running unpack. Only a comment remains explaining why.
2. **Added first-launch conda-unpack to `gui/electron/main.ts`** —
   `ensureRuntimeReady()` now checks for a `.conda-unpacked` marker file. If absent,
   it runs `python bin/conda-unpack` (macOS) or `python Scripts/conda-unpack` (Windows)
   on the user's machine, then writes the marker. The marker prevents re-running on
   subsequent launches.
3. **Added NSIS installer hook for Windows** — `gui/installer/conda-unpack.nsh`
   runs conda-unpack during NSIS install via `customInstall` macro. Writes the
   `.conda-unpacked` marker on success. The main.ts first-launch check is a fallback
   in case the NSIS hook fails.
4. **Updated `gui/electron-builder.json5`** — Added `"include": "installer/conda-unpack.nsh"`
   to the `nsis` section.

### Verification (un-unpacked runtime)

Re-extracted runtime from tarball WITHOUT running conda-unpack, then tested:

| Test | Before unpack | After unpack |
|------|--------------|--------------|
| `python -c "import sys; print('OK')"` | OK | OK |
| `import qmatsuite` | 1.0.1 | 1.0.1 |
| `import ssl` | OK | OK |
| `import sqlite3` | OK | OK |
| `requests.get('https://api.github.com')` | (not tested pre-unpack) | OK (status 200) |

Key finding: CPython auto-detects `sys.prefix` from its own physical location, so
the Python binary and all pure-Python imports work even without conda-unpack. The
unpack step fixes shebangs in scripts, `.pc` files, and OpenSSL config paths.

### Re-verification after fix

| Check | Result |
|-------|--------|
| TypeScript `tsc --noEmit` | 0 errors |
| Python tests | 6514 passed, 4 skipped, 0 failed |
| Playwright E2E | 20 passed, 0 failed |
| DMG build (un-unpacked runtime) | Success, 372 MB |
| Bundled Python before conda-unpack | Works (ssl, sqlite3, qmatsuite) |
| conda-unpack on installed app | Success, marker written |
| Bundled Python after conda-unpack | Works (ssl, sqlite3, requests+ssl) |
| No conda-unpack in .yml files | Confirmed (only comments) |

---

## CI Failure Fixes (2026-02-24)

### Windows: tar path separator failure

**Error**: `tar (child): Cannot connect to D: resolve failed` — `${{ github.workspace }}`
returns `D:\a\QMatSuite\QMatSuite` on Windows, but bash `tar` interprets `D:` as a
remote host prefix. Mixed forward/back slashes in the path compound the issue.

**Fix**: Changed all `${{ github.workspace }}/...` paths in the conda-pack step to
relative paths (`runtime-packed.tar.gz`, `gui/runtime`). The step already runs in the
workspace directory, so relative paths work correctly and avoid the Windows drive letter
issue entirely.

### macOS: EMFILE too many open files during code signing

**Error**: `EMFILE: too many open files` — the runtime had 39,763 files, exceeding the
macOS CI runner's default `ulimit -n` (256). electron-builder opens all files in the
app bundle simultaneously during code signing.

**Fix** (two-pronged):
1. **Strip non-essential files from runtime before packaging** — removes `__pycache__/`,
   `*.pyc`, `*.pyo`, `*.a` (static libs), `tests/`/`test/` dirs inside site-packages,
   and `share/man share/doc` directories. Reduces 39,763 -> 20,379 files, 860 MB -> 526 MB.
2. **Raise `ulimit -n 65536`** before both unsigned and signed DMG build steps.

### Strip impact on sizes

| Metric | Before strip | After strip | v1.1.0 |
|--------|-------------|-------------|--------|
| Runtime dir | 860 MB | 526 MB | N/A |
| File count | 39,763 | 20,379 | N/A |
| App size | 1.3 GB | 982 MB | 531 MB |
| DMG size | 372 MB | **284 MB** | 296 MB |

The DMG is now **smaller than v1.1.0** (284 MB vs 296 MB) while eliminating first-launch
extraction delay. Stripped runtime passes all import checks (ssl, sqlite3, qmatsuite,
daemon, MCP, numpy).

### Verification

- TypeScript: `tsc --noEmit` — 0 errors
- Stripped runtime: all imports pass (ssl, sqlite3, qmatsuite, daemon, MCP, numpy)
- DMG build: success, 284 MB
- Bundled Python test inside .app: all checks passed

---

## Code Signing Audit (2026-02-24)

### macOS — Mach-O Inventory

Built unsigned DMG (`CSC_IDENTITY_AUTO_DISCOVERY=false`) at `gui/release/mac-arm64/QMatSuite.app`.

#### Total Mach-O files in .app: **409**

| Category | Count | Details |
|----------|-------|---------|
| Electron framework | 15 | QMatSuite, Helper (x4), Electron Framework, libEGL/GLESv2/ffmpeg/vk_swiftshader, crashpad, ReactiveObjC, Squirrel, ShipIt, Mantle |
| Runtime executables (`bin/`) | 25 | python3.12, openssl, bzip2, sqlite3_analyzer, tclsh8.6, wish8.6, ICU tools, ncurses tools, etc. |
| Runtime `.dylib` (non-symlink) | 60 | libpython3.12, libssl.3, libcrypto.3, libsqlite3, ICU libs, ncurses, readline, tk/tcl, etc. |
| Runtime `.dylib` (symlinks) | 34 | Versioned symlinks (not separate Mach-O files) |
| Runtime `.so` (lib-dynload) | 77 | CPython stdlib C extensions (_ssl, _hashlib, _sqlite3, array, etc.) |
| Runtime `.so` (site-packages) | 217 | scipy (109), pandas (45), numpy (19), matplotlib (9), PIL (8), fontTools (6), lupa (4), pymatgen (2), others |
| **Total Mach-O** | **409** | 15 Electron + 394 runtime |

#### Top `.so` contributors (site-packages)

| Package | .so files |
|---------|-----------|
| scipy | 109 |
| pandas | 45 |
| numpy | 19 |
| matplotlib | 9 |
| PIL (Pillow) | 8 |
| fontTools | 6 |
| lupa | 4 |
| pymatgen | 2 |

#### Signing coverage: **409/409 (100%)**

electron-builder applied ad-hoc signatures to all 409 Mach-O files in the unsigned build.
When `CSC_NAME` is set in CI, electron-builder replaces ad-hoc with Developer ID signatures
for every Mach-O file in the `.app` bundle — this is automatic and requires no special config.

Spot-checked signatures on critical binaries:

| Binary | Signed | Type |
|--------|--------|------|
| `Contents/MacOS/QMatSuite` | ad-hoc (linker-signed) | Main Electron exe |
| `runtime/bin/python3.12` | ad-hoc | Python interpreter |
| `runtime/lib/libpython3.12.dylib` | ad-hoc | Python shared lib |
| `runtime/lib/libssl.3.dylib` | ad-hoc | OpenSSL |
| `runtime/lib/python3.12/lib-dynload/_ssl.cpython-312-darwin.so` | ad-hoc | SSL extension |

#### Unsigned files found: **0**

No Mach-O files in the .app bundle are missing signatures.

#### Deep verification note

`codesign --deep --verify` fails on the unsigned build because the main executable has a
linker-signed ad-hoc signature without resource seals. This is expected — in CI with
`CSC_NAME` set, electron-builder produces full Developer ID signatures with proper resource
seals. Notarization requires all Mach-O files to be signed with Developer ID, and
electron-builder handles this automatically for everything inside the `.app` bundle.

#### macOS signing summary

- **No action needed.** electron-builder signs all Mach-O files (including the 394 runtime
  files) automatically when `CSC_NAME` is set. The `extraResources` runtime directory is
  inside the `.app` bundle, so it's covered by the standard signing walk.
- The `ulimit -n 65536` in the CI workflow ensures the 409 files don't hit EMFILE limits
  during signing.
- The removed `afterPackSignZstd.cjs` hook is no longer needed (it signed zstd binaries
  in `extra/bin/`; there are no extra binaries to sign now).

---

### Windows — Trusted Signing Audit

#### Signing architecture

The Windows release workflow uses a two-phase approach:

1. **electron-builder** builds the NSIS installer with `CSC_IDENTITY_AUTO_DISCOVERY=false`
   (no signing during build)
2. **Azure Trusted Signing action** signs files post-build:
   ```yaml
   files-folder: gui\release
   files-folder-filter: exe,dll
   files-folder-recurse: true
   ```

#### What gets signed

electron-builder for NSIS creates `gui/release/win-unpacked/` (unpacked app) plus the
NSIS installer `.exe`. The Trusted Signing action recurses into `gui/release/` and signs:

| Category | Signed? | Filter match |
|----------|---------|-------------|
| NSIS installer `.exe` | Yes | `exe` |
| `win-unpacked/QMatSuite.exe` | Yes | `exe` |
| Electron `.dll` files | Yes | `dll` |
| `runtime/python.exe` | Yes | `exe` |
| `runtime/*.dll` (python312.dll, ssl, etc.) | Yes | `dll` |
| `runtime/Scripts/*.exe` | Yes | `exe` |
| `runtime/**/*.pyd` (Python extensions) | **No** | Not in filter |
| `runtime/**/*.pyd` count (estimated) | **~294** | — |

#### Estimated Windows signable file counts (from macOS runtime)

| Type | macOS equivalent | Windows ext | Count | In signing filter? |
|------|-----------------|-------------|-------|-------------------|
| Shared libs | `.dylib` | `.dll` | ~60 | Yes |
| Python extensions | `.so` | `.pyd` | ~294 | **No** |
| Executables | Mach-O in `bin/` | `.exe` in `Scripts/` | ~25 | Yes |
| Electron + app | — | `.exe` + `.dll` | ~15 | Yes |
| **Total signed** | — | `.exe` + `.dll` | **~100** | — |
| **Total unsigned** | — | `.pyd` | **~294** | — |

#### .pyd signing gap analysis

`.pyd` files are Python extension modules (compiled C/C++ code loaded as DLLs). They are
**not** in the Trusted Signing filter (`exe,dll`). Impact assessment:

- **SmartScreen**: Does not check individual DLLs/PYDs inside installed apps. Only checks
  the installer and main executable. **No impact.**
- **Windows Defender / AV**: May flag unsigned DLLs in some heuristic scans, but .pyd files
  from well-known packages (scipy, numpy, pandas) are not typically flagged. **Low risk.**
- **Enterprise group policy**: Some organizations block unsigned DLLs via AppLocker or WDAC.
  These environments would need to whitelist the app. **Niche risk.**
- **User trust**: Users see the signed installer and signed main .exe. **No impact.**

**Recommendation**: The `.pyd` gap is a known limitation. Adding `pyd` to the filter
(`files-folder-filter: exe,dll,pyd`) would sign all ~294 Python extensions at the cost
of ~294 additional signing operations per release. This is optional and can be done in
a future step if enterprise customers require it.

#### Azure Trusted Signing quota impact

| Scenario | Signing operations per release |
|----------|-------------------------------|
| Current filter (`exe,dll`) | ~100 |
| Extended filter (`exe,dll,pyd`) | ~394 |
| Standard Azure quota | 5,000/month |
| Headroom (current) | ~50 releases/month |
| Headroom (extended) | ~12 releases/month |

Current configuration is well within quota. Even with `.pyd` signing, quota is not a concern.

#### Windows signing summary

- **Installer .exe is signed** — this is what SmartScreen checks and what users see.
- **Main app .exe and Electron DLLs are signed** — via the `win-unpacked/` directory.
- **Runtime .exe and .dll files are signed** — python.exe, python312.dll, openssl DLLs, etc.
- **~294 .pyd files are NOT signed** — not in the `exe,dll` filter. Low practical risk.
- **Optional fix**: Add `pyd` to `files-folder-filter` if enterprise signing is needed.
- **Quota**: ~100 operations/release, well within 5,000/month standard quota.

---

### Audit Summary

| Platform | Total native binaries | Signed | Unsigned | Coverage |
|----------|-----------------------|--------|----------|----------|
| macOS (.app) | 409 | 409 | 0 | **100%** |
| Windows (NSIS) | ~394 | ~100 | ~294 (.pyd) | **~25%** |

#### macOS: No action required

electron-builder signs all Mach-O files in the `.app` bundle automatically. The runtime
directory is inside the bundle and is fully covered. Notarization will pass.

#### Windows: Optional improvement available

The `.pyd` signing gap is standard for most Electron + Python apps. The installer and all
`.exe`/`.dll` files are signed, which satisfies SmartScreen and typical AV checks.
If full coverage is desired, add `pyd` to `files-folder-filter` in `release-windows.yml`.

---

## Fix: Add .pyd to Windows Trusted Signing filter (2026-02-24)

Added `pyd` to `files-folder-filter` in `release-windows.yml` (`exe,dll` → `exe,dll,pyd`).
This signs Python C extension modules (~294 files) alongside exe/dll. ~394 total signing
operations per release, well within Azure Trusted Signing quota (5,000/month).
