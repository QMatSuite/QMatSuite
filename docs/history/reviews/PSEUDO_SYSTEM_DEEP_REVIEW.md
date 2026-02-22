# Pseudo System Deep Review — All Bugs, All Cases

**Date**: 2026-02-20
**Branch**: v2-python
**Trigger**: MCP agent trace showing `auto_resolve_species_map` failing for GaAs despite SSSP being installed with 103 UPFs

## Executive Summary

The pseudo system has **three independent, incompatible subsystems** that were built at different times and never unified. The MCP download pipeline (NEW) installs to one layout, while the resolution chain, library manager, and pseudo options system all look in a different layout. The result: downloads succeed but resolution fails.

This review identifies **16 bugs** and **4 design problems** across 10 source files, then proposes a single unified fix.

---

## The Three Incompatible Subsystems

| # | System | Install Layout | Used By |
|---|--------|---------------|---------|
| 1 | **OLD** (pseudo_config.py) | `sssp/1.3.0/precision/library/` | `library_manager.py`, `list_installed_sssp()`, seed install |
| 2 | **NEW** (pseudo/pipeline.py) | `SSSP/precision/1.3.0/` | MCP `download_pseudo_library`, `auto_resolve_species_map` |
| 3 | **ARCHIVE** (pseudo_installs.py) | `archives/<filename>` | `pseudo_options.py`, UI availability chips |

These three systems do not interoperate. A library installed by System 2 is invisible to Systems 1 and 3. A library installed by System 1 is invisible to System 2.

### Current state on disk (actual)

```
.qmatsuite/libraries/pseudo/
└── SSSP/                          ← NEW layout (dir_name=SSSP, uppercase)
    ├── head.json                  ← ROOT head.json: {"variant":"efficiency","version":"1.3.0"}
    │                                 ⚠ MISSING library_key!
    └── efficiency/
        └── 1.3.0/
            ├── head.json          ← INSTALL head.json: has library_key, 7 fields
            └── 103 UPF files

# OLD layout (sssp/1.3.0/precision/library/) — DOES NOT EXIST
# ARCHIVE layout (archives/<filename>) — DOES NOT EXIST
```

---

## Bug Inventory

### BUG 1: `auto_resolve_species_map_internal` missing `version` parameter

**File**: `src/qmatsuite/mcp/tools/_resource_utils.py:52-57`
**Severity**: CRITICAL (root cause of MCP failure)

```python
request = PseudoResolutionRequest(
    project_root=svc.project_root,
    elements=list(elements),
    library=library,
    flavor=flavor,
    # version NOT PASSED — always defaults to "1.3.0"
)
```

`PseudoResolutionRequest.version` defaults to `"1.3.0"` so this *happens* to work for SSSP 1.3.0. But the function signature has no `version` param at all — callers cannot pass it. More importantly, the `flavor` param from the caller maps to the `flavor` field on the request, but the resolution code at `pseudo_config.py:1419` uses `request.flavor` as `req_variant` for index lookup. This means `flavor="precision"` is passed to `resolve_element_from_index(library_key, variant="precision", ...)` which is correct. **So this is not the primary root cause — see BUG 2 and BUG 4.**

**Fix**: Add `version` parameter, pass it through. Low risk.

---

### BUG 2: Root `head.json` missing `library_key`

**File**: `src/qmatsuite/pseudo/pipeline.py:248-253`
**Severity**: CRITICAL (root cause of resolution failure)

```python
lib_root_head = libraries_root / info.dir_name / "head.json"
lib_root_head.write_text(
    json.dumps(
        {"variant": info.variant, "version": info.version}, indent=2
    )
)
```

The root `head.json` (at `SSSP/head.json`) has only `{variant, version}` — it's missing `library_key`, `dir_name`, and all other fields.

The resolution code at `pseudo_config.py:1469` reads:
```python
lib_key_from_head = head.get("library_key", "")
if lib_key_from_head:
    lib_filename = resolve_element_from_index(...)
else:
    # Fallback: try the requested library's exact filename
    lib_filename = exact_filename
```

When `library_key` is missing, it falls back to `exact_filename` — which IS the correct filename from the requested library. So this fallback should work... **IF the head.json scan finds the right directory**. See BUG 3.

**Fix**: Write `library_key` to root head.json. One line change.

---

### BUG 3: Resolution scans root `head.json`, not install-level `head.json`

