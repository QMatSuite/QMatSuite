# Analysis Pipeline — Phase 3 Implementation Plan

**Author:** Claude Opus 4.6 (senior architect role)
**Date:** 2026-02-08
**Prerequisite:** `ANALYSIS_PIPELINE_PHASE2_ACCEPTANCE_REVIEW.md` (same directory)
**Spec Reference:** `ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` v1.4 (BINDING)

---

## Execution Notes for Codex

**Read these BEFORE writing any code.**

### Pitfall 0: venv and Test Commands (MANDATORY)

**Always activate the project venv before running anything:**
```bash
source .venv/bin/activate
```

**Full test suite — ALWAYS use parallel execution:**
```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Never use `-x -q --tb=line` for full suite runs.** The parallel flags (`-n auto --dist=loadfile`) are mandatory — the test suite is large and serial execution is unacceptably slow.

**For single-file or targeted tests**, parallel flags are optional:
```bash
source .venv/bin/activate && python -m pytest tests/drivers/vasp/test_vasp_bands_parser.py -v --tb=short
```

Every verification command in this plan assumes the venv is active. If a command fails with `ModuleNotFoundError`, you forgot to activate the venv.

### Pitfall 1: Legacy Code Is Woven Into service.py

`service.py` has 16 `from quantumvitas.analysis.*` import sites scattered across the `Analysis` inner class methods. These are lazy imports (inside method bodies), not top-level. When deleting legacy methods, do NOT accidentally break the new pipeline methods that live in the same class. Specifically:

- Lines 1682–1864 (Surface A/B/C + snapshot) are NEW — **do not touch**.
- Lines 512–706, 1122–1230, 1240–1340, 1866–1943, 1945–2040 are LEGACY — these are the deletion targets.

### Pitfall 2: Daemon Handler Registration Table

`daemon/server.py` has a handler registration dict (around line 350–370). Legacy entries:
```
"ensure_calculation_analysis": self._handle_ensure_calculation_analysis,
"get_scf_convergence": self._handle_get_scf_convergence,
"get_dos_data": self._handle_get_dos_data,
"get_band_structure_data": self._handle_get_band_structure_data,
```
These must be removed along with their handler methods. But the NEW entries (`get_analysis`, `get_analysis_snapshot`, `get_step_digest`, `list_raw_files`, `read_raw_file`) must remain.

### Pitfall 3: VASP Bands ≠ QE Bands

VASP does not have a separate post-processing step (no `bands.x` equivalent). The eigenvalues are written directly during the `bandspw` step to `EIGENVAL` (or `vasprun.xml`). The gen_step_sequence for VASP bands should be `["bandspw"]` (same as QE), but the parser reads EIGENVAL, not `*.bands.dat.gnu`.

**Real EIGENVAL format** (from our actual Si bands run at `.tmp/engine_research/vasp/real_run/si_bands/EIGENVAL`):
```
    2    2    1    1                      ← header line 1: NION, NION, ?, ?
  0.8009131E+02 ...  0.5000000E-15       ← header line 2: cell volume info
   1.0000000000000000E-004               ← header line 3: temperature
  CAR                                    ← header line 4: coordinate type
 Si diamond band structure               ← header line 5: system name
      8    200     16                    ← NELECT  NKPTS  NBANDS
                                         ← blank line
  0.0000000E+00  0.0000000E+00  0.0000000E+00  0.5000000E-02  ← kx ky kz weight
      1        -10.068717   1.000000     ← band_index  energy_eV  occupation
      2         -6.418531   1.000000
      ...
     16          5.300004   0.000000
                                         ← blank line separates k-points
  <next k-point block>
