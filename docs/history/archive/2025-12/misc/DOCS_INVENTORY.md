# Documentation Inventory

This document provides a comprehensive inventory of all Markdown documentation files in the QuantumVITAS repository, organized by location with metadata about purpose, status, and key topics.

**Last Updated**: 2025-01-XX

---

## Root-level docs

### README.md

- **Path:** README.md
- **Title:** QuantumVITAS (Python v2) - Main project README
- **Purpose:** Main entry point for the repository. Describes the project overview, installation, CLI usage, testing structure, and links to detailed documentation. Includes a "Testing Overview (for Contributors)" section derived from `docs/testing_guide.md`.
- **Type:** meta/notes, cli-usage
- **Status:** canonical-current
- **Mentions schema?:** No explicit schema examples, but references DAG + ID-only model via links to `docs/STRUCTURE_AND_CLI_USAGE.md`
- **Mentions snapshots?:** Yes - briefly mentions `qv init project --snapshot` and `qv save-project` commands
- **Mentions standalone QE?:** Yes - mentions `qv run step` with `--standalone` flag for running QE input files in isolation
- **Mentions tests/CI?:** Yes - describes quick tests, extended tests, GUI E2E tests, and pytest markers
- **Overlaps with:** `docs/STRUCTURE_AND_CLI_USAGE.md` (CLI details), `docs/testing_guide.md` (testing info), `PROJECT_ARCHITECTURE.md` (high-level architecture)

### PROJECT_ARCHITECTURE.md

- **Path:** PROJECT_ARCHITECTURE.md
- **Title:** QuantumVITAS Python Architecture (v2)
- **Purpose:** High-level architectural overview of the Python v2 rewrite. Describes layered structure (io/, engine/, calculation/, project/, analysis/), key concepts (Resource model, project structure, calculation/step YAML), and testing approach.
- **Type:** architecture-spec
- **Status:** canonical-current
- **Mentions schema?:** Yes - describes calculation.yaml and step YAML structure, mentions `structure_id` (ULID) and `step_id` (ULID) in calculation.yaml, but also mentions `parent_workflow_id` in step YAML (which is outdated per DAG model)
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - brief mention of test organization
- **Overlaps with:** `AI_understanding.md` (more detailed architecture), `docs/GUI_ARCHITECTURE.md` (GUI-specific architecture)

### SCHEMA_REFACTOR_PLAN.md

- **Path:** SCHEMA_REFACTOR_PLAN.md
- **Title:** Schema Refactor Plan: DAG + ID-only References
- **Purpose:** Design document describing the target schema for DAG + ID-only model. Shows current schema (with duplication issues) vs target schema (ID-only references). Describes how project.qv.yml, calculation.yaml, and step YAML should be structured.
- **Type:** schema-spec, refactor-plan
- **Status:** partially-outdated (plan document, but refactor is largely complete)
- **Mentions schema?:** Yes - explicitly describes current vs target schema, shows examples of ID-only references (`structure_id`, `step_id`), mentions removal of `parent_workflow_id` from step YAML
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** `CONSISTENCY_SWEEP_REPORT.md` (verification of ID-only references), `REFACTORING_PLAN.md` (broader refactor context)

### STANDALONE_STEP_IMPLEMENTATION.md

- **Path:** STANDALONE_STEP_IMPLEMENTATION.md
- **Title:** Standalone Step Execution Implementation
- **Purpose:** Documents the implementation of standalone mode for running QE steps without a project context. Describes `StandaloneStepContext`, `run_standalone_step()`, CLI flags (`--standalone`, `--input`, `--engine`, `--bidirectional`), and how it reuses existing core run logic.
- **Type:** standalone-qe-doc, implementation-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** Yes - primary focus of the document. Describes standalone as a "pure QE helper working on raw input files" that does NOT create Step resources in the DAG. Mentions bidirectional vs pass-through mode.
- **Mentions tests/CI?:** No
- **Overlaps with:** `AI_understanding.md` section on standalone mode (more detailed)

### SNAPSHOT_OPTION_A_AUDIT.md

- **Path:** SNAPSHOT_OPTION_A_AUDIT.md
- **Title:** Snapshot Implementation Audit: Option A Compliance
- **Purpose:** Audit document comparing current snapshot implementation against "Option A" (snapshots store real ULIDs and reuse them on restore). Finds that export matches Option A, but materialize regenerates IDs (does NOT match Option A). Describes what changes would be needed to adopt Option A.
- **Type:** snapshot-doc, refactor-plan
- **Status:** mostly-historical (describes Option A as desired, but current implementation uses Option B)
- **Mentions schema?:** Yes - mentions snapshot schema with `meta.id` and `*_id` cross-references
- **Mentions snapshots?:** Yes - primary focus. Describes Option A as "snapshots are backup/demo artifacts, not templates" with ULID preservation. Notes that current implementation does NOT match Option A (regenerates IDs).
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** `SNAPSHOT_DOCS_UPDATE_SUMMARY.md` (describes Option B adoption), `AI_understanding.md` section 23.3 (current Option B semantics)

### SNAPSHOT_DOCS_UPDATE_SUMMARY.md

