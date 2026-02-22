# Distribution Step 1 Foundation Worklog (2026-02-22)

## Scope and constraints followed

- Scope: Step 1 foundation only (paths/dependencies/lazy imports/package-data for distribution readiness).
- Full-test rule enforced on every full run:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Waited for full completion before moving to next major step.
- Kept non-network/OPTIMADE failures as actionable; treated network/OPTIMADE failures as transient external failures.

## Starting state at handoff

- Existing Step 1 work was already partially implemented (paths refactor/tests/dependency edits/lazy import edits).
- Remaining gaps identified at handoff:
  - `pyproject.toml` package-data only covered `data/*.json` (missing nested driver JSON).
  - Daemon import startup still above target in recent measurement (~0.65-0.70s).
  - Worklog detail depth insufficient for retrospective review.

## What I did (chronological)

### 1) Verified current state and unresolved items

- Reviewed modified files and current `pyproject.toml`.
- Re-ran heavy-import scan for module-level `pymatgen/matplotlib/scipy`.
- Confirmed package-data gap and startup timing issue persisted.

### 2) Profiled daemon import to isolate startup bottleneck

- Ran:
  - `PYTHONPROFILEIMPORTTIME=1 python -c "from quantumvitas.daemon.server import main"`
- Findings:
  - `quantumvitas.io.structure_io` was a major import hotspot (historically pulled pymatgen stack early).
  - `pymatgen/scipy` still entered via LAMMPS path during daemon import chain.

### 3) Lazy-import fixes applied

#### File: `src/quantumvitas/io/structure_io.py`

- Problem:
  - Module-level `pymatgen` imports caused heavyweight dependency loading during daemon import.
- Change:
  - Removed module-level `pymatgen` imports.
  - Added `TYPE_CHECKING` gated type imports.
  - Moved `from pymatgen.core import Structure as PMGStructure, Molecule as PMGMolecule` into `read_structure()`.
  - Removed unused `Element`/`Lattice` module-level imports.
- Result:
  - `quantumvitas.io.structure_io` import footprint dropped substantially in profile output.

#### File: `src/quantumvitas/io/lammps_data.py`

- Problem:
  - Module-level `from pymatgen.core import Structure, Molecule` caused early pymatgen load via LAMMPS import path.
- Change:
  - Replaced module-level imports with `TYPE_CHECKING` declarations.
  - Added function-local imports where runtime class objects are actually required:
    - `write_lammps_data()` for `isinstance(..., Structure)`
    - `read_lammps_data()` before constructing `Structure(...)`
- Result:
  - Daemon import path no longer pulls pymatgen/scipy on cold import.

### 4) Startup measurements before/after

- Before these final lazy-import edits (from session state):
  - `time python -c "from quantumvitas.daemon.server import main"` around `0.65-0.70s`.
- After edits:
  - `/usr/bin/time -p python -c "from quantumvitas.daemon.server import main"`
  - Observed: `real 0.29` (below target 0.50s).

### 5) Package-data audit and fix

- Audited runtime resources:
  - `src/quantumvitas/resources` does not exist in current tree.
  - Runtime data files found in:
    - `src/quantumvitas/data/*.json`
    - `src/quantumvitas/drivers/*/data/*.json`
- Problem:
  - `pyproject.toml` had only:
    - `"quantumvitas" = ["data/*.json"]`
- Change:
  - Updated `pyproject.toml` package-data to:
    - `data/*.json`
    - `drivers/**/data/*.json`

## Tests and verification runs

### Full run after lazy-import changes (required command)

- Command:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- One run produced:
  - `40 failed, 6408 passed, 7 skipped` in ~6m31s
- Failure class:
  - All failures were online/network/OPTIMADE/PubChem integration tests.
  - No local deterministic regression failures detected in that run.

### Full run after package-data update (required command)

- Command:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Result:
  - `6451 passed, 4 skipped, 976 warnings` in `374.46s` (~6m14s)
- Interpretation:
  - Full suite green in this environment after final changes.

## Issues encountered and how I handled them

1. Import-profile ambiguity after first lazy change
- Symptom: startup remained ~0.70s after `io/structure_io.py` changes.
- Action: used profile logs with line-context to identify next source (`lammps_data` path).
- Resolution: moved `pymatgen` imports in `lammps_data.py` to function scope; startup dropped to 0.29s.

2. Transient full-suite network failures
- Symptom: full run showed 40 failures concentrated in online OPTIMADE/PubChem tests.
- Action: enumerated failed test set to confirm failure class.
- Resolution: treated as external-network class; reran required full suite after next code step; run returned fully green.

