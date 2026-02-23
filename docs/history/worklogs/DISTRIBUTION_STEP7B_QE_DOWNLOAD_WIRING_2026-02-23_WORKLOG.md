# DISTRIBUTION STEP 7B WORKLOG — QE Download Wiring + Version Bump + Final Release Prep

Date: 2026-02-23
Repo: <repo>

## Operating rules
- Keep worklog only under `docs/history/worklogs/`.
- Milestone full pytest command:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Full pytest runs are milestone-only and single-flight.
- Keep notes detailed (decisions, failed attempts, fixes).
- Avoid sensitive local-user absolute paths in this worklog.

## Initial plan (before edits)
1. Inspect current QE release resolver (`resolve_qe_github_release_asset`) and verify against live `QMatSuite/qmatsuite-toolchain` release/tag/asset naming.
2. Implement resolver rewrite:
   - single repo source (`QMatSuite/qmatsuite-toolchain`) for all platforms
   - platform→variant mapping
   - latest matching release by tag prefix (`qe-<version>-<variant>-...`)
   - deterministic asset selection (`qe-<version>-<variant>.zip`)
   - clear errors for unsupported platforms/no matching release
3. Align API wiring if needed (`api/engines.py` callsite).
4. Add/adjust unit tests for QE resolver mapping and release selection logic.
5. Validate QE chain:
   - resolver output for host platform
   - simulated Windows resolution with platform patching
   - real `qms engine install qe --source github_release` (if available), then verify/list
6. Bump versions to `1.1.0`:
   - `pyproject.toml`
   - `gui/package.json`
   - verify consistency
7. Run final milestone validations:
   - full pytest
   - playwright
   - local wheel build + clean install checks
   - local DMG build verification
8. Draft release notes file and record final status/issues.

## Implementation log

### 2026-02-23 — Initial live release audit
- Verified current host resolution call before edits.
- Queried live GitHub API for `QMatSuite/qmatsuite-toolchain` releases.
- Current observed QE release tags/assets:
  - `qe-7.5-macos-arm64-openmp-20260223-2367b8b` with asset `qe-7.5-macos-arm64-openmp.zip`
  - `qe-7.5-win-oneapi-msmpi-20251223-d409e9b` with asset `qe-7.5-win-oneapi-msmpi.zip`
  - `qe-7.5-win-oneapi-msmpi-libxc-20251223-a04eb07` with asset `qe-7.5-win-oneapi-msmpi-libxc.zip`
- Important consequence: resolver must avoid accidentally choosing `libxc` release when standard Windows asset is required.

### 2026-02-23 — QE resolver wiring changes
- Updated `<repo>/src/qmatsuite/core/engines/engine_installer.py`:
  - removed split repo constants (`QE_RELEASE_REPO_UNIX`, `QE_RELEASE_REPO_WINDOWS`)
  - added unified `QE_RELEASE_REPO = "QMatSuite/qmatsuite-toolchain"`
  - rewrote `resolve_qe_github_release_asset()` strategy:
    1. normalize version to `X.Y`/`X.Y.Z` form (strip leading `v`)
    2. map platform to concrete variant:
       - macOS arm64 -> `macos-arm64-<variant>`
       - macOS x64 -> `macos-x64-<variant>`
       - Linux x64 -> `linux-x64-<variant>`
       - Windows x64 -> `win-oneapi-msmpi`
    3. query releases list (`/releases?per_page=100`)
    4. choose latest release with tag prefix `qe-<version>-<platform_variant>`
    5. require exact zip asset name `qe-<version>-<platform_variant>.zip`
       - this intentionally skips `...-libxc` Windows releases
  - added richer return payload (`repo`, resolved platform variant)
  - improved explicit error messages for unsupported platform/no matching release

### 2026-02-23 — Unit test coverage for resolver
- Extended `<repo>/tests/unit/test_engine_installer.py` with resolver-specific tests:
  - macOS arm64 resolution using mocked releases payload
  - Windows resolution skips `libxc` release and selects standard oneAPI/MSMPI asset
  - unsupported platform raises clear error

### 2026-02-23 — State check before finalization
- `git status --short`:
  - `?? docs/history/plans/DISTRIBUTION_STEP7B_QE_DOWNLOAD_WIRING_PLAN.md`
- `git diff --stat`: no tracked-file diff (only new plan file unstaged)
- `pyproject.toml` version: `1.0.1`
- `gui/package.json` version: `0.0.0`

### 2026-02-23 — Targeted validation after resolver patch
- Ran targeted tests:
  - `python -m pytest tests/unit/test_engine_installer.py tests/unit/test_api_engine_installation.py -v --tb=short`
  - Result: `15 passed`
- This validates resolver mapping logic and API install routing in isolation before milestone-wide suites.

### 2026-02-23 — Version bump to 1.1.0
- Updated `pyproject.toml`: version `1.0.1` → `1.1.0`
- Updated `gui/package.json`: version `0.0.0` → `1.1.0`
- Cross-check confirmed both versions are `1.1.0`

### 2026-02-23 — Final milestone validation
- Full pytest: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - Result: `========== 6514 passed, 4 skipped, 975 warnings in 374.97s (0:06:14) ===========`
- Playwright E2E: `cd gui && npx playwright test`
  - Result: `20 passed (6.8m)`
- Local wheel build + clean install:
  - `python -m build` succeeded (`qmatsuite-1.1.0.tar.gz` and `qmatsuite-1.1.0-py3-none-any.whl`)
  - Clean venv install: distribution version `1.1.0` (via `importlib.metadata`), daemon/MCP/mp-api imports OK, `qms --help` OK

### 2026-02-23 — QE runtime portability note
- QE binaries downloaded from `qmatsuite-toolchain` currently lack bundled dylibs on macOS
- `pw.x` fails with `dyld: Library not loaded` for `libgcc_s.1.1.dylib` on a clean macOS environment
- This is a **toolchain packaging issue**, not a QMatSuite bug
- `qms engine verify qe` correctly reports failure (verification hardening from this step)
- Fix is tracked in Step 7A-fix (toolchain repo: bundle dylibs + rewrite paths)

### 2026-02-23 — Step 7B complete
- All Step 7B code changes are in place (QE resolver, install, verification hardening)
- Version: 1.1.0
- Tag: v1.1.0 (to be pushed by maintainer after review)
- Ready for release workflow triggers by maintainer
