# Local vs Remote Experiment Audit

Date: 2026-03-12
Branch: `v2-python`
Remote baseline: `origin/v2-python` at `c893dbb9` (`v1.2.4`)
Local HEAD: `f369738a`
Method:

- static diff + governance audit by reviewer
- full-suite result provided by user and incorporated below
- reviewer did not independently run the full suite

## Scope

This audit answers:

1. What differs between the current local workspace and the GitHub remote branch?
2. Are the local edits consistent with the constitution, laws, specs, kernel/API/GUI/MCP layering, and engine guide?
3. Are the edits limited to the ORCA execution path?
4. What is the risk to other engines, especially QE?
5. If these local edits were to be pushed, what should the push plan be?

## Governance Reviewed

Authoritative and binding references reviewed for this audit:

- `CONSTITUTION.md`
- `docs/laws/README.md`
- `docs/laws/L1/API_CONSTITUTION.md`
- `docs/laws/L1/KERNEL_DEPENDENCY_SPEC.md`
- `docs/laws/L1/ENGINE_INTEGRATION_CONSTITUTION.md`
- `docs/laws/L1/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md`
- `docs/laws/L2/MULTI_FRONTEND_ARCHITECTURE_SPEC.md`
- `docs/laws/L2/engine_driver_protocol.md`
- `docs/laws/L2/engine_registry_and_dispatch.md`
- `docs/laws/L2/B1_ENGINE_PLAYBOOK.md`
- `docs/laws/L2/RELAX_SPEC.md`

Key constraints used in the assessment:

- API must remain thin, with frontends calling API only (`docs/laws/L1/API_CONSTITUTION.md:14-16`, `:52-74`).
- Frontends/tools must not bypass API into kernel (`docs/laws/L2/MULTI_FRONTEND_ARCHITECTURE_SPEC.md:15-24`, `:140-190`).
- Engine routing must use explicit registry lookup; no silent fallback, no "log and continue" on unknown routing (`docs/laws/L1/ENGINE_INTEGRATION_CONSTITUTION.md:18-64`).
- Relax structure artifacts are expected at `generated_structures/step_<ulid>/current.json` and use the same schema as project structures (`docs/laws/L2/RELAX_SPEC.md:40-49`, `:55-89`).
- B1 engine work is driver-level only; it should not casually spill into kernel/API/shared infrastructure (`docs/laws/L2/B1_ENGINE_PLAYBOOK.md:16`, `:28-32`).
- Engines are supposed to consume runtime-provided input rather than read SSOT YAML directly (`docs/laws/L1/KERNEL_DEPENDENCY_SPEC.md:222`, plus the ORCA file already contains `K4-ALLOW` comments acknowledging transitional debt).

## Repository State Summary

### 1. Branch position

Local `HEAD` is behind remote by 2 commits:

- `4522e960` `refactor: remove obsolete CRASH file and add HUBBARD key to parameter set in set_parameters.py`
- `c893dbb9` `chore: bump version to v1.2.4`

This matters because a naive push from the current local state would not only publish the experimental edits; it would also reintroduce already-removed / already-updated upstream content unless first rebased onto `origin/v2-python`.

### 2. Unstaged local modifications

Current unstaged local edits:

- `gui/package-lock.json`
- `gui/package.json`
- `src/qmatsuite/api/service.py`
- `src/qmatsuite/calculation/structure_steps.py`
- `src/qmatsuite/engine/orca_engine.py`
- `src/qmatsuite/engine/registry.py`
- `src/qmatsuite/engines/orca/input_compiler.py`
- `src/qmatsuite/inputformat/structure_utils.py`
- `src/qmatsuite/mcp/knowledge/__init__.py`
- `src/qmatsuite/mcp/knowledge/store.py`
- `src/qmatsuite/mcp/tools/inspect_calculation.py`
- `tests/unit/orca/test_input_compiler.py`

### 3. Additional local-vs-remote drift caused by being behind remote

These appear in `git diff origin/v2-python` but are not current unstaged edits:

- `CRASH` would be re-added locally relative to remote
- `pyproject.toml` is still `1.2.3` locally vs `1.2.4` on remote
- `src/qmatsuite/__init__.py` is still `1.2.3` locally vs `1.2.4` on remote
- `src/qmatsuite/mcp/tools/set_parameters.py` locally lacks `HUBBARD` in `_QE_CARD_KEYS`, while remote added it in `4522e960`

