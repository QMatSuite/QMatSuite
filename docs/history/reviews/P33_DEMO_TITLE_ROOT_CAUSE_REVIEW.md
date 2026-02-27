# P33 Root Cause Review: Demo Titles and Step Paths

**Date**: 2026-02-27
**Scope**: Deep investigation of P33 ("Demo '0 Si SCF' Step Detail Fails to Load")
**Status**: Review only — no code or data changes

---

## Executive Summary

P33 is two bugs sharing the same origin:
1. **Bad titles** — "0 Si Scf", "3 Si Vc Relax", etc. (cosmetic)
2. **Malformed step paths** — flat `si.scf.step.yaml` instead of canonical `calculations/<calc>/steps/<step>.step.yaml` (functional failure)

Both bugs entered through `tools/import_tutorial_datasets.py`, were baked into the corpus by `tools/demo_store/create_qe_corpus.py`, and survive re-generation because `generate_all.py`'s "preserve existing" strategy copies the old demo wholesale instead of regenerating through the translator.

Dev testing missed it because no test validates title format or step path canonicality. The functional failure only manifests through the GUI's step detail resolution — a code path no backend test exercises.

---

## Demo Store Pipeline Overview

Understanding P33 requires understanding the full demo store pipeline — a 6-stage system that goes far beyond "generate YAML from corpus". The pipeline generates demos, runs them on real engines, captures analysis outputs as reference packs, and validates everything end-to-end.

### Architecture Diagram

```
Stage 1: CORPUS (Layer 1)                    Stage 2: GENERATION (Layer 1 → Layer 2)
─────────────────────────────                ────────────────────────────────────────
tests/inputformat/samples/                   tools/demo_store/generate_all.py
  <engine>/<case>/                             ├─ Strategy 1: preserve existing demo
    case.yaml          ──────────────────────→ ├─ Strategy 2: direct_snapshot (Python engines)
    *.inp, *.abi, etc.                         └─ Strategy 3: full translator pipeline
    corpus_index.yaml (124 entries)                    │
                                                       ↓
                                               resources/demo_projects/
                                                 52× <demo_slug>.yml
                                                 .generator_manifest.json

Stage 3: COMPILATION & REPLAY               Stage 4: REAL-RUN + REF PACK CAPTURE
────────────────────────────────             ────────────────────────────────────────
demo_store/compiler.py                       tools/demo_store/generate_ref_packs_realrun.py
  snapshot → AuthoringOps IR                   ├─ QMSService.create_demo_project()
    (InitProject, ImportStructure,             ├─ svc.run.run_calculation()  (real engine)
     CreateCalculation, AddStep,               ├─ svc.analysis.get_analysis()
     SetField × N, ConfigureSpeciesMap)        └─ write ref_packs/<slug>/{manifest,*.json}
            │                                          │
            ↓                                          ↓
demo_store/replay.py                         resources/demo_projects/ref_packs/
  ops → QMSService calls                       52 directories, 124 JSON files
  → Live project on disk                       (convergence, bands, dos, trajectory, field3d)

Stage 5: ROUNDTRIP VERIFICATION              Stage 6: ANALYSIS RESWEEP
────────────────────────────────             ────────────────────────────────────────
demo_store/roundtrip.py                      tools/demo_store/analysis_resweep.py
  Original snapshot                            Re-parse preserved workdirs
    → compile → replay → re-export             Expected analysis count vs actual
    → canonicalize (strip ULIDs, managed keys) Coverage report per engine/demo
    → deep diff ≈ original                     .tmp/analysis_resweep_results.json
```

### Stage-by-Stage Detail

**Stage 1 — Corpus (Layer 1)**: 124 corpus cases across 15 engines at `tests/inputformat/samples/`. Each case has a `case.yaml` (title, description, step types, demo eligibility) and raw engine input files. 52 cases are `demo_eligible: true` and have a `demo_slug`. The `corpus_index.yaml` is the authoritative index. Governed by `docs/laws/L2/DEMO_STORE_SPEC.md`.

**Stage 2 — Generation (Layer 1 → Layer 2)**: `generate_all.py` reads the corpus index, selects eligible cases, and produces 52 demo YAML snapshots. Each snapshot is a complete `ProjectSnapshot` containing project metadata, structures (lattice/species/coordinates), calculations (step sequences, parameters), pseudo info, and gallery metadata (title, subtitle, difficulty, tags). ULIDs are deterministic (SHA-256 seeded from demo_slug). A `.generator_manifest.json` tracks checksums for idempotency verification.

