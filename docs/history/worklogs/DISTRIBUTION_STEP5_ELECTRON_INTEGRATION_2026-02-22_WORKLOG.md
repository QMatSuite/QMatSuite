# DISTRIBUTION STEP 5 WORKLOG — Electron Integration + GUI Engine Manager + Auto-Updater

Date: 2026-02-22
Repo: <repo_root>

## Operating rules for this step
- Worklog location rule: all notes in `docs/history/worklogs/` (no repo-root docs).
- Full-suite pytest command rule (strict):
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Full-suite runs are single-flight; wait for completion before further test runs.
- Start with Task 0 (`MAMBA_NO_RC` boolean fix), then continue Electron/GUI/updater work.

## Initial plan (before edits)
1. Mandatory reading and architecture mapping
   - distribution design sections for Electron/runtime/update
   - constitution/laws relevant to daemon/API/frontend boundaries
   - Electron main/preload/renderer structure and existing RPC flow
2. Task 0 hotfix
   - change default `MAMBA_NO_RC` from `"1"` to `"true"`
   - run targeted micromamba tests (if present), then strict full suite
   - commit milestone before main Electron changes
3. Electron runtime integration
   - map current daemon launch path and Python path resolution
   - implement `findPythonPath()` priority chain including runtime env
   - ensure child daemon env sets `QMATSUITE_ELECTRON=1`
   - add first-launch runtime extraction flow + setup UI state
4. Engine Manager GUI
   - add top-of-settings Engine Management section
   - wire list/install/uninstall/verify/path actions through existing RPC
   - add install progress polling via job-status API
   - add inline missing-engine guidance in run-results path (no launch popup)
5. Auto-updater integration
   - add `electron-updater` integration in main process + renderer notifications
   - update builder publish config for GitHub releases
6. E2E + verification
   - add Playwright coverage for new flows
   - run Playwright suite
   - run strict full Python suite
   - run electron build verification commands
7. Final documentation
   - update this worklog with decisions, issues, and test/build evidence

## Risks to watch early
- Existing Electron code may have custom daemon boot logic; avoid breaking dev mode.
- UI architecture may separate settings panel by feature flags/routes.
- Playwright may require mocks for updater and install progress flows.
- Keep kernel/API boundary intact: GUI talks to daemon/API only.

## Mandatory reading + architecture law notes (completed)
- Design doc sections reviewed for this step:
  - §1.2–§1.3 (lite/full release contents, first-launch behavior)
  - §1.6 (per-platform install behavior)
  - §2.2–§2.3 (target layout + path resolution constraints)
  - §4.3 (embedded Python runtime via tarball)
  - §4.5 (Electron `findPythonPath()` + daemon launch flow)
  - §4.6 (independent update dimensions)
- Governance/laws reviewed:
  - `CONSTITUTION.md`
  - `docs/laws/L1/API_CONSTITUTION.md`
  - `docs/laws/L1/KERNEL_DEPENDENCY_SPEC.md`
  - `docs/laws/L2/MULTI_FRONTEND_ARCHITECTURE_SPEC.md`
  - `docs/laws/L2/engine_registry_and_dispatch.md`
  - `docs/laws/L2/engine_driver_protocol.md`
- Boundary reaffirmed:
  - GUI -> daemon RPC only
  - daemon -> API layer only
  - no frontend direct kernel usage

## Current-state code map (before Step 5 edits)

### Electron process + daemon launch
- Main process: `gui/electron/main.ts`
  - `findPythonPath()` currently resolves:
    1) `QMS_DAEMON_PYTHON`
    2) `<repo>/.venv` and `<repo>/venv`
    3) fallback `"python"` on PATH
  - Missing today:
    - runtime path (`<app_data>/runtime/...`)
    - `QMATSUITE_ELECTRON=1` env injection when spawning daemon
    - first-launch runtime extraction flow from `runtime.tar.zst`
    - updater integration
- Renderer bridge: `gui/electron/preload.ts`
  - Exposes `request`, daemon status listeners, file/directory picker, log helpers.
  - No updater/setup channels exposed yet.

### Renderer app structure
- Main app: `gui/src/App.tsx`
  - Run flow currently does `preflight_check` then `run_calculation`.
  - On preflight failure, only toast notification is shown.
  - No inline missing-engine remediation panel yet.
- Settings: `gui/src/components/panels/SettingsPanel.tsx`
  - QE-centric sections:
    - QE detect/re-detect and two-state bin-dir selection
    - no generic Engine Manager list/actions
  - Existing engine family listing exists but not install/manage UI.
- Types + client:
  - `gui/src/types/qms.ts` currently does not include typed `engine.*` management RPCs beyond generic map entries already used elsewhere.
  - `useQMSClient` has no convenience wrappers for engine install/list/register/verify/set-active.

### Daemon/API engine management surface
- Daemon has only Step 3 endpoints:
  - `engine.install`
  - `engine.uninstall`
  - `engine.list_installable`
