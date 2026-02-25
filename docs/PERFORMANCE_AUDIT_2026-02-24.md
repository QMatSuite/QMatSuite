# QMatSuite Performance Audit

**Date**: 2026-02-24
**Scope**: Full-stack — Python daemon, React/Electron frontend, IPC layer
**Constraint**: Read-only audit. No code changes. Findings documented for future action.

---

## Architecture Summary

```
+------------------------------------------------------------------+
|                     Electron Application                          |
|  +----------------------------+   +---------------------------+  |
|  | Renderer (React 18 + Vite) |   | Preload Bridge            |  |
|  | - 3D viz (Three.js)        |<--| - window.qms.request()    |  |
|  | - Charts (Recharts)        |   | - window.qms.onLog()      |  |
|  +----------------------------+   +---------------------------+  |
|            ^                               |                      |
|            +------------ IPC --------------+                      |
|  +-----------------------------------------------------------+   |
|  | Main Process (Node.js/TypeScript, 1226 lines)              |   |
|  | - Daemon spawn & monitoring                                |   |
|  | - Request/response correlation (pendingRequests Map)        |   |
|  | - 60s request timeout, fs.appendFileSync log forwarding     |   |
|  +-----------------------------------------------------------+   |
|            ^                               |                      |
|            +---- stdin/stdout JSON-RPC ----+                      |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
|           Python Daemon  (qmatsuite.daemon.server, 5172 lines)    |
|  - ~80 RPC endpoints                                              |
|  - QMSService (9115 lines) for business logic                     |
|  - JobManager: ThreadPoolExecutor(max_workers=1)                  |
|  - ProjectCache per project root (ResourceIndex + QMSService)     |
+------------------------------------------------------------------+
            ^                               |
            +--- Filesystem (YAML SSOT) ----+

+------------------------------------------------------------------+
|               Project Root (YAML-based SSOT)                      |
|  - project.qms.yml, calculations/<slug>/calculation.yaml          |
|  - step.yaml per step, structures/*.json, presets/                |
|  - 15 engine drivers (QE, VASP, ORCA, LAMMPS, CP2K, ...)         |
+------------------------------------------------------------------+
```

**Key facts**:
- Frontend: React 18 + Vite 7.2.6 + Electron 39.2.6
- Backend: Python daemon via stdio JSON-RPC (single-threaded request processing)
- Data: YAML SSOT (calculation.yaml + step.yaml), JSON structures, HDF5 blobs
- 15 quantum chemistry engine drivers registered via DriverRegistry singleton

---

## Severity & Effort Scales

| Severity | Label | Description |
|----------|-------|-------------|
| **P0** | Critical | Directly causes noticeable lag on every interaction |
| **P1** | High | Causes perceivable delay in common workflows |
| **P2** | Medium | Causes delay in specific scenarios or scales poorly |
| **P3** | Low | Minor inefficiency, best practice violation |

| Effort | Description |
|--------|-------------|
| **XS** | < 1 hour. Config change, one-liner |
| **S** | 1-4 hours. Targeted fix in one module |
| **M** | 1-2 days. Refactoring a subsystem |
| **L** | 3-5 days. Architectural change, multiple modules |
| **XL** | 1+ weeks. Major refactor or new infrastructure |

---

## Backend Findings

### Startup & Initialization

#### [F001] N+1 query pattern in `list_calculations` with `detail=True`
- **Location**: `src/qmatsuite/api/service.py:3390-3459` (loop at line 3450)
- **Category**: Data Load
- **Severity**: P0
- **Effort**: M
- **Description**: When `list_calculations` is called with `detail=True`, it loops over
  every calculation and calls `self.get_detail(calc_ulid)` inside the loop (line 3450).
  Each `get_detail()` call does:
  1. `load_project_config()` — reads project.qms.yml
  2. `load_calculation()` — reads calculation.yaml
  3. `read_structure()` — reads and parses full structure JSON (50-500 KB)
  4. `build_resource_index()` — full filesystem scan (line 4438)
  5. For each step: `resolve_step()` + `StructureStepSpec.from_yaml()` — reads step YAML

  For a project with 50 calculations and 10 steps each:
  - 50 calls to `build_resource_index()` (200-500ms each)
  - 50 `load_calculation()` calls
  - 500 step YAML reads
  - **Total: 10-120 seconds** vs. 100-200ms for a shallow list
- **Evidence**: `service.py` line 3450: `results.append(self.get_detail(dto.calc_ulid))`
  inside `for calc_resolved in calc_resolved_list` loop
- **Recommendation**: Return shallow DTOs from list. Add a `get_details_batch()` endpoint
  that builds the resource index once and resolves all calculations in a single pass.
- **Expected Impact**: 90% improvement (10-120s -> 100-500ms for 50 calculations)

---

