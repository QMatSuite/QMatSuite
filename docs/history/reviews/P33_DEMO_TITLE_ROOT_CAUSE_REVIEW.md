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

### Step 3: Add gate tests (2 tests)

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

### Step 4 (optional): Guard the preserve strategy

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
