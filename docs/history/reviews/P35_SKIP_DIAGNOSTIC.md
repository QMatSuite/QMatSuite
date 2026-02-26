# P35 Skip & Failure Diagnostic

## 1. Test Suite Summary

```
4 failed, 6548 passed, 31 skipped, 1014 warnings in 368.86s (0:06:08)
```

**Baseline (commit 3677349, v2-python):** 6535 passed, 5 skipped, 0 failed.

**Delta caused by P35 rework:**
- **26 new skips** (all ORCA) — regression introduced by P35
- **4 new failures** (PySCF relax) — regression introduced by P35
- **5 pre-existing skips** — not caused by P35

---

## 2. Skip Analysis

### 2.1 Complete Skip List

| # | Test | File:Line | Skip Condition | Cause | Pre-existing? |
|---|------|-----------|----------------|-------|---------------|
| 1 | `test_notebook_no_kernel_imports` | `tests/gates/test_import_rules.py:274` | `not notebook_dir.exists()` → `src/qmatsuite/frontends/notebook` | Dir doesn't exist (planned module) | YES |
| 2 | `test_tools_no_kernel_imports` | `tests/gates/test_import_rules.py:325` | `not tools_dir.exists()` → `src/qmatsuite/tools` | Dir doesn't exist (planned module) | YES |
| 3 | `test_gui_methods_covered` | `tests/contract_crawler/test_gui_methods_covered.py:25-28` | `os.environ.get("QMS_ENFORCE_GUI_RPC_COVERAGE") != "1"` | Soft gate, env var not set | YES |
| 4 | `test_gui_methods_covered_soft` | `tests/contract_crawler/test_gui_methods_covered.py:108` | Dynamic: missing GUI methods | Soft gate dynamic skip | YES |
| 5 | `test_cod_search` | `tests/integration/test_online_structure_import.py:99-100` | `result.timed_out or result.error` | COD endpoint timed out (verified: `HTTPSConnectionPool Read timed out`) | YES (transient) |
| 6-15 | 10x `test_orca_execution.py` | `tests/integration/orca/test_orca_execution.py:70-71` | `not ORCA_BIN` in `orca_engine` fixture | **P35 REGRESSION**: `resolve_engine_binary("orca","orca")` fails — `_scan_bundled()` can't find ORCA | **NO — NEW** |
| 16 | `test_bundled_path_found` | `tests/unit/orca/test_orca_engine.py:121-122` | `resolve_engine_binary("orca","orca")` raises | **P35 REGRESSION**: same root cause | **NO — NEW** |
| 17-24 | 8x `test_system_integration.py` | `tests/integration/orca/test_system_integration.py:74-75` | `not ORCA_BIN` in `orca_engine` fixture | **P35 REGRESSION**: same root cause | **NO — NEW** |
| 25-28 | 4x `test_orca_project_level.py` | `tests/integration/orca/test_orca_project_level.py:44-45` | `not ORCA_BIN` | **P35 REGRESSION**: same root cause | **NO — NEW** |
| 29-31 | 3x `test_orca_relax_real.py` | `tests/integration/test_orca_relax_real.py:36-39` | `resolve_engine_binary("orca","orca")` raises | **P35 REGRESSION**: same root cause | **NO — NEW** |

### 2.2 Category Summary

- **Pre-existing skips**: 5 (2 missing dirs, 2 soft gates, 1 network timeout)
- **P35 regressions (ORCA broken)**: 26 skips

### 2.3 Root Cause: ORCA Discovery Broken by `_scan_bundled()` Hardcoded `bin/` Requirement

**The Problem:**

ORCA is installed at:
```
.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca
```

The `orca` binary is directly in the version directory — there is **no `bin/` subdirectory**.

`_scan_bundled()` at `engine_registry.py:365-367`:
```python
bin_dir = install_dir / "bin"
if not bin_dir.is_dir():
    continue              # ← SKIPS ORCA because bin/ doesn't exist
```

**Before P35 (commit 3677349):**
All ORCA tests called `orca_resolver.resolve_orca_bin()` which had ORCA-specific knowledge:
```python
# orca_resolver.py lines 82-90 (DELETED by P35)
for subdir in sorted(bundled_base.iterdir(), reverse=True):
    if subdir.is_dir() and subdir.name.startswith("orca_"):
        orca_binary = subdir / "orca"           # ← No bin/ required!
        if orca_binary.exists() and orca_binary.is_file():
            return orca_binary
```

**After P35:**
All ORCA tests were migrated to call `resolve_engine_binary("orca", "orca")` which goes through the generic `_scan_bundled()` → requires `bin/` → doesn't find ORCA → all 26 tests skip.

**Gaussian has the same bug** but Gaussian tests work around it differently:
- `test_gaussian_execution.py:30-32` manually sets `os.environ["g09root"]` before any resolution
- The Gaussian test uses `discover_engine()` (from `discovery.py`) which has its own fallback logic
- So Gaussian tests PASS despite `engines.json` showing `gaussian: active=None, installations=0`

