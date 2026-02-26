# MCP E2E Readiness Review & Gap Analysis

**Date:** 2026-02-25
**Scope:** Full audit of MCP implementation, test coverage, engine management gaps, and path to "zero-knowledge" agent E2E experience.

---

## Part 1: Current MCP Implementation Inventory

### 1.1 MCP Server Entry Point

**File:** `src/qmatsuite/mcp/server.py` (113 lines)

The MCP server is started via:

```bash
python -m qmatsuite.mcp.server
```

There is **no `qms mcp` CLI subcommand**. The entry point is purely `python -m`. The `if __name__ == "__main__"` block (line 111-112) calls `create_server().run()`.

**Transport:** stdio only (FastMCP 2.14.5 with NDJSON). No HTTP/SSE transport.

**Startup sequence:**
1. `_register_tools()` — imports all 32 tool modules (side-effect registration via `@mcp.tool`)
2. `_autoload_project()` — reads `QMATSUITE_PROJECT` env var (defaults to `.`), attempts `find_project_root()` walk-up
3. `mcp.run()` — starts stdio event loop

### 1.2 Configuration File

**File:** `.mcp.json.example` (repo root)

```json
{
  "mcpServers": {
    "qmatsuite": {
      "type": "stdio",
      "command": ".venv/bin/python",
      "args": ["-m", "qmatsuite.mcp.server"],
      "instructions": "QMatSuite is a computational materials science..."
    }
  }
}
```

