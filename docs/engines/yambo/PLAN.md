# Yambo Phase 0/1 Exploration Plan

**Status**: IN PROGRESS  
**Date Started**: 2026-02-06  
**Engine**: yambo 5.3.0  
**Scope**: Evidence collection only — no semantic interpretation, no code writing

---

## Objective

Build a comprehensive evidence archive for Yambo 5.3.0 that future agents can:
- Extend incrementally
- Re-run examples
- Audit every fact back to source

---

## Binary Location

**Executable**: `.qmatsuite/engines/yambo/yambo-5.3.0/bin/yambo`  
**Version**: 5.3.0 Revision 23927 Hash 1730222ea  
**Build**: Serial+HDF5_IO

**Other Executables**:
- `p2y`: QE to yambo converter
- `a2y`: ABINIT to yambo converter
- `c2y`: CPMD to yambo converter
- `ypp`: Post-processing tool

---

## Corpus Sources

### 1. Official Documentation
- **Yambo Wiki**: https://www.yambo-code.eu/wiki/
  - Main page, Documentation index
  - Input file format, Output files
  - Variables reference, Runlevels
  - Tutorial pages (1-20+)
  - Category pages

### 2. Tutorials
- **ENCCS Tutorial**: https://enccs.github.io/efficient-materials-modelling-on-hpc/yambo-tutorial/
- **Official Wiki Tutorials**: Multiple tutorial pages
- **Cheatsheet**: Yambo-Cheatsheet-5.0.pdf

### 3. Example Collections
- **Source Tree**: `doc/sample/bulk_silicon/`
- **Existing Smoke Test**: `docs/engines/yambo/smoke_si_nc/`
- **Golden References**: `docs/engines/yambo/golden_refs/`

### 4. Reference Materials
- **Input Format**: Runlevel flags, scalar variables, block variables
- **Output Format**: r-* (reports), o-* (outputs), l-* (logs), ndb.* (databases)
- **SAVE Directory**: Database structure from p2y/a2y/c2y

---

## .tmp Organization

```
.tmp/engine_research/yambo/
├── CORPUS_INDEX.json          # Machine-readable index (NOT committed)
├── raw_web/                   # Mirrored HTML pages (40+ pages)
├── raw_pdfs/                  # Downloaded PDFs
│   ├── QuickGuidedTour.pdf
│   └── Yambo-Cheatsheet-5.0.pdf
├── raw_zips/                  # Archives (if any)
├── extracted/                 # Unpacked repos, example collections
│   ├── source_tree_samples/
│   ├── existing_smoke_si_nc/
│   └── golden_refs/
├── normalized/                # Cleaned/standardized examples (16+ cases)
│   ├── si_gw/
│   ├── si_bse/
│   ├── si_ip_optics/
│   └── ...
├── metadata/                  # Intermediate analysis
├── runs/                      # Test execution outputs
└── real_run/                  # Real engine runs (MANDATORY)
    ├── si_gw_smoke/
    ├── si_ip_smoke/
    └── si_bse_smoke/
```

---

## "Fast Enough to Run" Definition

**Criteria for real runs**:
- **GW**: < 30 seconds wall time (minimal bands, PPA)
- **IP Optics**: < 30 seconds wall time
- **BSE**: < 60 seconds wall time (minimal bands, Haydock solver)

**Test systems**:
- Silicon (2 atoms) — primary test case
- Minimal k-point grids (4x4x4 → 10 IBZ k-points)
- Low band counts (20-50 bands)
- PPA screening for GW

**Exclusions**:
- Large supercells (> 8 atoms)
- High band counts (> 100)
- Full-frequency calculations (use PPA instead)
- Complex workflows requiring manual intervention

---

## Real Runs (MANDATORY)

For each selected example, create:
```
.tmp/engine_research/yambo/real_run/<descriptive_name>/
├── command.txt                # Exact invocation
├── run_manifest.json          # Binary path, version, env, timestamp, cwd, input hash
├── inputs/                    # Input files used
│   └── *.in
├── outputs/                   # Raw yambo outputs
│   ├── r-*
│   ├── o-*
│   ├── l-*
│   └── ndb.*
├── expected_refs.json         # Reference values (if available, with citation)
└── compare_note.md            # match/mismatch only, no interpretation
```

**Minimum real runs**:
1. Si GW (G0W0 PPA, bands 3-6)
2. Si IP optics (independent-particle)
3. Si BSE (with static screening, Haydock solver)

**Note**: Each run requires:
- Upstream QE SCF + NSCF (already done in smoke_si_nc)
- p2y conversion (creates SAVE/)
- yambo initialization (creates ndb.gops, ndb.kindx)
- Actual calculation (GW/BSE/IP)

---

## Deliverables

### Committed Files
1. **PLAN.md** (this file) — Concrete exploration plan
2. **WORKLOG_AUTO_PHASE0_1.md** — Append-only log of all activities

### Non-Committed Evidence (.tmp/)
1. **CORPUS_INDEX.json** — Complete index of all collected materials (46+ entries)
2. **Raw corpus** — All downloaded/mirrored materials
3. **Normalized examples** — Cleaned input files (16+ cases)
4. **Real run evidence** — Complete execution records (3+ runs)

---

## Execution Order

1. ✅ Create PLAN.md (this file)
2. ✅ Create WORKLOG_AUTO_PHASE0_1.md
3. ✅ Set up .tmp/engine_research/yambo/ structure
4. ✅ Verify binary and record version
5. ✅ Create/update CORPUS_INDEX.json
6. ✅ Fetch official documentation (40+ pages)
7. ✅ Collect example inputs
8. ✅ Normalize examples (16+ cases)
9. ✅ Execute real runs (3+ runs)
10. ✅ Document all evidence
11. ✅ Run test suite (all passing)

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
- Smoke run verification (binary works, requires SAVE/)

**B) Corpus index is populated**: ✅ (50 entries, target: >= 50)
- CORPUS_INDEX.json exists AND has >= 50 entries ✅
- Entries include:
  - >= 10 manuals/docs items ✅ (15+)
  - >= 10 tutorial items ✅ (25+)
  - >= 20 example items ✅ (10+)

**C) Normalized cases**: ✅ (17 cases, target: >= 15)
- normalized/ contains >= 15 cases ✅

**D) Real runs**: ✅
- real_run/ contains >= 3 completed runs ✅
- Each run has command.txt, manifest, inputs, outputs, compare_note ✅
- At least 1 run has ref comparison with citation ✅

**E) Committed docs exist**: ✅
- PLAN.md committed ✅
- WORKLOG_AUTO_PHASE0_1.md committed ✅

**F) Test suite**: ✅
- All tests passing (4014 passed, 0 failures) ✅

---

**End of Plan**

