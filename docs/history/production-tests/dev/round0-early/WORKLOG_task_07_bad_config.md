# Task 07 — Bad Config: Si SCF with ecutwfc=5 Ry and fixed occupations

## Task Description
Calculate the total energy of silicon using Quantum ESPRESSO.
- ecutwfc = 5 Ry (intentionally very low — "bad config")
- occupations = fixed

## Tool Calls Log

### Step 1: Ping MCP server
- **Tool**: `ping`
- **Result**: success, version 0.1.0

### Step 2: Init project
- **Tool**: `init_project(name="task_07_bad_config")`
- **Result**: Existing project loaded at `<REPO_ROOT>`

### Step 3: List structures
- **Tool**: `list_structures()`
- **Result**: Found 1 structure: `si.scf` (Si2, Fd-3m, ULID=01KJ0C2YER3RDHRJZWFQ5H4K9N)

### Step 4: Create calculation
- **Tool**: `create_calculation(engine="qe", workflow="scf", structure_selector="01KJ0C2YER3RDHRJZWFQ5H4K9N", name="si_scf_bad_config")`
- **Note**: First attempt with name `si.scf` failed ("structure not found"), used ULID instead — success
- **Result**: calc_ulid=`01KJ0C8VCG9PAC73F1XV5NMG4R`, step_ulid=`01KJ0C8VD1AZ0K7Z776YTAGDKR`, species map auto-resolved

### Step 5: Set parameters
- **Tool**: `set_parameters(calc_ulid="01KJ0C8VCG9PAC73F1XV5NMG4R", params={"SYSTEM": {"ecutwfc": 5, "occupations": "fixed"}}, step=0)`
- **Result**: Success, parameters set

### Step 6: Dry-run / preflight inspect
- **Tool**: `inspect_calculation(..., dry_run=True)`
- **Preflight issues**: `LOW_ECUTWFC` advisory — "ecutwfc=5 Ry is very low for production calculations. Most pseudopotentials need at least 30-40 Ry."
- **Observation**: Input file also retains `smearing = 'gaussian'` and `degauss = 0.01` from defaults even with `occupations = 'fixed'` set — inconsistency but QE may handle gracefully
- **Input file looks correct**: ecutwfc=5, occupations='fixed', K_POINTS automatic 8x8x8, Si pseudopotential resolved

### Decision: Proceed with run despite bad config
The task explicitly requests ecutwfc=5 Ry (bad config). Preflight flagged it as advisory-only. Running to observe outcome.

### Step 7: Run calculation
- **Tool**: `run_calculation(calc_ulid="01KJ0C8VCG9PAC73F1XV5NMG4R")`
- **Result**: ERROR — `execution_failed`
- **Error message**: "Project root cannot be the repository root. Provided project_root=<REPO_ROOT> is the repo root, which is invalid."
- **Root cause**: `init_project` loaded the existing `project.qv.yml` at `<REPO_ROOT>` (the git repo root). QMatSuite disallows running calculations when the project root IS the git repo root.

### Step 8: Check status
- **Tool**: `get_status(calc_ulid="01KJ0C8VCG9PAC73F1XV5NMG4R")`
- **Result**: overall_status="not_run" (step 0 status="not_run") — confirms no execution occurred

---

## Final Outcome

**Calculation**: Si SCF with ecutwfc=5 Ry and fixed occupations
**Status**: FAILED TO RUN due to system-level misconfiguration

### Two layers of "bad config" encountered:

1. **Physics-level bad config** (ecutwfc=5 Ry):
   - Preflight correctly flagged: `LOW_ECUTWFC` advisory
   - "ecutwfc=5 Ry is very low for production calculations. Most pseudopotentials need at least 30-40 Ry."
   - This is recoverable — would produce physically inaccurate results if run
   - **Total energy**: NOT obtained (run blocked before execution)

2. **System-level bad config** (project root = git repo root):
   - `init_project` resolved to `<REPO_ROOT>` (the git repo root)
   - QMatSuite enforces: project root MUST NOT be the git repo root
   - `run_calculation` raised `execution_failed` with: "Project root cannot be the repository root"
   - **This is a hard blocker** — cannot be worked around via MCP tools alone

### What was successfully configured:
- Structure: Si2 (Fd-3m) imported and available
- Calculation created: `si_scf_bad_config` (calc_ulid=`01KJ0C8VCG9PAC73F1XV5NMG4R`)
- Parameters set: `ecutwfc=5`, `occupations='fixed'`
- Species map: auto-resolved (Si pseudopotential found)
- Input file materialized correctly:
  ```
  &SYSTEM
      ecutwfc = 5,
      occupations = 'fixed',
      nat = 2, ntyp = 1,
      smearing = 'gaussian', degauss = 0.01,  ← leftover default, harmless with fixed occ
  /
  ```

### Resolution (if attempted again):
- Set `QMATSUITE_PROJECT` environment variable to a non-repo-root directory (e.g., the task directory itself)
- Or initialize a fresh project in a subdirectory outside the git repo root



