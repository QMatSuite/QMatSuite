# V1.2.1 Bugfix Implementation Audit

**Date**: 2026-02-26
**Auditor**: Claude Code (automated source verification)
**Trigger**: Discovery that `_unescape_content` CIF import fix was tested locally but never committed to source. This audit checks every v1.2.1/v1.2.2 bugfix for the same pattern.

---

## Summary

- **19 / 22** fixes verified present in git at HEAD
- **1** fix was missing and has been restored (`_unescape_content`)
- **2** fixes intentionally deferred (P25 blocked, P33 skipped per user)
- **1** fix on separate unmerged branch (P35)

---

## Per-Issue Status

| P# | Description | Commit | In HEAD? | Status |
|----|-------------|--------|----------|--------|
| P1 | Disable differential download | d5b7a259 | Yes | Verified |
| P2 | "Up to date" banner + 5s dismiss | 552c1931 | Yes | Verified |
| P3 | Version from package.json via Vite | 828a982a | Yes | Verified |
| P4 | QE-centric welcome text replaced | 8418b7a9 | Yes | Verified |
| P5 | Volume DEV hidden in production | 1e04d43c | Yes | Verified |
| P6 | Element name parsing | ad0d2045 | Yes | Verified |
| P9 | Structure selector refresh | 5d102f16 | Yes | Verified |
| P10 | Pseudo update after structure change | 56a3eb0b | Yes | Verified |
| P11 | SSSP library scan | (P27 dep) | Yes | Verified (no standalone fix needed) |
| P12 | Gen-type labels in Add Step | 186e81d5 | Yes | Verified |
| P13 | Collapse secondary digest fields | 8a16e47f | Yes | Verified |
| P14 | Auto-switch to Plot tab | b58e31a4 | Yes | Verified |
| P20/P21 | Preserve relative path in artifact read | 3a784a16 | Yes | Verified |
| P23 | Home dir path leak → tilde | e64d7107 | Yes | Verified |
| P25 | macOS entitlements | — | No | BLOCKED (documented) |
| P27 | SSSP `.to_dict()` serialization | f29c3303 | Yes | Verified |
| P29 | matplotlib MPLCONFIGDIR | 65d751c9 | Yes | Verified |
| P30 | OPTIMADE lazy-load | 94f47629 | Yes | Verified |
| P31 | engine.list fast path | a93701d7 | Yes | Verified |
| P32 | UTF-8 encoding on `open()` | 6b29d3cd | Yes | Verified |
| P33 | Demo YAML titles | — | No | SKIPPED (per user) |
| P35 | Engine resolution unification | a7a0d4f0 | No | Separate branch |
| CIF | `_unescape_content` | — | **Was missing** | **RESTORED** |

---

## Detailed Verification

### Phase 1 — Core Fixes

#### P27 — SSSP serialization `.to_dict()` — VERIFIED
- **Commit**: f29c3303
- **File**: `src/qmatsuite/daemon/server.py:1025`
- **Evidence**: `_handle_get_library_status()` returns `status.to_dict()`, not raw dataclass
- **No concerns**

#### P32 — UTF-8 encoding on `open()` — VERIFIED
- **Commit**: 6b29d3cd
- **File**: `src/qmatsuite/api/service.py:8705`
- **Evidence**: `open(snapshot_path, "r", encoding="utf-8")` in `list_demo_projects()`
- **No concerns**

#### P3 — Version from package.json via Vite define — VERIFIED
- **Commit**: 828a982a
- **Files**: `gui/vite.config.ts:10`, `gui/src/vite-env.d.ts:3`, `gui/src/components/Sidebar.tsx:303`
- **Evidence**: `define: { __APP_VERSION__: JSON.stringify(pkg.version) }`, Sidebar uses `{__APP_VERSION__}`
- **No concerns**

#### P4 — QE-centric welcome text replaced — VERIFIED
- **Commit**: 8418b7a9
- **Files**: `gui/src/components/panels/ProjectSummaryPanel.tsx:106,132`, `gui/src/components/Sidebar.tsx:276`
- **Evidence**: Three QE-specific strings replaced with engine-agnostic text
- **No concerns**

