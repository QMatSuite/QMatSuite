# Post-Phase 1 Polish Stage P4 — Worklog

**Status**: DONE
**Date**: 2026-02-19
**Prior stage**: P3 (demo friction fixes, 26 tools, 6102 tests)
**Result**: 27 tools, 6138 tests, 0 failures, 4 skipped

## Investigation A: FTS5 Query Path

**Finding**: `store.py:_fts_search()` line 133 passes `query_text` directly as FTS5 MATCH
parameter via SQL parameterization (`?`). SQL injection is safe, but FTS5 syntax
characters (`-`, `"`, `OR`, `AND`, `NOT`, `*`, `NEAR`) in the query text are interpreted
as FTS5 operators. Hyphens become NOT operators, causing crashes on queries like
"non-convergence" or "Quantum-ESPRESSO".

`search_parameters` uses in-memory BM25 with `re.compile(r"[a-z0-9_]+")` tokenizer
— NOT affected by FTS5 syntax issues.

**Fix**: Add `_sanitize_fts_query()` that strips all non-alphanumeric/non-underscore
characters using `re.compile(r"[a-zA-Z0-9_]+").findall()`, also filtering out FTS5
boolean keywords (AND/OR/NOT/NEAR).

## Investigation B: QE Step Types

**Finding**: 19 spec types in `step_types.py`, mapping to 12 distinct executables:
- **pw.x steps** (gen): `scf`, `nscf`, `relax`, `md`, `bandspw`, `neb`, `custom`
- **Non-pw.x steps** (gen): `dos` (dos.x), `bands` (bands.x), `pdos` (projwfc.x),
  `ph` (ph.x), `gipaw` (gipaw.x), `q2r` (q2r.x), `matdyn` (matdyn.x), `dynmat` (dynmat.x),
  `pp` (pp.x), `plotband` (plotband.x), `hp` (hp.x), `pw2wannier` (pw2wannier90.x),
  `pw2qmcpack` (pw2qmcpack.x)

QE preflight checker has 20 rules targeting pw.x parameters (ecutwfc, K_POINTS,
CONTROL.calculation, etc.). Running these on dos.x/bands.x steps generates false
positives (MISSING_ECUTWFC, MISSING_KPOINTS, INVALID_CALCULATION_TYPE).

Dry-run materialization similarly generates pw.x-style input for non-pw.x steps.

**Fix**: Gate preflight and dry_run to `_PW_X_GEN_STEPS` set in `inspect_calculation.py`.

## Investigation C: PseudoVariant Installed Flag

**Finding**: `PseudoVariant.to_dict()` already computes `availability.any_installed`
from sources. But `_list_qe_resources()` only surfaces `n_variants` and `examples` —
discards the installed flag.

**Fix**: Add `n_installed` count per element in the list_resources response.

## Investigation D: SSSP Metadata Check for Missing Elements

**Finding**: `get_pseudo_options_for_elements()` returns empty list for elements not
found in any source (project/internal/lib). The MCP layer doesn't distinguish "no
metadata" from "metadata exists but not installed".

**Fix**: Covered by Fix 3 (list_resources enhancement). No separate fix needed.

## Investigation E: Single-File Download Path

**Finding**: `ensure_qe_pseudos()` line 423 sets `download_target = system_pseudo_dir`
which points to `resources/pseudo/` (committed directory inside repo). This is a
runtime concern. MCP auto_resolve uses `resolve_project_pseudos()` which has its own
resolution chain (project → repo → store → seed → download).

**Decision**: Deferred. Runtime download path is not an MCP tool issue.

## Investigation F: Download Pipeline Entry Point

**Finding**: `pseudo_config.download_sssp_library()` is the fully-implemented entry point:
1. Fetches `MANIFEST_PSEUDO_SEED.json` from GitHub release
2. Selects entries by version/flavor/xc
3. Downloads tar.gz + cutoffs JSON to temp dir
4. Verifies SHA256 checksums
5. Extracts UPF files to `store_dir/sssp/{version}/{flavor}/library/`
6. Creates manifest.json
7. Optionally saves to seed_dir for disaster recovery

Already production-ready. Just needs an MCP tool wrapper.

## Investigation G: Resolution Chain & additional_search_dirs

**Finding**: `resolve_project_pseudos()` resolution order:
1. `project_root/pseudo/` — project-local copies
2. `resources/pseudo/` — committed internal pseudos
3. `store_dir/sssp/{version}/{flavor}/library/` — installed SSSP
4. Seed installation (from `seed_dir/sssp/`)
5. Download (TODO/stubbed)

`ensure_qe_pseudos()` (runtime) also checks `additional_search_dirs` and
`QMS_PSEUDO_PATH` env var.

No MCP fix needed — the chain is correct.

## Investigation H: preview_compilation

**Finding**: `compile_presets_for_step()` catches exceptions and returns `{}`.
When all steps have empty parameters, the response gives no guidance. The
`context_hint` always says "To commit, call create_calculation + apply_preset."

