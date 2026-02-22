# Phase 2A Post-Demo Review: Si Bands Issues

**Date:** 2026-02-19
**Scope:** READ-ONLY investigation of all issues identified from Si band structure agent demos
**Deliverable:** This document (no source code modifications)

---

## Issue Index

| ID | Layer | Title | Severity | Fix Scope |
|----|-------|-------|----------|-----------|
| C1 | MCP | `set_parameters` cannot set QE cards | High | MCP tool only |
| C2 | Kernel | Runtime-managed keys (filband) not injected for bands.x | Medium | Kernel + driver |
| C3 | MCP | No MCP tool for k-path generation | Medium | New MCP tool |
| C4 | Preset | `nbnd` not set in any preset | Low | Preset/knowledge |
| M1 | Kernel | Cascade invalidation missing for Run Step mode | Medium | Runner (~5 lines) |
| M2 | MCP | Dry-run materializer diverges from runtime for cards | High | MCP tool |
| Q1 | MCP | ASCII renderer produces sparklines, not 2D charts | Low | Renderer |
| Q2 | MCP | PNG saves to `.scratch/` | Info | By design |
| Q3 | — | Bands evidence not found (symptom of C2) | N/A | Resolved by C2 |

---

## C1: `set_parameters` Cannot Set QE Cards

### Summary

The `set_parameters` MCP tool hardcodes all user input into the `parameters:` namespace in step.yaml. QE cards (K_POINTS, ATOMIC_SPECIES, ATOMIC_POSITIONS, CELL_PARAMETERS) live in the separate `cards:` namespace and cannot be set through this tool.

### Root Cause

**File:** `src/qmatsuite/mcp/tools/set_parameters.py`, line 53

```python
svc.calculation.update_step_params(
    calc_selector=calc_ulid,
    step_selector=step_ulid,
    params={"parameters": params},  # <-- HARDCODED to "parameters" namespace
)
```

The API layer (`update_step_params` in `api/service.py:3972-4071`) already supports a `"cards"` key and routes it to `step_doc.apply_patch({"cards": ...})`. The materializer (`calculation/input_runner.py:743-799`) properly handles both namespaces via `apply_card_overrides_to_qe_input()`. The bottleneck is solely in the MCP tool wrapper.

### Step YAML Schema (Reference)

```yaml
parameters:        # Namelists: CONTROL, SYSTEM, ELECTRONS, IONS, CELL
  SYSTEM:
    ecutwfc: 60
cards:             # QE cards: K_POINTS, ATOMIC_SPECIES, ATOMIC_POSITIONS, CELL_PARAMETERS
  K_POINTS:
    option: "automatic"
    data: [[4, 4, 4, 0, 0, 0]]
```

### Impact

An agent cannot set K_POINTS for a band structure calculation via MCP. If it passes `{"K_POINTS": {"option": "tpiba_b", "data": [...]}}` to `set_parameters`, the data goes into `step.yaml["parameters"]["K_POINTS"]` (namelists), not `step.yaml["cards"]["K_POINTS"]` (cards). The materializer ignores it.

### Fix Options

1. **Option A (Recommended):** Add `namespace` parameter (default `"parameters"`, can be `"cards"`). Backward-compatible, explicit.
2. **Option B:** Auto-detect namespace by checking if keys match known card types (`K_POINTS`, `ATOMIC_SPECIES`, etc.) vs namelist sections (`SYSTEM`, `ELECTRONS`).
3. **Option C:** Accept mixed top-level dict `{"parameters": {...}, "cards": {...}}` and forward directly to API.

### Deferred Item Entry

```
- C1: set_parameters cards support
  Layer: MCP tool
  Fix: Add namespace parameter or auto-detect card keys
  Files: src/qmatsuite/mcp/tools/set_parameters.py (line 53)
```

---

## C2: Runtime-Managed Keys — `filband` Not Injected for bands.x

### Summary