3. Patch context mismatch during an edit
- Symptom: initial patch attempt on `structure_steps.py` failed due stale context assumptions.
- Action: re-read file header and confirmed the import had already been migrated (no further edit needed there).

## Files changed in this segment

- `src/quantumvitas/io/structure_io.py`
  - Converted pymatgen imports to function-local + TYPE_CHECKING.
- `src/quantumvitas/io/lammps_data.py`
  - Converted pymatgen imports to function-local + TYPE_CHECKING.
- `pyproject.toml`
  - Expanded package-data patterns to include nested driver JSON.
- `docs/history/worklogs/DISTRIBUTION_STEP1_FOUNDATION_2026-02-22_WORKLOG.md`
  - Added this detailed retrospective.

## Remaining validation to complete in this session

- Non-editable install validation block (`pip install .` in clean venv + import/CLI checks) and logging results.
- Final checklist command block execution and result recording.

---

## 2026-02-22 (Resources SSOT migration follow-up)

### User directives captured (must-follow)
- Full-suite command policy: always use `.venv` and run
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Wait for the full run to finish before proceeding.
- Keep a detailed retrospective-quality worklog in `docs/history/worklogs` with failures, attempted approaches, and decision rationale.
- `fastmcp` must remain in core dependencies; no optional behavior-gating for MCP availability.
- Resource single source of truth must be `src/quantumvitas/resources/` only.
- Top-level `<repo_root>/resources/` must be removed only after content parity + callsite migration verification.

### State found at resume
- The tree already contained both:
  - `<repo_root>/resources/`
  - `<repo_root>/src/quantumvitas/resources/`
- Parity check from prior step:
  - root_count=316
  - pkg_count=314
  - only in root = `.DS_Store` files
  - only in package = `__init__.py`
- Conclusion: runtime content parity is effectively complete; remaining risk is stale path callsites.

### Deep search completed before edits
- Scanned runtime source and tests for repo-style resource resolution.
- Runtime callsites requiring migration were confirmed in:
  - `src/quantumvitas/core/resources.py`
  - `src/quantumvitas/demo_store/translator.py`
  - `src/quantumvitas/project/snapshot.py`
  - `src/quantumvitas/calculation/structure_steps.py`
  - `src/quantumvitas/pseudo/registry.py`
- Additional dual-mode helpers reviewed:
  - `src/quantumvitas/core/pseudo_config.py`
  - `src/quantumvitas/drivers/qe/engine/qe_pseudopotentials.py`
- Test files with hardcoded `.../resources/...` paths identified (37 files). These will be migrated to package-resource resolution (`get_resources_dir`) to avoid reliance on deleted top-level resources.

### Decision rationale
- Do **not** preserve repo-root `resources/` fallback in runtime path resolution because it creates split-brain resource authority and sync burden.
- Keep dev/install dual-mode by resolving resources through the package location (`src/quantumvitas/resources` in editable dev; site-packages in wheel install).
- Migrate tests to the same resolver so test assumptions match distribution behavior.

### Execution plan from this point
1. Patch runtime source callsites first (resource resolution SSOT).
2. Patch tests in batches, replacing direct `repo_root / "resources"` style paths with resolver-based paths.
3. Remove top-level `<repo_root>/resources/`.
4. Run the required full test command once after migration batch.
5. Record pass/fail details and any residual issues.

### Runtime and test migration (resources SSOT execution)

#### Runtime source changes applied
- `src/quantumvitas/core/resources.py`
  - Removed repo-root-first resolution; resources now resolve from package location only.
- `src/quantumvitas/demo_store/translator.py`
  - `_resolve_pseudo_info()` now reads pseudos from `get_resources_dir()/pseudo`.
- `src/quantumvitas/project/snapshot.py`
  - Removed manual upward repo search for `resources/pseudo`; uses `get_resources_dir()`.
- `src/quantumvitas/calculation/structure_steps.py`
  - Removed `project_root/resources/pseudo` candidates; kept `project/pseudo` + bundled package pseudo.
- `src/quantumvitas/pseudo/registry.py`
  - Manifest/index lookup now uses `get_resources_dir()/pseudo_libinfo` directly.
- `src/quantumvitas/core/pseudo_config.py`
  - `_find_quantumvitas_root()` simplified to derive from package resources root.
- `src/quantumvitas/drivers/qe/engine/qe_pseudopotentials.py`
  - `_find_quantumvitas_root()` aligned to package resources root.
- `src/quantumvitas/core/pseudo_libinfo.py`
  - `load_pseudo_libinfo_bundle()` now supports both legacy repo-root and new package-root candidate shapes when explicit `repo_root` is provided, defaulting to package resources.

#### Test migration (hardcoded repo `resources/` path removal)

