# Revision Brief: AGENT_INTEGRATION_DESIGN.md

## Context

You previously wrote `docs/design/AGENT_INTEGRATION_DESIGN.md` based on the original design brief and `AGENT_DESIGN_REFERENCE.md`. The document is solid — well-grounded in the codebase, good tool catalog, strong philosophical foundation. However, after detailed design review, several architectural assumptions need correction and multiple areas need deepening. This revision brief describes ALL changes needed. Apply them comprehensively.

Read the existing `AGENT_INTEGRATION_DESIGN.md` first, then apply all revisions below. The result should be a single updated `.md` file that supersedes the original.

---

## REVISION 1: Tool Catalog Restructuring — "No Preset" as First-Class Workflow

### The Problem

The current design assumes a `preview_compilation → submit_calculation` happy path where presets are the primary way to configure calculations. **This does not match reality.** Currently:

- Only QE has partial preset-IR-engine mapping, and only for common parameters
- The other 14 engines have NO presets yet
- Even QE's preset coverage is incomplete — many parameters require direct engine-specific setting
- Preset expansion requires careful taste/judgment per engine and will happen AFTER MCP launch, not before

This means the MCP server must treat **direct engine-specific parameter setting** as a first-class workflow, not an "override" escape hatch.

### The Four Real Usage Scenarios

Design the tool catalog to support all four equally:

**Scenario A — Preset available, good enough**: Agent applies preset → optionally overrides a few params → run. This is the "quick win" path. ~80% of QE calculations with common workflows.

**Scenario B — No preset exists**: Agent queries parameter documentation (`search_parameters`) → sets engine-specific parameters directly through QMatSuite's parameter system → run. This is how ALL non-QE engines work today, and how uncommon QE parameters work.

**Scenario C — Preset as starting point, heavy modification**: Agent applies preset to get a baseline → overrides many parameters for specific research needs. Common for advanced users.

**Scenario D — Exploratory then refine**: Agent uses preset for a quick screening run → analyzes results → creates a new calculation with carefully tuned parameters based on what was learned. This is the scientific method in action.

### New Tool Catalog Design

Replace the current always-loaded tool catalog with a **fine-grained approach + one convenience shortcut**:

**Always-loaded tools (core cycle: discover → configure → run → analyze):**

1. `list_engines` — Available engines with installation status and capabilities. (Keep as-is.)

2. `list_workflows` — For a given engine, available workflow templates (step sequences). (Keep as-is.)

3. `get_presets` — For engine+workflow, available preset dimensions. **CRITICAL CHANGE**: Must clearly indicate when NO presets are available (e.g., `{"presets_available": false, "message": "No presets defined for VASP/scf. Use search_parameters to find relevant parameters and set_parameters to configure directly."}`)

4. `search_parameters` — **ELEVATED IMPORTANCE**. This is now the primary knowledge source for agents working without presets. BM25 search over tag JSONs. When no preset exists, the agent's workflow is: `search_parameters("convergence threshold VASP")` → learn about EDIFF → `set_parameters(calc_ulid, step, {INCAR: {EDIFF: 1e-6}})`.

5. `create_calculation` — **NEW**. Create a calculation directory with engine, workflow template, and structure. Persists immediately to `calculation.yaml`. Returns `calc_ulid`. Maps to `QMSService.Calculation.create()` or equivalent.

6. `set_parameters` — **NEW**. Set engine-specific parameters on a calculation's step. Persists immediately to the step's YAML. This is the primary configuration tool for no-preset workflows. Maps to `QMSService.Calculation.update_step_params()` or equivalent. Input should accept the engine's native parameter namespace (e.g., `{INCAR: {ENCUT: 520, EDIFF: 1e-6}}` for VASP, `{SYSTEM: {ecutwfc: 40}}` for QE).

7. `apply_preset` — **NEW** (extracted from old `submit_calculation`). Compile and apply preset dimensions to a calculation. Persists compiled parameters to YAML. Only available when presets exist for the engine+workflow combination. Maps to the preset compiler pipeline. Returns the compiled parameters so agent can see what was set.

