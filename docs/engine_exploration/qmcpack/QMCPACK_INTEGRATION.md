# QMCPACK Integration

## Overview

QMCPACK (Quantum Monte Carlo PACKage) is integrated into QMatSuite as a first-class
engine alongside QE, LAMMPS, ORCA, PySCF, and CP2K.

| Property           | Value                             |
|--------------------|-----------------------------------|
| Engine family      | `qmcpack`                         |
| Driver module      | `quantumvitas.drivers.qmcpack`    |
| Engine class       | `QmcpackEngine`                   |
| Step types (gen)   | `vmc`, `dmc`, `wfopt`             |
| Step types (spec)  | `qmcpack_vmc`, `qmcpack_dmc`, `qmcpack_wfopt` |
| Input format       | XML (`qmc_input.xml`)             |
| Output artifacts   | `*.scalar.dat`, `*.dmc.dat`, `*.opt.xml` |
| Wavefunction input | HDF5 (`.h5`) from pw2qmcpack     |
| Pseudopotentials   | XML format (e.g., `C.BFD.xml`)    |

## Architecture

### Driver Bundle (`src/quantumvitas/drivers/qmcpack/`)

```
drivers/qmcpack/
  __init__.py       # DriverBundle registration (auto-discovered)
  driver.py         # QMCPACKDriverBundle: step types, handler reference
  handler.py        # qmcpack_step_handler: job execution orchestration
  recipe.py         # QMCPACKRecipe: step type -> gen type materialization
  writer.py         # XML input generation from structured parameters
  parser.py         # Output parsing (scalar.dat, dmc.dat, stdout)
```

### Engine (`src/quantumvitas/engine/qmcpack_engine.py`)

- `QmcpackEngine.materialize_inputs()`: Builds `qmc_input.xml` from step
  parameters, stages HDF5 wavefunction and pseudopotential files into workdir.
- `QmcpackEngine.run_step()`: Executes `qmcpack qmc_input.xml` via subprocess.
- `_stage_supporting_files()`: Copies `.h5` and pseudo XML files from
  `project_root` into the step's isolated working directory.

### Resolver (`src/quantumvitas/core/engines/qmcpack_resolver.py`)

Two resolver functions:

**`resolve_qmcpack_bin()`** — Search order:
1. `QMATS_QMCPACK_BIN` environment variable
2. `.qmatsuite/engines/qmcpack/*/bin/qmcpack` (home + cwd)
3. `$CONDA_PREFIX/bin/qmcpack`
4. System paths (`/usr/local/bin`, `/usr/bin`, `/opt/homebrew/bin`)
5. PATH: `qmcpack`

**`resolve_pw2qmcpack_bin()`** — Search order:
1. `QMATS_PW2QMCPACK_BIN` environment variable
2. `.qmatsuite/engines/qe/*/bin/pw2qmcpack.x` (home + cwd)
3. Same directory as QE `pw.x` (via `resolve_qe_bin_dir`)
4. PATH: `pw2qmcpack.x`

## Workflow: QE -> pw2qmcpack -> QMCPACK

QMCPACK requires wavefunctions from a prior DFT calculation. The standard
pipeline is:

```
pw.x (QE SCF)  -->  pw2qmcpack.x  -->  qmcpack (VMC/DMC/wfopt)
                        |
                   pwscf.pwscf.h5
```

### Step 1: QE SCF

Run a standard QE SCF calculation with `wf_collect = .true.` to produce
wavefunctions. Key settings:
- `nosym = .true.` (QMCPACK requires this)
- BFD pseudopotentials (`C.BFD.upf` for carbon)
- `outdir = 'pwscf_output'`, `prefix = 'pwscf'`

### Step 2: pw2qmcpack

Convert QE wavefunctions to QMCPACK HDF5 format:
```
&inputpp
   write_psir = .false.
   prefix = 'pwscf'
   outdir = 'pwscf_output'
/
```

Produces `pwscf_output/pwscf.pwscf.h5`.

### Step 3: QMCPACK VMC/DMC

Run QMCPACK using the HDF5 wavefunction file and XML pseudopotentials.
The QMatSuite engine handles XML generation and file staging.

## Step Type Support

### VMC (`vmc` / `qmcpack_vmc`)

Variational Monte Carlo. Parameters:

| Parameter    | Default | Description                |
|-------------|---------|----------------------------|
| `walkers`    | 1       | Number of walkers          |
| `blocks`     | 200     | Number of blocks           |
| `steps`      | 10      | Steps per block            |
| `substeps`   | 2       | Sub-steps per step         |
| `timestep`   | 0.3     | Time step (Ha^-1)          |
| `warmupsteps`| 50      | Warmup steps               |
| `usedrift`   | "yes"   | Use drift in moves         |