Patched to use `get_resources_dir()` where resources are read:
- CLI tests:
  - `tests/cli/conftest.py`
  - `tests/cli/test_cli_output_contracts.py`
  - `tests/cli/test_cli_show_command_integration.py`
  - `tests/cli/test_si_bands_auto_calculation_cli.py`
  - `tests/cli/test_si_bands_manual_calculation_cli.py`
  - `tests/cli/test_si_dos_calculation_cli.py`
  - `tests/cli/test_si_dos_calculation_comprehensive.py`
- Core test infra:
  - `tests/conftest.py` (allowed write paths text + bundled pseudo path)
- Daemon contract:
  - `tests/daemon/contract/conftest.py`
- Gate tests:
  - `tests/gates/test_demo_generated.py`
  - `tests/gates/test_demo_integrity.py`
  - `tests/gates/test_ref_analysis_sweep.py`
  - `tests/gates/test_ref_packs.py`
  - `tests/gates/test_gen_spec_convergence_gate.py` (demo search path for rg)
  - `tests/gates/test_no_legacy_identity_fields.py` (resource scan roots + allowlist path)
- Integration tests:
  - `tests/integration/test_abinit_execution.py`
  - `tests/integration/test_lammps_chain.py`
  - `tests/integration/test_lammps_eam_md.py`
  - `tests/integration/test_lammps_incremental_skip.py`
  - `tests/integration/test_lammps_long_smoke.py`
  - `tests/integration/test_lammps_restart_parallel.py`
  - `tests/integration/test_pseudo_unification.py`
  - `tests/integration/test_pyscf_execution.py`
  - `tests/integration/test_si_bands_calculation.py`
  - `tests/integration/test_si_dos_calculation.py`
  - `tests/integration/test_yambo_execution.py`
- Integrity tests:
  - `tests/integrity/authoring/test_roundtrip_b.py`
- Unit tests:
  - `tests/unit/test_demo_schema_validation.py`
  - `tests/unit/test_lammps_potentials.py`
  - `tests/unit/test_project_snapshot.py`
  - `tests/unit/test_pseudo_libinfo_bundle_integrity.py`
  - `tests/unit/test_pseudo_libinfo_loader.py`
  - `tests/unit/test_pseudo_no_repo_root.py`
  - `tests/unit/test_pseudo_provenance.py`
  - `tests/unit/test_pseudo_sha_token_normalization.py`
  - `tests/unit/test_pseudo_species_map_resolution.py` (renamed temp fixture path from `resources/pseudo` to `bundled/pseudo`)
  - `tests/unit/test_pyscf_integration.py`
  - `tests/unit/test_w90_parameter_rendering.py`
  - `tests/unit/test_wannier90_integration.py`

#### Verification searches after migration
- `rg -n '/\s*"resources"\s*/' tests --glob '*.py'`
  - Remaining hit is only a tmp fixture path in `tests/unit/test_pseudo_libinfo_bundle_integrity.py` (`tmp_path/resources/pseudo_libinfo`) used for synthetic corruption test setup, not repo-root runtime lookup.
- `rg -n 'repo_root\s*/\s*"resources"|REPO_ROOT\s*/\s*"resources"|Path\(__file__\).*"resources"' tests --glob '*.py'`
  - No remaining matches.

#### Sanity test run before full suite
- Command:
  - `source .venv/bin/activate && python -m pytest tests/unit/test_pseudo_libinfo_loader.py tests/unit/test_pseudo_no_repo_root.py tests/cli/test_cli_output_contracts.py tests/gates/test_demo_generated.py tests/integration/test_si_dos_calculation.py -q --tb=short`
- Result:
  - `12 passed, 1 warning` in `109.90s`.
- Notes:
  - Warning is expected species_overrides compatibility warning during one CLI run; no failures.

#### Issues encountered in this segment
1. Patch context drift in one integration file
- Symptom: initial patch for `tests/integration/test_lammps_incremental_skip.py` failed due import-line mismatch.
- Action: opened file head, corrected exact import block context, re-applied patch.
- Result: patch applied cleanly.

2. Avoiding false-positive migration metrics
- Some remaining `resources/...` mentions are docstrings/comments or intentional tmp test fixture paths.
- Action: separated code path joins from documentation references in search criteria.
- Result: confirmed runtime/test executable path joins are migrated.

## 2026-02-22 (Full-suite failure triage and root-cause fixes)

### Full run command and result
- Command:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Result:
  - `5 failed, 6446 passed, 4 skipped` (~6m40s)
