# GUI Engine Support & Demo System End-to-End Audit

**Status**: Review document (diagnosis only, no fixes)
**Date**: 2026-02-07
**Scope**: GUI engine support, demo system, consumption path, B1 gap analysis

---

## 1. GUI Engine Support Map

### 1.1 Engine Support Summary

| Engine | Backend Registered | CLI Supported | GUI Selectable | GUI Parameters | Demo Exists | Verdict |
|--------|-------------------|---------------|----------------|----------------|-------------|---------|
| QE | Yes | Yes (default) | No (auto-selected) | Yes (full) | 14 demos | **Real** |
| Wannier90 | Yes | Yes | No | No | 3 demos | **Partial** (QE+W90 workflow only) |
| ORCA | Yes | Yes | No | No | 3 demos | **Broken** (wrong step_type_spec) |
| PySCF | Yes | Yes (default for molecule) | No (auto-selected) | No | 1 demo | **Partial** (runs but no param UI) |
| VASP | Yes | Yes | No | No | 0 demos | **Backend only** |
| LAMMPS | Yes | Yes | No | No | 0 demos | **Backend only** |
| Gaussian | Yes | Yes | No | No | 0 demos | **Backend only** |
| ABINIT | Yes | Yes | No | No | 0 demos | **Backend only** |
| CP2K | Yes | Yes | No | No | 0 demos | **Backend only** |
| Siesta | Yes | Yes | No | No | 0 demos | **Backend only** |
| GPAW | Yes | Yes | No | No | 0 demos | **Backend only** |
| Psi4 | Yes | Yes | No | No | 0 demos | **Backend only** |
| xTB | Yes | Yes | No | No | 0 demos | **Backend only** |
| QMCPACK | Yes | Yes | No | No | 0 demos | **Backend only** |
| Yambo | Yes | Yes | No | No | 0 demos | **Backend only** |

**Summary**: Of 15 registered engines, only QE has real GUI support. Wannier90 works as a QE adjunct. PySCF can run but has no parameter UI. ORCA demos are broken. The remaining 11 engines are backend-only.

### 1.2 Where QE Is Treated as Special

#### GUI (TypeScript)

| File | Lines | What It Does | QE-Specific? |
|------|-------|-------------|--------------|
| `gui/src/components/panels/CalculationOverviewTab.tsx` | 453-460 | Step type dropdown | **Hard-coded**: SCF, NSCF, Relax, VC-Relax, Bands (PW), Bands, DOS |
| `gui/src/components/panels/CalculationListPanel.tsx` | 1344-1354 | Step type dropdown (list view) | **Hard-coded**: SCF, NSCF, Relax, VC-Relax, Bands PW, Bands PP, DOS, PDOS, Phonon, Post-Process — all QE pw.x/bands.x/dos.x/ph.x |
| `gui/src/components/panels/StepDetailPanel.tsx` | 52-73 | `stepTypeToModule()` function | **Hard-coded**: maps step types to QE modules (pw, bands, ph, projwfc, pp). Returns `null` for anything non-QE |
| `gui/src/components/panels/StepDetailPanel.tsx` | 76-87+ | `LEGACY_EDITABLE_PARAMS` | **Hard-coded**: QE namelist/key parameter definitions (SYSTEM.ecutwfc, etc.) |
| `gui/src/components/panels/StepDetailPanel.tsx` | 528 | Parameter fetch call | Uses `listQeUiParameters(module, stepType)` — QE-only RPC |
| `gui/src/components/panels/SettingsPanel.tsx` | 111, 146, 174, 438, 481 | Engine detection & config | Calls `list_qe_engines`, `detect_qe`, `set_qe_engine` — all QE-only RPCs |
| `gui/src/components/panels/QEParameterBrowserPanel.tsx` | entire file | Parameter browser | Entirely QE: calls `list_qe_parameter_metadata` throughout |
| `gui/src/hooks/useQEParameterMetadata.ts` | entire file | QE param metadata hook | Types named `QEModuleMeta`, `QESectionMeta`, `QEParameterMeta` |
| `gui/src/hooks/useQVClient.ts` | 54, 58, 382, 390 | RPC client methods | `listQeUiParameters`, `listQeParameterMetadata` — QE-only methods |
| `gui/src/types/qv.ts` | 493-525, 696-714 | RPC type definitions | `detect_qe`, `list_qe_engines`, `discover_qe_engines`, `set_qe_engine`, `list_qe_ui_parameters`, `list_qe_parameter_metadata` |