```
Our real run: 200 k-points, 16 bands, G→X→W→K→G→L path (40 points per segment).

### Pitfall 4: Test Fixtures Must Be Real VASP Output

All test data must live under `tests/data/`, never under `.tmp/`. **Tests must NEVER reference `.tmp/` paths** — the gate test `test_no_tmp_corpus_in_runtime` enforces this. You can READ files from `.tmp/` during research/development, and COPY artifacts from `.tmp/` into `tests/data/`, but all test code and fixtures must use `tests/data/` paths only.

For the VASP bands test, **do NOT synthesize fake data**. We already have a real VASP Si bands run at:

```
.tmp/engine_research/vasp/real_run/si_bands/
├── EIGENVAL    (3606 lines, 200 k-points, 16 bands — REAL VASP 6.5.0 output)
├── KPOINTS     (Line-mode: G→X→W→K→G→L, 40 pts/segment)
├── INCAR       (ICHARG=11, ENCUT=300, NBANDS=16, ISMEAR=0)
├── POSCAR      (Si diamond, 2 atoms)
├── OUTCAR      (full output with Fermi energy)
├── vasprun.xml (full XML — Fermi energy at <i name="efermi">)
└── ...
```

Copy the minimum needed files (EIGENVAL, KPOINTS, POSCAR, and a trimmed vasprun.xml or OUTCAR snippet for Fermi energy) into `tests/data/analysis_vasp_bands/`. These are real artifacts from a real VASP calculation — the parser must handle them correctly.

### Pitfall 5: Contract Crawler Exemptions

When deleting legacy methods, their contract crawler entries (in `tests/contract_crawler/introspection.py`) must also be removed. When adding new VASP analysis methods, no new exemptions should be needed — the universal `get_analysis()` endpoint already covers all engines.

### Pitfall 6: Gate Test Will Enforce Capability Declaration

Gate test `test_analysis_capability_declaration` (line 278 in `test_analysis_invariants.py`) scans all `@register_parser` decorators that are NOT `scf_digest` and verifies the engine's driver has matching `ANALYSIS_CAPABILITIES`. If you add `@register_parser("vasp", "bands")` without adding `ANALYSIS_CAPABILITIES` to `VASPDriver`, the gate test will fail.

### Pitfall 7: No Engine-Specific Logic in Universal Code

Gate test `test_no_engine_branching_in_orchestrator` scans `orchestrator.py`, `bundles.py`, and all transform files for string comparisons against engine names. Never put `if engine == "vasp"` in any universal analysis module.

### Pitfall 8: VASP Installation and Research Resources Available Locally

VASP 6.5.0 is installed and runnable at `.qmatsuite/engines/vasp/vasp.6.5.0/bin/`. Pseudopotentials are at `.qmatsuite/engines/vasp/potpaw_PBE.64/` and `.qmatsuite/engines/vasp/potpaw_LDA.64/`.

**Research resources for understanding EIGENVAL/KPOINTS format** (use ALL of these before writing the parser):

| Resource | Path (relative to repo root) | What it contains |
|----------|------------------------------|------------------|
| Real Si bands run | `.tmp/engine_research/vasp/real_run/si_bands/` | Complete VASP output: EIGENVAL, KPOINTS, OUTCAR, vasprun.xml, etc. |
| 12 curated cases | `tests/inputformat/samples/vasp/` | Input files for si_scf, si_bands, si_relax, si_dos, etc. |
| Normalized samples | `.tmp/engine_research/vasp/normalized/` | 15 external VASP examples |
| VASP research docs | `docs/engines/vasp/PHASE_B1_PLAN.md`, `PHASE_B1_WORKLOG.md` | Our prior detailed VASP research |
| VASP sources log | `docs/engines/vasp/SOURCES.md`, `.tmp/engine_research/vasp/SOURCES.md` | URLs and references used |
| Curated index | `docs/engines/vasp/CURATED_INDEX.md` | Sample diversity rationale |
| INCAR tag DB | `src/quantumvitas/drivers/vasp/data/vasp_incar_tags.json` | 232 tags with types |
| Existing VASP IO | `src/quantumvitas/drivers/vasp/io/incar.py` | Parse/write INCAR (reusable patterns) |
| Existing VASP parser | `src/quantumvitas/drivers/vasp/parsers/output.py` | VASPOutputParser for scf_digest (vasprun.xml + OUTCAR) |

You can also **search the web** for VASP EIGENVAL format documentation and parsing examples. The VASP wiki has detailed format specs.

---

## Section 1: Gap Closure

### Step G1: Delete Dead `analysis/dos.py`

**Problem:** `analysis/dos.py` (168 lines) is DEPRECATED and has zero imports anywhere in the codebase.

**Actions:**
1. Delete `src/quantumvitas/analysis/dos.py`
2. Remove any re-export from `analysis/public.py` or `analysis/__init__.py` if present

**Verification:**
```bash
grep -r "from quantumvitas.analysis.dos" src/ tests/ && echo "FAIL: still imported" || echo "OK: no imports"
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Step G2: Add Staleness Invalidation Test

**Problem:** `check_staleness()` is implemented but has no direct test. This is a correctness gap — if staleness detection breaks, the memo cache serves stale data silently.

