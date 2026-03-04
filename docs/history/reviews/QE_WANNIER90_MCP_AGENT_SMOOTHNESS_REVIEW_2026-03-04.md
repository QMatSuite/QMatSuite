# QE-Wannier90 MCP Agent Smoothness Review (Si Bands + Fe AHC)

Date: 2026-03-04  
Author: Codex (deep repo review + external run-trace replay)  
Scope: Why agent fell back to direct engine execution, and minimum patches to keep future runs MCP-native and agent-friendly.

Revision note (second-pass audit): this version adds missing critical root causes found after re-reading traces under lower context pressure, especially Wannier/pw2wannier parameter materialization gaps that made MCP `set_parameters` non-effective for key AHC knobs.

## 1. Request Restatement

You asked for a deep review of why a GPT+MCP agent could not complete QE→Wannier90 tasks fully inside QMatSuite MCP, then a minimum patch proposal so the next run can be completed smoothly without direct engine commands.

Constraints followed in this review:
- No source code changes.
- No test run.
- One review document only.

## 2. Evidence Reviewed

### 2.1 External experiment report and traces

- `/Users/<username>/gpt_agent_test/DETAILED_REPORT_SI_BANDS_AND_FE_AHC.md`
- `/Users/<username>/gpt_agent_test/task_1_trace_si_band_single_thread_gpt_5_3_codex_extra_high`
- `/Users/<username>/gpt_agent_test/task_2_trace_fe_AHC_np_12_gpt_5_3_codex_extra_high`
- Raw artifacts under:
  - `/Users/<username>/gpt_agent_test/project/calculations/si_bands_attempt1`
  - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1`
  - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1`

### 2.2 QMatSuite code paths reviewed

- Workflow definitions and materialization:
  - `src/qmatsuite/workflow/templates.py`
  - `src/qmatsuite/workflow/generalized_steps.py`
  - `src/qmatsuite/core/driver_registry.py`
- MCP workflow tools and status/analysis tools:
  - `src/qmatsuite/mcp/tools/create_calculation.py`
  - `src/qmatsuite/mcp/tools/quick_run.py`
  - `src/qmatsuite/mcp/tools/list_workflows.py`
  - `src/qmatsuite/mcp/tools/get_status.py`
  - `src/qmatsuite/mcp/tools/get_results_summary.py`
  - `src/qmatsuite/mcp/tools/list_analyses.py`
  - `src/qmatsuite/mcp/tools/plot_analysis.py`
  - `src/qmatsuite/mcp/tools/inspect_calculation.py`
  - `src/qmatsuite/mcp/tools/list_resources.py`
- Execution and materialization internals:
  - `src/qmatsuite/drivers/qe/recipe.py`
  - `src/qmatsuite/drivers/qe/engine/qe_engine.py`
  - `src/qmatsuite/drivers/qe/engine/qe_calculation.py`
  - `src/qmatsuite/calculation/structure_steps.py`
  - `src/qmatsuite/calculation/wannier90_kpoints.py`
  - `src/qmatsuite/calculation/step_done.py`
  - `src/qmatsuite/calculation/manifest_reconcile.py`
- Analysis capabilities and parsers:
  - `src/qmatsuite/api/service.py`
  - `src/qmatsuite/drivers/qe/driver.py`
  - `src/qmatsuite/drivers/w90/driver.py`
  - `src/qmatsuite/drivers/w90/parsers/output.py`
  - `src/qmatsuite/parsers/registry.py`
  - `src/qmatsuite/drivers/qe/parsers/bands.py`
  - `src/qmatsuite/core/analysis/band_structure/model.py`
- Defaults/presets:
  - `src/qmatsuite/calculation/step_defaults.py`
  - `src/qmatsuite/presets/variants_registry.py`
- Demo consistency check:
  - `src/qmatsuite/resources/demo_projects/qe_diamond_wannier.yml`

## 3. What Happened in Practice

## 3.1 Si bands run (MCP mostly worked)

- MCP flow succeeded after one blocking preflight issue: missing explicit k-path for `bandspw`.
- Agent had to call `generate_kpath` + `set_parameters` to proceed.
- MCP summary did not provide VBM/CBM k-location fields, so the agent manually parsed `bands.bands.dat`.

Trace anchors:
- Schema mismatch on first pseudo listing call: `task_1_trace...:15`
- Missing k-path preflight block: `task_1_trace...:45`
- Manual VBM/CBM extraction because summary lacked locations: `task_1_trace...:75`

