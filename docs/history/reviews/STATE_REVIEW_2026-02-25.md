# QMatSuite — Comprehensive State-of-the-Project Review

**Date**: 2026-02-25
**Version**: v1.2.0
**Branch**: `v2-python`
**Reviewer**: Automated (Claude Code) — all facts verified against live code/artifacts

---

## Executive Summary

QMatSuite v1.2.0 is a computational materials science workflow manager supporting 15 simulation engines, distributed as a Python package (PyPI) and an Electron desktop application (macOS arm64 + Windows x64). The v1.2.0 release completed the **runtime-in-app architecture shift** (Step 8), eliminating first-launch extraction delays by bundling the Python runtime as a plain directory inside the app.

### Key Metrics

| Metric | Value |
|--------|-------|
| Python source (src/) | ~152,700 LOC |
| Test code (tests/) | ~134,800 LOC across 623 files |
| Test count | 6,535 passed, 4 skipped |
| Engines supported | 15 |
| MCP tools | 32 |
| Preset variants | 24 |
| Pseudo libraries | 8 |
| Demo calculations | 80+ JSON-based |
| CI workflows | 5 |
| Gate tests | 68 (constitutional enforcement) |

---

## 1. Published Artifacts

### 1.1 PyPI

| Field | Value | Verified |
|-------|-------|----------|
| Package name | `qmatsuite` | Yes |
| Latest version | 1.2.0 | Yes — `pip install qmatsuite==1.2.0` succeeds |
| Python requirement | >=3.9 | Yes — pyproject.toml line 12 |
| Entry point | `qms` → `qmatsuite.cli:app` | Yes — pyproject.toml line 58 |

**Import verification** (clean venv, PyPI):
- `import qmatsuite` — PASS
- `from qmatsuite.daemon.server import main` — PASS
- `from qmatsuite.mcp.server import create_server` — PASS

### 1.2 GitHub Releases

**v1.2.0 is a published release** (not draft, not pre-release). Verified via `gh release view v1.2.0` on 2026-02-25.

| Release | Date | Assets |
|---------|------|--------|
| v1.2.0 (latest, **published**) | 2026-02-24 23:39:50 UTC | QMatSuite-macOS-1.2.0.dmg (287 MB), QMatSuite-Windows-1.2.0.exe (251 MB), blockmaps, latest-mac.yml, latest.yml |
| v1.1.0 (pre-release) | 2026-02-24 02:43:17 UTC | (QE download wiring) |
| v0.9.1 (pre-release) | 2026-02-24 01:13:30 UTC | — |
| v0.9.0 (pre-release) | 2026-02-24 01:06:13 UTC | — |

### 1.3 Toolchain Repository (QMatSuite/qmatsuite-toolchain)

- Latest release: `qe-7.5-macos-arm64-openmp-20260223-10d20bf` (macOS arm64 OpenMP, **verified portable** — see §4.5)
- Previous releases: `qe-7.5-win-oneapi-msmpi-20251223-d409e9b` (Windows MPI), `qe-7.5-win-oneapi-msmpi-libxc-20251223-a04eb07` (Windows MPI+libxc)
- Build matrix: Ubuntu, macOS, Windows (MinGW + Intel oneAPI)
- QE 7.5 + Wannier90 workflows

### 1.4 QE Windows Binaries (QMatSuite/quantum-espresso-windows-exe)

- Latest: `qe-7.5-win-oneapi-msmpi` (2025-12-23)
- Asset: `qe-7.5-win-oneapi-msmpi.zip` (400 MB, 156 downloads)
- Intel oneAPI + MKL + MS-MPI, Microsoft Trusted-Signed

---

## 2. Codebase Health

### 2.1 Version Consistency

| Location | Version | Status |
|----------|---------|--------|
| `pyproject.toml` | 1.2.0 | OK |
| `gui/package.json` | 1.2.0 | OK |
| `src/qmatsuite/__init__.py` | 1.2.0 | FIXED (was 1.0.1, corrected during this review) |
| PyPI | 1.2.0 | OK |
| GitHub release tag | v1.2.0 | OK |

