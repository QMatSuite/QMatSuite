# Fatbands + PDOS Final Closeout Plan

## Context

The multi-engine bands/DOS expansion is complete (4745 tests, 6 engines wired). The remaining gaps are:
- **QE**: no fatbands (k-resolved orbital projections on band structure)
- **ABINIT**: no PDOS (l-projected DOS per atom)
- Five engines lack fatbands — each needs a concrete verdict (DONE or NOT SUPPORTED)

This plan permanently closes EVERY cell in the bands/dos/pdos/fatbands matrix. No "defer" remains.

**Object type taxonomy (FIXED):** bands / dos / convergence / trajectory / field3d — NO additions.
**Fatbands = bands with `projections != None`. PDOS = dos with `pdos != None`.** No new object_types.

---

## Final Engine x Feature Matrix

| Engine | Bands | DOS | PDOS | Fatbands | Action |
|--------|-------|-----|------|----------|--------|
| **VASP** | DONE | DONE | DONE | DONE | — |
| **QE** | DONE | DONE | DONE | **NEW** | Parse `*.projwfc_up` |
| **ABINIT** | DONE | DONE | **NEW** | NOT SUPPORTED | Parse `*_DOS_AT*` |
| **Siesta** | DONE | DONE | DONE | NOT SUPPORTED | — |
| **CP2K** | DONE | DONE | DONE | NOT SUPPORTED | — |
| **GPAW** | DONE | DONE | NOT SUPPORTED | NOT SUPPORTED | — |

### NOT SUPPORTED — Concrete Technical Justifications

| Engine | Feature | Reason |
|--------|---------|--------|
| **ABINIT** | fatbands | K-resolved projections stored in `FATBANDS.nc` (NetCDF binary). Text `_DOS_AT` files are energy-resolved only (k-summed). Parsing NetCDF requires `netCDF4` or `h5py` dependency not in project. |
| **Siesta** | fatbands | Requires `fat` post-processing utility on `.WFSX` binary files, which need special input flags (`COOP.Write` / `WFS.Write.For.Bands`). Not part of standard Siesta output. |
| **CP2K** | fatbands | No native k-resolved projection output. `.bs` file contains eigenvalues only. No per-k-point PDOS option in CP2K. |
| **GPAW** | PDOS | No standalone PDOS output file. Projections only via Python API (`calc.get_projections()`). Would require embedding projection computation in calculation scripts — a script-generation concern, not a parser concern. |
| **GPAW** | fatbands | Same as PDOS — k-resolved projections only via `KPoint.P_ani` attribute in Python runtime. No serialized output file to parse. |

### Not Applicable (molecular / classical / QMC)
ORCA, Gaussian, Psi4, PySCF, xTB, LAMMPS, QMCPACK, Wannier90, Yambo — no periodic band structure / DOS.

---

## Existing Infrastructure to Reuse

| Component | Path | Reuse |
|-----------|------|-------|
| VASP PROCAR parser (fatbands TEMPLATE) | `drivers/vasp/parsers/bands.py:parse_procar()` | Pattern for QE projwfc_up parser |
| VASP PDOS parser (PDOS TEMPLATE) | `drivers/vasp/parsers/dos.py` | Pattern for ABINIT _DOS_AT parser |
| QE bands provider | `drivers/qe/parsers/bands.py:QEBandsProvider` | Add projections integration |
| QE DOS provider (has PDOS) | `drivers/qe/parsers/dos.py:QEDOSProvider` | Already done — parses `*.pdos_atm*` |
| ABINIT DOS provider | `drivers/abinit/parsers/dos.py:ABINITDOSProvider` | Add _DOS_AT parsing |
| BandStructure model | `core/analysis/band_structure/model.py` | projections (4D), projection_labels fields |
| DOS model | `core/analysis/dos/model.py` | pdos (3D), atom_labels, orbital_labels fields |

---

## Section 1: Opus Foundation Work

Two deliverables: **QE fatbands** + **ABINIT PDOS**. Plus golden recipe docs.

### Step F1: Generate QE Fatbands Fixture

Run projwfc.x on a Si NSCF bands calculation to get k-resolved orbital projections.

**Workflow:**
1. pw.x SCF for Si (using Si_r.upf from QE PP library)
2. pw.x NSCF `calculation='bands'` along standard FCC k-path (L-G-X-W-K)
3. projwfc.x with `filproj='si_bands'` on the NSCF output

