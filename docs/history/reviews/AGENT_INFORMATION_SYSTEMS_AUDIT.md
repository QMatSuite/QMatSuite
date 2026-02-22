# Agent Information Systems Audit

**Date**: 2026-02-20
**Auditor**: Claude (automated review)
**Worklog**: `docs/history/worklogs/AGENT_INFORMATION_SYSTEMS_AUDIT_WORKLOG.md`
**Design Reference**: `docs/design/AGENT_INTEGRATION_DESIGN.md`
**Scope**: READ-ONLY audit of all information channels between QMatSuite and the MCP agent. No fixes made.

---

## 1. Executive Summary

This audit reviewed **9 distinct information channels** through which QMatSuite communicates with the MCP agent. The overall picture is strong: the tool API is well-designed, context hints cover almost every tool with conditional variants, the knowledge base exists and has a solid schema, and error returns are structured and machine-actionable for the most common failure modes. However, three significant gaps undermine the agent's ability to make good decisions without human intervention.

**Overall Assessment**: The agent is well-guided *once it starts working*, but poorly oriented *at session start*. The absence of a `.mcp.json` instructions field means the agent receives no persona, no Decision Hierarchy guidance, and no hint that demos are the preferred first step. Mid-workflow guidance (context hints, error recovery, preflight) is substantially better than cold-start orientation.

### Top 5 Critical Gaps

| # | Gap | Impact |
|---|-----|--------|
| 1 | **No `.mcp.json` instructions field** | Agent has no initial persona, no Decision Hierarchy, no "check demos first" guidance |
| 2 | **Knowledge base has 20 entries — sparse for non-QE engines** | Error recovery for VASP/ORCA/CP2K/ABINIT falls through to generic UNKNOWN_FAILURE |
| 3 | **Preflight exists only for QE** | Agent can run misconfigured VASP/ORCA/CP2K calculations with no pre-run warnings |
| 4 | **Parameter search truncates descriptions at 200 chars** | Valid values / enum options may be cut off; enum field is present but often null |
| 5 | **`get_status` description misleads** | "mainly useful for checking past runs" contradicts it being the only reliable status check |

---

## 2. Channel Inventory Matrix

| Channel | Status | Coverage | Quality | Est. Token Cost | Priority Fixes |
|---------|--------|----------|---------|-----------------|----------------|
| 1: Tool Definitions | ✅ Implemented | 31 tools | Good (30/31) | ~6,200 initial | Fix `get_status` description |
| 2: Context Hints | ✅ Implemented | 28/31 tools, 71 variants | Good | ~100-200 per call | None blocking |
| 3: Knowledge Base | ✅ Implemented | 20 entries, 11 categories | Adequate — sparse non-QE | ~300 chars/entry | Add 15+ non-QE entries |
| 4: Error Returns | ✅ Implemented | 5 error types structured | Good for QE/VASP | ~500-800 per error | Expand to more engine errors |
| 5: Preflight Messages | ⚠️ Partial | QE only (20 rules) | Excellent for QE; absent for 14 engines | ~100-300 per issue | Add preflight for VASP/ORCA |
| 6: Parameter Search | ✅ Implemented | 11 engines, ~1000 docs | Good — descriptions short | ~200 per result × 5 | Document valid enum values |
| 7: Demo Store Metadata | ✅ Implemented | 50+ demos, Wave 2 enriched | Excellent | ~500 per search | None |
| 8: Proactive Injection | ❌ Not implemented | — | Phase 2+ design | — | Implement in Phase 2 |
| 9: MCP Configuration | ⚠️ Minimal | Server connection only | Missing instructions | 0 (no field set) | **Add instructions field** |

---

## 3. Channel 1: Tool Definitions

### 3.1 Registration Mechanism

All tools are registered via the `@mcp.tool` decorator from `qmatsuite.mcp.app`. The server (`server.py`) organizes registration into 11 functional stages via side-effect imports. The knowledge store (`search_knowledge`) uses lazy initialization via `_get_store()` — it's registered eagerly but the SQLite database is opened only on first call.

### 3.2 Complete Tool Inventory

**Total: 31 tools**

| # | Tool Name | Stage | Required Params | Optional Params | Quality | Notes |
|---|-----------|-------|-----------------|-----------------|---------|-------|
| 1 | `ping` | 0 | none | none | Good | Simple health check |
| 2 | `init_project` | P1 | none | `name` | Good | Mentions QMATSUITE_PROJECT env var |
| 3 | `list_engines` | 0+1 | none | `installed_only` | Good | Explains `installed_only` reserved |
| 4 | `list_workflows` | 0+1 | `engine` | none | Good | Clear |
| 5 | `get_presets` | 0+1 | `engine`, `workflow` | none | Good | Warns non-QE engines report `presets_available: false` |
| 6 | `search_parameters` | 0+1 | `query` | `engine`, `category`, `max_results` | Good | Mentions BM25, gives query examples |
| 7 | `create_calculation` | 2 | `engine`, `workflow`, `structure_selector` | `name` | Good | Clear prerequisite chain |
| 8 | `set_species_map` | 2 | `calc_ulid`, `species_map` | none | Good | Has example, lists required engines |
| 9 | `set_parameters` | 2 | `calc_ulid`, `params` | `step` | Good | QE + VASP examples; explains card auto-routing |
| 10 | `apply_preset` | 2 | `calc_ulid`, `presets` | none | Good | Has example dict |
| 11 | `inspect_calculation` | 2 | `calc_ulid` | `step`, `dry_run` | Good | Explains dry_run triggers preflight |
| 12 | `preview_compilation` | 2 | `engine`, `workflow`, `presets` | none | Good | Stateless note; mentions preflight_issues |
| 13 | `run_calculation` | 3 | `calc_ulid` | `run_mode` | Good | Mentions structured diagnostics + suggested_fixes |
| 14 | `get_status` | 3 | `calc_ulid` | none | **Needs improvement** | "mainly useful for checking past runs" misleads; it's the primary status tool |
| 15 | `get_results_summary` | 3 | `calc_ulid` | `step` | Good | Clear |
| 16 | `quick_run` | 3 | `engine`, `workflow`, `structure_selector` | `species_map`, `presets`, `overrides`, `name` | Good | Clearly a combined convenience tool |
| 17 | `search_knowledge` | 4 | none | `query`, `engine`, `workflow`, `system_type`, `method`, `grade_min`, `confidence_min`, `limit` | Good | All filter options documented; BM25 mentioned |
| 18 | `list_structures` | 7 | none | none | Good | Clear truncation note |
| 19 | `import_structure` | 7 | none | `file_path`, `file_content`, `format`, `name` | Good | Two-mode pattern clearly documented |
| 20 | `get_structure_detail` | 7 | `structure_ulid` | none | Good | 50-atom truncation documented |
| 21 | `promote_structure` | 9 | `calc_ulid` | `step_index`, `name` | Good | Use-case (downstream calcs) explained |
| 22 | `search_demos` | 10 | none | `engine`, `tag`, `difficulty`, `query`, `system_class`, `method`, `property_of_interest` | Good | All 7 filter dimensions documented |
| 23 | `get_demo_results` | 10 | `demo_id` | `object_type` | Good | Two-mode (list vs load) explained |
| 24 | `load_demo` | 10 | `demo_id` | `name` | **Needs improvement** | Doesn't mention that structure is auto-imported (context hint compensates) |
| 25 | `list_available_resources` | P2 | `engine` | `elements` | Good | Per-engine behavior documented |
| 26 | `auto_resolve_species_map` | P2 | `calc_ulid` | `library`, `variant` | Good | Supported engines listed; VASP exclusion noted |
| 27 | `download_pseudo_library` | P4 | none | `library`, `variant`, `version` | Good | SHA256 verification mentioned |
| 28 | `cleanup_project` | P1b | none | `dry_run` | Good | dry_run=True default explained |
| 29 | `list_analyses` | 2A | `calc_ulid` | `step` | Good | Evidence-file check vs full parse distinction noted |
| 30 | `plot_analysis` | 2A | `calc_ulid`, `object_type` | `step` | Good | Raw data exclusion documented; 200-300 token response noted |
| 31 | `generate_kpath` | 2A | `structure_selector` | `points_per_segment`, `path_type` | Good | Output format (QE crystal_b) documented |