This is the most important distinction in the whole audit:

- Not every local-vs-remote difference is part of the current experiment.
- But if pushed carelessly, those remote regressions would still be part of the push outcome.

## Full Test Suite Result Provided by User

User-provided suite result:

- `36 failed`
- `6683 passed`
- `196 skipped`
- `2 errors`
- wall time `989.94s` (`0:16:29`)

The reviewer did not rerun the full suite. The interpretation below is based on the failure summary supplied by the user.

### Failure clusters from the supplied run

#### 1. Environment / test harness failures

`tests/gates/test_gen_spec_convergence_gate.py` has 23 failures, all due to:

- `FileNotFoundError: [Errno 2] No such file or directory: 'rg'`

Interpretation:

- These are not meaningful signals about the local experiment itself.
- They indicate the test environment used for the full suite did not have `rg` on `PATH`.
- They should be treated as harness/environment failures, not merge-blocking architecture regressions from the edited files.

#### 2. QE executable availability failures

Observed failures and errors include:

- missing `dos.x`
- missing `ph.x`

Representative examples:

- `tests/cli/test_si_dos_calculation_cli.py`
- `tests/integration/test_ph_quick_tests.py`

Interpretation:

- These are also at least partly environment/toolchain issues, not necessarily code regressions from the local patch.
- They do, however, matter for release readiness and for interpreting QE-related failures below.

#### 3. QE bands / DOS / Wannier workflow failures

Observed failures include:

- bands `.gnu` output not found
- DOS analysis in `missing_evidence` state instead of `ok`
- CLI/template calculations reporting `FAILED`
- Wannier workflow missing `wannierprep.nnkp`
- golden daemon / integration bands failures
- missing SCF `run_ulid` in history for a QE bands realrun test

Representative failing tests:

- `tests/cli/test_si_bands_manual_calculation_cli.py`
- `tests/cli/test_template_calculation.py`
- `tests/cli/test_si_bands_auto_calculation_cli.py`
- `tests/daemon/contract/test_realrun_al_dos.py`
- `tests/daemon/contract/test_realrun_si_dos.py`
- `tests/cli/test_cli_output_contracts.py`
- `tests/daemon/contract/test_realrun_qe_wannier.py`
- `tests/integration/test_si_bands_calculation.py`
- `tests/daemon/test_si_bands_golden_daemon.py`
- `tests/daemon/contract/test_realrun_si_bands.py`
- `tests/integration/test_si_dos_calculation.py`
- `tests/cli/test_si_dos_calculation_comprehensive.py`

Interpretation:

- These failures are highly relevant to the push decision.
- They show the local workspace, as tested in the user’s environment, is not currently safe for push as a general branch update.
- They are QE-heavy and not confined to ORCA.

Important caution:

- The supplied failure summary alone does not prove these failures were caused by the current unstaged edits.
- Some may be preexisting, and some may be downstream consequences of missing QE binaries.
- But from a push-readiness standpoint, that distinction does not rescue the branch: the tested state is still not acceptable for merge without triage.

## Difference Summary by Theme

### A. ORCA-specific changes

Files:

- `src/qmatsuite/engine/orca_engine.py`
- `src/qmatsuite/engines/orca/input_compiler.py`
- `tests/unit/orca/test_input_compiler.py`

Observed changes:

- ORCA chain wrapping now falls back from registry lookup to `normalize_step_type_to_gen(step_type)` when the registry returns no spec.
- ORCA input compiler now:
  - preserves keyword order instead of sorting
  - supports explicit `keyword_line`
  - injects `Opt` and `%geom` when the root step itself is `relax`
  - reads explicit `charge`, `multiplicity`, and `spin_multiplicity`
  - deduplicates keywords case-insensitively
- One new ORCA unit test covers relax-root compilation.

### B. Shared structure / relax artifact handling changes

Files:

- `src/qmatsuite/api/service.py`
- `src/qmatsuite/inputformat/structure_utils.py`
- `src/qmatsuite/calculation/structure_steps.py`
- `src/qmatsuite/mcp/tools/inspect_calculation.py`

Observed changes:

- Promote-relax logic in API now prefers `generated_structures/step_<ulid>/current.json` before engine-specific output parsing.
- Shared `structure_to_dict()` now supports both periodic structures and molecules.
- Materialization for `content_role == "combined"` now uses that shared structure conversion helper.
- MCP `inspect_calculation` now emits molecular `StructureDoc` using `cart_coords` when lattice is absent.

These changes are not ORCA-only.

### C. Shared engine registry behavior change

File:

- `src/qmatsuite/engine/registry.py`

Observed changes:

- `create_default_registry()` no longer registers engines directly.
- It now wraps every engine registration in `_try_register(...)` and converts any registration-time failure into a warning plus silent omission from the registry.

This affects all engines, including QE.

### D. MCP knowledge changes

Files:

- `src/qmatsuite/mcp/knowledge/__init__.py`
- `src/qmatsuite/mcp/knowledge/store.py`

Observed changes:

- Builtin knowledge DB access/build is now conditional on `_builtin_enabled()`.
- Local DB remains available.

These changes are not ORCA-only, but they are limited to the MCP knowledge subsystem.

### E. GUI/package drift

Files:

- `gui/package.json`
- `gui/package-lock.json`

Observed changes:

- GUI version changed from `1.2.4` back to `1.2.3`
- Playwright dev dependencies bumped to `1.58.2`

This is unrelated to ORCA execution.

## Findings

### Finding 1: `engine/registry.py` introduces a cross-engine silent-failure path that conflicts with the engine integration constitution

Severity: High

Evidence:

- `src/qmatsuite/engine/registry.py:72-104` now swallows registration exceptions for `qe`, `pyscf`, `orca`, `vasp`, `lammps`, `cp2k`, `qmcpack`, `psi4`, and `gpaw`.
- The engine integration constitution explicitly requires hard errors for unknown/invalid routing states and explicitly forbids "logging a warning and continuing" (`docs/laws/L1/ENGINE_INTEGRATION_CONSTITUTION.md:47-64`).

Why this matters:

- This is not ORCA-local.
- If `QeEngine(...)` or another engine constructor starts failing because of an environment or code regression, the registry can now come up in a degraded, partially populated state instead of failing fast.
- That changes failure semantics for every caller of `create_default_registry()`, including CLI, API service paths, presets/capability logic, and integration paths that expect QE to exist.

QE risk:

- Direct risk to QE is real. `create_default_registry()` is used in multiple QE-related flows and tests. A QE registration failure would now manifest as "QE missing from registry" later rather than an immediate, explainable failure at registry construction.

Consistency verdict:

- Not consistent with `ENGINE_INTEGRATION_CONSTITUTION.md`.
- Not a safe "quick fix" to push as-is.

### Finding 2: the local changes are not limited to the ORCA execution path

Severity: High for scope-control; not necessarily high for runtime breakage

Evidence:

- Shared/API files changed: `src/qmatsuite/api/service.py`, `src/qmatsuite/inputformat/structure_utils.py`, `src/qmatsuite/calculation/structure_steps.py`, `src/qmatsuite/mcp/tools/inspect_calculation.py`, `src/qmatsuite/mcp/knowledge/*`, `src/qmatsuite/engine/registry.py`
- GUI/package files changed as well.

Conclusion:

- The answer to "are they only limited to ORCA execution path?" is no.
- Some edits are ORCA-specific, but the workspace currently contains broader shared-path changes and packaging drift.

### Finding 3: pushing the current local state without rebasing would reintroduce upstream regressions, including a QE-facing MCP regression

Severity: High

Evidence:

- Remote commit `4522e960` removed `CRASH` and added `HUBBARD` to `_QE_CARD_KEYS` in `src/qmatsuite/mcp/tools/set_parameters.py`.
- Local branch is behind that commit.
- Remote commit `c893dbb9` bumped versions to `1.2.4`; local still has `1.2.3` in:
  - `pyproject.toml:7`
  - `src/qmatsuite/__init__.py:14`
  - `gui/package.json:4`

QE risk:

- The missing `HUBBARD` routing is specifically QE-relevant. Pushing the current local branch state wholesale would risk regressing QE MCP parameter handling.

Consistency verdict:

- This is inconsistent with a safe merge/release process.
- It is not evidence that the unstaged experiment itself touched QE MCP, but it is a concrete push risk.

### Finding 3A: the user’s full-suite result confirms that the tested local state is not push-ready, with failures concentrated in QE workflows rather than ORCA