**Actions:**
1. Create `tests/api/test_analysis_staleness.py`:
   - Set up a QE bands run via `setup_qe_bands_run(tmp_path)`
   - Call `get_analysis()` — should succeed
   - Modify the source evidence file (append a byte to `si.bands.dat.gnu`)
   - Call `get_analysis()` again — should re-derive (not serve stale memo)
   - Assert the second call's bundle is still valid (not an error)
   - Assert the evidence fingerprint changed (or at minimum, the code path re-derived)

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/api/test_analysis_staleness.py -v --tb=short
```

---

## Section 2: QE Golden Daemon-Level Test

### Step D1: Create QE Bands Golden Daemon Test

**Problem:** No test exercises the full daemon RPC → analysis pipeline → CAS/SQLite path. The existing "ancient" daemon test (`tests/daemon/test_si_bands_calculation_daemon.py`) only tests legacy endpoints.

**Goal:** A single test that:
1. Uses the committed `si_bands_demo.yml` from `resources/demo_projects/`
2. Actually runs QE (marked `pytest.mark.qe_core`)
3. Runs SCF → NSCF → bandspw → bands (the full 4-step QE bands workflow)
4. Asserts on the NEW pipeline (not legacy):
   - `get_step_digest()` returns `available: True` for each step
   - `get_analysis(run_ulid, "bands")` returns a bundle with correct structure
   - `get_analysis_snapshot(run_ulid, "bands")` returns the same `canonical_sha`
   - `list_raw_files()` includes `*.bands.dat.gnu`
   - SQLite `analysis_snapshots` table has exactly 1 row for this run
   - CAS blob exists at `.provenance/.cas/analysis/<sha>.json.gz`
5. Does NOT call any legacy endpoints (`ensure_analysis`, `get_band_structure_data`, etc.)

**Actions:**
1. Create `tests/daemon/test_si_bands_golden_daemon.py`
2. Use the same fixture pattern as the ancient test: `QVDaemon` + `QVService` + `JobManager`, project initialized from `si_bands_demo.yml`
3. After the run completes successfully, call the 5 new RPC endpoints via `daemon.handle_request()`
4. Assert heavily on the response shapes and CAS/SQLite artifacts
5. Mark with `pytest.mark.qe_core`

**Key imports / references:**
- Demo: `resources/demo_projects/si_bands_demo.yml` (4 steps: scf, nscf, bandspw, bands)
- Fixture data seeded by: `tests/data/analysis_bands/` (committed `.bands.dat.gnu` + `.pp.out`)
- Daemon helpers: `send_request()`, `wait_for_job()` from the ancient test (can be shared or copied)
- New RPC types: `get_analysis`, `get_analysis_snapshot`, `get_step_digest`, `list_raw_files`, `read_raw_file`

**Verification:**
```bash
# Must be run on a machine with QE installed:
source .venv/bin/activate && python -m pytest tests/daemon/test_si_bands_golden_daemon.py -v --tb=short -m qe_core
```

### Step D2: Mark Ancient Daemon Test as Legacy

**Problem:** `test_si_bands_calculation_daemon.py` calls legacy `get_band_structure_data` and `analyze_band`. It should be marked so it's clearly superseded.

**Actions:**
1. Add a module-level docstring note to `test_si_bands_calculation_daemon.py`:
   ```
   LEGACY: This test exercises the old analysis/artifacts.py pipeline.
   Superseded by test_si_bands_golden_daemon.py (new pipeline).
   Will be deleted after Section 3 legacy removal.
   ```
2. Do NOT delete it yet — it serves as a regression guard until legacy removal is complete.

**Verification:**
```bash
head -20 tests/daemon/test_si_bands_calculation_daemon.py | grep -i legacy && echo "OK" || echo "FAIL"
```

---

## Section 3: Legacy Removal + Golden Contract Updates

### Step L1: Delete Legacy Analysis Methods from service.py

**Problem:** The `Analysis` inner class in `service.py` contains legacy methods that import from the deprecated `analysis/artifacts.py` module. These must be removed.

**Methods to delete (all inside `class Analysis` in `service.py`):**
- `get_summary()` (lines ~512–561) — uses `read_artifact, AnalysisType`
- `list_properties()` (lines ~563–609) — uses `artifact_exists, AnalysisType`
- `get_property_ref()` (lines ~611–706) — uses `get_artifact_path, read_artifact`
- `load_artifact()` (lines ~708–798) — uses `get_property_ref` output
- `get_band_structure_data()` (lines ~1122–1230) — uses `parse_bands_gnu, read_artifact`
- `get_scf_convergence_data()` (lines ~1224–1340) — uses `parse_scf_output, read_artifact`
- `ensure_analysis()` (lines ~1866–1943) — dispatches to the three above
- `get_dos_data()` (lines ~1945–2040) — uses `parse_dos_data, read_artifact`
- `analyze_band()` — if present, delete
- `analyze_dos()` — if present, delete

**Methods to KEEP:**
- `list_raw_files()` (line 1682) — Surface A, NEW
- `read_raw_file()` (line 1760) — Surface A, NEW
- `get_step_digest()` (line 1780) — Surface B, NEW
- `get_analysis()` (line 1823) — Surface C, NEW
- `get_analysis_snapshot()` (line 1854) — Snapshot replay, NEW
- `get_reference_analysis()` (line ~2042) — Demo reference data, keep for now

**Actions:**
1. Delete the legacy methods listed above from `service.py`
2. Remove all `from quantumvitas.analysis.artifacts import ...` statements that are no longer needed
3. Remove all `from quantumvitas.analysis.parsers import ...` statements that are no longer needed
4. Keep `from quantumvitas.analysis.structure_viz import ...` (structure visualization is independent)
5. Keep `from quantumvitas.analysis.kpath import ...` (k-path generation is independent)

**Verification:**
```bash
grep -c "from quantumvitas.analysis.artifacts" src/quantumvitas/api/service.py
# Expected: 0
grep -c "AnalysisType" src/quantumvitas/api/service.py
# Expected: 0
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Step L2: Delete Legacy Daemon Handlers

**Problem:** Daemon `server.py` has 4 legacy handler registrations + 4 handler methods.

**Actions:**
1. Remove these entries from the handler registration dict (~line 350–370):
   - `"ensure_calculation_analysis"`
   - `"get_scf_convergence"`
   - `"get_dos_data"`
   - `"get_band_structure_data"`
2. Delete the corresponding handler methods:
   - `_handle_ensure_calculation_analysis` (line ~4608)
   - `_handle_get_scf_convergence` (line ~4682)
   - `_handle_get_dos_data` (line ~4704)
   - `_handle_get_band_structure_data` (line ~4728)

