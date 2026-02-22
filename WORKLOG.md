# Distribution Step 1 Worklog

Date: 2026-02-22
Repo: /Users/hh7465/QMatSuite

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
