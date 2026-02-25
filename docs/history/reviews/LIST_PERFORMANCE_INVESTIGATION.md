# list_calculations Performance Investigation

**Date**: 2026-02-24
**Benchmark project**: 50 calculations (85 steps), created from demo store
**Machine**: MacBook Pro (Darwin 25.2.0)

## Executive Summary

`list_calculations(detail=False)` takes **42.2 seconds** for 50 calculations. **96.2% of that time (40.6s)** is spent in `build_resource_index()`, which is called **389 times** — once per step resolution and structure lookup, scanning all ~140 YAML files each time. The fix is straightforward: pass a shared `ResourceIndex` through the call chain instead of rebuilding it from scratch on every resolve call.

## Call Tree

The full call path for `list(detail=False)` on 50 calculations:

```
svc.calculation.list(detail=False)                     # service.py:3390
├── list_calculations(project_root)                    # resolution.py:1799  [ONCE]
│   ├── _load_config(project_root)                     # resolution.py:1593  → reads project.qms.yml
│   └── _calculation_to_resolved(root, entry) × 50     # resolution.py:1239
│       └── for calc_dir in calculations_dir.iterdir() # O(n) scan per entry → O(n²) total
│           └── load_yaml_meta_subtree(calc_yaml)      # yaml_io.py:65  → yaml.safe_load
│
├── Project.open(project_root)                         # model.py:111  [ONCE]
│   ├── ProjectDoc.load(project.qms.yml)               # reads config
│   ├── _load_structures(root, entries)                 # model.py:145
│   │   └── build_resource_index(root)                 # ★ 1 call (~104ms)
│   └── _load_calculations(root, entries)              # model.py:244
│       └── build_resource_index(root)                 # ★ 1 call (~104ms)
│
└── FOR EACH calc_resolved (× 50):
    ├── load_calculation(calc_yaml, project_root)      # models.py:393
    │   ├── load_yaml_doc(calc_yaml)                   # yaml_io.py:105  → full YAML parse
    │   ├── CalculationModel.from_dict(data)            # pure dict ops, fast
    │   └── resolve_structure(root, structure_ulid)    # resolution.py:900
    │       └── build_resource_index(root)             # ★ 47 calls (~104ms each) = ~4.9s
    │
    ├── Calculation.from_yaml(calc_dir, project,       # calculation.py:169
    │                         materialize_steps=False)
    │   ├── CalcDoc.load(calculation.yaml)              # another YAML parse
    │   ├── project.get_structure(structure_ulid)       # dict lookup, fast
    │   ├── _build_step_inspection(step_data) × 85     # calculation.py:504  [PER STEP]
    │   │   ├── require_step(root, calc_sel, step_ulid) # resolution.py:1739
    │   │   │   └── resolve_step(root, calc, step)     # resolution.py:1302
    │   │   │       ├── resolve_calculation(root, sel)  # resolution.py:1098
    │   │   │       │   └── build_resource_index(root) # ★ 170 calls = ~17.7s
    │   │   │       └── build_resource_index(root)     # ★ 170 calls = ~17.7s
    │   │   ├── StepDoc.load(step_file)                 # YAML parse
    │   │   └── StructureStepSpec.from_yaml(...)        # more YAML, resolver setup
    │   │       └── load_project_config + make_resolver # per step!
    │   └── ensure_calculation_identity(calc_dir)       # calc_identity.py:17
    │       └── CalcDoc.load(calculation.yaml)          # ANOTHER YAML parse of same file
    │
    └── calculation_to_dto(resolved, model, obj)       # dto_mapping.py:339  [~11µs, negligible]
```

## Profiling Data

### cProfile Top Functions (cumulative time)

| Calls | Tot Time | Cum Time | Per Call | Function |
|------:|--------:|---------:|--------:|----------|
| 1 | 0.00s | 119.16s | 119.16s | `service.py:3390(list)` |
| 389 | 0.28s | 114.73s | 0.295s | `resolution.py:533(build_resource_index)` |
| 54,414 | 0.07s | 112.12s | 0.002s | `yaml_io.py:32(_load_yaml_raw)` |
| 54,414 | 0.03s | 110.38s | 0.002s | `yaml/safe_load` |
| 53,790 | 0.03s | 109.78s | 0.002s | `yaml_io.py:65(load_yaml_meta_subtree)` |
| 50 | 0.00s | 102.30s | 2.046s | `calculation.py:168(from_yaml)` |
| 85 | 0.00s | 102.13s | 1.202s | `calculation.py:504(_build_step_inspection)` |
| 170 | 0.00s | 100.80s | 0.593s | `resolution.py:1739(require_step)` |
| 220 | 0.00s | 50.16s | 0.228s | `resolution.py:1098(resolve_calculation)` |
| 50 | 0.00s | 14.37s | 0.287s | `models.py:393(load_calculation)` |