**Fix**: Add per-step notes for empty parameters and a top-level hint when all
steps are empty.

## Investigation I: METAL_FIXED_OCC

**Finding**: `preflight.py` line 183-193: severity="warning", message says
"Metals typically need smearing." This is correct for SCF but overly prescriptive
for band structure/DOS workflows where fixed occupations are standard.

**Fix**: Change to severity="advisory", soften message to "Consider using smearing
for SCF convergence."

## Implementation Log

### Fix 1: FTS5 Hyphen Crash (CRITICAL) — DONE
- Added `_FTS5_TOKEN_RE` regex and `_FTS5_RESERVED` frozenset to `store.py`
- Added `_sanitize_fts_query()` helper that strips all non-alphanumeric chars and FTS5 keywords
- Called at top of `_fts_search()` before building SQL; returns `[]` if all tokens stripped

### Fix 2: dos.x Preflight/Dry-Run False Positives (CRITICAL) — DONE
- Added `_PW_X_GEN_STEPS` frozenset to `inspect_calculation.py`
- Gated `_run_preflight()` to only run for pw.x steps (or non-QE engines)
- Gated dry_run materialization; non-pw.x steps get `dry_run_note` explaining skip

### Fix 5: download_pseudo_library Tool (MEDIUM) — DONE
- New file `src/qmatsuite/mcp/tools/download_pseudo_library.py`
- Wraps `pseudo_config.download_sssp_library()` with flavor validation
- Registered in `server.py` (tool count: 26 → 27)

### Fix 4: auto_resolve Download Hint (MEDIUM) — DONE
- Updated `resolve_species_map.py` resolution_failed hint to mention `download_pseudo_library(flavor='efficiency')`

### Fix 3: list_resources Installed Count (MEDIUM) — DONE
- Enhanced `_list_qe_resources()` to include `n_installed` per element
- Added top-level `any_installed` flag
- Dynamic `context_hint`: mentions `download_pseudo_library` when nothing installed

### Fix 6: set_species_map File Warning (MEDIUM) — DONE
- Added `_pseudo_file_exists()` helper (checks project/internal/store paths)
- After successful `update_species_map()`, checks each pseudo file existence
- Missing files produce non-blocking warnings in response envelope

### Fix 7: preview_compilation Empty Params (LOW) — DONE
- Per-step `note` when `compiled == {}`: "Use set_parameters() to configure manually"
- Top-level `hint` when all steps have empty params

### Fix 8: METAL_FIXED_OCC Severity (LOW) — DONE
- Changed severity from `"warning"` to `"advisory"`
- Softened message: "Consider using smearing for SCF convergence"
- Updated test_stage8.py to match new severity

### Test Updates
- Updated tool count assertions in test_stage_p1.py, test_stage_p2.py, test_stage11.py (26 → 27)
- Updated test_stage8.py METAL_FIXED_OCC severity assertion (warning → advisory)

## Test Results

```
6138 passed, 0 failed, 4 skipped (304s)
```

36 new tests:
- `tests/mcp/test_stage_p4.py` — 22 MCP-level tests
- `tests/api/test_p4_hardening.py` — 14 API-level tests

## Files Created/Modified

### New Files
- `src/qmatsuite/mcp/tools/download_pseudo_library.py` — new MCP tool
- `tests/mcp/test_stage_p4.py` — 22 MCP-level tests
- `tests/api/test_p4_hardening.py` — 14 API-level tests

### Modified Files
- `src/qmatsuite/mcp/knowledge/store.py` — FTS5 sanitization (Fix 1)
- `src/qmatsuite/mcp/tools/inspect_calculation.py` — pw.x gen-step gate (Fix 2)
- `src/qmatsuite/mcp/tools/list_resources.py` — installed flag (Fix 3)
- `src/qmatsuite/mcp/tools/resolve_species_map.py` — download hint (Fix 4)
- `src/qmatsuite/mcp/tools/set_species_map.py` — file existence warning (Fix 6)
- `src/qmatsuite/mcp/tools/preview_compilation.py` — empty params hint (Fix 7)
- `src/qmatsuite/drivers/qe/preflight.py` — METAL_FIXED_OCC advisory (Fix 8)
- `src/qmatsuite/mcp/server.py` — import download_pseudo_library tool
- `tests/mcp/test_stage_p1.py` — tool count 26 → 27
- `tests/mcp/test_stage_p2.py` — tool count 26 → 27
- `tests/mcp/test_stage11.py` — tool count 26 → 27, expected_names updated
- `tests/mcp/test_stage8.py` — METAL_FIXED_OCC severity warning → advisory

## Deferred Items
- `ensure_qe_pseudos` download target path (`resources/pseudo/` vs project/pseudo)
  — runtime concern, not MCP
- `.qmatsuite/pseudo/` loose pseudo directory — low priority, resolution chain
  already works without it
