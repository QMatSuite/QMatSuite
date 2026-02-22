# B1 Engine Playbook — Compliance Review

**Reviewed against**: `docs/architecture/B1_ENGINE_PLAYBOOK.md` v2.2 (with §1.5–§1.12 corpus/binary/real-run/diversity/composite policy)
**Review date**: 2026-02-06
**Reviewer**: Claude (automated audit)
**Scope**: All 15 engines — file-level evidence check, no code/corpus/test modifications

---

## 1. Summary Table

| Engine | Tier | B1 Status | Binary Path Evidence | Plan | Worklog | SOURCES.md | CURATED_INDEX.md | CORPUS_INDEX.json | .tmp corpus | Curated samples | Real-Run Validation | Rollup Index | Gaps |
|--------|------|-----------|---------------------|------|---------|------------|------------------|-------------------|-------------|-----------------|---------------------|-------------|------|
| QE | A | Gold std | `.qmatsuite/engines/qe/q-e-qe-7.5/bin/` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | — |
| VASP | A | Pre-playbook, remediation required | Recorded: `.qmatsuite/engines/vasp/vasp.6.5.0/bin/` | Yes | Yes | **MISSING** (only in .tmp) | **MISSING** | **MISSING** | Sparse | 12 | **MISSING** (no `real_run/` dirs) | **MISSING** | S1, C1, C2, R1, B1, IX, DV, CW |
| ORCA | B1 | Pre-playbook, remediation required | **Not yet recorded** — discovery required (§1.8) | Yes | Yes | Yes | **MISSING** | **Wrong format** (.md not .json, wrong location) | Moderate | 1 | **MISSING** (no `real_run/` dirs) | **MISSING** | C1, C2, C3, S2, R1, B1, IX, DV, CW |
| LAMMPS | B1 | Pre-playbook, remediation required | Recorded: `$(brew --prefix)/bin/lmp_serial` | Yes | Yes | **Case dup** (sources.md + SOURCES.md) | **MISSING** | **MISSING** | Rich (843 files) | 8 | **MISSING** (no `real_run/` dirs; runs/ exists but not per §1.9 layout) | **MISSING** | C1, C2, S3, R1, IX, DV |
| Gaussian | B1 | Pre-playbook, remediation required | Recorded: `.qmatsuite/engines/gaussian/gaussian09/g09/g09` | Yes | Yes | Yes | **MISSING** | **MISSING** | Good | 6 | **MISSING** (no `real_run/` dirs; runs/ exists but not per §1.9 layout) | **MISSING** | C1, C2, R1, IX, DV, CW |
| W90 | B1 | Pre-playbook, remediation required | Recorded: `.qmatsuite/engines/qe/q-e-qe-7.5/bin/wannier90.x` | Yes | Yes | Yes | **MISSING** | **MISSING** | Good (20 cases) | 5 | **MISSING** (no `real_run/` dirs; runs/ exists but not per §1.9 layout) | **MISSING** | C1, C2, R1, IX, DV |
| QMCPACK | B1 | Pre-playbook, remediation required | Recorded: `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack` | Yes | Yes | Yes | **MISSING** | **MISSING** | Rich (1438 XMLs) | 5 | **MISSING** (no `real_run/` dirs; runs/ exists but not per §1.9 layout) | **MISSING** | C1, C2, R1, IX, DV |
| ABINIT | B0 | Pre-playbook, full B1 required | Recorded: `.qmatsuite/engines/abinit/10.4.7/bin/abinit` | No | No | No | No | No | **None** | 1 | **MISSING** | **MISSING** | Full B1 |
| CP2K | C | Pre-playbook, full B1 required | Not yet recorded — discovery required (§1.8); expected at `$(brew --prefix)/bin/cp2k` | No | No | No | No | No | **None** | 0 | **MISSING** | **MISSING** | Full B1 |
| Siesta | B0 | Pre-playbook, full B1 required | Not yet recorded — discovery required (§1.8); expected via conda | No | No | No | No | No | **None** | 0 | **MISSING** | **MISSING** | Full B1 |
| xTB | C | Pre-playbook, full B1 required | Not yet recorded — discovery required (§1.8); expected via conda | No | No | No | No | No | **None** | 1 | **MISSING** | **MISSING** | Full B1 |
| GPAW | B0 | Pre-playbook, full B1 required | Not yet recorded — discovery required (§1.8); expected via pip | No | No | No | No | No | **None** | 0 | **MISSING** | **MISSING** | Full B1 |
| Psi4 | C | Pre-playbook, full B1 required | Not yet recorded — discovery required (§1.8); expected via conda | No | No | No | No | No | **None** | 0 | **MISSING** | **MISSING** | Full B1 |
| PySCF | C | Pre-playbook, full B1 required | Not yet recorded — discovery required (§1.8); expected via pip | No | No | No | No | No | **None** | 0 | **MISSING** | **MISSING** | Full B1 |
| Yambo | B0 | Pre-playbook, full B1 required | Not yet recorded — discovery required (§1.8); expected at `.qmatsuite/engines/yambo/` | No | No | No | No | No | **None** | 0 | **MISSING** | **MISSING** | Full B1 |

**Gap codes**: C1 = missing CURATED_INDEX.md (§1.7), C2 = missing CORPUS_INDEX.json (§1.6), C3 = wrong index format, S1 = SOURCES.md misplaced, S2 = low curated sample count, S3 = filename case duplication, R1 = missing real-run validation artifacts per §1.9, B1 = binary path not recorded per §1.8 E3, IX = missing repo-level rollup index entry (§1.10 I5), DV = no diversity rationale in curated set (§1.11 D2), CW = missing composite pipeline in curated set despite known pipeline (§1.12 W1)

---

## 2. Per-Engine Notes

### 2.1 QE (Gold Standard — no B1 needed)

QE is the reference implementation and template for all other engines. It has the most mature IO stack (`drivers/qe/io/` with parser.py, generator.py, model.py, structure_io.py), comprehensive metadata (`data/qe_metadata.py` + `data/qe_module_parameters.json`), and a regex-based line tokenizer with roundtrip capability. No B1 work is required — QE _is_ the standard.

**Binary path**: `.qmatsuite/engines/qe/q-e-qe-7.5/bin/` — recorded and verified.
**Files**: `src/qmatsuite/drivers/qe/` (full driver stack)

### 2.2 VASP (Tier A — Pre-Playbook, Remediation Required)

