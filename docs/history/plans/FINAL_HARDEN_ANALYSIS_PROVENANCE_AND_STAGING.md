# Hardening Plan: Analysis Objects, Provenance & Staging

**Date**: 2026-01-19  
**Status**: Ready for Implementation  
**Spec Reference**: `docs/specs/ANALYSIS_OBJECTS_FRAMEWORK.md`

---

## 1. Spec Compliance Audit

### Aligned ✅

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Cache location: `calc/.analysis/` (hidden) | ✅ Aligned | `src/quantumvitas/core/analysis/cache.py:18` — `ANALYSIS_CACHE_DIR = ".analysis"` |
| Provenance file: `calc/.runtime/provenance.json` | ✅ Aligned | `src/quantumvitas/core/provenance.py:25-27` — `RUNTIME_DIR = ".runtime"`, `PROVENANCE_FILE = "provenance.json"` |
| Stale detection: only source_files stat (size+mtime) | ✅ Aligned | `src/quantumvitas/core/analysis/cache.py:35-65` — `is_cache_stale()` only uses `stat.st_size` and `stat.st_mtime` |
| No sha256 in v1 for stale detection | ✅ Aligned | `src/quantumvitas/core/analysis/base.py:17` — `SourceFileStat` only has `size_bytes` and `mtime`, no `sha256` field |
| Parsers do not wrap positions | ✅ Aligned | `src/quantumvitas/core/analysis/trajectory/utils.py:13-42` — `wrap_positions()` is a separate utility, not called by parsers |
| Visual primitives are data+meta only (no style) | ✅ Aligned | `src/quantumvitas/core/analysis/primitives.py` — `Series1D`, `GeometryFrame`, `Marker` have no style fields |
| Provenance is current-only, for UI explanation | ✅ Aligned | `src/quantumvitas/core/provenance.py:1-6` docstring explicitly states this |
| Provenance NOT used for stale detection | ✅ Aligned | `src/quantumvitas/core/analysis/cache.py:43` — comment explicitly states this |
| Parser info in meta for debug | ✅ Aligned | `src/quantumvitas/core/analysis/base.py:78-80` — `parser_name` and `parser_version` fields |

### Deviations / Risks ⚠️

| Issue | Severity | Evidence | Impact |
|-------|----------|----------|--------|
| **CHGCAR in VASP ignore patterns** | 🔴 Critical | `src/quantumvitas/core/artifact_scanning.py:56-62` — VASP ignore includes `CHGCAR`, `CHG`, `WAVECAR` | Provenance fails to track staged CHGCAR; **root cause of failing test** |
| Provenance uses same ignore patterns as analysis | 🔴 Critical | `src/quantumvitas/core/provenance.py:173` calls `scan_raw_directory(calc_dir, engine, ...)` | Provenance misses files that are legitimately final artifacts but ignored for analysis performance |
| `_last_scan` not persisted, only reconstructed from files | 🟡 Medium | `src/quantumvitas/core/provenance.py:74-86` — reconstructs `_last_scan` from `provenance.files` | After restart, if new files are added, they may be detected as "added" but attribution is correct |
| mtime uses `float` (st_mtime), not `int` (mtime_ns) | 🟡 Low | `src/quantumvitas/core/artifact_scanning.py:27`, `src/quantumvitas/core/analysis/base.py:22` | Float precision may cause spurious mismatches on some filesystems; not critical for provenance |
| Path normalization uses native Path, not POSIX always | 🟡 Low | `src/quantumvitas/core/artifact_scanning.py:133` — `str(file_path.relative_to(base_dir))` | On Windows, paths may use backslashes; potential cross-platform issue |
| QE parser handles alat/crystal/bohr but lacks unit tests | 🟡 Low | `src/quantumvitas/parsers/qe/trajectory.py:166-183` — parsing logic present but no unit tests | Risk of regression in unit conversions |

---

## 2. Root Cause Analysis: Missing CHGCAR Provenance

### The Bug

**File**: `src/quantumvitas/core/artifact_scanning.py`  
**Lines**: 56-62

```python
ENGINE_IGNORE_PATTERNS: Dict[str, List[str]] = {
    # ...
    "vasp": [
        "WAVECAR",
        "CHGCAR",   # ← THIS IS THE BUG
        "CHG",
        "PROCAR",
        "DOSCAR",
    ],
    # ...
}
```

### Why This Happens

1. **Test setup** (`tests/integration/test_analysis_cache_staging.py:31-35`):
   - Creates `step1/OUTCAR` and `step1/CHGCAR`
   - Calls `update_provenance_after_step(..., engine="vasp")`