## 3.2 Fe AHC run (MCP scaffolding worked, completion required direct engine control)

Observed MCP-created workflow in both attempts:
- `qe_scf -> qe_nscf -> qe_pw2wannier -> w90_wannier`
- No `w90_wannierprep` step present in calculation.yaml.

Files:
- `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1/calculation.yaml`
- `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1/calculation.yaml`

Breakpoints that forced direct shell execution:
- Missing `.nnkp` before `pw2wannier90`.
  - `.../fe_bcc_ahc_attempt1/raw/pw2wannier.out:51`
  - `.../fe_bcc_ahc_attempt1/raw/CRASH:4`
- Seedname drift in attempt1 (`pw2wan.in` asked for `pw2wannier.nnkp`).
  - `.../fe_bcc_ahc_attempt1/raw/pw2wan.in:4`
  - `.../fe_bcc_ahc_attempt1/raw/pw2wannier.out:51`
- SOC spinor inconsistency (`spinor = T` missing in `.win`).
  - `.../fe_bcc_ahc_attempt1-1/raw/pw2wannier.out:63`
  - `.../fe_bcc_ahc_attempt1-1/raw/pw2wannier.out:72`
- Projection mode conflict and projection cardinality errors.
  - `.../fe_bcc_ahc_attempt1-1/raw/pw2wannier_manual.out:61`
  - `.../fe_bcc_ahc_attempt1-1/raw/wannier_pp.out:1`
  - `.../fe_bcc_ahc_attempt1-1/raw/wannier_run.out:1`
- MCP parameter intent vs generated inputs diverged:
  - Step YAML had `spinors/berry/berry_task/berry_kmesh/auto_projections/postproc_setup`, but generated `wannier.win` (before manual edits) lacked them.
    - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1/steps/wannier.step.yaml`
    - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1/raw/wannier.win.bak`
  - Step YAML had `write_unk: true`, but generated `pw2wan.in` remained `write_unk = .false.` (default).
    - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1/steps/pw2wannier.step.yaml`
    - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1/raw/pw2wan.in`
- Postprocessing AHC stage required direct `postw90.x`, plus manual `fermi_energy` patch.
  - Missing Fermi level for Berry mode: `.../wannier.wpout` (first failing postw90 run in trace)
  - Final AHC present only in `.wpout`: `.../wannier.wpout:244`

Result: The agent executed `wannier90.x -pp`, `pw2wannier90.x`, and `postw90.x` directly in raw directory, with repeated manual `.win`/NSCF edits.

## 4. Agent Thought Experiment: Where a Future Agent Will Still Fail

If another agent repeats this task with only MCP tools and no hidden hand-tuning, the likely failure path is:

1. Select `workflow='wannier'` from `list_workflows(engine='qe')`.
2. Create calculation; template omits `wannierprep`.
3. Run; `pw2wannier` fails on missing `.nnkp` (or wrong seedname fallback if no `.win` anchor exists).
4. Agent tries `set_parameters` on Wannier step (`spinors`, `berry_task`, `berry_kmesh`, etc.), but materialization drops most of these keys from generated `.win`.
5. Agent tries `set_parameters` on `pw2wannier` (`write_unk`, projection-mode knobs), but materialization keeps mostly defaults and ignores many `INPUTPP` controls.
6. Projection-mode mismatch (`auto_projections` in `.nnkp` vs `pw2wannier` flags) persists, producing repeat failures.
7. Even after Wannierization works, there is no first-class MCP `postw90` stage in workflow/step taxonomy.
8. `list_analyses` / `plot_analysis` cannot surface AHC because capabilities/parsers are keyed to calc engine (`qe`) and no AHC object parser exists.
9. Agent drops to shell for `wannier90 -pp`, `pw2wannier90`, `postw90`, and `.wpout` parsing.
10. Status APIs can report misleading completeness when older successful runs exist for same step ULIDs but current config/manifest is not done.

## 5. Root Causes in Code (with Concrete Anchors)

## 5.1 Workflow template omits mandatory Wannier prep step

Current `wannier` template:
- `src/qmatsuite/workflow/templates.py:110-115`
- Sequence is `("scf", "nscf", "pw2wannier", "wannier")`.

