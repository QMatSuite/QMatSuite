# Production Blind Test: QMatSuite v1.2.2 — Claude Code

**Date:** 2026-02-26
**Agent:** Claude Code (Claude Sonnet 4)
**QMatSuite Version:** 1.2.2 (PyPI)
**Platform:** macOS arm64, Python 3.12
**Starting State:** Empty directory `~/qms-blindtest/`, no QMatSuite installed, no engines, no MCP configured.

---

## Test 1: CLI-Only Bootstrap (Pre-MCP)

**Prompt:**
```
Install qmatsuite from PyPI in a new venv, configure it as an MCP server,
then run an SCF calculation on silicon
```

**Objective:** Validate the full bootstrap path — pip install → MCP config → engine install → calculation.

### Trace

#### 1.1 Agent Research Phase

Agent begins by searching the web for qmatsuite:

```
⏺ Web Search("qmatsuite PyPI MCP server SCF calculation")
  ⎿  Did 1 search in 6s

⏺ Web Search("qmatsuite python package quantum materials")
  ⎿  Did 1 search in 7s

⏺ Fetch(https://pypi.org/project/qmatsuite/)
  ⎿  Received 80.5KB (200 OK)

⏺ Fetch(https://github.com/QMatSuite/QMatSuite)
  ⎿  Received 381.5KB (200 OK)
```

**Observation:** Agent found the PyPI page and GitHub README. The README's "AI Agent Quick Start" section was read and informed subsequent actions.

#### 1.2 Installation

```
⏺ Bash(python3 -m venv .venv && source .venv/bin/activate && pip install
      --upgrade pip && pip install qmatsuite)
  ⎿  Requirement already satisfied: pip in ./.venv/lib/python3.12/site-packages (25.0.1)
     Collecting pip
     … +424 lines
  ⎿  (timeout 5m)
```

**Result:** ✅ qmatsuite 1.2.2 installed successfully with all dependencies.

#### 1.3 MCP Configuration

```
⏺ Bash(source /Users/<user>/qms-blindtest/.venv/bin/activate && qms mcp config --write)
  ⎿  Written to /Users/<user>/qms-blindtest/.mcp.json
```

**Observation:** Agent discovered `qms mcp config --write` from the README and used it correctly. Generated config:

```json
{
  "mcpServers": {
    "qmatsuite": {
      "command": "/Users/<user>/qms-blindtest/.venv/bin/python3",
      "args": ["-m", "qmatsuite.mcp.server"],
      "type": "stdio"
    }
  }
}
```

**Result:** ✅ Correct absolute path, correct format.

#### 1.4 Engine Detection & Installation

Agent checked for QE availability:

```
⏺ Bash(source /Users/<user>/qms-blindtest/.venv/bin/activate && qms detect-qe)
  ⎿  Error: Exit code 1
     [QE_STATE] source=none qe_bin_dir=None mode=None error='No internal QE
     found under .qmatsuite/engines/qe/**/bin'
```

Agent then explored CLI help to find the engine install command:

```
⏺ Bash(… && qms --help)
  ⎿   Usage: qms [OPTIONS] COMMAND [ARGS]...
     … +37 lines

⏺ Bash(… && qms engine --help)
  ⎿   Usage: qms engine [OPTIONS] COMMAND [ARGS]...
     … +18 lines

⏺ Bash(… && qms engine install --help)
  ⎿   Usage: qms engine install [OPTIONS] ENGINE_FAMILY
     … +18 lines
```

Agent installed QE:

```
⏺ Bash(… && qms engine install qe)
  ⎿  No checksum available for qe-7.5-macos-arm64-openmp.zip — skipping verification
     Installed qe (github_release): github-7.5-openmp
     … +2 lines
  ⎿  (timeout 10m)
```

Verification:

```
⏺ Bash(… && qms detect-qe)
  ⎿  Quantum ESPRESSO detection summary
     ----------------------------------------
     Environment QE_HOME  : not set
     … +19 lines
```

**Result:** ✅ QE 7.5 installed via GitHub release. pw.x, ph.x, dos.x, bands.x all detected.
**Note:** ⚠️ Checksum verification was skipped — "No checksum available for qe-7.5-macos-arm64-openmp.zip".

#### 1.5 Project Initialization

```
⏺ Bash(… && qms init si_scf_project)
  ⎿  Error: Exit code 2
     No such command 'si_scf_project'. Did you mean 'project'?

⏺ Bash(… && qms init project --help)
  ⎿   Usage: qms init project [OPTIONS]
     … +22 lines

⏺ Bash(… && qms init project --name "Silicon SCF" --path ./si_scf)
  ⎿  Project created at /Users/<user>/qms-blindtest/si_scf/silicon-scf
```