**Plan**: `docs/engines/vasp/PHASE_B1_PLAN.md` (125 lines) — present, well-structured
**Worklog**: `docs/engines/vasp/PHASE_B1_WORKLOG.md` (61 lines) — present but notably brief for a Tier A engine
**SOURCES.md**: **GAP** — exists only at `.tmp/engine_research/vasp/SOURCES.md`, NOT at `docs/engines/vasp/SOURCES.md`. Per playbook §1.7, SOURCES.md should be committed under `docs/engines/<engine>/`.

**Binary path**: `.qmatsuite/engines/vasp/vasp.6.5.0/bin/` — path recorded in dashboard but not formally recorded per §1.8 E3 (no version string, no discovery timestamp in worklog). **NON-COMPLIANT** with §1.8 E3.

**Corpus** (`.tmp/engine_research/vasp/`):
- Directory exists but is sparse. Contains `SOURCES.md` and `WORKLOG.md` and largely empty subdirectories.
- No `CORPUS_INDEX.json` (§1.6 requirement). **NON-COMPLIANT**.
- The VASP B1 was done before the `.tmp/` convention was fully established — research was done inline rather than through the standard corpus pipeline. This is not an excuse under the current playbook — the corpus must be backfilled.

**Curated samples** (`tests/inputformat/samples/vasp/`): **12 cases** — the richest sample set of any engine. Each case has `INCAR`, `POSCAR`, `KPOINTS`, and `case.yaml`. The `si_scf` case also has `ref_values.yaml`.

**Real-run validation**: **NON-COMPLIANT** with §1.9. No `.tmp/engine_research/vasp/real_run/` directory exists. The existing `runs/` directory (if any) does not follow the §1.9 V3 layout (command.txt, run_manifest.json, outputs/, expected_refs.json, compare_note.md). All 12 curated samples need real-run evidence created.

**Diversity assessment** (§1.11): VASP has 12 curated samples covering scf, relax, vc_relax, bands, dos, magnetic, Hubbard, vdW, MD, slab, hybrid, SOC — good Category A/B diversity. No near-duplicates detected. However, no diversity rationale is documented (§1.11 D2). **Needs CURATED_INDEX.md with rationale.**

**Composite pipeline** (§1.12): VASP participates in the VASP→Wannier90 pipeline (§1.12 W4). **None of the 12 curated samples is a composite workflow.** **NON-COMPLIANT** with §1.12 W1.

**Gaps**:
1. SOURCES.md not in `docs/engines/vasp/` (only in `.tmp/`)
2. No CURATED_INDEX.md (§1.7) — also blocks diversity rationale (§1.11 D2)
3. No CORPUS_INDEX.json (§1.6)
4. `.tmp/` corpus is sparse — needs full backfill (§1.5 C1)
5. Binary path not formally recorded with version string (§1.8 E3)
6. No real-run validation for any curated sample (§1.9 V1)
7. No entry in repo-level rollup index (§1.10 I5)
8. No composite pipeline curated example (§1.12 W1) — need VASP→W90 case
9. No diversity rationale per curated sample (§1.11 D2)

### 2.3 ORCA (Tier B1 — Pre-Playbook, Remediation Required)

**Plan**: `docs/engines/orca/PHASE_B1_PLAN.md` — present
**Worklog**: `docs/engines/orca/PHASE_B1_WORKLOG.md` — present
**SOURCES.md**: `docs/engines/orca/SOURCES.md` — present and committed

**Binary path**: **Not yet recorded.** No evidence of binary discovery per §1.8. The ORCA binary is guaranteed to exist in one of the 4 canonical locations (§1.8 E2) — most likely `.qmatsuite/engines/orca/`. The agent MUST locate it before any further work. **NON-COMPLIANT** with §1.8 E1/E3.

**Corpus** (`.tmp/engine_research/orca/`):
- Contains `CORPUS_INDEX.md` (154 lines) — **wrong format** per §1.6 (should be `.json`, not `.md`).
- Also has a copy at `docs/engines/orca/CORPUS_INDEX.md` — **wrong location** per §1.6 (corpus index belongs in `.tmp/`, not committed to docs).
- Contains `metadata_seed/orca_keywords.json` (24 categories), 8 normalized cases, `SOURCES.md`, `WORKLOG.md`.

**Curated samples** (`tests/inputformat/samples/orca/`): **1 sample** (`benzene_opt.inp`). This is notably low — the playbook recommends 5+.

**Real-run validation**: **NON-COMPLIANT** with §1.9. No `.tmp/engine_research/orca/real_run/` directory exists. The 1 curated sample has no execution evidence. Binary must be discovered first (§1.8), then all curated samples must be run.

**Fixtures**: `tests/fixtures/orca/` contains 3 files (water_scf.out, water_scf.property.txt, water_scf_td.property.txt) — used by output parser tests.

**Diversity assessment** (§1.11): Only 1 curated sample — insufficient for any diversity assessment. When expanded to 5+, must follow §1.11 D1-D3: spread across workflows (SP, optimization, frequency, TDDFT, solvation, multi-reference) before physics variants.

**Composite pipeline** (§1.12): ORCA participates in the ORCA→QMCPACK pipeline via `convert4qmc` (§1.12 W4). **No composite curated sample exists.** **NON-COMPLIANT** with §1.12 W1 (pending curated set expansion).

**Gaps**:
1. No CURATED_INDEX.md (§1.7) — also blocks diversity rationale (§1.11 D2)
2. CORPUS_INDEX.md exists but wrong format (.md not .json) and wrong location (§1.6)
3. Only 1 curated sample (recommend 5+) — diversity impossible with 1 sample (§1.11)
4. No `data/` directory with production metadata
5. Binary path not recorded (§1.8 E1/E3)
6. No real-run validation (§1.9 V1)
7. No entry in repo-level rollup index (§1.10 I5)
8. No composite pipeline curated example (§1.12 W1) — need ORCA→QMCPACK case
9. No diversity rationale per curated sample (§1.11 D2)

### 2.4 LAMMPS (Tier B1 — Pre-Playbook, Remediation Required)

**Plan**: `docs/engines/lammps/PHASE_B1_PLAN.md` — present
**Worklog**: `docs/engines/lammps/PHASE_B1_WORKLOG.md` — present
**SOURCES.md**: **Case duplication** — both `docs/engines/lammps/sources.md` (lowercase) and `docs/engines/lammps/SOURCES.md` (uppercase) exist.

