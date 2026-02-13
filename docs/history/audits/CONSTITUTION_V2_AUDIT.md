# Constitution v2.0 Audit Summary

**Date**: 2026-02-03
**Author**: Opus (Constitution Editor)
**Scope**: CONSTITUTION_ZH.md v1.2 → v2.0

---

## 1. What Was Outdated in the Old Constitution

| Section | Issue | Severity |
|---------|-------|----------|
| §10.1.1 | References `step.yml` — correct name is `step.yaml` | HIGH (wrong SSOT filename) |
| §10.1.3 | References `calc` responsibilities but never mentions `calculation.yaml` by correct name | MEDIUM |
| §7.5.2-7.7 | References `calc.yml` — correct name is `calculation.yaml` | HIGH |
| §13.2 | "StepTypeRegistry" narrative predates GEN/SPEC constitution; mixes old "machine step_type" / "generalized step" terminology with newer GEN/SPEC | HIGH |
| Missing | No History world separation rules (Present vs Past, `.history/`, Job == Run, RunRevision) | HIGH |
| Missing | No Concurrency/Lock rules (edit.lock / run.lock) | HIGH |
| Missing | No Incremental run manifest rules (skip decision, StepDonePolicy) | HIGH |
| Missing | No Scan rules (ScanRef token, dict-leaf ban, parameter_scan structure) | HIGH |
| Missing | No RELAX audit rules (structure transformer, QC strong-chain boundary) | MEDIUM |
| Missing | No LAMMPS integration constitution (potential_map, restart_from, fingerprint) | MEDIUM |
| Missing | No API layering constitution (3-layer model, H9 filesystem control) | HIGH |
| Missing | No Kernel dependency rules (7-domain model, reverse import ban) | HIGH |
| Missing | No Managed params UI policy | LOW |
| Missing | No UI type contract (A-class / B-class keys) | LOW |
| §10 (ParamSpace) | ~400 lines of detailed mechanics inline — makes constitution unreadable | MEDIUM (governance issue) |
| Revision history | ~200 lines of incremental revision summaries accumulated at bottom | LOW (clutter) |

## 2. What Changed

### Structure

| Aspect | v1.2 | v2.0 |
|--------|------|------|
| Total lines | ~1400 | ~550 |
| Sections | 14 (§1-§14) | 20 (§1-§20) + Prologue + Final Clauses |
| Detail level | Full mechanics inline | High-level invariants + references to specs |
| Governance folder | Did not exist | `docs/governance/` with 7 spec documents |
| Document hierarchy | Not defined | 3-tier: Constitution > Governance Specs > Impl Docs |

### Section Mapping (v1.2 → v2.0)

| v1.2 Section | v2.0 Section | Change |
|--------------|-------------|--------|
| §1 Language | §1 Language | Unchanged |
| §2 ULID DAG | §6 Identity: ULID-only | Expanded with ULID-only law alignment |
| §3 Geometry | §15 Geometry | Relocated, unchanged |
| §4 Atom list & Bonds | §15 (merged) | Folded into geometry section |
| §5 QE Structure Schema | §16 QE Structure Schema | Relocated |
| §6 Pseudo SHA | §9.4 (merged) | Folded into Species/Pseudo section |
| §7 Pseudo Management | §9 Species/Pseudo SSOT | Thinned; species_map SSOT added |
| §8 Windows Toolchain | DELETED | Removed (policy, not invariant) |
| §9 Data Root Dirs | §20 Data Root Dirs | Thinned |
| §10 ParamSpace (~400 lines) | §8 (thin) + PARAMSPACE_SPEC.md | Major extraction to governance spec |
| §11 YamlDoc & Journal | §2.4 (SSOT section) | Folded into SSOT rules |
| §12 Key Ownership | §8.4 (ParamSpace constraints) | Folded into thin ParamSpace section |
| §13 Workflow & Registry | §7 (Step Type GEN/SPEC) | Replaced with GEN/SPEC constitution |
| §14 Engine Execution | §17 Engine Execution | Thinned; references ENGINE_INTEGRATION_CONSTITUTION |
| — (missing) | §2 SSOT & Persistence | **NEW** |
| — (missing) | §3 History World Separation | **NEW** |
| — (missing) | §4 Concurrency & Locks | **NEW** |
| — (missing) | §5 Incremental Run Manifest | **NEW** |
| — (missing) | §10 Scan Rules | **NEW** |
| — (missing) | §11 Managed Params | **NEW** |
| — (missing) | §12 UI Type Contract | **NEW** |
| — (missing) | §13 RELAX Audit | **NEW** |
| — (missing) | §14 LAMMPS Integration | **NEW** |
| — (missing) | §18 API Layering | **NEW** |
| — (missing) | §19 Kernel Dependencies | **NEW** |