**Quality summary**: 29 Good, 2 Needs-improvement, 0 Poor.

### 3.3 Token Cost Estimate

| Component | Estimate |
|-----------|----------|
| Average tool name + description | ~90 tokens |
| Average parameter set (2-3 params) | ~80 tokens |
| Total per tool | ~170 tokens |
| **31 tools × 170 tokens** | **~5,270 tokens** |
| Server stage comments / headers | ~150 tokens |
| **Total initial context cost** | **~5,400 tokens** |

This is a reasonable budget. The design doc targets tool definitions as a fixed initial context cost; ~5,400 tokens leaves ample room for conversation history in a 200K-token context window.

---

## 4. Channel 2: Context Hints

### 4.1 Envelope Definition

Context hints are a first-class field in both `make_response()` and `make_error()`:

```python
# envelope.py
def make_response(data, context_hint=None, warnings=None, status="success")
def make_error(error_type, message, context_hint=None, suggestions=None,
               *, severity, diagnostics=None, suggested_fixes=None)
```

Both return `context_hint` as a string field in the JSON envelope. The agent can always ignore hints and deviate — they are metadata, not instructions.

### 4.2 Complete Context Hint Map

**28 of 31 tools return context hints. Only `ping`, and the two implicit internal helpers have none.**

| Tool | Condition | Context Hint (verbatim excerpt) |
|------|-----------|----------------------------------|
| `init_project` | existing project | `"Existing project loaded. Use list_structures() to see structures, or search_demos() to find ready-made calculations."` |
| `init_project` | new project | `"Project created. Use import_structure() to add a structure, or search_demos() to find ready-made calculations."` |
| `list_engines` | always | `"Use list_workflows(engine='...') to see available workflows for a specific engine. Use search_demos() to find ready-made calculations with pre-configured structures."` |
| `list_workflows` | always | `"Use get_presets(engine='...', workflow='...') to check for available quality presets."` |
| `get_presets` | presets available | `"Use preview_compilation(engine='...', workflow='...', presets=...) to preview, or quick_run(...) to run directly."` |
| `get_presets` | no presets | `"No presets for {engine}/{workflow}. Use search_parameters(engine='{engine}') to find parameters, then create_calculation + set_parameters to configure manually."` |
| `search_parameters` | always | `"Use these parameters with set_parameters(calc_ulid, params=...) to configure a calculation. For QE, nest parameters under their namelist section..."` |
| `create_calculation` | unknown engine | `"Use list_engines() to see all available engines."` |
| `create_calculation` | unknown workflow | `"Use list_workflows(engine='{engine}') to see available workflows."` |
| `create_calculation` | structure not found | `"Use import_structure() to import a structure, or list_structures() to see existing ones."` |
| `create_calculation` | species map not resolved | `"IMPORTANT: For engines using pseudopotentials (QE, ABINIT, Siesta, VASP), call auto_resolve_species_map(calc_ulid='{calc_ulid}') or set_species_map(...) first. Then use apply_preset or set_parameters..."` |
| `create_calculation` | species map auto-resolved | `"Species map auto-resolved. Use apply_preset or set_parameters to configure, then inspect_calculation(...) to review, then run_calculation(...) to execute."` |
| `set_species_map` | empty map | `"Provide a mapping like {\"Si\": {\"pseudopot\": \"Si.UPF\"}}."` |
| `set_species_map` | missing pseudopot key | `"Each species entry needs at least {\"pseudopot\": \"filename\"}."` |
| `set_species_map` | success | `"Species map set. Use inspect_calculation(calc_ulid='{calc_ulid}') to review, then run_calculation() or apply_preset() to continue."` |
| `set_parameters` | invalid step | `"Valid step indices: 0..{n-1}."` |
| `set_parameters` | success, no warnings | `"Use inspect_calculation(calc_ulid='{calc_ulid}') to review, or run_calculation(calc_ulid='{calc_ulid}') to execute."` |
| `set_parameters` | success, with validation warnings | appends: `"Warning: some parameters may be in the wrong namelist section. Check validation_warnings and use the suggested_fix to correct."` |
| `apply_preset` | always | `"Use set_parameters(calc_ulid='{calc_ulid}', params=...) to override specific values, or inspect_calculation(calc_ulid='{calc_ulid}') to review."` |
| `inspect_calculation` | step=-1 | `"Use set_parameters(calc_ulid='{calc_ulid}') to adjust, or run_calculation(calc_ulid='{calc_ulid}') to execute."` |
| `inspect_calculation` | step>=0 | adds: `"Use inspect_calculation(calc_ulid='{calc_ulid}', step={step}, dry_run=True) to preview input files and run preflight checks."` |
| `preview_compilation` | always | `"To commit, call create_calculation + apply_preset."` |
| `run_calculation` | missing species_map | `"Call auto_resolve_species_map(calc_ulid='{calc_ulid}') or set_species_map(calc_ulid='{calc_ulid}', ...) first."` |
| `run_calculation` | success (non-relax) | `"Use get_results_summary(calc_ulid='{calc_ulid}') to see results."` |
| `run_calculation` | success (relax) | adds: `"For the relaxed geometry, use promote_structure(calc_ulid='{calc_ulid}') to extract and register it as a new structure."` |
| `run_calculation` | failure | `"Check step messages for failure details."` |
| `get_status` | not run | `"Use run_calculation(calc_ulid='{calc_ulid}') to execute this calculation."` |
| `get_status` | completed (non-relax) | `"Use get_results_summary(calc_ulid='{calc_ulid}') to see results."` |
| `get_status` | completed (relax) | adds promote_structure guidance |
| `get_status` | partial/other | `"Some steps have not been run. Use run_calculation(calc_ulid='{calc_ulid}') to execute."` |
| `get_results_summary` | no results | `"Use run_calculation to execute first."` |
| `get_results_summary` | non-relax | `"Use inspect_calculation(calc_ulid='{calc_ulid}') for parameter details."` |
| `get_results_summary` | relax | adds promote_structure |
| `quick_run` | execution error | `"Check engine installation and calculation parameters. For pseudopotential engines (QE, ABINIT, Siesta, VASP), ensure species_map is set."` |
| `quick_run` | success (non-relax) | `"Use get_results_summary(calc_ulid='{calc_ulid}') to see results."` |
| `quick_run` | success (relax) | adds promote_structure |
| `search_knowledge` | has results | `"Found {n} insight(s). Use these insights to inform your parameter choices with set_parameters or apply_preset."` |
| `search_knowledge` | no results | `"No matching knowledge found. Try broader search terms or remove filters."` |
| `list_structures` | empty | `"No structures in this project. Use import_structure(...) to add one."` |
| `list_structures` | has structures | `"Use get_structure_detail(structure_ulid='...') for full data, or create_calculation(structure_ulid='...', ...) to start a calculation."` |
| `import_structure` | CIF parse error | `"CIF parse failed. Common issues: missing _atom_site_label column, missing _cell_length_a, or incorrect symmetry tags. Try POSCAR format for simple crystals, or use search_demos() to find calculations with pre-configured structures."` |
| `import_structure` | other format error | `"Check the structure file format. Use search_demos() to find calculations with pre-configured structures."` |
| `import_structure` | success | `"Structure imported. Use create_calculation(structure_ulid='{ulid}', engine='...', workflow='...') to start a calculation."` |
| `get_structure_detail` | always | `"Use create_calculation(structure_ulid='{ulid}', engine='...', workflow='...') to start a calculation."` |
| `promote_structure` | no relax step | `"Create a calculation with workflow='relax' and run it first."` |
| `promote_structure` | not relax (error) | `"Only completed relax/vc-relax steps can be promoted."` |
| `promote_structure` | no output | `"Run the calculation first: run_calculation(calc_ulid='{calc_ulid}')."` |
| `promote_structure` | success | `"Structure promoted (ULID: {ulid}). Use create_calculation(structure_selector='{ulid}', ...) to start a new calculation."` |
| `search_demos` | has results | `"Use get_demo_results(demo_id=...) to preview pre-computed results, or load_demo(demo_id=...) to load a demo into your project."` |
| `search_demos` | no results | `"No demos matched. Try broader filters, or use create_calculation(...) to start from scratch."` |
| `get_demo_results` | listing types | `"Use get_demo_results(demo_id='{demo_id}', object_type=...) to load a specific result type."` |
| `load_demo` | success | `"Demo '{demo_id}' loaded. Structure '{structure_ulid}' is now in your project library — you do NOT need to import a structure separately. Calculation '{calc_ulid}' is configured with {n} step(s). Use run_calculation(calc_ulid='{calc_ulid}') to execute, or inspect_calculation(calc_ulid='{calc_ulid}') to review parameters. To use a different material with the same workflow, use create_calculation() instead."` |
| `list_available_resources` | builtin engines | `"Proceed directly with create_calculation(engine='{engine}', ...)."` |
| `list_available_resources` | unmanaged engines | `"Create the calculation first, then use set_species_map() to configure pseudopotentials manually."` |
| `list_available_resources` | QE, has pseudos | `"Use auto_resolve_species_map(calc_ulid=...) to auto-select pseudopotentials, or set_species_map() to choose manually."` |
| `list_available_resources` | QE, none installed | `"No pseudo libraries installed. Use download_pseudo_library(library='sssp') to install SSSP first, then auto_resolve_species_map() to auto-select."` |
| `list_available_resources` | VASP | `"Use set_species_map() with POTCAR variant names to configure. Example: {\"Si\": {\"pseudopot\": \"Si\"}}"` |
| `list_available_resources` | LAMMPS with potentials | `"LAMMPS potential files are referenced in input scripts. No species_map needed for LAMMPS."` |
| `list_available_resources` | LAMMPS without potentials | `"Set LAMMPS_POTENTIALS environment variable or place potential files in .qmatsuite/engines/lammps/potentials/."` |
| `auto_resolve_species_map` | unsupported engine | `"For VASP, use set_species_map() with POTCAR variant names. For molecular codes (ORCA, Gaussian, etc.), no species_map is needed."` |
| `auto_resolve_species_map` | resolution failed | `"Ensure the SSSP pseudo library is installed. Use download_pseudo_library(variant='precision') to install SSSP. Internal pseudos are available for: Si, Al, C, H, O, Fe, Cu, Li, He. Or use set_species_map(calc_ulid='{calc_ulid}', ...) to set manually."` |
| `auto_resolve_species_map` | success | `"Species map auto-resolved and applied. Use inspect_calculation(calc_ulid='{calc_ulid}') to review, then run_calculation(calc_ulid='{calc_ulid}') to execute."` |
| `download_pseudo_library` | invalid library | lists available library names |
| `download_pseudo_library` | success | `"Use auto_resolve_species_map(calc_ulid=...) to auto-select pseudopotentials for your calculation."` |
| `download_pseudo_library` | download failed | `"Check network connectivity."` |
| `cleanup_project` | no orphans | `"No orphaned references found. Project is clean."` |
| `cleanup_project` | dry run found orphans | `"Found {n} orphaned reference(s). Run cleanup_project(dry_run=False) to remove them."` |
| `cleanup_project` | cleaned | `"Removed {n} orphaned reference(s) from project.qms.yml."` |
| `list_analyses` | no capabilities | `"Engine '{engine}' has no declared analysis capabilities."` |
| `list_analyses` | default | `"Use plot_analysis(calc_ulid='{calc_ulid}', object_type='<type>') to parse and render an analysis."` |
| `plot_analysis` | analysis not found | `"Use list_analyses(calc_ulid='{calc_ulid}', step={step}) to see available types."` |
| `plot_analysis` | parse failed | `"Ensure the calculation has been run successfully."` |
| `plot_analysis` | success | `"Use list_analyses(calc_ulid='{calc_ulid}') to see other available analyses."` |
| `generate_kpath` | always | `"Use set_parameters(..., params={'K_POINTS': data['kpoints_card']}) to apply this k-path to a bands calculation step."` |
| `error_enrichment` | any recoverable error | `"Use set_parameters(calc_ulid='{calc_ulid}', params=...) to apply a fix, then run_calculation(calc_ulid='{calc_ulid}') to retry."` |
| `ping` | always | **(no context_hint)** |

