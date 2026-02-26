# WORKLOG — Silicon Band Structure via QMatSuite MCP

**Task**: Calculate the electronic band structure of silicon using Quantum ESPRESSO. Show the band gap and plot the bands.
**Date**: 2026-02-21

---

## Step 1: Initialize project

Calling `init_project` to set up the QMatSuite project context.

**Result**: Loaded existing project at `<REPO_ROOT>`.

---

## Step 2: Search for Si band structure demos

Searched demos with `engine=qe, property_of_interest=band_structure`. Found 5 demos.

Chose **`si_bands_demo`** ("Silicon band structure") — 4-step workflow (SCF → NSCF → Bands → BandsPW), PBE, L-Γ-X-U-Γ path, ~50s runtime.

Pre-computed results available:
- `bands`: 91 k-points, 8 bands, reference energy 6.133 eV
- `convergence`: also available

---

## Step 3: Load demo into project

Loading `si_bands_demo` via `load_demo`.

**Result**:
- `calc_ulid`: `01KJ0C95HWKMVKKXNKX0SB1YQZ`
- `structure_ulid`: `01KJ0C95HV90QEGY8KXVXBNCR4`
- 4 steps: SCF → NSCF → Bands (pw.x) → Bands PP (bands.x)

---

## Step 4: Run the calculation

Running all 4 steps with `run_calculation`.