**Stage 3 — Compilation & Replay**: The compiler (`compiler.py`) breaks a snapshot into fine-grained `AuthoringOp` instructions — one per scalar leaf parameter. 8 op types: `InitProject`, `ImportStructure`, `CreateCalculation`, `AddStep`, `SetField`, `UnsetField`, `ReplaceMap`, `ConfigureSpeciesMap`. The replayer (`replay.py`) executes these ops via `QMSService` methods — the same API endpoints the GUI uses. This validates that every demo can be reconstructed through the public API, not just by unpacking YAML.

**Stage 4 — Real-Run + Ref Pack Capture**: `generate_ref_packs_realrun.py` materializes all 52 demos, runs them on real engine binaries (QE 7.5, VASP 6.5.0, ABINIT 10.4.7, CP2K 2026.1, ORCA 6.1.1, etc.), parses the outputs, and serializes analysis results as `CanonicalPrimitiveBundle` JSON files. Each ref pack directory has a `manifest.json` with SHA-256 checksums per analysis type. This is the most expensive stage (~15 min total, all 52 demos).

**Stage 5 — Roundtrip Verification**: `roundtrip.py` verifies that `snapshot → compile → replay → re-export → canonicalize ≈ original`. Canonicalization strips ULIDs, paths, timestamps, and engine-specific managed keys (QE: `outdir`, `pseudo_dir`, `prefix`, `restart_mode`, `wfcdir`; VASP: `SYSTEM`; CP2K: `PROJECT_NAME`; Siesta: `SystemLabel`). Differences are reported with JSON pointer paths.

**Stage 6 — Analysis Resweep**: `analysis_resweep.py` re-runs analysis providers over preserved workdirs (from Stage 4) and compares expected vs actual analysis type counts. Each engine's driver declares `ANALYSIS_CAPABILITIES`; the resweep validates that the parser actually produces all expected analysis types. Reports coverage gaps, parser failures, and missing evidence files.

### Current Statistics (as of 2026-02-20 audit)

| Metric | Value |
|--------|-------|
| **Layer 1 — Corpus** | |
| Total corpus cases indexed | 124 |
| Demo-eligible cases | 52 |
| Engines with corpus cases | 15 |
| Engines with 0 standalone demos | 2 (Yambo, W90 — require prior DFT data) |
| **Layer 2 — Demo Snapshots** | |
| Total demo .yml files | 52 |
| Generator version | 1.0.0 |
| Manifest checksum coverage | 52/52 (100%) |
| **Ref Packs** | |
| Total ref pack directories | 52 |
| Total analysis JSON files | 72 (excluding 52 manifests) |
| Ref pack generator version | 3.0.0 (realrun) |
| **Analysis Coverage by Type** | |
| Convergence | 44/52 demos (85%) |
| Trajectory | 13/52 demos (25%) |
| Bands | 7/52 demos (13%) |
| DOS | 4/52 demos (8%) |
| Field3D | 4/52 demos (8%) — VASP only |
| **Real-Run Results (Feb 20)** | |
| Demos executed | 52/52 (100% success) |
| Run failures | 0 |
| Timeout candidates (>10 min) | 0 |
| Slowest demo | cp2k_h2o_geo_opt (171.8s) |
| **Demo Distribution by Engine** | |
| QE | 15 demos (29%) |
| VASP | 5 demos (10%) |
| ABINIT, CP2K, Gaussian, GPAW, LAMMPS, ORCA, Psi4, PySCF, Siesta, xTB | 3 each (6%) |
| QMCPACK | 2 demos (4%) |
| Yambo, W90 | 0 demos (only reachable via QE composite workflows) |

### Ref Pack Coverage Matrix

Engines with richest analysis coverage:

| Engine | Demos | Convergence | Bands | DOS | Trajectory | Field3D |
|--------|:-----:|:-----------:|:-----:|:---:|:----------:|:-------:|
| VASP | 5 | 5 | 1 | 1 | 1 | 4 |
| QE | 15 | 11 | 2 | 2 | 1 | — |
| ABINIT | 3 | 2 | 1 | — | 1 | — |
| CP2K | 3 | 3 | — | — | 2 | — |
| Siesta | 3 | 2 | 1 | — | 1 | — |
| GPAW | 3 | 3 | 1 | — | — | — |
| Gaussian | 3 | 3 | — | — | 1 | — |
| LAMMPS | 3 | — | — | — | 3 | — |
| xTB | 3 | — | — | — | 3 | — |
| ORCA | 3 | 3 | — | — | — | — |
| Psi4 | 3 | 3 | — | — | — | — |
| PySCF | 3 | 3 | — | — | — | — |
| QMCPACK | 2 | 2 | — | — | — | — |

