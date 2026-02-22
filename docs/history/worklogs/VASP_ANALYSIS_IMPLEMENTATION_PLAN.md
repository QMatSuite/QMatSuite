# VASP Analysis Implementation Plan

**Author:** Claude Opus 4.6 (senior architect role)
**Date:** 2026-02-09
**Design doc:** `docs/architecture/design/VASP_ANALYSIS_DESIGN.md` v2.1 FINAL
**Prerequisite reading:** `ANALYSIS_OBJECT_PRIMITIVES_SPEC.md`, `ANALYSIS_PIPELINE_PLAYBOOK.md`

---

## Execution Notes

**Always activate the project venv before running anything:**
```bash
source .venv/bin/activate
```

**Full test suite — ALWAYS use parallel execution:**
```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**For single-file or targeted tests:**
```bash
source .venv/bin/activate && python -m pytest tests/drivers/vasp/test_vasp_bands_parser.py -v --tb=short
```

---

## Section 1: Foundation Work (DONE)

This section covers the k-distance fix and design doc finalization. Both are complete.

### 1.1 Design Doc Finalization (DONE)

`docs/architecture/design/VASP_ANALYSIS_DESIGN.md` updated from DRAFT v2.0 → v2.1 FINAL with:

- Header status change
- Wannier90 MLWF field3d infrastructure citations in §2.5 (marchingCubes.ts 875 lines, volumeCoordinates.ts 110 lines, volumeIndexing.ts 80 lines, VolumeViewerSandbox.tsx 1053 lines)
- Pattern constraint: VASP field3d MUST produce VolumeMetadata + BlobStore blobs identical to XSF/BXSF pipeline; GUI code is NOT engine-aware
- PARCHG added to field3d discovery list (§2.5, §8, Appendix A)
- EvidenceBundle sharpened as explicit design choice in §4.2
- Cubic-cell invariant note in §2.1.1 (fix does not change distances for cubic cells, only scale factor)

### 1.2 K-Distance Fix (DONE)

**Problem:** `_compute_k_distances()` and `_read_kpoints_labels()` used fractional Euclidean distance, which is incorrect for non-cubic cells because it ignores the metric tensor of reciprocal space.

**Fix applied in** `src/qmatsuite/drivers/vasp/parsers/bands.py`:

1. New helper `_reciprocal_lattice(lattice)` computes `B = 2π * inv(A)^T`
2. `_compute_k_distances(kpoints, lattice)` transforms `dk_frac @ recip` to Cartesian reciprocal space before computing Euclidean norm
3. `_read_kpoints_labels(raw_dir, lattice)` uses `recip.T @ delta_frac` for segment distances
4. `VASPBandsProvider.parse()` reads POSCAR from `candidate_dirs`, extracts lattice matrix, passes to both functions
5. POSCAR added to `source_files` tracking
6. Warning emitted if no POSCAR found (fallback to fractional Euclidean)

**New import:** `from qmatsuite.drivers.vasp.io.poscar import parse_poscar_text`

**Why existing tests survive:**
- Si fixture has cubic POSCAR (a=5.4309 Å). For cubic cells, reciprocal Cartesian = `(2π/a) × fractional Euclidean` — only scale changes, not shape
- `test_k_distance_monotonic` checks `diffs >= -1e-10` — still passes (monotonicity preserved)
- `test_kpoints_labels_from_real_kpoints` calls `_read_kpoints_labels(FIXTURE_DIR)` without lattice — defaults to `None`, uses fractional distances — label names and sort order unaffected
- `test_to_primitives_valid` SHA test compares two calls (deterministic) — SHA changes but both calls produce same value
- Golden daemon test checks `len=200` + monotonicity + label presence — no absolute k_distance values asserted

### 1.3 Regression Tests (DONE)

4 new tests in `tests/drivers/vasp/test_vasp_bands_parser.py`:

| Test | What it verifies |
|------|-----------------|
| `test_reciprocal_lattice_cubic` | B = 2π/a * I for cubic lattice |
| `test_k_distances_cubic_vs_fractional` | Cartesian = scale × fractional for cubic |
| `test_k_distances_noncubic_differs_from_fractional` | Hexagonal BN lattice: ratios vary per segment (anisotropic metric) + analytical Gamma→M distance |
| `test_k_distances_with_poscar_in_fixture` | Si fixture: k_distances[39] matches analytical Gamma→X = (2π/a)√0.5 |

**Result:** 14/14 passed (10 existing + 4 new)

---

## Section 2: Phase 1 — EvidenceBundle + DOS Provider

### 2.1 EvidenceBundle Refactor

**Goal:** Replace the 6-kwarg `parse()` signature with a typed `EvidenceBundle` dataclass.

**Files to create/modify:**

| File | Action |
|------|--------|
| `src/qmatsuite/core/analysis/evidence.py` | **CREATE** — `EvidenceBundle` dataclass |
| `src/qmatsuite/core/analysis/orchestrator.py` | **MODIFY** — build `EvidenceBundle` instead of kwargs dict |
| `src/qmatsuite/drivers/vasp/parsers/bands.py` | **MODIFY** — `parse(evidence: EvidenceBundle)` |
| `src/qmatsuite/drivers/qe/parsers/bands.py` | **MODIFY** — `parse(evidence: EvidenceBundle)` |
| `tests/drivers/vasp/test_vasp_bands_parser.py` | **MODIFY** — update `parse()` calls |
| `tests/drivers/qe/test_qe_bands_parser.py` | **MODIFY** — update `parse()` calls |

**EvidenceBundle schema:**
```python
@dataclass
class EvidenceBundle:
    primary_raw_dir: Path
    calc_dir: Path
    run_ulid: str
    calc_ulid: str
    step_ulids: list[str]
    gen_steps: list[str]
    engine_name: str
    evidence_steps: list[EvidenceStep]  # always present, may be empty