> **Bug found and fixed**: `__init__.py.__version__` was still `"1.0.1"`. Updated to `"1.2.0"` during this review session and committed. The PyPI package metadata was uploaded from `pyproject.toml` (correct), so `importlib.metadata.version("qmatsuite")` returns `"1.2.0"`, but `qmatsuite.__version__` would have returned `"1.0.1"` at runtime. The fix is in the repo but the published PyPI package (v1.2.0) still has the old string — a v1.2.1 release would fix this for pip users.

### 2.2 Dependencies (pyproject.toml)

| Package | Purpose | Status |
|---------|---------|--------|
| numpy | Array operations | CORE |
| ase | Trajectory I/O parser | LAZY — intentionally kept (used in traj parser) |
| scipy | Scientific computing | Transitive via pymatgen; 1 direct lazy use |
| matplotlib | Plotting | CORE |
| plotext >=5.2 | Terminal plotting | LAZY — MCP renderer only |
| PyYAML | YAML parsing | CORE |
| typer >=0.12 | CLI framework | CORE |
| pymatgen >=2024.0.0 | Materials science | CORE |
| ulid-py >=1.1 | ULID generation | CORE |
| msgpack >=1.0.0 | Binary serialization | CORE |
| requests >=2.25.0 | HTTP client | CORE |
| certifi >=2023.7.22 | TLS certificates | CORE |
| portalocker >=2.8,<3 | File locking | CORE |
| jinja2 >=3.0.0 | Template engine | LAZY — LAMMPS writer only |
| fastmcp >=2,<3 | MCP server | CORE (MCP mode) |
| mp-api >=0.30.0 | Materials Project API | LAZY |

> **Note on `ase`**: The original distribution design doc incorrectly marked ase as "Removed in v1.1.0". It was intentionally kept because it is lazy-imported and used in the trajectory parser. The design doc has been corrected during this review.

### 2.3 Governance Structure

| Layer | Count | Purpose |
|-------|-------|---------|
| CONSTITUTION.md | 1 (554 lines) | Central constitution (L0) |
| L1 laws | 8 files | Binding architecture laws |
| L2 specs | 15 files | Binding operational rules |
| Gate tests | 68 files | CI enforcement of constitutional invariants |
| CLAUDE.md | 1 | AI assistant instructions |

---

## 3. Feature Inventory

### 3.1 Engine Drivers (15 engines)

All 15 engines have registered drivers under `src/qmatsuite/drivers/`:

| Engine | Phase B1 Status | Curated Samples | Output Parser | Metadata DB |
|--------|----------------|-----------------|---------------|-------------|
| QE | Complete | Yes | Yes | Yes (qe_module_parameters.json) |
| VASP | Complete | 12 cases | Yes (vasprun.xml + OUTCAR) | Yes (232 INCAR tags) |
| ORCA | Complete | 8 cases | Yes | Yes (120+ keywords) |
| LAMMPS | Complete | 8 cases | Yes | Yes (114 commands) |
| Gaussian | Complete | 10 cases | Yes | Yes (130 keywords) |
| ABINIT | Complete | 10 cases | Yes | Yes (170+ tags) |
| QMCPACK | Complete | 8 cases | Yes | Yes (65 tags) |
| CP2K | Complete | 10 cases | Yes | Yes (215 tags) |
| Siesta | Partial | — | — | — |
| Wannier90 | Partial | — | — | — |
| GPAW | Partial (Python-script) | — | — | — |
| Psi4 | Partial (Python-script) | — | — | — |
| PySCF | Partial (Python-script) | — | — | — |
| xTB | Partial | — | — | — |
| Yambo | Partial | — | — | — |

### 3.2 Engine Management System

The engine management system is **fully implemented** — all 7 Phase 2 roadmap items verified on 2026-02-25. The design doc previously marked these as "🔲 Not started" which was a major documentation drift.

#### Implementation Inventory

| Component | File | Lines | Status |
|-----------|------|-------|--------|
| Central registry | `core/engines/engine_registry.py` | 672 | ✅ Implemented |
| Engine metadata | `core/engines/engine_meta.py` | 267 | ✅ Implemented |
| Discovery (8-tier) | `core/engines/discovery.py` | 729 | ✅ Implemented |
| Installer (micromamba) | `core/engines/engine_installer.py` | 708 | ✅ Implemented |
| Micromamba interface | `core/engines/micromamba.py` | 344 | ✅ Implemented |
| Engine-specific resolvers | `*_resolver.py` (6 files) | ~764 | ✅ Implemented |
| API surface | `api/engines.py` | — | ✅ Implemented |
| Daemon RPC handlers | `daemon/server.py` (10 endpoints) | — | ✅ Implemented |
| GUI engine manager | `SettingsPanel.tsx:EngineManagementSection` | — | ✅ Implemented |
| **Total** | **22 files** | **4,270** | **Operational** |