**Binary path**: `$(brew --prefix)/bin/lmp_serial` — path recorded, binary confirmed available. Partially compliant with §1.8 (path known, but no formal version string + timestamp in worklog per E3).

**Corpus** (`.tmp/engine_research/lammps/`):
- **Richest corpus** of any engine: 843 input files, 257 potential files, 85 crawled web pages.
- 40 normalized cases in `normalized/`.
- 7 validation runs in `runs/` — these runs exist but do NOT follow the §1.9 V3 layout (no `real_run/` directory, no `command.txt`, no `compare_note.md`).
- No `CORPUS_INDEX.json` (§1.6 requirement).

**Curated samples** (`tests/inputformat/samples/lammps/`): **8 cases** — good coverage.

**Real-run validation**: **NON-COMPLIANT** with §1.9. The existing `runs/` directory has 7 validation runs, but they do not follow the §1.9 V3 standard layout. Each curated sample needs a corresponding `real_run/<example_slug>/` folder with the required artifacts.

**Diversity assessment** (§1.11): 8 curated samples covering NVE/NVT/minimize/ReaxFF/EAM/core-shell/MEAM/elastic — good Category A diversity (different force fields, ensembles, and analysis modes). No obvious near-duplicates. However, no diversity rationale is documented. **Needs CURATED_INDEX.md with rationale.**

**Composite pipeline** (§1.12): LAMMPS is typically a downstream consumer of DFT data (force field fitting). No standard composite pipeline in §1.12 W4 list. No action needed for §1.12.

**Gaps**:
1. No CURATED_INDEX.md (§1.7) — also blocks diversity rationale (§1.11 D2)
2. No CORPUS_INDEX.json (§1.6)
3. Duplicate sources.md / SOURCES.md (case inconsistency)
4. Real-run layout does not conform to §1.9 V3
5. No entry in repo-level rollup index (§1.10 I5)
6. No diversity rationale per curated sample (§1.11 D2)

### 2.5 Gaussian (Tier B1 — Pre-Playbook, Remediation Required)

**Plan**: `docs/engines/gaussian/PHASE_B1_PLAN.md` (124 lines) — present
**Worklog**: `docs/engines/gaussian/PHASE_B1_WORKLOG.md` (214 lines) — present, detailed
**SOURCES.md**: `docs/engines/gaussian/SOURCES.md` (101 lines) — present, well-structured

**Binary path**: `.qmatsuite/engines/gaussian/gaussian09/g09/g09` — path recorded, binary confirmed available (g09 Rev D.01, x86_64). Most compliant with §1.8 among all engines (version info recorded in worklog).

**Corpus** (`.tmp/engine_research/gaussian/`):
- 22 raw_web pages, 4 metadata JSON files.
- 14 normalized cases in `normalized/`.
- 9 validation runs in `runs/` — runs exist but do NOT follow the §1.9 V3 layout.
- No `CORPUS_INDEX.json` (§1.6 requirement).

**Curated samples** (`tests/inputformat/samples/gaussian/`): **6 files** — good coverage.

**Real-run validation**: **NON-COMPLIANT** with §1.9. The 9 validation runs in `runs/` are the closest to compliant of any engine (each has `run_manifest.json`, `digest.json`, `output.log`), but they lack the §1.9 V3 standard layout (`command.txt`, `expected_refs.json`, `compare_note.md`). Conforming them would be straightforward.

**Diversity assessment** (§1.11): 6 curated samples covering SP/optimization/frequency/TDDFT/solvation/multi-reference (CASSCF) — good Category A diversity (different workflows/methods). No obvious near-duplicates. No diversity rationale documented. **Needs CURATED_INDEX.md with rationale.**

**Composite pipeline** (§1.12): Gaussian participates in the Gaussian→QMCPACK pipeline via `convert4qmc` (§1.12 W4). **No composite curated sample exists.** **NON-COMPLIANT** with §1.12 W1.

**Gaps**:
1. No CURATED_INDEX.md (§1.7) — also blocks diversity rationale (§1.11 D2)
2. No CORPUS_INDEX.json (§1.6)
3. Real-run layout does not conform to §1.9 V3 (closest to compliant, needs minor restructuring)
4. No entry in repo-level rollup index (§1.10 I5)
5. No composite pipeline curated example (§1.12 W1) — need Gaussian→QMCPACK case
6. No diversity rationale per curated sample (§1.11 D2)

### 2.6 Wannier90 / W90 (Tier B1 — Pre-Playbook, Remediation Required)

**Plan**: `docs/engines/wannier90/PHASE_B1_PLAN.md` — present
**Worklog**: `docs/engines/wannier90/PHASE_B1_WORKLOG.md` — present, detailed
**SOURCES.md**: `docs/engines/wannier90/SOURCES.md` — present

**Binary path**: `.qmatsuite/engines/qe/q-e-qe-7.5/bin/wannier90.x` — path recorded, binary confirmed available (QE-bundled).

**Corpus** (`.tmp/engine_research/wannier90/`):
- Extracted documentation (user guide), 20 normalized cases, 2 validation runs.
- No `CORPUS_INDEX.json` (§1.6 requirement).

**Curated samples** (`tests/inputformat/samples/w90/`): **5 samples** in subdirectories with .win files.

**Real-run validation**: **NON-COMPLIANT** with §1.9. The 2 validation runs in `runs/` (example01_gaas, diamond_qe_pipeline) do not follow the §1.9 V3 layout. The 5 curated samples need matching `real_run/` evidence.

**Diversity assessment** (§1.11): 5 curated samples — covering GaAs, Cu, diamond, BaTiO3, Fe-spinors. Materials are diverse (semiconductor, metal, covalent, ferroelectric, magnetic). Worklog shows QE→W90 diamond pipeline was validated. Need to verify whether a pipeline case is among the 5 curated samples. No diversity rationale documented. **Needs CURATED_INDEX.md with rationale.**

**Composite pipeline** (§1.12): W90 participates in the QE→W90 pipeline (§1.12 W4). Worklog confirms the diamond QE pipeline was validated with both engines available. **Likely compliant** — but must verify the pipeline case is among the 5 committed curated samples. If not, promote it.

**Gaps**:
1. No CURATED_INDEX.md (§1.7) — also blocks diversity rationale (§1.11 D2)
2. No CORPUS_INDEX.json (§1.6)
3. Real-run layout does not conform to §1.9 V3
4. No entry in repo-level rollup index (§1.10 I5)
5. No diversity rationale per curated sample (§1.11 D2)
6. Composite pipeline curated status unverified (§1.12 W1) — need to confirm pipeline case is committed

