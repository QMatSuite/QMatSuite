# Distribution Step 3 Micromamba Integration Worklog (2026-02-22)

## Scope and hard rules

- Scope: Step 3 only (micromamba integration + engine install/manage APIs + daemon/CLI wiring + tests).
- Worklog location rule: this worklog is under `docs/history/worklogs/`; no root-level worklogs.
- Full-suite command rule (strict):
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Full-suite execution rule: one full run at a time, wait for completion before proceeding.
- Practical test cadence: run targeted suites during implementation; reserve full suite for milestone verification to avoid serial 6-minute reruns.

## Mandatory reading and code survey completed before coding

### Design doc

- `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` (full read; focus sections re-reviewed):
  - §3.4 Micromamba Integration
  - §3.5 Discovery Flow
  - §3.6 / §3.9 GitHub Release download mechanism
  - §3.8 Python engine management
  - §4.3 Embedded Python via micromamba decision

### Laws / architecture docs

- `CONSTITUTION.md`
- `docs/laws/L1/API_CONSTITUTION.md`
- `docs/laws/L1/KERNEL_DEPENDENCY_SPEC.md`
- `docs/laws/L2/MULTI_FRONTEND_ARCHITECTURE_SPEC.md`
- `docs/laws/L2/engine_registry_and_dispatch.md`
- `docs/laws/L2/engine_driver_protocol.md`

Key constraints extracted for this step:
- Frontends (daemon/CLI/MCP) must call API layer; no direct kernel calls from frontend handlers.
- Kernel must not import API.
- New installation/discovery state lives in kernel (`core/engines/*`) and is surfaced via thin API wrappers.

### Step 2 foundation reviewed

- `src/qmatsuite/core/engines/engine_meta.py`
- `src/qmatsuite/core/engines/engine_registry.py`
- `src/qmatsuite/api/engines.py`
- `docs/history/worklogs/DISTRIBUTION_STEP2_ENGINE_REGISTRY_2026-02-22_WORKLOG.md`

### Existing implementation audit for Step 3

- Existing conda/micromamba references:
  - `core/engines/engine_registry.py` already scans `<app_data>/micromamba/envs/*`.
  - `core/engines/discovery.py` still has legacy conda-tier probing (to be left compatible unless needed).
  - xTB handler still suggests manual conda install in error text.
- Existing download+checksum pattern available for reuse:
  - `core/pseudo_config.py` (`compute_sha256`, `download_github_release_asset`).
- Daemon async infrastructure for long-running tasks already exists:
  - `daemon/jobs.py` and RPC polling endpoints (`get_job_status`, `list_jobs`, etc.).
- CLI currently has no `qms engine ...` subcommands.

## Task 0 architecture plan (completed before code changes)

### 1) Module placement (kernel vs API)

Kernel modules (new):
- `src/qmatsuite/core/engines/micromamba.py`
  - micromamba binary acquisition, checksum verification, command wrappers, env lifecycle.
- `src/qmatsuite/core/engines/engine_installer.py`
  - engine installation/uninstallation orchestration, install verification, engines.json registration.

API module (extend existing):
- `src/qmatsuite/api/engines.py`
  - add thin API wrappers for install/uninstall/list-installable operations.

Frontend integration:
- Daemon (`src/qmatsuite/daemon/server.py`) adds RPC handlers that call API functions only.
- CLI (`src/qmatsuite/cli/main.py`) adds `qms engine ...` commands that call API functions only.

Justification:
- Keeps filesystem/process management in kernel.
- Preserves frontend boundary law (H1) by routing through API.

### 2) Kernel/API split details

Kernel responsibilities:
- micromamba binary management:
  - resolve platform artifact name from `(platform.system(), platform.machine())`
  - download micromamba + checksum asset
  - verify SHA256
  - atomic placement in `<app_data>/micromamba/bin`
  - unix executable bit and optional macOS ad-hoc signing
- conda env management:
  - create/remove/list envs under `<app_data>/micromamba/envs`
  - run micromamba commands with `MAMBA_ROOT_PREFIX=<app_data>/micromamba`
- engine install orchestration:
  - conda install path
  - GitHub release install path (initially QE-focused)
  - install verification (binary --version or python import)
  - engines.json registration and active installation management
- uninstall orchestration:
  - remove env or engine dir
  - remove installation from registry and rotate active pointer

