## DISTRIBUTION STEP 7B — QE Download Wiring + Version Bump + Final Release Prep (Implementation Plan)

Date: 2026-02-23  
Repo: QMatSuite/QMatSuite  
Related worklog: `DISTRIBUTION_STEP7B_QE_DOWNLOAD_WIRING_2026-02-23_WORKLOG.md`

---

## 1. Current State Review (What the previous agent already did)

- **QE GitHub release resolver (`resolve_qe_github_release_asset`)**
  - Implemented in `src/qmatsuite/core/engines/engine_installer.py` as a unified resolver for all platforms, backed by a single repo:
    - `QE_RELEASE_REPO = "QMatSuite/qmatsuite-toolchain"`  
      (no more `QE_RELEASE_REPO_UNIX` / `QE_RELEASE_REPO_WINDOWS` split).
  - Behavior:
    - Normalizes requested version: strips leading `v`, defaults to `"7.5"` if unspecified.
    - Detects host platform via `platform.system().lower()` / `platform.machine().lower()`.
    - Maps `(system, machine)` → **platform variant**:
      - `windows` + `amd64|x86_64` → `"win-oneapi-msmpi"`.
      - `darwin` + `arm64|aarch64` → `"macos-arm64-openmp"` (for `variant="openmp"`).
      - `darwin` + `x86_64|amd64` → `"macos-x64-openmp"`.
      - `linux` + `x86_64|amd64` → `"linux-x64-openmp"`.
      - Anything else → `RuntimeError("No QE GitHub binary mapping for platform ...")`.
    - Builds:
      - `tag_prefix = f"qe-{qe_version}-{platform_variant}"`.
      - `asset_name = f"{tag_prefix}.zip"`.
    - Fetches `https://api.github.com/repos/QMatSuite/qmatsuite-toolchain/releases?per_page=100` using `_download_text`.
    - Scans releases (most recent first, as returned by the API) for:
      - `release_tag == tag_prefix` **or** `release_tag.startswith(f"{tag_prefix}-")` (e.g. date + shorthash suffix).
      - Finds assets with:
        - `name == asset_name` → zip.
        - `name == f"{asset_name}.sha256"` → optional checksum.
      - Returns the first matching release with:
        - `asset_url`, `asset_name`, `checksum_url`, `release_url`, `release_tag`, `variant` (platform variant), `repo`.
    - If no match is found, raises a clear `RuntimeError` that includes platform, repo, tag prefix, asset name.
  - **Windows libxc handling**:
    - Because `asset_name` is exactly `qe-<ver>-win-oneapi-msmpi.zip` and Windows releases with `-libxc` have `asset_name = qe-<ver>-win-oneapi-msmpi-libxc.zip`, libxc variants are automatically excluded.

- **QE GitHub-release installation (`install_engine_github_release`)**
  - Implemented / extended in `engine_installer.install_engine_github_release`:
    - Downloads the asset to `<app_data>/.tmp/downloads/<asset_name>`.
    - Verifies checksum via `_verify_or_download_sha256` when `checksum_url` is provided.
    - Extracts:
      - If zip: `zipfile.ZipFile(asset_path).extractall(unpack_dir)`.
      - If tar: `tarfile.open(asset_path).extractall(unpack_dir)`.
      - Else: treats payload as a single executable, drops it into `unpack_dir/bin/<binary_name>` and sets mode `0o755` on non-Windows.
    - Uses `_find_binary_in_tree(unpack_dir, family)` to find the first valid engine binary and its bin directory.
    - Derives:
      - `version_hint` from asset name via `_version_hint_from_name`.
      - `variant` from asset name via `_variant_hint_from_name` (`openmp`, `mpi` detection).
      - `install_id = f"github-{version_hint}` or `github-<version>-<variant>`.
    - Copies the unpack tree to `<app_data>/engines/<family>/<install_id>/`.
    - **New behavior**: on non-Windows platforms, after copying:
      - Re-resolves the final `bin` directory via `_find_binary_in_tree(target_root, family)`.
      - Iterates over files in that directory and sets executable bits (`st_mode | 0o111`) so QE binaries are runnable (fixes the "non-executable pw.x" issue).
    - Registers installation into `engines.json` via `EngineRegistry` and sets it active.

