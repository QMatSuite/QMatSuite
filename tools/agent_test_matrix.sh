#!/bin/bash
# QMatSuite MCP Agent Test Matrix
#
# Spawns 9 Claude Code CLI agents against QMatSuite MCP, each performing a
# different materials science calculation.  Agents receive ONLY a simple
# task prompt and .mcp.json — no preconditioning about resources, paths,
# or tool usage.  The MCP server instructions in .mcp.json are the sole
# guide.
#
# Phases:
#   0  Walk-up guard + wipe pseudo libraries + seed cache
#   1  Agent 0 (Na BCC SCF, sequential) — forces cold SSSP download
#   2  Agents 1-8 in parallel
#   3  Summary with pass/fail gates
#
# Every run creates a unique directory under <repo>/.tmp/agent_mcp_test/.
# Never overwrites previous runs.
#
# Usage: bash tools/agent_test_matrix.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"

# ---- Paths (from src/quantumvitas/core/paths.py) ----

PSEUDO_LIB="$REPO_ROOT/.qmatsuite/libraries/pseudo"
SEED_DIR="$REPO_ROOT/.qmatsuite/seeds/pseudo"
SSSP_LIB="$PSEUDO_LIB/SSSP"

# ---- Prerequisites ----

[[ -f "$VENV_PYTHON" ]] || { echo "ABORT: .venv/bin/python not found" >&2; exit 1; }
command -v claude &>/dev/null || { echo "ABORT: 'claude' CLI not in PATH" >&2; exit 1; }

# ---- Gate: no project.qv.yml in walk-up path from .tmp to / ----
#
# If a project.qv.yml exists anywhere above the task directories, the MCP
# server's init_project() will attach to it instead of creating a fresh
# project.  Abort early if found.

_walk="$REPO_ROOT/.tmp"
while [[ "$_walk" != "/" && "$_walk" != "." ]]; do
    if [[ -f "$_walk/project.qv.yml" ]]; then
        echo "ABORT: project.qv.yml found at $_walk" >&2
        echo "  Agents will attach to this project instead of creating fresh ones." >&2
        echo "  Fix: rm $_walk/project.qv.yml" >&2
        exit 1
    fi
    _walk="$(dirname "$_walk")"
done
if [[ -f "/project.qv.yml" ]]; then
    echo "ABORT: project.qv.yml found at /" >&2; exit 1
fi
# Also check inside .tmp/agent_mcp_test/ at intermediate levels (stale from old runs)
if [[ -d "$REPO_ROOT/.tmp/agent_mcp_test" ]]; then
    _stale="$(find "$REPO_ROOT/.tmp/agent_mcp_test" -maxdepth 2 -name project.qv.yml \
              ! -path "*/task_*/project.qv.yml" 2>/dev/null || true)"
    if [[ -n "$_stale" ]]; then
        echo "ABORT: stale project.qv.yml in .tmp/agent_mcp_test/ (not inside a task dir):" >&2
        echo "$_stale" >&2
        exit 1
    fi
fi
unset _walk _stale
echo "GATE PASS: no project.qv.yml in walk-up path"

# ---- Run directory ----

RUN_ID="run_$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$REPO_ROOT/.tmp/agent_mcp_test/$RUN_ID"
TRACES_DIR="$RUN_DIR/traces"
mkdir -p "$TRACES_DIR"

echo ""
echo "=========================================="
echo "  QMatSuite MCP Agent Test Matrix"
echo "  Run ID : $RUN_ID"
echo "  Run Dir: $RUN_DIR"
echo "=========================================="

# ============================================================
# PHASE 0: Wipe pseudo libraries + seed cache
# ============================================================

echo ""
echo "=== Phase 0: Wipe pseudo libraries and seed cache ==="
echo "  Deleting: $PSEUDO_LIB"
echo "  Deleting: $SEED_DIR"

rm -rf "$PSEUDO_LIB"
rm -rf "$SEED_DIR"

# Assert deletion succeeded
if [[ -d "$PSEUDO_LIB" ]]; then
    echo "GATE FAIL: $PSEUDO_LIB still exists after deletion" >&2
    exit 1
fi
if [[ -d "$SEED_DIR" ]]; then
    echo "GATE FAIL: $SEED_DIR still exists after deletion" >&2
    exit 1
fi
echo "GATE PASS: pseudo libraries and seed cache wiped"

# ============================================================
# Helpers
# ============================================================

