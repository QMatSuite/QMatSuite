# Resource Management Review — Worklog

## Started: 2026-02-18

### Phase 1: Investigation (COMPLETE)
- [x] Global resource layout (`.qmatsuite/`, path resolution)
- [x] QE pseudopotential lifecycle (storage, species_map, staging, download)
- [x] Per-engine resource inventory (all 15 engines)
- [x] Portability analysis
- [x] Agent experience analysis
- [x] MCP tool current state

### Progress Log

**2026-02-18 — Investigation Phase**

Read and analyzed the following source files:

1. `src/qmatsuite/core/paths.py` — Centralized path helpers; `.qmatsuite/` always at repo root (dev mode). No `QMATSUITE_HOME` env var yet. `get_repo_root()` walks from `paths.py` up to find `pyproject.toml`.

2. `src/qmatsuite/core/pseudo.py` — `ensure_qe_pseudos()` canonical resolution entry point. Species_map-first resolution with QE input parsing fallback. 4-step search: project → system → additional_search_dirs → download. `__MISSING_PSEUDO__` placeholder system.

3. `src/qmatsuite/core/pseudo_config.py` — `PseudoConfig` dataclass, SSSP download from GitHub releases (`QMatSuite/qmatsuite-assets`), user config at platform-specific path (`~/Library/Application Support/QMatSuite/config.json` on macOS). SSSP versioned store layout: `${store_dir}/sssp/${version}/${flavor}/library/`.

4. `src/qmatsuite/core/pseudo_materialization.py` — `materialize_calc_pseudos()` for run-time staging to `working_dir/pseudo/`. SHA256-pinned path + legacy filename-only path. Resolution: project/pseudo → internal → installed archives.

5. `src/qmatsuite/core/pseudo_options.py` — `get_pseudo_options_for_elements()` generates UI options. SHA256-keyed variants with PseudoSource chips (project/internal/lib). `materialize_pseudo_file()` resolves SHA256 to actual file path.

6. `src/qmatsuite/core/pseudo_runtime.py` — Step0 preparation. `PseudoSelection` model. `prepare_project_pseudos_for_run()` — the only function allowed to mutate `project/pseudo`. Collision rules: same sha256=noop, same sha_family=overwrite, different sha_family=rename.

7. `src/qmatsuite/core/pseudo_provenance.py` — Read-only provenance recognition. `resolve_pseudo_provenance()` matches SHA256/sha_family against libinfo index.

8. `src/qmatsuite/core/pseudo_libinfo.py` — Vendored metadata bundle loader from `resources/pseudo_libinfo/`.

9. `src/qmatsuite/core/pseudo_installs.py` — Generic archive installation/management. SHA256-verified installs to `<install_root>/archives/`.

10. `src/qmatsuite/drivers/vasp/engine/vasp_potcar.py` — `stage_potcar()` concatenates per-element POTCARs. Search: `VASP_PP_PATH` → `.qmatsuite/engines/vasp/`. `list_available_potcars()` exists but not exposed to MCP.

11. `src/qmatsuite/drivers/lammps/engine/lammps_potential.py` — `stage_potentials()` copies force-field files. Search: `LAMMPS_POTENTIALS` → `.qmatsuite/engines/lammps/potentials/` → Homebrew.

12. All 15 `drivers/<engine>/inputspec.py` — ResourceRefSpec staging_policy survey complete.

13. MCP tools: `set_species_map.py`, `create_calculation.py`, `run_calculation.py`, `quick_run.py` — analyzed for resource handling gaps.

14. `CONSTITUTION.md` §9 — 3-source model (internal, lib, project), SHA256 vs SHA_FAMILY semantics.

**2026-02-18 — Review Document Written**

Produced `docs/history/reviews/RESOURCE_MANAGEMENT_REVIEW.md` (~800 lines) covering:
- Executive summary with 5 key findings
- Current state audit of all 15 engines
- Agent experience gap analysis
- Unified design proposal
- Phased implementation roadmap
- Open questions for maintainer input