- **Engine verification hardening (`EngineRegistry`)**
  - In `src/qmatsuite/core/engines/engine_registry.py`:
    - `_verify_installation` for binary engines:
      - Resolves `base_path = Path(installation["path"])`.
      - Looks for required binaries:
        - Primary: `installation["required_binaries"]` or meta `required_binaries`.
        - Fallback: `get_platform_primary_binary` → fallback detection via `get_detection_binaries`.
      - If no binary is found, returns `(False, "required binaries not found ...")`.
      - Then calls `_detect_binary_version`:
        - If a `version_command` exists and version probe returns `None`, verification returns:
          - `ok = False`, `reason = f"version probe failed for {resolved_binary}"`.
        - Otherwise, if a version string is found, writes it back into `installation["version"]`.
    - `verify_engine(engine_family)`:
      - Calls `_verify_installation`.
      - Returns `(False, reason or "Engine '<family>' verification failed.")` on error, `(True, "OK")` on success.
  - This means that **if QE binaries cannot launch** (e.g. `dyld` missing `libgcc_s.1`), verification will now correctly fail instead of reporting a false-positive "OK".

- **New unit tests in `tests/unit/test_engine_installer.py`**
  - `test_verify_binary_engine_rejects_non_runnable_binary`:
    - Creates a fake `xtb` binary that exits non-zero and prints a `dyld: Library not loaded`-style message.
    - Asserts that `_verify_binary_engine("xtb", bin_dir)` raises `RuntimeError("Version probe failed ...")`.
  - `test_resolve_qe_github_release_asset_macos_arm64`:
    - Mocks:
      - `platform.system` → `"Darwin"`.
      - `platform.machine` → `"arm64"`.
      - `_download_text` → JSON payload with a single macOS QE release.
    - Asserts:
      - `repo == "QMatSuite/qmatsuite-toolchain"`.
      - Correct `release_tag`, `asset_name`, `variant == "macos-arm64-openmp"`.
  - `test_resolve_qe_github_release_asset_windows_skips_libxc_release`:
    - Mocks two Windows releases:
      - One `...-win-oneapi-msmpi-libxc-...` with `qe-7.5-win-oneapi-msmpi-libxc.zip`.
      - One `...-win-oneapi-msmpi-...` with `qe-7.5-win-oneapi-msmpi.zip`.
    - Asserts that:
      - Resolver picks the non-libxc asset.
      - `variant == "win-oneapi-msmpi"`.
  - `test_resolve_qe_github_release_asset_unsupported_platform`:
    - Mocks `platform.system = "Linux"` and `platform.machine = "riscv64"`.
    - Asserts a `RuntimeError("No QE GitHub binary mapping ...")`.
  - `test_install_engine_github_release_sets_executable_bits_on_unix`:
    - Creates a minimal zip with `qe-7.5/bin/pw.x`.
    - Mocks:
      - `platform.system = "Darwin"`.
      - `_download_binary` to copy the local zip into place.
      - `_verify_or_download_sha256` to no-op.
    - Calls `install_engine_github_release("qe", ...)` with a temporary `app_data_dir`.
    - Asserts that `<install_path>/pw.x` exists and is executable (`os.access(..., os.X_OK)`).

- **Targeted test runs and CLI checks**
  - Targeted pytest run:
    - `python -m pytest tests/unit/test_engine_installer.py tests/unit/test_api_engine_installation.py -v --tb=short` → reported as **15 passed** in the worklog.
  - Manual resolution tests (from the previous agent, per your trace):
    - Called `resolve_qe_github_release_asset()` on the host (macOS arm64) to confirm live mapping.
    - Used `unittest.mock.patch` to simulate Windows (`system="Windows"`, `machine="AMD64"`) and confirmed mapping & returned asset metadata.
  - CLI wiring sanity checks:
    - `python -m qmatsuite.cli --help`.
    - `python -m qmatsuite.cli engine --help`.
  - Real QE install chain (macOS arm64):
    - In a fresh `QMATSUITE_HOME` under `/tmp`:
      - `qms engine install qe --source github_release`.
      - `qms engine verify qe`.
      - `qms engine list --installed-only`.
    - A minimal QE `pw.x` smoke run was attempted, which surfaced a **runtime dependency issue**:
      - `pw.x` failed with a `dyld` error (`libgcc_s.1` / Fortran runtime not found) when launched directly.
      - This is a toolchain packaging/runtime problem (missing or mismatched runtime libs), not a QMatSuite resolver bug.
    - As a mitigation, `EngineRegistry` verification logic was hardened so that such failures now cause `verify qe` to fail instead of silently passing.