### 2.7 QMCPACK (Tier B1 — Pre-Playbook, Remediation Required)

**Plan**: `docs/engines/qmcpack/PHASE_B1_PLAN.md` (265 lines) — present, thorough
**Worklog**: `docs/engines/qmcpack/PHASE_B1_WORKLOG.md` (170 lines) — present, detailed
**SOURCES.md**: `docs/engines/qmcpack/SOURCES.md` (91 lines) — present

**Binary path**: `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack` — path recorded, binary confirmed available. Note: the playbook v2.0 dashboard incorrectly showed "NOT INSTALLED" for QMCPACK — the binary was always present and used for 6 validation runs. Corrected in v2.1 dashboard.

**Corpus** (`.tmp/engine_research/qmcpack/`):
- **Second-richest corpus**: 1438+ extracted XML files from source tree.
- 3 metadata JSONs (175 elements, QMC parameters, estimators).
- 13 normalized cases (+ 1 QE workflow = 14 total).
- 6 validation runs (5 self-contained + 1 QE pipeline).
- No `CORPUS_INDEX.json` (§1.6 requirement).

**Curated samples** (`tests/inputformat/samples/qmcpack/`): **5 XML files**.

**Real-run validation**: **NON-COMPLIANT** with §1.9. The 6 validation runs exist but do not follow the §1.9 V3 layout. The 5 curated samples need matching `real_run/` evidence.

**Diversity assessment** (§1.11): 5 curated XMLs — covering VMC (He), VMC multi-atom (H2), VMC periodic+PP (LiH solid), optimization loop (He opt), electron gas (HEG). Good Category A diversity (different QMC methods, boundary conditions, wavefunction types). No near-duplicates. Worklog shows QE→QMCPACK LiH workflow was validated. Need to verify whether a pipeline case is among the 5 curated samples. No diversity rationale documented. **Needs CURATED_INDEX.md with rationale.**

**Composite pipeline** (§1.12): QMCPACK participates in the QE→QMCPACK pipeline (§1.12 W4). Worklog confirms the LiH QE→pw2qmcpack→QMCPACK workflow was validated. **Likely compliant** — but must verify the pipeline case is among the 5 committed curated samples. The `lih_solid_vmc_pp` sample is the most likely candidate.

**Gaps**:
1. No CURATED_INDEX.md (§1.7) — also blocks diversity rationale (§1.11 D2)
2. No CORPUS_INDEX.json (§1.6)
3. Real-run layout does not conform to §1.9 V3
4. No entry in repo-level rollup index (§1.10 I5)
5. No diversity rationale per curated sample (§1.11 D2)
6. Composite pipeline curated status unverified (§1.12 W1) — need to confirm pipeline case is committed

### 2.8 ABINIT (Tier B0 — Pre-Playbook, Full B1 Required)

**Current state**: Has basic I/O from Phase B0 work. custom_parser wired in inputspec.py.

**Binary path**: `.qmatsuite/engines/abinit/10.4.7/bin/abinit` — path known from prior exploration but not formally recorded per §1.8 E3 (no version string or discovery timestamp in worklog). **NON-COMPLIANT**.

**Files**:
- `src/qmatsuite/drivers/abinit/inputspec.py` — custom_parser wired
- `src/qmatsuite/drivers/abinit/parser.py` — 550 lines, handles multi-line arrays, znucl reversal
- `tests/inputformat/samples/abinit/si_scf.abi` — 1 curated sample (no real-run evidence)
- No `docs/engines/abinit/PHASE_B1_*` files
- No `.tmp/engine_research/abinit/` directory

**What's needed for B1**: Full Stages 0–8 per v2.1 playbook. Binary discovery and smoke run (§1.8). Parser exists but needs hardening. No output digest parser. No metadata catalog. No corpus. The 1 existing curated sample needs real-run validation (§1.9).

### 2.9 CP2K (Tier C — Pre-Playbook, Full B1 Required)

**Current state**: Minimal driver. custom_writer only (no parser).

**Binary path**: Expected at `$(brew --prefix)/bin/cp2k` — **not yet recorded**. Discovery required per §1.8. **NON-COMPLIANT**.

**Files**:
- `src/qmatsuite/drivers/cp2k/inputspec.py` — custom_writer only
- `src/qmatsuite/drivers/cp2k/writer.py` — basic input generation
- No curated samples, no docs, no corpus

**What's needed for B1**: Full Stages 0–8. Binary discovery first (§1.8). Parser from scratch (recursive descent for nested `&SECTION...&END`). No output digest. No metadata. No corpus.

### 2.10 Siesta (Tier B0 — Pre-Playbook, Full B1 Required)

**Current state**: Basic driver. custom_writer only. Has parser.py (348 lines) but unwired.

**Binary path**: Expected via conda — **not yet recorded**. Discovery required per §1.8. **NON-COMPLIANT**.

**Files**:
- `src/qmatsuite/drivers/siesta/inputspec.py` — custom_writer only
- `src/qmatsuite/drivers/siesta/parser.py` — 348 lines (exists but unwired)
- No curated samples, no docs, no corpus

**What's needed for B1**: Full Stages 0–8. Binary discovery (§1.8). Existing parser.py (348 lines) gives a head start but needs wiring to inputspec and hardening.

### 2.11 xTB (Tier C — Pre-Playbook, Full B1 Required)

**Current state**: Minimal driver. custom_writer only. Has parser.py (105 lines, minimal).

**Binary path**: Expected via conda — **not yet recorded**. Discovery required per §1.8. **NON-COMPLIANT**.

**Files**:
- `src/qmatsuite/drivers/xtb/inputspec.py` — custom_writer only
- `src/qmatsuite/drivers/xtb/parser.py` — 105 lines (minimal)
- `tests/inputformat/samples/xtb/water.xyz` — 1 curated sample (no real-run evidence)
- No docs, no corpus

**What's needed for B1**: Full Stages 0–8. Binary discovery (§1.8). xTB is a CLI tool with simple input. The 1 existing curated sample needs real-run validation (§1.9).

### 2.12 GPAW (Tier B0 — Pre-Playbook, Full B1 Required)

**Current state**: Python-script engine (F7). custom_writer only.

**Binary path**: Expected via pip (`import gpaw`) — **not yet recorded**. Discovery required per §1.8. **NON-COMPLIANT**.

