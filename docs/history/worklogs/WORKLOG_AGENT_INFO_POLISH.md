# Agent Information Pipeline Polish — Worklog

**Date**: 2026-02-21
**Reference**: `docs/history/reviews/AGENT_INFORMATION_SYSTEMS_AUDIT.md`
**Scope**: Fix high-impact, small-scope issues from the audit. No new features.

---

## Task 1: .mcp.json.example + instructions

### Findings
- `.mcp.json` exists in repo root (tracked) — should be .gitignored (user-specific)
- No `instructions` field anywhere — agent gets zero orientation at session start
- Test project (`~/qmatsuite-demo/.mcp.json`) also lacks instructions

### Actions
- Created `.mcp.json.example` in repo root with `instructions` field (~400 tokens)
- Added `.mcp.json` to `.gitignore`
- Synced `instructions` field to `~/qmatsuite-demo/.mcp.json`

---

## Task 2: Tool description fixes (3 tools)

### 2a: get_status
- **Before**: "mainly useful for checking past runs" — misleading
- **After**: "Check the run state of all steps in a calculation. Use after run_calculation to verify completion or diagnose failure."

### 2b: load_demo
- **Before**: No mention of automatic structure import
- **After**: Added "The demo's structure is automatically imported into the project — no separate import_structure call needed."

### 2c: preview_compilation context_hint
- **Before**: "To commit, call create_calculation + apply_preset."
- **After**: "To apply these presets to an existing calculation, call apply_preset(calc_ulid=..., presets=...). To create a new calculation, call create_calculation() first."

---

## Task 3: search_demos text index — add step_summary + method

### Findings
- Text query searched: title, subtitle, description, name, tags
- Missing: step_summary, method
- Agent searching for "vc-relax" or "mp2" would miss relevant demos

### Fix
- Added `step_summary` and `method` to the searchable text in `demo_store.py`

---

## Task 4: QE parameter enum pipeline

### Investigation
- QE JSON (`qe_module_parameters.json`): HAS enum fields (e.g., `occupations` → `["'smearing'", "'tetrahedra'", ...]`)
- QE metadata (`qe_metadata.py`): `_iter_params()` includes enum in yielded dict
- **Pipeline bug**: `TagDoc` in `search_index.py` has no `enum` slot — data discarded at indexing
- `search_parameters.py` output has no `enum` field

### VASP spot-check
- Mixed: `PREC` and `ALGO` have structured enums; `ISMEAR` and `ISPIN` embed values in description
- VASP metadata supports `enum` field in JSON schema

### ORCA spot-check
- Keywords: `type: "flag"`, no enum (correct — they're boolean flags)
- Block params: use `type: "enum"` with `values: [...]` (different field name)

### Fix
- Added `enum` field to `TagDoc.__slots__` and `__init__`
- Wired QE enum from `_iter_params()` → TagDoc
- Wired standard-tags engines enum from metadata → TagDoc
- Wired ORCA block params `values` → TagDoc enum
- Added `enum` to `search_parameters.py` output dict (only when non-null)
- Increased description truncation: 200 → 400 chars

---

## Task 5: Verification

- [x] `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` → **6445 passed, 4 skipped, 0 failures** (matches baseline)
- [x] `search_demos(query="vc-relax")` → 3 results (qe_si_vc_relax, qe_al_dos, qe_graphene_bands) via step_summary
- [x] `search_demos(query="mp2")` → 1 result (pyscf_n2_mp2) via method field
- [x] `search_parameters(query="occupations smearing", engine="qe")` → smearing at #1 with full enum
- [x] VASP `PREC` returns enum `['Low', 'Medium', 'High', 'Normal', 'Accurate', 'Single']`
- [x] QE `occupations` (pw.x) has enum `["'smearing'", "'tetrahedra'", ...]` — pipeline flows correctly
- [x] Description truncation increased 200→400 chars — allows more context for complex parameters
- [x] `.mcp.json.example` instructions reviewed — covers Decision Hierarchy, init_project, species_map rules, demo-first pattern

### QE enum upstream data note
Some QE parameters have `enum: null` but list valid values in description text (`cell_dofree`, `mixing_mode`, `diagonalization`, `ion_dynamics`). This is an upstream data quality issue — added to DEFERRED_ITEMS.md as P2 item.

---

## Task 6: Deferred items update

Added audit-identified items to `docs/plans/DEFERRED_ITEMS.md`:
- P1: builtin.db expansion, VASP preflight, error enrichment
- P2: QE metadata curation, run progress, preflight severity grouping, proactive knowledge injection
- P3: ORCA/CP2K/ABINIT preflight, knowledge packs, auto-invoke search_knowledge

---

## Files Modified

| File | Change |
|------|--------|
| `.mcp.json.example` | NEW — canonical MCP config with instructions field |
| `.gitignore` | Added `.mcp.json` |
| `~/qmatsuite-demo/.mcp.json` | Added `instructions` field |
| `src/qmatsuite/mcp/tools/get_status.py` | Fixed misleading description |
| `src/qmatsuite/mcp/tools/demo_store.py` | load_demo description + search_demos text index |
| `src/qmatsuite/mcp/tools/preview_compilation.py` | Fixed context_hint |
| `src/qmatsuite/mcp/search_index.py` | Added enum field to TagDoc, wired for all engines |
| `src/qmatsuite/mcp/tools/search_parameters.py` | Added enum to output, description 200→400 |
| `docs/plans/DEFERRED_ITEMS.md` | Added audit deferred items |
| `docs/history/worklogs/WORKLOG_AGENT_INFO_POLISH.md` | This worklog |