- Missing daemon endpoints needed by Step 5 GUI manager:
  - list installed status (`api.engines.list_engines`)
  - verify (`api.engines.verify_engine`)
  - register user path (`api.engines.register_engine`)
  - set active (`api.engines.set_active_engine`)
  - unregister (`api.engines.unregister_engine`)
- API already provides these functions in `src/qmatsuite/api/engines.py`; daemon wiring is the gap.

### Packaging/updater current state
- Builder config (`gui/electron-builder.json5`) is placeholder:
  - `appId: "YourAppID"`
  - `productName: "YourAppName"`
  - no publish provider configuration
- `gui/package.json` currently does not include `electron-updater`.

### E2E harness map
- Playwright config: `gui/playwright.config.ts` (single worker, non-parallel).
- Existing E2E specs under `gui/tests/e2e/`.
- Existing helper/fixture pattern supports mocking via preload IPC hooks (useful for updater/install simulation tests).

## Implementation decisions before coding
1. Do Task 0 first with isolated patch in `micromamba.py`.
2. Add daemon RPC wrappers for existing API engine management functions (no kernel bypass).
3. Build Engine Manager in Settings on top of those RPCs + `get_job_status` polling.
4. Keep legacy QE section for backward compatibility while adding generic Engine Management section at the top.
5. Implement inline missing-engine guidance by intercepting preflight/run failure in `App.tsx` (no first-launch popup).
6. Implement runtime setup + updater in Electron main, push status/events to renderer via preload bridge.
7. Add focused Playwright specs with mocks (avoid real installs/updates in E2E).

## Task 0 progress (MAMBA_NO_RC boolean fix)
- File changed: `src/qmatsuite/core/engines/micromamba.py`
  - `run_micromamba()` default env changed:
    - from `MAMBA_NO_RC="1"`
    - to `MAMBA_NO_RC="true"`
- Rationale:
  - Step 4 validation found micromamba `2.5.0-2` rejects `"1"` for this flag and expects YAML boolean text.
- Additional boolean env vars check:
  - No other `MAMBA_*` boolean defaults currently set in this module.
- Verification pending immediately after edit:
  1. targeted: `tests/unit/test_micromamba.py`
  2. strict full suite (single-flight): `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

### Task 0 verification results
- Targeted test command:
  - `source .venv/bin/activate && python -m pytest tests/unit/test_micromamba.py -v --tb=short`
  - Result: `8 passed` (exit code 0)
- Full suite command (strict, single-flight):
  - `set -o pipefail; source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile | tee /tmp/qms-step5-task0-full-pytest.log`
  - Result: `6497 passed, 4 skipped, 980 warnings` (exit code 0)
  - Runtime: `380.50s` (`0:06:20`)
- Notes:
  - Full output captured at `/tmp/qms-step5-task0-full-pytest.log` for post-run greps and evidence reuse.

## Deep context map before Step 5 implementation edits

### Daemon/API reality check (as of this checkpoint)
- Daemon exposes only three install-management RPCs:
  - `engine.install`
  - `engine.uninstall`
  - `engine.list_installable`
- API layer already has broader operations required by GUI manager:
  - `list_engines(installed_only=False)`
  - `verify_engine(engine_family)`
  - `set_active_engine(engine_family, installation_id)`
  - `register_engine(engine_family, path, source, env_vars)`
  - `unregister_engine(engine_family, installation_id)`
- Gap: daemon wrappers for those API functions are missing, so GUI cannot use them yet.

### Electron main process map
- `gui/electron/main.ts` currently:
  - `findPythonPath()` = env override -> `.venv/venv` -> system `python` fallback
  - no runtime location check (`<app_data>/runtime/...`)
  - daemon spawn env does not set `QMATSUITE_ELECTRON=1`
  - no runtime extraction flow from `runtime.tar.zst`
  - no updater integration
- IPC channels exist for daemon request bridge, file pickers, logs, path reveal; none for runtime-setup progress or updater state/actions.

### Renderer/UI map
- Settings (`SettingsPanel.tsx`) is QE-centric and generic-family informational only; no unified engine manager controls.
- Run flow in `App.tsx` does preflight and falls back to toast; no inline missing-engine remediation panel.
- Existing UI architecture supports this cleanly:
  - `useQMSClient` typed calls already used for all backend operations
  - top-level App handles run orchestration and tab switch decisions

### E2E and contract impact map
- Adding daemon RPC method names changes introspection inventory used by contract crawler tests.
- If new RPCs are stateful/mutating, we must either:
  - supply deterministic minimal payload behavior that returns data without raising, or
  - add recipe/exemption updates to avoid coverage failures.
- Playwright suite is single-worker sequential by design; new E2E should avoid real installs and use UI-triggered behavior that can run against normal daemon state.

## Implementation plan for remaining Step 5 tasks
1. Daemon/API bridge expansion (backend-safe first)
   - Add daemon handlers + registry entries for:
     - `engine.list`
     - `engine.verify`
     - `engine.set_active`
     - `engine.register_path` (plus alias `engine.path`)
     - `engine.unregister`
   - Ensure handlers return structured non-throwing responses where practical for deterministic contract crawling.
   - Update daemon contract tests + contract crawler payload/introspection coverage as needed.

2. Electron runtime integration
   - Add Electron-side `getAppDataDir()` matching Python `_electron_app_data_dir()` semantics.
   - Update `findPythonPath()` chain to include runtime env priority.
   - Add first-launch runtime extraction flow:
     - detect runtime tarball in resources
     - extract to `<app_data>/runtime`
     - verify import with extracted python
     - publish progress/error events to renderer
   - Ensure daemon spawn injects `QMATSUITE_ELECTRON=1`.

3. GUI engine manager + run-time remediation
   - Add top Settings section “Engine Management” with actions:
     - install/uninstall
     - configure path (commercial engines)
     - set active installation
     - verify
   - Poll `get_job_status` for install/uninstall progress.
   - In run flow, add inline missing-engine panel when preflight/run indicates engine missing; no first-launch popup.

4. Auto-updater integration
   - Add `electron-updater` dependency and main-process wiring.
   - Add renderer notification/banner with download + restart actions.
   - Add `electron-builder.json5` publish block and production app metadata.

5. Verification
   - Python targeted tests for modified backend contract surfaces.
   - GUI/electron checks (`npm run build` / targeted Playwright, then full Playwright if feasible).
   - Strict full pytest once implementation stabilizes:
     - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`