#### Daemon/Backend (Python)

| File | Lines | What It Does | QE-Specific? |
|------|-------|-------------|--------------|
| `src/quantumvitas/daemon/server.py` | 718-771 | RPC handlers | `_handle_detect_qe`, `_handle_get_env_info`, `_handle_list_qe_engines`, `_handle_discover_qe_engines`, `_handle_set_qe_engine` |
| `src/quantumvitas/daemon/server.py` | 1432-1993 | Parameter metadata RPCs | `_handle_list_qe_ui_parameters`, `_handle_list_qe_parameter_metadata`, `_handle_reload_qe_parameter_metadata`, `_handle_get_qe_parameter_metadata_debug_info` |
| `src/quantumvitas/daemon/server.py` | 4157-4196 | QE input import | `_handle_import_step_from_qe_input` — only QE |
| `src/quantumvitas/api/service.py` | 3689-3756 | Common card fetch | `get_common_cards()` only handles K_POINTS (QE concept). Imports `from quantumvitas.calculation.k_points_view` |
| `src/quantumvitas/api/service.py` | 4302-4372 | Common card write | `set_common_card()` only handles K_POINTS. Raises error for all other cards |
| `src/quantumvitas/api/service.py` | 2796-2801 | Step detail extraction | Checks `"CONTROL" in spec.parameters` and extracts `calculation`, `outdir` — QE namelist structure |
| `src/quantumvitas/api/service.py` | 4436-4441 | Pseudo dir extraction | `control_params = parameters.get("CONTROL", {})` for `pseudo_dir` |
| `src/quantumvitas/api/service.py` | 6244 | Engine default | `engine_family = "pyscf" if structure_kind == "molecule" else "qe"` |
| `src/quantumvitas/calculation/importers.py` | entire file | Step import from input | Entirely QE: imports `QEInputGenerator`, `QEInputParser`, `QEInput`, `QECardType`, `QEModule` |
| `src/quantumvitas/calculation/k_points_view.py` | entire file | K-points view model | Entirely QE: K_POINTS card modes (gamma, automatic, tpiba, crystal) |

#### Constitutional Violations in Backend

| File | Line | Issue | Rule Violated |
|------|------|-------|---------------|
| `service.py` | 3182 | `engine = step_spec.engine if step_spec else "qe"` | **Ban #4**: No silent fallbacks |
| `service.py` | 3825 | `engine_family = getattr(calc_model, 'engine_family', None) or "qe"` | **Ban #4**: No silent fallbacks |
| `service.py` | 7267 | `resolve_step_type_spec()` default `engine_family: str = "qe"` | **Ban #4**: No silent fallbacks |

### 1.3 What Is Correctly Engine-Agnostic

| Component | File | Assessment |
|-----------|------|------------|
| Runner | `src/quantumvitas/calculation/runner.py` | Fully engine-agnostic. Uses `DriverRegistry.get_handler()` |
| Executor | `src/quantumvitas/execution/executor.py` | Fully engine-agnostic. Pluggable handler dispatch |
| DriverRegistry | `src/quantumvitas/core/driver_registry.py` | Correct: all 15 engines registered |
| Compat layer | `src/quantumvitas/daemon/compat.py` | No QE-specific response shaping found |
| Demo gallery | `gui/src/components/panels/DemoGalleryPanel.tsx` | Engine-agnostic: lists all demos, creates any |

---

## 2. Demo Catalog

### 2.1 All Demo Snapshots