But shipped QE→W90 demos encode a 5-step chain including prep:
- `src/qmatsuite/resources/demo_projects/qe_diamond_wannier.yml:875`
- Step summary explicitly: `SCF → NSCF → W90 prep → pw2wannier → Wannierize`.

Impact:
- `.nnkp` prerequisite is not guaranteed in MCP-created Wannier workflows.
- This directly matches the observed runtime failure (`Could not find ... .nnkp`).

## 5.2 Wannier step parameters are not faithfully materialized into `.win`

In the Wannier materialization branch, only a narrow subset is copied (`num_wann`, `num_bands`, `num_iter`, `mp_grid`, `kpoints`, projection block):
- `src/qmatsuite/calculation/structure_steps.py:943-1038`

Then `.win` is written directly, but no pass-through of remaining step parameters occurs:
- `src/qmatsuite/calculation/structure_steps.py:1083-1107`

Yet the writer supports generic extra key/value emission:
- `src/qmatsuite/io/wannier90_input.py:89-101`

Observed evidence of this gap:
- Step YAML carried `spinors`, `auto_projections`, `berry`, `berry_task`, `berry_kmesh`, `postproc_setup`, disentanglement windows.
- Generated pre-manual `wannier.win` omitted these tags.
  - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1/steps/wannier.step.yaml`
  - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1/raw/wannier.win.bak`

Impact:
- MCP `set_parameters` appears successful but does not control runtime behavior for key AHC knobs.
- Agent is pushed to direct file surgery.

## 5.3 pw2wannier `INPUTPP` parameter plumbing is incomplete

`pw2wannier` materialization only sets `seedname`, `prefix`, `outdir`:
- `src/qmatsuite/calculation/structure_steps.py:1157-1181`

It does not propagate many `INPUTPP` controls from step YAML (including keys required for projection mode consistency).

`Pw2Wannier90Input` supports only a limited hardcoded set and has no generic passthrough:
- `src/qmatsuite/io/wannier90_input.py:336-377`

Observed evidence:
- Step YAML had `write_unk: true`, while generated `pw2wan.in` stayed at default `write_unk = .false.`.
  - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1/steps/pw2wannier.step.yaml`
  - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1/raw/pw2wan.in`

Impact:
- Projection-mode and SOC-related pw2wannier control is brittle from MCP APIs.

## 5.4 Seedname coherence is fragile without explicit prep chain

When no `.win` exists, `pw2wannier` seedname falls back to step slug:
- `src/qmatsuite/calculation/structure_steps.py:1170`

In attempt1 this produced `seedname='pw2wannier'`, so runtime searched `pw2wannier.nnkp` and failed:
- `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1/raw/pw2wan.in:4`
- `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1/raw/pw2wannier.out:51`

Impact:
- Missing prep + weak seed fallback compounds `.nnkp` failures.

## 5.5 No first-class MCP step/workflow for postw90 AHC stage

There is no `postw90` in public gen steps:
- `src/qmatsuite/workflow/gen_steps.py:16-61`

No corresponding step spec in workflow registry:
- `src/qmatsuite/workflow/registry.py:316-355` (has `w90_wannierprep`, `qe_pw2wannier`, `w90_wannier`, but no `postw90`).

W90 driver supports only prep and wannier:
- `src/qmatsuite/drivers/w90/driver.py:33-35`

Note: parts of runtime policy already mention `postw90` (done checks / verification), but taxonomy and execution plumbing are not connected:
- `src/qmatsuite/calculation/step_done.py:18`
- `src/qmatsuite/calculation/verification.py:99`

Impact:
- Even when Berry tags are set, MCP workflow cannot schedule `postw90.x` as a step.
- Agent must leave MCP and invoke `postw90.x` manually.

## 5.6 Analysis pipeline is calculation-engine keyed, not step-engine keyed

`list_analyses` uses `detail.engine_family` (calc-level engine):
- `src/qmatsuite/mcp/tools/list_analyses.py:54-67`

`get_analysis_instances_for_step` similarly chooses driver/parser via calc engine:
- `src/qmatsuite/api/service.py:1148-1159`
- Parser lookup uses `get_parser(engine, object_type)`:
- `src/qmatsuite/api/service.py:1193-1195`

QE capabilities include no AHC object:
- `src/qmatsuite/drivers/qe/driver.py:17-63`

W90 capabilities currently only `field3d`:
- `src/qmatsuite/drivers/w90/driver.py:38-44`

