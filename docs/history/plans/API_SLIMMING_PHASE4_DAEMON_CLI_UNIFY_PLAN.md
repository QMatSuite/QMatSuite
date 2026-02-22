# API Slimming Phase 4: Daemon/CLI Unify Plan

**Date**: 2026-02-02
**Status**: REVISED - Architecture Issue Identified
**Goal**: Ensure CLI uses API functions instead of bypassing them

---

## 1. Overview

### 1.1 Problem Statement (REVISED)

**Original assumption**: Daemon and CLI call DIFFERENT API functions for the same operation.

**Actual finding**: The API has ONE function per operation. The issue is:
- **Daemon**: Calls API functions correctly (e.g., `svc.calculation.add_step()`)
- **CLI**: BYPASSES the API and does direct file I/O (e.g., `_write_step_spec()`)

This is a **Law H1 violation** (Import Boundary) - CLI should use API, not bypass it.

### 1.2 Correct Architecture

| Layer | Should Do | CLI Currently Does |
|-------|-----------|-------------------|
| QMSService | Capability implementation | (correct) |
| Daemon | JSON-RPC wrapper → API | (correct) |
| CLI | Typer wrapper → API | **BYPASSES API** |

---

## 2. CLI API Bypass Issues (Verified)

### 2.1 Init Step / Add Step

| Consumer | What it calls | API Function |
|----------|--------------|--------------|
| Daemon | `svc.calculation.add_step()` | YES - uses API |
| CLI | `_write_step_spec()` (private helper) | NO - bypasses API |

**Evidence**: `grep -n "svc\.calculation\.add_step" src/qmatsuite/cli/main.py` returns no matches.

**CLI does instead**:
1. Manually reads `calculation.yaml`
2. Parses existing steps
3. Generates step ULID
4. Writes step.yaml file directly
5. Updates calculation.yaml directly

**Fix**: CLI should call `svc.calculation.add_step()` instead of `_write_step_spec()`.

### 2.2 Update Step Parameters

| Consumer | What it calls | API Function |
|----------|--------------|--------------|
| Daemon | `svc.calculation.update_step_params()` | YES - uses API |
| CLI | Direct YAML manipulation | NO - bypasses API |

**CLI does instead**:
1. `yaml.safe_load()` step file
2. Modifies dict in memory
3. `yaml.safe_dump()` back to file

**Fix**: CLI should call `svc.calculation.update_step_params()`.

### 2.3 Create Calculation

| Consumer | What it calls | API Function |
|----------|--------------|--------------|
| Daemon | `svc.project.init_calculation()` | YES - uses API |
| CLI | Direct file I/O + utils | NO - bypasses API |

**CLI does instead**:
1. Calls template utils (`list_calculation_templates`, `copy_calculation_template`)
2. Calls `svc.structure.require_ref()` for resolution
3. Does direct YAML manipulation
4. Calls `svc.project.update_config()` to save

**Note**: `svc.project.init_calculation()` exists but CLI doesn't use it.

**Fix**: CLI should call `svc.project.init_calculation()`.

### 2.4 Import Structure

| Consumer | What it calls | API Function |
|----------|--------------|--------------|
| Daemon | `svc.structure.import_file()` | YES - uses API |
| CLI | Direct file I/O + utils | NO - bypasses API |

**CLI does instead**:
1. Calls `read_structure()`, `write_structure()` utils
2. Generates name/slug manually
3. Does direct YAML manipulation
4. Calls `svc.project.update_config()`

**Fix**: CLI should call `svc.structure.import_file()`.

---

## 3. Analysis Functions (NOT Duplicates)

### 3.1 Band Structure Analysis

| Function | Purpose | Used By |
|----------|---------|---------|
| `analyze_band()` | Parse raw files, optionally plot | CLI |
| `get_band_structure_data()` | Retrieve cached/computed data for GUI | Daemon |

**These are COMPLEMENTARY, not duplicates**:
- `analyze_band`: GENERATE analysis (parse QE output)
- `get_band_structure_data`: RETRIEVE data (from artifact cache)

`get_band_structure_data` internally calls `ensure_analysis_artifact` which may use `analyze_band` logic.

**No unification needed** - different purposes, different output formats.

### 3.2 DOS Analysis

