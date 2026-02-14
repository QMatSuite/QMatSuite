# AnalysisObject Spec Reconciliation Review

**Date**: 2026-02-13
**Status**: Research Review (non-binding)
**Author**: Claude Code (automated spec archaeology)

---

## Executive Summary

The AnalysisObject system — QMatSuite's engine-agnostic analysis pipeline — is governed by a hierarchy of documents spanning L2 binding specs, design docs, open questions, and historical audits. This review enumerates **all** repo documents touching AnalysisObject semantics, classifies them by normative level, and answers five specific questions (A–E) about enumeration semantics, sequence constraints, missing taxonomy, multi-engine calculations, and type taxonomy.

**Key finding**: There is a **critical inconsistency** between the L2 binding spec and the design doc on multi-match enumeration semantics:

- **L2 SPEC** (`ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` §5.3, line 480): "Each capability produces **at most one** canonical bundle per run."
- **DESIGN DOC** (`ANALYSIS_OBJECTS_DESIGN.md` §1.1, line 26): "Core rule: ALL matches, not first match."
- **CODE** (`orchestrator.py` lines 42–63): Implements first-match-per-type (one result per `object_type`).

By governance hierarchy, **L2 wins**. The design doc's "all matches" rule is aspirational but non-binding. However, the design doc explicitly calls the current code a "spec violation" (§2.1, line 140), creating confusion about intended behavior. This must be resolved by either (a) updating the L2 spec to mandate all-matches, or (b) updating the design doc to align with the L2 spec's at-most-one rule.

Five additional **spec gaps** are identified: bandspw→bands adjacency semantics, runtime-fail scenarios for malformed sequences, multi-engine analysis dispatch, type taxonomy merge policy, and the enumeration ordinal assignment contract.

---

## 1. Document Inventory

### 1.1 Binding Documents (L1/L2)

| # | Document | Path | Normative Level | Version | Key AnalysisObject Content |
|---|----------|------|-----------------|---------|---------------------------|
| 1 | AnalysisObject Primitives Spec | `docs/laws/L2/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` | **L2 BINDING** | v1.5 | 14 invariants (Inv-A1–A14), data model (§6), post-run pipeline (§4), capability matching (§5), gate tests (§12) |
| 2 | Analysis Pipeline Playbook | `docs/laws/L2/ANALYSIS_PIPELINE_PLAYBOOK.md` | **L2 SOP** | — | Triangle pattern (driver→@register_parser→orchestrator), Recipe A/B, DO NOT MODIFY files, engine×analysis matrix |
| 3 | Calc Type System Kind Spec | `docs/laws/L2/CALC_TYPE_SYSTEM_KIND_SPEC.md` | **L2 BINDING** | v1.0 | `engine_group` immutability per calculation — constrains analysis dispatch to single engine |
| 4 | Step Type GEN/SPEC Constitution | `docs/laws/L1/STEP_TYPE_GEN_SPEC_CONSTITUTION.md` | **L1 FINAL** | v1.1 | GEN step registry as SSOT — analysis capabilities are defined over GEN step sequences |

### 1.2 Design Documents (non-binding)

| # | Document | Path | Status | Key AnalysisObject Content |
|---|----------|------|--------|---------------------------|
| 5 | Analysis Objects Design | `docs/design/ANALYSIS_OBJECTS_DESIGN.md` | Design | Enumeration algorithm (§1.2), root cause taxonomy (§3), capability matrix (§4), demo diagnosis (§5), type taxonomy (§6), action plan (§7) |
| 6 | Trajectory Analysis Design | `docs/design/TRAJECTORY_ANALYSIS_DESIGN.md` | Design | Trajectory-specific design; frame model, convergence subobject |
| 7 | VASP Analysis Design | `docs/design/VASP_ANALYSIS_DESIGN.md` | Design | VASP-specific analysis pipeline design |

### 1.3 History/Progress Artifacts