**Result:** ✅ Project created after one syntax error (agent self-corrected).
**Observation:** Project was created at `~/qms-blindtest/si_scf/silicon-scf/` — a nested path. This becomes relevant later.

#### 1.6 Structure Creation

Agent generated a silicon CIF using pymatgen (available as a qmatsuite dependency):

```
⏺ Bash(… && python3 -c "
    from pymatgen.core import Structure, Lattice…)
  ⎿  Silicon CIF written

⏺ Bash(… && cd /Users/<user>/qms-blindtest/si_scf/silicon-scf &&
      qms import-structure si_diamond.cif --id si_bulk)
  ⎿  Imported structure 'si_bulk' -> structures/si_bulk.json
```

**Result:** ✅ Structure imported via pymatgen → CIF → qms import.

#### 1.7 Calculation Attempts (CLI Bugs Encountered)

**Attempt 1: `qms run structure`**

```
⏺ Bash(… && qms run structure si_bulk --type scf
      --SYSTEM.ecutwfc=30 --SYSTEM.ecutrho=240 --k_points="automatic:4,4…)
  ⎿  Error: Exit code 1
     Traceback:
     qmatsuite/cli/main.py:2179 in run_structure_command
     ❱ 2179 │   qe_input = svc.generate_qe_input_from_structure(
```

**Bug 1:** `generate_qe_input_from_structure` method missing or has wrong signature on QMSService.

**Attempt 2: `qms run step --standalone`**

```
⏺ Bash(… && qms run step --standalone --input si_scf.in -v)
  ⎿  Error: Exit code 2
     Invalid value: Positional argument (target) cannot be used with --standalone.

⏺ Bash(… && qms run step --standalone --input si_scf.in)
  ⎿  Error: Exit code 1
     Traceback: …wrong keyword arg in build_step_spec_from_qe_input
```

**Bug 2:** `qms run step --standalone` has argument parsing issues and a keyword argument error in `build_step_spec_from_qe_input`.

#### 1.8 Direct pw.x Execution (Workaround)

Agent fell back to calling pw.x directly:

```
⏺ Write(si_scf.in)
  ⎿  Wrote 30 lines to si_scf.in
       1 &CONTROL
       2     calculation = 'scf'
       3     prefix      = 'silicon'
       4     outdir      = './tmp'
       5     pseudo_dir  = './pseudo'
       6 /
       7
       8 &SYSTEM
       9     ibrav       = 2
      10     celldm(1)   = 10.2612
      …
```

Agent manually downloaded the pseudopotential:

```
⏺ Bash(… && curl -sL -o pseudo/Si.pbe-n-kjpaw_psl.1.0.0.UPF
      "https://pseudopotentials.quantum-espresso.org/upf_file…)
  ⎿  total 3312
```

Ran pw.x directly:

```
⏺ Bash(~/.qmatsuite/engines/qe/github-7.5-openmp/bin/pw.x < si_scf.in 2>&1)
  ⎿       Program PWSCF v.7.5 starts on 26Feb2026 at 10: 6:48
     … +159 lines
  ⎿  (timeout 5m)
```

**Result:** ✅ SCF converged.

#### 1.9 Analysis

```
⏺ Bash(… && qms analyze scf tmp/silicon.save/)
  ⎿  Error: Exit code 2
     Invalid value: Expected file path, got directory
```

**Bug 3:** `qms analyze scf` rejects directory paths, only accepts file paths.

Agent re-ran with output capture:

```
⏺ Bash(… && pw.x < si_scf.in > si_scf.out 2>&1 && qms analyze scf si_scf.out)
  ⎿  {
       "converged": true,
       "iterations": [
     … +34 lines
```

**Result:** ✅ Analysis succeeded on file output.

#### 1.10 Final Results (Test 1)

| Property | Value |
|----------|-------|
| Converged | Yes (8 iterations) |
| Total energy | -93.4392 Ry (-1160.13 Ry all-electron) |
| Highest occupied level | 6.2505 eV |
| ecutwfc / ecutrho | 30 / 240 Ry |
| k-points | 4×4×4 Monkhorst-Pack (8 irreducible) |
| Wall time | 2.39 s |

**Total time:** ~4 min 22 s (including installation, engine download, calculation).

### Test 1 Summary

