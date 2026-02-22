# GUI Testing Coverage Plan

## Executive Summary

This document defines a comprehensive testing strategy to ensure QMatSuite's GUI works for all user-facing functionality without manual testing. The plan establishes a **three-tier testing pyramid**:

1. **Plan C: RPC Contract Tests (pytest)** — HIGHEST PRIORITY — Systematic tests for all 120+ RPC endpoints
2. **Plan D: Component Tests (Vitest)** — MEDIUM PRIORITY — Tests for critical React components with business logic
3. **Plan A: Playwright e2e Smoke Tests** — LOWER PRIORITY BUT ESSENTIAL — 25-30 critical end-to-end flows

**Current State:** 5760 Python tests (69% coverage), 8 e2e tests (~1534 lines), 120 RPC handlers, but significant gaps in RPC contract testing and component coverage.

**Goal:** After executing this plan, we can confidently ship the GUI knowing that all user-facing operations are tested at the appropriate layer.

---

## 1. Current State: Baseline Metrics

### 1.1 Python Test Baseline

**Test Execution:**
```
5760 passed, 30 skipped in 274.05s (0:04:34)
Overall coverage: 69%
```

**Critical Coverage Gaps:**
- `daemon/server.py` (269KB, 120 RPC handlers): Coverage unknown but likely low
- `io/online_search.py`: 48% coverage
- `io/providers/materials_project.py`: 60%
- `io/providers/pubchem.py`: 68%
- `presets/detector.py`: 43%
- `provenance/restore.py`: 24%
- `provenance/scanner.py`: 26%

**Existing Daemon Tests (17 files, ~3519 lines):**
- `test_daemon_payload_contracts.py` — Placeholder tests (not fully implemented)
- `test_gui_rpc_wiring.py` — Gate test ensuring GUI methods have daemon handlers
- `test_gui_job_and_step_flows.py` — Job/step workflow tests
- `test_qe_detection.py`, `test_pseudo_scanning.py` — Environment setup tests
- Various specific RPC endpoint tests

**Demo Store Tests (6 files):**
- `test_authoring_ops.py` — AuthoringOps IR serialization
- `test_replay.py` — Demo replay from authoring ops
- `test_patch_semantics.py` — Patch operation semantics
- `test_roundtrip.py` — Roundtrip validation

### 1.2 GUI e2e Test Baseline

**TypeScript Build Status:** ❌ **FAILING**
```
src/App.tsx(813,11): error TS2353: Object literal may only specify known properties
src/App.tsx(968,36): error TS2339: Property 'structure_type' does not exist
src/App.tsx(969,20): error TS2339: Property 'pbc' does not exist
```
**Note:** GUI has TypeScript errors preventing e2e test execution. These must be fixed before e2e tests can run.

**Existing e2e Tests (8 files, ~1534 lines):**
1. `analysis_convergence.spec.ts` (~5275 lines) — Convergence analysis visualization
2. `analysis_dos.spec.ts` (~5013 lines) — DOS analysis visualization
3. `demo_calculation_run.spec.ts` (~15742 lines) — Full calculation run workflow
4. `demo_calculation.spec.ts` (~12691 lines) — Calculation management UI
5. `demo_gallery.spec.ts` (~5206 lines) — Demo gallery browsing
6. `step_defaults.spec.ts` (~11681 lines) — Step default parameters
7. `structures_view.test.ts` (~10327 lines) — Structure viewing/browsing
8. `welcome.spec.ts` (~2107 lines) — Welcome screen

**Documented Coverage per GUI_E2E_REFACTOR.md:**
- ✅ Basic navigation (Calculations, Structures, etc.)
- ✅ Calculation Overview & Steps tab
- ✅ Step Focus mode (two-column layout)
- ✅ Run & Logs tab auto-switch on run
- ✅ Analysis tab (scoped to calculation)
- ✅ Bands analysis rendering
- ⚠️ SCF and DOS analysis types (not comprehensively tested)
- ⚠️ Step parameter editing (basic only)
- ⚠️ Structure fetching from external databases (minimal)

### 1.3 Codebase Structure

**Python Backend:**
```
src/qmatsuite/
├── api/                 # QMSService API layer
│   └── service.py       # Main API service (12KB)
├── daemon/              # JSON-RPC server
│   ├── server.py        # RPC handlers (269KB, 120 endpoints)
│   ├── jobs.py          # JobManager for async operations
│   └── compat.py        # v0 compatibility layer
├── core/                # Core domain logic
│   ├── analysis/        # AnalysisObject orchestrator
│   ├── resources/       # ResourceIndex
│   └── driver_registry/ # Engine driver registry
├── drivers/             # 15 engine drivers (QE, VASP, ORCA, etc.)
├── execution/           # Runner, executor, recipes
├── inputformat/         # Input file generation/parsing
├── io/                  # Structure I/O, online providers
├── ir/                  # Intermediate representation (IR)
├── presets/             # Preset system
├── provenance/          # History, CAS, versioning
└── workflow/            # Step types, templates
```

**GUI Frontend (91 TypeScript/TSX files):**
```
gui/src/
├── components/panels/   # Major UI panels
│   ├── CalculationListPanel.tsx (65KB)
│   ├── CalculationOverviewTab.tsx (20KB)
│   ├── CalculationAnalysisPanel.tsx (21KB)
│   ├── CalculationRunPanel.tsx (12KB)
│   ├── EngineParameterBrowserPanel.tsx (41KB)
│   ├── AnalysisVizPanel.tsx (13KB)
│   ├── FatbandsVizPanel.tsx (12KB)
│   ├── Field3DVizPanel.tsx (15KB)
│   ├── HistoryPanel.tsx (17KB)
│   └── ... (50+ more panels)
├── services/            # RPC client
│   └── qms-daemon.ts     # QMSCommand dispatcher
├── types/               # TypeScript types
│   └── qms.ts            # QMSCommandMap interface
└── App.tsx              # Main app (large, needs refactoring)
```

### 1.4 RPC Interface Inventory

**Total RPC Handlers:** 120

**Categories:**
- **System:** ping, shutdown (2)
- **Environment & Settings:** detect_qe, get_env_info, list_qe_engines, set_qe_engine, set_log_level, set_debug_resolution, get_debug_resolution (7)
- **Generic Engine RPCs:** list_engine_families, list_step_palette, list_engine_ui_parameters, list_engine_parameter_metadata, set_engine_family (5)
- **Pseudopotential:** get/set/validate_pseudo_config, init_pseudo_dirs, install_seed_to_store, list_installed_sssp, download_sssp_library, etc. (14)
- **Generic Library Manager:** list_libraries, get_library_status, install_library, remove_library, repair_library, compute_store_size (6)
- **Project/Resource Listing:** get_project_summary, list_structures, list_calculations, find_project_root, rebuild_project_registry (5)
- **Project Management:** create_project, import_structure (2)
- **Online Structure Search:** structure_search_online, structure_get_online_candidate, structure_list_providers, structure_update_online_sources, structure_import_online_candidate (5)
- **Structure Management:** rename_structure, delete_structure, can_delete_structure (3)
- **Calculation Management:** list_calculation_templates, create_calculation, rename_calculation, delete_calculation, can_delete_calculation, get_calculation_detail, reorder_calculation_steps, add_step_to_calculation, change_calculation_structure (9)
- **Step Management:** get_step_detail, update_step_params, reset_step_params, delete_step, get_common_cards, set_common_card, get_relax_final_structure_preview, save_relax_final_structure (8)
- **Pseudo Mapping:** get_pseudo_mapping, set_pseudo_mapping, import_pseudo_files, search_legacy_pseudos, download_pseudo_by_filename, download_pseudo_candidate, get_calculation_pseudo_mapping, update_calculation_species_map, get_pseudo_options_for_calculation, materialize_pseudo_file (10)
- **Presets:** get_preset_catalog, detect_presets, detect_workflow, apply_presets_to_step, apply_presets_to_calculation, get_step_preset_footprints (6)
- **Workflows:** list_workflow_templates, detect_workflow_for_calculation, instantiate_workflow (3)
- **Preflight:** preflight_check (1)
- **Demo Store:** create_demo_project, list_demo_projects (2)
- **Visualization:** get_structure_vis (1)
- **Analysis:** get_reference_analysis, get_analysis, get_analysis_instances_for_step, get_analysis_snapshot (4)
- **Step Artifacts:** get_step_digest, list_step_artifacts, read_step_artifact_text, list_raw_files, read_raw_file, compile_fixture_volume (6)
- **Execution:** run_calculation, run_step, run_single_step (3)
- **Job Management:** get_job_status, get_job_logs, list_jobs, job_counts, cancel_job (5)
- **History & Provenance:** list_journal_entries, get_journal_entry, get_project_history, get_run_revision, list_project_runs, pin_analysis_to_history, can_pin_to_run, get_pin_data, get_latest_run_for_step, delete_project_history, get_storage_summary (11)
- **Relax Promotion:** promote_relax_structure (1)

