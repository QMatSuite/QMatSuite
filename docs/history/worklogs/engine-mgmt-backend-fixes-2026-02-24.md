# Engine Management Backend Fixes Worklog — 2026-02-24

## Context

Fixes 3 confirmed bugs from the engine management review that caused the
"Download/Install does nothing" behaviour in the UI.

## Bug Fixes

### H3 — Micromamba subprocess timeout (Fix 3)

**Problem**: `run_micromamba()` had no timeout — `micromamba create` could hang indefinitely.

**Fix**: Added `timeout` parameter (default 900s) to `run_micromamba()`,
`create_env()` (default 900s), and `remove_env()` (default 120s).
`subprocess.TimeoutExpired` is caught and re-raised as `RuntimeError`.

**Files**: `src/qmatsuite/core/engines/micromamba.py`

### H2 — Checksum filename mismatch (Fix 2)

**Problem**: Code looked for `<asset>.sha256` but releases publish
`checksums.txt`; SHA256 verification was silently skipped.

**Fix**:
- Added `_parse_checksums_txt(text, target_filename)` helper.
- Refactored `_verify_or_download_sha256()` → `_verify_sha256()` with
  `expected_hash` and `checksum_url` parameters. On mismatch, deletes the
  bad file and raises `RuntimeError`. Logs WARNING when no checksum is
  available.
- `resolve_qe_github_release_asset()` now scans for `checksums.txt` asset
  and extracts the hash.
- `install_engine_github_release()` accepts `expected_sha256` parameter.
- `api/engines.py` passes `expected_sha256` through.

**Files**: `src/qmatsuite/core/engines/engine_installer.py`,
`src/qmatsuite/api/engines.py`

### H1 — No install progress data (Fix 1)

**Problem**: Engine install jobs produced no progress data — UI showed
static "install in progress..." for 5-20 minutes.

**Fix**:
- Added 4 progress fields to `Job` dataclass: `progress_pct`,
  `progress_bytes`, `progress_total`, `progress_stage`.
- Both `_download_binary()` functions (micromamba + engine_installer) now
  do chunked 64KB reads with `on_progress(**kw)` callback.
- `ensure_micromamba()` and `run_micromamba()` accept `on_progress`.
  When provided, `run_micromamba` uses Popen + reader-thread pattern for
  safe timeout with streaming output.
- `create_env()` threads `on_progress` through.
- `install_engine_conda()` and `install_engine_github_release()` emit
  stage events (Bootstrapping, Installing, Verifying, Extracting,
  Registering) and forward download progress.
- `api/engines.py:install_engine()` accepts and forwards `on_progress`.
- `daemon/server.py:_handle_engine_install()` creates a progress callback
  closure that updates `Job` fields in real-time.

**Files**: `src/qmatsuite/daemon/jobs.py`, `src/qmatsuite/daemon/server.py`,
`src/qmatsuite/core/engines/micromamba.py`,
`src/qmatsuite/core/engines/engine_installer.py`,
`src/qmatsuite/api/engines.py`

## Tests Added

| File | Tests | Description |
|------|-------|-------------|
| `tests/unit/test_micromamba.py` | +4 | timeout forwarding, timeout error, create_env timeout, download progress |
| `tests/unit/test_engine_installer.py` | +9 | checksums.txt parsing (4), verify_sha256 (2), resolve with checksums.txt (1), download progress (2) |
| `tests/unit/test_job_progress.py` (new) | +2 | progress fields default None, fields in to_dict/to_summary_dict |
| `tests/integration/test_engine_install_real.py` (new) | +2 | checksums.txt format (network), full xTB install pipeline (opt-in) |
| `tests/unit/test_api_engine_installation.py` | fixed | Updated mocks for new `on_progress` and `expected_sha256` params |

## Test Results

- 5979 passed, 4 skipped, 0 new failures
- Pre-existing: 1 gate test failure (sensitive path in unrelated worklog)