**File**: `src/qmatsuite/core/pseudo_config.py:1452-1503`
**Severity**: CRITICAL (root cause)

The resolution loop at step 3:
```python
for lib_dir in sorted(libraries_root.iterdir()):
    head_path = lib_dir / "head.json"          # Reads SSSP/head.json (ROOT)
    head = json.loads(head_path.read_text())
    head_variant = head.get("variant", "")     # "efficiency"
    head_version = head.get("version", "")     # "1.3.0"
    upf_dir = lib_dir / head_variant / head_version  # SSSP/efficiency/1.3.0/
```

This ONLY reads the root head.json, which stores the LAST installed variant. If efficiency was installed after precision, the root head.json says `variant=efficiency` and the code constructs `SSSP/efficiency/1.3.0/` — it will NEVER look in `SSSP/precision/1.3.0/` even if it exists.

Even worse: if the user requests `flavor="precision"` but only `SSSP/efficiency/1.3.0/` exists (because precision was never installed), the scan finds the efficiency UPFs and the index lookup for precision returns a different filename than what's on disk → resolution fails silently.

**The actual failure path for GaAs**: The root head.json says `variant=efficiency`. The resolution code constructs `SSSP/efficiency/1.3.0/`. It looks for `Ga` and `As` UPFs there. The index says the efficiency filenames for Ga/As are (e.g.) `Ga.pbe-dn-kjpaw_psl.1.0.0.UPF` and `As.pbe-n-rrkjus_psl.1.0.0.UPF`. These files DO exist in the efficiency dir... but wait — the agent was requesting `precision` (which is the default). The precision dir doesn't exist at all on this machine. So the scan finds only `SSSP/` dir, reads root head.json (efficiency), constructs `SSSP/efficiency/1.3.0/`, and the index lookup for precision Ga/As returns filenames that may differ from efficiency filenames. If they differ → not found on disk → resolution fails.

**Fix**: Don't rely on root head.json. Instead, walk the full directory tree: for each `lib_dir/variant_dir/version_dir/`, check for install-level head.json and use that.

---

### BUG 4: Root `head.json` overwritten on second variant install

**File**: `src/qmatsuite/pseudo/pipeline.py:248-253`
**Severity**: HIGH

Installing efficiency after precision overwrites `SSSP/head.json` with `{"variant":"efficiency","version":"1.3.0"}`. Now the code can never discover the precision install. This is exactly what happened in testing — precision was installed first, then efficiency, and the root head.json lost the precision reference.

**Fix**: Either (a) remove root head.json entirely and scan subdirs, or (b) make root head.json a list of installed variants.

---

### BUG 5: `list_available_resources` reports `n_installed=0`

**File**: `src/qmatsuite/mcp/tools/list_resources.py:115-157`
**Severity**: HIGH (user-visible, misleading)

The code reads root `head.json` to get `lib_key`, which is empty (BUG 2). Then:
```python
lib_key = head.get("library_key", "")  # ""
if lib_key and elements:
    for elem in elements:
        fname = resolve_element_from_index(lib_key, variant, version, elem)
        # lib_key="" → always returns None
```

Result: `available_elements` is always empty → user sees "0 installed" even when 103 UPFs are on disk.

Meanwhile, `svc.project.get_pseudo_options(elements)` goes through `pseudo_options.py` which checks `archives/` dir (System 3) — also empty. So `n_installed=0` everywhere.

**Fix**: Follows from fixing BUG 2 (add library_key to root head.json) or BUG 3 (scan install-level head.json).

---

### BUG 6: `library_manager.py` uses OLD layout exclusively

**File**: `src/qmatsuite/core/library_manager.py:148-151`
**Severity**: HIGH

```python
lib_path = get_sssp_library_path(store_dir, version, variant)
library_path = lib_path / "library"
# Constructs: store_dir/sssp/1.3.0/precision/library/
```

`get_sssp_library_path()` returns `store_dir/sssp/version/flavor` — the OLD layout. Libraries installed by the NEW pipeline at `SSSP/precision/1.3.0/` are invisible to `_get_sssp_status()`, `install_library()`, and `remove_library()`.

**Fix**: Update `library_manager.py` to check both OLD and NEW layouts, or drop the OLD layout entirely.

---

### BUG 7: `pseudo_options.py` checks `archives/` directory (System 3)

