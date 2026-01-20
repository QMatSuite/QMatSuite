# CP2K File and Artifact Policy

**Version**: v2.0 (Alignment Update)
**Last Updated**: 2026-01-20
**CP2K Version**: 2025.1

---

## 1. Overview

This document specifies the **deterministic filename patterns** for CP2K artifacts and the **"latest" selection rules** used by QMatSuite parsers. All rules are based on official CP2K documentation and behavior.

### 1.1 Key Alignment (v2 Update)

| Aspect | Policy |
|--------|--------|
| **Latest Selection** | **mtime-based** (NOT numeric suffix parsing) |
| **Runtime SSOT** | Always `raw/<step_ulid>/` |
| **Cell Information** | Separate `.cell` file for MD trajectories |
| **Artifact Retention** | All artifacts retained (never deleted) |

---

## 2. CP2K Output File Naming Convention

### 2.1 PROJECT Prefix

All CP2K output files are prefixed with the `PROJECT` name set in `&GLOBAL`:

```
&GLOBAL
  PROJECT cp2k_calc    # Fixed by QMatSuite (runtime-managed)
  RUN_TYPE ...
&END GLOBAL
```

QMatSuite uses a **fixed** PROJECT name: `cp2k_calc`

### 2.2 Complete File Catalog

| File Pattern | Description | When Generated | Selection |
|--------------|-------------|----------------|-----------|
| `cp2k_calc-RESTART.wfn` | Wavefunction restart | After each SCF | Direct (single) |
| `cp2k_calc-RESTART.wfn.bak-N` | Wavefunction backups | Automatic | Ignore (use main) |
| `cp2k_calc-N.restart` | Full calculation restart | GEO_OPT/MD, every M steps | mtime (max) |
| `cp2k_calc-pos-N.xyz` | Position trajectory | MD/GEO_OPT | mtime (max) |
| `cp2k_calc-frc-N.xyz` | Force trajectory | If enabled | mtime (max) |
| `cp2k_calc-vel-N.xyz` | Velocity trajectory | If enabled | mtime (max) |
| `cp2k_calc-N.ener` | Energy file | MD | mtime (max) |
| `cp2k_calc-N.cell` | Cell evolution | NPT MD / if enabled | mtime (max) |
| `cp2k_calc-N.stress` | Stress tensor | If enabled | mtime (max) |
| `cp2k_calc-BFGS.Hessian` | BFGS Hessian matrix | GEO_OPT | N/A (single) |

### 2.3 Numbering Scheme

**Pattern**: `<PROJECT>-N.<ext>` where N starts at 1.

CP2K increments N based on configuration:
- For `.ener`, `.cell`, `.stress`: typically N=1 (single file per run)
- For `.restart`: N increments based on `RESTART_EACH` setting
- For `-pos-N.xyz`: N=1 for trajectory output

**Note**: Multiple runs in the same directory will NOT overwrite. CP2K appends or uses higher N values depending on output type.

---

## 3. mtime-Based Selection Rules (UPDATED)

### 3.1 Selection Policy

**CRITICAL**: Latest selection uses **file modification time (mtime)**, not numeric suffix parsing.

**Rationale**:
- More robust short-term implementation
- Doesn't rely on CP2K naming conventions
- Works uniformly across artifact types
- Simpler implementation

### 3.2 General Algorithm

```python
def find_latest_by_mtime(workdir: Path, pattern: str) -> Optional[Path]:
    """
    Find latest file matching pattern by modification time.

    Args:
        workdir: Directory to search (Runtime SSOT: raw/<step_ulid>/)
        pattern: Glob pattern (e.g., "cp2k_calc-*.restart", "*.wfn")

    Returns:
        Path to file with most recent mtime, or None if no matches.

    Sources:
        - QMatSuite v4 alignment decision
    """
    candidates = list(workdir.glob(pattern))
    if not candidates:
        return None

    # Select by mtime (most recent)
    return max(candidates, key=lambda p: p.stat().st_mtime)
```

### 3.3 Restart Files

**Pattern**: `cp2k_calc-*.restart`

**Algorithm**:
```python
def find_latest_restart(workdir: Path) -> Optional[Path]:
    """
    Find latest restart file by mtime.

    Returns:
        Path to most recently modified cp2k_calc-*.restart, or None.
    """
    return find_latest_by_mtime(workdir, "cp2k_calc-*.restart")
```