**RPC Contract Coverage Status:**
- ✅ Gate test `test_gui_rpc_wiring.py` ensures all GUI-called methods exist
- ⚠️ `test_daemon_payload_contracts.py` has placeholders but is not fully implemented
- ❌ Most RPC endpoints lack systematic contract tests (request/response schema validation)
- ❌ No tests for error path handling (invalid inputs, missing resources, etc.)
- ❌ No tests for sequential call patterns that mirror GUI workflows

### 1.5 Demo Store Infrastructure

**43 Reference Demo Projects** in `resources/demo_projects/ref_packs/`:
- QE demos: si_bands_demo, si_dos_demo, qe_si_scf, qe_si_vc_relax, qe_graphene_bands, qe_al_dos, qe_fe_dos, qe_copper_wannier, qe_diamond_wannier, qe_he_qmcpack_vmc, qe_lih_qmcpack_vmc, qe_si_yambo_bse, qe_si_yambo_gw, etc.
- VASP demos: vasp_si_scf, vasp_si_bands, vasp_si_dos, vasp_si_relax, vasp_fe_magnetic
- ORCA demos: orca_water_sp, orca_formaldehyde_tddft, orca_methane_freq
- LAMMPS demos: lammps_lj_melt, lammps_lj_minimize, lammps_peptide_nvt
- Gaussian demos: gaussian_water_hf, gaussian_water_opt
- ABINIT demos: abinit_si_scf, abinit_si_bands, abinit_si_relax
- CP2K demos: cp2k_h2o_energy, cp2k_h2o_geo_opt, cp2k_si_relax
- Siesta demos: siesta_si_scf, siesta_si_bands, siesta_si_relax
- xTB demos: xtb_water_opt, xtb_water_md, xtb_caffeine_grad
- GPAW/Psi4 demos: gpaw_al_scf, gpaw_si_scf

**Authoring Ops IR:**
- Decomposes demos into user-granularity operations: InitProject, ImportStructure, CreateCalculation, AddStep, SetField, UnsetField, ReplaceMap, ConfigureSpeciesMap
- Replay system can reconstruct demos from ops
- Tests validate serialization, bulk op detection, field validation

**Potential:** Authoring ops can be extended to validate RPC responses (e.g., create_calculation should return calc DTO with expected fields).

---

## 2. Coverage Gap Analysis

| Layer | Test Count | Coverage % | Key Gaps |
|-------|-----------|------------|----------|
| **Kernel (core domain)** | ~4000 | 69% overall | Preset detector (43%), provenance restore/scanner (24-26%), online providers (48-68%) |
| **Engine drivers (15)** | ~1200 | High (80%+) | Field3D for some engines, convergence parsers for molecular codes |
| **IR / Preset / Workflow** | ~300 | ~75% | Workflow detection edge cases, preset footprint validation |
| **API layer (QMSService)** | ~100 | ~80% | Analysis orchestrator error paths, DTO mapping edge cases |
| **Daemon / RPC server** | ~200 | Unknown (low?) | Most handlers lack contract tests, error paths untested |
| **RPC contract (req/res schema)** | ~10 | <10% | Only placeholder tests in `test_daemon_payload_contracts.py` |
| **GUI component (Vitest)** | 0 | 0% | No component tests exist |
| **GUI e2e (Playwright)** | 8 tests | ~15%? | Missing: engine setup, structure import, preset application, multi-engine workflows |

### 2.1 RPC Coverage Gaps

**Endpoints with Tests:**
- ✅ `list_structures`, `list_calculations` — Placeholder contract tests
- ✅ `detect_qe`, `get_qe_engine_status` — Basic tests in `test_qe_detection.py`
- ✅ `get_pseudo_config`, `validate_pseudo_config` — Tests in `test_pseudo_scanning.py`
- ✅ `get_calculation_detail` — Tests in `test_gui_calculation_detail.py`
- ✅ `run_calculation`, `run_step` — Basic tests in `test_gui_job_and_step_flows.py`

**Endpoints WITHOUT Tests (partial list):**
- ❌ `structure_search_online`, `structure_get_online_candidate`, `structure_import_online_candidate`
- ❌ `get_structure_vis` (critical for 3D viewer)
- ❌ `get_preset_catalog`, `detect_presets`, `apply_presets_to_step`, `apply_presets_to_calculation`
- ❌ `list_engine_families`, `list_step_palette`, `list_engine_ui_parameters`, `set_engine_family`
- ❌ `reorder_calculation_steps`, `change_calculation_structure`
- ❌ `get_analysis`, `get_analysis_instances_for_step`, `get_analysis_snapshot`
- ❌ `get_step_digest`, `list_step_artifacts`, `read_step_artifact_text`
- ❌ `list_workflow_templates`, `instantiate_workflow`
- ❌ Most pseudo management RPCs (download_pseudo_by_filename, materialize_pseudo_file, etc.)
- ❌ Most history/provenance RPCs (list_journal_entries, get_run_revision, pin_analysis_to_history, etc.)

### 2.2 GUI Component Gaps

**Components with Business Logic (need tests):**
- `CalculationListPanel.tsx` (65KB) — Calculation selection, filtering, state management
- `CalculationOverviewTab.tsx` (20KB) — Step focus mode toggle, step list management
- `CalculationAnalysisPanel.tsx` (21KB) — Analysis type selection, auto-loading data
- `EngineParameterBrowserPanel.tsx` (41KB) — Parameter tree navigation, filtering
- `AnalysisVizPanel.tsx`, `FatbandsVizPanel.tsx`, `Field3DVizPanel.tsx` — Visualization rendering
- `HistoryPanel.tsx` — History navigation, provenance display
- Preset selector component (if exists)
- Workflow builder component (if exists)

**Current Component Test Status:** 0 tests (no `*.spec.tsx` or `*.test.tsx` files found in `gui/src/components/`)

### 2.3 e2e Coverage Gaps

**User Journeys NOT Covered:**
- ❌ Engine setup flow (detect → select → configure)
- ❌ Structure import from file (CIF, POSCAR, XYZ, etc.)
- ❌ Structure fetch from Materials Project / OPTIMADE / PubChem
- ❌ Pseudopotential setup (download SSSP, configure mapping)
- ❌ Multi-engine workflow (e.g., QE SCF → QMCPACK VMC)
- ❌ Preset application at calculation level
- ❌ Workflow template instantiation
- ❌ History navigation and provenance inspection
- ❌ Error recovery (failed job, invalid input, missing file)
- ❌ Project rename/delete operations

---

## 3. Complete User Journey Map

This section enumerates EVERY user interaction a new or experienced user might perform. For each journey step, we categorize test coverage needs.

### 3.1 Persona: First-Time User (The "First 5 Minutes")

| Journey Step | RPC Contract Test? | Component Test? | e2e Test? | Current Status |
|--------------|-------------------|-----------------|-----------|----------------|
| Launch app → see welcome screen | No | Yes (Welcome) | Yes | ✅ welcome.spec.ts |
| App connects to daemon | Yes (ping) | Yes (DaemonStatus) | Yes | ⚠️ Basic only |
| View onboarding / getting started guide | No | Yes | Yes | ❌ Missing |
| Engine setup: detect available engines | Yes (detect_qe, list_engine_families) | Yes | Yes | ⚠️ QE only, not generic |
| Engine setup: select bundled QE | Yes (set_qe_engine) | Yes | Yes | ❌ Missing e2e |
| Engine setup: configure external engine | Yes (set_qe_engine with bin_dir) | Yes | Yes | ❌ Missing |
| Pseudo setup: detect installed SSSP | Yes (validate_pseudo_config) | Yes | Yes | ❌ Missing |
| Pseudo setup: download SSSP library | Yes (download_sssp_library) | Yes | No | ❌ Missing tests |
| Open Demo Store | Yes (list_demo_projects) | Yes | Yes | ✅ demo_gallery.spec.ts |
| Browse demos by category | No | Yes | Yes | ⚠️ Basic only |
| View pre-computed demo results WITHOUT engine installed | Yes (get_reference_analysis) | Yes | Yes | ❌ Not tested |
| Import a demo as starting point | Yes (create_demo_project) | Yes | Yes | ❌ Missing |

