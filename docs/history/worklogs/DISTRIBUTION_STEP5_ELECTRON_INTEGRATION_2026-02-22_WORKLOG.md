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