QMatSuite manages three runtime keys (`prefix`, `outdir`, `pseudo_dir`) that are automatically injected into QE input files. However, `filband` (the output filename for bands.x) is NOT managed. This means the agent must know to set it manually, and the default QE value (`"bands.out"`) may not match the evidence file glob pattern (`*.bands.dat.gnu`).

### Root Cause

**Runtime keys defined at:** `src/qmatsuite/calculation/structure_steps.py`, line 309

```python
RUNTIME_KEYS = {"prefix", "outdir", "pseudo_dir"}
```

`filband` is absent from this set. The injection function `_inject_calculation_prefix_outdir()` (lines 353-461) injects `prefix` and `outdir` into any step whose QE module schema defines those parameters, but does not touch `filband`.

### How Prefix Injection Works

1. Each step maps to a QE module via `STEP_TYPE_MODULE_MAP` (line 280-294): `"bands"` -> `QEModule.BANDS`
2. The BANDS module schema includes `prefix`, `outdir`, and `filband` parameters
3. Only `prefix` and `outdir` are injected; `filband` is left to user/default

### Prefix Convention

- Function: `stable_short_calc_prefix(ulid)` at line 327
- Formula: `"qms" + ulid[-6:].lower()` (e.g., ULID ending `...PTB4B2` -> prefix `"qmstb4b2"`)
- Stable across slug changes (ULID-derived, not name-derived)

### Evidence File Pattern

QE driver declares: `evidence_files=["*.bands.dat.gnu"]` (driver.py, line 20). This matches files like `qmstb4b2.bands.dat.gnu`, which are produced when prefix is injected. If filband were also managed (e.g., set to `"bands.dat"`), the output would be `<prefix>.bands.dat.gnu`, matching the evidence glob.

### Impact

If the user does not set `filband`, QE uses default `"bands.out"`. The output file would be `<prefix>.bands.out.gnu`, which does NOT match the evidence glob `*.bands.dat.gnu`. This causes `list_analyses` to report `evidence_available=false` for bands.

### Fix Options

1. **Add filband to runtime injection:** Set `filband = "bands.dat"` for BANDS module steps, ensuring output matches evidence glob.
2. **Widen the evidence glob:** Change to `*.bands.*.gnu` to match both `.dat.gnu` and `.out.gnu`.
3. **Knowledge base entry:** Document that users should set `filband = "bands.dat"`.

### Deferred Item Entry

```
- C2: filband runtime injection
  Layer: Kernel (structure_steps.py)
  Fix: Add filband injection for BANDS module, or widen evidence glob
  Files: src/qmatsuite/calculation/structure_steps.py (RUNTIME_KEYS + _inject_calculation_prefix_outdir)
         src/qmatsuite/drivers/qe/driver.py (evidence_files glob)
```

---

## C3: No MCP Tool for K-Path Generation

### Summary

QMatSuite has a complete k-path generation module (`analysis/kpath.py`, 296 lines) that uses pymatgen's `HighSymmKpath` to auto-generate high-symmetry k-point paths for any crystal system. It is used by the CLI (`--auto-kpath` flag) but not exposed as an MCP tool. An agent must manually construct K_POINTS card data.

### Existing Implementation

**File:** `src/qmatsuite/analysis/kpath.py`

- `generate_kpath(structure, points_per_segment=20, path_type="hinuma")` -> `KPathResult`
- `KPathResult.to_qe_kpoints_crystal_b()` -> QE K_POINTS card format
- Supports all crystal systems via pymatgen's `HighSymmKpath` + `SpacegroupAnalyzer`
- Three path algorithms: `"hinuma"`, `"seekpath"`, `"setyawan_curtarolo"` (with fallback cascade)
- API wrapper: `QMSService.generate_kpath()` at `api/service.py:8375-8398`

**CLI usage:**
```bash
qms init step bandspw --structure si --auto-kpath --kpath-points 20
```

### Why It's Not an MCP Tool

