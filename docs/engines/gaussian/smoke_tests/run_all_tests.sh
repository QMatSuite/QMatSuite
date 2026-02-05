#!/bin/bash
# Gaussian Smoke Tests Runner
# Regenerates all smoke test outputs from the .gjf input files.
#
# Prerequisites:
#   - Gaussian 09 or 16 installed
#   - Environment configured (g09root, GAUSS_EXEDIR, GAUSS_SCRDIR)
#
# Usage:
#   cd docs/engines/gaussian/smoke_tests
#   ./run_all_tests.sh

set -e

# Configure Gaussian environment
if [ -z "$GAUSS_EXEDIR" ]; then
    REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
    export g09root="$REPO_ROOT/.qmatsuite/engines/gaussian/gaussian09"
    export GAUSS_EXEDIR="$g09root/g09"
    export GAUSS_SCRDIR=/tmp
    export PATH="$GAUSS_EXEDIR:$PATH"
fi

# Check Gaussian availability
if [ ! -x "$GAUSS_EXEDIR/g09" ]; then
    echo "Error: Gaussian not found at $GAUSS_EXEDIR/g09"
    echo "Please install Gaussian or set GAUSS_EXEDIR"
    exit 1
fi

echo "Using Gaussian at: $GAUSS_EXEDIR/g09"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

run_test() {
    local name="$1"
    local input="$2"
    local output="$3"

    echo "=== Running: $name ==="
    cd "$SCRIPT_DIR/$name"
    $GAUSS_EXEDIR/g09 < "$input" > "$output" 2>&1
    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "  Status: SUCCESS"
        grep -E "SCF Done|Normal termination|EUMP2|Optimization completed|Excited State" "$output" | head -5
    else
        echo "  Status: FAILED (exit code $exit_code)"
        tail -10 "$output"
    fi
    echo ""
}

# Run all tests
run_test "water_hf_sp" "water_sp.gjf" "water_sp.log"
run_test "water_opt" "water_opt.gjf" "water_opt.log"
run_test "water_opt_freq" "water_opt_freq.gjf" "water_opt_freq.log"
run_test "ethylene_mp2" "ethylene_mp2.gjf" "ethylene_mp2.log"
run_test "formaldehyde_tddft" "formaldehyde_tddft.gjf" "formaldehyde_tddft.log"

echo "=== All tests completed ==="
