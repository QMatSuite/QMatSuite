# Engine Management Cleanup — Worklog

**Date**: 2026-02-24 (Session 3)
**Branch**: v2-python
**References**:
- Review: `docs/history/reviews/engine-management-review-2026-02-24.md` — recommendations #8, #11-14
- Session 1 worklog: `docs/history/worklogs/engine-mgmt-backend-fixes-2026-02-24.md`
- Session 2 worklog: `docs/history/worklogs/engine-mgmt-frontend-fixes-2026-02-24.md`

---

## Task 1: Auto-Source QE Prefers github_release

**Problem**: When `source="auto"`, the install logic checked `conda_package` first. Since QE has `conda_package: "qe"`, auto always selected conda — ignoring the signed, platform-optimized pre-built binary from `qmatsuite-toolchain`.

**Fix** (`src/qmatsuite/api/engines.py`):
- Added `_QE_TOOLCHAIN_PLATFORMS` set: macOS arm64, macOS x64, Windows x64
- Added `_qe_github_release_available()` helper: checks `(system, machine)` against the set
- Updated auto-source logic: QE on supported platform → `github_release`; QE on Linux → `conda` fallback; other engines → unchanged

**Tests** (`tests/unit/test_api_engine_installation.py`):
- `test_auto_source_qe_macos_arm64_prefers_github_release` — mocks platform as Darwin/arm64, verifies github_release
- `test_auto_source_qe_windows_x64_prefers_github_release` — mocks platform as Windows/AMD64, verifies github_release
- `test_auto_source_qe_linux_x64_falls_back_to_conda` — mocks platform as Linux/x86_64, verifies conda fallback
- `test_auto_source_xtb_always_uses_conda` — verifies xTB unchanged behavior

All 9 tests in file pass (5 existing + 4 new).

---

## Task 2: Design Doc Updates

**File**: `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md`

### 2a. §3.9 — Checksum naming (recommendation #11)
Updated download flow step 4 to document:
- `checksums.txt` (sha256sum format) as the primary checksum file from toolchain releases
- Per-asset `.sha256` sidecar files as backward-compatible fallback (used by micromamba releases)
- Warning+skip behavior when neither exists

### 2b. §3.10 — Three-state resolver (recommendation #12)
Replaced the design doc's two-state model with the actual three-state implementation:
1. Registry (`engines.json`) — highest priority
2. Settings (`settings.qe.bin_dir`) — backward compatibility
3. Auto-scan (`.qmatsuite/engines/qe/**/bin/`) — legacy fallback

Added note that other engines follow simpler two-tier: registry → `shutil.which()`.

### 2c. §3.11 — Progress reporting (recommendation #13)
Added new subsection documenting:
- Async job model (single-worker ThreadPoolExecutor)
- Progress fields: `progress_pct`, `progress_bytes`, `progress_total`, `progress_stage`
- Download phases report bytes; conda install phases stream subprocess output
- Frontend polls every 2s, renders determinate/indeterminate progress bar

### 2d. §3.6/§3.9 — Auto-source selection (recommendation #14)
Added table to §3.6 documenting the complete auto-source selection logic:
- QE on macOS/Windows → `github_release` (signed toolchain binary)
- QE on Linux → `conda` (no toolchain binary yet)
- All other conda-installable engines → `conda`
- VASP/ORCA/Gaussian/Yambo → error (user must configure path)

### Status table updates
Updated implementation status summary table:
- Engine registry: ✅ Implemented
- Micromamba integration: ✅ Implemented
- Engine manager GUI: ✅ Implemented
- §3.6 header: Changed from "Not yet implemented" to "Implemented"

---

## Files Modified

| File | Change |
|------|--------|
| `src/qmatsuite/api/engines.py` | Added platform check helper, updated auto-source logic |
| `tests/unit/test_api_engine_installation.py` | 4 new auto-source tests |
| `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` | §3.9, §3.10, new §3.11, §3.6 updates |
| `docs/history/worklogs/engine-mgmt-cleanup-2026-02-24.md` | This worklog |