This is **project-scoped** (designed for Claude Code's `.mcp.json` convention). It references `.venv/bin/python` as a relative path, which only works if the agent's CWD is the repo root.

**For Claude Desktop** (`claude_desktop_config.json`), the command path would need to be absolute. No template for this exists.

**For global Claude Code** (`~/.claude/settings.json`), no template exists.

### 1.3 Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `QMATSUITE_PROJECT` | Project directory for MCP server | `.` (CWD) |
| `QMATSUITE_HOME` | App data directory (engines, config, libraries) | Tier-based (see Part 3) |
| `QMATSUITE_ELECTRON` | If `1`, use platform-specific app-data paths | Not set |

### 1.4 All 32 MCP Tools

#### Stage P1: Project Management
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 1 | `init_project(name="")` | Initialize or load QMS project | `QMSService.init_project()` |

#### Stage 0+1: Read-Only Discovery
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 2 | `ping()` | Health check | Returns version + status |
| 3 | `list_engines(installed_only=False)` | All 15 engines with capabilities | `api.engines.list_engines()` + `DriverRegistry` |
| 4 | `list_workflows(engine)` | Workflows for an engine | `DriverRegistry.get_driver()` |
| 5 | `get_presets(engine, workflow)` | Quality preset dimensions | Preset compiler |
| 6 | `search_parameters(query, engine="", max_results=5)` | BM25 search over ~1000 parameter docs | `SearchIndex` |

#### Stage 2: Configuration
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 7 | `create_calculation(engine, workflow, structure_selector, name="")` | Create calc with steps | `QMSService.create_calculation()` |
| 8 | `set_species_map(calc_ulid, species_map)` | Set pseudopotential mapping | `QMSService.set_species_map()` |
| 9 | `set_parameters(calc_ulid, params, step=0)` | Update engine-native parameters | `QMSService.set_parameters()` |
| 10 | `apply_preset(calc_ulid, presets)` | Broadcast presets to all steps | `QMSService.apply_preset()` |
| 11 | `inspect_calculation(calc_ulid, step=-1, dry_run=False)` | Review config + preflight | `QMSService.inspect_calculation()` |
| 12 | `preview_compilation(engine, workflow, presets)` | Stateless preset compilation | Preset compiler (no project needed) |
| 13 | `list_calculations()` | All calculations in project | `QMSService.list_calculations()` |

#### Stage 3: Execution
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 14 | `run_calculation(calc_ulid, run_mode="incremental")` | Execute synchronously | `QMSService.run_calculation()` |
| 15 | `get_status(calc_ulid)` | Historical run state | `QMSService.get_run_status()` |
| 16 | `get_results_summary(calc_ulid, step=-1)` | Compact results | `QMSService.get_results_summary()` |
| 17 | `quick_run(engine, workflow, structure_selector, ...)` | Create + configure + run in one call | Chains 7+8+10+14 |

#### Stage 4: Knowledge
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 18 | `search_knowledge(query="", engine="", workflow="", ...)` | FTS5 over curated DFT insights | `KnowledgeStore.search()` |

#### Stage 7: Structures
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 19 | `list_structures()` | All structures in project | `QMSService.list_structures()` |
| 20 | `import_structure(file_path="", file_content="", format="cif", name="")` | Import structure | `QMSService.import_structure()` |
| 21 | `get_structure_detail(structure_ulid)` | Full atomic data | `QMSService.get_structure()` |

#### Stage 9: Promote
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 22 | `promote_structure(calc_ulid, step_index=-1, name="")` | Extract relaxed geometry | `QMSService.promote_structure()` |

#### Stage 10: Demo Store
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 23 | `search_demos(engine="", tag="", difficulty="", ...)` | Search pre-built demos | `QMSService.list_demo_projects()` |
| 24 | `get_demo_results(demo_id, object_type="")` | Preview pre-computed results | `ref_packs.load_ref_pack()` |
| 25 | `load_demo(demo_id, name="")` | Load demo into project | `QMSService.load_demo_as_calculation()` |

#### Stage P2: Resource Management
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 26 | `auto_resolve_species_map(calc_ulid, library="sssp", variant="precision")` | Auto-resolve pseudos | `QMSService.auto_resolve_species_map()` |
| 27 | `list_available_resources(engine, elements=None)` | Available pseudos/potentials | Resource scanners |

#### Stage P4: Pseudo Download
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 28 | `download_pseudo_library(library="sssp", variant="", version="latest")` | Download + install pseudos | SSSP downloader with SHA256 |

#### Stage P1b: Project Health
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 29 | `cleanup_project(dry_run=True)` | Remove orphaned references | `QMSService.cleanup_project()` |

#### Stage 2A: Analysis & Visualization
| # | Tool | Description | Calls |
|---|------|-------------|-------|
| 30 | `list_analyses(calc_ulid, step=-1)` | Available analysis types | Evidence checks |
| 31 | `plot_analysis(calc_ulid, object_type, step=-1)` | Parse + render (ASCII + PNG) | Parser + renderer pipeline |
| 32 | `generate_kpath(structure_selector, points_per_segment=10, path_type="hinuma")` | High-symmetry k-path | Brillouin zone library |

### 1.5 Response Envelope

All tools return a standard envelope:

```python
# Success
{"status": "success", "data": {...}, "context_hint": str, "warnings": [...]}

# Error (enriched for run failures)
{"status": "error", "error_type": str, "message": str, "severity": str,
 "context_hint": str, "suggestions": [...], "suggested_fixes": [...]}
```

---

## Part 2: Test Coverage Review

### 2.1 MCP-Specific Tests

**Location:** `tests/mcp/` — 26 test files, ~8,440 LOC, ~425 test functions

| File | Focus | Tests |
|------|-------|-------|
| `test_bands_workflow.py` | Workflow execution, kpath, band structure | ~30 |
| `test_stage10.py` | Post-processing analysis | Integration |
| `test_stage11.py` | Advanced analysis (fatbands, PDOS) | Integration |
| `test_phase2a.py` | Phase 2A core functionality | Comprehensive |
| `test_stage_p2.py` | Parameter handling | Set/get with validation |
| `test_stage_p3.py` | Advanced parameterization | Complex workflows |
| `test_stage3.py` | Execution (run, status, results) | Contract + real QE |
| `test_demo_store_mcp.py` | Demo discovery | Filters by engine/difficulty |
| `test_list_engines_install_detection.py` | Engine list/install detection | Installed status mapping |
| `test_project_robustness.py` | Project lifecycle | Edge cases |
| `test_stage_p4.py` | Pseudo download | Extended workflows |

### 2.2 Agent Matrix Test Results

**Location:** `.tmp/agent_mcp_test/run_20260221_165410/`

17 tasks, **all PASS**, covering:

| Task | Workflow | Engine |
|------|----------|--------|
| na_scf | SCF | QE |
| si_scf | SCF | QE |
| si_bands | Bands | QE |
| si_dos | DOS | QE |
| si_relax_bands | Relax+Bands | QE |
| al_scf | SCF | QE |
| fe_magnetic | Magnetic SCF | QE |
| bad_config | Error recovery | QE |
| water_xtb | Single-point | xTB |
| fe_magnetization_check | Magnetization | QE |
| xtb_promote | Promote structure | xTB |
| si_vc_relax | VC-relax | QE |
| orca_water | Single-point | ORCA |
| failing_scf | SCF failure handling | QE |
| al_dos | DOS | QE |
| mg_hcp_scf | HCP SCF | QE |
| si_convergence | Convergence | QE |

**Matrix dimensions:** 3 engines (QE, xTB, ORCA) x 10+ workflows x 17 scenarios. All 17 created projects. SSSP downloaded successfully.

### 2.3 Contract Crawler Coverage

**Location:** `tests/contract_crawler/` — 23 files

```
Total RPC methods:    116
  Covered (auto):      26 (22.4%)
  Covered (recipe):    85 (73.3%)
  Exempt:               5 (4.3%)
  Total covered:      111 (95.7%)

GUI methods:           70
  Covered:             66 (94.3%)
  Exempt:               4 (5.7%)
```

**Exempt methods (5):** `cancel_job`, `get_job_status`, `get_job_logs` (ephemeral job state), `compile_fixture_volume` (dev-only), `shutdown` (terminates daemon).

**How this maps to MCP:** The contract crawler covers daemon RPC methods. MCP tools are a separate frontend that call `QMSService` directly (not daemon RPC). The 32 MCP tools have their own test suite in `tests/mcp/`. The crawler's 95.7% coverage applies to the daemon/GUI path only.

### 2.4 Engine Management Tests

| Layer | File | What's Tested |
|-------|------|---------------|
| Unit | `tests/unit/test_api_engine_installation.py` | Install routing (conda vs GitHub), uninstall, commercial engine rejection, platform-aware source selection |
| Unit | `tests/unit/test_engine_installer.py` | Conda env creation, registry persistence, cleanup on failure, Python engine install |
| Integration | `tests/integration/test_engine_install_real.py` | Real checksums.txt fetch, full xTB conda install/uninstall pipeline (network-gated) |
| CLI | `tests/cli/test_engine_commands.py` | `qms engine list/install/uninstall/verify` |
| Daemon RPC | `tests/daemon/contract/test_engine_rpcs.py` | engine.list, engine.install, engine.uninstall, engine.verify, engine.set_active |
| GUI E2E (mock) | `gui/tests/e2e/engine_manager.spec.ts` | Progress bar, state transitions, missing-engine guidance |
| GUI E2E (real) | `gui/tests/e2e/engine_install_real.spec.ts` | Full xTB install/uninstall through Electron UI, real conda |

---

## Part 3: Engine Management via MCP — The Critical Gap

### 3.1 What Engine Management is Exposed via MCP Today

**One tool only:**

```python
# src/qmatsuite/mcp/tools/list_engines.py
@mcp.tool
def list_engines(installed_only: bool = False) -> dict:
    """List all available computation engines with their capabilities."""
```

This is **read-only**. It returns engine metadata (display name, gen steps, capabilities, parameter count, syntax family, installed status). It calls `api.engines.list_engines()` + `DriverRegistry`.

**Everything else is missing.** No install, uninstall, register path, verify, set active, list installable, fix permissions, or unregister.

### 3.2 Daemon RPC vs MCP: Complete Gap Matrix

| Daemon RPC Method | Handler (server.py) | API Function (api/engines.py) | MCP Tool | Status |
|-------------------|---------------------|-------------------------------|----------|--------|
| `engine.list` | `_handle_engine_list` | `list_engines()` | `list_engines` | Present |
| `engine.list_installable` | `_handle_engine_list_installable` | `list_installable_engines()` | -- | **MISSING** |
| `engine.install` | `_handle_engine_install` | `install_engine()` | -- | **MISSING** |
| `engine.uninstall` | `_handle_engine_uninstall` | `uninstall_engine()` | -- | **MISSING** |
| `engine.register_path` | `_handle_engine_register_path` | `register_engine()` | -- | **MISSING** |
| `engine.unregister` | `_handle_engine_unregister` | `unregister_engine()` | -- | **MISSING** |
| `engine.verify` | `_handle_engine_verify` | `verify_engine()` | -- | **MISSING** |
| `engine.set_active` | `_handle_engine_set_active` | `set_active_engine()` | -- | **MISSING** |
| `engine.fix_permissions` | `_handle_engine_fix_permissions` | `fix_engine_permissions()` | -- | **MISSING** |
| `engine.path` (alias) | `_handle_engine_register_path` | (same as register_path) | -- | **MISSING** |

**Summary:** 9 of 10 engine management capabilities are daemon-only. MCP has read-only access.

### 3.3 QVService and Engine Management

**Finding: Engine management is NOT in QVService.**

`QMSService` (`src/qmatsuite/api/service.py`, 398 KB) handles project-scoped operations (calculations, structures, analysis). Engine management lives in a separate module: `src/qmatsuite/api/engines.py` (306 lines).

This is architecturally correct — engines are application-wide (stored in `~/.qmatsuite/`), not per-project. The MCP tools that exist (like `list_engines`) already call `api.engines` directly, not through `QMSService`. New engine MCP tools should follow the same pattern.

### 3.4 Engine Install Call Chain (Traced)

```
MCP tool (MISSING) → api.engines.install_engine()
  ├── Normalize engine_family (validate against ENGINE_META)
  ├── Select source (auto → resolve from ENGINE_META)
  │   ├── If conda: → core.engines.engine_installer.install_engine_conda()
  │   └── If github_release:
  │       ├── resolve_qe_github_release_asset() → {asset_url, checksum_url, sha256}
  │       └── → core.engines.engine_installer.install_engine_github_release()
  ├── Creates micromamba env / downloads binary
  ├── Verifies binary exists and is executable
  ├── EngineRegistry.add_installation() → persist to engines.json
  ├── EngineRegistry.set_active()
  └── Returns {"engine", "source", "installation": {id, path, version, ...}}
```

The API layer is fully implemented. The **only** missing piece is the MCP tool wrapper.

### 3.5 The Pip-Install Engine Storage Path Question

**`get_app_data_dir()` resolution chain** (`src/qmatsuite/core/paths.py:94-115`):

| Priority | Condition | Resolved Path |
|----------|-----------|---------------|
| 1 | `QMATSUITE_HOME` env var set | Whatever the env var says |
| 2 | Running from source checkout (dev mode) | `<repo_root>/.qmatsuite` |
| 3 | `QMATSUITE_ELECTRON=1` set | Platform-specific (e.g., `~/Library/Application Support/QMatSuite`) |
| 4 | Fallback (pip install from PyPI) | `~/.qmatsuite` |

**Current dev setup verified:** `get_app_data_dir()` returns `/Users/hh7465/QMatSuite/.qmatsuite` (tier 2, dev mode).

**Engine storage paths relative to `get_app_data_dir()`:**

| Asset | Relative Path |
|-------|--------------|
| Engine registry | `config/engines.json` |
| Engine binaries (bundled/GitHub) | `engines/<family>/<install_id>/bin/` |
| Micromamba binary | `micromamba/bin/micromamba` |
| Conda environments | `micromamba/envs/<env_name>/` |
| Pseudo libraries | `libraries/pseudo/` |

**Persistence across venv recreation:**

| Scenario | Venv A | Venv B | Data Dir Same? | Engines Persist? |
|----------|--------|--------|----------------|-----------------|
| Both pip from PyPI | `~/.qmatsuite` | `~/.qmatsuite` | Yes | **Yes** |
| Both editable install | `<repo>/.qmatsuite` | `<repo>/.qmatsuite` | Yes | **Yes** |
| Editable -> PyPI | `<repo>/.qmatsuite` | `~/.qmatsuite` | **No** | **No** |
| PyPI -> Editable | `~/.qmatsuite` | `<repo>/.qmatsuite` | **No** | **No** |

**For the "zero-knowledge" agent scenario (pip install from PyPI):** Engines are stored at `~/.qmatsuite/engines/`. Destroying and recreating the venv does NOT affect this directory. Previously installed engines **will** be found on reinstall. This is correct behavior.

---

## Part 4: MCP Self-Setup — What's Missing

### 4.1 MCP Config Generation

**Current state: No CLI command exists.**

There is no `qms mcp` subcommand. The CLI (`src/qmatsuite/cli/main.py`) has `engine`, `init`, `step`, `run`, `analyze`, `history` subcommands but no `mcp`.

**Minimal MCP config for Claude Code** (project-scoped `.mcp.json`):

```json
{
  "mcpServers": {
    "qmatsuite": {
      "type": "stdio",
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "qmatsuite.mcp.server"],
      "env": {
        "QMATSUITE_PROJECT": "/path/to/project"
      }
    }
  }
}
```

**For Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "qmatsuite": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "qmatsuite.mcp.server"],
      "env": {
        "QMATSUITE_PROJECT": "/path/to/project"
      }
    }
  }
}
```

### 4.2 Documentation for Agent Self-Setup

**Existing:** `docs/design/AGENT_INTEGRATION_DESIGN.md` (178 KB) — master design doc with philosophical foundations, decision hierarchy, and MCP stage worklogs. This is a design doc, NOT an agent-readable bootstrap guide.

**Missing:** A concise, machine-readable bootstrap guide that an agent could follow. Something like:

```
1. python -m venv .venv && source .venv/bin/activate
2. pip install qmatsuite
3. Write .mcp.json with: {"mcpServers": {"qmatsuite": ...}}
4. Restart agent
5. call init_project()
6. call list_engines(installed_only=True) to check what's available
```

### 4.3 The Bootstrap Chicken-and-Egg Problem

Before MCP is configured, the agent can only use shell commands. Minimal shell sequence from zero to working MCP:

```bash
# 1. Create venv and install
python3 -m venv .venv
.venv/bin/pip install qmatsuite