| # | File | Engine | Workflow | Status |
|---|------|--------|----------|--------|
| 1 | `00_Si_scf.yml` | QE | SCF | **Usable** |
| 2 | `03_Si_vc_relax.yml` | QE | VC-Relax | **Usable** |
| 3 | `04_Si_DOS.yml` | QE | SCF -> NSCF -> DOS | **Usable** |
| 4 | `06_Al_DOS.yml` | QE | VC-Relax -> SCF -> NSCF -> DOS | **Usable** |
| 5 | `07_Si_bandStructure.yml` | QE | SCF -> NSCF -> Bands PW -> Bands PP | **Usable** |
| 6 | `08_Fe_DOS.yml` | QE | SCF (magnetic) | **Usable** |
| 7 | `09_Si_phonon.yml` | QE | SCF -> ph -> q2r -> matdyn -> custom | **Usable** |
| 8 | `12_NMR_gipaw.yml` | QE | SCF -> GIPAW | **Usable** |
| 9 | `13_graphene.yml` | QE | VC-Relax -> SCF -> Bands | **Usable** |
| 10 | `15_bulk_modulus_Si.yml` | QE | 3x SCF (parameter scan) | **Usable** |
| 11 | `19_Si_CPMD.yml` | QE | 3x custom (CP-MD) | **Usable** |
| 12 | `si_bands_demo.yml` | QE | SCF -> NSCF -> Bands PW -> Bands PP | **Usable** (primary bands demo) |
| 13 | `si_dos_demo.yml` | QE | SCF -> NSCF -> DOS | **Usable** (primary DOS demo) |
| 14 | `copper_wannier90_demo.yml` | QE+W90 | SCF -> NSCF -> wannierprep -> pw2wannier -> wannier | **Usable** (no `engine_family`, mixed step types) |
| 15 | `diamond_wannier90_demo.yml` | QE+W90 | SCF -> NSCF -> wannierprep -> pw2wannier -> wannier | **Usable** (same as above) |
| 16 | `silicon_wannier90_demo.yml` | QE+W90 | SCF -> NSCF -> wannierprep -> pw2wannier -> wannier | **Usable** (same as above) |
| 17 | `water_orca_scf.yml` | ORCA | SCF | **BROKEN**: `engine_family: orca` but `step_type_spec: qe_scf` |
| 18 | `methane_orca_freq.yml` | ORCA | SCF | **BROKEN**: `engine_family: orca` but `step_type_spec: qe_scf` (freq step missing) |
| 19 | `formaldehyde_orca_tddft.yml` | ORCA | SCF + TDDFT | **BROKEN**: `engine_family: orca` but steps use `step_type_spec: qe_scf` and `step_type_spec: pyscf_td` |
| 20 | `water_pyscf_scf.yml` | PySCF | SCF | **Usable** (correct `step_type_spec: pyscf_scf`) |

### 2.2 Critical Demo Defects

#### ORCA Demos: Wrong `step_type_spec` (3 demos affected)

All 3 ORCA demos declare `engine_family: orca` at the calculation level but use incorrect `step_type_spec` values:

| Demo | Declared `engine_family` | Actual `step_type_spec` | Should Be |
|------|-------------------------|------------------------|-----------|
| `water_orca_scf.yml` | `orca` | `qe_scf` | `orca_scf` |
| `methane_orca_freq.yml` | `orca` | `qe_scf` | `orca_scf` (and missing freq step) |
| `formaldehyde_orca_tddft.yml` | `orca` | `qe_scf`, `pyscf_td` | `orca_scf`, `orca_td` |

**Impact**: If materialized and run, the runner would dispatch these steps to QE/PySCF handlers, not ORCA. These demos are misleading — they appear to be ORCA demos in the gallery but would not produce ORCA calculations.

#### Missing `engine_family` on Older Demos

The 14 QE demos and 3 Wannier90 demos have no `engine_family` field at the calculation level. They rely on the backend default (`"qe"`). While functionally correct today, this is an implicit assumption that becomes problematic when the system supports engine selection.

The PySCF demo also lacks `engine_family` but has the correct `step_type_spec: pyscf_scf`.

#### LAMMPS Template: Jinja2, Not YAML SSOT

The LAMMPS calculation template at `resources/calculation_templates/lammps/` contains `.in.j2` Jinja2 template files (not YAML SSOT). These are:
- `md_npt.in.j2`
- `md_nve.in.j2`
- `md_nvt.in.j2`
- `minimize.in.j2`

