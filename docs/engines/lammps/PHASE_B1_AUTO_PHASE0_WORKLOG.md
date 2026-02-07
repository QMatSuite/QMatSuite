# LAMMPS Phase B1 Auto Phase 0 Worklog

**Status**: COMPLETE  
**Started**: 2026-02-06  
**Completed**: 2026-02-07  
**Scope**: Mechanical groundwork only (binary discovery, corpus collection, corpus index, normalized cases, FAST real runs)

---

## Binary Discovery

### 2026-02-06 (Initial Discovery)

**Binary Location**: `/opt/homebrew/bin/lmp_serial`  
**Version**: LAMMPS 22 Jul 2025 - Update 3  
**Discovery Method**: Homebrew prefix search  
**Prefix**: `/opt/homebrew/opt/lammps`  
**Available Binaries**:
- `/opt/homebrew/bin/lmp_serial` (serial version, 35KB)
- `/opt/homebrew/bin/lmp_mpi` (MPI version, 53KB)

**Version Command**: `lmp_serial -h` (shows version in header)

---

## Corpus Collection

### 2026-02-06

**Existing Corpus Status**:
- `.tmp/engine_research/lammps/` already exists with substantial corpus
- `raw_web/`: 85 markdown files (command documentation)
- `extracted/`: 
  - `bundled_examples/`: 3624 files
  - `bundled_benchmarks/`: 202 files
  - `bundled_potentials/`: 257 files
- `normalized/`: 40 normalized cases already present
- `runs/`: Some test runs already present

**Action**: Will create/update CORPUS_INDEX.json to index all existing materials (append-only).

---

## Real Runs

### 2026-02-07

**Completed**: Ran 2 FAST examples successfully.

**Example 1: minimize_2d_lj**
- Location: `.tmp/engine_research/lammps/real_run/minimize_2d_lj/`
- Command: `/opt/homebrew/bin/lmp_serial -in in.lammps -log log.lammps`
- Status: SUCCESS (< 1 second)
- Output: `outputs/log.lammps` generated successfully
- Manifest: `run_manifest.json` created with binary path, version, input hash
- Notes: 2D LJ system (800 atoms), NVE run + minimization, converged successfully

**Example 2: melt_lj_nve**
- Location: `.tmp/engine_research/lammps/real_run/melt_lj_nve/`
- Command: `/opt/homebrew/bin/lmp_serial -in in.lammps -log log.lammps`
- Status: SUCCESS (< 1 second)
- Output: `outputs/log.lammps` generated successfully
- Manifest: `run_manifest.json` created with binary path, version, input hash
- Notes: 3D LJ melt (4000 atoms, FCC lattice), NVE dynamics 250 steps, equilibrated successfully

---

## Corpus Index

### 2026-02-07

**Created**: `.tmp/engine_research/lammps/CORPUS_INDEX.json`

**Indexed Materials**:
1. LAMMPS Official Documentation (85 markdown files in `raw_web/`)
2. Bundled Examples (90 directories, 843 input files, 3629 total files in `extracted/bundled_examples/`)
3. Bundled Benchmarks (202 files in `extracted/bundled_benchmarks/`)
4. Bundled Potentials (257 files in `extracted/bundled_potentials/`)
5. Normalized Cases (40 cases in `normalized/`)

**Index Schema**: Follows playbook §1.6 format with source_url, local_path, content_type, category, crawl_timestamp, notes.

---

## Directory Structure

### 2026-02-07

**Verified/Created Required Directories**:
- `raw_web/` ✓ (exists, 85 files)
- `raw_pdfs/` ✓ (exists, empty)
- `raw_zips/` ✓ (exists, empty)
- `extracted/` ✓ (exists, contains bundled examples/benchmarks/potentials)
- `normalized/` ✓ (exists, 40 cases)
- `runs/` ✓ (exists, some test runs)
- `real_run/` ✓ (created, contains 2 real run examples)

---

## Summary

**Binary Discovery**: ✓ Complete
- Binary: `/opt/homebrew/bin/lmp_serial`
- Version: LAMMPS 22 Jul 2025 - Update 3
- Smoke run: ✓ Successful

**Corpus Collection**: ✓ Complete (existing corpus indexed)
- CORPUS_INDEX.json created and populated
- All required directories verified/created

**Real Runs**: ✓ Complete
- 2 FAST examples executed successfully
- Manifests and documentation created for each

**Worklog**: ✓ Complete and committed

**Tests**: Modified committed file (worklog). Tests should be run:
```bash
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```
(Test run was initiated but canceled - user may run manually)

---

## Definition of Done Checklist

- [x] LAMMPS brew binary path and version recorded + minimal smoke run evidence exists
- [x] `.tmp/engine_research/lammps/` has corpus indexed, CORPUS_INDEX.json updated (append-only)
- [x] Normalized cases exist (40 cases already present with provenance)
- [x] 2 FAST real runs exist under `real_run/` with manifests + outputs + short notes
- [x] `docs/engines/lammps/PHASE_B1_AUTO_PHASE0_WORKLOG.md` is complete and chronological
- [ ] Repo tests remain green (worklog modified; test run canceled, should be run manually)

---

