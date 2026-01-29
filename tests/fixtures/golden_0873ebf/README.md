# Golden Contract Fixtures from 0873ebf

These fixtures capture the daemon RPC response shapes from commit `0873ebf` (pre-DTO baseline).

## Coverage

Golden fixtures cover ALL methods that the auto-crawler and recipes successfully call at baseline:
- Auto-crawl methods: stateless methods with minimal payloads
- Recipe methods: complex methods requiring setup (calculations, steps, structures)

This ensures maximal contract coverage and drift detection.

## Generation

Golden fixtures were generated using git worktree + worktree_runner.py with guaranteed baseline isolation:

```bash
cd tests/fixtures/golden_contracts
python generate_golden.py
```

Process:
1. Creates git worktree at commit 0873ebf
2. **Copies contract_crawler package into worktree** (0873ebf won't have it)
   - Copies: introspection.py, payloads.py, crawler.py, recipes/
3. Copies worktree_runner.py into worktree
4. Runs worktree_runner.py with **isolated PYTHONPATH** (worktree-only)
   - PYTHONPATH=worktree/src:worktree/tests
   - Prevents editable install leakage
5. **Runtime assertions verify baseline isolation**:
   - git HEAD == 0873ebf
   - quantumvitas module loaded from worktree path
6. Runs crawler + ALL_RECIPES from 0873ebf baseline code
7. Captures JSON output and writes to golden_0873ebf/daemon/*.json
8. Cleans up worktree

**CRITICAL**: The runtime assertions in step 5 MUST appear in console output.
If missing, baseline isolation failed and golden fixtures are INVALID.

Do NOT regenerate unless updating the baseline. Document reason if doing so.

## Normalization

Non-deterministic fields are normalized using **key-based replacement** (no content heuristics):
- ULIDs: `<NORMALIZED_ID>` (for keys: id, structure_id, calc_id, step_id, run_id, job_id, etc.)
- Timestamps: `<NORMALIZED_TIMESTAMP>` (for keys: created_at, updated_at, started_at, completed_at, timestamp)
- Paths: `<NORMALIZED_PATH>` (for keys: project_root, log_path, io_dir)

Normalization is key-based only - we do NOT examine value content to decide normalization.

## Usage

Golden fixtures are used by `tests/contract_crawler/test_golden_contracts.py` to detect contract drift.

