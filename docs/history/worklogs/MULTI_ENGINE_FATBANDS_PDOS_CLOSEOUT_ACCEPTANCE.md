# Multi-Engine Fatbands + PDOS Closeout Acceptance

## Final Engine x Feature Matrix

| Engine | Bands | DOS | PDOS | Fatbands | Status |
|--------|-------|-----|------|----------|--------|
| **VASP** | DONE | DONE | DONE | DONE | Complete |
| **QE** | DONE | DONE | DONE | DONE | Complete |
| **ABINIT** | DONE | DONE | DONE | NOT SUPPORTED | Complete |
| **Siesta** | DONE | DONE | DONE | NOT SUPPORTED | Complete |
| **CP2K** | DONE | DONE | DONE | NOT SUPPORTED | Complete |
| **GPAW** | DONE | DONE | NOT SUPPORTED | NOT SUPPORTED | Complete |

### Not Applicable (molecular / classical / QMC)
ORCA, Gaussian, Psi4, PySCF, xTB, LAMMPS, QMCPACK, Wannier90, Yambo -- no periodic band structure / DOS.

**ALL cells DONE or NOT SUPPORTED. No "defer" remains.**

---

## NOT SUPPORTED -- Concrete Technical Justifications

| Engine | Feature | Reason |
|--------|---------|--------|
| **ABINIT** | fatbands | K-resolved projections stored in `FATBANDS.nc` (NetCDF binary). Text `_DOS_AT` files are energy-resolved only (k-summed). Parsing NetCDF requires `netCDF4` or `h5py` dependency not in project. |
| **Siesta** | fatbands | Requires `fat` post-processing utility on `.WFSX` binary files, which need special input flags (`COOP.Write` / `WFS.Write.For.Bands`). Not part of standard Siesta output. |
| **CP2K** | fatbands | No native k-resolved projection output. `.bs` file contains eigenvalues only. No per-k-point PDOS option in CP2K. |
| **GPAW** | PDOS | No standalone PDOS output file. Projections only via Python API (`calc.get_projections()`). |
| **GPAW** | fatbands | K-resolved projections only via `KPoint.P_ani` attribute in Python runtime. No serialized output file to parse. |

---

## What Was Implemented

### QE Fatbands (NEW)
- **Parser**: `src/qmatsuite/drivers/qe/parsers/bands.py`
  - Added `parse_projwfc_up()` function to parse QE `filproj` output
  - Parses atomic wfc headers (atom index, element, n, l, m)
  - Groups projections by (atom, l) with m-components summed
  - Returns projections shape: (n_kpoints, n_bands, n_atoms, n_orbitals)
  - Integrated into `QEBandsProvider.parse()` with dimension validation
- **Fixture**: `tests/data/analysis_bands/si_bands.projwfc_up` (41 k-points, 8 bands, 2 atoms, 2 orbitals)
  - Generated from real QE 7.5 projwfc.x run on Si diamond
  - Matching bands: `si_fatbands.bands.dat.gnu`, `si_fatbands.bands.pp.out`, `si_fatbands.nscf.out`

### ABINIT PDOS (NEW)
- **Parser**: `src/qmatsuite/drivers/abinit/parsers/dos.py`
  - Added `_parse_abinit_pdos_at()` for `_DOS_AT` files (l-projected per-atom DOS)
  - Converts energy from Hartree to eV, DOS from states/Hartree to states/eV
  - Integrated into `ABINITDOSProvider.parse()` with grid consistency check
  - Prefers `_DOS` over `_DOS_TOTAL` for backward compatibility
  - Graceful grid mismatch handling (warns and skips PDOS)
- **Fixture**: `tests/data/analysis_abinit_pdos/` (2 atoms, 1801 energies, 5 l-channels)
  - Generated from real ABINIT 10.4.7 run with prtdos=3
  - Contains `_DOS_TOTAL`, `_DOS_AT0001`, `_DOS_AT0002`, `.abo`

---

## Files Created/Modified

| File | Action |
|------|--------|
| `src/qmatsuite/drivers/qe/parsers/bands.py` | MODIFIED: added `parse_projwfc_up()`, projections integration |
| `src/qmatsuite/drivers/abinit/parsers/dos.py` | MODIFIED: added `_parse_abinit_pdos_at()`, PDOS integration |
| `tests/data/analysis_bands/si_bands.projwfc_up` | CREATED: QE fatbands fixture |
| `tests/data/analysis_bands/si_fatbands.bands.dat.gnu` | CREATED: matching bands fixture |
| `tests/data/analysis_bands/si_fatbands.bands.pp.out` | CREATED: matching symmetry fixture |
| `tests/data/analysis_bands/si_fatbands.nscf.out` | CREATED: matching NSCF fixture |
| `tests/data/analysis_abinit_pdos/si_pdoso_DS2_DOS_TOTAL` | CREATED: ABINIT total DOS |
| `tests/data/analysis_abinit_pdos/si_pdoso_DS2_DOS_AT0001` | CREATED: ABINIT atom 1 PDOS |
| `tests/data/analysis_abinit_pdos/si_pdoso_DS2_DOS_AT0002` | CREATED: ABINIT atom 2 PDOS |
| `tests/data/analysis_abinit_pdos/si_pdos.abo` | CREATED: ABINIT output for Fermi energy |
| `tests/data/analysis_abinit_dos/si_pdoso_DS2_DOS_AT0001` | CREATED: PDOS in mixed fixture dir |
| `tests/data/analysis_abinit_dos/si_pdoso_DS2_DOS_AT0002` | CREATED: PDOS in mixed fixture dir |
| `tests/data/analysis_abinit_dos/si_pdoso_DS2_DOS_TOTAL` | CREATED: total DOS in mixed dir |
| `tests/drivers/qe/test_qe_bands_provider.py` | MODIFIED: added 7 fatbands tests |
| `tests/drivers/abinit/test_abinit_dos_parser.py` | MODIFIED: added 7 PDOS tests |
| `tests/gates/test_analysis_invariants.py` | MODIFIED: added 3 closeout gate tests |
| `docs/engines/qe/RECIPE_FATBANDS.md` | CREATED: golden fatbands recipe |
| `docs/engines/qe/RECIPE_PDOS.md` | CREATED: golden PDOS recipe |
| `docs/engines/abinit/RECIPE_PDOS.md` | CREATED: golden PDOS recipe |
| `docs/architecture/worklogs/MULTI_ENGINE_BANDS_DOS_FATBANDS_PHASE4_CLOSEOUT_PLAN.md` | CREATED: plan |

---

## Verification Commands

```bash
# Full test suite
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# QE fatbands only
python -m pytest tests/drivers/qe/test_qe_bands_provider.py -v -k "projections or fatband"

# ABINIT PDOS only
python -m pytest tests/drivers/abinit/test_abinit_dos_parser.py -v -k "pdos"

# Gate tests
python -m pytest tests/gates/test_analysis_invariants.py -v -k "fatband or pdos or matrix"
```