#### P5 — Volume DEV hidden in production — VERIFIED
- **Commit**: 1e04d43c
- **Files**: `gui/src/components/Sidebar.tsx:283-294`, `gui/src/components/AppLayout.tsx:741,884`
- **Evidence**: Three `import.meta.env.DEV` guards wrap Volume UI elements
- **No concerns**

#### P20/P21 — `.name` → full relative path — VERIFIED
- **Commit**: 3a784a16
- **File**: `src/qmatsuite/api/service.py:798`
- **Evidence**: `file_path = raw_dir_resolved / str(artifact_path_obj)` (not `.name`)
- **Security**: Path traversal protection via `is_relative_to()` check at line 803
- **No concerns**

#### P2 — Update "not-available" banner — VERIFIED
- **Commit**: 552c1931
- **File**: `gui/src/components/AppLayout.tsx:751,754-760,811-812`
- **Evidence**: `'not-available'` in visibility list, `setTimeout` 5s auto-dismiss, "You are up to date" message
- **No concerns**

### Phase 2 — Data & Search Fixes

#### P6 — Element name parsing — VERIFIED
- **Commit**: ad0d2045
- **File**: `src/qmatsuite/io/online_search.py:47-108`
- **Evidence**: `_element_name_to_symbol()` + `_looks_like_formula()` heuristic; "titanium" → "Ti" before formula regex
- **No concerns**

#### P9 — Structure selector refresh — VERIFIED
- **Commit**: 5d102f16
- **File**: `gui/src/components/AppLayout.tsx:116-127`
- **Evidence**: `handleCreateCalculationSuccess()` calls `await project.fetchStructures()` at line 126
- **No concerns**

#### P10 — Pseudo update after structure change — VERIFIED
- **Commit**: 56a3eb0b
- **File**: `src/qmatsuite/api/service.py:4629-4667`
- **Evidence**: `set_structure()` rebuilds species_map with new elements, auto-matches SSSP pseudos
- **No concerns**

#### P11 — SSSP library scan — VERIFIED (dependency on P27)
- **No standalone commit needed**: Scanner code was already correct
- **Root cause**: P27 (`.to_dict()`) was blocking JSON serialization of library status to frontend
- **Documented**: V1_2_2_BUGFIX_WORKLOG.md: "P11 — unblocked by P27, no changes needed"
- **No concerns**

### Phase 3 — Performance Fixes

#### P29 — matplotlib MPLCONFIGDIR — VERIFIED
- **Commit**: 65d751c9
- **File**: `src/qmatsuite/daemon/server.py:5230-5260`
- **Evidence**: `_set_mplconfigdir()` sets `os.environ["MPLCONFIGDIR"]` before daemon startup, platform-aware paths
- **No concerns**

#### P30 — OPTIMADE lazy-load — VERIFIED
- **Commit**: 94f47629
- **File**: `src/qmatsuite/io/providers/optimade.py:215-290`
- **Evidence**: `fetch_optimade_registry(refresh=False)` returns `CURATED_DEFAULT_PROVIDERS.copy()` without HTTP call; 6 curated providers defined at lines 49-99
- **No concerns**

#### P31 — engine.list fast path — VERIFIED
- **Commit**: a93701d7
- **Files**: `src/qmatsuite/api/engines.py:75-93`, `src/qmatsuite/daemon/server.py:1410-1416`, `gui/src/hooks/useQMSClient.ts:404`, `gui/src/components/panels/SettingsPanel.tsx:455-462`
- **Evidence**: `registry.load()` instant cached read; `discover()` only on `refresh=True` (Settings manual refresh, post-install)
- **No concerns**

### Phase 4 — UX Polish & Platform

#### P1 — Disable differential download — VERIFIED
- **Commit**: d5b7a259
- **File**: `gui/electron/main.ts:149`
- **Evidence**: `autoUpdater.disableDifferentialDownload = true;` in `configureAutoUpdater()`
- **No concerns**