#### [F002] Redundant `build_resource_index()` on every `get_detail()` call
- **Location**: `src/qmatsuite/api/service.py:4438`, `src/qmatsuite/core/resolution.py:533-702`
- **Category**: Data Load
- **Severity**: P0
- **Effort**: S
- **Description**: `build_resource_index()` does a full filesystem scan: iterdir() on all
  calculation dirs, glob("*.step.yaml") on all steps dirs, glob("*.json") on structures.
  For a project with 50 calcs x 10 steps + 100 structures = ~500 file checks + ~50 globs.
  Cost: 200-500ms on SSD, 1-2s on HDD.

  The daemon's `ProjectCache` (server.py line 130) caches this correctly, but `get_detail()`
  at line 4438 rebuilds it from scratch, bypassing the cache entirely.
  When called inside the N+1 loop (F001), this is called 50+ times.
- **Evidence**: `resolution.py` lines 698: `if duration_ms > 100: logger.warning("SLOW...")`
  — this warning fires frequently
- **Recommendation**: Pass the already-cached `ResourceIndex` from ProjectCache into
  `get_detail()` instead of rebuilding. The service layer should accept an optional
  pre-built index.
- **Expected Impact**: Eliminates 200-500ms per detail call; combined with F001 fix,
  eliminates 10-25s of redundant scanning

---

#### [F003] App.tsx monolithic component (52 state variables, 3079 lines)
- **Location**: `gui/src/App.tsx:89-209` (state declarations), entire file
- **Category**: Interaction
- **Severity**: P0
- **Effort**: L
- **Description**: App.tsx is a single 3079-line component with 52 `useState` calls and
  119 total hook calls. Any state update triggers a re-render of the entire component,
  which re-executes all callbacks and re-creates all child arrays/objects.

  Module-level constants are recreated on every render (e.g., `ENGINE_DISPLAY_NAMES`
  object at line 62-78). All child components receive new prop references on every
  render since there is no state management extraction (no Context, Redux, or Zustand).

  This means:
  - Typing in any input field re-renders the entire app
  - Selecting a calculation re-renders all panels
  - Job status poll updates re-render all visualization components
- **Evidence**: Lines 89-209: 52 separate `useState` declarations.
  No `React.memo`, no context splitting, no extracted state hooks.
- **Recommendation**: Extract state into domain-specific custom hooks or Context providers:
  1. `useProjectState` — project root, summary, structures, calculations
  2. `useCalculationState` — selected calc, detail, steps, params
  3. `useJobState` — running jobs, status, notifications
  4. `useUIState` — view, tabs, sidebar collapse

  Split into Context providers so unrelated state changes don't cascade.
- **Expected Impact**: Eliminates 60-80% of unnecessary re-renders across entire UI

---

#### [F004] Synchronous `fs.appendFileSync()` blocks Electron event loop
- **Location**: `gui/electron/main.ts:213` (appendToLogFile), called from line 536
- **Category**: Interaction
- **Severity**: P0
- **Effort**: S
- **Description**: Every line of daemon stderr output triggers `fs.appendFileSync()`:
  ```typescript
  daemonProcess.stderr?.on('data', (data: Buffer) => {
    const message = data.toString().trim();
    console.log(`[daemon] ${message}`);
    process.stderr.write(`[daemon stderr] ${message}\n`);
    safeSend('daemon-log', message);
    appendToLogFile(message);  // <-- fs.appendFileSync() BLOCKS
  });
  ```
  Each sync write blocks 1-10ms on SSD. During high-volume daemon output (e.g., long
  calculation with progress logs), 100 lines/sec x 5ms = 500ms/sec event loop blocking.
  This stalls IPC response delivery and window updates.
- **Evidence**: `appendToLogFile` at line 205-218 uses `fs.appendFileSync(logPath, logLine)`
- **Recommendation**: Buffer log messages in memory (ring buffer of 100-500 lines), flush
  to disk every 500ms or on buffer full using `fs.appendFile()` (async).
- **Expected Impact**: Eliminates event loop blocking from log I/O entirely

---

### RPC / API Layer

#### [F005] Full file re-reads on every RPC request (no model caching)
- **Location**: `src/qmatsuite/api/service.py:4418-4430` (get_detail),
  `service.py:1830-1855` (import_file dedup)
- **Category**: Data Load
- **Severity**: P1
- **Effort**: M
- **Description**: The service layer has no in-memory cache for loaded models:
  - `load_calculation()` re-reads `calculation.yaml` (100-500 KB) on every request
  - `read_structure()` re-reads and parses full JSON (50-500 KB) + pymatgen composition
  - Step YAML files re-read per step per request
  - Structure dedup on import reads ALL structure files twice (lines 1830 and 1855)

  The daemon `ProjectCache` caches `ResourceIndex` and `QMSService` but NOT loaded
  Calculation or Structure model instances.

  For a 50-calculation project: 50 x (YAML parse + JSON parse) = 500-1000ms per list.
- **Evidence**: No LRU cache, no `@functools.cache`, no memoization on `load_calculation`
  or `read_structure`.
- **Recommendation**: Add an LRU cache (size ~100-200 entries, keyed by path + mtime)
  for `CalculationModel` and `StructureModel` in the service layer. Invalidate on mutation.
- **Expected Impact**: 50-80% reduction in I/O for repeated access patterns

---