### 3.2 Persona: Researcher Running Basic DFT Calculation

| Journey Step | RPC Contract Test? | Component Test? | e2e Test? | Current Status |
|--------------|-------------------|-----------------|-----------|----------------|
| **Structure Acquisition** |
| Create new project | Yes (create_project) | Yes | Yes | ❌ Missing contract test |
| Name project | No | Yes | Yes | ❌ Missing |
| Fetch structure from Materials Project | Yes (structure_search_online, structure_get_online_candidate, structure_import_online_candidate) | Yes | Yes | ❌ Missing all tests |
| Fetch structure from OPTIMADE | Yes (structure_search_online with provider) | Yes | Yes | ❌ Missing |
| Fetch structure from PubChem | Yes (structure_search_online with provider) | Yes | Yes | ❌ Missing |
| Import structure from CIF file | Yes (import_structure) | Yes | Yes | ❌ Missing e2e |
| Import structure from POSCAR file | Yes (import_structure) | Yes | Yes | ❌ Missing e2e |
| Import structure from XYZ file | Yes (import_structure) | Yes | Yes | ❌ Missing e2e |
| View structure in 3D viewer | Yes (get_structure_vis) | Yes | Yes | ✅ structures_view.test.ts (basic) |
| Manipulate structure view (rotate, zoom, supercell) | Yes (get_structure_vis with supercell) | Yes | Yes | ⚠️ Basic only |
| Edit structure properties | No (future) | Yes | No | ❌ Not implemented |
| **Calculation Setup** |
| Create new calculation | Yes (create_calculation) | Yes | Yes | ⚠️ Basic contract test |
| Select structure for calculation | Yes (get_calculation_detail includes structure_ulid) | Yes | Yes | ✅ demo_calculation.spec.ts |
| Select engine family | Yes (set_engine_family) | Yes | Yes | ❌ Missing tests |
| **Workflow Building** |
| Select workflow template (e.g., "SCF → Relax → DOS → Band") | Yes (list_workflow_templates, instantiate_workflow) | Yes | Yes | ❌ Missing all tests |
| Add step manually | Yes (add_step_to_calculation) | Yes | Yes | ⚠️ Basic only |
| Reorder steps | Yes (reorder_calculation_steps) | Yes | Yes | ❌ Missing tests |
| Delete step | Yes (delete_step) | Yes | Yes | ❌ Missing tests |
| **Preset Application** |
| Choose preset (e.g., "Standard DFT-PBE") | Yes (get_preset_catalog) | Yes | Yes | ❌ Missing tests |
| Apply preset to calculation | Yes (apply_presets_to_calculation) | Yes | Yes | ❌ Missing tests |
| Apply preset to step | Yes (apply_presets_to_step) | Yes | Yes | ❌ Missing tests |
| Detect current presets | Yes (detect_presets) | Yes | Yes | ❌ Missing tests |
| View preset footprint | Yes (get_step_preset_footprints) | Yes | Yes | ❌ Missing tests |
| **Parameter Editing** |
| View step parameters (Overview mode) | Yes (get_step_detail) | Yes | Yes | ✅ Basic |
| Enter Step Focus mode | No | Yes | Yes | ✅ demo_calculation.spec.ts |
| Edit parameters at IR level | Yes (update_step_params with IR params) | Yes | Yes | ❌ Missing tests |
| Edit parameters at engine-specific level | Yes (update_step_params) | Yes | Yes | ⚠️ Basic only |
| Browse engine parameter metadata | Yes (list_engine_parameter_metadata) | Yes | Yes | ❌ Missing tests |
| Reset parameters to defaults | Yes (reset_step_params) | Yes | Yes | ❌ Missing tests |
| View parameter validation warnings | No | Yes | Yes | ❌ Not implemented |
| **Pseudopotential Configuration** |
| View current pseudo mapping | Yes (get_pseudo_mapping) | Yes | Yes | ❌ Missing tests |
| Set pseudo mapping | Yes (set_pseudo_mapping) | Yes | Yes | ❌ Missing tests |
| Search for pseudopotential files | Yes (search_legacy_pseudos) | Yes | Yes | ❌ Missing tests |
| Download pseudopotential | Yes (download_pseudo_by_filename) | Yes | Yes | ❌ Missing tests |
| Import local pseudo files | Yes (import_pseudo_files) | Yes | Yes | ❌ Missing tests |
| Configure species map | Yes (update_calculation_species_map) | Yes | Yes | ❌ Missing tests |
| **Preflight & Validation** |
| Run preflight check | Yes (preflight_check) | Yes | Yes | ❌ Missing tests |
| View preflight warnings/errors | No | Yes | Yes | ❌ Missing tests |
| **Execution** |
| Submit calculation | Yes (run_calculation) | Yes | Yes | ✅ demo_calculation_run.spec.ts |
| Auto-switch to Run & Logs tab | No | Yes | Yes | ✅ Verified in e2e |
| Monitor job progress | Yes (list_jobs, job_counts) | Yes | Yes | ⚠️ Basic only |
| View job logs | Yes (get_job_logs) | Yes | Yes | ❌ Missing tests |
| Cancel running job | Yes (cancel_job) | Yes | Yes | ❌ Missing tests |
| **Results Viewing** |
| Switch to Analysis tab | No | Yes | Yes | ✅ demo_calculation_run.spec.ts |
| Auto-detect analysis type | No | Yes | Yes | ❌ Missing tests |
| View SCF convergence | Yes (get_analysis with type="convergence") | Yes | Yes | ✅ analysis_convergence.spec.ts |
| View DOS plot | Yes (get_analysis with type="dos") | Yes | Yes | ✅ analysis_dos.spec.ts |
| View band structure | Yes (get_analysis with type="bands") | Yes | Yes | ✅ demo_calculation_run.spec.ts |
| View fatbands projection | Yes (get_analysis with fatbands data) | Yes | Yes | ❌ Missing tests |
| View Field3D (charge density, etc.) | Yes (get_analysis with type="field3d") | Yes | Yes | ❌ Missing tests |
| View trajectory (MD/relax) | Yes (get_analysis with type="trajectory") | Yes | Yes | ❌ Missing tests |
| Export results | No (future) | Yes | No | ❌ Not implemented |

### 3.3 Persona: Advanced User (Multi-Engine Workflows)

| Journey Step | RPC Contract Test? | Component Test? | e2e Test? | Current Status |
|--------------|-------------------|-----------------|-----------|----------------|
| Set up QE → QMCPACK workflow | Yes (multi-engine steps) | Yes | Yes | ❌ Missing |
| Set up QE → Wannier90 workflow | Yes | Yes | Yes | ❌ Missing |
| Set up QE → Yambo workflow | Yes | Yes | Yes | ❌ Missing |
| Compare results across engines | Yes (get_analysis for multiple steps) | Yes | Yes | ❌ Missing |
| Use ORCA for molecular system | Yes | Yes | Yes | ❌ Missing |
| Use Gaussian for QC calculations | Yes | Yes | Yes | ❌ Missing |
| Use LAMMPS for classical MD | Yes | Yes | Yes | ❌ Missing |
| Chain calculations (output → input) | No (manual file management) | No | No | ❌ Not tested |

### 3.4 Persona: Project Manager