**Example**:
```
workdir/
├── cp2k_calc-1.restart    # mtime: 10:00:00
├── cp2k_calc-5.restart    # mtime: 10:05:00
├── cp2k_calc-10.restart   # mtime: 10:10:00 ← SELECTED (latest mtime)
└── cp2k_calc.restart      # mtime: 09:00:00 (if exists, may be selected if latest)
```

### 3.4 Wavefunction Files

**Pattern**: `cp2k_calc-RESTART.wfn`

**Algorithm**:
```python
def find_latest_wfn(workdir: Path) -> Optional[Path]:
    """
    Find latest wavefunction restart file.

    CP2K maintains one main wfn file and up to 3 backups:
    - cp2k_calc-RESTART.wfn        ← USE THIS (latest)
    - cp2k_calc-RESTART.wfn.bak-1  (previous)
    - cp2k_calc-RESTART.wfn.bak-2  (older)
    - cp2k_calc-RESTART.wfn.bak-3  (oldest)

    Returns:
        Path to non-backup wfn file, or None if not found.

    Sources:
        - https://docs.bioexcel.eu/qmmm_bpg/en/main/running_cp2k/cp2k_output.html
    """
    main_wfn = workdir / "cp2k_calc-RESTART.wfn"
    if main_wfn.exists():
        return main_wfn

    return None
```

**Backup Files**:
- `*.wfn.bak-1`: Most recent backup (one SCF step old)
- `*.wfn.bak-2`: Second backup
- `*.wfn.bak-3`: Oldest backup (three SCF steps old)

**Policy**: Always use the non-backup file. Backups are for recovery only.

### 3.5 Trajectory Files

**Pattern**: `cp2k_calc-pos-*.xyz`

**Algorithm**:
```python
def find_latest_trajectory(workdir: Path) -> Optional[Path]:
    """
    Find latest trajectory file by mtime.

    CP2K trajectory naming: PROJECT-pos-N.xyz
    Default is N=1 for single trajectory file.

    Returns:
        Path to most recently modified trajectory, or None.
    """
    return find_latest_by_mtime(workdir, "cp2k_calc-pos-*.xyz")
```

### 3.6 Energy Files

**Pattern**: `cp2k_calc-*.ener`

```python
def find_latest_ener(workdir: Path) -> Optional[Path]:
    """Find latest energy file by mtime."""
    return find_latest_by_mtime(workdir, "cp2k_calc-*.ener")
```

### 3.7 Cell Files

**Pattern**: `cp2k_calc-*.cell`

```python
def find_latest_cell(workdir: Path) -> Optional[Path]:
    """Find latest cell file by mtime."""
    return find_latest_by_mtime(workdir, "cp2k_calc-*.cell")
```

---

## 4. Input File Conventions

### 4.1 Input Filename

QMatSuite uses a fixed input filename: `input.inp`

### 4.2 Output Filename

CP2K stdout is captured to: `output.log`

**Command**: `cp2k.ssmp -i input.inp -o output.log`

### 4.3 Input Structure

CP2K input uses a hierarchical section-based format:

```
&GLOBAL
  PROJECT cp2k_calc
  RUN_TYPE ENERGY_FORCE
&END GLOBAL

&FORCE_EVAL
  METHOD Quickstep
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    POTENTIAL_FILE_NAME GTH_POTENTIALS
    &MGRID
      CUTOFF 400
      REL_CUTOFF 60
    &END MGRID
    &SCF
      EPS_SCF 1.0E-6
      MAX_SCF 100
      SCF_GUESS RESTART
    &END SCF
    &XC
      &XC_FUNCTIONAL PBE
      &END XC_FUNCTIONAL
    &END XC
  &END DFT
  &SUBSYS
    &CELL
      ...
    &END CELL
    &COORD
      ...
    &END COORD
    &KIND Si
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q4
    &END KIND
  &END SUBSYS
&END FORCE_EVAL

&MOTION
  ...
&END MOTION
```

---

## 5. Artifact Categories

### 5.1 Required Outputs (for success determination)

| Step Type | Required Output | Check |
|-----------|-----------------|-------|
| cp2k_scf | `output.log` with SCF convergence | Parse "SCF CONVERGED" |
| cp2k_relax | `output.log` + `cp2k_calc-pos-*.xyz` | Parse final geometry |
| cp2k_md | `output.log` + `cp2k_calc-pos-*.xyz` | Trajectory exists |

### 5.2 Optional Outputs (for enhanced functionality)