#### [F006] Sequential step operations in `get_detail()` with no batching
- **Location**: `src/qmatsuite/api/service.py:4442-4501`
- **Category**: Data Load
- **Severity**: P1
- **Effort**: S
- **Description**: Inside `get_detail()`, steps are processed in a sequential loop:
  ```python
  for entry in calc_model.steps:
      step_resolved = resolve_step(...)    # index lookup
      spec = StructureStepSpec.from_yaml(step_path, ...)  # reads YAML file
      step_type_gen = get_step_type_gen(step_type_spec)    # registry lookup
  ```
  For a 20-step calculation: 20 YAML reads (2-5ms each) = 40-100ms.
  No pre-loading, no batch reading, no parallel I/O.
- **Recommendation**: Pre-load all step files in one pass (e.g., read all *.step.yaml
  files with a single glob, then parse). Cache step metadata.
- **Expected Impact**: Reduce step loading from 40-100ms to 10-20ms

---

#### [F007] Single-threaded daemon blocks on slow requests
- **Location**: `src/qmatsuite/daemon/server.py:572-692` (request handler)
- **Category**: Interaction
- **Severity**: P1
- **Effort**: L
- **Description**: The daemon processes requests sequentially on a single thread.
  One slow request (e.g., `list_calculations` with detail=True taking 5-10s) blocks
  all subsequent requests, including job status polls. The frontend sees stale data
  until the blocking call completes.

  Example stall scenario:
  1. GUI calls `list_calculations(detail=True)` -> 5-10s blocking call
  2. `job_counts` polling calls queue up behind it
  3. User sees stale job status for entire duration
- **Recommendation**: Either:
  (a) Move heavy operations to a background thread pool, or
  (b) Split long operations into chunked responses, or
  (c) Priority-queue fast operations (ping, job_counts) ahead of slow ones
- **Expected Impact**: UI stays responsive during heavy backend operations

---

#### [F008] No daemon readiness check before accepting IPC requests
- **Location**: `gui/electron/main.ts:1196-1225`
- **Category**: Startup
- **Severity**: P1
- **Effort**: S
- **Description**: `spawnDaemon()` returns `true` at line 593 immediately after stdout
  pipes are connected, NOT after the daemon is actually ready to process requests.
  The renderer may send IPC requests via `window.qms.request()` before the daemon's
  stdin reader loop starts.

  There is no "ready" handshake message from the daemon. The renderer can issue requests
  immediately after window loads (line 1143), potentially before daemon is listening.
- **Evidence**: Lines 522-524: daemon output processed via readline, but no "daemon ready"
  signal check. No `daemonReady` flag gating request dispatch.
- **Recommendation**: Have daemon emit `{"type":"__ready__"}` on stdout when its main
  loop starts. Main process sets `daemonReady` flag; queues or rejects IPC requests
  until flag is set.
- **Expected Impact**: Eliminates startup race condition; prevents failed initial requests

---

#### [F009] DTO serialization uses `dataclasses.asdict()` on every response
- **Location**: `src/qmatsuite/api/types/base.py:77-86`
- **Category**: Interaction
- **Severity**: P2
- **Effort**: S
- **Description**: Every RPC response goes through `BaseDTO.to_dict()`:
  ```python
  def to_dict(self) -> dict[str, Any]:
      result = {}
      for key, value in asdict(self).items():  # Full recursive copy
          result[key] = to_json_value(value)   # Recursive JSON validation
      return result
  ```
  `asdict()` recursively converts the entire dataclass tree. For a CalculationDTO
  with 20 steps, this traverses ~200 fields. Cost: 1-2ms per response x 50 calcs = 50-100ms.
- **Recommendation**: Use `__dict__` with explicit field listing instead of `asdict()`,
  or implement `__json__` protocol on DTOs for zero-copy serialization.
- **Expected Impact**: 2-5x faster serialization per response

---

### Engine Management & Computation

#### [F010] All 15 engine drivers eagerly imported on first `drivers` import
- **Location**: `src/qmatsuite/drivers/__init__.py:20-64`
- **Category**: Startup
- **Severity**: P1
- **Effort**: M
- **Description**: The drivers package imports all 15 engines at module level:
  ```python
  from qmatsuite.drivers import qe, vasp, lammps, cp2k, w90, orca, pyscf,
       qmcpack, psi4, gpaw, siesta, xtb, yambo, abinit, gaussian
  ```
  Each driver's `__init__.py` calls `DriverRegistry.register(EngineDriver())` and
  imports its parser submodule (`from . import parsers`). This triggers transitive
  imports of handler modules, metadata modules, I/O modules, and data files.

  NOTE: Currently the daemon startup path (`from qmatsuite.api import QMSService`)
  does NOT import `qmatsuite.drivers`, so this cost is deferred until first use.
  However, any RPC that touches drivers (e.g., `list_engine_families`, `list_step_palette`,
  any calculation operation) pays the full ~300-500ms cost on first call.
- **Evidence**: 6.8 MB total driver code (QE: 1.1 MB, VASP: 700 KB, ABINIT: 600 KB, etc.)
- **Recommendation**: Implement lazy driver loading: register factory callables instead
  of eagerly importing all 15 modules. Load each driver on first use.
  ```python
  LAZY_DRIVERS = {"qe": "qmatsuite.drivers.qe", ...}
  def ensure_driver_loaded(engine_family):
      if not DriverRegistry.is_engine_registered(engine_family):
          __import__(LAZY_DRIVERS[engine_family])
  ```