**File**: `src/qmatsuite/core/pseudo_options.py:380-385`
**Severity**: MEDIUM

The `get_pseudo_options_for_elements()` function checks archive installation status via `check_archive_status()`, which looks for archives in `store_dir/archives/<filename>`. The NEW pipeline doesn't put archives there — it extracts UPFs directly to `SSSP/variant/version/`. So `any_installed` is always `False` for libraries installed by the pipeline.

**Fix**: Teach pseudo_options to also check the NEW pipeline layout, or unify the install systems.

---

### BUG 8: `download_pseudo_library` docstring says `flavor` but param is `variant`

**File**: `src/qmatsuite/mcp/tools/download_pseudo_library.py:24-26`
**Severity**: LOW (cosmetic but confusing for LLM agents)

```python
def download_pseudo_library(
    library: str = "sssp",
    variant: str = "",   # ← param is "variant"
    ...
) -> dict:
    """...
    Args:
        flavor: Library flavor — ...   # ← docstring says "flavor"
    """
```

The LLM agent sees the docstring and tries `flavor=` which fails. The actual param is `variant`.

**Fix**: Align docstring with parameter name.

---

### BUG 9: `_find_qmatsuite_root()` fails in wheel installs

**File**: `src/qmatsuite/core/pseudo_config.py:56-67`
**Severity**: MEDIUM (blocks production deployment)

```python
def _find_qmatsuite_root() -> Optional[Path]:
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "src" / "qmatsuite").exists():
            return current
        current = current.parent
    return None
```

When installed as a wheel, `__file__` is inside `site-packages/qmatsuite/core/pseudo_config.py` — there is no `src/qmatsuite` directory above it. Returns `None`, which means:
- `repo_pseudo_dir = None` → bundled resources not found
- `store_dir` may be empty if `PseudoConfig.get_default_store_dir()` also fails

Similarly `paths.py:get_repo_root()` (line 42-52) fails with `RuntimeError` in wheel installs.

**Fix**: Use `importlib.resources` or `pkg_resources` for finding bundled files. For `store_dir`, use `~/.qmatsuite/` unconditionally.

---

### BUG 10: `PseudoConfig.store_dir` silently empty when repo root not found

**File**: `src/qmatsuite/core/pseudo_config.py:92-97`
**Severity**: MEDIUM

```python
@classmethod
def get_default_store_dir(cls) -> str:
    try:
        return str(home_pseudo_libraries_dir())
    except Exception:
        return ""
```

If `home_pseudo_libraries_dir()` raises (because `get_repo_root()` fails), `store_dir=""`. Then resolution step 3 (`if store_dir and ...`) is skipped entirely. No error is raised — resolution just silently returns "not found" for all elements.

**Fix**: Fall back to `~/.qmatsuite/libraries/pseudo/` if repo root lookup fails.

---

### BUG 11: Resolution seed path uses OLD layout

**File**: `src/qmatsuite/core/pseudo_config.py:1507`
**Severity**: MEDIUM

```python
seed_path = get_sssp_seed_path(seed_dir, request.version, request.flavor)
# Returns: seed_dir/sssp/version/flavor/
```

But the NEW pipeline stores seeds at `seeds_root / info.filename` (flat, not in subdirs). So the seed-retry path in resolution will never find seeds cached by the new pipeline.

**Fix**: Check both layouts, or use the pipeline's seed location.

---

### BUG 12: `install_sssp_from_seed` installs to OLD layout

**File**: `src/qmatsuite/core/pseudo_config.py:621-623`
**Severity**: MEDIUM

```python
store_path = get_sssp_library_path(store_dir, version, flavor)
library_path = store_path / "library"
# Installs to: store_dir/sssp/1.3.0/precision/library/
```

If resolution step 4 (seed install) succeeds, it creates the OLD layout. Then the retry in step 4 scans root head.json files (NEW layout) and won't find the OLD layout install. Seed install succeeds but resolution still fails.

**Fix**: Use NEW layout for seed install, or scan both layouts during resolution.

---

### BUG 13: Cutoffs loaded from OLD layout only

**File**: `src/qmatsuite/core/pseudo_config.py:1387-1401`
**Severity**: LOW (cutoffs not critical for resolution, just for optimal parameters)

```python
lib_base = get_sssp_library_path(store_dir, request.version, request.flavor)
cutoffs_path = lib_base / "cutoffs.json"
# Looks at: store_dir/sssp/1.3.0/precision/cutoffs.json (OLD layout)
```