| Step | Status | Notes |
|------|--------|-------|
| pip install | ✅ | Clean install, all deps resolved |
| `qms mcp config --write` | ✅ | Agent found command via README |
| QE install via `qms engine install qe` | ✅ | GitHub release, checksum skipped |
| `qms run structure` | ❌ Bug | Missing method on QMSService |
| `qms run step --standalone` | ❌ Bug | Argument parsing + keyword arg error |
| Direct pw.x execution | ✅ | Agent workaround |
| `qms analyze scf` on directory | ❌ Bug | Rejects directory, needs file path |
| `qms analyze scf` on file | ✅ | Correct JSON output |

---

## MCP Activation (Between Tests)

After Test 1 completed, Claude Code displayed a grey auto-suggestion:

```
Restart Claude Code to activate the MCP server
```

User pressed Tab to accept, agent responded:

```
Please /exit and restart Claude Code in this directory to activate
the qmatsuite MCP server.
```

User ran `/exit`, then restarted `claude` in the same directory. On restart, MCP server was detected and connected.

---

## Test 2: MCP-Driven DOS Calculation

**Prompt:**
```
now calculate silicon DOS and analyze
```

**Objective:** Validate MCP-driven calculation workflow — structure import, multi-step workflow (SCF→NSCF→DOS), analysis with plotting.

### Trace

#### 2.1 Parallel Discovery (4 concurrent MCP calls)

Agent immediately issued 4 parallel MCP tool calls:

```
⏺ qmatsuite - init_project (MCP)
  ⎿  {"status": "success", "data": { … +8 lines }}

⏺ qmatsuite - list_structures (MCP)
  ⎿  {"status": "success", "data": { … +7 lines }}

⏺ qmatsuite - list_engines (MCP)(installed_only: true)
  ⎿  {"status": "success", "data": { … +38 lines }}

⏺ qmatsuite - list_workflows (MCP)(engine: "qe")
  ⎿  {"status": "success", "data": { … +36 lines }}
```

**Observation:** Agent parallelized 4 discovery calls in one turn. `init_project` created project at `~/qms-blindtest/` (the CWD), different from Test 1's nested `si_scf/silicon-scf/` path.

#### 2.2 Structure Import

First attempt with CIF format failed:

```
⏺ qmatsuite - import_structure (MCP)(
    file_content: "data_Si\n_symmetry_space_group_name_H-M 'F d -3 m'\n
      _cell_length_a 5.431\n_cell_length_b 5.431\n_cell_length_c 5.431\n
      _cell_angle_alpha 90.0\n_cell_angle_beta 90.0\n_cell_angle_gamma 90.0\n\n
      loop_\n_atom_site_label\n_atom_site_type_symbol\n
      _atom_site_fract_x\n_atom_site_fract_y\n_atom_site_fract_z\n
      Si1 Si 0.0 0.0 0.0\nSi2 Si 0.25 0.25 0.25\n",
    format: "cif",
    name: "Si-diamond")
  ⎿  {"status": "error", "error_type": "import_failed", … +9 lines}
```

**Bug 4:** CIF inline content import fails. The CIF content appears syntactically correct but was rejected by the parser.

Agent recovered by switching to POSCAR format:

```
⏺ qmatsuite - import_structure (MCP)(
    file_content: "Si diamond\n5.431\n1.0 0.0 0.0\n0.0 1.0 0.0\n
      0.0 0.0 1.0\nSi\n2\ndirect\n0.0 0.0 0.0\n0.25 0.25 0.25\n",
    format: "poscar",
    name: "Si-diamond")
  ⎿  {"status": "success", "data": { … +22 lines }}
```

**Result:** ✅ Structure imported via POSCAR format.

#### 2.3 Calculation Creation & Preset Application

```
⏺ qmatsuite - create_calculation (MCP)(
    engine: "qe", workflow: "dos",
    structure_selector: "Si-diamond", name: "Si-DOS")
  ⎿  {"status": "success", "data": { … +29 lines }}
```

**Observation:** Species map was auto-resolved (SSSP pseudopotentials were available from the earlier download or bundled demo pseudos).

```
⏺ qmatsuite - apply_preset (MCP)(
    calc_ulid: "01KJD7ZC324Q2DWTTJ4GWRTN3M",
    presets: {
      "magnetism": "NM",
      "precision": "MED",
      "occupations_scheme": "TETRAHEDRA",
      "convergence": "NORMAL"
    })
  ⎿  {"status": "success", "data": { … +31 lines }}
```