- **Worklog coverage**
  - `docs/history/worklogs/DISTRIBUTION_STEP7B_QE_DOWNLOAD_WIRING_2026-02-23_WORKLOG.md` documents:
    - Live GitHub release inspection for `QMatSuite/qmatsuite-toolchain` (macOS + Windows + Windows libxc assets).
    - Resolver design decisions and implementation.
    - Unit tests additions.
    - Targeted test run results.
  - Later edits (engine verification tightening, QE install/verify chain, and pw.x smoke run) are referenced in your trace and visible in code, even if not fully written into the worklog yet.

- **Not yet done (from code + config inspection)**
  - **Version bump**:
    - `pyproject.toml` still shows `version = "1.0.1"`.
    - `gui/package.json` still shows `"version": "0.0.0"`.
  - **Release workflows**:
    - `.github/workflows/release-macos.yml`, `release-windows.yml`, `release-pip.yml` exist and are parameterized by `workflow_dispatch` inputs (version, sign, target), but **no 1.1.0-specific changes** have been wired yet.
  - **Global test + packaging passes for Step 7B**:
    - No evidence yet in the repo of:
      - Full pytest run for this step.
      - Playwright GUI E2E run for this step.
      - Local wheel build + clean install verification for this step.
      - Local DMG build & smoke test for this step.
  - **Release notes**:
    - No `v1.1.0` release-notes markdown exists yet.
  - **Commit/tag/push**:
    - No `v1.1.0` tag present in this repo snapshot (per workflows and pyproject).

---

## 2. Gap Analysis vs. Original Step 7B Tasks

The original Step 7B prompt defined Tasks 0–5. Below is a point-by-point mapping from the spec to current state and remaining work.

- **Task 0: Fix `resolve_qe_github_release_asset()`**
  - **Spec highlights**:
    - Single repo: `QMatSuite/qmatsuite-toolchain` for all platforms.
    - Platform asset map with tags:
      - macOS arm64: `qe-7.5-macos-arm64-openmp-*` → `qe-7.5-macos-arm64-openmp.zip`.
      - Windows: `qe-7.5-win-oneapi-msmpi-*` → `qe-7.5-win-oneapi-msmpi.zip`.
      - Future: macOS x64, Linux x64.
    - Must avoid accidentally picking Windows `-libxc` variants.
    - Clear error message when no release is found for the given platform.
  - **Current status**:
    - ✅ Single repo (`QE_RELEASE_REPO`) and platform-to-variant mapping implemented.
    - ✅ Correct tag-prefix logic and asset-name matching implemented.
    - ✅ Windows `libxc` variant is effectively ignored via exact asset-name constraint.
    - ✅ Clear and platform-specific `RuntimeError` when:
      - No mapping exists for `(system, machine)`; or
      - No matching release/asset can be found in the toolchain repo.
    - ✅ Unit tests cover:
      - macOS arm64 happy path.
      - Windows with libxc vs non-libxc coexistence.
      - Unsupported platform error path.
  - **Gaps**:
    - No explicit unit tests yet for:
      - macOS x64 mapping (`macos-x64-openmp`).
      - Linux x64 mapping (`linux-x64-openmp`).
      - Behavior when the GitHub API returns an empty list or only non-QE releases.
    - Worklog does not yet record the **post-hardening verification behavior** (e.g. how failures propagate into CLI / daemon RPC).