## Incremental implementation log (continuously updated)

### 2026-02-22 — session continuation checkpoint
- Resumed from partially completed Step 5 state with uncommitted edits in:
  - `gui/electron/main.ts`
  - `gui/electron/preload.ts`
  - renderer files (`App.tsx`, `SettingsPanel.tsx`, `useQMSClient.ts`, `qms.ts`, CSS)
  - daemon RPC expansion and related contract tests.
- Confirmed targeted backend tests were green before continuing Electron integration:
  - `tests/daemon/contract/test_engine_rpcs.py`
  - `tests/contract_crawler/test_coverage.py`
  - previous run result: `18 passed`.

### Problem encountered: runtime/updater code existed but was not wired
- What I found:
  - `main.ts` already contained helper functions for runtime extraction and updater state structs.
  - Startup path still did `spawnDaemon()` immediately and never called `ensureRuntimeReady()`.
  - No IPC contract existed for runtime/updater state or updater actions.
  - Daemon child env still missed `QMATSUITE_ELECTRON=1`.
- Consequence:
  - Runtime setup UI would never receive true setup states.
  - Packaged-lite first launch could fail silently or race.
  - Updater UI could not be implemented end-to-end.

### Fix applied in `gui/electron/main.ts`
- Added updater enable policy and setup:
  - `isUpdaterEnabled()` with dev/test gating.
  - `configureAutoUpdater()` attaching handlers for checking/available/not-available/download-progress/downloaded/error.
- Added daemon child env flag:
  - `QMATSUITE_ELECTRON=1` in `spawnDaemon()` env.
- Added IPC endpoints:
  - `qms-runtime-setup-status`
  - `qms-updater-state`
  - `qms-check-for-updates`
  - `qms-download-update`
  - `qms-quit-and-install-update`
  - `qms-e2e-set-updater-state` (test-mode helper only)
- Updated renderer event bootstrapping:
  - `did-finish-load` now pushes `daemon-status`, `runtime-setup-status`, and `updater-state` snapshots.
- Reworked app startup order:
  1. `configureAutoUpdater()`
  2. `createWindow()`
  3. async bootstrap: `ensureRuntimeReady()` -> `spawnDaemon()` -> silent startup `checkForUpdates()`
- Decision made:
  - In packaged mode, runtime extraction/verification failure blocks daemon start and surfaces error state.
  - In development mode, runtime failure/non-availability falls back to dev/system Python.

### Fix applied in `gui/electron/preload.ts`
- Added type mirror interfaces:
  - `RuntimeSetupStatus`
  - `UpdaterState`
- Added bridge APIs:
  - `getRuntimeSetupStatus()`, `onRuntimeSetupStatus()`
  - `getUpdaterState()`, `onUpdaterState()`
  - `checkForUpdates()`, `downloadUpdate()`, `quitAndInstallUpdate()`
  - `setE2EUpdaterState()` (for E2E simulation)

### Fix applied in renderer types (`gui/src/types/qms.ts`)
- Added exported renderer-side types:
  - `RuntimeSetupStatus`
  - `UpdaterState`
- Extended `QMSApi` contract with all runtime/updater bridge methods.

### In-progress renderer wiring (`gui/src/App.tsx`)
- Added state hooks:
  - `runtimeSetupStatus`
  - `updaterState`
  - `updaterDismissed`
