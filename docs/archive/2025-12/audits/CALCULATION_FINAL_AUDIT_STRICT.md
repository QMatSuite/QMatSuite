# Calculation Final Audit Report (Strict)

**Date**: Generated after strict final workflow → calculation cleanup  
**Purpose**: Document all remaining occurrences of "workflow" (any case) in the repository after the comprehensive strict cleanup operation.

## Search Methodology

- **Tool**: `grep -Rni "workflow" .` (case-insensitive recursive search)
- **Excluded directories**:
  - `.git/`
  - Build/cache directories: `node_modules/`, `dist/`, `build/`, `.pytest_cache/`, `venv/`, `htmlcov/`, `.coverage`
  - Binary/build artifacts: `*.asar`, `*.app/`, compiled binaries
  - `.github/workflows/` (GitHub Actions - external, whitelisted)
  - `WORKFLOW_AUDIT_REPORT.md` (historical audit - whitelisted)
  - `gui/package-lock.json` (external URLs in lockfile - whitelisted)
  - `temp/qe_docs/` (external Quantum ESPRESSO documentation - whitelisted)
  - `*.backup` files (excluded from search)

## Remaining "workflow" Occurrences

### 1. GitHub Actions Configuration and Documentation (Whitelisted)

These are explicitly external GitHub Actions references and must remain unchanged:

#### 1.1 GitHub Actions Configuration Files
- **`.github/workflows/tests.yml`**
  - Entire file: GitHub Actions workflow definition
  - Contains: `workflow_dispatch`, `workflow` in path
  - **Reason**: External GitHub Actions standard

#### 1.2 Documentation References to GitHub Actions
- **`docs/ARCHITECTURE_OVERVIEW.md`** (lines 19, 102)
  - References: `.github/workflows/` paths
  - **Reason**: Documenting GitHub Actions CI/CD structure

- **`README_TESTS.md`** (lines 94, 98, 102)
  - References: GitHub Actions workflow tests, `workflow_dispatch`
  - **Reason**: Documentation of CI/CD testing

- **`tests/SUMMARY.md`** (lines 29, 64)
  - References: `.github/workflows/` paths
  - **Reason**: Test documentation referencing CI structure

- **`tests/docs/archive/REFACTORING_COMPLETE.md`** (line 110)
  - Contains: `workflow_dispatch`
  - **Reason**: Historical documentation of GitHub Actions

- **`docs/tests_overview.md`** (line 224)
  - References: `.github/workflows/`
  - **Reason**: Test documentation

- **`docs/ci/legacy/tests.yml.before_qe_install_cache`** (line 246)
  - Contains: `workflow_dispatch`
  - **Reason**: Historical GitHub Actions config

### 2. External URLs / Third-Party Content (Whitelisted)

- **`gui/package-lock.json`**
  - Contains: URLs with `github.com` and other external references
  - **Reason**: External third-party lockfile - URLs must remain unchanged

- **`src/quantumvitas/data/qe_module_parameters*.json`**
  - Contains: External GitHub URLs
  - **Reason**: External URL references

- **`temp/qe_docs/*.html`**
  - Contains: External Quantum ESPRESSO documentation
  - **Reason**: External third-party documentation (e.g., "The workflow is just:")

### 3. Historical Audit File (Whitelisted)

- **`WORKFLOW_AUDIT_REPORT.md`**
  - Entire file: Historical audit report from before the rename
  - **Reason**: Historical record - explicitly preserved

### 4. Legacy Opaque IDs Containing WORKFLOW (Do Not Rename)

These are opaque identifiers in the DAG model that contain "WORKFLOW" as part of the ID string. These must NOT be modified, even by substring replacement, as they are treated as opaque identifiers.

**Note**: The template files have already been updated to use `01KBSIBANDSCALCULATION00001` instead of `01KBSIBANDSWORKFLOW00001`. The following are legacy IDs found in trash/deleted files or historical references:

