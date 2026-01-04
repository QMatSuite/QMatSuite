# Wannier90 Diamond Job Status Report

## Files Present in raw/ Directory

Based on inspection of `/Users/kfranke/Documents/diamond-wannier90-demo/calculations/diamond-mlwfs/raw/`:

### ✅ Completed Steps

1. **SCF step** (`scf.in` → `scf.out`)
   - ✅ `scf.in` exists
   - ✅ `scf.out` exists (22KB)
   - Status: COMPLETE

2. **NSCF step** (`nscf.in` → `nscf.out`)
   - ✅ `nscf.in` exists
   - ✅ `nscf.out` exists (17KB)
   - Status: COMPLETE

3. **w90_preproc step** (`diamond.win` → `diamond.nnkp`)
   - ✅ `diamond.win` exists (1.9KB)
   - ✅ `diamond.nnkp` exists (18KB)
   - ✅ `diamond.wout` exists but contains preproc output only (ends with "Exiting... diamond.nnkp written")
   - Status: COMPLETE

### ❌ Missing Steps

4. **pw2wannier90 step** (`diamond.pw2wan` → `diamond.mmn`, `diamond.amn`, `diamond.eig`)
   - ✅ `diamond.pw2wan` exists (179B)
   - ❌ `diamond.mmn` MISSING
   - ❌ `diamond.amn` MISSING
   - ❌ `diamond.eig` MISSING
   - ❌ `diamond.pw2wan.out` MISSING (or may be named differently)
   - Status: **NOT RUN** or **FAILED**

5. **w90_run step** (`diamond.win` + `.mmn/.amn/.eig` → `diamond.wout` with Final State)
   - ❌ `diamond.wout` exists but is from preproc, not final run
   - Missing "Final State" section in `.wout`
   - Status: **NOT RUN** (cannot run without pw2wannier90 outputs)

## Expected Output Files (from Integration Test)

From `tests/integration/test_wannier90_project_execution.py`, after successful run, `raw/` should contain:

**Input files:**
- `diamond.scf`
- `diamond.nscf`
- `diamond.win`
- `diamond.pw2wan`

**Output files:**
- `diamond.scf.out`
- `diamond.nscf.out`
- `diamond.nnkp` (from w90_preproc)
- `diamond.mmn` (from pw2wannier90)
- `diamond.amn` (from pw2wannier90)
- `diamond.eig` (from pw2wannier90)
- `diamond.wout` (from w90_run, with "Final State" section)
- `diamond.chk` (optional checkpoint file)

## Expected Results (from Example5.tex Solution Booklet)

**Final Wannier Function Centers and Spreads:**
```
WF centre and spread    1  ( -0.000000,  0.000000, -0.000000 )     0.58022623
WF centre and spread    2  ( -0.806995,  0.806995,  0.000000 )     0.58022623
WF centre and spread    3  ( -0.000000,  0.806995,  0.806995 )     0.58022623
WF centre and spread    4  ( -0.806995, -0.000000,  0.806995 )     0.58022623
Sum of centres and spreads ( -1.613990,  1.613990,  1.613990 )     2.32090491

Final Spread (Ang^2)       Omega Total  =     2.320904912
```

## Issue Analysis

### pw2wannier90 Step Not Running

The `pw2wannier90` step appears to have not executed successfully. Possible causes:

1. **Errno 21 "Is a directory: '.'"** - This error suggests that somewhere in the code, the input file path for `pw2wannier90` is being resolved to `'.'` (current directory) instead of the actual file path.

2. **Step execution order** - The step may be failing silently or the error is being caught somewhere.

3. **Input file resolution** - The `diamond.pw2wan` file exists, but the step runner might not be finding it correctly.

### Verification Needed

1. Check step execution logs for `pw2wannier90` step
2. Verify `Step.input_file` is correctly set for `pw2wannier90` step
3. Confirm `resolve_input_path()` is working correctly for `.pw2wan` files
4. Check if `pw2wannier90.x` executable is being called correctly (stdin redirection)

## Next Steps

1. Fix the Errno 21 issue (likely in input file resolution for pw2wannier90)
2. Ensure pw2wannier90 step executes and produces `.mmn`, `.amn`, `.eig` files
3. Verify w90_run step can then execute with these inputs
4. Validate final results match expected values from solution booklet

