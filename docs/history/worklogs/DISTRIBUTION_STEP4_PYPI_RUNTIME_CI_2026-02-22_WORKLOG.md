# DISTRIBUTION STEP 4 WORKLOG — PyPI CI + Runtime Tarball CI + Real Engine Validation

Date: 2026-02-22
Repo: <repo_root>

## Scope and constraints
- This step adds CI workflows and performs real-world validation.
- No core Python behavior changes are intended.
- Full-suite pytest command rule (strict):
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- Full-suite run must be allowed to finish before any concurrent testing.

## Mandatory reads completed
1. Distribution design doc (initial section sweep) via `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md`
2. Existing CI workflow: `.github/workflows/tests.yml`
3. Current workflows listing: `.github/workflows/`
4. Packaging config: `pyproject.toml`
5. Step 3 install stack:
   - `src/qmatsuite/core/engines/micromamba.py`
   - `src/qmatsuite/core/engines/engine_installer.py`
6. Current package version check in `pyproject.toml`:
   - `version = "1.0.1"`

## Key findings from reads
- Only one workflow currently exists (`tests.yml`); release/runtime workflows are not present yet.
- Project version is static in pyproject (`1.0.1`), not SCM-derived.
- `fastmcp` is a core dependency already.
- micromamba management already includes:
  - platform asset mapping
  - SHA256 verification
  - atomic placement
  - macOS ad-hoc codesign
- engine installer already supports conda install path and verification logic.

## Execution plan (Step 4)
1. Create `.github/workflows/release-pip.yml`
   - manual dispatch inputs: version + target
   - verify input version matches `pyproject.toml`
   - build sdist/wheel
   - clean-venv install and smoke checks (`import`, daemon, CLI, MCP)
   - upload to TestPyPI/PyPI via twine and corresponding token
2. Create `.github/workflows/build-runtime-tarball.yml`
   - manual dispatch input for version/local
   - matrix for macOS arm64 + windows x64
   - setup micromamba, create runtime env, install package + mcp extra
   - runtime verification + size report
   - generate `.tar.zst` artifact in cross-platform Python step
3. Run local validations (real)
   - local build + clean install checks
   - local runtime tarball prototype build and size measurement
   - real micromamba download (`ensure_micromamba`) with evidence
   - real `qms engine install xtb` + detection + verify
   - run at least one real xTB integration test if available
   - optionally test lammps install/verify
4. Run strict full pytest once and wait to completion.
5. Document secrets checklist + publish instructions in this worklog.

## Notes on decision boundaries
- For PyPI workflow version handling, fail-fast on input mismatch with static `pyproject.toml` to avoid hidden mutation/commit side effects in CI.
- Runtime tarball compression will be done in Python using `zstandard` to avoid OS-specific `tar --zstd` gaps on windows runners.
- Validation commands and timings will be recorded with timestamps and command outputs summarized.

## Task 1 progress — PyPI release workflow

### Local pre-validation (build + clean install) before writing CI YAML
Command run:
- `source .venv/bin/activate`
- `python -m pip install --upgrade pip build twine`
- `rm -rf dist build && python -m build`
- `python -m venv /tmp/qms-verify-step4`
- `/tmp/qms-verify-step4/bin/pip install dist/*.whl`
- `/tmp/qms-verify-step4/bin/python -c "import qmatsuite"`
- `/tmp/qms-verify-step4/bin/python -c "from qmatsuite.daemon.server import main"`
- `/tmp/qms-verify-step4/bin/qms --help`
- `/tmp/qms-verify-step4/bin/python -c "from qmatsuite.mcp.server import create_server"`

Observed results:
- Build succeeded:
  - `dist/qmatsuite-1.0.1.tar.gz`
  - `dist/qmatsuite-1.0.1-py3-none-any.whl`
- Clean-venv install succeeded from wheel.
- Smoke checks passed:
  - `qmatsuite import OK`
  - `version: 1.0.1`
  - `daemon OK`
  - `MCP OK`
  - `qms --help` rendered expected CLI help header.

Noted warning (non-blocking for Step 4):
- setuptools deprecation warning on `project.license` TOML table form.

### Workflow file added
- `.github/workflows/release-pip.yml`

Implemented behavior:
- Manual dispatch with inputs:
  - `version` (required)
  - `target` (`testpypi` or `pypi`)
- Version guard:
  - parses `pyproject.toml` using `tomllib`
  - fails if input version != static project version
- Build stage:
  - `python -m build`
  - `twine check dist/*`
- Mandatory clean-venv verification stage:
  - wheel install
  - import/version check
  - daemon import
  - CLI help
  - MCP import