# 2. Verify installation
.venv/bin/python -c "import qmatsuite; print('OK')"

# 3. Write MCP config (agent must do this via shell)
cat > .mcp.json << 'EOF'
{
  "mcpServers": {
    "qmatsuite": {
      "type": "stdio",
      "command": ".venv/bin/python",
      "args": ["-m", "qmatsuite.mcp.server"]
    }
  }
}
EOF

# 4. User restarts agent (manual step)
# 5. After restart, MCP tools are available
```

**Problem:** Step 3 requires the agent to generate a correct JSON config without any QMatSuite assistance. A `qms mcp config` CLI command would solve this:

```bash
.venv/bin/qms mcp config > .mcp.json
```

### 4.4 Existing CLI Engine Commands

The CLI already has engine management (`qms engine <subcommand>`):

| CLI Command | What It Does | API Function |
|-------------|-------------|--------------|
| `qms engine list` | List engine installation status | `api.engines.list_engines()` |
| `qms engine install <engine> [--version V] [--source S]` | Install engine | `api.engines.install_engine()` |
| `qms engine uninstall <engine> [--installation-id ID]` | Uninstall engine | `api.engines.uninstall_engine()` |
| `qms engine verify <engine>` | Verify active installation | `api.engines.verify_engine()` |
| `qms engine path <engine> <path>` | Register user-provided path (BYOE) | `api.engines.register_engine()` |

These work before MCP is configured. An agent could use `qms engine install qe` via shell to bootstrap QE before MCP setup.

---

## Part 5: Gap Analysis — Current State vs Vision

| # | Capability | Required | Current State | Gap | Priority |
|---|-----------|----------|---------------|-----|----------|
| 1 | MCP server starts via `python -m qmatsuite.mcp.server` | Yes | **Working** | None | -- |
| 2 | Agent can list engines via MCP | Yes | **Working** — `list_engines()` | None | -- |
| 3 | Agent can install QE via MCP | Yes | **Missing** — no MCP tool, API exists | Add `install_engine` MCP tool | **P0** |
| 4 | Agent can install conda engines (xTB, PySCF...) via MCP | Yes | **Missing** — same gap | Same tool handles all engines | **P0** |
| 5 | Agent can register BYOE path via MCP | Yes | **Missing** — no MCP tool, API exists | Add `register_engine_path` MCP tool | **P1** |
| 6 | Agent can run a calculation via MCP | Yes | **Working** — `run_calculation()`, `quick_run()` | None | -- |
| 7 | Agent can get results via MCP | Yes | **Working** — `get_results_summary()`, `plot_analysis()` | None | -- |
| 8 | Agent can download pseudopotentials via MCP | Nice | **Working** — `download_pseudo_library()` | None | -- |
| 9 | `qms mcp config` CLI generates MCP JSON | Yes | **Missing** — no CLI subcommand | Add `qms mcp config` command | **P1** |
| 10 | Engine storage survives venv recreation | Yes | **Working** for same install type | Edge case: editable<->PyPI | Low |
| 11 | Global MCP config works (not just project-scoped) | Yes | **Partially** — `.mcp.json.example` exists, no global template | Add global config template + docs | **P2** |
| 12 | Agent can list installable engines via MCP | Yes | **Missing** — no MCP tool, API exists | Add `list_installable_engines` MCP tool | **P0** |
| 13 | Agent can verify engine via MCP | Yes | **Missing** — no MCP tool, API exists | Add `verify_engine` MCP tool | **P1** |
| 14 | Agent can uninstall engine via MCP | Nice | **Missing** — no MCP tool, API exists | Add `uninstall_engine` MCP tool | **P2** |
| 15 | Agent can set active engine installation via MCP | Nice | **Missing** — no MCP tool, API exists | Add `set_active_engine` MCP tool | **P2** |
| 16 | Agent-readable bootstrap documentation | Yes | **Missing** — only design doc exists | Write bootstrap guide | **P1** |

---

## Part 6: Proposed Implementation Plan

### Phase A: Minimum Viable Agent E2E (P0)

The absolute minimum to go from `pip install qmatsuite` to a completed Si SCF calculation via MCP, assuming QE is not pre-installed.

#### A1. Add `install_engine` MCP tool

**File to create:** `src/qmatsuite/mcp/tools/install_engine.py`

```python
@mcp.tool
def install_engine(
    engine: str,
    version: str = "",
    source: str = "auto",
) -> dict:
    """Install a computation engine (e.g., QE, xTB, ORCA).

    Installs via conda (micromamba) or GitHub release depending on the engine.
    This is a synchronous operation — it will block until installation completes.
    For QE, expect ~60-120 seconds (GitHub release download + extraction).
    For conda engines (xTB, PySCF), expect ~30-60 seconds.

    Args:
        engine: Engine family name (e.g., 'qe', 'xtb', 'pyscf', 'orca').
        version: Version to install (optional, uses latest if empty).
        source: Install source ('auto', 'conda', 'github_release').
    """