- **Task 1: Test QE Download → Install → Run Chain**
  - **Spec highlights**:
    - 1a: Windows path (mock platform or on real Windows).
    - 1b: macOS arm64 real install + verify + run.
    - 1c: GUI Engine Manager path (daemon RPC, GUI).
  - **Current status**:
    - ✅ Resolver verified against live toolchain releases for host macOS and mocked Windows.
    - ✅ Real QE install chain (macOS arm64) executed:
      - `install` + `verify` + `list` from CLI under isolated `QMATSUITE_HOME`.
    - ✅ `install_engine_github_release` ensures QE binaries are executable on unix after extraction.
    - ✅ EngineRegistry verification now fails if binaries cannot run a version probe.
    - ⚠️ QE `pw.x` still fails at runtime on this specific macOS environment due to missing or mismatched runtime libraries (toolchain/runtime issue).
  - **Gaps**:
    - Need a **clean, documented picture** of:
      - What `qms engine verify qe` now returns on a fresh machine with the current toolchain asset.
      - How CLI/daemon/GUI error messages surface the underlying `dyld` failure, so users are not misled.
    - No explicit documentation yet of:
      - Windows path exercised via CLI (only resolver-level test, not full install/verify).
      - GUI Engine Manager path (daemon RPC + TS/React flow) tested against the new resolver and verification semantics.

- **Task 2: Version Bump to 1.1.0**
  - **Spec highlights**:
    - `pyproject.toml` → `version = "1.1.0"`.
    - `gui/package.json` → `"version": "1.1.0"`.
    - Script to assert version consistency between these two.
  - **Current status**:
    - `pyproject.toml` shows `version = "1.0.1"`.
    - `gui/package.json` shows `"version": "0.0.0"`.
    - No cross-check script committed yet for verifying equality.
  - **Gaps**:
    - Version bump and sync are **not implemented**.
    - Workflows (`release-macos`, `release-windows`, `release-pip`) still rely on runtime `workflow_dispatch` inputs; they are logically compatible but not yet validated with `1.1.0`.

- **Task 3: Final Pre-Release Validation**
  - **Spec highlights**:
    - 3a: Full pytest, record count.
    - 3b: Playwright E2E, all tests passing.
    - 3c: Local wheel build + clean venv verification.
    - 3d: Local DMG build (arm64).
    - 3e: Electron unpacked build + quick smoke test of the GUI.
  - **Current status**:
    - Only targeted pytest runs were executed (unit-level).
    - No evidence yet of:
      - Full pytest over `tests/`.
      - Playwright runs from `gui/`.
      - Local wheel build + clean env tests.
      - DMG build + smoke test.
  - **Gaps**:
    - All of Task 3 remains to be executed and recorded in the worklog for this step.

- **Task 4: Prepare Release Notes**
  - **Spec highlights**:
    - Draft `QMatSuite v1.1.0` release notes, covering:
      - Features, installation methods, first steps, etc.
  - **Current status**:
    - No dedicated `v1.1.0` release notes file found in `docs/history/` or `docs/`.
  - **Gaps**:
    - Need to decide canonical location and filename for release notes and then draft content accordingly.

- **Task 5: Commit and Prepare for CI Release**
  - **Spec highlights**:
    - `git add -A`, `git commit -m "release: v1.1.0 — QE download wiring + version bump"`, `git tag v1.1.0`.
    - Push changes but **do not** trigger release workflows directly.
  - **Current status**:
    - Not performed yet (per pyproject version and absence of `v1.1.0` tag).
  - **Gaps**:
    - Need to define the exact final commit contents and ensure they come **after** all validations are green.

---

## 3. Detailed Step-by-Step Implementation Plan (No-Code Phase vs. Code Phase)

This section describes, in detail, what I will do **after you approve this plan**. I will respect your constraint: for now this is purely a plan; no code changes will be made until you explicitly request implementation.

### 3.1. Phase 0 — Safety & Baseline Snapshot

1. **Confirm clean working tree or enumerate deltas**
   - Run:
     - `git status --short`.
   - Capture:
     - Which files are modified in this Step 7B session (likely `engine_installer.py`, `engine_registry.py`, unit tests, worklog).
   - Purpose:
     - Ensure future commits for `v1.1.0` are clearly scoped to Step 7B.

2. **Re-read Step 7B worklog**
   - Re-open `docs/history/worklogs/DISTRIBUTION_STEP7B_QE_DOWNLOAD_WIRING_2026-02-23_WORKLOG.md`.
   - Append or reconcile notes from this plan (especially around runtime QE behavior and verification semantics) once implementation is complete.