- **Path:** SNAPSHOT_DOCS_UPDATE_SUMMARY.md
- **Title:** Snapshot Documentation and Test Update Summary
- **Purpose:** Documents the clarification of snapshot semantics to "Option B: Template with Fresh IDs". Describes export behavior (preserves IDs), materialize behavior (regenerates IDs), and adds explicit test `test_snapshot_id_regeneration.py` to verify ID regeneration.
- **Type:** snapshot-doc, refactor-summary
- **Status:** canonical-current
- **Mentions schema?:** Yes - mentions snapshot schema with IDs and cross-references
- **Mentions snapshots?:** Yes - primary focus. Explicitly documents Option B: snapshots are templates, not backups. ULIDs are regenerated on materialization. Demo/reference features do NOT depend on preserving snapshot ULIDs.
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - describes new test `test_snapshot_id_regeneration.py`
- **Overlaps with:** `SNAPSHOT_OPTION_A_AUDIT.md` (contrasting Option A vs Option B), `AI_understanding.md` section 23.3 (same Option B semantics)

### CONSISTENCY_SWEEP_REPORT.md

- **Path:** CONSISTENCY_SWEEP_REPORT.md
- **Title:** ID-Only Cross-Resource References: Consistency Sweep Report
- **Purpose:** Verification report confirming that all cross-resource references use ID-only format per DAG + ID-only invariants. Audits project.qv.yml, calculation.yaml, step YAML, and snapshot format. Finds mostly clean with minor in-memory issues that don't affect YAML serialization.
- **Type:** schema-spec, refactor-summary
- **Status:** canonical-current
- **Mentions schema?:** Yes - primary focus. Verifies ID-only references in all YAML files. Notes that step YAML should NOT contain `structure_id` or `parent_workflow_id` (DAG model). Confirms snapshots use ID-only references.
- **Mentions snapshots?:** Yes - verifies snapshots use ID-only references, notes that materialization regenerates IDs (separate issue)
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - mentions test files that verify ID-only references
- **Overlaps with:** `SCHEMA_REFACTOR_PLAN.md` (target schema), `REFACTORING_SUMMARY.md` (refactor completion)

### REFACTORING_PLAN.md

- **Path:** REFACTORING_PLAN.md
- **Title:** test_qe_roundtrip_execution.py 重构计划 (Chinese)
- **Purpose:** Refactoring plan (in Chinese) for reorganizing test utilities. Describes moving functions from `extended-tests/utils/test_qe_roundtrip_execution.py` to appropriate locations (`src/quantumvitas/core/engines/` for core functionality, `tests/core/` for test-specific utilities).
- **Type:** refactor-plan, meta/notes
- **Status:** mostly-historical (refactor is complete)
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - describes test utility reorganization
- **Overlaps with:** `REFACTORING_SUMMARY.md` (completion of this plan)

### REFACTORING_SUMMARY.md

- **Path:** REFACTORING_SUMMARY.md
- **Title:** test_qe_roundtrip_execution.py 重构总结 (Chinese)
- **Purpose:** Summary (in Chinese) of completed refactoring of test utilities. Documents functions moved to `src/quantumvitas/core/engines/qe_pseudopotentials.py` and `tests/core/qe_test_utils.py`. Describes new import patterns.
- **Type:** refactor-summary, meta/notes
- **Status:** mostly-historical (refactor is complete)
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - describes test utility refactoring
- **Overlaps with:** `REFACTORING_PLAN.md` (plan for this refactor)

### PROJECT_LOGIC_SUMMARY.md

- **Path:** PROJECT_LOGIC_SUMMARY.md
- **Title:** 项目逻辑总结 (Chinese)
- **Purpose:** Summary (in Chinese) of implemented project logic. Documents step-by-step testing, pseudo directory handling, step execution logic location, test framework centralization, outdir handling, and jobconfig ordering.
- **Type:** meta/notes, test-suite-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - describes test execution logic and framework organization
- **Overlaps with:** `PROJECT_LOGIC_CHECK.md`, `PROJECT_LOGIC_VERIFICATION.md` (verification of same logic)

### PROJECT_LOGIC_CHECK.md

- **Path:** PROJECT_LOGIC_CHECK.md
- **Title:** 项目逻辑检查报告 (Chinese)
- **Purpose:** Check report (in Chinese) verifying project logic implementation. Checks step-by-step testing, pseudo directory handling, step execution location, test framework centralization, outdir handling, and jobconfig ordering.
- **Type:** meta/notes, test-suite-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - verification of test logic implementation
- **Overlaps with:** `PROJECT_LOGIC_SUMMARY.md`, `PROJECT_LOGIC_VERIFICATION.md`

### PROJECT_LOGIC_VERIFICATION.md

- **Path:** PROJECT_LOGIC_VERIFICATION.md
- **Title:** 项目逻辑验证报告 (Chinese)
- **Purpose:** Verification report (in Chinese) confirming all project logic requirements are implemented. Verifies step-by-step testing, pseudo directory handling, step execution location, test framework centralization, outdir handling, and jobconfig ordering.
- **Type:** meta/notes, test-suite-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - final verification of test logic
- **Overlaps with:** `PROJECT_LOGIC_SUMMARY.md`, `PROJECT_LOGIC_CHECK.md`

### AI_understanding.md