```

**Calls:** `api.engines.install_engine(engine, version=version or None, source=source, on_progress=None)`

**Design decisions:**
- **Synchronous** — MCP tools are synchronous by nature (no job manager). The daemon uses async jobs because the GUI needs non-blocking UI, but an agent can wait.
- **No progress callback** — MCP has no streaming mechanism. The tool blocks until done and returns the result.
- **Returns installation dict** — includes `id`, `path`, `version`, `source`.

**Estimated complexity:** S (Small) — the API function is fully implemented, this is a thin wrapper.

#### A2. Add `list_installable_engines` MCP tool

**File to create:** `src/qmatsuite/mcp/tools/list_installable_engines.py`

```python
@mcp.tool
def list_installable_engines() -> dict:
    """List engines that can be automatically installed.

    Returns engines with their available install methods (conda, github_release)
    and whether they require manual installation (commercial engines like VASP).
    """
```

**Calls:** `api.engines.list_installable_engines()`

**Estimated complexity:** S

#### A3. Register new tools in `server.py`

**File to modify:** `src/qmatsuite/mcp/server.py`

Add two import lines in `_register_tools()`:
```python
import qmatsuite.mcp.tools.install_engine  # noqa: F401
import qmatsuite.mcp.tools.list_installable_engines  # noqa: F401
```

#### A4. Add tests

**File to create:** `tests/mcp/test_engine_management_mcp.py`

Tests:
- `test_list_installable_engines_returns_engines` — verify response schema
- `test_install_engine_invalid_engine_returns_error` — error path for unknown engine
- `test_install_engine_commercial_rejects_auto` — VASP returns error on "auto"
- `test_install_engine_mocked_conda` — mock `api.engines.install_engine`, verify call
- `test_install_engine_mocked_github` — mock for QE GitHub release path

**Estimated complexity:** M (Medium) — need to mock the API layer carefully.

### Phase B: Full Engine Lifecycle via MCP (P1)

#### B1. Add `verify_engine` MCP tool

**File:** `src/qmatsuite/mcp/tools/verify_engine.py`

```python
@mcp.tool
def verify_engine(engine: str) -> dict:
    """Verify the active installation of an engine.

    Checks that the engine binary exists and is executable.

    Args:
        engine: Engine family name (e.g., 'qe', 'xtb').
    """