**Verification:**
```bash
grep -c "ensure_calculation_analysis\|get_scf_convergence\|get_dos_data\|get_band_structure_data" src/quantumvitas/daemon/server.py
# Expected: 0 (or just comments if any)
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Step L3: Delete `analysis/artifacts.py` Module

**Problem:** After L1 and L2, `analysis/artifacts.py` should have zero import sites.

**Actions:**
1. Verify: `grep -r "from quantumvitas.analysis.artifacts" src/ tests/` returns nothing
2. Delete `src/quantumvitas/analysis/artifacts.py`
3. Remove any re-export from `analysis/__init__.py` or `analysis/public.py`
4. Remove `AnalysisType` from any public re-exports

**Verification:**
```bash
test ! -f src/quantumvitas/analysis/artifacts.py && echo "OK: deleted" || echo "FAIL: still exists"
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Step L4: Fix Broken Tests After Legacy Removal

**Problem:** Some tests may import legacy methods. These must be updated or deleted.

**Actions:**
1. Run full test suite and identify failures
2. For each failing test:
   - If it tests legacy behavior that is now superseded by new pipeline tests → DELETE
   - If it tests valid behavior via legacy API → REWRITE to use new API
3. Update `tests/api/test_analysis_capabilities.py` if it imports `ensure_analysis`
4. Delete `tests/daemon/test_si_bands_calculation_daemon.py` (superseded by golden test from D1)

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
# All tests must pass. No legacy analysis imports should remain in passing tests.
```

### Step L5: Update Contract Crawler

**Problem:** Contract crawler may still reference deleted legacy methods. Exemptions for deleted endpoints must be removed.

**Actions:**
1. In `tests/contract_crawler/introspection.py`, remove any entries for deleted methods:
   - `get_summary`, `list_properties`, `get_property_ref`, `load_artifact`
   - `get_band_structure_data`, `get_dos_data`, `get_scf_convergence_data`
   - `ensure_analysis`, `analyze_band`, `analyze_dos`
2. Keep entries for: `list_raw_files`, `read_raw_file`, `get_step_digest`, `get_analysis`, `get_analysis_snapshot`
3. Run contract crawler to verify

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/contract_crawler/ -v --tb=short
```

### Step L6: Add Gate Test — No Legacy Analysis Imports in Runtime

**Problem:** Need a gate to prevent re-introduction of legacy `analysis/artifacts.py` imports.