**Observation:** Agent chose `TETRAHEDRA` occupation scheme for DOS — physically correct choice for semiconductor DOS calculation.

#### 2.4 Dry Run Inspection

```
⏺ qmatsuite - inspect_calculation (MCP)(
    calc_ulid: "01KJD7ZC324Q2DWTTJ4GWRTN3M",
    step: 0, dry_run: true)
  ⎿  {"status": "success", "data": { … +43 lines }}
```

Agent verified: ecutwfc=50 Ry, 6×6×6 k-mesh, tetrahedra occupations.

**Observation:** Agent used `inspect_calculation(dry_run=True)` before running — this is exactly the safe workflow the design intended.

#### 2.5 Execution

```
⏺ qmatsuite - run_calculation (MCP)(
    calc_ulid: "01KJD7ZC324Q2DWTTJ4GWRTN3M")
  ⎿  {"status": "success", "data": { … +27 lines }}
```

**Result:** ✅ All 3 steps completed: SCF → NSCF → DOS.

#### 2.6 Results & Analysis

```
⏺ qmatsuite - get_results_summary (MCP)(
    calc_ulid: "01KJD7ZC324Q2DWTTJ4GWRTN3M", step: 0)
  ⎿  {"status": "success", "data": { … +15 lines }}

⏺ qmatsuite - list_analyses (MCP)(
    calc_ulid: "01KJD7ZC324Q2DWTTJ4GWRTN3M", step: 2)
  ⎿  {"status": "success", "data": { … +17 lines }}

⏺ qmatsuite - plot_analysis (MCP)(
    calc_ulid: "01KJD7ZC324Q2DWTTJ4GWRTN3M",
    object_type: "dos", step: 2)
  ⎿  {"status": "success", "data": { … +32 lines }}

⏺ qmatsuite - plot_analysis (MCP)(
    calc_ulid: "01KJD7ZC324Q2DWTTJ4GWRTN3M",
    object_type: "convergence", step: 0)
  ⎿  {"status": "success", "data": { … +34 lines }}
```

**Result:** ✅ DOS plot and convergence plot both generated (ASCII + PNG).

#### 2.7 Agent's Physical Analysis

The agent provided scientifically sound analysis of the results:

> **DOS Analysis:**
> 1. **Valence band** (below E_F ~ -2.25 eV): Sharp peak at ~-6.5 eV — bottom of valence band (s-like bonding states). Cluster of peaks from -3 to -1 eV — upper valence band (p-like bonding states). Van Hove singularities visible as sharp features (expected with tetrahedra method).
> 2. **Band gap:** Clear zero-DOS region between ~-0.5 eV and ~0.5 eV, giving an indirect gap of ~0.6 eV. Consistent with the well-known DFT-PBE underestimate of silicon's experimental gap (1.12 eV).
> 3. **Conduction band** (above the gap): Multiple peaks from 0.5 to 4 eV corresponding to antibonding states.

#### 2.8 Final Results (Test 2)

| Property | Value |
|----------|-------|
| Converged | Yes (9 iterations) |
| Total energy | -305.269 eV (-22.437 Ry) |
| Fermi energy | -2.248 eV |
| ecutwfc | 50 Ry |
| k-mesh | 6×6×6 Monkhorst-Pack |
| Occupation scheme | Tetrahedra |
| Wall time | ~16 s |
| Band gap (DFT-PBE) | ~0.6 eV (experimental: 1.12 eV) |

**Total time:** 2 min 21 s (MCP tool calls only, no installation).

### Test 2 MCP Tool Call Sequence

| # | Tool | Purpose | Result |
|---|------|---------|--------|
| 1 | `init_project` | Initialize project at CWD | ✅ |
| 2 | `list_structures` | Check existing structures | ✅ (empty) |
| 3 | `list_engines(installed_only=True)` | Verify QE available | ✅ |
| 4 | `list_workflows(engine="qe")` | Discover DOS workflow | ✅ |
| 5 | `import_structure` (CIF) | Import Si structure | ❌ CIF parse failure |
| 6 | `get_presets(engine="qe", workflow="dos")` | Get preset options | ✅ |
| 7 | `import_structure` (POSCAR) | Import Si structure (retry) | ✅ |
| 8 | `create_calculation` | Create DOS calc with 3 steps | ✅ |
| 9 | `apply_preset` | Set precision/method | ✅ |
| 10 | `inspect_calculation(dry_run=True)` | Verify config before running | ✅ |
| 11 | `run_calculation` | Execute SCF→NSCF→DOS | ✅ |
| 12 | `get_results_summary` | Get SCF energy/convergence | ✅ |
| 13 | `list_analyses` | Discover available plots | ✅ |
| 14 | `plot_analysis(dos)` | Generate DOS plot | ✅ |
| 15 | `plot_analysis(convergence)` | Generate convergence plot | ✅ |