#### Phase 2 Roadmap Verification

| Roadmap Item | Design Doc Said | Verified Status | Key Evidence |
|---|---|---|---|
| 2.1 `engines.json` registry | 🔲 Not started | ✅ Done | `EngineRegistry` class: load/save/add/remove/list/get_active/set_active, atomic writes, schema versioning |
| 2.2 QE resolver integration | 🔲 Not started | ✅ Done | `_resolve_qe_bin_dir_from_registry()` — registry-first lookup, falls back to legacy two-state |
| 2.3 All engine handlers | 🔲 Not started | ✅ Done | All 15 handlers use `engine_registry.get(family)` — no engine-specific path imports |
| 2.4 `list_engines` detection | 🔲 Not started | ✅ Done | `api/engines.py:list_engines()` — registry discovery + importlib/shutil.which fallback |
| 2.5 Micromamba integration | 🔲 Not started | ✅ Done | `micromamba.py` — platform-aware download, SHA256 verify, ad-hoc codesign (macOS), create/remove/list envs |
| 2.6 Daemon RPC endpoints | 🔲 Not started | ✅ Done | 10 handlers: engine.list, engine.verify, engine.set_active, engine.register_path, engine.unregister, engine.install, engine.uninstall, engine.list_installable, list_engine_families, set_engine_family |
| 2.7 GUI engine manager | 🔲 Not started | ✅ Done | Install/uninstall with real-time progress bar, verify, configure-path, switch active, job polling |

ENGINE_META covers all 15 engines with: display_name, engine_family, conda_package, binary names, version probing, supported source types (managed, system_path, custom_path).

Discovery priorities: env var → engines.json → managed install → system PATH → custom path → conda → module → venv.

### 3.3 MCP Server (32 Tools)

All 32 tools are fully implemented in `src/qmatsuite/mcp/tools/`:

| Category | Tools |
|----------|-------|
| **Project** | `init_project`, `cleanup_project`, `list_workflows` |
| **Structure** | `import_structure`, `list_structures`, `promote_structure`, `get_structure_detail`, `generate_kpath` |
| **Calculation** | `create_calculation`, `list_calculations`, `inspect_calculation`, `run_calculation`, `quick_run` |
| **Configuration** | `apply_preset`, `set_parameters`, `resolve_species_map`, `set_species_map`, `get_presets`, `search_parameters` |
| **Analysis** | `get_results_summary`, `plot_analysis`, `list_analyses` |
| **Engines** | `list_engines`, `download_pseudo_library` |
| **Knowledge** | `search_knowledge`, `preview_compilation` |
| **Demo/Resources** | `search_demos`, `get_demo_results`, `load_demo`, `list_available_resources` |
| **Status** | `get_status`, `ping` |

### 3.4 Preset System

- **Files**: 17 modules in `src/qmatsuite/presets/` (6,797 LOC)
- **Dimensions**: 4 (magnetism, occupations_scheme, precision, convergence)
- **Variants declared**: 24
- **Architecture**: Declarative catalog → IR compilation → engine-specific parameter application
- **Multi-engine support**: Yes (capability matrix per engine)

### 3.5 Pseudopotential Libraries

8 registered libraries in `src/qmatsuite/pseudo/registry.py`:

| Library | Directory | Default Variant |
|---------|-----------|-----------------|
| SSSP | SSSP | precision |
| PseudoDojo | PseudoDojo | nc-sr_pbe_standard |
| GBRV | GBRV | pbe |
| SG15 | SG15 | oncv |
| HGH | HGH | default |
| PS-Library | PS-Library | default |
| GIPAW | GIPAW | default |
| SCAN_TM | SCAN_TM | default |

Download pipeline: `pipeline.py` (download → verify → extract → manifest update).

### 3.6 Demo Store