API responsibilities:
- public wrappers with normalized dict outputs:
  - `install_engine(engine_family, version=None, source="auto")`
  - `uninstall_engine(engine_family, installation_id)`
  - `list_installable_engines()`
- keep existing API-level engine ops (`list_engines`, `verify_engine`, etc.) unchanged and compatible.

Daemon responsibilities:
- add RPC methods that call API wrappers:
  - `engine.install`
  - `engine.uninstall`
  - `engine.list_installable`
- use `JobManager` for background installation to provide task/job polling via existing `get_job_status`.

CLI responsibilities:
- add `qms engine` group:
  - `list`, `install`, `uninstall`, `verify`, `path`.
- CLI calls API only; no kernel imports.

### 3) Install methods by engine family

Planned method policy:
- `conda` installable (from ENGINE_META conda fields):
  - `qe`, `xtb`, `lammps`, `abinit`, `cp2k`, `siesta`, `qmcpack`, `pyscf`, `psi4`, `gpaw`.
- manual-only (commercial/restricted/no package configured):
  - `vasp`, `orca`, `gaussian`, `w90`, `yambo` (unless explicit package support added later).
- GitHub release path:
  - implemented for QE as alternative source (`source="github_release"`).

Versioned env naming convention:
- `<engine>-<version-or-latest>`
- stored under `<app_data>/micromamba/envs/<name>/`.

### 4) Registry integration plan

- Reuse Step 2 `EngineRegistry` for install persistence.
- Install record shape:
  - binary engines: `id`, `source`, `version`, `path`, `required_binaries`, `conda_env?`, `release_url?`, `verified`
  - python engines: `id`, `source`, `version`, `python_executable`, `conda_env?`, `verified`
- Set active installation if none active; for explicit install actions we will set the newly installed record active.

### 5) Progress reporting strategy

- Use existing daemon `JobManager` for install/uninstall commands.
- `engine.install` and `engine.uninstall` return `{job_id, status}` immediately.
- Client reads progress/result via existing `get_job_status` and `list_jobs` endpoints.
- This avoids introducing a second async subsystem.

### 6) Risk list and mitigation

- Micromamba artifact format varies by platform (compressed archive vs raw binary):
  - implement extract-or-direct handling by content type/extension and robust fallback.
- macOS Gatekeeper behavior for downloaded binaries:
  - best-effort ad-hoc sign call (`codesign --force --sign -`), non-fatal if unavailable.
- Conda package name drift:
  - verify with live conda-forge package checks and document outcomes.
- Long-running tests:
  - isolate via mocked unit tests; mark real network tests as integration and skip unless explicitly enabled.

## Implementation log

- 2026-02-22: Task 0 architecture plan completed in worklog before code edits.
- Next: verify conda-forge package availability list and begin kernel module implementation.

## Conda-forge package availability verification (network)

Checked via HTTP status of `https://anaconda.org/conda-forge/<package>`:

- qe: 200
- xtb: 200
- lammps: 200
- cp2k: 200
- abinit: 200
- siesta: 200
- qmcpack: 200
- pyscf: 200
- psi4: 200
- gpaw: 200
- wannier90: 200
- yambo: 200

Interpretation for this step:
- All candidate packages resolve on conda-forge.
- Step 3 implementation will still gate installability by `ENGINE_META` configuration (commercial engines remain manual unless explicitly enabled in metadata policy).

## Implementation progress (in-flight)

### Kernel implementation added

Created:
- `src/qmatsuite/core/engines/micromamba.py`
- `src/qmatsuite/core/engines/engine_installer.py`

`micromamba.py` details:
- Pinned release tag: `2.5.0-2`.
- Platform-aware asset mapping:
  - macOS arm64: `micromamba-osx-arm64`
  - macOS x86_64: `micromamba-osx-64`
  - Linux x86_64: `micromamba-linux-64`
  - Linux arm64: `micromamba-linux-aarch64`
  - Windows x64: `micromamba-win-64.exe`
- Implemented:
  - `ensure_micromamba()` with SHA256 verification from release `.sha256` sidecar
  - atomic placement via staged file + `replace()`
  - Unix executable permission setup
  - macOS ad-hoc signing attempt (`codesign --force --sign -`), warning-only on failure
  - `run_micromamba()`, `create_env()`, `remove_env()`, `list_envs()`

