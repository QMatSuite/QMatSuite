# GPAW Engine Exploration Report

**Date**: 2026-02-03
**GPAW Version**: 25.7.0
**ASE Version**: 3.27.0
**Python**: 3.14.2

---

## 1. Installation Verification

GPAW v25.7.0 is installed in the project `.venv`. PAW setup data (559 setup files) are bundled in `gpaw_data` package at:
```
.venv/lib/python3.14/site-packages/gpaw_data/setups/
```

Setup files follow the pattern `{Element}.{XC}.gz` (e.g., `Si.PBE.gz`, `Fe.LDA.gz`) plus LCAO basis files `{Element}.dzp.basis.gz`.

Smoke test verified: H2 molecule energy calculation in FD mode returned -5.8485 eV.

---

## 2. What GPAW Is

GPAW (Grid-based Projector Augmented Wave) is a density-functional theory Python code based on the PAW method. Key characteristics:

- **Python-native**: Unlike QE/VASP/CP2K, GPAW does not use text input files. "Input" is a Python script that sets up ASE Atoms + GPAW calculator and calls ASE methods.
- **Three wave-function modes**: FD (finite-difference real-space grid), PW (plane-wave), LCAO (linear combination of atomic orbitals).
- **Deep ASE integration**: Structure, optimizer, MD integrator, analysis tools all come from ASE.
- **Output**: Binary `.gpw` restart files (ULM format), `.txt` text logs, ASE `.traj` trajectory files, `.json` band structure files.

### 2.1 Calculation Types

| Capability | Status | GPAW Method |
|-----------|--------|-------------|
| SCF ground state | Full | `atoms.get_potential_energy()` |
| Band structure | Full | `calc.fixed_density(kpts={path:...})` |
| DOS | Full | `ase.dft.dos.DOS(calc)` |
| Geometry relaxation | Full | `ase.optimize.BFGS(atoms)` |
| Cell relaxation | Full (PW only) | `FrechetCellFilter` + optimizer |
| Molecular dynamics | Full | ASE dynamics (NVE, NVT, NPT) |
| TDDFT | Full | `gpaw.tddft`, `gpaw.lrtddft` |
| GW (G0W0) | Full (PW only) | `gpaw.response.g0w0.G0W0` |
| Optical response | Full | `gpaw.response.df.DielectricFunction` |
| Hybrid functionals | Yes (PW) | PBE0, HSE06, B3LYP |
| Spin-orbit coupling | Yes | `soc=True` |

### 2.2 Key Parameters

| Parameter | Purpose | Values |
|-----------|---------|--------|
| `mode` | Wave function representation | `PW(ecut)`, `'fd'`, `'lcao'` |
| `xc` | Exchange-correlation | `'LDA'`, `'PBE'`, `'RPBE'`, `'HSE06'`, ... |
| `kpts` | K-point grid | `(n1,n2,n3)`, `{'path':'GXWK','npoints':60}`, `{'density':6.0}` |
| `h` | Grid spacing (FD/LCAO) | Angstrom (default 0.2) |
| `nbands` | Number of bands | int (negative = N extra beyond occupied) |
| `convergence` | Convergence criteria | `{'energy': 0.0005, 'density': 1e-4, ...}` |
| `occupations` | Smearing | `FermiDirac(width)`, `MethfesselPaxton(width, n)` |
| `basis` | LCAO basis set | `'szp'`, `'dzp'`, `'tzdp'` |
| `setups` | PAW setups | `'paw'` (default), `'sg15'` |
| `spinpol` | Spin polarization | `True`/`False`/`None` (auto) |
| `parallel` | Parallelization | `{'domain': n, 'band': n, 'kpt': n}` |
| `txt` | Log file | filename or `None` |

---

## 3. Real Calculations Performed

### 3.1 Calc 1: Si Bulk SCF (Single-Step Topology)

**Setup**: Si diamond, a=5.43 Ang, PW(300), PBE, 4x4x4 k-points

**Results**:
- Total energy: **-10.787154 eV** (extrapolated)
- Fermi level: **5.596 eV**
- Band gap: **1.180 eV** (indirect)
- Direct gap: **2.745 eV**
- Converged in **13 SCF iterations**
- Runtime: **~2 seconds** (serial)
- Memory: **128.86 MiB**

