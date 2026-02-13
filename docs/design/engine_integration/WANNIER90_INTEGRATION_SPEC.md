# Wannier90 Integration Specification

**Version**: 1.0 (MVP)  
**Date**: 2026-01-02  
**Status**: Implementation Ready

---

## 1. Overview

This specification defines the end-to-end Wannier90 integration in QMatSuite. The goal is to enable users to run Wannier90 workflows (SCF → NSCF → Wannier preprocessing → pw2wannier90 → wannier90) using the bundled QE engine.

### 1.1 MVP Target

Implement the **Diamond example** from the Wannier90 tutorial (example05):
- Diamond structure (2 C atoms, FCC)
- 4 sp³ bond-centered Wannier functions
- Full workflow: SCF → NSCF → w90_preproc → pw2wannier90 → wannier90

### 1.2 Key Constraints

- **Constitution compliance**: `step.yml` is the only executable truth
- **No workflow persistence**: Workflow is inferred from step topology
- **Managed engine**: Uses executables from `.qmatsuite/engines/qe/q-e-qe-7.5/bin/`
- **Minimal parameter model**: Structured subset + raw passthrough

---

## 2. Step Types

### 2.1 New Step Types

| Step Type | Executable | Description |
|-----------|------------|-------------|
| `w90_preproc` | `wannier90.x -pp` | Generate `.nnkp` file |
| `pw2wannier90` | `pw2wannier90.x` | Compute overlaps (`.mmn`, `.amn`, `.eig`) |
| `w90_run` | `wannier90.x` | Main MLWF optimization |

### 2.2 Dependency Graph (Diamond Workflow)

```
SCF (pw.x) 
    ↓
NSCF (pw.x, uniform k-grid) 
    ↓
w90_preproc (wannier90.x -pp)  ←── requires .win file
    ↓
pw2wannier90 (pw2wannier90.x) ←── requires .nnkp + QE save files
    ↓
w90_run (wannier90.x)         ←── requires .win + .mmn + .amn + .eig
```

### 2.3 Input/Output Files

#### w90_preproc
- **Input**: `{seedname}.win`
- **Output**: `{seedname}.nnkp`
- **Command**: `wannier90.x -pp {seedname}`

#### pw2wannier90
- **Input**: 
  - `{seedname}.pw2wan` (pw2wannier90 input)
  - `{seedname}.nnkp` (from w90_preproc)
  - QE save directory (from NSCF)
- **Output**: `{seedname}.mmn`, `{seedname}.amn`, `{seedname}.eig`
- **Command**: `pw2wannier90.x < {seedname}.pw2wan`

#### w90_run
- **Input**: `{seedname}.win`, `.mmn`, `.amn`, `.eig`
- **Output**: `{seedname}.wout`, `{seedname}.chk`, spread/center data
- **Command**: `wannier90.x {seedname}`

---

## 3. Parameter Model

### 3.1 Wannier90 Input (.win) Parameters

Minimum structured subset for MVP:

```yaml
# In step.yml for w90_preproc or w90_run
parameters:
  seedname: "diamond"      # Controls all filenames
  num_wann: 4              # Number of Wannier functions
  num_bands: 4             # Number of bands (optional, defaults to num_wann)
  num_iter: 20             # Max iterations for localization
  
  # Unit cell (Bohr or Angstrom)
  unit_cell_cart:          # List of 3 vectors
    - [-1.613990, 0.000000, 1.613990]
    - [0.000000, 1.613990, 1.613990]
    - [-1.613990, 1.613990, 0.000000]
  
  # Atoms in fractional coordinates
  atoms_frac:
    - [C, -0.125, -0.125, -0.125]
    - [C, 0.125, 0.125, 0.125]
  
  # MP grid for k-points
  mp_grid: [4, 4, 4]
  
  # K-points (explicit list)
  kpoints: []              # Auto-generated from mp_grid if empty
  
  # Projections block (raw string for MVP)
  projections_block: |
    f=0.0,0.0,0.0:s
    f=0.0,0.0,0.5:s
    f=0.0,0.5,0.0:s
    f=0.5,0.0,0.0:s
  
  # Raw passthrough for any additional parameters
  extra_win_lines: ""      # Appended verbatim to .win file
```

### 3.2 pw2wannier90 Input (.pw2wan) Parameters

```yaml
parameters:
  seedname: "diamond"       # Must match .win seedname
  prefix: "di"              # QE calculation prefix (from NSCF)
  outdir: "./"              # QE outdir
  write_mmn: true
  write_amn: true
  write_unk: false          # For plotting (larger files)
  spin_component: "none"    # none, up, down
```

---

## 4. File Rendering

### 4.1 .win File Format

```
num_wann        = 4
num_iter        = 20

begin atoms_frac
C   -0.12500  -0.1250    -0.125000
C    0.12500   0.1250     0.125000
end atoms_frac

begin projections
f=0.0,0.0,0.0:s
f=0.0,0.0,0.5:s
f=0.0,0.5,0.0:s
f=0.5,0.0,0.0:s
end projections

begin unit_cell_cart
-1.613990   0.000000   1.613990
 0.000000   1.613990   1.613990
-1.613990   1.613990   0.000000
end unit_cell_cart

mp_grid : 4 4 4

begin kpoints
0.0000  0.0000  0.0000
0.0000  0.2500  0.0000
...
end kpoints
```