- Added subscription/init effect:
  - fetch initial status snapshots via preload
  - subscribe to runtime/updater events for live state updates
- Pending next edits:
  - render runtime setup full-screen overlay with error/report path
  - render updater banner/actions
  - connect updater action handlers to preload methods

### Open risks tracked now
- `electron-updater` dependency still needs to be added to `gui/package.json` before build/typecheck.
- Need to ensure `App.tsx` UI additions do not break existing layout/E2E selectors.
- After renderer + preload + main finalize, run targeted GUI build first, then required full strict pytest command once.

### Additional progress update (same session)
- Renderer wiring progressed:
  - `gui/src/App.tsx`
    - Added live subscriptions for `runtime-setup-status` and `updater-state`.
    - Added updater action handlers (`check`, `download`, `restart/install`).
    - Added updater banner UI with progress and action buttons.
    - Added runtime setup full-screen overlay with progress + error panel and "Report Issue" link.
  - `gui/src/App.css`
    - Added styles for updater banner and runtime setup overlay, including mobile behavior.
- Packaging metadata updates:
  - `gui/package.json`
    - Added runtime dependency `electron-updater`.
  - `gui/electron-builder.json5`
    - Replaced placeholders with production identity:
      - `appId: com.qmatsuite.app`
      - `productName: QMatSuite`
      - GitHub publish provider (`QMatSuite/QMatSuite`)
- Issue noted:
  - No dedicated app icon files currently tracked in repo; builder config intentionally avoids hardcoded icon path to prevent immediate build break.
  - Follow-up for branded icon assets remains required in installer/signing step.

### Build/typecheck checkpoint
- Installed GUI dependency updates in `gui/`:
  - `npm install` completed successfully.
  - lockfile updated for `electron-updater` dependency.
- Ran renderer/electron compile verification:
  - Command: `cd gui && npm run build:e2e`
  - First run: failed with TS nullability error in `App.tsx` (`statusResponse.data` possibly undefined during missing-engine install polling).
  - Fix: introduced explicit `statusData` guard before field access.
  - Second run: succeeded (`tsc` + `vite build` for renderer/main/preload all green).

### E2E determinism improvement + new specs
- Added E2E-only RPC mock bridge to avoid real engine installs in Playwright:
  - Main process (`gui/electron/main.ts`):
    - `qms-set-e2e-rpc-mock`
    - `qms-clear-e2e-rpc-mocks`
    - `qms-request` now checks mock queues first when `E2E_TEST_MODE=true`.
  - Preload (`gui/electron/preload.ts`):
    - `setE2ERpcMock()` and `clearE2ERpcMocks()` exposed.
  - Type contract (`gui/src/types/qms.ts`) updated with optional E2E mock methods.
- Added Playwright spec:
  - `gui/tests/e2e/engine_manager.spec.ts`
  - Coverage added for:
    - Engine Manager visible in Settings
    - Install button -> progress state (mocked `engine.install`/`get_job_status`)
    - Commercial engine `Configure Path` presence
    - Run-flow missing-engine inline guidance panel
    - Updater banner visibility/actions when update-available state is simulated

### Test and build validation updates
- Backend targeted regressions:
  - Command: `source .venv/bin/activate && python -m pytest tests/daemon/contract/test_engine_rpcs.py tests/contract_crawler/test_coverage.py -v --tb=short`
  - Result: `18 passed`.
- Playwright targeted new spec:
  - Command: `cd gui && npx playwright test tests/e2e/engine_manager.spec.ts --project=electron`
  - Result: `4 passed`.
- Playwright full suite:
  - Command: `cd gui && npx playwright test`
  - Result: `20 passed` in ~7.0m.
  - Notes:
    - Real-run QE specs are long and produce heavy daemon polling logs; run completed green.
- Electron build verification:
  - Command: `cd gui && npm run build`
    - Result: success (renderer+electron build + DMG artifact generation).
  - Command: `cd gui && npx electron-builder --dir`
    - Result: success (unpacked app output).
  - Expected warnings observed:
    - app icon not set (default Electron icon used)
    - code signing skipped (Step 6 scope)
    - package metadata warnings for missing `description`/`author` in `gui/package.json`

### Continuity note (post-checkpoint)
- Confirmed requirement: keep detailed incremental worklog entries during implementation, including failures, attempted fixes, and rationale for final choices.
- Going forward in Step 5, each substantive code/test action will be logged immediately in this file before context switches.
- Current status remains: Step 5 feature set implemented and validated (targeted + full runs); next actions are cleanup/commit-level polish and any user-requested follow-up adjustments.

### User-requested rebrand follow-up (same session)
- User raised PyPI publish failure:
  - `403 Invalid API Token: project-scoped token is not valid for project 'qmatsuite'`
  - Root cause: distribution metadata/workflows still used old package project name `qmatsuite`.