| Journey Step | RPC Contract Test? | Component Test? | e2e Test? | Current Status |
|--------------|-------------------|-----------------|-----------|----------------|
| Open existing project | Yes (find_project_root, get_project_summary) | Yes | Yes | ❌ Missing tests |
| Browse calculation history | Yes (list_calculations) | Yes | Yes | ✅ Basic |
| View calculation details | Yes (get_calculation_detail) | Yes | Yes | ✅ Basic |
| Rename calculation | Yes (rename_calculation) | Yes | Yes | ❌ Missing tests |
| Delete calculation | Yes (can_delete_calculation, delete_calculation) | Yes | Yes | ❌ Missing tests |
| Check if structure can be deleted | Yes (can_delete_structure) | Yes | Yes | ❌ Missing tests |
| Delete structure | Yes (delete_structure) | Yes | Yes | ❌ Missing tests |
| Rename structure | Yes (rename_structure) | Yes | Yes | ❌ Missing tests |
| Clone calculation with modified params | No (manual) | No | No | ❌ Not implemented |
| Navigate provenance history | Yes (get_project_history, list_journal_entries) | Yes | Yes | ❌ Missing tests |
| View run revision | Yes (get_run_revision) | Yes | Yes | ❌ Missing tests |
| Pin analysis to history | Yes (can_pin_to_run, pin_analysis_to_history) | Yes | Yes | ❌ Missing tests |
| View storage summary | Yes (get_storage_summary) | Yes | Yes | ❌ Missing tests |
| Delete project history | Yes (delete_project_history) | Yes | Yes | ❌ Missing tests |

### 3.5 User Journey Coverage Summary

| Category | Total Steps | RPC Contract Needed | Component Needed | e2e Needed | Currently Tested |
|----------|------------|--------------------|--------------------|------------|------------------|
| First-Time User | 11 | 6 | 11 | 11 | 2 (18%) |
| Structure Acquisition | 9 | 5 | 9 | 9 | 1 (11%) |
| Calculation Setup | 2 | 2 | 2 | 2 | 1 (50%) |
| Workflow Building | 4 | 4 | 4 | 4 | 0 (0%) |
| Preset Application | 5 | 5 | 5 | 5 | 0 (0%) |
| Parameter Editing | 7 | 4 | 7 | 7 | 1 (14%) |
| Pseudopotential Config | 6 | 6 | 6 | 6 | 0 (0%) |
| Preflight & Validation | 2 | 1 | 2 | 2 | 0 (0%) |
| Execution | 5 | 4 | 5 | 5 | 2 (40%) |
| Results Viewing | 8 | 5 | 8 | 8 | 4 (50%) |
| Advanced Multi-Engine | 8 | 8 | 8 | 8 | 0 (0%) |
| Project Management | 13 | 12 | 13 | 13 | 1 (8%) |
| **TOTAL** | **80** | **62** | **80** | **80** | **12 (15%)** |

---

## 4. Three-Tier Testing Plan

### 4.1 Plan C: RPC Contract Tests (pytest) — HIGHEST PRIORITY

#### Philosophy
- **Goal:** Every RPC endpoint has a contract test validating request schema, response schema, and error handling.
- **Why pytest?** Fast, no GUI overhead, can run in CI on every commit.
- **Coverage target:** 100% of RPC endpoints (120 handlers).

#### Strategy

**Leverage Existing Infrastructure:**
1. **Expand `test_daemon_payload_contracts.py`** — Currently has placeholders for list_structures, list_calculations, run_calculation. Systematically add tests for all 120 endpoints.
2. **Reuse authoring ops replay** — Demo replay infrastructure already validates end-to-end workflows. Extend it to capture and validate RPC responses.
3. **Use demo ref_packs** — 43 pre-computed demos can serve as golden reference data for analysis RPCs.

**Test Structure (per endpoint):**
```python
class TestRPC_<endpoint_name>:
    def test_happy_path(self, temp_project, daemon):
        """Validate response structure for valid inputs."""
        response = send_request(daemon, "<endpoint_name>", {
            # Valid payload
        })
        # Assert response structure matches TypeScript QMSCommandMap
        assert "expected_field" in response
        assert isinstance(response["expected_field"], expected_type)

    def test_error_missing_param(self, daemon):
        """Missing required param returns proper error."""
        response = daemon.handle_request(RPCRequest(
            id="test", type="<endpoint_name>", payload={}
        ))
        assert not response.ok
        assert response.error["code"] == "invalid_argument"

    def test_error_not_found(self, temp_project, daemon):
        """Non-existent resource returns resource_not_found error."""
        response = daemon.handle_request(RPCRequest(
            id="test", type="<endpoint_name>",
            payload={"ulid": "nonexistent"}
        ))
        assert not response.ok
        assert response.error["code"] == "resource_not_found"

    def test_sequential_workflow(self, temp_project, daemon):
        """Test endpoint as part of a realistic workflow."""
        # E.g., create_calculation → add_step → update_step_params → get_step_detail
        # Validates state consistency across RPC calls
```

**Priority Order (by GUI dependency):**

**Tier 1 — Critical for GUI Operation (25 endpoints):**
1. `ping`, `shutdown`
2. `find_project_root`, `get_project_summary`, `list_structures`, `list_calculations`
3. `create_project`, `import_structure`, `create_calculation`
4. `get_structure_vis` (3D viewer)
5. `get_calculation_detail`, `get_step_detail`
6. `add_step_to_calculation`, `update_step_params`
7. `run_calculation`, `list_jobs`, `job_counts`, `get_job_status`
8. `get_analysis`, `get_analysis_instances_for_step`
9. `list_engine_families`, `set_engine_family`
10. `get_preset_catalog`, `apply_presets_to_step`

**Tier 2 — Frequently Used (30 endpoints):**
1. Structure search: `structure_search_online`, `structure_get_online_candidate`, `structure_import_online_candidate`
2. Step management: `delete_step`, `reorder_calculation_steps`, `reset_step_params`
3. Pseudo: `get_pseudo_config`, `validate_pseudo_config`, `get_pseudo_mapping`, `set_pseudo_mapping`
4. Analysis: `get_analysis_snapshot`, `get_step_digest`, `list_step_artifacts`
5. Workflow: `list_workflow_templates`, `instantiate_workflow`, `detect_workflow`
6. Engine metadata: `list_step_palette`, `list_engine_ui_parameters`, `list_engine_parameter_metadata`
7. Job control: `get_job_logs`, `cancel_job`
8. Calculation management: `rename_calculation`, `delete_calculation`, `change_calculation_structure`

**Tier 3 — Less Critical but Complete Coverage (65 endpoints):**
1. All pseudo management RPCs
2. All library manager RPCs
3. All history/provenance RPCs
4. All demo store RPCs
5. All QE-specific RPCs (detect_qe, list_qe_engines, etc.)
6. Advanced features (compile_fixture_volume, etc.)

**Estimated Test Count:** ~360 tests (3 tests per endpoint × 120 endpoints)

**Execution Time Estimate:** ~5-10 minutes (pytest with parallelization)

#### Acceptance Criteria
- [ ] All 120 RPC endpoints have at least 3 tests (happy path, error path, workflow integration)
- [ ] Response schemas match TypeScript `QMSCommandMap` interface
- [ ] Error codes match GUI error handling expectations
- [ ] Sequential workflows mirror actual GUI call patterns

---

### 4.2 Plan D: Component Tests (Vitest + Testing Library) — MEDIUM PRIORITY

#### Philosophy
- **Goal:** Test React components with business logic in isolation, mocking RPC responses.
- **Why Vitest?** Fast, supports JSX/TSX, React Testing Library integration.
- **Coverage target:** 20-25 critical components.

#### Components to Test (Priority Order)

**Tier 1 — Critical Business Logic (8 components):**
1. **CalculationListPanel** — Calculation selection, filtering, state management
   - Test: Selecting a calculation updates state
   - Test: Filtering by name/engine works
   - Test: Clicking "New Calculation" triggers RPC
2. **CalculationOverviewTab** — Step focus mode toggle
   - Test: Clicking step enters focus mode
   - Test: "Back to overview" exits focus mode
   - Test: Step list renders correctly
3. **CalculationAnalysisPanel** — Analysis type selection, auto-loading
   - Test: Selecting "bands" calls `get_analysis` with correct params
   - Test: Analysis data renders when RPC returns
   - Test: Loading state displays during fetch
4. **StepDetailPanel** (if exists as separate component) — Parameter editing
   - Test: Editing parameter calls `update_step_params`
   - Test: Reset button calls `reset_step_params`
   - Test: Validation errors display
5. **PresetSelector** (if exists) — Preset selection and application
   - Test: Clicking preset calls `apply_presets_to_step`
   - Test: Preset footprint displays
6. **EngineParameterBrowserPanel** — Parameter tree navigation
   - Test: Expanding sections works
   - Test: Filtering parameters works
   - Test: Clicking parameter copies to clipboard (or whatever action)