`engine_installer.py` details:
- Implemented conda install flow:
  - build env name `<engine>-<version-or-latest>`
  - create micromamba env
  - verify binary/python import
  - register in engines.json via `EngineRegistry`
  - set active installation
  - cleanup env on verification/registration failure
- Implemented GitHub asset install flow:
  - download asset
  - optional checksum verification
  - extract/copy payload
  - locate engine binary in extracted tree
  - register `github_release` installation and activate
- Implemented uninstall flow:
  - micromamba env removal for `source=micromamba`
  - guarded directory deletion for app-managed bundled/github installs
  - deregister from engines.json
- Added `list_installable_engines()` and `resolve_qe_github_release_asset()` helpers.

### API integration added

Modified:
- `src/qmatsuite/api/engines.py`

Added API methods:
- `install_engine(engine_family, version=None, source="auto")`
- `uninstall_engine(engine_family, installation_id)`
- `list_installable_engines()`

Behavior:
- `source=auto` resolves to conda when `ENGINE_META` has `conda_package`.
- `source=github_release` currently supported for QE path.
- Existing Step 2 APIs remain intact.

### Daemon integration added

Modified:
- `src/qmatsuite/daemon/server.py`

Added RPC endpoints:
- `engine.install`
- `engine.uninstall`
- `engine.list_installable`

Design choice:
- install/uninstall default to async and use existing `JobManager`.
- optional payload `async=false` executes synchronously.
- keeps progress/status polling compatible with existing `get_job_status` and `list_jobs`.

### CLI integration added

Modified:
- `src/qmatsuite/cli/main.py`

Added `qms engine` command group with subcommands:
- `qms engine list [--installed-only]`
- `qms engine install <engine> [--version X] [--source auto|conda|github_release]`
- `qms engine uninstall <engine> [--installation-id ID]`
- `qms engine verify <engine>`
- `qms engine path <engine> <path> [--source user_path|user_venv]`

### Test scaffolding added

Created:
- `tests/unit/test_micromamba.py`
- `tests/unit/test_engine_installer.py`
- `tests/unit/test_api_engine_installation.py`
- `tests/cli/test_engine_commands.py`

Updated:
- `tests/daemon/contract/test_engine_rpcs.py` with new RPC coverage tests.

Quick syntax gate:
- `python -m compileall` on all changed files passed.

### Known follow-up before full-suite run

- Contract-crawler coverage may require explicit handling for new RPC method names (`engine.*`) to avoid uncovered-method gate failures.
- Need targeted pytest runs for new/changed test groups before the mandatory full-suite run.

## Test iteration log (targeted)

### Batch 1: new Step 3 tests
Command:
- `source .venv/bin/activate && python -m pytest tests/unit/test_micromamba.py tests/unit/test_engine_installer.py tests/unit/test_api_engine_installation.py tests/cli/test_engine_commands.py tests/daemon/contract/test_engine_rpcs.py -q --tb=short`

Result:
- `30 passed`
- Warnings only (third-party deprecation warnings from spglib).

### Contract crawler gate check
Issue anticipated:
- New RPC method names (`engine.install`, `engine.uninstall`, `engine.list_installable`) are discovered by contract coverage gates.
- Without explicit handling they could appear uncovered.

Fixes applied:
- `tests/contract_crawler/payloads.py`
  - Added minimal stateless payload for `engine.list_installable`.
- `tests/contract_crawler/test_coverage.py`
  - Added explicit exemptions with reasons for:
    - `engine.install`
    - `engine.uninstall`
  - Rationale: state-mutating, potentially network/solver dependent, nondeterministic in crawler.

Verification command:
- `source .venv/bin/activate && python -m pytest tests/contract_crawler/test_coverage.py -q --tb=short`

Result:
- `4 passed`

### Step 2 regression check
Command:
- `source .venv/bin/activate && python -m pytest tests/unit/test_api_engine_registry.py tests/unit/test_engine_registry_distribution.py tests/mcp/test_list_engines_install_detection.py -q --tb=short`

Result:
- `14 passed`

Status before full suite:
- All targeted tests for new functionality and immediate regressions are green.
- Ready for mandatory full parallel pytest run.

## Mandatory full-suite run (strict command) and remediation