**Actions:**
1. Add to `tests/gates/test_analysis_invariants.py`:
   ```python
   def test_no_legacy_analysis_artifact_imports() -> None:
       """Legacy analysis/artifacts.py must not be imported by runtime code."""
       runtime_roots = [
           REPO_ROOT / "src" / "quantumvitas" / "api",
           REPO_ROOT / "src" / "quantumvitas" / "daemon",
           REPO_ROOT / "src" / "quantumvitas" / "core",
       ]
       for root in runtime_roots:
           for path in root.rglob("*.py"):
               text = path.read_text(encoding="utf-8")
               assert "from quantumvitas.analysis.artifacts" not in text, (
                   f"{path} imports deprecated analysis/artifacts module"
               )
               assert "quantumvitas.analysis.artifacts" not in text, (
                   f"{path} references deprecated analysis/artifacts module"
               )
   ```

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/gates/test_analysis_invariants.py::test_no_legacy_analysis_artifact_imports -v
```

---

## Section 4: VASP Bands — Demo + Provider + Golden Test

### Step V1: Research EIGENVAL Format + Copy Real Artifacts to Test Fixtures

**Problem:** Need real VASP band structure output as test fixtures. We already have a complete Si bands run.

**Phase 1 — Research (BEFORE writing any parser code):**

1. Read the real EIGENVAL file at `.tmp/engine_research/vasp/real_run/si_bands/EIGENVAL` to understand the exact format (header structure, k-point blocks, band indexing, energy/occupation columns)
2. Read the KPOINTS file at `.tmp/engine_research/vasp/real_run/si_bands/KPOINTS` to understand Line-mode format (label extraction from `! G`, `! X`, etc.)
3. Read the existing VASPOutputParser at `src/quantumvitas/drivers/vasp/parsers/output.py` to see how vasprun.xml is already parsed (Fermi energy extraction pattern exists here — reuse it)
4. Read `docs/engines/vasp/PHASE_B1_WORKLOG.md` and `docs/engines/vasp/SOURCES.md` for prior research
5. Read `.tmp/engine_research/vasp/normalized/` samples for additional EIGENVAL format variations (spin-polarized, SOC, metals, etc.)
6. Search the web for "VASP EIGENVAL format specification" and "VASP KPOINTS line-mode format" to fill any gaps
7. Cross-reference with `tests/inputformat/samples/vasp/si_bands/` (our curated INCAR+POSCAR+KPOINTS)

**Phase 2 — Copy real artifacts:**

1. Create `tests/data/analysis_vasp_bands/` directory
2. Copy from `.tmp/engine_research/vasp/real_run/si_bands/`:
   - `EIGENVAL` — full file (3606 lines, 200 k-points, 16 bands) — **real VASP 6.5.0 output**
   - `KPOINTS` — Line-mode: G→X→W→K→G→L with 40 pts/segment
   - `POSCAR` — Si diamond, 2 atoms (needed for lattice vectors → reciprocal space distances)
3. Extract a minimal Fermi energy snippet — choose ONE of:
   - Option A: Copy a trimmed `vasprun.xml` containing only the `<i name="efermi">` tag and surrounding `<parameters>` block (remove huge `<eigenvalues>` arrays to keep the file small)
   - Option B: Copy `OUTCAR` and let tests grep for `E-fermi` (OUTCAR is large; trimming is preferred)
   - Option C: Create a small `OUTCAR_snippet` with just the `E-fermi :   5.XXXX` line and a few surrounding lines
4. Do NOT include large binary files (WAVECAR, CHGCAR, vaspout.h5)
5. Do NOT include POTCAR (licensing)

**Known values from the real run (use these in test assertions):**
- 200 k-points, 16 bands, 8 electrons
- K-path: G(0,0,0)→X(0.5,0,0.5)→W(0.5,0.25,0.75)→K(0.375,0.375,0.75)→G(0,0,0)→L(0.5,0.5,0.5)
- 5 segments × 40 k-points = 200 total
- First band energy at G: ~ -10.07 eV (deep valence)
- Band gap: Si has indirect gap ~ 0.6 eV (LDA) between G-valence and ~X-conduction

**Verification:**
```bash
ls tests/data/analysis_vasp_bands/
# Expected: EIGENVAL, KPOINTS, POSCAR, plus Fermi-energy source (trimmed vasprun.xml or OUTCAR snippet)
wc -l tests/data/analysis_vasp_bands/EIGENVAL
# Expected: 3606
head -6 tests/data/analysis_vasp_bands/EIGENVAL | tail -1
# Expected: "      8    200     16" (NELECT NKPTS NBANDS)
```

### Step V2: Implement VASPBandsProvider

**Problem:** VASP has no `@register_parser("vasp", "bands")` provider. Need one that parses EIGENVAL into `BandStructure`.

**Research sources to consult BEFORE writing the parser:**
- Real EIGENVAL: `tests/data/analysis_vasp_bands/EIGENVAL` (committed in V1)
- Existing VASP output parser: `src/quantumvitas/drivers/vasp/parsers/output.py` (vasprun.xml + OUTCAR patterns)
- QE bands parser (reference implementation): `src/quantumvitas/drivers/qe/parsers/bands.py`
- Prior VASP research: `docs/engines/vasp/PHASE_B1_WORKLOG.md`
- External VASP examples: `.tmp/engine_research/vasp/normalized/` (15 cases, some with bands)
- Real run with all outputs: `.tmp/engine_research/vasp/real_run/si_bands/` (EIGENVAL + vasprun.xml + OUTCAR)
- Web search: "VASP EIGENVAL format", "VASP wiki EIGENVAL", "VASP KPOINTS line-mode"

**Actions:**
1. Create `src/quantumvitas/drivers/vasp/parsers/bands.py` with three public functions:

   **`parse_eigenval(eigenval_path: Path) -> dict`** — Standalone EIGENVAL parser:
   - Read 5 header lines (lines 1-5)
   - Parse line 6: `NELECT  NKPTS  NBANDS` (space-separated integers)
   - Skip blank line
   - For each k-point block: parse `kx ky kz weight` line, then `NBANDS` lines of `band_index energy occupation`
   - Blocks separated by blank lines
   - Return: `{n_electrons: int, n_kpoints: int, n_bands: int, kpoints: ndarray(N,3), weights: ndarray(N), eigenvalues: ndarray(N,M), occupations: ndarray(N,M), system_name: str}`
   - Handle edge cases: trailing whitespace, blank lines at EOF, spin-polarized (two spin channels — detect from header line 1, parse both)

   **`_read_kpoints_labels(raw_dir: Path) -> list[HighSymPoint]`** — KPOINTS label extractor:
   - Detect "Line-mode" or "line" (case-insensitive) on line 3
   - Parse coordinate + label pairs: `0.00000 0.00000 0.00000  ! G`
   - Labels appear after `!` character
   - Pairs of lines define segments; blank lines separate segments
   - Deduplicate consecutive labels at segment boundaries (end of segment N = start of segment N+1)
   - Return ordered list with k-distances computed from cumulative Euclidean distance of k-point coordinates in reciprocal space

   **`VASPBandsProvider`** — Analysis provider class:
   ```python
   @register_parser("vasp", "bands")
   class VASPBandsProvider:
       """VASP band structure analysis provider."""

       def can_parse(self, raw_dir: Path) -> bool:
           return (raw_dir / "EIGENVAL").exists()

       def parse(self, raw_dir: Path, calc_dir: Path | None = None, **kwargs) -> BandStructure:
           # 1. parse_eigenval(raw_dir / "EIGENVAL")
           # 2. Compute k-distances: cumulative Euclidean distance in reciprocal space
           # 3. _read_kpoints_labels(raw_dir) for high-symmetry points
           # 4. Fermi energy: try vasprun.xml (<i name="efermi">), then OUTCAR (E-fermi), then None
           #    (Reuse pattern from existing VASPOutputParser in output.py)
           # 5. Build AnalysisObjectMeta + BandStructure
           ...
   ```

2. Wire parser registration in `src/quantumvitas/drivers/vasp/parsers/__init__.py`:
   ```python
   """VASP analysis parsers.

   Importing this package triggers parser registration via @register_parser.
   """
   from .output import VASPOutputParser
   from .bands import VASPBandsProvider

   __all__ = ["VASPOutputParser", "VASPBandsProvider"]
   ```

3. Ensure `src/quantumvitas/drivers/vasp/__init__.py` imports parsers:
   ```python
   from . import parsers  # noqa: F401, E402
   ```

**Key constraints:**
- EIGENVAL parsing must be stdlib-only (plus numpy for arrays)
- The parser must NOT import from `quantumvitas.analysis.*` (legacy) — only from `quantumvitas.core.analysis.*`
- k-distance computation: cumulative Euclidean distance between consecutive k-point coordinates
- Fermi energy: try `vasprun.xml` first (ElementTree, `<i name="efermi">`), then OUTCAR regex (`E-fermi\s*:\s*([\d.-]+)`), then None
- Must handle the real EIGENVAL from V1 correctly (200 kpts, 16 bands, 8 electrons)

**Verification:**
```bash
source .venv/bin/activate && python -c "
from quantumvitas.parsers.registry import get_parser
import quantumvitas.drivers.vasp
p = get_parser('vasp', 'bands')
assert p is not None, 'VASP bands parser not registered'
print('OK: VASP bands parser registered')
"
```

### Step V3: Add ANALYSIS_CAPABILITIES to VASPDriver

**Problem:** Gate test `test_analysis_capability_declaration` will fail if `VASPBandsProvider` is registered but `VASPDriver` has no `ANALYSIS_CAPABILITIES`.

**Actions:**
1. Add to `src/quantumvitas/drivers/vasp/driver.py`:
   ```python
   from quantumvitas.core.analysis.capability import AnalysisCapability

   class VASPDriver(BaseEngineDriver):
       # ... existing code ...
       ANALYSIS_CAPABILITIES = [
           AnalysisCapability(
               object_type="bands",
               gen_step_sequence=["bandspw"],
               evidence_files=["EIGENVAL"],
           ),
       ]
   ```

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/gates/test_analysis_invariants.py::test_analysis_capability_declaration -v
```