**projwfc.x input:**
```
&PROJWFC
  prefix = 'si'
  outdir = './tmp'
  filproj = 'si_bands'
/
```

**Key output:** `si_bands.projwfc_up` — text file with per-k-point, per-band projection weights.

**projwfc_up file format** (from QE source + web research):
```
     1     1    Si   1    s    0.500   (header per atomic wfc)
     ...
     k =   0.0000  0.0000  0.0000
 ==== e(   1) =    -5.744 eV ====
     0.49723    0.00000    ...     (projection weights per atomic wfc)
 ==== e(   2) =     6.255 eV ====
     ...
```

Each k-point block lists bands with projection weights onto each atomic wavefunction (squared: |<psi_nk|phi_i>|^2).

**Fixture destination:** `tests/data/analysis_bands/si_bands.projwfc_up` (alongside existing `si.bands.dat.gnu`)

### Step F2: QE Fatbands Parser

**File:** `src/quantumvitas/drivers/qe/parsers/bands.py` (EDIT existing)

Add `_parse_projwfc_up(path: Path) -> dict` function:
- Parse header: atomic wfc definitions (atom index, symbol, orbital label)
- Parse per-k-point blocks: `k = ...` header, then per-band `==== e(N) = ... ====` with projection rows
- Return: `{projections: ndarray(n_kpoints, n_bands, n_atoms, n_orbitals), orbital_labels: list[str], atom_labels: list[str]}`
- Group atomic wavefunctions by atom: sum m-components per l to get per-(atom, l) projections

**Pattern:** Follow `parse_procar()` in `drivers/vasp/parsers/bands.py` (lines 27-113).

Modify `QEBandsProvider.parse()`:
- After parsing bands, look for `*.projwfc_up` files in candidate dirs
- If found, call `_parse_projwfc_up()`
- Verify dimensions match eigenvalues (n_kpoints, n_bands)
- Populate `BandStructure(projections=..., projection_labels=...)`
- Add `SourceFileStat` for projwfc_up file
- Handle dimension mismatch gracefully (warning, skip projections)

### Step F3: Generate ABINIT PDOS Fixture

Run ABINIT with `prtdos 3` for Si to generate per-atom l-resolved DOS files.

**Workflow:**
1. Copy existing Si SCF input, add: `prtdos 3`, `natsph 2`, `iatsph 1 2`, `ratsph 2*2.0`
2. Run ABINIT → generates `*_DOS_AT0001`, `*_DOS_AT0002` files

**ABINIT _DOS_AT file format** (from ABINIT docs):
```
# energy(Ha)  l=0   l=1   l=2   l=3   l=4   (integral=>)  l=0   l=1   l=2   l=3   l=4
  -0.5000  0.0000  0.0000  0.0000  0.0000  0.0000  0.0000  0.0000  0.0000  0.0000  0.0000
```
- Column 1: energy in Hartree
- Columns 2-6: DOS per l-channel (l=0 through l=4), units states/Ha
- Columns 7-11: integrated DOS per l-channel

**Fixture destination:** `tests/data/analysis_abinit_dos/` (add to existing directory alongside `*_DOS`)

### Step F4: ABINIT PDOS Parser

**File:** `src/quantumvitas/drivers/abinit/parsers/dos.py` (EDIT existing)

Add `_parse_abinit_pdos_at(path: Path) -> dict` function:
- Parse `_DOS_AT####` file: skip `#` comments, parse data columns
- Column 1 = energy (Hartree) → convert to eV (* 27.211386245988)
- Columns 2-6 = DOS for l=0..4 (states/Hartree) → convert to states/eV (/ 27.211386245988)
- Return: `{energies_eV: array, projections: array(nedos, 5), integrated: array(nedos, 5)}`

Modify `ABINITDOSProvider.parse()`:
- After parsing total DOS, glob for `*_DOS_AT*` files in raw_dir
- If found, parse each per-atom file with `_parse_abinit_pdos_at()`
- Build `pdos` array: shape (n_atoms, nedos, n_orbitals) where n_orbitals = number of non-zero l channels
- Build `atom_labels`: extract atom index from filename (`_DOS_AT0001` → "atom_1"), or read from `.abi`/`.abo` for real species
- Build `orbital_labels`: `["s", "p", "d", "f", "g"]` (truncate to max non-zero l)
- Populate `DOS(pdos=..., atom_labels=..., orbital_labels=...)`

