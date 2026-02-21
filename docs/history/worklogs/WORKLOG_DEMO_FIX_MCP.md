# Demo Store — Fix Bugs, Enrich Metadata, Harden MCP Tools

**Started:** 2026-02-20
**Branch:** v2-python

---

## Wave 1: Fix Bugs + Enrich Metadata

### Bug A: GPAW bands not in ref pack

**Root cause:** `write_gpaw_script()` in `drivers/gpaw/writer.py` only generates a
band structure script when `restart_from` is provided. For a single-step `bandspw`
calculation (no prior SCF step), `restart_from=None` falls through to the standard
SCF script generator, producing `results.json` but NOT `bandstructure.json`.

**Fix:** Add `_write_combined_scf_bands_script()` function to `writer.py`. Called when
`gen_type == "bandspw"` and `restart_from is None`. The script does:
1. Load structure → run SCF → save `scf.gpw`
2. Load `scf.gpw` → `fixed_density()` → compute band structure → save `bandstructure.json`

**Status:** DONE

---

### Bug B: Siesta trajectory not in ref pack

**Root cause:** Two issues:
1. Starting geometry (`si_relax` demo with LatticeConstant=5.5 Ang) converges in ~1 CG step
   → no trajectory frames written
2. `WriteMDXmol: true` in step params causes Siesta to OVERWRITE `siesta_relax.xyz`
   each step (not append), losing intermediate frames

**Fix:**
1. Update `resources/demo_projects/siesta_si_relax.yml`: change LatticeConstant to 5.80 Ang
   (7% stretched), fractional position of Si2 to 0.30 (vs ideal 0.25), remove `WriteMDXmol: true`
2. Update `drivers/siesta/parsers/trajectory.py` to also handle `*.xyz` multi-frame files
   as fallback (for future robustness)

**Status:** DONE

---

### Bug C: qe_fe_dos mislabeled (should be qe_fe_scf)

**Root cause:** The `qe/fe_dos` corpus case is an SCF calculation (noncollinear Fe),
not a DOS calculation. Its demo_slug is `qe_fe_dos` but should be `qe_fe_scf`.

**Fix:**
1. `tests/inputformat/samples/qe/fe_dos/case.yaml`: change `demo_slug: qe_fe_dos` → `qe_fe_scf`,
   fix `title`, `recommended_analysis`, `tags`
2. `tests/inputformat/samples/corpus_index.yaml`: update the entry's demo_slug
3. `tools/demo_store/generate_all.py`: add `qe_fe_dos` → `qe_fe_scf` to `OLD_TO_NEW_SLUG`,
   add `qe_fe_dos.yml` to `OLD_DEMO_FILENAMES`

**Status:** DONE

---

### Step 1.4: generate_all.py — propagate new metadata fields

**Status:** DONE

---

### Step 1.5: Enrich all 52 demo case.yaml files

**Status:** IN PROGRESS

---

### Step 1.6: Regenerate and verify

**Status:** PENDING

---

### Step 1.7: Commit Wave 1

**Status:** PENDING

---

## Wave 2: Audit & Harden MCP Tools

### Step 2.1: Inventory existing MCP tools

**Status:** DONE (during planning)

---

### Step 2.2: Fix list_demo_projects() in service.py

**Status:** PENDING

---

### Step 2.3: Fix search_demos MCP tool

**Status:** PENDING

---

### Step 2.4: Fix get_demo_results MCP tool

**Status:** PENDING

---

### Step 2.5: Fix load_demo MCP tool context_hint

**Status:** PENDING

---

### Step 2.6: Write tests

**Status:** PENDING

---

### Step 2.7: Commit Wave 2

**Status:** PENDING

---

## Notes

- GPAW workdir policy = SHARED → evidence dir falls back to `raw/`
- Siesta workdir policy = ISOLATED → evidence dir = `raw/<step_ulid>/`
- All 52 demo case.yaml files need new fields for MCP search effectiveness
- generate_all.py is the SINGLE WRITER for demo YAMLs (Rule T1)
- No runner/executor/registry edits per constitutional law