```

**Migration approach:** Clean break (no backward compat). Only 2 providers exist (VASP bands, QE bands). Update both simultaneously.

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/drivers/vasp/test_vasp_bands_parser.py tests/drivers/qe/ -v --tb=short
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### 2.2 DOS Model

**File to create:** `src/qmatsuite/core/analysis/dos/model.py`

**DOS dataclass fields:**
- `meta: AnalysisObjectMeta`
- `energies: np.ndarray` — shape `(nedos,)`, eV
- `total_dos: np.ndarray` — shape `(nedos,)` or `(2, nedos)` for spin
- `fermi_energy: float | None`
- `integrated_dos: np.ndarray | None`
- `pdos: np.ndarray | None` — shape `(n_atoms, nedos, n_orbitals)`
- `atom_labels: list[str] | None`
- `orbital_labels: list[str] | None`
- `spin_polarized: bool`

**Must implement** `to_primitives() -> CanonicalPrimitiveBundle` following the schema in design doc §2.2.

### 2.3 DOSCAR Parser

**File to create:** `src/qmatsuite/drivers/vasp/parsers/dos.py`

**Class:** `VASPDOSProvider` with `@register_parser("vasp", "dos")`

**Parsing strategy** (from design doc §4.5):
1. Parse header (lines 1-6) → NEDOS, EFERMI
2. Read total DOS block (NEDOS lines) → auto-detect spin from column count (3=non-spin, 5=spin)
3. If more data follows: read per-atom PDOS blocks → auto-detect orbital decomposition from column count
4. Support LORBIT=10 (spd) and LORBIT=11 (full lm)

**Capability registration** in `drivers/vasp/driver.py`:
```python
AnalysisCapability(
    object_type="dos",
    gen_step_sequence=["dos"],
    evidence_files=["DOSCAR"],
)
```

### 2.4 DOS Test Fixtures

**Directory:** `tests/data/analysis_vasp_dos/`

Required files:
- `DOSCAR` — Si total DOS (non-spin, NEDOS=301)
- `DOSCAR_spin` — Fe spin-polarized DOS
- `DOSCAR_pdos` — TiO2 with LORBIT=11
- `vasprun.xml` — minimal (efermi only)

**Test file:** `tests/drivers/vasp/test_vasp_dos_parser.py`

Key assertions:
- NEDOS count matches header
- Energy range spans Fermi level
- Spin channels shape `(2, nedos)` for spin-polarized
- PDOS shape `(n_atoms, nedos, n_orbitals)` for LORBIT=11
- `to_primitives()` produces valid `CanonicalPrimitiveBundle`

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/drivers/vasp/test_vasp_dos_parser.py -v --tb=short
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Section 3: Phase 2 — Convergence, Trajectory, field3d

### 3.1 Convergence Provider

**Files:**
| File | Action |
|------|--------|
| `src/qmatsuite/core/analysis/convergence/model.py` | **CREATE** — `Convergence` dataclass + `to_primitives()` |
| `src/qmatsuite/drivers/vasp/parsers/convergence.py` | **CREATE** — `VASPConvergenceProvider` + `parse_oszicar()` |
| `tests/data/analysis_vasp_convergence/` | **CREATE** — OSZICAR fixtures (scf, relax, md) |
| `tests/drivers/vasp/test_vasp_convergence_parser.py` | **CREATE** — unit tests |

**OSZICAR parsing** (from design doc §4.6):
- Electronic steps: lines starting with `CG :`, `DAV:`, or `RMM:` → extract energy, dE
- Ionic summary: lines with `F=` → extract F, E0
- MD variant: lines with `T=`, `EK=` → extract temperature, kinetic energy
- Build flat SCF arrays + ionic-step arrays

**Capability:** `AnalysisCapability(object_type="convergence", gen_step_sequence=["scf"], evidence_files=["OSZICAR"])`

**Key test assertions:** SCF step count > 5, energy generally decreasing, ionic step count matches, converged flag.

### 3.2 Trajectory Provider

**Files:**
| File | Action |
|------|--------|
| `src/qmatsuite/drivers/vasp/parsers/trajectory.py` | **CREATE** — `VASPTrajectoryProvider` |
| `tests/data/analysis_vasp_trajectory/` | **CREATE** — vasprun.xml + XDATCAR fixtures |
| `tests/drivers/vasp/test_vasp_trajectory_parser.py` | **CREATE** — unit tests |

**No new model needed** — `core/analysis/trajectory/` already exists with `Frame` dataclass.

**Primary path:** vasprun.xml streaming with `iterparse()` + element clearing (from design doc §4.7):
```python
for event, elem in ET.iterparse(path, events=("end",)):
    if elem.tag == "calculation":
        # Extract structure, forces, stress, energy
        elem.clear()