7. **StructureViewer** (if exists as component) — 3D viewer controls
   - Test: Supercell controls call `get_structure_vis` with correct params
   - Test: Display mode toggle works
8. **OnlineStructureSearchPanel** (if exists) — External structure search
   - Test: Entering search term calls `structure_search_online`
   - Test: Clicking result calls `structure_get_online_candidate`
   - Test: Import button calls `structure_import_online_candidate`

**Tier 2 — Visualization & Analysis (7 components):**
1. **AnalysisVizPanel** — Generic analysis visualization
2. **FatbandsVizPanel** — Fatbands projection display
3. **Field3DVizPanel** — Field3D (charge density) visualization
4. **ConvergenceChartPanel** (if exists) — SCF convergence chart
5. **DOSChartPanel** (if exists) — DOS plot
6. **BandsChartPanel** (if exists) — Band structure plot
7. **TrajectoryViewer** (if exists) — MD/relax trajectory

**Tier 3 — Supporting UI (10 components):**
1. **HistoryPanel** — Provenance navigation
2. **JobListPanel** — Job monitoring
3. **PseudoMappingPanel** (if exists) — Pseudo configuration
4. **WorkflowBuilderPanel** (if exists) — Workflow template selection
5. **DemoGalleryPanel** — Demo browsing
6. **WelcomeScreen** — First-time user onboarding
7. **EngineSetupPanel** (if exists) — Engine detection/configuration
8. **SettingsPanel** (if exists) — App settings
9. **DebugPanel** — Debug tools
10. **DaemonErrorBanner** — Daemon connection status

**Test Structure (per component):**
```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { ComponentName } from './ComponentName';

describe('ComponentName', () => {
  it('renders with mocked data', () => {
    const mockData = { /* ... */ };
    render(<ComponentName data={mockData} />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });

  it('calls RPC on user interaction', async () => {
    const mockRPC = vi.fn().mockResolvedValue({ ok: true, data: {} });
    render(<ComponentName onAction={mockRPC} />);

    fireEvent.click(screen.getByRole('button', { name: /action/i }));

    await waitFor(() => {
      expect(mockRPC).toHaveBeenCalledWith('expected_rpc_method', {
        /* expected payload */
      });
    });
  });

  it('displays error state correctly', () => {
    const mockError = { code: 'error_code', message: 'Error message' };
    render(<ComponentName error={mockError} />);
    expect(screen.getByText(/Error message/i)).toBeInTheDocument();
  });
});
```

**Estimated Test Count:** ~150 tests (~6 tests per component × 25 components)

**Execution Time Estimate:** ~2-5 minutes

#### Acceptance Criteria
- [ ] All critical components have tests for user interactions → RPC calls
- [ ] Mocked RPC responses render correctly
- [ ] Error states display properly
- [ ] Loading states work as expected

---

### 4.3 Plan A: Playwright e2e Smoke Tests — LOWER PRIORITY BUT ESSENTIAL

#### Philosophy
- **Goal:** 25-30 critical end-to-end smoke tests covering the most important user journeys.
- **Why e2e?** Validates full integration: GUI → daemon → kernel → engine (where applicable).
- **Coverage target:** "If these pass, the app fundamentally works."

#### Test Suite Design

**PREREQUISITE:** Fix TypeScript build errors in GUI before running e2e tests.

**Tier 1 — Core Workflows (10 tests):**
1. **App Launch & Welcome**
   - App launches, daemon connects, welcome screen renders
   - Existing: ✅ `welcome.spec.ts`
2. **Demo Gallery**
   - Open demo store → browse → view pre-computed results (bands, DOS, convergence)
   - Existing: ⚠️ `demo_gallery.spec.ts` (basic)
   - Enhance: Add viewing pre-computed analysis without engine
3. **Structure Viewing**
   - Navigate to Structures → select structure → view in 3D
   - Existing: ✅ `structures_view.test.ts`
4. **Structure Import from File**
   - Create project → import CIF → verify structure appears
   - Status: ❌ Missing
5. **Structure Fetch from Online Database**
   - Search Materials Project → select structure → import
   - Status: ❌ Missing
6. **Calculation Creation**
   - Create calculation → select structure → verify calculation appears
   - Existing: ⚠️ `demo_calculation.spec.ts` (partial)
7. **Step Management**
   - Add step → enter focus mode → view parameters → exit focus mode
   - Existing: ✅ `demo_calculation.spec.ts` + `step_defaults.spec.ts`
8. **Preset Application**
   - Select calculation → choose preset → verify parameters updated
   - Status: ❌ Missing
9. **Calculation Execution**
   - Submit calculation → verify auto-switch to Run & Logs → monitor job
   - Existing: ✅ `demo_calculation_run.spec.ts`
10. **Analysis Viewing**
    - After run → switch to Analysis → view bands/DOS/convergence
    - Existing: ✅ `demo_calculation_run.spec.ts`, `analysis_convergence.spec.ts`, `analysis_dos.spec.ts`

**Tier 2 — Advanced Workflows (10 tests):**
11. **Engine Setup**
    - First-time flow → detect QE → configure bundled QE → verify success
    - Status: ❌ Missing
12. **Pseudopotential Setup**
    - Configure pseudo store → download SSSP → verify installed
    - Status: ❌ Missing
13. **Workflow Template**
    - Create calculation → select "SCF → Relax → DOS → Band" template → verify steps created
    - Status: ❌ Missing
14. **Multi-Step Workflow Execution**
    - Run calculation with 4 steps → verify all steps execute in order
    - Status: ❌ Missing
15. **Step Reordering**
    - Reorder steps in calculation → verify order persists
    - Status: ❌ Missing
16. **Parameter Editing**
    - Edit step parameter → save → verify parameter updated in YAML
    - Status: ❌ Missing (only basic viewing tested)
17. **Calculation Rename/Delete**
    - Rename calculation → verify name updates
    - Delete calculation → verify removed from list
    - Status: ❌ Missing
18. **Structure Rename/Delete**
    - Rename structure → verify name updates
    - Delete structure → verify removed (or error if in use)
    - Status: ❌ Missing
19. **History Navigation**
    - View project history → select run → view provenance
    - Status: ❌ Missing
20. **Error Recovery**
    - Submit calculation with invalid params → verify error displays
    - Cancel running job → verify job stops
    - Status: ❌ Missing

**Tier 3 — Edge Cases & Polish (5 tests):**
21. **Tab Switching Persistence**
    - Switch between calculations → verify tab state persists
    - Status: ❌ Missing
22. **Analysis Auto-Detection**
    - Run calculation → verify Analysis tab auto-detects available types
    - Status: ❌ Missing
23. **Relax Structure Promotion**
    - Run relax → promote final structure → verify new structure created
    - Status: ❌ Missing
24. **Fatbands Visualization**
    - Run bands with PROCAR → view fatbands → verify projections display
    - Status: ❌ Missing
25. **Field3D Visualization**
    - Run SCF with charge density output → view Field3D → verify isosurface renders
    - Status: ❌ Missing

**Estimated Test Count:** 25 tests (expanding from current 8)

**Execution Time Estimate:** ~15-30 minutes (Playwright in headless mode)

#### Test Implementation Strategy

**Use Existing Patterns:**
- Test IDs (`data-testid`) already defined in components
- Helper functions in `gui/tests/e2e/helpers/`
- Fixtures in `gui/tests/e2e/fixtures/`

**New Helper Functions Needed:**
```typescript
// gui/tests/e2e/helpers/workflows.ts
export async function createCalculationWithSteps(
  page: Page,
  calcName: string,
  structureName: string,
  stepTypes: string[]
): Promise<void> { /* ... */ }

export async function applyPreset(
  page: Page,
  calcName: string,
  presetName: string
): Promise<void> { /* ... */ }

export async function importStructureFromFile(
  page: Page,
  filePath: string
): Promise<void> { /* ... */ }

export async function searchOnlineStructure(
  page: Page,
  provider: string,
  query: string
): Promise<void> { /* ... */ }
```

**Fixtures Needed:**
- Sample CIF files for import
- Sample POSCAR files
- Mock Materials Project responses (if possible)

#### Acceptance Criteria
- [ ] All 25 smoke tests pass on a fresh install
- [ ] Tests run in <30 minutes in CI
- [ ] Tests cover all critical user journeys
- [ ] Failures are actionable (clear error messages, screenshots on failure)