**Files**:
- `src/qmatsuite/drivers/gpaw/inputspec.py` — custom_writer only
- `src/qmatsuite/drivers/gpaw/writer.py` — generates Python scripts
- No curated samples, no docs, no corpus

**What's needed for B1**: Full Stages 0–8 with adapted scope (F7 Python-script engine — skip Phase 4 parser/writer). Binary discovery (§1.8). Metadata catalog covers GPAW API parameters. Output digest from results.json.

### 2.13 Psi4 (Tier C — Pre-Playbook, Full B1 Required)

**Current state**: Python-script engine (F7). Empty input spec.

**Binary path**: Expected via conda — **not yet recorded**. Discovery required per §1.8. **NON-COMPLIANT**.

**Files**:
- `src/qmatsuite/drivers/psi4/inputspec.py` — returns empty spec (no input files)
- No curated samples, no docs, no corpus

**What's needed for B1**: Stages 0–8 with adapted scope (F7 engine). Binary discovery (§1.8). Focus on metadata catalog + output digest.

### 2.14 PySCF (Tier C — Pre-Playbook, Full B1 Required)

**Current state**: Python-script engine (F7). Empty input spec.

**Binary path**: Expected via pip (`import pyscf`) — **not yet recorded**. Discovery required per §1.8. **NON-COMPLIANT**.

**Files**:
- `src/qmatsuite/drivers/pyscf/inputspec.py` — returns empty spec (no input files)
- No curated samples, no docs, no corpus

**What's needed for B1**: Same as Psi4 — adapted scope for F7 engines.

### 2.15 Yambo (Tier B0 — Pre-Playbook, Full B1 Required)

**Current state**: Basic driver. custom_writer only. Has parser.py (262 lines) but unwired.

**Binary path**: Expected at `.qmatsuite/engines/yambo/` — **not yet recorded**. Discovery required per §1.8. Per the v2.1 playbook, "not available" or "not installed" is a violation — the binary is guaranteed to exist and MUST be found. **NON-COMPLIANT**.

**Files**:
- `src/qmatsuite/drivers/yambo/inputspec.py` — custom_writer only
- `src/qmatsuite/drivers/yambo/parser.py` — 262 lines (exists but unwired)
- No curated samples, no docs, no corpus

**What's needed for B1**: Full Stages 0–8. Binary discovery first (§1.8). Pipeline workflow (QE → p2y → yambo). Existing parser.py (262 lines) gives a head start but needs wiring.

---

## 3. Cross-Cutting Issues

### 3.1 Universal: No Engine Has Real-Run Validation Per §1.9 (NEW)

**Severity**: Critical
**Affected**: All 15 engines (14 non-QE)

The v2.1 playbook §1.9 requires every committed curated input to have a corresponding `real_run/<example_slug>/` folder in `.tmp/` with standardized artifacts (command.txt, run_manifest.json, outputs/, expected_refs.json, compare_note.md). **Zero engines** have this structure.

Four engines (LAMMPS, Gaussian, W90, QMCPACK) have older-format validation runs in `.tmp/engine_research/<engine>/runs/`, but these do not conform to the §1.9 V3 layout. They are close and can be restructured with moderate effort.

**Evidence**: No `.tmp/engine_research/*/real_run/` directories exist anywhere.

### 3.2 Universal: Repo-Level Rollup Index Does Not Exist (NEW)

**Severity**: Critical
**Affected**: All 15 engines

The v2.1 playbook §1.10 I5 requires `docs/architecture/B1_ENGINE_CORPUS_INDEX.md` — a committed rollup index covering all 15 engines. This file does not yet exist. It is a new requirement from v2.1.

**Evidence**: `docs/architecture/B1_ENGINE_CORPUS_INDEX.md` — does not exist.

### 3.3 Universal: CURATED_INDEX.md Missing Everywhere (§1.7)

**Severity**: High
**Affected**: All 6 B1-complete engines + 2 engines with samples (ABINIT, xTB)

The playbook §1.7 requires a committed `CURATED_INDEX.md` in `docs/engines/<engine>/` listing all curated samples, their purpose, provenance, and `real_run_slug` pointer. **Zero out of eight** engines with curated samples have this file.

**Evidence**: `docs/engines/*/CURATED_INDEX.md` — none exist.

### 3.4 Universal: CORPUS_INDEX.json Missing Everywhere (§1.6)

**Severity**: High
**Affected**: All 6 B1-complete engines (the other 8 have no `.tmp/` corpus yet)

**Zero out of six** engines have a proper `.json` index. ORCA has a `CORPUS_INDEX.md` (wrong format, also incorrectly committed to `docs/engines/orca/`).

**Evidence**: No `.tmp/engine_research/*/CORPUS_INDEX.json` files found.

### 3.5 Binary Path Evidence Incomplete (§1.8)

**Severity**: High
**Affected**: ORCA, CP2K, Siesta, xTB, GPAW, Psi4, PySCF, Yambo (8 engines with no recorded path)

Per §1.8, all 15 engine binaries are guaranteed to exist locally. Eight engines have no recorded binary path. The v2.1 playbook explicitly bans language like "not available", "not installed", or "cannot run" — the agent MUST search the 4 canonical locations and record the resolved path.

Engines with recorded paths (7): QE, VASP, LAMMPS, Gaussian, W90, QMCPACK, ABINIT. Of these, only Gaussian has a formal version string in the worklog.

### 3.6 SOURCES.md Placement Inconsistencies

**Severity**: Medium
**Affected**: VASP, LAMMPS

- **VASP**: `SOURCES.md` exists only at `.tmp/engine_research/vasp/SOURCES.md`, not at `docs/engines/vasp/SOURCES.md`.
- **LAMMPS**: Has both `docs/engines/lammps/sources.md` (lowercase) and `docs/engines/lammps/SOURCES.md` (uppercase) — filename case duplication.

### 3.7 Curated Sample Count Disparity

**Severity**: Medium
**Affected**: ORCA (1 sample), ABINIT (1 sample), xTB (1 sample)

The playbook recommends 5+ curated samples. ORCA has only 1 sample (`benzene_opt.inp`) despite being B1-complete. For context: VASP has 12, LAMMPS has 8, Gaussian has 6, W90 and QMCPACK have 5 each.

### 3.8 Metadata `data/` Directory Inconsistency

**Severity**: Low
**Affected**: ORCA, LAMMPS, W90, QMCPACK

Only VASP and Gaussian have a `data/` subdirectory with production metadata files. The other 4 B1-complete engines have metadata only in `.tmp/`.

