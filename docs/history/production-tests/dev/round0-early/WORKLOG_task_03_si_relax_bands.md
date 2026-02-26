# Task 03: Silicon Relax + Band Structure — WORKLOG

**Task**: Relax Si crystal with QE, then compute band structure on relaxed geometry.
**Date**: 2026-02-21
**Working dir**: `.tmp/agent_mcp_test/run_20260221_101107/task_03_si_relax_bands`

---

## Step 1: Initialize Project

Ping confirmed MCP server is running (v0.1.0).
Starting project initialization...

## Step 2: Project Resolution Issue

- `init_project` initially loaded project at repo root (`<REPO_ROOT>`) — `find_project_root` walks up from task dir and finds the repo's project.qv.yml
- Workaround: called `QVService.init_project(task_dir)` directly via CLI to create a local `project.qv.yml` in the task dir
- Re-ran `init_project` → correctly loaded project at task dir
- Decision: This is a design tension in the test matrix script — `QMATSUITE_PROJECT` env var is set but project search walks up past it

## Step 3: Import Si Structure

- No structures in local project
- Found Si structures in repo: `si.json`, `si-scf.json`, `si-2.json`
- Imported `si.json` → ULID `01KJ0CCY8D5WBB897C2H696PCH` (Si2, Fd-3m, a≈3.896 Å)

## Step 4: Create Relax Calculation

- `create_calculation(engine='qe', workflow='relax', structure='01KJ0CCY8D5WBB897C2H696PCH')`
- Calc ULID: `01KJ0CD2469XE5F7VFHXCP2FMC`
- Species map auto-resolved: `Si → Si.pbe-n-rrkjus_psl.1.0.0.UPF`
- Applied presets: `precision=MED, magnetism=NM, convergence=NORMAL, occupations=FIXED`
- ecutwfc=50, ecutrho=400, K_POINTS=10×10×10, conv_thr=1e-8
- Dry run passed: all pseudos resolved, input file generated correctly

## Step 5: Run Relax Calculation

Running `run_calculation(01KJ0CD2469XE5F7VFHXCP2FMC)`...