### Step V4: Unit Tests for VASP Bands Parser (Against Real Data)

**Key principle:** All assertions are against the real VASP output committed in V1. This is NOT synthetic data — every expected value comes from the actual VASP 6.5.0 Si bands run.

**Actions:**
1. Create `tests/drivers/vasp/test_vasp_bands_parser.py` with these test functions:

   **`test_parse_eigenval_header`** — Parse header correctly:
   - `n_electrons == 8` (Si, 2 atoms × 4 valence)
   - `n_kpoints == 200` (5 segments × 40 points)
   - `n_bands == 16` (as set in INCAR NBANDS=16)
   - `system_name` contains "Si diamond"

   **`test_parse_eigenval_shapes`** — Array shapes:
   - `kpoints.shape == (200, 3)`
   - `eigenvalues.shape == (200, 16)`
   - `occupations.shape == (200, 16)`
   - `weights.shape == (200,)`

   **`test_parse_eigenval_physics`** — Physical plausibility:
   - First k-point is G (0, 0, 0)
   - First band energy at G: approximately -10.07 eV (deep Si 3s)
   - Bands 1-4 have occupation ~1.0 at G (8 electrons → 4 doubly-occupied bands)
   - Bands 5+ have occupation ~0.0 at G (conduction bands)
   - All energies in reasonable range: -15 eV to +10 eV

   **`test_can_parse_true_when_eigenval_exists`** — `VASPBandsProvider.can_parse()` returns True

   **`test_can_parse_false_when_no_eigenval`** — Returns False for empty dir

   **`test_parse_returns_band_structure`** — Full provider parse:
   - Returns `BandStructure` instance
   - `meta.object_type == "bands"`
   - `meta.engine_name == "vasp"`
   - `len(k_distances) == 200`
   - `eigenvalues.shape == (200, 16)`

   **`test_k_distance_monotonic`** — k-distances are non-decreasing (with resets at segment boundaries allowed if k-path wraps)

   **`test_kpoints_labels_from_real_kpoints`** — KPOINTS label extraction:
   - Labels include G, X, W, K, L (the 5 high-symmetry points in our path)
   - Labels are in correct order: G, X, W, K, G, L
   - k-distances at labels are at segment boundaries

   **`test_to_primitives_valid`** — Canonical bundle roundtrip:
   - `band_structure.to_primitives()` returns `CanonicalPrimitiveBundle`
   - Bundle has `render_meta`, `provenance_meta`, and data arrays
   - `compute_canonical_sha(bundle)` returns deterministic 64-char hex string

   **`test_fermi_energy_extraction`** — If vasprun.xml or OUTCAR snippet is present in fixture dir, Fermi energy is extracted and matches expected value

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/drivers/vasp/test_vasp_bands_parser.py -v --tb=short
# Expected: all pass, using real VASP data from tests/data/analysis_vasp_bands/
```

### Step V5: Wire VASP Bands Through Full Pipeline Test

**Problem:** Need to verify VASP bands works end-to-end through the universal analysis pipeline (not just unit-test the parser).

**Actions:**
1. Create `tests/api/test_vasp_bands_pipeline.py`:
   - Similar structure to `_analysis_pipeline_test_utils.py` but for VASP
   - Set up a project with one VASP `bandspw` step
   - Copy EIGENVAL + KPOINTS from `tests/data/analysis_vasp_bands/` into raw dir
   - Call `_finalize_run_analysis_pipeline()`
   - Assert:
     - SQLite `analysis_snapshots` has 1 row for `object_type="bands"`
     - CAS blob exists
     - `get_analysis(run_ulid, "bands")` returns valid bundle
     - Bundle has correct k_distances, eigenvalues, high_symmetry_points
     - `get_analysis_snapshot(run_ulid, "bands")` returns same canonical_sha
   - This test does NOT require VASP installed — it uses committed fixtures

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/api/test_vasp_bands_pipeline.py -v --tb=short
```