```

**Fallback path:** XDATCAR (positions) + OSZICAR (energies) for when vasprun.xml is missing or too large.

**Two capabilities:**
- `AnalysisCapability(object_type="trajectory", gen_step_sequence=["relax"], evidence_files=["vasprun.xml"])`
- `AnalysisCapability(object_type="trajectory", gen_step_sequence=["md"], evidence_files=["vasprun.xml"])`

**Key test assertions:** Frame count >= 3, position shape `(n_atoms, 3)`, energy per frame, forces shape if available.

### 3.3 field3d Provider

**Files:**
| File | Action |
|------|--------|
| `src/qmatsuite/drivers/vasp/parsers/field3d.py` | **CREATE** — `VASPField3DProvider` + `parse_chgcar_text()` |
| `tests/data/analysis_vasp_field3d/` | **CREATE** — small CHGCAR + LOCPOT fixtures |
| `tests/drivers/vasp/test_vasp_field3d_parser.py` | **CREATE** — unit tests |

**No new model needed** — reuses `VolumeMetadata` from `analysis/volume_artifacts.py`.

**CHGCAR parsing** (from design doc §4.8):
1. Parse POSCAR header → lattice vectors, species
2. Read `NGX NGY NGZ` grid dimensions
3. Read `NGX*NGY*NGZ` floats → flat array → reshape with FORTRAN (i-fastest) ordering
4. For CHGCAR: detect blank separator → parse augmentation charges separately
5. Compute `VolumeMetadata`: grid_shape, origin=[0,0,0], grid_vectors from lattice
6. Write full grid to BlobStore as `.f32`, preview via `downsample_grid(factor=4)`

**Discovery:** Single capability registered. Provider discovers which files exist (CHGCAR, LOCPOT, ELFCAR, PARCHG) at parse time. Produces one bundle per discovered file.

**Capability:** `AnalysisCapability(object_type="field3d", gen_step_sequence=["scf"], evidence_files=["CHGCAR"])`

**Key test assertions:**
- Grid shape matches NGX/NGY/NGZ
- `data_order` is `FORTRAN_I_FASTEST`
- `blob_id` registered in BlobStore
- Preview grid dimensions = full / downsample_factor
- Augmentation charges separated from valence (CHGCAR only)
- LOCPOT → `field_kind = "potential"` (no augmentation section)

**Existing code to reuse (NOT re-implement):**
- `volume_artifacts.py` — `VolumeMetadata` dataclass (99 lines)
- `volume_parsers.py` — `downsample_grid()` (from 641-line module)
- `blob_store.py` — `.f32` storage (207 lines)
- GUI files: marchingCubes.ts, volumeCoordinates.ts, volumeIndexing.ts, VolumeViewerSandbox.tsx

### 3.4 Gate Test Extension

**File to modify:** `tests/gates/test_analysis_invariants.py`

Add gate test verifying VASP driver declares capabilities for all 5 object_types:
```python
def test_vasp_analysis_capabilities_cover_five_types():
    from qmatsuite.drivers.vasp.driver import VASPDriver
    driver = VASPDriver()
    object_types = {cap.object_type for cap in driver.ANALYSIS_CAPABILITIES}
    assert {"bands", "dos", "convergence", "trajectory", "field3d"}.issubset(object_types)