```

**Calls:** `api.engines.verify_engine(engine)` -> returns `(ok: bool, message: str)`

**Complexity:** S

#### B2. Add `register_engine_path` MCP tool

**File:** `src/qmatsuite/mcp/tools/register_engine_path.py`

```python
@mcp.tool
def register_engine_path(
    engine: str,
    path: str,
    source: str = "user_path",
) -> dict:
    """Register a user-provided engine installation path (BYOE).

    Use this when the engine is already installed on the system at a known path.

    Args:
        engine: Engine family name (e.g., 'vasp', 'qe', 'gaussian').
        path: Absolute path to the engine binary directory.
        source: Source type ('user_path' for binary, 'user_venv' for Python engines).
    """
```

**Calls:** `api.engines.register_engine(engine, path, source=source)`

**Complexity:** S

#### B3. Add `uninstall_engine` MCP tool

**File:** `src/qmatsuite/mcp/tools/uninstall_engine.py`

```python
@mcp.tool
def uninstall_engine(
    engine: str,
    installation_id: str = "",
) -> dict:
    """Uninstall an engine installation.

    Removes the engine binary/environment and deregisters from the engine registry.
    If no installation_id is provided, uninstalls the active installation.

    Args:
        engine: Engine family name.
        installation_id: Specific installation ID to uninstall (optional).
    """