---

## 5. Execution Roadmap

### 5.1 Phase 1: Foundation (Week 1)

**Goals:**
- Fix TypeScript build errors in GUI
- Set up component testing infrastructure (Vitest)
- Create RPC contract test framework

**Tasks:**
1. ✅ Fix TypeScript errors in `src/App.tsx` (structure_type, pbc fields)
2. ✅ Set up Vitest for GUI component tests
   - Install dependencies: `vitest`, `@testing-library/react`, `@testing-library/user-event`
   - Configure `vite.config.ts` for test environment
   - Create sample component test to validate setup
3. ✅ Expand `test_daemon_payload_contracts.py`
   - Create fixtures for temp project setup
   - Implement helper function `send_request(daemon, endpoint, payload)`
   - Write 5 Tier 1 contract tests as examples

**Deliverables:**
- GUI builds without TypeScript errors
- Vitest runs (even if 0 tests)
- 5 new RPC contract tests passing

### 5.2 Phase 2: RPC Contract Tests — Tier 1 (Week 2-3)

**Goals:**
- Complete contract tests for 25 critical RPC endpoints
- Validate response schemas match TypeScript types

**Tasks:**
1. Write contract tests for Tier 1 endpoints (see §4.1)
2. For each endpoint:
   - Happy path test
   - Error path test (missing param, not found, invalid input)
   - Workflow integration test (if applicable)
3. Use demo ref_packs as golden reference data where applicable
4. Run tests in CI to catch regressions

**Deliverables:**
- 75 new RPC contract tests (3 per endpoint × 25 endpoints)
- All tests passing in CI
- Coverage report showing RPC handler coverage increase

### 5.3 Phase 3: Component Tests — Tier 1 (Week 3-4)

**Goals:**
- Write component tests for 8 critical components
- Validate user interactions → RPC call patterns

**Tasks:**
1. Write tests for Tier 1 components (see §4.2)
2. Mock RPC responses using Vitest mocks
3. Test rendering, user interactions, error states, loading states
4. For each component: ~6 tests

**Deliverables:**
- 48 new component tests (6 per component × 8 components)
- All tests passing in local dev and CI
- Component test documentation in `gui/tests/README.md`

### 5.4 Phase 4: e2e Smoke Tests — Tier 1 (Week 4-5)

**Goals:**
- Write 10 critical e2e smoke tests
- Validate full GUI → daemon → kernel integration

**Tasks:**
1. Fix any remaining GUI build issues
2. Write Tier 1 e2e tests (see §4.3)
3. Create helper functions for common workflows
4. Set up screenshots on failure
5. Run tests in CI (headless mode)

**Deliverables:**
- 10 new e2e tests (expanding from current 8 to 18 total)
- All tests passing on fresh install
- e2e test run time <15 minutes

### 5.5 Phase 5: Expand Coverage — Tier 2 (Week 5-7)

**Goals:**
- Add Tier 2 RPC contract tests (30 endpoints)
- Add Tier 2 component tests (7 components)
- Add Tier 2 e2e tests (10 tests)

**Tasks:**
1. RPC contracts: 90 new tests (3 × 30)
2. Component tests: 42 new tests (6 × 7)
3. e2e tests: 10 new tests

**Deliverables:**
- 165 new tests + 75 from Phase 2 = 240 tests
- Test suite runs in <20 minutes total

### 5.6 Phase 6: Complete Coverage — Tier 3 (Week 7-9)

**Goals:**
- Complete all RPC contract tests (65 remaining endpoints)
- Complete all component tests (10 remaining components)
- Complete all e2e tests (5 remaining edge cases)

**Tasks:**
1. RPC contracts: 195 new tests (3 × 65)
2. Component tests: 60 new tests (6 × 10)
3. e2e tests: 5 new tests

**Deliverables:**
- 500+ total new tests
- 100% RPC endpoint coverage
- All critical components tested
- All user journeys validated

### 5.7 Phase 7: CI Integration & Documentation (Week 9-10)

**Goals:**
- Integrate all tests into CI pipeline
- Document testing strategy and best practices
- Create test maintenance guide

**Tasks:**
1. Configure CI to run all test tiers
2. Set up test result reporting (coverage, flakiness)
3. Write `docs/testing/TESTING_GUIDE.md`
4. Write `docs/testing/COMPONENT_TEST_GUIDE.md`
5. Write `docs/testing/E2E_TEST_GUIDE.md`
6. Create test failure runbook

**Deliverables:**
- All tests run in CI on every commit
- Test documentation complete
- Test coverage reports published

### 5.8 Ongoing: Maintenance & Iteration

**Tasks:**
- Add tests for new features as they're developed
- Fix flaky tests
- Refactor brittle selectors
- Update tests when API changes

---

## 6. Automation Strategy

### 6.1 How Claude Code CLI Can Help

**Strengths:**
- Can read/write code files
- Can run pytest and see results
- Can run Playwright and see screenshots
- Can iterate based on test failures
- Can generate boilerplate test code quickly

**Workflow:**
1. **RPC Contract Tests:** Claude reads handler code → generates contract test → runs pytest → fixes failures
2. **Component Tests:** Claude reads component code → generates test with mocked RPC → runs Vitest → fixes failures
3. **e2e Tests:** Claude writes Playwright test → runs in headed mode → views screenshot → iterates on selectors

**Example Prompt for Claude:**
```
Write a contract test for the RPC endpoint `get_structure_vis` in
`tests/daemon/test_daemon_payload_contracts.py`. The endpoint should:
1. Accept payload: { project_root: str, structure_ulid: str, supercell: [int, int, int] }
2. Return: StructureVisData with atoms, bonds, lattice, etc.
3. Test happy path, error for missing structure, error for invalid supercell

Run the test and iterate until it passes.
```

### 6.2 CI Integration

**Test Stages:**
1. **Fast Checks (2 min)** — Linting, type checking, gate tests
2. **Unit & RPC Contract Tests (5 min)** — All pytest tests
3. **Component Tests (3 min)** — Vitest tests
4. **e2e Smoke Tests (15 min)** — Critical Playwright tests
5. **Full e2e Suite (30 min)** — All Playwright tests (nightly only)

**Failure Handling:**
- Stage 1 failure → block PR
- Stage 2-3 failure → block PR
- Stage 4 failure → block PR (critical smoke tests)
- Stage 5 failure → notify but don't block (nightly regression)

### 6.3 Test Stability & Maintenance

**Strategies to Avoid Flakiness:**
1. **Use test IDs** — Prefer `data-testid` over brittle CSS selectors
2. **Wait for conditions** — Use `waitFor()` instead of fixed timeouts
3. **Mock time-sensitive operations** — Don't rely on real timeouts
4. **Isolate tests** — Each test should be independent (no shared state)
5. **Use fixtures** — Consistent test data across runs

**Monitoring:**
- Track test flakiness in CI
- Alert on tests that fail >10% of the time
- Quarantine flaky tests until fixed

---

## 7. Success Metrics

### 7.1 Coverage Targets

| Metric | Current | Target (Phase 5) | Target (Phase 6) |
|--------|---------|------------------|------------------|
| RPC contract test coverage | <10% | 50% (55/120) | 100% (120/120) |
| Python overall coverage | 69% | 75% | 80% |
| Component test coverage | 0% | 50% (13/25) | 100% (25/25) |
| e2e user journey coverage | 15% (12/80) | 50% (40/80) | 75% (60/80) |

### 7.2 Confidence Metrics

**"Can we ship?"** — Answer these questions with tests:
- [ ] Can a new user launch the app and see the welcome screen?
- [ ] Can they open the demo store and view pre-computed results?
- [ ] Can they import a structure from a file?
- [ ] Can they create a calculation and add steps?
- [ ] Can they apply a preset?
- [ ] Can they run a calculation and monitor progress?
- [ ] Can they view analysis results (bands, DOS, convergence)?
- [ ] Can they navigate history and provenance?
- [ ] Does the app gracefully handle errors (missing engine, invalid input, etc.)?

If all these tests pass, **we can ship with confidence**.

---

## Appendix A: Full RPC Endpoint Inventory with Test Coverage Status

