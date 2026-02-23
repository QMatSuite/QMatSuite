# DISTRIBUTION STEP 6 WORKLOG — Release CI + Lite Installers + Cleanup + Final Validation

Date: 2026-02-23
Repo: /Users/hh7465/QMatSuite

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
- Updated `/Users/hh7465/QMatSuite/pyproject.toml`:
  - moved `mp-api>=0.30.0` into core `[project].dependencies`
  - removed optional groups `mp-api`, `mcp`, `all`
  - retained only `[project.optional-dependencies].dev`
  - added `[project.urls]` with Homepage/Repository/Issues
- Updated workflow references in `/Users/hh7465/QMatSuite/.github/workflows/build-runtime-tarball.yml`:
  - local runtime install: `pip install '.'` (was `'.[mcp]'`)
  - PyPI runtime install: `pip install qmatsuite==...` (was `qmatsuite[mcp]==...`)
- Updated docs references:
  - `/Users/hh7465/QMatSuite/docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md`
  - `/Users/hh7465/QMatSuite/docs/history/plans/DISTRIBUTION_IMPLEMENTATION_PLAN.md`
  - `/Users/hh7465/QMatSuite/docs/history/worklogs/STRUCTURE_FETCH_V2_PLAN.md`

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
- Fresh local venv `/tmp/qms-local-test` with `pip install /Users/hh7465/QMatSuite`:
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