- **Location**: `src/qmatsuite/resources/demo_projects/`
- **Format**: JSON-based metadata files (80+ files) with reference packs
- **Coverage**: All 15 engines represented
- **Access**: `search_demos`, `get_demo_results`, `load_demo` MCP tools

### 3.7 inputformat Package

| Phase | Status | Description |
|-------|--------|-------------|
| Phase A | Complete | Write orchestrator for all 15 engines, custom_writer content-role dispatch |
| Phase B0 | Complete | Parse orchestrator with merge strategies, VASP/ORCA/ABINIT custom parsers |

---

## 4. Distribution Architecture (v1.2.0)

### 4.1 Runtime-in-App (Step 8 — Complete)

The v1.2.0 release completed the runtime-in-app architecture shift:

| Aspect | Before (v1.1.0) | After (v1.2.0) |
|--------|------------------|-----------------|
| Runtime bundling | `runtime.tar.zst` (compressed) | `runtime/` directory (plain) |
| First-launch | 10-30s extraction overlay | Instant (0s) |
| zstd dependency | Bundled zstd binary + libzstd | None |
| afterPack hook | Required (rpath patching, codesigning) | None |
| Total disk usage | ~1.3 GB (app + AppData) | ~700 MB (app only) |
| DMG size (measured) | 296 MB | 284 MB |

### 4.2 Packaging Configuration

**electron-builder.json5**:
- `extraResources`: `runtime/` → `runtime/`
- No `afterPack` hook
- macOS: DMG (arm64), category `public.app-category.education`
- Windows: NSIS installer with `installer/conda-unpack.nsh` for path fixup

### 4.3 Python Path Resolution (main.ts `findPythonPath()`)

Priority order:
1. `QMS_DAEMON_PYTHON` env var
2. `.venv` / `venv` (dev checkout)
3. In-app runtime (`<resources>/runtime/`)
4. AppData runtime (v1.1.0 migration fallback)
5. System Python (fallback, marks `found: false`)

### 4.4 Code Signing

| Platform | Method | Signed Items |
|----------|--------|-------------|
| macOS | Apple Developer ID (electron-builder `--deep`) | 409 Mach-O files |
| Windows | Azure Trusted Signing | exe, dll, pyd (~394 files) |

### 4.5 QE macOS Binary Portability (Step 7A — Verified)

**Method**: Static analysis via `otool -L` on all Mach-O binaries in the latest toolchain release (`qe-7.5-macos-arm64-openmp-20260223-10d20bf`). This is the correct verification — running `pw.x` on this dev machine would prove nothing because Homebrew libraries are available locally.

**Toolchain asset**: `qe-7.5-macos-arm64-openmp.zip` (179 MB)

**Contents**: 89 Mach-O executables in `bin/`, 4 dylibs in `lib/`

**All unique dylib references across ALL 89 binaries**:

| Reference | Category | Portable? |
|-----------|----------|-----------|
| `@executable_path/../lib/libfftw3.3.dylib` | Bundled | ✅ Yes |
| `@executable_path/../lib/libgfortran.5.dylib` | Bundled | ✅ Yes |
| `@executable_path/../lib/libquadmath.0.dylib` | Bundled | ✅ Yes |
| `/System/Library/Frameworks/Accelerate.framework/Versions/A/Accelerate` | System framework | ✅ Yes |
| `/usr/lib/libSystem.B.dylib` | System | ✅ Yes |

**Bundled dylibs verified present**:

| Dylib | Size | Own dependencies |
|-------|------|-----------------|
| `libfftw3.3.dylib` | 696K | `@loader_path/` + `/usr/lib/libSystem.B.dylib` |
| `libgfortran.5.dylib` | 2.1M | `@loader_path/libquadmath.0.dylib`, `@loader_path/libgcc_s.1.1.dylib`, `/usr/lib/libSystem.B.dylib` |
| `libquadmath.0.dylib` | 356K | `@loader_path/` + `/usr/lib/libSystem.B.dylib` |
| `libgcc_s.1.1.dylib` | 216K | `@loader_path/` + `/usr/lib/libSystem.B.dylib` |

**Key notable binaries verified**: pw.x, ph.x, pp.x, bands.x, dos.x, projwfc.x, pw2wannier90.x, matdyn.x, q2r.x — all present, all clean.