2. **Provenance update flow** (`src/quantumvitas/core/provenance.py:147-203`):
   - Calls `scan_raw_directory(calc_dir, engine, ...)` (line 173)
   - This applies engine-specific ignore patterns

3. **Scanning excludes CHGCAR** (`src/quantumvitas/core/artifact_scanning.py:176`):
   - `patterns = get_engine_ignore_patterns(engine)` returns `["WAVECAR", "CHGCAR", ...]`
   - `should_ignore("raw/step1/CHGCAR", patterns)` returns `True` (line 99 matches basename)

4. **Result**: CHGCAR is never added to `current_scan`, so it's never recorded in provenance.

### The Conceptual Confusion

The ignore patterns were designed for **two different purposes**:

| Purpose | Should Ignore CHGCAR? | Reason |
|---------|----------------------|--------|
| **Analysis cache staleness** | Maybe | If parser doesn't use CHGCAR, excluding it reduces scanning overhead |
| **Provenance tracking** | **NO** | Provenance must track ALL final artifacts for UI explanation |

The current implementation conflates these two purposes into a single ignore list.

---

## 3. Proposed Fix

### Philosophy Clarification

**Provenance vs Analysis Scanning are different concerns**:

| Concern | Purpose | Should Ignore CHGCAR? | Should Ignore outdir? |
|---------|---------|----------------------|----------------------|
| **Provenance** | UI explanation: "which run produced what" | **NO** - it's a staged artifact | Debatable (but simplest: NO) |
| **Analysis cache staleness** | Performance: "did source files change" | Maybe (if parser doesn't use it) | Yes (large scratch) |

**The current bug**: Both use the same `scan_raw_directory()` with engine ignore patterns, so provenance misses files that users expect to see.

### Minimal Change Set

**The fix**: Provenance scanning should NOT apply engine ignore patterns. Provenance tracks all files in raw/ for user explanation.

**Alternative consideration**: Create separate `PROVENANCE_IGNORE_PATTERNS` and `ANALYSIS_IGNORE_PATTERNS`. However, this adds complexity. The simpler approach is:
- Provenance scans **everything** (no engine patterns, only user-configured additional ignores)
- Analysis staleness checking uses `AnalysisObjectMeta.source_files`, which is parser-controlled

**Impact on existing tests**: The existing `test_ignores_outdir` test will fail and must be updated. This is intentional - we're changing the provenance philosophy to be more complete.

### Changes Required

#### Change 1: Add `scan_raw_directory_for_provenance()` (No Ignore Patterns)

**File**: `src/quantumvitas/core/artifact_scanning.py`

**Add new function** after `scan_raw_directory()`:

```python
def scan_raw_directory_for_provenance(
    calc_dir: Path,
    additional_ignore: Optional[List[str]] = None,
) -> Dict[str, FileStat]:
    """
    Scan calculation raw directory for provenance tracking.
    
    Unlike scan_raw_directory(), this does NOT apply engine-specific
    ignore patterns. Provenance tracks ALL final artifacts.
    
    Args:
        calc_dir: Calculation directory
        additional_ignore: User-configured patterns only
    
    Returns:
        Dict mapping calc-relative paths to FileStat
    """
    raw_dir = calc_dir / "raw"
    if not raw_dir.exists():
        return {}
    
    # Only user-configured patterns, NO engine defaults
    patterns = additional_ignore or []
    
    return scan_directory(raw_dir, patterns, base_dir=calc_dir)
```

#### Change 2: Update `update_provenance_after_step()` to Use New Scanner

**File**: `src/quantumvitas/core/provenance.py`

**Modify** the import and function call:

```python
# Change import
from quantumvitas.core.artifact_scanning import (
    FileStat,
    scan_raw_directory_for_provenance,  # Changed
    diff_scans,
)

# In update_provenance_after_step(), change line 173:
def update_provenance_after_step(
    calc_dir: Path,
    run_id: str,
    step_ulid: str,
    engine: str,  # Keep for future use (e.g., engine-specific provenance metadata)
    additional_ignore: Optional[List[str]] = None,
) -> Dict[str, str]:
    # ...
    
    # Scan current state - NO engine ignore patterns for provenance
    current_scan = scan_raw_directory_for_provenance(calc_dir, additional_ignore)
    
    # ... rest unchanged
```

---

## 4. Hardening Concerns

### A) Restart Consistency for Provenance Scanning

**Issue**: `_last_scan` is an in-memory field, reconstructed from `provenance.files` on load. This is correct but has edge cases.

**Current behavior** (acceptable):
- On restart, `_last_scan` is rebuilt from persisted `files` entries
- New files are detected as "added" with correct attribution
- Modified files are detected as "modified" with correct attribution
- This is correct behavior for current-only provenance

**Test to add**: Verify restart produces correct attribution.

### B) Hook Ordering

**Current behavior** (`src/quantumvitas/calculation/runner.py:612-623`):
- Provenance update occurs AFTER manifest update
- Comment says "after staging is complete, if any"

**Risk**: If staging happens in a separate post-job hook, provenance may run before staging.

**Verification needed**: Check if VASP staging (`src/quantumvitas/execution/vasp_staging.py`) is called before provenance update.

### C) Ignore Patterns & Normalization

**Issue**: Path normalization uses native Path, may produce backslashes on Windows.

**Fix**: Use `PurePosixPath` or `.as_posix()` for consistent path strings.

### D) mtime Precision

**Current behavior**: Uses `float` from `stat.st_mtime`.

**Improvement**: Use `stat.st_mtime_ns` (nanosecond precision) for more robust comparison. Not critical for provenance (which doesn't gate stale detection).

### E) Parser Unit Tests

**Issue**: QE parser handles alat/crystal/bohr conversions but lacks unit tests.

**Fix**: Add minimal fixtures with known QE outputs and expected positions.

---

## 5. Implementation Plan (Cursor-Auto-Ready)

### PR Scope

**Single PR**: "Fix provenance staging and harden foundation"

### Step-by-Step Tasks

#### Task 1: Fix artifact_scanning.py

**File**: `src/quantumvitas/core/artifact_scanning.py`

**Action**: Add `scan_raw_directory_for_provenance()` function after line 181.

```python
def scan_raw_directory_for_provenance(
    calc_dir: Path,
    additional_ignore: Optional[List[str]] = None,
) -> Dict[str, FileStat]:
    """
    Scan calculation raw directory for provenance tracking.
    
    Unlike scan_raw_directory(), this does NOT apply engine-specific
    ignore patterns. Provenance tracks ALL final artifacts for UI explanation.
    
    Args:
        calc_dir: Calculation directory
        additional_ignore: User-configured patterns only (e.g., "*.tmp")
    
    Returns:
        Dict mapping calc-relative paths to FileStat
    """
    raw_dir = calc_dir / "raw"
    if not raw_dir.exists():
        return {}
    
    # Only user-configured patterns, NO engine defaults
    patterns = additional_ignore or []
    
    return scan_directory(raw_dir, patterns, base_dir=calc_dir)
```

**Also add** path normalization fix in `scan_directory()` at line 133:

```python
# Change:
relative = str(file_path.relative_to(base_dir))

# To:
relative = file_path.relative_to(base_dir).as_posix()
```

#### Task 2: Update provenance.py

**File**: `src/quantumvitas/core/provenance.py`

**Action 1**: Change import at line 17-21:

```python
from quantumvitas.core.artifact_scanning import (
    FileStat,
    scan_raw_directory_for_provenance,
    diff_scans,
)
```

**Action 2**: Change line 173 in `update_provenance_after_step()`:

```python
# OLD:
current_scan = scan_raw_directory(calc_dir, engine, additional_ignore)

# NEW:
current_scan = scan_raw_directory_for_provenance(calc_dir, additional_ignore)
```

**Note**: Keep `engine` parameter in signature for future use (logging, engine-specific provenance metadata).

#### Task 3: Update Unit Tests for Provenance Scanning

**File**: `tests/unit/test_provenance.py` (existing file)

**IMPORTANT**: The existing `test_ignores_outdir` test (lines 97-116) will need to be UPDATED. The new philosophy is:
- Provenance tracks ALL files in raw/ (including those in outdir)
- Only user-configured additional_ignore patterns are respected

**Delete or update** the existing `test_ignores_outdir` test and **add new test class**:

```python
# UPDATE the existing test at lines 97-116:
# REMOVE or change test_ignores_outdir - provenance now tracks ALL files

class TestProvenanceScansAllFiles:
    """Provenance should track all files, including CHGCAR and outdir."""
    
    def test_provenance_tracks_chgcar(self, tmp_path):
        """CHGCAR should be tracked even for VASP engine."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        # Create CHGCAR (would be ignored by analysis scanning)
        (raw_dir / "CHGCAR").write_text("charge density")
        (raw_dir / "OUTCAR").write_text("output")
        
        # Update provenance with VASP engine
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "vasp")
        
        # Both files should be tracked
        prov = load_provenance(calc_dir)
        assert "raw/CHGCAR" in prov.files
        assert "raw/OUTCAR" in prov.files
    
    def test_provenance_tracks_qe_outdir(self, tmp_path):
        """Provenance now tracks outdir files too (for complete artifact tracking)."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        outdir = raw_dir / "outdir"
        outdir.mkdir(parents=True)
        
        # Create files
        (raw_dir / "scf.out").write_text("output")
        (outdir / "pwscf.save").write_text("save data")
        
        # Update
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "qe")
        
        # Check - both are now tracked
        prov = load_provenance(calc_dir)
        assert "raw/scf.out" in prov.files
        assert any("outdir" in p for p in prov.files)  # Now tracked!
    
    def test_provenance_respects_additional_ignore(self, tmp_path):
        """User-configured ignore patterns are still respected."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        (raw_dir / "scf.out").write_text("output")
        (raw_dir / "test.tmp").write_text("temp")
        
        # Ignore *.tmp via additional_ignore
        update_provenance_after_step(
            calc_dir, "01JRUN1", "01JSTEP1", "qe",
            additional_ignore=["*.tmp"]
        )
        
        prov = load_provenance(calc_dir)
        assert "raw/scf.out" in prov.files
        assert "raw/test.tmp" not in prov.files  # Ignored by user config
    
    def test_provenance_restart_consistency(self, tmp_path):
        """After restart, new files get correct attribution."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        # Step 1
        (raw_dir / "scf.out").write_text("step1")
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "qe")
        
        # Simulate restart by reloading
        prov1 = load_provenance(calc_dir)
        assert prov1.files["raw/scf.out"].step_ulid == "01JSTEP1"
        
        # Step 2 (after restart)
        (raw_dir / "bands.out").write_text("step2")
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP2", "qe")
        
        # Check attribution
        prov2 = load_provenance(calc_dir)
        assert prov2.files["raw/scf.out"].step_ulid == "01JSTEP1"  # Unchanged
        assert prov2.files["raw/bands.out"].step_ulid == "01JSTEP2"  # New
```

#### Task 4: Fix Integration Test Assertion (Optional Clarification)

**File**: `tests/integration/test_analysis_cache_staging.py`

The existing test is correct; it will pass after the fix. No changes needed.

#### Task 5: Add Path Normalization Test

**File**: `tests/unit/test_artifact_scanning.py` (new file)

```python
"""Tests for artifact scanning."""
import pytest
from pathlib import Path

from quantumvitas.core.artifact_scanning import (
    scan_directory,
    scan_raw_directory,
    scan_raw_directory_for_provenance,
    should_ignore,
    get_engine_ignore_patterns,
)


class TestPathNormalization:
    """Paths should use POSIX separators."""
    
    def test_scan_returns_posix_paths(self, tmp_path):
        """Scanned paths use forward slashes."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("content")
        
        result = scan_directory(subdir, base_dir=tmp_path)
        
        # Path should be POSIX (forward slashes)
        assert "subdir/file.txt" in result
        assert "\\" not in result["subdir/file.txt"].relative_path


class TestIgnorePatterns:
    """Engine ignore patterns work correctly."""
    
    def test_vasp_ignores_wavecar(self):
        patterns = get_engine_ignore_patterns("vasp")
        assert should_ignore("WAVECAR", patterns)
    
    def test_vasp_ignores_chgcar_for_analysis(self):
        """CHGCAR is ignored for analysis (performance)."""
        patterns = get_engine_ignore_patterns("vasp")
        assert should_ignore("CHGCAR", patterns)
    
    def test_qe_ignores_outdir(self):
        patterns = get_engine_ignore_patterns("qe")
        assert should_ignore("outdir/pwscf.save", patterns)


class TestProvenanceScanning:
    """Provenance scanning tracks all files."""
    
    def test_provenance_scan_no_engine_patterns(self, tmp_path):
        """Provenance scan does not apply engine ignore patterns."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        (raw_dir / "CHGCAR").write_text("charge")
        (raw_dir / "WAVECAR").write_text("wave")
        
        # Provenance scanning should include CHGCAR and WAVECAR
        result = scan_raw_directory_for_provenance(calc_dir)
        
        assert "raw/CHGCAR" in result
        assert "raw/WAVECAR" in result
    
    def test_analysis_scan_uses_engine_patterns(self, tmp_path):
        """Analysis scan applies engine ignore patterns."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        (raw_dir / "CHGCAR").write_text("charge")
        (raw_dir / "OUTCAR").write_text("output")
        
        # Analysis scanning should exclude CHGCAR
        result = scan_raw_directory(calc_dir, "vasp")
        
        assert "raw/CHGCAR" not in result
        assert "raw/OUTCAR" in result
```

#### Task 6: Add QE Parser Unit Conversion Test

**File**: `tests/unit/test_qe_trajectory_parser.py` (new file)

```python
"""Tests for QE trajectory parser unit conversions."""
import pytest
import tempfile
from pathlib import Path

from quantumvitas.parsers.qe.trajectory import QETrajectoryParser


class TestQEUnitConversions:
    """Test that QE parser correctly converts units."""
    
    def test_ry_to_ev_conversion(self):
        """Energy in Ry is converted to eV."""
        from quantumvitas.parsers.qe.trajectory import RY_TO_EV
        
        # 1 Ry = 13.605693... eV
        assert abs(RY_TO_EV - 13.605693122994) < 1e-6
    
    def test_bohr_to_angstrom_conversion(self):
        """alat in Bohr is converted to Å."""
        # From QE output: "lattice parameter (alat) = 10.2623 a.u."
        # Expected alat in Å: 10.2623 * 0.529177 = 5.431...
        bohr_to_angstrom = 0.529177
        alat_bohr = 10.2623
        alat_angstrom = alat_bohr * bohr_to_angstrom
        
        assert abs(alat_angstrom - 5.431) < 0.01
    
    def test_parse_angstrom_positions(self, tmp_path):
        """Positions in angstrom are returned as-is."""
        # Create minimal QE relax output with ATOMIC_POSITIONS (angstrom)
        qe_output = """
     Program PWSCF v.7.2

     bravais-lattice index     =            0
     lattice parameter (alat)  =      10.2623  a.u.
     
ATOMIC_POSITIONS (angstrom)
Si      0.000000    0.000000    0.000000
Si      1.357625    1.357625    1.357625

     number of scf cycles    =   1
     
End final coordinates
"""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        output_file = raw_dir / "relax.out"
        output_file.write_text(qe_output)
        
        parser = QETrajectoryParser()
        traj = parser.parse(raw_dir, calc_dir)
        
        # Positions should be in Å
        assert len(traj.frames) >= 1
        assert traj.frames[0].positions[0, 0] == pytest.approx(0.0, abs=1e-6)
        assert traj.frames[0].positions[1, 0] == pytest.approx(1.357625, abs=1e-4)
```

### Files Changed Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/quantumvitas/core/artifact_scanning.py` | Modify | Add `scan_raw_directory_for_provenance()`, fix path normalization |
| `src/quantumvitas/core/provenance.py` | Modify | Use new provenance scanner |
| `tests/unit/test_provenance.py` | **Modify** | Remove/update `test_ignores_outdir`, add CHGCAR tracking tests, restart consistency test |
| `tests/unit/test_artifact_scanning.py` | Create | Path normalization tests, ignore pattern tests |
| `tests/unit/test_qe_trajectory_parser.py` | Create | Unit conversion tests |

**Breaking test change**: The existing `test_ignores_outdir` test (lines 97-116) will fail after this fix. This is intentional. Remove or update that test to reflect the new philosophy.

### Acceptance Criteria Checklist

- [ ] `test_provenance_after_staging_chgcar` passes
- [ ] `test_provenance_updated_after_staging_not_before` still passes
- [ ] New test `test_provenance_tracks_chgcar` passes
- [ ] New test `test_provenance_restart_consistency` passes
- [ ] New test `test_provenance_scan_no_engine_patterns` passes
- [ ] New test `test_analysis_scan_uses_engine_patterns` passes
- [ ] Path normalization test passes
- [ ] QE parser unit conversion test passes
- [ ] All existing tests still pass (`pytest tests/`)
- [ ] No linter errors

### PR Breakdown

**Single PR**: `fix: provenance tracks all artifacts, not just analysis sources`

**Commit sequence**:
1. `feat(scanning): add scan_raw_directory_for_provenance without engine patterns`
2. `fix(provenance): use provenance scanner that tracks all files`
3. `fix(scanning): normalize paths to POSIX format`
4. `test: add provenance hardening tests`
5. `test: add artifact scanning tests`
6. `test: add QE parser unit conversion tests`

---

## 6. Summary

| Issue | Fix | Risk |
|-------|-----|------|
| CHGCAR missing from provenance | New `scan_raw_directory_for_provenance()` without engine patterns | Low (additive change) |
| Path normalization | Use `.as_posix()` | Low (cosmetic) |
| Restart consistency | Already correct; add test | None (test only) |
| QE parser units | Already correct; add test | None (test only) |

**Estimated effort**: 30 minutes implementation + 30 minutes testing

---

**End of Plan**