### Gate Tests Enforcing the Pipeline

| Gate Test | What It Enforces |
|-----------|-----------------|
| `tests/gates/test_demo_generated.py` | All 52 demos have manifest entries; checksums match files |
| `tests/gates/test_corpus_index.py` | Corpus/index agreement; slug uniqueness; redistributable assets present |
| `tests/gates/test_demo_integrity.py` | All demos have `engine_family`; `step_type_spec` prefix matches engine |
| `tests/gates/test_ref_packs.py` | Ref pack manifests valid JSON; all files exist; SHA-256 checksums match |
| `tests/integrity/backend/test_demo_lifecycle.py` | Demos load as ProjectSnapshot; materialize; gallery metadata exists |

### Governance Rules (from `DEMO_STORE_SPEC.md`)

- **Single writer**: Only `generate_all.py` writes to `resources/demo_projects/` — no hand-editing Layer 2
- **Route-1 only**: Layer 2 may only contain end-to-end runnable demos
- **Filename stability**: `si_bands_demo.yml` and `si_dos_demo.yml` filenames must survive (GUI e2e tests depend on them)
- **Integrity suite excluded from default pytest**: Run explicitly with `pytest tests/integrity/backend/`

### P33 Impact on the Pipeline

The 4 affected demos passed **every stage** of this pipeline:
- Stage 2: Generated successfully (bad titles are valid strings)
- Stage 3: Compiled and replayed (flat paths don't prevent compilation)
- Stage 4: Ran on real QE engine, produced ref packs (execution doesn't need canonical paths)
- Stage 5: Roundtrip passed (flat paths are preserved identically)
- Stage 6: Analysis resweep matched expectations

The bug only manifests in the **GUI step-detail resolution** — which is outside the pipeline's validation scope. Every backend stage treats step paths as opaque strings. The GUI is the first consumer that actually parses the path format to locate a calculation.

---

## Affected Files

| Demo File | Title | Step Path Format | Functional? |
|-----------|-------|-----------------|-------------|
| `qe_si_scf.yml` | `0 Si Scf` | `si.scf.step.yaml` (FLAT) | BROKEN |
| `qe_si_vc_relax.yml` | `3 Si Vc Relax` | `si.vc_relax.step.yaml` (FLAT) | BROKEN |
| `qe_si_dos_alt.yml` | `4 Si Dos` | `calculations/4-si-dos/steps/...` | Works but ugly slug |
| `qe_si_bands_alt.yml` | `7 Si Bandstructure` | `calculations/7-si-bandstructure/steps/...` | Works but ugly slug |

Good demos for comparison:
- `vasp_si_scf.yml` — title: `Silicon diamond SCF`, path: `calculations/silicon-diamond-scf/steps/scf.step.yaml`
- `abinit_si_scf.yml` — title: `Silicon SCF ground state`, path: `calculations/silicon-scf-ground-state/steps/scf.step.yaml`

---

## Root Cause Chain (5 links)

### Link 1: QE Tutorial Folder Names

The original QE tutorial datasets live at `tests/data/` with numbered folder names from the QE tutorial series:

```
tests/data/0_Si_scf/
tests/data/3_Si_vc_relax/
tests/data/4_Si_DOS/
tests/data/7_Si_bandStructure/
```

These numbers are tutorial sequence indices, not data. The folder names were designed as filesystem identifiers, not display titles.

### Link 2: `import_tutorial_datasets.py` — Naive Title Generation

`tools/import_tutorial_datasets.py` line 1526:
```python
"title": dataset.folder_name.replace("_", " ").title(),
```

This takes the raw folder name `0_Si_scf` and applies:
1. `replace("_", " ")` → `0 Si scf`
2. `.title()` → `0 Si Scf`

The leading digit is preserved. No attempt to strip numeric prefixes, no manual title overrides. The same pattern at line 537 generates calculation names from folder names.

For single-step demos, this script also produced flat step paths like `si.scf.step.yaml` instead of the canonical nested format. Multi-step demos got canonical paths because the import logic already handled subdirectory structure for multi-step workflows.

### Link 3: `create_qe_corpus.py` — Reverse-Engineering Bakes In Bad Data

`tools/demo_store/create_qe_corpus.py` is a bootstrap tool that creates Layer 1 corpus FROM existing Layer 2 demos. Line 214-215:

```python
title = demo_meta.get("title", demo_slug)
subtitle = demo_meta.get("subtitle", "")
```

It reads the title from the existing demo's `meta.title` field — which already contains "0 Si Scf". This value is written into the corpus `case.yaml`, making the bad title the corpus SSOT.

**This is the critical amplification step**: bad data in a mutable Layer 2 file gets enshrined as "source truth" in Layer 1.

### Link 4: `generate_all.py` — Preservation Trap

`tools/demo_store/generate_all.py` lines 242-264 implements three strategies:

```python
if existing_path and existing_path.exists():           # Strategy 1: PRESERVE
    snapshot = generate_demo_from_existing(...)
elif case_data.get("parser_mode") == "direct_snapshot": # Strategy 2: DIRECT
    snapshot = build_direct_snapshot(...)
else:                                                    # Strategy 3: TRANSLATOR
    snapshot = generate_demo_via_translator(...)
```

For qe_si_scf.yml: the file already exists (it IS the original output of `import_tutorial_datasets.py`), so Strategy 1 fires. `generate_demo_from_existing()`:
- **Preserves** the entire existing demo structure (steps, paths, parameters)
- **Only rewrites** ULIDs (deterministic) and gallery metadata (from case.yaml)
- **Does NOT rewrite** step paths

The translator (Strategy 3) generates correct canonical paths at lines 505 and 736:
```python
"path": f"calculations/{calc_slug}/steps/{_slugify(step_type_gen)}.step.yaml"
```

But it is **never called** for these demos because the preserve strategy takes precedence.

### Link 5: Self-Reinforcing Cycle

Running the generator again does not fix the problem:
1. Generator scans `DEMO_DIR`, finds `qe_si_scf.yml` exists
2. Strategy 1 fires → preserves the old demo (including flat path)
3. New demo file written with same flat path
4. Repeat forever

The translator (which would produce correct paths) is permanently bypassed for any demo that already has a Layer 2 file.

---

## Why Dev Testing Didn't Catch It

### What the tests DO check

| Test | What It Validates | Catches P33? |
|------|------------------|--------------|
| `test_gallery_metadata()` | `assert meta.get("title")` — truthy check | No (non-empty is truthy) |
| `test_demo_integrity.py` | `engine_family` set, `step_type_spec` prefix matches engine | No |
| `test_demo_generated.py` | Manifest checksums match files | No (checksums of bad files match) |
| `test_demo_schema_validation.py` | No k_points in params, species_map complete | No |
| `test_demo_lifecycle.py` | Demo loads as ProjectSnapshot, materializes | No (materialization succeeds) |

### What the tests DON'T check

1. **No title quality validation** — "0 Si Scf" is truthy, so it passes. No regex for leading digits, no capitalization check, no length minimum.

2. **No step path format validation** — No test checks that `step.meta.path` follows the canonical format `calculations/*/steps/*.step.yaml`. The flat path `si.scf.step.yaml` is structurally valid YAML, just semantically wrong.

3. **No GUI resolution test** — The functional failure (clicking a step and getting "Calculation not found") requires the GUI's step-detail resolution logic, which maps `step.meta.path` back to a calculation. No backend test exercises this resolution. The materialization test proves the YAML can be unpacked, but not that the step detail panel can resolve the path.

### The Gap Pattern

The tests validate **structural integrity** (fields exist, types correct, checksums match) but not **semantic correctness** (paths are canonical, titles are human-readable, resolution works end-to-end). P33 is a semantic bug invisible to structural tests.

---

## Why This Pattern Affected Only QE

Other engines (VASP, ABINIT, CP2K, ORCA, etc.) were added to the corpus AFTER the demo store architecture was established. Their corpus cases were created manually with proper titles and then generated through the translator (Strategy 3). They never had pre-existing Layer 2 files, so the "preserve existing" trap never fired.

The 4 affected QE demos are the **oldest demos** in the system — created by the original `import_tutorial_datasets.py` BEFORE the corpus/translator architecture existed. They were grandfathered into the new system via `create_qe_corpus.py` (reverse-engineering bootstrap), and then the "preserve existing" strategy kept them frozen in their original broken form.

The other QE demos (si_bands_demo, si_dos_demo, graphene_bands, etc.) were also originally created by the import script but either:
- Had folder names without numeric prefixes (e.g., `graphene_bands`)
- Were later manually recreated with proper titles
- Were fully regenerated through the translator

---

## Proposed Fix

### Step 1: Fix Layer 1 corpus titles (4 files)

Edit `tests/inputformat/samples/qe/<case>/case.yaml`:

| File | Current Title | Proposed Title |
|------|--------------|----------------|
| `qe/si_scf/case.yaml` | `0 Si Scf` | `Silicon SCF (LDA)` |
| `qe/si_vc_relax/case.yaml` | `3 Si Vc Relax` | `Silicon variable-cell relaxation` |
| `qe/si_dos_alt/case.yaml` | `4 Si Dos` | `Silicon density of states (PBE)` |
| `qe/si_bands_alt/case.yaml` | `7 Si Bandstructure` | `Silicon band structure (PBE)` |

### Step 2: Force translator re-generation (4 files)

Delete the 4 existing Layer 2 demo files, then run `generate_all.py`. With no existing file found, Strategy 3 (full translator) fires, producing:
- Canonical step paths: `calculations/<calc-slug>/steps/<step>.step.yaml`
- Titles from the fixed case.yaml
- Proper calc slugs (no numeric prefixes)

```bash
rm src/qmatsuite/resources/demo_projects/qe_si_scf.yml
rm src/qmatsuite/resources/demo_projects/qe_si_vc_relax.yml
rm src/qmatsuite/resources/demo_projects/qe_si_dos_alt.yml
rm src/qmatsuite/resources/demo_projects/qe_si_bands_alt.yml
python tools/demo_store/generate_all.py
```

### Step 3: Re-run ref pack generation for the 4 demos

After `generate_all.py` produces new Layer 2 files, the ref packs for these 4 demos must be regenerated. The existing ref packs reference old checksums and were generated from the broken demos.

```bash
python tools/demo_store/generate_ref_packs_realrun.py --only=qe_si_scf,qe_si_vc_relax,qe_si_dos_alt,qe_si_bands_alt
```

This runs Stages 3-4 of the pipeline: materialize → run on QE → capture analysis → write new ref packs with updated SHA-256 checksums.

**Current ref pack state for the 4 affected demos**:
- `qe_si_scf`: convergence (1 type)
- `qe_si_vc_relax`: convergence + trajectory (2 types)
- `qe_si_dos_alt`: convergence + dos (2 types)
- `qe_si_bands_alt`: convergence + bands (2 types)

These ref packs should be preserved or improved after regeneration.

### Step 4: Add gate tests (2 tests)

**Test 1 — Step path canonicality** (in `tests/gates/test_demo_integrity.py`):
```python
def test_step_paths_canonical(demo_path):
    """Step meta.path must follow calculations/*/steps/*.step.yaml format."""
    import re
    data = _load_demo(demo_path)
    for calc in data.get("calculations", []):
        for step in calc.get("steps", []):
            path = step.get("meta", {}).get("path", "")
            assert re.match(r"calculations/[^/]+/steps/[^/]+\.step\.yaml$", path), \
                f"Non-canonical step path in {demo_path.name}: {path}"
```

**Test 2 — Title quality** (in `tests/gates/test_demo_integrity.py`):
```python
def test_title_no_numeric_prefix(demo_path):
    """Demo titles must not start with a digit (legacy numbering artifact)."""
    data = _load_demo(demo_path)
    title = data.get("meta", {}).get("title", "")
    assert title and not title[0].isdigit(), \
        f"Title starts with digit in {demo_path.name}: '{title}'"
```

### Step 5 (optional): Guard the preserve strategy

In `generate_all.py`, add a validation step after preserve:
```python
# After generate_demo_from_existing(), validate paths
for calc in snapshot.get("calculations", []):
    for step in calc.get("steps", []):
        path = step.get("meta", {}).get("path", "")
        if not path.startswith("calculations/"):
            raise ValueError(f"Preserved demo {demo_slug} has non-canonical step path: {path}. "
                             f"Delete the existing demo and re-run to use the translator.")
```

---

## Additional Bad Corpus Entries (out of P33 scope)

The audit also found 4 additional QE corpus cases with numbered titles. These are not demo-eligible per the current corpus index, but if they become eligible in the future, they'll exhibit the same bug:

| Corpus Case | Title | Issue |
|-------------|-------|-------|
| `qe/si_bulk_modulus` | `15 Bulk Modulus Si` | Numeric prefix |
| `qe/si_phonon` | `09 Si Phonon  3 Phonon Dispersion` | Numeric prefix + junk suffix |
| `qe/si_cpmd` | `19 Si Cpmd  4 Bomd Nvt` | Numeric prefix + junk suffix |
| `qe/nmr_gipaw` | `12 Nmr Gipaw  2 Benzene` | Numeric prefix + junk suffix |

These should also be fixed in Layer 1 if/when they become demo-eligible.