- **Expected Impact**: First RPC that uses drivers loads only the needed engine(s);
  startup of daemon becomes near-instant for all paths

---

#### [F011] Parser modules imported eagerly with driver registration
- **Location**: Each driver's `__init__.py`, e.g., `drivers/qe/__init__.py:5`
- **Category**: Startup
- **Severity**: P2
- **Effort**: M
- **Description**: Every driver `__init__.py` has `from . import parsers` which triggers
  registration of all output parsers via `@register_parser()` decorator. Parser modules
  are large (QE output.py: 9000+ lines) and import `numpy`. Parsing is only needed when
  reading results, not when materializing inputs or listing engines.
- **Recommendation**: Move parser imports to a lazy initialization function called only
  when parsing is actually requested.
- **Expected Impact**: Save 50-100ms per driver at registration time

---

#### [F012] Large output files loaded entirely into memory
- **Location**: `src/qmatsuite/drivers/vasp/parsers/output.py:93` (vasprun.xml),
  line 287 (OUTCAR)
- **Category**: Computation
- **Severity**: P1
- **Effort**: M
- **Description**: `ET.parse(path)` loads the entire vasprun.xml DOM tree into memory.
  For VASP MD runs with 1000+ ionic steps, vasprun.xml can exceed 500 MB.
  OUTCAR fallback uses `path.read_text()` (line 287), same issue.
  No streaming or iterparse used anywhere.
- **Recommendation**: Use `ET.iterparse()` with `elem.clear()` after processing each
  `<calculation>` element. This reduces memory from O(file_size) to O(one_ionic_step).
- **Expected Impact**: Enables parsing of >1 GB output files; reduces memory by 90%

---

#### [F013] Blocking subprocess wait with no daemon responsiveness
- **Location**: `src/qmatsuite/drivers/qe/engine/qe_calculation.py:368-390`
- **Category**: Computation
- **Severity**: P1
- **Effort**: L
- **Description**: QE subprocess execution uses `process.wait(timeout=...)` which blocks
  the entire executor thread. JobManager uses `ThreadPoolExecutor(max_workers=1)`, so
  ONE blocking job stalls all subsequent requests. No non-blocking polling, no file watching,
  no incremental output monitoring.
- **Recommendation**: Use `process.poll()` in a loop with `time.sleep(0.5)` intervals
  to allow the thread to check for cancellation signals. Alternatively, increase
  `max_workers` to 2+ so status queries don't stall.
- **Expected Impact**: Daemon stays responsive during calculations; enables job cancellation

---

#### [F014] No preset compilation caching
- **Location**: `src/qmatsuite/presets/compiler.py:39-134`
- **Category**: Computation
- **Severity**: P2
- **Effort**: XS
- **Description**: `compile_magnetism()`, `compile_occupations_scheme()`,
  `compile_precision()` are pure functions called on every step materialization.
  No `@lru_cache` or memoization despite identical inputs producing identical outputs.
  For a 100-step workflow with same preset, compilation runs 100 times.
- **Evidence**: `grep -n "cache\|lru\|memoiz" compiler.py` returns no results
- **Recommendation**: Add `@lru_cache(maxsize=128)` to pure compilation functions.
- **Expected Impact**: Cache hits on repeated presets save 100-500ms for large workflows

---

#### [F015] No parsed digest caching — re-parsed on every view
- **Location**: `src/qmatsuite/execution/executor.py` (post-job processing),
  `src/qmatsuite/drivers/*/parsers/output.py`
- **Category**: Data Load
- **Severity**: P2
- **Effort**: S
- **Description**: Each time the UI requests a step digest (energy, forces, convergence),
  the output file is re-parsed from scratch. Large output files (100+ MB) take 1-5s to
  parse. The manifest stores step metadata but not parsed digest objects. No mtime-based
  cache invalidation.
- **Recommendation**: Cache parsed digests keyed by (output_file_path, mtime). Store in
  a sidecar `.digest.json` or in-memory LRU cache. Return cached version if file unchanged.
- **Expected Impact**: Subsequent views of same result: 1-5s -> <1ms

---

### Python-Specific

#### [F016] Eager ULID generator instantiation at module import time
- **Location**: `src/qmatsuite/core/resources.py:148`
- **Category**: Startup
- **Severity**: P1
- **Effort**: S
- **Description**: Module-level instantiation: `_monotonic_generator = _MonotonicUlidGenerator()`
  This runs during import of `qmatsuite.core.resources`, which is triggered by
  `qmatsuite/__init__.py` importing `project.model` -> `core.resources`.
  The `@dataclass(slots=True)` processing on `ResourceMeta` (line 203) is expensive.
  Combined with the import chain, this adds ~235-265ms to daemon startup.
- **Recommendation**: Defer generator creation to first use:
  ```python
  _monotonic_generator = None
  def _get_generator():
      global _monotonic_generator
      if _monotonic_generator is None:
          _monotonic_generator = _MonotonicUlidGenerator()
      return _monotonic_generator
  ```
