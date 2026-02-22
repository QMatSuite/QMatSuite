# QMatSuite — Deferred Items (Canonical Backlog)

Last updated: 2026-02-21 (MCP Phase 1 close-out)

Consolidates all deferred items from MCP Stage 1–11 worklogs, agent test matrix Rounds 1–3,
demo store audit, and launch-related planning. Organized by domain and priority.

---

## 1. MCP Core — Completed Items (Reference Only)

These items were fixed during MCP Phase 1 and are listed here for historical completeness.
Do not reopen unless regressions are discovered.

- [x] BUG-1: `apply_preset` returns success when steps_updated=0
- [x] BUG-2: `promote_structure` missing "minimize" + stale vc-relax refs
- [x] BUG-3: `get_results_summary` only uses QE parser → now engine-agnostic via `find_parser_for_raw()`
- [x] BUG-4: `quick_run` missing error enrichment on failure
- [x] BUG-5: `get_status` never detects failures
- [x] GAP-1: Magnetization in QESCFDigest + results summary pipeline
- [x] GAP-3: New `list_calculations` MCP tool
- [x] GAP-5/6/7: `.mcp.json.example` instructions expanded
- [x] GAP-8: `load_demo` context_hint mentions species_map status
- [x] Demo ecutwfc: qe_si_scf 20 Ry → 30 Ry
- [x] Fix 2a: xTB energy field alias in `get_results_summary` (`final_energy_eV`)
- [x] Fix 2b: xTB `promote_structure` path handling (ISOLATED workdir + `xtbopt.xyz`)
- [x] `inspect_calculation dry_run` materialization (Stage 2 → Stage 5)

---

## 2. MCP — High Priority

### H1: Law P2 opctx gap (systemic migration)
- **Source**: MCP_STAGE10B_PROVENANCE_AUDIT.md
- `save_calculation()`, `save_project()`, `materialize_project_from_snapshot()`, `load_demo_as_calculation()` all skip opctx
- The `opctx` parameter is currently optional (migration mode); Law P2 enforcement deferred until all callers updated
- **Fix**: Systemic migration — update all callers to provide OperationContext

### H2: Error enrichment for ENGINE_CRASH and UNKNOWN_FAILURE
- **Source**: Agent Test Matrix Round 1 P1, Round 3 Issue 4
- ENGINE_CRASH currently returns no raw output — agents fall back to `Bash cat` to inspect stderr (Round 3 task 13)
- UNKNOWN_FAILURE provides engine-not-found message but no suggested_fixes
- **Fix**: Include first 50 lines of stdout/stderr in the error enrichment response. Add basic suggested_fixes for all error types (check binary path, check disk space, check permissions)

### H3: Expand knowledge base (builtin.db) from 20 to 50+ entries
- **Source**: Agent Test Matrix Round 1 P1
- Currently only QE-focused knowledge entries. Non-QE engines need coverage.
- **Fix**: Add 3–5 error recovery entries per engine (ORCA, CP2K, ABINIT, LAMMPS, Siesta). Cover: convergence failures, memory errors, file-not-found, license issues.

### H4: VASP preflight rules
- **Source**: Agent Test Matrix Round 1 P1
- Only QE has a full preflight checker (20 rules). VASP is the second most-used engine.
- **Fix**: 5–8 rules: ISMEAR+IBRION compatibility check, ENCUT < ENMAX warning, MAGMOM array length vs ISPIN=2, LREAL=Auto for large cells, KPOINTS format validation

---

## 3. MCP — Medium Priority

### M1: Parser auto-registration chain for all engines
- **Source**: Engine integration audit
- QE, VASP, ORCA, ABINIT, CP2K, W90 output parsers are not auto-discovered via registry chain
- **Partial fix** (2026-02-21): `get_results_summary` and `run_calculation` use `find_parser_for_raw()` with `import quantumvitas.drivers` trigger
- **Remaining**: Wire parser registration into DriverRegistry startup for systemic coverage

### M2: search_knowledge adoption — agent instruction strengthening
- **Source**: Agent Test Matrix Round 3 Issue 1
- 0/17 agents called `search_knowledge()` proactively (was 2/9 in Round 2)
- Instruction exists in `.mcp.json.example` but agents skip it for clear tasks
- **Fix**: Two-pronged: (1) Change instruction to "ALWAYS call search_knowledge() before creating a new calculation"; (2) Embed search_knowledge hint in `create_calculation` response context_hint