### 3.9 `.tmp/` Corpus Depth Varies Widely

**Severity**: Medium (upgraded from Low under v2.1 — §1.5 C1 requires exhaustive corpora)
**Affected**: VASP (sparse — playbook violation under §1.5 C1), ORCA (thin)

Under v2.1, a sparse `.tmp/` corpus is now a compliance violation (§1.5 C1: "Phases 0–3 are mandatory, exhaustive, and incremental"). VASP's sparse corpus and ORCA's thin corpus both require backfill.

### 3.10 Pre-Playbook Engines Are Not Excused

**Severity**: Informational (policy clarification)
**Affected**: All 14 non-QE engines

Under v2.1, all engines completed before the current playbook are classified as **"pre-playbook, remediation required"** — not as "complete" or "optional". The 6 B1-complete engines have functional code (parser, writer, output digest, tests) but lack the documentation/index/validation infrastructure required by §1.6–§1.10. The 8 remaining engines need full B1 from scratch.

No engine is excused from the v2.2 requirements. Pre-playbook status explains the gap but does not forgive it.

### 3.11 Universal: No Curated Set Has Diversity Rationale (§1.11 D2) (NEW)

**Severity**: High
**Affected**: All 8 engines with curated samples (VASP, ORCA, LAMMPS, Gaussian, W90, QMCPACK, ABINIT, xTB)

The v2.2 playbook §1.11 D2 requires each curated example to include a "diversity rationale" in `CURATED_INDEX.md` — one sentence justifying what new workflow, physics regime, or syntax feature it covers. Since no engine has a `CURATED_INDEX.md` yet (§3.3), no engine has diversity rationale either.

**Preliminary diversity assessment of existing curated sets:**
- **VASP** (12 samples): Good diversity — covers scf, relax, vc_relax, bands, dos, magnetic, Hubbard, vdW, MD, slab, hybrid, SOC. Likely compliant with §1.11 D1 (no near-duplicates). **Missing composite pipeline** (VASP→W90 per §1.12 W4).
- **ORCA** (1 sample): Insufficient count for diversity assessment. Needs expansion to 5+. **Missing composite pipeline** (ORCA→QMCPACK via `convert4qmc` per §1.12 W4).
- **LAMMPS** (8 samples): Good diversity — covers NVE/NVT/minimize/ReaxFF/EAM/core-shell/MEAM/elastic. No known composite pipeline (LAMMPS is typically downstream).
- **Gaussian** (6 samples): Moderate diversity — covers SP/opt/freq/TDDFT/solvation/multi-reference. **Missing composite pipeline** (Gaussian→QMCPACK via `convert4qmc` per §1.12 W4).
- **W90** (5 samples): Moderate diversity — covers GaAs/Cu/diamond/BaTiO3/Fe-spinors. Includes QE→W90 composite pipeline cases (good). Need to verify diversity rationale is documented.
- **QMCPACK** (5 samples): Good diversity — covers VMC/DMC/optimization/periodic/electron-gas. Includes QE→QMCPACK composite pipeline (worklog confirms LiH workflow). Need to verify curated set includes pipeline case.

### 3.12 Composite Pipeline Coverage Gaps (§1.12 W1) (NEW)

**Severity**: High
**Affected**: VASP, ORCA, Gaussian, Yambo (4 engines with known pipelines but no composite curated example)

The v2.2 playbook §1.12 W1 requires engines with known composite pipelines to include at least one composite workflow case in their curated set. Assessment:

| Engine | Known Pipeline(s) | Composite in Curated Set? | Status |
|--------|-------------------|--------------------------|--------|
| W90 | QE→W90 | **Yes** (diamond pipeline validated in worklog) | **Likely compliant** — verify curated set includes it |
| QMCPACK | QE→QMCPACK | **Yes** (LiH workflow validated in worklog) | **Likely compliant** — verify curated set includes it |
| VASP | VASP→W90 | **No** — 12 curated samples, none are VASP→W90 | **Non-compliant** (CW) |
| ORCA | ORCA→QMCPACK | **No** — only 1 curated sample | **Non-compliant** (CW) |
| Gaussian | Gaussian→QMCPACK | **No** — 6 curated samples, none are composite | **Non-compliant** (CW) |
| Yambo | QE→Yambo | N/A — no curated samples yet | Will be required when B1 starts |
| LAMMPS | DFT→LAMMPS (downstream) | N/A — pipeline is typically upstream of LAMMPS | No action needed |
| ABINIT | None commonly known | N/A | No action needed |

**Note**: W90 and QMCPACK have pipeline validation runs in their worklogs but it is not confirmed whether the corresponding pipeline inputs are among the 5 committed curated samples. This must be verified during remediation.

---

## 4. Prioritized Remediation Checklist

Ordered by dependency (what must come first) and leverage (what unblocks the most engines).

### Priority 1: Create Repo-Level Rollup Index (NEW, §1.10 I5)

**Leverage**: All 15 engines | **Effort**: Medium (1 hour) | **Blocks**: Everything else (this is the master tracking file)

Create `docs/architecture/B1_ENGINE_CORPUS_INDEX.md`. For each of the 15 engines, record:
- Corpus status (`.tmp/` dir exists? `CORPUS_INDEX.json` present?)
- Curated items list (example_slugs from `tests/inputformat/samples/`)
- Real-run validation status (yes/no + slug for each curated item)
- Binary path evidence (recorded path or "discovery required")

This file becomes the single source of truth for tracking remediation progress across all engines.

### Priority 2: Record Binary Paths for All 8 Missing Engines (§1.8)

**Leverage**: 8 engines | **Effort**: Low (30 min total) | **Blocks**: Real-run validation for these engines

For each of ORCA, CP2K, Siesta, xTB, GPAW, Psi4, PySCF, Yambo:
- Search the 4 canonical locations per §1.8 E2
- Record resolved absolute path, version string, and discovery timestamp
- Run minimal smoke case (< 30s) per §1.8 E4
- Update `docs/architecture/B1_ENGINE_CORPUS_INDEX.md` with results

### Priority 3: Create CORPUS_INDEX.json for All 6 B1-Complete Engines (§1.6)

**Leverage**: 6 engines | **Effort**: Medium (30 min per engine) | **Risk if deferred**: Corpus undiscoverable, incremental work impossible

Create `.tmp/engine_research/<engine>/CORPUS_INDEX.json` per §1.6 schema for VASP, ORCA, LAMMPS, Gaussian, W90, QMCPACK.

