# v1.2.2 Bug Fix Worklog

**Started**: 2026-02-26
**Reference**: `docs/history/reviews/V1_2_1_PRODUCTION_REVIEW.md`
**Branch**: `v2-python`

---

## Phase 1 — Trivial / One-Line Fixes

| # | Issue | Status | Commit |
|---|-------|--------|--------|
| 1 | P27 — SSSP `.to_dict()` serialization | DONE | 25064766 |
| 2 | P27 audit — other `_handle_*` missing `.to_dict()` | DONE (clean) | — |
| 3 | P32 — Demo gallery `encoding="utf-8"` | DONE | f8c6326a |
| 4 | P3 — Sidebar version `__APP_VERSION__` | DONE | fa06dfeb |
| 5 | P5 — Volume (DEV) production guard | DONE | 85e98c5a |
| 6 | P4 — Welcome text QE-centric | DONE | 8a3b9f3f |
| 7 | P20/P21 — Raw output `.name` → `str()` | DONE | b46ea0ee |
| 8 | P2 — "Up to date" banner feedback | DONE | 5c7fc22d |
| 9 | P33 — Demo "0 Si SCF" fix | SKIPPED (per user) | — |

## Phase 2 — Critical Functional Fixes

| # | Issue | Status | Commit |
|---|-------|--------|--------|
| 10 | P1 — Auto-update `disableDifferentialDownload` | DONE | 4386e192 |
| 11 | P35 — QE Resolver + `discover(persist=True)` | DONE | bc2025a3 |
| 12 | P6 — "titanium" → "Ti" element name detection | DONE | 08471340 |
| 13 | P10 — Pseudo update after structure change | DONE | 972707b1 |
| 14 | P9 — Structure selector re-fetch | DONE | af971abb |
| 15 | P11 — SSSP library scan (unblocked by P27) | DONE (no changes needed) | — |

## Phase 3 — Performance

| # | Issue | Status | Commit |
|---|-------|--------|--------|
| 16 | P30 — OPTIMADE lazy-load | DONE | 92bd04db |
| 17 | P29 — matplotlib MPLCONFIGDIR | DONE | 8438d728 |
| 18 | P31 — engine.list fast path | DONE | b7ba0f89 |

## Phase 4 — UX Polish

| # | Issue | Status | Commit |
|---|-------|--------|--------|
| 19 | P25 — macOS entitlements | BLOCKED (needs electron-builder.json5 change) | — |
| 20 | P23 — Sensitive path `~` replacement | DONE | 1578fc5b |
| 21 | P12 — Step dropdown labels | DONE | 4c42584a |
| 22 | P13 — Digest verbosity | DONE | a8e4a7c7 |
| 23 | P14 — Auto-select plot tab | DONE | 04c9f048 |

---

## Execution Log

### P27 — SSSP `.to_dict()` serialization
**Files**: `server.py:1025` — `status` → `status.to_dict()`
**Tests**: 69 passed | **Commit**: `25064766`
**Audit**: 112 `_handle_*` methods — no other missing `.to_dict()`

### P32 — Demo gallery encoding
**Files**: `service.py:8665` — added `encoding="utf-8"` to `open()`
**Tests**: 577 passed | **Commit**: `f8c6326a`

### P3 — Sidebar version
**Files**: `vite.config.ts` (define), `vite-env.d.ts` (declare), `Sidebar.tsx`
**Tests**: tsc clean | **Commit**: `fa06dfeb`

### P5 — Volume (DEV) guard
**Files**: `Sidebar.tsx`, `AppLayout.tsx` — `import.meta.env.DEV` guards
**Tests**: tsc clean | **Commit**: `85e98c5a`

### P4 — Welcome text
**Files**: `Sidebar.tsx`, `ProjectSummaryPanel.tsx` — 3 string replacements
**Tests**: tsc clean | **Commit**: `8a3b9f3f`

### P20/P21 — Raw output path
**Files**: `service.py:798` — `.name` → `str(artifact_path_obj)`
**Tests**: 69 passed | **Commit**: `b46ea0ee`

### P2 — Up-to-date banner
**Files**: `AppLayout.tsx` — added `not-available` to banner, useEffect auto-dismiss 5s
**Tests**: tsc clean | **Commit**: `5c7fc22d`

### P1 — Auto-update differential download
**Files**: `main.ts:149` — `autoUpdater.disableDifferentialDownload = true`
**Tests**: tsc clean | **Commit**: `4386e192`

### P35 — Engine registry persist
**Files**: `api/engines.py:78` — `persist=False` → `persist=True`
**Files**: `qe_resolver.py` docstring updated
**Tests**: 34 passed | **Commit**: `bc2025a3`

### P6 — Element name detection
**Files**: `io/online_search.py` — `_element_name_to_symbol()`, `_looks_like_formula()` before regex
**Tests**: 63 passed | **Commit**: `08471340`

### P10 — Species map rebuild
**Files**: `api/service.py:set_structure()` — rebuild species_map + SSSP auto-match
**Tests**: 320 passed | **Commit**: `972707b1`

### P9 — Structure selector refresh
**Files**: `AppLayout.tsx:handleCreateCalculationSuccess` — added `fetchStructures()`
**Tests**: tsc clean | **Commit**: `af971abb`

### P11 — SSSP library scan
**Result**: Unblocked by P27 fix. Library scan finds SSSP correctly. No code changes needed.

### P30 — OPTIMADE lazy-load
**Files**: `optimade.py:fetch_optimade_registry()` — return curated defaults when cache=None + refresh=False
**Tests**: 11 OPTIMADE tests pass, 4 updated to match lazy-load semantics | **Commit**: `92bd04db`

### P29 — matplotlib MPLCONFIGDIR
**Files**: `daemon/server.py:_set_mplconfigdir()` — set MPLCONFIGDIR at daemon entry (stdlib only, no kernel imports)
**Tests**: 354 passed, daemon kernel ban gate passes | **Commit**: `8438d728`

### P31 — engine.list fast path
**Files**: `api/engines.py:list_engines()` — load from cache, discover only when empty or refresh=True
**Files**: `daemon/server.py` — pass `refresh` param from payload
**Files**: `gui/src/hooks/useQMSClient.ts` + `SettingsPanel.tsx` + `types/qms.ts` — add refresh param, Refresh button sends discover=true
**Tests**: 14 engine RPC contract tests pass | **Commit**: `b7ba0f89`

### P23 — Sensitive path replacement
**Files**: `SettingsPanel.tsx` — `sanitizePath()` replaces home-dir prefix with `~` on all path displays
**Tests**: tsc clean | **Commit**: `1578fc5b`

### P12 — Step dropdown labels
**Files**: `CalculationOverviewTab.tsx:473-482` — prefix `[GEN_TYPE]` to dropdown options
**Tests**: tsc clean | **Commit**: `4c42584a`

### P13 — Digest verbosity
**Files**: `StepDigestPanel.tsx` — split into primary/secondary keys, collapsible toggle
**Tests**: tsc clean | **Commit**: `a8e4a7c7`

### P14 — Auto-select plot tab
**Files**: `CalculationAnalysisPanel.tsx:234-240` — auto setViewMode('analysis') when objects found
**Tests**: tsc clean | **Commit**: `04c9f048`

### P25 — macOS entitlements
**Status**: BLOCKED — requires electron-builder.json5 change (user ban)
