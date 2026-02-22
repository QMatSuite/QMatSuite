# Post-Phase 1 Polish Stage P1 — Worklog

**Status**: Complete
**Date**: 2026-02-18

## Summary

Fixed 5 friction points discovered when a real Claude Code agent tried to
conduct an SCF calculation of silicon crystal via the MCP server.

## Fixes Implemented

### Fix 1: quick_run Crash — Wrong Import (CRITICAL)

**Problem**: `service.py:4737` imported `resolve_precision_context` from
`api.utils` (stub with wrong signature: `(structure, pseudo_library, elements)`).
The real function at `presets/precision_context.py:52` takes `(calculation_dir,
project_root, calc_model)`. Calling with `calculation_dir=` keyword → TypeError.

**Fix**:
- `service.py:4737`: Import `resolve_precision_context` directly from
  `presets.precision_context` instead of `api.utils`
- `api/utils.py:2031`: Fixed stub to match real signature — passthrough delegate
  with `(calculation_dir, project_root=None, calc_model=None)`

### Fix 2: CIF Import Error Message (MEDIUM)

**Problem**: `structure_io.py:111-115`: generic `except Exception` catches CIF
parse error, falls through to `PMGMolecule.from_file()` which gives misleading
"Cannot determine file type". The real error ("Invalid CIF file") was swallowed.

**Fix**: Chain exceptions so when both parsers fail, the Structure error
(informative) is raised with the Molecule error as context:
```python
except Exception as struct_err:
    try:
        return PMGMolecule.from_file(str(filepath))
    except Exception as mol_err:
        raise struct_err from mol_err
```

### Fix 3: set_species_map MCP Tool (CRITICAL)

**Problem**: `species_map` is required for QE/ABINIT/Siesta/VASP but
`create_calculation` and `quick_run` never set it. No MCP tool exposed it.

**Fix**:
- Created `mcp/tools/set_species_map.py` — validates species_map entries
  (non-empty, each has `pseudopot` key), calls `svc.calculation.update_species_map()`
- Updated `create_calculation.py` context_hint to mention `set_species_map`
- Added `species_map: dict | None = None` parameter to `quick_run`
- Wired in `server.py` as Stage 2 configuration tool

### Fix 4: init_project MCP Tool (LOW)

**Problem**: `QMSService.init_project()` exists but no MCP tool wraps it.
Agent couldn't create a project through the MCP interface.

**Fix**: Created `mcp/tools/init_project.py` — creates project, then calls
`set_project_root()` to point MCP session at new project. Validates that
target path is not inside an existing project.

### Fix 5: QE Si SCF Demo — NO CODE CHANGE

Demo exists at `qe_si_scf.yml` and works correctly. Agent usage issue.

## Files Changed

| File | Action |
|------|--------|
| `src/qmatsuite/api/service.py` | Fixed import at L4737 |
| `src/qmatsuite/api/utils.py` | Fixed stub signature at L2031 |
| `src/qmatsuite/io/structure_io.py` | Fixed error chain at L109 |
| `src/qmatsuite/mcp/tools/set_species_map.py` | Created |
| `src/qmatsuite/mcp/tools/init_project.py` | Created |
| `src/qmatsuite/mcp/server.py` | Added 2 imports |
| `src/qmatsuite/mcp/tools/create_calculation.py` | Updated context_hint |
| `src/qmatsuite/mcp/tools/quick_run.py` | Added species_map param |
| `tests/mcp/test_stage_p1.py` | Created (11 tests) |
| `tests/mcp/test_stage11.py` | Updated tool count 22→24 |

## Test Results

- Stage P1 tests: **11/11 passed**
- All MCP tests: **350/350 passed**
- Full suite: **6010 passed, 4 skipped, 0 failed**

Tool count: 22 → 24 (+init_project, +set_species_map)