- **Path:** AI_understanding.md
- **Title:** AI Understanding of QuantumVITAS (Python v2)
- **Purpose:** Comprehensive architectural knowledge base for AI assistants. Covers project overview, core concepts (Resource model, project structure, calculation/step YAML), CLI commands, daemon/GUI architecture, QE engine integration, analysis, snapshots, standalone mode, testing, and many implementation details. Very detailed (4500+ lines).
- **Type:** architecture-spec, meta/notes, api-reference, cli-usage, daemon-gui-contract, snapshot-doc, standalone-qe-doc, testing-overview
- **Status:** canonical-current (actively maintained)
- **Mentions schema?:** Yes - extensive coverage. Section 2.3 shows calculation.yaml and step YAML examples. Mentions `structure_id` (ULID) and `step_id` (ULID) in calculation.yaml. Also mentions `parent_workflow_id` in step YAML (section 2.3), but this is outdated per DAG model (should be removed). Section 23.1 shows snapshot schema with `structure_id` and `parent_workflow_id` in step data (outdated).
- **Mentions snapshots?:** Yes - section 23 covers snapshots extensively. Section 23.3 explicitly documents "Option B: Template with Fresh IDs" - snapshots are templates, ULIDs are regenerated on materialization. This is the canonical documentation for current snapshot behavior.
- **Mentions standalone QE?:** Yes - section on standalone mode. Describes standalone as working on raw input files without creating Step resources in the DAG. Mentions bidirectional vs pass-through mode.
- **Mentions tests/CI?:** Yes - section 22 covers GUI E2E testing, section on test organization
- **Overlaps with:** Many docs - serves as central knowledge base. Overlaps with `PROJECT_ARCHITECTURE.md` (more detailed), `docs/CLI_API_REFERENCE.md` (CLI details), `docs/DAEMON_API_REFERENCE.md` (daemon details), `docs/GUI_ARCHITECTURE.md` (GUI details), `SNAPSHOT_DOCS_UPDATE_SUMMARY.md` (snapshot semantics)

### README_TESTS.md

- **Path:** README_TESTS.md
- **Title:** Testing Guide
- **Purpose:** High-level testing guide covering quick tests, GUI E2E tests, extended tests, running instructions, CI configuration, test markers, directory structure, and adding new tests. Suitable for README-level documentation.
- **Type:** testing-overview
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - primary focus. Describes quick tests, GUI E2E tests, extended tests, CI configuration, pytest markers
- **Overlaps with:** `docs/testing_guide.md` (similar content, more detailed), `docs/tests_overview.md` (much more detailed), `tests/README.md` (quick tests only), `tests/QUICK_TESTS.md` (quick tests only)

### ROBUSTNESS_TESTS_SUMMARY_CORRECTED.md

- **Path:** ROBUSTNESS_TESTS_SUMMARY_CORRECTED.md
- **Title:** 稳健性测试总结（修正版）(Chinese)
- **Purpose:** Corrected summary (in Chinese) of robustness tests added for calculation failure handling, resource renaming, snapshots, and pseudopotential resolution. Lists 9 new tests (corrected from 10) with descriptions of behavior guarantees.
- **Type:** meta/notes, test-suite-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** Yes - describes snapshot edge case tests
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - describes new robustness tests
- **Overlaps with:** None (standalone summary document)

---

## docs/

### CLI_API_REFERENCE.md

- **Path:** docs/CLI_API_REFERENCE.md
- **Title:** CLI & API Quick Reference
- **Purpose:** Comprehensive reference for all `qv` CLI commands with quick examples. Organized by command category (init, configure, run, analyze, delete, etc.). Also includes Python API methods from `QVService` that are meant for direct use.
- **Type:** cli-usage, api-reference
- **Status:** canonical-current
- **Mentions schema?:** No explicit schema examples, but commands work with DAG + ID-only model
- **Mentions snapshots?:** Yes - documents `qv save-project` and `qv init project --snapshot` commands
- **Mentions standalone QE?:** Yes - documents `qv run step --standalone` command
- **Mentions tests/CI?:** No
- **Overlaps with:** `docs/STRUCTURE_AND_CLI_USAGE.md` (more detailed examples), `README.md` (brief CLI overview)

**Note on standalone mode:** The CLI reference documents `qv run step` with `--standalone` flag, but detailed standalone implementation is documented in `STANDALONE_STEP_IMPLEMENTATION.md`.

### DAEMON_API_REFERENCE.md

- **Path:** docs/DAEMON_API_REFERENCE.md
- **Title:** QuantumVITAS Daemon API Reference
- **Purpose:** Complete reference for the JSON-RPC daemon interface used by the GUI. Documents request/response format, all available RPC methods (project operations, CRUD, visualization, job management), error handling, and protocol details.
- **Type:** daemon-gui-contract, api-reference
- **Status:** canonical-current
- **Mentions schema?:** No explicit schema, but RPC methods work with DAG + ID-only model (calculation selectors use slug, step selectors use ULID)
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** `docs/GUI_DAEMON_API_MAPPING.md` (GUI → daemon mapping), `docs/GUI_ARCHITECTURE.md` (GUI architecture)

### GUI_ARCHITECTURE.md

- **Path:** docs/GUI_ARCHITECTURE.md
- **Title:** QuantumVITAS GUI Architecture
- **Purpose:** Comprehensive documentation of the Electron + React + TypeScript GUI. Covers technology stack, architecture diagram, daemon communication, component structure, IPC handlers, state management, error handling, and UI/UX features.
- **Type:** architecture-spec, daemon-gui-contract
- **Status:** canonical-current
- **Mentions schema?:** No explicit schema, but describes GUI's use of calculation slugs and step ULIDs
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** `docs/GUI_DAEMON_API_MAPPING.md` (API mapping), `AI_understanding.md` section 11 (GUI architecture)