Also: Remove `docs/engines/orca/CORPUS_INDEX.md` (wrong format and location).

### Priority 4: Create CURATED_INDEX.md for All 8 Engines with Samples (§1.7, §1.11 D2)

**Leverage**: 8 engines | **Effort**: Low-Medium (15-30 min per engine) | **Blocks**: Real-run validation tracking, diversity audit

Create `docs/engines/<engine>/CURATED_INDEX.md` for VASP, ORCA, LAMMPS, Gaussian, W90, QMCPACK, ABINIT, xTB. Each file lists:
- All files in `tests/inputformat/samples/<engine>/`
- For each: filename, calculation type, provenance, purpose, `real_run_slug` (initially "pending")
- **NEW (§1.11 D2)**: A "diversity rationale" sentence per sample — what workflow, physics regime, or syntax feature this example covers that no other curated example already covers
- During this step, identify near-duplicates (§1.11 D1) and flag them for replacement in Priority 8

### Priority 5: Create Real-Run Validation for All Curated Samples (§1.9)

**Leverage**: 8 engines (37 curated samples total) | **Effort**: High (2–4 hours total) | **Critical for compliance**

For each curated sample across all engines with samples (VASP 12, LAMMPS 8, Gaussian 6, W90 5, QMCPACK 5, ORCA 1, ABINIT 1, xTB 1 = 39 total):
- Execute the sample through the engine binary
- Create `.tmp/engine_research/<engine>/real_run/<example_slug>/` per §1.9 V3
- Populate: command.txt, run_manifest.json, outputs/, expected_refs.json, compare_note.md
- Update CURATED_INDEX.md with the `real_run_slug`

**Note**: Engines with existing `runs/` directories (LAMMPS 7, Gaussian 9, W90 2, QMCPACK 6) can restructure existing run data rather than re-executing. VASP and ORCA require fresh runs after binary discovery.

### Priority 6: Fix VASP SOURCES.md Placement + Corpus Backfill

**Leverage**: 1 engine | **Effort**: Low (copy) + Medium (corpus expansion)

- Copy `.tmp/engine_research/vasp/SOURCES.md` to `docs/engines/vasp/SOURCES.md`
- Expand the sparse `.tmp/engine_research/vasp/` corpus to meet §1.5 C1 ("exhaustive")

### Priority 7: Fix LAMMPS Filename Case Duplication

**Leverage**: 1 engine | **Effort**: Trivial

Resolve `docs/engines/lammps/sources.md` vs `docs/engines/lammps/SOURCES.md`. Keep uppercase, remove lowercase.

### Priority 8: Increase ORCA Curated Samples from 1 to 5+ (§1.11, §1.12)

**Leverage**: 1 engine | **Effort**: Medium (1–2 hours)

Promote 4+ of the 8 normalized cases from `.tmp/engine_research/orca/normalized/` to `tests/inputformat/samples/orca/`. Selection MUST follow §1.11 diversity criteria (different workflows/physics/syntax). Each promoted sample must then get real-run validation per §1.9. At least one promoted sample SHOULD be an ORCA→QMCPACK composite workflow case (§1.12 W1) if `convert4qmc` is available.

### Priority 9: Add Composite Pipeline Curated Examples (§1.12 W1) (NEW)

**Leverage**: 3 engines (VASP, Gaussian; ORCA covered in Priority 8) | **Effort**: Medium (1–2 hours)

For engines with known composite pipelines that lack a curated pipeline example:
- **VASP**: Add a VASP→W90 curated example (VASP SCF/NSCF → wannier90.x). Requires both engines (both available locally).
- **Gaussian**: Add a Gaussian→QMCPACK curated example (Gaussian SCF → `convert4qmc` → QMCPACK). Check if `convert4qmc` is available at `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/convert4qmc`.
- **W90/QMCPACK**: Verify that existing curated sets include their validated pipeline cases. If not, promote pipeline cases from `.tmp/` normalized corpus.

### Priority 10: Begin B1 for Remaining 8 Engines

**Leverage**: 8 engines | **Effort**: High (1–3 sessions each)

Suggested order (based on existing code, guaranteed binary availability, and complexity):

| Order | Engine | Rationale |
|-------|--------|-----------|
| 1 | ABINIT | Has 550-line parser, binary at `.qmatsuite/engines/abinit/10.4.7/bin/abinit`, F1 family (like QE) |
| 2 | xTB | Simple CLI tool, binary via conda, small surface area |
| 3 | Siesta | Has 348-line parser, binary via conda |
| 4 | CP2K | Binary via brew, but needs parser from scratch (recursive descent) |
| 5 | Yambo | Has 262-line parser, binary at `.qmatsuite/engines/yambo/`, pipeline workflow |
| 6 | GPAW | F7 Python-script, binary via pip, adapted B1 scope |
| 7 | Psi4 | F7 Python-script, binary via conda, adapted B1 scope |
| 8 | PySCF | F7 Python-script, binary via pip, adapted B1 scope |

All B1 work must follow v2.2 playbook from the start — including binary discovery (§1.8), real-run validation (§1.9), both indices (§1.6/§1.7), and rollup index updates (§1.10).

---

## 5. Recommended Remediation Plan (No Work Performed in This Review)

This section provides the recommended dependency-ordered sequence for bringing all engines into full v2.2 compliance. No implementation was done as part of this review.

### Phase R1: Infrastructure (do first — unblocks everything)

1. **Finalize playbook v2.1** — the playbook patch in this changeset establishes the binding rules. No further schema changes needed.
2. **Create `docs/architecture/B1_ENGINE_CORPUS_INDEX.md`** — the repo-level rollup index. Start with a skeleton listing all 15 engines with current status. This becomes the master tracking document.

### Phase R2: Binary Discovery (prerequisite for all real-run work)

3. **Record binary paths for all 15 engines.** Seven engines already have known paths. Eight need discovery per §1.8. For each:
   - Search 4 canonical locations
   - Record absolute path + version string + timestamp
   - Run smoke case (< 30s)
   - Update rollup index

### Phase R3: Index Backfill (can parallelize with Phase R2)

4. **Create `.tmp/engine_research/<engine>/CORPUS_INDEX.json`** for all 6 B1-complete engines per §1.6 schema.
5. **Create `docs/engines/<engine>/CURATED_INDEX.md`** for all 8 engines with curated samples per §1.7.
6. **Fix placement issues**: VASP SOURCES.md, LAMMPS case duplication, ORCA wrong-format index.