```

**Calls:** `api.engines.uninstall_engine(engine, install_id)` with fallback to `get_active_engine()` if no ID provided.

**Complexity:** S

#### B4. Add `set_active_engine` MCP tool

**File:** `src/qmatsuite/mcp/tools/set_active_engine.py`

**Complexity:** S

### Phase C: Self-Setup Tooling (P1-P2)

#### C1. Add `qms mcp config` CLI command

**File to modify:** `src/qmatsuite/cli/main.py`

Add a new Typer subcommand group:

```python
mcp_app = typer.Typer(help="MCP server configuration.", no_args_is_help=True)
app.add_typer(mcp_app, name="mcp")

@mcp_app.command("config")
def mcp_config(
    project: Optional[Path] = typer.Option(None, "--project", help="Project directory"),
    global_config: bool = typer.Option(False, "--global", help="Output global config for ~/.claude/settings.json"),
    format: str = typer.Option("claude-code", "--format", help="Config format: claude-code, claude-desktop"),
) -> None:
    """Generate MCP server configuration JSON."""
```

**Logic:**
1. Detect venv Python path (`sys.executable`)
2. Detect project directory (CWD or `--project`)
3. Generate appropriate JSON for the target format
4. Print to stdout (user redirects to file)

**Complexity:** M

#### C2. Agent bootstrap documentation

**File to create:** `docs/guides/AGENT_BOOTSTRAP.md`

A concise, step-by-step guide written for AI agents (not humans). Includes:
- The exact shell commands for venv setup
- How to generate `.mcp.json`
- What to do after MCP restart
- First tool calls to make (init_project, list_engines, install_engine)
- Troubleshooting common issues

**Complexity:** S

#### C3. Global MCP config template

**File to create:** `.mcp.global.json.example`

Template for `~/.claude/settings.json` global MCP configuration.

**Complexity:** S

---

## Part 7: The Litmus Test

### Step-by-step: Fresh Machine to Si SCF Results

**Starting state:** Fresh macOS machine, no QMatSuite, no QE, no venv. Agent: Claude Code with no MCP configured.

---

**Step 1: Agent creates venv, installs qmatsuite**

```bash
# Agent executes via shell (Bash tool)
python3 -m venv .venv
.venv/bin/pip install qmatsuite
```

**Currently works?** Yes (assuming qmatsuite is published to PyPI). The package installs cleanly.

**Blocked?** No.

---

**Step 2: Agent configures MCP**

```bash
# Option A: Agent generates config manually (works today)
cat > .mcp.json << 'EOF'
{
  "mcpServers": {
    "qmatsuite": {
      "type": "stdio",
      "command": ".venv/bin/python",
      "args": ["-m", "qmatsuite.mcp.server"]
    }
  }
}
EOF