Severity: High

Evidence from the supplied suite summary:

- QE bands failures
- QE DOS failures
- QE Wannier failure
- CLI output contract failures around QE calculations
- integration failures in Si bands / Si DOS
- missing `run_ulid` history in a QE bands contract test

Assessment:

- Whatever the exact root-cause split between environment and code, the tested branch state is currently unstable in QE-facing workflows.
- This materially strengthens the earlier static-risk conclusion: even if the experimental intent was ORCA repair, the branch state now carries broad QE-facing failure surface.

What this means for the audit question:

- The answer to "any risk of changing behavior of other engines, especially QE?" is now an unequivocal yes.
- The user-supplied suite result is direct evidence of broad QE-path instability in the tested state.

Scope note:

- The provided failures do not directly implicate the ORCA compiler edits.
- The failures are instead concentrated around QE execution, analysis, artifacts, and contract expectations.

### Finding 4: the `api/service.py` relax-promotion change is broadly consistent with the relax spec and is safer than the old QE-specific parse-first fallback

Severity: Low to Medium

Evidence:

- `src/qmatsuite/api/service.py:2483-2535` now prefers `generated_structures/step_<ulid>/current.json`.
- `docs/laws/L2/RELAX_SPEC.md:43-49` defines that path as the artifact location and states that `current.json` uses the same schema as project structures.

Assessment:

- This change is directionally correct and more aligned with the relax artifact contract than directly parsing engine output first.
- It also reduces QE-special handling by preferring the generic artifact.

Risk:

- Moderate only because it changes behavior for all relax-capable engines, not just ORCA.
- The main missing piece is verification coverage, not architectural inconsistency.

Consistency verdict:

- Consistent with `RELAX_SPEC`.
- Reasonable candidate for upstreaming if backed by tests.

Additional note after the supplied suite result:

- The current failure summary does not point to relax-promotion as the primary observed breakage cluster.
- The larger observed problem is QE workflow completeness and artifact production in bands/DOS/Wannier paths.

### Finding 5: the structure conversion changes are shared-path edits but appear architecturally sound

Severity: Low to Medium

Evidence:

- `src/qmatsuite/inputformat/structure_utils.py:27-60` now supports molecules (`cart_coords`) as well as periodic structures.
- `src/qmatsuite/calculation/structure_steps.py:1438-1448` now uses `structure_to_dict()` centrally.
- `src/qmatsuite/mcp/tools/inspect_calculation.py:270-309` mirrors the same molecule-vs-periodic distinction.

Assessment:

- This is a sensible unification of `StructureDoc` handling across API/MCP/materialization.
- It is not ORCA-only.
- It fits the repo’s existing use of `cart_coords` for molecular engines and the relax artifact schema.

Risk:

- Shared-path risk exists because `structure_to_dict()` is reused by materialization.
- However, this is a coherent generalization rather than an obviously dangerous shortcut.

Consistency verdict:

- Largely consistent with the architecture and relax/schema direction.
- Needs targeted regression coverage before merge.

### Finding 6: the ORCA input compiler changes look like plausible bug fixes, but one piece relies on non-constitutional fallback behavior

Severity: Medium

Evidence:

- `src/qmatsuite/engines/orca/input_compiler.py:52-185` contains the bulk of the functional ORCA changes.
- `src/qmatsuite/engine/orca_engine.py:654-685` now falls back to `normalize_step_type_to_gen(step_type)` if registry lookup misses.
- `src/qmatsuite/workflow/registry.py:1329-1363` still contains legacy-style normalization/fallback logic, including prefix stripping.

Assessment:

- The compiler-side changes are reasonable ORCA fixes:
  - relax-root chains need `Opt`
  - explicit keyword ordering is defensible for ORCA input
  - explicit charge/multiplicity overrides are useful
- The `orca_engine.py` fallback is less clean:
  - it allows operation after registry miss instead of treating the miss as an error
  - that is adjacent to the same "no guessing / hard error" principle from the engine integration constitution

Scope:

- This specific fallback is ORCA-path-local.
- It does not directly affect QE.

Consistency verdict:

- Compiler changes: mostly consistent, reasonable experimental fixes.
- Registry-miss fallback in ORCA chain detection: not ideal constitutionally; should likely fail fast instead.