- Explicit user request recorded:
  - move distribution naming to `qmatsuite`
  - keep CLI command `qms`
  - log this request and implementation details in worklog.

#### Changes applied for rebrand compatibility
1. `pyproject.toml`
   - `project.name`: `qmatsuite` -> `qmatsuite`
   - updated user-facing metadata (`description`, `authors`) to QMatSuite branding
   - `project.scripts.qms`: `qmatsuite.cli:app` -> `qmatsuite.cli:app`
   - package-data table key changed to wildcard `"*"` to avoid hard-binding on old top-level package name
2. New compatibility package shim
   - Added `src/qmatsuite/__init__.py`
   - Re-exports from legacy internal package `qmatsuite` and mirrors `__path__` so imports like:
     - `import qmatsuite`
     - `from qmatsuite.daemon.server import main`
     - `from qmatsuite.mcp.server import create_server`
     work without moving internal module layout yet.
3. CI workflow updates
   - `.github/workflows/release-pip.yml`
     - wheel verification now validates `import qmatsuite`
     - metadata check uses `importlib.metadata.version('qmatsuite')`
     - daemon/MCP import checks use `qmatsuite.*`
   - `.github/workflows/build-runtime-tarball.yml`
     - input renamed: `qmatsuite_version` -> `qmatsuite_version`
     - PyPI install line now installs `qmatsuite[mcp]==...`
     - runtime verification imports switched to `qmatsuite.*`
4. Gate helper update
   - `tests/gates/test_import_rules.py`
   - CLI entry discovery now supports both legacy and new script forms:
     - `qms = "qmatsuite.cli:app"`
     - `qms = "qmatsuite.cli:app"` (compat fallback)
5. User-facing CLI branding cleanup
   - Updated `QMatSuite` strings to `QMatSuite` in CLI help/docstrings.

#### Validation snapshots (ongoing)
- `tests/gates/test_import_rules.py`: pass (`10 passed, 2 skipped`).
- Local build output after rename:
  - `dist/qmatsuite-1.0.1-py3-none-any.whl`
  - `dist/qmatsuite-1.0.1.tar.gz`
- Clean-venv install sanity:
  - `import qmatsuite` works
  - `importlib.metadata.version('qmatsuite') == 1.0.1`
  - daemon + MCP import checks via `qmatsuite.*` pass
  - `qms --help` runs (initial shell block had non-critical `pipefail` + `head` exit artifact; rerun cleanly passed)

#### Notes / tradeoff
- Internal module tree is still `src/qmatsuite/...` for now; this follow-up intentionally addresses distribution/project naming and compatibility for publishing/install flows without a high-risk internal package-tree rename in this session.

#### Full-suite verification after rebrand patch
- Command (strict rule):
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Result:
  - `6509 passed, 4 skipped, 978 warnings` in `372.53s` (`0:06:12`)
- Notes:
  - No regressions introduced by the `qmatsuite` distribution rename and workflow updates.
  - Target workflow files and `pyproject.toml` no longer contain `qmatsuite` package-name references.

#### Completion state for this follow-up
- User request addressed in this session:
  - Publish/install-facing package name migrated to `qmatsuite`.
  - CI publish/runtime workflows now target `qmatsuite`.
  - CLI command remains `qms`.
  - Compatibility import path `qmatsuite.*` validated via clean-wheel install.

### New user directive (hard rename, no legacy)
- User requested strict rename policy:
  - no legacy shim
  - no `qmatsuite` remaining in repo
  - CLI command must be `qms` (not `qms`)
  - only package under `src/` should be `qmatsuite`
- Implementation strategy selected:
  1. Rename real package directory first (`src/qmatsuite` -> `src/qmatsuite`).
  2. Remove prior compatibility shim to enforce no-legacy policy.
  3. Perform controlled repo-wide string migration (`qmatsuite` -> `qmatsuite` + branding cases).
  4. Update CLI entrypoint to `qms` and remove `qms` script mapping.
  5. Reinstall editable package in `.venv` so script entry points are refreshed.
  6. Run focused sanity checks, then one strict full-suite run.
  7. Verify zero `qmatsuite` matches remain.

#### Immediate actions completed
- Removed previous temporary shim package directory: `src/qmatsuite/` (compat layer from prior session).
- Renamed canonical package tree:
  - `src/qmatsuite/` -> `src/qmatsuite/`
- Removed stale local build artifact directory if present:
  - `src/qmatsuite.egg-info/`

#### Risk notes captured before global replacement
- This is a cross-repo namespace migration touching imports, workflow commands, tests, docs, and path-based gates.
- To avoid whack-a-mole behavior, migration is being done as a systematic bulk namespace replacement followed by targeted contract checks, then full strict pytest once.

### Rebrand sweep continuation: remove all legacy short-name tokens (except README history)
- New user request applied in this pass: ensure no legacy short-name token remains in docs/tests/manual tests, and broadly across repo content.