W90 parsers register only `scf_digest` and `field3d`:
- `src/qmatsuite/drivers/w90/parsers/output.py:63`
- `src/qmatsuite/drivers/w90/parsers/__init__.py:7-10`

Impact:
- AHC from `.wpout` is invisible to MCP analysis endpoints.
- Agent must parse raw text manually.

## 5.7 Status/result APIs can be stale relative to current calculation state

`get_status` marks a step completed if a successful run exists for that step ULID:
- `src/qmatsuite/mcp/tools/get_status.py:53-59`

`get_results_summary` resolves digest from the same latest-success query path:
- `src/qmatsuite/mcp/tools/get_results_summary.py:64-74`

Underlying query selects latest successful run by `step_ulid` only:
- `src/qmatsuite/api/service.py:8165-8170`

No check against current step SHA / manifest done state.

Observed in artifacts:
- Manifest for Fe attempts keeps `qe_pw2wannier` and `w90_wannier` done=false:
  - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1/.run_tmp_info/manifest.json:36`
  - `/Users/<username>/gpt_agent_test/project/calculations/fe_bcc_ahc_attempt1-1/.run_tmp_info/manifest.json:36`
- Provenance still contains at least one older run marked success for same calc/steps.

Impact:
- Agent may receive "completed" signals that do not reflect latest edited state.
- Agent may also read stale numerical summaries from older successful runs.
- Encourages confusing retries and direct shell debugging.

## 5.8 Guardrails are weak for SOC-Wannier-AHC configuration

Preflight is effectively restricted to pw.x-style steps when engine is `qe`:
- `src/qmatsuite/mcp/tools/inspect_calculation.py:107-119`

No dedicated W90 preflight checker is wired.

K-point mismatch currently only warns (non-blocking):
- `src/qmatsuite/calculation/structure_steps.py:1018-1026`

Automatic NSCF k-mesh extraction returns `None` (not explicit list):
- `src/qmatsuite/calculation/wannier90_kpoints.py:41-43`

`.win` writer does not enforce mutual exclusivity between `auto_projections` and explicit projection blocks:
- `src/qmatsuite/io/wannier90_input.py:89-137`

Impact:
- Common SOC/Wannier failure modes appear late at runtime.
- Agent gets long trial-and-error loops (spinor/projection/fermi/k-grid consistency).

## 5.9 MCP ergonomics regressions that reduce agent confidence

Silent step-add failures in key tools:
- `src/qmatsuite/mcp/tools/create_calculation.py:96-98`
- `src/qmatsuite/mcp/tools/quick_run.py:114-115`

This can hide missing/unsupported workflow steps.

Observed tool-schema friction in trace:
- Initial `list_available_resources` call failed schema then retried.
- Trace evidence: `task_1_trace...:15`
- Current code annotation expects list for elements:
  - `src/qmatsuite/mcp/tools/list_resources.py:17-19`

Impact:
- Agent may infer tool instability and switch to shell sooner.

## 5.10 Band-summary result payload lacks edge-location data

`get_results_summary` only exposes scalar gap/energy terms from digest:
- `src/qmatsuite/mcp/tools/get_results_summary.py:224-235`

QE digest itself has no VBM/CBM k-location fields:
- `src/qmatsuite/drivers/qe/parsers/output.py:17-27`

Impact:
- Even successful MCP bands workflows need raw-file postprocessing for VBM/CBM coordinates.

## 5.11 Parallel execution control is process-global, QE-centric, and not agent-overridable

How env enters runtime (confirmed in this repo + run artifacts):
- Client/server launch config injects env into the MCP server process:
  - `/Users/<username>/gpt_agent_test/.mcp.json`
  - `/Users/<username>/.codex/config.toml`
  - `/Users/<username>/QMatSuite/.tmp/task3_chain_a/project/.mcp.json`
  - Note: `/Users/<username>/QMatSuite/.tmp/task3_chain_a/.mcp.json` is absent; the effective file in that experiment tree is under `project/`.
- Batch harness also exports the same vars before agent launch:
  - `/Users/<username>/QMatSuite/.tmp/task3_chain_a/run_chain_a.sh:351-352`
- Engine config reads process env at construction time:
  - `src/qmatsuite/core/engines/base.py:35-40`
  - MPI validation/defaulting when cores > 1: `src/qmatsuite/core/engines/base.py:42-49`

Which executables this currently controls:
- QE command builder prepends `mpi_command -np mpi_cores` for QE-run steps when `mpi_cores > 1`:
  - `src/qmatsuite/drivers/qe/engine/qe_engine.py:423-426`
- QE recipe forces `wannierprep/pw2wannier/wannier` through QE handler:
  - `src/qmatsuite/drivers/qe/recipe.py:94-100`
- Therefore QE SCF/NSCF and QE-routed Wannier-chain stages all share one global MPI toggle.

Which executables this does *not* currently control in MCP flow:
- `postw90` is not a first-class executable step in workflow/step taxonomy (already covered in 5.5), so no MCP launch policy is applied to it.
- Standalone W90 execution path is not production-ready:
  - Default runtime engine registry does not register `w90`: `src/qmatsuite/engine/registry.py:66-95`
  - W90 handler execution is placeholder: `src/qmatsuite/drivers/w90/handler.py:154-164`

Agent-control reality today:
- MCP run tools expose no parallel controls:
  - `src/qmatsuite/mcp/tools/run_calculation.py:10`
- Service run path creates default registry without run-level MPI override input:
  - `src/qmatsuite/api/service.py:6377`
- If `QMS_MPI_*` is set in JSON/TOML launch config, agent cannot opt out from inside MCP.
- If `QMS_MPI_*` is not set, agent cannot opt in from inside MCP.
- Only out-of-band switches exist today: restart server/client session with different env, or leave MCP and run shell commands directly.

Additional consistency gap:
- Driver protocol includes `mpi_aware` metadata (`src/qmatsuite/core/driver_protocol.py:54`) and W90 marks `mpi_aware=False` (`src/qmatsuite/drivers/w90/driver.py:78,86`), but launch routing does not currently enforce/consume this metadata.

Impact:
- Agent cannot toggle serial/parallel during iterative recovery without leaving MCP.
- Mixed-capability pipelines (MPI-capable `pw2wannier90.x`, potentially serial Wannier binaries) remain opaque.
- Parallel behavior is not uniformly controllable across QE + Wannier executables.

## 5.12 Thought experiment: why agent still gets stuck on parallel/serial decisions

Likely path for a future agent on the same task:
1. MCP server starts with `QMS_MPI_CORES=12`.
2. SCF/NSCF run with MPI as expected.
3. Wannier stage shows behavior suggesting serial binary or unstable MPI behavior.
4. Agent decides to retry that stage in serial only.
5. MCP API offers no run-level launch override, so the agent cannot issue "serial retry for this run" through MCP.
6. Agent either:
   - keeps retrying with unchanged global MPI policy (wasting runs), or
   - drops to direct shell execution (`wannier90.x` / `postw90.x`) and exits MCP-native workflow.

This is exactly the “comfort gap”: even with correct scientific parameters, operational control is too coarse for autonomous recovery.

## 6. Minimum Patch Set (Prioritized)

This is the smallest coherent package that addresses both requirements:
- Agent can stay inside MCP for QE→Wannier90→AHC.
- Parameter/workflow complexity is reduced enough for autonomous operation.

## P0-A. Fix workflow correctness and visibility

Patch:
- Update `wannier` template to include `wannierprep` before `pw2wannier`.
  - `templates.py` sequence should become: `scf -> nscf -> wannierprep -> pw2wannier -> wannier`.
- In `create_calculation` and `quick_run`, stop swallowing step-add exceptions.
  - Return `steps_requested`, `steps_added`, `steps_failed` with explicit reasons.

Why minimal:
- One template correction + error-reporting behavior change.
- Immediately removes `.nnkp` structural failure and hidden-step ambiguity.

Acceptance criteria:
- New MCP-created QE wannier calc contains 5 steps including `w90_wannierprep`.
- If any workflow step cannot be instantiated, tool returns explicit error details (not silent pass).

## P0-B. Make Wannier-chain parameter plumbing truthful

Patch:
- In Wannier (`wannierprep` / `wannier`) materialization, pass through all non-structural W90 parameters to output `.win` (do not drop `spinors`, `auto_projections`, `berry*`, `postproc_setup`, disentanglement windows, `fermi_energy`, etc.).
- In `pw2wannier` materialization, propagate relevant `INPUTPP` parameters beyond `seedname/prefix/outdir` (at least `write_mmn`, `write_amn`, `write_unk`, `spin_component`; and projection-mode controls needed for SCDM/auto-projection paths).
- Add deterministic cross-step coupling:
  - Seedname must be coherent across `wannierprep -> pw2wannier -> wannier` without slug fallback drift.
  - If `.win` requests auto-projection mode, `pw2wannier` input should be made consistent (or preflight-blocked if inconsistent).

Why minimal:
- This directly fixes the biggest hidden failure: MCP `set_parameters` looked successful but runtime files ignored key settings.
- Without this, the agent still needs raw file editing even if other gaps are patched.

Acceptance criteria:
- Setting W90 keys via MCP is reflected verbatim in generated `.win`.
- Setting pw2wannier keys via MCP is reflected in generated `pw2wan.in`.
- No seedname drift like `pw2wannier.nnkp` mismatch in default flow.
- Fe SOC+AHC setup can reach consistent `pw2wannier`/Wannier runs without raw `.win` surgery.

## P0-C. Add MCP-native postw90 stage for AHC

Patch:
- Introduce first-class `postw90` step support end-to-end:
  - Add gen step + spec step + workflow exposure.
  - Add AHC-oriented workflow (e.g. `wannier_ahc`):
    - `scf -> nscf -> wannierprep -> pw2wannier -> wannier -> postw90`.
- Wire execution plumbing (not just taxonomy):
  - command routing / executable mapping / stdin policy / done policy for `postw90`.

Why minimal:
- Without this, AHC completion still requires direct engine invocation.
- This is the core MCP-coverage gap for the target task.

Acceptance criteria:
- Agent can run full Fe AHC pipeline without any shell commands.
- `run_calculation` includes a managed `postw90` step and records provenance normally.

## P0-D. Make analysis step-engine-aware and add AHC parser

Patch:
- In `list_analyses` and `get_analysis_instances_for_step`, resolve capabilities/parser by each step’s engine (`step_type_spec` prefix), not calculation engine family.
- Add W90 parser for AHC tensor from `.wpout` (object type `ahc`).
- Add W90 analysis capability for `postw90` evidence (`*.wpout`).
- Extend `plot_analysis` summary extraction for AHC tensor components/magnitude.

Why minimal:
- Execution alone is insufficient; agent must retrieve/compare AHC from MCP APIs.
- Eliminates manual `.wpout` grep/parsing.

Acceptance criteria:
- `list_analyses(..., step=postw90_step)` includes `ahc` with evidence available.
- `plot_analysis(..., object_type='ahc')` returns parsed tensor.
- No raw-file parsing needed for final AHC report.

## P0-MPI. Add explicit MCP launch policy (auto/serial/mpi) with per-step effective mode

Patch:
- Extend MCP run APIs with optional launch controls:
  - `run_calculation(..., launch_mode='auto'|'serial'|'mpi', mpi_cores=?, mpi_command=?)`
  - `run_step(..., launch_mode=..., mpi_cores=?, mpi_command=?)`
  - `quick_run(..., launch_mode=..., mpi_cores=?, mpi_command=?)`
- Thread launch policy through `svc.run.run_calculation(...)` and runner context so it can override process-env defaults *for that invocation only*.
- Centralize launch decision in one helper used by execution handlers:
  - Respect step `mpi_aware` metadata.
  - Add explicit executable capability flag for known serial binaries where needed.
  - If `launch_mode='mpi'` but a step is non-MPI-capable, fail fast with explicit diagnostic (no silent fallback).
  - If `launch_mode='serial'`, force no MPI wrapper even when `QMS_MPI_*` exists in server env.
- Return launch telemetry in step summaries/status:
  - `requested_launch_mode`
  - `effective_launch_mode`
  - `effective_command`
  - optional `launch_reason` (e.g., `non_mpi_capable_binary`)

Why minimal:
- Small API addition + one centralized runtime decision layer.
- Removes the need to restart MCP server just to switch serial/parallel.
- Gives a reusable contract for all engines while immediately unblocking QE/Wannier workflows.

Acceptance criteria:
- With global `QMS_MPI_CORES=12`, agent can run a serial retry via MCP only.
- With no global MPI env, agent can opt into MPI via MCP only.
- Per-step output makes serial vs MPI execution explicit for QE/Wannier chain.
- No direct shell fallback is needed solely for launch-mode switching.

## P1-E. Add SOC-Wannier guardrails (fast-fail preflight)

Patch:
- Add W90/Wannier-chain preflight checks surfaced in `inspect_calculation`:
  - If upstream NSCF has `noncolin/lspinorb`, require `spinors=true`.
  - Flag/block `auto_projections=true` + explicit projections co-existence.
  - If `berry=true`, require `berry_task`, `berry_kmesh`, and `fermi_energy`.
  - Promote NSCF/W90 k-grid mismatch from warning to blocking for Wannier workflows.
- Improve `extract_kpoints_from_qe_input` to expand `K_POINTS automatic` into explicit ordered list.

Why minimal:
- Converts runtime trial-and-error into deterministic pre-run guidance.

Acceptance criteria:
- Known bad SOC/projection/fermi/k-grid configurations are blocked before run.
- Agent receives actionable MCP preflight issues for these cases.

## P1-F. Make status reporting reflect current state, not stale history

Patch:
- `get_status` and `get_results_summary` should prioritize current manifest `done` state (and current step SHA context) over "any historical successful run for step ULID".
- Return `status_source` and `stale_reason` fields when historical success exists but current step state is invalidated.

Why minimal:
- Avoids contradictory agent guidance during iterative fixing.

Acceptance criteria:
- After step parameter change invalidates manifest done, status returns not completed.
- Historical successful runs no longer mask current incomplete state in status or summary paths.

## P2-G. Agent comfort improvements (small, high leverage)

Patch:
- Add default parameter scaffolds for Wannier chain step types in `step_defaults.py`:
  - `w90_wannierprep`, `qe_pw2wannier`, `w90_wannier` (and new `postw90` step if added).
- Add a focused preset profile for SOC metal Wannier-AHC workflows.
- Extend bands summary payload to include VBM/CBM k-locations (from bands object), not only scalar band gap.
- Fix MCP tool schema consistency for list-valued args (`elements`) to avoid first-call mismatch.
- Improve error-enrichment hints to point agents to launch controls (`launch_mode`, `mpi_cores`) when runtime behavior suggests serial/parallel mismatch.

Why minimal:
- Keeps agent from spending tokens searching/guessing large parameter surfaces.

Acceptance criteria:
- AHC run can be configured with no raw `.win` surgery.
- Si bands task returns VBM/CBM locations directly from MCP summary APIs.
- Agent can see whether postw90 is configured to run serial or MPI before launching a long mesh run.

## 7. Suggested Delivery Order

1. P0-A (template + no silent failures)  
2. P0-B (parameter plumbing truthfulness + seed/projection coupling)  
3. P0-C (postw90 first-class execution)  
4. P0-D (analysis/parser for AHC + step-engine-aware resolution)  
5. P0-MPI (MCP-level launch policy + per-step launch telemetry)  
6. P1-E (preflight guardrails)  
7. P1-F (status truthfulness)  
8. P2-G (comfort improvements)

This order gives immediate "stay in MCP" capability first, then makes it robust and comfortable.

## 8. Expected Outcome After Minimum Patch Set

For the same Fe AHC task, a future agent should be able to:
- Use only MCP tools from project init to final AHC tensor retrieval.
- Avoid manual `wannier90.x -pp`, `pw2wannier90.x`, and `postw90.x` shell invocations.
- Trust that MCP `set_parameters` on Wannier/pw2wannier actually controls generated runtime inputs.
- Switch between serial and MPI from MCP calls (per run) without restarting MCP server.
- Receive early, explicit validation when SOC/projection/fermi/k-grid settings are inconsistent.
- Trust `get_status`, `get_results_summary`, and `list_analyses` as current-state truthful.

For Si bands, the agent should:
- Either get k-path guidance up front or receive direct summary fields for VBM/CBM locations without manual raw parsing.

## 9. Final Judgment

The fallback to direct engine invocation was not primarily an "agent behavior" problem. It was a product-gap cluster:
- Incorrect default workflow shape for QE→Wannier handoff.
- Broken parameter plumbing where MCP step parameters were not faithfully reflected in generated Wannier-chain input files.
- Missing first-class postw90/AHC execution and parsing in MCP.
- Engine-resolution and status semantics that hide or blur true state during iterative recovery.
- Process-global MPI control with no MCP run-level override, making serial/parallel recovery non-autonomous.

Applying P0-A through P0-D together is the minimum credible "once-through MCP" fix.  
Without P0-B (parameter plumbing truthfulness), the agent still needs raw-file surgery even if workflow and postw90 support are added.