### Step V6: Create VASP Si Bands Demo

**Problem:** No VASP bands demo exists in `resources/demo_projects/`.

**Reference:** The real run that produced our test fixtures used these parameters (from `.tmp/engine_research/vasp/real_run/si_bands/INCAR`):
```
ENCUT = 300, ICHARG = 11, ISMEAR = 0, SIGMA = 0.05, NBANDS = 16, LORBIT = 11, PREC = Accurate
```

**Actions:**
1. Create `resources/demo_projects/si_bands_vasp_demo.yml`:
   - Structure: Si diamond, 2 atoms (same lattice as QE demo: a=5.431 A)
   - Steps: SCF (vasp_scf) → Bands (vasp_bandspw)
   - VASP only needs 2 steps (no NSCF, no post-processing like QE)
   - SCF step: ENCUT=300, ISMEAR=0, SIGMA=0.05, PREC=Accurate, 8×8×8 k-mesh
   - Bands step: ICHARG=11 (read CHGCAR), LORBIT=11, NBANDS=16, Line-mode KPOINTS (G→X→W→K→G→L, 40 pts/segment)
   - Pseudo directory: `.qmatsuite/engines/vasp/potpaw_PBE.64/` (reference, user must have VASP license)
   - Species: Si (POTCAR from potpaw_PBE.64/Si/)
2. Add demo metadata with `recommended_analysis: bands`
3. Model the YAML structure after the existing `si_bands_demo.yml` (QE version) for consistency

**Verification:**
```bash
source .venv/bin/activate && python -c "
import yaml
from pathlib import Path
demo = yaml.safe_load(Path('resources/demo_projects/si_bands_vasp_demo.yml').read_text())
steps = demo['calculations'][0]['steps']
specs = [s['step_type_spec'] for s in steps]
assert 'vasp_scf' in specs, f'Missing vasp_scf: {specs}'
assert 'vasp_bandspw' in specs, f'Missing vasp_bandspw: {specs}'
print(f'OK: VASP bands demo has steps {specs}')
"
```

### Step V7: VASP Golden Daemon Test (Requires VASP Installed)

**Problem:** Need a daemon-level test that actually runs VASP for bands, analogous to the QE golden test (D1).

**VASP is available locally:** `.qmatsuite/engines/vasp/vasp.6.5.0/bin/vasp_std` (and vasp_gam, vasp_ncl). Pseudopotentials at `.qmatsuite/engines/vasp/potpaw_PBE.64/`.

**Actions:**
1. Create `tests/daemon/test_vasp_bands_golden_daemon.py`
2. Mark with `pytest.mark.vasp_core` (new marker — requires VASP installed)
3. Initialize project from `si_bands_vasp_demo.yml` (created in V6)
4. Run the 2-step VASP workflow (SCF → bands) via daemon + JobManager
5. After run completes, assert on new pipeline endpoints:
   - `get_step_digest(run_ulid, step_ulid)` returns `available: True` for both steps
   - `get_analysis(run_ulid, "bands")` returns bundle with 16 bands and k-path labels
   - `get_analysis_snapshot(run_ulid, "bands")` returns same `canonical_sha` as eager write
   - `list_raw_files()` includes `EIGENVAL`, `KPOINTS`, `OUTCAR`, `vasprun.xml`
   - SQLite `analysis_snapshots` has 1 row with `object_type="bands"`
   - CAS blob exists at `.provenance/.cas/analysis/<sha>.json.gz`
   - Bundle eigenvalues match Si physics (indirect gap, 4 occupied bands)
6. Add `vasp_core` marker to `pytest.ini` or `pyproject.toml`
7. This test proves the **universal analysis pipeline works with a second engine** — the most important validation of engine-agnosticism

**Verification:**
```bash
# Run on this machine (VASP 6.5.0 installed):
source .venv/bin/activate && python -m pytest tests/daemon/test_vasp_bands_golden_daemon.py -v --tb=short -m vasp_core
```

---

## Execution Order and Dependencies

```
Section 1 (Gap Closure):
  G1 → G2  (independent of everything else)

Section 2 (QE Golden Test):
  D1 → D2  (D1 can run in parallel with Section 1)

Section 3 (Legacy Removal):
  L1 → L2 → L3 → L4 → L5 → L6
  (MUST wait until D1 is done — golden test proves new pipeline works before deleting legacy)

Section 4 (VASP Bands):
  V1 → V2 → V3 → V4 → V5 → V6 → V7
  (V1–V5 can run in parallel with Section 3)
  (V6–V7 should run after L4 to avoid legacy interference)
```

