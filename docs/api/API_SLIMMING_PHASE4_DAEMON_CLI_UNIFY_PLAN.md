# API Slimming Phase 4: Daemon/CLI Unify Plan

**Date**: 2026-02-02
**Status**: PLANNING
**Goal**: Merge duplicate daemon/CLI operations into single canonical API capabilities

---

## 1. Overview

### 1.1 Problem Statement

The daemon (119 handlers) and CLI (31 commands) often implement the same operations with different code paths:
- Daemon: JSON-RPC handlers that call QVService methods
- CLI: Typer commands with terminal formatting, mode handling, standalone execution

This creates:
1. Duplicate code to maintain
2. Inconsistent behavior between interfaces
3. Larger API surface than necessary

### 1.2 Unification Principle

**Each operation should have ONE canonical API capability.**

| Layer | Responsibility |
|-------|---------------|
| QVService | Capability implementation (single source of truth) |
| Daemon | JSON-RPC wrapper (thin) |
| CLI | Terminal formatting + user interaction (thin) |

---

## 2. Candidate Operations (Ranked)

### 2.1 Easy (Quick Wins) - Batch 39-41

| # | Operation | Daemon Handler | CLI Command | Shared API | Delta |
|---|-----------|----------------|-------------|------------|-------|
| 1 | List Structures | `_handle_list_structures` | `list_resources` | `svc.structure.list()` | -0 (already unified) |
| 2 | List Calculations | `_handle_list_calculations` | `list_resources` | `svc.calculation.list()` | -0 (already unified) |
| 3 | Delete Structure | `_handle_delete_structure` | `delete_structure_command` | `svc.structure.delete()` | -0 (already unified) |
| 4 | Delete Calculation | `_handle_delete_calculation` | `delete_calculation_command` | `svc.calculation.delete()` | -0 (already unified) |
| 5 | Delete Step | `_handle_delete_step` | `delete_step_command` | `svc.calculation.remove_step()` | -0 (already unified) |

**Analysis**: These are already unified at API level. Both daemon and CLI call the same QVService methods. No action needed.

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
1. Both daemon and CLI import from `quantumvitas.api`
2. Both call same QVService methods
3. No duplicate logic outside API layer

**Expected Delta**: 0 (verification only)

### 3.2 Batch 40: Init Project Unification

**Current State**:
- Daemon: Calls `QVService.init_project(target_dir, name, template)`
- CLI: Same, but also supports `--snapshot` mode for template-based creation

**Action**:
1. If `--snapshot` mode uses separate logic, consider:
   - Moving snapshot logic into `QVService.init_project(snapshot=...)`
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

Looking at the audit, daemon and CLI both import from `quantumvitas.api`, so they already share:
- All DTOs
- All error types
- All QVService methods

**Finding**: The duplication is NOT in API surface - it's in internal implementation patterns.

---

## 5. Revised Strategy

### 5.1 Key Insight

The daemon/CLI unification goal was based on assumption of duplicate API entrypoints.
After investigation: **There are no true duplicate API entrypoints.**

Both consumers use the SAME API:
- `QVService.*` methods
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

The daemon/CLI unification campaign revealed that the architecture is ALREADY well-unified at the API layer. Both consumers import from `quantumvitas.api`.

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