**Note**: cProfile's cumulative time for `build_resource_index` (114.73s) exceeds the wall-clock 42.2s because it includes nested/recursive cumtime from the 606M function calls within YAML parsing. The wall-clock instrumented time is 40.6s.

### Sub-Operation Timing (sampled, first 5 calcs)

| Operation | Per-Calc | Projected 50 | Notes |
|-----------|--------:|------------:|-------|
| `list_calculations()` (resolution) | 13.5ms | 675ms | One-time; O(n) scan per entry |
| `Project.open()` | — | 213ms | One-time |
| `load_calculation()` | 107.5ms | 5.4s | Per-calc; includes `resolve_structure` → `build_resource_index` |
| `Calculation.from_yaml()` | 423.1ms | 21.2s | Per-calc; `_build_step_inspection` dominates |
| `build_resource_index()` standalone | — | 103ms | Single call baseline |
| `_load_config()` | — | 3.6ms | One-time |
| `calculation_to_dto()` | 0.011ms | 0.6ms | Negligible |
| `ensure_calculation_identity()` | 0.445ms | 22ms | Negligible |

### I/O Operations During Full list(detail=False)

| Metric | Count | Time |
|--------|------:|-----:|
| File reads (Path.read_text) | 72,697 | 1.61s |
| Total bytes read | 70.7 MB | — |
| Directory scans (iterdir) | 439 | 0.03s |
| Glob calls | 19,839 | 0.55s |
| YAML safe_load calls | 54,414 | ~110s |

### build_resource_index Call Sites

| Call Site | Count | Time (est.) |
|-----------|------:|----------:|
| `resolution.py:1126 resolve_calculation()` | 170 | ~17.7s |
| `resolution.py:1344 resolve_step()` | 170 | ~17.7s |
| `resolution.py:932 resolve_structure()` | 47 | ~4.9s |
| `model.py:166 _load_structures()` | 1 | ~0.1s |
| `model.py:270 _load_calculations()` | 1 | ~0.1s |
| **Total** | **389** | **~40.6s** |

### Scaling Test

**`_calculation_to_resolved` scaling** (O(n) — linear):

| n | Time | Per-calc |
|--:|-----:|--------:|
| 1 | 0.022s | 22.4ms |
| 5 | 0.073s | 14.6ms |
| 10 | 0.126s | 12.6ms |
| 25 | 0.349s | 14.0ms |
| 50 | 0.680s | 13.6ms |

**`load_calculation + from_yaml` scaling** (O(n) per-calc but with hidden per-step cost):

| n | Time | Per-calc |
|--:|-----:|--------:|
| 1 | 0.540s | 540ms |
| 5 | 2.666s | 533ms |
| 10 | 5.379s | 538ms |
| 25 | 14.283s | 571ms |
| 50 | 41.404s | 828ms |

The per-calc cost increases from ~540ms to ~828ms at n=50. This is because `build_resource_index()` gets progressively slower as more files are on disk (more steps to scan), and the high n means the profiling counter's monkey-patching adds cumulative overhead.

## Time Breakdown

```
Total: 42.2s for 50 calculations

build_resource_index()                   40.6s  (96.2%)
  ├── From resolve_calculation (170x)    17.7s  (42.0%)
  ├── From resolve_step (170x)           17.7s  (42.0%)
  ├── From resolve_structure (47x)        4.9s  (11.6%)
  └── From Project.open (2x)             0.2s   (0.5%)

Other YAML parsing                        0.8s   (1.9%)
  ├── CalcDoc.load in from_yaml (50x)
  ├── CalcDoc.load in load_calculation (50x)
  ├── CalcDoc.load in ensure_identity (50x)
  └── StepDoc.load in _build_step_inspection (85x)

list_calculations resolution              0.7s   (1.7%)
  └── _calculation_to_resolved (50x)
      └── iterdir + load_yaml_meta (O(n) scan per entry)

File I/O (reads + globs)                  0.1s   (0.2%)

Unaccounted (dict ops, DTO building)     <0.1s  (<0.1%)
```

**96.2% accounted for by build_resource_index alone.**

## Root Causes

### Root Cause 1: `_build_step_inspection` rebuilds index for every step (340 calls)

**`calculation.py:504 _build_step_inspection()`** calls `require_step()` for each step, which calls `resolve_step()`, which calls both:
- `resolve_calculation()` — calls `build_resource_index()` because no `index=` passed
- `resolve_step()` itself — calls `build_resource_index()` because no `index=` passed

For 85 steps across 50 calculations, this produces **340 calls to `build_resource_index()`**, consuming **~35.4 seconds** (84% of total).