| Output | Purpose | Availability |
|--------|---------|--------------|
| `cp2k_calc-RESTART.wfn` | Wavefunction for restart | If WFN_RESTART enabled |
| `cp2k_calc-*.restart` | Full restart | GEO_OPT/MD |
| `cp2k_calc-*.ener` | Energy time series | MD |
| `cp2k_calc-*.cell` | Cell evolution | NPT MD or if explicitly enabled |

### 5.3 Artifact Retention

**Policy**: All artifacts are **retained** (never deleted by QMatSuite).

**Rationale**:
- Audit trail
- Recovery from partial failures
- Post-analysis flexibility
- mtime selection handles old files naturally

---

## 6. Cell Information Handling (CRITICAL)

### 6.1 The Problem

**CP2K XYZ (XMOL) format does NOT contain cell information.**

This means trajectory files alone are insufficient for reconstructing full periodic structures.

### 6.2 Solution: Enable Cell Output

For MD simulations and any calculation where cell information is needed, enable cell printing:

```
&MOTION
  &PRINT
    &CELL
      &EACH
        MD 1              ! Print every step (adjust as needed)
        GEO_OPT 1         ! Print every GEO_OPT step
      &END EACH
    &END CELL
    &TRAJECTORY
      FORMAT XYZ
    &END TRAJECTORY
  &END PRINT
&END MOTION
```

### 6.3 Cell File Format

The `.cell` file contains cell vectors at each timestep:

```
#  Step   Time [fs]       Ax [Angstrom]   Ay [Angstrom]   Az [Angstrom]   Bx [Angstrom]   By [Angstrom]   Bz [Angstrom]   Cx [Angstrom]   Cy [Angstrom]   Cz [Angstrom]   Volume [Angstrom^3]
     1       0.5000        10.000000       0.000000       0.000000       0.000000      10.000000       0.000000       0.000000       0.000000      10.000000      1000.000000
     2       1.0000        10.001234       0.000000       0.000000       0.000000      10.001234       0.000000       0.000000       0.000000      10.001234      1000.370371
```

### 6.4 Parsing Cell File

```python
def parse_cp2k_cell(cell_path: Path) -> list[dict]:
    """
    Parse CP2K .cell file.

    Returns:
        List of dicts with step, time, cell vectors (A, B, C), volume.
    """
    data = []
    with open(cell_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 11:
                data.append({
                    "step": int(parts[0]),
                    "time_fs": float(parts[1]),
                    "A": [float(parts[2]), float(parts[3]), float(parts[4])],
                    "B": [float(parts[5]), float(parts[6]), float(parts[7])],
                    "C": [float(parts[8]), float(parts[9]), float(parts[10])],
                    "volume": float(parts[11]) if len(parts) > 11 else None,
                })
    return data
```

### 6.5 Fallback Strategy

If no `.cell` file is available:
1. Use cell from initial structure (static cell approximation)
2. Log a warning that cell evolution is not available
3. Mark trajectory as having static cell

---

## 7. Structure Artifact Extraction

### 7.1 For Relax Steps

Extract final structure from trajectory:

```python
def extract_final_structure_from_trajectory(
    xyz_path: Path,
    cell_path: Optional[Path] = None,
    initial_structure: Optional["Structure"] = None,
) -> Structure:
    """
    Extract final (last) frame from CP2K trajectory XYZ file.

    CP2K XYZ format (per frame):
    ```
    N
     i =        5, E =      -17.12345678
    Si        0.0000000000     0.0000000000     0.0000000000
    Si        1.3570000000     1.3570000000     1.3570000000
    ...
    ```

    Args:
        xyz_path: Path to trajectory XYZ file
        cell_path: Optional path to cell file (for cell evolution)
        initial_structure: Fallback structure for cell if no cell file

    Returns:
        Pymatgen Structure of the final frame.
    """
    # Parse all frames
    frames = parse_cp2k_xyz(xyz_path)

    # Get cell for final frame
    if cell_path and cell_path.exists():
        cell_data = parse_cp2k_cell(cell_path)
        final_cell = cell_data[-1] if cell_data else None
    else:
        final_cell = None

    # Build final structure
    final_frame = frames[-1]

    if final_cell:
        lattice = Lattice([final_cell["A"], final_cell["B"], final_cell["C"]])
    elif initial_structure:
        lattice = initial_structure.lattice
    else:
        raise ValueError("No cell information available for final structure")

    return Structure(lattice, final_frame.species, final_frame.coords, coords_are_cartesian=True)
```