- Deterministic failures:
  1. `tests/drivers/qmcpack/test_qmcpack_driver.py::TestQMCPACKResolver::test_resolver_not_found`
  2. `tests/unit/test_engine_discovery.py::TestSearchBundled::test_finds_binary_in_project_root`
  3. `tests/unit/test_engine_discovery.py::TestSearchBundled::test_returns_none_when_not_found`
  4. `tests/unit/test_pseudopotential_resolution.py::TestPseudopotentialResolutionEdgeCases::test_pp_resolution_missing_element_reports_clear_error`
  5. `tests/gates/test_no_deep_domain_import.py::test_no_cross_domain_deep_imports`

### Critical forensic finding: why `src/quantumvitas/pseudo/` was repeatedly deleted
- Symptom observed:
  - `ModuleNotFoundError: No module named 'quantumvitas.pseudo'`
  - Coverage warnings at report time: `No source for code: src/quantumvitas/pseudo/*.py`
  - `git status` showed `D src/quantumvitas/pseudo/__init__.py` and siblings.
- Root cause:
  - Earlier change made `_find_quantumvitas_root()` return `get_resources_dir().parent`, i.e. `src/quantumvitas` in editable dev mode.
  - Test `tests/unit/test_pseudo_no_repo_root.py` uses `_find_quantumvitas_root()` and deletes `<root>/pseudo` as cleanup of forbidden `repo_root/pseudo`.
  - With the changed root semantics, that cleanup path became `src/quantumvitas/pseudo`, i.e. the runtime package itself.
- Fix strategy:
  - Restore `_find_quantumvitas_root()` semantics to return actual repo root in dev checkout.
  - Keep installed-mode fallback to package root only when repo root cannot be found.

### Code fixes applied

1. **Bundled engine discovery determinism**
- File: `src/quantumvitas/core/engines/discovery.py`
- Change:
  - `_search_bundled()` now searches only `<project_root>/.qmatsuite/engines` when `project_root` is explicitly provided.
  - Managed app-data fallback is used only when `project_root is None`.
- Why:
  - Prevents unit tests with tmp project roots from being polluted by developer-local global engines.

2. **Root resolver semantics corrected (dev vs installed)**
- File: `src/quantumvitas/core/pseudo_config.py`
- Change:
  - `_find_quantumvitas_root()` now:
    - First detects repo root via `pyproject.toml + src/quantumvitas` upward walk.
    - Falls back to package root (`get_resources_dir().parent`) only when repo root is absent.
- Why:
  - Prevents accidental targeting of `src/quantumvitas/pseudo` as “repo pseudo”.

3. **Driver-side root resolver unified**
- File: `src/quantumvitas/drivers/qe/engine/qe_pseudopotentials.py`
- Change:
  - Local `_find_quantumvitas_root()` now delegates to canonical `core.pseudo_config._find_quantumvitas_root()`.
- Why:
  - Eliminates resolver divergence and duplicate semantics.

4. **Pseudo strict-mode testability restored without breaking distribution mode**
- File: `src/quantumvitas/core/pseudo.py`
- Changes:
  - In `ensure_qe_pseudos()`, default `system_pseudo_dir` resolution now uses `get_system_pseudo_dir()`.
  - `get_system_pseudo_dir()` now gates on `_find_quantumvitas_root()` and returns `None` when root resolver is unavailable.
- Why:
  - Restores ability for tests to monkeypatch `_find_quantumvitas_root` to force “no bundled pseudo” edge cases.
  - Still supports distribution mode via installed-package fallback root behavior.

5. **Gate compliance: no deep cross-domain imports**
- Files:
  - `src/quantumvitas/engine/lammps_engine.py`
  - `src/quantumvitas/engine/lammps_writer.py`
- Change:
  - Replaced direct deep import `quantumvitas.core.resources.get_resources_dir` with `quantumvitas.core.public.get_resources_dir`.
- Why:
  - Satisfies `test_no_deep_domain_import` contract.

6. **QMCPACK resolver test isolation from machine-local managed engines**
- File: `tests/drivers/qmcpack/test_qmcpack_driver.py`
- Change:
  - `test_resolver_not_found` now sets `QMATSUITE_HOME` to an isolated tmp path.
- Why:
  - Prevents false negatives when developer machine has managed QMCPACK binaries under local app-data.

7. **Recovered deleted pseudo package files**
- Action:
  - Restored `src/quantumvitas/pseudo/` from `HEAD` after root-resolver fix.
- Verification:
  - Directory exists post-tests with all expected files.

### Targeted regression verification run
- Command:
  - `source .venv/bin/activate && python -m pytest tests/drivers/qmcpack/test_qmcpack_driver.py::TestQMCPACKResolver::test_resolver_not_found tests/unit/test_engine_discovery.py::TestSearchBundled::test_finds_binary_in_project_root tests/unit/test_engine_discovery.py::TestSearchBundled::test_returns_none_when_not_found tests/unit/test_pseudopotential_resolution.py::TestPseudopotentialResolutionEdgeCases::test_pp_resolution_missing_element_reports_clear_error tests/gates/test_no_deep_domain_import.py::test_no_cross_domain_deep_imports tests/unit/test_pseudo_no_repo_root.py::test_repo_root_pseudo_never_created -v --tb=short`