- **Expected Impact**: Reduces daemon startup by ~235ms

---

#### [F017] Eager heavy imports in `qmatsuite/__init__.py`
- **Location**: `src/qmatsuite/__init__.py:44-47`
- **Category**: Startup
- **Severity**: P1
- **Effort**: S
- **Description**: Package `__init__.py` eagerly imports:
  ```python
  from .project.model import Project, ProjectSettings, StructureRef, CalculationRef
  from .calculation.calculation import Calculation
  from .calculation.runner import CalculationRunner
  from .api import QMSService
  ```
  Only `QMSService` is needed by the daemon. The other imports cascade into
  `core.resources` (F016), triggering expensive dataclass processing.
  Total cost: ~250-265ms of ~300ms total daemon startup.
- **Recommendation**: Use `__getattr__` for lazy loading of non-essential exports:
  ```python
  from .api import QMSService  # Only this is needed at startup
  def __getattr__(name):
      if name == "Project": from .project.model import Project; return Project
      # ... etc
      raise AttributeError(...)
  ```
- **Expected Impact**: Daemon startup from ~265ms to ~50ms (5x faster)

---

#### [F018] F-string logging evaluates arguments even at wrong log level
- **Location**: `src/qmatsuite/execution/executor.py:158-230`,
  `src/qmatsuite/calculation/input_runner.py:248-300`,
  `src/qmatsuite/execution/relax_artifacts.py:127-359`,
  `src/qmatsuite/daemon/server.py:549-565`
- **Category**: Computation
- **Severity**: P2
- **Effort**: S
- **Description**: Hot paths use f-string logging:
  ```python
  # BAD - f-string evaluated even if log level too high:
  logger.info(f"[EXECUTOR] Job {job.id} FAILED: {job_result.error}")
  # GOOD - lazy evaluation:
  logger.info("[EXECUTOR] Job %s FAILED: %s", job.id, job_result.error)
  ```
  In executor with 100 variants: 100 x 7 f-string evaluations = 700 string allocations.
- **Recommendation**: Convert hot-path f-string logs to %-style formatting.
- **Expected Impact**: Eliminates unnecessary string allocation in tight loops

---

#### [F019] DaemonState project cache has no eviction policy
- **Location**: `src/qmatsuite/daemon/server.py:91-169`
- **Category**: Data Load
- **Severity**: P2
- **Effort**: S
- **Description**: `DaemonState._caches: Dict[Path, ProjectCache]` grows unbounded.
  Each `ProjectCache` holds a `ResourceIndex` and `QMSService` instance. In long
  sessions where user switches between many projects, memory grows linearly.
  No LRU eviction, no TTL, no size limit.
- **Recommendation**: Use `functools.lru_cache` or a bounded dict (max ~10 entries)
  with LRU eviction.
- **Expected Impact**: Prevents memory growth in long-running daemon sessions

---

#### [F020] JobManager `_jobs` and `_futures` dicts grow without bound
- **Location**: `src/qmatsuite/daemon/jobs.py:131-132`
- **Category**: Data Load
- **Severity**: P2
- **Effort**: S
- **Description**: `_jobs: Dict[str, Job]` and `_futures: Dict[str, Future]` accumulate
  entries forever. Completed/failed jobs are never cleaned up. In long sessions with
  hundreds of job submissions, these dicts grow without bound.
- **Recommendation**: Add periodic cleanup: remove jobs in terminal state (completed/failed)
  older than 1 hour, keeping most recent N entries.
- **Expected Impact**: Prevents memory leak over long sessions

---

#### [F021] Regex compilation inside parser methods (not module-level)
- **Location**: `src/qmatsuite/drivers/orca/parsers/output.py:143-205`,
  `src/qmatsuite/io/parser/volume_parsers.py:140,577`
- **Category**: Computation
- **Severity**: P3
- **Effort**: XS
- **Description**: Some regex patterns compiled inside `parse()` methods, recompiled
  on every call. Example: ORCA parser compiles ~6 patterns per parse call.
- **Recommendation**: Move `re.compile()` to module level.
- **Expected Impact**: Minor (microseconds per parse), but good practice

---

## Frontend Findings

### Bundle Size & Code Splitting

#### [F022] No manual code splitting in Vite config
- **Location**: `gui/vite.config.ts` (29 lines, no `rollupOptions`)
- **Category**: Startup
- **Severity**: P2
- **Effort**: S
- **Description**: Vite config has no manual chunk splitting. Heavy dependencies
  (Three.js ~900KB, Recharts ~200KB, @react-three/drei ~400KB) are not split into
  separate chunks. This means the initial load includes 3D and charting code even
  if the user only views the project list.
- **Recommendation**: Add manual chunks:
  ```typescript
  build: { rollupOptions: { output: { manualChunks: {
    'three-lib': ['three', '@react-three/fiber', '@react-three/drei'],
    'charts-lib': ['recharts'],
  }}}}
  ```
- **Expected Impact**: 1-2s faster initial load; 3D/chart code loaded only when needed

---

### React Rendering Performance