### M3: Post-run analysis hints in run_calculation response
- **Source**: Agent Test Matrix Round 3 Issue 2
- `plot_analysis` rate dropped to 6/17 (35%) from 9/9 (100%) in Round 2
- Agents don't consistently follow the "After a successful run" instruction
- **Fix**: Embed "Call list_analyses() then plot_analysis() to visualize results" directly in `run_calculation` success response context_hint

### M4: inspect(dry_run) regression — strengthen demo-path guidance
- **Source**: Agent Test Matrix Round 3 Issue 3
- 5/17 (29%) used dry_run before running, down from 6/9 (67%) in Round 2
- Agents skip it for demo-loaded calculations (trust demo config)
- **Fix**: Make instruction unambiguous: "ALWAYS call inspect_calculation(dry_run=True) before EVERY run_calculation() call, including after load_demo()"

### M5: QE ecutwfc minimum sanity check in preflight
- **Source**: Agent Test Matrix Round 3 Issue 6, Round 1 demo audit
- ecutwfc=5 and ecutwfc=1 both ran without preflight warning
- **Fix**: Add preflight rule: if `ecutwfc < 15` Ry for QE, emit WARNING advisory. Separate from the SSSP-aware recommended cutoff (which requires species_map lookup).

### M6: Demo ecutwfc validation gate test
- **Source**: Agent Test Matrix Round 1
- No CI test prevents demos from shipping with unreasonably low ecutwfc
- **Fix**: Gate test: all QE demos with `demo_eligible: true` must have ecutwfc >= 25 Ry

### M7: CP2K recipes.py circular import
- **Source**: MCP_STAGE8_WORKLOG.md, CP2K Phase B1
- recipes.py imports from drivers/<engine>/recipe.py which imports back
- Systemic issue affecting all engines; 1 xfailed test
- **Fix**: Decouple recipe registration from module-level imports

### M8: Text-search upgrade for search_demos
- **Source**: WORKLOG_DEMO_AUDIT.md
- Current text search is substring-only. "iron" doesn't match "Fe" demos
- **Fix**: BM25 or fuzzy matching for better recall

### M9: Ref pack staleness detection
- **Source**: WORKLOG_DEMO_AUDIT.md
- If demo input parameters change but ref pack isn't regenerated, results become stale
- **Fix**: Manifest checksum comparison to warn

### M10: History service query for failed runs
- **Source**: Agent Test Matrix Round 1 GAP-4
- `get_latest_run_for_step()` only queries `r.status = 'success'` in SQL
- Failed runs return `run_ulid: None`, indistinguishable from "not run"
- **Fix**: Add `get_latest_run_for_step(include_failed=True)` variant

### M11: Remaining engine preflight checkers
- **Source**: MCP_STAGE5_WORKLOG.md
- Only QE has a full preflight checker. VASP is addressed in H4.
- ABINIT, ORCA, Gaussian, LAMMPS, CP2K — all Phase 2
- **Fix**: Implement per-engine preflight checkers following QE pattern

---

## 4. MCP — Low Priority

### L1: Binary detection for `installed` field
- **Source**: MCP_STAGE1_WORKLOG.md
- `list_engines` always reports `installed: True`; `installed_only` parameter is a no-op
- **Fix**: Implement PATH/config-based engine binary detection. (Partly addressed by cross-platform engine management design.)

### L2: Search index serialization caching
- **Source**: MCP_STAGE1_WORKLOG.md
- ~1000 documents from 11 engines; BM25 index rebuilt on every MCP server start
- Not a performance concern at current scale (~200ms)
- **Fix**: Serialize index to disk, invalidate on metadata changes

### L3: Preset value normalization for agent-friendly enum names
- **Source**: MCP_STAGE2_WORKLOG.md
- Preset values use enum values (e.g. `collinear_lsda`), not profile names (e.g. `COL`)
- **Fix**: Add normalization layer in MCP tools for agent-friendly names

### L4: PrecisionAdvisor in preview_compilation
- **Source**: MCP_STAGE2_WORKLOG.md
- Requires structure access for precision recommendations
- **Fix**: Wire structure into preview_compilation for adaptive precision advice

### L5: XYZ import format note in agent instructions
- **Source**: Agent Test Matrix Round 3 Issue 5
- Tasks 08, 10, 12 all attempted XYZ import without header on first try
- **Fix**: Add to `.mcp.json.example`: "For XYZ format: file MUST start with atom count line (standard XYZ format). Never omit the count and comment lines."