- Result:
  - `6 passed`

### Next action
- Re-run full suite with required command and wait for completion before proceeding.

## 2026-02-22 (Pseudo/Demo/Metadata special-care migration + old resources decommission)

### User directive focus for this segment
- Treat pseudo/demo/metadata pipelines as special-critical and validate deeply.
- Migrate all remaining dev tooling to the SSOT resource root:
  - `src/quantumvitas/resources/`
- Verify no remaining runtime/tool callsites rely on top-level repo `resources/`.
- Delete `<repo_root>/resources` after migration verification.
- Run required full pytest command and commit milestone if green.

### Deep callsite audit done before final deletion

#### Runtime callsite sweep (pseudo/demo/metadata)
Commands run:
- `rg -n "root\s*/\s*\"resources\"|repo_root\s*/\s*\"resources\"|REPO_ROOT\s*/\s*\"resources\"|project_root\s*/\s*\"resources\"|Path\(__file__\).*\"resources\"" src/quantumvitas --glob '*.py'`
- `rg -n "get_resources_dir\(|pseudo_libinfo|demo_projects|resources/pseudo|resources/demo_projects" src/quantumvitas/core src/quantumvitas/pseudo src/quantumvitas/demo_store src/quantumvitas/project src/quantumvitas/drivers --glob '*.py'`

Findings:
- Functional pseudo registry lookup still had an upward walk pattern via `current / "resources" / "pseudo_libinfo"` in `src/quantumvitas/pseudo/registry.py`.
- Pseudo libinfo loader (`src/quantumvitas/core/pseudo_libinfo.py`) had multi-candidate root handling that could include `root/resources/pseudo_libinfo` when `repo_root` is explicitly passed.
- Demo/ref-pack runtime loading already uses `get_resources_dir()` and is distribution-safe.

#### Tools callsite sweep
Command run:
- `rg -n "repo_root\s*/\s*\"resources\"|REPO_ROOT\s*/\s*\"resources\"|Path\(__file__\).*\"resources\"|\brepo/resources\b|resources/demo_projects|resources/pseudo|resources/qe_docs_raw|\bresources/pseudo_libinfo\b" tools --glob '*.py' --glob '*.sh' --glob '*.md'`

Findings:
- Multiple dev scripts/docs still pointed to old top-level `resources/` paths.
- These were migrated to `src/quantumvitas/resources` (details below).

### Changes applied (with rationale)

#### Runtime pseudo/demo/metadata
1. `src/quantumvitas/pseudo/registry.py`
- Replaced upward repo/resource search with package-resource resolution:
  - now loads from `get_resources_dir() / "pseudo_libinfo"`
- Why:
  - eliminates dependence on top-level repo `resources/` layout
  - aligns runtime resolution with installed package behavior.

2. `src/quantumvitas/core/pseudo_libinfo.py`
- Tightened `repo_root` handling:
  - repo-root case prefers `root/src/quantumvitas/resources/pseudo_libinfo`
  - non-repo roots still support package/test layouts (`root/resources/pseudo_libinfo`, etc.)
- Why:
  - avoids accidental fallback to deprecated repo-top-level `resources/` when a real repo root is passed,
  - preserves package-root/test-root compatibility required by existing callsites/tests.

3. `src/quantumvitas/demo_store/manifest.py`
- Updated generated metadata `output_file` to `src/quantumvitas/resources/demo_projects/...`.

4. Documentation/comment accuracy updates to reduce operator confusion:
- `src/quantumvitas/demo_store/__init__.py`
- `src/quantumvitas/demo_store/ref_packs.py`
- `src/quantumvitas/core/pseudo_runtime.py`
- `src/quantumvitas/core/pseudo_libinfo.py`

#### Dev tools/scripts migration to SSOT resources
5. `tools/purge_demos.sh`
- switched to `src/quantumvitas/resources/demo_projects` and added missing-dir guard.

6. `tools/snapshot_qe_docs.py`
- default output now `src/quantumvitas/resources/qe_docs_raw`.

7. `tools/build_pseudo_libinfo_bundle.py`
- installation target moved to `src/quantumvitas/resources/pseudo_libinfo/<tag>/`.

8. `tools/import_tutorial_datasets.py`
- introduced `get_resources_root(repo_root)` and replaced old `repo_root/resources/...` usage.
- output/pseudo directories now under `src/quantumvitas/resources/...`.
- updated internal comments/docs accordingly.