The CLI directly calls `QMSService.generate_kpath()` and stores the result in step.yaml (both the K_POINTS card data and `kpath_metadata`). No MCP tool wrapper was created during Phase 1 or Phase 2A because band structure was not in scope.

### k-path Metadata Storage

When `--auto-kpath` is used, the step YAML stores:
```yaml
cards:
  K_POINTS:
    option: "crystal_b"
    data: [[kx, ky, kz, npts], ...]
kpath_metadata:
  lattice_type: "cubic"
  spacegroup_symbol: "Fd-3m"
  labels: ["G", "X", "M", "G"]
  segments: [...]
```

### Impact

An agent cannot auto-generate k-paths via MCP. It must either:
1. Manually construct K_POINTS data (error-prone for non-cubic systems)
2. Use hardcoded high-symmetry points (which may be wrong for the crystal system)

### Proposed MCP Tool

```python
@mcp.tool
def generate_kpath(structure_selector: str, points_per_segment: int = 20) -> dict:
    """Generate high-symmetry k-point path for band structure calculations."""
```

Returns: path_string, labels, coords, K_POINTS card data ready for `set_parameters`.

### Deferred Item Entry

```
- C3: generate_kpath MCP tool
  Layer: MCP tool (new)
  Fix: Wrap existing QMSService.generate_kpath() as MCP tool
  Files: New: src/qmatsuite/mcp/tools/generate_kpath.py
         Existing: src/qmatsuite/analysis/kpath.py, src/qmatsuite/api/service.py:8375
```

---

## C4: `nbnd` Not Set in Any Preset

### Summary

The QE parameter `nbnd` (number of bands) is not set in any preset dimension. For band structure calculations, the QE default (`nbnd = n_electrons/2`) only includes occupied bands. To see conduction bands (essential for band gap visualization), `nbnd` must be explicitly increased.

### Investigation

Grep of `src/qmatsuite/presets/` for `nbnd`: **zero matches**. The preset system handles `ecutwfc`, `ecutrho`, `smearing`, `degauss`, `conv_thr`, etc., but not `nbnd`.

### QE Default Behavior

For Si (8 valence electrons, 2 atoms in cell): `nbnd_default = n_electrons/2 = 4`. This means only 4 bands are computed, all occupied. No conduction bands appear in the band structure.

A typical band structure calculation for Si would use `nbnd = 8` or higher to include conduction bands above the gap.

### Impact

An agent using presets to configure a band structure calculation will get a band structure with only occupied bands. The band gap is invisible because there are no conduction bands.

### Fix Options

1. **Knowledge base entry:** Add a high-confidence insight: "For band structure calculations, set nbnd >= 2 * n_electrons/2 to include conduction bands."
2. **Preset extension:** Add an `nbnd_policy` preset dimension (e.g., `"occupied_only"`, `"include_conduction"`, `"double"`) that sets nbnd relative to the default.
3. **Workflow template default:** The `bandspw` step default could include `nbnd` guidance.

### Deferred Item Entry

```
- C4: nbnd preset/knowledge
  Layer: Preset + Knowledge
  Fix: Add knowledge entry about nbnd for band structure, consider preset dimension
  Files: src/qmatsuite/presets/ (new dimension), src/qmatsuite/mcp/knowledge/ (new insight)
```

---

## M1: Cascade Invalidation Missing for Run Step Mode

### Summary

Constitution section 5.3 specifies: "Run Single Step: The target step must always execute (no skip). After success, conservatively marks downstream steps as `done=false`." The cascade invalidation is **not implemented** in the runner, despite the infrastructure (`clear_manifest_from_step()`) existing.

### Root Cause

**File:** `src/qmatsuite/calculation/runner.py`

The runner's `_execute_with_jobgraph()` method (lines 477-667) handles target step execution but does not call `clear_manifest_from_step()` after successful target step completion. The function exists at `calculation/manifest.py:227-256` and is tested in `tests/integration/test_incremental_run.py:745`, but it's never called from the runner.

### Skip Decision Logic (Working Correctly)