| # | Document | Path | Type | Key AnalysisObject Content |
|---|----------|------|------|---------------------------|
| 8 | Analysis Pipeline Review | `docs/history/audits/ANALYSIS_PIPELINE_REVIEW.md` | Audit (2026-02-10) | Spec compliance matrix (13/14 PASS, 1 PARTIAL for CAS tier) |
| 9 | Analysis Pipeline Next Plan | `docs/history/worklogs/ANALYSIS_PIPELINE_NEXT_PLAN.md` | Plan | Step G3 proposes `test_no_redundant_canonical` gate test |
| 10 | Analysis Pipeline Phase 2 Acceptance | `docs/history/worklogs/ANALYSIS_PIPELINE_PHASE2_ACCEPTANCE_REVIEW.md` | Acceptance | Phase 2 review with `test_no_redundant_canonical` results |
| 11 | Analysis Pipeline Acceptance | `docs/history/worklogs/ANALYSIS_PIPELINE_ACCEPTANCE_REVIEW.md` | Acceptance | Earlier acceptance review |
| 12 | Analysis Objects Open Questions | `docs/history/dev-notes/ANALYSIS_OBJECTS_OPEN_QUESTIONS.md` | Living doc (2026-01-19) | 13 open questions (performance, robustness, extensibility) |
| 13 | Analysis Objects Design (history) | `docs/design/ANALYSIS_OBJECTS_DESIGN.md` | Design | Note: also listed under 1.2; references retired ANALYSIS_OBJECTS_FRAMEWORK.md |
| 14 | Analysis Visualization Architecture Audit | `docs/history/audits/ANALYSIS_VISUALIZATION_ARCHITECTURE_AUDIT.md` | Audit | Visualization arch review |
| 15 | Analysis Pipeline Playbook Review | `docs/history/audits/B1_ENGINE_PLAYBOOK_REVIEW.md` | Audit | Includes analysis pipeline coverage notes |

### 1.4 Code (SSOT for behavior)

| # | File | Path | Role |
|---|------|------|------|
| 16 | capability.py | `src/quantumvitas/core/analysis/capability.py` | `AnalysisCapability` dataclass, `find_contiguous_match()` — the matching primitive |
| 17 | orchestrator.py | `src/quantumvitas/core/analysis/orchestrator.py` | `run_post_run_analysis()` — the dispatch loop (first-match-per-type) |
| 18 | Driver capabilities | `src/quantumvitas/drivers/*/driver.py` | `ANALYSIS_CAPABILITIES` class attribute (13 engines declare; QMCPACK + Yambo = empty) |
| 19 | Gate tests | `tests/gates/test_analysis_invariants.py` | 109 gate tests enforcing Inv-A1–A14, §5.2/§5.3 |
| 20 | Capability tests | `tests/core/analysis/test_capability.py` | 8 unit tests for `find_contiguous_match()` |
| 21 | Orchestrator tests | `tests/core/analysis/test_orchestrator.py` | ~10 tests for `run_post_run_analysis()` |

---

## 2. Rule-by-Rule Reconciliation

### Question A: Enumeration Semantics

**Question**: Where is the authoritative rule for multi-match enumeration — does a capability match ALL occurrences or only the first? Is it L1, L2, or design-only?

#### Source 1: L2 SPEC (BINDING)

`docs/laws/L2/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md`

- **§5.3, line 480**: "Each capability produces **at most one** canonical bundle per run. If the same sequence could match in multiple positions, the implementation MUST use a deterministic tie-breaking rule (e.g., prefer the first occurrence)."
- **§5.5, line 561**: "prefer longest match first, then stable declaration order" — described as a "Suggestion" with "Implementer freedom."
- **§12.1, line 1072**: Gate test `test_no_redundant_canonical`: "A run with GEN steps `[bandspw, bands]` and a capability `["bandspw", "bands"]` produces exactly ONE canonical bands bundle, not two."
- **§12.2, line 1096**: Behavioral criterion #11: "A run with GEN steps `[scf, bandspw, bands]` and a bands capability `["bandspw", "bands"]` MUST NOT produce two separate bands analyses for bandspw and bands. Exactly one bands canonical bundle is produced."