9. `tools/run_lammps_long_smoke.py`
- centralized constants for repo/resources/test-data roots.
- potential file lookup now from `src/quantumvitas/resources/lammps/potentials`.

10. `tools/test_silicon_wannier90_demo_logging.py`
- demo lookup now uses `get_resources_dir()/demo_projects`.
- added robust candidate fallback list to avoid hard fail on renamed demo IDs.

11. Demo-store generation tooling:
- `tools/demo_store/generate_all.py`
- `tools/demo_store/generate_ref_packs.py`
- `tools/demo_store/generate_ref_packs_realrun.py`
- `tools/demo_store/create_qe_corpus.py`
- `tools/demo_store/augment_corpus.py`
- `tools/demo_store/generate_corpus_index.py`

All migrated to SSOT resource paths and updated metadata source strings where applicable.

12. Tooling docs update:
- `tools/README_import_tutorials.md`

### Issues encountered + handling
1. Potential ambiguity between “old repo resources path” and “package root resources path”
- Problem:
  - `root/resources/...` can mean deprecated repo-top-level layout OR valid package-root layout depending on `root`.
- Handling:
  - In `load_pseudo_libinfo_bundle(repo_root=...)`, added repo-root detection to avoid deprecated lookup when `repo_root` is an actual checkout root.
  - Kept package/test compatibility for non-repo roots.

2. Legacy demo filename drift in debug script
- Problem:
  - `tools/test_silicon_wannier90_demo_logging.py` pointed at `silicon_wannier90_demo.yml`, not always present.
- Handling:
  - Added ordered fallback candidates (`silicon_wannier90_demo.yml`, `qe_w90_silicon.yml`, `qe_silicon_wannier.yml`, `qe_diamond_wannier.yml`, `qe_copper_wannier.yml`).

### Current verification state (before final full suite)
- Migration patch set is applied and staged in working tree (not committed yet).
- Next required actions in this session:
  1. Run targeted pseudo/demo/metadata tests for quick confidence.
  2. Delete `<repo_root>/resources`.
  3. Run required full suite command:
     `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  4. If green, commit milestone.

### Post-migration validation before full suite

#### Targeted pseudo/demo/metadata suite (pre-deletion)
Command:
- `source .venv/bin/activate && python -m pytest tests/unit/test_pseudo_libinfo_loader.py tests/unit/test_pseudo_libinfo_bundle_integrity.py tests/unit/test_pseudo_no_repo_root.py tests/unit/test_pseudo_provenance.py tests/mcp/test_stage10.py tests/gates/test_demo_generated.py -v --tb=short`

Result:
- `205 passed, 28 warnings` in `26.36s`

#### Resource SSOT parity check + deletion
- Compared old vs new resource trees:
  - old files: 316
  - new files: 314
  - differences only:
    - old-only: `.DS_Store` files
    - new-only: `src/quantumvitas/resources/__init__.py`
- Deleted old top-level resources folder:
  - `rm -rf <repo_root>/resources`
  - verified absent (`resources_missing`).

#### Post-deletion smoke slice
Command:
- `source .venv/bin/activate && python -m pytest tests/unit/test_pseudo_no_repo_root.py tests/unit/test_pseudo_libinfo_loader.py::test_load_pseudo_libinfo_bundle tests/mcp/test_stage10.py::TestSearchDemos::test_search_all_returns_demos tests/gates/test_demo_generated.py -v --tb=short`

Result:
- `7 passed` in `7.91s`

Interpretation:
- Pseudo lookup, bundled libinfo loading, demo discovery, and demo manifest integrity all work after removing `<repo_root>/resources`.

### Next required gate
- Run mandatory full suite command and wait for completion:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

### Retest after gate fixes (2026-02-22, post-compact continuation)

Command:
- `source .venv/bin/activate && python -m pytest tests/gates/test_corpus_index.py::test_redistributable_assets_present tests/gates/test_no_sensitive_paths.py::TestNoSensitivePaths::test_no_sensitive_identifiers -v --tb=short`

Result:
- `2 passed` in `10.30s`

Notes:
- Confirms both previously failing gates are fixed after:
  - corpus source path migration to `src/quantumvitas/resources/pseudo`
  - sensitive-path sanitization in active worklogs
- Next action: rerun the required full suite command and wait for completion before further edits.

### Mandatory full-suite rerun (post deletion + gate fixes)

Command (required by user rule):
- `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

Result:
- `6451 passed, 4 skipped, 968 warnings` in `386.59s` (`0:06:26`)
- Exit code: `0`

