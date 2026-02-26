# Agent MCP Test Matrix — Worklog

**Date**: 2026-02-21
**Branch**: v2-python
**Goal**: Build and run a shell script that spawns 9 Claude Code CLI agent sessions against QMatSuite MCP, each performing a different materials science calculation.

---

## Phase 0: Claude Code CLI Research

### How to invoke Claude Code CLI non-interactively

**Primary non-interactive flag**: `-p` / `--print`
```sh
claude -p "Your task here"
```
- Exits after response (no interactive loop)
- Skips workspace trust dialog

**Working directory**: No `--cwd` flag. Use shell `cd`:
```sh
(cd /path/to/task_dir && claude -p "task")
```

**MCP discovery**: Claude reads `.mcp.json` from CWD automatically. Each task directory gets its own `.mcp.json`.

**Non-interactive flags used**:
- `--dangerously-skip-permissions`: Bypass all tool permission prompts (required for non-interactive mode)
- `--output-format text`: Plain text output for readable trace logs

**Transcript capture**:
```sh
(cd task_dir && claude -p "task") > trace.log 2>&1
```

**Session isolation**: Each task runs in its own subshell with its own CWD.

### Key finding: QMATSUITE_PROJECT env var
From `src/quantumvitas/mcp/server.py` line 73:
```python
_project_dir = _Path(_os.environ.get("QMATSUITE_PROJECT", ".")).resolve()
```
When not set, resolves to CWD of the MCP server process (= CWD of Claude = task directory). Each `.mcp.json` sets `env.QMATSUITE_PROJECT` to the absolute task directory path for explicit isolation.

### Pseudo_lib paths (confirmed from `src/quantumvitas/core/paths.py`)
- **Installed libraries**: `$REPO_ROOT/.qmatsuite/libraries/pseudo/SSSP/`
- **Seed cache**: `$REPO_ROOT/.qmatsuite/seeds/pseudo/`
- **Temporary downloads**: `$REPO_ROOT/.tmp/downloads/` (ephemeral, recreated per run)

Cleanup before Task 0:
```sh
rm -rf $REPO_ROOT/.qmatsuite/libraries/pseudo/SSSP
rm -rf $REPO_ROOT/.qmatsuite/seeds/pseudo
```
This forces Task 0 to discover and download SSSP fresh.

**Note**: Paths are repo-root-relative, NOT `~/.qmatsuite/` — they live under the repo root.

---

## Phase 1: Script Design

**Script**: `tools/agent_test_matrix.sh`

### Design decisions
1. **Run ID**: `run_YYYYMMDD_HHMMSS` (timestamp-based, always unique per run)
2. **Task dirs**: `.tmp/agent_mcp_test/run_<ID>/task_XX_<name>/`
3. **`.mcp.json` per task**: Python-generated from `.mcp.json.example`, with:
   - `command` set to absolute `$VENV_PYTHON` path
   - `env.QMATSUITE_PROJECT` set to absolute task directory path
4. **Task 0**: Runs synchronously (sequential). SSSP download verified before proceeding.
5. **Tasks 1-8**: All launched in parallel with `&`. `wait` collects them.
6. **Timeout**: 600 seconds per task. Uses `timeout` (or `gtimeout` if GNU coreutils installed via Homebrew).
7. **Output format**: `--output-format text` for readable trace logs.

### Iteration log

#### Iteration 1 — Run run_20260221_101013
- **Issue 1**: `CLAUDECODE` env var set → `claude: error: Claude Code cannot be launched inside another Claude Code session.`
- **Fix**: Added `unset CLAUDECODE && unset CLAUDE_CODE_ENTRYPOINT` before each `claude -p` invocation.

#### Iteration 2 — Run run_20260221_101107
- **Issue 2**: Repo root `project.qv.yml` contaminated — agents created structures/calculations there.
- **Root cause**: Claude Code searches parent directories for `.mcp.json`. Repo root had `.mcp.json` (without `QMATSUITE_PROJECT`). When found alongside task-specific `.mcp.json`, it loaded two QMatSuite MCP servers named "qmatsuite". The repo-root server had no `QMATSUITE_PROJECT`, defaulted to repo root CWD, used the repo project.
- **Fix A**: Deleted `<REPO_ROOT>/.mcp.json` from repo root (only `.mcp.json.example` kept).
- **Fix B**: Run agents from `/tmp/qmatsuite_agent_XXXXXX/` (outside repo) to prevent finding parent `.mcp.json` files AND prevent CLAUDE.md dev-mode context.
- **Fix C**: Pass `--mcp-config $task_dir/.mcp.json` explicitly to each claude invocation.
- **Fix D**: Added explicit "Your project directory is: {task_dir}" and "Write WORKLOG.md to: {task_dir}/WORKLOG.md" to all agent prompts.
- Restored `project.qv.yml` at repo root via `git checkout -- project.qv.yml`.

---

## Phase 2: Execution Results

(To be filled after first run)

---

## Phase 3: Final Results

(To be filled after successful run)