### Step F5: Golden Recipe Documentation

Write golden example recipes to `docs/engines/` for future demo use.

**Create `docs/engines/qe/RECIPE_FATBANDS.md`:**
- Complete 3-step recipe: pw.x SCF → pw.x NSCF bands → projwfc.x with filproj
- Input files for each step
- Expected output files and their formats
- How to interpret projwfc_up data

**Create `docs/engines/abinit/RECIPE_PDOS.md`:**
- Complete recipe: ABINIT with prtdos=3 + natsph/iatsph/ratsph
- Input file with key variables annotated
- Expected output _DOS_AT file format
- How to interpret l-projected DOS

**Create `docs/engines/qe/RECIPE_PDOS.md`:**
- Complete recipe: pw.x SCF → projwfc.x with filpdos
- Input files, expected `*.pdos_atm*` output files
- How to interpret orbital-projected DOS

---

## Section 2: Cursor Auto Mechanical Tasks

> **Instructions for Cursor Auto:** The steps below should be implemented by Cursor Auto.
> They depend on the Opus foundation work (Section 1) being complete first.
> All fixture files, parser implementations, and model changes will already be in place.
> Your job is to write the tests that exercise the parsers.

### Step M1: QE Fatbands Tests

**File:** `tests/drivers/qe/test_qe_bands_provider.py` (EDIT existing)

Add tests (follow `test_vasp_bands_parser.py` projection tests pattern):
- `test_projections_populated_when_projwfc_up_exists` — `bs.projections is not None`
- `test_projections_shape` — shape = (n_kpoints, n_bands, n_atoms, n_orbitals)
- `test_projection_labels_atoms` — atom_labels like ["Si_1", "Si_2"]
- `test_projection_labels_orbitals` — orbital_labels like ["s", "p"]
- `test_projections_values_reasonable` — all values in [0, 1], sum per band ~1
- `test_to_primitives_has_projections` — `bundle.arrays["projections"]` exists
- `test_to_primitives_fatband_hint` — `render_meta.extra["fatband_display_hint"] == "width"`

**Fixture setup:** Copy `tests/data/analysis_bands/si_bands.projwfc_up` (created in Step F1) into raw_dir alongside `si.bands.dat.gnu` and `si.3_bands.pp.out`.

**Helper update:** Modify `_prepare_provider_raw_dir()` or create a new `_prepare_provider_raw_dir_with_projwfc()` that also copies the projwfc_up fixture.

### Step M2: ABINIT PDOS Tests

**File:** `tests/drivers/abinit/test_abinit_dos_parser.py` (EDIT existing)

Add tests:
- `test_pdos_populated_when_dos_at_exists` — `dos.pdos is not None`
- `test_pdos_shape` — shape = (n_atoms, nedos, n_orbitals)
- `test_pdos_atom_labels` — labels present, correct count
- `test_pdos_orbital_labels` — subset of ["s", "p", "d", "f", "g"]
- `test_pdos_energies_in_eV` — values in reasonable eV range (not Hartree)
- `test_pdos_values_non_negative` — all pdos values >= 0
- `test_to_primitives_has_pdos` — `bundle.arrays["pdos"]` exists

**Fixture:** The `_DOS_AT0001`, `_DOS_AT0002` files in `tests/data/analysis_abinit_dos/` (created in Step F3) will be auto-discovered by `ABINITDOSProvider` because the existing `FIXTURE_DIR` already points there.

---

## Section 3: Opus Acceptance

### Step A1: Final Matrix Gate Test

**File:** `tests/gates/test_analysis_invariants.py` (EDIT)

Add comprehensive closeout gate:
```python
# Fatbands support gate
@pytest.mark.parametrize("engine", ["vasp", "qe"])
def test_fatbands_parser_populates_projections(engine):
    """Gate: engines with fatband support produce projections in BandStructure."""
    ...  # parse fixture, assert bs.projections is not None

# PDOS support gate
@pytest.mark.parametrize("engine", ["vasp", "qe", "siesta", "cp2k"])
def test_pdos_parser_populates_pdos(engine):
    """Gate: engines with PDOS support produce pdos in DOS."""
    ...  # parse fixture, assert dos.pdos is not None

# NOT SUPPORTED documentation gate
def test_final_matrix_documented():
    """Gate: acceptance doc exists with all cells closed."""
    from pathlib import Path
    doc = Path("docs/architecture/worklogs/MULTI_ENGINE_FATBANDS_PDOS_CLOSEOUT_ACCEPTANCE.md")
    assert doc.exists()
```

