# Psi4 Engine Exploration Report

**Date**: 2026-02-03
**Psi4 Version**: 1.10 (conda, miniforge)
**System**: macOS Darwin 25.2.0, ARM64

---

## 1. Installation & Availability

Psi4 1.10 is installed via conda at `/opt/homebrew/Caskroom/miniforge/base/bin/psi4`. It is importable as a Python module (`import psi4`) and executable as a CLI binary.

**Smoke test**: HF/STO-3G water energy = -74.9630 Hartree (correct reference).

---

## 2. Psi4 Architecture Overview

### 2.1 Execution Model

Psi4 is fundamentally a **Python-native** quantum chemistry package. Unlike QE/VASP (Fortran executables with text input) or ORCA (binary with text input), Psi4's primary interface is Python:

- **PsiAPI mode** (preferred): `import psi4; psi4.energy('scf/cc-pvdz')` — runs entirely in-process
- **Psithon mode** (legacy): `psi4 input.dat` — text input file with Python-like syntax
- **Subprocess mode**: `python script.py` — Python script that imports psi4

### 2.2 Key Python API Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| `psi4.energy(method)` | Single-point energy | `(energy, wfn)` |
| `psi4.optimize(method)` | Geometry optimization | `(energy, wfn)` |
| `psi4.frequency(method)` | Vibrational frequencies | `(energy, wfn)` |
| `psi4.gradient(method)` | Energy gradient | `(gradient, wfn)` |
| `psi4.properties(method)` | One-electron properties | `(energy, wfn)` |
| `tdscf_excitations(wfn)` | TDDFT excited states | `list[dict]` |

All functions accept `return_wfn=True` to return a wavefunction object, and `ref_wfn=wfn` to reuse a prior wavefunction.

### 2.3 Variable System

Psi4 stores all computed quantities as named variables accessible via:
- `psi4.core.variable("SCF TOTAL ENERGY")` — single variable
- `psi4.core.variables()` — dict of all variables

Key variables by calculation type:

**SCF**: `SCF TOTAL ENERGY`, `HF TOTAL ENERGY`, `NUCLEAR REPULSION ENERGY`, `ONE-ELECTRON ENERGY`, `TWO-ELECTRON ENERGY`, `SCF ITERATIONS`, `SCF DIPOLE`

**MP2**: `MP2 TOTAL ENERGY`, `MP2 CORRELATION ENERGY`, `MP2 SAME-SPIN CORRELATION ENERGY`, `MP2 OPPOSITE-SPIN CORRELATION ENERGY`, `SCS-MP2 TOTAL ENERGY`

**CCSD**: `CCSD TOTAL ENERGY`, `CCSD CORRELATION ENERGY`, `(T) CORRECTION ENERGY`, `CCSD(T) TOTAL ENERGY`

**Frequency**: `ZPVE`, `THERMAL ENERGY CORRECTION`, `ENTHALPY CORRECTION`, `GIBBS FREE ENERGY CORRECTION`

**TDDFT**: Returned as list of dicts with `EXCITATION ENERGY`, `LENGTH-GAUGE OSCILLATOR STRENGTH (LIN)`, `LENGTH-GAUGE ELECTRIC DIPOLE TRANSITION MOMENT`

### 2.4 Methods Supported

| Category | Methods |
|----------|---------|
| **SCF** | HF (RHF, UHF, ROHF), DFT (LDA, GGA, hybrid, meta-GGA, double-hybrid, LRC) |
| **DFT Functionals** | B3LYP, PBE, PBE0, BLYP, BP86, M06-2X, ωB97X-D, B2PLYP, CAM-B3LYP, ... |
| **Perturbation Theory** | MP2, MP2.5, MP3 (all DF or conventional) |
| **Coupled Cluster** | CCSD, CCSD(T), CC2, CC3, DLPNO-CCSD(T) |
| **Multi-Reference** | CASSCF, CASCI, Mk-MRCCSD, MRPT |
| **Excited States** | TDDFT/TDA (RPA), EOM-CCSD, ADC |
| **SAPT** | SAPT0, SAPT2, SAPT2+ |
| **Orbital-Optimized** | OMP2, OMP3, OLCCD |