# Create task dir with .mcp.json (absolute python path, instructions from example)
setup_task() {
    local task_dir="$1"
    mkdir -p "$task_dir"
    "$VENV_PYTHON" - "$task_dir" "$REPO_ROOT" <<'PYEOF'
import json, pathlib, sys
task_dir = pathlib.Path(sys.argv[1])
repo_root = pathlib.Path(sys.argv[2])
config = json.loads((repo_root / ".mcp.json.example").read_text())
config["mcpServers"]["qmatsuite"]["command"] = str(repo_root / ".venv" / "bin" / "python")
task_dir.joinpath(".mcp.json").write_text(json.dumps(config, indent=2))
PYEOF
}

# Run one agent.  Prompt is the ONLY input — no preconditioning.
run_agent() {
    local tnum="$1"
    local task_dir="$2"
    local task_prompt="$3"
    local trace_file="$TRACES_DIR/task_${tnum}.log"

    echo "[task_${tnum}] Starting — $(basename "$task_dir")"
    (
        cd "$task_dir"
        unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true
        claude -p \
            --dangerously-skip-permissions \
            --output-format stream-json --verbose \
            "$task_prompt"
    ) > "$trace_file" 2>&1 || true

    local lines
    lines="$(wc -l < "$trace_file" 2>/dev/null || echo 0)"
    echo "[task_${tnum}] Done (trace: ${lines// /} lines)"
}

# ============================================================
# PHASE 1: Agent 0 — Na BCC SCF (sequential, cold SSSP download smoke test)
# ============================================================
#
# Na BCC is the fastest possible smoke test: 1 valence electron, BCC
# structure, small basis (ecutwfc ~30 Ry), converges in ~5 SCF iterations.
# Na is NOT in the bundled internal pseudo resources, so the agent MUST
# call download_pseudo_library (cold SSSP download) before it can run.

echo ""
echo "=== Phase 1: Agent 0 — Na BCC SCF (cold SSSP smoke test) ==="

T0_DIR="$RUN_DIR/task_00_na_scf"
setup_task "$T0_DIR"
run_agent "00" "$T0_DIR" \
    "Calculate the total energy of BCC sodium using Quantum ESPRESSO."

# Gate: SSSP must now be downloaded
if [[ ! -d "$SSSP_LIB" ]]; then
    echo "GATE FAIL: SSSP library not found at $SSSP_LIB after agent 0" >&2
    echo "  Agent must download SSSP to run QE calculations." >&2
    echo "  Check: $TRACES_DIR/task_00.log" >&2
    exit 1
fi
echo "GATE PASS: SSSP library present at $SSSP_LIB"

# Gate: agent 0 must have created a project
if [[ ! -f "$T0_DIR/project.qv.yml" ]]; then
    echo "GATE FAIL: agent 0 (na_scf) did not create project.qv.yml in $T0_DIR" >&2
    echo "  Check: $TRACES_DIR/task_00.log" >&2
    exit 1
fi
echo "GATE PASS: agent 0 created project"

# ============================================================
# PHASE 2: Agents 1-9 (parallel)
# ============================================================

echo ""
echo "=== Phase 2: Agents 1-16 (parallel) ==="

_launch() {
    local tnum="$1" tname="$2" tprompt="$3"
    local task_dir="$RUN_DIR/$tname"
    setup_task "$task_dir"
    run_agent "$tnum" "$task_dir" "$tprompt" &
}

_launch "01" "task_01_si_scf" \
    "Calculate the total energy of bulk silicon using Quantum ESPRESSO."

_launch "02" "task_02_si_bands" \
    "Calculate the electronic band structure of silicon using Quantum ESPRESSO."

_launch "03" "task_03_si_dos" \
    "Calculate the density of states of silicon using Quantum ESPRESSO."

_launch "04" "task_04_si_relax_bands" \
    "Relax the silicon crystal structure using Quantum ESPRESSO, then calculate its band structure on the relaxed geometry."

_launch "05" "task_05_al_scf" \
    "Calculate the total energy of FCC aluminum using Quantum ESPRESSO."

_launch "06" "task_06_fe_magnetic" \
    "Calculate the magnetic moment of BCC iron using Quantum ESPRESSO."

_launch "07" "task_07_bad_config" \
    "Calculate the total energy of silicon using Quantum ESPRESSO with ecutwfc = 5 Ry and fixed occupations."

_launch "08" "task_08_water_xtb" \
    "Optimize the geometry of a water molecule using xTB."

# New tasks (09-16) — Round 3 expansion

_launch "09" "task_09_fe_magnetization_check" \
    "Calculate the magnetic moment of BCC iron using Quantum ESPRESSO. After the calculation completes, call get_results_summary and confirm that total_magnetization is present in the response."

_launch "10" "task_10_xtb_promote" \
    "Optimize the geometry of a water molecule using xTB, then call promote_structure to register the optimized geometry as a new structure in the project. Finally call get_results_summary to verify the energy is reported."