# Option B: Using proposed `qms mcp config` (Phase C1)
.venv/bin/qms mcp config > .mcp.json
```

**Currently works?** Option A works but requires the agent to know the exact JSON format. Option B is blocked (CLI command doesn't exist).

**What would unblock:** Phase C1 (`qms mcp config`). Or: agent reads `.mcp.json.example` from the repo if doing `pip install -e .`, but that's dev-only.

---

**Step 3: User restarts agent**

The user sees "MCP server configured, please restart Claude Code" and restarts. After restart, the MCP connection is established.

**Currently works?** Yes — the server starts correctly via `python -m qmatsuite.mcp.server`.

**Blocked?** No.

---

**Step 4: Agent calls MCP tools to install QE**

```python
# Tool call sequence:
init_project(name="my-simulation")           # Initialize project
list_installable_engines()                    # See what can be auto-installed  [BLOCKED]
install_engine(engine="qe")                   # Install QE                      [BLOCKED]
verify_engine(engine="qe")                    # Verify installation             [BLOCKED]
```

**Currently works?** `init_project` works. The other three are **BLOCKED** — no MCP tools exist.

**What would unblock:** Phase A (add `install_engine`, `list_installable_engines`) + Phase B1 (`verify_engine`).

**Workaround (today):** Agent falls back to shell:

```bash
.venv/bin/qms engine install qe
.venv/bin/qms engine verify qe
```

This works today but defeats the "zero-knowledge" vision — the user would see shell commands they don't understand.

---

**Step 5: Agent runs Si SCF calculation**

```python
# All of these work today via MCP:
search_demos(engine="qe", query="silicon scf")
load_demo(demo_id="qe_si_scf")
inspect_calculation(calc_ulid="...", dry_run=True)
run_calculation(calc_ulid="...")
```

**Currently works?** Yes — all 4 tools are implemented and tested.

**Blocked?** No (assuming Step 4 succeeded and QE is installed).

---

**Step 6: Agent reports results**

```python
get_results_summary(calc_ulid="...")
plot_analysis(calc_ulid="...", object_type="convergence")
```

**Currently works?** Yes — returns energy, convergence data, ASCII plot.

**Blocked?** No.

---

### Summary: What's Blocking the Litmus Test

| Step | Status | Blocker |
|------|--------|---------|
| 1. Install package | Works | None |
| 2. Configure MCP | Partially works | No `qms mcp config` CLI (agent must handwrite JSON) |
| 3. Restart agent | Works | None (user action) |
| 4. Install QE | **BLOCKED via MCP** | No `install_engine` / `list_installable_engines` / `verify_engine` MCP tools |
| 5. Run calculation | Works | None |
| 6. Get results | Works | None |

**Minimum changes to unblock the litmus test:**
1. `install_engine` MCP tool (Phase A1) — ~50 lines of code
2. `list_installable_engines` MCP tool (Phase A2) — ~30 lines of code
3. Register both in `server.py` (Phase A3) — 2 lines

**Total estimated effort for minimum viable E2E:** ~100 lines of production code + ~200 lines of tests.

The agent can work around the missing `qms mcp config` by writing the JSON manually (it just needs to know the format). But `install_engine` has **no workaround** within MCP — the agent must fall back to shell commands, which breaks the "zero-knowledge" UX.

---

## Appendix A: Architecture Diagram

```
                 ┌──────────────────────────────────────────┐
                 │              Frontend Layer                │
                 ├──────────┬───────────────┬────────────────┤
                 │ Electron │  Claude Code   │    CLI         │
                 │ (GUI)    │  (MCP Agent)   │  (qms cmd)    │
                 └────┬─────┴──────┬────────┴───────┬────────┘
                      │            │                 │
              daemon RPC      MCP stdio          direct call
                      │            │                 │
                 ┌────▼─────┐  ┌──▼───────────┐  ┌──▼──────────┐
                 │  Daemon   │  │  MCP Server  │  │             │
                 │ server.py │  │  server.py   │  │             │
                 └────┬──────┘  └──┬───────────┘  │             │
                      │            │               │             │
                 ┌────▼────────────▼───────────────▼─────────┐
                 │           api/ Layer                        │
                 ├─────────────────────┬──────────────────────┤
                 │  QMSService         │  api.engines          │
                 │  (project-scoped)   │  (app-wide)           │
                 ├─────────────────────┴──────────────────────┤
                 │           core/ Layer (Kernel)              │
                 ├─────────────────┬──────────────────────────┤
                 │  DriverRegistry  │  EngineRegistry          │
                 │  Project, Steps  │  engine_installer        │
                 │  Structures      │  micromamba              │
                 └─────────────────┴──────────────────────────┘
                                         │
                                         ▼
                              ~/.qmatsuite/ (app data)
                              ├── config/engines.json
                              ├── engines/<family>/<id>/bin/
                              ├── micromamba/
                              └── libraries/pseudo/