```

### 3.5 Verification

After all sections complete:
```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

Expected: all existing tests pass + new tests for DOS, convergence, trajectory, field3d.

---

## Summary: Implementation Order

| Phase | What | Deps | Key Files |
|-------|------|------|-----------|
| Foundation (DONE) | Design doc v2.1, k-distance fix | None | bands.py, VASP_ANALYSIS_DESIGN.md |
| Phase 1 | EvidenceBundle + DOS | Foundation | evidence.py, orchestrator.py, dos.py |
| Phase 2a | Convergence | Phase 1 | convergence.py, OSZICAR parser |
| Phase 2b | Trajectory | Phase 1 | trajectory.py, vasprun.xml streaming |
| Phase 2c | field3d | Phase 1 | field3d.py, CHGCAR parser, BlobStore |
| Gate | 5-type coverage gate test | Phase 2 | test_analysis_invariants.py |

---

## Progress Log

### Phase 1: EvidenceBundle Refactor (COMPLETED ✓)

**Date:** 2026-02-09

**Completed tasks:**
- ✓ Created `src/qmatsuite/core/analysis/evidence.py` with `EvidenceBundle` dataclass
- ✓ Modified `src/qmatsuite/core/analysis/orchestrator.py` to build and pass `EvidenceBundle`
- ✓ Updated `src/qmatsuite/drivers/vasp/parsers/bands.py` to accept `EvidenceBundle`
- ✓ Updated `src/qmatsuite/drivers/qe/parsers/bands.py` to accept `EvidenceBundle`
- ✓ Updated all test files to use `EvidenceBundle`

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/drivers/vasp/test_vasp_bands_parser.py tests/drivers/qe/test_qe_bands_provider.py -v --tb=short
```
**Result:** 20/20 passed ✓

### Phase 1: DOS Provider (COMPLETED ✓)

**Date:** 2026-02-09

**Completed tasks:**
- ✓ Created `src/qmatsuite/core/analysis/dos/model.py` with `DOS` dataclass and `to_primitives()`
- ✓ Created `src/qmatsuite/core/analysis/dos/__init__.py`
- ✓ Created `src/qmatsuite/drivers/vasp/parsers/dos.py` with `VASPDOSProvider`
- ✓ Registered DOS capability in `src/qmatsuite/drivers/vasp/driver.py`
- ✓ Generated real VASP fixtures using `scripts/generate_vasp_dos_fixtures.py`:
  - `tests/data/analysis_vasp_dos/DOSCAR` (Si non-spin, NEDOS=301)
  - `tests/data/analysis_vasp_dos/DOSCAR_spin` (Fe spin-polarized, NEDOS=301)
  - `tests/data/analysis_vasp_dos/DOSCAR_pdos` (TiO2 with LORBIT=11, NEDOS=301)
  - `tests/data/analysis_vasp_dos/vasprun.xml` (minimal, for efermi)
  - `tests/data/analysis_vasp_dos/README.md` (documentation)
- ✓ Created `tests/drivers/vasp/test_vasp_dos_parser.py` with 8 test cases

**Verification:**
```bash
source .venv/bin/activate && python -m pytest tests/drivers/vasp/test_vasp_dos_parser.py -v --tb=short
```
**Result:** 8/8 passed ✓

**Test coverage:**
- NEDOS count matches header
- Energy range spans Fermi level
- Spin-polarized DOS shape (2, nedos)
- PDOS shape (n_atoms, nedos, n_orbitals) for LORBIT=11
- `to_primitives()` produces valid `CanonicalPrimitiveBundle`
- Deterministic SHA computation

### Phase 2: Fix Failures + Convergence + Trajectory + field3d (COMPLETED ✓)

**Date:** 2026-02-09

**Step 0: Fix 4 test failures + missing import (COMPLETED ✓)**
- ✓ Added `Sequence` to `from typing import` in `drivers/vasp/parsers/bands.py`
- ✓ Updated `SuccessfulBandsProvider.parse()` and `FailingProvider.parse()` to accept `EvidenceBundle` in `tests/core/analysis/test_orchestrator.py`
- ✓ Updated `provider.parse()` call to use `EvidenceBundle` in `tests/core/analysis/test_qe_bands_e2e.py`
- ✓ Fixed `_Provider.parse()` in `tests/gates/test_analysis_invariants.py`

**Step 1: Convergence Model + VASP Provider (COMPLETED ✓)**
- ✓ Created `src/qmatsuite/core/analysis/convergence/__init__.py` and `model.py`
  - Engine-agnostic `Convergence` dataclass: SCF steps, ionic steps, algorithm, converged flag
  - `to_primitives()` produces `Series1D` for SCF energy, SCF dE, ionic energy, and ionic max force
- ✓ Created `src/qmatsuite/drivers/vasp/parsers/convergence.py` with `VASPConvergenceProvider`
  - OSZICAR parser: DAV/CG/RMM electronic lines, F= ionic lines, T= MD lines
  - VASP Fortran float regex: `[-+]?\d*\.\d+E[+-]\d+` (handles `-.10586221E+02`)
- ✓ Created fixtures: `tests/data/analysis_vasp_convergence/OSZICAR` (3 ionic steps, 21 SCF) + `OSZICAR_md`
- ✓ Created `tests/drivers/vasp/test_vasp_convergence_parser.py` (10 tests)

**Step 2: Trajectory Provider (COMPLETED ✓)**
- ✓ Created `src/qmatsuite/drivers/vasp/parsers/trajectory.py` with `VASPTrajectoryProvider`
  - Primary: vasprun.xml full parse (species, positions, forces, stress, energy per calculation)
  - Fallback: XDATCAR (positions) + OSZICAR (energies)
  - Reuses existing `Trajectory` + `Frame` from `core/analysis/trajectory/model.py`
- ✓ Created fixtures: `tests/data/analysis_vasp_trajectory/vasprun.xml` (3 ionic steps, 2-atom Si), `XDATCAR`, `OSZICAR`
- ✓ Created `tests/drivers/vasp/test_vasp_trajectory_parser.py` (11 tests, including fallback path)

**Step 3: field3d Provider (COMPLETED ✓)**
- ✓ Created `src/qmatsuite/drivers/vasp/parsers/field3d.py` with `VASPField3DProvider` + `Field3D` class
  - Parses CHGCAR/LOCPOT/ELFCAR/PARCHG format (POSCAR header + grid + values)
  - `Field3D.to_primitives()` produces volume_metadata, preview via factor-4 downsampling
  - Discovery: detects all volumetric files, parses primary (CHGCAR > LOCPOT > ELFCAR > PARCHG)
- ✓ Created fixtures: `tests/data/analysis_vasp_field3d/CHGCAR` (2-atom Si, 4x4x4 grid) + `LOCPOT`
- ✓ Created `tests/drivers/vasp/test_vasp_field3d_parser.py` (11 tests)

**Step 4: Wiring + Gate Test (COMPLETED ✓)**
- ✓ Updated `src/qmatsuite/drivers/vasp/parsers/__init__.py` — all 6 providers registered
- ✓ Updated `src/qmatsuite/drivers/vasp/driver.py` — 8 capabilities (bands, dos, convergence×3, trajectory×2, field3d)
- ✓ Added `test_vasp_analysis_capabilities_cover_five_types()` gate test
- ✓ Updated `tests/daemon/test_vasp_bands_golden_daemon.py` — analysis_snapshots now expects multiple rows

**Final verification:**
```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```
**Result:** 4630 passed, 0 failed, 19 skipped ✓ (+37 new tests vs pre-Phase 2)