_launch "11" "task_11_si_vc_relax" \
    "Relax the silicon crystal structure AND optimize the unit cell using Quantum ESPRESSO by setting CONTROL.calculation='vc-relax' in the parameters. After the relax completes, call promote_structure to extract the relaxed geometry."

_launch "12" "task_12_orca_water" \
    "Calculate the total energy of a water molecule using ORCA with the HF/STO-3G method. If ORCA is not available, report the error diagnostics returned by the MCP tool."

_launch "13" "task_13_failing_scf" \
    "Calculate the total energy of silicon using Quantum ESPRESSO, but intentionally set ecutwfc=1.0 Ry and electron_maxstep=2. This will fail or produce wrong results — report what error diagnostics the system returns."

_launch "14" "task_14_al_dos" \
    "Calculate the density of states of FCC aluminum using Quantum ESPRESSO. Do NOT use a pre-built demo — build the calculation from scratch."

_launch "15" "task_15_mg_hcp_scf" \
    "Calculate the total energy of HCP magnesium using Quantum ESPRESSO. Magnesium has a hexagonal close-packed structure (space group P6_3/mmc, a=3.21 Angstrom, c=5.21 Angstrom, 2 atoms in the unit cell)."

_launch "16" "task_16_si_convergence" \
    "Perform a plane-wave cutoff convergence study for silicon using Quantum ESPRESSO: run two separate SCF calculations with ecutwfc=20 Ry and ecutwfc=40 Ry. Compare the total energies from get_results_summary for each and report the energy difference to assess convergence."

wait
echo "  All parallel agents complete."

# ============================================================
# PHASE 3: Summary and gates
# ============================================================

echo ""
echo "=== Phase 3: Summary ==="

PASS=0
FAIL=0

ALL_TASKS=(
    "00:task_00_na_scf"
    "01:task_01_si_scf"
    "02:task_02_si_bands"
    "03:task_03_si_dos"
    "04:task_04_si_relax_bands"
    "05:task_05_al_scf"
    "06:task_06_fe_magnetic"
    "07:task_07_bad_config"
    "08:task_08_water_xtb"
    "09:task_09_fe_magnetization_check"
    "10:task_10_xtb_promote"
    "11:task_11_si_vc_relax"
    "12:task_12_orca_water"
    "13:task_13_failing_scf"
    "14:task_14_al_dos"
    "15:task_15_mg_hcp_scf"
    "16:task_16_si_convergence"
)

_check() {
    local tnum="$1" tname="$2"
    local tdir="$RUN_DIR/$tname"
    local wlog proj lines status

    wlog="$(test -f "$tdir/WORKLOG.md" && echo "✓" || echo "✗")"
    proj="$(test -f "$tdir/project.qv.yml" && echo "✓" || echo "✗")"
    lines="$(wc -l < "$TRACES_DIR/task_${tnum}.log" 2>/dev/null || echo 0)"
    lines="${lines// /}"

    if [[ "$proj" == "✓" ]]; then
        status="PASS"; ((PASS++)) || true
    else
        status="FAIL"; ((FAIL++)) || true
    fi

    printf "[%s] Task %s  %-26s  WORKLOG=%s  PROJECT=%s  TRACE=%s lines\n" \
        "$status" "$tnum" "$tname" "$wlog" "$proj" "$lines"
}

SUMMARY_FILE="$RUN_DIR/SUMMARY.txt"
{
echo "=== Agent Test Matrix Results ==="
echo "Run ID:  $RUN_ID"
echo "Run Dir: $RUN_DIR"
echo "Date:    $(date)"
echo ""

for entry in "${ALL_TASKS[@]}"; do
    _check "${entry%%:*}" "${entry#*:}"
done

echo ""
echo "SSSP downloaded: $(test -d "$SSSP_LIB" && echo "✓" || echo "✗")"

wcount=0
pcount=$PASS
for entry in "${ALL_TASKS[@]}"; do
    tname="${entry#*:}"
    test -f "$RUN_DIR/$tname/WORKLOG.md" && ((wcount++)) || true
done

echo "Tasks with worklog: $wcount/17"
echo "Tasks with project: $pcount/17"
echo ""
if [[ $FAIL -gt 0 ]]; then
    echo "OVERALL: FAIL ($FAIL task(s) without project)"
else
    echo "OVERALL: PASS (all 17 tasks created projects)"
fi
} | tee "$SUMMARY_FILE"

echo ""
echo "All artifacts staged at: $RUN_DIR"
echo "Summary: $SUMMARY_FILE"

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