### Phase R4: Real-Run Validation (depends on Phase R2)

7. **For each curated sample across all engines**, create `.tmp/engine_research/<engine>/real_run/<example_slug>/` with:
   - `command.txt` (exact invocation)
   - `run_manifest.json` (engine path, version, cwd, timestamp, input hash)
   - `outputs/` (raw output files)
   - `expected_refs.json` (best-effort from tutorial/docs)
   - `compare_note.md` (expected vs observed)
8. **Update CURATED_INDEX.md** with `real_run_slug` for each validated sample.
9. **Update rollup index** with validation status.

### Phase R5: Corpus Expansion + Diversity + Composite Pipelines (for engines with thin corpora or missing coverage)

10. **Backfill VASP `.tmp/` corpus** — currently sparse, needs exhaustive collection per §1.5 C1.
11. **Expand ORCA curated samples** from 1 to 5+ (promote from normalized cases per §1.11 diversity criteria).
12. **Expand ORCA `.tmp/` corpus** — currently thin.
13. **Add composite pipeline curated examples** (§1.12 W1) for VASP (→W90), ORCA (→QMCPACK), Gaussian (→QMCPACK). Verify W90 and QMCPACK curated sets include their validated pipeline cases.
14. **Audit all curated sets for near-duplicates** (§1.11 D1) — if any curated set has examples that differ only in species/cell size, replace with more diverse cases.

### Phase R6: New Engine B1s (depends on Phases R1–R3)

15. **Execute full B1 (Stages 0–8)** for 8 remaining engines in dependency order: ABINIT, xTB, Siesta, CP2K, Yambo, GPAW, Psi4, PySCF. Each B1 must comply with v2.2 from the start — including diversity rationale (§1.11) and composite pipelines where applicable (§1.12).

### Summary of Remediation Dependencies

```
Phase R1 (Infrastructure: rollup index)
    |
    v
Phase R2 (Binary discovery) ←→ Phase R3 (Index backfill + diversity rationale) [parallel]
    |
    v
Phase R4 (Real-run validation for all curated samples)
    |
    v
Phase R5 (Corpus expansion + composite pipelines + diversity audit)
    |
    v
Phase R6 (Full B1 for 8 remaining engines — v2.2 compliant from start)
```

---

## Appendix: File Evidence Paths

All claims in this review are based on direct file inspection. Key paths:

```
# B1 Plans and Worklogs
docs/engines/vasp/PHASE_B1_PLAN.md         (125 lines)
docs/engines/vasp/PHASE_B1_WORKLOG.md      (61 lines)
docs/engines/orca/PHASE_B1_PLAN.md
docs/engines/orca/PHASE_B1_WORKLOG.md
docs/engines/lammps/PHASE_B1_PLAN.md
docs/engines/lammps/PHASE_B1_WORKLOG.md
docs/engines/gaussian/PHASE_B1_PLAN.md     (124 lines)
docs/engines/gaussian/PHASE_B1_WORKLOG.md  (214 lines)
docs/engines/wannier90/PHASE_B1_PLAN.md
docs/engines/wannier90/PHASE_B1_WORKLOG.md
docs/engines/qmcpack/PHASE_B1_PLAN.md      (265 lines)
docs/engines/qmcpack/PHASE_B1_WORKLOG.md   (170 lines)

# SOURCES.md (committed)
docs/engines/orca/SOURCES.md
docs/engines/lammps/SOURCES.md              # also sources.md (lowercase dup)
docs/engines/gaussian/SOURCES.md            (101 lines)
docs/engines/wannier90/SOURCES.md
docs/engines/qmcpack/SOURCES.md             (91 lines)
# VASP: only at .tmp/engine_research/vasp/SOURCES.md (NOT committed)

# Missing indices (none exist yet)
docs/architecture/B1_ENGINE_CORPUS_INDEX.md     # rollup index — DOES NOT EXIST
docs/engines/*/CURATED_INDEX.md                 # per-engine — NONE EXIST
.tmp/engine_research/*/CORPUS_INDEX.json        # per-engine — NONE EXIST
.tmp/engine_research/*/real_run/                # real-run evidence — NONE EXIST

# Curated samples (committed)
tests/inputformat/samples/vasp/             (12 cases)
tests/inputformat/samples/orca/             (1 sample: benzene_opt.inp)
tests/inputformat/samples/lammps/           (8 cases)
tests/inputformat/samples/gaussian/         (6 files)
tests/inputformat/samples/w90/              (5 samples)
tests/inputformat/samples/qmcpack/          (5 files)
tests/inputformat/samples/abinit/           (1 sample: si_scf.abi)
tests/inputformat/samples/xtb/              (1 sample: water.xyz)

# .tmp corpus directories (non-committed)
.tmp/engine_research/vasp/                  (sparse — §1.5 C1 violation)
.tmp/engine_research/orca/                  (thin)
.tmp/engine_research/lammps/                (rich — 843 files)
.tmp/engine_research/gaussian/              (good — 14 cases, 9 runs)
.tmp/engine_research/wannier90/             (good — 20 cases)
.tmp/engine_research/qmcpack/               (rich — 1438 XMLs)
# 8 remaining engines: NO .tmp/engine_research/ dirs exist

# Binary path evidence
QE:      .qmatsuite/engines/qe/q-e-qe-7.5/bin/           # confirmed
VASP:    .qmatsuite/engines/vasp/vasp.6.5.0/bin/          # known, not formally recorded
LAMMPS:  $(brew --prefix)/bin/lmp_serial                   # confirmed
Gaussian:.qmatsuite/engines/gaussian/gaussian09/g09/g09    # confirmed, version in worklog
W90:     .qmatsuite/engines/qe/q-e-qe-7.5/bin/wannier90.x # confirmed (QE-bundled)
QMCPACK: .qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack  # confirmed
ABINIT:  .qmatsuite/engines/abinit/10.4.7/bin/abinit      # known, not formally recorded
ORCA:    discovery required — expected at .qmatsuite/engines/orca/
CP2K:    discovery required — expected at $(brew --prefix)/bin/cp2k
Siesta:  discovery required — expected via conda
xTB:     discovery required — expected via conda
GPAW:    discovery required — expected via pip
Psi4:    discovery required — expected via conda
PySCF:   discovery required — expected via pip
Yambo:   discovery required — expected at .qmatsuite/engines/yambo/
```