`should_skip_step()` at `manifest.py:277-320` uses three input-identity SHAs:
- `pseudo_set_sha` (pseudopotential set)
- `structure_sha` (structure data)
- `step_sha` (step parameters)
Plus a `done` flag. Output hashes are never used (Constitution section 5.2).

### Run Modes

| Mode | Status | Cascade |
|------|--------|---------|
| `incremental` (default) | Working | N/A (all steps evaluated) |
| `full` | Working | All steps reset to `done=false` |
| `target` (Run Step) | Partial | Missing cascade invalidation |

### Missing Code Location

After successful target step execution in `runner.py:_execute_with_jobgraph()` (~line 575), the following logic should be added:

```python
if target_step_ulid and result.success:
    target_step_idx = <find index of target step>
    clear_manifest_from_step(calculation.dir, target_step_idx + 1)
```

### MCP Exposure

The `run_calculation` MCP tool (`mcp/tools/run_calculation.py`) does NOT expose `run_mode` or `target_step_ulid` parameters. Only `calc_ulid` is accepted. The underlying runner supports both parameters.

### Impact

If an agent re-runs a single step (e.g., bandspw) after parameter changes, downstream steps remain marked `done=true` in the manifest. A subsequent incremental run would skip them even though their input (the re-run step's output) has changed.

### Deferred Item Entry

```
- M1: cascade invalidation for Run Step
  Layer: Kernel (runner.py)
  Fix: Call clear_manifest_from_step() after successful target step execution (~5 lines)
  Files: src/qmatsuite/calculation/runner.py (_execute_with_jobgraph, ~line 575)
         Infrastructure exists: src/qmatsuite/calculation/manifest.py:227-256
  Also: Consider exposing run_mode/target_step_ulid in MCP run_calculation tool
```

---

## M2: Dry-Run Materializer Diverges from Runtime for Cards

### Summary

The `inspect_calculation` dry-run (`dry_run=True`) uses a different materialization path than the runtime. The dry-run path converts QE cards into a flat `kpoints` dict, losing the card option field (e.g., `tpiba_b`). This means dry-run cannot preview band structure input files correctly.

### Root Cause

**Dry-run path:** `src/qmatsuite/mcp/tools/inspect_calculation.py`
- `_run_dry_run()` (lines 192-244) calls `_merge_cards_into_params()` (lines 303-327)
- `_merge_cards_into_params()` converts K_POINTS card into flat `params["kpoints"] = {mesh, shift}`
- Only extracts the first row of card data (line 323)
- **Loses** the K_POINTS `option` field (e.g., `"tpiba_b"`, `"crystal_b"`)
- The inputformat writer (`drivers/qe/inputspec.py:135-140`) then hardcodes `K_POINTS (automatic)`

**Runtime path:** `src/qmatsuite/calculation/structure_steps.py`
- Calls `apply_card_overrides_to_qe_input()` (in `input_runner.py:741-780`)
- Preserves the full QECard object with `card.option` field
- Uses `QEInputGenerator` which reads `card.option` to produce correct header (e.g., `K_POINTS {tpiba_b}`)

### Comparison Table

| Aspect | Dry-Run Path | Runtime Path |
|--------|--------------|--------------|
| Card representation | Flat dict (loses structure) | QECard objects (preserves) |
| K_POINTS option | NEVER preserved | ALWAYS preserved |
| Writer | inputformat/inputspec.py (generic) | QEInputGenerator (QE-specific) |
| K_POINTS formats | Only `automatic` | All formats (tpiba_b, crystal_b, etc.) |

### Impact

When an agent uses `inspect_calculation(dry_run=True)` to preview a band structure calculation, the generated input file shows `K_POINTS (automatic)` with a 3x2 grid instead of the correct `K_POINTS {tpiba_b}` with the k-path data. This makes dry-run unusable for band structure verification.

### Fix Options

1. **Reuse runtime materializer:** Make dry-run call `materialize_step_spec()` (the same function the runtime uses) instead of reimplementing via inputformat.
2. **Fix the card conversion:** Extend `_merge_cards_into_params()` to preserve option and full data, and extend the inputformat writer to handle all K_POINTS formats.
3. **Separate card rendering:** Pass cards separately to the writer (not merged into params).

### Deferred Item Entry

```
- M2: dry-run materializer card handling
  Layer: MCP tool (inspect_calculation.py)
  Fix: Reuse runtime materializer or fix card conversion to preserve option field
  Files: src/qmatsuite/mcp/tools/inspect_calculation.py (_run_dry_run, _merge_cards_into_params)
         src/qmatsuite/drivers/qe/inputspec.py (hardcoded K_POINTS automatic)
```

---

## Q1: ASCII Renderer Produces Sparklines, Not 2D Charts

### Summary

The ASCII renderer (`mcp/renderers/ascii_renderer.py`) produces text tables with Unicode sparklines, not proper 2D charts with axes, ticks, and coordinate systems. For convergence data, it shows a table of iteration/energy values followed by a 40-character sparkline. For DOS, it shows horizontal bars. For bands, it only shows metadata (no chart at all).

### Current Capabilities

| Object Type | Rendering | Quality |
|-------------|-----------|---------|
| convergence | Table + 40-char sparkline | Minimal |
| dos | Horizontal bars (30 chars) | Basic |
| bands | Metadata only (no chart) | None |
| scf_digest | Key-value table | OK |
| trajectory | Statistics + sparkline | Minimal |
| field3d | Grid dimensions only | N/A (volumetric) |

### Known Edge Case Issues

| Case | Behavior |
|------|----------|
| Negative values | `_sparkline()` normalization breaks; `_unicode_bar()` returns empty |
| NaN/Inf | No checks; crashes on `min()`/`max()` |
| All same value | Sparkline uses 0.5-height block (OK) |
| Empty series | Returns `"(no data)"` (OK) |
| Large datasets | Naive downsampling (every Nth point, loses peaks) |

### Plotext Comparison (Reference)

Plotext (v5.3.2, MIT license) is a stdlib-only terminal plotting library that demonstrates what's achievable:
- Full 2D chart with frame, ticks, axis labels
- Smart tick formatting (auto-precision)
- Bresenham line interpolation between data points
- NaN/Inf filtering before min/max
- Constant-value auto-range expansion
- Multiple overlaid series
- Terminal-size-aware dimensions

### Proposed Enhancement

A `TerminalChart` class (stdlib-only) providing:
- 2D canvas with axes and ticks
- Configurable width/height (default 80x20)
- Smart downsampling (LTTB or Chebyshev)
- Multiple series support
- Horizontal/vertical marker lines (Fermi level, convergence target)
- Robust edge case handling

### Impact

Current ASCII rendering is adequate for convergence verification but provides poor visualization for DOS and no visualization for bands. The agent gets minimal visual feedback about calculation results.

### Deferred Item Entry

```
- Q1: ASCII renderer upgrade to 2D charts
  Layer: MCP renderer
  Fix: Create TerminalChart class with axes, ticks, smart downsampling
  Files: New: src/qmatsuite/mcp/renderers/terminal_chart.py
         Modify: src/qmatsuite/mcp/renderers/ascii_renderer.py
```

---

## Q2: PNG Saves to `.scratch/`

### Summary

The `plot_analysis` tool saves PNG files to `<calc_dir>/.scratch/<object_type>_step<N>.png`. This was initially flagged as potentially incorrect, but investigation confirms it is **by design**.

### Finding

The `.scratch/` directory is used consistently across the project for transient rendering outputs:
- `api/service.py:1198-1199`: Field3D data materialized to `.scratch/field3d/`
- `daemon/server.py`: References `.scratch/` for frontend rendering
- `mcp/tools/plot_analysis.py:134`: PNG plots to `.scratch/`

There is no `results/` directory convention in the project. SSOT files (calculation.yaml, step.yaml) stay in the calculation directory; transient rendering outputs go to `.scratch/`.

### Conclusion

**NOT A BUG.** The `.scratch/` path is the correct location for transient plot outputs. No action needed.

---

## Q3: Bands Evidence Not Found — Symptom of C2

### Summary

`list_analyses(step=1)` reports `evidence_available=false` for bands after a successful run. This was initially investigated as an evidence directory resolution issue, but is actually a **filename mismatch caused by C2**.

### Root Cause

All QE artifacts are in `raw/` directly. `outdir/` only contains QE scratch files (`.save`, `.wfc`, `.xml`). The evidence directory resolution is correct.

The problem is:
- Evidence glob: `*.bands.dat.gnu` (from `AnalysisCapability.evidence_files`)
- Actual file: `bands.out.gnu` (QE default when `filband` is not set)

When `filband` is not runtime-managed (C2), QE uses its default (`"bands.out"`), producing `bands.out.gnu`. This doesn't match the glob.

### Resolution

This is fully resolved by C2 (filband runtime injection). When filband is set to `"bands.dat"`, the output becomes `{prefix}.bands.dat.gnu`, which matches `*.bands.dat.gnu`.

As defense-in-depth, C2 should also widen the parser glob to `["*.bands.dat.gnu", "*.bands.out.gnu"]` with a warning on the fallback match.

### Status: Not an independent issue — covered by C2.

---

## Summary: Priority Matrix

### Must Fix (blocks band structure workflow)

| ID | Issue | Fix Effort |
|----|-------|-----------|
| C1 | set_parameters can't set cards | Small (1 file, ~20 lines) |
| M2 | Dry-run breaks for non-automatic K_POINTS | Medium (1 file, needs design choice) |

### Should Fix (degraded experience)

| ID | Issue | Fix Effort |
|----|-------|-----------|
| C2 | filband not runtime-managed | Small (2 files, ~10 lines) |
| C3 | No k-path MCP tool | Medium (new tool, wraps existing API) |
| M1 | Cascade invalidation missing | Small (1 file, ~5 lines) |

Note: Q3 (bands `evidence_available=false`) is a direct symptom of C2 and requires no separate fix.

### Nice to Have (quality improvement)

| ID | Issue | Fix Effort |
|----|-------|-----------|
| C4 | nbnd not in presets | Small (knowledge entry + optional preset) |
| Q1 | ASCII renderer quality | Large (new TerminalChart class) |
| Q2 | PNG to .scratch/ | None (by design) |

---

## Appendix: Key File References

| File | Role |
|------|------|
| `src/qmatsuite/mcp/tools/set_parameters.py:53` | C1: hardcoded namespace |
| `src/qmatsuite/calculation/structure_steps.py:309` | C2: RUNTIME_KEYS definition |
| `src/qmatsuite/calculation/structure_steps.py:353-461` | C2: prefix/outdir injection |
| `src/qmatsuite/analysis/kpath.py` | C3: k-path generation (296 lines) |
| `src/qmatsuite/api/service.py:8375-8398` | C3: QMSService.generate_kpath() |
| `src/qmatsuite/presets/` | C4: preset dimensions (no nbnd) |
| `src/qmatsuite/calculation/runner.py:477-667` | M1: _execute_with_jobgraph() |
| `src/qmatsuite/calculation/manifest.py:227-256` | M1: clear_manifest_from_step() (exists, unused) |
| `src/qmatsuite/mcp/tools/inspect_calculation.py:192-327` | M2: dry-run materializer |
| `src/qmatsuite/calculation/input_runner.py:741-799` | M2: runtime card application |
| `src/qmatsuite/mcp/renderers/ascii_renderer.py` | Q1: current ASCII renderer |
| `src/qmatsuite/mcp/tools/plot_analysis.py:134` | Q2: .scratch/ path |
| `src/qmatsuite/drivers/qe/driver.py:17-37` | C2/Q3: ANALYSIS_CAPABILITIES (evidence_files glob) |
