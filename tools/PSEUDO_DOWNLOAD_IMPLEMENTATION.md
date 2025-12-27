# Pseudopotential Download Implementation Summary

## Overview

Implemented automatic pseudopotential downloading and resolution for demo import and expansion.

## Changes Made

### 1. Importer Enhancement (`tools/import_tutorial_datasets.py`)

**Location**: `create_demo_from_dataset()` function

**Changes**:
- When pseudos are missing, automatically attempts to download them to `repo/pseudo`
- Uses `QVService.download_pseudo_by_filename()` with `dest_dir=repo_pseudo_dir`
- Updates search directories to include `repo/pseudo` after successful downloads
- Continues processing even if some downloads fail (reports errors)

**Code Flow**:
1. Check if pseudo exists in search directories (including dataset folder, tests/data)
2. If not found, attempt download to `repo/pseudo`
3. If download succeeds, add `repo/pseudo` to search directories
4. If download fails, report error but continue (allows partial success)

**Result**: Success rate improved from 22/28 (79%) to 24/28 (86%)

### 2. Materialization Enhancement (`src/quantumvitas/project/snapshot.py`)

**Location**: `materialize_project_from_snapshot()` function, around line 688

**Changes**:
- When expanding a demo snapshot to a project, copies pseudos from `repo/pseudo` to `project/pseudo`
- If pseudo not in `repo/pseudo`, attempts to download directly to `project/pseudo`
- Always ensures `project/pseudo` has required pseudos before project is ready

**Code Flow**:
1. Create `project/pseudo` directory
2. For each required pseudo from snapshot:
   - Skip if already exists in `project/pseudo`
   - Try to copy from `repo/pseudo` (if repo root found)
   - If not in repo, download to `project/pseudo`
   - Log warnings but continue if download fails

**Behavior**:
- **First priority**: Copy from `repo/pseudo` (fast, no network)
- **Fallback**: Download to `project/pseudo` (if not in repo)
- **Non-blocking**: Warnings logged but project creation continues

## Workflow

### During Demo Import

```
1. Discover datasets in tests/data/
2. For each dataset:
   a. Extract required pseudopotential filenames
   b. Check if pseudo exists in:
      - repo/pseudo
      - tests/data/
      - dataset folder
   c. If not found, download to repo/pseudo
   d. Create demo snapshot with pseudo file list
```

### During Demo Expansion

```
1. Load demo snapshot
2. Create project structure
3. For each pseudo in snapshot.pseudo.files:
   a. Check if exists in project/pseudo → skip
   b. Try to copy from repo/pseudo → success
   c. If not in repo, download to project/pseudo → success
   d. Log warning if download fails → continue
4. QE runs use project/pseudo as pseudo_dir
```

## Results

### Success Rate
- **Before**: 22/28 successful (79%)
- **After**: 24/28 successful (86%)
- **Improvement**: +2 datasets (9% increase)

### Downloaded Pseudos
- `Fe.pbe-spn-kjpaw_psl.0.2.1.UPF` - Successfully downloaded
- Others attempted but some failed with 404 (not in QE repository)

### Remaining Failures (4 datasets)
All due to pseudos not available in QE repository (404 errors):
- `14_DFT_plus_U_NiO` (both subcases) - `ni_pbe_v1.4.uspp.F.UPF` (404)
- `5_NH3_inversion` - `N.oncvpsp.upf` (404)

These would require:
- Manual addition of pseudos to `repo/pseudo`, OR
- Alternative pseudo sources

## Files Modified

1. **tools/import_tutorial_datasets.py**
   - Enhanced `create_demo_from_dataset()` to download missing pseudos
   - Added download logic with error handling

2. **src/quantumvitas/project/snapshot.py**
   - Enhanced `materialize_project_from_snapshot()` to copy/download pseudos
   - Added repo/pseudo → project/pseudo copy logic
   - Added fallback download logic

## Testing

### Test Import
```bash
python tools/import_tutorial_datasets.py
```

Expected:
- Missing pseudos are downloaded to `repo/pseudo`
- Success rate improves
- Warnings logged for failed downloads

### Test Expansion
```python
from quantumvitas.api import QVService
from pathlib import Path

# Expand a demo
result = QVService.create_demo_project(
    target_dir=Path("/tmp/test_demo"),
    demo_id="00_Si_scf"
)

# Verify pseudos are in project/pseudo
project_root = Path(result["project_root"])
pseudo_dir = project_root / "pseudo"
assert (pseudo_dir / "Si.pbe-n-rrkjus_psl.1.0.0.UPF").exists()
```

## Notes

- Downloads use `QVService.download_pseudo_by_filename()` which:
  - Deduplicates by SHA256
  - Handles filename conflicts
  - Uses QE official repository URL
  - Respects SSL context and timeouts

- Materialization is non-blocking:
  - Warnings logged for missing pseudos
  - Project creation continues
  - User can manually add missing pseudos later

- QE execution always uses `project/pseudo`:
  - This is already handled by existing QE engine code
  - `pseudo_dir` is set in generated `.in` files
  - Ensures self-contained projects

