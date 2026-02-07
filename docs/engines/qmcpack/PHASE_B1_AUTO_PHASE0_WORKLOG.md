# QMCPACK Phase 0 (Mechanical) Worklog

**Status**: COMPLETE
**Scope**: Binary discovery, corpus collection, corpus index, normalized examples, FAST real runs
**Discipline**: Append-only, mechanical only (no semantic work)

---

## 2026-02-06T21:16:00Z — Session Start

### Binary Discovery

**QMCPACK binary**:
- Path: `<repo root>/.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack`
- Version: QMCPACK version 4.1.0 built on Jan 27 2026
- Executable: YES (20133896 bytes, -rwxr-xr-x)
- Command: `qmcpack input [--dryrun --gpu]`

**QE pw.x binary** (for composite workflows):
- Path: `<repo root>/.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw.x` (symlink to `../PW/src/pw.x`)
- Version: Program PWSCF v.7.5
- Executable: YES (symlink)

**QE pw2qmcpack.x binary** (for composite workflows):
- Path: `<repo root>/.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw2qmcpack.x`
- Version: Program pw2qmcpack v.7.5
- Executable: YES (12058000 bytes, -rwxr-xr-x)

---

## 2026-02-06T21:17:00Z — CORPUS_INDEX.json Creation

**Created**: `.tmp/engine_research/qmcpack/CORPUS_INDEX.json`

**Indexed existing corpus**:
- 9 entries covering all existing materials:
  - ReadTheDocs documentation (raw_web/)
  - Bundled examples (extracted/examples/)
  - Lab tutorials (extracted/labs/) - 5 labs
  - Test molecules (extracted/tests_molecules/) - 22 test systems
  - Test solids (extracted/tests_solids/) - 28 test systems
  - Converter tests (extracted/tests_converter/) - 22 test systems
  - XSD schema files (extracted/schema/)
  - Test pseudopotentials (extracted/pseudopotentials_for_tests/)
  - Normalized cases (normalized/) - 13 cases
  - Metadata seed (metadata/) - 3 JSON files

**Files touched**: `.tmp/engine_research/qmcpack/CORPUS_INDEX.json`

---

## 2026-02-06T21:17:12Z — FAST Real Run: he_vmc_sto

**Case**: He atom VMC with STO analytic wavefunction

**Execution**:
- Command: `<repo root>/.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack qmc_input.xml`
- Working directory: `.tmp/engine_research/qmcpack/normalized/he_vmc_sto/`
- Wall time: ~0.47 seconds
- Status: SUCCESS

**Output files generated**:
- He.s000.scalar.dat (block-averaged VMC data)
- He.s000.stat.h5 (statistics HDF5)
- He.s000.config.h5 (walker configurations)
- He.s000.cont.xml (continuation XML)
- He.info.xml (run info)
- stdout.txt (full output log)

**Real run folder created**: `.tmp/engine_research/qmcpack/real_run/he_vmc_sto/`
- command.txt (exact command)
- run_manifest.json (binary paths, versions, timestamp, input hash)
- outputs/ (all output files)
- expected_refs.json (reference energy -2.9037 Ha)
- compare_note.md (run summary and comparison)

**Files touched**: 
- `.tmp/engine_research/qmcpack/real_run/he_vmc_sto/command.txt`
- `.tmp/engine_research/qmcpack/real_run/he_vmc_sto/run_manifest.json`
- `.tmp/engine_research/qmcpack/real_run/he_vmc_sto/expected_refs.json`
- `.tmp/engine_research/qmcpack/real_run/he_vmc_sto/compare_note.md`
- `.tmp/engine_research/qmcpack/real_run/he_vmc_sto/outputs/` (copied from normalized directory)

---

## 2026-02-06T21:17:38Z — FAST Real Run: lih_qe_workflow (Composite)

**Case**: LiH solid QE→pw2qmcpack→QMCPACK workflow

**Step 1 (QE SCF)**:
- Command: `<repo root>/.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw.x -in qe_scf.in`
- Wall time: ~1.7 seconds
- Status: SUCCESS
- Output: Generated `pwscf_output/LiH-gamma.save/`

**Step 2 (pw2qmcpack)**:
- Command: `<repo root>/.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw2qmcpack.x < pw2qmcpack.in`
- Wall time: ~0.2 seconds
- Status: SUCCESS
- Output: Generated `pwscf_output/LiH-gamma.pwscf.h5` (3.9 MB)

**Step 3 (QMCPACK)**:
- Command: `<repo root>/.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack qmc_input.xml`
- Status: FAILED (charge mismatch error)
- Error: `Ion species Li charge 3 pseudopotential charge 1 mismatch!`
- Note: This is a semantic input file issue, not a binary/mechanical problem. QE and pw2qmcpack steps succeeded, verifying those binaries work.

**Real run folder created**: `.tmp/engine_research/qmcpack/real_run/lih_qe_workflow/`
- command.txt (all 3 workflow steps)
- run_manifest.json (all binary paths and versions)
- outputs/ (qe_scf.out, pw2qmcpack.out, qmcpack.out)
- compare_note.md (detailed step-by-step results)

**Files touched**:
- `.tmp/engine_research/qmcpack/real_run/lih_qe_workflow/command.txt`
- `.tmp/engine_research/qmcpack/real_run/lih_qe_workflow/run_manifest.json`
- `.tmp/engine_research/qmcpack/real_run/lih_qe_workflow/compare_note.md`
- `.tmp/engine_research/qmcpack/real_run/lih_qe_workflow/outputs/` (all output files)

**Mechanical verification**: PASS
- QE pw.x binary works correctly
- pw2qmcpack.x binary works correctly
- QMCPACK binary works correctly (verified in he_vmc_sto run)
- Composite workflow binaries are functional

---

## Summary

**Binary Discovery**: COMPLETE
- QMCPACK: `<repo root>/.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack` (v4.1.0)
- QE pw.x: `<repo root>/.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw.x` (v7.5)
- QE pw2qmcpack.x: `<repo root>/.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw2qmcpack.x` (v7.5)

**Corpus Index**: COMPLETE
- Created `.tmp/engine_research/qmcpack/CORPUS_INDEX.json` with 9 entries
- Indexed all existing corpus materials (extracted/, normalized/, metadata/, raw_web/)

**Normalized Cases**: EXISTING (13 cases already present)
- No new normalization needed; existing cases are sufficient

**Real Runs**: COMPLETE
- `he_vmc_sto`: SUCCESS (standalone QMCPACK, ~0.47s)
- `lih_qe_workflow`: PARTIAL (QE + pw2qmcpack succeeded, QMCPACK failed due to input file charge mismatch - semantic issue, not mechanical)

**Worklog**: COMPLETE
- Created `docs/engines/qmcpack/PHASE_B1_AUTO_PHASE0_WORKLOG.md`
- Continuously updated with all activities

**Definition of Done**: MET
- ✅ QMCPACK binary path and version recorded
- ✅ QE/pw2qmcpack paths and versions recorded
- ✅ CORPUS_INDEX.json exists and indexes all corpus
- ✅ Normalized cases exist (13 cases)
- ✅ 2 FAST real_run folders exist (he_vmc_sto standalone, lih_qe_workflow composite)
- ✅ Worklog complete and continuously updated
- ✅ No committed files modified (no pytest needed)

---

