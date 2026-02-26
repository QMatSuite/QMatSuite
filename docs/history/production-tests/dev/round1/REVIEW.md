# Agent MCP Test Matrix — Review & Analysis

**Run:** `run_20260221_121301` · Feb 21, 2026
**Model:** `claude-sonnet-4-6` (all 9 agents)
**Total cost:** ~$3.28 across 9 tasks
**Overall result:** PASS — all 9/9 tasks created projects and ran calculations to completion

---

## 1. Per-Task Results

| # | Task | Path | Turns | Time | Converged | Key Result | Post-Analysis |
|---|------|------|-------|------|-----------|------------|---------------|
| 00 | Na BCC SCF (cold) | Scratch | 9 | 69s | Yes (5 iter) | -2594.49 eV | results_summary |
| 01 | Si SCF | Demo `qe_si_scf` | 8 | 23s | Yes (5 iter) | -310.69 eV | results_summary |
| 02 | Si Bands | Demo `qe_si_bands_alt` | 9 | 53s | Yes (all 4 steps) | gap=0.78 eV | results_summary + bands plot |
| 03 | Si DOS | Demo `qe_si_dos_alt` | 11 | 42s | Yes (all 3 steps) | DOS plotted | results_summary + DOS plot |
| 04 | Si Relax+Bands | Scratch | 27 | 217s | Yes (all steps) | Relax → bands chain | results_summary + bands plot |
| 05 | Al FCC SCF | Scratch | 11 | 74s | Yes (5 iter) | -158.01 Ry | results_summary |
| 06 | Fe Magnetic | Scratch | 19 | 200s | Yes (13 iter) | 2.24 µB/Fe | results_summary + convergence plot + Bash grep |
| 07 | Bad Config (5 Ry) | Demo (modified) | 9 | 28s | Yes (5 iter) | -23.22 Ry (wrong) | results_summary |
| 08 | Water xTB | Scratch | 15 | 39s | Yes | -5.071 Eh, O-H=0.959 Å | results_summary + trajectory plot |

---

## 2. Agent Decision Pipeline Analysis

### 2.1 Demo vs Scratch Decision

The agents correctly bifurcate:
- **4 tasks used demos** (01, 02, 03, 07): Si SCF/bands/DOS are well-covered in the demo catalog.
- **5 tasks built from scratch** (00, 04, 05, 06, 08): No relevant demo found → manual pipeline.
- Tasks 05 and 08 **skipped demo search entirely**, going straight to scratch. The MCP instructions say "FIRST: call init_project()" then "search_demos()" — two agents violated the hierarchy.

### 2.2 Tool Call Sequences

**Typical demo path** (tasks 01, 02, 03):
```
init_project → search_demos → load_demo → [auto_resolve_species_map] → run_calculation → get_results_summary
```

**Typical scratch path** (tasks 00, 05, 06):
```
init_project → search_demos (no match) → import_structure → create_calculation → get_presets → apply_preset → [set_parameters] → [inspect_calculation dry_run] → run_calculation → get_results_summary
```

**Gold standard** (task 04 — most complex):
```
init_project → list_workflows → search_demos (no match) → import_structure (CIF fail → POSCAR retry)
→ create_calculation(relax) → apply_preset → auto_resolve_species_map → inspect_calculation(dry_run=true)
→ run_calculation → get_results_summary + promote_structure
→ create_calculation(bands) → apply_preset → generate_kpath → set_parameters(K_POINTS) → auto_resolve_species_map
→ run_calculation → get_results_summary + plot_analysis(bands)
```

### 2.3 Best Practices Observed

| Practice | Tasks That Did It | Tasks That Didn't |
|----------|-------------------|-------------------|
| `search_demos` before scratch | 00, 01, 02, 03, 04, 06, 07 | **05, 08** |
| `inspect_calculation(dry_run=true)` before run | **04, 06** | 00, 01, 02, 03, 05, 07, 08 |
| `plot_analysis` after completion | 02, 03, 04, 06, 08 | 00, 01, 05, 07 |
| `search_knowledge` for guidance | — | **All 9 tasks** (none used it) |

---

## 3. Bugs Found

### BUG-1: `apply_preset` returns `status: "applied"` on failure

**Observed in:** Task 05 (Al SCF)
**What happened:** Agent called `apply_preset` with `SMEARING_MP` (Methfessel-Paxton). The tool returned `status: "applied"` with `steps_updated: 0` and a step-level error buried inside `step_results`. The top-level status was misleading.
**Impact:** Agent had to call `get_presets` to discover valid values, then retry. Wasted 2 tool calls.
**Fix:** `apply_preset` should return `status: "error"` or `status: "partial"` when `steps_updated == 0` and step errors exist. The error should surface the valid options.