#### P23 — Path leak (home dir → tilde) — VERIFIED
- **Commit**: e64d7107
- **File**: `gui/src/components/panels/SettingsPanel.tsx:29-31`
- **Evidence**: `sanitizePath()` regex handles macOS/Linux/Windows home paths; applied at 6 locations (lines 727, 1223, 1299, 1308, 1407, 1447)
- **No concerns**

#### P12 — Gen-type labels in Add Step dropdown — VERIFIED
- **Commit**: 186e81d5
- **File**: `gui/src/components/panels/CalculationOverviewTab.tsx:475,482`
- **Evidence**: `[${step.gen.toUpperCase()}] ${step.description || step.gen}` format
- **No concerns**

#### P13 — Collapse secondary digest fields — VERIFIED
- **Commit**: 8a16e47f
- **File**: `gui/src/components/panels/StepDigestPanel.tsx:4,43-44,76`
- **Evidence**: `PRIMARY_KEYS` set, primary/secondary filter, expandable toggle
- **No concerns**

#### P14 — Auto-switch to Plot tab — VERIFIED
- **Commit**: b58e31a4
- **File**: `gui/src/components/panels/CalculationAnalysisPanel.tsx:241,374`
- **Evidence**: `setViewMode('analysis')` triggered when analysis data matched
- **No concerns**

---

## CIF Import Fix (`_unescape_content`) — RESTORED

- **Problem**: Function was developed locally, tests written (32 tests in `tests/mcp/test_import_structure.py`), test file committed in `b379b06c`, but `_unescape_content` was **never added** to the committed source `src/qmatsuite/mcp/tools/import_structure.py`
- **Discovery**: CI failed on both macOS and Ubuntu with ImportError
- **Fix applied**: Function added to source module + wired into `file_content` path
- **Verification**: All 32 tests now pass; `python -c "from qmatsuite.mcp.tools.import_structure import _unescape_content"` succeeds
- **Full analysis**: `docs/history/reviews/CI_IMPORT_STRUCTURE_UNESCAPE_REVIEW.md`

---

## Fixes Not In HEAD (by design)

### P25 — macOS entitlements — BLOCKED
- **Status**: Documented as blocked in `docs/history/worklogs/V1_2_2_BUGFIX_WORKLOG.md`
- **Reason**: Requires `electron-builder.json5` change; no `entitlements.mac.plist` created
- **Impact**: Electron-builder uses built-in default entitlements. May cause macOS Music permission dialog on Settings page load (original P25 symptom).
- **No commit exists**: This was never attempted

### P33 — Demo YAML titles — SKIPPED
- **Status**: Documented as skipped per user request in `docs/history/worklogs/V1_2_2_CHANGELOG.md`
- **Current state**: 4 QE demo files still have numbered titles:
  - `qe_si_scf.yml:122` — `0 Si Scf`
  - `qe_si_dos_alt.yml:144` — `4 Si Dos`
  - `qe_si_bands_alt.yml:166` — `7 Si Bandstructure`
  - `qe_si_vc_relax.yml:128` — `3 Si Vc Relax`
- **Impact**: Cosmetic only; demos function correctly

### P35 — Engine resolution unification — SEPARATE BRANCH
- **Status**: Implemented on `p35-engine-unification` branch, not merged into `v2-python`
- **Commits**: 8fbff5e5 → 904ceea0 → c9548427 → 65b724a0 → a7a0d4f0
- **Content**: `resolve_engine_binary()` / `resolve_engine_python()` unification, legacy resolver deletion
- **Verified**: `git merge-base --is-ancestor a7a0d4f0 HEAD` → false; `git branch --contains a7a0d4f0` → `p35-engine-unification` only
- **Impact**: Legacy per-engine resolver files still present at HEAD

---

## Conclusion

The `_unescape_content` incident was an isolated case. All other v1.2.1/v1.2.2 bugfixes that were intended to be committed **are present and verified** at HEAD. The three items not at HEAD (P25, P33, P35) were all documented as blocked/skipped/deferred before this audit.