### Finding 7: the MCP knowledge toggle is low-risk and contained, but still not ORCA-only

Severity: Low

Evidence:

- `src/qmatsuite/mcp/knowledge/__init__.py:17-29`
- `src/qmatsuite/mcp/knowledge/store.py:174-198`, `:671-678`

Assessment:

- This looks like a contained configuration change for builtin/local knowledge DB behavior.
- It does not touch engine execution or QE execution paths.

Consistency verdict:

- Acceptable from an architectural standpoint.
- Independent of the ORCA experiment.

### Finding 8: the full-suite result includes many failures that are probably environmental, but that does not reduce merge risk

Severity: Medium to High

Evidence:

- 23 gate failures are due to missing `rg`
- 2 errors are due to missing `ph.x`
- at least one DOS CLI failure explicitly reports missing `dos.x`

Assessment:

- These likely do not come from the local code edits themselves.
- But they still block a confident push from this exact tested state because they mask the signal needed to separate true regressions from environment issues.

Practical consequence:

- Before any merge decision, the suite needs a normalized environment with:
  - `rg` on `PATH`
  - complete QE toolchain for the intended test matrix (`pw.x`, `bands.x`, `dos.x`, `ph.x`, Wannier-related tools as required)

This is a mitigation requirement, not an exoneration of the local patch.

## Answers to the Specific Questions

### Are the local edits consistent with the constitution, laws, specs, layering, and engine guide?

Partially.

Consistent or directionally consistent:

- `api/service.py` shift to `generated_structures/.../current.json`
- `structure_utils.py` molecule support
- `structure_steps.py` use of shared structure conversion
- `mcp/tools/inspect_calculation.py` molecular structure docs
- most of the ORCA input compiler changes
- MCP knowledge builtin toggle

Not consistent or at least not cleanly aligned:

- `engine/registry.py` silent skip on engine registration failure
- `orca_engine.py` fallback after registry miss instead of explicit failure
- any attempt to treat the current workspace as a clean ORCA-only B1 patch, because the actual edit set crosses shared infrastructure and package/version files

Also note:

- The repo is already carrying transitional ORCA SSOT-reading debt (`yaml.safe_load` in `orca_engine.py` marked `K4-ALLOW`). The local edit does not introduce that debt, but it also does not move the ORCA path toward the intended `EngineInput` contract.

### Are the edits only limited to ORCA execution path?

No.

They include:

- shared engine registry behavior
- shared API relax promotion behavior
- shared structure serialization/materialization behavior
- MCP inspection and knowledge behavior
- GUI/package/version drift

Only part of the patch set is ORCA-specific.

### Is there risk of changing behavior of other engines, especially QE?

Yes.

Highest risk:

- `src/qmatsuite/engine/registry.py` affects all engines, including QE.

Meaningful but probably acceptable if tested:

- `src/qmatsuite/api/service.py` and shared structure-doc changes affect all relax-capable engines, including QE.

Push-process risk to QE:

- Because local `HEAD` is behind remote, pushing the current local branch state carelessly would revert the remote `HUBBARD` MCP fix for QE and revert the version bump to `1.2.4`.

Observed test-state risk to QE:

- The user-provided full-suite run shows multiple QE bands/DOS/Wannier failures and contract failures.
- Regardless of exact causality, this is direct evidence that the tested state is not isolated to ORCA and is not safe to promote as a branch-wide update.

ORCA-only low spillover:

- `src/qmatsuite/engines/orca/input_compiler.py`
- `src/qmatsuite/engine/orca_engine.py`
- `tests/unit/orca/test_input_compiler.py`

## Risk Assessment

### As the workspace stands today

Overall push risk: High

Reason:

- The workspace is a mixed state: experimental ORCA fixes + shared-path changes + branch-behind-remote drift.
- The registry change alters global engine failure semantics.
- A naive push would likely also reintroduce upstream regressions unrelated to the experiment.
- The user-provided full-suite result shows the tested state currently fails broadly in QE-facing workflows.

### By change group

Low risk:

- MCP knowledge builtin toggle

Low to medium risk:

- ORCA input compiler improvements
- shared structure serialization changes
- API prefer-`current.json` relax promotion

Medium risk:

- ORCA registry-miss fallback in `orca_engine.py`

High risk:

- `engine/registry.py` silent registration skip
- any push that is not first rebased onto `origin/v2-python`
- any push that carries the local `1.2.3` version files / `CRASH` / missing QE `HUBBARD` routing
- any push attempt before triaging the QE workflow failures observed in the supplied suite result

## Recommended Push Plan

### Goal

Upstream only the parts that are architecturally sound, intentionally scoped, and validated against the current remote head.

### Plan

1. Rebase or restack onto `origin/v2-python` first.
   - This is mandatory.
   - Do not push from the current behind-remote base.

2. Explicitly discard non-mergeable drift from the experimental patch.
   - Do not re-add `CRASH`.
   - Do not revert version files from `1.2.4` to `1.2.3`.
   - Keep the remote `HUBBARD` fix in `src/qmatsuite/mcp/tools/set_parameters.py`.

3. Split the work into separate reviewable commits or PRs.
   - PR A: ORCA-only compiler/runtime fixes
   - PR B: generic relax artifact / structure-doc fixes
   - PR C: MCP knowledge toggle, only if still wanted
   - Do not include `engine/registry.py` in any of those unless there is an explicit architecture decision to change failure semantics

4. Remove or redesign the registry silent-skip change.
   - Preferred outcome: revert it.
   - If the product requirement is "list capabilities even when some engines are unavailable", implement that through explicit capability metadata or a scoped allowlist, not blanket exception swallowing across all engine constructors.

5. Tighten the ORCA fallback path.
   - Prefer explicit registry-based failure over `normalize_step_type_to_gen(...)` after miss.
   - If compatibility behavior is required, document it and isolate it behind a narrow, tested adapter.

6. Add or verify targeted coverage before merge.
   - ORCA relax-root compilation
   - ORCA explicit `keyword_line`
   - ORCA explicit charge/multiplicity
   - promote-relax via `generated_structures/.../current.json` for at least QE and one molecular engine
   - molecule `StructureDoc` materialization path
   - registry construction behavior, specifically ensuring QE cannot disappear silently

7. Normalize the test environment before using the suite as a merge gate.
   - Ensure `rg` is installed/on `PATH`.
   - Ensure the intended QE executables are available for the selected test matrix, especially `dos.x` and `ph.x`.
   - Re-run the relevant QE-heavy clusters after environment normalization.

8. Use the normalized suite result as the final gate.
   - Since this audit did not independently run the full suite, merge confidence must come from the user’s full-suite outcome after environment normalization plus targeted review of the high-risk files above.

## Suggested Mergeability Decision

### Safe to consider for merge after rebase and validation

- `src/qmatsuite/api/service.py`
- `src/qmatsuite/inputformat/structure_utils.py`
- `src/qmatsuite/calculation/structure_steps.py`
- `src/qmatsuite/mcp/tools/inspect_calculation.py`
- `src/qmatsuite/engines/orca/input_compiler.py`
- `tests/unit/orca/test_input_compiler.py`
- possibly `src/qmatsuite/mcp/knowledge/__init__.py`
- possibly `src/qmatsuite/mcp/knowledge/store.py`

### Should not be merged as-is

- `src/qmatsuite/engine/registry.py`

### Must be excluded from any push unless independently intended

- `gui/package.json`
- `gui/package-lock.json`
- branch-behind-remote version drift in `pyproject.toml` and `src/qmatsuite/__init__.py`
- remote-only regression risk around `src/qmatsuite/mcp/tools/set_parameters.py`
- `CRASH`

## Bottom Line

The local workspace is not an ORCA-only patch. It contains:

- real ORCA execution/input fixes
- shared relax/structure improvements that are mostly architecturally sound
- one high-risk cross-engine registry change
- unrelated package/version drift
- remote-behind branch drift that would create avoidable regressions if pushed carelessly

The user-provided full-suite result strengthens that conclusion:

- the tested state is not stable in QE-heavy workflows
- some failures are clearly environmental (`rg`, missing QE executables)
- but the branch is still not in a pushable condition until QE failures are triaged in a normalized environment

If the goal is to upstream the experimental work, the correct move is not "push local". The correct move is:

1. rebase to current remote,
2. drop unrelated drift,
3. split ORCA fixes from shared relax/structure fixes,
4. reject or redesign the registry silent-failure change,
5. normalize the test environment,
6. re-run the QE-heavy failing clusters,
7. gate the result on those outcomes plus the full suite.