#### What I did (systematic, not one-off)
1. Baseline scan
   - Ran tracked-file scans and broad workspace scans to map remaining token classes:
     - legacy package name leftovers
     - legacy CLI/service symbols
     - legacy environment-variable prefixes
     - legacy GUI type names
2. Filename/path migration
   - Renamed remaining legacy short-name files:
     - `gui/src/types/qms.ts` now used as the GUI command/type SSOT path
     - `gui/src/hooks/useQMSClient.ts` now used for renderer bridge hooks
     - `tests/unit/test_qmsservice_gui.py` updated to new service naming
     - `tests/gates/test_single_qmsservice_definition.py` updated to new gate naming
     - `tools/qms_migrate_legacy_project.py` updated for migration utility naming
     - all remaining `project.qms.yml` fixtures aligned in `manual_tests/` and `tests/data/`
   - Cleared transient pycache files in `tests/**/__pycache__/` that still carried legacy filenames.
3. Content migration pass #1
   - Replaced old textual tokens in impacted files (docs/tests/manual/code):
     - legacy package variants -> `qmatsuite` / `QMatSuite`
     - legacy service class family -> `QMSService`
     - legacy environment variable prefixes -> `QMS_*`
     - legacy bundle/project suffixes -> `.qms*`
     - legacy CLI helper names -> `run_qms`
4. Content migration pass #2 (GUI/API symbol normalization)
   - Renamed GUI type/system symbols to remove the old namespace:
     - command-map/type/payload/result/response/error family now uses `QMS...`
     - client and client-state types now use `QMSClient`/`QMSClientState`
     - bridge API/request types now use `QMSApi`/`QMSRequest`
     - log hook now uses `useQMSLogs`
     - renderer bridge variable now uses `qmsApi`
5. Data/docs/test residue cleanup
   - Fixed remaining explicit textual occurrences in docs/tests/examples.
   - Updated a small set of demo/test ULID literals that contained legacy short-name fragments.
   - Updated legacy short-prefixed example strings in docs/tests (for example, now using `qmstest1`).

#### Verification results
- Brand-pattern scan (excluding `README.md`):
  - legacy package/symbol tokens -> **0 matches**.
- Strict raw legacy-substring scan (excluding `README.md`):
  - Remaining matches are only in `gui/package-lock.json` integrity hashes (base64 digest strings from npm lockfile metadata).
  - No remaining semantic/code/doc/test/manual rebrand tokens.

#### Important note about `gui/package-lock.json`
- Legacy substring appears only inside integrity hash payloads (not identifiers/symbols/names).
- These hash strings are generated by npm and are not semantic project naming.
- I regenerated lockfile metadata (`cd gui && npm install --package-lock-only`) after broad refactors to ensure lockfile is internally consistent post-editing.

## 2026-02-22 17:5x — Demo Corpus Regression Found and User Directive

- Completed required full parallel suite run:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - Result: `6 failed, 6378 passed, 4 skipped` in ~6m21s.
- Failures were demo/reference-pack related, not runtime/path resolution:
  - Missing demo snapshots (`qe_fe_dos`, `qe_nmr_gipaw`, `qe_si_bulk_modulus`, `qe_si_phonon`).
  - MCP demo-store assertions reported only 27 ref packs instead of expected >=52.
  - `siesta_si_relax` trajectory result missing in ref-pack content.
- User directive recorded: demo content IDs/text should not be changed during rebrand cleanup. Demo payload should be restored to original state unless strong justification exists.
- Planned corrective action:
  1. Restore canonical demo corpus/ref-pack files from git-tracked baseline.
  2. Keep naming cleanup restricted to code/docs/tests/manual naming surfaces, not demo payload semantics.
  3. Re-run full parallel pytest after restore.

## 2026-02-22 18:0x — Demo Restore Applied

- Restored `src/qmatsuite/resources/demo_projects` from git-tracked canonical content using archive extraction from `HEAD` baseline.
- Verification after restore:
  - `ref_packs` directory count returned to 52.
- Kept demo payload semantics intact (no ULID/data/result regeneration in this restore pass).
- Updated only three demo README command examples from the legacy short CLI token to `qms`:
  - `src/qmatsuite/resources/demo_projects/water_orca_scf_README.md`
  - `src/qmatsuite/resources/demo_projects/methane_orca_freq_README.md`
  - `src/qmatsuite/resources/demo_projects/formaldehyde_orca_tddft_README.md`
- Repo-wide token scan status:
  - Legacy package-name token: no matches outside allowed `README.md` exception.
  - Legacy short CLI token: remaining matches are non-semantic checksum substrings inside `gui/package-lock.json` integrity hashes.

## 2026-02-22 18:2x — Demo Layer 1/Layer 2 Static Pipeline Audit (No Generator Execution)

User directive: do not run `generate_all.py` or ref-pack generators now; restore and investigate path/package-move risks by code inspection.