The NEW pipeline stores cutoffs at `SSSP/precision/1.3.0/SSSP_1.3.0_PBE_precision.json` (companion file). Not found by this code.

**Fix**: Check both locations, or rename the companion file to `cutoffs.json` during install.

---

### BUG 14: `resolve_project_pseudos` step 3 skips when `exact_filename` is None

**File**: `src/qmatsuite/core/pseudo_config.py:1448`
**Severity**: MEDIUM

```python
if not found and store_dir and exact_filename:
    # ^^^ If exact_filename is None (index lookup failed), entire step 3 is SKIPPED
```

If the element is not in the index (e.g., rare element, or version mismatch), the entire installed-library scan is skipped. There's no fallback to a tight glob scan of installed library dirs.

**Fix**: Enter the scan even when `exact_filename is None`, use tight glob as fallback.

---

### BUG 15: `list_resources` double-counts library sources

**File**: `src/qmatsuite/mcp/tools/list_resources.py:161-177`
**Severity**: LOW

`svc.project.get_pseudo_options(elements)` goes through `pseudo_options.py` which does SHA256-based scanning across project, internal, and library sources. This is completely independent of the head.json-based installed library scan above it. They can report conflicting information.

**Fix**: Use one system, not both.

---

### BUG 16: `download_pseudo_library` default variant resolves to first archive

**File**: `src/qmatsuite/pseudo/pipeline.py:87` + `registry.py`
**Severity**: LOW

When `variant=""` (default), the registry resolves to the first archive for the library. For SSSP this is `efficiency`. But `auto_resolve_species_map_internal` defaults to `flavor="precision"`. So: download defaults to efficiency, but resolution requests precision → resolution fails because precision was never installed.

**Fix**: Align defaults. Either both default to `precision` or both default to `efficiency`.

---

## Design Problems

### DESIGN 1: Three independent install systems

The fundamental problem. Three systems were built at different times:
1. **OLD** (`pseudo_config.py`): Manual SSSP download with manifest fetch + extract to `sssp/version/flavor/library/`
2. **NEW** (`pseudo/pipeline.py`): Generic pipeline using PseudoRegistry, installs to `DIR_NAME/variant/version/`
3. **ARCHIVE** (`pseudo_installs.py`): Archive-centric, stores raw archives in `archives/`, extracts on demand

None of these three systems is aware of the others.

**Proposed fix**: Deprecate Systems 1 and 3. Make System 2 (pipeline.py) the sole install system. Update all consumers to use the pipeline's layout.

---

### DESIGN 2: `flavor` vs `variant` terminology inconsistency

| Module | Term Used | Meaning |
|--------|-----------|---------|
| `_resource_utils.py` | `flavor` | "precision" or "efficiency" |
| `PseudoResolutionRequest` | `flavor` | same |
| `download_pseudo_library` MCP tool | `variant` (param), `flavor` (docstring) | same |
| `pipeline.py` | `variant` | same |
| `ArchiveInfo` | `variant` | same |
| `library_manager.py` | `variant` | same |
| `pseudo_config.py` | `flavor` (function args) | same |
| `head.json` | `variant` | same |

The same concept has two names. MCP tools use `variant`, resolution uses `flavor`, index uses `variant`.

