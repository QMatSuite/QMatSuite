# Analysis Objects Design — End-to-End Implementation Plan

**Date**: 2026-02-13
**Scope**: Domain A/C (provenance/demo) e2e correctness and coverage.
Domain B (present-tense UI step-scoped API) deferred to follow-up PR.

## Context

The `ANALYSIS_OBJECTS_DESIGN.md` (design doc) defines a spec-v2.2-aligned analysis
pipeline. Core infrastructure is ALREADY implemented: `enumerate_all_matches()`,
`ResultState`/`MissingReason` enums, multi-match orchestrator, CAS writer with `match_key`.

What's missing for Domain A/C:

1. `effective_sequence` + `canonical_match_key()` (design doc Patch 3)
2. Convergence parsers for 6 engines (ORCA, Gaussian, GPAW, Psi4, PySCF, QMCPACK)
3. Convergence capability declarations for those 6 engines
4. Elimination of hardcoded `ENGINE_ANALYSIS_TYPES` dict
5. Service layer ad-hoc match_key replaced with `canonical_match_key()` calls
6. Analysis-only re-sweep tool for iterating without engine re-runs

## Steps

### Step 0: Baseline Tests
Run full test suite, record pass/fail/skip counts.

### Step 1: Full Demo Real-Run Baseline
Run all demos through engines once, preserve artifacts for re-sweep.
Create `tools/demo_store/analysis_resweep.py` for analysis-only iteration.

### Step 2: `canonical_match_key()` + `effective_sequence`
- Add `effective_sequence` to `CapabilityMatch` and `AnalysisResult`
- Add `match_key: str = ""` to `AnalysisResult`
- Add `canonical_match_key()` function
- Wire through orchestrator and service layer (replace 2 ad-hoc sites)

### Step 3: ORCA + Gaussian Convergence Parsers
- Create `drivers/orca/parsers/convergence.py`
- Create `drivers/gaussian/parsers/convergence.py`
- Add convergence capabilities to both drivers
- Tests for both

### Step 4: GPAW, Psi4, PySCF, QMCPACK Convergence
- One convergence parser per engine
- Add capabilities and register parsers
- Tests for all 4

### Step 5: Eliminate `ENGINE_ANALYSIS_TYPES`
- Replace hardcoded dict with dynamic derivation from ANALYSIS_CAPABILITIES
- Update `generate_ref_packs_realrun.py`
- Create `analysis_resweep.py`

### Step 6: Final Verification
- Full pytest run
- Smoke tests for canonical_match_key and dynamic analysis types

## Files Summary

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `tools/demo_store/analysis_resweep.py` | Analysis-only re-sweep tool |
| MODIFY | `src/quantumvitas/core/analysis/capability.py` | `effective_sequence`, `canonical_match_key()` |
| MODIFY | `src/quantumvitas/core/analysis/orchestrator.py` | Wire effective_sequence + match_key |
| MODIFY | `src/quantumvitas/api/service.py` | Replace ad-hoc match_key (2 sites) |
| CREATE | 6x `drivers/<engine>/parsers/convergence.py` | Convergence parsers |
| MODIFY | 6x `drivers/<engine>/driver.py` | Add convergence capabilities |
| MODIFY | 6x `drivers/<engine>/parsers/__init__.py` | Import convergence |
| MODIFY | `tools/demo_store/generate_ref_packs_realrun.py` | Dynamic ENGINE_ANALYSIS_TYPES |
| CREATE | Tests for all 6 convergence parsers + canonical_match_key |

## Acceptance Criteria

- `canonical_match_key()` exists and is the sole constructor of match_key values
- `effective_sequence` populated on all `CapabilityMatch` and `AnalysisResult` instances
- All 11 DFT/QC engines have convergence capability + parser (was 5, adding 6)
- `ENGINE_ANALYSIS_TYPES` eliminated (dynamic derivation)
- All existing tests pass, no regressions
- New tests cover all 6 convergence parsers + canonical_match_key