### BUG-2: `promote_structure` fails after successful xTB relax

**Observed in:** Task 08 (Water xTB)
**What happened:** After a successful `quick_run` of xTB relax (`.xtboptok` present, "normal termination"), `promote_structure` returned "Run the calculation first."
**Root cause:** `_RELAX_GEN_TYPES = frozenset({"relax"})` in `promote_structure.py:9` — this set is missing `"vc-relax"` and `"vc_relax"`. For xTB, the step_type_gen mapping may not match this set.
**Impact:** Agent had to use `Bash` + `cat` to read `xtbopt.xyz` directly. The MCP abstraction broke down.
**Fix:** Expand `_RELAX_GEN_TYPES` to include all relax variants. Also verify xTB's step_type_gen is correctly registered.

### BUG-3: `get_results_summary` only has QE fallback parser

**Observed in:** Latent (all non-QE engines)
**What it means:** The `_parse_direct` function in `get_results_summary.py:131` only imports `QEOutputParser`. For VASP, ORCA, ABINIT, etc., if the provenance digest is not available, the tool returns "no_results" even though output files exist.
**Fix:** Use `DriverRegistry` to get the appropriate output parser for the engine family.

### BUG-4: `quick_run` has no error enrichment

**Observed in:** Latent
**What it means:** When `run_calculation` fails, it calls `enrich_run_error()` which provides structured diagnostics (SCF_NOT_CONVERGED, IONIC_NOT_CONVERGED, etc.) with actionable `suggested_fixes`. `quick_run` does not — it returns a generic error. Agents using the fast path get worse diagnostic information.
**Fix:** Add the same `enrich_run_error()` call to `quick_run`'s failure path.

### BUG-5: `get_status` can never report failure

**Observed in:** Latent
**What it means:** In `get_status.py:42`, `has_failed` is initialized to `False` but no code path sets it to `True`. The `overall_status` can never be `"failed"`.
**Fix:** Set `has_failed = True` when any step status indicates failure.

---

## 4. MCP Information Gaps

### GAP-1: Magnetic moment not in results summary

**Observed in:** Task 06 (Fe Magnetic)
**What happened:** Agent called `get_results_summary` after a spin-polarized SCF. The result included energy and convergence but NOT magnetization. Agent resorted to `Bash` + `grep` on the raw QE output to find `total magnetization = 4.47 Bohr mag/cell`.
**Impact:** Breaks the MCP abstraction — agents should never need to read raw engine output files.
**Fix:** Add `total_magnetization_bohr_mag` and `absolute_magnetization_bohr_mag` to the results summary when `nspin=2`. The QE output parser already captures these.

### GAP-2: No preflight warning for absurdly low cutoffs

**Observed in:** Task 07 (ecutwfc=5 Ry)
**What happened:** Neither the agent nor the MCP system flagged ecutwfc=5 Ry as problematic. The calculation ran and produced unphysical results (-23.22 Ry vs correct ~-22.84 Ry).
**Impact:** Agents cannot warn users about bad configurations.
**Fix:** Add a preflight rule: `if ecutwfc < min_cutoff_for_pseudo → advisory warning`. The SSSP library includes recommended cutoff values per element — use them.

### GAP-3: No `list_calculations()` tool

**Impact:** An agent resuming a session has no way to discover existing calculations. Must read `project.qv.yml` manually.
**Fix:** Add `list_calculations()` returning calc_ulid, name, engine, workflow, status for each.

### GAP-4: CIF inline import is fragile

**Observed in:** Tasks 04 and 06 — CIF import failed, agents recovered with POSCAR.
**Pattern:** Simple cubic structures (task 05 Al) succeed; more complex structures fail.
**Impact:** Agents waste tool calls on CIF failure + POSCAR retry.
**Fix:** Improve the CIF parser error message to suggest POSCAR as fallback. Or improve the parser itself.

### GAP-5: `search_knowledge` never used proactively

**Observed in:** All 9 tasks — zero calls to `search_knowledge`.
**Root cause:** The MCP instructions only mention it for error recovery: "On failure: use search_knowledge() for recovery guidance." No guidance to use it proactively before configuration.
**Impact:** Agents miss best-practice advice (e.g., "metals need smearing", "magnetic systems need nspin=2").
**Fix:** Add to instructions: "For unfamiliar systems, use search_knowledge() to check best practices before configuring."

