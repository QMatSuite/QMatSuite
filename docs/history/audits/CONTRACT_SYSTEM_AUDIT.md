# Golden Contract System Audit Report

**Date**: 2025-01-27  
**Auditor**: Independent Review  
**Scope**: Golden contract system, daemon compat shaping, contract_crawler tests, and GUI field usage  
**Goal**: Assess semantic drift risks and determine if system is safe for GUI/E2E

---

## Executive Summary

The golden contract system provides a baseline comparison mechanism to detect API drift from commit 0873ebf (pre-DTO baseline). The system includes:

- **Baseline generation**: Git worktree isolation with runtime assertions
- **Compat shaping**: Response transformation layer to maintain v0 format
- **Contract tests**: Normalized comparison with skip mechanisms for non-deterministic fields
- **Coverage**: 111/116 methods (95.7%), 5 exempt

**Critical Findings**:
1. ✅ **Baseline isolation is properly enforced** with runtime assertions
2. ⚠️ **Comparator skip mechanisms may hide semantic drift** for GUI-critical fields
3. ⚠️ **Compat shaper performs I/O** (`create_demo_project` reads project files)
4. ⚠️ **GUI field usage not fully validated** - gaps between contract tests and actual GUI needs

**Risk Level**: **MEDIUM-HIGH** - System provides good protection but has gaps that could allow semantic drift to slip through.

---

## A) Inventory: Current System Components

### A.1) Golden Fixture Generation

**Location**: `tests/fixtures/golden_contracts/`