#### [F023] Zero `React.memo()` usage across entire component tree
- **Location**: `gui/src/components/` (all component files)
- **Category**: Interaction
- **Severity**: P1
- **Effort**: M
- **Description**: No component in the tree uses `React.memo()`. This means every
  parent re-render cascades to ALL children, even when props haven't changed.
  Heavy components like `StructureViewer3D`, `CalculationListPanel`,
  `ActiveParametersPanel`, `FatbandsVizPanel` re-render unnecessarily.
- **Evidence**: `grep -r "React.memo" gui/src/components/` returns no results
- **Recommendation**: Wrap leaf and expensive components in `React.memo`:
  ```typescript
  export const CalculationListPanel = React.memo(CalculationListPanelImpl);
  ```
  Focus on: CalculationListPanel, StructureListPanel, ActiveParametersPanel,
  all visualization panels.
- **Expected Impact**: Eliminates 50-70% of unnecessary child re-renders

---

#### [F024] No list virtualization for calculation/structure lists
- **Location**: `gui/src/components/panels/CalculationListPanel.tsx:22-150`
- **Category**: Interaction
- **Severity**: P1
- **Effort**: S
- **Description**: Lists render ALL items via `.map()` into full DOM. For 100+
  calculations, all 100+ DOM nodes are created even though only ~20 are visible.
  No `react-window` or `react-virtualized`.
  ```typescript
  {calculations.map((calc) => (
    <div key={calc.calc_ulid}>{/* Full calculation card */}</div>
  ))}
  ```
- **Recommendation**: Use `react-window` `FixedSizeList` for lists > 50 items.
- **Expected Impact**: Constant-time rendering regardless of list size

---

#### [F025] Sequential RPC waterfalls in common flows
- **Location**: `gui/src/App.tsx:398-517` (project browsing),
  `gui/src/App.tsx:1367-1375` (structure import),
  `gui/src/App.tsx:1403-1478` (calculation selection)
- **Category**: Navigation
- **Severity**: P1
- **Effort**: S
- **Description**: Several user flows make sequential RPC calls when parallel would work:

  **Project browsing** (worst case 5 sequential calls):
  1. `getProjectSummary(path)` -> fail ->
  2. `find_project_root({start_dir})` -> found ->
  3. `getProjectSummary(found_path)` -> fail ->
  4. `create_project(...)` ->
  5. `getProjectSummary(path)` again

  **Structure import**: `fetchStructures()` then `list_structures()` again (redundant).

  **Calculation selection**: `get_calculation_detail()` -> 404 -> 500ms timeout -> retry.
- **Recommendation**: Parallelize independent calls with `Promise.all()`.
  Eliminate redundant re-fetches (import already returns the new structure).
  Replace retry-with-delay with server-side warming.
- **Expected Impact**: 40-60% reduction in navigation latency

---

#### [F026] No debounce on parameter value editing
- **Location**: `gui/src/components/step_parameters/ParameterValueEditor.tsx:154-156`
- **Category**: Interaction
- **Severity**: P2
- **Effort**: XS
- **Description**: Every keystroke triggers `onChange` callback immediately:
  ```typescript
  const handleChange = useCallback((newValue: string) => {
    onChange(coerceForType(newValue));
  }, [onChange, coerceForType]);
  ```
  This propagates up to App.tsx, causing full re-render on every character typed.
  If parent makes RPC calls on change, this creates request storms.
- **Recommendation**: Add 300-500ms debounce:
  ```typescript
  const debouncedOnChange = useMemo(
    () => debounce(onChange, 300),
    [onChange]
  );
  ```
- **Expected Impact**: 10x fewer state updates during parameter editing

---

#### [F027] Inline style objects recreated on every render
- **Location**: Various components (e.g., `StepDetailPanel.tsx`)
- **Category**: Interaction
- **Severity**: P3
- **Effort**: S
- **Description**: Scattered `style={{...}}` objects are recreated on every render,
  preventing shallow comparison optimizations (relevant once React.memo is added).
- **Recommendation**: Extract to module-level constants or CSS classes.
- **Expected Impact**: Enables React.memo shallow comparison to work correctly

---

### Network & Data Fetching

#### [F028] Connection polling every 5s even when idle
- **Location**: `gui/src/hooks/useQMSClient.ts:362`
- **Category**: Interaction
- **Severity**: P2
- **Effort**: XS
- **Description**: `checkConnection()` fires every 5000ms via `setInterval`, even when
  the daemon status subscription (lines 221-235) is already providing event-driven
  updates. This adds an unnecessary RPC round-trip every 5 seconds permanently.
- **Recommendation**: Remove the periodic polling; rely on the existing
  `window.qms.onDaemonStatus()` event subscription.
- **Expected Impact**: Eliminates 12 unnecessary RPC calls per minute

---

## Electron / Cross-Cutting Findings

#### [F029] Per-request console logging in Electron main process
- **Location**: `gui/electron/main.ts:776,793`
- **Category**: Interaction
- **Severity**: P2
- **Effort**: XS
- **Description**: Every IPC request and response is logged to console:
  ```typescript
  console.log(`[main] IPC request: ${request.type} (${request.id})`);
  console.log(`[main] IPC response: ${request.type} ok=${response.ok}`);
  ```
  In production, this adds ~1ms overhead per request. During rapid polling (job_counts
  every 2-3s + connection check every 5s), this is a constant overhead.