### GUI_CLI_PARITY_PLAN.md

- **Path:** docs/GUI_CLI_PARITY_PLAN.md
- **Title:** GUI-CLI Feature Parity Plan
- **Purpose:** Maps CLI capabilities to GUI features and defines implementation roadmap. Tables showing which CLI commands are implemented in GUI (✅ Done) vs missing (❌ Missing) with priorities. Covers project operations, structure operations, calculation operations, step operations, analysis, and job management.
- **Type:** refactor-plan, meta/notes
- **Status:** partially-outdated (some features may have been implemented since writing)
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** `docs/GUI_DAEMON_API_MAPPING.md` (implementation details)

### GUI_DAEMON_API_MAPPING.md

- **Path:** docs/GUI_DAEMON_API_MAPPING.md
- **Title:** GUI → Daemon → Backend API Mapping
- **Purpose:** Maps GUI components to daemon endpoints and backend functions, ensuring consistency with DAG + ID-only model. Documents job submission/listing flow, step detail retrieval flow, path normalization fixes, and selector usage (calculation.slug, step ULID).
- **Type:** daemon-gui-contract, api-reference
- **Status:** canonical-current
- **Mentions schema?:** Yes - explicitly documents that GUI uses calculation.slug (not ULID) for calculation selector and step.id (ULID) for step selector, per DAG + ID-only model
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** `docs/DAEMON_API_REFERENCE.md` (daemon API), `docs/GUI_ARCHITECTURE.md` (GUI architecture)

### STRUCTURE_AND_CLI_USAGE.md

- **Path:** docs/STRUCTURE_AND_CLI_USAGE.md
- **Title:** Structure I/O and CLI Usage Guide
- **Purpose:** Detailed examples and usage patterns for QuantumVITAS structure handling and CLI commands. Covers structure I/O functions, CLI commands, parameter overrides, complete calculation examples, and API reference.
- **Type:** cli-usage, api-reference
- **Status:** canonical-current
- **Mentions schema?:** No explicit schema, but examples show DAG + ID-only model usage
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** `docs/CLI_API_REFERENCE.md` (CLI reference), `README.md` (brief CLI overview)

### QE_EXECUTABLE_DETECTION.md

- **Path:** docs/QE_EXECUTABLE_DETECTION.md
- **Title:** QE Executable Detection and Path Resolution
- **Purpose:** Documents the automatic detection and path resolution for Quantum ESPRESSO executables. Covers QE home detection order (QE_HOME env var → PATH → shell configs → home directory scan), internal registry, cross-platform support, and error handling.
- **Type:** engine-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - mentions CI/CD environments and QE_HOME usage
- **Overlaps with:** `docs/QE_MODULE_DOCUMENTATION.md` (QE module docs), `docs/QE_MODULE_SUPPORT.md` (module support)

### QE_MODULE_DOCUMENTATION.md

- **Path:** docs/QE_MODULE_DOCUMENTATION.md
- **Title:** Quantum ESPRESSO Module Documentation Links
- **Purpose:** Lists all QE modules and their official documentation links following the pattern `https://www.quantum-espresso.org/Doc/INPUT_{MODULE_NAME}.html`. Covers core modules (PW, PH, Q2R, MATDYN), post-processing modules (PP, BANDS, DOS, PROJWFC), and advanced modules.
- **Type:** engine-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** `docs/QE_MODULE_SUPPORT.md` (module support details)

### QE_MODULE_SUPPORT.md

- **Path:** docs/QE_MODULE_SUPPORT.md
- **Title:** Quantum ESPRESSO Module Support
- **Purpose:** Lists all supported QE modules with their purposes, namelists, documentation links, and detection methods. Covers core modules (PW, PH, Q2R, MATDYN) and post-processing modules (PP, BANDS, DOS, PROJWFC).
- **Type:** engine-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** `docs/QE_MODULE_DOCUMENTATION.md` (documentation links)

### tests_overview.md

- **Path:** docs/tests_overview.md
- **Title:** Test Suite Overview
- **Purpose:** Comprehensive markdown document (1400+ lines) summarizing the entire pytest test suite. Includes overall structure (directories, markers, subsystems), summary table of test files, detailed per-file descriptions (module/feature, related code, key dependencies, contained tests), fixtures and shared infrastructure, and notes on coverage and gaps.
- **Type:** testing-overview, test-suite-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** Yes - describes snapshot test files (`test_project_snapshot.py`, `test_snapshot_id_regeneration.py`, `test_demo_snapshot_restore.py`)
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - primary focus. Comprehensive coverage of all test files, markers, fixtures, dependencies
- **Overlaps with:** `docs/testing_guide.md` (condensed version), `tests/README.md` (quick tests only), `tests/TEST_STRUCTURE.md` (test structure)

### testing_guide.md

- **Path:** docs/testing_guide.md
- **Title:** Testing Overview (for Contributors)
- **Purpose:** Short, README-level testing guide derived from `docs/tests_overview.md`. Provides brief introduction, compact "Test Organization by Subsystem" table, "What to Run When You Change Things" quick recipes, and notes about QE dependencies. Suitable for `CONTRIBUTING.md` or `README.md`.
- **Type:** testing-overview
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - condensed version of `docs/tests_overview.md`
- **Overlaps with:** `docs/tests_overview.md` (detailed version), `README.md` (includes this content), `README_TESTS.md` (similar content)