### 4.3 Gap Analysis

**Missing hints**: Only `ping` has no context_hint, which is appropriate (it's a health check, not a workflow step).

**Incorrect hints**: None found. All referenced tool names exist.

**Weak hints**:
- `preview_compilation` → `"To commit, call create_calculation + apply_preset."` — Slightly misleading: the user has already committed to the engine/workflow; the correct framing is "to apply these presets to an existing calculation, call `apply_preset`."
- `run_calculation` failure → `"Check step messages for failure details."` — This is the *fallback* hint (when enrichment itself fails). The enriched path has much better guidance. But if enrichment fails, this is the only signal the agent gets.
- `plot_analysis` on parse failure → `"Ensure the calculation has been run successfully."` — Generic; doesn't tell the agent what to look for in the output.

**Design compliance** (vs §6.2 table in AGENT_INTEGRATION_DESIGN.md): The implemented hints match the design table exactly for the main happy-path tools. The implementation adds significantly more conditional variants than the design table shows (the design shows ~8 entries; the implementation has 71 variants). This is a positive extension.

---

## 5. Channel 3: Knowledge Base

### 5.1 Status

**builtin.db exists and is populated.**

- Location: `.qmatsuite/knowledge/builtin.db` (68 KB)
- Total entries: **20 active insights** (7 principles + 13 findings)
- Observations and bookkeeping: 0 (by design — those live in Layer 3 provenance only)
- Rebuild: deterministic, idempotent (ULID from SHA-256 of salt + index + content prefix)

### 5.2 Schema

```sql
CREATE TABLE insights (
    id TEXT PRIMARY KEY,
    grade TEXT NOT NULL,           -- 'principle' | 'finding' | 'observation' | 'bookkeeping'
    scope_engine TEXT DEFAULT '*', -- '*' | 'qe' | 'vasp' | 'abinit' | ...
    scope_workflow TEXT DEFAULT '*',
    scope_system_type TEXT DEFAULT '*',
    scope_method TEXT DEFAULT '*',
    scope_extra TEXT DEFAULT '{}', -- JSON for material, property, basis_set, etc.
    content TEXT NOT NULL,
    confidence TEXT DEFAULT 'medium', -- 'high' | 'medium' | 'low'
    source_type TEXT NOT NULL DEFAULT 'local',
    source_origin TEXT,
    ...status, superseded_by, contradiction_count, upvotes, timestamps...
);

CREATE VIRTUAL TABLE insights_fts USING fts5(
    content, tags, scope_engine, scope_system_type,
    content='insights', content_rowid='rowid'
);
```

Grade hierarchy (4 levels, only top 2 reach the knowledge base):
- **principle** (7): Cross-system general rules, highest confidence
- **finding** (13): Validated conclusions with evidence
- observation: Provenance Layer 3 only
- bookkeeping: Provenance Layer 3 only

### 5.3 Content Inventory

| Category | Count | Examples |
|----------|-------|---------|
| Error Recovery | 5 | SCF oscillation → reduce mixing_beta; energy divergence → check structure; charge sloshing → Kerker mixing |
| Smearing / Occupations | 3 | Metal → Methfessel-Paxton; insulator → fixed occupations; entropy term validation |
| Convergence Guidance | 4 | ecutwfc protocol; k-mesh protocol; production thresholds; QE ecutrho 8-12x rule |
| Workflow Sequencing | 6 | Always relax before properties; SCF→NSCF→bands; SCF→NSCF-dense→DOS; phonon requirements |
| Method-Specific | 4 | DFT+U Hubbard U values (3-8 eV); HSE06 (25% exchange); GW (10-20x empty bands); spin-polarized setup |
| Band Structure nbnd | 2 | QE nbnd formula; VASP NBANDS formula |
| Occupations Crash Recovery | 3 | QE metal MUST use smearing; IEEE crash fix; degauss=0.01 Ry safety default |

**Engine scope distribution**:
- Multi-engine (`scope_engine='*'`): 17 (85%)
- QE-specific: 2 (10%)
- VASP-specific: 1 (5%)

**Confidence distribution**:
- High confidence: 19 (95%)
- Medium confidence: 1 (5%)

### 5.4 Search Implementation

FTS5 BM25 via SQLite with ranking formula:
```
score = confidence_weight × |bm25_rank|
```
where confidence_weight ∈ {3.0 (high), 2.0 (medium), 1.0 (low)}, with secondary sort by grade (principles above findings).

Query sanitization: strips FTS5 operators (AND/OR/NOT/NEAR), keeps only `[a-zA-Z0-9_]+` tokens.

Two search modes: FTS + scope filter (when query provided) or scope-only (when query empty).

### 5.5 Return Schema

Each search result entry:
```json
{
  "id": "<ULID>",
  "grade": "principle" | "finding",
  "scope_engine": "*" | "qe" | ...,
  "scope_workflow": "scf" | "*" | ...,
  "scope_system_type": "metal" | "*" | ...,
  "scope_method": "dft" | "*" | ...,
  "content": "...(truncated to 300 chars)...",
  "confidence": "high" | "medium" | "low",
  "tags": "[\"tag1\", \"tag2\"]",
  "source_type": "builtin"
}
```

### 5.6 Gap Analysis

**The 20-entry count is at the low end** of the design's 30-50 target. The sparse coverage for non-QE engines is the main gap:

- ORCA-specific error recovery: 0 entries
- CP2K-specific error recovery: 0 entries
- ABINIT-specific error recovery: 0 entries (the 2 QE entries cover QE-specific crashes; ABINIT has its own failure modes)
- LAMMPS-specific guidance: 0 entries
- VASP: 1 entry (magnetic Fe ISMEAR guidance) — could use more

**The agent will fall through to UNKNOWN_FAILURE** when running ORCA/CP2K/ABINIT/LAMMPS without QE-style convergence signals. The knowledge base offers no engine-specific recovery guidance for these engines.

**Recommended additions** (to reach 35 entries):

| Proposed Entry | Grade | Engine | Category |
|----------------|-------|--------|----------|
| ORCA SCF convergence → SlowConv/TightSCF | finding | orca | error_recovery |
| ORCA geometry opt → MaxIter too low | finding | orca | error_recovery |
| CP2K cutoff convergence (CUTOFF vs REL_CUTOFF) | principle | cp2k | convergence |
| CP2K DIAG vs OT SCF solver tradeoff | finding | cp2k | methodology |
| ABINIT ecut vs pawecutdg for PAW | principle | abinit | convergence |
| ABINIT kptopt=3 for spin-orbit | finding | abinit | methodology |
| LAMMPS timestep rule (1/10 fastest vibration) | principle | lammps | methodology |
| VASP NELMIN=6 for difficult metals | finding | vasp | error_recovery |
| VASP ALGO=Fast vs Normal for metals vs insulators | principle | vasp | methodology |
| VASP LDAU_TYPE=2 for DFT+U | finding | vasp | methodology |
| Siesta mesh cutoff vs basis set completeness | principle | siesta | convergence |
| GPAW mode selection (PW vs LCAO) | principle | gpaw | methodology |
| Yambo QPkrange for efficient GW | finding | yambo | methodology |
| QMCPACK timestep extrapolation for DMC | principle | qmcpack | methodology |
| Gaussian basis set hierarchy (3-21G → 6-31G* → cc-pVTZ) | principle | gaussian | methodology |

---

## 6. Channel 4: Error Returns

### 6.1 Envelope Format

**Success** (`make_response`):
```json
{
  "status": "success",
  "data": { ... },
  "context_hint": "...",
  "warnings": []
}
```

**Error** (`make_error`):
```json
{
  "status": "error",
  "error_type": "SCF_NOT_CONVERGED",
  "message": "Human-readable summary",
  "severity": "recoverable",
  "context_hint": "...",
  "suggestions": [],
  "diagnostics": { ... },
  "suggested_fixes": [ ... ]
}
```

The `diagnostics` and `suggested_fixes` fields are **optional** (present only if not None). This matches the design doc §5.6 `ErrorReturn` schema. The implementation uses functions rather than dataclasses, but the field structure is identical.

### 6.2 Per-Tool Error Coverage

| Tool | Error Types | Diagnostics | Suggested Fixes | Notes |
|------|-------------|-------------|-----------------|-------|
| `run_calculation` | 5 structured types + fallback | Yes (for SCF/IONIC) | Yes (QE + VASP) | Most complete |
| `quick_run` | inherits run_calculation | Yes | Yes | Delegates to run_calculation |
| `set_parameters` | invalid_step_index | No | No | Simple validation error |
| `set_species_map` | missing_key, empty_map | No | No | Simple validation |
| `create_calculation` | unknown_engine, unknown_workflow, structure_not_found | No | No | Has context hints instead |
| `import_structure` | format errors | No | Partial (format tips in hint) | No structured diagnostics |
| `auto_resolve_species_map` | resolution_failed | No | Partial (hint lists alternatives) | |
| All others | generic exception → make_error | No | No | Only context hint guides recovery |

### 6.3 Error Enrichment Pipeline

The `error_enrichment.py` module recognizes 5 error types from calculation execution:

| Error Type | Severity | Detection Criteria | QE Fixes | VASP Fixes |
|-----------|----------|-------------------|----------|-----------|
| `SCF_NOT_CONVERGED` | recoverable | digest.converged==False, n_iterations>0, workflow==scf | reduce mixing_beta → 0.3; increase electron_maxstep → 200 | reduce AMIX → 0.2; increase NELM → 200 |
| `IONIC_NOT_CONVERGED` | recoverable | digest.converged==False, n_iterations>0, workflow in (relax,vc-relax) | tighten conv_thr → 1e-8 | tighten EDIFF → 1e-7 |
| `ENGINE_CRASH` | fatal | n_iterations==0 or exit_code!=0 without other signals | — | — |
| `OUT_OF_MEMORY` | recoverable | exit_code!=0, message contains oom/killed/signal 9 | reduce npool → 1 | — |
| `UNKNOWN_FAILURE` | error | any other failure | — | — |

**Knowledge base integration**: `_query_knowledge_for_error()` runs FTS5 search on builtin.db to enrich the `reason` field in suggested_fixes. This creates a direct link from Channel 4 to Channel 3.

### 6.4 Design Compliance

The design doc §5.6 `SuggestedFix` dataclass specifies: `action`, `parameter`, `from_value`, `to_value`, `confidence`, `reason`. The implementation includes all these fields. The design's `ErrorReturn` severity enum (`fatal | recoverable | warning`) is implemented. **Compliance: complete for QE/VASP SCF failures.**

**Gaps**:
- ORCA failures: No enrichment beyond ENGINE_CRASH or UNKNOWN_FAILURE
- CP2K failures: Same
- ABINIT failures: QE-like enrichment partially applicable (both use plane-wave SCF), but the field names differ
- `ENGINE_CRASH`: No suggested_fixes — the agent receives only the error type and must infer what to check

---

## 7. Channel 5: Preflight Messages

### 7.1 Implementation

**File**: `src/qmatsuite/drivers/qe/preflight.py` (393 lines)
**Only QE has a preflight implementation.** All other 14 engines return `None` from `get_preflight_checker()`.

### 7.2 Complete Rule Inventory (20 Rules)

**Blocking rules (6)** — agent cannot proceed without fixing:

| Code | Message (excerpt) | Parameter | Suggestion |
|------|-------------------|-----------|------------|
| `MISSING_ECUTWFC` | "ecutwfc is missing or non-positive." | `SYSTEM.ecutwfc` | "Set ecutwfc to at least 30 Ry (typical: 40-80 Ry)" |
| `MISSING_KPOINTS` | "No k-points specified for a periodic structure." | `K_POINTS` | "Add a K_POINTS card (e.g. automatic 4 4 4 0 0 0)" |
| `INVALID_CALCULATION_TYPE` | "calculation='{x}' is not a valid QE calculation type." | `CONTROL.calculation` | "Valid types: bands, md, nscf, relax, scf, vc-relax." |
| `NSCF_WITHOUT_SCF` | "'{current_gen}' step requires a preceding 'scf' step." | — | "Add an 'scf' step before this step in the workflow." |
| `NEGATIVE_DEGAUSS` | "degauss={x} is negative." | `SYSTEM.degauss` | "degauss must be non-negative (typical: 0.01-0.02 Ry)" |
| `ZERO_NAT` | "nat is explicitly set to 0." | `SYSTEM.nat` | "Remove nat or set it to the actual number of atoms." |

**Warning rules (8)** — agent should act, but can proceed:

| Code | Message (excerpt) | Parameter | Suggestion |
|------|-------------------|-----------|------------|
| `METAL_FIXED_OCC` | "Fixed occupations with metallic elements ({metals})." | `SYSTEM.occupations` | "Use occupations='smearing' with an appropriate smearing method." |
| `SPIN_UNPOLARIZED_MAGNETIC` | "nspin=1 (unpolarized) with magnetic elements ({elements})." | `SYSTEM.nspin` | "Consider nspin=2 for spin-polarized calculation." |
| `TETRAHEDRA_WITH_RELAX` | "Tetrahedra occupations with calculation='{x}'." | `SYSTEM.occupations` | "Use smearing for relaxation/MD calculations." |
| `TETRAHEDRA_METALS` | "Tetrahedra occupations with metallic elements." | `SYSTEM.occupations` | "Consider smearing for metals unless using tetrahedra_opt." |
| `SMEARING_NO_DEGAUSS` | "occupations='smearing' but degauss is not set." | `SYSTEM.degauss` | "Explicitly set degauss (typical: 0.01-0.02 Ry)" |
| `ECUTRHO_TOO_LOW` | "ecutrho={x} < 4*ecutwfc={y}." | `SYSTEM.ecutrho` | "ecutrho should be at least 4*ecutwfc (8-12x for ultrasoft/PAW)" |
| `VC_RELAX_FIXED_CELL` | "vc-relax with cell_dofree='{x}' restricts cell degrees of freedom." | `CELL.cell_dofree` | "Ensure this is intentional. Use cell_dofree='all' for full relaxation." |
| `MD_NO_TEMPERATURE` | "calculation='md' without tempw or ion_temperature." | `IONS.tempw` | "Set tempw (in K) or ion_temperature for MD runs." |

**Advisory rules (7)** — informational, no action required:

| Code | Message (excerpt) | Parameter | Suggestion |
|------|-------------------|-----------|------------|
| `LOW_ECUTWFC` | "ecutwfc={x} Ry is very low for production calculations." | `SYSTEM.ecutwfc` | "Most pseudopotentials need at least 30-40 Ry." |
| `LOOSE_CONV_THR` | "conv_thr={x} is loose. Results may be poorly converged." | `ELECTRONS.conv_thr` | "Use conv_thr <= 1.0e-6 for production (1.0e-8 for forces)." |
| `LOW_ELECTRON_MAXSTEP` | "electron_maxstep={x} may be too few SCF iterations." | `ELECTRONS.electron_maxstep` | "Default is 100. Increase for difficult convergence." |
| `GAUSSIAN_SMEARING_FOR_DOS` | "Gaussian smearing with a DOS workflow." | `SYSTEM.smearing` | "Use smearing='mp' or 'marzari-vanderbilt' for DOS workflows." |
| `LARGE_MIXING_BETA` | "mixing_beta={x} is large. SCF may oscillate." | `ELECTRONS.mixing_beta` | "Typical range: 0.1-0.7. Lower for difficult systems." |
| `ECUTWFC_VERY_HIGH` | "ecutwfc={x} Ry is unusually high. May waste compute time." | `SYSTEM.ecutwfc` | "Check pseudopotential cutoff recommendations." |
| `PARAM_WRONG_SECTION` | "'{param}' is in &{current} but QE expects it in &{expected}." | `{current}.{param}` | "Move '{param}' from {current} to {expected}." |

### 7.3 Where Preflight Appears

1. **`inspect_calculation(dry_run=True, step>=0)`**: Returns `preflight_issues` list. Each issue: `{code, severity, message, parameter, suggestion}`.
2. **`preview_compilation`**: Returns `preflight_issues` per compiled step. Each issue adds `step_index` and `step_type_gen`.

Preflight is **best-effort** — tool never fails because of preflight results.

### 7.4 Actionability Assessment

Every suggestion references the exact QE parameter to fix. The suggestion text is concise and LLM-actionable (e.g., "Set ecutwfc to at least 30 Ry"). The agent can directly translate suggestions into `set_parameters` calls.

**Severity is not yet exposed as a structured filter in the MCP envelope** — all preflight issues arrive in a flat list. The agent must inspect the `severity` field in each issue dict to distinguish blocking from advisory. This is workable but could be improved by grouping or surfacing blocking issues prominently.

### 7.5 Gap Analysis

**14 engines have zero preflight coverage.** For VASP, an agent could submit a calculation with `ISMEAR=-5` (tetrahedra) + `IBRION=2` (relaxation) — a physically incorrect combination — and receive no pre-run warning. The QE preflight rules W3/W4 show exactly this category of mistake is caught for QE.

Priority preflight additions:
- VASP: ISMEAR=-5 + IBRION check, ENCUT < ENMAX, MAGMOM missing for ISPIN=2
- ORCA: Incompatible keyword combinations (e.g., RI-MP2 without AuxBasis)
- ABINIT: Missing required tags (acell, rprim, natom)

---

## 8. Channel 6: Parameter Search

### 8.1 Implementation

**Algorithm**: Okapi BM25 (k1=1.5, b=0.75)
**Corpus**: ~1,000 parameter documents from 11 engines
**Source file**: `src/qmatsuite/mcp/search_index.py`

Tokenization: regex `[a-z0-9_]+` on lowercased combined field `{tag_name} {description} {category}`.

### 8.2 Corpus Sources

| Source Type | Engines | Field Mapping |
|-------------|---------|---------------|
| Module-structured | QE | `category=namelist`, `section=namelist`, from `_iter_params()` |
| Tags dict | VASP, ABINIT, CP2K, W90, xTB, Yambo, QMCPACK | `tags.{name}.{type,default,category,description}` |
| Keywords dict | ORCA, Gaussian | `keywords` (! line / # route), `blocks` (% sections) |
| Commands dict | LAMMPS | `commands.{name}.{type,default,category,description}` |

### 8.3 Return Schema

```json
{
  "query": "user query",
  "engine_filter": "qe" | null,
  "category_filter": null,
  "results": [
    {
      "engine": "qe",
      "tag_name": "ecutwfc",
      "type": "REAL",
      "default": null,
      "category": "SYSTEM",
      "description": "...(first 200 chars)...",
      "relevance_score": 4.23,
      "section": "SYSTEM"
    }
  ],
  "total_results": 5
}
```

**Description truncation**: 200 characters. This is tight. For parameters with long enum lists or complex valid-value tables, the agent sees only a fragment.

### 8.4 Documentation Quality Spot-Check

| Engine | Parameter | Type | Default | Enum | Description (200 chars) | Quality |
|--------|-----------|------|---------|------|------------------------|---------|
| QE | `ecutwfc` | from JSON | null | null | (from qe_module_parameters.json) | Good — no enum needed |
| QE | `occupations` | — | — | null | — | **Gap**: valid values {"fixed","smearing","tetrahedra"} not in enum field |
| QE | `smearing` | — | — | null | — | **Gap**: valid values {"gaussian","mp","marzari-vanderbilt",...} missing |
| VASP | `ENCUT` | REAL | "largest ENMAX in POTCAR" | null | "Plane-wave energy cutoff in eV." | Good |
| VASP | `ISMEAR` | INTEGER | "1" | null | "Smearing method. -5=tetrahedron, -1=Fermi, 0=Gaussian, 1=MP, 2=MP2." | **Good** — enum values embedded in description |
| VASP | `SIGMA` | REAL | "0.2" | null | "Width of smearing in eV." | Good |
| VASP | `ISPIN` | INTEGER | — | null | — | — |
| VASP | `EDIFF` | REAL | — | null | — | — |

**Key finding**: The `enum` field is present in the schema but is `null` for most parameters. For QE, valid values for `occupations` and `smearing` are embedded in the preflight code but not in the search index documents. An agent searching for "occupations" sees only the description — which may or may not enumerate the valid values within 200 chars. The VASP ISMEAR description does inline the enum values, which is the right pattern.

### 8.5 BM25 Quality Assessment

With k1=1.5 and b=0.75 (standard Okapi defaults), ranking quality for domain-specific terms should be adequate. The combined tokenization of `{tag_name} {description} {category}` means an exact tag name match ("ecutwfc") always ranks first due to high TF in a short field. Longer natural-language queries ("energy cutoff plane wave") will find `ecutwfc` via description match.

**Potential issue**: The query sanitizer strips ALL FTS5 operators. A user searching "not converged" will have "not" stripped (it matches `NOT` after uppercasing) and only "converged" searched. This is intentional (prevents injection) but could affect precision for negation queries.

---

## 9. Channel 7: Demo Store Metadata

### 9.1 Storage Architecture

- Demo project configs: `resources/demo_projects/*.yml` (50+ files)
- Pre-computed ref packs: `resources/demo_projects/ref_packs/<demo_slug>/manifest.json` + `<type>.json`
- Demo metadata loaded from YAML `meta:` section at search time

### 9.2 search_demos Output Schema

Each result in `demos` array:

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `ulid` | str | meta.ulid | Demo ID (e.g., "abinit_si_scf") |
| `title` | str | meta.title | Display title |
| `subtitle` | str | meta.subtitle | Workflow description |
| `description` | str | meta.description | Long description |
| `tags` | list[str] | meta.tags | Category tags |
| `difficulty` | str\|None | meta.difficulty | "beginner"\|"intermediate"\|"advanced" |
| `estimated_runtime_s` | float\|None | meta.estimated_runtime_s | Wall-time seconds |
| `system_class` | str | meta.system_class | "crystal"\|"molecule"\|"surface"\|"1d"\|"cluster" |
| `periodicity` | str | meta.periodicity | "periodic"\|"non-periodic" |
| `method` | str | meta.method | "dft-pbe"\|"hf"\|"mp2"\|"vmc-dmt"\|... |
| `property_of_interest` | str | meta.property_of_interest | "total_energy"\|"band_structure"\|"dos"\|... |
| `spin_treatment` | str | meta.spin_treatment | "nonmagnetic"\|"collinear"\|"noncollinear" |
| `multi_engine` | bool | meta.multi_engine | True for QE→W90, QE→Yambo workflows |
| `engines_used` | list[str] | meta.engines_used | e.g., ["qe", "w90"] |
| `n_steps` | int\|None | meta.n_steps | Number of steps |
| `step_summary` | str | meta.step_summary | e.g., "SCF → NSCF → Bands" |
| `available_analysis` | list[str] | meta.available_analysis | e.g., ["convergence", "bands"] |
| `engine` | str | injected | From meta.required_engine |
| `has_ref_pack` | bool | injected | True if ref pack exists |
| `ref_pack_types` | list[str] | injected | e.g., ["convergence", "bands"] |

**Wave 2 enrichment** is complete across all 52 demos. The metadata is rich enough that the agent can make an informed selection from `search_demos` output alone, without needing to call `get_demo_results` to decide.

### 9.3 get_demo_results Scalar Summaries

| Analysis Type | Summary Fields | Notes |
|---------------|---------------|-------|
| `convergence` | final_energy_eV, n_scf_steps, n_ionic_steps, converged, algorithm | |
| `bands` | reference_energy_eV, n_kpoints, n_bands, high_symm_labels | |
| `dos` | fermi_energy_eV, n_series, n_energy_points, energy_range_eV, series_labels | |
| `trajectory` | trajectory_type, n_frames, n_atoms, initial_energy_eV, final_energy_eV | |
| `field3d` | field_kind, grid_shape, value_min, value_max, value_mean, n_grid_points | |
| unknown | reference_energy, extra | fallback |

Raw array data (series x/y, eigenvalue matrices, DOS grids) is never included. The response is compact (~200-400 tokens per analysis type).

### 9.4 Assessment

The demo store is the strongest information channel. Wave 2 enrichment is thorough. The `load_demo` context hint explicitly tells the agent that structure auto-import happened (compensating for the tool description's silence on this). The ref packs provide pre-computed results that let the agent evaluate workflows without running calculations.

One minor gap: `search_demos` free-text query searches `title`, `subtitle`, `description`, and `tags` — but does **not** include `step_summary` or `method` in the text index. An agent searching for "Methfessel-Paxton" won't find metal demos via that term unless it appears in the description.

---

## 10. Channel 8: Proactive Injection

**Status: NOT IMPLEMENTED (Phase 2+ design)**

The design doc §7.8 describes proactive injection: when `create_calculation` or `quick_run` detects the material/engine/workflow context, it includes relevant high-confidence knowledge in the tool response under a `relevant_knowledge` field.

```json
{
  "calc_ulid": "01KC...",
  "relevant_knowledge": [
    {
      "grade": "principle",
      "content": "For metallic Fe with VASP, ISMEAR=1 converges 3x faster than Gaussian.",
      "confidence": "high",
      "source_type": "builtin"
    }
  ]
}
```

The design specifies:
- Only inject `finding` and `principle` grade entries
- Limit to top-K=3 by `confidence × scope_specificity`
- Engine+system+material scoped entries rank above wildcard entries

**Current state**: `create_calculation` does not query the knowledge base. No `relevant_knowledge` field appears in any tool response. This is expected for Phase 1.

**Readiness**: The knowledge base schema already has scope dimensions (`scope_engine`, `scope_system_type`, `scope_method`) that would enable scope-specific ranking. Adding injection to `create_calculation` is a well-defined Phase 2 task.

---

## 11. Channel 9: MCP Configuration

### 11.1 .mcp.json Content

```json
{
  "mcpServers": {
    "qmatsuite": {
      "type": "stdio",
      "command": ".venv/bin/python",
      "args": ["-m", "qmatsuite.mcp.server"]
    }
  }
}
```

**This is the complete file. There is no `instructions` field.**

### 11.2 Server Startup Behavior

The server performs auto-detection of project context at startup:

```python
# server.py lines 67-82
_project_dir = _Path(_os.environ.get("QMATSUITE_PROJECT", ".")).resolve()
try:
    from qmatsuite.core.project_utils import find_project_root as _find_project_root
    from qmatsuite.mcp.project import set_project_root as _set_project_root
    _found = _find_project_root(start=_project_dir) if _project_dir.exists() else None
    if _found is not None:
        _set_project_root(_found)
except Exception:
    pass  # Best-effort: don't prevent server from starting
```

This is correct and well-implemented. But the *agent* receives no information about this behavior — it doesn't know whether a project was found at startup, so it may still call `init_project` unnecessarily.

### 11.3 Gap Analysis

The `instructions` field in `.mcp.json` is the only mechanism to provide the agent with a system-prompt-level persona *before its first tool call*. Without it, the agent:

1. Has no guidance on the **Decision Hierarchy** (search demos first → try presets → configure manually → preflight → run)
2. Has no prompt to use `search_demos` as the first step for common requests
3. Has no reminder that `init_project` is idempotent and should be called first in a new session
4. Has no guidance on which engines are production-ready vs experimental
5. Has no token-budget hints (e.g., "use get_demo_results before load_demo to preview")

The context hints compensate *partially* — `init_project` hints lead to `search_demos`, `list_engines` hints lead to `search_demos`. But the agent must first call a tool before receiving any guidance, and which tool it calls first is entirely up to its own priors.

**Recommended `instructions` field** (draft):

```
QMatSuite is a computational materials science workflow manager for 15 simulation engines.

Decision Hierarchy for new calculations:
1. FIRST: search_demos() — pre-configured calculations with pre-computed results
2. If no demo: import_structure + create_calculation + get_presets (or search_parameters for non-QE)
3. Always: inspect_calculation(dry_run=True) before run_calculation — catches blocking errors
4. On failure: read suggested_fixes in the error return; query search_knowledge for recovery guidance

Key rules:
- Call init_project() at the start of every session (idempotent, safe to call repeatedly)
- For QE/ABINIT/Siesta/VASP: always set species_map via auto_resolve_species_map() first
- For ORCA/Gaussian/PySCF/xTB/GPAW: no species_map needed
- Presets (apply_preset) are QE-focused; other engines use set_parameters directly
- plot_analysis() returns ASCII plots + PNG paths; never ask for raw data arrays

Production-ready engines: QE, VASP, ORCA, ABINIT, CP2K, Gaussian, LAMMPS, Siesta, xTB, GPAW, Psi4, PySCF, QMCPACK, Yambo, Wannier90
```

---

## 12. Cross-Channel Analysis

### 12.1 Agent Workflow Walkthrough: Si Band Structure

Tracing a complete "calculate Si band structure" request through all information channels:

**Step 1: Session start**
- Channel 9 (MCP config): No instructions → agent has no guidance on where to start
- Agent's prior: likely calls `list_engines` or `search_demos` based on general Claude behavior
- If `list_engines`: hint → "Use search_demos()"
- **Gap**: Without instructions, agent's first action is unpredictable

**Step 2: search_demos(query="Si band structure")**
- Channel 7 (Demo store): Returns `qe_si_bands` demo with `step_summary="SCF → NSCF → Bands"`, `available_analysis=["convergence","bands"]`, `estimated_runtime_s=~45`, `has_ref_pack=True`
- Context hint: "Use get_demo_results or load_demo"
- **All information needed for decision is in the search result itself (Channel 7 excellent)**

**Step 3: load_demo("qe_si_bands")**
- Channel 2 (Context hint): "Demo loaded. Structure is in your project library — you do NOT need to import separately. Use run_calculation or inspect_calculation."
- **Channel 7 + Channel 2 working well together**

**Step 4: inspect_calculation(calc_ulid=..., step=0, dry_run=True)**
- Channel 5 (Preflight): Checks 20 QE rules. For a well-configured demo, likely no blocking issues.
- Result includes `preflight_issues: []`
- Context hint → "run_calculation"

**Step 5: run_calculation(calc_ulid=...)**
- Runs 3 steps: scf → nscf → bandspw
- On success: Channel 2 → "Use get_results_summary"
- On SCF failure: Channel 4 → structured error with suggested_fixes; Channel 3 (knowledge) enriches reason

**Step 6: get_results_summary(calc_ulid=...)**
- Returns energy, convergence status
- Context hint → "Use inspect_calculation for parameter details"

**Step 7: list_analyses(calc_ulid=...)**
- Returns ["convergence", "bands"]
- Context hint → "Use plot_analysis"

**Step 8: plot_analysis(calc_ulid=..., object_type="bands")**
- Channel 6 (search_parameters) not needed here
- Returns ASCII band structure + PNG path
- Context hint → "Use list_analyses to see other available analyses"

**Total tool calls (demo path)**: 6-8 calls. Every step has a guiding hint. **Channels 2 and 7 are the primary navigation system throughout.**

**Without demo (manual path)**:
1. import_structure / list_structures
2. create_calculation(engine="qe", workflow="bands", structure_selector=...)
3. auto_resolve_species_map(calc_ulid=...)
4. get_presets(engine="qe", workflow="bands") → apply_preset(...)
5. generate_kpath(structure_selector=...)
6. set_parameters(calc_ulid=..., step=N, params={K_POINTS: kpath}) [step=2 for bandspw]
7. inspect_calculation(calc_ulid=..., step=2, dry_run=True)
8. run_calculation(calc_ulid=...)
9. list_analyses / plot_analysis

**Total: 9-10 calls.** All guided by hints. The manual path exposes the agent to Channel 5 (preflight), Channel 6 (search_parameters if confused), and Channel 3 (search_knowledge if SCF fails).

### 12.2 Where the Agent Gets Stuck

1. **Cold start**: No instructions → agent may not know to call `init_project` or `search_demos` first. Relies on its general priors.

2. **Non-QE engine failure**: ORCA/CP2K/ABINIT crash → `UNKNOWN_FAILURE` with no suggested_fixes, no preflight warnings, no knowledge base entries. Agent receives `"Check step messages for failure details."` and must guess next steps.

3. **Parameter discovery for non-QE engines**: `search_parameters` returns results, but descriptions may be truncated at 200 chars with no enum values. For ORCA keywords like `TightSCF` or `SlowConv`, the agent may not know the valid keyword variants.

4. **Cross-engine workflow setup** (QE → Yambo, QE → Wannier90): The demo store has multi-engine demos, but if the agent builds from scratch, there's no guidance (no preflight, limited knowledge) on the data-passing protocol between engines.

5. **After promote_structure**: The hint says to call `create_calculation` with the new structure. But for non-trivial workflows (e.g., promoted relaxed structure → phonon calculation), the agent needs to know which workflow to use, which k-mesh, which ecutwfc. Channel 3 has some guidance but not engine-specific detail.

### 12.3 Information Redundancy

| Guidance Topic | Channels That Provide It |
|----------------|--------------------------|
| "Use smearing for metals" | Channel 3 (knowledge base), Channel 5 (preflight W1 METAL_FIXED_OCC), Channel 6 (ISMEAR description) |
| "Run SCF before NSCF/bands" | Channel 5 (preflight B4 NSCF_WITHOUT_SCF), Channel 3 (workflow sequencing entries), Channel 7 (demo step_summary) |
| "Set species_map first" | Channel 2 (create_calculation hint), Channel 1 (set_species_map description) |
| "Reduce mixing_beta for SCF oscillation" | Channel 4 (error enrichment suggested_fixes), Channel 3 (knowledge base), Channel 5 (advisory A5) |

This redundancy is **intentional and healthy** — the agent encounters the guidance at multiple points in a workflow, which is appropriate given that context hints don't persist across calls.

### 12.4 Token Budget Analysis (Typical 10-Call Workflow)

| Component | Tokens | Notes |
|-----------|--------|-------|
| Tool definitions (one-time, all 31) | ~5,400 | Paid once at session start |
| Per tool call: request | ~50 | Tool name + params |
| Per tool call: response | ~300-600 | Data + context_hint + warnings |
| Error with suggested_fixes | ~800-1,200 | Structured diagnostics |
| search_knowledge result (5 entries) | ~500 | 5 × 300 chars |
| search_parameters result (5 entries) | ~400 | 5 × 200 char descriptions |
| plot_analysis response | ~400 | ASCII plot + summary |
| **10-call workflow total (no errors)** | **~5,400 + 10 × 450 = ~9,900** | Typical |
| **10-call workflow with 1 error + recovery** | **~11,500-12,500** | Adds error + knowledge |
| **Context budget remaining** (200K window) | **~188,000** | Ample |

Token efficiency is excellent. The explicit exclusion of raw array data from `plot_analysis` and `get_demo_results` is a critical design decision that keeps responses compact.

---

## 13. Prioritized Recommendations

### P0: Blocking Issues (Agent Cannot Proceed)
*None identified.* The agent can complete calculations for QE with currently implemented channels.

### P1: Major Gaps (Agent Makes Poor Decisions)

**P1-1: Add `instructions` field to `.mcp.json`**
The agent has no initial persona, no Decision Hierarchy, and no "demos first" guidance. This is the highest-leverage single fix. A 200-token `instructions` block would orient every session correctly.

**P1-2: Expand knowledge base with 15+ non-QE entries**
Currently 17/20 entries are engine-agnostic; only 3 are engine-specific (2 QE, 1 VASP). An agent running ORCA/CP2K/ABINIT/LAMMPS has zero engine-specific recovery knowledge. Add at least 2-3 entries per major engine covering their most common failure modes.

**P1-3: Add preflight for VASP at minimum**
VASP is the second-most-used engine after QE. Its most common configuration errors (ISMEAR=-5 + IBRION; missing MAGMOM for ISPIN=2; ENCUT below ENMAX) are straightforward to check and directly analogous to QE rules W1, W2, and B1.

### P2: Quality Improvements (Agent Works But Suboptimally)

**P2-1: Fix `get_status` description**
Change "mainly useful for checking past runs" to something that accurately reflects its role as the primary status check. Suggested: *"Check the run state of all steps in a calculation. Use after run_calculation to verify completion or diagnose failure."*

**P2-2: Add enum values to parameter search index**
For QE parameters like `occupations` and `smearing`, the valid enum values are not in the search document (enum field is null). Populate enum from the preflight code's known-good value sets, and include enum values in the search document text so they appear within 200 chars.

**P2-3: Improve error enrichment fallback**
The `ENGINE_CRASH` and `UNKNOWN_FAILURE` types return no suggested_fixes. For ENGINE_CRASH, add a structured fix: check that the engine binary is installed, check disk space/memory, and look at the raw stderr. For UNKNOWN_FAILURE, include the step messages text in the diagnostics dict.

**P2-4: Fix `preview_compilation` context hint**
Current: *"To commit, call create_calculation + apply_preset."*
Better: *"To apply these presets to an existing calculation, call apply_preset(calc_ulid=..., presets=...). To create a new calculation with these presets, call create_calculation + apply_preset."*

**P2-5: Include `step_summary` and `method` in `search_demos` text index**
Agents searching for "Methfessel-Paxton" or "vc-relax" should find relevant demos without needing exact tag matches.

### P3: Future Enhancements (Phase 2+)

**P3-1: Implement proactive knowledge injection**
Add `relevant_knowledge` field to `create_calculation` and `quick_run` responses. Query knowledge base with `scope_engine + scope_system_type` filters. Limit to top-3 high-confidence entries. This is the design §7.8 feature.

**P3-2: Add preflight for CP2K, ORCA, ABINIT**
After VASP, extend preflight to the next-most-complex engines.

**P3-3: Expose preflight severity grouping**
In `inspect_calculation` dry_run output, surface blocking issues separately from advisories (e.g., `blocking_issues: [...]`, `advisory_issues: [...]`) rather than a flat `preflight_issues` list.

**P3-4: Knowledge pack system**
Phase 3 design: downloadable knowledge packs from QMatSuite hub. Infrastructure already in schema (`source_pack_id`, `source_type`).

**P3-5: Auto-invoke `search_knowledge` on error**
When `run_calculation` fails, the error enrichment pipeline already queries the knowledge base for the `reason` field. Consider also returning the top matching knowledge entry as a separate field in the error return, so the agent sees it without needing to manually call `search_knowledge`.
