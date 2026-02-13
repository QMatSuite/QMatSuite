# Execution Modes Inventory

**Date:** 2025-01-XX  
**Purpose:** Complete map of all execution modes in QMatSuite, with focus on pseudopotential SSOT and override handling per mode.

---

## Executive Summary

QMatSuite supports **6 distinct execution modes**, each with different requirements for project context, YAML SSOT, and pseudopotential handling:

1. **Standalone Mode** (`--standalone`): Runs QE input without project context. Performs full roundtrip: import .in → step.yaml → generate .in → run. Uses `workdir/pseudo` for pseudos.

2. **Project SSOT Run (Normal)**: Standard project execution via `qv run step` or `QVService.run_step()`. Requires `calculation.yaml` and `step.yaml`. Generates .in from YAML SSOT. Uses `project_root/pseudo`.

3. **Project Calculation Run**: Runs entire calculation via `qv run calculation` or `QVService.run_calculation()`. Same as Project SSOT Run but for all steps.

4. **Compat Input Playback**: Tutorial test mode that executes existing .in files with minimal patching. Bypasses YAML SSOT. Uses `project_root/pseudo`.

5. **Daemon/JobManager Run**: Same as Project SSOT Run but executed via daemon/JobManager for GUI/background execution.

6. **CLI Run Structure**: Generates and runs .in from structure + overrides. No calculation.yaml required. Uses `workdir/pseudo` or `project_root/pseudo` if project exists.

**Key Finding:** Pseudopotential SSOT varies by mode:
- **Project modes:** Use `calculation.yaml` → `species_map` (preferred) or `step.yaml` → `species_overrides` (fallback)
- **Standalone mode:** Parses from .in → writes to temporary step.yaml → uses step.yaml `species_overrides`
- **Compat mode:** Parses from existing .in directly (bypasses YAML)

**Override Support:** All modes support parameter/card overrides, but storage location and precedence differ.

---

## Execution Modes List

| Mode | Requires calculation.yaml? | Uses step.yaml as SSOT? | Executes existing .in directly? | Pseudo SSOT source | Pseudo staging destination | Supports species_overrides? | Supports card_overrides? | Supports parameter overrides? | Notes / risks |
|------|---------------------------|------------------------|--------------------------------|-------------------|---------------------------|----------------------------|-------------------------|------------------------------|---------------|
| **Standalone** | ❌ No | ✅ Yes (temporary) | ❌ No (roundtrip) | Parses from .in → step.yaml `species_overrides` | `workdir/pseudo` | ✅ Yes (in step.yaml) | ✅ Yes | ✅ Yes | Creates temp step.yaml, then materializes |
| **Project SSOT Run** | ✅ Yes | ✅ Yes | ❌ No | `calculation.yaml` → `species_map` (preferred) or `step.yaml` → `species_overrides` (fallback) | `project_root/pseudo` | ✅ Yes (fallback) | ✅ Yes | ✅ Yes | Normal production path |
| **Project Calculation Run** | ✅ Yes | ✅ Yes | ❌ No | Same as Project SSOT Run | `project_root/pseudo` | ✅ Yes (fallback) | ✅ Yes | ✅ Yes | Runs all steps in calculation |
| **Compat Input Playback** | ✅ Yes (for input path) | ❌ No | ✅ Yes (minimal patch) | Parses from existing .in `ATOMIC_SPECIES` | `project_root/pseudo` | ❌ No (bypasses YAML) | ❌ No (bypasses YAML) | ❌ No (bypasses YAML) | Tutorial test mode, bypasses YAML SSOT |
| **Daemon/JobManager Run** | ✅ Yes | ✅ Yes | ❌ No | Same as Project SSOT Run | `project_root/pseudo` | ✅ Yes (fallback) | ✅ Yes | ✅ Yes | Same as Project SSOT Run, via daemon |
| **CLI Run Structure** | ❌ No | ❌ No | ❌ No | Overrides passed at runtime | `workdir/pseudo` or `project_root/pseudo` | ✅ Yes (runtime) | ✅ Yes (runtime) | ✅ Yes (runtime) | Generates from structure + overrides |

---

## Mode-by-mode Details

### Mode 1: Standalone Execution

#### 1.A) Name & Purpose

**Name:** Standalone Mode  
**Purpose:** Run QE input files without project context. Pure QE helper that operates on raw input files.

**Entry Point:** `qv run step --standalone --input <file>`

#### 1.B) Call Chain

**Entry:** `src/quantumvitas/cli/main.py::_run_standalone_step()` (lines 1636-1758)

**Call Chain:**
1. `cli/main.py::_run_standalone_step()` (line 1636)
   - Validates input file exists
   - Creates workdir (defaults to cwd)