### Full run command executed
Command (as required by user rule):
- `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

Result:
- Exit code: `1`
- Runtime: `381.76s` (~6m21s)
- Summary: `2 failed, 6493 passed, 4 skipped`

Failures captured:
1. `tests/gates/test_schema_self_consistency.py::TestSchemaConsistency::test_no_legacy_key_assertions`
   - Violations from new tests asserting legacy key access `['id']` instead of `['ulid']`.
   - Locations:
     - `tests/unit/test_api_engine_installation.py:51`
     - `tests/unit/test_engine_installer.py:86`
2. `tests/contract_crawler/test_introspection.py::TestRPCIntrospection::test_all_methods_categorized`
   - Uncategorized RPC methods:
     - `engine.install`
     - `engine.uninstall`
     - `engine.list_installable`

### Remediation edits

1. Updated legacy assertion in API install test:
- File: `tests/unit/test_api_engine_installation.py`
- Changed mocked GitHub installation key from `id` to `ulid` and assertion accordingly:
  - `result["installation"]["ulid"] == "github-7.5-openmp"`

2. Removed legacy `['id']` assertion in installer test:
- File: `tests/unit/test_engine_installer.py`
- Replaced direct id equality assertion with semantic checks on active install attributes:
  - source equality
  - conda env equality

3. Categorized new RPC methods for introspection gate:
- File: `tests/contract_crawler/introspection.py`
- Added to `environment` category:
  - `engine.install`
  - `engine.uninstall`
  - `engine.list_installable`

### Focused verification after fixes
Command:
- `source .venv/bin/activate && python -m pytest tests/unit/test_api_engine_installation.py tests/unit/test_engine_installer.py tests/contract_crawler/test_introspection.py tests/gates/test_schema_self_consistency.py -q --tb=short`

Result:
- `19 passed`
- No failures.

### Next action
- Re-run the mandatory full suite with the strict command and wait to completion before any further step.

### Mandatory full-suite rerun after remediation
Command (strict):
- `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

Result:
- Exit code: `0`
- Runtime: `384.31s` (~6m24s)
- Summary: `6495 passed, 4 skipped, 976 warnings`

Status:
- Step 3 code and test changes are fully green on the mandatory full parallel suite.
- Prior two failures (legacy test key assertion + uncategorized new RPC methods) are resolved.

### Post-green smoke checks (after full suite)
Commands:
- `source .venv/bin/activate && qms engine list`
- `source .venv/bin/activate && qms engine list --installed-only`
- `source .venv/bin/activate && python -c "from qmatsuite.api.engines import list_installable_engines; ..."`

Observed:
- CLI list renders real per-engine detection (not all-true behavior).
- `--installed-only` filters correctly.
- `list_installable_engines()` returns 15 engines with expected manual-only set including commercial/manual paths.

Milestone commit created:
- `1381acce` — Step 3 micromamba install management + API/daemon/CLI wiring + tests.

## Incident Investigation: repo-root `CRASH` + `input_tmp.in` artifacts (2026-02-22)

### Trigger and evidence
- User reported unexpected files at repo root:
  - `<repo_root>/CRASH`
  - `<repo_root>/input_tmp.in`
- File metadata observed:
  - both created `2026-02-22 12:50:11`
- `CRASH` content:
  - QE error: `Error in routine read_namelists (2): could not find namelist &control`
- `input_tmp.in` content:
  - empty file

### Timeline correlation
- `coverage.xml` from mandatory full pytest rerun was written at `12:49:25`.
- Artifact creation occurred ~46s later at `12:50:11`.
- That interval corresponds to post-pytest manual smoke commands (`qms engine list`), not code edit operations.

### Deep root-cause analysis
1. `qms engine list` calls API `list_engines()`.
2. `list_engines()` calls `EngineRegistry().discover(persist=False)`.
3. `discover()` verifies installations and runs version probes.
4. QE metadata uses version probe command `pw.x --version`.
5. On this QE build (`q-e-qe-7.5`), `pw.x --version` does not behave as a pure version command:
   - starts runtime banner,
   - waits/reads stdin,
   - on EOF/invalid input emits `CRASH` (and often `input_tmp.in`) in process CWD.

### Reproduction performed
- Direct binary run in isolated temp dir:
  - `pw.x --version` created `CRASH` + `input_tmp.in` in that dir.
- CLI reproduction:
  - running `qms engine list` from an empty temp dir created `CRASH` + `input_tmp.in` there.