8. `inspect_calculation` — **REPLACES `preview_compilation` for stateful queries**. Read the current state of a configured calculation from YAML. Shows all parameters currently set, their provenance (preset/manual/default), the structure, and the workflow steps. Optionally supports `dry_run: true` flag that materializes input files (calls the writer) and returns the generated input file content WITHOUT executing. Maps to reading `calculation.yaml` + `step.yaml`, with dry_run calling `write_engine_inputs()` to a temp dir.

9. `run_calculation` — **REPLACES `submit_calculation`**. Execute a configured calculation. Only runs — does not configure. Supports `dry: true` flag as alias for `inspect_calculation(dry_run=true)`. Maps to `QMSService.Run.run_calculation()`.

10. `get_status` — Check job status. (Keep as-is.)

11. `get_results_summary` — Token-efficient result summary. (Keep as-is.)

**Convenience shortcut (always-loaded):**

12. `quick_run` — **NEW**. One-shot: create calculation from workflow template + apply preset + run. Equivalent to `create_calculation` → `apply_preset` → `run_calculation` in one call. Designed for the 80% case where presets exist and are good enough. Input: engine, workflow, structure_ulid, preset dimensions, optional overrides, name. Returns: calc_ulid + job_id. This is what the "quick win" demo uses.

**Stateless what-if query (always-loaded):**