2. `calculation/importers.py::build_step_spec_from_qe_input()` (line 1696)
   - Parses .in file
   - Extracts structure, parameters, cards, **species_overrides** from `ATOMIC_SPECIES`
   - Writes temporary `step.yaml` to `.qv_standalone_import/`
3. `calculation/structure_steps.py::materialize_step_spec()` (line 1721)
   - Loads step.yaml
   - Generates .in from step.yaml
   - Calls `ensure_qe_pseudos()` with `species_map=None` (uses step.yaml `species_overrides`)
4. `calculation/standalone.py::run_standalone_step()` (line 44) - **NOT USED** (legacy)
   - Actually, standalone CLI uses `Step.run()` directly (line 1745)
5. `calculation/step.py::Step.run()` (line 1745)
   - Executes generated .in via engine

**QE Invocation:** `engine.backend.run_step()` (via `Step.run()`)

#### 1.C) Pseudopotential SSOT & Staging

**Pseudo filename mapping source:**
- **Primary:** Parsed from original .in `ATOMIC_SPECIES` card
- **Storage:** Written to temporary `step.yaml` → `species_overrides` field
- **Runtime:** `materialize_step_spec()` reads from `step.yaml` → `species_overrides`
- **Evidence:** 
  - `calculation/importers.py:198-223` - Extracts `species_overrides` from ATOMIC_SPECIES
  - `calculation/structure_steps.py:1112` - Passes `species_map=None` to `generate_qe_input_from_spec()`
  - `calculation/structure_steps.py:575` - Falls back to `spec.species_overrides` when `species_map=None`

**Pseudo directory:**
- **Destination:** `workdir/pseudo` (line 1728: `project_root=workdir_path`)
- **Evidence:** `calculation/structure_steps.py:1145` - `project_pseudo_dir = project_root_path / "pseudo"`

**Pseudo staging:**
- **Who calls:** `materialize_step_spec()` → `ensure_qe_pseudos()` (line 1166)
- **Inputs:** 
  - `qe_input_file`: Temporary generated .in
  - `project_pseudo_dir`: `workdir/pseudo`
  - `species_map`: `None` (so falls back to parsing .in)
- **Evidence:** `calculation/structure_steps.py:1166-1170`

**Does NOT use:** `calculation.yaml` → `species_map` (no calculation exists)

#### 1.D) Override Handling

**species_overrides:**
- **Storage:** Temporary `step.yaml` → `species_overrides` field
- **Source:** Extracted from original .in `ATOMIC_SPECIES` card
- **Applied:** During `materialize_step_spec()` → `generate_qe_input_from_spec()` (line 575)
- **Evidence:** `calculation/importers.py:198-223` - Extracts and writes to step.yaml

**card_overrides:**
- **Storage:** Temporary `step.yaml` → `cards` field
- **Source:** Extracted from original .in
- **Applied:** During `generate_qe_input_from_spec()` (line 571)
- **Evidence:** `calculation/importers.py:194-196` - Extracts cards

**parameter_overrides:**
- **Storage:** Temporary `step.yaml` → `parameters` field
- **Source:** Extracted from original .in namelists
- **Applied:** During `generate_qe_input_from_spec()` (line 514)
- **Evidence:** `calculation/importers.py:193-196` - Extracts parameters

