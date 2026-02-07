# CP2K Evidence-Only Exploration Plan

**Status**: IN PROGRESS  
**Date Started**: 2026-02-06  
**Scope**: Evidence collection only — no semantic interpretation, no code writing

---

## Objective

Build a comprehensive evidence archive for CP2K 2026.1 that future agents can:
- Extend incrementally
- Re-run examples
- Audit every fact back to source

---

## Binary Location

**Executable**: `/opt/homebrew/opt/cp2k/bin/cp2k.psmp` (Homebrew installation)  
**Version**: CP2K version 2026.1 (git:5e54ba2)  
**Type**: Parallel MPI version (psmp)  
**Flags**: omp libint fftw3 libxc parallel scalapack mpi_f08

**Note**: Serial version (ssmp) may also be available. Check both.

---

## Corpus Sources to Fetch

### 1. Official Documentation
- **CP2K website**: https://www.cp2k.org/
  - User manual
  - Input reference
  - Tutorial pages
  - Example gallery
- **CP2K manual**: https://manual.cp2k.org/
  - Complete input reference
  - Theory sections
  - Tutorials
- **CP2K GitHub**: https://github.com/cp2k/cp2k
  - Test suite examples
  - Tutorial examples
  - Input file examples

### 2. Example Collections
- **CP2K test suite**: Bundled examples in repository
- **Tutorial examples**: From official tutorials
- **Community examples**: GitHub repos, forum posts (if publicly available)

### 3. Reference Materials
- **Input file format specification**: Nested-section syntax (`&SECTION ... &END SECTION`)
- **Output file format**: .out structure, trajectory files
- **Pseudopotential formats**: GTH, GTH-HF, GTH-PBE specifications

---

## Types of Workflows to Cover (Qualitative Only)

### Core Workflows
1. **ENERGY** — Single-point energy calculation
2. **GEO_OPT** — Geometry optimization
3. **MD** — Molecular dynamics
4. **VIBRATIONAL_ANALYSIS** — Frequency calculation

### Extended Workflows
5. **CELL_OPT** — Cell optimization
6. **BAND** — Band structure calculation
7. **META_DYNAMICS** — Metadynamics
8. **LINEAR_RESPONSE** — Response properties

### Advanced Workflows (if examples available)
9. **DFT+U** — DFT+U calculations
10. **TDDFT** — Time-dependent DFT
11. **QM/MM** — Hybrid QM/MM calculations

**Note**: We collect examples, not interpret what they do.

---

## .tmp Organization

```
.tmp/engine_research/cp2k/
├── CORPUS_INDEX.json          # Machine-readable index (NOT committed)
├── SOURCES.md                 # Human-readable source list (NOT committed)
├── WORKLOG.md                 # Research worklog (NOT committed)
├── raw_web/                   # Mirrored HTML pages
│   ├── manual.cp2k.org/       # Official manual
│   └── www.cp2k.org/           # Main website pages
├── raw_pdfs/                  # Downloaded PDFs
├── raw_zips/                  # Archives, example bundles
├── extracted/                 # Unpacked repos, example collections
│   └── test_suite/            # If available
├── normalized/                # Cleaned/standardized examples
│   ├── h2o_energy/
│   ├── si_energy/
│   └── ...
├── metadata/                  # Intermediate analysis (NOT semantic)
├── runs/                      # Test execution outputs
└── real_run/                  # Real engine runs (MANDATORY)
    ├── h2o_energy_smoke/
    ├── si_geo_opt_smoke/
    └── ...
```

---

## "Fast Enough to Run" Definition

**Criteria for real runs**:
- **ENERGY**: < 30 seconds wall time
- **GEO_OPT**: < 2 minutes wall time (small systems, few steps)
- **MD**: < 1 minute wall time (short trajectory)
- **VIBRATIONAL_ANALYSIS**: < 2 minutes wall time

**Test systems**:
- Water molecule (3 atoms) — primary test case
- Small molecules (H2, CH4, etc.)
- Minimal basis sets (DZVP, SZV)
- Low cutoff (200-300 Ry)

**Exclusions**:
- Large systems (> 20 atoms)
- High-cutoff calculations (> 500 Ry)
- Long MD trajectories (> 100 steps)
- Complex workflows requiring manual intervention

---

## Real Runs (MANDATORY)

For each selected example, create:
```
.tmp/engine_research/cp2k/real_run/<descriptive_name>/
├── command.txt                # Exact invocation
├── run_manifest.json          # Binary path, version, env, timestamp, cwd, input hash
├── inputs/                    # Input files used
│   └── *.inp
├── outputs/                   # Raw CP2K outputs
│   ├── *.out
│   ├── *.xyz (if trajectory)
│   └── ...
├── expected_refs.json         # Reference values (if available, with citation)
└── compare_note.md            # match/mismatch only, no interpretation
```

**Minimum real runs**:
1. H2O ENERGY (single-point)
2. H2O GEO_OPT (geometry optimization)
3. Si ENERGY or MD (diverse workflow)

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
3. ⏳ Set up .tmp/engine_research/cp2k/ structure
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

