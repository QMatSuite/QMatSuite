#!/bin/bash
# QMatSuite MCP Agent Test Matrix
#
# Spawns 9 Claude Code CLI agents against QMatSuite MCP, each performing a
# different materials science calculation. Every run creates a unique directory.
# Task dirs live in /tmp (outside the repo) so init_project() creates fresh
# per-task projects instead of finding the repo's project.qv.yml.
#
# Usage: bash tools/agent_test_matrix.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"

# ---- Prerequisites ----

[[ -f "$VENV_PYTHON" ]] || { echo "ERROR: .venv/bin/python not found" >&2; exit 1; }
command -v claude &>/dev/null || { echo "ERROR: 'claude' not in PATH" >&2; exit 1; }

# ---- Run directory (in /tmp for project isolation) ----

RUN_ID="run_$(date +%Y%m%d_%H%M%S)"
RUN_DIR="/tmp/qmatsuite_tests/$RUN_ID"
TRACES_DIR="$RUN_DIR/traces"
mkdir -p "$TRACES_DIR"

echo "=========================================="
echo "  QMatSuite MCP Agent Test Matrix"
echo "  Run ID: $RUN_ID"
echo "  Dir:    $RUN_DIR"
echo "=========================================="

# ---- Clean SSSP (force fresh download in Task 0) ----
# Paths from src/quantumvitas/core/paths.py:
#   .qmatsuite/libraries/pseudo/SSSP/ — installed UPF files
#   .qmatsuite/seeds/pseudo/          — download archives

PSEUDO_LIB_SSSP="$REPO_ROOT/.qmatsuite/libraries/pseudo/SSSP"
echo ""
echo "=== Cleaning SSSP for fresh download ==="
rm -rf "$PSEUDO_LIB_SSSP" "$REPO_ROOT/.qmatsuite/seeds/pseudo"
echo "  Done."

# ---- Helper: create task dir with .mcp.json ----
# Copies .mcp.json.example with command set to absolute venv python path.

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

# ---- Helper: run one agent ----

run_agent() {
    local tnum="$1"
    local task_dir="$2"
    local task_prompt="$3"
    local trace_file="$TRACES_DIR/task_${tnum}.log"

    echo "[task_${tnum}] Starting..."
    (
        cd "$task_dir"
        unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT
        claude -p \
            --dangerously-skip-permissions \
            --output-format stream-json --verbose \
            "You are testing QMatSuite MCP tools. Complete the task below.
You MUST write a WORKLOG.md in the current directory documenting every tool call, every decision, and the final outcome.

Task: $task_prompt"
    ) > "$trace_file" 2>&1 || true
    local lines; lines="$(wc -l < "$trace_file" 2>/dev/null || echo 0)"
    echo "[task_${tnum}] Done. Trace: $lines lines"
}

# ---- Task 0: Cold Start (sequential, must succeed before parallel phase) ----

echo ""
echo "=== Task 0: Cold Start (Sequential) ==="
T0_DIR="$RUN_DIR/task_00_si_scf_cold"
setup_task "$T0_DIR"
run_agent "00" "$T0_DIR" \
    "Calculate the total energy of bulk silicon using Quantum ESPRESSO."

if [[ ! -d "$PSEUDO_LIB_SSSP" ]]; then
    echo ""
    echo "ERROR: Task 0 did not download SSSP. Check $TRACES_DIR/task_00.log" >&2
    exit 1
fi
echo "  SSSP verified: ✓"

# ---- Tasks 1-8: Parallel ----

echo ""
echo "=== Tasks 1-8: Parallel Calculations ==="

_launch() {
    local tnum="$1" tname="$2" tprompt="$3"
    local task_dir="$RUN_DIR/$tname"
    setup_task "$task_dir"
    run_agent "$tnum" "$task_dir" "$tprompt" &
}

_launch "01" "task_01_si_bands_demo" \
    "Calculate the electronic band structure of silicon using Quantum ESPRESSO. Show me the band gap and plot the bands."

_launch "02" "task_02_si_dos_demo" \
    "Calculate the density of states of silicon using Quantum ESPRESSO. Plot the DOS."

_launch "03" "task_03_si_relax_bands" \
    "First relax the silicon crystal structure using Quantum ESPRESSO, then calculate its band structure using the relaxed geometry."

_launch "04" "task_04_al_scf_scratch" \
    "Calculate the total energy of aluminum (FCC structure) using Quantum ESPRESSO. Use a high-quality preset if available."

_launch "05" "task_05_gaas_bands" \
    "Calculate the band structure of GaAs (zincblende structure) using Quantum ESPRESSO with PBE functional."

_launch "06" "task_06_fe_magnetic" \
    "Calculate the magnetic moment of BCC iron using Quantum ESPRESSO. This is a ferromagnetic metal."

_launch "07" "task_07_bad_config" \
    "Calculate the total energy of silicon using Quantum ESPRESSO. Set ecutwfc to 5 Ry and use fixed occupations."

_launch "08" "task_08_water_xtb" \
    "Optimize the geometry of a water molecule using xTB with the GFN2 method."

wait
echo "  All parallel tasks complete."

# ---- Summary ----

_check() {
    local tnum="$1" tname="$2"
    local tdir="$RUN_DIR/$tname"
    local wlog; wlog="$(test -f "$tdir/WORKLOG.md" && echo ✓ || echo ✗)"
    local proj; proj="$(test -f "$tdir/project.qv.yml" && echo ✓ || echo ✗)"
    local lines; lines="$(wc -l < "$TRACES_DIR/task_${tnum}.log" 2>/dev/null || echo 0)"
    printf "Task %s (%-22s): WORKLOG=%-2s  PROJECT=%-2s  TRACE=%s lines\n" \
        "$tnum" "$tname" "$wlog" "$proj" "$lines"
}

SUMMARY_FILE="$RUN_DIR/SUMMARY.txt"
{
echo "=== Agent Test Matrix Results ==="
echo "Run ID: $RUN_ID"
echo "Run Dir: $RUN_DIR"
echo "Date: $(date)"
echo ""
_check "00" "task_00_si_scf_cold"
_check "01" "task_01_si_bands_demo"
_check "02" "task_02_si_dos_demo"
_check "03" "task_03_si_relax_bands"
_check "04" "task_04_al_scf_scratch"
_check "05" "task_05_gaas_bands"
_check "06" "task_06_fe_magnetic"
_check "07" "task_07_bad_config"
_check "08" "task_08_water_xtb"
echo ""
echo "SSSP downloaded: $(test -d "$PSEUDO_LIB_SSSP" && echo ✓ || echo ✗)"
wcount=0; pcount=0
for n in task_00_si_scf_cold task_01_si_bands_demo task_02_si_dos_demo \
         task_03_si_relax_bands task_04_al_scf_scratch task_05_gaas_bands \
         task_06_fe_magnetic task_07_bad_config task_08_water_xtb; do
    test -f "$RUN_DIR/$n/WORKLOG.md" && ((wcount++)) || true
    test -f "$RUN_DIR/$n/project.qv.yml" && ((pcount++)) || true
done
echo "Tasks with worklog: $wcount/9"
echo "Tasks with project: $pcount/9"
} | tee "$SUMMARY_FILE"
echo ""
echo "Summary: $SUMMARY_FILE"