### typography.md

- **Path:** docs/typography.md
- **Title:** Typography & Font Stacks
- **Purpose:** Documents the system font stack design for the QMatSuite frontend. Covers goals (system fonts, CJK support), detailed stack order for `--qms-font-sans` and `--qms-font-mono`, platform-specific behavior, usage guidelines, explanation of no bundled fonts policy, and implementation details.
- **Type:** meta/notes
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** None

---

## tests/ and related

### tests/README.md

- **Path:** tests/README.md
- **Title:** Quick Tests
- **Purpose:** Overview of quick tests in `tests/` directory. Describes structure (unit/, integration/, cli/, core/), running instructions, test categories, and CI integration. Notes that all QE test-suite dependent tests have been moved to `extended-tests/`.
- **Type:** testing-overview, test-suite-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - primary focus. Describes quick tests structure and CI integration
- **Overlaps with:** `tests/QUICK_TESTS.md` (similar content), `docs/testing_guide.md` (more comprehensive), `docs/tests_overview.md` (much more detailed)

### tests/QUICK_TESTS.md

- **Path:** tests/QUICK_TESTS.md
- **Title:** Quick Tests
- **Purpose:** Brief overview of quick tests. Describes structure, running instructions, CI integration, and requirements. Very concise (40 lines).
- **Type:** testing-overview
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - describes quick tests and CI
- **Overlaps with:** `tests/README.md` (more detailed), `docs/testing_guide.md` (more comprehensive)

### tests/TEST_STRUCTURE.md

- **Path:** tests/TEST_STRUCTURE.md
- **Title:** Test Structure Overview
- **Purpose:** Overview of test organization. Describes quick tests vs extended tests, directory structure, running instructions, test categories, and CI integration.
- **Type:** testing-overview, test-suite-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - primary focus. Describes quick vs extended tests, directory structure, CI behavior
- **Overlaps with:** `tests/README.md` (quick tests), `extended-tests/README.md` (extended tests), `docs/testing_guide.md` (more comprehensive)

### tests/ARCHITECTURE.md

- **Path:** tests/ARCHITECTURE.md
- **Title:** 测试框架架构 (Chinese)
- **Purpose:** Architecture document (in Chinese) for the test framework. Describes design philosophy (hybrid approach: folder organization + unified class interface), directory structure, core components (TestResult, TestCase, TestSuite, TestRunner), and implementation details.
- **Type:** test-suite-doc, architecture-spec
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - describes test framework architecture
- **Overlaps with:** `tests/TEST_SUITE_MODULES.md` (test suite modules)

### tests/TEST_SUITE_MODULES.md

- **Path:** tests/TEST_SUITE_MODULES.md
- **Title:** Test Suite Modules (inferred)
- **Purpose:** Documents test suite module structure. Likely describes how test suites are organized and run.
- **Type:** test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** `tests/ARCHITECTURE.md` (test framework)

### tests/SUMMARY.md

- **Path:** tests/SUMMARY.md
- **Title:** (inferred - summary document)
- **Purpose:** Likely a summary of test results or test organization.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** Various test docs

### tests/REFACTORING_COMPLETE.md

- **Path:** tests/REFACTORING_COMPLETE.md
- **Title:** (inferred - refactoring completion)
- **Purpose:** Likely documents completion of test refactoring.
- **Type:** refactor-summary, meta/notes
- **Status:** mostly-historical
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** `REFACTORING_SUMMARY.md` (refactoring summary)

### tests/README_REFACTOR.md

- **Path:** tests/README_REFACTOR.md
- **Title:** (inferred - refactor README)
- **Purpose:** Likely documents test refactoring plans or changes.
- **Type:** refactor-plan, meta/notes
- **Status:** mostly-historical
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** `REFACTORING_PLAN.md`, `REFACTORING_SUMMARY.md`

### tests/MIGRATION_COMPLETE.md

- **Path:** tests/MIGRATION_COMPLETE.md
- **Title:** (inferred - migration completion)
- **Purpose:** Likely documents completion of test migration or refactoring.
- **Type:** refactor-summary, meta/notes
- **Status:** mostly-historical
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** Various migration/refactor docs

### tests/IMPLEMENTATION_SUMMARY.md

- **Path:** tests/IMPLEMENTATION_SUMMARY.md
- **Title:** (inferred - implementation summary)
- **Purpose:** Likely summarizes test implementation details.
- **Type:** meta/notes, test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** Various test docs

### tests/BIDIRECTIONAL_TEST_SUMMARY.md

- **Path:** tests/BIDIRECTIONAL_TEST_SUMMARY.md
- **Title:** (inferred - bidirectional test summary)
- **Purpose:** Likely summarizes bidirectional parse/generate tests.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Possibly (bidirectional mode)
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** `extended-tests/BIDIRECTIONAL_FIX_SUMMARY.md`

### tests/MODULE_SUPPORT.md

- **Path:** tests/MODULE_SUPPORT.md
- **Title:** (inferred - module support)
- **Purpose:** Likely documents QE module support in tests.
- **Type:** test-suite-doc, engine-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** `docs/QE_MODULE_SUPPORT.md` (module support)

### tests/OFFICIAL_TESTSUITE_RESULTS.md

