# QE CONTROL.prefix Code Review Report

**Date**: 2024  
**Scope**: How is QE CONTROL.prefix determined and where does it live (calc-level vs step-level)?

---

## A) Prefix Source (Single Source of Truth)

### A1) Computation/Injection Location

**Primary injection function**: `src/qmatsuite/calculation/structure_steps.py::_inject_calculation_prefix_outdir()` (lines 280-384)

**Pseudocode**:
```python
# R1: Canonical prefix = calculation.meta.slug
calculation_prefix = calc_model.meta.slug if calc_model.meta else None

# R2: Only inject if schema defines prefix parameter
if calculation_prefix and "prefix" in param_to_sections:
    target_section = prefix_sections[0]  # Usually "CONTROL"
    namelist.parameters["prefix"] = calculation_prefix  # Override any existing
```

**Source derivation**:
- **File**: `src/qmatsuite/calculation/structure_steps.py` (lines 1034-1035)
- **Logic**: `calculation_prefix = calc_model.meta.slug if calc_model.meta else None`
- **Source**: `calculation.yaml` → `meta.slug` field
- **NOT derived from**: calc.id, project config, or constants

**Additional injection sites**:
- `src/qmatsuite/calculation/structure_steps.py` (lines 901-910): pw2wannier90 special case (uses same `calc_model.meta.slug`)
- `src/qmatsuite/api.py` (lines 4244-4245): API layer uses same derivation (`calculation_model.meta.slug`)

---

## B) Persistence / Where it Appears

### B1) Written to step.yaml?

**Answer**: NO. Prefix is NOT written to step YAML files.

**Evidence**:
- `src/qmatsuite/project/snapshot.py` (lines 375-381): Export function explicitly **strips** prefix/outdir from step parameters before writing:
  ```python
  # R4: Remove prefix/outdir from step parameters (injected from calculation.meta.slug)
  if "parameters" in step_dict:
      for section_name, section_params in step_dict["parameters"].items():
          if isinstance(section_params, dict):
              section_params.pop("prefix", None)
              section_params.pop("outdir", None)
  ```
- Step YAML files contain only step-local configuration (parameters, cards, species_overrides), not calculation-level injected fields.

### B2) Written to calculation.yaml?

**Answer**: NO. Prefix is NOT written to `calculation.yaml`.

**Evidence**:
- Prefix is derived FROM `calculation.yaml` (`meta.slug`), not written TO it.
- `calculation.yaml` stores `meta.slug` (the source), not `CONTROL.prefix` (the derived value).

### B3) Written to manifest?

**Answer**: NO. Prefix is NOT written to manifest.

**Evidence**:
- Manifest stores execution metadata (step status, fingerprints, timestamps), not QE input parameters.
- No code paths found that write prefix to manifest.

**Conclusion**: Prefix is **runtime-only** and injected during materialization. It is NOT persisted anywhere.

---

## C) Override Semantics

### C1) Can step-level CONTROL.prefix be specified in step.yaml?

**Answer**: YES, but it is **ignored**.

**Evidence**:
- `src/qmatsuite/calculation/structure_steps.py` (lines 336-341):
  ```python
  if "prefix" in flat_spec_params and calculation_prefix:
      ignored_step_prefix = flat_spec_params["prefix"]
      logger.info(
          f"[PREFIX_INJECTION] Step-level prefix '{ignored_step_prefix}' will be ignored, "
          f"calculation prefix '{calculation_prefix}' takes precedence"
      )
  ```
- Step-level prefix in `spec_params` is detected and logged as "ignored", but calculation-level prefix always wins.

### C2) Does UI show "ignored step-level overrides"?

**Answer**: YES, via logging.

**Evidence**:
- `src/qmatsuite/calculation/structure_steps.py` (lines 338-340): Logs `[PREFIX_INJECTION]` message when step-level prefix is ignored.
- `src/qmatsuite/api.py` (lines 4261-4274): API layer tracks `ignored_step_prefix` in `injection_info` dict for UI consumption.

### C3) Does import/show treat it as original param?

**Answer**: NO. Import/show strips runtime-only fields.

**Evidence**:
- `tests/unit/test_project_and_cli.py` (lines 1003-1014): Test explicitly strips `outdir`, `prefix`, `pseudo_dir` from comparison:
  ```python
  RUNTIME_ONLY_KEYS = {"outdir", "prefix", "pseudo_dir"}
  # Remove runtime-only fields from comparison
  ```
- `src/qmatsuite/project/snapshot.py` (lines 375-381): Export function strips prefix/outdir from step parameters.

**Conclusion**: Step-level prefix is **ignored** (calculation-level always wins), and runtime-only fields are **stripped** from import/show paths.

---

## Call Graph: QE Input Generation

```
CalculationRunner.run()
  └─> _execute_with_jobgraph()
       └─> QERecipe.materialize()  [src/qmatsuite/execution/recipes.py:92-159]
            └─> Creates JobGraph with Job objects (no input file generation yet)
                 
JobExecutor.execute()
  └─> qe_step_handler()  [src/qmatsuite/execution/handlers.py:37-143]
       └─> step.run()  [src/qmatsuite/calculation/step.py]
            └─> materialize_step_spec()  [src/qmatsuite/calculation/structure_steps.py:592-1653]
                 ├─> Load calculation context (lines 1013-1044)
                 │    └─> calculation_prefix = calc_model.meta.slug  [line 1035]
                 ├─> generate_qe_input_from_spec()  [line 1054]
                 └─> _inject_calculation_prefix_outdir()  [lines 1057-1065]
                      └─> Injects prefix into QEInput.namelists["CONTROL"].parameters["prefix"]  [line 362]
                           
                 └─> set_outdir_to_temp()  [line 1080]
                 └─> set_pseudo_dir_in_input()  [line 1100]
                 └─> QEInputGenerator.write_file()  [writes .in file]
```

**Injection order**:
1. **Prefix** injected via `_inject_calculation_prefix_outdir()` (line 1058) - **AFTER** `generate_qe_input_from_spec()`
2. **Outdir** injected via `set_outdir_to_temp()` (line 1080) - **AFTER** prefix injection
3. **Pseudo_dir** injected via `set_pseudo_dir_in_input()` (line 1100) - **AFTER** outdir injection

**All three are injected during materialization, before file write.**

---

## Conclusion: Current Behavior vs Desired Policy

**Question**: Does current behavior match desired policy?

**Answer**: **YES**, with one caveat.

**Policy alignment**:
- ✅ Prefix is **calc-level** (from `calculation.meta.slug`), not step-level
- ✅ Prefix is **NOT persisted** in step.yaml, calculation.yaml, or manifest
- ✅ Step-level prefix is **ignored** (calculation-level always wins)
- ✅ Runtime-only fields are **stripped** from import/show paths
- ✅ Injection is **schema-aware** (only injects if QE module schema defines prefix parameter)

**Caveat**:
- ⚠️ **No explicit policy document** found that defines "prefix must be calc-level only"
- ⚠️ The behavior is **consistent** across codebase, but the policy is **implicit** (enforced by code, not documented)

**Recommendation**: Document the policy explicitly:
- Prefix is calculation-level only (from `calculation.meta.slug`)
- Step-level prefix in step.yaml is ignored
- Prefix is runtime-only (not persisted)
- This ensures consistent prefix across all steps in a calculation

---

**Report End**