#### 4.1 Legacy IDs in Trash/Deleted Files

These files are in `trash/` directories (deleted files) but still contain legacy IDs:

- **`manual_tests/project2_bands_kauto/trash/*.step.yaml`**
  - Contains: `parent_workflow_id: 01KBH0RGF179RD73PNKD0N8GNS` (multiple files)
  - Contains: `parent_workflow_id: 01KBH5KYPE659SWXHXQP1BXX16` (multiple files)
  - **Reason**: Legacy opaque IDs in deleted/trash files - these are historical and the IDs are treated as opaque

- **`tests/data/project_examples/project2_bands_kauto/trash/*.step.yaml`**
  - Contains: Same legacy IDs as above
  - **Reason**: Legacy opaque IDs in test data trash files

**Note**: These trash files contain legacy field names (`parent_workflow_id:`) and paths (`path: workflows/`) that reference historical deleted files. The field names have been updated to `parent_calculation_id:` and paths to `calculations/`, but the actual ID values (ULIDs) remain unchanged as they are opaque identifiers.

#### 4.2 Historical References in Documentation

- **`CALCULATION_FINAL_AUDIT.md`** (lines 107, 111)
  - References: `01KBSIBANDSWORKFLOW00001` (mentioned as example of legacy ID)
  - **Reason**: Documentation of legacy IDs - historical reference

**Summary of Legacy Opaque IDs:**
- `01KBH0RGF179RD73PNKD0N8GNS` - Found in trash files (legacy calculation ID)
- `01KBH5KYPE659SWXHXQP1BXX16` - Found in trash files (legacy calculation ID)
- `01KBSIBANDSWORKFLOW00001` - Historical reference (already updated in templates to `01KBSIBANDSCALCULATION00001`)

These IDs are treated as opaque and are not modified. The field names (`parent_workflow_id` → `parent_calculation_id`) have been updated, but the ID values themselves remain unchanged.

## GitHub/Actions + "calculation" in Documentation

After the rename, we checked for any documentation lines where "GitHub" or "Actions" appears near "calculation" to identify potentially awkward phrasing:

**Result**: No instances found where "GitHub" or "Actions" appears near "calculation" in a way that creates awkward phrasing.

All references to GitHub Actions correctly use "workflow" (external concept), and internal domain references have been successfully renamed to "calculation".

## Summary

### Total Remaining "workflow" References
- **GitHub Actions (external)**: ~15-20 occurrences (expected, whitelisted)
- **External URLs/third-party**: Variable (whitelisted)
- **Historical audit file**: 1 file (whitelisted)
- **Legacy opaque IDs**: ~15 occurrences in trash files (whitelisted - IDs are opaque)

### Internal Domain Model References
- **Core code (src/)**: ✅ Clean (0 internal references)
- **GUI code (gui/src/)**: ✅ Clean (0 internal references)
- **Test code (tests/)**: ✅ Clean (all class/function names updated)
- **Active documentation**: ✅ Clean (updated to "calculation")
- **Documentation archives**: ✅ Clean (updated to "calculation")
- **Test result files**: ✅ Clean (updated to "calculation")
- **AI_understanding.md**: ✅ Clean (updated to "calculation")
- **temporary_ai_prompts**: ✅ Clean (updated to "calculation")

### Conclusion

The strict final cleanup from "workflow" to "calculation" has been successfully completed for all internal domain model references. Remaining occurrences are:

1. **External references** (GitHub Actions) - correctly preserved
2. **External URLs/third-party content** - correctly preserved
3. **Historical audit file** - explicitly preserved
4. **Legacy opaque IDs** - correctly preserved (IDs are opaque identifiers, not modified)

The codebase is now consistent in using "calculation" for the internal domain concept throughout all active code, tests, documentation (including archives), and test outputs. All internal references have been cleaned, with only external concepts (GitHub Actions) and opaque identifiers retaining "workflow".

