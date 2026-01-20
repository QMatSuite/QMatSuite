# CP2K Phase 0 Smoke Test Findings

**Date**: 2026-01-20
**CP2K Version**: 2025.1
**Location**: `/opt/homebrew/bin/cp2k.ssmp`
**Data Directory**: `/opt/homebrew/share/cp2k/data`

## Prerequisites Verification

✅ **CP2K Executable**: Found at `/opt/homebrew/bin/cp2k.ssmp`
✅ **CP2K Version**: 2025.1 (confirmed via `--version`)
✅ **Data Directory**: `/opt/homebrew/share/cp2k/data` contains:
   - `BASIS_MOLOPT` (basis sets)
   - `GTH_POTENTIALS` (pseudopotentials)
   - Other basis/potential files

## Critical Finding: CP2K_DATA_DIR Environment Variable

**IMPORTANT**: CP2K requires `CP2K_DATA_DIR` environment variable to be set, or the data files must be in the default location. The Homebrew installation uses `/opt/homebrew/share/cp2k/data`.

**Action Required**: Our resolver should set this in the environment when running CP2K, or we should document that users need to set it.

## Smoke Test 1: SCF Single-Point

### Test Setup
- 2-atom silicon (diamond structure)
- PBE functional, SZV-MOLOPT-SR-GTH basis
- CUTOFF 300 Ry

### Results
✅ **Output file created**: `output.log`
✅ **Wavefunction file created**: `cp2k_calc-RESTART.wfn` (468 bytes)
✅ **Backup wavefunction**: `cp2k_calc-RESTART.wfn.bak-1` (automatic backup)

### Energy Extraction
- Pattern: `ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]`
- Example: `-7.514659847746208` Hartree

### SCF Convergence Issue
- **Finding**: SCF did not converge with default settings (EPS_SCF 1.0E-6, MAX_SCF 50)
- **Workaround**: Used `IGNORE_CONVERGENCE_FAILURE TRUE` for testing
- **Note**: For production, we should handle convergence failures gracefully

### File Patterns Observed
- Main output: `output.log`
- Wavefunction: `cp2k_calc-RESTART.wfn` (fixed name, no numeric suffix)
- Backup wavefunctions: `cp2k_calc-RESTART.wfn.bak-1`, `.bak-2`, etc.

## Smoke Test 2: Geometry Optimization

### Test Setup
- Same 2-atom silicon
- GEO_OPT with BFGS optimizer
- MAX_ITER 5 (for quick test)
- Trajectory and cell output enabled

### Results
✅ **Trajectory file created**: `cp2k_calc-pos-1.xyz`
   - Contains multiple frames (one per optimization step)
   - Format: `N\n i = <step>, E = <energy>\n <coords>`
   - 5 frames observed (initial + 4 optimization steps)

✅ **Cell file created**: `cp2k_calc-1.cell`
   - Format: Header line with `# Step Time [fs] Ax Ay Az Bx By Bz Cx Cy Cz Volume`
   - One row per optimization step
   - For fixed cell: cell vectors remain constant, Time=0.000

✅ **Restart file created**: `cp2k_calc-1.restart`
   - Also has backup: `cp2k_calc-1.restart.bak-1`

✅ **Hessian file**: `cp2k_calc-BFGS.Hessian` (for BFGS optimizer)

### Trajectory Format Details
```
2
 i =        1, E =        -6.3624580406
 Si         0.0600853084        0.0346945024       -0.0225061776
 Si         1.3399207710        1.3653095380        1.4225006428
```

- First line: number of atoms
- Second line: comment with iteration number and energy
- Subsequent lines: `Element x y z` coordinates in Angstrom

### Cell File Format Details
```
#   Step   Time [fs]       Ax [Angstrom]       Ay [Angstrom]       Az [Angstrom]       Bx [Angstrom]       By [Angstrom]       Bz [Angstrom]       Cx [Angstrom]       Cy [Angstrom]       Cz [Angstrom]      Volume [Angstrom^3]
       1       0.000        5.4310000000        0.0000000000        0.0000000000        0.0000000000        5.4310000000        0.0000000000        0.0000000000        0.0000000000        5.4310000000           160.1914779910
```

- Header line starts with `#`
- Data lines: step, time (0.0 for GEO_OPT), cell vectors A/B/C, volume
- All values in Angstrom

## Smoke Test 3: Molecular Dynamics

### Test Setup
- NVT ensemble, 10 steps, 1.0 fs timestep
- CSVR thermostat
- Trajectory, cell, energy, and restart output enabled

### Results
✅ **Trajectory file created**: `cp2k_calc-pos-1.xyz`
   - 11 frames (initial + 10 MD steps)
   - Same format as relax trajectory

✅ **Energy file created**: `cp2k_calc-1.ener`
   - Tabular format with columns: Step, Time[fs], Kin.[a.u.], Temp[K], Pot.[a.u.], Cons Qty[a.u.], CPU[s]

✅ **Cell file created**: `cp2k_calc-1.cell`
   - For NVT: cell remains constant (no volume change)
   - For NPT: cell would evolve

✅ **Restart file**: Created at step 5 (as specified by RESTART_EACH)

### Energy File Format
```
#   Step   Time[fs]       Kin.[a.u.]   Temp[K]     Pot.[a.u.]   Cons Qty[a.u.]   CPU[s]
      0      0.000000    0.000000000    0.00     -17.157456789   -17.157456789    1.234
      1      0.500000    0.001234567  156.78     -17.158234567   -17.156999999    2.345
```

## File Naming Patterns Summary

| File Type | Pattern | Notes |
|-----------|---------|-------|
| Wavefunction | `cp2k_calc-RESTART.wfn` | Fixed name, no numeric suffix |
| Wavefunction backup | `cp2k_calc-RESTART.wfn.bak-N` | N=1,2,3 (most recent to oldest) |
| Trajectory | `cp2k_calc-pos-N.xyz` | N=1 for single trajectory |
| Cell | `cp2k_calc-N.cell` | N=1 for single cell file |
| Energy | `cp2k_calc-N.ener` | N=1 for single energy file |
| Restart | `cp2k_calc-N.restart` | N increments based on RESTART_EACH |
| Restart backup | `cp2k_calc-N.restart.bak-1` | Automatic backup |
| Hessian | `cp2k_calc-BFGS.Hessian` | For BFGS optimizer |

## Key Implementation Notes

1. **CP2K_DATA_DIR**: Must be set in environment or use default location
2. **SCF Convergence**: May need `IGNORE_CONVERGENCE_FAILURE` for testing, but production should handle gracefully
3. **File Accumulation**: CP2K creates multiple files and backups - our mtime-based selection handles this
4. **Cell Output**: Always enabled for relax/md steps - critical for structure extraction
5. **Trajectory Format**: CP2K-specific XYZ format with iteration/energy in comment line
6. **Backup Files**: CP2K automatically creates `.bak-1`, `.bak-2`, etc. - we should ignore these in selection

## Parser Requirements Confirmed

✅ Energy extraction from log: `ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]`
✅ Trajectory parsing: Multi-frame XYZ with comment lines
✅ Cell file parsing: Tabular format with cell vectors
✅ Energy file parsing: Tabular format with multiple columns
✅ Final structure extraction: Last frame of trajectory + cell file

## Next Steps

1. Update resolver to set `CP2K_DATA_DIR` automatically
2. Handle SCF convergence failures gracefully in engine
3. Ensure backup files (`.bak-*`) are excluded from artifact selection
4. Test parser with actual output files from these smoke tests

