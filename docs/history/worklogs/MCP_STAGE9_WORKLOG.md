# MCP Stage 9: promote_structure + Knowledge Evolution — Worklog

**Status**: Complete

## Plan (Pre-Implementation Research)

### save_relax_final_structure() API Deep Dive

Found at `src/qmatsuite/api/service.py:2377`. Key findings:

- **Signature**: `save_relax_final_structure(calculation_selector, step_selector, parent_structure_ulid, slug_hint=None, index=None, config=None) -> dict`
- **Returns**: `{"structure_ulid": str, "already_exists": bool}`
- **Idempotency**: Checks `step_yaml_data.get("produced_structure_ulid")` in the step YAML. If already set, returns immediately with `already_exists=True`.
- **Step type validation**: Uses `get_step_type_gen(step_type_spec)` to convert engine-specific type (e.g. "qe_relax") to gen type, then checks `step_gen == "relax"`. Note: vc-relax is a CONTROL parameter in QE, not a separate gen step — so "relax" gen covers both.
- **Artifact reading**: Parses the final geometry from the QE output file (`relax.out`), NOT from `generated_structures/`. Uses `read_final_geometry_from_output_text()`.
- **Exceptions**: `ValueError` (not a relax step), `FileNotFoundError` (output file missing).
- **Two variants exist**: `promote_relax_structure()` reads from `generated_structures/step_<ulid>/current.json` (artifact-based), while `save_relax_final_structure()` parses the output file. Design doc specifies the latter.

### Knowledge Schema Comparison

Current schema (Stage 4) has 23 columns in `insights` table. Design doc Section 7.4 specifies two additional columns:
- `last_validated TEXT` — ISO-8601 datetime of last confirming observation
- `contradiction_count INTEGER DEFAULT 0` — incremented when new results contradict

Since `build_builtin.py` drops and recreates all data, no migration needed — just update SCHEMA_DDL and INSERT statement.

### Builtin Entries Audit

Current 20 entries by category:
- 5 error recovery (SCF oscillation, not converging, diverging, charge sloshing, forces)
- 3 smearing/occupations (metals, semiconductors, entropy)
- 4 convergence guidance (ecutwfc, k-mesh, thresholds, ecutrho)
- 4 workflow-specific (bands, DOS, relax, phonons)
- 4 method-specific (DFT+U, HSE06, GW, spin-polarized)

Missing categories per design doc Section 7.6:
- Cross-engine methodology (e.g. "metallic systems need smearing; which type depends on engine")
- Result interpretation aids (e.g. "PBE underestimates semiconductor band gaps by 30-50%")
- Workflow sequencing wisdom (e.g. "always relax geometry before computing band structure")

## Implementation Log

### Step 1: Knowledge Schema Evolution (Part B)

**File**: `src/qmatsuite/mcp/knowledge/schema.py`

Added two columns to SCHEMA_DDL between `upvotes` and `created_at`:
```sql
last_validated TEXT,
contradiction_count INTEGER DEFAULT 0,
```

**File**: `src/qmatsuite/mcp/knowledge/build_builtin.py`

Updated INSERT statement to include `last_validated` (set to `now`) and `contradiction_count` (set to 0) for each builtin entry. Added one extra `now` parameter to the tuple.

### Step 2: Builtin.db Expansion (Part C)

**File**: `src/qmatsuite/mcp/knowledge/builtin_entries.py`

Added 20 new entries (20 → 40 total) in three new categories:

**Cross-Engine Methodology (7 entries, grade: principle/finding)**
1. Metallic systems smearing by engine (QE cold/m-v, VASP ISMEAR=1, ABINIT occopt)
2. Pseudopotential selection (NC for optical, US moderate, PAW default recommendation)
3. Spin-orbit coupling (essential for Z > 50, negligible for Z < 20)
4. DFT+U validation (starting values, self-consistent methods)
5. Basis set convergence by code type (plane-wave vs localized vs Gaussian)
6. Van der Waals corrections (essential for layered materials, DFT-D3 as default)
7. K-point density scaling with cell size (k_i * a_i rule of thumb)

**Result Interpretation (7 entries, grade: principle/finding)**
1. PBE band gap underestimation (30-50% for semiconductors)
2. LDA overbinding (lattice constants 1-2% too small)
3. Total energy only meaningful as differences
4. Force convergence thresholds (< 0.01 eV/A well-converged)
5. PBE-D3 for vdW systems
6. Band structure reading (direct vs indirect gap)
7. Polymorph comparison consistency requirements

**Workflow Sequencing (6 entries, grade: principle/finding)**
1. Always relax before electronic properties
2. Band structure workflow (SCF → NSCF along k-path)
3. DOS workflow (SCF → NSCF dense k-mesh)
4. Variable-cell relax may need multiple restarts
5. Phonon requires fully relaxed structure
6. Consistent settings for energy comparisons

All entries follow quality guidelines: 50-150 words, actionable, specific parameter names, tagged consistently, engine scope specified where appropriate.