3. **Baseline `qms` CLI behavior snapshot**
   - With current `main` code (prior to new Step 7B changes, if any remain to be merged), record:
     - `qms engine list`.
     - `qms engine list --installed-only`.
   - Purpose:
     - Provide a concrete “before” snapshot if we need to compare engine registry behavior later.

### 3.2. Phase 1 — QE Resolver & Installation Behavior Finalization

**Goal**: Ensure `resolve_qe_github_release_asset` + `install_engine_github_release` semantics are correct, stable, and fully covered for all target platforms.

1. **Extend resolver unit tests to cover Linux and macOS x64**
   - Add tests in `tests/unit/test_engine_installer.py`:
     - `test_resolve_qe_github_release_asset_linux_x64`:
       - `platform.system` → `"Linux"`, `platform.machine` → `"x86_64"`.
       - Mock `_download_text` with a Linux release carrying `tag_name = "qe-7.5-linux-x64-openmp-..."` and `qe-7.5-linux-x64-openmp.zip`.
       - Assert `variant == "linux-x64-openmp"`, correct `asset_name` and `asset_url`.
     - `test_resolve_qe_github_release_asset_macos_x64`:
       - `platform.system` → `"Darwin"`, `platform.machine` → `"x86_64"`.
       - Mock `_download_text` with `qe-7.5-macos-x64-openmp-...`.
       - Assert `variant == "macos-x64-openmp"` and correct asset metadata.
   - Keep these tests **fully mocked** (no live network).

2. **Add explicit “no releases found” unit test**
   - New test case:
     - Mocks `_download_text` to return an empty list (`[]`) or a list with non-QE tags only.
     - Confirms that `resolve_qe_github_release_asset` raises `RuntimeError` whose message:
       - Includes the platform.
       - Includes `tag prefix` and `asset` names.
       - Clearly states that no QE asset was found.

3. **Add a “checksum present” unit test path**
   - New test:
     - Mocks a release where assets include both:
       - `qe-7.5-macos-arm64-openmp.zip`.
       - `qe-7.5-macos-arm64-openmp.zip.sha256`.
     - Asserts:
       - `resolved["checksum_url"]` is non-empty.
       - `resolved["release_url"]` is populated as expected.
   - This keeps `resolve_qe_github_release_asset` semantics well-defined for when the toolchain repo starts publishing checksums.

4. **Tighten worklog entries for Task 0**
   - After tests are green, update the Step 7B worklog with:
     - A short bullet list summarizing:
       - Linux/macOS x64 mapping behavior.
       - Empty-release-list behavior.
       - Checksum asset handling.
     - A brief mention that all new tests are pure-unit and network-free.

### 3.3. Phase 2 — QE Install / Verify / Run Chain Across CLI & Daemon

**Goal**: Validate (and, where necessary, tighten) the end-to-end QE engine lifecycle: resolve → download → install → verify → run, and ensure errors are surfaced clearly to users.

#### 3.3.1. Backend CLI flows (no GUI yet)

1. **Fresh macOS arm64 install chain in an isolated home**
   - Commands (from repo root with `.venv` activated):
     - `export QMATSUITE_HOME=/tmp/qms-step7b-home3`.
     - `rm -rf "$QMATSUITE_HOME" && mkdir -p "$QMATSUITE_HOME"`.
     - `python -m qmatsuite.cli engine install qe --source github_release`.
     - `python -m qmatsuite.cli engine verify qe`.
     - `python -m qmatsuite.cli engine list --installed-only`.
   - Artifacts to capture:
     - Tail of install/verify/list logs.
     - The resulting `engines.json` snippet for `qe`:
       - Ensure `source == "github_release"`, `id == "github-7.5-openmp"` (or similar), `path` points to `.../bin`, and `required_binaries` includes `pw.x` or equivalent.
   - Expected behavior:
     - If the current toolchain asset is still missing runtime libs, `verify qe` should **fail with a clear reason**, not "OK".
   - Worklog entry:
     - Record exact commands, exit codes, and error messages, especially error text from `EngineRegistry.verify_engine`.