**L2 verdict**: At most one canonical bundle per capability per run. First occurrence is the preferred tie-break.

#### Source 2: DESIGN DOC (non-binding)

`docs/design/ANALYSIS_OBJECTS_DESIGN.md`

- **§1.1, line 22**: "**Enumeration** is the act of computing ALL expected analysis instances for a calculation."
- **§1.1, line 26**: "**Core rule: ALL matches, not first match.** The same AnalysisObject type can match multiple times in a single calculation."
- **§1.1, lines 29–42**: Normative example: `[scf, scf, scf]` + capability `convergence → ["scf"]` → **3 Convergence instances**.
- **§1.2, lines 44–103**: Full `enumerate_expected_instances()` algorithm: iterates every `start_idx`, collects all matches, applies per-start-index longest-wins, emits one instance per object_type per start index.
- **§2.1, line 140**: "The current orchestrator implements **first-match-per-type** semantics, which **VIOLATES** the all-matches spec."

**Design verdict**: ALL matches, with per-start-index longest-wins de-duplication. Explicitly contradicts L2 §5.3.

#### Source 3: CODE (actual behavior)

`src/quantumvitas/core/analysis/orchestrator.py`, lines 42–63:

```python
# Deterministic capability resolution:
# - Evaluate one match per object_type
# - Prefer longest contiguous sequence, then declaration order
capabilities_by_type: Dict[str, List[Tuple[int, Any]]] = {}
...
for object_type in type_order:
    ranked = sorted(
        capabilities_by_type[object_type],
        key=lambda row: (-len(row[1].gen_step_sequence), row[0]),
    )
    for _, candidate in ranked:
        candidate_match = find_contiguous_match(candidate, ordered_gen_steps)
        if candidate_match is not None:
            selected_capability = candidate
            selected_match = candidate_match
            break  # ← ONE result per object_type
```

`src/quantumvitas/core/analysis/capability.py`, lines 50–58:

```python
for start in range(0, len(ordered_gen_steps) - n_required + 1):
    window = ordered_gen_steps[start : start + n_required]
    if all(window[index][1] == sequence[index] for index in range(n_required)):
        return CapabilityMatch(...)  # ← returns FIRST match, early return
```

**Code verdict**: First-match-per-type. One result per `object_type`, longest capability tried first, first contiguous match wins.

#### Source 4: TESTS (behavioral contract)

`tests/core/analysis/test_capability.py`:
- `test_first_occurrence_wins_when_ambiguous()` (line 62): Tests that `[scf, relax, scf]` + capability `["scf"]` returns the FIRST scf (at index 0).
- `test_overlapping_matches_allowed_across_capabilities()` (line 79): Tests that DIFFERENT `object_type` values can match overlapping steps independently.

`tests/gates/test_analysis_invariants.py`:
- `test_no_redundant_canonical()` (line 375): Tests that overlapping capabilities `["bandspw"]` and `["scf", "bandspw"]` produce ONE bands bundle.

**Tests verdict**: Consistent with code (first-match-per-type) and L2 spec (at most one per capability per run).

#### RECONCILIATION VERDICT (A)

| Source | Rule | Normative Level |
|--------|------|-----------------|
| L2 SPEC §5.3 | At most one per capability per run; prefer first occurrence | **BINDING** |
| DESIGN §1.1 | ALL matches across all start indices | Non-binding |
| CODE | First-match-per-type (one per object_type) | Implementation |
| TESTS | Consistent with code / L2 spec | Enforcement |

**Status**: **INCONSISTENT**. L2 spec and code agree on "at most one." Design doc says "ALL matches" and calls the code a "spec violation." By governance hierarchy, L2 wins.