These follow a completely different format from the demo snapshot system and are not integrated with the demo gallery. They appear to be standalone input templates, not runnable demos.

### 2.3 Reference Artifacts

| Demo | Artifact Files | Present? |
|------|---------------|----------|
| `00_Si_scf` | `00_Si_scf.scf.json` | Yes |
| `04_Si_DOS` | `04_Si_DOS.dos.json`, `04_Si_DOS.scf.json` | Yes |
| `06_Al_DOS` | `06_Al_DOS.dos.json`, `06_Al_DOS.scf.json` | Yes |
| `07_Si_bandStructure` | `07_Si_bandStructure.bands.json`, `07_Si_bandStructure.scf.json` | Yes |
| `08_Fe_DOS` | `08_Fe_DOS.dos.json`, `08_Fe_DOS.scf.json` | Yes |
| `09_Si_phonon` | `09_Si_phonon.scf.json` | Yes |
| `12_NMR_gipaw` | `12_NMR_gipaw.scf.json` | Yes |
| `13_graphene` | `13_graphene.bands.json`, `13_graphene.scf.json` | Yes |
| `15_bulk_modulus_Si` | `15_bulk_modulus_Si.scf.json` | Yes |
| `si_bands_demo` | `si_bands_demo.bands.json`, `si_bands_demo.scf.json` | Yes |
| `si_dos_demo` | `si_dos_demo.dos.json`, `si_dos_demo.scf.json` | Yes |
| `water_pyscf_scf` | `water_pyscf_scf.scf.json` | Yes |
| ORCA demos | None | **Missing** |
| Wannier90 demos | None | **Missing** |

Also present:
- `01_H2.scf.json` — orphan artifact (no corresponding `01_H2.yml` snapshot)
- `orca_demo_index.json` — metadata index for ORCA demos
- `import_report.json`, `import_report.md` — import audit artifacts

### 2.4 Supplementary Files

| File | Purpose | Status |
|------|---------|--------|
| `orca_demo_index.json` | Index of ORCA demo metadata | Informational, not consumed by runtime |
| `*_README.md` (3 files) | Human-readable explanations for ORCA demos | Not consumed by runtime |
| `import_report.json` / `.md` | Audit of demo import process | Not consumed by runtime |

---

## 3. Demo -> GUI Consumption Path

### 3.1 Discovery Flow

```
User opens GUI
  -> Welcome screen shows "Demo Gallery" button
     (testid: qv-welcome-btn-demo-gallery)
  -> Click opens DemoGalleryPanel
     (gui/src/components/panels/DemoGalleryPanel.tsx)
  -> Panel calls RPC: list_demo_projects
     (daemon/server.py -> service.py:list_demo_projects())
  -> Service scans resources/demo_projects/*.yml
  -> Extracts metadata (title, subtitle, tags, difficulty, recommended_analysis)
  -> Returns list of 20 demo descriptors
  -> GUI renders demo cards with metadata
```

### 3.2 Materialization Flow

```
User clicks "Create Project" on a demo card
  -> GUI prompts for target directory (file picker)
  -> GUI calls RPC: create_demo_project(target_dir, name, demo_id)
     (daemon/server.py -> service.py:create_demo_project())
  -> Service loads snapshot YAML
  -> Calls materialize_project_from_snapshot()
     (project/snapshot.py:521)
     -> Generates new ULIDs for all entities
     -> Creates directory structure:
        project_root/
          project.qv.yml
          structures/*.json
          calculations/*/calculation.yaml
          calculations/*/steps/*.step.yaml
          pseudo/
     -> Stages pseudopotential files (if available)
  -> Returns project_root
  -> GUI loads new project into workspace
```

### 3.3 What Happens After Materialization

The materialized project is a standard SSOT project. The GUI then:
1. Loads the project tree (calculations, structures, steps)
2. Displays calculation overview with step list
3. User can click into a step to see/edit parameters
4. **HERE IS THE PROBLEM**: `StepDetailPanel.tsx:stepTypeToModule()` maps step_type_gen to a QE module. For non-QE steps, it returns `null`, and parameter UI is blank or broken.

### 3.4 Missing Abstractions