### Step 3: InsightRecord Dataclass (Part D)

**File**: `src/qmatsuite/mcp/knowledge/insight_record.py` (NEW)

Created `InsightRecord` dataclass with 8 fields per design doc Section 5.4:
- `content: str` — distilled conclusion (enters knowledge base)
- `reasoning: str | None` — thought process (provenance only, not indexed)
- `grade: str = "observation"` — bookkeeping | observation | finding | principle
- `scope: dict` — engine, workflow, system_type, method filters
- `run_refs: list[str]` — associated calculation ULIDs
- `tags: list[str]` — freeform FTS tags
- `intent_id: str | None` — links to originating intent
- `created_by: str = "agent"` — origin marker

### Step 4: promote_structure Tool (Part A)

**File**: `src/qmatsuite/mcp/tools/promote_structure.py` (NEW)

Tool signature: `promote_structure(calc_ulid, step_index=-1, name="")`

Logic flow:
1. Get calculation detail via `svc.calculation.get_detail(calc_ulid)`
2. If `step_index == -1`: auto-detect by iterating steps, finding last where `step_type_gen == "relax"`
3. Validate: step exists, is a relax type, has parent structure ULID
4. Call `svc.structure.save_relax_final_structure(calc_ulid, step_ulid, parent_structure_ulid, slug_hint)`
5. Return `{structure_ulid, already_exists, source_calc_ulid, name, formula, n_atoms}`

Error cases:
- `no_relax_step`: No relax step found in calculation (with list of actual gen types)
- `not_relax_step`: Explicitly selected non-relax step
- `invalid_step_index`: Out-of-range step index
- `no_output`: FileNotFoundError → step hasn't been run
- `promote_failed`: Generic catch-all

**File**: `src/qmatsuite/mcp/server.py`

Added import: `import qmatsuite.mcp.tools.promote_structure` under "Stage 9" comment.

### Step 5: Tests (Part E)

**File**: `tests/mcp/test_stage9.py` (NEW, 17 tests)

**TestPromoteStructure (5 tests, qms_project fixture):**
- test_promote_no_relax_step_error — SCF-only calc → no_relax_step error
- test_promote_invalid_calc_ulid — nonexistent calc → not_found
- test_promote_invalid_step_index — out-of-range → invalid_step_index
- test_promote_step_not_relax_type — explicitly selecting SCF step → not_relax_step
- test_promote_relax_step_not_run — unexecuted relax → error about missing output

**TestKnowledgeSchemaEvolution (4 tests, tmp_path):**
- test_schema_has_last_validated — column exists in table
- test_schema_has_contradiction_count — column exists with default 0
- test_existing_search_still_works — FTS search returns results after schema change
- test_new_columns_populated_in_builtin — last_validated set, contradiction_count=0

**TestBuiltinExpansion (6 tests, tmp_path):**
- test_entry_count_at_least_35 — count >= 35
- test_methodology_entries_exist — FTS finds methodology entries
- test_interpretation_entries_exist — FTS finds interpretation entries
- test_workflow_sequence_entries_exist — FTS finds workflow sequencing entries
- test_no_duplicate_entry_ids — all ULIDs unique
- test_builtin_entries_match_db — BUILTIN_ENTRIES length == DB count

**TestInsightRecord (2 tests, no fixtures):**
- test_insight_record_fields — defaults correct
- test_insight_record_content_reasoning_separation — content != reasoning

## Files Created (4)

| File | Lines | Purpose |
|------|-------|---------|
| `src/qmatsuite/mcp/tools/promote_structure.py` | ~145 | promote_structure MCP tool |
| `src/qmatsuite/mcp/knowledge/insight_record.py` | ~40 | InsightRecord dataclass |
| `tests/mcp/test_stage9.py` | ~250 | 17 tests across 4 classes |
| `docs/history/worklogs/MCP_STAGE9_WORKLOG.md` | this file | Implementation worklog |

## Files Modified (4)

| File | Change |
|------|--------|
| `src/qmatsuite/mcp/knowledge/schema.py` | Added `last_validated` + `contradiction_count` to SCHEMA_DDL |
| `src/qmatsuite/mcp/knowledge/build_builtin.py` | Updated INSERT to include new columns |
| `src/qmatsuite/mcp/knowledge/builtin_entries.py` | Added 20 entries (20 → 40 total) |
| `src/qmatsuite/mcp/server.py` | Registered promote_structure tool |

## Test Results

```
tests/mcp/test_stage9.py — 17 passed
tests/mcp/ (all) — 137 passed
tests/ (full suite) — 5797 passed, 0 failed, 4 skipped
```

## Cumulative MCP Stats

| Stage | Tools | MCP Tests | Total Suite |
|-------|-------|-----------|-------------|
| 0-8 | 18 | 120 | 5780 |
| 9 | 19 (+1: promote_structure) | 137 (+17) | 5797 (+17) |
