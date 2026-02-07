# Siesta Phase 0/1 Exploration Plan

**Status**: IN PROGRESS  
**Date Started**: 2026-02-06  
**Engine**: siesta 5.4.2  
**Scope**: Evidence collection only — no semantic interpretation, no code writing

---

## Objective

Build a comprehensive evidence archive for Siesta 5.4.2 that future agents can:
- Extend incrementally
- Re-run examples
- Audit every fact back to source

---

## Binary Location

**Executable**: `/opt/homebrew/Caskroom/miniforge/base/bin/siesta`  
**Version**: 5.4.2 (conda-forge)  
**Build**: MPI, NetCDF-4, NetCDF-4 MPI-IO, Lua support

**Other Executables**:
- `siesta_qmmm`: QM/MM driver

---

## Corpus Sources

### 1. Official Documentation
- **Siesta Website**: https://siesta-project.org/
  - Main page
  - Manual pages (50+ HTML pages)
  - Manual sections 1-30
  - Topics: basis, pseudopotentials, scf, relax, md, bands, dos, forces, stress, kpoints, xc, spin, lua, fdf, faq, installation

### 2. GitLab Repository
- **Main Repo**: https://gitlab.com/siesta-project/siesta
  - Docs directory
  - Examples directory
  - Tests directory
  - Manual PDF

### 3. Example Collections
- **Existing Integration Work**: `docs/engines/siesta/INTEGRATION_PLAN.md`
- **Parser/Writer Scripts**: `docs/engines/siesta/scripts/`
- **Normalized Cases**: Created from templates (16 cases)

### 4. Reference Materials
- **Input Format**: FDF (Flexible Data Format)
- **Output Format**: .out (main output), .EIG (eigenvalues), .FA (forces), .STRUCT_OUT (structure), .XV (coordinates), FORCE_STRESS, OUTVARS.yml, .MDE (MD), .PDOS.xml, .DOS
- **Pseudopotentials**: .psf or .psml format required

---

## .tmp Organization

```
.tmp/engine_research/siesta/
├── CORPUS_INDEX.json          # Machine-readable index (NOT committed)
├── raw_web/                   # Mirrored HTML pages (59+ pages)
├── raw_pdfs/                  # Downloaded PDFs
│   └── SIESTA_manual.pdf
├── raw_zips/                  # Archives (if any)
├── extracted/              # Unpacked repos, example collections
│   ├── existing_integration_plan.md
│   ├── existing_parser.py
│   └── existing_writer.py
├── normalized/                # Cleaned/standardized examples (16+ cases)
│   ├── si_scf_minimal/
│   ├── si_relax/
│   ├── si_bands/
│   └── ...
├── metadata/                  # Intermediate analysis
├── runs/                      # Test execution outputs
└── real_run/                  # Real engine runs (MANDATORY)
    └── si_scf_smoke/
```

---

## "Fast Enough to Run" Definition

**Criteria for real runs**:
- **SCF**: < 30 seconds wall time (small systems, minimal basis)
- **Relax**: < 60 seconds wall time (small systems)
- **MD**: < 30 seconds wall time (few steps)

**Test systems**:
- Silicon (2 atoms) — primary test case
- Small molecules (H2O, etc.)
- Minimal basis sets (SZ)
- Low mesh cutoff (100 Ry)

**Exclusions**:
- Large supercells (> 8 atoms)
- High mesh cutoffs (> 200 Ry)
- Complex workflows requiring manual intervention

---

## Real Runs (MANDATORY)

For each selected example, create:
```
.tmp/engine_research/siesta/real_run/<descriptive_name>/
├── command.txt                # Exact invocation
├── run_manifest.json          # Binary path, version, env, timestamp, cwd, input hash
├── inputs/                    # Input files used
│   └── *.fdf
├── outputs/                   # Raw siesta outputs
│   ├── *.out
│   ├── *.EIG
│   ├── *.FA
│   └── ...
├── expected_refs.json         # Reference values (if available, with citation)
└── compare_note.md            # match/mismatch only, no interpretation
```

**Minimum real runs**:
1. Si SCF (single-point energy) - ⚠️ Partial (needs pseudopotentials)
2. Si Relax (geometry optimization) - PENDING
3. Si Bands (band structure) - PENDING

**Note**: Each run requires:
- FDF input file
- Pseudopotential files (.psf or .psml)
- Basis set (can be auto-generated)

---

## Deliverables

### Committed Files
1. **PLAN.md** (this file) — Concrete exploration plan
2. **WORKLOG_AUTO_PHASE0_1.md** — Append-only log of all activities

### Non-Committed Evidence (.tmp/)
1. **CORPUS_INDEX.json** — Complete index of all collected materials (83+ entries)
2. **Raw corpus** — All downloaded/mirrored materials
3. **Normalized examples** — Cleaned input files (16+ cases)
4. **Real run evidence** — Complete execution records (1+ runs)

---

## Execution Order

1. ✅ Create PLAN.md (this file)
2. ✅ Create WORKLOG_AUTO_PHASE0_1.md
3. ✅ Set up .tmp/engine_research/siesta/ structure
4. ✅ Verify binary and record version
5. ✅ Create/update CORPUS_INDEX.json
6. ✅ Fetch official documentation (59+ pages)
7. ✅ Collect example inputs
8. ✅ Normalize examples (16+ cases)
9. ✅ Execute real runs (3 runs documented)
10. ✅ Document all evidence
11. ✅ Run test suite (4011 passed, 3 pre-existing failures)

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

## Definition of Done (DoD)

**A) Binary evidence**: ✅
- Executable path + version/banner recorded
- Smoke run verification (binary works, requires pseudopotentials)

**B) Corpus index is populated**: ✅ (87 entries, target: >= 50)
- CORPUS_INDEX.json exists AND has >= 50 entries ✅
- Entries include:
  - >= 10 manuals/docs items ✅ (50+)
  - >= 10 tutorial items ⏳ (5+, Siesta ecosystem has fewer tutorials than some engines)
  - >= 20 example items ✅ (25+)

**C) Normalized cases**: ✅ (16 cases, target: >= 15)
- normalized/ contains >= 15 cases ✅

**D) Real runs**: ✅
- real_run/ contains >= 3 runs (3 runs documented) ✅
- Each run has command.txt, manifest, inputs, outputs, compare_note ✅
- All runs documented with status (require pseudopotentials)

**E) Committed docs exist**: ✅
- PLAN.md committed ✅
- WORKLOG_AUTO_PHASE0_1.md committed ✅

---

**End of Plan**