### Findings

1. `tools/demo_store/generate_ref_packs.py` had destructive default behavior:
   - It removed any existing `ref_packs/<slug>` not present in its hardcoded `GOLDEN_OUTPUT_MAP`.
   - The map is partial, so running it can collapse Layer 2 ref packs to a subset.
   - This explains earlier observed drop to 27 packs.

2. `tools/demo_store/generate_all.py` manifest entry format drift:
   - It emitted `output_file: src/qmatsuite/resources/demo_projects/<slug>.yml`.
   - Current canonical `.generator_manifest.json` uses `output_file: resources/demo_projects/<slug>.yml`.
   - Regeneration would create avoidable manifest churn despite unchanged demo payloads.

3. QE corpus helper script had stale demo filename/slug assumptions:
   - `tools/demo_store/create_qe_corpus.py` referenced old QE demo filenames/slugs (e.g., `08_Fe_DOS.yml` / `qe_fe_dos`).
   - Current Layer 2 naming uses `qe_fe_scf.yml` etc.

### Fixes applied (no generator executed)

- `tools/demo_store/generate_ref_packs.py`
  - Added safe default mode that **preserves stale ref packs**.
  - Added explicit `--prune-stale` flag for destructive cleanup when intentionally requested.
  - Updated QE DOS slug key from `qe_fe_dos` -> `qe_fe_scf`.

- `tools/demo_store/generate_all.py`
  - Manifest `output_file` now writes `resources/demo_projects/<slug>.yml` to match canonical manifest style.
  - Updated legacy wannier mapping for old demo names to current slugs:
    - `copper_wannier90_demo` -> `qe_copper_wannier`
    - `diamond_wannier90_demo` -> `qe_diamond_wannier`

- `src/qmatsuite/demo_store/manifest.py`
  - `build_demo_manifest_entry()` now emits `output_file: resources/demo_projects/<name>.yml` for consistency.

- `tools/demo_store/create_qe_corpus.py`
  - Updated `QE_DEMO_MAP` to current QE demo filenames (e.g., `qe_si_scf.yml`, `qe_fe_scf.yml`, etc.).
  - Updated analysis map key `qe_fe_dos` -> `qe_fe_scf`.

### Layering sanity after audit

- Runtime paths (Layer 2 consumption) stay package-SSOT via `get_resources_dir()`.
- Translator/corpus access remains dev-only and rooted at `tests/inputformat/samples` (Layer 1).
- No generator/ref-pack command was run in this audit cycle.

## 2026-02-22 18:3x — Final Verification + GitHub Actions Rename Audit

- Full suite rerun after demo-pipeline safety patches:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - Result: `6509 passed, 4 skipped, 977 warnings` (pass).
  - Log saved at `/tmp/qms_full_pytest_step5_postfix.log`.

- GitHub Actions workflow rename audit completed:
  - Scanned all `.github/**/*.yml` for legacy tokens.
  - No remaining legacy command/package references found in workflow YAML.
  - Verified expected new naming in workflows:
    - package install/import uses `qmatsuite`
    - CLI checks use `qms --help`
    - coverage paths use `src/qmatsuite`

- Additional notes:
  - Remaining lowercase short-token occurrences repo-wide are checksum substrings in `gui/package-lock.json` integrity hashes only (non-semantic hash material).

## 2026-02-22 18:4x — CI GPAW Trajectory Parser Dependency Fix

User reported CI failures in `tests/drivers/gpaw/test_gpaw_trajectory_parser.py` with:
- `ImportError: ASE required for GPAW trajectory parsing`.

Investigation:
- `src/qmatsuite/drivers/gpaw/parsers/trajectory.py` already performs a lazy import:
  - `from ase.io import read as ase_read` inside `parse()`.
- `pyproject.toml` no longer listed `ase` in core dependencies, so clean CI installs could miss it.

Fix:
- Restored `ase` to `[project].dependencies` in `pyproject.toml`.
- Kept lazy import behavior unchanged to avoid startup import regression.

Validation plan:
1. Run targeted GPAW trajectory parser tests.
2. Run full parallel suite:
   `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`.

- Targeted validation completed:
  - `source .venv/bin/activate && python -m pytest tests/drivers/gpaw/test_gpaw_trajectory_parser.py -v --tb=short`
  - Result: `9 passed` (all GPAW trajectory parser tests green).

- Full-suite verification after restoring `ase` to core dependencies:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - Result: `6509 passed, 4 skipped, 962 warnings` in ~6m27s.
  - Log saved at `/tmp/qms_full_pytest_asefix.log`.

- CI impact summary:
  - Clean installs now include `ase`, so GPAW trajectory parser tests no longer fail with missing dependency.
  - Lazy import contract preserved (no module-level `ase` import in parser).

## 2026-02-22 19:3x — GUI E2E Flake Investigation: Engine Install Progress Indicator