### 2.5 Basis Sets

All standard basis sets supported via Psi4's built-in library:
- Pople: 6-31G, 6-31G*, 6-311++G**
- Dunning: cc-pVDZ, cc-pVTZ, cc-pVQZ, aug-cc-pVDZ, ...
- Ahlrichs: def2-SVP, def2-TZVP, def2-QZVP
- Auxiliary: DF fitting bases auto-matched

### 2.6 Molecular Focus

Psi4 is a **molecular** (non-periodic) code. It does NOT support:
- Periodic boundary conditions (PBC)
- Crystal/slab/surface calculations
- Plane-wave basis sets
- Pseudopotentials

This is important for QMatSuite integration — Psi4 is for **molecular systems only**, like PySCF and ORCA.

---

## 3. Calculation Experiments

### 3.1 Calculation 1: SCF → MP2 Chain (Water, HF/cc-pVDZ)

**Topology**: SCF → post-SCF chain (2 steps sharing reference wavefunction)

**Results**:
- SCF energy: -76.0267427160 Hartree (12 iterations)
- MP2 total: -76.2307325266 Hartree
- MP2 correlation: -0.2040 Hartree
- Wavefunction reuse: ✅ `ref_wfn=scf_wfn` works correctly

**Artifacts produced**:
- `scf_mp2_output.dat` (11 KB) — text output with full detail
- `scf_wfn.npy` (23 KB) — NumPy wavefunction file
- `mp2_wfn.npy` (22 KB) — NumPy wavefunction file
- `results.json` (3 KB) — structured results from Python API
- `timer.dat` (7 KB) — timing information

**Key findings**:
1. Wavefunction can be saved to .npy files and reused between calculations
2. `psi4.core.variables()` returns ~29 named quantities after MP2
3. Output .dat file uses binary encoding (not pure ASCII)

### 3.2 Calculation 2: Geometry Optimization + Frequency (Water, B3LYP/6-31G*)

**Topology**: Relax → Freq (standalone relax, then vibrational analysis)

**Results**:
- Optimized energy: -76.4089553829 Hartree
- Optimized geometry: O-H = 0.9697 Å, H-O-H = 103.7°
- Frequencies: 1713.0, 3727.1, 3849.0 cm⁻¹ (all positive — true minimum)
- ZPVE: 0.02116 Hartree = 13.28 kcal/mol
- Gibbs correction: 0.00350 Hartree

**Artifacts produced**:
- `opt_freq_output.dat` (242 KB) — large due to finite-difference Hessian
- `opt_wfn.npy` (18 KB)
- `results.json` (3 KB)
- `timer.dat` (8 KB)

**Key findings**:
1. Optimization uses geometric optimizer (internal coords)
2. Frequencies via finite-difference of gradients (no analytic Hessian for DFT)
3. Thermochemistry auto-computed at 298.15 K
4. Output file is large for freq (many gradient evaluations)

### 3.3 Calculation 3: SCF → TDDFT (Formaldehyde, HF/cc-pVDZ)

**Topology**: SCF → TD chain (excited states from reference wavefunction)

**Results**:
- SCF energy: -113.8762189044 Hartree
- Excitation 1: 4.594 eV (n→π*, dark)
- Excitation 2: 9.944 eV
- 5 excited states computed

**Artifacts produced**:
- `tddft_output.dat` (13 KB)
- `results.json` (7 KB)
- `timer.dat` (5 KB)

**Key findings**:
1. TDDFT uses `tdscf_excitations(wfn, states=N)` function
2. Requires `save_jk=True` option for SCF wavefunction
3. Returns list of dicts with excitation energies and transition dipoles
4. TDA (Tamm-Dancoff) and full RPA both available

---

## 4. File System & Artifact Analysis

### 4.1 Files Produced by Psi4

| File | Size | Persistence | Description |
|------|------|-------------|-------------|
| `output.dat` | 10-250 KB | Keep | Full text output (SCF iterations, energies, geometry) |
| `wavefunction.npy` | 18-23 KB | Optional | NumPy wavefunction (checkpoint equivalent) |
| `timer.dat` | 5-8 KB | Optional | Timing breakdown |
| `results.json` | 3-7 KB | Keep | Structured results (our generation) |