**Recommended execution sequence:**
1. G1, G2, D1, D2 (gap closure + golden QE test)
2. V1, V2, V3, V4, V5 (VASP parser + pipeline test)
3. L1, L2, L3, L4, L5, L6 (legacy removal)
4. V6, V7 (VASP demo + golden daemon test)

**Verification after all steps:**
```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
# Expected: all pass, zero legacy analysis imports in runtime code
```

---

## Progress Log

_To be filled by executor as each step completes._

| Step | Status | Tests After | Notes |
|------|--------|-------------|-------|
| G1 | DONE | PASS | Deleted `src/quantumvitas/analysis/dos.py` and removed exports; `grep -r "from quantumvitas.analysis.dos" src/ tests/` -> `OK: no imports`. |
| G2 | DONE | PASS | Added `tests/api/test_analysis_staleness.py`; `source .venv/bin/activate && python -m pytest tests/api/test_analysis_staleness.py -v --tb=short` passed. |
| D1 | DONE | PASS | Added `tests/daemon/test_si_bands_golden_daemon.py`; `source .venv/bin/activate && python -m pytest tests/daemon/test_si_bands_golden_daemon.py -v --tb=short -m qe_core` passed. |
| D2 | DONE | PASS | Legacy daemon test was later removed in L4; verification command reported `N/A: file deleted in L4` (superseded). |
| V1 | DONE | PASS | Added real fixtures under `tests/data/analysis_vasp_bands/`; `ls ...`, `wc -l .../EIGENVAL`=`3606`, `head -6 ... | tail -1`=`8 200 16`. |
| V2 | DONE | PASS | Added `src/quantumvitas/drivers/vasp/parsers/bands.py` and parser wiring; parser registration check command printed `OK: VASP bands parser registered`. |
| V3 | DONE | PASS | Added VASP `ANALYSIS_CAPABILITIES` in `src/quantumvitas/drivers/vasp/driver.py`; `source .venv/bin/activate && python -m pytest tests/gates/test_analysis_invariants.py::test_analysis_capability_declaration -v --tb=short` passed. |
| V4 | DONE | PASS | Added `tests/drivers/vasp/test_vasp_bands_parser.py`; `source .venv/bin/activate && python -m pytest tests/drivers/vasp/test_vasp_bands_parser.py -v --tb=short` passed (10 tests). |
| V5 | DONE | PASS | Added `tests/api/test_vasp_bands_pipeline.py`; `source .venv/bin/activate && python -m pytest tests/api/test_vasp_bands_pipeline.py -v --tb=short` passed. |
| L1 | DONE | PASS | Removed legacy analysis methods/imports from `src/quantumvitas/api/service.py`; `grep -c "from quantumvitas.analysis.artifacts" ...`=`0`, `grep -c "AnalysisType" ...`=`0`. |
| L2 | DONE | PASS | Removed legacy daemon handlers in `src/quantumvitas/daemon/server.py`; `grep -c "ensure_calculation_analysis\\|get_scf_convergence\\|get_dos_data\\|get_band_structure_data" ...`=`0`. |
| L3 | DONE | PASS | Deleted `src/quantumvitas/analysis/artifacts.py` and exports; `test ! -f src/quantumvitas/analysis/artifacts.py && echo "OK: deleted"` -> `OK: deleted`. |
| L4 | IN PROGRESS | PENDING | Legacy tests updated/removed (including `tests/daemon/test_si_bands_calculation_daemon.py`); awaiting final mandated full-suite parallel run. |
| L5 | DONE | PASS | Updated contract crawler fixtures/introspection; `source .venv/bin/activate && python -m pytest tests/contract_crawler/ -v --tb=short` passed (`340 passed, 18 skipped`). |
| L6 | DONE | PASS | Added gate in `tests/gates/test_analysis_invariants.py`; `source .venv/bin/activate && python -m pytest tests/gates/test_analysis_invariants.py::test_no_legacy_analysis_artifact_imports -v --tb=short` passed. |
| V6 | DONE | PASS | Added `resources/demo_projects/si_bands_vasp_demo.yml`; YAML verification command printed `OK: VASP bands demo has steps ['vasp_scf', 'vasp_bandspw']`. |
| V7 | DONE | PASS | Added `tests/daemon/test_vasp_bands_golden_daemon.py`; `source .venv/bin/activate && python -m pytest tests/daemon/test_vasp_bands_golden_daemon.py -v --tb=short -m vasp_core` passed. |
| L4 (completion) | DONE | PASS | Fixed remaining schema/import-gate fallout: added `pseudo_sha256` + `pseudo_sha_family` to `resources/demo_projects/si_bands_vasp_demo.yml`, switched `src/quantumvitas/cli/main.py` `analyze band/dos` handlers to API-only imports, added API utility wrappers in `src/quantumvitas/api/utils.py`; `source .venv/bin/activate && python -m pytest tests/unit/test_demo_schema_validation.py tests/gates/test_import_rules.py tests/gates/test_import_gate.py -v --tb=short -n auto --dist=loadfile` passed (`116 passed, 2 skipped`). |
| FINAL | DONE | PASS | Mandated full-suite verification run completed with parallel mode: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` -> `4584 passed, 19 skipped` (includes `tests/daemon/test_si_bands_golden_daemon.py` and `tests/daemon/test_vasp_bands_golden_daemon.py`). |
