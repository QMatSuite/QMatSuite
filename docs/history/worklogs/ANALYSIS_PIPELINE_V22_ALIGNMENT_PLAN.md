# Analysis Pipeline Spec v2.2 Alignment — Implementation Plan

**Date:** 2026-02-13
**Spec:** `docs/laws/L2/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` v2.2

## Context

The L2 spec was updated to v2.2 with multi-match semantics, three matching domains (A/B/C), explicit result states, GEN-first matching, engine effective-sequence selection, reused-skipped step inclusion, step-scoped UI enumeration, and the unified no-provider rule (runtime=non-fatal, gate=strict). The current code implements **first-match-per-type** with no result states, no Domain B step-scoped API, and SQLite/memo structures that assume one match per (run_ulid, object_type).

## Spec vs Code Gap Table

| # | Spec Requirement | Current Code | Gap |
|---|-----------------|-------------|-----|
| G1 | `enumerate_all_matches()` — sliding window, multi-match (§5.4, §5.9) | `find_contiguous_match()` returns first match only | No multi-match |
| G2 | Orchestrator uses multi-match, processes ALL instances (§4 Phase 2) | `run_post_run_analysis()` picks one match per object_type | One-per-type limit |
| G3 | Result states: OK / MISSING_EVIDENCE / PARSER_ERROR with reason (§5.5) | No enum; failures silently continue | No typed result states |
| G4 | Per-start-index longest-wins de-dup (§5.4.3) | Implicit via sorted by longest + first-match-break | Not applicable to multi-match |
| G5 | No-provider at runtime = MISSING_EVIDENCE(NO_PROVIDER), non-fatal (§2 Inv-A13, §5.5) | Provider missing → warn + continue | No typed reason |
| G6 | Gate: declared capability MUST have provider (§12.1) | Checks providers→capabilities direction only | Reverse direction missing |
| G7 | SQLite allows multiple rows per (run_ulid, object_type) (§10.4) | `UNIQUE(run_ulid, object_type)` constraint | Blocks multi-match |
| G8 | Memo cache indexed by (run_ulid, object_type, step_ulids) (§10.3) | `_analysis_index` keyed by `(run_ulid, object_type)` | Single entry per type |
| G9 | Domain B: step-scoped enumeration (§5.3-B) | No step-scoped API | No Domain B |
| G10 | Domain A: DONE list includes reused-skipped steps (§5.3-A) | Already includes "skipped" status | **Already compliant** |
| G11 | No repeated step types in capability gen_step_sequence (§5.4.6) | No validation | Missing validation |

## Implementation Steps

### Step 1-2: capability.py — enumerate_all_matches + result types
- Add `enumerate_all_matches(capabilities, ordered_gen_steps) -> list[CapabilityMatch]`
- Add `ResultState` enum (OK, MISSING_EVIDENCE, PARSER_ERROR)
- Add `MissingReason` enum (NO_PROVIDER, NO_EVIDENCE)
- Add `AnalysisResult` dataclass
- Add `__post_init__` validation: reject repeated step types

### Step 3: orchestrator.py — multi-match rewrite
- Return `List[AnalysisResult]` instead of `List[Dict[str, Any]]`
- Use `enumerate_all_matches()` instead of per-type first-match
- Each result gets exactly one of OK/MISSING_EVIDENCE/PARSER_ERROR

### Step 4: schema.py + cas_writer.py — SQLite multi-match
- Change `UNIQUE(run_ulid, object_type)` → `UNIQUE(run_ulid, object_type, match_key)`
- Update ON CONFLICT targets in cas_writer

### Step 5: service.py — memo + persist updates
- Memo key: `(run_ulid, object_type, match_key)`
- Persist loop: iterate AnalysisResult objects, only persist OK
- `_derive_canonical_for_run_object`: accept optional match_key

### Step 6: Domain B step-scoped API
- `get_analysis_instances_for_step()` in service.py
- Handler in server.py

### Steps 7-8: Gate + lock-in tests
- `test_declared_capability_has_provider()`
- `test_capability_no_repeated_gen_steps()`
- Multi-match capability tests
- Orchestrator result state tests
- SQLite multi-row test

## Files Modified

| File | Changes |
|------|---------|
| `src/qmatsuite/core/analysis/capability.py` | +enumerate_all_matches, +ResultState, +MissingReason, +AnalysisResult, +validation |
| `src/qmatsuite/core/analysis/orchestrator.py` | Rewrite to multi-match + result states |
| `src/qmatsuite/core/analysis/cas_writer.py` | Update UNIQUE conflict target |
| `src/qmatsuite/provenance/schema.py` | Change UNIQUE constraint |
| `src/qmatsuite/api/service.py` | Update memo keys, persist loop, add Domain B method |
| `src/qmatsuite/daemon/server.py` | Register new handler |
| `tests/core/analysis/test_capability.py` | Add multi-match + validation tests |
| `tests/core/analysis/test_orchestrator.py` | Adapt to AnalysisResult, add multi-match tests |
| `tests/gates/test_analysis_invariants.py` | Add gate tests |