### 4.2 .pw2wan File Format

```
&inputpp
   outdir = './'
   prefix = 'di'
   seedname = 'diamond'
   spin_component = 'none'
   write_mmn = .true.
   write_amn = .true.
   write_unk = .false.
/
```

---

## 5. Runner Implementation

### 5.1 Command Execution

```python
# w90_preproc: wannier90.x -pp seedname
command = [wannier90_exe, "-pp", seedname]

# pw2wannier90: pw2wannier90.x < input.pw2wan > output.out
command = [pw2wannier90_exe]
# Execute with stdin from .pw2wan file

# w90_run: wannier90.x seedname
command = [wannier90_exe, seedname]
```

### 5.2 Working Directory Setup

All Wannier90 steps must run in the same working directory where:
- QE save files exist (from NSCF)
- `.win` file is present
- `.nnkp` will be created (by w90_preproc)
- `.mmn`, `.amn`, `.eig` will be created (by pw2wannier90)

---

## 6. Demo Generator Strategy

### 6.1 Source Files

Location: `.qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/examples/example05/`

Files:
- `diamond.scf` → SCF step input
- `diamond.nscf` → NSCF step input
- `diamond.pw2wan` → pw2wannier90 step input
- `diamond.win` → Wannier90 input

Pseudo location: `.qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/pseudo/C.pz-vbc.UPF`

### 6.2 Demo Generation Script

Script: `tools/generate_wannier90_demo.py`

Steps:
1. Copy pseudo to `resources/pseudo/` if not present
2. Create project structure
3. Import SCF and NSCF steps as QE step types
4. Create w90_preproc step with .win parameters
5. Create pw2wannier90 step with .pw2wan parameters
6. Create w90_run step
7. Export project snapshot to `resources/demo_projects/`

### 6.3 Output Demo

File: `resources/demo_projects/diamond_wannier90_demo.yml`

---

## 7. Verification Checklist

### 7.1 Pre-execution
- [x] Demo project generated by script
- [x] Demo YAML verified by `tools/verify_demos.py`
- [x] Pseudo identity triple present in species_map
- [x] All 5 steps defined in demo calculation
- [ ] Demo project loads in UI (user verification)
- [ ] Step dependencies correctly shown (user verification)
- [ ] .win and .pw2wan files render correctly (user verification)

### 7.2 Execution (user verification)
- [ ] SCF completes with JOB DONE
- [ ] NSCF completes with JOB DONE
- [ ] w90_preproc creates `.nnkp` file
- [ ] pw2wannier90 creates `.mmn`, `.amn`, `.eig` files
- [ ] w90_run creates `.wout` file with spread data

### 7.3 Results (user verification)
- [ ] `.wout` contains "Final State" with spread values
- [ ] Wannier centers and spreads are reasonable
- [ ] No errors in any step output

---

## 8. Future Work (Post-MVP)

### 8.1 Deferred Features
- [ ] postw90.x integration (Berry phase, transport)
- [ ] wannier_plot.x integration (cube files)
- [ ] Disentanglement parameters (dis_win_min/max, etc.)
- [ ] Band structure interpolation (kpoint_path, bands_plot)
- [ ] Spinor/SOC support
- [ ] Multiple seednames per calculation
- [ ] Fermi surface plotting

### 8.2 Parameter Expansion
- Full structured parameters for projections (instead of raw block)
- Automated k-point generation from mp_grid
- Energy window parameters for disentanglement
- Plotting parameters (wannier_plot, bands_plot, etc.)

### 8.3 Additional Examples
- Silicon (example03) - disentanglement
- Copper (example04) - Fermi surface
- Iron (example06) - spin-polarized

---

## 9. Implementation Files

### 9.1 New Files
- `src/quantumvitas/io/wannier90_input.py` - .win file parser/generator
- `src/quantumvitas/io/pw2wannier90_input.py` - .pw2wan file generator
- `tools/generate_wannier90_demo.py` - Demo generator script

### 9.2 Modified Files
- `src/quantumvitas/calculation/types.py` - Add W90 step types
- `src/quantumvitas/workflow/registry.py` - Register W90 step specs
- `src/quantumvitas/core/engines/qe.py` - Add W90 executable map
- `src/quantumvitas/cli/main.py` - Add W90 to known step types

---

## 10. Assumptions & TODOs

### 10.1 Assumptions
- Wannier90 executables are in same bin directory as QE
- All W90 steps share working directory with QE steps
- Seedname is consistent across all W90 files
- K-points in .win must match those in NSCF

### 10.2 TODO Later
- [ ] Support for `outdir` != working directory
- [ ] Automatic seedname propagation between steps
- [ ] K-point consistency validation
- [ ] Parse .wout for spread/center extraction
- [ ] UI visualization of Wannier spread convergence

