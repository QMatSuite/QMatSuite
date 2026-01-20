# CP2K File I/O and Directory Contracts

**Last reviewed**: 2025-01-19
**CP2K version target**: 2025.1
**Sources consulted**:
- [CP2K Manual - TRAJECTORY](https://manual.cp2k.org/trunk/CP2K_INPUT/MOTION/PRINT/TRAJECTORY.html)
- [CP2K Manual - GLOBAL](https://manual.cp2k.org/trunk/CP2K_INPUT/GLOBAL.html)
- [CP2K Output Understanding Guide](https://docs.bioexcel.eu/qmmm_bpg/en/main/running_cp2k/cp2k_output.html)
- [CP2K Basis Sets Documentation](https://www.cp2k.org/basis_sets)
- [ASE CP2K Calculator](https://wiki.fysik.dtu.dk/ase/ase/calculators/cp2k.html)

---

## 1. Input File Conventions

### 1.1 Single Input File

CP2K uses a single `.inp` file for all calculation settings:

```
input.inp                    # Main input file
```

**Command line invocation**:
```bash
cp2k.ssmp -i input.inp -o output.log
# or simply:
cp2k.ssmp input.inp > output.log
```

### 1.2 PROJECT_NAME and File Naming

The `PROJECT` keyword in `&GLOBAL` section determines output file prefixes:

```
&GLOBAL
  PROJECT silicon_scf
  RUN_TYPE ENERGY_FORCE
&END GLOBAL
```

All output files will be prefixed with `silicon_scf`:
- `silicon_scf-RESTART.wfn`
- `silicon_scf-pos-1.xyz`
- `silicon_scf-1.ener`

### 1.3 Filename Control Modifiers

CP2K provides fine-grained filename control:

| Modifier | Behavior | Example |
|----------|----------|---------|
| `filename` | Prepends PROJECT | `PROJECT-filename` |
| `./filename` | Removes PROJECT prefix | `filename` |
| `=filename` | Exact filename (no iteration suffix) | `filename` |

**Example**:
```
&PRINT
  &TRAJECTORY
    FILENAME =trajectory.xyz    # Exact: trajectory.xyz
  &END TRAJECTORY
&END PRINT
```

---

## 2. Output File Catalog

### 2.1 Standard Output Files

| File Pattern | Description | When Generated |
|--------------|-------------|----------------|
| `PROJECT.out` or stdout | Main log output | Always |
| `PROJECT-RESTART.wfn` | Wavefunction restart | After SCF convergence |
| `PROJECT-RESTART.wfn.bak-1` | Wavefunction backup | Previous SCF step |
| `PROJECT.restart` | Full calculation restart | GEO_OPT/MD |
| `PROJECT-1.restart` | Periodic MD restart | Every N MD steps |

### 2.2 Trajectory and Property Files

| File Pattern | Description | Content |
|--------------|-------------|---------|
| `PROJECT-pos-1.xyz` | Position trajectory | XYZ format coordinates |
| `PROJECT-frc-1.xyz` | Force trajectory | Forces on atoms |
| `PROJECT-vel-1.xyz` | Velocity trajectory | Atomic velocities |
| `PROJECT-1.ener` | Energy file | Step, time, energies |
| `PROJECT-1.cell` | Cell evolution | Cell vectors per step |
| `PROJECT-1.stress` | Stress tensor | Stress per step |

### 2.3 Energy File Format (`.ener`)

```
#   Step   Time[fs]       Kin.[a.u.]   Temp[K]     Pot.[a.u.]   Cons Qty[a.u.]   CPU[s]
      0      0.000000    0.000000000    0.00     -17.157456789   -17.157456789    1.234
      1      0.500000    0.001234567  156.78     -17.158234567   -17.156999999    2.345
```

### 2.4 Optimization-Specific Files

| File Pattern | Description |
|--------------|-------------|
| `PROJECT-BFGS.Hessian` | BFGS Hessian matrix |
| `PROJECT-CG.Hessian` | CG Hessian approximation |
| `PROJECT-rot-1.xyz` | Rotated structures (NEB) |

---

## 3. Data File Discovery (Basis Sets & Potentials)

### 3.1 CP2K_DATA_DIR Environment Variable

CP2K searches for basis set and potential files in this order:

1. Current working directory
2. Path specified in input file (absolute or relative)
3. `$CP2K_DATA_DIR` environment variable
4. Built-in data directory (compile-time `__DATA_DIR` macro)

**Homebrew installation** (macOS):
```bash
__DATA_DIR="/opt/homebrew/Cellar/cp2k/2025.1/share/cp2k/data"
```

### 3.2 Specifying Data Files in Input

```
&FORCE_EVAL
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    BASIS_SET_FILE_NAME GTH_BASIS_SETS    # Can specify multiple
    POTENTIAL_FILE_NAME GTH_POTENTIALS
    ...
  &END DFT
&END FORCE_EVAL
```

### 3.3 Common Data Files

| File | Contents |
|------|----------|
| `BASIS_MOLOPT` | Molecularly optimized basis sets |
| `BASIS_SET` | Standard basis sets |
| `GTH_BASIS_SETS` | GTH-compatible basis sets |
| `GTH_POTENTIALS` | Goedecker-Teter-Hutter pseudopotentials |
| `POTENTIAL` | General potentials |
| `ALL_POTENTIALS` | All available potentials |

### 3.4 Recommended QMatSuite Strategy

**Option A: Rely on CP2K_DATA_DIR** (Recommended)
- Set `CP2K_DATA_DIR` environment variable
- Input files reference data by filename only
- Works across installations

**Option B: Embed full paths**
- Use absolute paths in input
- More explicit but less portable

```
# Option A (portable):
BASIS_SET_FILE_NAME BASIS_MOLOPT

# Option B (explicit):
BASIS_SET_FILE_NAME /opt/homebrew/Cellar/cp2k/2025.1/share/cp2k/data/BASIS_MOLOPT
```

---

## 4. Directory State Contract

### 4.1 Recommended QMatSuite Directory Layout

```
calculations/<calc_id>/
├── calculation.yaml                    # SSOT: calculation definition
├── steps/
│   ├── <step1_ulid>.step.yaml          # SSOT: step definition
│   └── <step2_ulid>.step.yaml
├── raw/
│   ├── <step1_ulid>/                   # Working directory for step 1
│   │   ├── input.inp                   # Generated CP2K input
│   │   ├── output.log                  # CP2K stdout
│   │   ├── cp2k_calc-RESTART.wfn       # Wavefunction restart
│   │   ├── cp2k_calc.restart           # Full restart (if GEO_OPT/MD)
│   │   ├── cp2k_calc-pos-1.xyz         # Trajectory
│   │   └── cp2k_calc-1.ener            # Energy log (if MD)
│   └── <step2_ulid>/                   # Working directory for step 2
│       └── ...
└── .run_tmp_info/
    └── manifest.json                   # Incremental run state
```

### 4.2 Managed PROJECT Name

QMatSuite should use a **fixed PROJECT name** per step to ensure predictable output filenames:

```
PROJECT = "cp2k_calc"
```

This yields consistent output patterns:
- `cp2k_calc-RESTART.wfn`
- `cp2k_calc-pos-1.xyz`
- `cp2k_calc.restart`

**Alternative**: Use step ULID suffix for uniqueness:
```
PROJECT = "step_01HYABCD"
```

### 4.3 Working Directory Isolation

**Rule**: Each CP2K job runs in its own isolated directory.

```
cd calculations/<calc_id>/raw/<step_ulid>/
cp2k.ssmp -i input.inp -o output.log
```

**Benefits**:
- No filename collisions between steps
- Clear artifact ownership
- Easy cleanup and re-run

### 4.4 CP2K Writes Relative to CWD

CP2K writes all output files relative to the current working directory (CWD), not the input file location.

**Implication**: Always `cd` to the step working directory before invoking CP2K.

```python
# Correct:
os.chdir(working_dir)
subprocess.run(["cp2k.ssmp", "-i", "input.inp", "-o", "output.log"])

# Wrong (files would be written to wrong location):
subprocess.run(["cp2k.ssmp", "-i", str(working_dir / "input.inp"), "-o", str(working_dir / "output.log")])
```

---

## 5. Avoiding Global State

### 5.1 No Shared Scratch Directory

Unlike QE (which uses `outdir` for shared wavefunction storage), CP2K stores wavefunctions in the working directory. This means:

- No need for a shared `outdir` equivalent
- Each step's `.wfn` file is self-contained
- Restarts reference files by explicit path

### 5.2 Environment Variables

| Variable | Purpose | QMatSuite Handling |
|----------|---------|-------------------|
| `CP2K_DATA_DIR` | Data file discovery | Set in execution environment |
| `OMP_NUM_THREADS` | OpenMP parallelism | Set per job |
| `OMP_STACKSIZE` | Thread stack size | May need tuning (512M typical) |

**Example execution environment**:
```bash
export CP2K_DATA_DIR=/opt/homebrew/share/cp2k/data
export OMP_NUM_THREADS=4
export OMP_STACKSIZE=512M
cp2k.ssmp -i input.inp -o output.log
```

### 5.3 Reproducibility Guarantees

For reproducible runs:
1. Use fixed PROJECT name per step
2. Set explicit random seeds (for MD):
   ```
   &GLOBAL
     SEED 12345
   &END GLOBAL
   ```
3. Record CP2K version in history
4. Store complete input file (no @INCLUDE)

---

## 6. Restart File Management

### 6.1 Restart File Locations

| Artifact | Location | Reference Pattern |
|----------|----------|-------------------|
| Wavefunction | `<step_dir>/cp2k_calc-RESTART.wfn` | `WFN_RESTART_FILE_NAME ../step1/cp2k_calc-RESTART.wfn` |
| Full restart | `<step_dir>/cp2k_calc.restart` | `RESTART_FILE_NAME ../step1/cp2k_calc.restart` |
| MD restart | `<step_dir>/cp2k_calc-1.restart` | `RESTART_FILE_NAME ../step1/cp2k_calc-1.restart` |

### 6.2 Cross-Step References

When step 2 needs artifacts from step 1:

```
&EXT_RESTART
  RESTART_FILE_NAME ../01HYAAAA/cp2k_calc.restart
&END EXT_RESTART

&FORCE_EVAL
  &DFT
    WFN_RESTART_FILE_NAME ../01HYAAAA/cp2k_calc-RESTART.wfn
  &END DFT
&END FORCE_EVAL
```

### 6.3 Structure Extraction

To extract final geometry from a relaxation:

1. **From trajectory**: Parse last frame of `cp2k_calc-pos-1.xyz`
2. **From restart**: Parse `cp2k_calc.restart` (contains coordinates in COORD section)

**Trajectory XYZ format**:
```
8
 i =        5, E =      -17.12345678
Si        0.000000000     0.000000000     0.000000000
Si        1.357000000     1.357000000     1.357000000
...
```

---

## 7. Summary: QMatSuite Directory Contract

### 7.1 Input Generation

1. Create step working directory: `raw/<step_ulid>/`
2. Generate `input.inp` with managed PROJECT name
3. Set relative paths for any restart references
4. No external includes or absolute paths (except data files)

### 7.2 Execution

1. Set environment: `CP2K_DATA_DIR`, `OMP_NUM_THREADS`
2. `cd` to working directory
3. Run: `cp2k.ssmp -i input.inp -o output.log`
4. Capture return code and check output

### 7.3 Output Parsing

| Artifact | Source | Parse For |
|----------|--------|-----------|
| Energy | `output.log` or `.ener` | Total energy, convergence |
| Forces | `output.log` or `-frc-1.xyz` | Force vectors |
| Structure | `-pos-1.xyz` (last frame) | Final geometry |
| Wavefunction | `-RESTART.wfn` | Pass to next step |

### 7.4 Manifest Recording

Track in manifest:
- `step_sha`: Hash of input.inp
- `pseudo_set_sha`: N/A (basis/potential in input)
- `structure_sha`: Hash of input structure
- `done`: True when output.log shows successful completion