**Proposed fix**: Standardize on `variant` everywhere (it's what the index and head.json use). Add a compatibility shim only in `PseudoResolutionRequest` during transition.

---

### DESIGN 3: Root head.json is an anti-pattern

A single `head.json` at the library root (`SSSP/head.json`) that stores only one variant's info is inherently broken for libraries with multiple variants (SSSP has both efficiency and precision).

**Proposed fix**: Remove root head.json entirely. During resolution, scan for `<lib_dir>/<variant_dir>/<version_dir>/head.json` patterns. The install-level head.json has all necessary fields.

---

### DESIGN 4: No unified "is library X installed?" function

Code that needs to know if SSSP precision is installed must independently:
- `library_manager.py`: Check `sssp/1.3.0/precision/library/` (OLD)
- `list_resources.py`: Scan root head.json + index lookup (NEW)
- `pseudo_options.py`: Check `archives/` + SHA256 (ARCHIVE)
- `pseudo_config.py`: Check both OLD and NEW during resolution

**Proposed fix**: One function: `is_library_installed(library_key, variant, version) -> InstalledLibInfo | None` that checks the canonical NEW layout and returns install-level head.json data.

---

## The Three Operational Cases

### Case 1: Library AND seed both empty → Download and install

**Current behavior**:
1. MCP agent calls `download_pseudo_library(library="sssp", variant="precision")`
2. `pipeline.py:download_and_install()` runs 5-step pipeline
3. Downloads from GitHub → caches seed → extracts → installs to `SSSP/precision/1.3.0/`
4. Writes install-level head.json (7 fields) + root head.json (2 fields, missing library_key)
5. Returns success

**Then resolution**:
6. Agent calls `auto_resolve_species_map(calc_ulid=...)`
7. → `_resource_utils.py:auto_resolve_species_map_internal(flavor="precision")`
8. → `resolve_project_pseudos(config, request)` with `request.flavor="precision"`
9. Resolution step 3 scans `store_dir/` for head.json files
10. Finds `SSSP/head.json` → reads `{variant: "precision", version: "1.3.0"}`
11. Constructs `SSSP/precision/1.3.0/` → finds UPFs → copies to project/pseudo/
12. **WORKS** (if only one variant installed and it matches the request)

**Failure scenario**: If efficiency was installed first, root head.json says efficiency. Request for precision fails.

**Bugs hit**: BUG 2 (missing library_key), BUG 3 (root head.json only), BUG 4 (overwrite on 2nd install)

**Required fix**: Scan install-level head.json files instead of root.

---

### Case 2: Library empty, seed cached → Decompress seed to lib (no download)

**Current behavior (NEW pipeline)**:
1. `pipeline.py:download_and_install()` checks `seeds_root / info.filename`
2. If seed exists and SHA256 matches → skip download
3. Extract + install as in Case 1

**Current behavior (OLD system, resolution step 4)**:
1. `pseudo_config.py:1507`: `seed_path = get_sssp_seed_path(seed_dir, request.version, request.flavor)`
2. Looks at `seed_dir/sssp/1.3.0/precision/` (OLD seed layout)
3. NEW pipeline stores seeds at `seeds_root/<filename>` (flat) → NOT FOUND
4. Even if found, `install_sssp_from_seed()` installs to OLD layout
5. Resolution retry still scans NEW layout head.json → doesn't find OLD install

**Bugs hit**: BUG 11 (seed path mismatch), BUG 12 (installs to OLD layout)

**Required fix**: Either (a) make resolution's seed-install use the NEW pipeline, or (b) have a single seed location that both systems use.

---

### Case 3: Library already installed → Use directly

**Current behavior**:
1. `pipeline.py` checks `install_dir.exists()` + has UPFs + has head.json → returns "already installed"
2. Resolution step 3 scans root head.json → constructs path → finds UPFs

**Failure scenarios**:
- Two variants installed: root head.json only points to the last one installed (BUG 4)
- `list_available_resources` reports 0 installed because library_key missing (BUG 5)
- `library_manager._get_sssp_status()` reports not_installed because it checks OLD layout (BUG 6)

**Bugs hit**: BUG 3, BUG 4, BUG 5, BUG 6, BUG 7

**Required fix**: Walk install-level head.json files; stop relying on root head.json.

---

## Proposed Unified Fix (Priority Order)

### Phase 1: Make resolution work (CRITICAL, 4 bugs)

1. **Fix root head.json** (BUG 2): Add `library_key` to the root head.json in `pipeline.py:248-253`.

2. **Fix resolution scan** (BUG 3): Replace root-head.json scan with a walk that finds all `<lib_dir>/<variant>/<version>/head.json` files. Each install-level head.json has `library_key`, `variant`, `version`.

3. **Fix step-3 skip** (BUG 14): Enter library scan even when `exact_filename is None`.

4. **Align defaults** (BUG 16): Make `auto_resolve_species_map_internal` default to `flavor="efficiency"` (matching pipeline default), OR make pipeline default to `variant="precision"` (matching resolution default).

### Phase 2: Eliminate layout confusion (HIGH, 5 bugs)

5. **Drop root head.json** (BUG 4, DESIGN 3): Stop writing root head.json. It's a single-variant store that breaks with multiple variants.

6. **Update library_manager** (BUG 6): Check NEW layout (`SSSP/variant/version/`) instead of OLD (`sssp/version/flavor/library/`).

7. **Fix list_resources** (BUG 5, BUG 15): Use install-level head.json scan. Remove pseudo_options dependency.

8. **Fix docstring** (BUG 8): Align `download_pseudo_library` docstring with actual param names.

9. **Standardize terminology** (DESIGN 2): Rename `flavor` to `variant` in `PseudoResolutionRequest` and `auto_resolve_species_map_internal`.

### Phase 3: Unify install systems (MEDIUM, 4 bugs)

10. **Deprecate OLD install** (BUG 12): Make seed-install use pipeline's `download_and_install()` instead of `install_sssp_from_seed()`.

11. **Fix seed path** (BUG 11): Use pipeline's flat seed location in resolution.

12. **Fix cutoffs** (BUG 13): Look for cutoffs in NEW layout.

13. **Fix pseudo_options** (BUG 7): Teach it to check NEW layout, or deprecate archive-based system.

### Phase 4: Production hardening (LOW, 2 bugs)

14. **Fix repo root detection** (BUG 9, BUG 10): Use `importlib.resources` for bundled files. Use `~/.qmatsuite/` as fallback for store_dir.

---

## Minimum Viable Fix (Fastest Path to Working MCP)

If time is limited, these **3 changes** fix the MCP end-to-end:

1. **`pipeline.py:248-253`**: Add `library_key` to root head.json:
   ```python
   lib_root_head.write_text(json.dumps({
       "library_key": info.library_key,
       "variant": info.variant,
       "version": info.version,
   }, indent=2))
   ```

2. **`pseudo_config.py:1452-1503`**: Replace root-head.json scan with install-level scan:
   ```python
   for lib_dir in sorted(libraries_root.iterdir()):
       if not lib_dir.is_dir():
           continue
       for variant_dir in sorted(lib_dir.iterdir()):
           if not variant_dir.is_dir() or variant_dir.name == "head.json":
               continue
           for version_dir in sorted(variant_dir.iterdir()):
               if not version_dir.is_dir():
                   continue
               head_path = version_dir / "head.json"
               if not head_path.exists():
                   continue
               # Now we have the install-level head.json with all fields
               head = json.loads(head_path.read_text())
               lib_key_from_head = head.get("library_key", "")
               # ... rest of resolution logic using version_dir as upf_dir
   ```

3. **`_resource_utils.py:52-57`**: Pass default variant matching pipeline:
   ```python
   request = PseudoResolutionRequest(
       project_root=svc.project_root,
       elements=list(elements),
       library=library,
       version="1.3.0",
       flavor=flavor,
   )
   ```

These 3 changes ensure: download → install → resolution → species_map works end-to-end.

---

## Files Affected

| File | Bugs | Priority |
|------|------|----------|
| `src/qmatsuite/pseudo/pipeline.py` | BUG 2, 4 | Phase 1 |
| `src/qmatsuite/core/pseudo_config.py` | BUG 3, 11, 12, 13, 14 | Phase 1-3 |
| `src/qmatsuite/mcp/tools/_resource_utils.py` | BUG 1 | Phase 1 |
| `src/qmatsuite/mcp/tools/list_resources.py` | BUG 5, 15 | Phase 2 |
| `src/qmatsuite/core/library_manager.py` | BUG 6 | Phase 2 |
| `src/qmatsuite/core/pseudo_options.py` | BUG 7 | Phase 3 |
| `src/qmatsuite/mcp/tools/download_pseudo_library.py` | BUG 8, 16 | Phase 2 |
| `src/qmatsuite/core/pseudo_installs.py` | BUG 7 (consumer) | Phase 3 |
| `src/qmatsuite/core/paths.py` | BUG 9, 10 | Phase 4 |
| `tests/integration/test_pseudo_resolution.py` | — | Update |

---

## Test Plan

### Existing tests to update
- `tests/integration/test_pseudo_resolution.py:TestResolutionChain` — verify all 3 cases work
- `tests/integration/test_pseudo_download_pipeline.py:test_head_json_exists` — verify library_key present

### New tests needed
- `test_resolution_with_two_variants_installed` — install both efficiency AND precision, verify both discoverable
- `test_resolution_without_root_head_json` — delete root head.json, verify resolution still works via install-level scan
- `test_list_resources_shows_installed_elements` — verify `available_elements` is non-empty after install
- `test_library_manager_finds_new_layout` — verify `_get_sssp_status()` finds NEW layout installs
