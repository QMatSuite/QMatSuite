# DISTRIBUTION STEP 6 WORKLOG — Release CI + Lite Installers + Cleanup + Final Validation

Date: 2026-02-23
Repo: <repo>

## Operating rules for this step
- Worklog path rule: keep all notes under `docs/history/worklogs/`.
- Milestone full pytest command (strict):
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Full-suite runs are single-flight: do not start concurrent pytest runs.
- For this step, prioritize milestone-level full pytest (avoid unnecessary repeats).

## Context snapshot
- Branch: `v2-python` (ahead by 1 commit)
- Starting working tree: clean
- Existing workflows: `tests.yml`, `release-pip.yml`, `build-runtime-tarball.yml`
- Existing builder config: `gui/electron-builder.json5` has base mac/win config but no runtime staging or signing CI workflows.

## Initial architecture plan (before edits)

### Task 0 (known issues first)
1. Regenerate `gui/package-lock.json` from clean install and verify `npm ci` + `npm run build:e2e`.
2. Simplify `pyproject.toml` extras:
   - move `mp-api` into core dependencies
   - remove extras: `mcp`, `mp-api`, `all`
   - retain only `dev`
3. Add `[project.urls]` (Homepage/Repository/Issues).
4. Run rebrand residue audit and resolve remaining old-name tokens outside approved README history mention.
5. Clean-venv PyPI install validation against published `qmatsuite` package.
6. Milestone verification:
   - Full pytest (strict command)
   - Playwright (`cd gui && npm ci && npx playwright test`)
7. Commit Task 0 fixes as one milestone.

### Installer/CI work
8. Update `gui/electron-builder.json5` for lite installer runtime embedding (mac + windows targets).
9. Build local macOS DMG (lite path) and run practical validation checks.
10. Add release workflows:
    - `.github/workflows/release-macos.yml`
    - `.github/workflows/release-windows.yml`
11. Add runtime archive helper script (`scripts/build_runtime_archive.py`) for CI reuse.
12. Verify QE GitHub release install pathway state and record platform behavior.

### Final validation and handoff
13. Milestone full pytest + full Playwright + local electron builder command.
14. Document secrets checklist and release runbook in this worklog.
15. Record unresolved limitations explicitly.

## Risks tracked upfront
- `gui/package-lock.json` integrity corruption may require full regenerate, not manual patching.
- Updating extras can break existing workflow commands using `.[mcp]`; all references must be migrated.
- Runtime tarball staging paths must align between electron-builder config and release workflows.
- Windows Trusted Signing details depend on available pattern reference in repo/toolchain.

## Implementation log

### 2026-02-23 — Task 0a lockfile repair
- Confirmed Step 6 work had started from a partially edited state:
  - `gui/package-lock.json` modified
  - new worklog file present
- First validation attempt (`npm ci && npm run build:e2e`) failed with `EINTEGRITY`.
  - Failure signature matched prior rebrand corruption: many lockfile integrity hashes had one-character mutation (`...v...` changed to `...ms...`).
  - Example: `truncate-utf8-bytes` expected `sha512-...QXQvru...`, lockfile had `sha512-...QXQmsru...`.
- Regeneration approach used:
  1. moved corrupted lockfile aside to `/tmp/qms_pkglock_corrupt_<ts>.json`
  2. regenerated lockfile from scratch via `npm install --package-lock-only --ignore-scripts`
  3. verified hash correction (`QXQvru` restored)
  4. re-ran `npm ci && npm run build:e2e` successfully
- Result: lockfile integrity issue resolved locally; deterministic install path confirmed.

### 2026-02-23 — Task 0b/0c pyproject + references
- Updated `<repo>/pyproject.toml`:
  - moved `mp-api>=0.30.0` into core `[project].dependencies`
  - removed optional groups `mp-api`, `mcp`, `all`
  - retained only `[project.optional-dependencies].dev`
  - added `[project.urls]` with Homepage/Repository/Issues
- Updated workflow references in `<repo>/.github/workflows/build-runtime-tarball.yml`:
  - local runtime install: `pip install '.'` (was `'.[mcp]'`)
  - PyPI runtime install: `pip install qmatsuite==...` (was `qmatsuite[mcp]==...`)
- Updated docs references:
  - `<repo>/docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md`
  - `<repo>/docs/history/plans/DISTRIBUTION_IMPLEMENTATION_PLAN.md`
  - `<repo>/docs/history/worklogs/STRUCTURE_FETCH_V2_PLAN.md`

### 2026-02-23 — Task 0d rebrand residue audit (in-progress)
- Verified module/runtime checks:
  - `python -c "from qmatsuite.daemon.server import main; print('OK')"` -> OK
  - `python -m qmatsuite.mcp.server --help` starts FastMCP server successfully (no import/module error)
- Grep audit (current scope):
  - no `quantumvitas` hits in `src/*.py`, `tests/*.py`, `gui/src`, `gui/electron`, `.github/*.yml`, or `pyproject.toml`
  - README still contains legacy historical links and `project.qv.yml` filename references (expected; README exception retained)

