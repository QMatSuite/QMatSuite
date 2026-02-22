# QMatSuite v2 Architecture Overview

## 1) High-level Shape

**Major subsystems:**
- **GUI/Electron**: `gui/` - React/TypeScript Electron app
- **Daemon/Backend**: `src/qmatsuite/daemon/` - Python JSON-RPC stdio daemon
- **CLI/API**: `src/qmatsuite/cli/` + `src/qmatsuite/api.py` - CLI commands and service layer
- **Data/Assets**: `src/qmatsuite/data/` - QE metadata JSON, `resources/` - templates/demos
- **Tests**: `tests/` (unit/integration), `gui/tests/e2e/` (Playwright)
- **Docs**: `docs/` - architecture, API references, guides

**Top-level folders:**
- `src/qmatsuite/` - Python backend (core, calculation, engine, io, project, daemon, data)
- `gui/` - Electron frontend (React/TS, Vite build)
- `tests/` - Python unit/integration tests
- `tools/` - QE metadata extractors, validation scripts
- `docs/` - Documentation
- `.github/workflows/` - CI/CD (GitHub Actions)

## 2) GUI / Electron App

**Tech stack:**
- **Build**: Vite + TypeScript + React 18
- **Electron**: Main process (`gui/electron/main.ts`), preload bridge (`gui/electron/preload.ts`)
- **Styling**: CSS modules + CSS custom properties (`data-theme` for dark/light), no Tailwind
- **3D visualization**: React Three Fiber + Three.js

**Entry points:**
- **Renderer**: `gui/src/main.tsx` → `gui/src/App.tsx` (root component)
- **Main process**: `gui/electron/main.ts` (spawns Python daemon, manages IPC)
- **Preload**: `gui/electron/preload.ts` (exposes `window.qms` API via `contextBridge`)

**IPC model:**
- **Pattern**: Renderer → `window.qms.request(type, payload)` → Preload → Main (`ipcMain.handle('qms-request')`) → Python daemon (stdio JSON-RPC) → Response flows back
- **Types**: `gui/src/types/qms.ts` - centralized `QMSCommandMap` for end-to-end type safety
- **Hook**: `gui/src/hooks/useQMSClient.ts` - typed React hook wrapping `window.qms.request()`

**Layout/Routing:**
- **App shell**: `gui/src/App.tsx` - manages view state (`ViewType`), renders `Sidebar` + main panel
- **Panels**: `gui/src/components/panels/` - `JobsPanel`, `CalculationListPanel`, `StructureListPanel`, `QEParameterBrowserPanel`, `SettingsPanel`, etc.
- **No router**: View switching via state (`selectedView`, `selectedWorkflow`, etc.)

## 3) Daemon / Backend

**Startup:**
- **Entry**: `src/qmatsuite/daemon/server.py` - `python -m qmatsuite.daemon.server`
- **Communication**: stdio JSON-RPC (one JSON object per line on stdin/stdout)
- **Spawn**: Electron main process spawns Python daemon as subprocess, pipes stdin/stdout/stderr

**RPC surface:**
- **Handler registration**: `DaemonState` class in `server.py` maintains `_handlers` dict mapping command names to handler functions
- **Request parsing**: `_parse_request()` reads stdin line-by-line, validates JSON, extracts `id`, `type`, `payload`
- **Response**: `RPCResponse.to_json()` writes to stdout
- **Error handling**: Catches exceptions, returns `{"ok": false, "error": {...}}` with code/message

**Job system:**
- **Job model**: `src/qmatsuite/daemon/jobs.py` - `Job` dataclass (id, status, result, error, io_dir, steps)
- **Job manager**: `JobManager` with `ThreadPoolExecutor(max_workers=1)` for sequential execution
- **Execution**: `execute_job()` calls runner, updates job status/results, extracts `io_dir` from runner result
- **Calculation execution**: `_handle_run_calculation()` → `api.run_calculation()` → `CalculationRunner.run()` → `CalculationResult` with `io_dir`
- **I/O directory**: `compute_io_dir_from_workflow_model()` in `src/qmatsuite/calculation/runner.py` is single source of truth (default "raw")

**Metadata system:**
- **JSON location**: `src/qmatsuite/data/qe_module_parameters.json` (production), `*.legacy.v*.json` (archived)
- **Loader**: `src/qmatsuite/data/qe_metadata.py` - `load_metadata()` with `@lru_cache`, `safe_load_metadata()`, `reload_metadata()`
- **State tracking**: `QE_METADATA_LOAD_STATE` dict (loaded_via, loaded_at, schema_version, path_abs) for debug panel
- **RPC**: `list_qe_parameter_metadata`, `reload_qe_parameter_metadata`, `get_qe_parameter_metadata_debug_info`

## 4) Calculation/Project Model

**Concepts:**
- **Project**: Root directory with `project.qms.yml` (lists structures/calculations by ID only, DAG model)
- **Structure**: Crystal structure (JSON file in `structures/`, referenced by ULID)
- **Calculation**: YAML file (`calculation.yaml`) with `structure_id` (ULID), `working_dir` (I/O dir name, default "raw"), `steps` list (step_id ULIDs)
- **Step**: YAML file (`steps/*.step.yaml`) with step-local config (type, input, parameters), inherits `structure_id` from calculation