```

**Key insight:** The `api.engines` module is the shared backend for all three frontends. The daemon wraps it in async jobs. The CLI calls it directly. MCP should also call it directly (synchronous). The API layer is fully implemented — only the MCP tool wrappers are missing.

## Appendix B: File Quick Reference

| Purpose | File |
|---------|------|
| MCP server entry point | `src/qmatsuite/mcp/server.py` |
| MCP app singleton | `src/qmatsuite/mcp/app.py` |
| MCP config template | `.mcp.json.example` |
| MCP tool: list_engines | `src/qmatsuite/mcp/tools/list_engines.py` |
| MCP response envelope | `src/qmatsuite/mcp/envelope.py` |
| MCP project context | `src/qmatsuite/mcp/project.py` |
| Engine API (public) | `src/qmatsuite/api/engines.py` |
| Engine installer (kernel) | `src/qmatsuite/core/engines/engine_installer.py` |
| Engine registry (kernel) | `src/qmatsuite/core/engines/engine_registry.py` |
| Micromamba bootstrap | `src/qmatsuite/core/engines/micromamba.py` |
| Path resolution | `src/qmatsuite/core/paths.py` |
| Daemon RPC handlers | `src/qmatsuite/daemon/server.py` (lines 1396-1628) |
| CLI engine commands | `src/qmatsuite/cli/main.py` (lines 1506-1631) |
| Engine unit tests | `tests/unit/test_api_engine_installation.py` |
| Engine integration tests | `tests/integration/test_engine_install_real.py` |
| MCP tests | `tests/mcp/test_*.py` (26 files) |
| Contract crawler | `tests/contract_crawler/` |
| Agent matrix tests | `.tmp/agent_mcp_test/` |
| Design doc | `docs/design/AGENT_INTEGRATION_DESIGN.md` |