### 2026-02-23 — Task 0e clean-venv PyPI validation (in-progress)
- Fresh venv created at `/tmp/qms-pypi-test` and installed published package from PyPI.
- Success checks:
  - `import qmatsuite` -> version `1.0.1`
  - daemon import -> OK
  - MCP import -> OK
  - `qms --help` -> OK
  - `qms engine list` -> OK
- Failure found:
  - `import mp_api` failed (`ModuleNotFoundError`) in published `qmatsuite==1.0.1`
  - Root cause: package currently on PyPI predates this Step 6 dependency move; local fix is in repo but not yet published.
- Consequence:
  - PyPI validation currently fails the `mp_api` expectation until next release publish from updated `pyproject.toml`.

### 2026-02-23 — Local release-candidate validation after dependency fix
- Fresh local venv `/tmp/qms-local-test` with `pip install <repo>`:
  - `import qmatsuite` -> version `1.0.1`
  - daemon import -> OK
  - MCP import -> OK
  - `import mp_api` -> OK (confirms Step 6 dependency migration is correct in repo)
  - `qms --help` -> OK
  - `qms engine list` -> OK
- `python -m qmatsuite.mcp.server --help` behavior note:
  - module starts the FastMCP server directly and prints banner (no argparse help output path), but entrypoint is runnable and imports are healthy.

### 2026-02-23 — Playwright artifact timestamp decision
- `docs/demo_store/GUI_E2E_INTEGRITY_REPORT.md` timestamp changed during E2E run.
- User decision: keep this timestamp update.

### 2026-02-23 — Task 0f milestone verification
- Full pytest executed with required command:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - Result: `6509 passed, 4 skipped, 975 warnings in 357.81s (0:05:57)`
  - Log: `/tmp/step6_task0_full_pytest.log`
- GUI E2E verification:
  - Command: `cd gui && npm ci && npx playwright test`
  - Result: `20 passed (6.9m)`
  - Log: `/tmp/step6_task0_playwright.log`
- Task 0 status at milestone boundary:
  - lockfile integrity issue resolved
  - pyproject extras simplified and URLs added
  - rebrand residue (`quantumvitas`) audit clean in active source/test/gui/ci scope
  - clean-venv PyPI check exposed published-version gap (`mp_api` absent in 1.0.1), while local package build validates fix

### 2026-02-23 — Installer/release implementation (in progress)
- Updated `<repo>/gui/electron-builder.json5` for lite distribution packaging:
  - output directory now `release`
  - `extraResources` now bundles `runtime.tar.zst` when staged in `gui/`
  - mac target constrained to `dmg` + `arm64`
  - mac category + DMG title set for production branding
  - NSIS options expanded (desktop/start menu shortcuts)
  - removed Linux AppImage target from this distribution config (Step 6 scope is macOS + Windows)

- Added reusable runtime archive helper:
  - new file: `<repo>/scripts/build_runtime_archive.py`
  - behavior: archives an existing runtime env prefix (`RUNTIME_ENV_PREFIX`) into `runtime-<platform>.tar.zst` (or `RUNTIME_ARCHIVE` override), prints compressed/uncompressed size metrics

- Added release workflows:
  - `<repo>/.github/workflows/release-macos.yml`
    - builds runtime env with micromamba
    - installs `qmatsuite` (local checkout or pinned PyPI version)
    - creates runtime archive via helper script
    - stages `gui/runtime.tar.zst`
    - builds DMG
    - optional Apple cert import + notarize/staple
    - uploads artifacts and drafts GitHub release assets
  - `<repo>/.github/workflows/release-windows.yml`
    - equivalent runtime build/stage flow for Windows x64
    - builds NSIS installer
    - optional Trusted Signing via `azure/trusted-signing-action@v0.5.9`
    - uploads artifacts and drafts GitHub release assets

- Trusted Signing reference status:
  - checked local `qmatsuite-toolchain` workflows for a pre-existing Trusted Signing template
  - no Trusted Signing step found there; implemented the workflow using the official Azure Trusted Signing action pattern

### 2026-02-23 — Local macOS DMG build validation
- Created local runtime tarball for packaging test:
  - command used helper script with env prefix `/tmp/qms-local-test`
  - output: `<repo>/gui/runtime.tar.zst`
  - measured sizes: `687,625,610` bytes uncompressed, `137,834,669` bytes compressed
- Built DMG successfully (unsigned) with:
  - `CSC_IDENTITY_AUTO_DISCOVERY=false npx electron-builder --mac dmg --arm64 --config electron-builder.json5`
- Artifacts confirmed in `gui/release`:
  - `QMatSuite-macOS-0.0.0.dmg`
  - `latest-mac.yml`
  - blockmap files
- Verified packaged app includes runtime tarball:
  - found at `gui/release/mac-arm64/QMatSuite.app/Contents/Resources/runtime.tar.zst`
- Mounted DMG via `hdiutil` and confirmed `QMatSuite.app` is present in image root.
- Note: stale legacy `YourAppName-...` DMG files still exist under `gui/release/0.0.0` from historical builds; new workflow should clean release output before building.

