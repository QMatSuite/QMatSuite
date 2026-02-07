# xTB Evidence-Only Exploration Plan

**Status**: IN PROGRESS  
**Date Started**: 2026-02-06  
**Scope**: Evidence collection only — no semantic interpretation, no code writing

---

## Objective

Build a comprehensive evidence archive for xTB 6.7.1 that future agents can:
- Extend incrementally
- Re-run examples
- Audit every fact back to source

---

## Binary Location

**Executable**: `/opt/homebrew/Caskroom/miniforge/base/bin/xtb` (Conda installation)  
**Version**: xTB version 6.7.1 (edcfbbe)  
**Type**: Serial executable  
**Compiled**: 2025-09-04

**Note**: xTB is a semiempirical quantum chemistry program for extended tight-binding calculations.

---

## Corpus Sources to Fetch

### 1. Official Documentation
- **xTB website**: https://xtb-docs.readthedocs.io/
  - User manual
  - Input/output format documentation
  - Tutorial pages
  - Example gallery
- **xTB GitHub**: https://github.com/grimme-lab/xtb
  - README and documentation
  - Test suite examples
  - Example inputs
- **xTB documentation**: https://xtb-docs.readthedocs.io/
  - Complete manual
  - API reference
  - Tutorials

### 2. Example Collections
- **xTB test suite**: Bundled examples in repository
- **Tutorial examples**: From official tutorials
- **Community examples**: GitHub repos, forum posts (if publicly available)
- **Existing artifacts**: `docs/engines/xtb/artifacts/` (already present)

### 3. Reference Materials
- **Input file format**: XYZ coordinate files + command-line options
- **Output file format**: `.out` structure, `.xyz` trajectories, `.engrad`, `.hessian`
- **Method documentation**: GFN-xTB methods (GFN0-xTB, GFN1-xTB, GFN2-xTB, GFN-FF)

---

## Types of Workflows to Cover (Qualitative Only)

### Core Workflows
1. **Single-point** — Energy calculation
2. **Optimization** — Geometry optimization
3. **Frequency** — Vibrational frequency calculation
4. **MD** — Molecular dynamics

### Extended Workflows
5. **Gradient** — Gradient calculation
6. **Hessian** — Hessian matrix calculation
7. **Conformer search** — Conformational search
8. **Thermochemistry** — Thermochemical properties

### Advanced Workflows (if examples available)
9. **Solvation** — Implicit solvation models
10. **Periodic** — Periodic boundary conditions
11. **QM/MM** — Hybrid QM/MM calculations

**Note**: We collect examples, not interpret what they do.

---

## .tmp Organization

```
.tmp/engine_research/xtb/
├── CORPUS_INDEX.json          # Machine-readable index (NOT committed)
├── SOURCES.md                 # Human-readable source list (NOT committed)
├── WORKLOG.md                 # Research worklog (NOT committed)
├── raw_web/                   # Mirrored HTML pages
│   ├── xtb-docs.readthedocs.io/  # Official documentation
│   └── github.com/               # GitHub pages
├── raw_pdfs/                  # Downloaded PDFs
├── raw_zips/                  # Archives, example bundles
├── extracted/                 # Unpacked repos, example collections
│   └── test_suite/            # If available
├── normalized/                # Cleaned/standardized examples
│   ├── h2o_sp/
│   ├── h2o_opt/
│   └── ...
├── metadata/                  # Intermediate analysis (NOT semantic)
├── runs/                      # Test execution outputs
└── real_run/                  # Real engine runs (MANDATORY)
    ├── h2o_sp_smoke/
    ├── h2o_opt_smoke/
    └── ...
```

---

## "Fast Enough to Run" Definition

**Criteria for real runs**:
- **Single-point**: < 5 seconds wall time
- **Optimization**: < 30 seconds wall time (small molecules, few steps)
- **Frequency**: < 1 minute wall time
- **MD**: < 1 minute wall time (short trajectory)

**Test systems**:
- Water molecule (3 atoms) — primary test case
- Small molecules (H2, CH4, NH3, etc.)
- Minimal systems (< 10 atoms)

**Exclusions**:
- Large systems (> 50 atoms)
- Long MD trajectories (> 1000 steps)
- Complex workflows requiring manual intervention

---

## Real Runs (MANDATORY)

For each selected example, create:
```
.tmp/engine_research/xtb/real_run/<descriptive_name>/
├── command.txt                # Exact invocation
├── run_manifest.json          # Binary path, version, env, timestamp, cwd, input hash
├── inputs/                    # Input files used
│   └── *.xyz
├── outputs/                   # Raw xTB outputs
│   ├── xtb.out
│   ├── *.xyz (if trajectory)
│   └── ...
├── expected_refs.json         # Reference values (if available, with citation)
└── compare_note.md            # match/mismatch only, no interpretation
```

**Minimum real runs**:
1. H2O single-point (energy)
2. H2O optimization
3. H2O frequency (diverse workflow)

---

## Deliverables

### Committed Files
1. **PLAN.md** (this file) — Concrete exploration plan
2. **WORKLOG_AUTO_PHASE0_1.md** — Append-only log of all activities

### Non-Committed Evidence (.tmp/)
1. **CORPUS_INDEX.json** — Complete index of all collected materials
2. **SOURCES.md** — Human-readable source list
3. **Raw corpus** — All downloaded/mirrored materials
4. **Normalized examples** — Cleaned input files
5. **Real run evidence** — Complete execution records

---

## Execution Order

1. ✅ Create PLAN.md (this file)
2. ⏳ Create WORKLOG_AUTO_PHASE0_1.md
3. ⏳ Set up .tmp/engine_research/xtb/ structure
4. ⏳ Verify binary and run minimal smoke test
5. ⏳ Create/update CORPUS_INDEX.json
6. ⏳ Fetch official documentation
7. ⏳ Collect example inputs
8. ⏳ Normalize examples
9. ⏳ Execute real runs
10. ⏳ Document all evidence

---

## Hard Boundaries

❌ **MUST NOT**:
- Interpret parameter meanings
- Propose YAML mappings
- Write parser/writer code
- Delete existing files
- Write conclusions or reviews

✅ **MAY**:
- Download and mirror documentation
- Normalize example inputs
- Run the real engine
- Capture raw outputs
- Extract verbatim reference values (with citation)
- Compare reference vs observed (match/mismatch only)

---

**End of Plan**