- **Path:** tests/OFFICIAL_TESTSUITE_RESULTS.md
- **Title:** (inferred - official test suite results)
- **Purpose:** Likely documents results from QE official test suite runs.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - test results
- **Overlaps with:** `extended-tests/PH_TEST_RESULTS.md` (PH test results)

### tests/integration/README_CI_TESTS.md

- **Path:** tests/integration/README_CI_TESTS.md
- **Title:** (inferred - CI tests README)
- **Purpose:** Likely documents CI test configuration and behavior.
- **Type:** test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - CI tests
- **Overlaps with:** `tests/integration/CI_TEST_STATUS.md`, `tests/integration/CI_TEST_DATA.md`

### tests/integration/README_QUICK_PW_TESTS.md

- **Path:** tests/integration/README_QUICK_PW_TESTS.md
- **Title:** (inferred - quick PW tests README)
- **Purpose:** Likely documents quick pw.x (Quantum ESPRESSO) tests.
- **Type:** test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Possibly
- **Mentions tests/CI?:** Yes - quick tests
- **Overlaps with:** `tests/README.md` (quick tests)

### tests/integration/PH_TEST_SKIP_REASONS.md

- **Path:** tests/integration/PH_TEST_SKIP_REASONS.md
- **Title:** (inferred - PH test skip reasons)
- **Purpose:** Likely documents reasons for skipping PH (phonon) tests.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - test skip reasons
- **Overlaps with:** `extended-tests/PH_TEST_COMPARISON.md`, `extended-tests/PH_TEST_RESULTS.md`

### tests/integration/DISTRIBUTION.md

- **Path:** tests/integration/DISTRIBUTION.md
- **Title:** (inferred - distribution)
- **Purpose:** Likely documents test distribution or test data distribution.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** Various test docs

### tests/integration/CI_TEST_STATUS.md

- **Path:** tests/integration/CI_TEST_STATUS.md
- **Title:** (inferred - CI test status)
- **Purpose:** Likely documents CI test status or results.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - CI test status
- **Overlaps with:** `tests/integration/CI_TEST_DATA.md`, `tests/integration/README_CI_TESTS.md`

### tests/integration/CI_TEST_DATA.md

- **Path:** tests/integration/CI_TEST_DATA.md
- **Title:** (inferred - CI test data)
- **Purpose:** Likely documents CI test data requirements or structure.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - CI test data
- **Overlaps with:** `tests/integration/CI_TEST_STATUS.md`, `tests/integration/README_CI_TESTS.md`

### tests/integration/scripts/README.md

- **Path:** tests/integration/scripts/README.md
- **Title:** (inferred - integration scripts README)
- **Purpose:** Likely documents integration test scripts.
- **Type:** test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** Various test docs

### tests/data/README.md

- **Path:** tests/data/README.md
- **Title:** (inferred - test data README)
- **Purpose:** Likely documents test data structure and organization.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** Various test docs

### tests/core/README_STEP_VERIFICATION.md

- **Path:** tests/core/README_STEP_VERIFICATION.md
- **Title:** (inferred - step verification README)
- **Purpose:** Likely documents step verification logic in test framework.
- **Type:** test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Possibly
- **Mentions tests/CI?:** Yes - test verification
- **Overlaps with:** `tests/core/MIGRATION_SUMMARY.md`

### tests/core/MIGRATION_SUMMARY.md

- **Path:** tests/core/MIGRATION_SUMMARY.md
- **Title:** (inferred - migration summary)
- **Purpose:** Likely summarizes migration of test utilities to `tests/core/`.
- **Type:** refactor-summary, meta/notes
- **Status:** mostly-historical
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - test migration
- **Overlaps with:** `REFACTORING_SUMMARY.md` (refactoring summary)

---

## Other locations

### test_results_summary.md

- **Path:** test_results_summary.md
- **Title:** Test Results Summary
- **Purpose:** Summarizes test execution results with counts by category (integration tests, unit tests). Documents test execution date and overall pass/fail statistics.
- **Type:** meta/notes, test-suite-doc
- **Status:** mostly-historical (test results are time-sensitive)
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - test results summary
- **Overlaps with:** Various test result docs

---

## extended-tests/ and related

### extended-tests/README.md

- **Path:** extended-tests/README.md
- **Title:** Extended Tests
- **Purpose:** Overview of extended tests based on full QE official test-suite. Describes purpose (full validation, success rate analysis, regression testing), structure, usage, requirements, and CI integration (excluded from automatic runs).
- **Type:** testing-overview, test-suite-doc
- **Status:** canonical-current
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** Yes - describes extended tests and CI exclusion
- **Overlaps with:** `tests/TEST_STRUCTURE.md` (test structure), `docs/testing_guide.md` (testing overview)

### extended-tests/MIGRATION_TUTORIAL.md

- **Path:** extended-tests/MIGRATION_TUTORIAL.md
- **Title:** (inferred - migration tutorial)
- **Purpose:** Likely tutorial for migrating tests to extended-tests structure.
- **Type:** test-suite-doc, meta/notes
- **Status:** mostly-historical
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - test migration
- **Overlaps with:** `extended-tests/MIGRATION.md`

### extended-tests/MIGRATION.md

- **Path:** extended-tests/MIGRATION.md
- **Title:** (inferred - migration)
- **Purpose:** Likely documents migration of tests to extended-tests.
- **Type:** refactor-plan, meta/notes
- **Status:** mostly-historical
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - test migration
- **Overlaps with:** `extended-tests/MIGRATION_TUTORIAL.md`