**Recommended resolution**: Either:
- **(A-opt-1)** Update the design doc §1.1/§2.1 to align with L2 §5.3 ("at most one" is the intended production rule; "all matches" is a future consideration to be proposed as a spec amendment).
- **(A-opt-2)** Propose an L2 spec amendment to adopt the all-matches semantics from the design doc. This would require updating the orchestrator, adding ordinal assignment, and reworking the `test_no_redundant_canonical` gate test.

**Impact assessment**: Option A-opt-1 is low-risk (editorial only). Option A-opt-2 is high-impact: it changes behavior for calculations with repeated GEN steps (e.g., `[scf, scf, scf]`), but no current demo exercises this pattern.

---

### Question B: Sequence Constraints and Adjacency

**Question**: Does the spec define what happens with `scf-bandspw-bands-bandspw-bands` (two bands objects)? Is `scf-bands-bandspw-bands` a runtime failure or silent skip? Where is the "artifact producer adjacency" rule?

#### B.1 Contiguous subsequence matching

**L2 SPEC** §5.3, line 479: "A capability matches if its `gen_step_sequence` appears as a **contiguous subsequence** of the run's ordered GEN step list."

This is the ONLY matching rule. There is no "adjacency" concept beyond contiguity. A capability `["bandspw", "bands"]` matches wherever the literal sequence `bandspw` followed immediately by `bands` appears in the GEN step list.

#### B.2 Example: `scf-bandspw-bands-bandspw-bands`

Under current semantics (L2 §5.3, at-most-one):
- Capability `bands → ["bandspw", "bands"]` matches at index 1 (first occurrence) → exactly ONE bands bundle.
- The second `bandspw-bands` at indices 3–4 is **silently ignored** (no match attempt beyond first hit).

Under design doc semantics (all-matches):
- Match at index 1 → Bands instance #0 covering `[1, 3)`
- Match at index 3 → Bands instance #1 covering `[3, 5)`
- Result: **TWO** bands bundles.

**Neither scenario is explicitly documented.** The specific example `scf-bandspw-bands-bandspw-bands` does not appear in any spec, design doc, or test.

#### B.3 Example: `scf-bands-bandspw-bands` (malformed sequence)

- Capability `bands → ["bandspw", "bands"]` checks for contiguous `bandspw` then `bands`. At index 1, gen step is `bands` (not `bandspw`) → no match. At index 2, gen step is `bandspw` followed by `bands` → match at index 2.
- Under at-most-one: ONE bands bundle from indices 2–3.
- Under all-matches: Same result (only one contiguous match exists).
- The lone `bands` step at index 1 is **silently skipped** — no capability matches gen sequence `["bands"]` alone. This is not a runtime failure; it's a non-match. No error, no warning.

**This scenario is NOT documented anywhere.** It is a natural consequence of the contiguous subsequence rule but is not called out as a test case or acceptance criterion.

#### B.4 "Artifact producer adjacency"

No document uses the phrase "artifact producer adjacency." The concept is implicit: `bandspw` produces the k-point eigenvalue evidence; `bands` post-processes it. The capability `["bandspw", "bands"]` encodes this as a contiguous sequence requirement, but the spec does not explain *why* these steps must be contiguous or what happens if they are separated by other steps.

#### RECONCILIATION VERDICT (B)

| Scenario | Documented? | Where? | Behavior |
|----------|:-----------:|--------|----------|
| Repeated match (`A-B-A-B`) | **No** | — | At-most-one: first match only. All-matches: two instances. |
| Malformed sequence (`scf-bands-bandspw-bands`) | **No** | — | Silent skip of lone `bands`; match at later index. Not a runtime error. |
| Adjacency rationale | **No** | — | Implicit in contiguous subsequence rule. No explicit justification. |
| Contiguous subsequence rule | **Yes** | L2 SPEC §5.3 line 479 | BINDING |