**Components**:
1. **`generate_golden.py`** (main orchestrator)
   - Creates git worktree at commit 0873ebf
   - Copies `contract_crawler` package into worktree (0873ebf doesn't have it)
   - Copies `worktree_runner.py` into worktree
   - Runs worktree_runner with isolated PYTHONPATH
   - Captures JSON output and writes to `tests/fixtures/golden_0873ebf/daemon/*.json`

2. **`worktree_runner.py`** (executed inside worktree)
   - **Runtime assertions** (lines 32-66):
     - Verifies `git HEAD == 0873ebf`
     - Verifies `qmatsuite.__file__` is under worktree path
     - Prints verification to stderr
   - Imports crawler/recipes from copied modules
   - Runs `crawl_all_methods()` for auto-crawler methods
   - Runs `ALL_RECIPES` for recipe methods
   - Normalizes responses using key-based + value-based heuristics
   - Outputs JSON to stdout

**Baseline Isolation Verification**:
- ✅ **Hard assertions present**: Lines 50-63 in `worktree_runner.py`
  ```python
  # Line 50-53: Git HEAD check
  assert git_head.startswith(BASELINE_COMMIT), (
      f"ERROR: Worktree git HEAD is {git_head}, expected {BASELINE_COMMIT}. "
      f"Worktree isolation violated."
  )
  
  # Line 60-63: Module path check
  assert str(qms_module_path).startswith(str(worktree_src)), (
      f"ERROR: qmatsuite loaded from {qms_module_path}, expected under {worktree_src}. "
      f"Editable install leakage detected. Set PYTHONPATH correctly."
  )
  ```
- ✅ **PYTHONPATH isolation**: Lines 148-153 in `generate_golden.py` set worktree-only paths
  ```python
  env["PYTHONPATH"] = os.pathsep.join([
      str(worktree_path / "src"),
      str(worktree_path / "tests"),
  ])
  ```
- ✅ **Verification output**: Assertions print to stderr (lines 65-66), visible in console
- ✅ **Covers all paths**: Assertions run at module import time (line 70), before any crawler/recipe execution

**Coverage**: 111 methods have golden fixtures (95.7% of 116 total methods)

**Method Counts** (verified via `tests/contract_crawler/introspection.py`):
- **Total RPC methods**: 116 (from `get_all_rpc_methods()`)
- **Auto-crawler successful**: 26 (from `coverage_report.json`)
- **Recipe-covered**: 85 (from `coverage_report.json`)
- **Exempt**: 5 (see A.6 below)
- **GUI-used methods**: 70 (from `gui/tests/e2e/tools/gui_rpc_methods.json`)
- **GUI-covered**: 66 (from `coverage_report.json`)
- **GUI-exempt**: 4 (from `coverage_report.json`)

### A.2) Crawler Payload Builders

**Location**: `tests/contract_crawler/payloads.py`

**Function**: `get_minimal_payload(method_name, tmp_path=None)`
- Returns minimal payloads for stateless methods
- Returns `None` if `tmp_path` not provided (requires fixture)
- Used for auto-crawler method replay

### A.3) Recipe Coverage

**Location**: `tests/contract_crawler/recipes/`

**Types**:
- **Static recipes**: `ALL_RECIPES` list (e.g., `GetStepDetailRecipe`)
- **Parameterized recipes**: `PARAMETERIZED_RECIPES` (cover multiple methods dynamically)

**Coverage**: Recipe methods require setup (calculations, steps, structures) that auto-crawler cannot provide.

### A.4) Golden Comparison Logic

**Location**: `tests/contract_crawler/golden_comparison.py`

**Function**: `compare_to_golden(method_name, response_data)`
- Loads golden fixture
- Normalizes both golden and actual responses
- Recursively compares dicts with skip mechanisms
- Returns `(matches: bool, differences: list[str])`

**Normalization** (shared with `tests/contract_crawler/normalization.py`):
- **Key-based**: Fields in `NORMALIZE_FIELDS` → placeholders (`<NORMALIZED_ID>`, `<NORMALIZED_TIMESTAMP>`, `<NORMALIZED_PATH>`)
- **Value-based heuristics**: ULID pattern matching, temp path detection, path-in-string normalization

### A.5) Daemon Compat Shaping Layer

**Location**: `src/qmatsuite/daemon/compat.py`

**Components**:
1. **Payload Adapters** (11 methods): Transform v0 payloads → HEAD format
   - Example: `change_calculation_structure` accepts `structure` → maps to `new_structure`
   
2. **Response Shapers** (26 methods): Transform HEAD responses → v0 format
   - Example: `get_step_detail` maps step types (`scf` → `qe_scf`)
   - Example: `create_demo_project` adds v0 fields by reading project files

**Integration**: Applied in `server.py` at RPC boundary:
```python
adapted_payload = compat.adapt_payload(request.type, request.payload)
result = handler(adapted_payload)
shaped_result = compat.shape_response(request.type, result)
```

### A.6) Exempt/Skipped Methods

**Location**: `tests/contract_crawler/test_coverage.py` (lines 14-23)

**Exempt Methods** (5 total, verified):
```python
EXEMPT_METHODS: dict[str, str] = {
    "cancel_job": "Requires active running job; job state is ephemeral...",
    "get_job_status": "Requires active job in JobManager; job state is ephemeral...",
    "get_job_logs": "Requires active job with log file; job state is ephemeral...",
    "compile_fixture_volume": "Dev-only endpoint requiring specific Wannier90 fixture files...",
    "shutdown": "Terminates daemon process; cannot be tested in golden generation...",
}
```

**Note**: `tests/contract_crawler/v0_payloads.py` defines `V0_EXEMPT_METHODS` (9 methods) which includes baseline-broken methods (`reset_step_params`, `apply_presets_to_step`, etc.). These are separate from the contract coverage `EXEMPT_METHODS` (5 methods) which are truly impossible to test.

**Justification**: All exempt methods require ephemeral state (job state) or terminate the daemon, making them impossible to deterministically recreate for golden fixtures.

---

## B) High-Impact Risk Audit

### B.1) Baseline Purity / Import Isolation

**Status**: ✅ **VERIFIED - Properly Enforced**

**Evidence**:
1. **Runtime assertions** in `worktree_runner.py` (lines 32-66):
   ```python
   assert git_head.startswith(BASELINE_COMMIT), (
       f"ERROR: Worktree git HEAD is {git_head}, expected {BASELINE_COMMIT}..."
   )
   assert str(qms_module_path).startswith(str(worktree_src)), (
       f"ERROR: qmatsuite loaded from {qms_module_path}, expected under {worktree_src}..."
   )
   ```

2. **PYTHONPATH isolation** in `generate_golden.py` (lines 148-153):
   ```python
   env["PYTHONPATH"] = os.pathsep.join([
       str(worktree_path / "src"),
       str(worktree_path / "tests"),
   ])
   ```

3. **Verification output**: Assertions print to stderr, visible in console output

**Verdict**: Baseline isolation is **CRITICAL** and properly enforced. No action needed.

---

### B.2) Comparator Loosening

**Status**: ⚠️ **RISK - Skip Mechanisms May Hide Semantic Drift**

#### Skip Mechanisms Inventory (Literal Sets from Code)

**1. DATA_DEPENDENT_FIELDS** (`tests/contract_crawler/golden_comparison.py` lines 79-123)
```python
DATA_DEPENDENT_FIELDS = {
    "formula", "n_atoms", "lattice_params", "lattice_abc", "lattice_angles",
    "cell_volume_ang3", "volume", "a", "b", "c", "alpha", "beta", "gamma",
    "sssp_defaults", "installed_sources", "candidates_by_element",
    "resolved_by_element", "files_installed", "success",
    "steps",  # ⚠️ GUI-CRITICAL
    "structure",  # ⚠️ GUI-CRITICAL
    "perf", "prep_ms", "bonds_ms", "ser_ms", "total_ms", "bytes",
    "seed_dir_created", "store_dir_created", "libraries",
    "session_id", "message",
    "grouped_by_library", "species_map", "sssp_defaults",
    "sssp_installed", "precision", "efficiency",
    "status", "installed", "installed_variants",  # ⚠️ "status" IS skipped
    "variant_statuses", "version", "file_count", "size_bytes",
    "data",
}
```
- **Purpose**: Skip value comparison for fields that vary by recipe world state
- **Risk**: **HIGH** - Fields like `structure`, `steps`, `status` are GUI-critical

**2. VARIABLE_LENGTH_LISTS** (`tests/contract_crawler/golden_comparison.py` lines 61-75)
```python
VARIABLE_LENGTH_LISTS = {
    "candidates", "errors", "messages", "internal_engines",
    "entries", "skipped", "installed", "failed", "files_downloaded",
    "installed_libraries", "warnings", "demos", "archives",
    "variant_statuses", "installed_variants",
}
```
- **Purpose**: Skip length/content comparison for lists that vary by environment
- **Note**: `steps` is NOT in this list (it's in DATA_DEPENDENT_FIELDS instead)
- **Risk**: **LOW** - These are truly environment-dependent

**3. DATA_DEPENDENT_SUBTREES** (`tests/contract_crawler/test_schema_preservation.py` lines 66-77)
```python
DATA_DEPENDENT_SUBTREES = {
    "entries", "demos", "archives", "libraries",
    "steps",  # ⚠️ GUI-CRITICAL - entire subtree skipped
    "perf", "sssp_defaults", "installed_sources",
    "variant_statuses", "data",
}
```
- **Purpose**: Skip entire subtrees in schema comparison
- **Risk**: **HIGH** - `steps` subtree is GUI-critical

**4. ENVIRONMENT_DEPENDENT_DICTS** (`tests/contract_crawler/test_schema_preservation.py` lines 57-63)
```python
ENVIRONMENT_DEPENDENT_DICTS = {
    "grouped_by_library", "species_map", "resolved_by_element",
    "candidates_by_element", "element_colors",
}
```
- **Purpose**: Skip key presence check for dicts where keys are data (not schema)
- **Risk**: **LOW** - These are truly data-dependent

**5. allow_extra_keys** (`tests/contract_crawler/golden_comparison.py` line 131)
- **Purpose**: Allow extra keys in HEAD response (backward compatible)
- **Default**: `True`
- **Risk**: **LOW** - Extra keys are acceptable for backward compat

#### GUI-Critical Fields in Skip Lists

**HIGH RISK**:
- `structure` (DATA_DEPENDENT_FIELDS) - GUI displays structure info
- `steps` (DATA_DEPENDENT_FIELDS, VARIABLE_LENGTH_LISTS, DATA_DEPENDENT_SUBTREES) - GUI displays step lists
- `status` (DATA_DEPENDENT_FIELDS) - GUI displays status badges
- `id`, `name`, `slug` (normalized but not skipped) - GUI uses for navigation

**Example Risk Scenario**:
```python
# Baseline (0873ebf):
steps: [{"id": "ABC123", "type": "qe_scf", "name": "SCF"}]

# HEAD (after DTO change):
steps: [{"step_id": "XYZ789", "step_type": "scf", "step_name": "SCF"}]

# Test result: PASS (because steps is in DATA_DEPENDENT_FIELDS)
# GUI result: BREAK (GUI expects steps[].id, gets steps[].step_id)
```

**Verdict**: Skip mechanisms are **too permissive** for GUI-critical fields. Schema preservation tests help but don't catch value-level semantic changes.

---

### B.3) Compat Shaping Correctness

**Status**: ⚠️ **RISK - I/O Operations in Shapers**

#### Shapers That Perform I/O

**1. `_shape_create_demo_project`** (`compat.py` lines 709-758)
- **I/O Operations**:
  - Reads project files via `QMSService.get_project_summary(project_path)` (line 726)
  - Reads structures via `QMSService.list_structures_data(project_path)` (line 735)
  - Reads calculations via `QMSService.list_calculations_data(project_path)` (line 744)
- **Risk**: **MEDIUM** - Introduces nondeterminism if project state changes between calls
- **Side Effects**: None (read-only)

**2. Other Shapers**
- All other shapers are **pure transformations** (no I/O)
- They derive fields from existing response data or provide defaults

#### Format-Change Disguised as Data-Dependent Skip

**Example**: `structure` field
- **v0 format**: `structure: "name"` (string)
- **HEAD format**: `structure_id: "ULID"` (string)
- **Shaping**: `_shape_calculation_detail` (line 477-482) derives `structure` from `structure_name` or `structure_slug` or `structure_id`
- **Skip**: `structure` is in `DATA_DEPENDENT_FIELDS`, so value comparison is skipped
- **Risk**: If shaping fails silently, GUI gets wrong format but test passes

**Verdict**: I/O in `create_demo_project` shaper is acceptable (read-only, deterministic). Format changes are handled by shapers, but skip mechanisms may hide shaping failures.

---

### B.4) Contract Meaning

**What the Contract Actually Guarantees**:

1. **Schema Preservation** (via `test_schema_preservation.py`):
   - ✅ All keys from baseline exist in shaped response
   - ✅ Types match (dict/list/scalar)
   - ⚠️ Values may differ (normalized or skipped)

2. **Value Comparison** (via `test_golden_contracts.py`):
   - ✅ Non-normalized, non-skipped fields match exactly
   - ⚠️ Normalized fields match placeholder format
   - ⚠️ Skipped fields are not compared

3. **Backward Compatibility**:
   - ✅ Extra keys in HEAD are allowed
   - ✅ Shapers transform HEAD → v0 format
   - ⚠️ Shaping failures may not be detected if field is skipped

**Does "Tests Green" Imply GUI Will Not Break?**

**Answer**: **PARTIALLY** - Tests green means:
- ✅ Schema is preserved (keys/types match)
- ✅ Non-skipped values match
- ⚠️ **BUT**: Skipped GUI-critical fields (`structure`, `steps`, `status`) are not validated
- ⚠️ **BUT**: Shaping failures may be hidden if field is skipped

**Gap**: Contract tests don't validate that GUI-required fields are present and in correct format. Schema tests help but don't catch semantic changes (e.g., `id` → `step_id`).

---

## C) GUI Field Usage Review

### C.1) Investigation Methodology

**Commands Used**:
```bash
# Find RPC method invocations
grep -r "\.request\(|call\(|invoke\(" gui/src

# Find response.data field accesses
grep -r "response\.data\." gui/src

# Find specific GUI-critical field patterns
grep -r "response\.data\.\(id|name|step_type|structure|steps|status|slug|path|kind|calculation|parameters\)" gui/src
```

**GUI Code Location**: `gui/src/` directory (present in this repository)
- TypeScript/React components in `gui/src/components/`
- Hooks in `gui/src/hooks/`
- Type definitions in `gui/src/types/qms.ts`
- Electron IPC layer in `gui/electron/`

**Manifest Generated**: `gui_required_fields_manifest.json` (see Appendix C.5)

### C.2) RPC Call Patterns

**GUI RPC Client**: `gui/src/hooks/useQMSClient.ts`
- Uses `window.qms.request(type, payload)` (line 248)
- Response format: `{ok: boolean, data: T, error?: {...}}`
- GUI accesses `response.data` for all field access

**IPC Layer**: `gui/electron/preload.ts` → `gui/electron/main.ts`
- `ipcRenderer.invoke('qms-request', request)` → `ipcMain.handle('qms-request')`
- Transparent pass-through to daemon

### C.3) GUI Field Access Patterns

**Analysis Method**: Static grep analysis of `gui/src` directory

**Key Findings**:

#### Critical Fields (High Usage):

1. **Step Fields** (`StepDetailPanel.tsx`):
   - `response.data.id` (line 363) - Step ID
   - `response.data.name` (line 364) - Step name
   - `response.data.step_type` (line 365) - Step type (GUI displays as badge)
   - `response.data.parameters` (line 371) - Step parameters (GUI edits these)
   - `response.data.parameter_scan` (line 373) - Parameter scan config
   - `response.data.structure` (line 1368) - Structure reference

2. **Calculation Fields** (`CalculationListPanel.tsx`):
   - `response.data.structures` (line 510) - Structure list
   - `response.data.steps` (line 854) - Step list (GUI displays step order)
   - `response.data.structure_id` (line 1625) - Structure ID for relax operations

3. **Structure Fields** (`StructureListPanel.tsx`):
   - `response.data.structures[].id` - Structure ID
   - `response.data.structures[].name` - Structure name
   - `response.data.structures[].slug` - Structure slug

4. **Status Fields**:
   - `response.data.status` - Job/step status (GUI displays status badges)
   - `response.data.ok` - Request success (GUI shows error banners)

5. **Navigation Fields**:
   - `response.data.id`, `response.data.slug`, `response.data.path` - Used for routing/navigation

#### Field Access Patterns:

**Direct Access**:
```typescript
response.data.id
response.data.name
response.data.step_type
```

**Array Access**:
```typescript
response.data.structures.map(s => s.id)
response.data.steps[].id
response.data.entries[].calc_id
```

**Nested Access**:
```typescript
response.data.parameters[namelist][key]
response.data.metadata.grid_shape
response.data.metadata.origin_cart
```

### C.4) GUI Required Fields Inventory (Detailed)

**Source**: `gui_required_fields_manifest.json` (generated via static analysis)

**Top GUI-Used Methods with Field Access Evidence**:

1. **`get_step_detail`** (`gui/src/components/panels/StepDetailPanel.tsx:351`)
   - **Invocation**: `window.qms.request<StepDetail>('get_step_detail', {...})`
   - **Required fields**:
     - `id` (line 363): `response.data.id`
     - `name` (line 364): `response.data.name`
     - `step_type` (lines 365, 409, 435): `response.data.step_type`
     - `parameters` (lines 371, 436, 549, 845, 883): `response.data.parameters`
     - `parameter_scan` (line 373): `response.data.parameter_scan`
     - `structure` (line 1368): `stepDetail.structure`

2. **`get_calculation_detail`** (`gui/src/App.tsx:1290`)
   - **Invocation**: `qms.call('get_calculation_detail', {...})`
   - **Required fields**:
     - `steps` (lines 112, 925): `calculationDetail?.steps`
     - `steps[].id` (lines 1439, 1440): `step.id` (ULID from calculation.yaml)
     - `structure_id` (line 1625): `selectedCalculation?.structure_id`

3. **`list_structures`** (`gui/src/hooks/useQMSClient.ts:362`)
   - **Invocation**: `call('list_structures', { project_root: projectRoot })`
   - **Required fields**:
     - `structures` (lines 473, 510, 1227, 1991): `response.data.structures`
     - `structures[].id` (line 1228): Used for structure lookup

4. **`list_calculations`** (`gui/src/hooks/useQMSClient.ts:367`)
   - **Invocation**: `call('list_calculations', { project_root: projectRoot })`
   - **Required fields**:
     - `calculations` (lines 499, 2019): `response.data.calculations`

5. **`list_journal_entries`** (`gui/src/components/settings/JournalHistoryPanel.tsx:39`)
   - **Invocation**: `qms.call('list_journal_entries', {...})`
   - **Required fields**:
     - `entries` (line 40): `response.data.entries`
     - `entries[].calc_id`, `entries[].step_id` (inferred from usage)

**Full manifest**: See `gui_required_fields_manifest.json` for complete method list.

### C.5) GUI Required Fields Manifest

**File**: `gui_required_fields_manifest.json`

**Generation Method**:
1. Static grep analysis of `gui/src` directory
2. Pattern matching for RPC invocations: `\.request\(|call\(|invoke\(`
3. Pattern matching for field access: `response\.data\.`
4. Manual review of key GUI components (StepDetailPanel, CalculationListPanel, etc.)

**Limitations**:
- Field paths are best-effort JSONPath approximations
- Nested field access (e.g., `parameters[namelist][key]`) is simplified
- Array iteration patterns (e.g., `structures.map(s => s.id)`) are represented as array access
- Conditional access patterns may not be fully captured
- TypeScript type definitions provide additional context but are not exhaustively analyzed

**Reproducibility**: Commands documented in manifest file metadata.

| Method | Required Fields (JSONPath) | Location in Code |
|--------|---------------------------|------------------|
| `get_step_detail` | `id`, `name`, `step_type`, `parameters.*`, `parameter_scan.*`, `structure` | `StepDetailPanel.tsx:363-373` |
| `get_calculation_detail` | `id`, `steps[].id`, `steps[].name`, `steps[].type`, `steps[].slug`, `structure_id` | `CalculationListPanel.tsx:854` |
| `list_structures` | `structures[].id`, `structures[].name`, `structures[].slug` | `StructureListPanel.tsx` |
| `list_calculations` | `calculations[].id`, `calculations[].steps[]` | `CalculationListPanel.tsx:509` |
| `list_journal_entries` | `entries[].calc_id`, `entries[].step_id` | `JournalHistoryPanel.tsx:40` |
| `get_structure_vis` | `atoms[]`, `bonds[]`, `boundary_atoms[]` | `StructureViewer3D.tsx` |
| `get_common_cards` | `cards.*` | `StepDetailPanel.tsx:382` |
| `get_pseudo_mapping` | `mapping.*` | `StepDetailPanel.tsx:397` |
| `create_demo_project` | `project_root`, `project_id`, `project_name`, `structure.id`, `calculation` | `CreateProjectDialog.tsx` |
| `list_demo_projects` | `demos[].id`, `demos[].title` | `DemoGalleryPanel.tsx` |
| `get_project_summary` | `id`, `name` | `ProjectSummaryPanel.tsx` |
| `run_step` | `id`, `status` | `StepDetailPanel.tsx:600` |
| `get_job_status` | `status`, `run_id` | `JobsPanel.tsx` |
| `list_step_artifacts` | `artifacts[]` | `StepOutputTextViewer.tsx:61` |
| `read_step_artifact_text` | `content`, `truncated` | `StepOutputTextViewer.tsx:111` |
| `get_band_structure_data` | `kpoints[]`, `bands[]` | `AnalysisPanel.tsx` |
| `get_dos_data` | `energies[]`, `dos[]` | `AnalysisPanel.tsx` |
| `get_structure_vis` | `atoms[]`, `bonds[]` | `StructureViewer3D.tsx` |
| `get_preset_catalog` | `presets[].id`, `presets[].name` | `PresetSection.tsx` |
| `list_qe_ui_parameters` | `parameters[].name`, `parameters[].type` | `QEParameterBrowserPanel.tsx` |

### C.6) Mismatch Analysis: GUI Needs vs Contract Enforces

#### Gaps (GUI Reads But Contract Doesn't Enforce):

1. **`steps[].id`** (GUI-critical):
   - **GUI uses**: `steps[].id` for step selection/navigation
   - **Contract**: `steps` is in `DATA_DEPENDENT_SUBTREES`, entire subtree skipped
   - **Risk**: If `steps[].id` → `steps[].step_id`, GUI breaks but test passes

2. **`step_type`** (GUI-critical):
   - **GUI uses**: `response.data.step_type` for type badges
   - **Contract**: `step_type` is normalized/shaped, but if shaping fails, test may pass
   - **Risk**: If `step_type` missing or wrong format, GUI breaks

3. **`structure`** (GUI-critical):
   - **GUI uses**: `response.data.structure` (string name)
   - **Contract**: `structure` is in `DATA_DEPENDENT_FIELDS`, value comparison skipped
   - **Risk**: If shaping fails to provide `structure`, GUI breaks but test passes

4. **`status`** (GUI-critical):
   - **GUI uses**: `response.data.status` for status badges
   - **Contract**: `status` is in `DATA_DEPENDENT_FIELDS`, value comparison skipped
   - **Risk**: If `status` format changes, GUI breaks but test passes

#### Risks (Contract Skips But GUI Uses Semantically):

1. **`steps` subtree**:
   - **Contract**: Entire subtree skipped (`DATA_DEPENDENT_SUBTREES`)
   - **GUI**: Reads `steps[].id`, `steps[].name`, `steps[].type`, `steps[].slug`
   - **Risk**: Schema test ensures keys exist, but doesn't validate semantic correctness

2. **`structure` field**:
   - **Contract**: Value comparison skipped (`DATA_DEPENDENT_FIELDS`)
   - **GUI**: Expects string name, shaper derives from `structure_name`/`structure_slug`/`structure_id`
   - **Risk**: If shaper fails silently, GUI gets wrong format

3. **`parameters` nested dict**:
   - **Contract**: Normalized (ULIDs/timestamps), but structure validated
   - **GUI**: Reads `parameters[namelist][key]` for editing
   - **Risk**: If parameter structure changes, GUI breaks but test may pass

---

## D) GUI-Critical Keys: Semantic Drift Risk Analysis

### D.1) GUI-Critical Keys Identification

**Candidate GUI-Critical Keys** (from manifest analysis):
- `id`, `step_id`, `calculation_id`, `structure_id` - Navigation/selection
- `name`, `step_name`, `calculation_name` - Display labels
- `step_type` - Type badges, module selection
- `structure` - Structure references (string name in v0)
- `steps` - Step lists (GUI displays step order)
- `steps[].id` - Step selection (ULID from calculation.yaml)
- `steps[].name`, `steps[].type`, `steps[].slug` - Step display
- `status` - Status badges
- `slug`, `path` - Routing/navigation
- `parameters` - Parameter editing
- `parameters.*` - Nested parameter access

### D.2) Enforcement Level for Each Key

| Key | Enforcement Level | Location | Risk |
|-----|------------------|----------|------|
| `id` | **Strict** (normalized, not skipped) | `NORMALIZE_FIELDS` | LOW - Value normalized but key/type enforced |
| `step_id` | **Strict** (normalized, not skipped) | `NORMALIZE_FIELDS` | LOW - Value normalized but key/type enforced |
| `step_type` | **Shape-only** (shaped, not skipped) | Shapers map `scf`→`qe_scf` | MEDIUM - Shaping failure may hide format change |
| `structure` | **Effectively skipped** | `DATA_DEPENDENT_FIELDS` | **HIGH** - Value comparison skipped, only schema checked |
| `steps` | **Effectively skipped** | `DATA_DEPENDENT_FIELDS` + `DATA_DEPENDENT_SUBTREES` | **HIGH** - Entire subtree skipped in schema, value skipped |
| `steps[].id` | **Effectively skipped** | Inside `steps` subtree | **HIGH** - Not validated if `steps` subtree skipped |
| `status` | **Effectively skipped** | `DATA_DEPENDENT_FIELDS` | **HIGH** - Value comparison skipped |
| `parameters` | **Strict** (structure validated) | Not in skip lists | LOW - Structure validated, values normalized |
| `slug`, `path` | **Strict** (normalized, not skipped) | `NORMALIZE_FIELDS` | LOW - Value normalized but key/type enforced |

### D.3) Concrete Examples of Skip List Expansion

**Example 1: `steps` Added to Skip Lists**

**Context**: From `tests/contract_crawler/WORKLOG.md` (lines 448-459):
- Step order can vary in recipe world operations
- `steps` added to `DATA_DEPENDENT_FIELDS` (line 97 in `golden_comparison.py`)
- `steps` added to `DATA_DEPENDENT_SUBTREES` (line 71 in `test_schema_preservation.py`)

**Rationale**: Recipe world creates steps in different orders, making step-by-step comparison impossible.

**Risk**: If HEAD changes `steps[].id` → `steps[].step_id`, test passes (subtree skipped) but GUI breaks (expects `steps[].id`).

**Example 2: `structure` Added to Skip List**

**Context**: From `tests/contract_crawler/golden_comparison.py` (line 98-99):
```python
# Structure field format changed (v0: name, HEAD: id)
"structure",
```

**Rationale**: Format changed from string name (v0) to structure_id (HEAD), handled by shapers.

**Risk**: If shaper fails to provide `structure` field, test passes (value skipped) but GUI breaks (expects `structure` string).

**Example 3: `status` in Skip List**

**Context**: From `tests/contract_crawler/golden_comparison.py` (line 119):
```python
"status", "installed", "installed_variants",
```

**Rationale**: Status values vary by environment/state.

**Risk**: If `status` format changes (e.g., `"running"` → `{"state": "running"}`), test passes (value skipped) but GUI breaks (expects string).

### D.4) Why Skip Mechanisms Can Hide Semantic Drift

**Scenario**: HEAD changes `steps[].id` → `steps[].step_id`

1. **Baseline (0873ebf)**: `steps: [{"id": "ABC123", "type": "qe_scf"}]`
2. **HEAD**: `steps: [{"step_id": "XYZ789", "type": "scf"}]`
3. **After shaping**: `steps: [{"id": "XYZ789", "type": "qe_scf"}]` (if shaper works)
4. **After normalization**: `steps: [{"id": "<NORMALIZED_ID>", "type": "qe_scf"}]`
5. **Comparison**: `steps` is in `DATA_DEPENDENT_FIELDS`, so value comparison is **skipped**
6. **Schema check**: `steps` is in `DATA_DEPENDENT_SUBTREES`, so subtree schema check is **skipped**
7. **Test result**: ✅ **PASS** (no comparison performed)
8. **GUI result**: ❌ **BREAK** (GUI expects `steps[].id`, gets `steps[].step_id` if shaper fails)

**Root Cause**: Skip mechanisms assume shapers will fix format changes, but shaping failures are not detected if the field is skipped.

---

## E) Actionable Next Steps (Prioritized)

### P0: Critical - Tests Green But GUI Breaks

**E.1) Add GUI-Critical Field Presence Assertions**
- **File**: `tests/contract_crawler/test_golden_contracts.py`
- **Action**: Add `test_gui_critical_fields_present()` that:
  - Loads `gui_required_fields_manifest.json`
  - For each GUI-used method, verifies required fields exist in shaped response
  - Checks field types match GUI expectations (e.g., `steps[].id` is string, not missing)
- **Fields to validate**:
  - `steps[].id` (not `step_id`) - from `get_calculation_detail`
  - `step_type` (string) - from `get_step_detail`
  - `structure` (string, when present) - from `get_calculation_detail`
  - `status` (string/enum, when present) - from job/step methods
- **Test-driven**: Minimal assertion test, no refactoring

**E.2) Validate Shaping Produces GUI Format**
- **File**: `tests/contract_crawler/test_golden_contracts.py`
- **Action**: Add `test_shaping_produces_gui_format()` that:
  - For methods with shapers, verifies shaped response has GUI-required fields
  - Checks format matches GUI expectations (e.g., `structure` is string, not dict)