User-reported failure (Playwright, Electron project):
- `tests/e2e/engine_manager.spec.ts:55:3`
- Assertion failed: `getByTestId('qms-engine-progress-xtb')` not found/visible within 10s.
- Screenshot evidence showed the xTB row rendering `install completed` directly, without a visible intermediate progress state.

### Investigation path

1. Reproduced against the targeted spec file:
   - `cd gui && npx playwright test tests/e2e/engine_manager.spec.ts --project=electron --workers=1 --reporter=line`
2. Inspected UI logic in:
   - `gui/src/components/panels/SettingsPanel.tsx`
3. Inspected E2E IPC mocks and job progression behavior in:
   - `gui/electron/main.ts`
   - `gui/electron/preload.ts`
4. Correlated with failing assertion timing and screenshot output.

### Root cause

`EngineManagementSection` polling effect was configured so that when `pendingJobs` changed, the effect re-ran and performed an immediate extra `pollJobs()` call in addition to interval polling.

Effectively this could compress mocked state transitions too quickly (`running -> running -> completed`) before Playwright sampled the DOM for `qms-engine-progress-xtb`, causing intermittent miss of the progress indicator.

### Patch applied

File changed:
- `gui/src/components/panels/SettingsPanel.tsx`

Change:
- Removed immediate `void pollJobs();` invocation from the polling `useEffect`.
- Kept interval-based polling (`setInterval(..., 2000)`) so progress state remains observable for test and user UI.

### Validation status

- Targeted spec rerun result:
  - `tests/e2e/engine_manager.spec.ts` => **passed** (all tests in file passed in targeted run).
- Full Playwright suite:
  - A full run was started and observed executing long-running Electron E2E specs.
  - At least one recurrence of the same assertion was observed during an in-progress full run prior to compaction.
  - Current status at this log point: full-suite completion summary still pending capture.

### Additional note

This issue is timing-sensitive rather than a backend installation failure; UI transitions to `install completed` are happening, but the explicit progress test-id visibility window can be too short under some event timing paths.


## 2026-02-22 20:0x — Engine Manager E2E Failure Closed (Progress Indicator Flake)

User request context:
- Fix failing GUI E2E assertion for `qms-engine-progress-xtb`.
- Continue until fully solved.
- Later directive: frontend-only changes, so no full pytest rerun required in this pass.

### Observed failure

- Failing test:
  - `gui/tests/e2e/engine_manager.spec.ts`
  - `Engine install action shows progress and commercial engine keeps configure path`
- Symptom:
  - Expected `qms-engine-progress-xtb` visible.
  - Screenshot showed row already in `install completed` notice state.

### Investigation and findings

1. Initial assumption tested:
- Hypothesis: polling effect timing in `SettingsPanel.tsx` cleared progress too quickly.
- Action: patched UI polling flow to remove immediate poll and later added an immediate pending placeholder state.

2. Important operational finding:
- Playwright E2E launches from compiled artifacts (`dist/` + `dist-electron/`), not live TS source.
- Earlier reruns were using stale build output until `npm run build:e2e` was rerun.

3. Actual root cause for flake:
- In E2E mode, RPC mock queue is keyed only by method name.
- `get_job_status` is polled by multiple UI surfaces/jobs telemetry, not only Engine Manager.
- The queued `get_job_status` mock sequence for this test was being consumed by unrelated polling calls, causing unexpected fast transition to completion and missed progress assertion.
- This is a shared-mock-consumption issue, not Playwright test parallelism (tests are serial by config).

4. Performance note captured (not root cause but relevant):
- `engine.list` calls in logs repeatedly took ~5.6s due deep discovery/version probing.
- This increases UI latency but did not directly explain this assertion failure.

### Fixes applied

- UI hardening:
  - `gui/src/components/panels/SettingsPanel.tsx`
  - Added deterministic immediate pending state on install click.
  - Guarded polling so placeholder pseudo-job (`__pending__`) is not polled.

- E2E determinism fix (primary closure for failing assertion):
  - `gui/tests/e2e/engine_manager.spec.ts`
  - Changed `get_job_status` mock for this test from queued `running->running->completed` array to a stable single `running` response.
  - Prevents cross-consumption of queue elements by unrelated background polling.

### Verification executed

1. Rebuilt E2E artifacts:
- `cd gui && npm run build:e2e`

2. Stress check of target spec:
- `cd gui && npx playwright test tests/e2e/engine_manager.spec.ts --project=electron --workers=1 --repeat-each=3`
- Result: **12 passed**.

3. Full GUI suite:
- `cd gui && npx playwright test`
- Result: **20 passed (7.0m)**.

4. Pytest:
- Not rerun in this pass per latest explicit user direction (frontend-only changes).

### Files modified in this closure

- `gui/src/components/panels/SettingsPanel.tsx`
- `gui/tests/e2e/engine_manager.spec.ts`