**YAML formats:**
- **Parser**: `src/qmatsuite/core/models.py` - `load_calculation()`, `save_calculation()`, `CalculationModel` dataclass
- **Calculation YAML**: `id`, `structure_id`, `working_dir`, `steps: [{step_id, type, input, reference}]`
- **Step YAML**: `id`, `type`, `input`, `parameters`, etc. (no cross-resource IDs except inherited structure_id)

**IDs/Selectors:**
- **ULIDs**: All resources use ULID (`ulid-py`) for stable IDs
- **Resolution**: `src/qmatsuite/core/resolution.py` - `resolve_calculation()`, `resolve_step()` convert selectors (name/slug/ID) to `ResolvedResource`
- **Registry**: `ResourceIndex` built from `project.qms.yml` + filesystem scan, cached per-project in daemon

## 5) Tests and CI

**Test locations:**
- **Unit tests**: `tests/unit/` - Python unit tests (pytest)
- **Integration tests**: `tests/integration/` - Full calculation execution tests
- **Daemon tests**: `tests/daemon/` - JSON-RPC protocol tests
- **E2E tests**: `gui/tests/e2e/` - Playwright tests for Electron GUI

**E2E setup:**
- **Playwright**: `gui/tests/e2e/` - uses `@playwright/test` with Electron support
- **Launch**: `gui/tests/e2e/helpers/electron.ts` - spawns Electron app, connects via CDP
- **Build**: `npm run build:e2e` (TypeScript + Vite), then `playwright test`

**CI calculation:**
- **File**: `.github/workflows/tests.yml`
- **Steps**: Checkout → Set QE env vars → Install Python → Install system deps → Cache QE source/install/ccache → Build QE (if cache miss) → Install Python deps → Run pytest (`-n auto --dist=loadfile`) → Run GUI e2e (`npm run test:e2e`)
- **QE caching**: Caches QE source tarball, built install prefix (per OS/build opts), ccache

## 6) Data and Docs

**Static data:**
- **QE metadata**: `src/qmatsuite/data/qe_module_parameters.json` (schema v3), `*.legacy.v*.json` (v0/v1/v2)
- **UI parameters**: `src/qmatsuite/data/qe_ui_parameters.json` - UI-friendly parameter metadata
- **Templates**: `resources/calculation_templates/` - YAML templates
- **Demos**: `resources/demo_projects/` - example projects
- **Structures**: `resources/structure_library/` - example crystal structures

**Documentation:**
- **Architecture**: `docs/ARCHITECTURE.md` - layered structure, calculation execution
- **API references**: `docs/DAEMON_API_REFERENCE.md`, `docs/CLI_API_REFERENCE.md`
- **GUI**: `docs/GUI_ARCHITECTURE.md` - IPC patterns, component structure
- **QE metadata**: `docs/JOB_IO_DIRECTORY_SEMANTICS.md` - io_dir semantics, runner source of truth

## 7) "Most Important" Call Graphs

**Launch GUI → start daemon → list jobs → show job detail:**
1. Electron main (`gui/electron/main.ts`) spawns Python daemon subprocess on `app.whenReady()`
2. Renderer (`gui/src/App.tsx`) mounts, `useQMSClient()` hook calls `window.qms.request('list_jobs', {})`
3. Preload (`gui/electron/preload.ts`) forwards to main via `ipcRenderer.invoke('qms-request')`
4. Main (`gui/electron/main.ts`) writes JSON-RPC request to daemon stdin, waits for stdout response
5. Daemon (`src/qmatsuite/daemon/server.py`) `_handle_list_jobs()` → `JobManager.list_jobs()` → returns `JobSummary[]`
6. Response flows back: daemon stdout → main → IPC → renderer → `JobsPanel` displays list
7. User selects job → `JobsPanel` calls `window.qms.request('get_job_status', {job_id})` → daemon returns `Job` with `io_dir`, `steps`, `result`

**QE Parameter Browser: list modules/sections/parameters and reload metadata:**
1. `QEParameterBrowserPanel` mounts → calls `qms.listQeParameterMetadata('list_modules', {})`
2. Daemon `_handle_list_qe_parameter_metadata()` → `list_supported_modules()` from `src/qmatsuite/data/qe_metadata.py`
3. `load_metadata()` checks `@lru_cache`, loads `qe_module_parameters.json`, updates `QE_METADATA_LOAD_STATE`
4. Returns module list → GUI displays in dropdown
5. User selects module → `list_sections` → `get_module_param_sections(module)` → returns namelist sections
6. User clicks "Reload metadata" → `reload_qe_parameter_metadata` → `reload_metadata()` clears cache, reloads JSON, updates load state
7. Debug panel (`SettingsPanel`) calls `get_qe_parameter_metadata_debug_info` → returns `loaded_via`, `loaded_at`, `schema_version`, `path_abs`