### Deleted Content

| Content | Reason |
|---------|--------|
| §8 Windows Toolchain | Policy/preference, not an architectural invariant |
| ~200 lines of revision history | Replaced with single v2.0 summary |
| Detailed ParamSpace cell/profile definitions | Extracted to PARAMSPACE_SPEC.md |
| Detailed YamlDoc/Journal mechanics | Referenced via KERNEL_DEPENDENCY_SPEC |
| Detailed Step0 pseudo conflict rules | Retained in v1.2 archive; too detailed for thin constitution |

## 3. New Laws Added

| Law | Constitution § | Source |
|-----|---------------|--------|
| History world separation (Present vs Past) | §3 | User-aligned law 1.2 |
| Concurrency: edit.lock + run.lock | §4 | User-aligned law 1.3 |
| Incremental run manifest (non-SSOT) | §5 | User-aligned law 1.4 |
| ULID-only identity (no legacy fields) | §6 | User-aligned law 1.5 |
| Scan rules (ScanRef, dict-leaf ban) | §10 | User-aligned law 1.9 |
| Managed params UI read-only | §11 | User-aligned law 1.10 |
| A-class / B-class key typing | §12 | User-aligned law 1.11 |
| RELAX audit (structure transformer) | §13 | User-aligned law 1.12 |
| LAMMPS integration | §14 | User-aligned law 1.13 |
| API 3-layer model + H9 | §18 | API_CONSTITUTION |
| Kernel 7-domain model | §19 | KERNEL_DEPENDENCY_SPEC |

## 4. Laws Clarified (Not New, But Updated)

| Law | Change |
|-----|--------|
| SSOT (§2) | Explicitly names `calculation.yaml` + `step.yaml`; adds input-file-is-intermediate rule; adds outdir/.save ban |
| Step Type (§7) | Fully replaced old StepTypeRegistry narrative with GEN/SPEC two-namespace law |
| Species/Pseudo (§9) | Added species_map as SSOT; pseudo_dir runtime management; species_overrides warning policy |
| Engine Execution (§17) | Added session-chain vs artifact-bridged model distinction |

## 5. Assumptions Made

1. **§8 Windows Toolchain removed**: The Windows oneAPI/MinGW policy was a toolchain preference, not an architectural invariant. It does not belong in the constitution. If the author disagrees, it can be re-added as §21.

2. **Detailed pseudo UI/Step0 rules not in thin constitution**: The old §7.5-7.7 (UI selection rules, Step0 conflict rules, tie-break rules) are detailed implementation mechanics. They are preserved in the governance spec or can be extracted to a dedicated `PSEUDO_SPEC.md` if needed.

3. **Atom list & Bonds folded into Geometry**: §4 (atom list) was merged into §15 (geometry) since both address the same domain. Only the key invariants (first-class citizens, pure function bonds) are retained.

4. **ParamSpace Oracle/Key-Access detailed rules**: Extracted to PARAMSPACE_SPEC.md rather than inline. The constitution §8 retains the core constraints.

---

## 6. Governance Folder Structure Created

```
docs/governance/
├── README.md                              # Index + cross-references + hierarchy
├── API_CONSTITUTION.md                    # API surface laws (copied from docs/api/)
├── KERNEL_DEPENDENCY_SPEC.md              # Kernel 7-domain model (copied from docs/architecture/)
├── KERNEL_EXCEPTIONS.md                   # Approved exceptions (copied from docs/architecture/)
├── STEP_TYPE_GEN_SPEC_CONSTITUTION.md     # GEN/SPEC step type law (copied from docs/spec/)
├── ENGINE_INTEGRATION_CONSTITUTION.md     # Engine invariants (copied from docs/spec/engine_integration/)
├── ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md  # Engine recipe system + runner independence (NEW)
├── PARAMSPACE_SPEC.md                     # ParamSpace framework (NEW, extracted from old §10)
└── CONSTITUTION_V2_AUDIT.md               # This document
```

---

## 7. v2.1 Update: English Translation + Engine Recipe Spec

### v2.1 Changes (2026-02-03)

1. **Constitution translated to English**: `CONSTITUTION.md` (English, v2.1) is now the authoritative document. `CONSTITUTION_ZH.md` marked as DEPRECATED.
2. **ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md added**: New governance spec codifying the engine recipe system, runner independence, three recipe archetypes, directory contracts, and hard bans.
3. **Constitution §17.4 added**: New subsection referencing ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md.
4. **CLAUDE.md updated**: Engine recipe guidance, hard bans, and "how to add a new engine" checklist added.
5. **Governance README updated**: English constitution as top-level authority; ENGINE_RECIPE spec added to index and cross-reference table.

---

**End of Audit**
