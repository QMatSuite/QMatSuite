# Worklog: Close MCP + Cross-Platform Distribution Design

**Date:** 2026-02-21
**Branch:** v2-python

---

## Phase 1: Close MCP — DONE

### Actions
- Read existing DEFERRED_ITEMS.md (136 lines, 6 sections)
- Read Round 3 REVIEW.md (261 lines, 8 sections, 6 remaining issues)
- Rewrote DEFERRED_ITEMS.md as canonical backlog with 6 sections:
  1. Completed items (reference only) — 13 items
  2. High priority — 4 items (opctx gap, ENGINE_CRASH enrichment, knowledge base expansion, VASP preflight)
  3. Medium priority — 11 items (parser chain, search_knowledge adoption, post-run hints, dry_run regression, ecutwfc check, demo gate, CP2K circular import, search upgrade, ref pack, history query, engine preflight)
  4. Low priority — 12 items (binary detection, search cache, preset normalization, PrecisionAdvisor, XYZ format, subtitle gate, demo benchmarks, QE metadata, progress visibility, severity grouping, knowledge injection, search_knowledge test task)
  5. Phase 2+ future — 7 items (engine preflights, knowledge packs, auto-knowledge, Materials Project, ML potentials, additional demos, contributing guide)
  6. Non-MCP architecture — 4 items (cross-platform paths, Electron packaging, Python bundling, unified engine registry)

---

## Phase 2: Codebase Investigation — DONE

### 2a: Engine Discovery

**Key findings:**
- QE has a sophisticated two-state resolver in `drivers/qe/engine/qe_resolver.py`:
  - State 1 (External): `settings.qe.bin_dir` → validate `pw.x` exists → use
  - State 2 (Internal): Auto-select from `.qmatsuite/engines/qe/**/bin/` (sort by mtime)
  - Fallback: `shutil.which("pw.x")` on PATH (deprecated)
  - Error: `RuntimeError` with actionable message
- Other engines: No managed discovery. xTB catches `FileNotFoundError` and suggests `conda install`. VASP similar to QE. ORCA/Gaussian assume PATH.
- Runner is fully engine-agnostic: `DriverRegistry.get_handler(step_type_spec)` → handler closure
- Binary validation is deferred to execution time (not registration time)
- `ESPRESSO_PSEUDO` set to `project/pseudo/` by Step0 before engine execution
- `OMP_NUM_THREADS` defaulted to 1 if not set

**Files examined:**
- `src/qmatsuite/drivers/qe/engine/qe_resolver.py` — two-state resolution
- `src/qmatsuite/drivers/qe/engine/qe_engine.py` — executable lookup
- `src/qmatsuite/drivers/qe/engine/qe_calculation.py` — subprocess invocation
- `src/qmatsuite/calculation/runner.py` — engine-agnostic runner
- `src/qmatsuite/execution/handlers.py` — handler map creation
- `src/qmatsuite/core/driver_registry.py` — central registry
- `src/qmatsuite/drivers/xtb/handler.py` — xTB subprocess pattern
- `src/qmatsuite/drivers/vasp/handler.py` — VASP handler

### 2b: File Layout

**Key findings:**
- All paths via `src/qmatsuite/core/paths.py` (203 lines):
  - `get_repo_root()`: walks up from `__file__` looking for `pyproject.toml` + `src/qmatsuite/`
  - `get_qmatsuite_home_root()`: `<repo_root>/.qmatsuite/`
  - `get_qmatsuite_tmp_root()`: `<repo_root>/.tmp/`
  - 13 subdirectory helpers (config, engines, seeds, libraries, logs, pseudo, qe-specific, tmp-*)