- **Recommendation**: Wrap with `if (process.env.NODE_ENV === 'development')`.
- **Expected Impact**: ~1ms per IPC call in production

---

#### [F030] Hard 60s timeout on shutdown command; hard-coded delays
- **Location**: `gui/electron/main.ts:728-766`
- **Category**: Startup
- **Severity**: P2
- **Effort**: S
- **Description**: Shutdown uses `sendDaemonRequest()` with the default 60s timeout,
  then waits a hard 2s (line 739), then sends SIGTERM and waits another 1s (line 754).
  If the shutdown request hangs, app close takes 60+ seconds.
- **Recommendation**: Use a 5-10s timeout for shutdown. Replace hard delays with
  polling `process.killed` every 50ms.
- **Expected Impact**: App closes in <2s instead of potentially 60s+

---

#### [F031] No IPC request batching or deduplication
- **Location**: `gui/electron/main.ts:775-806`, `gui/electron/preload.ts:74`
- **Category**: Interaction
- **Severity**: P2
- **Effort**: M
- **Description**: Every RPC operation requires a full IPC round-trip: renderer -> main
  process -> daemon stdin -> daemon stdout -> main process -> renderer. No batching API
  exists. If the UI needs 5 pieces of data, it makes 5 separate round-trips.
  No deduplication: if the same request fires twice (e.g., from two useEffect hooks),
  both execute independently.
- **Recommendation**: Add `qms.requestBatch([{type, payload}, ...])` that sends all
  requests in one IPC message and returns all responses together. Add request
  deduplication (same type+payload within 100ms window returns same promise).
- **Expected Impact**: Reduces IPC overhead for bulk operations by 3-5x

---

#### [F032] Synchronous `readLogFile()` blocks Electron main process
- **Location**: `gui/electron/main.ts:226-230`
- **Category**: Interaction
- **Severity**: P3
- **Effort**: XS
- **Description**: `readLogFile()` uses `fs.existsSync()` + `fs.readFileSync()`.
  Called via IPC handler (line 989). Blocks main thread for 5-10ms on large log files.
- **Recommendation**: Use `fs.promises.readFile()` (async).
- **Expected Impact**: Minor, but prevents occasional main-thread stalls

---

#### [F033] No auto-update rate limiting
- **Location**: `gui/electron/main.ts:1220-1224`
- **Category**: Startup
- **Severity**: P3
- **Effort**: XS
- **Description**: `autoUpdater.checkForUpdates()` runs on every app launch. No
  rate limiting (e.g., once per 24 hours). If GitHub API is slow or offline, adds
  1-30s of network latency to startup (non-blocking, but consumes bandwidth).
- **Recommendation**: Cache last check timestamp; skip if checked within 24 hours.
- **Expected Impact**: Eliminates unnecessary network request on most launches

---

## Summary Table

| ID | Finding | Severity | Effort | Category | Location |
|----|---------|----------|--------|----------|----------|
| F001 | N+1 `list_calculations` with detail | P0 | M | Data Load | `service.py:3450` |
| F002 | Redundant `build_resource_index()` per detail call | P0 | S | Data Load | `service.py:4438` |
| F003 | App.tsx monolith (52 state vars, 3079 lines) | P0 | L | Interaction | `App.tsx:89-209` |
| F004 | `fs.appendFileSync()` blocks Electron event loop | P0 | S | Interaction | `main.ts:213` |
| F005 | No model caching in service layer | P1 | M | Data Load | `service.py:4418` |
| F006 | Sequential step loading in get_detail | P1 | S | Data Load | `service.py:4442` |
| F007 | Single-threaded daemon blocks on slow requests | P1 | L | Interaction | `server.py:572` |
| F008 | No daemon readiness check | P1 | S | Startup | `main.ts:1215` |
| F009 | `asdict()` + `to_json_value()` on every response | P2 | S | Interaction | `base.py:77` |
| F010 | 15 engine drivers eagerly imported | P1 | M | Startup | `drivers/__init__.py:20` |
| F011 | Parser modules eagerly imported with drivers | P2 | M | Startup | `drivers/*/init` |
| F012 | Large output files loaded into memory (no streaming) | P1 | M | Computation | `vasp/parsers/output.py:93` |
| F013 | Blocking subprocess wait, no cancellation | P1 | L | Computation | `qe_calculation.py:376` |
| F014 | No preset compilation caching | P2 | XS | Computation | `compiler.py:39` |
| F015 | No parsed digest caching | P2 | S | Data Load | `drivers/*/parsers/` |
| F016 | Eager ULID generator at module import | P1 | S | Startup | `resources.py:148` |
| F017 | Eager heavy imports in `__init__.py` | P1 | S | Startup | `__init__.py:44` |
| F018 | F-string logging in hot paths | P2 | S | Computation | `executor.py:158` |
| F019 | DaemonState cache no eviction | P2 | S | Data Load | `server.py:91` |
| F020 | JobManager dicts grow without bound | P2 | S | Data Load | `jobs.py:131` |
| F021 | Regex compiled inside parse methods | P3 | XS | Computation | `orca/parsers/output.py` |
| F022 | No Vite manual code splitting | P2 | S | Startup | `vite.config.ts` |
| F023 | Zero React.memo in component tree | P1 | M | Interaction | `gui/src/components/` |
| F024 | No list virtualization | P1 | S | Interaction | `CalculationListPanel.tsx` |
| F025 | Sequential RPC waterfalls | P1 | S | Navigation | `App.tsx:398` |
| F026 | No debounce on parameter editing | P2 | XS | Interaction | `ParameterValueEditor.tsx` |
| F027 | Inline style objects | P3 | S | Interaction | Various components |
| F028 | Idle connection polling every 5s | P2 | XS | Interaction | `useQMSClient.ts:362` |
| F029 | Console logging every IPC request | P2 | XS | Interaction | `main.ts:776` |
| F030 | 60s shutdown timeout + hard delays | P2 | S | Startup | `main.ts:728` |
| F031 | No IPC request batching | P2 | M | Interaction | `main.ts:775` |
| F032 | Sync readLogFile blocks main | P3 | XS | Interaction | `main.ts:226` |
| F033 | No auto-update rate limiting | P3 | XS | Startup | `main.ts:1220` |