2. **Minimal QE `pw.x` smoke run (documented, but allowed to fail)**
   - Under the same `QMATSUITE_HOME`, run:
     - A trivial SCF input using the installed `pw.x`, ensuring pseudo/TMP paths are harmless and local.
   - Objective:
     - Confirm whether, on this specific machine:
       - `pw.x` launches successfully, or
       - still fails with `dyld` / missing library.
   - Worklog:
     - If it fails, **explicitly attribute the failure** to toolchain runtime packaging, not QMatSuite, and link to the observed `dyld` message.

3. **Simulated Windows chain (resolver + registry semantics)**
   - Using `unittest.mock.patch` to simulate Windows:
     - `platform.system` → `"Windows"`.
     - `platform.machine` → `"AMD64"`.
   - In a unit/integration test:
     - Use `resolve_qe_github_release_asset(...)` with a mocked `_download_text` returning both `-libxc` and non-libxc Windows releases.
     - Use `install_engine_github_release("qe", ...)` with:
       - `_download_binary` mocked to emit a synthetic QE zip with `bin/pw.x.exe`.
       - `_verify_or_download_sha256` mocked to no-op.
     - Validate:
       - `engines.json` entry for `qe`:
         - `source == "github_release"`.
         - `required_binaries` contains `pw.x.exe` variant or equivalent.
       - `EngineRegistry.verify_engine("qe")` returns `(True, "OK")` in this artificial Windows-like environment.
   - Purpose:
     - Ensure Windows path is logically wired end-to-end without needing a real Windows runner during this step.

4. **Error-message quality audit for `verify_engine`**
   - For QE on macOS (real environment):
     - Run `qms engine verify qe` and inspect stderr/stdout.
     - If the error is too opaque (e.g. just “version probe failed”), consider in a **future code patch**:
       - Decorating error messages with a short hint:
         - E.g. `"version probe failed for pw.x (likely missing QE runtime libraries; see Step 7B worklog)"`.
   - For the purposes of this plan:
     - We will not change code yet.
     - We will document in the worklog what the current error message looks like, so we can decide if a UX tweak is warranted later.

#### 3.3.2. Daemon RPC & GUI Engine Manager flow

1. **Backend API / RPC inspection**
   - Locate TS/React and backend glue:
     - `grep -n "engine.install\\|github_release" gui/src/ -r --include="*.ts" --include="*.tsx"`.
   - Identify:
     - Which RPC method is used (likely `engine.install` / `engine.verify`).
     - Which payload fields specify `source: "github_release"` and `engine_family: "qe"`.
   - Confirm:
     - The GUI path for QE install uses the same backend code path as CLI (`install_engine_github_release` + `EngineRegistry`).

2. **Daemon RPC smoke tests (without GUI)**
   - Start the daemon:
     - `qms daemon start` (or `python -m qmatsuite.daemon.server ...`, depending on standard practice).
   - From a separate terminal:
     - Send a JSON-RPC request via `curl` or `python`:
       - `engine.install` with `{"engine_family": "qe", "source": "github_release"}`.
     - Then call `engine.verify` and `engine.list`.
   - Validate:
     - Success path (if QE verifies) and failure path (if version probe fails) map to:
       - Clear `result` / `error` payloads.
       - Structured error codes if defined for “ENGINE_NOT_INSTALLED” or “ENGINE_VERIFICATION_FAILED”.
   - Worklog:
     - Record one successful and one failing RPC transcript (redacted for tokens/paths).

3. **GUI-level smoke (post-backend validation)**
   - After backend and RPC are confirmed:
     - Launch the Electron app from a local dev build (`npx electron-builder --dir` + `open .../QMatSuite.app`).
     - Navigate to:
       - Settings → Engine Manager.
       - QE Install flow via Engine Manager.
   - Confirm:
     - QE shows as “Not Installed” initially.
     - After triggering install from GUI:
       - Progress/feedback appears.
       - Final status reflects the backend’s verification result:
         - If `verify qe` fails due to runtime libs: GUI should show a “verification failed” state, not a false “installed” checkmark.
   - For this plan:
     - We only describe the procedure; actual GUI tweaks (e.g. better copy for verification failures) can be addressed in a later pass if needed.

### 3.4. Phase 3 — Version Bump to 1.1.0 (Backend + GUI)