**Tool calls:** 15 total (1 failure + recovery, 14 successful)
**Parallelism:** Calls 1-4 were issued in parallel. Calls 5-6 were issued in parallel.

---

## Bugs Discovered

| # | Component | Description | Severity | Affects MCP? |
|---|-----------|-------------|----------|-------------|
| 1 | CLI | `qms run structure` — `generate_qe_input_from_structure` missing/broken on QMSService | Medium | No |
| 2 | CLI | `qms run step --standalone` — argument parsing conflict + keyword arg error in `build_step_spec_from_qe_input` | Medium | No |
| 3 | CLI | `qms analyze scf` rejects directory path, only accepts file path | Low | No |
| 4 | MCP | `import_structure` with inline CIF content fails to parse | Medium | **Yes** |
| 5 | Engine | QE GitHub release has no checksum — "No checksum available for qe-7.5-macos-arm64-openmp.zip" | Low | Indirect |

## Key Observations

### Agent Behavior: CLI vs MCP

| Dimension | CLI Mode (Test 1) | MCP Mode (Test 2) |
|-----------|-------------------|-------------------|
| Tool calls | ~15 shell commands | 15 MCP calls |
| Errors encountered | 4 (3 bugs + 1 syntax) | 1 (CIF import) |
| Self-recovery | Yes (fell back to raw pw.x) | Yes (CIF → POSCAR) |
| Parallelism | None (sequential shell) | Yes (4 parallel discovery calls) |
| Manual workarounds | Downloaded pseudo manually, wrote input file, called pw.x directly | None needed |
| Physical insight | Basic (reported numbers) | Detailed (DOS analysis, gap interpretation, methodology notes) |
| Time | 4 min 22 s | 2 min 21 s |
| Used `dry_run` preview | No | Yes |

### MCP Design Validation

The MCP tool call sequence in Test 2 matches the intended design from `AGENT_INTEGRATION_DESIGN.md`:

1. **Discovery phase:** `list_engines` + `list_workflows` + `get_presets` — agent learns what's available
2. **Configuration phase:** `create_calculation` + `apply_preset` — agent sets up the calculation
3. **Preview phase:** `inspect_calculation(dry_run=True)` — agent verifies before executing
4. **Execution phase:** `run_calculation` — single blocking call runs all steps
5. **Analysis phase:** `get_results_summary` + `plot_analysis` — agent retrieves and interprets results

The `context_hint` system appears to have guided the agent through this sequence naturally.

### Project Nesting Edge Case

Test 1 created a project at `~/qms-blindtest/si_scf/silicon-scf/`.
Test 2 created a project at `~/qms-blindtest/` (CWD).

This means `~/qms-blindtest/` now contains:
- A MCP-managed project (with its own `calculation.yaml` and `calculations/`)
- A nested CLI-created project at `si_scf/silicon-scf/` (with its own `calculation.yaml`)

This is a potential issue for `find_project_root()` walk-up logic. If a user `cd`s into `si_scf/` (the middle directory), the walk-up would find `~/qms-blindtest/` which may not be the intended project. ULIDs prevent calculation ID conflicts, but slug-based references could theoretically collide.

**Status:** Noted for investigation. Not blocking.

### Engine Persistence Validation

QE was installed in Test 1 via CLI (`qms engine install qe`) and stored at `~/.qmatsuite/engines/qe/github-7.5-openmp/`. In Test 2 (after restart), `list_engines(installed_only=True)` correctly detected the QE installation. This confirms that:

- Engine storage at `~/.qmatsuite/` persists across sessions
- The MCP server reads from the same `engines.json` registry as the CLI
- No re-installation was needed after restart

---

## Conclusion

**MCP path: Production-ready.** The agent completed a 3-step DOS workflow (SCF→NSCF→DOS) with analysis and plotting in 2 min 21 s, with correct physical methodology choices and a single recoverable error.

**CLI path: Multiple bugs.** Three CLI commands have issues that prevent direct use for calculations. These do not affect MCP users but would impact CLI-only workflows.

**Bootstrap path: Works.** `pip install qmatsuite` → `qms mcp config --write` → restart → MCP available. Agent discovered this flow autonomously from the README.