### 4.2 Scratch Files

Psi4 uses `/tmp/` as default scratch. Files include:
- `*.default.*.npy` — temporary wavefunction files
- No large scratch files for small molecules

### 4.3 Wavefunction Persistence

Unlike ORCA (`.gbw` binary) or PySCF (`.chk` HDF5), Psi4 uses NumPy `.npy` format:
- `wfn.to_file("wfn.npy")` — save
- `psi4.core.Wavefunction.from_file("wfn.npy")` — load

This is a critical difference from ORCA's approach where `.gbw` files are shared across chain jobs.

---

## 5. Comparison with Existing QMatSuite Engines

| Feature | Psi4 | PySCF | ORCA | QE |
|---------|------|-------|------|-----|
| **Type** | Molecular QC | Molecular QC | Molecular QC | Periodic DFT |
| **Interface** | Python API | Python API | External binary | External binary |
| **Input** | Python script | Python API | Text input | Text input |
| **Output** | Variables dict + .dat | JSON results | .property.txt + .out | Text output |
| **Wfn format** | .npy (NumPy) | .chk (HDF5-like) | .gbw (binary) | outdir/ (scratch) |
| **Chain support** | ✅ (ref_wfn) | ✅ (shared mf) | ✅ (MORead) | N/A (shared outdir) |
| **Subprocess?** | Optional | Required¹ | Required | Required |
| **MPI** | No² | No | Yes | Yes |

¹ PySCF is run via subprocess to avoid import conflicts
² Psi4 uses OpenMP threading internally

### 5.1 Closest Analog: PySCF

Psi4 is most similar to PySCF in QMatSuite's engine taxonomy:
- Both are Python-native molecular QC codes
- Both support chain execution (SCF → post-SCF)
- Both can run in-process or via subprocess
- Both produce structured results (variables dict / results.json)

**Key difference**: Psi4 is a compiled C++/Fortran library with Python bindings (faster, but heavier), while PySCF is mostly pure Python (lighter, slower). Psi4 also has broader method coverage (SAPT, DLPNO-CCSD(T)).

---

## 6. Execution Model Decision

### 6.1 Option A: In-Process (like direct PySCF)

```python
import psi4
e, wfn = psi4.energy('scf/cc-pvdz')
```

**Pros**: Fastest, simplest, direct access to variables
**Cons**: Psi4 import is heavy (~1s), global state (memory, threads), potential for crashes taking down the daemon

### 6.2 Option B: Subprocess Python Script (like PySCF handler)

```python
# Generate psi4_input.py, then:
subprocess.run(["python", "psi4_input.py"], cwd=working_dir)
# Parse results.json
```

**Pros**: Isolation from daemon, clean state each run, robust against crashes
**Cons**: Script generation overhead, subprocess startup

### 6.3 Recommendation: **Option B (Subprocess)**

Follow the PySCF pattern exactly. Reasons:
1. **Isolation**: Psi4 has global state (memory, threads, output file) that can conflict with daemon
2. **Robustness**: Segfaults in Psi4 don't crash the daemon
3. **Consistency**: Matches PySCF handler pattern, no new archetype needed
4. **Results format**: Generate Python script → execute → parse results.json

---

## 7. Recipe Archetype Decision

### 7.1 Strong-Chain Recipe (like ORCA/PySCF)

Psi4 naturally fits the **strong-chain recipe** archetype:

- **Chain topology**: SCF → MP2, SCF → CCSD, SCF → TD
- **One job per subchain target**: Cumulative execution (like ORCA)
- **Wavefunction reuse**: Via `ref_wfn` parameter (like ORCA's MORead)
- **Working directory**: `calc/raw/scf_<ulid_suffix>/` (namespace folder)
- **WorkdirPolicy**: `ISOLATED`

### 7.2 Why Not Other Archetypes

- **Directory-State (QE-like)**: Psi4 doesn't use shared outdir scratch
- **Cleanup (VASP-like)**: Unnecessary — no stale file conflicts
- **Session-only**: Psi4 supports checkpoint reuse via .npy

### 7.3 Chain Execution Strategy

For chain `[SCF, MP2, TD]`:

```
Job "s":     Execute SCF only → save wfn.npy → results.json
Job "s_m2":  Execute SCF + MP2 (ref_wfn from SCF) → results.json
Job "s_t":   Execute SCF + TD (ref_wfn from SCF) → results.json
```

Each job generates a Python script, executes it via subprocess, and reads results.json.

---

## 8. Parser Strategy

### 8.1 Primary: Python API Variables

The preferred parsing method uses `psi4.core.variables()` inside the generated script. The script dumps all variables to `results.json`, which the handler reads.

This is more reliable than text parsing because:
- Structured data (no regex fragility)
- Complete (all computed quantities)
- Type-safe (numbers, not strings)

### 8.2 Fallback: Text Output Parsing

For existing output files or debugging, the text parser extracts:
- SCF energy from `@DF-RHF Final Energy:` pattern
- MP2 energy from `DF-MP2 Energies` block
- Frequencies from vibrational analysis section
- Thermochemistry from ZPVE/thermal/enthalpy/Gibbs section
- Geometry from `Geometry (in Angstrom)` blocks

---

## 9. Supported Step Types for Psi4

Based on Psi4's capabilities and QMatSuite's GEN step registry:

| GEN Step | SPEC Step | Psi4 Function | Description |
|----------|-----------|---------------|-------------|
| `scf` | `psi4_scf` | `psi4.energy('scf')` | HF/DFT SCF |
| `hf` | `psi4_hf` | `psi4.energy('hf')` | Pure Hartree-Fock |
| `mp2` | `psi4_mp2` | `psi4.energy('mp2')` | MP2 correlation |
| `relax` | `psi4_relax` | `psi4.optimize(method)` | Geometry optimization |
| `td` | `psi4_td` | `tdscf_excitations(wfn)` | TDDFT/TDA excited states |

### 9.1 Potential Future Steps (not in initial integration)

| GEN Step | SPEC Step | Notes |
|----------|-----------|-------|
| `freq`¹ | `psi4_freq` | Frequency analysis (needs new GEN step) |
| `ccsd`¹ | `psi4_ccsd` | CCSD/CCSD(T) |
| `sapt`¹ | `psi4_sapt` | Symmetry-Adapted PT |

¹ These GEN steps are NOT yet in `GenStepRegistry.GEN_STEPS`. Adding them requires updating `gen_steps.py` — a kernel change.

### 9.2 GenStepRegistry Impact

Current `GEN_STEPS` includes: `scf`, `hf`, `relax`, `mp2`, `td` — all needed for initial Psi4 integration.

**No kernel change needed for initial step types.**

If we want to support `freq` or `ccsd` as first-class GEN steps, we need to add them to `GenStepRegistry.GEN_STEPS` in `gen_steps.py`. This is a minimal kernel change (adding strings to a frozenset).

---

## 10. Integration Complexity Assessment

### 10.1 What Can Be Done Without Kernel Changes

✅ Create `drivers/psi4/` bundle (driver, recipe, handler, writer, parser)
✅ Register Psi4Driver in `drivers/__init__.py`
✅ Support scf, hf, mp2, relax, td step types
✅ Subprocess execution with results.json exchange
✅ Chain execution following ORCA/PySCF strong-chain pattern

### 10.2 What Requires Kernel Changes

1. **Adding `freq` and `ccsd` to GenStepRegistry** (`workflow/gen_steps.py`):
   - Add `"freq"` and `"ccsd"` to `GEN_STEPS` frozenset
   - Reason: These are generic computation intents not currently registered
   - Impact: Minimal — additive only, no existing code changes

2. **Import in `drivers/__init__.py`**:
   - Add `from quantumvitas.drivers.psi4 import Psi4Driver` or similar
   - Reason: Required for auto-registration
   - Impact: One line addition

### 10.3 What Does NOT Need Kernel Changes

- runner.py — No changes (engine-agnostic)
- executor.py — No changes
- handlers.py — No changes (handler map from registry)
- recipes.py — No changes (BaseRecipe used)
- driver_protocol.py — No changes (protocol unchanged)
- driver_registry.py — No changes (registration API unchanged)