**Why it's slow**: Each `build_resource_index()` scans `calculations/*/calculation.yaml` (50 files) + `calculations/*/steps/*.step.yaml` (85 files) = **135 YAML files parsed via `yaml.safe_load()`**. At ~2ms per parse, that's ~270ms per call. But the monkey-patching overhead and PyYAML's inherent cost make it ~104ms per measured call.

**Is it necessary?** No. `_build_step_inspection` is just trying to load a step file by ULID. It doesn't need a fresh index — it could accept a pre-built one or use the already-loaded `project.calculations` dict to find the step file directly via path.

### Root Cause 2: `load_calculation` rebuilds index for structure lookup (47 calls)

**`models.py:461-466`**: If `structure_ulid` exists but `structure_name` is missing, `load_calculation()` calls `resolve_structure()` which calls `build_resource_index()`. This happens for 47 of 50 calculations (3 have `structure_name` already set).

**Is it necessary?** No. Structure name is a cosmetic field for display. It could be deferred, or the lookup could accept a pre-built index.

### Root Cause 3: `Project.open` builds index twice (2 calls)

`_load_structures()` and `_load_calculations()` each call `build_resource_index()` independently. They could share a single index.

### Root Cause 4: `_calculation_to_resolved` does O(n) directory scan

**`resolution.py:1247`**: For each calculation entry, iterates ALL calculation directories and parses YAML until it finds a matching ULID. For 50 entries, this is O(n²) in YAML reads. Currently fast (~0.68s total) but would become significant at 200+ calcs.

### Root Cause 5: Same YAML files parsed repeatedly

`calculation.yaml` for each calculation is parsed at least 3 times:
1. In `load_calculation()` via `load_yaml_doc()`
2. In `Calculation.from_yaml()` via `CalcDoc.load()`
3. In `ensure_calculation_identity()` via `CalcDoc.load()`

Plus it's parsed once per entry in `_calculation_to_resolved()` via `load_yaml_meta_subtree()`, and again inside every `build_resource_index()` call.

### Root Cause 6: YAML parsing is inherently slow (PyYAML)

PyYAML's pure-Python `safe_load` is slow. The profiling shows 54,414 `yaml.safe_load` calls consuming the vast majority of CPU time. The YAML scanner alone (`check_token`, `fetch_more_tokens`) accounts for ~60 seconds of cumulative CPU time across 26M+ function calls.

## Theoretical Minimum

To list 50 calculations with basic metadata, we need:
- 1 read of `project.qms.yml` (~4ms)
- 50 reads of `calculation.yaml` meta blocks (~50 × 2ms = 100ms)
- Maybe 85 reads of step YAML meta blocks (~85 × 2ms = 170ms)

**Theoretical minimum: ~275ms** (or ~5.5ms per calculation)

**Current: 42,200ms** — **153x slower than theoretical minimum**.

## Proposed Solutions

### S1: Thread index through `_build_step_inspection` [P0, Effort: S]

**Impact: -35.4s (84% of current time)**

Pass a pre-built `ResourceIndex` into `Calculation.from_yaml()` and through to `_build_step_inspection()`.

```python
# Calculation.from_yaml signature change:
def from_yaml(cls, calculation_dir, project, materialize_steps=True, index=None):
    ...
    # In _build_step_inspection, pass index to require_step:
    step_resolved = require_step(project.root, calc_selector, step_ulid, index=index)
```

The `require_step` → `resolve_step` → `resolve_calculation` chain already accepts `index=` — it's just never passed by the caller.

**Risk**: Low. The index is read-only and the function already supports the parameter. Request-scoped (no staleness risk).

### S2: Thread index through `load_calculation` [P0, Effort: XS]

**Impact: -4.9s (12% of current time)**

Pass `index=` to `resolve_structure()` call in `load_calculation()`.

```python
def load_calculation(path, project_root=None, index=None):
    ...
    if model.structure_ulid and not model.structure_name and project_root:
        resolved = resolve_structure(project_root, model.structure_ulid, index=index)
```

**Risk**: Low. Same reasoning as S1.

### S3: Share index in `Project.open` [P1, Effort: XS]

**Impact: -0.1s (minor)**

Build index once and share between `_load_structures()` and `_load_calculations()`.

**Risk**: None.

### S4: Build index once in `service.list()` and pass everywhere [P0, Effort: M]

**Impact: Combines S1+S2+S3 = -40.5s (96%)**

Build `ResourceIndex` once at the top of `service.list()` and pass it to:
- `list_calculations()` (already accepts `config=`)
- `Project.open()` (needs new `index=` parameter)
- `load_calculation()` (needs new `index=` parameter)
- `Calculation.from_yaml()` (needs new `index=` parameter)

The total `build_resource_index` calls would drop from 389 to 1.

Expected time: **~1.5-2.0 seconds** (Project.open + 50 × load_calculation + 50 × from_yaml, minus index overhead).

**Risk**: Low. All changes are request-scoped. The index is built fresh for each RPC call, so no staleness risk. The call chain already supports `index=` parameters in most places.