### 7.2 XYZ Comment Line Parsing

CP2K uses a specific comment line format:

```python
def parse_cp2k_xyz_comment(line: str) -> dict:
    """
    Parse CP2K XYZ comment line.

    Format: ' i =        5, E =      -17.12345678'

    Returns:
        {"iteration": 5, "energy": -17.12345678}
    """
    import re

    match = re.match(r"\s*i\s*=\s*(\d+),\s*E\s*=\s*([-\d.]+)", line)
    if match:
        return {
            "iteration": int(match.group(1)),
            "energy": float(match.group(2)),
        }
    return {}
```

---

## 8. Energy Parsing

### 8.1 Energy File Format

The `.ener` file contains MD energies in tabular format:

```
#   Step   Time[fs]       Kin.[a.u.]   Temp[K]     Pot.[a.u.]   Cons Qty[a.u.]   CPU[s]
      0      0.000000    0.000000000    0.00     -17.157456789   -17.157456789    1.234
      1      0.500000    0.001234567  156.78     -17.158234567   -17.156999999    2.345
```

### 8.2 Parsing Energy File

```python
def parse_cp2k_ener(ener_path: Path) -> list[dict]:
    """
    Parse CP2K .ener file.

    Returns:
        List of dicts with step, time, kinetic, temp, potential, conserved, cpu.
    """
    data = []
    with open(ener_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 7:
                data.append({
                    "step": int(parts[0]),
                    "time_fs": float(parts[1]),
                    "kinetic_au": float(parts[2]),
                    "temp_K": float(parts[3]),
                    "potential_au": float(parts[4]),
                    "conserved_au": float(parts[5]),
                    "cpu_s": float(parts[6]),
                })
    return data
```

---

## 9. Output Log Parsing

### 9.1 Success Indicators

| Step Type | Success Pattern |
|-----------|-----------------|
| cp2k_scf | `*** SCF run converged in` |
| cp2k_relax | `*** GEOMETRY OPTIMIZATION COMPLETED ***` |
| cp2k_md | `*** MD COMPLETED ***` or energy steps match |

### 9.2 Energy Extraction from Log

```python
def parse_total_energy_from_log(log_path: Path) -> Optional[float]:
    """
    Extract total energy from CP2K output log.

    Pattern: 'ENERGY| Total FORCE_EVAL ...'
    """
    import re

    pattern = re.compile(r"ENERGY\|\s+Total FORCE_EVAL.*:\s+([-\d.]+)")
    energy = None

    with open(log_path) as f:
        for line in f:
            match = pattern.search(line)
            if match:
                energy = float(match.group(1))

    return energy  # Last match (final energy)
```

---

## 10. Runtime SSOT Clarification

### 10.1 Where Artifacts Live

**All artifact searches happen in the Runtime SSOT directory:**

```
calc/raw/<step_ulid>/    ← This is ALWAYS the search directory
```

**NEVER search in:**
```
calc/raw/scan/<variant_key>/    ← This is archive-only, for post-run analysis
```

### 10.2 Dependency Resolution

When resolving restart/wfn dependencies from a predecessor step:

```python
# CORRECT: Search in runtime SSOT
predecessor_dir = calculation.io.raw_dir / predecessor_step.meta.id
wfn_file = find_latest_wfn(predecessor_dir)

# WRONG: Never search in scan archive
# scan_dir = calculation.io.raw_dir / "scan" / variant_key / predecessor_step.meta.id
```

---

## 11. Reference Sources

- [CP2K Manual - GLOBAL Section](https://manual.cp2k.org/trunk/CP2K_INPUT/GLOBAL.html)
- [CP2K Manual - TRAJECTORY](https://manual.cp2k.org/trunk/CP2K_INPUT/MOTION/PRINT/TRAJECTORY.html)
- [CP2K Manual - CELL Print](https://manual.cp2k.org/trunk/CP2K_INPUT/MOTION/PRINT/CELL.html)
- [CP2K Output Guide (BioExcel)](https://docs.bioexcel.eu/qmmm_bpg/en/main/running_cp2k/cp2k_output.html)
- [CP2K Restarting Guide](https://www.cp2k.org/restarting)
- [CP2K pwtools Restart Guide](https://elcorto.github.io/pwtools/written/cp2k_restart.html)
- [CP2K Running Calculations (2018)](https://www.cp2k.org/_media/events:2018_summer_school:running_cp2k_calculations.pdf)