| Missing Abstraction | Impact |
|---------------------|--------|
| **No demo metadata schema validation** | ORCA demos shipped with wrong `step_type_spec` — no automated check caught the mismatch between `engine_family` and `step_type_spec` prefix |
| **No engine capability tags on demos** | Gallery cannot filter "show me VASP demos" — tags are free-form strings |
| **No engine-specific parameter metadata RPC** | Only `list_qe_ui_parameters` exists. No `list_engine_ui_parameters(engine, ...)` |
| **No engine detection/config abstraction** | Only `detect_qe` / `set_qe_engine` exist. No `detect_engine(engine_family)` / `set_engine(engine_family, config)` |
| **No engine-aware step type catalog** | GUI hard-codes QE step types in dropdown. Should dynamically query available step types per engine via DriverRegistry |
| **No card abstraction beyond K_POINTS** | `get_common_cards` / `set_common_card` only handle QE K_POINTS. No concept of engine-agnostic "card" or "input section" |

### 3.5 Implicit Assumptions Blocking Non-QE Engines

1. **Engine auto-selection** (`service.py:6244`): `create_calculation` defaults to QE for periodic, PySCF for molecular. No user choice exposed through GUI.

2. **Parameter display** (`StepDetailPanel.tsx:52-73`): `stepTypeToModule()` returns `null` for non-QE steps, so parameter editing UI shows nothing.

3. **Step type dropdown** (`CalculationOverviewTab.tsx:453-460`, `CalculationListPanel.tsx:1344-1354`): Only QE step types listed. User cannot add VASP, ORCA, LAMMPS, etc. steps via GUI.

4. **Parameter fetch RPC** (`list_qe_ui_parameters`): Only QE metadata available. No equivalent for other engines despite all B1-complete engines having `data/<engine>_metadata.py`.

5. **Card editing** (`get_common_cards` / `set_common_card`): Assumes QE K_POINTS structure. VASP uses KPOINTS file, ORCA has no k-points, LAMMPS has no k-points.

6. **Settings panel** (`SettingsPanel.tsx`): Only QE binary detection and configuration. No VASP, ORCA, LAMMPS binary detection.

7. **Input import** (`import_step_from_qe_input`): Can only import from QE input files. Despite VASP, ORCA, LAMMPS, Gaussian, ABINIT, QMCPACK all having parsers in their B1 I/O stack.

---

## 4. Gap Analysis vs B1 Playbook Philosophy

### 4.1 B1 Playbook Principles

From `docs/architecture/B1_ENGINE_PLAYBOOK.md`:

> "B1 complete" means: an engineer or agent unfamiliar with the engine could run any supported workflow type using only the driver's I/O stack, validate the outputs programmatically, and trust the parameter metadata catalog for input validation. No black boxes.

The playbook explicitly scopes B1 to driver-level work:

> Scope: This playbook covers the driver-level work only. It does NOT cover kernel integration, runner changes, or public API surface — those are separate phases.

### 4.2 Concrete Mismatches

| B1 Expectation | Current Reality | Gap |
|---------------|-----------------|-----|
| Engine-agnostic runner | Runner IS engine-agnostic | **No gap** |
| Each B1 engine has parameter metadata catalog | VASP, ORCA, LAMMPS, Gaussian, QMCPACK all have `data/<engine>_tags.json` + `<engine>_metadata.py` | **No gap** at driver level; **GUI has no way to consume it** |
| Each B1 engine has bidirectional I/O | All B1 engines have parse + write in `io/` | **No gap** at driver level; **GUI has no way to invoke it** |
| Each B1 engine has output digest parser | All B1 engines have `parsers/output.py` with `@register_parser` | **No gap** at driver level |
| Demo-driven UX (implied by demo gallery) | 14 QE demos work. 3 ORCA demos broken. 0 demos for VASP/LAMMPS/Gaussian/ABINIT/CP2K/Siesta/GPAW/Psi4/xTB/QMCPACK/Yambo | **Large gap**: 11 B1-ready engines have zero demos |
| No engine-specific GUI logic | GUI is almost entirely QE-specific | **Critical gap**: GUI unusable for non-QE engines |

### 4.3 Severity Classification