**Output files produced**:
| File | Size | Content |
|------|------|---------|
| `scf.txt` | 12 KB | Full SCF log with convergence, energies, timing |
| `si_scf.gpw` | 180 KB | Restart file (density only) |
| `si_scf_wf.gpw` | 2.1 MB | Restart file (with wave functions) |
| `results.json` | 1 KB | Structured results (written by script) |

### 3.2 Calc 2: Si SCF → Bands → DOS (Multi-Step Topology)

**Step 1: Ground State SCF**
- PW(300), PBE, 6x6x6 k-points, 108 irreducible k-points
- Energy: **-10.790148 eV**
- Output: `gs.txt`, `gs.gpw`, `gs_wf.gpw`

**Step 2: Band Structure (fixed density)**
- `GPAW('gs.gpw').fixed_density(kpts={'path':'GXWKL', 'npoints':60})`
- 60 k-points along GXWKL path, 16 bands
- Band gap: **0.570 eV** (indirect), **2.558 eV** (direct)
- Output: `bands.txt`, `bands.gpw`, `bandstructure.json`

**Step 3: DOS**
- `DOS(calc, npts=500, width=0.1)` from ground state
- Energy range: [-12.68, 9.38] eV, integral = 16.0 (correct: 8 valence electrons * 2 spin)
- Output: `dos.json`

**Key observation**: Step chaining is done via:
1. `calc.write('gs.gpw')` — save ground state
2. `GPAW('gs.gpw').fixed_density(...)` — reload and compute bands with frozen density
3. `DOS(calc)` — compute DOS from reloaded calculator

This is different from QE/VASP where separate executable calls chain through files. GPAW chains through the Python API and `.gpw` restart files.

### 3.3 Calc 3: H2O Molecule Relaxation

**Setup**: H2O molecule, FD mode (h=0.25), PBE, no PBC

**Results**:
- Final energy: **-14.948 eV**
- 34 BFGS optimization steps (coarse grid caused slow convergence)
- Output: `relax.txt` (108 KB), `relax.traj` (25 KB), `opt.log`, `h2o_relaxed.gpw`, `opt_history.json`

**Key observation**: Relaxation is fully handled by ASE optimizers (BFGS, LBFGS, FIRE). GPAW only provides forces. The trajectory file (`.traj`) stores all optimization steps and is an ASE ULM format binary.

---

## 4. File System & Artifacts

### 4.1 Files GPAW Reads

| File Type | Format | Purpose | Location |
|-----------|--------|---------|----------|
| PAW setups | `*.PBE.gz` etc. | PAW data | `GPAW_SETUP_PATH` or package data |
| LCAO basis | `*.dzp.basis.gz` | Basis sets | Same as setups |
| Restart `.gpw` | Binary ULM | Previous calculation state | Working directory |
| Structure files | Various (via ASE) | Input geometry | Via ASE `read()` |

### 4.2 Files GPAW Writes

| File | Format | Content | How Created |
|------|--------|---------|-------------|
| `.txt` | Plain text | SCF log, energies, convergence, timing | `txt='file.txt'` parameter |
| `.gpw` | Binary ULM | Density, potential, optionally wave functions | `calc.write('file.gpw')` |
| `.traj` | ASE trajectory (ULM) | Optimization/MD trajectory | ASE optimizer `trajectory=` |
| `.json` | JSON | Band structure data | `bs.write('bs.json')` |
| `results.json` | JSON | Structured results | Generated by our script |

### 4.3 `.gpw` File Details

The `.gpw` restart file contains:
- Atoms (cell, numbers, positions, pbc)
- Density (atomic density matrices, electron density array)
- Hamiltonian (energy components, potential)
- Parameters (mode, xc, kpts, convergence)
- Wave functions (if `mode='all'`): eigenvalues, occupations, projections, coefficients
- Results: dipole, energy, forces

Two write modes:
- `calc.write('file.gpw')` — density + parameters (compact, ~180 KB for Si)
- `calc.write('file.gpw', mode='all')` — includes wave functions (~2.1 MB for Si)

### 4.4 Important: No Traditional Input Files

GPAW has no `*.in`, `INCAR`, `&CONTROL` sections, or XML input. The "input" is a Python script. This is the single most important architectural distinction from all other engines in QMatSuite.