### Step A2: Full Test Suite

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

Baseline: 4745 passed. Expected delta: ~+15-20 tests. Final: ~4760+ passed, 0 failed, ~20 skipped.

### Step A3: Write Acceptance Doc

**File:** `docs/architecture/worklogs/MULTI_ENGINE_FATBANDS_PDOS_CLOSEOUT_ACCEPTANCE.md`

Contents:
- Final engine x feature matrix (ALL cells DONE or NOT SUPPORTED)
- NOT SUPPORTED justifications (copied from plan)
- Test count delta
- Files created/edited
- Verification commands

### Step A4: Save Plan

Copy this plan to `docs/architecture/worklogs/MULTI_ENGINE_BANDS_DOS_FATBANDS_PHASE4_CLOSEOUT_PLAN.md`

---

## Dependency Graph

```
F1 (QE fatbands fixture) ──→ F2 (QE fatbands parser) ──→ M1 (QE fatbands tests)
F3 (ABINIT PDOS fixture) ──→ F4 (ABINIT PDOS parser) ──→ M2 (ABINIT PDOS tests)
F5 (golden recipe docs)  ────────────────────────────────────┐
                                                              │
A1 (gate tests) ←── needs F2 + F4 + M1 + M2 ────────────────┘
A2 (full suite) ←── needs A1
A3 (acceptance) ←── needs A2
A4 (plan doc)   ←── parallel with A3
```

F1/F3/F5 can run in parallel. F2/F4 can run in parallel after their fixtures.

---

## Critical Files Summary

| File | Action | Owner |
|------|--------|-------|
| `src/quantumvitas/drivers/qe/parsers/bands.py` | EDIT: add `_parse_projwfc_up()` + projections integration | **Opus** |
| `src/quantumvitas/drivers/abinit/parsers/dos.py` | EDIT: add `_parse_abinit_pdos_at()` + PDOS integration | **Opus** |
| `tests/data/analysis_bands/si_bands.projwfc_up` | CREATE: QE fatbands fixture (from real projwfc.x run) | **Opus** |
| `tests/data/analysis_abinit_dos/*_DOS_AT*` | CREATE: ABINIT PDOS fixtures (from real ABINIT run) | **Opus** |
| `tests/drivers/qe/test_qe_bands_provider.py` | EDIT: add fatbands tests | **Cursor Auto** |
| `tests/drivers/abinit/test_abinit_dos_parser.py` | EDIT: add PDOS tests | **Cursor Auto** |
| `tests/gates/test_analysis_invariants.py` | EDIT: add fatbands/PDOS gate tests | **Opus** |
| `docs/engines/qe/RECIPE_FATBANDS.md` | CREATE: golden fatbands recipe | **Opus** |
| `docs/engines/qe/RECIPE_PDOS.md` | CREATE: golden PDOS recipe | **Opus** |
| `docs/engines/abinit/RECIPE_PDOS.md` | CREATE: golden PDOS recipe | **Opus** |
| `docs/architecture/worklogs/MULTI_ENGINE_FATBANDS_PDOS_CLOSEOUT_ACCEPTANCE.md` | CREATE: acceptance | **Opus** |
| `docs/architecture/worklogs/MULTI_ENGINE_BANDS_DOS_FATBANDS_PHASE4_CLOSEOUT_PLAN.md` | CREATE: plan copy | **Opus** |

## Verification

```bash
# Run all tests
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# Verify QE fatbands
python -c "
import quantumvitas.drivers
from quantumvitas.parsers.registry import _PARSERS
from pathlib import Path
from quantumvitas.core.analysis.evidence import EvidenceBundle
p = _PARSERS[('qe','bands')]()
d = Path('tests/data/analysis_bands')
print('can_parse:', p.can_parse(d))
print('has projwfc_up:', bool(list(d.glob('*.projwfc_up'))))
"

# Verify ABINIT PDOS
python -c "
import quantumvitas.drivers
from quantumvitas.parsers.registry import _PARSERS
from pathlib import Path
p = _PARSERS[('abinit','dos')]()
d = Path('tests/data/analysis_abinit_dos')
print('can_parse:', p.can_parse(d))
print('has DOS_AT:', bool(list(d.glob('*_DOS_AT*'))))
"
```