13. `preview_compilation` — **RETAINED but clarified**. This is a STATELESS query: "what would the compiled parameters look like if I applied these presets to this structure?" Does NOT create a calculation, does NOT write to disk. Returns compiled parameters + parameter provenance + optionally generated input file content. Useful for exploration before committing. Only works when presets are available (otherwise there's nothing to "compile").

So the three levels of pre-run inspection are:
- **`preview_compilation`** — Stateless what-if. No calculation exists yet. "What would standard precision Si bands look like?"
- **`inspect_calculation`** — Stateful read. Calculation exists, YAML is configured. "Show me what's currently set up."  
- **`inspect_calculation(dry_run=true)`** — Stateful materialization. "Generate the actual input files so I can verify the writer output."

**On-demand tools** — Keep the current deferred tools (analysis, structure, parameter tuning, project management) but review each for consistency with the new model.

**Move `list_structures` to on-demand** — Agent usually knows the structure or fetches it; doesn't need this in initial context.

### Updated Workflow Narratives

Add or revise workflow narratives showing:

**Narrative A (with preset):**
```
list_workflows(engine="qe") → get_presets(engine="qe", workflow="bands") → preview_compilation(stateless what-if) → quick_run(engine="qe", ..., presets={precision: "med"}) → get_status → get_results_summary
```

**Narrative B (without preset):**
```
list_workflows(engine="vasp") → get_presets(engine="vasp", workflow="scf") → returns presets_available=false → search_parameters(query="cutoff energy VASP") → search_parameters(query="k-points VASP") → create_calculation(engine="vasp", workflow="scf", structure_ulid="...") → set_parameters(calc_ulid, step=0, params={INCAR: {ENCUT: 520, EDIFF: 1e-6, ISMEAR: 1, SIGMA: 0.1}, KPOINTS: {grid: [8,8,8]}}) → inspect_calculation(calc_ulid, dry_run=true) → [agent checks input files look correct] → run_calculation(calc_ulid) → get_status → get_results_summary
```

**Narrative C (preset + heavy modification):**
```
create_calculation(engine="qe", workflow="bands", ...) → apply_preset(calc_ulid, presets={precision: "high"}) → set_parameters(calc_ulid, step=0, params={SYSTEM: {lda_plus_u: true, Hubbard_U: {Fe: 5.0}}}) → inspect_calculation(calc_ulid) → run_calculation(calc_ulid)
```

---

## REVISION 2: MCP as Equal Frontend — Architectural Principle

Add a new subsection (in Section 3 or as a standalone principle) that clearly states:

**QMatSuite's API facade (`QMSService`) is the ABI. ALL frontends are equal consumers:**

```
GUI (Electron)  ─┐
CLI              ─┤
MCP Server       ─┼── QMSService (API facade / ABI) ── Core Kernel
Daemon           ─┤
Jupyter (future) ─┘
```

**Rules:**
- MCP server MUST NOT call any core kernel code directly. Everything goes through `QMSService`.
- If MCP needs a capability that `QMSService` doesn't expose, the correct action is to ADD a method to `QMSService`, not to hack around it in MCP.
- DTO structures and error types should be designed to serve ALL frontends. If MCP needs richer error diagnostics (e.g., `suggested_fixes`), this should be added to the core `ErrorDTO`, benefiting GUI and CLI too.
- During MCP development, if the existing API/DTO/error hierarchy is insufficient, **propose core refactors rather than MCP-layer workarounds**. MCP development is expected to drive improvements to the core API.

---

## REVISION 3: Four-Layer Memory Architecture (replaces Section 7)

Replace the current three-timescale memory with a precise four-layer model:

### Layer 1: Agent Context (ephemeral)
- The LLM's context window, managed by the client (Claude Code, Gemini CLI, etc.)
- QMatSuite cooperates by returning token-efficient data
- Ephemeral — lost when conversation ends or compacts
- QMatSuite NEVER assumes the agent remembers a previous tool return

### Layer 2: Present-Tense SSOT (current state, flat)
- **Storage**: `calculation.yaml`, `step.yaml`, `raw/*.in`, `raw/*.out`, `raw/artifacts/`
- **Semantics**: "What IS the current state of this calculation?" Always flat, always current.
- **Key property**: YAML is the single source of truth. Every `set_parameters`, `apply_preset` call immediately persists to YAML. Runtime logic reads YAML directly — never queries provenance or history to determine current state.
- **Agent access**: `inspect_calculation` reads this layer.

### Layer 3: Provenance (append-only ledger, project-scoped)
- **Storage**: `.provenance/` directory — SQLite run history + `.cas` content-addressable store
- **Semantics**: "What HAPPENED?" An immutable audit trail of all actions and their outcomes.
- **Key property**: Append-only. Never modified. Never used as runtime logic base. This is the "court of final record."
- **What gets recorded**:
  - Agent intent: WHY a calculation was submitted (via `record_intent`)
  - Run metadata: WHEN it ran, WHAT parameters were used (auto-recorded by QMatSuite)
  - Result digest: WHAT came out — energy, convergence, key properties (auto-recorded)
  - Agent interpretation: WHAT the agent concluded from the results (via `record_interpretation`)
- **Agent access**: `get_project_history`, `get_provenance`
- **Critical design point**: Intent is NOT part of present-tense SSOT. Presets encode intent structurally (e.g., "precision=high" IS the intent). But the textual rationale ("testing U=5 because literature suggests 4-6 eV range") lives ONLY in provenance.

### Layer 4: Knowledge Base (evolvable best-knowledge, multi-scope)
- **Storage**: `~/.qmatsuite/knowledge.db` (SQLite, user-global)
- **Semantics**: "What have we LEARNED?" Distilled insights from accumulated experience.
- **Key property**: Unlike provenance, this IS mutable — insights can be updated, superseded, deduplicated. This is the agent's "best current understanding," not an audit trail.
- **Two scopes**:
  - **Project-scope insights**: "For this specific FeO system, U=5 eV is optimal." Relevant within a project context.
  - **Global-scope insights**: "Transition metal oxides generally need U in the 4-6 eV range." "Methfessel-Paxton smearing converges faster for metals." Relevant across all projects.
- **Relationship to provenance**: Knowledge is DISTILLED from provenance. The provenance ledger has individual entries like "U=5 gave bandgap=2.5 eV" and "U=7 gave bandgap=3.1 eV." The knowledge base synthesizes: "For FeO, U=5 eV best matches experiment." Agent can be asked to review provenance and update/generate knowledge entries.
- **Deduplication**: When a new insight contradicts an existing one, the old insight is superseded (marked with `superseded_by` reference), not deleted. History is preserved.
- **Agent access**: `search_knowledge`, `record_insight`, `update_insight`

### The Distillation Pipeline (future, Phase 3+)

```
Provenance entries (raw experience)
    ↓ Agent reviews and synthesizes
Project-scope knowledge (specific to this system/project)  
    ↓ Agent generalizes across projects
Global-scope knowledge (general computational wisdom)
```

This mirrors how researchers build expertise: individual experiments → project-specific conclusions → general domain knowledge accumulated over a career.

**Implementation note**: The full distillation pipeline is Phase 3+. In Phase 1-2, provenance handles everything. Knowledge base is a "good to have" that makes the agent smarter over time. Provenance is the "court of final record" — all truth can be reconstructed from provenance even if the knowledge base is empty or wrong.

---

## REVISION 4: Provenance Interaction Protocol

Add a new section (or subsection of Memory Architecture) defining the standard agent-provenance interaction for each research cycle:

### The Research Cycle Protocol

```
1. INTENT — Before running:
   record_intent(calc_ulid, reason="Testing Hubbard U=5 eV for FeO to match exp. bandgap of 2.4 eV")
   → Appended to provenance journal

2. EXECUTE — During run:
   run_calculation(calc_ulid)
   → QMatSuite auto-records: run start time, full parameter snapshot, engine version
   → QMatSuite auto-records on completion: result digest (energy, convergence, wall time, key properties)

3. INTERPRET — After analyzing results:
   record_interpretation(calc_ulid, interpretation="U=5 gives bandgap=2.5 eV, within 0.1 eV of experiment. Acceptable for screening. HSE06 needed for publication-quality gaps.")
   → Appended to provenance journal

4. LEARN (optional) — When a pattern emerges across calculations:
   record_insight(scope="project", insight="For this FeO system, PBE+U with U=5 eV reproduces experimental bandgap within 5%", evidence=[calc_ulid_1, calc_ulid_2, ...])
   → Written to knowledge base
```

### New MCP Tools for Provenance

- `record_intent(calc_ulid, reason: str)` — Record WHY this calculation is being run. Called before `run_calculation`.
- `record_interpretation(calc_ulid, interpretation: str)` — Record WHAT the agent concluded. Called after analyzing results.
- Both are thin wrappers around journal entry creation in the provenance system.

### What Gets Auto-Recorded (no tool call needed)

- Run start/end timestamps
- Full parameter snapshot at time of execution
- Result digest (energy, forces, convergence, etc.)
- Engine version and execution environment

---

## REVISION 5: Writer-Only Input Generation (add new section or subsection)

Add a section titled "Input Generation Integrity" or similar:

### Principle: All Input Files Go Through QMatSuite's Writers

The agent is NEVER allowed to bypass QMatSuite and write engine input files directly. All parameter setting goes through `set_parameters` → YAML → writer materialization. This ensures:

- **Provenance completeness**: Every parameter is tracked and recorded
- **Validation**: QMatSuite validates parameters against engine-specific schemas
- **Reproducibility**: Any calculation can be reconstructed from YAML
- **Consistency**: The SSOT (YAML) always matches what was actually run

### When the Writer Has a Bug

If the writer generates incorrect input for a specific parameter combination:
- The `dry_run` flag on `inspect_calculation` / `run_calculation` is the primary debugging tool — it materializes input files without executing, so the agent (or user) can inspect and catch issues
- The correct response is to REPORT the writer bug, not to work around it
- Agent should NOT attempt to manually edit generated input files
- The user should file an issue or fix the writer; future calculations benefit from the fix

### Writer Reliability Expectations

Structured writers are inherently more reliable than hand-written input files because they enforce type checking, enum validation, and mutual exclusion rules. However, given that QMatSuite is in active development:
- Engine-specific parameter coverage varies across engines
- Some parameter combinations may not be well-tested
- The `dry_run` → inspect flow provides a safety net
- MCP development may uncover writer gaps that should be fixed in the writer, not worked around in MCP

---

## REVISION 6: Batch Submission Support

Add `submit_batch` and `get_batch_status` tools to the catalog:

### `submit_batch` (on-demand, defer_loading: true)

Submit multiple independent calculations in parallel. Creates and runs each calculation as a separate job. Useful for parameter scans, convergence tests, and screening workflows.

**Input**: Array of calculation specifications (each with engine, workflow, structure, presets/params, name).
**Output**: Array of {calc_ulid, job_id} pairs.
**Behavior**: Each calculation gets its own `calculation.yaml`, its own job. Different calculations CAN run in parallel (QMatSuite allows parallel jobs across different calculations, just not within a single calculation).

### `get_batch_status` (on-demand, defer_loading: true)

Poll status of multiple jobs at once. Returns status array.

**Implementation note**: These tools internally loop over `create_calculation` + `run_calculation` for each item. The batch is a UX optimization (fewer tool calls for the agent), not a new execution model.

---

## REVISION 7: Long-Running Job Design — Fire and Forget

Add a subsection addressing the workflow for calculations that take hours:

### The Fire-and-Forget Pattern

For long-running DFT calculations (hours on HPC):

```
Session 1 (submit):
  Agent: create_calculation(...) → set_parameters(...) → record_intent(calc_ulid, "Running high-precision HSE06 band structure for CsPbI3") → run_calculation(calc_ulid) → get_status(job_id) → "Job queued, estimated 4 hours."
  Agent: "Your HSE06 calculation is submitted. It should complete in ~4 hours. Come back and ask me to check on it."
  [User closes conversation]

Session 2 (check, hours/days later):
  User: "How's my CsPbI3 calculation going?"
  Agent: get_project_history(status="all") → finds the HSE06 calc → get_status(job_id) → "completed"
  Agent: get_results_summary(calc_ulid) → analyzes
  Agent: record_interpretation(calc_ulid, "HSE06 bandgap = 1.73 eV, in excellent agreement with experiment.")
```

**Key enabler**: Provenance records enough context (intent, parameters, structure) that the agent can fully reconstruct what was happening without any conversation history from Session 1.

**Future optimization**: MCP Notifications could eliminate polling — the server pushes a notification when a job completes. For v1, polling via `get_status` is sufficient. Mention Notifications as a future enhancement in the design.

---

## REVISION 8: Phase Redefinition — Capability Closures

Redefine phases around what capability the user gains at each milestone. Remove Phase 0 (it had no user value on its own). Four phases, each is a meaningful demo:

### Phase 1: RUN — "Agent can complete a real calculation end-to-end"

**User story**: Researcher says "Calculate Si band structure with QE" → agent discovers capabilities → configures → runs → returns results.

**Milestone demo**: Si SCF with QE, end-to-end. User says one sentence, gets energy + convergence status back.

**Tools implemented**: `list_engines`, `list_workflows`, `get_presets`, `create_calculation`, `set_parameters`, `apply_preset`, `preview_compilation`, `inspect_calculation` (with dry_run), `run_calculation`, `quick_run`, `get_status`, `get_results_summary`, `search_parameters`, `list_structures`.

**Core milestone**: The "wow" moment. Agent can do a simple calculation that would take a new user 30 minutes to set up manually.

### Phase 2: RECOVER — "Agent can handle errors and do real research"

**User story**: Agent submits a calculation that fails SCF convergence → gets structured diagnostics → applies suggested fix → previews the fix → resubmits → succeeds. Also: agent does parameter scans (U-parameter, convergence testing).

**Milestone demo**: FeO U-parameter scan. Agent submits 5 calculations, compares bandgaps, identifies optimal U.

**Tools added**: `submit_batch`, `get_batch_status`, `compare_calculations`, structured error diagnostics with `suggested_fixes` in error returns, `record_intent`, `record_interpretation`.

**Also in Phase 2**: Detailed analysis tools (`get_band_structure`, `get_dos`, `get_convergence_history`, `get_output_raw`), MCP Apps for visualization (start with convergence dashboard and band structure viewer — these are 2D Plotly, simplest to implement; defer 3D structure viewer to Phase 4).

**Core milestone**: Agent handles failure gracefully. Agent can do multi-calculation research. Results are visualized interactively.

### Phase 3: LEARN — "Agent remembers and builds expertise"

**User story**: Agent starts a new project involving a metallic system → queries knowledge base → finds that Methfessel-Paxton smearing works best for metals (learned from previous project) → applies this knowledge automatically.

**Milestone demo**: Multi-session perovskite study. Session 1: screening. Session 2 (days later): agent recovers full context from provenance, continues detailed calculations.

**Tools added**: `get_project_history`, `get_provenance`, `annotate_calculation`, `search_knowledge`, `record_insight`, `update_insight`. Knowledge base SQLite + FTS5 implementation. Provenance interaction protocol fully implemented.

**Also in Phase 3**: Structure fetching tools (`fetch_structure`, `import_structure`), `diff_presets`, `get_parameter_detail`. defer_loading and Tool Search compatibility for the full tool catalog.

**Core milestone**: Agent doesn't start from scratch. Accumulated wisdom persists across sessions and projects.

### Phase 4: MASTER — "Agent operates QMatSuite with full fluency"

**User story**: Agent operates remotely on HPC, manages complex multi-engine workflows, generates publication-quality visualizations, helps write methods sections.

**Tools added**: 3D structure viewer (Three.js/NGL MCP App), parameter space explorer. Streamable HTTP transport for remote deployment. OAuth 2.0. SLURM integration. Full MCP Notifications support (push instead of poll).

**Also in Phase 4**: Security hardening, rate limiting, comprehensive documentation, tutorials, paper writing.

**Core milestone**: Production-ready. Agent is a fully capable research assistant.

---

## REVISION 9: Minor Corrections and Additions

### 9a: Notifications mention
In the deployment/architecture section, mention MCP Notifications as a future optimization for long-running jobs. Currently using polling, but the protocol supports server-initiated notifications when job status changes.

### 9b: MCP Apps phasing
In the MCP Apps section, note the implementation order: Phase 2 starts with 2D Plotly-based apps (convergence dashboard, band structure viewer, DOS viewer) because they're simplest and the MCP Apps protocol is very new (Jan 2026). 3D viewers (structure viewer with Three.js/NGL) and complex interactive tools (parameter space explorer) are Phase 4 after the protocol has matured.

Also note that QMatSuite already has an `AnalysisObject → canonical primitive → processed primitive → viz module` pipeline. MCP Apps are just another viz module consuming the same processed primitives (1D/2D/3D arrays + metadata). Implementation cost is low because the data pipeline already exists — only the renderer (HTML/JS in iframe) is new.

### 9c: Resource design
In Section 4 (MCP Primitives), note that Resources should be kept lightweight. The heavyweight parameter lookup is handled by the `search_parameters` tool, not by Resources. Resources provide summary-level reference data:
- `qmatsuite://engines` — brief list of engines and capabilities
- `qmatsuite://presets/{engine}/{workflow}` — preset dimension summary (not full compiled parameters)

Don't over-invest in Resource design — most agent interaction is through Tools.

### 9d: `submit_calculation` → `run_calculation` rename
Throughout the document, rename `submit_calculation` to `run_calculation` for consistency with the new fine-grained model. The word "submit" implies "create + configure + run" bundled together; "run" clearly means "execute what's already configured."

### 9e: Always-loaded count
With the new catalog, there are ~13 always-loaded tools. This is more than the original 9, but justified because the fine-grained configuration tools (`create_calculation`, `set_parameters`, `apply_preset`) are essential for the no-preset workflow. The tradeoff is ~3,500-4,000 tokens of tool definitions in initial context, which is acceptable given that these tools cover 95%+ of all agent interactions. The deferred tools (analysis, structure, batch, knowledge) add zero tokens until needed.

---

## Writing Instructions

1. **Preserve what's good.** Section 2 (Philosophical Foundation), Section 8 (Error Recovery), Section 11 (Competitive Differentiation), Section 12 (Security) are largely fine. Update them for consistency with the new tool names but don't rewrite from scratch.

2. **Section 5 (Tool Catalog) needs the most work.** Redesign it completely per Revision 1. Every always-loaded tool needs full JSON Schema definitions, example inputs/outputs, and "Maps to" code paths. The on-demand tools can remain as tables.

3. **Section 7 (Memory) needs replacement.** Replace with the four-layer model from Revision 3. This is a deeper, more precise treatment.

4. **Add new sections** for: Provenance Interaction Protocol (Revision 4), Writer Integrity (Revision 5). These can be subsections of existing sections if that flows better.

5. **Re-examine the codebase** for any new tools. The fine-grained model (create_calculation, set_parameters, apply_preset) needs to map to actual QMSService methods. If these methods don't exist yet, note what would need to be added to QMSService. Remember: MCP should drive core API improvements, not hack around gaps.

6. **Update all workflow examples** (Section 9) to use the new tool names and show both with-preset and without-preset paths.

7. **Update the roadmap** (Section 15) per Revision 8 — four phases defined by capability closure.

8. Save the updated document to the same path: `docs/design/AGENT_INTEGRATION_DESIGN.md`