**Verdict**: **✅ Step 7A VERIFIED — all 89 QE binaries are portable.** Zero Homebrew (`/opt/homebrew/`), MacPorts (`/opt/local/`), `/usr/local/`, or build-path (`/Users/`) references. All non-system libraries use `@executable_path/../lib/` pointing to bundled dylibs that are present in the archive. The `Accelerate.framework` reference is Apple's built-in BLAS/LAPACK (ships with every macOS installation).

---

## 5. CI/CD Workflows

| Workflow | File | Purpose |
|----------|------|---------|
| Tests | `tests.yml` | pytest (6500+ tests) + Playwright E2E (20 tests), Ubuntu + macOS, Python 3.12 |
| Release macOS | `release-macos.yml` | conda-pack runtime → DMG, code signing + notarization |
| Release Windows | `release-windows.yml` | conda-pack runtime → NSIS, Azure Trusted Signing (exe,dll,pyd) |
| Release PyPI | `release-pip.yml` | Build sdist/wheel → upload to PyPI |
| Build Runtime Dir | `build-runtime-dir.yml` | Standalone runtime build for testing |

---

## 6. Design Document vs Code Reality

Drift analysis between `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` and actual codebase. **Major drifts corrected during this review** (2026-02-25):

| Area | Design Doc Said | Code Reality | Status |
|------|----------------|--------------|--------|
| Engine management | "🔲 Mostly not started" (§3, §6, §7 Phase 2) | 4,270 LOC across 22 files, all Phase 2 items complete | **FIXED** — design doc §3, §6, §7 updated with verified statuses |
| QE macOS portability | "Step 7A incomplete — dylib bundling not portable" | 89 binaries verified portable via otool -L static analysis | **FIXED** — design doc §1.4, §6, §0.4 updated |
| `ase` dependency | "✅ Removed in v1.1.0" (§4.2, Appendix B) | Intentionally kept (lazy, traj parser) | **FIXED** — corrected in §4.2, Appendix B |
| Toolchain latest release | `qe-7.5-win-oneapi-msmpi-20251223-d409e9b` | `qe-7.5-macos-arm64-openmp-20260223-10d20bf` | **FIXED** — updated in Appendix A |
| MCP tools | Not detailed in design doc | 32 tools, fully implemented | Doc scope — not a distribution concern |
| Preset system | Not detailed in design doc | 6,797 LOC, 24 variants, 4 dimensions | Doc scope — not a distribution concern |
| Demo store | Not detailed in design doc | 80+ demos, 15 engines | Doc scope — not a distribution concern |
| Runtime architecture | Correctly documented (§1.2, §4.3) | Matches v1.2.0 implementation | OK |
| Code signing | Correctly documented (§8) | Matches (409 macOS, ~394 Windows) | OK |
| CI workflows | Correctly documented (§5) | Matches 5 workflows | OK |

---

## 7. Deleted Artifacts (Step 8 Cleanup — Verified)

All old runtime extraction infrastructure has been removed:

| Artifact | Status |
|----------|--------|
| `gui/scripts/afterPackSignZstd.cjs` | Deleted |
| `scripts/build_runtime_archive.py` | Deleted |
| `.github/workflows/build-runtime-tarball.yml` | Replaced by `build-runtime-dir.yml` |
| `getRuntimeTarballCandidates()` in main.ts | Deleted |
| `locateRuntimeTarball()` in main.ts | Deleted |
| `getBundledZstdPath()` in main.ts | Deleted |
| `validateBundledZstd()` in main.ts | Deleted |
| `extractWithBundledZstd()` in main.ts | Deleted |
| `extractRuntimeTarball()` in main.ts | Deleted |
| `findRuntimeRoot()` in main.ts | Deleted |
| Runtime setup overlay (App.tsx) | Deleted |
| `.runtime-setup-overlay` styles (App.css) | Deleted |
| `RuntimeSetupStatus` type (qms.ts) | Deleted |
| Runtime setup IPC (preload.ts) | Deleted |
| zstd staging steps (CI workflows) | Deleted |

---

## 8. Bugs Found and Fixed During This Review