**Runtime-managed CONTROL keys:**
- **prefix:** Not set (standalone doesn't use calculation prefix)
- **outdir:** Set to `workdir/outdir` (line 92-96 in `standalone.py`, but not used in CLI path)
- **pseudo_dir:** Set to `workdir/pseudo` (line 1188 in `materialize_step_spec()`)
- **Evidence:** `calculation/structure_steps.py:1188` - `set_pseudo_dir_in_input()`

**Existing input merge/parse:**
- **Yes:** Original .in is parsed to extract structure, parameters, cards, species_overrides
- **Evidence:** `calculation/importers.py:95-266` - Full parsing of .in file

#### 1.E) Output Materialization

**Where .in is written:**
- **Location:** `workdir/<stem>.in` (generated from step.yaml)
- **Original preserved:** `workdir/<stem>.raw.in` (line 78-86 in `standalone.py`, but CLI path uses different flow)
- **Evidence:** `calculation/structure_steps.py:908` - Returns `generated_input` path

**Clean rewrite vs patch:**
- **Clean rewrite:** Full generation from step.yaml (no patching)
- **Evidence:** `calculation/structure_steps.py:1112` - `generate_qe_input_from_spec()` creates new QEInput

**Parsing during run:**
- **No:** Generated .in is executed directly (no parsing during run)

---

### Mode 2: Project SSOT Run (Normal)

#### 2.A) Name & Purpose

**Name:** Project SSOT Run (Normal)  
**Purpose:** Execute a single step within a project using YAML as SSOT.

**Entry Points:**
- CLI: `qv run step --calculation X --step Y`
- API: `QVService.run_step(project_root, calculation_selector, step_selector)`

#### 2.B) Call Chain

**Entry:** `src/quantumvitas/cli/main.py::run_step_command()` (line 1427) or `src/quantumvitas/api.py::QVService.run_step()` (if exists)

**Call Chain:**
1. `cli/main.py::run_step_command()` (line 1427)
   - Resolves project, calculation, step via registry
   - Calls `QVService.run_step()` (line 1604)
2. `api.py::QVService.run_step()` (if exists) or direct to `CalculationRunner`
3. `calculation/runner.py::CalculationRunner.run()` (line 132)
   - Loads calculation: `Calculation.from_yaml(..., materialize_steps=True)` (line 1208)
   - Creates `JobGraph` and `JobExecutor`
4. `execution/executor.py::JobExecutor.execute()` (line 75)
   - Executes jobs from JobGraph
5. `execution/handlers.py::qe_step_handler()` (line 87)
   - Finds step by ULID
   - Calls `step.run()` (line 196)
6. `calculation/step.py::Step.run()` (line ~200)
   - Calls `materialize_step_spec()` if needed
   - Executes via engine

**QE Invocation:** `engine.backend.run_step()` (via `Step.run()`)

#### 2.C) Pseudopotential SSOT & Staging

**Pseudo filename mapping source:**
- **Primary:** `calculation.yaml` → `species_map` (if present)
- **Fallback:** `step.yaml` → `species_overrides` (for backwards compatibility)
- **Evidence:**
  - `calculation/structure_steps.py:1090` - Loads `calc_model.species_map`
  - `calculation/structure_steps.py:1112` - Passes `species_map=calculation_species_map` to `generate_qe_input_from_spec()`
  - `calculation/structure_steps.py:575` - Falls back to `spec.species_overrides` if `species_map=None`
  - `execution/handlers.py:192` - Passes `species_map=calculation.species_map` to `step.run()`

**Pseudo directory:**
- **Destination:** `project_root/pseudo`
- **Evidence:** `calculation/structure_steps.py:1145` - `project_pseudo_dir = project_root_path / "pseudo"`

**Pseudo staging:**
- **Who calls:** `materialize_step_spec()` → `ensure_qe_pseudos()` (line 1166)
- **Inputs:**
  - `qe_input_file`: Temporary generated .in
  - `project_pseudo_dir`: `project_root/pseudo`
  - `species_map`: `calculation.species_map` (calculation-level authority)
- **Evidence:** `calculation/structure_steps.py:1166-1170`

#### 2.D) Override Handling

**species_overrides:**
- **Storage:** `step.yaml` → `species_overrides` field (legacy, fallback only)
- **Precedence:** `calculation.species_map` takes precedence (line 575)
- **Applied:** During `generate_qe_input_from_spec()` (line 575)
- **Evidence:** `calculation/structure_steps.py:573-576`

**card_overrides:**
- **Storage:** `step.yaml` → `cards` field
- **Applied:** During `generate_qe_input_from_spec()` (line 571)
- **Evidence:** `calculation/structure_steps.py:571`

**parameter_overrides:**
- **Storage:** `step.yaml` → `parameters` field
- **Applied:** During `generate_qe_input_from_spec()` (line 514)
- **Evidence:** `calculation/structure_steps.py:514`

**Runtime-managed CONTROL keys:**
- **prefix:** Set from calculation ULID (stable prefix)
- **outdir:** Set to `./outdir` (relative to raw_dir)
- **pseudo_dir:** Set to `project_root/pseudo` (absolute path)
- **Evidence:** `calculation/structure_steps.py:1115-1123`, `1188`

**Existing input merge/parse:**
- **No:** Uses YAML SSOT only (no parsing of existing .in)

#### 2.E) Output Materialization

**Where .in is written:**
- **Location:** `calculation/raw/<step_type>.in` (or `raw/<step_id>.in`)
- **Evidence:** `calculation/structure_steps.py:648` - `output_dir` parameter

**Clean rewrite vs patch:**
- **Clean rewrite:** Full generation from step.yaml (no patching)
- **Evidence:** `calculation/structure_steps.py:1112` - `generate_qe_input_from_spec()` creates new QEInput

**Parsing during run:**
- **No:** Generated .in is executed directly (no parsing during run)

---

### Mode 3: Project Calculation Run

#### 3.A) Name & Purpose

**Name:** Project Calculation Run  
**Purpose:** Execute all steps in a calculation sequentially.

**Entry Points:**
- CLI: `qv run calculation X` (if exists)
- API: `QVService.run_calculation(project_root, calculation_selector)`
- Daemon: `daemon/server.py::_handle_run_calculation()` (line 5358)

#### 3.B) Call Chain

**Entry:** `src/quantumvitas/api.py::QVService.run_calculation()` (line 1151) or `src/quantumvitas/daemon/server.py::_handle_run_calculation()` (line 5358)

**Call Chain:**
1. `api.py::QVService.run_calculation()` (line 1151)
   - Loads calculation: `Calculation.from_yaml(..., materialize_steps=True)` (line 1208)
   - Creates `CalculationRunner` and calls `runner.run()` (line 1195)
2. `calculation/runner.py::CalculationRunner.run()` (line 132)
   - Materializes `JobGraph` from calculation steps
   - Creates `JobExecutor` and executes
3. `execution/executor.py::JobExecutor.execute()` (line 75)
   - Executes all jobs in sequence
4. `execution/handlers.py::qe_step_handler()` (line 87)
   - Executes each step (same as Mode 2)

**QE Invocation:** Same as Mode 2 (per step)

#### 3.C) Pseudopotential SSOT & Staging

**Same as Mode 2** (Project SSOT Run):
- **Primary:** `calculation.yaml` → `species_map`
- **Fallback:** `step.yaml` → `species_overrides`
- **Staging:** `project_root/pseudo`
- **Evidence:** Same as Mode 2

**Additional:** Step0 pseudo preparation (lines 180-228 in `runner.py`):
- Prepares pseudos in `project_root/pseudo` before first step
- Uses `calculation.species_map` exclusively
- **Evidence:** `calculation/runner.py:183-195`

#### 3.D) Override Handling

**Same as Mode 2** (Project SSOT Run)

#### 3.E) Output Materialization

**Same as Mode 2** (Project SSOT Run)

---

### Mode 4: Compat Input Playback

#### 4.A) Name & Purpose

**Name:** Compat Input Playback  
**Purpose:** Tutorial test mode that executes existing .in files with minimal patching (bypasses YAML SSOT).

**Entry Point:** `CalculationRunner.run(compat_input_playback=True)` (line 140)

#### 4.B) Call Chain

**Entry:** `calculation/runner.py::CalculationRunner.run(compat_input_playback=True)` (line 140)

**Call Chain:**
1. `calculation/runner.py::CalculationRunner.run()` (line 140)
   - Sets `compat_input_playback=True` in context (line 556)
2. `execution/executor.py::JobExecutor.execute()` (line 75)
   - Passes context to handlers
3. `execution/handlers.py::qe_step_handler()` (line 87)
   - Checks `compat_input_playback` flag (line 161)
   - Gets existing input path from `calculation.yaml` (line 167)
   - Calls `compat_executor.py::run_qe_step_from_existing_input_compat()` (line 176)
4. `calculation/compat_executor.py::run_qe_step_from_existing_input_compat()` (line 22)
   - Reads .in as text (no parsing)
   - Patches CONTROL namelist (prefix, outdir, pseudo_dir)
   - Extracts pseudo filenames from `ATOMIC_SPECIES` (text regex)
   - Stages pseudos
   - Executes patched .in

**QE Invocation:** `engine.backend.run_step()` (line 116)

#### 4.C) Pseudopotential SSOT & Staging

**Pseudo filename mapping source:**
- **Primary:** Parsed from existing .in `ATOMIC_SPECIES` card (text regex, not full parsing)
- **Does NOT use:** `calculation.yaml` → `species_map` or `step.yaml` → `species_overrides`
- **Evidence:**
  - `calculation/compat_executor.py:203-237` - `_extract_required_pseudos_from_atomic_species()` uses regex
  - `calculation/compat_executor.py:86` - Extracts from input text directly

**Pseudo directory:**
- **Destination:** `project_root/pseudo`
- **Evidence:** `calculation/compat_executor.py:73` - `project_pseudo_dir = project_root / "pseudo"`

**Pseudo staging:**
- **Who calls:** `_stage_required_pseudos()` (line 87)
- **Inputs:**
  - `required_pseudos`: List of filenames extracted from .in
  - `project_pseudo_dir`: `project_root/pseudo`
  - `system_pseudo_dir`: `get_system_pseudo_dir()`
- **Evidence:** `calculation/compat_executor.py:87-91`

**Does NOT use:** YAML species_map or species_overrides (bypasses YAML SSOT)

#### 4.D) Override Handling

**species_overrides:**
- **Not supported:** Bypasses YAML, uses existing .in as-is
- **Evidence:** `calculation/compat_executor.py:22-131` - Only patches CONTROL keys

**card_overrides:**
- **Not supported:** Bypasses YAML, uses existing .in as-is
- **Evidence:** Same as above

**parameter_overrides:**
- **Not supported:** Bypasses YAML, uses existing .in as-is
- **Evidence:** Same as above

**Runtime-managed CONTROL keys:**
- **prefix:** Patched from calculation slug (line 67)
- **outdir:** Patched to `./outdir` (line 70)
- **pseudo_dir:** Patched to `project_root/pseudo` (absolute path, line 75)
- **Evidence:** `calculation/compat_executor.py:134-200` - `_patch_control_namelist()`

**Existing input merge/parse:**
- **Yes:** Existing .in is read as text and patched (minimal, no full parsing)
- **Evidence:** `calculation/compat_executor.py:63` - `input_text = existing_input_path.read_text()`

#### 4.E) Output Materialization

**Where .in is written:**
- **Location:** `calculation/raw/<existing_input_name>` (same filename as original)
- **Evidence:** `calculation/compat_executor.py:95` - `output_input_path = working_dir / existing_input_path.name`

**Clean rewrite vs patch:**
- **Patch:** Text-based patching of CONTROL namelist only (no full rewrite)
- **Evidence:** `calculation/compat_executor.py:78-83` - `_patch_control_namelist()`

**Parsing during run:**
- **No:** Patched .in is executed directly (no parsing during run)

---

### Mode 5: Daemon/JobManager Run

#### 5.A) Name & Purpose

**Name:** Daemon/JobManager Run  
**Purpose:** Execute calculations/steps via daemon/JobManager for GUI/background execution.

**Entry Points:**
- GUI → Daemon: `daemon/server.py::_handle_run_calculation()` (line 5358) or `_handle_run_step()` (line 5450)

#### 5.B) Call Chain

**Entry:** `src/quantumvitas/daemon/server.py::_handle_run_calculation()` (line 5358)

**Call Chain:**
1. `daemon/server.py::_handle_run_calculation()` (line 5358)
   - Normalizes project_root
   - Submits job via `JobManager.submit_with_id()` (line 5424)
2. `daemon/jobs.py::JobManager.submit_with_id()` (line 187)
   - Creates Job and submits to ThreadPoolExecutor
3. `daemon/jobs.py::JobManager._execute_job()` (wrapper function)
   - Calls `QVService.run_calculation()` (line 5427)
4. **Same as Mode 3** (Project Calculation Run)

**QE Invocation:** Same as Mode 3

#### 5.C) Pseudopotential SSOT & Staging

**Same as Mode 3** (Project Calculation Run):
- **Primary:** `calculation.yaml` → `species_map`
- **Fallback:** `step.yaml` → `species_overrides`
- **Staging:** `project_root/pseudo`
- **Evidence:** Same as Mode 3

#### 5.D) Override Handling

**Same as Mode 3** (Project Calculation Run)

#### 5.E) Output Materialization

**Same as Mode 3** (Project Calculation Run)

---

### Mode 6: CLI Run Structure

#### 6.A) Name & Purpose

**Name:** CLI Run Structure  
**Purpose:** Generate and run .in from structure + overrides (no calculation.yaml required).

**Entry Point:** `qv run structure <structure> [--type scf] [overrides...]`

#### 6.B) Call Chain

**Entry:** `src/quantumvitas/cli/main.py::run_structure_command()` (line 1764)

**Call Chain:**
1. `cli/main.py::run_structure_command()` (line 1764)
   - Resolves structure
   - Parses overrides from CLI args
   - Calls `run_input_step()` (line 1819)
2. `calculation/input_runner.py::run_input_step()` (line 458)
   - Calls `prepare_input_step()` to generate .in
   - Calls `run_prepared_step()` to execute
3. `calculation/input_runner.py::prepare_input_step()` (line 199)
   - Generates .in from structure + overrides
   - Calls `ensure_qe_pseudos()` if project_root provided
4. `calculation/input_runner.py::run_prepared_step()` (line 403)
   - Executes via engine

**QE Invocation:** `engine.backend.run_step()` (line 430)

#### 6.C) Pseudopotential SSOT & Staging

**Pseudo filename mapping source:**
- **Primary:** `species_overrides` parameter (passed at runtime)
- **Fallback:** Parsed from generated .in `ATOMIC_SPECIES` (if no overrides)
- **Evidence:**
  - `calculation/input_runner.py:205` - Accepts `species_overrides` parameter
  - `calculation/input_runner.py:458` - Passes overrides to `prepare_input_step()`

**Pseudo directory:**
- **Destination:** `project_root/pseudo` if project_root provided, else `workdir/pseudo`
- **Evidence:** `calculation/input_runner.py:216` - `project_root` parameter

**Pseudo staging:**
- **Who calls:** `prepare_input_step()` → `ensure_qe_pseudos()` (if project_root provided)
- **Inputs:**
  - `qe_input_file`: Generated .in
  - `project_pseudo_dir`: `project_root/pseudo` or `workdir/pseudo`
  - `species_map`: `None` (uses .in parsing or species_overrides parameter)
- **Evidence:** `calculation/input_runner.py:199-232` - `prepare_input_step()` signature

#### 6.D) Override Handling

**species_overrides:**
- **Storage:** Passed as parameter (runtime, not stored in YAML)
- **Applied:** During `prepare_input_step()` → `apply_species_overrides_to_qe_input()`
- **Evidence:** `calculation/input_runner.py:205` - Parameter

**card_overrides:**
- **Storage:** Passed as parameter (runtime, not stored in YAML)
- **Applied:** During `prepare_input_step()` → `apply_card_overrides_to_qe_input()`
- **Evidence:** `calculation/input_runner.py:204` - Parameter

**parameter_overrides:**
- **Storage:** Passed as parameter (runtime, not stored in YAML)
- **Applied:** During `prepare_input_step()` → parameter overrides
- **Evidence:** `calculation/input_runner.py:203` - Parameter

**Runtime-managed CONTROL keys:**
- **prefix:** Not set (no calculation context)
- **outdir:** Set to `workdir/outdir` (if not in overrides)
- **pseudo_dir:** Set to `project_root/pseudo` or `workdir/pseudo` (if project_root provided)
- **Evidence:** `calculation/input_runner.py:199-232` - `prepare_input_step()` logic

**Existing input merge/parse:**
- **No:** Generates fresh .in from structure + overrides

#### 6.E) Output Materialization

**Where .in is written:**
- **Location:** `workdir/<input_name>.in` (or default name)
- **Evidence:** `calculation/input_runner.py:229` - `output_name` parameter

**Clean rewrite vs patch:**
- **Clean rewrite:** Full generation from structure + overrides (no patching)
- **Evidence:** `calculation/input_runner.py:199-232` - `prepare_input_step()` generates new QEInput

**Parsing during run:**
- **No:** Generated .in is executed directly (no parsing during run)

---

## Pseudopotential SSOT & Staging Rules Per Mode

### Summary Table

| Mode | Pseudo Filename Source | Pseudo Directory | Staging Function | species_map Parameter |
|------|----------------------|------------------|------------------|----------------------|
| **Standalone** | step.yaml `species_overrides` (from .in parse) | `workdir/pseudo` | `ensure_qe_pseudos()` | `None` (falls back to .in parsing) |
| **Project SSOT Run** | `calculation.yaml` → `species_map` (preferred) or `step.yaml` → `species_overrides` (fallback) | `project_root/pseudo` | `ensure_qe_pseudos()` | `calculation.species_map` |
| **Project Calculation Run** | Same as Project SSOT Run | `project_root/pseudo` | `ensure_qe_pseudos()` + Step0 prep | `calculation.species_map` |
| **Compat Input Playback** | Parsed from existing .in `ATOMIC_SPECIES` (regex) | `project_root/pseudo` | `_stage_required_pseudos()` | N/A (bypasses YAML) |
| **Daemon/JobManager Run** | Same as Project Calculation Run | `project_root/pseudo` | Same as Project Calculation Run | `calculation.species_map` |
| **CLI Run Structure** | `species_overrides` parameter (runtime) or parsed from .in | `project_root/pseudo` or `workdir/pseudo` | `ensure_qe_pseudos()` (if project_root) | `None` (uses .in parsing or overrides) |

### Detailed Rules

**Rule 1: Calculation-level species_map takes precedence**
- **Applies to:** Project SSOT Run, Project Calculation Run, Daemon/JobManager Run
- **Evidence:** `calculation/structure_steps.py:575` - `effective_species_overrides = species_map if species_map else spec.species_overrides`
- **Exception:** Standalone and CLI Run Structure don't have calculation context

**Rule 2: Step-level species_overrides is fallback only**
- **Applies to:** Project SSOT Run, Project Calculation Run, Daemon/JobManager Run
- **Evidence:** Same as Rule 1
- **Note:** Standalone uses step-level as primary (no calculation exists)

**Rule 3: Parsing from .in is last resort**
- **Applies to:** Standalone (if step.yaml missing), CLI Run Structure (if no overrides)
- **Evidence:** `ensure_qe_pseudos()` fallback logic (line 193-212 in `pseudo.py`)

**Rule 4: Compat mode bypasses YAML entirely**
- **Applies to:** Compat Input Playback
- **Evidence:** `compat_executor.py:86` - Extracts from .in text directly

**Rule 5: Pseudo staging always uses project_root/pseudo or workdir/pseudo**
- **Applies to:** All modes
- **Evidence:** 
  - Project modes: `calculation/structure_steps.py:1145`
  - Standalone: `calculation/structure_steps.py:1728` (workdir as project_root)
  - Compat: `compat_executor.py:73`

---

## Overrides Matrix

### Storage Locations

| Override Type | Standalone | Project SSOT Run | Project Calculation Run | Compat Input Playback | Daemon/JobManager Run | CLI Run Structure |
|--------------|-----------|------------------|------------------------|----------------------|----------------------|-------------------|
| **species_overrides** | Temporary step.yaml | step.yaml (fallback) | step.yaml (fallback) | ❌ Not supported | step.yaml (fallback) | Runtime parameter |
| **card_overrides** | Temporary step.yaml | step.yaml | step.yaml | ❌ Not supported | step.yaml | Runtime parameter |
| **parameter_overrides** | Temporary step.yaml | step.yaml | step.yaml | ❌ Not supported | step.yaml | Runtime parameter |
| **calculation.species_map** | ❌ N/A | calculation.yaml | calculation.yaml | ❌ Not used | calculation.yaml | ❌ N/A |

### Application Timing

| Override Type | When Applied | Function |
|--------------|--------------|----------|
| **species_overrides** | Before generating .in | `generate_qe_input_from_spec()` → `apply_species_overrides_to_qe_input()` (line 576) |
| **card_overrides** | Before generating .in | `generate_qe_input_from_spec()` → `apply_card_overrides_to_qe_input()` (line 571) |
| **parameter_overrides** | Before generating .in | `generate_qe_input_from_spec()` → parameter overrides (line 514) |
| **calculation.species_map** | Before generating .in | `generate_qe_input_from_spec()` → `species_map` parameter (line 492) |

### Precedence Rules

1. **calculation.species_map** > **step.species_overrides** (for project modes)
2. **step.species_overrides** > **parsing from .in** (for standalone)
3. **Runtime overrides** > **YAML stored overrides** (for CLI Run Structure)

---

## Risks / Multiple Truths

### Risk #1: Standalone Uses Step-Level species_overrides as Primary

**Location:** `calculation/structure_steps.py:1721-1729` (standalone materialization)

**Problem:** Standalone mode creates temporary step.yaml with `species_overrides`, but has no calculation.yaml. This means standalone uses step-level as primary (not fallback), which differs from project modes.

**Consequence:** Inconsistent behavior between standalone and project modes. If standalone is intended to match project behavior, it should create a temporary calculation.yaml with species_map.

**Evidence:**
- `cli/main.py:1696-1704` - Creates step.yaml only (no calculation.yaml)
- `calculation/structure_steps.py:1112` - Passes `species_map=None` (so falls back to step.species_overrides)

### Risk #2: Compat Mode Bypasses YAML SSOT Entirely

**Location:** `calculation/compat_executor.py:22-131`

**Problem:** Compat mode reads existing .in as text and patches it, completely bypassing YAML SSOT. This creates a third source of truth (raw .in files) that diverges from intended design.

**Consequence:** Tutorial tests may pass with compat mode but fail with normal project execution if .in and YAML diverge.

**Evidence:**
- `compat_executor.py:63` - Reads .in as text (no parsing)
- `compat_executor.py:86` - Extracts pseudos via regex (not YAML)

### Risk #3: Import Writes Step-Level, Runtime Prefers Calc-Level

**Location:** 
- Import: `calculation/importers.py:198-223` (writes step-level)
- Runtime: `calculation/structure_steps.py:575` (prefers calc-level)

**Problem:** When importing a single step, pseudo info is written to `step.yaml` → `species_overrides`, but runtime prefers `calculation.yaml` → `species_map`. This creates a migration gap.

**Consequence:** Imported steps work via fallback, but don't follow intended SSOT pattern. Should write to calculation.yaml instead.

**Evidence:**
- `calculation/importers.py:198-223` - Writes `species_overrides` to step.yaml
- `calculation/structure_steps.py:575` - Prefers `species_map` from calculation.yaml

### Risk #4: CLI Run Structure Has No Persistent Storage

**Location:** `calculation/input_runner.py:199-232`

**Problem:** CLI Run Structure accepts overrides as runtime parameters but doesn't store them in YAML. This means the generated .in cannot be reproduced without re-running with same parameters.

**Consequence:** No audit trail or reproducibility for CLI-generated runs.

**Evidence:**
- `calculation/input_runner.py:199-232` - `prepare_input_step()` accepts parameters but doesn't save to YAML

### Risk #5: Pseudo Directory Location Inconsistency

**Location:** Various (see table above)

**Problem:** Different modes use different pseudo directory locations:
- Project modes: `project_root/pseudo`
- Standalone: `workdir/pseudo`
- CLI Run Structure: `project_root/pseudo` or `workdir/pseudo` (depends on project_root)

**Consequence:** Inconsistent behavior makes it harder to reason about where pseudos are staged.

**Evidence:** See "Pseudopotential SSOT & Staging Rules Per Mode" table above

---

## Recommendations

### Recommendation #1: Make Standalone Create Temporary Calculation with species_map

**Current:** Standalone creates temporary step.yaml only, uses step-level species_overrides as primary.

**Recommendation:** After importing .in to step.yaml, create a temporary calculation.yaml with species_map extracted from step.yaml. This ensures standalone matches project mode behavior (calc-level SSOT).

**Minimal Path:**
1. After `build_step_spec_from_qe_input()`, extract species_overrides
2. Create temporary `calculation.yaml` with `species_map` field
3. Pass calculation_dir to `materialize_step_spec()` so it loads species_map
4. Remove species_overrides from step.yaml (or keep for backwards compat)

### Recommendation #2: Deprecate Compat Mode or Make It Use YAML

**Current:** Compat mode bypasses YAML SSOT entirely, uses raw .in as source of truth.

**Recommendation:** Either:
- **Option A:** Deprecate compat mode in favor of normal project execution
- **Option B:** Make compat mode parse .in → create temporary YAML → use normal execution path

**Minimal Path (Option B):**
1. In compat mode, parse existing .in to create temporary step.yaml
2. Use normal `materialize_step_spec()` path instead of text patching
3. This ensures compat mode uses same SSOT as project modes

### Recommendation #3: Make Import Write to Calculation-Level species_map

**Current:** Import writes to step-level species_overrides, but runtime prefers calc-level species_map.

**Recommendation:** When importing steps, write pseudo info to `calculation.yaml` → `species_map` instead of (or in addition to) `step.yaml` → `species_overrides`.

**Minimal Path:**
1. After importing all steps, collect species_overrides from all steps
2. Call `migrate_species_overrides_to_calc()` to create species_map
3. Save to calculation.yaml
4. Optionally remove species_overrides from step.yaml (or keep for backwards compat)

### Recommendation #4: Document Pseudo Directory Policy

**Current:** Different modes use different pseudo directory locations.

**Recommendation:** Document clear policy:
- **Project modes:** Always use `project_root/pseudo`
- **Standalone:** Use `workdir/pseudo` (no project exists)
- **CLI Run Structure:** Use `project_root/pseudo` if project exists, else `workdir/pseudo`

**Minimal Path:** Add documentation comment explaining pseudo directory policy per mode.

### Recommendation #5: Add YAML Storage for CLI Run Structure

**Current:** CLI Run Structure accepts overrides as runtime parameters but doesn't store them.

**Recommendation:** After generating .in, optionally create step.yaml (and calculation.yaml if project exists) to store overrides for reproducibility.

**Minimal Path:**
1. After `prepare_input_step()`, create step.yaml with overrides
2. If project_root exists, optionally create/update calculation.yaml
3. This enables audit trail and reproducibility

---

## Evidence Summary (File + Line References)

### Entry Points
- `src/quantumvitas/cli/main.py:1427` - `run_step_command()` (Project SSOT Run, Standalone)
- `src/quantumvitas/cli/main.py:1636` - `_run_standalone_step()` (Standalone)
- `src/quantumvitas/cli/main.py:1764` - `run_structure_command()` (CLI Run Structure)
- `src/quantumvitas/api.py:1151` - `QVService.run_calculation()` (Project Calculation Run)
- `src/quantumvitas/daemon/server.py:5358` - `_handle_run_calculation()` (Daemon/JobManager Run)
- `src/quantumvitas/calculation/runner.py:140` - `CalculationRunner.run(compat_input_playback=True)` (Compat Input Playback)

### Pseudopotential Resolution
- `src/quantumvitas/core/pseudo.py:67-392` - `ensure_qe_pseudos()` (canonical resolution function)
- `src/quantumvitas/calculation/structure_steps.py:1166-1171` - Calls `ensure_qe_pseudos()` with species_map
- `src/quantumvitas/calculation/compat_executor.py:86-91` - Extracts and stages pseudos (bypasses ensure_qe_pseudos)

### Override Application
- `src/quantumvitas/calculation/structure_steps.py:573-576` - Species override precedence (calc-level > step-level)
- `src/quantumvitas/calculation/structure_steps.py:571` - Card override application
- `src/quantumvitas/calculation/structure_steps.py:514` - Parameter override application

### QE Invocation
- `src/quantumvitas/engine/qe_calculation.py:147` - `QECalculationRunner.run_step()` (actual QE execution)
- `src/quantumvitas/calculation/step.py:200+` - `Step.run()` (wraps engine execution)

---

## Conclusion

QMatSuite has **6 distinct execution modes** with varying requirements for project context, YAML SSOT, and pseudopotential handling. The main inconsistency is that **standalone and compat modes use different SSOT sources** than project modes:

- **Project modes:** Use `calculation.yaml` → `species_map` as primary SSOT
- **Standalone:** Uses temporary `step.yaml` → `species_overrides` (no calculation exists)
- **Compat:** Bypasses YAML entirely, uses raw .in as SSOT

**Key Recommendation:** Align all modes to use calculation-level `species_map` as SSOT, with step-level `species_overrides` as fallback only. This requires:
1. Making standalone create temporary calculation.yaml
2. Deprecating or fixing compat mode to use YAML
3. Ensuring import writes to calculation-level

This will create a consistent SSOT across all execution modes.