| RPC Endpoint | Category | GUI Uses? | Contract Test? | e2e Test? | Priority |
|--------------|----------|-----------|----------------|-----------|----------|
| ping | System | Yes | ⚠️ Basic | ✅ | Tier 1 |
| shutdown | System | Yes | ❌ | ❌ | Tier 1 |
| detect_qe | Environment | Yes | ⚠️ Basic | ❌ | Tier 1 |
| get_env_info | Environment | Yes | ❌ | ❌ | Tier 1 |
| list_qe_engines | Environment | Yes | ❌ | ❌ | Tier 2 |
| set_qe_engine | Environment | Yes | ❌ | ❌ | Tier 1 |
| set_log_level | Settings | Yes | ❌ | ❌ | Tier 3 |
| set_debug_resolution | Settings | Yes | ❌ | ❌ | Tier 3 |
| get_debug_resolution | Settings | Yes | ❌ | ❌ | Tier 3 |
| list_engine_families | Engine | Yes | ❌ | ❌ | Tier 1 |
| list_step_palette | Engine | Yes | ❌ | ❌ | Tier 2 |
| list_engine_ui_parameters | Engine | Yes | ❌ | ❌ | Tier 2 |
| list_engine_parameter_metadata | Engine | Yes | ❌ | ❌ | Tier 2 |
| set_engine_family | Engine | Yes | ❌ | ❌ | Tier 1 |
| get_pseudo_config | Pseudo | Yes | ⚠️ Basic | ❌ | Tier 2 |
| set_pseudo_config | Pseudo | Yes | ❌ | ❌ | Tier 2 |
| validate_pseudo_config | Pseudo | Yes | ⚠️ Basic | ❌ | Tier 2 |
| init_pseudo_dirs | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| install_seed_to_store | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| list_installed_sssp | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| list_seed_archives | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| download_sssp_library | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| download_all_sssp | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| resolve_project_pseudo_provenance | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| import_seed_archives | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| list_pseudo_archives_status | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| install_pseudo_archive | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| analyze_project_pseudo_effects | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| list_libraries | Library | Yes | ❌ | ❌ | Tier 3 |
| get_library_status | Library | Yes | ❌ | ❌ | Tier 3 |
| install_library | Library | Yes | ❌ | ❌ | Tier 3 |
| remove_library | Library | Yes | ❌ | ❌ | Tier 3 |
| repair_library | Library | Yes | ❌ | ❌ | Tier 3 |
| compute_store_size | Library | Yes | ❌ | ❌ | Tier 3 |
| get_project_summary | Project | Yes | ❌ | ❌ | Tier 1 |
| list_structures | Project | Yes | ⚠️ Placeholder | ✅ | Tier 1 |
| list_calculations | Project | Yes | ⚠️ Placeholder | ✅ | Tier 1 |
| find_project_root | Project | Yes | ❌ | ❌ | Tier 1 |
| rebuild_project_registry | Project | Yes | ❌ | ❌ | Tier 2 |
| create_project | Project | Yes | ❌ | ❌ | Tier 1 |
| import_structure | Project | Yes | ❌ | ❌ | Tier 1 |
| structure_search_online | Online | Yes | ❌ | ❌ | Tier 2 |
| structure_get_online_candidate | Online | Yes | ❌ | ❌ | Tier 2 |
| structure_list_providers | Online | Yes | ❌ | ❌ | Tier 2 |
| structure_update_online_sources | Online | Yes | ❌ | ❌ | Tier 3 |
| structure_import_online_candidate | Online | Yes | ❌ | ❌ | Tier 2 |
| rename_structure | Structure | Yes | ❌ | ❌ | Tier 2 |
| delete_structure | Structure | Yes | ❌ | ❌ | Tier 2 |
| can_delete_structure | Structure | Yes | ❌ | ❌ | Tier 2 |
| list_calculation_templates | Calculation | Yes | ❌ | ❌ | Tier 2 |
| create_calculation | Calculation | Yes | ⚠️ Basic | ✅ | Tier 1 |
| rename_calculation | Calculation | Yes | ❌ | ❌ | Tier 2 |
| delete_calculation | Calculation | Yes | ❌ | ❌ | Tier 2 |
| can_delete_calculation | Calculation | Yes | ❌ | ❌ | Tier 2 |
| get_step_detail | Step | Yes | ⚠️ Basic | ✅ | Tier 1 |
| update_step_params | Step | Yes | ⚠️ Basic | ⚠️ Basic | Tier 1 |
| reset_step_params | Step | Yes | ❌ | ❌ | Tier 2 |
| get_common_cards | Step | Yes | ⚠️ Basic | ❌ | Tier 2 |
| promote_relax_structure | Step | Yes | ❌ | ❌ | Tier 3 |
| set_common_card | Step | Yes | ❌ | ❌ | Tier 2 |
| get_pseudo_mapping | Pseudo | Yes | ❌ | ❌ | Tier 2 |
| set_pseudo_mapping | Pseudo | Yes | ❌ | ❌ | Tier 2 |
| import_pseudo_files | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| search_legacy_pseudos | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| download_pseudo_by_filename | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| download_pseudo_candidate | Pseudo | Yes | ❌ | ❌ | Tier 3 |
| get_relax_final_structure_preview | Relax | Yes | ❌ | ❌ | Tier 3 |
| save_relax_final_structure | Relax | Yes | ❌ | ❌ | Tier 3 |
| get_calculation_detail | Calculation | Yes | ⚠️ Basic | ✅ | Tier 1 |
| reorder_calculation_steps | Calculation | Yes | ❌ | ❌ | Tier 2 |
| add_step_to_calculation | Calculation | Yes | ❌ | ⚠️ Basic | Tier 1 |
| change_calculation_structure | Calculation | Yes | ❌ | ❌ | Tier 2 |
| get_calculation_pseudo_mapping | Calculation | Yes | ❌ | ❌ | Tier 2 |
| update_calculation_species_map | Calculation | Yes | ❌ | ❌ | Tier 2 |
| get_pseudo_options_for_calculation | Calculation | Yes | ❌ | ❌ | Tier 3 |
| materialize_pseudo_file | Calculation | Yes | ❌ | ❌ | Tier 3 |
| delete_step | Step | Yes | ❌ | ❌ | Tier 2 |
| get_preset_catalog | Preset | Yes | ❌ | ❌ | Tier 1 |
| detect_presets | Preset | Yes | ❌ | ❌ | Tier 2 |
| detect_workflow | Workflow | Yes | ❌ | ❌ | Tier 2 |
| apply_presets_to_step | Preset | Yes | ❌ | ❌ | Tier 1 |
| apply_presets_to_calculation | Preset | Yes | ❌ | ❌ | Tier 1 |
| get_step_preset_footprints | Preset | Yes | ❌ | ❌ | Tier 2 |
| preflight_check | Execution | Yes | ❌ | ❌ | Tier 2 |
| create_demo_project | Demo | Yes | ❌ | ❌ | Tier 2 |
| list_demo_projects | Demo | Yes | ❌ | ✅ | Tier 2 |
| get_structure_vis | Visualization | Yes | ❌ | ✅ | Tier 1 |
| get_reference_analysis | Analysis | Yes | ❌ | ❌ | Tier 2 |
| get_analysis | Analysis | Yes | ❌ | ✅ | Tier 1 |
| get_analysis_instances_for_step | Analysis | Yes | ❌ | ❌ | Tier 1 |
| get_analysis_snapshot | Analysis | Yes | ❌ | ❌ | Tier 2 |
| get_step_digest | Artifact | Yes | ❌ | ❌ | Tier 2 |
| list_step_artifacts | Artifact | Yes | ❌ | ❌ | Tier 2 |
| read_step_artifact_text | Artifact | Yes | ❌ | ❌ | Tier 3 |
| list_raw_files | Artifact | Yes | ❌ | ❌ | Tier 3 |
| read_raw_file | Artifact | Yes | ❌ | ❌ | Tier 3 |
| compile_fixture_volume | Artifact | No | ❌ | ❌ | Tier 3 |
| run_calculation | Execution | Yes | ⚠️ Placeholder | ✅ | Tier 1 |
| run_step | Execution | Yes | ⚠️ Placeholder | ⚠️ Basic | Tier 1 |
| run_single_step | Execution | Yes | ❌ | ❌ | Tier 2 |
| get_job_status | Job | Yes | ⚠️ Basic | ⚠️ Basic | Tier 1 |
| get_job_logs | Job | Yes | ❌ | ❌ | Tier 2 |
| list_jobs | Job | Yes | ⚠️ Basic | ⚠️ Basic | Tier 1 |
| job_counts | Job | Yes | ⚠️ Basic | ❌ | Tier 1 |
| cancel_job | Job | Yes | ❌ | ❌ | Tier 2 |
| list_journal_entries | History | Yes | ❌ | ❌ | Tier 3 |
| get_journal_entry | History | Yes | ❌ | ❌ | Tier 3 |
| get_project_history | History | Yes | ❌ | ❌ | Tier 3 |
| get_run_revision | History | Yes | ❌ | ❌ | Tier 3 |
| list_project_runs | History | Yes | ❌ | ❌ | Tier 3 |
| pin_analysis_to_history | History | Yes | ❌ | ❌ | Tier 3 |
| can_pin_to_run | History | Yes | ❌ | ❌ | Tier 3 |
| get_pin_data | History | Yes | ❌ | ❌ | Tier 3 |
| get_latest_run_for_step | History | Yes | ❌ | ❌ | Tier 2 |
| delete_project_history | History | Yes | ❌ | ❌ | Tier 3 |
| get_storage_summary | Storage | Yes | ❌ | ❌ | Tier 3 |
| list_workflow_templates | Workflow | Yes | ❌ | ❌ | Tier 2 |
| detect_workflow_for_calculation | Workflow | Yes | ❌ | ❌ | Tier 2 |
| instantiate_workflow | Workflow | Yes | ❌ | ❌ | Tier 2 |