- Publish stage:
  - TestPyPI upload with `TESTPYPI_API_TOKEN`
  - PyPI upload with `PYPI_API_TOKEN`

## Task 2 progress — Runtime tarball CI workflow

### Workflow file added
- `.github/workflows/build-runtime-tarball.yml`

Implemented behavior:
- Manual dispatch input:
  - `qmatsuite_version` (defaults to `local`)
- Matrix:
  - `macos-14` (`macos-arm64`)
  - `windows-latest` (`windows-x64`)
- Setup:
  - `setup-micromamba` action
  - create runtime env with python 3.12
- Install source:
  - `local` -> install from checkout (`.[mcp]`)
  - non-local -> install `qmatsuite[mcp]==<version>` from PyPI
- Verification:
  - import/version
  - daemon import
  - MCP import
  - `qms --help`
- Packaging:
  - cross-platform `.tar.zst` creation via Python + `zstandard`
  - prints uncompressed + compressed byte sizes
- Artifact upload:
  - `runtime-${platform}`

### Sanity check
- Parsed both new YAML files successfully with PyYAML in local dev env.

## Task 3 progress — Real micromamba + engine installation validation

### 3a) Real micromamba download/setup via Step 3 API
Command:
- `python -c "from qmatsuite.core.engines.micromamba import ensure_micromamba ..."`

Observed:
- `app_data`: `<repo_root>/.qmatsuite`
- `resolved_path`: `<repo_root>/.qmatsuite/micromamba/bin/micromamba`
- `release_tag`: `2.5.0-2`
- `platform`: `Darwin arm64`
- `existed_before`: `False`
- `exists_after`: `True`
- elapsed: `1.65s`
- binary size: `13,933,424` bytes

Ad-hoc signing evidence:
- `codesign -dv --verbose=2 .qmatsuite/micromamba/bin/micromamba`
- reports `Signature=adhoc` and `flags=0x2(adhoc)`

SHA256 note:
- `ensure_micromamba()` path executed the built-in checksum verification (download checksum + compare) before promoting the binary.

### 3b) Real xTB install through CLI/API path

#### Initial failure discovery (important)
Command:
- `qms engine install xtb`

Result:
- failed with `CalledProcessError` from micromamba subprocess.

Deep diagnosis:
- Direct micromamba command succeeded:
  - `.qmatsuite/micromamba/bin/micromamba -r .qmatsuite/micromamba create --yes --name xtb-latest -c conda-forge xtb`
- Reproduced failure in a minimal Python subprocess with same env shape used by `run_micromamba`.
- Root cause stderr:
  - `Bad conversion of configurable 'no_rc' from environment variable 'MAMBA_NO_RC' with value '1'`
- Interpretation:
  - On this micromamba build, `MAMBA_NO_RC=1` is rejected by config parsing (expects boolean text form).

Validation workaround (without changing core code in Step 4):
- Set shell env `MAMBA_NO_RC=true` before running CLI commands.
- Because Step 3 code uses `env.setdefault("MAMBA_NO_RC", "1")`, the pre-set value is preserved.

#### Clean-cycle xTB pipeline test
Commands:
- `qms engine uninstall xtb`
- `MAMBA_NO_RC=true qms engine install xtb`
- `qms engine verify xtb`

Observed:
- uninstall: success (`real 0.41s`)
- install: success (`real 1.67s`) to:
  - `<repo_root>/.qmatsuite/micromamba/envs/xtb-latest/bin`
- verify: `xtb: OK` (`real 0.68s`)
- subsequent install call reports stable parsed version:
  - `Installed xtb (conda): conda-6.7.1`
  - `version: 6.7.1`

Installed env size:
- `du -sh .qmatsuite/micromamba/envs/xtb-latest` -> `54M`

### 3c) Real xTB calculation end-to-end
Command:
- `PATH=.qmatsuite/micromamba/envs/xtb-latest/bin:$PATH python -m pytest tests/integration/test_xtb_execution.py -v --tb=short`

Result:
- `7 passed, 3 warnings in 11.69s` (`real 12.97s`)

Interpretation:
- Validates full practical chain:
  - installed xTB binary execution
  - registry/discovery visibility
  - driver registration
  - full relax+promote workflow using real xTB execution

### 3d) Optional second engine test — LAMMPS
Commands:
- `MAMBA_NO_RC=true qms engine install lammps`
- `qms engine verify lammps`

Result:
- install success (`real 37.30s`)
- verify success (`real 1.39s`)
- installation path:
  - `<repo_root>/.qmatsuite/micromamba/envs/lammps-latest/bin`

Installed env size:
- `du -sh .qmatsuite/micromamba/envs/lammps-latest` -> `966M`

### Engine inventory after real installs
Command:
- `qms engine list --installed-only`

