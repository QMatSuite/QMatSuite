# MACE B1 Integration Worklog

## Phase 0: Baseline + Research

**Date**: 2026-03-01

### Baseline Test Results
- **Passed**: 6678
- **Skipped**: 5
- **Errors**: 1 (pre-existing QMCPACK integration test — unrelated)

### Research Summary
- MACE is a Python library (`mace-torch`) providing ASE Calculator objects
- Foundation models: `mace_mp()` for materials, `mace_off()` for organic molecules
- Custom models: `MACECalculator(model_paths=...)` for user-trained potentials
- Output: energy (eV), forces (eV/A), stress (6-element Voigt, eV/A^3)
- Execution model: Python-script engine (same as GPAW/PySCF/Psi4)

### Key Design Decisions
- PREFIX: "mace"
- SUPPORTED_GEN_STEPS: {"scf", "relax", "md"}
- WorkdirPolicy: ISOLATED
- Trajectory format: JSONL (stdlib-only parsing, no ASE .traj pickle)
- Calculator branch: mace_mp (foundation) vs MACECalculator (custom)
- supports_restart: False (all 3 step types — ML potentials are fast)

---

## Phase 1-2: Tags JSON + Metadata Layer

- 42 tags in `mace_tags.json` across 12 categories
- Categories: model, device, dispersion, calculator, optimizer, cell_relax, md_ensemble, md_npt, md_output, structure, output, environment
- ML potentials have fundamentally fewer parameters than DFT codes (42 vs 150-250)
- Metadata layer clones xTB pattern exactly

## Phase 3: Curated Cases

5 cases covering all 3 gen step types:
- si_scf, si_relax, water_md (demo-eligible)
- li_metal_scf, perovskite_relax (test-only)

## Phase 4: Script Generator + InputSpec

- Python-script engine following GPAW pattern
- SCF/relax/MD script templates with JSONL trajectory output
- FrechetCellFilter for variable-cell relaxation
- NVE/NVT/NPT MD ensemble support

## Phase 6: Output Parsers

- MACEDigest (17 fields) + MACEOutputParser (JSON-primary)
- MACETrajectoryParser (JSONL -> Frame/Trajectory)

## Phase 7a: Driver + Handler + Recipe

- MACEDriver: 7 MUST items, ISOLATED workdir
- mace_step_handler: subprocess execution
- MACERecipe: one job per step

## Phase 7b: Real-Run Validation

All 3 validation runs successful:

| Run | System | Energy (eV) | Time (s) | Notes |
|-----|--------|-------------|----------|-------|
| SCF | Si diamond | -10.676 | 2.5 | Stress tensor correct |
| Relax | Distorted Si | -10.672 | 2.6 | Converged in 2 steps, 4 traj frames |
| MD | Water NVT | -13.417 | 3.2 | 11 traj frames with time/energy/temp |

Bug fixes during validation:
- `atoms.pbc` returns numpy bools → fixed with `[bool(x) for x in atoms.pbc]`
- `opt.converged()` requires gradient arg in newer ASE → switched to force threshold check

## Phase 8: Integration + Tests

### Kernel updates (data-only):
1. Added "mace" to ENGINE_PREFIXES in step_type_convert.py
2. Added "mace" entry to ENGINE_META in engine_meta.py
3. Added `from qmatsuite.drivers import mace` to drivers/__init__.py

### MCP updates (data-only):
4. Added "mace": "Python script" to _SYNTAX_FAMILIES
5. Added "mace" to _TAG_ENGINES set

### Test count updates:
- 15 → 16 engine count in 4 test files

### Final Test Results
- **Passed**: 6742 (+64 vs baseline)
- **Skipped**: 4 (-1 vs baseline)
- **Failures**: 0
- **Errors**: 1 (pre-existing QMCPACK integration — unchanged)

---