### DMC (`dmc` / `qmcpack_dmc`)

Diffusion Monte Carlo. Preceded by a VMC equilibration. Parameters:

| Parameter        | Default | Description                |
|-----------------|---------|----------------------------|
| `targetwalkers`  | 256     | Target walker population   |
| `blocks`         | 100     | Number of blocks           |
| `steps`          | 20      | Steps per block            |
| `timestep`       | 0.005   | Time step (Ha^-1)          |
| `warmupsteps`    | 50      | Warmup steps               |
| `nonlocalmoves`  | "yes"   | T-move approximation       |

### Wavefunction Optimization (`wfopt` / `qmcpack_wfopt`)

Optimize Jastrow coefficients. Parameters:

| Parameter                  | Default    | Description              |
|---------------------------|------------|--------------------------|
| `blocks`                   | 100        | Blocks per optimization  |
| `steps`                    | 50         | Steps per block          |
| `samples`                  | 5000       | Samples for optimization |
| `minmethod`                | "adaptive" | Optimization method      |
| `num_loops`                | 3          | Optimization iterations  |
| `max_relative_cost_change` | 10.0       | Cost change threshold    |
| `max_param_change`         | 3.0        | Max parameter change     |

## Writer Details

### `driver_version` parameter

QMCPACK 4.x defaults to the "batched" driver, which rejects certain legacy
parameters (e.g., `walkers`). The writer adds
`<parameter name="driver_version">legacy</parameter>` to the `<project>`
element to ensure compatibility.

### Wavefunction section

The writer uses the `sposet_collection` + `determinantset` pattern (modern
QMCPACK style) rather than the older `determinantset type="einspline"` style.
Both work but the sposet pattern is the forward-compatible approach.

## Key Implementation Notes

### Case-insensitive parameter keys

The StepDoc/apply_patch system may uppercase parameter keys (e.g., `cell` ->
`CELL`). The QMCPACK engine performs case-insensitive key lookup when
extracting parameters from the step spec.

### Materialization bypass

QMCPACK steps bypass the QE input generation pipeline in
`materialize_step_spec()`. Like LAMMPS, ORCA, PySCF, and CP2K, the QMCPACK
engine builds its input file (XML) dynamically from the step parameters
during `materialize_inputs()`, not through the QE `.in` file writer.

### File staging

The engine copies the HDF5 wavefunction and pseudopotential files from
`project_root` into the step's isolated working directory before execution.
Files are referenced by relative path in the step parameters
(`wavefunction.href`, `species[].pseudo_file`).

## Test Coverage

| Test                                        | Type          | What it tests                              |
|--------------------------------------------|---------------|--------------------------------------------|
| `tests/drivers/qmcpack/test_qmcpack_driver.py` | Unit (37) | Writer, parser, recipe, resolver, registry |
| `tests/integration/test_qmcpack_vmc.py`    | Integration   | Standalone VMC via API (requires h5+qmcpack) |
| `tests/integration/test_qmcpack_diamond_workflow.py` | Integration | Full QE->pw2qmcpack->QMCPACK pipeline |

The diamond workflow test:
- Runs QE SCF for diamond C 1x1x1 (subprocess)
- Runs pw2qmcpack to generate HDF5 (subprocess)
- Runs QMCPACK VMC via full QMatSuite API (project/calc/step)
- Asserts `scalar.dat` exists, energy is finite and in range [-15, -5] Ha
- Verifies `driver_version=legacy` in generated XML
- Skips if pw.x, pw2qmcpack.x, or qmcpack binaries not available

## Known Limitations

1. **No automatic QE->pw2qmcpack->QMCPACK chain**: The multi-engine workflow
   (QE SCF, pw2qmcpack conversion, QMCPACK QMC) is not automated as a single
   calculation chain. The QE/pw2qmcpack phases must be run separately, then
   the HDF5 file staged for QMCPACK.

2. **BFD pseudopotentials only**: The smoke test uses BFD pseudopotentials.
   Other pseudo families (ccECP, etc.) should work but are untested.

3. **Serial execution only**: The engine runs `qmcpack` without MPI. For
   production calculations, users should configure MPI externally.

4. **No batched driver support**: The writer always sets `driver_version=legacy`.
   The QMCPACK 4.x batched driver has different parameter semantics and is
   not supported yet.

5. **Single k-point only**: The smoke test uses Gamma-only. Multi-k-point
   (twist-averaged) calculations are structurally supported but untested.