### 2.4 Evidence

Verified on disk:
```
$ ls .qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca
# EXISTS — the binary is right here

$ ls .qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/bin/
# ls: No such file or directory
```

`engines.json` confirms zero ORCA installations:
```json
"orca": {"active": null, "installations": []}
"gaussian": {"active": null, "installations": []}
```

---

## 3. Failure Analysis

### 3.1 The 4 Failures Are a P35 Regression

**Failed tests:**
```
tests/integration/test_relax_promote_e2e.py::test_promote_creates_new_structure_resource
tests/integration/test_relax_promote_e2e.py::test_promoted_structure_can_be_used_for_new_calculation
tests/integration/test_pyscf_relax_real.py::test_pyscf_relax_execution_creates_current_json
tests/integration/test_pyscf_relax_real.py::test_pyscf_relax_structure_changes
```

All fail with: `Geometry optimization failed: No module named 'berny'`

### 3.2 Complete Import Chain

```
test → svc.run.run_step()
  → service.py:6493 → runner.run()
  → runner.py:547 → executor.execute()
  → executor.py:704 → handler(job, calculation)
  → handler.py:111 → engine.run_step_with_chain()
  → pyscf_engine.py:916 → subprocess.run(cmd)
      WHERE cmd = [_get_pyscf_python(), "-m", "qmatsuite.engines.pyscf", ...]
  → pyscf_engine.py:75-86 → _get_pyscf_python()
      → engine_registry.py:812-822 → resolve_active_python("pyscf")
      → RETURNS: "/opt/homebrew/Caskroom/miniforge/base/bin/python" (CONDA Python)
  → SUBPROCESS runs conda Python
  → runner.py:727 → from pyscf.geomopt.geometric_solver → FAILS (no geometric in conda)
  → runner.py:730 → from pyscf.geomopt.berny_solver → FAILS (no berny in conda)
  → runner.py:764-766 → "Geometry optimization failed: No module named 'berny'"
```

### 3.3 Root Cause: Conda Python Prioritized Over Venv Python

**Before P35:** `engines.json` had no PySCF installations (no conda/dev_venv scan tiers existed). `resolve_active_python("pyscf")` returned `None`. `_get_pyscf_python()` fell back to `sys.executable` (venv Python). Venv Python has berny. Tests PASSED.

**After P35:** New conda scan tier discovered PySCF 2.11.0 in conda base environment. `ACTIVE_SOURCE_PRIORITY` ranks conda above dev_venv. `engines.json`:
```json
"pyscf": {
  "active": "conda-2.11.0",
  "installations": [
    {"id": "conda-2.11.0", "python_executable": "/opt/homebrew/Caskroom/miniforge/base/bin/python", "source": "conda"},
    {"id": "dev-venv-2.12.0", "python_executable": ".../QMatSuite/.venv/bin/python", "source": "dev_venv"}
  ]
}
```

Now `resolve_active_python("pyscf")` returns conda Python. Conda Python has PySCF but NOT berny/geometric.

**Verified empirically:**
```bash
# Venv Python — has berny:
$ .venv/bin/python -c "import berny"   # ✓ OK

# Conda Python — no berny:
$ /opt/homebrew/Caskroom/miniforge/base/bin/python -c "import berny"
# ModuleNotFoundError: No module named 'berny'
```

### 3.4 Why Pre-Flight Check Doesn't Catch This

`is_pyscf_available()` (`test_pyscf_relax_real.py:27-45`) checks:
```python
from pyscf.geomopt.berny_solver import optimize  # runs in VENV Python (test process)
```
This succeeds because the test process IS the venv Python which has berny. But the actual execution runs in a SUBPROCESS using the conda Python (from registry). **The availability check and the execution use different Python interpreters.**

---

## 4. COD Network Timeout Verification

Verified the COD endpoint is genuinely timing out:
```bash
$ python -c "import requests; requests.get('https://www.crystallography.net/cod/optimade/v1/structures?...', timeout=15)"
# Error: HTTPSConnectionPool(host='www.crystallography.net', port=443): Read timed out
```

This is a transient network issue, not a code bug. The test correctly skips via `pytest.skip(f"COD unavailable: {result.error or 'timeout'}")` at `test_online_structure_import.py:100`.

---

## 5. Proposed Fixes

### 5.1 Fix `_scan_bundled()` — Flat Directory Layout Support

**File:** `src/qmatsuite/core/engines/engine_registry.py:364-367`

**Current (broken):**
```python
for install_dir in sorted(candidates, reverse=True):
    bin_dir = install_dir / "bin"
    if not bin_dir.is_dir():
        continue
```