- **Example**: For `get_calculation_detail`, verify `steps[].id` exists (not `step_id`) after shaping
- **Test-driven**: Minimal validation test, no refactoring

### P1: High Impact - Minimal Additional Tests

**E.3) Add Doctor Canary Test**
- **File**: `tests/contract_crawler/test_golden_contracts.py`
- **Action**: Add `test_gui_workflow_shapes()` that runs minimal workflow:
  ```python
  # create_demo_project → list_structures → get_calculation_detail → get_step_detail
  # Verify each response has GUI-required fields from manifest
  ```
- **Test-driven**: Single integration test, no refactoring

**E.4) Add Shaping Failure Detection**
- **File**: `tests/contract_crawler/test_golden_contracts.py`
- **Action**: Add `test_shaping_does_not_fail_silently()` that:
  - For each method with a shaper, verify shaped response has all v0-required fields
  - Fail if shaping removes GUI-critical fields
- **Test-driven**: Minimal validation test, no refactoring

### P2: Cleanups / Documentation

**E.5) Document Skip Rationale**
- **File**: `tests/contract_crawler/golden_comparison.py`
- **Action**: Add inline comments explaining why each skipped field is skipped and whether it's GUI-critical
- **Example**: `"steps",  # GUI-CRITICAL: Skip value comparison (recipe world order varies), but schema validated separately`