**P0 — Demos Are Wrong (Trust Issue)**
- 3 ORCA demos have wrong `step_type_spec`. If a user materializes and tries to run them, they get QE dispatch, not ORCA. This is worse than having no demos — it's actively misleading.

**P1 — GUI Is QE-Only (Blocking)**
- Step type dropdown is hard-coded to QE
- Parameter UI only works for QE
- Engine detection/config only for QE
- Input import only for QE
- These prevent any non-QE engine from being used through the GUI at all

**P2 — No Demos for B1-Complete Engines (Adoption Blocker)**
- VASP, LAMMPS, Gaussian, QMCPACK, ABINIT all have comprehensive B1 driver stacks
- Zero demos exist for any of them
- Demo gallery is the primary onboarding entry point — if there's no demo, the engine effectively doesn't exist for GUI users

**P3 — Schema & Consistency**
- `engine_family` field missing from older demos (14 QE + 3 W90 + 1 PySCF)
- No validation gate catches `engine_family` / `step_type_spec` mismatch
- `01_H2.scf.json` is an orphan artifact with no corresponding snapshot

**P4 — Silent Fallbacks (Constitution Violation)**
- 3 places in `service.py` silently default to `"qe"` when engine info is missing
- Violates ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md §9 Ban #4

---

## 5. Prioritized Architectural Gaps

### Tier 1: Fix Broken Demos (Trust)

1. **Fix ORCA demo `step_type_spec` values**: All 3 ORCA demos need `orca_scf`, `orca_freq`, `orca_td` instead of `qe_scf` / `pyscf_td`
2. **Add schema validation gate**: New test that verifies `step_type_spec` prefix matches `engine_family` (or inferred engine) for all demo snapshots
3. **Add `engine_family` to all demos**: Make it explicit, not inferred from defaults
4. **Remove orphan `01_H2.scf.json`** or add corresponding snapshot

### Tier 2: Engine-Agnostic GUI Primitives

5. **Generic parameter metadata RPC**: Replace `list_qe_ui_parameters` with `list_engine_ui_parameters(engine_family, step_type, ...)` that dispatches to each engine's metadata catalog
6. **Dynamic step type catalog RPC**: New RPC `list_engine_step_types(engine_family)` that queries DriverRegistry for supported GEN steps per engine
7. **Engine selection in calculation creation**: Expose `engine_family` parameter in `create_calculation` GUI flow (dropdown populated from `DriverRegistry.list_engines()`)
8. **Generic engine detection/config RPC**: Replace QE-specific detection RPCs with `detect_engine(engine_family)` / `configure_engine(engine_family, config)`

### Tier 3: Demo Coverage

9. **Create demos for B1-complete engines**: At minimum, VASP, LAMMPS, Gaussian, QMCPACK need 1-2 starter demos each
10. **Create demos for ABINIT, CP2K, Siesta, xTB**: Lower priority since B1 may not be complete, but even a simple SCF demo validates the pipeline

### Tier 4: Cleanup

11. **Remove silent `"qe"` fallbacks**: Replace with hard errors per Constitution
12. **Generalize `get_common_cards` / `set_common_card`**: Either make engine-aware or deprecate in favor of engine-specific parameter editing
13. **Generalize input import**: Leverage existing B1 parsers (VASP, ORCA, LAMMPS, Gaussian, ABINIT, QMCPACK) behind a unified `import_step_from_input(engine_family, input_files)` RPC

---

## 6. High-Level Direction

The fundamental pattern is clear: the **driver layer** (runners, executors, registry, B1 drivers) is correctly engine-agnostic, but the **presentation layer** (GUI, RPCs, service methods, demos) was built for QE and never generalized. The fix is not to rip out the QE code but to:

1. **Extract the QE-specific patterns into an engine-dispatched abstraction** (parameter metadata, detection, cards, import)
2. **Wire the existing B1 metadata catalogs** (`<engine>_metadata.py`) into the generic abstraction
3. **Populate the demo gallery** with real, validated demos for each B1-complete engine
4. **Add validation gates** that enforce consistency between `engine_family` and `step_type_spec` in all demo snapshots

The runner/executor/registry infrastructure already supports all 15 engines. The gap is purely in the GUI and service layer.