**Implications for integration**:
- The "input writer" generates a Python script, not a parameter file
- The "runner" executes `python script.py` (or `gpaw python script.py` for MPI)
- Results are extracted either programmatically (load `.gpw`) or by parsing `results.json` that the script itself writes

---

## 5. Parsing Approach

### 5.1 Primary: Programmatic (via .gpw file)

```python
from gpaw import GPAW
calc = GPAW('output.gpw', txt=None)
energy = calc.get_atoms().get_potential_energy()
forces = calc.get_atoms().get_forces()
fermi = calc.get_fermi_level()
eigenvalues = calc.get_eigenvalues(kpt=0, spin=0)
```

This requires GPAW to be installed.

### 5.2 Secondary: JSON Results File

The generated Python script writes a `results.json` with structured data:
```json
{
  "total_energy_eV": -10.787154,
  "fermi_level_eV": 5.596,
  "forces_eV_per_ang": [[...], [...]],
  "n_bands": 8,
  "n_spins": 1,
  "converged": true
}
```

This requires no GPAW installation to parse and is the recommended approach for the engine handler.

### 5.3 Tertiary: Text Log Parsing (Fallback)

The `.txt` log can be parsed with regex for:
- Convergence status (`"Converged after N iterations"`)
- Total energy (`"Extrapolated: X.XXXXXX"`)
- Fermi level (`"Fermi level: X.XXXXX"`)
- Band gap (`"Gap: X.XXX eV"`)
- Forces (`"Forces in eV/Ang:"` section)
- SCF iterations (iter table)

Text parser was tested and works reliably.

### 5.4 Band Structure: `bandstructure.json`

ASE's `BandStructure.write()` produces a JSON with:
- `path.labelseq`: K-path labels (e.g., "GXWKL")
- `path.kpts`: K-point coordinates
- `energies.__ndarray__`: [shape, dtype, data] format
- `reference`: Fermi level

### 5.5 DOS: `dos.json`

Our script writes:
- `energies_eV`: array of energies
- `dos`: array of DOS values
- `fermi_eV`: Fermi level

---

## 6. Step Topology & Chaining Mechanism

### 6.1 Single-Step: SCF

Just `atoms.get_potential_energy()`. One script, one execution.

### 6.2 Multi-Step: SCF → Bands

1. SCF script writes `gs.gpw`
2. Bands script loads `gs.gpw`, calls `fixed_density()`, writes `bandstructure.json`

Chaining is via `.gpw` file on disk. The key function is `calc.fixed_density(**kwargs)` which creates a new calculator with frozen electron density.

### 6.3 Multi-Step: SCF → DOS

1. SCF script writes `gs.gpw`
2. DOS script loads `gs.gpw`, creates `DOS(calc)` object, extracts data

### 6.4 Relax

Single script with ASE optimizer loop. Each BFGS step calls `atoms.get_forces()` which triggers a full SCF. Trajectory stored in `.traj`.

### 6.5 How This Maps to QMatSuite Steps

| QMatSuite GEN Step | GPAW Implementation | Dependency |
|---|---|---|
| `scf` | Run SCF, write `.gpw` | None |
| `nscf` | `fixed_density()` from `.gpw` | Depends on SCF `.gpw` |
| `bands`/`bandspw` | `fixed_density(kpts={path:...})` from `.gpw` | Depends on SCF `.gpw` |
| `dos` | `DOS(calc)` from `.gpw` | Depends on SCF `.gpw` |
| `relax` | ASE optimizer loop | None (standalone) |
| `md` | ASE dynamics loop | None (standalone) or from `.gpw` |

---

## 7. Comparison with Existing QMatSuite Engines

### 7.1 GPAW vs PySCF (Most Similar)

Both are Python-native, no external executable. Key differences:

| Aspect | PySCF | GPAW |
|--------|-------|------|
| Domain | Molecular QC | Periodic DFT + Molecular |
| Input | Python script | Python script |
| Chaining | In-memory `mf` object | `.gpw` file on disk |
| Optimizer | PySCF geometric_optimizer | ASE BFGS/LBFGS/FIRE |
| Step topology | SCF → post-SCF chain | SCF → fixed_density() |
| Restart | `.chk` checkpoint | `.gpw` restart |
| Handler type | Strong-chain (replay from SCF) | Can be per-step or chain |