### S5: Eliminate `_calculation_to_resolved` O(n) scan [P1, Effort: S]

**Impact: -0.5s now, prevents O(n²) scaling**

Use the pre-built `ResourceIndex` to resolve calculation IDs in O(1) instead of scanning directories.

```python
def _calculation_to_resolved(project_root, entry, index=None):
    if index is None:
        index = build_resource_index(project_root)
    calculation_id = entry.get("calculation_id") or entry.get("ulid")
    if calculation_id in index.by_id:
        meta = index.by_id[calculation_id]
        # O(1) lookup instead of O(n) directory scan
```

**Risk**: Low.

### S6: Deduplicate YAML parsing [P2, Effort: M]

**Impact: ~0.3s improvement**

Each `calculation.yaml` is parsed 3+ times. Cache the parsed result within the request scope:

```python
# Simple request-scoped cache
_yaml_cache = {}
def load_yaml_cached(path):
    if path not in _yaml_cache:
        _yaml_cache[path] = load_yaml_doc(path)
    return _yaml_cache[path]
```

**Risk**: Low if cache is request-scoped and cleared after each RPC call.

### S7: Switch to C-based YAML parser [P3, Effort: S]

**Impact**: Reduces per-parse time from ~2ms to ~0.2ms.

Use `yaml.CSafeLoader` (requires `libyaml` C extension) instead of pure-Python `SafeLoader`. Check `yaml.__with_libyaml__` at startup.

```python
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader
```

**Risk**: Low. CSafeLoader is API-compatible. Most systems have libyaml installed.

### S8: Bypass `_build_step_inspection` entirely [P1, Effort: S]

**Impact: Eliminates the biggest cost center entirely**

For `detail=False`, the DTO only needs step ULIDs and step count. These are already available from `calculation.yaml`'s `steps` list — no need to resolve/load individual step files.

```python
# Instead of calling _build_step_inspection for each step:
step_ulids = [s.get("step_ulid") for s in data.get("steps", [])]
step_count = len(step_ulids)
# Skip _build_step_inspection entirely
```

This would require changing `Calculation.from_yaml` to support a "metadata-only" mode even lighter than `materialize_steps=False`.

**Risk**: Medium. Need to verify the DTO doesn't need any information from the step YAML files that can't be obtained from calculation.yaml. The `calculation_to_dto` function accesses `step.meta.ulid`, `step.status`, and step type for engine inference — some of these may require step file data.

## Priority Ranking

| # | Solution | Impact | Effort | Risk | Priority |
|---|----------|--------|--------|------|----------|
| S4 | Build index once, pass everywhere | **-40.5s (96%)** | M | Low | **P0 — DO THIS** |
| S8 | Skip step file loading for shallow list | **-20s (additional)** | S | Medium | P1 |
| S5 | O(1) calc resolution | -0.5s + scaling | S | Low | P1 |
| S6 | Deduplicate YAML parsing | -0.3s | M | Low | P2 |
| S7 | C-based YAML parser | -50% parse time | S | Low | P3 |

**S4 alone would bring `list(detail=False)` from 42s to ~1.5s.**

## Appendix: Diagnostic Scripts

| Script | Purpose | Command |
|--------|---------|---------|
| `tests/benchmarks/profile_list_calcs.py` | Full profiling suite (cProfile, timing, I/O counting, scaling) | `python tests/benchmarks/profile_list_calcs.py --project-root /path/to/bench` |
| `tests/benchmarks/create_bench_project.py` | Create 50-calc benchmark project | `python tests/benchmarks/create_bench_project.py --output-dir /path` |
| `tests/benchmarks/results/profile_list_calcs.json` | Raw profiling data | — |

All scripts are excluded from pytest collection via `tests/benchmarks/conftest.py`.

## Appendix: Data Flow Diagram

```
                      service.list(detail=False)
                              │
                    ┌─────────┼─────────────┐
                    │         │             │
           list_calculations  │    FOR EACH (×50)
           (resolution.py)    │         │
                    │    Project.open    ├── load_calculation
                    │    (model.py)      │   └── resolve_structure ──┐
                    │         │         │                            │
                    │    ┌────┴────┐    └── Calculation.from_yaml   │
                    │    │         │        └── _build_step_insp.   │
                    │    │         │            └── require_step    │
                    │    │         │                ├── resolve_calc─┤
                    │    │         │                └── resolve_step─┤
                    │    │         │                                 │
                    │    bri()    bri()                              │
                    │    ×1       ×1                                 ▼
                    │                                         build_resource_index()
                    │                                           ×47 + ×170 + ×170
                    │                                           = 387 calls
                    │                                           = 40.4s
                    ▼
          _calculation_to_resolved (×50)
             O(n) scan per entry
             ~0.7s total
```