Notes:
- This validates the repo after deleting top-level `<repo_root>/resources` and migrating pseudo/demo/metadata references.
- Accepted non-fatal noise: expected integration warnings (e.g., `optimade` live/network variability class and mark/deprecation warnings), no hard failures.

### Post-full-run path audit (pseudo/demo/metadata + tools)

Checks:
- `if [ -d resources ]; then echo resources_exists; else echo resources_missing; fi` -> `resources_missing`
- `rg -n "repo_root\\s*/\\s*['\" ]resources|REPO_ROOT\\s*/\\s*['\" ]resources|get_repo_root\\(\\)\\s*/\\s*['\" ]resources" src/quantumvitas --glob '*.py'` -> no matches
- Broad `resources/` grep in `src/quantumvitas`, `tools`, `tests` shows remaining occurrences are either:
  - explicit new SSOT path strings (`src/quantumvitas/resources/...`), or
  - human-facing comments/docstrings/messages (no repo-top-level path resolution code).

Conclusion:
- No active runtime/tool code path depends on deleted top-level `<repo_root>/resources`.
- Runtime SSOT for bundled assets is `src/quantumvitas/resources/`.

### Wording cleanup (clarify migrated resource layout)

Updated comments/docstrings to remove old top-level `resources/` wording ambiguity:
- `tests/daemon/contract/conftest.py`
- `tests/daemon/contract/test_realrun_si_scf.py`
- `tests/mcp/test_stage10.py`
- `tests/unit/test_pseudo_no_repo_root.py`
- `tests/gates/test_no_legacy_identity_fields.py`
- `src/quantumvitas/api/service.py`

### Sanity tests after wording updates

Command:
- `source .venv/bin/activate && python -m pytest tests/unit/test_pseudo_no_repo_root.py tests/mcp/test_stage10.py::TestSearchDemos::test_search_all_returns_demos tests/gates/test_no_legacy_identity_fields.py::TestNoLegacyIdentityFields::test_no_forbidden_keys_in_yaml_json_resources -v --tb=short`

Result:
- `3 passed` in `11.63s`

Interpretation:
- Pseudo invariant, demo discovery, and resource-gate scan remain green after final clarity edits.

## Appendix: Merged From Root WORKLOG.md (2026-02-22)

# Distribution Step 1 Worklog

Date: 2026-02-22
Repo: <repo_root>

## Session Scope
Implement Distribution Step 1 foundation only:
1. `paths.py` foundation refactor + caller migration + tests
2. Remove dead dependencies in `pyproject.toml`
3. Convert heavy imports to lazy imports
4. Fix package data for non-editable pip installs

Out of scope (explicitly not touched): engine registry (`engines.json` implementation), micromamba workflows, Electron/TypeScript, publishing.

## Mandatory Reading Completed
- Read full design doc: `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` (1509 lines)
- Re-read required sections:
  - §2.3 Path Resolution Design
  - §4.2 Dependency Audit Results
  - §4.5 Electron + Embedded Python Integration
  - Appendix B Dependency Inventory
- Read current implementation:
  - `src/quantumvitas/core/paths.py`
  - `pyproject.toml`
- Read test/CI setup:
  - `pytest --co -q` (baseline run)
  - `.github/workflows/tests.yml`

## Initial Plan
1. Map all path helper callers in `src/quantumvitas` and `tests` before edits.
2. Implement 4-level resolution chain in `src/quantumvitas/core/paths.py` with dev-mode compatibility preserved.
3. Migrate direct callers that still anchor on `get_repo_root() / ".qmatsuite"` to `get_app_data_dir()`.
4. Add/adjust tests for env overrides, dev mode, electron mode, pip fallback, cache resolution, and derived directories.
5. Run `pytest` after Task 1.
6. Remove dead dependencies (`ase`, `beautifulsoup4`) and optional `pyscf` extra entries in `pyproject.toml`; verify via grep and run `pytest` after each sub-step.
7. Measure daemon import startup (before).
8. Convert module-level heavy imports (`pymatgen`, `matplotlib`, `scipy`) to lazy imports file-by-file, running `pytest` after each file.
9. Measure daemon import startup (after).
10. Audit runtime resources, fix package-data patterns in `pyproject.toml`, validate non-editable install in clean venv.
11. Run final verification checklist and record all outcomes.

## Baseline Environment Notes
- Git working tree was already dirty before this session:
  - `M docs/plans/DEFERRED_ITEMS.md`
  - `?? docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md`
  - `?? docs/history/worklogs/DISTRIBUTION_DESIGN_V2_WORKLOG.md`
  - `?? docs/history/worklogs/DISTRIBUTION_DESIGN_V3_WORKLOG.md`
  - `?? docs/history/worklogs/MCP_CLOSEOUT_DISTRIBUTION_DESIGN_WORKLOG.md`