**E.6) Enhance Coverage Report**
- **File**: `tests/contract_crawler/coverage_report.json` (already exists)
- **Action**: Add `gui_critical_field_coverage` metric showing which GUI-critical fields are validated

---

## Summary

### Current State
- ✅ Baseline isolation is properly enforced (runtime assertions at lines 50-63 in `worktree_runner.py`)
- ✅ Schema preservation tests catch key/type drift
- ⚠️ Value comparison skips GUI-critical fields (`steps`, `structure`, `status` in `DATA_DEPENDENT_FIELDS`)
- ⚠️ Shaping correctness not fully validated (shaping failures may be hidden if field is skipped)

### Method Coverage (Verified)
- **Total RPC methods**: 116
- **Auto-crawler successful**: 26
- **Recipe-covered**: 85
- **Exempt**: 5 (`cancel_job`, `get_job_status`, `get_job_logs`, `compile_fixture_volume`, `shutdown`)
- **GUI-used methods**: 70
- **GUI-covered**: 66
- **GUI-exempt**: 4

### Risk Assessment
- **Baseline Purity**: ✅ LOW RISK (properly enforced with hard assertions)
- **Comparator Loosening**: ⚠️ MEDIUM-HIGH RISK (GUI-critical fields `steps`, `structure`, `status` are skipped)
- **Compat Shaping**: ⚠️ MEDIUM RISK (I/O in `create_demo_project` shaper, shaping failures may be hidden)
- **GUI Field Coverage**: ⚠️ MEDIUM RISK (gaps between contract and GUI needs documented in manifest)