- **Critical gap**: `get_repo_root()` FAILS for pip-installed packages (no `pyproject.toml` in site-packages)
- No `QMATSUITE_HOME` env var support exists
- No platform-specific path logic (no `sys.platform` checks, no `Application Support`, no `LOCALAPPDATA`)
- Pseudopotential layout: `.qmatsuite/libraries/pseudo/SSSP/<variant>/<version>/` (3-level: library/variant/version)
- Resources in `resources/pseudo/` (bundled, committed) vs `.qmatsuite/libraries/pseudo/` (installed, gitignored)
- `resources/pseudo_libinfo/CURRENT` points to asset tag dir with `MANIFEST_PSEUDO_SEED.json`

### 2c: Packaging State

**Key findings:**
- `pyproject.toml`: package `qmatsuite`, version 1.0.1, entry point `qms = "qmatsuite.cli:app"`
- Build: setuptools + wheel, Python >=3.9
- 14 core deps (numpy, scipy, pymatgen, matplotlib, ase, etc.), 4 optional groups (dev, pyscf, mp-api, mcp)
- No `setup.py` / `setup.cfg` / `MANIFEST.in`
- Electron: `gui/` directory with React 18 + Vite 7 + Electron 39 + TypeScript + Three.js
- `electron-builder.json5`: PLACEHOLDER values (`YourAppID`, `YourAppName`), dmg + nsis + AppImage targets
- `electron/main.ts` (865 lines): spawns `python -m qmatsuite.daemon.server` as subprocess
  - Python discovery: `QMS_DAEMON_PYTHON` → `.venv/bin/python` → `venv/bin/python` → system `python`
  - JSON-RPC over stdio, 60s timeout, log forwarding
- CI: `.github/workflows/tests.yml` — Ubuntu + macOS, builds QE from source, stages to `.qmatsuite/engines/qe/managed:qe-7.5:<os>`, runs pytest + Playwright E2E
- No PyInstaller, Nuitka, or any binary packaging config exists
- No Electron auto-update, no code signing

### 2d: External References

**quantum-espresso-windows-exe:**
- QE 7.5 Windows binary, Intel oneAPI + MKL + MS-MPI
- `qe-7.5-win-oneapi-msmpi.zip` (400MB, 156 downloads)
- Microsoft Trusted-Signed, SHA256 verified, GitHub Artifact Attestation

**qmatsuite-toolchain:**
- CI build recipes for QE 7.5 + Wannier90 3.1.0
- Platforms: Ubuntu, macOS, Windows (MinGW + Intel oneAPI)
- 9 workflow files, 115 commits
- Latest release: `qe-7.5-win-oneapi-msmpi-20251223-d409e9b`

---

## Phase 3: Design Document — DONE

Wrote `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` with 6 sections + 2 appendices:

1. **Distribution Channels**: 3 channels (pip, lite, full) with installation flows and platform support
2. **Cross-Platform File Layout**: Current state analysis, target state with platform-aware paths, `paths.py` redesign with `QMATSUITE_HOME` + Electron + pip mode resolution
3. **Engine Management**: Unified `engines.json` registry with 4 source types (bundled, micromamba, system_path, user_path), engine metadata, discovery flow, micromamba integration, QE version management
4. **Python Backend Packaging**: Evaluated 3 options (PyInstaller, Nuitka, Embedded Python via micromamba). Recommended Option C (micromamba-embedded Python) — natural fit with engine management, full extensibility, ~500MB for Python + scientific stack
5. **Gap Analysis**: 10-row table comparing current state → target state with gap sizes
6. **Roadmap**: 4 phases, 21 work packages with complexity estimates (S/M/L)
   - Phase 1: Foundation (paths.py refactor, pip install) — 4 items
   - Phase 2: Engine Management (registry, micromamba, GUI) — 7 items
   - Phase 3: Electron Distribution (builds, bundling, signing) — 9 items
   - Phase 4: Polish (auto-update, Linux AppImage, offline installer) — 6 items

Appendix A: External repo reference
Appendix B: Dependency inventory (~190MB total, all on conda-forge)

---

## Deliverables

1. `docs/plans/DEFERRED_ITEMS.md` — Canonical backlog (6 sections, 51 items)
2. `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` — Architecture design (6 sections + 2 appendices)
3. `WORKLOG.md` — This file