**Summary:**
- Total endpoints: 120
- With contract tests: ~20 (17%)
- With e2e tests: ~12 (10%)
- Tier 1 (critical): 25 endpoints
- Tier 2 (frequent): 30 endpoints
- Tier 3 (complete coverage): 65 endpoints

---

## Appendix B: Test Effort Estimation

| Phase | RPC Tests | Component Tests | e2e Tests | Total Tests | Estimated Hours | Calendar Weeks |
|-------|-----------|-----------------|-----------|-------------|----------------|----------------|
| Phase 1: Foundation | 5 | 1 (sample) | 0 | 6 | 16 | 1 |
| Phase 2: RPC Tier 1 | 75 | 0 | 0 | 75 | 40 | 2 |
| Phase 3: Components Tier 1 | 0 | 48 | 0 | 48 | 32 | 1 |
| Phase 4: e2e Tier 1 | 0 | 0 | 10 | 10 | 24 | 1 |
| Phase 5: Tier 2 | 90 | 42 | 10 | 142 | 80 | 2 |
| Phase 6: Tier 3 | 195 | 60 | 5 | 260 | 120 | 2 |
| Phase 7: CI & Docs | 0 | 0 | 0 | 0 | 24 | 1 |
| **TOTAL** | **365** | **151** | **25** | **541** | **336 hours** | **10 weeks** |

**Assumptions:**
- RPC contract test: ~30 min per test (including debugging)
- Component test: ~40 min per test (more complex mocking)
- e2e test: ~2 hours per test (more brittle, requires iteration)
- Documentation/CI: 24 hours

**Effort with Claude Code Automation:**
- Estimated 40-50% time savings on boilerplate generation
- Actual effort: ~170-200 hours (~5-6 weeks with full-time focus)

---

## Appendix C: Recommended Test File Organization

```
tests/
├── daemon/
│   ├── contract/                          # RPC contract tests
│   │   ├── test_system_rpcs.py            # ping, shutdown
│   │   ├── test_environment_rpcs.py       # detect_qe, get_env_info, etc.
│   │   ├── test_engine_rpcs.py            # list_engine_families, set_engine_family, etc.
│   │   ├── test_pseudo_rpcs.py            # get_pseudo_config, etc.
│   │   ├── test_library_rpcs.py           # list_libraries, install_library, etc.
│   │   ├── test_project_rpcs.py           # create_project, list_structures, etc.
│   │   ├── test_online_rpcs.py            # structure_search_online, etc.
│   │   ├── test_calculation_rpcs.py       # create_calculation, get_calculation_detail, etc.
│   │   ├── test_step_rpcs.py              # get_step_detail, update_step_params, etc.
│   │   ├── test_preset_rpcs.py            # get_preset_catalog, apply_presets, etc.
│   │   ├── test_workflow_rpcs.py          # list_workflow_templates, instantiate_workflow, etc.
│   │   ├── test_execution_rpcs.py         # run_calculation, run_step, preflight_check
│   │   ├── test_job_rpcs.py               # get_job_status, list_jobs, cancel_job, etc.
│   │   ├── test_analysis_rpcs.py          # get_analysis, get_analysis_snapshot, etc.
│   │   ├── test_artifact_rpcs.py          # get_step_digest, list_step_artifacts, etc.
│   │   ├── test_history_rpcs.py           # get_project_history, pin_analysis, etc.
│   │   └── conftest.py                    # Shared fixtures
│   ├── workflow/                          # Workflow integration tests
│   │   ├── test_full_scf_workflow.py
│   │   ├── test_relax_workflow.py
│   │   └── test_multi_engine_workflow.py
│   └── ... (existing daemon tests)
├── gui/                                   # New: GUI component tests
│   ├── components/
│   │   ├── CalculationListPanel.spec.tsx
│   │   ├── CalculationOverviewTab.spec.tsx
│   │   ├── CalculationAnalysisPanel.spec.tsx
│   │   ├── StepDetailPanel.spec.tsx
│   │   ├── PresetSelector.spec.tsx
│   │   ├── EngineParameterBrowserPanel.spec.tsx
│   │   ├── AnalysisVizPanel.spec.tsx
│   │   ├── FatbandsVizPanel.spec.tsx
│   │   ├── Field3DVizPanel.spec.tsx
│   │   └── ... (more component tests)
│   ├── services/
│   │   └── qms-daemon.spec.ts              # RPC client tests
│   └── vitest.config.ts                   # Vitest config
└── (existing test structure)

gui/tests/e2e/                             # Existing e2e tests (expand)
├── tier1/                                 # Critical smoke tests
│   ├── app_launch.spec.ts
│   ├── demo_gallery.spec.ts
│   ├── structure_viewing.spec.ts
│   ├── structure_import.spec.ts
│   ├── structure_fetch_online.spec.ts
│   ├── calculation_creation.spec.ts
│   ├── step_management.spec.ts
│   ├── preset_application.spec.ts
│   ├── calculation_execution.spec.ts
│   └── analysis_viewing.spec.ts
├── tier2/                                 # Advanced workflows
│   ├── engine_setup.spec.ts
│   ├── pseudo_setup.spec.ts
│   ├── workflow_template.spec.ts
│   ├── multi_step_execution.spec.ts
│   ├── step_reordering.spec.ts
│   ├── parameter_editing.spec.ts
│   ├── calculation_rename_delete.spec.ts
│   ├── structure_rename_delete.spec.ts
│   ├── history_navigation.spec.ts
│   └── error_recovery.spec.ts
├── tier3/                                 # Edge cases
│   ├── tab_persistence.spec.ts
│   ├── analysis_auto_detection.spec.ts
│   ├── relax_promotion.spec.ts
│   ├── fatbands_viz.spec.ts
│   └── field3d_viz.spec.ts
├── helpers/                               # Test helpers
│   ├── navigation.ts
│   ├── workflows.ts
│   ├── structures.ts
│   ├── calculations.ts
│   └── assertions.ts
└── fixtures/                              # Test fixtures
    ├── structures/
    │   ├── si.cif
    │   ├── si.vasp
    │   └── water.xyz
    └── configs/
        └── mock_mp_response.json
```

---

## Conclusion

This plan establishes a **clear, executable roadmap** to achieve comprehensive GUI testing coverage for QMatSuite. By prioritizing RPC contract tests (Plan C), we gain the most confidence with the least effort. Component tests (Plan D) validate UI logic in isolation, and e2e tests (Plan A) ensure full integration works end-to-end.

**Next Steps:**
1. Get approval for this plan
2. Execute Phase 1 (Foundation)
3. Begin Phase 2 (RPC Tier 1 contract tests)
4. Iterate through remaining phases
5. Ship with confidence! 🚀

---

**Document Metadata:**
- **Author:** Claude (Sonnet 4.5)
- **Date:** 2026-02-13
- **Version:** 1.0
- **Status:** Draft for Review
- **Target Audience:** QMatSuite development team, stakeholders
