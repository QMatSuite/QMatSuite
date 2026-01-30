# GEN/SPEC Cleanup Worklog

## Session 2: Comprehensive Legacy String Cleanup

### Objective
Remove ALL legacy naming patterns from codebase. No backwards compatibility.

### Patterns Being Fixed:
1. `step_type` → `step_type_spec` (for engine-specific) or `step_type_gen` (for generic)
2. `public_type` → `step_type_gen`
3. `machine_type` → `step_type_spec`
4. Dataclass `id:` fields → `ulid:` (for object's own ID)
5. `*_id` foreign keys → `*_ulid`

### Fixes Applied:

#### Session 1 (Earlier):
- Fixed `StepResult(step_type=...)` → `StepResult(step_type_spec=...)` in engine files
- Fixed `calculation.id` → `calculation.ulid` in Calculation class
- Fixed `meta.id` → `meta.ulid` across vault and src files
- Fixed `ResourceMeta` field access in test utilities
- Fixed `StepResultCompat` compatibility layer
- Fixed `RunStartedEvent.create()` parameter names
- Fixed workflow detection to use SPEC types via registry lookup
- Fixed PySCF chain execution `step_type_spec` key lookup

#### Session 2 (Current - Continued):

##### Fixes Applied:
1. **Engine files cleaned:**
   - `vasp_engine.py` - removed `public_type` fallback
   - `orca_engine.py` - renamed `steps_with_public_type` → `wrapped_steps`, fixed comments, fixed `.id` → `.ulid`
   - `executor.py` - fixed `step_type` → `step_type_spec` getattr patterns
   - `vasp_staging.py` - fixed step_type fallback
   - `reference_resolver.py` - fixed step_type and public_type patterns
   - `recipes.py` - fixed step_type and public_type patterns
   - `qc_engine_base.py` - fixed StepLike protocol `id` → `ulid`, fixed `step_ids` → `step_ulids`

2. **Workflow/Registry cleaned:**
   - `registry.py` - renamed `PUBLIC_TYPE_TOKENS` → `GEN_TYPE_TOKENS`
   - `registry.py` - renamed `get_token_for_public_type` → `get_token_for_gen_type`
   - `registry.py` - renamed `normalize_step_type_to_public` → `normalize_step_type_to_gen`
   - `templates.py` - cleaned step_type fallbacks, renamed `public_type` var → `gen_type`

3. **Driver recipes cleaned:**
   - `orca/recipe.py` - renamed `public_types` → `gen_types`
   - `pyscf/recipe.py` - renamed `public_types` → `gen_types`
   - `lammps/recipe.py` - renamed `public_type` → `gen_type`, fixed metadata keys
   - `cp2k/recipe.py` - renamed `public_type` → `gen_type`, fixed metadata keys
   - `vasp/recipe.py` - renamed `public_type` → `gen_type`
   - `qe/recipe.py` - renamed `public_type` → `gen_type`
   - `lammps/handler.py` - fixed `public_type` metadata key → `step_type_gen`
   - `vasp/staging.py` - fixed step_type fallback

4. **Core modules cleaned:**
   - `calc_identity.py` - renamed `machine_types` → `spec_types`, functions renamed
   - `resolution.py` - renamed `.id` property → `.ulid` on ResolvedResource
   - `structure_steps.py` - cleaned comments, renamed variables

5. **Presets/Integration cleaned:**
   - `variants_registry.py` - updated docstrings
   - `integration.py` - updated comments
   - `capability.py` - fixed step_type key lookup

6. **API/Service cleaned:**
   - `api/service.py` - fixed normalize_step_type_to_gen import and usage
   - `api/types/run.py` - removed step_id → step_ulid normalization (NO compat)
   - `dto_mapping.py` - removed fallback patterns

7. **Daemon cleaned:**
   - `daemon/server.py` - fixed `calculation_resolved.id` → `.ulid`, fixed syntax error
   - `daemon/compat.py` - removed `step_type` compat (NO compat)

8. **CLI cleaned:**
   - `cli/main.py` - fixed step_dict keys, step_type usage

9. **Snapshot cleaned:**
   - `project/snapshot.py` - removed step_type migration, now requires step_type_spec

10. **PySCF chain cleaned:**
    - `engines/pyscf/chain.py` - renamed `machine_type` → `spec_type` variables

##### Remaining Intentional Patterns:
- `job.id` - Job identifiers in JobGraph (not ULIDs, e.g., "step_00", "s_t")
- `request.id` - RPC request identifiers
- DTO `.id` properties - API compatibility (return `.ulid` values)
- `calculation.structure_id` - Widely used API property (returns ULID, needs separate rename pass)

#### Session 3 (Current):

##### Syntax Errors Fixed (from batch replace):
- `project_utils.py:610` - fixed `.get("step_type_spec"), "")` → `.get("step_type_spec", "")`
- `pyscf_engine.py:369` - fixed extra closing paren
- `pyscf_engine.py:493` - fixed duplicate get call with extra paren
- `calculation.py:377-379` - fixed malformed multi-line get chain
- `api/service.py:2998, 3716, 4687, 7137, 7409` - fixed misplaced comma in .get() calls
- `daemon/server.py:3914, 4158` - fixed extra closing parens
- `daemon/jobs.py:259, 263, 414, 417` - fixed extra closing parens
- `cli/main.py:1893, 1905, 2216, 2233` - fixed extra closing parens
- `engines/pyscf/__main__.py:32` - fixed misplaced comma
- `project/snapshot.py:789` - fixed nested get with multiple args
- `history/run_revision.py:448` - fixed misplaced comma
- `engines/pyscf/runner.py:929` - fixed misplaced comma

##### Test Files Updated:
1. **Import name updates:**
   - `test_qc_chain_tokens.py` - `PUBLIC_TYPE_TOKENS` → `GEN_TYPE_TOKENS`, `get_token_for_public_type` → `get_token_for_gen_type`
   - `test_calc_identity.py` - `_infer_engine_family_from_machine_types` → `_infer_engine_family_from_spec_types`, `machine_types` → `spec_types`

2. **ResolvedResource.id → .ulid:**
   - `test_delete_calculation_daemon.py` - `calc_resource.id` → `.ulid`, `resolved.id` → `.ulid`
   - `test_api_service.py` - `calc_resource.id` → `.ulid`
   - `test_update_step_params_persistence.py` - `calc_result.id` → `.ulid`
   - `test_promote_relax_structure.py` - `calc_result.id` → `.ulid`, `step_result.id` → `.ulid`
   - `recipes/structure_flow.py` - `calc_result.id` → `.ulid`
   - `recipes/world.py` - `calc_result.id` → `.ulid`
   - `test_relax_promote_e2e.py` - all `*_result.id` → `.ulid`
   - `test_pyscf_relax_real.py` - `calc_result.id`, `relax_step_result.id` → `.ulid`
   - `test_relax_e2e.py` - `calc_result.id`, `step_result.id` → `.ulid`
   - `test_qe_relax_real.py` - `calc_result.id`, `relax_step_result.id` → `.ulid`
   - `test_vasp_project_e2e.py` - `calc_result.id` → `.ulid`
   - `test_api_parameter_scan_persistence.py` - `calc_result.id` → `.ulid`

3. **step_type → step_type_spec:**
   - `test_calculation_importers.py` - `result.step_type` → `result.step_type_spec`, YAML key `step_type` → `step_type_spec`

### Decision Log:
- Function parameters CAN use simple names (step_type, step_id) per rules
- Dataclass fields MUST use canonical names (step_type_spec, ulid)
- Dict keys in API responses need to use canonical names
- `_vault` files are isolated legacy archive - left as-is
- NO backwards compatibility - removed all fallback/normalization patterns

### Test Progress (Session 3):
- **Initial**: 222 failed, 23 errors
- **After syntax fixes**: 221 failed, 7 errors
- **After test file updates**: 219 failed, 4 errors
- **Passes**: 2737
- **Skipped**: 29

##### Additional test file fixes (Session 3 cont.):
- `test_qc_chain_tokens.py` - `TestPublicTypeTokens` → `TestGenTypeTokens`
- `test_calc_identity.py` - function name and variable renames
- `test_delete_calculation_daemon.py` - `.id` → `.ulid` on ResolvedResource
- `test_gui_job_and_step_flows.py` - `step.step_type` → `step.step_type_spec`
- `test_project_and_cli.py` - `step.step_type` → `step.step_type_spec`
- `test_calculation_read.py` - StepDTO assertions
- `test_si_dos_calculation_cli.py` - CLI output assertions `step_type:` → `step_type_spec:`
- `test_snapshot_id_regeneration.py` - snapshot key lookups
- `qe_step_verification.py`, `qe_step_runner.py` - StepResult attributes
- `test_pw_quick_tests_ci.py` - StepResult attributes
- `test_orca_relax_real.py` - `.id` → `.ulid`
- `test_project_snapshot.py` - StructureStepSpec attributes
- `test_structure_steps.py` - test data and assertions