**Goal**: Align backend and GUI versions to `1.1.0` and ensure all release workflows are consistent with this single version number.

1. **Update `pyproject.toml` project version**
   - Edit `[project]` section:
     - Change:
       - `version = "1.0.1"` → `version = "1.1.0"`.

2. **Update `gui/package.json` version**
   - Change:
     - `"version": "0.0.0"` → `"version": "1.1.0"`.
   - Rationale:
     - Align Electron app version with backend package version; `electron-builder` typically picks version from `package.json`.

3. **Add a small version-consistency check script (optional but recommended)**
   - A short Python snippet, e.g. in a `scripts/check_versions.py` or as a one-off command in the worklog:
     - Reads `pyproject.toml` with `tomllib`.
     - Reads `gui/package.json` with `json`.
     - Asserts both versions match and print a confirmation line.
   - This step should be documented in the Step 7B worklog even if not committed as a script.

4. **Re-scan CI workflows and config**
   - Inspect:
     - `.github/workflows/release-macos.yml`.
     - `.github/workflows/release-windows.yml`.
     - `.github/workflows/release-pip.yml`.
     - `gui/electron-builder.json5`.
   - Validate:
     - No hard-coded references to `1.0.1` or earlier version numbers.
     - Workflows rely on:
       - `workflow_dispatch` input `version` and/or `pyproject.toml` version.
       - For `release-pip`, the “Verify workflow version matches pyproject.toml” step already guards against mismatch.
   - Worklog:
     - Record that workflows are already version-agnostic and only require the `version` input to be set to `1.1.0` when manually dispatched.

5. **Manual version sanity check after edits**
   - From repo root:
     - Run a quick Python snippet (similar to what the original prompt suggested) to verify:
       - `pyproject.toml` vs `gui/package.json` equality.
   - Record the output in the worklog.

### 3.5. Phase 4 — Final Validation Matrix for v1.1.0

**Goal**: Execute all validation tasks specified in the Step 7B prompt and record them in the worklog.