Same pattern:
- `analyze_dos()`: Parse raw files, optionally plot (CLI)
- `get_dos_data()`: Retrieve cached data for GUI (daemon)

**No unification needed** - complementary functions.

---

## 4. Impact on API Surface

**Key insight**: Fixing CLI to use API functions does NOT change API surface count.

The API already has the correct functions:
- `svc.calculation.add_step()` - 1 function (not 2)
- `svc.calculation.update_step_params()` - 1 function
- `svc.project.init_calculation()` - 1 function
- `svc.structure.import_file()` - 1 function

CLI refactoring is a **code quality** improvement, not an API slimming opportunity.

**Surface impact**: 0 (no API entrypoints added or removed)

---

## 5. Recommended Actions

### 5.1 CLI Refactoring (Code Quality, Not API Slimming)

| Priority | Operation | Current CLI | Fix |
|----------|-----------|-------------|-----|
| HIGH | Init Step | `_write_step_spec()` | Use `svc.calculation.add_step()` |
| HIGH | Update Step | Direct YAML | Use `svc.calculation.update_step_params()` |
| MEDIUM | Create Calculation | Direct file I/O | Use `svc.project.init_calculation()` |
| MEDIUM | Import Structure | Direct file I/O | Use `svc.structure.import_file()` |

**Note**: This work improves code consistency but doesn't reduce API surface.

### 5.2 Actual API Slimming Opportunities

From the audit, remaining opportunities are:
1. **CLI-only utils** (45 entries) - Could internalize if not needed by Jupyter/agents
2. **F401 re-exports** (4 entries) - Could remove if truly unused
3. **Bundle DTO upgrades** - Quality improvement, not count reduction

---

## 6. DEPRECATED: Original Candidate List

The following section contains the original analysis which assumed duplicate API functions.
These operations are already unified at the API level - the issue is CLI bypassing the API.

---

## 2. Candidate Operations (Ranked) [DEPRECATED]

### 2.1 Easy (Quick Wins) - Batch 39-41

| # | Operation | Daemon Handler | CLI Command | Shared API | Delta |
|---|-----------|----------------|-------------|------------|-------|
| 1 | List Structures | `_handle_list_structures` | `list_resources` | `svc.structure.list()` | -0 (already unified) |
| 2 | List Calculations | `_handle_list_calculations` | `list_resources` | `svc.calculation.list()` | -0 (already unified) |
| 3 | Delete Structure | `_handle_delete_structure` | `delete_structure_command` | `svc.structure.delete()` | -0 (already unified) |
| 4 | Delete Calculation | `_handle_delete_calculation` | `delete_calculation_command` | `svc.calculation.delete()` | -0 (already unified) |
| 5 | Delete Step | `_handle_delete_step` | `delete_step_command` | `svc.calculation.remove_step()` | -0 (already unified) |

**Analysis**: These are already unified at API level. Both daemon and CLI call the same QMSService methods. No action needed.

### 2.2 Medium (Refactor Required) - Batch 42-44

| # | Operation | Daemon Handler | CLI Command | Issue | Expected Delta |
|---|-----------|----------------|-------------|-------|----------------|
| 6 | Create Project | `_handle_create_project` | `init_project_command` | CLI has snapshot mode | -1 utils if snapshot moved |
| 7 | Import Structure | `_handle_import_structure` | `import_structure_command` | CLI does manual YAML | -0 (normalize logic) |
| 8 | Rename Operations | `_handle_rename_*` | `rename_*_command` | 4 pairs, all similar | -0 (already unified) |

### 2.3 Hard (Architecture Change) - Deferred

| # | Operation | Issue | Recommendation |
|---|-----------|-------|----------------|
| 9 | Run Calculation | Daemon uses JobManager; CLI runs inline | Keep separate for now |
| 10 | Run Step | CLI has standalone mode (no project) | Keep separate; standalone is different use case |
| 11 | Update Step Params | Daemon uses DTO; CLI manipulates YAML | Medium - needs abstraction |

---

## 3. Implementation Plan

### 3.1 Batch 39: Audit "Easy" Operations (Verify Already Unified)

**Action**: Confirm that list/delete operations truly share same code path.

**Checks**:
1. Both daemon and CLI import from `qmatsuite.api`
2. Both call same QMSService methods
3. No duplicate logic outside API layer

