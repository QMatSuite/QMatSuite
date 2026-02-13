# QMatSuite Documentation Taxonomy Review

> **Note**: This document is the pre-reorganization analysis that led to the `docs/laws/` L0/L1/L2 hierarchy. File paths referenced below reflect the state **before** reorganization. For current paths, see `docs/laws/README.md`.

**Date**: 2026-02-12
**Scope**: Full repo scan — every `.md` file classified
**Total files inventoried**: ~720 markdown files
**Status**: NON-BINDING review artifact

---

## Table of Contents

1. [Taxonomy Categories](#1-taxonomy-categories)
2. [Document Hierarchy (L0/L1/L2)](#2-document-hierarchy-l0l1l2)
3. [Complete Document Index](#3-complete-document-index)
   - 3.1 [L0 — Constitution (BINDING)](#31-l0--constitution-binding)
   - 3.2 [L1 — Governance Specs (BINDING)](#32-l1--governance-specs-binding)
   - 3.3 [L2 — Domain Specs (BINDING or SEMI-BINDING)](#33-l2--domain-specs-binding-or-semi-binding)
   - 3.4 [Design Documents (NON-BINDING)](#34-design-documents-non-binding)
   - 3.5 [Plans (NON-BINDING)](#35-plans-non-binding)
   - 3.6 [Worklogs (NON-BINDING)](#36-worklogs-non-binding)
   - 3.7 [Audit / Review Reports (NON-BINDING)](#37-audit--review-reports-non-binding)
   - 3.8 [Implementation Summaries (NON-BINDING)](#38-implementation-summaries-non-binding)
   - 3.9 [Dev Notes / Debug / Forensics (NON-BINDING)](#39-dev-notes--debug--forensics-non-binding)
   - 3.10 [How-to / Playbook / Guide (NON-BINDING)](#310-how-to--playbook--guide-non-binding)
   - 3.11 [Engine Research & Exploration (NON-BINDING)](#311-engine-research--exploration-non-binding)
   - 3.12 [Curated Indexes (NON-BINDING)](#312-curated-indexes-non-binding)
   - 3.13 [Test Documentation (NON-BINDING)](#313-test-documentation-non-binding)
   - 3.14 [GUI Documentation (NON-BINDING)](#314-gui-documentation-non-binding)
   - 3.15 [Project Meta (NON-BINDING)](#315-project-meta-non-binding)
4. [Duplicates and Conflicts](#4-duplicates-and-conflicts)
5. [Authoritative Document per Topic](#5-authoritative-document-per-topic)
6. [Missing Specs](#6-missing-specs)
7. [Proposed Target Layout](#7-proposed-target-layout)
8. [Migration Mapping Table](#8-migration-mapping-table)
9. [Naming Conventions](#9-naming-conventions)

---

## 1. Taxonomy Categories

| Category | Abbrev | Binding? | Description |
|----------|--------|----------|-------------|
| **Constitution** | CONST | BINDING | Highest-authority project law. Repo root only. |
| **Governance Spec** | GOV | BINDING | Detailed mechanics delegated by constitution. `docs/governance/` only. |
| **Domain Spec** | SPEC | BINDING or SEMI | Ratified specifications for specific subsystems (API, analysis, relax, etc.). |
| **Design** | DESIGN | NON-BINDING | Architectural rationale, design decisions, ADRs. Reference only. |
| **Plan** | PLAN | NON-BINDING | Implementation plans (past or future). |
| **Worklog** | WLOG | NON-BINDING | Chronological implementation progress logs. |
| **Audit/Review** | AUDIT | NON-BINDING | Code/architecture audits, compliance reviews, verdict memos. |
| **Implementation Summary** | IMPL | NON-BINDING | Post-hoc summaries of completed implementation work. |
| **Dev Notes** | DEV | NON-BINDING | Debug notes, forensics, diagnosis, archaeology, fix attempts. |
| **How-to / Playbook** | HOWTO | NON-BINDING | SOPs, guides, checklists, onboarding procedures. |
| **Engine Research** | RESEARCH | NON-BINDING | Engine exploration reports, integration research, capability surveys. |
| **Curated Index** | INDEX | NON-BINDING | Sample/corpus/case indexes for engine test data. |
| **Test Docs** | TEST | NON-BINDING | Test architecture, test data READMEs, test matrices. |
| **GUI Docs** | GUI | NON-BINDING | GUI-specific architecture, wiring, E2E testing. |
| **Project Meta** | META | NON-BINDING | README, CHANGELOG, CI templates, CLAUDE.md instructions. |

---

## 2. Document Hierarchy (L0/L1/L2)

```
L0  CONSTITUTION.md (v2.1 FINAL — sole supreme authority)
 │
 ├─ L1  docs/governance/API_CONSTITUTION.md           (§18, FINAL v2.1)
 ├─ L1  docs/governance/ENGINE_INTEGRATION_CONSTITUTION.md (§17, SPEC v1.0)
 ├─ L1  docs/governance/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md (§17.4, FINAL v1.0)
 ├─ L1  docs/governance/KERNEL_DEPENDENCY_SPEC.md     (§19, PROPOSED v3.1)
 ├─ L1  docs/governance/KERNEL_EXCEPTIONS.md          (§19, ACTIVE v3.1)
 ├─ L1  docs/governance/STEP_TYPE_GEN_SPEC_CONSTITUTION.md (§7, FINAL v1.1)
 ├─ L1  docs/governance/PARAMSPACE_SPEC.md            (§8, FINAL v1.0)
 ├─ L1  docs/governance/PROVENANCE_VERSIONED_HISTORY_SPEC.md (§3, PROPOSED v1.1)
 │
 ├─ L2  docs/specs/API_FACADE_CONTRACT.md             (CONST v2.0 — should be L1)
 ├─ L2  docs/specs/RELAX_SPEC.md                      (RATIFIED v1.0)
 ├─ L2  docs/specs/STRUCTURE_FINGERPRINT_SPEC.md      (RATIFIED v2.1)
 ├─ L2  docs/specs/MULTI_FRONTEND_ARCHITECTURE_SPEC.md (HARDENED v2.0)
 ├─ L2  docs/specs/ANALYSIS_OBJECTS_FRAMEWORK.md      (PROPOSED v1.1)
 ├─ L2  docs/specs/API_DTO_SCHEMA.md                  (spec)
 ├─ L2  docs/specs/API_ERROR_TAXONOMY.md              (spec)
 ├─ L2  docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md (BINDING v1.4)
 ├─ L2  docs/architecture/B1_ENGINE_PLAYBOOK.md       (ACTIVE SOP v1.0)
 ├─ L2  docs/architecture/CALC_TYPE_SYSTEM_KIND_SPEC.md (DESIGN v1.0)
 ├─ L2  docs/architecture/PROJECT_BUNDLE_SPEC.md      (DESIGN v1.0)
 ├─ L2  docs/architecture/ROLE_INFERENCE_SPEC.md      (DESIGN v1.0)
 └─ L2  docs/spec/DEMO_STORE_SPEC.md                  (Draft v6)
```

---

## 3. Complete Document Index

### 3.1 L0 — Constitution (BINDING)

| Path | Version | Status | Scope | Obsolete? |
|------|---------|--------|-------|-----------|
| `CONSTITUTION.md` | 2.1 | FINAL | repo-wide | **Current** — sole supreme authority |
| `CONSTITUTION_ZH.md` | 2.0 | **DEPRECATED** | repo-wide | **OBSOLETE** — retained for archaeology only |

### 3.2 L1 — Governance Specs (BINDING)

All located in `docs/governance/`. These are the **detailed mechanics** referenced by constitution sections.

| Path | Version | Status | Const. § | Scope | Obsolete? |
|------|---------|--------|----------|-------|-----------|
| `docs/governance/API_CONSTITUTION.md` | 2.1 | FINAL | §18 | api | Current |
| `docs/governance/ENGINE_INTEGRATION_CONSTITUTION.md` | 1.0 | SPEC | §17 | engine | Current |
| `docs/governance/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` | 1.0 | FINAL | §17.4 | engine/runner | Current |
| `docs/governance/KERNEL_DEPENDENCY_SPEC.md` | 3.1 | PROPOSED | §19 | kernel | Current (awaiting FINAL) |
| `docs/governance/KERNEL_EXCEPTIONS.md` | 3.1 | ACTIVE | §19 | kernel | Current (quarterly review) |
| `docs/governance/STEP_TYPE_GEN_SPEC_CONSTITUTION.md` | 1.1 | FINAL | §7 | kernel | Current |
| `docs/governance/PARAMSPACE_SPEC.md` | 1.0 | FINAL | §8 | kernel/workflow | Current |
| `docs/governance/PROVENANCE_VERSIONED_HISTORY_SPEC.md` | 1.1 | PROPOSED | §3 | provenance | Current (awaiting FINAL) |
| `docs/governance/PROVENANCE_IMPLEMENTATION_PLAN.md` | — | IMPL | §3 | provenance | Current (companion to spec) |
| `docs/governance/CONSTITUTION_V2_AUDIT.md` | — | AUDIT | — | governance | Current (migration record) |
| `docs/governance/README.md` | — | INDEX | — | governance | Current (cross-reference) |

### 3.3 L2 — Domain Specs (BINDING or SEMI-BINDING)

| Path | Category | Version | Status | Scope | Obsolete? |
|------|----------|---------|--------|-------|-----------|
| `docs/specs/API_FACADE_CONTRACT.md` | SPEC | 2.0 | CONST | api | Current — **misplaced, should be L1** |
| `docs/specs/API_DTO_SCHEMA.md` | SPEC | — | spec | api | Current |
| `docs/specs/API_ERROR_TAXONOMY.md` | SPEC | — | spec | api | Current |
| `docs/specs/API_FACADE_SLIMMING_DESIGN.md` | DESIGN | — | design | api | Current |
| `docs/specs/API_FACADE_SLIMMING_REVIEW.md` | AUDIT | — | review | api | Current |
| `docs/specs/API_FACADE_IMPLEMENTATION_PLAN.md` | PLAN | — | plan | api | Current |
| `docs/specs/MULTI_FRONTEND_ARCHITECTURE_SPEC.md` | SPEC | 2.0 | HARDENED | api/gui | Current |
| `docs/specs/RELAX_SPEC.md` | SPEC | 1.0 | RATIFIED | kernel | Current |
| `docs/specs/STRUCTURE_FINGERPRINT_SPEC.md` | SPEC | 2.1 | RATIFIED | kernel | Current |
| `docs/specs/ANALYSIS_OBJECTS_FRAMEWORK.md` | SPEC | 1.1 | PROPOSED | analysis | Current (see also PRIMITIVES) |
| `docs/specs/ANALYSIS_OBJECTS_OPEN_QUESTIONS.md` | DEV | — | questions | analysis | Current |
| `docs/specs/TRAJECTORY_CORE.md` | SPEC | 1.1 | **SUPERSEDED** | analysis | **OBSOLETE** — superseded by ANALYSIS_OBJECTS_FRAMEWORK |
| `docs/specs/REPO_CODE_REVIEW_REPORT.md` | AUDIT | — | review | repo-wide | Current |
| `docs/specs/detour-paramspace-and-speciesmap-contract.md` | DEV | — | notes | kernel | Current |
| `docs/specs/parameter_scan.md` | SPEC | — | spec | kernel | Current |
| `docs/spec/DEMO_STORE_SPEC.md` | SPEC | Draft v6 | draft | demo | Current |
| `docs/spec/step_type_gen_spec_constitution.md` | GOV | 1.1 | **DUPLICATE** | kernel | **OBSOLETE** — dup of governance/ |
| `docs/spec/engine_integration/engine_integration_constitution.md` | GOV | 1.0 | **DUPLICATE** | engine | **OBSOLETE** — dup of governance/ |
| `docs/spec/engine_integration/engine_driver_protocol.md` | SPEC | 1.0 | spec | engine | Current (reference) |
| `docs/spec/engine_integration/engine_registry_and_dispatch.md` | SPEC | 1.0 | spec | engine | Current (reference) |
| `docs/spec/engine_integration/migration_gates_and_test_contract.md` | SPEC | 1.0 | spec | engine | Current (reference) |
| `docs/spec/engine_integration/open_questions_shortlist.md` | DEV | — | questions | engine | Current |
| `docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` | SPEC | 1.4 | BINDING | analysis | Current — **strongest analysis spec** |
| `docs/architecture/ANALYSIS_PIPELINE_PLAYBOOK.md` | HOWTO | — | playbook | analysis | Current |
| `docs/architecture/B1_ENGINE_PLAYBOOK.md` | HOWTO | 1.0 | ACTIVE SOP | engine | Current — **binding SOP** |
| `docs/architecture/B1_ENGINE_CORPUS_INDEX.md` | INDEX | — | index | engine | Current |
| `docs/architecture/B1_ENGINE_PLAYBOOK_REVIEW.md` | AUDIT | — | review | engine | Current |
| `docs/architecture/CALC_TYPE_SYSTEM_KIND_SPEC.md` | SPEC | 1.0 | design | kernel | Current |
| `docs/architecture/PROJECT_BUNDLE_SPEC.md` | SPEC | 1.0 | design | kernel | Current |
| `docs/architecture/ROLE_INFERENCE_SPEC.md` | SPEC | 1.0 | design | kernel | Current |
| `docs/architecture/AGENT_READY_KERNEL.md` | DESIGN | — | design | kernel | Current |
| `docs/architecture/KERNEL_REVIEW_REPORT.md` | AUDIT | — | review | kernel | Current |
| `docs/architecture/KERNEL_WORKLOG.md` | WLOG | — | worklog | kernel | Current |
| `docs/architecture/ORCA_INTEGRATION_SPEC.md` | SPEC | — | spec | engine/orca | Current |
| `docs/architecture/WANNIER90_INTEGRATION_SPEC.md` | SPEC | — | spec | engine/w90 | Current |
| `docs/architecture/PYSCF_INTEGRATION_SPEC.md` | SPEC | — | spec | engine/pyscf | Current |
| `docs/architecture/GUI_ENGINE_DEMO_AUDIT.md` | AUDIT | — | audit | gui/engine | Current |
| `docs/architecture/GUI_ENGINE_FAMILY_DEMO_SPEC.md` | SPEC | — | spec | gui/demo | Current |
| `docs/architecture/TEST_AUDIT_GPAW_INTEGRATION.md` | AUDIT | — | audit | engine/gpaw | Current |
| `docs/architecture/IMPLEMENTATION_PLAN_KERNEL.md` | PLAN | — | plan | kernel | Current |

### 3.4 Design Documents (NON-BINDING)

**Root-level design docs (should be relocated):**

| Path | Scope | Notes |
|------|-------|-------|
| `BEHAVIOR_SPEC_FROM_CODE.md` | kernel/pseudo | Code-extracted behavior spec |
| `SIESTA_INTEGRATION_DESIGN.md` | engine/siesta | Integration design |
| `ARCHITECTURE_UNDERSTANDING_PSEUDO.md` | kernel/pseudo | Architecture analysis |
| `SSSP_SETTINGS_UX_ANALYSIS.md` | gui/pseudo | UX analysis |
| `SSSP_UX_REDESIGN_TEST_CHECKLIST.md` | gui/pseudo | Test checklist |
| `OCCUPATION_DEGAUSS_DEPENDENCY_DIAGNOSTIC.md` | kernel/qe | Diagnostic |

**docs/ design docs:**

| Path | Scope |
|------|-------|
| `docs/ARCHITECTURE.md` | repo-wide |
| `docs/ARCHITECTURE_OVERVIEW.md` | repo-wide |
| `docs/CANONICALIZATION_DESIGN.md` | kernel |
| `docs/HISTORY_DESIGN.md` | kernel/provenance |
| `docs/GUI_ARCHITECTURE.md` | gui |
| `docs/GUI_DAEMON_API_MAPPING.md` | gui/api |
| `docs/JOB_IO_DIRECTORY_SEMANTICS.md` | kernel/runner |
| `docs/SCHEMA.md` | kernel/yaml |
| `docs/PIPELINE_DATAFLOW_ANALYSIS.md` | kernel |
| `docs/PIPELINE_OUTPUTS_AND_ARTIFACTS.md` | kernel |
| `docs/COMMON_CARDS_CONTRACT.md` | kernel/qe |
| `docs/WORKFLOW_PRESET_DESIGN_V0.md` | kernel/workflow |
| `docs/journal_design.md` | kernel/provenance |
| `docs/design/UNIVERSAL_PARSER_WRITER_DESIGN.md` | inputformat |
| `docs/design/ONLINE_STRUCTURE_SOURCES.md` | api/structure |
| `docs/design/PHASE3C_RUNNER_SPEC.md` | kernel/runner |
| `docs/design/PHASE_PYSCF_ROADMAP.md` | engine/pyscf |
| `docs/design/ir_step_engine_v0.md` | kernel/ir |
| `docs/architecture/design/TRAJECTORY_ANALYSIS_DESIGN.md` | analysis |
| `docs/architecture/design/VASP_ANALYSIS_DESIGN.md` | analysis/vasp |
| `docs/analysis/ANALYSIS_OBJECTS_DESIGN.md` | analysis |
| `docs/research/ASE_ARCHITECTURE_REPORT.md` | research |
| `docs/research/RELAX_ENGINE_RESEARCH.md` | research/relax |

### 3.5 Plans (NON-BINDING)

**Root-level plans (should be relocated):**

| Path | Scope |
|------|-------|
| `CONTRACT_CRAWLER_PLAN.md` | kernel |
| `PHASE3A3B_PLAN.md` | kernel |
| `PR10_PYTEST_RECOVERY_PLAN.md` | testing |
| `REFACTOR_PLAN_PSEUDO.md` | kernel/pseudo |
| `RPC_CONTRACT_RECOVERY_FIX_PLAN.md` | api |

**docs/ plans:**

| Path | Scope |
|------|-------|
| `docs/API_SINGLE_SOURCE_MIGRATION_PLAN.md` | api |
| `docs/GEN_SPEC_CONVERGENCE_IMPLEMENTATION_PLAN.md` | kernel |
| `docs/GEN_SPEC_IMPLEMENTATION_PLAN.md` | kernel |
| `docs/GEN_SPEC_SEMANTICS_IMPLEMENTATION_PLAN.md` | kernel |
| `docs/IMPLEMENTATION_PLAN_MULTI_FRONTEND_REFACTOR.md` | api/gui |
| `docs/IMPLEMENTATION_PLAN_OCCUPATIONS_SCHEME.md` | kernel/qe |
| `docs/IMPLEMENTATION_PLAN_PRECISION.md` | kernel |
| `docs/IMPLEMENTATION_PLAN_PRECISION_DETECT_FIX.md` | kernel |
| `docs/IMPLEMENTATION_PLAN_PRESET_FIXES.md` | kernel |
| `docs/IMPLEMENTATION_PLAN_PRESET_UI.md` | gui |
| `docs/IMPLEMENTATION_PLAN_PRESETS.md` | kernel |
| `docs/IMPLEMENTATION_PLAN_PRESETS_COMPLETE.md` | kernel |
| `docs/IMPLEMENTATION_PLAN_PRESETS_HARDENING.md` | kernel |
| `docs/IMPLEMENTATION_PLAN_PHASE2_INTEGRATION.md` | kernel |
| `docs/PLAN_V2_REVISED_IMPLEMENTATION.md` | repo-wide |
| `docs/VOLUME_VIEWER_IMPLEMENTATION_PLAN.md` | gui |
| `docs/paramspace_apply_plan.md` | kernel |
| `docs/pyscf_integration_plan.md` | engine/pyscf |
| `docs/workflow_refactor_plan.md` | kernel |
| `docs/yamldoc_refactor_plan.md` | kernel |
| `docs/plan/CHUNK_2_MILESTONE.md` | repo-wide |
| `docs/plan/CLI_MIGRATION_MAP.md` | api/cli |
| `docs/plan/IMPLEMENTATION_PLAN_MULTI_FRONTEND_REFACTOR.md` | api/gui |
| `docs/plan/MULTI_FRONTEND_FACADE_AUDIT_REPORT.md` | api |
| `docs/plan/engine_driver_arch/*.md` (6 files) | engine |
| `docs/plan/engine_driver_migration/*.md` (16 files) | engine |
| `docs/plan/engine_driver_migration_qe/*.md` (10 files) | engine/qe |
| `docs/plan/lammps/*.md` (12 files) | engine/lammps |
| `docs/plans/*.md` (15 files) | mixed |
| `docs/design/PYSCF_V0_EXECUTION_PLAN.md` | engine/pyscf |
| `docs/design/ir_step_engine_v0_implementation_plan.md` | kernel |
| `docs/design/phase2_workflow_implementation_plan.md` | kernel |
| `docs/impl/CP2K_IMPLEMENTATION_PLAN.md` | engine/cp2k |

**Engine-specific plans (docs/engines/):**

| Path | Engine |
|------|--------|
| `docs/engines/abinit/PHASE_B1_PLAN.md` | abinit |
| `docs/engines/abinit/PLAN.md` | abinit |
| `docs/engines/abinit/ABINIT_INTEGRATION_PLAN.md` | abinit |
| `docs/engines/cp2k/PHASE_B1_PLAN.md` | cp2k |
| `docs/engines/cp2k/PLAN.md` | cp2k |
| `docs/engines/gaussian/PHASE_B1_PLAN.md` | gaussian |
| `docs/engines/gaussian/GAUSSIAN_INTEGRATION_PLAN.md` | gaussian |
| `docs/engines/gpaw/GPAW_INTEGRATION_PLAN.md` | gpaw |
| `docs/engines/lammps/PHASE_B1_PLAN.md` | lammps |
| `docs/engines/orca/PHASE_B1_PLAN.md` | orca |
| `docs/engines/psi4/PSI4_INTEGRATION_PLAN.md` | psi4 |
| `docs/engines/qmcpack/PHASE_B1_PLAN.md` | qmcpack |
| `docs/engines/qmcpack/QMCPACK_INTEGRATION_PLAN.md` | qmcpack |
| `docs/engines/siesta/PHASE_B1_PLAN.md` | siesta |
| `docs/engines/siesta/INTEGRATION_PLAN.md` | siesta |
| `docs/engines/siesta/PLAN.md` | siesta |
| `docs/engines/vasp/PHASE_B1_PLAN.md` | vasp |
| `docs/engines/wannier90/PHASE_B1_PLAN.md` | wannier90 |
| `docs/engines/xtb/PHASE_B1_PLAN.md` | xtb |
| `docs/engines/xtb/INTEGRATE_PLAN.md` | xtb |
| `docs/engines/xtb/PLAN.md` | xtb |
| `docs/engines/yambo/PHASE_B1_PLAN.md` | yambo |
| `docs/engines/yambo/YAMBO_INTEGRATION_PLAN.md` | yambo |

**Analysis/GUI plans:**

| Path | Scope |
|------|-------|
| `docs/architecture/worklogs/ANALYSIS_PIPELINE_IMPLEMENTATION_PLAN.md` | analysis |
| `docs/architecture/worklogs/ANALYSIS_PIPELINE_NEXT_PLAN.md` | analysis |
| `docs/architecture/worklogs/ANALYSIS_PIPELINE_PHASE3_PLAN.md` | analysis |
| `docs/architecture/worklogs/ANALYSIS_GUI_CLOSEOUT_PLAN.md` | analysis/gui |
| `docs/architecture/worklogs/FIELD3D_ALL_ENGINES_PLAN.md` | analysis |
| `docs/architecture/worklogs/FIELD3D_GUI_AND_E2E_CLOSEOUT_PLAN.md` | analysis/gui |
| `docs/architecture/worklogs/VASP_ANALYSIS_IMPLEMENTATION_PLAN.md` | analysis/vasp |
| `docs/architecture/worklogs/VASP_ANALYSIS_PHASE4_PLAN.md` | analysis/vasp |
| `docs/architecture/worklogs/MULTI_ENGINE_BANDS_DOS_FATBANDS_PHASE4_CLOSEOUT_PLAN.md` | analysis |
| `docs/demo_store/QE_COMPOSITE_PIPELINES_PLAN.md` | demo |
| `docs/demo_store/REFERENCE_PACKS_PLAN.md` | demo |
| `docs/demo_store/REFPACKS_REALRUN_PLAN.md` | demo |
| `docs/demo_store/AUTHORSHIP_PATH_PLAN.md` | demo |
| `docs/worklog/STRUCTURE_FETCH_V2_PLAN.md` | api/structure |

### 3.6 Worklogs (NON-BINDING)

**Root-level worklogs (should be relocated):**

| Path | Scope |
|------|-------|
| `PR10_WORKLOG.md` | testing |
| `WORK_LOG_PYTEST_RECOVERY.md` | testing |
| `WORKLOG_SONNET_GEN_SPEC_CLEANUP.md` | kernel |

**docs/ worklogs:**

| Path | Scope |
|------|-------|
| `docs/API_MIGRATION_WORKLOG.md` | api |
| `docs/GEN_SPEC_WORKLOG.md` | kernel |
| `docs/GEN_SPEC_IMPLEMENTATION_WORKLOG.md` | kernel |
| `docs/GUI_WIRING_WORKLOG.md` | gui |
| `docs/worklog/STRUCTURE_FETCH_V2_WORKLOG.md` | api |
| `docs/worklog/provenance_implementation.md` | provenance |

**Engine-specific worklogs (docs/engines/):**

| Path | Engine |
|------|--------|
| `docs/engines/abinit/PHASE_B1_WORKLOG.md` | abinit |
| `docs/engines/abinit/WORKLOG_AUTO_PHASE0_1.md` | abinit |
| `docs/engines/cp2k/PHASE_B1_WORKLOG.md` | cp2k |
| `docs/engines/cp2k/WORKLOG_AUTO_PHASE0_1.md` | cp2k |
| `docs/engines/gaussian/PHASE_B1_WORKLOG.md` | gaussian |
| `docs/engines/lammps/PHASE_B1_WORKLOG.md` | lammps |
| `docs/engines/lammps/PHASE_B1_AUTO_PHASE0_WORKLOG.md` | lammps |
| `docs/engines/orca/PHASE_B1_WORKLOG.md` | orca |
| `docs/engines/orca/PHASE_B1_AUTO_PHASE0_WORKLOG.md` | orca |
| `docs/engines/qmcpack/PHASE_B1_WORKLOG.md` | qmcpack |
| `docs/engines/qmcpack/PHASE_B1_AUTO_PHASE0_WORKLOG.md` | qmcpack |
| `docs/engines/siesta/PHASE_B1_WORKLOG.md` | siesta |
| `docs/engines/siesta/WORKLOG_AUTO_PHASE0_1.md` | siesta |
| `docs/engines/vasp/PHASE_B1_WORKLOG.md` | vasp |
| `docs/engines/vasp/PHASE_B1_AUTO_PHASE0_WORKLOG.md` | vasp |
| `docs/engines/wannier90/PHASE_B1_WORKLOG.md` | wannier90 |
| `docs/engines/wannier90/PHASE_B1_AUTO_PHASE0_WORKLOG.md` | wannier90 |
| `docs/engines/xtb/PHASE_B1_WORKLOG.md` | xtb |
| `docs/engines/xtb/PHASE_B1_AUTO_PHASE0_WORKLOG.md` | xtb |
| `docs/engines/yambo/PHASE_B1_WORKLOG.md` | yambo |
| `docs/engines/yambo/WORKLOG_AUTO_PHASE0_1.md` | yambo |

**Analysis worklogs:**

| Path | Scope |
|------|-------|
| `docs/architecture/worklogs/ANALYSIS_PIPELINE_GAPS_1245_WORKLOG.md` | analysis |
| `docs/architecture/worklogs/FIELD3D_ALL_ENGINES_WORKLOG.md` | analysis |
| `docs/architecture/worklogs/GUI_HISTORY_RESOURCES_CLI_WORKLOG.md` | gui |
| `docs/architecture/worklogs/TRAJECTORY_MULTI_ENGINE_WORKLOG.md` | analysis |

### 3.7 Audit / Review Reports (NON-BINDING)

**Root-level audits (76 files total — these are the largest category of misplaced docs):**

| Path | Category | Scope |
|------|----------|-------|
| `ADR_CONSISTENCY_REVIEW.md` | AUDIT | repo-wide |
| `API_SLIMMING_AUDIT_VERDICT.md` | AUDIT | api |
| `API_SLIMMING_PROGRESS_REVIEW.md` | AUDIT | api |
| `AUDIT_REPORT_PRECISION_BANDS_KPOINTS.md` | AUDIT | kernel |
| `CONTRACT_SYSTEM_AUDIT.md` | AUDIT | kernel |
| `GEN_SPEC_CONVERGENCE_AUDIT_REPORT.md` | AUDIT | kernel |
| `KERNEL_DRIFT_VERDICT_MEMO.md` | AUDIT | kernel |
| `PER_CALC_LOCKING_AND_INCREMENTAL_RUN_AUDIT.md` | AUDIT | kernel |
| `PRE_RELEASE_AUDIT.md` | AUDIT | repo-wide |
| `PRECISION_DETECTION_CODE_REVIEW.md` | AUDIT | kernel |
| `PRECISION_LOGIC_AUDIT.md` | AUDIT | kernel |
| `PSEUDO_MIGRATION_AUDIT.md` | AUDIT | kernel/pseudo |
| `PSEUDO_TEST_ANALYSIS.md` | AUDIT | kernel/pseudo |
| `QE_PARAMETER_SYSTEM_AUDIT_REPORT.md` | AUDIT | engine/qe |
| `RELAX_IMPLEMENTATION_AUDIT_REPORT.md` | AUDIT | kernel/relax |
| `SEMANTIC_DRIFT_AUDIT_0873ebf_to_HEAD.md` | AUDIT | kernel |
| `STEP_TYPE_MAPPING_SSOT_AUDIT.md` | AUDIT | kernel |
| `YAML_DICT_USAGE_REVIEW.md` | AUDIT | kernel |
| `IR_Landing_Review.md` | AUDIT | kernel/ir |
| `Report_A_p4vasp_Analysis_Architecture_Deep_Study.md` | AUDIT | analysis |
| `Report_B_QMatSuite_Analysis_Pipeline_Deep_Review.md` | AUDIT | analysis |

**docs/ audits/reviews:**

| Path | Scope |
|------|-------|
| `docs/ANALYSIS_VISUALIZATION_ARCHITECTURE_AUDIT.md` | analysis/gui |
| `docs/GEN_SPEC_CONSTITUTION_REVIEW.md` | kernel |
| `docs/GEN_SPEC_SEMANTICS_REVIEW.md` | kernel |
| `docs/GUI_HISTORY_AND_RESOURCES_REVIEW.md` | gui |
| `docs/LEGACY_AUDIT_GATE.md` | kernel |
| `docs/LIBRARY_MANAGER_REFACTOR_REVIEW.md` | kernel/pseudo |
| `docs/PRESET_PARAMSPACE_CODE_REVIEW.md` | kernel |
| `docs/review/API_SURFACE_MAP.md` | api |
| `docs/review/AUTO_REVIEW_MULTI_FRONTEND_REFACTOR.md` | api |
| `docs/review/DANGLING_CALLS_PLAN.md` | api |
| `docs/review/GOLD_STANDARD_DIFF_0873EBF.md` | kernel |
| `docs/review/REPO_STATUS_REPORT.md` | repo-wide |
| `docs/reviews/*.md` (17 files) | mixed |
| `docs/audits/API_DANGLING_CALLS_NEXT.md` | api |
| `docs/api/API_SLIMMING_REVIEW.md` | api |
| `docs/api/API_SLIMMING_WORKLOG.md` | api |
| `docs/api/BATCH_36_37_OWNERSHIP_REVIEW.md` | api |
| `docs/api/CLI_LAW_H9_VIOLATIONS.md` | api |
| `docs/api_slim_audit/api_dangling_calls.md` | api |
| `docs/architecture/worklogs/ANALYSIS_PIPELINE_ACCEPTANCE_REVIEW.md` | analysis |
| `docs/architecture/worklogs/ANALYSIS_PIPELINE_CLOSEOUT_REVIEW.md` | analysis |
| `docs/architecture/worklogs/ANALYSIS_PIPELINE_COMPLETENESS_REVIEW.md` | analysis |
| `docs/architecture/worklogs/ANALYSIS_PIPELINE_PHASE2_ACCEPTANCE_REVIEW.md` | analysis |
| `docs/architecture/worklogs/ANALYSIS_GUI_CLOSEOUT_ACCEPTANCE.md` | analysis/gui |
| `docs/architecture/worklogs/FIELD3D_GUI_AND_E2E_CLOSEOUT_ACCEPTANCE.md` | analysis/gui |
| `docs/architecture/worklogs/MULTI_ENGINE_BANDS_DOS_ACCEPTANCE.md` | analysis |
| `docs/architecture/worklogs/MULTI_ENGINE_FATBANDS_PDOS_CLOSEOUT_ACCEPTANCE.md` | analysis |
| `docs/architecture/worklogs/VASP_ANALYSIS_PHASE4_ACCEPTANCE.md` | analysis/vasp |

### 3.8 Implementation Summaries (NON-BINDING)

**Root-level summaries (should be relocated):**

| Path | Scope |
|------|-------|
| `CHANGELOG_FOR_TEST_FIXES.md` | testing |
| `CONTRACT_HARDENING_SUMMARY.md` | kernel |
| `DAEMON_IMPORT_FIX_SUMMARY.md` | api |
| `DEMO_SNAPSHOT_PSEUDO_FAMILY_FIX_REPORT.md` | demo |
| `DTO_COMPAT_FIX_REPORT.md` | api |
| `DTO_CONTRACT_TESTS_REPORT.md` | api |
| `GET_SETTINGS_COMPATIBILITY_SUMMARY.md` | api |
| `HARDENING_SUMMARY.md` | kernel |
| `IMPLEMENTATION_SUMMARY_PSEUDO_REFACTOR.md` | kernel/pseudo |
| `INCREMENTAL_RUN_IMPLEMENTATION_SUMMARY.md` | kernel |
| `INIT_PROJECT_COMPATIBILITY_SUMMARY.md` | api |
| `LEGACY_PURGE_REPORT.md` | kernel |
| `PHASE1_IR_BUG_FIXES.md` | kernel/ir |
| `PHASE1_IR_IMPLEMENTATION_COMPLETE.md` | kernel/ir |
| `PHASE1_IR_IMPLEMENTATION_PROGRESS.md` | kernel/ir |
| `PHASE2_CLOSEOUT_REPORT.md` | kernel |
| `PHASE2_COMPAT_NOTES.md` | kernel |
| `PHASE2_IMPLEMENTATION_PROGRESS.md` | kernel |
| `PHASE3A3B_COMPLETION_SUMMARY.md` | kernel |
| `PHASE3C_FIX_COMPLETE_REPORT.md` | kernel |
| `PHASE3C_FIX_SUMMARY.md` | kernel |
| `PHASE3C_REGRESSION_FIX_REPORT.md` | kernel |
| `PR10_CLOSEOUT_CHECKLIST.md` | testing |
| `PR10_LOCAL_SKIP_ELIMINATION.md` | testing |
| `PR10_SKIP_LEDGER.md` | testing |
| `PROGRESS_SUMMARY.md` | repo-wide |
| `PSEUDO_UX_REFINEMENT_SUMMARY.md` | gui/pseudo |
| `QE_LEGACY_TABLES_RECOVERY.md` | engine/qe |
| `TERMINOLOGY_CLARIFICATION_SUMMARY.md` | repo-wide |
| `TEST_FIXES_FINAL_REPORT.md` | testing |
| `TEST_FIXES_SUMMARY.md` | testing |
| `UI_PRESET_CATALOG_MIGRATION_SUMMARY.md` | gui |
| `VARIANTS_IMPLEMENTATION_SUMMARY.md` | kernel |
| `VARIANTS_MIGRATION_FIXES_SUMMARY.md` | kernel |

**docs/ implementation reports:**

| Path | Scope |
|------|-------|
| `docs/BUGFIX_*.md` (12 files) | engine/qe,w90 |
| `docs/COMPLETION_STATUS.md` | repo-wide |
| `docs/CODE_REVIEW_COMPLETION_STATUS.md` | repo-wide |
| `docs/E2E_TEST_FIXES_SUMMARY.md` | testing |
| `docs/FAILED_DEMOS_REPORT.md` | demo |
| `docs/FINAL_COMPLETION_REPORT.md` | repo-wide |
| `docs/FINAL_COMPLETION_SUMMARY.md` | repo-wide |
| `docs/FIX_PHASE0_CONTRACT_MISMATCH.md` | kernel |
| `docs/GEN_SPEC_CLEANUP_WORKLOG.md` | kernel |
| `docs/HARDENING_SUMMARY.md` | kernel |
| `docs/IMPLEMENTATION_NOTES.md` | repo-wide |
| `docs/IMPLEMENTATION_SUMMARY_PSEUDO_REFACTOR.md` | kernel/pseudo |
| `docs/LIBRARY_MANAGER_FIXES.md` | kernel/pseudo |
| `docs/SHA_FAMILY_MIGRATION_HARDENING.md` | kernel/pseudo |
| `docs/impl/CP2K_IMPLEMENTATION_COMPLETE.md` | engine/cp2k |
| `docs/impl/CP2K_PHASE0_FINDINGS.md` | engine/cp2k |
| `docs/demo_store/*.md` (closeout, report files) | demo |

### 3.9 Dev Notes / Debug / Forensics (NON-BINDING)

**Root-level dev notes:**

| Path | Scope |
|------|-------|
| `DIAGNOSTIC_REPORT_FULL_TEST_SUITE.md` | testing |

**docs/dev/ (40+ files — largest dev-notes directory):**

| Path | Scope |
|------|-------|
| `docs/dev/CP2K_CODE_REVIEW_NOTES.md` | engine/cp2k |
| `docs/dev/RELAX_IMPLEMENTATION_PLAN.md` | kernel/relax |
| `docs/dev/RELAX_TEST_MATRIX.md` | kernel/relax |
| `docs/dev/TESTING.md` | testing |
| `docs/dev/TEST_WARNINGS_INVESTIGATION.md` | testing |
| `docs/dev/archaeology-paramspace*.md` (2 files) | kernel |
| `docs/dev/diagnosis-steptype-enum-removal-errors.md` | kernel |
| `docs/dev/diff-baac796-vs-head.md` | kernel |
| `docs/dev/exec-pipeline-ssot-contract.md` | kernel |
| `docs/dev/execution-modes-inventory.md` | kernel |
| `docs/dev/final-audit-ir-*.md` (2 files) | kernel/ir |
| `docs/dev/fix-attempts-kpoints-regression.md` | kernel |
| `docs/dev/integration-pseudo-dir-forensics.md` | kernel/pseudo |
| `docs/dev/ir-boolean-canonical-contract.md` | kernel/ir |
| `docs/dev/ir-engine-serialization-fix.md` | kernel/ir |
| `docs/dev/ir-ssot-migration-plan.md` | kernel/ir |
| `docs/dev/kpoints-data-regression-*.md` (3 files) | kernel |
| `docs/dev/plan-*.md` (8 files) | kernel |
| `docs/dev/post-detour-deep-review-params-presets-ir-steps.md` | kernel |
| `docs/dev/pseudo-*.md` (3 files) | kernel/pseudo |
| `docs/dev/review-*.md` (2 files) | kernel |
| `docs/dev/scan-merge-summary.md` | kernel |
| `docs/dev/skipped-tests-analysis.md` | testing |
| `docs/dev/spec-*.md` (3 files) | kernel |
| `docs/dev/standalone-input-path-usage-audit.md` | kernel |
| `docs/dev/yaml-to-runner-fidelity-audit.md` | kernel |

**Other dev notes:**

| Path | Scope |
|------|-------|
| `docs/DEBUG_LOGS.md` | gui |
| `docs/DEBUG_VOLUME_VIEWER.md` | gui |
| `docs/BOND_DETECTION_NOTES.md` | gui |
| `docs/CRYSTAL_VIEWER_GEOMETRY.md` | gui |
| `docs/debug_notes.md` | misc |
| `docs/convergence_preset_note.md` | kernel |
| `docs/design/PHASE3C_*.md` (10 files) | kernel/runner |
| `docs/design/phase1_postmortem_root_causes.md` | kernel |

### 3.10 How-to / Playbook / Guide (NON-BINDING)

| Path | Scope | Notes |
|------|-------|-------|
| `docs/architecture/B1_ENGINE_PLAYBOOK.md` | engine | **BINDING SOP** for engine B1 work |
| `docs/architecture/ANALYSIS_PIPELINE_PLAYBOOK.md` | analysis | Playbook for analysis pipeline |
| `docs/CLI_API_REFERENCE.md` | api | API reference |
| `docs/DAEMON_API_REFERENCE.md` | api | Daemon API reference |
| `docs/STRUCTURE_AND_CLI_USAGE.md` | api | Usage guide |
| `docs/STANDALONE_QE.md` | engine/qe | Standalone QE guide |
| `docs/demo_store/ADDING_DEMOS.md` | demo | How to add demos |
| `docs/demo_store/DEMO_STORE_GUIDE.md` | demo | Demo store guide |
| `docs/testing_guide.md` | testing | Test guide |
| `docs/tests_overview.md` | testing | Test overview |
| `docs/TERMINOLOGY_DIRECTORIES.md` | repo-wide | Directory naming |
| `docs/checklists/RELAX_PR_REVIEW_CHECKLIST.md` | kernel/relax | PR checklist |

### 3.11 Engine Research & Exploration (NON-BINDING)

| Path | Engine |
|------|--------|
| `docs/engines/abinit/ABINIT_EXPLORATION.md` | abinit |
| `docs/engines/gaussian/GAUSSIAN_EXPLORATION.md` | gaussian |
| `docs/engines/gpaw/GPAW_EXPLORATION.md` | gpaw |
| `docs/engines/lammps/EXPLORE_SUMMARY.md` | lammps |
| `docs/engines/lammps/overview.md` | lammps |
| `docs/engines/lammps/workflows.md` | lammps |
| `docs/engines/lammps/output_parsing.md` | lammps |
| `docs/engines/lammps/integration_design.md` | lammps |
| `docs/engines/lammps/assets_and_potentials.md` | lammps |
| `docs/engines/lammps/codebase_review_notes.md` | lammps |
| `docs/engines/lammps/core_delta.md` | lammps |
| `docs/engines/orca/CORPUS_INDEX.md` | orca |
| `docs/engines/psi4/PSI4_ENGINE_EXPLORATION.md` | psi4 |
| `docs/engines/qmcpack/QMCPACK_EXPLORATION.md` | qmcpack |
| `docs/engines/qmcpack/QMCPACK_INTEGRATION.md` | qmcpack |
| `docs/engines/siesta/EXPLORATION.md` | siesta |
| `docs/engines/wannier90/EXPLORE_SUMMARY.md` | wannier90 |
| `docs/engines/xtb/EXPLORATION.md` | xtb |
| `docs/engines/yambo/YAMBO_EXPLORATION.md` | yambo |

**Engine-specific implementation docs:**

| Path | Engine |
|------|--------|
| `docs/engines/cp2k/CP2K_*.md` (8 files) | cp2k |
| `docs/engines/vasp/0[1-6]_*.md` (6 files) | vasp |
| `docs/engines/qe/RECIPE_FATBANDS.md` | qe |
| `docs/engines/qe/RECIPE_PDOS.md` | qe |
| `docs/engines/abinit/RECIPE_PDOS.md` | abinit |

### 3.12 Curated Indexes (NON-BINDING)

| Path | Engine |
|------|--------|
| `docs/engines/abinit/CURATED_INDEX.md` | abinit |
| `docs/engines/cp2k/CURATED_INDEX.md` | cp2k |
| `docs/engines/gaussian/CURATED_INDEX.md` | gaussian |
| `docs/engines/lammps/CURATED_INDEX.md` | lammps |
| `docs/engines/orca/CURATED_INDEX.md` | orca |
| `docs/engines/qmcpack/CURATED_INDEX.md` | qmcpack |
| `docs/engines/siesta/CURATED_INDEX.md` | siesta |
| `docs/engines/vasp/CURATED_INDEX.md` | vasp |
| `docs/engines/wannier90/CURATED_INDEX.md` | wannier90 |
| `docs/engines/xtb/CURATED_INDEX.md` | xtb |
| `docs/engines/yambo/CURATED_INDEX.md` | yambo |

### 3.13 Test Documentation (NON-BINDING)

| Path | Scope |
|------|-------|
| `tests/README.md` | testing |
| `tests/ARCHITECTURE.md` | testing |
| `tests/TEST_STRUCTURE.md` | testing |
| `tests/TEST_SUITE_MODULES.md` | testing |
| `tests/BIDIRECTIONAL_TEST_SUMMARY.md` | testing |
| `tests/IMPLEMENTATION_SUMMARY.md` | testing |
| `tests/MODULE_SUPPORT.md` | testing |
| `tests/OFFICIAL_TESTSUITE_RESULTS.md` | testing |
| `tests/SUMMARY.md` | testing |
| `tests/contract_crawler/*.md` (4 files) | testing |
| `tests/core/README_STEP_VERIFICATION.md` | testing |
| `tests/data/*.md` (4 files) | testing |
| `tests/docs/archive/*.md` (5 files) | testing |
| `tests/fixtures/golden_0873ebf/README.md` | testing |
| `tests/integration/*.md` (6 files) | testing |
| `tests/integration/scripts/README.md` | testing |

### 3.14 GUI Documentation (NON-BINDING)

| Path | Scope |
|------|-------|
| `gui/README.md` | gui |
| `gui/E2E_TEST_INVESTIGATION.md` | gui |
| `gui/tests/GUI_E2E_REFACTOR.md` | gui |

### 3.15 Project Meta (NON-BINDING)

| Path | Scope |
|------|-------|
| `README.md` | repo-wide |
| `CLAUDE.md` | repo-wide (AI instructions) |
| `.github/pull_request_template.md` | repo-wide (CI) |

### 3.16 Archived Documents (NON-BINDING)

`docs/archive/` contains 35+ files organized by date and topic:

| Path | Scope |
|------|-------|
| `docs/archive/GUI_CLI_PARITY_PLAN.md` | gui |
| `docs/archive/REFACTORING_PLAN.md` | kernel |
| `docs/archive/REFACTORING_SUMMARY.md` | kernel |
| `docs/archive/SCHEMA_REFACTOR_PLAN.md` | kernel |
| `docs/archive/SNAPSHOT_*.md` (2 files) | kernel |
| `docs/archive/CONSISTENCY_SWEEP_REPORT.md` | kernel |
| `docs/archive/2025-12/fixes/*.md` (3 files) | fixes |
| `docs/archive/2025-12/misc/*.md` (12 files) | misc |
| `docs/archive/2025-12/phase-notes/*.md` (8 files) | kernel |
| `docs/archive/2025-12/pipeline/*.md` (2 files) | kernel |
| `docs/archive/2025-12/tools/*.md` (1 file) | tools |
| `docs/archive/2025-12/audits/*.md` (9 files) | audits |
| `docs/archive/2025-12/import/*.md` (10 files) | kernel |
| `docs/archive/2025-12/qe-params/*.md` (2 files) | engine/qe |
| `docs/archive/2025-12/ai/*.md` (2 files) | ai |
| `docs/archive/2025-12/refactor/*.md` (2 files) | kernel |
| `docs/archive/2025-12/tests/*.md` (2 files) | testing |

---

## 4. Duplicates and Conflicts

### 4.1 Confirmed Duplicates (DELETE one copy)

| Authoritative Path | Duplicate Path | Issue |
|--------------------|----------------|-------|
| `docs/governance/STEP_TYPE_GEN_SPEC_CONSTITUTION.md` | `docs/spec/step_type_gen_spec_constitution.md` | Near-identical; duplicate omits `Parent Law` line |
| `docs/governance/ENGINE_INTEGRATION_CONSTITUTION.md` | `docs/spec/engine_integration/engine_integration_constitution.md` | Near-identical; duplicate omits `Parent Law` line |
| `docs/governance/API_CONSTITUTION.md` | `docs/api/API_CONSTITUTION.md` | Near-identical; duplicate omits `Parent Law` line |

### 4.2 Confirmed Obsolete

| Path | Reason |
|------|--------|
| `CONSTITUTION_ZH.md` | Explicitly marked DEPRECATED; English v2.1 is sole authority |
| `docs/specs/TRAJECTORY_CORE.md` | Explicitly marked SUPERSEDED by `ANALYSIS_OBJECTS_FRAMEWORK.md` |

### 4.3 Potential Conflicts

| Topic | Files | Conflict |
|-------|-------|----------|
| **API governance** | `docs/governance/API_CONSTITUTION.md` (L1) vs `docs/specs/API_FACADE_CONTRACT.md` (L2) | API_FACADE_CONTRACT declares itself "CONSTITUTION v2.0" but is NOT in governance/. Overlapping scope with API_CONSTITUTION. **Resolution needed**: promote to L1 or clarify as L2. |
| **Analysis binding spec** | `docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` (BINDING v1.4) vs `docs/specs/ANALYSIS_OBJECTS_FRAMEWORK.md` (PROPOSED v1.1) | PRIMITIVES is newer (2026-02-08) and more detailed than FRAMEWORK (2026-02-06). Both claim authority. **Resolution needed**: clarify which governs when they disagree. |
| **Duplicate IMPLEMENTATION_PLAN_MULTI_FRONTEND_REFACTOR** | `docs/IMPLEMENTATION_PLAN_MULTI_FRONTEND_REFACTOR.md` vs `docs/plan/IMPLEMENTATION_PLAN_MULTI_FRONTEND_REFACTOR.md` | Same filename in two locations. |
| **Duplicate HARDENING_SUMMARY** | `HARDENING_SUMMARY.md` (root) vs `docs/HARDENING_SUMMARY.md` | Same filename in two locations. |
| **Duplicate IMPLEMENTATION_SUMMARY_PSEUDO_REFACTOR** | `IMPLEMENTATION_SUMMARY_PSEUDO_REFACTOR.md` (root) vs `docs/IMPLEMENTATION_SUMMARY_PSEUDO_REFACTOR.md` | Same filename in two locations. |

---

## 5. Authoritative Document per Topic

For each topic area, the **single latest authoritative document** and what it supersedes:

| Topic | Authoritative Doc | Version | Status | Supersedes |
|-------|-------------------|---------|--------|------------|
| **Project constitution** | `CONSTITUTION.md` | 2.1 | FINAL | `CONSTITUTION_ZH.md` (v2.0, deprecated) |
| **API layering** | `docs/governance/API_CONSTITUTION.md` | 2.1 | FINAL | `docs/api/API_CONSTITUTION.md` (duplicate) |
| **API facade contract** | `docs/specs/API_FACADE_CONTRACT.md` | 2.0 | CONST | — (should be consolidated with API_CONSTITUTION) |
| **Engine integration** | `docs/governance/ENGINE_INTEGRATION_CONSTITUTION.md` | 1.0 | SPEC | `docs/spec/engine_integration/engine_integration_constitution.md` (duplicate) |
| **Engine recipes/runner** | `docs/governance/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` | 1.0 | FINAL | — |
| **Kernel dependencies** | `docs/governance/KERNEL_DEPENDENCY_SPEC.md` | 3.1 | PROPOSED | — |
| **Kernel exceptions** | `docs/governance/KERNEL_EXCEPTIONS.md` | 3.1 | ACTIVE | — |
| **GEN/SPEC step types** | `docs/governance/STEP_TYPE_GEN_SPEC_CONSTITUTION.md` | 1.1 | FINAL | `docs/spec/step_type_gen_spec_constitution.md` (duplicate) |
| **ParamSpace** | `docs/governance/PARAMSPACE_SPEC.md` | 1.0 | FINAL | — |
| **Provenance/history** | `docs/governance/PROVENANCE_VERSIONED_HISTORY_SPEC.md` | 1.1 | PROPOSED | — |
| **Analysis objects** | `docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` | 1.4 | BINDING | `docs/specs/TRAJECTORY_CORE.md` (superseded) |
| **Analysis framework** | `docs/specs/ANALYSIS_OBJECTS_FRAMEWORK.md` | 1.1 | PROPOSED | — (coexists with PRIMITIVES_SPEC) |
| **Relax workflows** | `docs/specs/RELAX_SPEC.md` | 1.0 | RATIFIED | — |
| **Structure fingerprint** | `docs/specs/STRUCTURE_FINGERPRINT_SPEC.md` | 2.1 | RATIFIED | — |
| **Multi-frontend arch** | `docs/specs/MULTI_FRONTEND_ARCHITECTURE_SPEC.md` | 2.0 | HARDENED | — |
| **Engine B1 playbook** | `docs/architecture/B1_ENGINE_PLAYBOOK.md` | 1.0 | ACTIVE | — |
| **Demo store** | `docs/spec/DEMO_STORE_SPEC.md` | Draft v6 | DRAFT | — |
| **Calc type/system kind** | `docs/architecture/CALC_TYPE_SYSTEM_KIND_SPEC.md` | 1.0 | DESIGN | — |
| **Project bundle** | `docs/architecture/PROJECT_BUNDLE_SPEC.md` | 1.0 | DESIGN | — |
| **Role inference** | `docs/architecture/ROLE_INFERENCE_SPEC.md` | 1.0 | DESIGN | — |
| **Input format** | `docs/design/UNIVERSAL_PARSER_WRITER_DESIGN.md` | — | DESIGN | — |
| **Driver protocol** | `docs/spec/engine_integration/engine_driver_protocol.md` | 1.0 | SPEC | — |

---

## 6. Missing Specs

Specs that **should exist** based on constitution sections and code complexity but are currently absent or incomplete:

| Topic | Constitution Ref | Current State | Recommendation |
|-------|------------------|---------------|----------------|
| **LAMMPS-specific invariants** | §14 | Only root constitution section; no standalone governance spec | Create `docs/governance/LAMMPS_SPEC.md` if LAMMPS rules grow beyond constitution section |
| **Geometry canonicalization** | §15 | Only root constitution section | Sufficient unless rules grow |
| **Species/pseudopotential spec** | §9 | Many audit/review docs but no single binding spec | Create `docs/governance/SPECIES_PSEUDO_SPEC.md` to consolidate the 10+ pseudo-related docs |
| **Parameter scan spec** | §10 | `docs/specs/parameter_scan.md` exists but status unclear | Clarify status (DRAFT/PROPOSED/RATIFIED) |
| **Incremental run spec** | §5 | Constitution section + scattered docs | Sufficient unless rules grow |
| **Lock/concurrency spec** | §4 | Constitution section only | Sufficient unless rules grow |
| **GUI/frontend spec** | — | `MULTI_FRONTEND_ARCHITECTURE_SPEC.md` exists but no GUI-specific binding spec | Consider `docs/governance/GUI_FRONTEND_SPEC.md` |
| **Input format spec** | — | Design doc exists but no binding spec for inputformat package | Create `docs/governance/INPUT_FORMAT_SPEC.md` once Phase B stabilizes |
| **Analysis pipeline governance** | — | PRIMITIVES_SPEC is BINDING but not in governance/ | Promote to `docs/governance/ANALYSIS_OBJECTS_SPEC.md` |

---

## 7. Proposed Target Layout

### Directory Structure

```
docs/
├── governance/                    # L0+L1: BINDING laws only
│   ├── L0_CONSTITUTION.md         # Symlink or redirect to root CONSTITUTION.md
│   ├── API_CONSTITUTION.md        # L1 (§18)
│   ├── API_FACADE_CONTRACT.md     # L1 (promoted from specs/)
│   ├── ENGINE_INTEGRATION_CONSTITUTION.md  # L1 (§17)
│   ├── ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md  # L1 (§17.4)
│   ├── KERNEL_DEPENDENCY_SPEC.md  # L1 (§19)
│   ├── KERNEL_EXCEPTIONS.md       # L1 (§19)
│   ├── STEP_TYPE_GEN_SPEC_CONSTITUTION.md  # L1 (§7)
│   ├── PARAMSPACE_SPEC.md         # L1 (§8)
│   ├── PROVENANCE_VERSIONED_HISTORY_SPEC.md  # L1 (§3)
│   ├── ANALYSIS_OBJECTS_SPEC.md   # L1 (promoted from architecture/)
│   └── README.md                  # Cross-reference index
│
├── specs/                         # L2: Ratified/binding domain specs
│   ├── RELAX_SPEC.md
│   ├── STRUCTURE_FINGERPRINT_SPEC.md
│   ├── MULTI_FRONTEND_ARCHITECTURE_SPEC.md
│   ├── ANALYSIS_OBJECTS_FRAMEWORK.md
│   ├── API_DTO_SCHEMA.md
│   ├── API_ERROR_TAXONOMY.md
│   ├── DEMO_STORE_SPEC.md         # Moved from docs/spec/
│   ├── CALC_TYPE_SYSTEM_KIND_SPEC.md  # Moved from architecture/
│   ├── PROJECT_BUNDLE_SPEC.md     # Moved from architecture/
│   ├── ROLE_INFERENCE_SPEC.md     # Moved from architecture/
│   ├── parameter_scan.md
│   └── engine_integration/        # Engine integration reference specs
│       ├── engine_driver_protocol.md
│       ├── engine_registry_and_dispatch.md
│       └── migration_gates_and_test_contract.md
│
├── design/                        # NON-BINDING: Architecture & design rationale
│   ├── ARCHITECTURE.md
│   ├── ARCHITECTURE_OVERVIEW.md
│   ├── UNIVERSAL_PARSER_WRITER_DESIGN.md
│   ├── ANALYSIS_OBJECTS_DESIGN.md
│   ├── TRAJECTORY_ANALYSIS_DESIGN.md
│   ├── VASP_ANALYSIS_DESIGN.md
│   ├── GUI_ARCHITECTURE.md
│   ├── HISTORY_DESIGN.md
│   ├── CANONICALIZATION_DESIGN.md
│   ├── PIPELINE_DATAFLOW_ANALYSIS.md
│   └── ... (other design docs)
│
├── guides/                        # NON-BINDING: How-tos, playbooks, references
│   ├── B1_ENGINE_PLAYBOOK.md      # Binding SOP (moved from architecture/)
│   ├── ANALYSIS_PIPELINE_PLAYBOOK.md
│   ├── CLI_API_REFERENCE.md
│   ├── DAEMON_API_REFERENCE.md
│   ├── ADDING_DEMOS.md
│   ├── DEMO_STORE_GUIDE.md
│   ├── testing_guide.md
│   └── ... (other guides)
│
├── engines/                       # Per-engine docs (unchanged, well-organized)
│   ├── abinit/
│   │   ├── CURATED_INDEX.md       # INDEX
│   │   ├── PHASE_B1_PLAN.md       # PLAN (keep for active reference)
│   │   ├── PHASE_B1_WORKLOG.md    # WLOG (keep for active reference)
│   │   └── ...
│   ├── cp2k/
│   ├── gaussian/
│   ├── gpaw/
│   ├── lammps/
│   ├── orca/
│   ├── psi4/
│   ├── qe/
│   ├── qmcpack/
│   ├── siesta/
│   ├── vasp/
│   ├── wannier90/
│   ├── xtb/
│   └── yambo/
│
├── history/                       # NON-BINDING: All progress artifacts
│   ├── audits/                    # Audit/review reports
│   │   ├── ADR_CONSISTENCY_REVIEW.md
│   │   ├── API_SLIMMING_AUDIT_VERDICT.md
│   │   ├── KERNEL_DRIFT_VERDICT_MEMO.md
│   │   ├── SEMANTIC_DRIFT_AUDIT_0873ebf_to_HEAD.md
│   │   └── ... (all audit/review files)
│   ├── summaries/                 # Implementation summaries/closeouts
│   │   ├── PHASE1_IR_IMPLEMENTATION_COMPLETE.md
│   │   ├── PHASE2_CLOSEOUT_REPORT.md
│   │   ├── LEGACY_PURGE_REPORT.md
│   │   └── ... (all summary files)
│   ├── plans/                     # Past implementation plans
│   │   ├── engine_driver_arch/
│   │   ├── engine_driver_migration/
│   │   ├── engine_driver_migration_qe/
│   │   ├── lammps/
│   │   └── ... (all plan files)
│   ├── worklogs/                  # Chronological progress logs
│   │   ├── analysis/              # Analysis pipeline worklogs
│   │   ├── api/                   # API worklogs
│   │   ├── kernel/                # Kernel worklogs
│   │   └── ... (all worklog files)
│   ├── dev-notes/                 # Debug/forensics/archaeology
│   │   ├── (all docs/dev/ files)
│   │   └── ...
│   └── archive/                   # Already-archived 2025-12 content (unchanged)
│       └── 2025-12/
│
├── roadmap/                       # Forward-looking planning (unchanged)
│   ├── CODE_REVIEW_ARCH_AUDIT.md
│   ├── DEMO_REGENERATION_REPORT.md
│   └── PLAN_2026_HIGH_IMPACT.md
│
└── research/                      # Research reports (unchanged)
    ├── ASE_ARCHITECTURE_REPORT.md
    └── RELAX_ENGINE_RESEARCH.md
```

### Key Moves

1. **Root `.md` files (76 files)**: Move ALL root-level `.md` files (except `CONSTITUTION.md`, `CLAUDE.md`, `README.md`) into `docs/history/` subdirectories
2. **`docs/spec/`**: Merge into `docs/specs/` (remove redundant `spec/` vs `specs/` split)
3. **`docs/api/`**: Move audits to `docs/history/audits/`, delete duplicate `API_CONSTITUTION.md`
4. **`docs/api_slim_audit/`**: Move to `docs/history/audits/`
5. **`docs/architecture/` specs**: Move binding specs to `docs/governance/` or `docs/specs/`; move playbooks to `docs/guides/`; move worklogs to `docs/history/worklogs/`
6. **`docs/impl/`**: Move to `docs/history/summaries/`
7. **`docs/plan/`**: Move to `docs/history/plans/`
8. **`docs/plans/`**: Merge into `docs/history/plans/`
9. **`docs/review/`**: Move to `docs/history/audits/`
10. **`docs/reviews/`**: Merge into `docs/history/audits/`
11. **`docs/audits/`**: Move to `docs/history/audits/`

---

## 8. Migration Mapping Table

### Critical Moves (Binding docs — do first)

| Current Path | Target Path | Action |
|--------------|-------------|--------|
| `CONSTITUTION_ZH.md` | `docs/history/archive/CONSTITUTION_ZH.md` | Archive deprecated |
| `docs/spec/step_type_gen_spec_constitution.md` | **DELETE** | Duplicate of governance/ |
| `docs/spec/engine_integration/engine_integration_constitution.md` | **DELETE** | Duplicate of governance/ |
| `docs/api/API_CONSTITUTION.md` | **DELETE** | Duplicate of governance/ |
| `docs/specs/API_FACADE_CONTRACT.md` | `docs/governance/API_FACADE_CONTRACT.md` | Promote to L1 |
| `docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` | `docs/governance/ANALYSIS_OBJECTS_SPEC.md` | Promote to L1 |
| `docs/specs/TRAJECTORY_CORE.md` | `docs/history/archive/TRAJECTORY_CORE.md` | Archive superseded |

### L2 Spec Consolidation

| Current Path | Target Path | Action |
|--------------|-------------|--------|
| `docs/spec/DEMO_STORE_SPEC.md` | `docs/specs/DEMO_STORE_SPEC.md` | Move to specs/ |
| `docs/spec/engine_integration/engine_driver_protocol.md` | `docs/specs/engine_integration/engine_driver_protocol.md` | Move to specs/ |
| `docs/spec/engine_integration/engine_registry_and_dispatch.md` | `docs/specs/engine_integration/engine_registry_and_dispatch.md` | Move to specs/ |
| `docs/spec/engine_integration/migration_gates_and_test_contract.md` | `docs/specs/engine_integration/migration_gates_and_test_contract.md` | Move to specs/ |
| `docs/architecture/CALC_TYPE_SYSTEM_KIND_SPEC.md` | `docs/specs/CALC_TYPE_SYSTEM_KIND_SPEC.md` | Move to specs/ |
| `docs/architecture/PROJECT_BUNDLE_SPEC.md` | `docs/specs/PROJECT_BUNDLE_SPEC.md` | Move to specs/ |
| `docs/architecture/ROLE_INFERENCE_SPEC.md` | `docs/specs/ROLE_INFERENCE_SPEC.md` | Move to specs/ |
| `docs/architecture/B1_ENGINE_PLAYBOOK.md` | `docs/guides/B1_ENGINE_PLAYBOOK.md` | Move to guides/ |

### Root-Level Cleanup (move 73 files)

| Current Pattern | Target Directory | Category |
|-----------------|------------------|----------|
| Root `*_AUDIT*.md`, `*_REVIEW*.md`, `*_VERDICT*.md` | `docs/history/audits/` | AUDIT |
| Root `*_SUMMARY*.md`, `*_REPORT*.md`, `*_COMPLETE*.md` | `docs/history/summaries/` | IMPL |
| Root `*_PLAN*.md` | `docs/history/plans/` | PLAN |
| Root `*_WORKLOG*.md`, `WORK_LOG_*.md` | `docs/history/worklogs/` | WLOG |
| Root `PHASE*_*.md`, `PR10_*.md` | `docs/history/summaries/` | IMPL |
| Root `*_FIX_*.md`, `*_FIXES_*.md` | `docs/history/summaries/` | IMPL |
| Root `DIAGNOSTIC_*.md` | `docs/history/dev-notes/` | DEV |

### docs/ Subdirectory Consolidation

| Current Path | Target Path | Action |
|--------------|-------------|--------|
| `docs/api/` (non-dup files) | `docs/history/audits/api/` | Move non-dup audits |
| `docs/api_slim_audit/` | `docs/history/audits/api/` | Merge |
| `docs/audits/` | `docs/history/audits/` | Merge |
| `docs/review/` | `docs/history/audits/` | Merge |
| `docs/reviews/` | `docs/history/audits/` | Merge |
| `docs/impl/` | `docs/history/summaries/engine/cp2k/` | Move |
| `docs/plan/` | `docs/history/plans/` | Move |
| `docs/plans/` | `docs/history/plans/` | Merge |
| `docs/dev/` | `docs/history/dev-notes/` | Move |
| `docs/checklists/` | `docs/history/audits/` | Move |
| `docs/tests/` | `docs/history/audits/testing/` | Move |
| `docs/worklog/` | `docs/history/worklogs/` | Move |
| `docs/spec/` | **DELETE** (after moving non-dups to specs/) | Remove empty dir |
| `docs/architecture/worklogs/` | `docs/history/worklogs/analysis/` | Move |

### Files That Stay

| Current Path | Reason |
|--------------|--------|
| `CONSTITUTION.md` | L0 — stays at root |
| `CLAUDE.md` | AI instructions — stays at root |
| `README.md` | Project readme — stays at root |
| `.github/pull_request_template.md` | CI template — stays |
| `docs/governance/*` | L1 — stays |
| `docs/specs/*` | L2 — stays (after consolidation) |
| `docs/engines/*` | Per-engine — stays (well-organized already) |
| `docs/design/*` | Design docs — stays (after cleanup) |
| `docs/guides/*` | New directory for how-tos |
| `docs/roadmap/*` | Forward-looking — stays |
| `docs/research/*` | Research — stays |
| `gui/*.md` | GUI docs — stays |
| `tests/**/*.md` | Test docs — stays |

---

## 9. Naming Conventions

### File Naming Rules

| Category | Pattern | Example |
|----------|---------|---------|
| Constitution | `<TOPIC>_CONSTITUTION.md` | `API_CONSTITUTION.md` |
| Governance Spec | `<TOPIC>_SPEC.md` | `PARAMSPACE_SPEC.md` |
| Domain Spec | `<TOPIC>_SPEC.md` | `RELAX_SPEC.md` |
| Design Doc | `<TOPIC>_DESIGN.md` | `UNIVERSAL_PARSER_WRITER_DESIGN.md` |
| Plan | `<TOPIC>_PLAN.md` or `PHASE_B1_PLAN.md` | `ABINIT_INTEGRATION_PLAN.md` |
| Worklog | `<TOPIC>_WORKLOG.md` or `PHASE_B1_WORKLOG.md` | `FIELD3D_ALL_ENGINES_WORKLOG.md` |
| Audit/Review | `<TOPIC>_AUDIT.md` or `<TOPIC>_REVIEW.md` | `API_SLIMMING_AUDIT_VERDICT.md` |
| Summary/Report | `<TOPIC>_SUMMARY.md` or `<TOPIC>_REPORT.md` | `PHASE2_CLOSEOUT_REPORT.md` |
| Playbook/Guide | `<TOPIC>_PLAYBOOK.md` or `<TOPIC>_GUIDE.md` | `B1_ENGINE_PLAYBOOK.md` |
| Index | `CURATED_INDEX.md` or `CORPUS_INDEX.md` | `CURATED_INDEX.md` |

### Version Headers

Every binding document (L0/L1/L2) MUST include a header block:

```markdown
# Title

**Version**: X.Y
**Status**: FINAL | PROPOSED | ACTIVE | RATIFIED | DRAFT | DEPRECATED | SUPERSEDED
**Parent Law**: CONSTITUTION.md §N (if L1)
**Last Updated**: YYYY-MM-DD
**Scope**: repo-wide | api | kernel | engine | engine/<name> | gui | analysis | provenance
```

### Status Taxonomy

| Status | Meaning | Can Be Changed? |
|--------|---------|-----------------|
| **FINAL** | Binding law; changes require constitution review | Yes, via governance process |
| **RATIFIED** | Binding domain spec; reviewed and approved | Yes, via spec owner |
| **ACTIVE** | Binding but evolving (e.g., exception lists) | Yes, quarterly review |
| **PROPOSED** | Under review; expected to become FINAL | Yes, pending review |
| **HARDENED** | Self-declared non-negotiable design | Yes, via spec owner |
| **DRAFT** | Work in progress; not yet binding | Yes, freely |
| **DEPRECATED** | No longer authoritative; kept for history | No (terminal) |
| **SUPERSEDED** | Replaced by newer document (pointer required) | No (terminal) |

### Directory Naming Rules

- All lowercase for new directories: `governance/`, `specs/`, `design/`, `guides/`, `history/`
- Engine directories: lowercase engine name (`abinit/`, `cp2k/`, `vasp/`)
- Archive subdirectories by date: `archive/YYYY-MM/`
- No `spec/` vs `specs/` split — use `specs/` (plural) only

---

*End of Documentation Taxonomy Review*