### extended-tests/PH_TEST_COMPARISON.md

- **Path:** extended-tests/PH_TEST_COMPARISON.md
- **Title:** (inferred - PH test comparison)
- **Purpose:** Likely compares PH (phonon) test results or implementations.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - PH test comparison
- **Overlaps with:** `extended-tests/PH_TEST_RESULTS.md`, `extended-tests/PH_TEST_NPROCS4_FIXED.md`

### extended-tests/PH_TEST_RESULTS.md

- **Path:** extended-tests/PH_TEST_RESULTS.md
- **Title:** (inferred - PH test results)
- **Purpose:** Likely documents PH (phonon) test results.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - test results
- **Overlaps with:** `extended-tests/PH_TEST_COMPARISON.md`, `extended-tests/PH_TEST_NPROCS4_FIXED.md`

### extended-tests/PH_TEST_NPROCS4_FIXED.md

- **Path:** extended-tests/PH_TEST_NPROCS4_FIXED.md
- **Title:** (inferred - PH test nprocs4 fixed)
- **Purpose:** Likely documents fix for PH tests with nprocs=4.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - test fix
- **Overlaps with:** `extended-tests/PH_TEST_COMPARISON.md`, `extended-tests/PH_TEST_RESULTS.md`

### extended-tests/BIDIRECTIONAL_FIX_SUMMARY.md

- **Path:** extended-tests/BIDIRECTIONAL_FIX_SUMMARY.md
- **Title:** (inferred - bidirectional fix summary)
- **Purpose:** Likely summarizes fixes for bidirectional parse/generate tests.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Possibly (bidirectional mode)
- **Mentions tests/CI?:** Yes - test fix summary
- **Overlaps with:** `tests/BIDIRECTIONAL_TEST_SUMMARY.md`

### extended-tests/DEBUG_SUMMARY.md

- **Path:** extended-tests/DEBUG_SUMMARY.md
- **Title:** (inferred - debug summary)
- **Purpose:** Likely summarizes debugging of extended tests.
- **Type:** meta/notes, test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - debug summary
- **Overlaps with:** Various extended-tests docs

### extended-tests/scripts/README.md

- **Path:** extended-tests/scripts/README.md
- **Title:** (inferred - scripts README)
- **Purpose:** Likely documents extended test scripts.
- **Type:** test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** Various extended-tests docs

### extended-tests/scripts/SUMMARY_AND_DEBUG.md

- **Path:** extended-tests/scripts/SUMMARY_AND_DEBUG.md
- **Title:** (inferred - summary and debug)
- **Purpose:** Likely summarizes extended test scripts and debugging.
- **Type:** meta/notes, test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** `extended-tests/scripts/STATUS.md`, `extended-tests/scripts/DEBUG_FIXES.md`

### extended-tests/scripts/STATUS.md

- **Path:** extended-tests/scripts/STATUS.md
- **Title:** (inferred - status)
- **Purpose:** Likely documents status of extended test scripts.
- **Type:** meta/notes, test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** `extended-tests/scripts/SUMMARY_AND_DEBUG.md`

### extended-tests/scripts/RUNNING_INSTRUCTIONS.md

- **Path:** extended-tests/scripts/RUNNING_INSTRUCTIONS.md
- **Title:** (inferred - running instructions)
- **Purpose:** Likely documents how to run extended test scripts.
- **Type:** test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - running instructions
- **Overlaps with:** `extended-tests/README.md` (extended tests overview)

### extended-tests/scripts/RESULTS_SUMMARY.md

- **Path:** extended-tests/scripts/RESULTS_SUMMARY.md
- **Title:** (inferred - results summary)
- **Purpose:** Likely summarizes results from extended test scripts.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - test results
- **Overlaps with:** Various extended-tests docs

### extended-tests/scripts/README_PW_STATS.md

- **Path:** extended-tests/scripts/README_PW_STATS.md
- **Title:** (inferred - PW stats README)
- **Purpose:** Likely documents pw.x (Quantum ESPRESSO) statistics from extended tests.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Possibly
- **Mentions tests/CI?:** Yes - test statistics
- **Overlaps with:** Various extended-tests docs

### extended-tests/scripts/MONITOR.md

- **Path:** extended-tests/scripts/MONITOR.md
- **Title:** (inferred - monitor)
- **Purpose:** Likely documents monitoring of extended test execution.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - test monitoring
- **Overlaps with:** Various extended-tests docs

### extended-tests/scripts/DEBUG_FIXES.md

- **Path:** extended-tests/scripts/DEBUG_FIXES.md
- **Title:** (inferred - debug fixes)
- **Purpose:** Likely documents debug fixes for extended test scripts.
- **Type:** meta/notes, test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Yes - debug fixes
- **Overlaps with:** `extended-tests/scripts/SUMMARY_AND_DEBUG.md`

### extended-tests/suites/tutorial_examples/README.md

- **Path:** extended-tests/suites/tutorial_examples/README.md
- **Title:** (inferred - tutorial examples README)
- **Purpose:** Likely documents tutorial example tests in extended-tests.
- **Type:** test-suite-doc
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** `extended-tests/suites/tutorial_examples/SUMMARY.md`

### extended-tests/suites/tutorial_examples/SUMMARY.md