**Expected Delta**: 0 (verification only)

### 3.2 Batch 40: Init Project Unification

**Current State**:
- Daemon: Calls `QMSService.init_project(target_dir, name, template)`
- CLI: Same, but also supports `--snapshot` mode for template-based creation

**Action**:
1. If `--snapshot` mode uses separate logic, consider:
   - Moving snapshot logic into `QMSService.init_project(snapshot=...)`
   - OR keeping as CLI-only feature (acceptable)

**Decision**: Audit CLI snapshot implementation first.

### 3.3 Batch 41: Import Structure Normalization

**Current State**:
- Daemon: ~15 lines, uses DTO layer
- CLI: ~85 lines, includes name generation, slug collision, YAML serialization

**Issue**: CLI duplicates logic that should be in API layer.

**Action**:
1. Identify logic in CLI that belongs in `svc.structure.import_file()`
2. Move name generation / slug collision to service layer
3. CLI becomes thin wrapper

**Expected Delta**: -0 entrypoints but cleaner architecture.

---

## 4. Actual Unification Opportunities

After analysis, the REAL unification opportunities are in **utils**, not service methods:

### 4.1 Utils Functions Used Only by One Consumer

| Utils Function | Daemon Usage | CLI Usage | Action |
|----------------|--------------|-----------|--------|
| `run_input_step` | 0 | 1 | CLI-only, consider removing from API |
| `apply_card_overrides_to_qe_input` | 0 | 1 | CLI-only |
| `apply_species_overrides_to_qe_input` | 0 | 1 | CLI-only |
| `visualize_structure` | 0 | 1 | CLI-only |
| `parse_scf_output` | 0 | 1+ | CLI-only analysis |
| `plot_scf_convergence` | 0 | 1 | CLI-only visualization |

**Opportunity**: These CLI-only utils (6 functions) could be:
1. Moved to internal CLI modules (not exported from API)
2. OR kept as API for Jupyter users

### 4.2 True Duplicates (Both Daemon and CLI Export)

Looking at the audit, daemon and CLI both import from `qmatsuite.api`, so they already share:
- All DTOs
- All error types
- All QMSService methods

**Finding**: The duplication is NOT in API surface - it's in internal implementation patterns.

---

## 5. Revised Strategy

### 5.1 Key Insight

The daemon/CLI unification goal was based on assumption of duplicate API entrypoints.
After investigation: **There are no true duplicate API entrypoints.**

Both consumers use the SAME API:
- `QMSService.*` methods
- `api/utils.*` functions
- `api/dtos.*` DTOs
- `api/errors.*` errors

### 5.2 Actual Opportunities

| Opportunity | Type | Delta |
|-------------|------|-------|
| CLI-only utils → internal | Remove 6 utils from API | -6 |
| Daemon-only utils → internal | TBD (need audit) | TBD |
| Normalize CLI logic into service | Architecture | -0 |

### 5.3 Revised Implementation

**Batch 39**: Audit CLI-only utils
- Identify utils used ONLY by CLI (not daemon, not tests, not notebooks)
- Decide: Keep in API for Jupyter, or move to internal CLI module

**Batch 40**: Audit Daemon-only utils
- Identify utils used ONLY by daemon
- Decide: Keep in API, or move to internal daemon module

**Batch 41**: Move decided functions
- Net reduction from moving utils to internal modules

---

## 6. Risk Assessment

| Risk | Mitigation |
|------|------------|
| Moving utils breaks Jupyter users | Check Jupyter notebooks for usage |
| Cycle dependencies if moved | Create proper internal modules |
| Losing discoverability | Document internal alternatives |

---

## 7. Conclusion

The daemon/CLI unification campaign revealed that the architecture is ALREADY well-unified at the API layer. Both consumers import from `qmatsuite.api`.

The remaining surface reduction opportunities are:
1. **CLI-only utils** → move to internal CLI module (-6 potential)
2. **Bundle DTOs** → replace dict returns with typed DTOs (quality, not count)
3. **Future capability review** → periodic ownership audits

**Next Steps**:
1. ~~Daemon/CLI unify batches~~ → Already unified
2. Audit CLI-only utils for potential internalization
3. Implement Bundle DTOs from Phase 3 QA

---

**End of Plan**