- `pytest --co -q` baseline reported:
  - `6424 tests collected, 1 error`
  - Collection error in `tests/mcp/test_terminal_chart.py` due missing module `plotext`
  - This is an environment/dependency state issue to correct before full test validation.

## Decision Log (live)
- No listed AGENTS skill was applicable (`skill-creator` and `skill-installer` are unrelated to requested implementation).

## Task 1a: Caller Blast Radius Map (pre-change)

### Direct path helper usage in `src/quantumvitas/`
- `src/quantumvitas/core/paths.py`
  - Defines and uses: `get_repo_root`, home helpers, tmp helpers
- `src/quantumvitas/drivers/vasp/engine/vasp_potcar.py`
  - Uses `get_repo_root` as fallback to locate bundled POTCAR resources
- `src/quantumvitas/drivers/qe/engine/qe_resolver.py`
  - Imports and calls `get_repo_root` for internal QE engine directory discovery
- `src/quantumvitas/core/engines/vasp_resolver.py`
  - Defines local `_get_repo_root()` and depends on repo-root anchored defaults
- `src/quantumvitas/core/pseudo_options.py`
  - Uses `home_pseudo_libraries_dir`
- `src/quantumvitas/core/library_manager.py`
  - Uses `home_pseudo_libraries_dir`
- `src/quantumvitas/core/pseudo_runtime.py`
  - Uses `home_pseudo_libraries_dir`
- `src/quantumvitas/core/pseudo_config.py`
  - Uses `home_pseudo_libraries_dir`
- `src/quantumvitas/core/pseudo_materialization.py`
  - Imports `home_pseudo_libraries_dir` lazily inside function
- `src/quantumvitas/pseudo/pipeline.py`
  - Uses `home_pseudo_libraries_dir`
- `src/quantumvitas/mcp/tools/list_resources.py`
  - Imports/uses `home_pseudo_libraries_dir` lazily
- `src/quantumvitas/api/service.py`
  - Imports/uses `home_pseudo_libraries_dir` lazily in service handlers

### Path helper usage in tests
- `tests/core/test_qe_resolver.py`
  - Imports `get_repo_root`, `home_qe_engines_dir`
- `tests/integration/test_wannier90_project_execution.py`
  - Imports and evaluates `get_repo_root` at module scope
- `tests/test_constitution_paths.py`
  - Imports/calls `get_repo_root`
- `tests/unit/test_vasp_registry.py`
  - Monkeypatches `resolver_mod._get_repo_root`
- `tests/integration/test_pseudo_unification.py`
  - Uses `home_pseudo_libraries_dir`
- `tests/integration/test_pseudo_resolution.py`
  - Uses `home_pseudo_libraries_dir`
- `tests/integration/test_pseudo_download_pipeline.py`
  - Uses `home_pseudo_libraries_dir`

### Risk Summary
- Highest compatibility risk: callers that directly expect `get_repo_root()` to always return a `Path` (outside repo this will now return `None`).
- Highest behavioral risk: any code constructing `.qmatsuite` and `.tmp` directly from repo root instead of using new app-data/cache helpers.
- Installed editable project deps via `python -m pip install -e '.[dev,mcp]'` to fix local collection environment.
- Post-install collection check: `6449 tests collected` (`pytest --co -q`).
- Full suite after `paths.py` refactor:
  - Command (per user rule): `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - Result: `6445 passed, 4 skipped, 979 warnings` in `393.47s`.
  - No regressions from `src/quantumvitas/core/paths.py` change.
- User rule captured for all full suite runs: always use `.venv` + parallel pytest command above.

## 2026-02-22 (Resources SSOT follow-up)
- Continuing detailed log in:
  - `docs/history/worklogs/DISTRIBUTION_STEP1_FOUNDATION_2026-02-22_WORKLOG.md`
- Goal: remove top-level `resources/` and keep only `src/quantumvitas/resources/` after migrating all source/test callsites.

## 2026-02-22 update (full-suite triage)
- Added detailed forensic and fix notes to:
  - `docs/history/worklogs/DISTRIBUTION_STEP1_FOUNDATION_2026-02-22_WORKLOG.md`
- Latest section: "2026-02-22 (Full-suite failure triage and root-cause fixes)".

## 2026-02-22 (continuation)

- Re-ran mandatory full suite in venv with xdist loadfile mode:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - Result: `6451 passed, 4 skipped` (green).
- Verified old top-level `resources/` is absent and no runtime `repo_root / "resources"` resolution remains.
- Performed wording cleanup in pseudo/demo/metadata callsite comments/docstrings to avoid future confusion around old path references.
- Ran focused sanity tests after wording cleanup:
  - `3 passed`.