1. **Full Python test suite**
   - Command:
     - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`.
   - Record in worklog:
     - Start/end timestamps.
     - Test count (e.g. “X passed in Y seconds”).
     - Any flaky tests observed (if any), and whether they were re-run.

2. **Playwright E2E (GUI)**
   - From `gui/`:
     - `npm ci` (or reuse node_modules if policy allows).
     - `npx playwright test`.
   - Record:
     - Total number of tests.
     - All passing / any failures and fixes.

3. **Local wheel build + clean install**
   - From repo root:
     - `rm -rf dist build`.
     - `python -m build`.
     - `python -m venv /tmp/qms-final-test`.
     - `/tmp/qms-final-test/bin/python -m pip install --upgrade pip`.
     - `/tmp/qms-final-test/bin/pip install dist/*.whl`.
   - Verification commands:
     - `/tmp/qms-final-test/bin/python -c "import qmatsuite; print(qmatsuite.__version__)"`.
     - `/tmp/qms-final-test/bin/python -c "from qmatsuite.daemon.server import main; print('daemon OK')"` .
     - `/tmp/qms-final-test/bin/python -c "from qmatsuite.mcp.server import create_server; print('MCP OK')"` .
     - `/tmp/qms-final-test/bin/python -c "import mp_api; print('mp-api OK')"` .
     - `/tmp/qms-final-test/bin/qms --help`.
     - `/tmp/qms-final-test/bin/qms engine list`.
   - Record:
     - Whether the installed wheel reports version `1.1.0`.
     - Any integration issues.

4. **Local DMG build (macOS arm64)**
   - From `gui/`:
     - Ensure `runtime.tar.zst` exists or is built via the runtime tarball script (`scripts/build_runtime_archive.py` + copy).
     - Run:
       - `CSC_IDENTITY_AUTO_DISCOVERY=false npx electron-builder --mac dmg --arm64 --config electron-builder.json5`.
   - After build:
     - Check `gui/release/` for DMG file:
       - Confirm its filename includes `1.1.0` (or check version metadata via `mdls` or `plist`).
   - Worklog:
     - Record DMG path, size, and any manual smoke tests performed.

5. **Electron dir build + GUI smoke**
   - From `gui/`:
     - `npx electron-builder --dir --mac --arm64 --config electron-builder.json5`.
     - Launch the app:
       - `open release/mac-arm64/QMatSuite.app`.
   - Smoke test checklist:
     - App launches without immediate error dialogs.
     - Daemon starts and connects.
     - Demo gallery loads and demos are viewable.
     - Settings → Engine Manager opens and renders engine list.
     - QE appears as:
       - “Not Installed” on a fresh `QMATSUITE_HOME`.
       - After CLI install: status reflects the backend verification result.
   - Worklog:
     - Document any UX issues or inconsistencies; these can inform post-1.1.0 polish.

### 3.6. Phase 5 — Release Notes for v1.1.0

**Goal**: Create a clear, user-facing release notes document for QMatSuite v1.1.0.

1. **Decide canonical location and filename**
   - Proposal:
     - `docs/history/release-notes/QMatSuite_v1.1.0.md` **or**
     - `docs/history/release_notes_v1.1.0.md` (depending on existing conventions).
   - I will:
     - Inspect existing release-notes-like files to match project style.
     - Use the path you prefer if you give guidance before implementation.

2. **Draft release notes structure**
   - Sections:
     - `# QMatSuite v1.1.0`.
     - `## What's New`.
     - `## Features` (list of supported engines, GUI Engine Manager, MCP server, CLI, cross-platform status).
     - `## Installation` (macOS DMG, Windows NSIS, pip).
     - `## First Steps` (demo gallery, QE install via Engine Manager, initial calculation).
   - Ensure:
     - QE GitHub-release install path is clearly documented as the **recommended** path for first-time quantum-ESPRESSO users.
     - Limit scope to features and guarantees that are actually validated in Phase 4.

3. **Link release notes into the worklog**
   - Add a reference to the release-notes file in the Step 7B worklog.
   - Optionally, link from `README.md` or a higher-level `docs/` index if the project has a standard “Release Notes” section.

### 3.7. Phase 6 — Commit, Tag, and CI Preparation (No Release Trigger)

**Goal**: Prepare the repository for the maintainer to trigger release workflows, without actually kicking off those workflows.

1. **Final `git status` and diff review**
   - Inspect:
     - Modified files (expected: `engine_installer.py`, `engine_registry.py`, tests, pyproject, GUI config, worklog, release notes).
   - Manually scan diffs for:
     - Accidental debug prints or logging changes.
     - Any modifications to CI workflow triggers (there should be none).

2. **Stage and commit**
   - Commands:
     - `git add -A`.
     - `git commit -m "release: v1.1.0 — QE download wiring + version bump"`.
   - Ensure commit message explicitly references:
     - QE download wiring.
     - Version bump.
     - Final validation.

3. **Tag the release**
   - Command:
     - `git tag v1.1.0`.
   - Ensure:
     - Tag points to the commit that has all Step 7B changes + green validations.

4. **Push, but do not manually trigger release workflows**
   - Commands:
     - `git push`.
     - `git push --tags`.
   - Per your original constraints:
     - Do **not** call workflow-dispatch endpoints or `gh workflow run` for:
       - `release-macos.yml`.
       - `release-windows.yml`.
       - `release-pip.yml`.
   - Instead:
     - Leave a short note in the worklog summarizing:
       - That `v1.1.0` is ready from the code/test perspective.
       - That actual signing/publishing workflows are to be triggered by the maintainer.

---

## 4. Summary of Next Steps (Pending Your Approval)

- **No code changes will be made until you explicitly approve this plan.**
- Once approved, I will:
  - Extend resolver and install tests to fully cover Linux/macOS x64 + edge cases.
  - Re-run and document real QE install/verify/run behavior on macOS and simulated Windows, ensuring errors are surfaced correctly.
  - Bump versions to `1.1.0` across backend and GUI, verify consistency, and run the full validation matrix (pytest, Playwright, wheel, DMG, GUI smoke).
  - Draft `v1.1.0` release notes and wire up final git commit + tag without triggering release workflows.
- Any open runtime issues attributable to the toolchain (e.g., missing QE runtime libs) will be clearly documented in the worklog and **not** worked around by fragile hacks in this repo; instead, verification semantics will stay honest and fail clearly when binaries cannot run.