**Fix:** Fall back to searching the version directory itself if no `bin/` exists:
```python
for install_dir in sorted(candidates, reverse=True):
    bin_dir = install_dir / "bin"
    if not bin_dir.is_dir():
        # Fall back: binary may be directly in version dir (ORCA-style flat layout)
        bin_dir = install_dir

    found_binary = self._find_first_binary(engine_family, bin_dir)
    if not found_binary:
        continue
    ...
```

**Effect:** ORCA found at `orca_6_1_1_macosx_arm64_openmpi411/orca`. All 26 ORCA skips fixed.

**For Gaussian** (binary at `gaussian09/g09/g09` — doubly nested), also add a Gaussian-specific check:
```python
# Gaussian uses {version_dir}/{g_version}/{g_version} layout
if engine_family == "gaussian":
    for g_ver in ["g16", "g09", "g03"]:
        g_dir = install_dir / g_ver
        if g_dir.is_dir():
            found_binary = self._find_first_binary(engine_family, g_dir)
            if found_binary:
                bin_dir = g_dir
                break
```

**Effect:** Gaussian found at `gaussian09/g09/g09`. `engines.json` gets `gaussian: active=gaussian09, source=bundled`.

### 5.2 Fix PySCF Priority — Dev Venv Before Conda

**File:** `src/qmatsuite/core/engines/engine_registry.py:24-33`

**Current:**
```python
ACTIVE_SOURCE_PRIORITY = [
    "user_path", "user_venv", "bundled", "micromamba",
    "github_release", "homebrew", "conda", "dev_venv", "system_path",
]
```

**Fix:** Move `dev_venv` before `conda` and `homebrew`:
```python
ACTIVE_SOURCE_PRIORITY = [
    "user_path", "user_venv", "bundled", "micromamba",
    "github_release", "dev_venv", "homebrew", "conda", "system_path",
]
```

**Rationale:** In a dev checkout, the `.venv` is the primary working environment with all deps installed. Conda base environments often have the engine but lack optional dependencies (berny, geometric). The dev venv should take precedence over auto-discovered external environments.

**Effect:** PySCF active becomes `dev-venv-2.12.0` (venv Python, which has berny). All 4 failures fixed.

### 5.3 Fix Pre-Flight Check — Use Resolved Python

**Files:**
- `tests/integration/test_pyscf_relax_real.py:27-45`
- `tests/integration/test_relax_promote_e2e.py:44-60`

**Fix:** Replace direct `import` check with subprocess check using the resolved Python:
```python
def is_pyscf_available() -> bool:
    """Check if PySCF and an optimizer are available in the RESOLVED Python."""
    import subprocess as sp
    from qmatsuite.engine.pyscf_engine import PySCFEngine
    engine = PySCFEngine()
    pyscf_python = engine._get_pyscf_python()
    for mod in ["pyscf.geomopt.geometric_solver", "pyscf.geomopt.berny_solver"]:
        try:
            r = sp.run([pyscf_python, "-c", f"from {mod} import optimize"],
                       capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return True
        except Exception:
            pass
    return False
```

**Effect:** Tests skip cleanly instead of failing when the resolved Python lacks optimizer packages. Defense-in-depth: protects against future priority changes.

---

## 6. Summary of All Regressions

| Issue | Count | Root Cause | Fix |
|-------|-------|------------|-----|
| ORCA tests skip | 26 | `_scan_bundled()` requires `bin/` subdir; ORCA has flat layout | Fall back to version dir itself |
| Gaussian undiscovered | 0 tests affected (env var workaround) | `_scan_bundled()` requires `bin/`; Gaussian has nested layout | Add Gaussian-specific path handling |
| PySCF relax fails | 4 | Conda Python (no berny) prioritized over venv Python | Move `dev_venv` before `conda` in priority |
| **Total regressions** | **30** | | |

---

## 7. Execution Estimate

### Commit 1: `fix(engines): _scan_bundled fallback for flat directory layouts (ORCA, Gaussian)`
- `src/qmatsuite/core/engines/engine_registry.py:364-387` — modify `_scan_bundled()` to fall back to version dir when no `bin/`; add Gaussian nested path handling
- Delete `engines.json`, re-run `discover()`, verify ORCA and Gaussian found
- Risk: Low. Only changes bundled scan fallback.

### Commit 2: `fix(engines): reorder ACTIVE_SOURCE_PRIORITY — dev_venv before conda`
- `src/qmatsuite/core/engines/engine_registry.py:24-33` — reorder
- Delete `engines.json`, re-run `discover()`, verify PySCF active = dev_venv
- Risk: Low.

### Commit 3: `fix(tests): check PySCF optimizer via resolved Python, not test Python`
- `tests/integration/test_pyscf_relax_real.py:27-45`
- `tests/integration/test_relax_promote_e2e.py:44-60`
- Risk: Very low.

### Expected Result After All Fixes
- **0 new failures** (PySCF relax passes, ORCA tests pass)
- **~5 skips** (2 missing dirs, 2 soft gates, 0-1 COD network)
- Same as baseline commit 3677349
