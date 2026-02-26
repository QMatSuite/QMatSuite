# Worklog: MCP Engine Management Tools + Agent Bootstrap

**Date**: 2026-02-26
**Branch**: v2-python

## Summary

Added 6 MCP engine management tools, `qms mcp config` CLI command for 3 agent
ecosystems, README "AI Agent Quick Start" section, and comprehensive tests.

## Changes

### New MCP Tools (6 files)

| Tool | File | Wraps |
|------|------|-------|
| `install_engine` | `mcp/tools/install_engine.py` | `api.engines.install_engine` |
| `list_installable_engines` | `mcp/tools/list_installable_engines.py` | `api.engines.list_installable_engines` |
| `verify_engine` | `mcp/tools/verify_engine.py` | `api.engines.verify_engine` |
| `register_engine_path` | `mcp/tools/register_engine_path.py` | `api.engines.register_engine` |
| `uninstall_engine` | `mcp/tools/uninstall_engine.py` | `api.engines.uninstall_engine` |
| `set_active_engine` | `mcp/tools/set_active_engine.py` | `api.engines.set_active_engine` |

All tools follow the `list_engines.py` pattern: lazy imports, `make_response`/`make_error`
envelopes, engine validation via `ENGINE_META`, `context_hint` for agent guidance.

Commercial engines (VASP, ORCA, Gaussian) are detected by absence of `conda_package`
and `github_release` support, returning `manual_only_engine` error pointing to
`register_engine_path`.

### CLI: `qms mcp config`

- Added `mcp_app` typer group in `cli/main.py`
- Supports `--agent claude|codex|gemini`, `--scope project|user`, `--project`, `--write`
- JSON output for Claude/Gemini, TOML-style for Codex
- `--write` does JSON deep-merge or TOML section replace/append

### README

Added "AI Agent Quick Start (MCP)" section with automatic setup commands,
manual config in `<details>` blocks, and tool categories overview.

### Server Registration

Added 6 import lines to `mcp/server.py` under "Engine management tools" section.
Total tools: 32 → 38.

### Tests

| File | Tests | Type |
|------|-------|------|
| `tests/mcp/test_engine_management_mcp.py` | 16 | Unit (monkeypatched) |
| `tests/cli/test_mcp_config.py` | 10 | CLI (CliRunner) |
| `tests/mcp/test_engine_install_real.py` | 1 | Integration (network) |

Updated tool count assertions in `test_stage_p1.py`, `test_stage11.py`,
`test_stage_p2.py` from 32 → 38.

## Test Results

```
6563 passed, 0 failed, 4 skipped (395s)
```

Previous baseline: 6535 passed. Net new: +28 tests.