### 7.2 GPAW vs QE (Most Feature-Similar)

Both do periodic DFT with band structure, DOS, etc. Key differences:

| Aspect | QE | GPAW |
|--------|-----|------|
| Input | Text `.in` files (Fortran namelists) | Python scripts |
| Executable | `pw.x`, `bands.x`, `dos.x`, etc. | `python script.py` |
| Chaining | Shared outdir with wfc/charge files | `.gpw` restart files |
| Modes | PW only | PW, FD, LCAO |
| Recipe | Directory-state (shared outdir) | Either: per-step isolated or shared |
| K-path | Manual specification | ASE auto band path |

---

## 8. Architectural Decision: Recipe Archetype

### 8.1 Analysis

GPAW can fit either:

**Option A: Directory-State (QE-like)**
- Steps share working directory
- `.gpw` files accumulate in shared dir
- Bands/DOS read SCF `.gpw` from same directory
- Simple, natural for GPAW's chaining via files

**Option B: Strong-Chain (PySCF-like)**
- One job per subchain
- Re-executes from SCF for each post-SCF step
- Isolated namespace folders
- More overhead but cleaner isolation

**Option C: Isolated per-step (VASP-like)**
- Each step in its own directory
- Copy `.gpw` from SCF step to downstream steps
- Most isolated but requires explicit artifact staging

### 8.2 Recommendation: Directory-State (Option A)

GPAW's natural execution model is:
1. Run SCF, write `.gpw` to current directory
2. Run bands/DOS script in same directory, reads `.gpw`

This maps directly to the QE-like directory-state recipe:
- One job per step
- Shared working directory (`calc/raw/`)
- `.gpw` files serve as shared artifacts (like QE's outdir)
- Sequential execution order

**WorkdirPolicy**: `SHARED`

This avoids unnecessary copying of `.gpw` files between step directories.

---

## 9. PAW Setups (Asset Management)

GPAW uses PAW setups bundled with the `gpaw-data` package. Unlike QE pseudopotentials:
- Setups are NOT per-project — they are installed system-wide
- Selection is automatic based on element + XC functional
- No `species_map` or `pseudo_dir` needed
- The setup path is auto-discovered from the package

**Implication**: GPAW does NOT need an engine assets map in `calculation.yaml`. The `gpaw_data` package handles setup discovery internally. This simplifies integration.

---

## 10. Utility Scripts Produced

Located in `/scratchpad/gpaw_utils/`:

### 10.1 `gpaw_input_writer.py`
- Generates GPAW Python calculation scripts from parameters
- Handles SCF, bands, DOS, and relax step types
- Supports restart-from chaining for bands/DOS
- Tested: generates valid scripts for all step types

### 10.2 `gpaw_output_parser.py`
- Programmatic parser (via `.gpw` file + GPAW API)
- Text log parser (fallback, no GPAW dependency)
- JSON parsers for `results.json`, `bandstructure.json`, `dos.json`
- All parsers tested against real calculation artifacts — 7/7 tests pass

### Test Artifacts

Located in `/scratchpad/gpaw_test_resources/`:
- `calc1_si_scf/`: Si SCF ground state (scf.txt, si_scf.gpw, results.json)
- `calc2_si_bands/`: Si SCF+Bands+DOS multi-step (gs.txt, bands.txt, bandstructure.json, dos.json, gs.gpw)
- `calc3_relax/`: H2O relaxation (relax.txt, relax.traj, opt_history.json, h2o_relaxed.gpw)

---

## 11. Known Issues & Caveats

1. **numpy RuntimeWarning**: GPAW v25.7.0 produces harmless matmul warnings on Python 3.14 due to floating point edge cases in setup initialization. These don't affect results.

2. **numpy API**: numpy 1.26.4 uses `np.trapz` not `np.trapezoid` (renamed in 2.0). Scripts must use the older API.

3. **MPI execution**: Serial execution works. MPI execution requires `gpaw python script.py` wrapper or `mpirun python script.py`. The driver should support both serial and MPI modes.

4. **Stress tensor**: Only available in PW mode. FD and LCAO modes cannot compute stress, so cell relaxation requires PW mode.

5. **Mode-specific limitations**: FD mode has no stress tensor; LCAO mode has limited basis set convergence; PW mode requires explicit cutoff.

---

## End of Exploration Report