- This confirms pollution source is version probing path, not direct file writes in repo code.

### Runtime-safety design decision
Requirements from user feedback:
- Must be dev + distribution safe.
- Must not assume repo `.tmp` exists in distribution.
- Must avoid hangs when user runs commands from interactive shells.

Chosen design:
- Introduce a shared safe probe runner for version commands.
- Execute probes in a temporary subdirectory under `tmp_probe_dir()` (which already maps correctly in dev/electron/pip contexts via `get_cache_dir()` chain).
- Force `stdin=subprocess.DEVNULL` to avoid interactive hangs on binaries that block on stdin.
- Keep timeout limits and parse version from stdout/stderr even on non-zero return code.
- Use temporary directories so transient files (`CRASH`, `input_tmp.in`, etc.) are isolated and auto-cleaned.

### Code changes implemented for fix
- Added shared helper module:
  - `src/qmatsuite/core/engines/version_probe.py`
  - function: `run_version_probe(command, timeout=...)`
- Updated version-probe callsites to use safe helper:
  - `src/qmatsuite/core/engines/engine_registry.py`
  - `src/qmatsuite/core/engines/engine_installer.py`

### Regression tests added
- `tests/unit/test_engine_registry_distribution.py`
  - `test_version_probe_does_not_pollute_caller_cwd`
- `tests/unit/test_engine_installer.py`
  - `test_installer_version_probe_does_not_pollute_caller_cwd`

Both tests use a fake executable that attempts to create `input_tmp.in` and `CRASH`; assertions verify caller CWD remains clean.

### Expected behavior after fix
- `qms engine list` / engine discovery/verification no longer creates QE crash artifacts in caller CWD.
- In distribution mode, probe scratch path resolves under app cache (`get_cache_dir()`), not repo paths.
- Interactive CLI use will not hang on version probes waiting for stdin.

### Validation after probe isolation fix

Focused test command:
- `source .venv/bin/activate && python -m pytest tests/unit/test_engine_registry_distribution.py tests/unit/test_engine_installer.py tests/unit/test_api_engine_registry.py tests/cli/test_engine_commands.py -q --tb=short`

Result:
- `24 passed`

Manual runtime reproduction checks:
1. Temp-cwd CLI check:
   - command: `(cd /tmp/<tmpdir> && qms engine list)`
   - observed: output correct, and temp dir remained empty (no `CRASH`, no `input_tmp.in`).
2. Repo-root stability check:
   - ran `qms engine list` from repo root and compared mtimes for existing `CRASH`/`input_tmp.in`.
   - observed: mtimes unchanged; no new writes.

Conclusion:
- Version probing now isolates side effects to app-mapped temporary probe paths.
- Caller CWD (repo root, arbitrary user launch dir, temp dirs) is no longer polluted by QE probe artifacts.
- Stdin-hang risk for interactive invocations is mitigated by explicit `stdin=DEVNULL` in probe execution.

### Mandatory full-suite rerun (post-version-probe hardening) and gate fallout
Command (strict):
- `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

Result:
- Exit code: `1`
- Runtime: `375.46s` (~6m15s)
- Summary: `1 failed, 6496 passed, 4 skipped`
- Failure:
  - `tests/gates/test_no_sensitive_paths.py::TestNoSensitivePaths::test_no_sensitive_identifiers`
  - Cause: this worklog accidentally included two absolute user path strings.

Remediation done immediately:
- Sanitized absolute paths in this worklog to repo-relative placeholders (`<repo_root>/...`).
- Removed repo-root runtime artifacts after the final rerun per instruction:
  - deleted `CRASH`
  - deleted `input_tmp.in`

Next action:
- Re-run the mandatory strict full suite once after this redaction fix.

### Mandatory full-suite rerun after redaction fix (strict)
Command:
- `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Output captured in: `.tmp/pytest_full_latest.log`

Result:
- Exit code: `0`
- Runtime: `364.57s` (~6m04s)
- Summary: `6497 passed, 4 skipped, 979 warnings`

Post-run state checks:
- Repo-root QE crash artifacts are absent (`CRASH`, `input_tmp.in` not present).
- Sensitive-path gate is green after worklog redaction.

Continuation status:
- Resumed and completed the previously blocked Step 3 closure flow after resolving the unexpected `CRASH` artifact incident.