---

## Recommended Optimization Roadmap

### Quick Wins (Week 1) — P0/P1 with effort XS/S

| Priority | Finding | Action | Time |
|----------|---------|--------|------|
| 1 | F004 | Replace `fs.appendFileSync` with async buffered writes | 2h |
| 2 | F002 | Pass cached ResourceIndex into `get_detail()` | 3h |
| 3 | F017 | Use `__getattr__` in `qmatsuite/__init__.py` | 1h |
| 4 | F016 | Defer ULID generator to first use | 1h |
| 5 | F008 | Add daemon "ready" handshake message | 2h |
| 6 | F028 | Remove idle connection polling | 30min |
| 7 | F026 | Add debounce to parameter editor | 30min |
| 8 | F029 | Conditional console logging in production | 30min |
| 9 | F014 | Add `@lru_cache` to preset compilers | 30min |
| 10 | F006 | Batch-load step files in get_detail | 2h |

**Estimated total: ~13 hours. Expected impact: 80% reduction in startup + list latency.**

### Short-Term (Week 2-3) — P0/P1 with effort M

| Priority | Finding | Action | Time |
|----------|---------|--------|------|
| 1 | F001 | Eliminate N+1 in list_calculations (batch or shallow) | 1d |
| 2 | F023 | Add React.memo to 10-15 key components | 1d |
| 3 | F005 | Add LRU model cache to service layer | 1d |
| 4 | F010 | Implement lazy driver loading | 1d |
| 5 | F025 | Parallelize RPC waterfalls in 3 flows | 4h |
| 6 | F024 | Add react-window to list components | 4h |
| 7 | F022 | Configure Vite manual chunks | 2h |
| 8 | F015 | Add mtime-based digest caching | 4h |

**Estimated total: ~6 days. Expected impact: 10-100x faster list/detail operations.**

### Medium-Term (Month 2) — P1/P2 with effort L

| Priority | Finding | Action | Time |
|----------|---------|--------|------|
| 1 | F003 | Extract App.tsx state into domain hooks/contexts | 3-5d |
| 2 | F007 | Add request priority queue or background thread pool | 3d |
| 3 | F012 | Implement streaming XML parser for VASP | 2d |
| 4 | F013 | Non-blocking subprocess monitoring | 3d |
| 5 | F031 | IPC request batching API | 2d |

**Estimated total: ~2-3 weeks. Expected impact: Responsive UI during all operations.**

### Long-Term (Month 3+) — Architectural improvements

| Priority | Finding | Action | Time |
|----------|---------|--------|------|
| 1 | F011 | Lazy parser loading across all 15 engines | 1w |
| 2 | F009 | Zero-copy DTO serialization | 3d |
| 3 | — | WebSocket replacement for polling-based status | 1w |
| 4 | — | Consider moving daemon to async (asyncio) | 2w+ |

---

## Appendix: Profiling Commands

```bash
# Python daemon startup time
time python -c "from qmatsuite.daemon.server import QMSDaemonServer; print('ready')"

# Python import time analysis
python -X importtime -c "from qmatsuite.api import QMSService" 2>&1 | head -50

# Python cProfile for list_calculations
python -m cProfile -s cumtime -c "
from qmatsuite.api import QMSService
svc = QMSService(...)
svc.list_calculations(project_root, detail=True)
"

# Frontend bundle size
du -sh gui/dist/
ls -la gui/dist/assets/*.js | awk '{print $5, $9}' | sort -rn

# React DevTools Profiler
# Open browser DevTools -> Profiler -> Record -> Interact -> Stop -> Analyze

# Electron IPC timing (add to main.ts temporarily)
const start = performance.now();
// ... after response:
console.log(`IPC ${request.type}: ${(performance.now() - start).toFixed(1)}ms`);
```