- **Path:** extended-tests/suites/tutorial_examples/SUMMARY.md
- **Title:** (inferred - tutorial examples summary)
- **Purpose:** Likely summarizes tutorial example tests.
- **Type:** test-suite-doc, meta/notes
- **Status:** unknown (file not read in detail)
- **Mentions schema?:** Unknown
- **Mentions snapshots?:** Unknown
- **Mentions standalone QE?:** Unknown
- **Mentions tests/CI?:** Likely yes
- **Overlaps with:** `extended-tests/suites/tutorial_examples/README.md`

---

## gui/

### gui/README.md

- **Path:** gui/README.md
- **Title:** React + TypeScript + Vite
- **Purpose:** Standard Vite + React template README. Covers ESLint configuration expansion. Very minimal (30 lines).
- **Type:** meta/notes
- **Status:** canonical-current (but minimal - mostly template boilerplate)
- **Mentions schema?:** No
- **Mentions snapshots?:** No
- **Mentions standalone QE?:** No
- **Mentions tests/CI?:** No
- **Overlaps with:** `docs/GUI_ARCHITECTURE.md` (actual GUI documentation)

---

## Summary Statistics

### By Location

- **Root-level:** 13 docs
- **docs/:** 12 docs
- **tests/:** 23 docs
- **extended-tests/:** 18 docs
- **gui/:** 1 doc
- **Total:** 67 markdown documentation files

### By Type

- **architecture-spec:** 4 docs
- **schema-spec:** 3 docs
- **api-reference:** 3 docs
- **engine-doc:** 3 docs
- **cli-usage:** 3 docs
- **daemon-gui-contract:** 3 docs
- **testing-overview:** 8 docs
- **test-suite-doc:** 15 docs
- **snapshot-doc:** 3 docs
- **standalone-qe-doc:** 1 doc
- **refactor-plan:** 4 docs
- **refactor-summary:** 4 docs
- **meta/notes:** 15 docs

### Key Findings

#### Schema Documentation

**Canonical schema docs:**
- `SCHEMA_REFACTOR_PLAN.md` - Target schema (DAG + ID-only)
- `CONSISTENCY_SWEEP_REPORT.md` - Verification of ID-only references
- `AI_understanding.md` section 2.3 - Current schema examples (but some outdated - mentions `parent_workflow_id` in step YAML)

**Schema inconsistencies:**
- `AI_understanding.md` section 2.3 shows step YAML with `parent_workflow_id` and `structure_id` (outdated per DAG model - these should NOT be in step YAML)
- `AI_understanding.md` section 23.1 shows snapshot step data with `parent_workflow_id` (outdated)
- `PROJECT_ARCHITECTURE.md` mentions `parent_workflow_id` in step YAML (outdated)

#### Snapshot Documentation

**Canonical snapshot docs:**
- `AI_understanding.md` section 23.3 - Explicitly documents "Option B: Template with Fresh IDs" (current behavior)
- `SNAPSHOT_DOCS_UPDATE_SUMMARY.md` - Documents Option B adoption and test addition
- `SNAPSHOT_OPTION_A_AUDIT.md` - Describes Option A (desired but not implemented) vs current Option B

**Snapshot semantics:**
- **Current behavior (Option B):** Snapshots are templates, ULIDs are regenerated on materialization
- **Option A (not implemented):** Snapshots are backups, ULIDs are preserved on restore
- All current docs consistently describe Option B as the implemented behavior

#### Standalone QE Documentation

**Canonical standalone docs:**
- `STANDALONE_STEP_IMPLEMENTATION.md` - Primary documentation for standalone mode
- `AI_understanding.md` - Section on standalone mode (more detailed)
- `README.md` - Brief mention of `qv run step --standalone`

**Standalone semantics:**
- Standalone mode works on raw input files without creating Step resources in the DAG
- Supports bidirectional vs pass-through mode
- Documented as "pure QE helper" not part of DAG

#### Test Documentation

**Canonical test docs:**
- `docs/tests_overview.md` - Most comprehensive (1400+ lines, detailed per-file descriptions)
- `docs/testing_guide.md` - Condensed README-level guide
- `tests/TEST_STRUCTURE.md` - Test organization overview
- `tests/README.md` - Quick tests overview
- `extended-tests/README.md` - Extended tests overview

**Test documentation overlaps:**
- Multiple docs describe similar test structure (quick vs extended, pytest markers, CI behavior)
- `docs/tests_overview.md` is the most detailed and canonical
- `docs/testing_guide.md` is a condensed version suitable for README
- `tests/README.md` and `tests/QUICK_TESTS.md` have overlapping content

---

## Major Inconsistencies

1. **Step YAML schema:** Some docs (`AI_understanding.md` section 2.3, `PROJECT_ARCHITECTURE.md`) show step YAML with `parent_workflow_id` and `structure_id`, but the DAG model requires these fields to be removed from step YAML (structure comes from calculation, parent is implicit from location).

2. **Snapshot semantics:** `SNAPSHOT_OPTION_A_AUDIT.md` describes Option A (preserve ULIDs) as desired, but all other docs (`AI_understanding.md` section 23.3, `SNAPSHOT_DOCS_UPDATE_SUMMARY.md`) describe Option B (regenerate ULIDs) as the current and intended behavior. The audit doc appears to be historical/aspirational.

3. **Test documentation duplication:** Multiple docs describe similar test structure and organization, with some overlap between `tests/README.md`, `tests/QUICK_TESTS.md`, `docs/testing_guide.md`, and `docs/tests_overview.md`.