### 2026-02-23 — QE GitHub release install pathway check
- `resolve_qe_github_release_asset()` on current platform (`darwin/arm64`) returns:
  - `RuntimeError: No QE release asset matched platform=darwin/arm64, variant=openmp`
- API install check (`install_engine('qe', source='github_release')`) returns the same clear error.
- Current platform status summary:
  - macOS arm64: QE GitHub release asset currently unavailable (clear error path)
  - Windows: code is configured to resolve from `QMatSuite/quantum-espresso-windows-exe`
  - Unix non-Windows path is configured to resolve from `QMatSuite/qmatsuite-toolchain`

### 2026-02-23 — Release workflow refinements
- Added explicit release output cleanup step (`rm -rf gui/release`) in both release workflows to prevent stale artifacts from being uploaded.
- Adjusted GitHub Release upload behavior:
  - release asset upload now runs only when `inputs.version != 'local'`.
  - local workflow runs still produce downloadable build artifacts via `actions/upload-artifact` without requiring a release tag.

### 2026-02-23 — Active-code rebrand residue check
- Ran residue scan in active code/config scope:
  - `src/`, `tests/`, `gui/`, `.github/`, `pyproject.toml`
  - pattern: `\\bqv\\b|quantumvitas`
- Result: no matches in active code/config scope.

## Secrets to configure (GitHub Actions)

### Required now
- [ ] `PYPI_API_TOKEN` — PyPI publish token
- [ ] `TESTPYPI_API_TOKEN` — TestPyPI publish token

### macOS release workflow (`release-macos.yml`)
- [ ] `APPLE_CERTIFICATE_P12` — Base64-encoded Developer ID Application `.p12`
- [ ] `APPLE_CERTIFICATE_PASSWORD` — password for `.p12`
- [ ] `APPLE_TEAM_ID` — Apple Developer Team ID used in `CSC_NAME`
- [ ] `APPLE_NOTARY_ISSUER_ID` — App Store Connect issuer ID
- [ ] `APPLE_NOTARY_KEY_ID` — App Store Connect key ID
- [ ] `APPLE_NOTARY_KEY` — App Store Connect private key content (`.p8`)

### Windows release workflow (`release-windows.yml`)
- [ ] `AZURE_TENANT_ID`
- [ ] `AZURE_CLIENT_ID`
- [ ] `AZURE_CLIENT_SECRET`
- [ ] `AZURE_TRUSTED_SIGNING_ENDPOINT`
- [ ] `AZURE_TRUSTED_SIGNING_ACCOUNT`
- [ ] `AZURE_TRUSTED_SIGNING_CERT_PROFILE`

## Release runbook

1. Bump version:
   - update `<repo>/pyproject.toml` project version
   - update `<repo>/gui/package.json` version
   - commit + tag: `vX.Y.Z`
2. Publish Python package:
   - run `Release to PyPI` with `target=testpypi`
   - smoke-check install from TestPyPI
   - rerun with `target=pypi`
3. Build macOS installer:
   - run `Release macOS` with `version=X.Y.Z`, `sign=true`
   - confirm DMG + `latest-mac.yml` uploaded to draft release
4. Build Windows installer:
   - run `Release Windows` with `version=X.Y.Z`, `sign=true`
   - confirm NSIS `.exe` + `latest.yml` uploaded to draft release
5. Publish GitHub release draft:
   - verify notes + artifacts
   - publish release so auto-updater metadata is live
6. Post-release checks:
   - clean venv: `pip install qmatsuite==X.Y.Z` then verify `qms --help`, daemon import, MCP import
   - launch installer on target platform and verify first-launch runtime setup flow + Engine Manager behavior

### 2026-02-23 — Sensitive path gate failure + fix
- Final full pytest initially failed on `tests/gates/test_no_sensitive_paths.py`.
- Root cause: this Step 6 worklog used absolute local user paths in multiple entries.
- Fix applied: replaced absolute repo path references with `<repo>/...` placeholders throughout this worklog.
- Action: rerun full pytest milestone command after redaction.

### 2026-02-23 — Final verification reruns
- Full pytest rerun (after redacting sensitive local paths in worklog):
  - command: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - result: `6509 passed, 4 skipped, 979 warnings in 357.25s (0:05:57)`
  - log: `/tmp/step6_final_full_pytest_rerun.log`
- Playwright rerun:
  - command: `cd gui && npm ci && npx playwright test`
  - result: `20 passed (6.9m)`
  - log: `/tmp/step6_final_playwright.log`

### 2026-02-23 — Local Electron build status for Step 6
- Local macOS DMG build already validated in this step:
  - `CSC_IDENTITY_AUTO_DISCOVERY=false npx electron-builder --mac dmg --arm64 --config electron-builder.json5`
  - output DMG present in `gui/release/` and mountable via `hdiutil`
  - app payload includes bundled runtime archive at `.../QMatSuite.app/Contents/Resources/runtime.tar.zst`
- No additional core Python code changes were introduced in this phase; changes are limited to packaging config, release workflows, helper script, and Step 6 worklog/doc updates.
- Post-redaction targeted gate confirmation:
  - `python -m pytest tests/gates/test_no_sensitive_paths.py -v --tb=short`
  - Result: passed
