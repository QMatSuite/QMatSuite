# QC Demos and Text Viewer Parity Plan

**Date**: 2026-01-XX  
**Status**: Planning Document  
**Scope**: Add QC (ORCA/PySCF) demos + implement text viewer parity with QE

---

## Table of Contents

1. [Repo Baseline (Evidence Map)](#1-repo-baseline-evidence-map)
2. [ORCA Documentation Findings](#2-orca-documentation-findings)
3. [Proposed QC Demo Set (MVP)](#3-proposed-qc-demo-set-mvp)
4. [Text Viewer Parity Plan (QE + QC)](#4-text-viewer-parity-plan-qe--qc)
5. [Implementation Roadmap](#5-implementation-roadmap)
6. [Open Questions](#6-open-questions)

---

## 1. Repo Baseline (Evidence Map)

### A) Existing Demos (QE/Wannier/PySCF)

#### **Quantum ESPRESSO (QE) Demos**

**Location**: `resources/demo_projects/`

**Demo Files**:
- `si_bands_demo.yml` - Silicon band structure calculation
- `si_dos_demo.yml` - Silicon DOS calculation
- `00_Si_scf.yml`, `01_H2.yml`, `02_H2O.yml`, etc. - Tutorial datasets

**Initialization**:
- Demos are YAML snapshot files created via `tools/generate_demo_snapshots.py`
- Uses `export_project_to_snapshot()` to export existing project structures
- Source: Test projects in `tests/data/project_examples/`

**Execution**:
- Via CLI: `qv run <demo_id>` or `qv create-demo-project --demo-id <demo_id>`
- Via API: `QVService.create_demo_project(target_dir, demo_id=<demo_id>)`
- Via GUI: Demo gallery panel (`gui/src/components/panels/DemoGalleryPanel.tsx`)

**Artifacts**:
- QE outputs stored in `calc/raw/outdir/` (filesystem contract)
- Primary output: `<step_type>.out` (e.g., `scf.out`, `bands.out`)
- Input files: `<step_type>.in` (e.g., `scf.in`)
- Additional artifacts: `.dat`, `.gnu`, `.rap` files for bands/DOS

**UI Text Display**:
- Uses `list_step_artifacts()` API endpoint (`src/quantumvitas/api.py:3595`)
- Pattern matching: `{step_type}.out` or `{step_type}-{n}.out` (numbered versions)
- Default candidate selection via `get_default_artifact()` in `src/quantumvitas/calculation/step_artifacts.py`
- UI component: `StepOutputTextViewer.tsx` displays artifact content via `read_step_artifact_text` RPC call

**Text Resolution Rule**:
- For QE steps, looks for `{step_type}.out` in `calc/raw/`
- Falls back to numbered versions (`{step_type}-1.out`, etc.)
- Uses `CalculationFileNaming.output_extension(step_type)` to determine expected extension

#### **Wannier90 Demos**

**Location**: `resources/demo_projects/`

**Demo Files**:
- `diamond_wannier90_demo.yml`
- `copper_wannier90_demo.yml`
- `silicon_wannier90_demo.yml`

**Initialization**:
- Generated via `tools/generate_wannier90_demos.py`
- Source: Wannier90 examples in `.qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/examples/`

**Execution**:
- Same as QE demos (CLI/API/GUI)
- Runs in-place under `calc/raw/` (filesystem contract)

**Artifacts**:
- Wannier90 outputs in `calc/raw/` (in-place execution)
- Primary artifacts:
  - `w90_preproc`: `<seedname>.nnkp`
  - `pw2wannier90`: `<seedname>.amn`, `<seedname>.mmn`, `<seedname>.eig`
  - `w90_run`: `<seedname>.wout` (main output for GUI)

**UI Text Display**:
- Uses step-specific artifact rules in `src/quantumvitas/calculation/step_artifacts.py`
- `_w90_run_artifacts()` returns `{seedname}.wout` as primary artifact
- Default candidate: `.wout` file (preferred over `.out` if both exist)

#### **PySCF Demos**

**Location**: `resources/demo_projects/`

**Demo Files**:
- `water_pyscf_scf.yml` - Water molecule RHF single point

**Initialization**:
- Generated via `tools/generate_pyscf_demo.py`
- Creates snapshot with molecular structure and SCF parameters

**Execution**:
- Via subprocess: `python -m quantumvitas.engines.pyscf.runner <job.json>`
- Job file contains step parameters, structure, and step_type
- Results written to `results.json` in working directory

**Artifacts**:
- **Text output**: `pyscf.log` (PySCF stdout/stderr redirected to file)
  - Location: `calc/raw/pyscf.log` (for standalone steps)
  - Location: `calc/raw/qc_chains/scf_<suffix>/pyscf.log` (for chain execution)
- **Structured output**: `results.json` (parsed calculation results)
- **Input script**: `input.py` (reproducible input script, if written)

**Text Resolution** (Current State):
- **No explicit artifact rule** in `step_artifacts.py` for PySCF steps
- Falls back to pattern matching: `{step_type}.out` (e.g., `pyscf_scf.out`)
- **Issue**: PySCF writes to `pyscf.log`, not `pyscf_scf.out`
- **Proposed fix**: Add `_pyscf_artifacts()` rule that looks for `pyscf.log` first, then falls back to `results.json` (pretty-printed)

**Text Display Fallback**:
- If no log file exists, show pretty-printed `results.json` content
- JSON contains: `energy`, `converged`, `n_electrons`, `n_atoms`, `execution_time`, etc.

### B) ORCA Engine Integration

#### **Adapter Code Location**

- **Engine**: `src/quantumvitas/engine/orca_engine.py`
- **Input Compiler**: `src/quantumvitas/engines/orca/input_compiler.py`
- **Property Parser**: `src/quantumvitas/engines/orca/property_parser.py`
- **Chain Infrastructure**: `src/quantumvitas/engine/qc_engine_base.py`
- **Token Registry**: `src/quantumvitas/workflow/registry.py`

#### **Step Materialization**

**Step Types** (from `workflow/registry.py`):
- `orca_scf` (public: `scf`, token: `s`)
- `orca_hf` (public: `hf`, token: `h`)
- `orca_td` (public: `td`, token: `t`)
- `orca_mp2` (public: `mp2`, token: `m2`) - Future
- `orca_freq` (public: `freq`, token: `f`) - Future
- `orca_nmr` (public: `nmr`, token: `n`) - Future

**Chain Model**:
- ORCA uses **strong-chain** model: one ORCA job = one complete chain
- Chains are SCF-rooted (every chain starts with `scf` or `hf`)
- Steps are fused into a single ORCA input file (e.g., SCF+TD in one `.inp`)

#### **Chain/Subchain Naming and Output Locations**

**Chain Namespace Folder**:
- Format: `calc/raw/qc_chains/scf_<suffix>/`
- Suffix: Last 6-10 characters of SCF root step's ULID
- Default: 6 characters (e.g., `scf_KR5DQ9`)
- On collision: Extend to 7, 8, 9, or 10 characters
- Function: `get_chain_namespace_folder(scf_root_ulid)` in `workflow/registry.py`

**Subchain Basenames**:
- Generated from stable token mapping: `generate_subchain_basename(public_types)`
- Examples:
  - `["scf"]` → `"s"`
  - `["scf", "td"]` → `"s_t"`
  - `["scf", "mp2"]` → `"s_m2"`
  - `["scf", "mp2", "nmr"]` → `"s_m2_n"`

**Expected Filenames in Chain Folder**:
- **Input**: `<basename>.inp` (e.g., `s.inp`, `s_t.inp`)
- **Output**: `<basename>.out` (e.g., `s.out`, `s_t.out`)
- **Properties**: `<basename>.property.txt` (e.g., `s.property.txt`, `s_t.property.txt`)
- **Wavefunction**: `scf.gbw` (canonical, hard-coded name, no prefix)

**Example Directory Structure**:
```
calc_01/raw/qc_chains/
  scf_KR5DQ9/          # Chain namespace folder
    scf.gbw            # Canonical wavefunction (from SCF subchain)
    s.inp               # SCF-only subchain input
    s.out               # SCF-only subchain output
    s.property.txt     # SCF-only subchain properties
    s_t.inp             # SCF+TD subchain input
    s_t.out             # SCF+TD subchain output
    s_t.property.txt   # SCF+TD subchain properties
```

#### **Rule for "Latest Output for Step"**

**Deterministic Mapping**:
1. **Find the chain** containing the step (via `find_chain_for_step()` in `qc_engine_base.py`)
2. **Extract subchain** from SCF root to target step (inclusive)
3. **Generate subchain basename** using `generate_subchain_basename()` with public types
4. **Resolve namespace folder** using `get_chain_namespace_folder()` from SCF root ULID
5. **Construct output path**: `calc/raw/qc_chains/{namespace}/{basename}.out`

**Example**:
- Step: TD step with ULID `01ABC...`
- SCF root ULID: `01XYZ...KR5DQ9`
- Subchain: `[scf, td]` → basename: `s_t`
- Output file: `calc/raw/qc_chains/scf_KR5DQ9/s_t.out`

**Multiple Steps Pointing to Same Output**:
- If multiple steps (e.g., SCF and TD) are in the same chain, they both point to the same `.out` file
- This is **intentional**: the chain output contains results for all steps in the chain
- UI should show the same text output for all steps in the chain (may repeat, but deterministic)

**Implementation Location**:
- Chain detection: `src/quantumvitas/engine/qc_engine_base.py::find_chain_for_step()`
- Subchain extraction: `src/quantumvitas/engine/qc_engine_base.py::QCChain` (partial chain logic)
- Basename generation: `src/quantumvitas/workflow/registry.py::generate_subchain_basename()`
- Namespace resolution: `src/quantumvitas/workflow/registry.py::get_chain_namespace_folder()`

### C) PySCF Integration Overview

**Engine**: `src/quantumvitas/engine/pyscf_engine.py`

**Execution Model**:
- **Standalone steps**: Subprocess execution via `quantumvitas.engines.pyscf.runner`
- **Chain execution**: In-memory session via `quantumvitas.engines.pyscf.chain_execution`
- **Weak-chain internally**: Steps execute sequentially in one Python session
- **Shared chain semantics**: Uses same namespace folders and basenames as ORCA

**Text Output Sources**:
- **Primary**: `pyscf.log` (stdout/stderr redirected to file)
  - Location: `calc/raw/pyscf.log` (standalone)
  - Location: `calc/raw/qc_chains/scf_<suffix>/pyscf.log` (chain)
- **Fallback**: `results.json` (pretty-printed JSON)

**Current Issue**:
- No artifact rule in `step_artifacts.py` for PySCF steps
- Pattern matching looks for `pyscf_scf.out`, but PySCF writes `pyscf.log`
- **Fix needed**: Add `_pyscf_artifacts()` rule

---

## 2. ORCA Documentation Findings

### A) Relevant Tutorial Sections

**ORCA Manual Index**:
- URL: https://www.faccts.de/docs/orca/6.0/manual/index.html
- Comprehensive reference for ORCA input syntax, keywords, and features

**ORCA Tutorials**:
- URL: https://www.faccts.de/docs/orca/6.0/tutorials/
- Practical examples and step-by-step guides

**ORCA Input Library**:
- URL: https://sites.google.com/site/orcainputlibrary/home
- Collection of example input files for various calculation types

### B) Selected Demo Cases

#### **1. ORCA DFT SCF Single Point (Water Molecule)** ✅ CHOSEN

**Tutorial Reference**:
- **Title**: "Hello Water! Your First ORCA Calculation"
- **URL**: https://orca-manual.mpi-muelheim.mpg.de/contents/quickstartguide/hellowater.html
- **Section**: Quick Start Guide → Hello Water

**Molecule (XYZ)**:
```
3

O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200
```

**Method/Basis/Keywords**:
- Method: B3LYP (DFT)
- Basis: def2-SVP
- Keywords: `! B3LYP def2-SVP TightSCF`

**Expected Key Output Files**:
- `s.inp` (SCF input)
- `s.out` (SCF output)
- `s.property.txt` (properties)
- `scf.gbw` (wavefunction)

**Runtime**: ~10-30 seconds on laptop

**QMatSuite Workflow**:
- **Template**: Single-step SCF calculation
- **Steps**: `[scf]` (public type)
- **Chain**: `[scf]` → basename: `s`
- **Namespace**: `scf_<suffix>` (from SCF step ULID)

#### **2. ORCA SCF + TDDFT (Formaldehyde Molecule)** ✅ CHOSEN

**Tutorial Reference**:
- **Title**: "TDDFT Calculations"
- **URL**: https://www.faccts.de/docs/orca/6.0/tutorials/tddft.html (inferred from ORCA tutorials structure)
- **Section**: Excited States → TDDFT

**Molecule (XYZ)**:
```
4

C   0.000000   0.000000   0.000000
O   1.200000   0.000000   0.000000
H  -0.600000   0.923800   0.000000
H  -0.600000  -0.923800   0.000000
```

**Method/Basis/Keywords**:
- Method: B3LYP (DFT)
- Basis: def2-SVP
- Keywords: `! B3LYP def2-SVP TightSCF`
- TDDFT block:
  ```
  %tddft
    NRoots 5
    TDA true
  end
  ```

**Expected Key Output Files**:
- `s_t.inp` (SCF+TD input)
- `s_t.out` (SCF+TD output)
- `s_t.property.txt` (properties)
- `scf.gbw` (wavefunction, reused via MORead)

**Runtime**: ~1-3 minutes on laptop

**QMatSuite Workflow**:
- **Template**: Two-step chain (SCF → TD)
- **Steps**: `[scf, td]` (public types)
- **Chain**: `[scf, td]` → basename: `s_t`
- **Namespace**: `scf_<suffix>` (from SCF step ULID)

#### **3. ORCA SCF + Frequency (Methane Molecule)** ✅ CHOSEN

**Tutorial Reference**:
- **Title**: "Frequency Calculations"
- **URL**: https://www.faccts.de/docs/orca/6.0/tutorials/frequencies.html (inferred from ORCA tutorials structure)
- **Section**: Vibrational Analysis → Frequency Calculations

**Molecule (XYZ)**:
```
5

C   0.000000   0.000000   0.000000
H   0.629118   0.629118   0.629118
H  -0.629118  -0.629118   0.629118
H  -0.629118   0.629118  -0.629118
H   0.629118  -0.629118  -0.629118
```

**Method/Basis/Keywords**:
- Method: B3LYP (DFT)
- Basis: def2-TZVP
- Keywords: `! B3LYP def2-TZVP TightSCF Freq`

**Expected Key Output Files**:
- `s_f.inp` (SCF+Freq input)
- `s_f.out` (SCF+Freq output)
- `s_f.property.txt` (properties)
- `s_f.hess` (Hessian matrix)
- `scf.gbw` (wavefunction)

**Runtime**: ~2-5 minutes on laptop

**QMatSuite Workflow**:
- **Template**: Two-step chain (SCF → Freq)
- **Steps**: `[scf, freq]` (public types)
- **Chain**: `[scf, freq]` → basename: `s_f`
- **Namespace**: `scf_<suffix>` (from SCF step ULID)

#### **4. ORCA SCF + MP2 (Optional - Not Chosen for MVP)**

**Rationale**: MP2 is less commonly used in tutorials and may require more complex setup. Defer to Phase 1+.

---

## 3. Proposed QC Demo Set (MVP)

### A) Directory Layout Proposal

**Location**: `resources/demo_projects/`

**Structure**:
```
resources/demo_projects/
  water_orca_scf.yml              # Demo 1: Water SCF
  formaldehyde_orca_tddft.yml     # Demo 2: Formaldehyde SCF+TD
  methane_orca_freq.yml            # Demo 3: Methane SCF+Freq
```

**Naming Convention**:
- Format: `{molecule}_{engine}_{workflow}.yml`
- Examples: `water_orca_scf.yml`, `formaldehyde_orca_tddft.yml`

### B) Files in Each Demo

Each demo YAML file contains:

1. **Project metadata**:
   - `meta.id`: ULID
   - `meta.name`: Human-readable name (e.g., "Water ORCA SCF")
   - `meta.slug`: URL-friendly slug (e.g., "water-orca-scf")

2. **Structure**:
   - `structures[0].data.atoms`: XYZ coordinates
   - `structures[0].data.charge`: Molecular charge
   - `structures[0].data.spin`: Spin multiplicity

3. **Calculation**:
   - `calculations[0].steps`: List of step specs
   - Each step: `step_type` (public type, e.g., `scf`, `td`), `parameters` (method, basis, keywords)

4. **Demo metadata** (top-level `meta`):
   - `title`: Display title
   - `subtitle`: Short description
   - `tags`: `["orca", "molecular", "scf", "water", "tutorial"]`
   - `recommended_analysis`: `"energy"` or `"excited_states"` or `"frequencies"`
   - `difficulty`: `"beginner"`

### C) QMatSuite Commands in README

**Conceptual commands** (for README.md in each demo):

```bash
# Create project from demo
qv create-demo-project --demo-id water_orca_scf

# Or via GUI: Select "Water ORCA SCF" from demo gallery

# Run calculation
qv run calc water-orca-scf

# Or via GUI: Click "Run" on the calculation

# View results
qv show calc water-orca-scf

# Or via GUI: Open calculation → View step output
```

**Note**: These commands are conceptual. Actual CLI may differ. Reference existing demo commands for exact syntax.

---

## 4. Text Viewer Parity Plan (QE + QC)

### A) Text Artifact Resolver (Conceptual)

**Location**: `src/quantumvitas/calculation/step_artifacts.py`

**Function**: `resolve_text_artifact_for_step(step_type, step_id, calculation_dir, project_root) -> Optional[Path]`

**Purpose**: Return the path to the most relevant text file for a step, relative to `calc/raw/`.

**Algorithm**:
1. Determine engine family (QE vs QC)
2. If QC: Resolve chain namespace and subchain basename
3. If QE: Use existing pattern matching
4. Return path relative to `calc/raw/`

### B) ORCA Mapping Rule (Deterministic)

**Implementation**:
1. **Resolve step** to get step ULID and public type
2. **Find chain** containing step: `find_chain_for_step(step_id, chains)`
3. **Extract subchain** from SCF root to target step: `chain.get_subchain_to_step(step_id)`
4. **Generate basename**: `generate_subchain_basename([scf, ..., target])`
5. **Resolve namespace**: `get_chain_namespace_folder(scf_root_ulid)`
6. **Construct path**: `qc_chains/{namespace}/{basename}.out`

**Example**:
- Step: TD step (`01ABC...`)
- Chain: `[SCF (01XYZ...KR5DQ9), TD (01ABC...)]`
- Subchain: `[SCF, TD]` → basename: `s_t`
- Path: `qc_chains/scf_KR5DQ9/s_t.out`

**Edge Cases**:
- **Step not in chain**: Return `None` (should not happen in normal execution)
- **Multiple chains with same step**: Use first chain found (deterministic)
- **File missing**: Return `None` (UI shows "No output files" message)

**Code Location**:
- Add function: `_orca_artifacts(step_type, params, raw_dir, step_id, project_root) -> List[str]`
- Integrate with `get_step_artifacts()` in `step_artifacts.py`
- Requires access to calculation model to resolve chains (may need API refactor)

### C) PySCF Mapping Rule + Fallback

**Primary**: `pyscf.log`
- Location: `calc/raw/pyscf.log` (standalone) or `calc/raw/qc_chains/scf_<suffix>/pyscf.log` (chain)

**Fallback**: `results.json` (pretty-printed)
- Location: `calc/raw/results.json` (standalone) or `calc/raw/qc_chains/scf_<suffix>/results.json` (chain)
- Format: Pretty-printed JSON with indentation

**Implementation**:
- Add function: `_pyscf_artifacts(step_type, params, raw_dir) -> List[str]`
- Check for `pyscf.log` first
- If missing, check for `results.json`
- Return list: `["pyscf.log", "results.json"]` (priority order)

**JSON Pretty-Print**:
- If `results.json` is selected, format as:
  ```json
  {
    "success": true,
    "energy": -76.023456,
    "energy_unit": "Hartree",
    "converged": true,
    "n_electrons": 10,
    "n_atoms": 3,
    "execution_time": 1.23
  }
  ```

### D) Error Behavior

**Missing File**:
- Return empty artifact list from `list_step_artifacts()`
- UI shows: "No output files found for this step yet."

**File Read Error**:
- `read_step_artifact_text()` returns error response
- UI shows: "Failed to load file: {error_message}"

**Large Files**:
- Existing truncation logic in `StepOutputTextViewer.tsx` (line 100-120)
- Truncate to first 1MB, show "(truncated)" message

---

## 5. Implementation Roadmap

### Phase 0: Add Demos Only + Smoke Tests

**Goal**: Create demo YAML files and verify they can be materialized.

**Tasks**:
- [ ] Create `tools/generate_orca_demos.py` script
- [ ] Generate 3 demo YAML files:
  - [ ] `water_orca_scf.yml`
  - [ ] `formaldehyde_orca_tddft.yml`
  - [ ] `methane_orca_freq.yml`
- [ ] Add demo metadata (title, subtitle, tags, difficulty)
- [ ] Test materialization: `qv create-demo-project --demo-id water_orca_scf`
- [ ] Verify project structure is correct (steps, structures, calculations)

**Tests to Add**:
- [ ] `tests/unit/test_orca_demo_generation.py`: Verify demo YAML structure
- [ ] `tests/integration/test_orca_demo_materialization.py`: Test project creation from demo

**Commands to Run**:
```bash
# Generate demos
python tools/generate_orca_demos.py

# Test materialization
qv create-demo-project /tmp/test-water --demo-id water_orca_scf
ls /tmp/test-water/calculations/*/steps/

# Run focused tests
pytest tests/unit/test_orca_demo_generation.py -v
pytest tests/integration/test_orca_demo_materialization.py -v
```

**Acceptance Criteria**:
- [ ] All 3 demo YAML files exist in `resources/demo_projects/`
- [ ] Demos can be materialized via CLI/GUI
- [ ] Materialized projects have correct structure (steps reference structures, calculations reference steps)
- [ ] Unit tests pass
- [ ] Integration tests pass

### Phase 1: Backend Text Artifact Resolver (No UI Yet)

**Goal**: Implement `resolve_text_artifact_for_step()` and integrate with `list_step_artifacts()`.

**Tasks**:
- [ ] Add `_orca_artifacts()` function to `step_artifacts.py`
  - [ ] Resolve step to get ULID and public type
  - [ ] Find chain containing step (requires calculation model access)
  - [ ] Generate subchain basename
  - [ ] Resolve namespace folder
  - [ ] Return `qc_chains/{namespace}/{basename}.out`
- [ ] Add `_pyscf_artifacts()` function to `step_artifacts.py`
  - [ ] Check for `pyscf.log` in `raw_dir` or `raw_dir/qc_chains/scf_<suffix>/`
  - [ ] Fallback to `results.json`
  - [ ] Return list in priority order
- [ ] Update `STEP_ARTIFACT_RULES` registry:
  - [ ] Add `orca_scf`, `orca_hf`, `orca_td` → `_orca_artifacts`
  - [ ] Add `pyscf_scf`, `pyscf_rhf`, `pyscf_uhf`, `pyscf_dft` → `_pyscf_artifacts`
- [ ] Refactor `list_step_artifacts()` to support chain resolution:
  - [ ] Load calculation model to access chains
  - [ ] Pass step_id to artifact rule functions
  - [ ] Handle QC chain paths (nested under `qc_chains/`)

**Tests to Add**:
- [ ] `tests/unit/test_step_artifacts_orca.py`:
  - [ ] Test `_orca_artifacts()` with mock chain
  - [ ] Test basename generation (s, s_t, s_f)
  - [ ] Test namespace resolution
- [ ] `tests/unit/test_step_artifacts_pyscf.py`:
  - [ ] Test `_pyscf_artifacts()` finds `pyscf.log`
  - [ ] Test fallback to `results.json`
- [ ] `tests/integration/test_api_step_artifacts_qc.py`:
  - [ ] Test `list_step_artifacts()` for ORCA step returns correct path
  - [ ] Test `list_step_artifacts()` for PySCF step returns correct path
  - [ ] Test missing file handling

**Commands to Run**:
```bash
# Run unit tests
pytest tests/unit/test_step_artifacts_orca.py -v
pytest tests/unit/test_step_artifacts_pyscf.py -v

# Run integration tests
pytest tests/integration/test_api_step_artifacts_qc.py -v

# Run existing artifact tests (regression)
pytest tests/unit/test_api_step_artifacts.py -v
```

**Acceptance Criteria**:
- [ ] `list_step_artifacts()` returns correct path for ORCA steps (e.g., `qc_chains/scf_KR5DQ9/s_t.out`)
- [ ] `list_step_artifacts()` returns correct path for PySCF steps (e.g., `pyscf.log`)
- [ ] Missing files return empty list (no errors)
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Existing QE/Wannier artifact tests still pass (regression)

### Phase 2: UI Wire-up for Text Panel

**Goal**: Connect backend resolver to UI text viewer.

**Tasks**:
- [ ] Verify `StepOutputTextViewer.tsx` already calls `list_step_artifacts()` (✅ confirmed)
- [ ] Test UI with ORCA demo:
  - [ ] Materialize `water_orca_scf` demo
  - [ ] Run calculation (or use pre-run artifacts)
  - [ ] Open step in UI
  - [ ] Verify "Text" panel shows `.out` file content
- [ ] Test UI with PySCF demo:
  - [ ] Materialize `water_pyscf_scf` demo
  - [ ] Run calculation
  - [ ] Open step in UI
  - [ ] Verify "Text" panel shows `pyscf.log` or `results.json`
- [ ] Handle JSON pretty-print in UI:
  - [ ] Detect `results.json` file
  - [ ] Parse JSON and format with indentation
  - [ ] Display in monospace font

**Tests to Add**:
- [ ] `tests/integration/test_ui_text_viewer_orca.py`:
  - [ ] Test UI can fetch ORCA `.out` file via RPC
  - [ ] Test file content is displayed correctly
- [ ] `tests/integration/test_ui_text_viewer_pyscf.py`:
  - [ ] Test UI can fetch PySCF `pyscf.log` via RPC
  - [ ] Test JSON fallback formatting

**Commands to Run**:
```bash
# Run integration tests
pytest tests/integration/test_ui_text_viewer_orca.py -v
pytest tests/integration/test_ui_text_viewer_pyscf.py -v

# Manual UI test (requires GUI running)
# 1. Start GUI: npm run dev (in gui/)
# 2. Create demo project from water_orca_scf
# 3. Run calculation
# 4. Open step → Verify "Text" panel shows output
```

**Acceptance Criteria**:
- [ ] UI "Text" panel displays ORCA `.out` file content for ORCA steps
- [ ] UI "Text" panel displays PySCF `pyscf.log` or `results.json` for PySCF steps
- [ ] JSON files are pretty-printed with indentation
- [ ] Missing files show "No output files" message
- [ ] Large files are truncated with "(truncated)" indicator
- [ ] Integration tests pass

### Phase 3: Optional Polish

**Goal**: Improve UX and add edge case handling.

**Tasks**:
- [ ] Add file size indicator in artifact selector dropdown
- [ ] Add "Last modified" timestamp in artifact metadata
- [ ] Add syntax highlighting for ORCA output (optional)
- [ ] Add search/filter in text viewer (optional)
- [ ] Improve error messages for missing chain resolution

**Tests to Add**:
- [ ] Test file size display
- [ ] Test timestamp display
- [ ] Test error message clarity

**Commands to Run**:
```bash
# Run focused tests
pytest tests/integration/test_ui_text_viewer_polish.py -v
```

**Acceptance Criteria**:
- [ ] File size and timestamp are displayed in UI
- [ ] Error messages are clear and actionable
- [ ] All tests pass

---

## 6. Open Questions

### A) Chain Resolution in `list_step_artifacts()`

**Question**: How to access calculation chains from `list_step_artifacts()`?

**Current State**:
- `list_step_artifacts()` receives `calculation_selector` and `step_selector`
- It resolves calculation and step, but does not load calculation model with chains

**Options**:
1. **Load calculation model** in `list_step_artifacts()`:
   - Use `load_calculation()` to get workflow model
   - Extract chains from workflow model
   - Pass chains to artifact rule functions

2. **Cache chains** in calculation metadata:
   - Store chain information in `calculation.yaml` or separate metadata file
   - Read cached chains in `list_step_artifacts()`

3. **Lazy chain resolution**:
   - Only resolve chains when needed (for QC steps)
   - Cache resolved chains in memory

**Recommendation**: Option 1 (load calculation model). Chains are already computed during execution, so loading the model is acceptable.

**Blocking**: Yes, if we cannot access chains, ORCA artifact resolution will fail.

### B) PySCF Chain Execution Log Location

**Question**: Where exactly does PySCF write `pyscf.log` in chain execution mode?

**Current State**:
- Standalone: `calc/raw/pyscf.log`
- Chain: Unknown (may be `calc/raw/qc_chains/scf_<suffix>/pyscf.log` or `calc/raw/pyscf.log`)

**Investigation Needed**:
- Review `src/quantumvitas/engines/pyscf/chain_execution.py`
- Check `run_chain_session()` to see where log file is written
- Verify with integration test

**Blocking**: No (can be determined during implementation), but should be confirmed before Phase 1.

### C) ORCA Subchain Basename for Single-Step Chains

**Question**: For a single SCF step, is the basename `s` or `scf`?

**Answer**: Basename is `s` (from token mapping: `scf → s`).

**Verification**: `generate_subchain_basename(["scf"])` returns `"s"`.

**Blocking**: No (already implemented and tested).

### D) Multiple Chains with Same Step

**Question**: What if a step appears in multiple chains? Which chain's output should be shown?

**Current Behavior**: `find_chain_for_step()` returns first chain found (deterministic but arbitrary).

**Recommendation**: Use first chain found. If this becomes an issue, add chain priority or user selection.

**Blocking**: No (edge case, can be handled later).

---

## Appendix: Key Files Reference

### Backend
- `src/quantumvitas/api.py:3595` - `list_step_artifacts()` implementation
- `src/quantumvitas/calculation/step_artifacts.py` - Artifact rules registry
- `src/quantumvitas/engine/qc_engine_base.py` - Chain detection and subchain extraction
- `src/quantumvitas/workflow/registry.py` - Token mapping and basename generation
- `src/quantumvitas/engine/orca_engine.py` - ORCA engine execution
- `src/quantumvitas/engines/pyscf/runner.py` - PySCF standalone execution
- `src/quantumvitas/engines/pyscf/chain_execution.py` - PySCF chain execution

### Frontend
- `gui/src/components/panels/StepOutputTextViewer.tsx` - Text viewer component
- `gui/src/components/panels/DemoGalleryPanel.tsx` - Demo gallery

### Documentation
- `docs/architecture/ORCA_INTEGRATION_SPEC.md` - ORCA filesystem contract
- `docs/plans/orca_execution_mvp_plan.md` - ORCA implementation history
- `docs/DEMO_GENERATION.md` - Demo generation guide

---

**End of Plan Document**

