# ABINIT Evidence-Only Exploration Plan

**Status**: IN PROGRESS  
**Date Started**: 2026-02-06  
**Scope**: Evidence collection only — no semantic interpretation, no code writing

---

## Objective

Build a comprehensive evidence archive for ABINIT 10.4.7 that future agents can:
- Extend incrementally
- Re-run examples
- Audit every fact back to source

---

## Binary Location

**Executable**: `.qmatsuite/engines/abinit/10.4.7/bin/abinit`  
**Version**: 10.4.7-d (verified)  
**Size**: 28,607,992 bytes

---

## Corpus Sources to Fetch

### 1. Official Documentation
- **ABINIT website**: https://www.abinit.org/
  - User guide (HTML/PDF)
  - Tutorial pages
  - Input variable reference
  - Example gallery
- **ABINIT documentation wiki**: https://docs.abinit.org/
  - Complete variable reference
  - Tutorials by topic
  - Theory pages

### 2. Example Collections
- **ABINIT test suite**: Bundled examples (if available in installation)
- **Tutorial examples**: From official tutorials
- **Community examples**: GitHub repos, forum posts (if publicly available)

### 3. Reference Materials
- **Input file format specification**: Variable syntax, multi-dataset rules
- **Output file format**: .abo structure, YAML blocks, binary file formats
- **Pseudopotential formats**: .pspnc, .psp8, .hgh, .xml specifications

---

## Types of Workflows to Cover (Qualitative Only)

### Core Workflows
1. **SCF** — Ground state single-point energy
2. **NSCF** — Non-self-consistent calculation (bands/DOS)
3. **Relax** — Ionic relaxation (ionmov=2)
4. **vc-relax** — Volume/cell optimization (optcell=1 or 2)

### Extended Workflows
5. **Multi-dataset** — Sequential calculations in one input (ndtset > 1)
6. **Band structure** — SCF → NSCF along k-path
7. **Density of states** — DOS calculation workflow

### Advanced Workflows (if examples available)
8. **DFPT** — Response functions (optdriver=1)
9. **GW** — Quasiparticle energies (optdriver=4)
10. **MD** — Molecular dynamics (ionmov=12)

**Note**: We collect examples, not interpret what they do.

---

## .tmp Organization

```
.tmp/engine_research/abinit/
├── CORPUS_INDEX.json          # Machine-readable index (NOT committed)
├── SOURCES.md                 # Human-readable source list (NOT committed)
├── WORKLOG.md                 # Research worklog (NOT committed)
├── raw_web/                   # Mirrored HTML pages
│   ├── docs.abinit.org/       # Official documentation
│   └── www.abinit.org/        # Main website pages
├── raw_pdfs/                  # Downloaded PDFs
│   ├── user_guide.pdf
│   └── tutorials/
├── raw_zips/                  # Archives, example bundles
├── extracted/                 # Unpacked repos, example collections
│   └── test_suite/            # If available
├── normalized/                # Cleaned/standardized examples
│   ├── si_scf/
│   ├── si_relax/
│   └── ...
├── metadata/                  # Intermediate analysis (NOT semantic)
│   └── variable_list.json     # Raw variable names only
├── runs/                      # Test execution outputs
└── real_run/                  # Real engine runs (MANDATORY)
    ├── si_scf_smoke/
    ├── si_relax_smoke/
    └── ...
```

---

## "Fast Enough to Run" Definition

**Criteria for real runs**:
- **SCF**: < 30 seconds wall time
- **NSCF**: < 60 seconds wall time
- **Relax**: < 5 minutes wall time (small systems only)
- **Multi-dataset**: < 2 minutes total

**Test systems**:
- Silicon (2 atoms) — primary test case
- Small molecules (if molecular examples found)
- Minimal k-point grids (2x2x2 or 4x4x4)
- Low ecut (10-15 Ha for Si)

**Exclusions**:
- Large supercells (> 8 atoms)
- High-ecut calculations (> 30 Ha)
- Complex workflows requiring manual intervention

---

## Real Runs (MANDATORY)

For each selected example, create:
```
.tmp/engine_research/abinit/real_run/<descriptive_name>/
├── command.txt                # Exact invocation
├── run_manifest.json          # Binary path, version, env, timestamp, cwd, input hash
├── inputs/                    # Input files used
│   └── *.abi
├── outputs/                   # Raw ABINIT outputs
│   ├── *.abo
│   ├── *_WFK
│   ├── *_DEN
│   └── ...
├── expected_refs.json         # Reference values (if available, with citation)
└── compare_note.md            # match/mismatch only, no interpretation
```

**Minimum real runs**:
1. Si SCF (single-point)
2. Si NSCF (bands calculation)
3. Si relax (ionic relaxation)

---

## Deliverables

### Committed Files
1. **PLAN.md** (this file) — Concrete exploration plan
2. **WORKLOG.md** — Append-only log of all activities

### Non-Committed Evidence (.tmp/)
1. **CORPUS_INDEX.json** — Complete index of all collected materials
2. **SOURCES.md** — Human-readable source list
3. **Raw corpus** — All downloaded/mirrored materials
4. **Normalized examples** — Cleaned input files
5. **Real run evidence** — Complete execution records

---

## Execution Order

1. ✅ Create PLAN.md (this file)
2. ⏳ Create WORKLOG.md
3. ⏳ Set up .tmp/engine_research/abinit/ structure
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