### GAP-6: `generate_kpath` not mentioned in MCP instructions

**Observed in:** Task 04 discovered it on its own via `list_workflows` → reasoning.
**Impact:** Agents doing band structure from scratch might not know this tool exists.
**Fix:** Add to instructions: "For band structure workflows, use generate_kpath() to automatically determine the high-symmetry k-path."

### GAP-7: `quick_run` not mentioned in MCP instructions

**Impact:** Agents always use the long path (create → set_species → apply_preset → run). `quick_run` combines all of these but is undiscoverable from the instructions.
**Fix:** Mention in instructions: "For simple calculations, quick_run() combines create + configure + run in one call."

### GAP-8: Demo pseudo override inconsistency

**Observed in:** Tasks 01 and 02
**What happened:** Agent called `auto_resolve_species_map` on a loaded demo, overriding the demo's LDA pseudo with PBE SSSP precision. The demo description says "LDA (PZ)" but the calculation ran with a PBE pseudopotential.
**Impact:** Subtle functional mismatch — not necessarily wrong, but inconsistent with the demo's intended configuration.
**Fix:** `load_demo` should either (a) auto-resolve species_map itself (so the agent doesn't call it redundantly), or (b) warn when species_map is already set and agent tries to override.

---

## 5. Physics Quality Assessment

| Task | ecutwfc | K-mesh | Occupations | Assessment |
|------|---------|--------|-------------|------------|
| 00 Na SCF | 50 Ry | 8³ | Gaussian smearing | Good (metal handled correctly) |
| 01 Si SCF | **20 Ry** | 6³ | fixed | **Poor** — demo default too low for production |
| 02 Si Bands | 40 Ry | — | fixed | Good |
| 03 Si DOS | 50 Ry | — | tetrahedra (NSCF) | Good |
| 04 Si Relax+Bands | 50 Ry | 11³ | fixed | Good — best params of all scratch tasks |
| 05 Al SCF | 50 Ry | 8³ | Gaussian smearing | Good (metal handled correctly) |
| 06 Fe Magnetic | 50 Ry | 11³ | Gaussian smearing, nspin=2 | Excellent — 2.24 µB/atom (exp: 2.22) |
| 07 Bad Config | 5 Ry | 6³ | fixed | Intentionally bad |
| 08 Water xTB | N/A | N/A | N/A | Good — O-H=0.959 Å (exp: 0.957) |

**Key finding:** Scratch-built calculations (tasks 00, 04, 05, 06) consistently use ecutwfc=50 Ry via presets. Demo-loaded tasks inherit whatever the demo specifies — which can be poor (task 01 at 20 Ry). The agent does NOT upgrade demo parameters to match SSSP recommended cutoffs.

---

## 6. Proposed MCP Improvements

### Priority 1 (Bugs — fix immediately)

1. **`apply_preset`: return `status: "error"` when no steps updated** — surface the valid options in the error message.
2. **`promote_structure`: expand `_RELAX_GEN_TYPES`** — add `"vc-relax"`, `"vc_relax"`, and verify xTB/LAMMPS relax step types.
3. **`quick_run`: add `enrich_run_error()`** — same error enrichment as `run_calculation`.
4. **`get_results_summary`: add magnetization fields** — `total_magnetization`, `absolute_magnetization` when nspin=2.

### Priority 2 (Information gaps — improve agent effectiveness)

5. **Add `list_calculations()` tool** — let agents discover existing calculations in a project.
6. **Update MCP instructions** — mention `generate_kpath()`, `quick_run()`, `search_knowledge()` for proactive use, and `list_analyses()` + `plot_analysis()` as post-run steps.
7. **Add preflight cutoff check** — compare ecutwfc against SSSP recommended values. Emit advisory if below threshold.
8. **`get_results_summary`: engine-agnostic parser fallback** — use `DriverRegistry` to find the right output parser, not hardcoded `QEOutputParser`.

### Priority 3 (Polish — improve reliability)

9. **`get_status`: fix `has_failed` detection** — actually set it when step status indicates failure.
10. **`load_demo` + `auto_resolve_species_map` interaction** — either auto-resolve in `load_demo` or warn on redundant override.
11. **CIF parser error improvement** — better error messages, suggest POSCAR fallback.
12. **`init_project`: report existing calc/structure counts** — helps agents decide whether to explore or start fresh.

---

## 7. Proposed Additional Test Cases

### Coverage gaps in current matrix

| # | Proposed Task | What It Tests | Gap Covered |
|---|--------------|---------------|-------------|
| 09 | "Resume the Si SCF calculation and increase ecutwfc to 60 Ry" | Session resumption, parameter modification, incremental run | No `list_calculations` tool exists |
| 10 | "Calculate the band structure of MgO using Quantum ESPRESSO" | Binary compound (not Si/Fe), insulator with large gap | Only Si tested for bands |
| 11 | "Run a variable-cell relaxation of silicon using Quantum ESPRESSO" | vc-relax workflow, `promote_structure` with vc-relax | BUG-2 verification |
| 12 | "Calculate the total energy of silicon using VASP" | Non-QE engine via MCP | All QE except task 08 |
| 13 | "Compare the energy of silicon at ecutwfc=30 and ecutwfc=60 Ry" | Convergence study, parameter scan, agent reasoning | No multi-run comparison test |
| 14 | "The previous SCF calculation of iron didn't converge. Fix it." | Error recovery, `search_knowledge`, diagnostic pipeline | Error enrichment untested |
| 15 | "Calculate the phonon frequencies of silicon" | DFPT workflow, post-processing chain | Only SCF/bands/DOS/relax tested |
| 16 | "Optimize a benzene molecule using ORCA" | Molecular code, ORCA engine, no pseudo needed | Only xTB tested for molecules |

### Proposed script additions

```bash
# After current tasks, add:
# -- Error recovery test (deliberately break, see if agent recovers)
_launch "09" "task_09_si_vc_relax" \
    "Run a variable-cell relaxation of silicon using Quantum ESPRESSO, then extract the relaxed structure."

# -- Non-QE engine test
_launch "10" "task_10_benzene_orca" \
    "Optimize the geometry of benzene using ORCA with B3LYP/def2-SVP."

# -- Convergence study (tests agent reasoning)
_launch "11" "task_11_convergence_test" \
    "Calculate the total energy of silicon at ecutwfc=20, 40, and 60 Ry using Quantum ESPRESSO. Compare the results."
```

### Proposed gate additions

```bash
# After Phase 2, add deeper checks:

# Gate: at least 5/9 tasks should have run_calculation that returned "completed"
# (Check traces for "completed" status in run_calculation results)

# Gate: tasks 02, 03 should have generated PNG plot files
for t in task_02_si_bands task_03_si_dos; do
    png_count=$(find "$RUN_DIR/$t" -name "*.png" 2>/dev/null | wc -l)
    if [[ $png_count -eq 0 ]]; then
        echo "GATE WARN: $t produced no plots"
    fi
done

# Gate: task 06 should have nspin=2 in its input (magnetic calculation correctness)
if ! grep -q "nspin.*=.*2" "$RUN_DIR/task_06_fe_magnetic/calculations/"*/raw/scf.in 2>/dev/null; then
    echo "GATE WARN: task_06 missing nspin=2 (magnetic calculation not configured correctly)"
fi
```

---

## 8. Summary of Systemic Issues

### Issue A: `search_knowledge` is invisible

The knowledge base contains curated DFT best practices but no agent ever called it. The instructions only mention it for error recovery. This is the single biggest missed opportunity — agents are making physics decisions (smearing type, magnetism settings, cutoff values) without consulting the knowledge base.

### Issue B: Demo parameters are not production-quality

The `qe_si_scf` demo uses ecutwfc=20 Ry — a tutorial value, not a production value. When agents load demos and run them, they inherit these weak parameters. Either (a) demos should use production-quality parameters, or (b) the MCP system should warn when demo parameters are below SSSP recommended cutoffs.

### Issue C: The "dry_run before run" pattern is inconsistently followed

Only 2 of 9 agents used `inspect_calculation(dry_run=true)` before running. The MCP instructions say "ALWAYS before running: inspect_calculation(dry_run=True)" — but agents don't consistently follow this. The instruction emphasis may need to be stronger, or `run_calculation` could auto-run preflight and block on critical issues.

### Issue D: Agents break out of MCP abstraction

Tasks 06 and 08 used `Bash` to read raw output files because the MCP tools didn't expose the needed data (magnetization, optimized geometry). Every `Bash` call to read raw output is a failure of the MCP abstraction layer.

### Issue E: Post-run analysis is inconsistent

Only 5 of 9 agents called `plot_analysis`. The 4 that didn't (00, 01, 05, 07) completed their task but provided less value to the user. The instructions should make post-run analysis a standard step, not optional.