| Bug | Severity | Status |
|-----|----------|--------|
| `__init__.py.__version__` = "1.0.1" (should be "1.2.0") | Medium | **Fixed** — edited and committed in repo. PyPI v1.2.0 still has old string; needs v1.2.1 for pip users. |
| Design doc marks `ase` as "Removed" (it's intentionally kept) | Low | **Fixed** — corrected in §4.2 and Appendix B |
| Design doc §3 "Not Started" for engine management (fully implemented) | Medium (doc-only) | **Fixed** — §3 rewritten with Phase 2 verification table, §6 gap analysis updated, §7 roadmap updated |
| Design doc §1.4 "Step 7A incomplete" (macOS QE portability) | Medium (doc-only) | **Fixed** — verified via otool -L static analysis (89 binaries, zero non-portable refs), §1.4 and §6 updated |
| Design doc toolchain latest release stale (pointed to Windows, not latest macOS) | Low | **Fixed** — updated to `qe-7.5-macos-arm64-openmp-20260223-10d20bf` |

---

## 9. Recommendations

### Immediate (pre-next-release)

1. ~~**Commit the `__version__` fix**~~ — ✅ Done. Fix committed in repo. PyPI v1.2.0 still has `"1.0.1"` at runtime; include fix in v1.2.1.

2. ~~**Update design doc §3**~~ — ✅ Done. Design doc §3, §6, §7 updated with verified Phase 2 status (all 7 items ✅ Done).

3. **Publish v1.2.1** — A patch release to fix `qmatsuite.__version__` on PyPI. The only code change is `__init__.py:14`.

### Near-term

4. **Version single-sourcing** — Consider reading version from `pyproject.toml` at build time (or use `importlib.metadata.version("qmatsuite")`) to prevent version string drift. The current three-location approach (pyproject.toml, package.json, `__init__.py`) is error-prone.

5. **Remaining Phase B1 engines** — Siesta, Wannier90, GPAW, Psi4, PySCF, xTB, Yambo still at partial maturity. Prioritize by user demand.

6. **MCP documentation** — The 32-tool MCP server is a major feature but has no dedicated section in the design doc. Consider adding a reference document.

7. **qmatsuite-full release** — Engine management (Phase 2) is complete. macOS QE binary is verified portable (Step 7A). The remaining work for the "full" release is packaging QE + SSSP into the installer (§1.3 of design doc).

### Low priority

8. **AppData cleanup** — Users upgrading from v1.1.0 have an unused `~/Library/Application Support/QMatSuite/runtime/` (~800 MB). A one-time cleanup in a future release would reclaim disk space.

9. **Legacy resolver stubs** — Several files in `core/engines/` are 6-12 line stubs (`qe_resolver.py`, `qe_installation.py`, `qe_pseudopotentials.py`, `qe_calculation.py`, `qe_binary_locator.py`, `qe.py`). Consider consolidation.

---

## 10. Test Suite

Tests were run during this review:

```
Command: source .venv/bin/activate && python -m pytest tests/ --tb=short -n auto --dist=loadfile -q
```

Results: **6,535 passed, 4 skipped, 0 failed** (368.96s, 70% coverage)

Note: Local count (6,535) differs slightly from CI (6,514) due to environment differences (CI skips tests requiring engines not installed in the runner). All tests pass.

---

## Appendix: Archived Reviews

This is the 15th review document in `docs/history/reviews/`. Previous reviews:

1. `AGENT_INFORMATION_SYSTEMS_AUDIT.md`
2. `ANALYSIS_PIPELINE_REVIEW.md`
3. `api_daemon_architecture_review.md`
4. `api_daemon_closeout_review.md`
5. `DEMO_STORE_AUDIT_20260220.md`
6. `engine-management-review-2026-02-24.md`
7. `LIST_PERFORMANCE_INVESTIGATION.md`
8. `PARAMETER_SYSTEM_AUDIT.md`
9. `PSEUDO_SYSTEM_DEEP_REVIEW.md`
10. `realrun_qe_pairs_1_5_independent_review_2026-02-15.md`
11. `RESOURCE_MANAGEMENT_REVIEW.md`
12. `RUNNER_SYSTEM_REVIEW.md`
13. `SI_BANDS_ISSUES_REVIEW.md`
14. `test_skips_investigation_2026-02-14.md`