### Recommendation
**System is functional but needs hardening for GUI safety**. Implement P0 items (E.1, E.2) before relying on contract tests as the sole gate for GUI compatibility. These are minimal, test-driven additions that validate GUI-critical fields without refactoring existing skip mechanisms.

---

## Appendix: File References and Evidence

### Key Files
- `tests/fixtures/golden_contracts/generate_golden.py` - Golden generation orchestrator
- `tests/fixtures/golden_contracts/worktree_runner.py` - Baseline runner with isolation assertions (lines 32-66)
- `tests/contract_crawler/golden_comparison.py` - Comparison logic with skip mechanisms
- `tests/contract_crawler/normalization.py` - Normalization utilities
- `tests/contract_crawler/test_golden_contracts.py` - Contract test suite
- `tests/contract_crawler/test_schema_preservation.py` - Schema preservation tests
- `tests/contract_crawler/test_coverage.py` - Coverage enforcement (EXEMPT_METHODS at lines 14-23)
- `tests/contract_crawler/introspection.py` - Method enumeration (`get_all_rpc_methods()`)
- `src/qmatsuite/daemon/compat.py` - Compat shaping layer
- `gui/src/hooks/useQMSClient.ts` - GUI RPC client
- `gui/src/components/panels/StepDetailPanel.tsx` - GUI step detail panel (high field usage)
- `gui_required_fields_manifest.json` - GUI field usage manifest (this audit)

