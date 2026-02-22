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
    1) `QV_DAEMON_PYTHON`
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
  - `gui/src/types/qv.ts` currently does not include typed `engine.*` management RPCs beyond generic map entries already used elsewhere.
  - `useQVClient` has no convenience wrappers for engine install/list/register/verify/set-active.

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
- API already provides these functions in `src/quantumvitas/api/engines.py`; daemon wiring is the gap.

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
- File changed: `src/quantumvitas/core/engines/micromamba.py`
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
  - `set -o pipefail; source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile | tee /tmp/qv-step5-task0-full-pytest.log`
  - Result: `6497 passed, 4 skipped, 980 warnings` (exit code 0)
  - Runtime: `380.50s` (`0:06:20`)
- Notes:
  - Full output captured at `/tmp/qv-step5-task0-full-pytest.log` for post-run greps and evidence reuse.

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
  - `useQVClient` typed calls already used for all backend operations
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
  - renderer files (`App.tsx`, `SettingsPanel.tsx`, `useQVClient.ts`, `qv.ts`, CSS)
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
  - `qv-runtime-setup-status`
  - `qv-updater-state`
  - `qv-check-for-updates`
  - `qv-download-update`
  - `qv-quit-and-install-update`
  - `qv-e2e-set-updater-state` (test-mode helper only)
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

### Fix applied in renderer types (`gui/src/types/qv.ts`)
- Added exported renderer-side types:
  - `RuntimeSetupStatus`
  - `UpdaterState`
- Extended `QVApi` contract with all runtime/updater bridge methods.

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
    - `qv-set-e2e-rpc-mock`
    - `qv-clear-e2e-rpc-mocks`
    - `qv-request` now checks mock queues first when `E2E_TEST_MODE=true`.
  - Preload (`gui/electron/preload.ts`):
    - `setE2ERpcMock()` and `clearE2ERpcMocks()` exposed.
  - Type contract (`gui/src/types/qv.ts`) updated with optional E2E mock methods.
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