### L6: Corpus-level subtitle/difficulty validation gate
- **Source**: WORKLOG_DEMO_AUDIT.md
- No gate test for demo metadata completeness
- **Fix**: Gate test that verifies `subtitle` and `difficulty` fields on all demos

### L7: Demo runtime benchmarking
- **Source**: WORKLOG_DEMO_AUDIT.md
- `estimated_runtime_s` values are manual estimates
- **Fix**: CI job to run each demo on reference machine and record actual runtimes

### L8: QE parameter metadata upstream curation
- **Source**: Agent Test Matrix Round 1 P2
- Several QE params have null enum but list values in description text (`cell_dofree`, `mixing_mode`, `diagonalization`, `ion_dynamics`)
- **Fix**: Curate enum values from QE documentation for these parameters

### L9: Run progress visibility
- **Source**: Agent Test Matrix Round 1 P2
- No real-time step completion reporting during long calculations
- **Fix**: Design and implement progress callback mechanism

### L10: Preflight severity grouping
- **Source**: Agent Test Matrix Round 1 P2
- `inspect_calculation` output mixes blocking errors and advisory warnings
- **Fix**: Separate blocking vs advisory in preflight output

### L11: Proactive knowledge injection in create_calculation
- **Source**: Agent Test Matrix Round 1 P2 (design section 7.8)
- Query knowledge base by engine+system_type on `create_calculation`, inject top-3 entries
- **Fix**: Implement as optional feature in `create_calculation` context_hint

### L12: search_knowledge-focused test matrix task
- **Source**: Agent Test Matrix Round 3 §8 Recommendation 6
- No task specifically tests whether agents use `search_knowledge` before setup
- **Fix**: Add task like "Set up DFT+U calculation for NiO — explain parameter choices based on best practices"

---

## 5. MCP — Phase 2+ (Future)

### F1: Preflight for ORCA, CP2K, ABINIT, Gaussian, LAMMPS
- Full preflight checker implementations for all remaining engines

### F2: Knowledge pack system (downloadable .db files)
- Downloadable knowledge databases for specific domains (e.g. strongly correlated, surfaces, molecular)

### F3: Auto-invoke search_knowledge on error
- Include top knowledge match directly in error return without requiring manual agent call

### F4: Materials Project API integration
- `search_materials_project()` MCP tool for structure search and import

### F5: ML potential integration
- MACE, CHGNet, M3GNet engine drivers for rapid pre-screening

### F6: Additional demos
- Non-QE engine demos (VASP, ORCA, CP2K, LAMMPS)
- Advanced workflow demos (phonons, DFPT, GW, BSE)
- Multi-engine pipeline demos (QE → Wannier90 → QMCPACK)

### F7: Contributing guide for MCP tools
- Document how to add a new MCP tool (template, testing, registration in server.py)

---

## 6. Non-MCP — Architecture & Infrastructure

### A1: Cross-platform paths.py migration
- **Source**: Distribution design (2026-02-21)
- Current `paths.py` hardcodes `repo_root/.qmatsuite/` via `get_repo_root()` walk-up
- Production distribution needs platform-appropriate paths (`~/Library/Application Support/QMatSuite/` on macOS, `%LOCALAPPDATA%\QMatSuite\` on Windows)
- **Fix**: Add `QMATSUITE_HOME` env var support + platform-aware default path resolution. See `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` §2

### A2: Electron packaging — production configuration
- **Source**: Distribution design (2026-02-21)
- `electron-builder.json5` uses placeholder `appId: "YourAppID"` and `productName: "YourAppName"`
- No code signing, no auto-update, no dmg background image
- **Fix**: Configure production Electron packaging for Mac + Windows. See `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` §1

### A3: Python backend bundling for Electron release
- **Source**: Distribution design (2026-02-21)
- Electron app currently requires separate Python venv with `pip install`
- Full release needs bundled Python so users don't need to install Python
- **Fix**: Micromamba-embedded Python environment. See design doc §4

### A4: Unified engine registry (engines.json)
- **Source**: Distribution design (2026-02-21)
- Currently QE-only binary discovery in `qe_resolver.py` with two-state model
- No unified registry across all engines, no micromamba integration
- **Fix**: Implement `engines.json` registry + discovery pipeline. See design doc §3