**Spec gaps**:
- **B-gap-1**: No test or acceptance criterion for repeated GEN step patterns (e.g., `bandspw-bands-bandspw-bands`).
- **B-gap-2**: No documentation of the silent-skip behavior for non-matching step subsequences.
- **B-gap-3**: No rationale for why certain step pairs must be contiguous (the physics of `bandspw→bands` as an artifact producer/consumer chain).

**Recommended patch**: Add a subsection to L2 SPEC §5.3 titled "Worked Examples" covering both scenarios above. Add at least one test case for a repeated capability pattern.

---

### Question C: Missing Taxonomy — "Capability Undeclared" vs "Instance Missing"

**Question**: What is the taxonomy for missing analysis instances? Is "capability undeclared" (engine doesn't declare the capability) distinct from "instance missing" (capability declared but parse failed)?

#### C.1 Design doc taxonomy (non-binding)

`docs/design/ANALYSIS_OBJECTS_DESIGN.md` §3, lines 144–166:

| Category | Name | Meaning |
|----------|------|---------|
| **A** | Expected capability not declared | Engine COULD produce the analysis, but no `AnalysisCapability` entry exists in `ANALYSIS_CAPABILITIES` |
| **B1** | Evidence missing | Capability declared, match found, but `can_parse()` returns False (evidence files absent) |
| **B2** | Parser failed | Capability declared, match found, evidence present, but `parse()` raises an exception |
| **C** | Sweep tool gap | The demo sweep tool doesn't probe this type due to hardcoded `ENGINE_ANALYSIS_TYPES` |

#### C.2 L2 spec taxonomy

The L2 spec does NOT define a root cause taxonomy. Relevant statements:

- **§5.3, line 482**: "Unmatched capabilities are silently skipped (the run simply lacks those analysis types)."
- **§5.4, line 498**: `can_parse()` returns a boolean; no error taxonomy.
- **§5.5**: No mention of failure categories.

The L2 spec's approach is binary: a capability either produces a canonical bundle or doesn't. There is no formalized A/B/C taxonomy at the L2 level.

#### C.3 Code behavior

`orchestrator.py`:
- Line 69–73: If `get_parser()` returns None → `warnings.warn()`, continue (silent skip).
- Line 78–79: If `can_parse()` returns False → continue (silent skip, no warning).
- Line 105–110: If `parse()` raises → `warnings.warn()`, continue (silent skip).

All three failure modes result in the same observable behavior: no result for that capability. The code does not distinguish or log different failure categories.

#### RECONCILIATION VERDICT (C)

| Taxonomy | Defined? | Where? | Level |
|----------|:--------:|--------|-------|
| A/B/C root cause categories | **Yes** | Design doc §3 | Non-binding |
| Binary pass/fail | **Yes** | L2 SPEC §5.3–§5.5 | BINDING |
| Structured failure logging | **No** | — | Not implemented |

**Status**: The design doc's taxonomy is well-thought-out and useful for debugging, but it is NOT binding. The L2 spec intentionally takes a simpler approach (binary pass/fail with silent skip).

**Spec gap**: **C-gap-1**: No binding requirement to log or categorize analysis failures. The current code warns on parser-not-found and parse-exception but silently skips `can_parse()=False`. A diagnostics requirement (e.g., "the orchestrator MUST log each skipped capability with a reason code") would aid debugging but is not currently mandated.

**Recommended patch**: Promote the A/B taxonomy to L2 as an optional diagnostics contract (not a hard failure). Category C is a tooling concern, not a spec concern.

---

### Question D: Multi-Engine Calculations

**Question**: How does the analysis pipeline handle calculations that span multiple engines (e.g., QE→Wannier90, QE→Yambo)?

#### D.1 Engine group immutability

`docs/laws/L2/CALC_TYPE_SYSTEM_KIND_SPEC.md`:
- `engine_group` is **immutable** per calculation. Once set, it cannot change.
- A calculation belongs to exactly one engine group.

#### D.2 Orchestrator dispatch

`orchestrator.py` line 37: `capabilities = getattr(driver, "ANALYSIS_CAPABILITIES", [])` — capabilities come from ONE driver. The `engine` parameter is a single string, not a list.

The orchestrator is called once per engine per run. There is no mechanism to merge capabilities across engines within a single calculation.

#### D.3 Cross-engine workflows

QE→Wannier90 and QE→Yambo are **composite pipelines**: multiple calculations that are sequenced by the user, not a single multi-engine calculation. Each calculation has its own engine group.

- QE produces DFT data (SCF, NSCF).
- Wannier90/Yambo consumes DFT data as input.
- Analysis is run independently for each calculation's engine.

#### D.4 What IS documented

No document explicitly addresses multi-engine analysis dispatch. The closest references:

- **L2 SPEC §5.4, line 505**: "For multi-step capabilities: `context['evidence_steps']` = ordered list of all matched steps." — This covers multi-STEP within one engine, not multi-ENGINE.
- **Design doc §4.1**: Capability matrix is per-engine. No cross-engine capabilities.
- **CONSTITUTION §17**: Engine integration is per-engine; no cross-engine composition rules.

#### RECONCILIATION VERDICT (D)

| Aspect | Documented? | Where? | Level |
|--------|:-----------:|--------|-------|
| engine_group immutability | **Yes** | CALC_TYPE_SYSTEM_KIND_SPEC | L2 BINDING |
| Single-engine dispatch | **Implicit** | orchestrator.py code | Implementation |
| Cross-engine analysis | **No** | — | Not addressed |
| Composite pipeline analysis | **No** | — | Not addressed |

**Status**: Multi-engine analysis dispatch is a **spec gap**. The current design inherently handles it by treating each calculation as single-engine, but there is no explicit statement about:
- Whether a future cross-engine capability is permitted (e.g., `bands` capability that consumes both QE NSCF and Wannier90 interpolation).
- How composite pipeline analysis correlation works (e.g., comparing QE DFT bands with Wannier90 interpolated bands).

**Recommended patch**: Add a brief paragraph to L2 SPEC §5 stating: "Analysis dispatch is per-calculation and per-engine. Cross-engine analysis correlation (comparing results across calculations) is a frontend concern, not an orchestrator concern." This makes the single-engine assumption explicit.

---

### Question E: Type Taxonomy and Merge Policy

**Question**: What is the canonical type taxonomy for AnalysisObjects? Is there an L1/L2-level merge policy for when types should be consolidated?

#### E.1 Current types in code

From `ANALYSIS_CAPABILITIES` declarations across 13 engine drivers:

| # | object_type | Engines declaring it |
|---|-------------|---------------------|
| 1 | `convergence` | QE, VASP, ABINIT, CP2K, Siesta |
| 2 | `bands` | QE, VASP, ABINIT, CP2K, Siesta, GPAW |
| 3 | `dos` | QE, VASP, ABINIT, CP2K, Siesta, GPAW |
| 4 | `trajectory` | QE, VASP, ABINIT, CP2K, Siesta, GPAW, LAMMPS, xTB, ORCA, Gaussian, Psi4, PySCF |
| 5 | `field3d` | QE, VASP, ABINIT, CP2K, Siesta, GPAW, ORCA, Gaussian, Psi4, PySCF, W90 |
| 6 | `neb_trajectory` | QE |

**Total in production**: 6 types.

#### E.2 Design doc proposed taxonomy

`docs/design/ANALYSIS_OBJECTS_DESIGN.md` §6 (lines 301–362):

Proposes **9 types** (6 existing + 3 new):

| # | Type | New? | Absorbs |
|---|------|:----:|---------|
| 1 | `convergence` | Exists | — |
| 2 | `bands` | Exists | phonon_bands (via `meta.kind`), GW bands |
| 3 | `dos` | Exists | phonon_dos (via `meta.kind`) |
| 4 | `trajectory` | Exists | NEB path (via `meta.kind="neb"`), scan, MD |
| 5 | `field3d` | Exists | — |
| 6 | `spectrum` | **New** | optical, TDDFT, IR, Raman, EELS |
| 7 | `scalar_report` | **New** | thermochemistry, molecular props, elastic, dielectric |
| 8 | `qmc_sample` | **New** | QMC block-averaged statistics |
| 9 | `gw_correction` | **New** | Quasiparticle corrections |

Merge rules use `meta.kind` as discriminator (§6.4, lines 335–349).

Decision criteria (§6.3, lines 325–331): "A merge is justified when (a) data shapes are structurally identical, (b) `to_primitives()` uses the same primitive types, and (c) the renderer can handle both sub-kinds with only a `meta.kind` switch."

#### E.3 L2 spec on types

The L2 SPEC does not enumerate or restrict valid `object_type` values. Relevant statements:

- **§5.2**: `AnalysisCapability.object_type` is a `str`. No enumeration of valid values.
- **§6.1**: `AnalysisObjectMeta.object_type` is `str`. Values shown in examples: `"trajectory"`, `"dos"`, `"bands"`, `"scf"`.
- **§2, Inv-A13**: "No engine-conditional logic" — types must be engine-agnostic, but no constraint on which types exist.

There is **no L1 or L2 type registry**. The set of valid types is implicitly defined by what engine drivers declare in `ANALYSIS_CAPABILITIES` and what parsers are registered via `@register_parser`.

#### E.4 Merge policy

No L1 or L2 document defines a merge policy. The design doc's criteria (§6.3) are the only documented guidance, but they are non-binding.

The existing `neb_trajectory` → `trajectory` merge is implemented in code (QE's `ANALYSIS_CAPABILITIES` includes `neb_trajectory` as a separate `object_type`; it uses `Trajectory` with `meta.kind="neb"`). This is a de facto convention, not a spec-mandated pattern.

#### RECONCILIATION VERDICT (E)

| Aspect | Documented? | Where? | Level |
|--------|:-----------:|--------|-------|
| Current type set (6 types) | **Implicit** | Driver `ANALYSIS_CAPABILITIES` | Code (SSOT) |
| Proposed type set (9 types) | **Yes** | Design doc §6 | Non-binding |
| Merge criteria | **Yes** | Design doc §6.3 | Non-binding |
| `meta.kind` discriminator | **Yes** | Design doc §6.4 | Non-binding |
| L2 type registry | **No** | — | Not defined |

**Status**: **SPEC GAP**. There is no binding type registry or merge policy. The type set is purely emergent from what drivers declare.

**Recommended patch**: Add a type enumeration to L2 SPEC §5 as a "known types" reference table (informational, not restrictive). Adding new types should remain open (the spec should not enumerate all allowed types), but documenting the current 6 + any merge conventions (e.g., `meta.kind` pattern) at L2 level would reduce ambiguity.

---

## 3. Gap Summary and Patch Proposals

### 3.1 Gaps Identified

| ID | Gap | Severity | Location |
|----|-----|----------|----------|
| **A-gap** | L2 spec vs design doc contradiction on multi-match enumeration | **HIGH** | L2 §5.3 vs Design §1.1 |
| **B-gap-1** | No test for repeated GEN step patterns | MEDIUM | Tests |
| **B-gap-2** | No documentation of silent-skip behavior | LOW | L2 SPEC §5.3 |
| **B-gap-3** | No adjacency rationale | LOW | L2 SPEC §5.3 or Design |
| **C-gap-1** | No binding diagnostics contract for skipped capabilities | LOW | L2 SPEC §5 |
| **D-gap** | No explicit single-engine assumption statement | MEDIUM | L2 SPEC §5 |
| **E-gap** | No binding type registry or merge policy | MEDIUM | L2 SPEC §5 or new §5.x |

### 3.2 Recommended Patches

**Patch 1 (HIGH priority): Resolve A-gap — enumeration semantics**

Option A-opt-1 (recommended for now): Add a note to the design doc §1.1 acknowledging that the "all matches" rule is a *proposed future enhancement*, not current binding policy. Update §2.1 to remove "spec violation" language and instead say "the current implementation follows L2 §5.3 at-most-one semantics; §1.1 describes a proposed extension."

Option A-opt-2 (for later): If multi-match is desired, propose a formal L2 amendment with:
- Updated §5.3 text
- `enumerate_expected_instances()` algorithm promoted to spec
- Ordinal assignment contract
- Updated `test_no_redundant_canonical` to test multi-match scenarios
- Impact analysis on existing demos

**Patch 2 (MEDIUM priority): Add worked examples to L2 SPEC**

Add a new §5.3.1 "Worked Examples" covering:
- Single match: `[scf, bandspw, bands]` + `bands→["bandspw","bands"]` → 1 bands bundle
- Non-match: `[scf, bands, bandspw, bands]` + `bands→["bandspw","bands"]` → 1 bands bundle (from indices 2–3)
- Repeated steps: `[scf, scf, scf]` + `convergence→["scf"]` → 1 convergence bundle (under at-most-one)

**Patch 3 (MEDIUM priority): Add single-engine statement**

Add to L2 SPEC §5.3: "The post-run analysis orchestrator operates within a single engine context. Cross-engine analysis correlation is not an orchestrator responsibility."

**Patch 4 (LOW priority): Add known-types table**

Add to L2 SPEC §5.2 or new §5.2.1:

```
Known object_type values (as of v1.6):
  convergence, bands, dos, trajectory, field3d, neb_trajectory

The meta.kind field within AnalysisObjectMeta may be used to distinguish
sub-kinds within a type (e.g., trajectory with meta.kind="neb").
New types may be added by engine drivers without spec amendment.
```

**Patch 5 (LOW priority): Add diagnostics guidance**

Add to L2 SPEC §5.5 or new §5.5.1: "Implementations SHOULD log each skipped capability with a reason category: (a) no parser registered, (b) `can_parse()` returned False, (c) `parse()` raised an exception."

---

## 4. Recommended Document Re-Organization

The current document landscape is adequate but has one structural issue: the design doc (`ANALYSIS_OBJECTS_DESIGN.md`) contains both aspirational rules (§1.1 all-matches) and factual content (§3 taxonomy, §4 capability matrix, §5 demo diagnoses). Readers may confuse aspirational design with binding spec.

### Recommended actions:

1. **ANALYSIS_OBJECTS_DESIGN.md §2.1**: Replace "spec violation" language with "proposed extension beyond current L2 semantics." This is the single highest-impact editorial change.

2. **ANALYSIS_OBJECTS_OPEN_QUESTIONS.md**: Add a new question (#14) about multi-match enumeration: "Should the L2 spec adopt all-matches semantics? What demos would exercise this? What is the migration path?"

3. **L2 SPEC**: Apply patches 2–5 above at the next version bump (v1.6).

4. **No new documents needed**: The existing L2 spec + design doc + open questions doc cover all necessary content. The issue is not missing documents but contradictory content between documents of different normative levels.

---

## 5. Answer to Success Criterion

> "After reading this review, one can answer: Where is the authoritative rule for multi-match enumeration and for bandspw→bands adjacency, and is it L1/L2/design?"

**Multi-match enumeration**: The authoritative rule is in **L2 SPEC** (`docs/laws/L2/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md`) §5.3, line 480: "at most one canonical bundle per run per capability." This is **BINDING**. The design doc's "all matches" rule in §1.1 is **non-binding** and contradicts the L2 spec.

**bandspw→bands adjacency**: The authoritative rule is the **contiguous subsequence** requirement in **L2 SPEC** §5.3, line 479. There is no separate "adjacency" concept — adjacency is a consequence of contiguity. A capability `["bandspw", "bands"]` matches only where `bandspw` immediately precedes `bands` in the GEN step list. This is **BINDING** at L2.

---

*End of Review*