Observed relevant entries:
- `xtb        installed  source=micromamba  active=conda-6.7.1`
- `lammps     installed  source=micromamba  active=conda-Large-scale Atomic/Molecular Massively Parallel Simulator - 29 Aug 2024`

## Task 2 local verification — Runtime tarball prototype on local macOS

### Local runtime build flow executed
Commands (local prototype):
1. create env:
   - `micromamba create -y -p /tmp/qms-step4-runtime -c conda-forge python=3.12 pip`
2. install package from local checkout:
   - `micromamba run -p /tmp/qms-step4-runtime python -m pip install '<repo_root>/.[mcp]'`
3. verify:
   - import/version
   - daemon import
   - MCP import
   - `qms --help`
4. compress to zstd tarball using Python `zstandard`

Timed observations:
- env create: `real 17.68s`
- pip upgrade in env: `real 2.68s`
- package install: `real 26.65s`

Verification outputs:
- `runtime version: 1.0.1`
- `runtime daemon OK`
- `runtime MCP OK`
- `qms --help` rendered as expected

Size metrics:
- uncompressed (`du -sh /tmp/qms-step4-runtime`): `801M`
- uncompressed (byte count): `872,179,131`
- compressed tarball bytes: `152,569,839`
- compressed file: `/tmp/qms-step4-runtime.tar.zst` (`146M`)

Self-contained extraction test:
- extracted archive to `/tmp/qms-step4-runtime-extract`
- ran `/tmp/qms-step4-runtime-extract/bin/python -c "import qmatsuite ..."`
- result: `extracted runtime version: 1.0.1` (`real 5.40s`)

Size note vs design expectation:
- current local prototype is significantly larger than the design target (~350MB uncompressed / ~115MB compressed).
- likely contributors: full scientific dependency stack + packaged resources.
- no Step 4 code changes were made for size tuning; this is recorded for release optimization follow-up.

## Step 4 issue log (for follow-up)
1. `MAMBA_NO_RC` compatibility with micromamba `2.5.0-2`:
   - value `1` fails parsing (`yaml-cpp bad conversion`) in this environment.
   - value `true` works.
   - This affects CLI/API install path because Step 3 `run_micromamba` defaults to `"1"`.
   - For Step 4 validation, used env override workaround (`MAMBA_NO_RC=true`) instead of core code edit.

## Task 5 — GitHub Secrets Checklist

### Secrets to Configure in GitHub Settings → Secrets → Actions

#### For PyPI publishing (Step 4)
- [ ] `PYPI_API_TOKEN` — from https://pypi.org/manage/account/token/
- [ ] `TESTPYPI_API_TOKEN` — from https://test.pypi.org/manage/account/token/ (optional but recommended)

#### For macOS signing (Step 6, future)
- [ ] `APPLE_CERTIFICATE_P12`
- [ ] `APPLE_CERTIFICATE_PASSWORD`
- [ ] `APPLE_TEAM_ID`
- [ ] `APPLE_NOTARY_ISSUER_ID`
- [ ] `APPLE_NOTARY_KEY_ID`
- [ ] `APPLE_NOTARY_KEY`

#### For Windows signing (Step 6, future)
- [ ] `AZURE_TENANT_ID`
- [ ] `AZURE_CLIENT_ID`
- [ ] `AZURE_CLIENT_SECRET`

## Publish Runbook (for maintainers)

### How to publish to PyPI
1. Go to GitHub → Actions → **Release to PyPI**.
2. Click **Run workflow**.
3. Enter `version` (must match `pyproject.toml`, e.g. `1.0.1`).
4. Select `target = testpypi` and run.
5. After test publish succeeds, run again with `target = pypi`.
6. Verify from a clean environment:
   - `pip install qmatsuite`
   - `qms --help`

### How to build runtime tarball artifacts
1. Go to GitHub → Actions → **Build Runtime Tarball**.
2. Click **Run workflow**.
3. Input `qmatsuite_version`:
   - `local` to build from checked-out source on workflow runner, or
   - concrete version (e.g. `1.0.1`) to pull from PyPI.
4. Download artifacts:
   - `runtime-macos-arm64`
   - `runtime-windows-x64`
5. Validate artifact by extraction and running `<extracted>/bin/python -c "import qmatsuite"` (platform path variant on Windows).

## Task 4 — Mandatory full-suite verification (strict)

Command:
- `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- output captured to `.tmp/pytest_step4_full.log`

Result:
- Exit code: `0`
- Runtime: `373.14s` (~6m13s)
- Summary: `6497 passed, 4 skipped, 980 warnings`

Conclusion:
- Step 4 changes (new CI YAML + documentation/worklog updates) did not introduce test regressions.