### Skip Mechanism Definitions (Exact Locations)
- `DATA_DEPENDENT_FIELDS`: `tests/contract_crawler/golden_comparison.py:79-123` (44 fields, includes `steps`, `structure`, `status`)
- `VARIABLE_LENGTH_LISTS`: `tests/contract_crawler/golden_comparison.py:61-75` (14 fields, does NOT include `steps`)
- `DATA_DEPENDENT_SUBTREES`: `tests/contract_crawler/test_schema_preservation.py:66-77` (9 fields, includes `steps`)
- `ENVIRONMENT_DEPENDENT_DICTS`: `tests/contract_crawler/test_schema_preservation.py:57-63` (5 fields)

### Commands to Reproduce Findings

**Method Count**:
```bash
source .venv/bin/activate
python3 -c "from tests.contract_crawler.introspection import get_all_rpc_methods; methods = get_all_rpc_methods(); print(f'Total: {len(methods)}')"
```

**GUI RPC Calls**:
```bash
grep -r "\.request\(|call\(|invoke\(" gui/src
```

**GUI Field Access**:
```bash
grep -r "response\.data\." gui/src
```

**Skip Lists**:
```bash
grep -A 50 "DATA_DEPENDENT_FIELDS = {" tests/contract_crawler/golden_comparison.py
grep -A 20 "VARIABLE_LENGTH_LISTS = {" tests/contract_crawler/golden_comparison.py
grep -A 15 "DATA_DEPENDENT_SUBTREES = {" tests/contract_crawler/test_schema_preservation.py
```

**Baseline Isolation Assertions**:
```bash
sed -n '50,63p' tests/fixtures/golden_contracts/worktree_runner.py
```

