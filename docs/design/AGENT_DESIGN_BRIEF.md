# Task Brief: Write QMatSuite Agent Integration Design Document

## Your Role

You are writing the **overarching design document** for QMatSuite's AI agent integration. This document will serve as the master blueprint from which all implementation plans, roadmaps, and technical specs will derive. It must be technically precise, strategically visionary, and grounded in the actual codebase.

## Context

QMatSuite is an AI-native materials simulation IDE supporting 15 computational engines (QE, VASP, ORCA, CP2K, LAMMPS, ABINIT, Gaussian, Siesta, W90, GPAW, Psi4, PySCF, xTB, QMCPACK, Yambo). The architecture has three layers: Intent (workflows + presets), IR (engine-agnostic intermediate representation), and Engine-specific (native parsers/writers). SSOT is maintained through `calculation.yaml` and `step.yaml` files with ULID-based referencing.

## Strategic Direction (ALREADY DECIDED — do not debate)

1. **MCP-first**: QMatSuite exposes capabilities as an MCP server. No LangGraph, no LangChain, no CrewAI.
2. **BYOE (Bring Your Own Engine)**: Users connect via their own Claude Code / GPT Codex CLI / Gemini CLI. QMatSuite does NOT manage LLM API keys or host agents.
3. **Less is more**: One powerful agent + excellent tools > multi-agent orchestration framework. The agent (Claude Code etc.) is already intelligent; QMatSuite gives it hands and feet.
4. **Tool-centric architecture**: QMatSuite is AI infrastructure, not an AI product. It empowers any agent that speaks MCP.

## Reference Materials

Read these files in the repo before starting:

1. **`AGENT_DESIGN_REFERENCE.md`** (attached separately) — Comprehensive research on MCP spec features, context engineering, advanced tool patterns, scientific MCP ecosystem, cognitive science foundations, and agent architecture consensus. This is your primary knowledge source for state-of-the-art patterns.
2. **`AGENT_ARCHITECTURE_DEEP_DIVE.md`** — Technical analysis of 5 competitor systems (El Agente, ChemGraph, VASPilot, DREAMS, Masgent)
3. **`COMPETITOR_ANALYSIS_REPORT.md`** — Strategic competitor landscape
4. **`ANALYSIS.md`** — Additional analysis notes

## What You Must Do First

Before writing ANY design content, thoroughly explore the codebase to understand:

1. **Current RPC API surface**: What endpoints exist? What DTOs are used? What's the request/response structure?
2. **The three-layer abstraction**: How do workflows, presets, IR, and engine-specific layers actually work in code?
3. **SSOT files**: What's the actual schema of `calculation.yaml` and `step.yaml`? What data lives in each?
4. **Parser/Writer system**: How do the 15 engine parsers/writers work? What's their interface?
5. **Preset system**: How are presets defined, compiled, and applied? How does mathematical reversibility work?
6. **Project/calculation data model**: SQLite schema, file organization, provenance tracking
7. **Test infrastructure**: Existing RPC contract tests, real-run smoke tests
8. **GUI-backend communication**: How does the React frontend talk to the Python backend?

This codebase exploration is ESSENTIAL. The design doc must map MCP tools to ACTUAL existing abstractions, not hypothetical ones.

## Document Structure

Write a single `.md` file with the following structure. Every section should be substantive — no placeholder text.

---

### 1. Executive Summary (1 page)

- What we're building and why
- The BYOE paradigm shift vs competitors
- Three-sentence value proposition for researchers, for the paper, and for adoption

### 2. Philosophical Foundation: The Intelligent Researcher Model

This section is our **conceptual innovation** — publishable framing that differentiates us.

**Core metaphor**: The agent is not a workflow executor (like LangGraph pipelines). The agent is an **intelligent researcher** who happens to have QMatSuite as their lab equipment. Just as a human researcher has:
- **Hands** (run calculations) — QMatSuite MCP tools
- **Eyes** (observe results) — Structured result returns + MCP Apps visualization
- **Memory** (remember what worked) — Project-level provenance + agent memory
- **Judgment** (decide what to do next) — The LLM itself
- **Lab notebook** (record everything) — SSOT files + structured logging

**Draw from cognitive science** (CoALA framework, A-MEM, ACE):
- Map working memory → agent context window
- Map episodic memory → project history (calculation provenance in SQLite/.cas)
- Map semantic memory → engine parameter knowledge (tag JSONs, preset definitions)
- Map procedural memory → accumulated strategies ("for metals, use Methfessel-Paxton smearing")

**Draw from scientific method**:
- Hypothesis → Plan formulation (agent decides what to calculate)
- Experiment → Calculation execution (MCP tool calls)
- Observation → Result analysis (structured returns + visualization)
- Reflection → Strategy update (agent notes what worked, adjusts approach)

**Draw from context engineering**:
- Every token returned by a tool is a bet against accuracy (Anthropic)
- 100:1 input-to-output ratio means tool returns must be ruthlessly concise (Manus)
- Use filesystem as externalized memory (Manus) → our SSOT files serve this role
- Manipulate attention through recitation (Manus) → agent updates todo.md with research plan

This section should be 2-3 pages. It's what makes the paper novel — not "we wrapped DFT in an API" but "we designed a cognitive architecture for computational materials research."

### 3. Architecture Overview

**Diagram** (ASCII art is fine):

```
┌─────────────────────────────────────────────────┐
│  User's AI Agent (Claude Code / Codex / Gemini) │
│  ┌─────────────┐  ┌──────────┐  ┌────────────┐  │
│  │ LLM Engine  │  │ Context  │  │ Sub-agents │  │
│  │ (their sub) │  │ Manager  │  │ (optional) │  │
│  └──────┬──────┘  └────┬─────┘  └─────┬──────┘  │
│         └──────────────┼───────────────┘         │
│                        │ MCP Protocol            │
└────────────────────────┼─────────────────────────┘
                         │ stdio / Streamable HTTP
┌────────────────────────┼─────────────────────────┐
│  QMatSuite MCP Server  │                         │
│  ┌─────────────────────┴──────────────────────┐  │
│  │           Tool Router + Registry           │  │
│  │  (defer_loading, Tool Search compatible)   │  │
│  ├────────────┬────────────┬──────────────────┤  │
│  │ Discovery  │ Execution  │ Analysis         │  │
│  │ Tools      │ Tools      │ Tools            │  │
│  ├────────────┴────────────┴──────────────────┤  │
│  │         QMatSuite Core (existing)          │  │
│  │  Intent Layer → IR Layer → Engine Layer    │  │
│  ├────────────────────────────────────────────┤  │
│  │  SSOT: calculation.yaml + step.yaml        │  │
│  │  Project DB: SQLite + .cas files           │  │
│  ├────────────────────────────────────────────┤  │
│  │  15 Engine Parsers/Writers                 │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

Explain each layer. Map to actual code modules/classes.

### 4. MCP Primitives Mapping

Explain how we use each MCP primitive:

| MCP Primitive | QMatSuite Usage | Example |
|---|---|---|
| **Tools** | Actions that modify state or compute | `submit_calculation`, `create_project` |
| **Resources** | Read-only reference data | Engine parameter schemas, preset definitions |
| **Elicitation** | Human-in-the-loop confirmation | Pre-submission review, resource allocation |
| **Sampling** | Server-side LLM reasoning | Error diagnosis, output section parsing |
| **Tool Output Schema** | Machine-readable results | Energy, bandgap, convergence status |
| **MCP Apps** | Interactive visualization | Band structure plots, convergence curves |
| **Tasks** | Long-running async operations | HPC job monitoring |

For each, explain WHY this primitive (not another) and give a concrete QMatSuite example.

### 5. Tool Design: The Complete Tool Catalog

This is the CORE of the document. Design every tool we need, organized by phase.

#### 5.1 Design Principles

Based on the design reference, articulate our tool design principles:

1. **Progressive Disclosure**: Discovery → Preview → Execute → Analyze (agent never needs all tools at once)
2. **Token Efficiency**: Every return is minimal by default; agent requests more detail explicitly
3. **Structured + Human-Readable Dual Returns**: Every tool returns both `structuredContent` (for agent) and `content` (for user)
4. **Self-Describing**: Rich JSON Schemas with defaults, constraints, mutual exclusions, and `input_examples`
5. **Idempotent Discovery**: Discovery/preview tools have zero side effects
6. **Error as Data**: Failures return structured diagnostics, not stack traces

#### 5.2 Always-Loaded Tools (defer_loading: false)

These ~8-10 tools are always in context. They are the agent's "dashboard":

- **`list_engines`**: Available engines, which are installed, capabilities of each
- **`list_workflows`**: For a given engine, what workflows are available (SCF, relax, bands, DOS, etc.)
- **`get_presets`**: For engine+workflow, available presets (fast/standard/precise) with brief descriptions
- **`preview_compilation`**: ⭐ KILLER FEATURE — given engine+workflow+preset+structure+optional overrides, return the FULL compiled parameters and generated input file WITHOUT executing. Let agent and user inspect before committing.
- **`submit_calculation`**: Submit a prepared calculation for execution
- **`get_status`**: Check calculation status (queued/running/converging/done/failed)
- **`get_results_summary`**: Token-efficient summary (5-10 key values: energy, bandgap, forces, convergence, wall time)
- **`search_parameters`**: BM25/fuzzy search over engine parameter documentation (tag JSONs)
- **`get_project_history`**: Query past calculations in current project (the "lab notebook")

For each tool, specify:
- Name, description (for Tool Search discovery)
- Input schema (JSON Schema with actual parameter names from the codebase)
- Output schema (structuredContent shape)
- Example input/output
- Which existing QMatSuite module/function it maps to

**`preview_compilation` deserves special attention**: This is what NO competitor has. Explain how it leverages the mathematical reversibility between presets and underlying parameters. Show the full flow: agent says "Si band structure with standard preset" → preview shows ecutwfc=40 Ry, k-path L-G-X-W-K, nbands=12, etc. → agent can say "increase ecutwfc to 60" → preview updates → user confirms → submit.

#### 5.3 On-Demand Tools (defer_loading: true)

These are discovered via Tool Search when needed. Organize by category:

**Structure Tools** (~5-8):
- `fetch_structure(source, identifier)` — from Materials Project, AFLOW, COD, or local
- `create_structure(spacegroup, lattice, atoms)` — from crystallographic data
- `modify_structure(operations)` — supercell, slab, vacancy, substitution
- `visualize_structure()` — returns MCP App with 3D viewer

**Detailed Analysis Tools** (~5-8):
- `get_results_detailed(calc_id, property)` — full data for specific property
- `get_band_structure(calc_id)` — k-resolved eigenvalues + MCP App with interactive plot
- `get_dos(calc_id)` — density of states data + MCP App
- `get_convergence_history(calc_id)` — SCF iteration data + MCP App with convergence curve
- `compare_calculations(calc_ids)` — side-by-side comparison of multiple runs
- `get_output_raw(calc_id, line_range?)` — escape hatch to raw output when structured data insufficient

**Parameter Tuning Tools** (~3-5):
- `diff_presets(engine, workflow, preset_a, preset_b)` — what changes between presets
- `get_parameter_schema(engine, workflow)` — full JSON Schema for all parameters
- `suggest_parameters(system_type, property_of_interest)` — expert recommendations based on system characteristics

**Project Management Tools** (~3-5):
- `create_project(name, description)`
- `list_projects()`
- `get_provenance(calc_id)` — full lineage: what led to this calculation
- `annotate_calculation(calc_id, notes)` — add researcher notes

For each category, show how it maps to actual QMatSuite modules.

#### 5.4 Tool Return Format Standard

Define a standard return envelope. Based on the design reference:

```python
# Structured return (for agent consumption)
{
    "status": "success" | "error" | "warning",
    "data": { ... },  # The actual result, varies by tool
    "context_hint": "For band structure details, call get_band_structure(calc_id='...')",
    "token_cost": "low"  # Agent knows this was a cheap call
}

# Error return (structured diagnostics, not stack traces)
{
    "status": "error",
    "error_type": "SCF_NOT_CONVERGED",
    "severity": "recoverable",
    "diagnostics": {
        "iterations_completed": 87,
        "energy_oscillating": true,
        "last_energy_change_eV": 0.003
    },
    "suggested_fixes": [
        {"action": "reduce_mixing_beta", "from": 0.7, "to": 0.3, "confidence": "high", "reason": "Energy oscillation indicates charge sloshing"},
        {"action": "increase_max_iterations", "from": 100, "to": 200, "confidence": "medium"}
    ],
    "context_hint": "Use preview_compilation with the suggested fix to see updated parameters before resubmitting"
}
```

### 6. Context Engineering Strategy

How QMatSuite's MCP server cooperates with the agent's context management.

#### 6.1 Tiered Returns (Progressive Disclosure)

Define three tiers for every data-producing tool:
- **Summary** (default): 5-10 key values, fits in ~200 tokens
- **Detailed**: Full structured data for a specific property, ~500-2000 tokens
- **Raw**: Escape hatch to output file sections, unbounded but paginated

Show how this maps to the 100:1 input-to-output ratio principle.

#### 6.2 Context Hints

Every tool return includes a `context_hint` field that guides the agent's next step. This is NOT prompt engineering — it's structured metadata that helps the agent reason about what to do next without trial-and-error tool calls.

#### 6.3 KV-Cache Cooperation

Based on Manus's lessons:
- Tool definitions are STABLE (never dynamically modified)
- Tool returns use deterministic JSON key ordering
- Resource URIs follow consistent patterns for cache-friendly prefixes

#### 6.4 Filesystem as External Memory

QMatSuite's SSOT files naturally serve as externalized agent memory:
- `calculation.yaml` → the agent's "lab notebook" for current calculation
- `step.yaml` → detailed step-level state
- Project SQLite → long-term episodic memory across calculations
- Agent can write its own notes via `annotate_calculation`

Map this to Manus's "filesystem as context" principle.

### 7. Memory Architecture: Three Timescales

This is where cognitive science meets engineering.

#### 7.1 Working Memory (Within a Conversation)

- Agent's context window, managed by the client (Claude Code's compaction, etc.)
- QMatSuite cooperates by returning token-efficient data
- `context_hint` fields guide attention

#### 7.2 Session Memory (Within a Project)

- Project's SQLite database stores calculation history, provenance, parameters, results
- `get_project_history` tool lets agent query past calculations
- `get_provenance` tool lets agent trace lineage
- Agent can annotate calculations with insights ("this functional underestimates the gap")

#### 7.3 Long-Term Memory (Across Projects)

- This is the most novel part — QMatSuite can optionally maintain a **knowledge base** of accumulated computational insights
- Inspired by A-MEM's Zettelkasten: interconnected notes about what worked
- Inspired by ACE's evolving playbook: strategies that improve over time
- Implementation: a `.qmatsuite/knowledge.yaml` or SQLite table that accumulates entries like:
  ```yaml
  - id: k_001
    category: convergence_strategy
    engine: QE
    system_type: metallic
    insight: "For metallic systems, Methfessel-Paxton smearing with sigma=0.02 Ry converges faster than Gaussian"
    evidence: [calc_id_1, calc_id_2, calc_id_3]
    confidence: high
    created: 2026-02-15
    updated: 2026-02-17
  ```
- Agent can query this via `search_knowledge(query)` tool
- Agent can add to it via `record_insight(category, insight, evidence)`
- Over time, this becomes a **personalized computational expertise database**

Discuss the analogy to how researchers build intuition over years of practice. QMatSuite makes this explicit and queryable.

### 8. Error Recovery Architecture

Based on competitor analysis, design a three-level error recovery system:

#### Level 0: Prevention (Schema Validation)
- MCP tool input schemas prevent malformed requests
- `preview_compilation` catches parameter conflicts BEFORE execution
- Elicitation confirms expensive operations

#### Level 1: Structured Diagnostics (Rule-Based)
- QMatSuite's error parser returns structured diagnostics (not raw logs)
- Suggested fixes with confidence levels
- Agent can directly act on suggestions without LLM parsing

#### Level 2: Agent-Driven Recovery
- Agent uses its own LLM reasoning to diagnose complex failures
- Can use `get_output_raw` to inspect specific output sections
- Can use `sampling` to ask its LLM for interpretation
- Can use `search_parameters` to find relevant documentation
- Can use `search_knowledge` to check if similar errors were solved before

Show how this is more elegant than El Agente's 58-agent hierarchy or DREAMS' separate LLM calls — one smart agent with structured error data can do it all.

### 9. Workflow Examples

Walk through 3 complete workflows showing tool call sequences. These should be realistic and demonstrate the system's power.

#### 9.1 Quick Win: "Calculate Si Band Structure" (5 minutes)

User says one sentence → agent discovers capabilities → previews → submits → analyzes → visualizes.

Show the exact tool call sequence with example inputs/outputs.

#### 9.2 Research Project: "Find Optimal U Parameter for FeO" (hours)

Agent plans a systematic U-parameter scan → submits multiple calculations → compares results → identifies optimal U → records insight to knowledge base.

Show how progressive disclosure and token efficiency matter when handling 10+ calculations.

#### 9.3 Long-Term: "Systematic Study of Perovskite Stability" (days/weeks)

Agent maintains a research plan → fetches structures from Materials Project → runs screening calculations → identifies promising candidates → runs detailed calculations → compares with literature → generates report.

Show how memory architecture (session + long-term) enables multi-day research continuity.

### 10. MCP Apps: Interactive Visualization

Design the interactive visualizations that tools can return:

- **Band Structure Viewer**: Interactive plot with zoom, hover for k-point values, orbital character overlay
- **DOS Viewer**: Projected DOS with element/orbital decomposition toggles
- **Convergence Dashboard**: Real-time SCF convergence plot, force convergence for relaxation
- **Structure Viewer**: 3D crystal structure with rotation, cell boundaries, bond highlighting
- **Parameter Space Explorer**: When doing scans, interactive heatmap of results vs parameters

For each, specify what data the tool returns and what the HTML/JS app renders. These are sandboxed iframes communicating via postMessage.

### 11. Competitive Differentiation

A crisp comparison table:

| Feature | El Agente | ChemGraph | VASPilot | DREAMS | Masgent | **QMatSuite** |
|---|---|---|---|---|---|---|
| Agent architecture | 58 agents | LangGraph DAG | CrewAI 4-agent | LangGraph | pydantic-ai | **MCP (BYOE)** |
| Engine coverage | ORCA only | ASE-limited | VASP only | ASE-limited | VASP only | **15 engines native** |
| Parameter access | ~100% (1 engine) | ~25% (ASE) | ~30% (pymatgen) | ~25% (ASE) | ~30% (pymatgen) | **100% (all engines)** |
| Preview before execute | ❌ | ❌ | ❌ | ❌ | ❌ | **✅ preview_compilation** |
| Interactive viz in conversation | ❌ | ❌ | ❌ | ❌ | ❌ | **✅ MCP Apps** |
| LLM lock-in | GPT-4 | GPT-4 | GPT-4/Claude | GPT-4o | GPT-4o | **None (BYOE)** |
| API key management | User provides | User provides | User provides | User provides | User provides | **User's own CLI** |
| Tool discovery scaling | Manual 34 tools | Manual | Manual | Manual | Manual | **Tool Search + defer_loading** |
| Solid-state workflows | ❌ | Limited | ✅ (VASP) | Limited | ✅ (VASP) | **✅ (all 15 engines)** |
| Long-term memory | MongoDB episodic | ❌ | SQLite | ❌ | ❌ | **Project provenance + knowledge base** |

### 12. Security and Trust

- **No API keys pass through QMatSuite** — BYOE means agent connects directly to its LLM
- **Elicitation for dangerous operations** — never delete data or submit expensive jobs without confirmation
- **Audit trail** — every tool call logged with timestamp, parameters, and result summary
- **Sandboxed MCP Apps** — visualization runs in iframe sandbox, no access to host
- **Input validation** — all tool inputs validated against JSON Schema before execution
- **Rate limiting** — configurable limits on tool calls per minute/hour

### 13. Deployment Architecture

Two deployment modes:

#### 13.1 Local (Default)
- MCP server runs locally via stdio transport
- Agent connects directly (Claude Code's `.mcp.json`)
- Calculations run on local machine
- Zero network latency, maximum privacy

```json
// .mcp.json
{
  "mcpServers": {
    "qmatsuite": {
      "command": "qmatsuite",
      "args": ["mcp", "serve"],
      "env": { "QMATSUITE_PROJECT": "/path/to/project" }
    }
  }
}
```

#### 13.2 Remote (Future)
- MCP server deployed via Streamable HTTP
- Agent connects over network (remote HPC, cloud)
- OAuth 2.0 authentication
- Supports load balancing, multiple concurrent users
- Session management via `Mcp-Session-Id`

### 14. Testing Strategy

- **Contract tests**: Every MCP tool has a contract test verifying input schema validation, output schema conformance, and error handling
- **Integration tests**: Tool calls that exercise actual QMatSuite core (with mock engines)
- **Real-run smoke tests**: End-to-end with actual QE calculations (Si SCF, Si bands, Al DOS — already partially implemented)
- **Agent simulation tests**: Scripted tool call sequences mimicking realistic agent behavior
- **Context budget tests**: Measure total tokens consumed by typical workflows

### 15. Implementation Roadmap

#### Phase 0: Foundation (Week 1-2)
- Set up FastMCP server skeleton
- Wire up stdio transport
- Implement `list_engines`, `list_workflows`, `get_presets` from existing core
- First end-to-end test: agent can discover QMatSuite capabilities

#### Phase 1: Core Loop (Week 3-5)
- Implement `preview_compilation` (the killer feature)
- Implement `submit_calculation`, `get_status`, `get_results_summary`
- Implement `search_parameters` with BM25 over tag JSONs
- Add output schemas to all tools
- First demo: "Calculate Si band structure" workflow works end-to-end

#### Phase 2: Rich Analysis (Week 6-8)
- Implement detailed analysis tools (`get_band_structure`, `get_dos`, etc.)
- Implement MCP Apps for interactive visualization
- Implement `compare_calculations`
- Add elicitation for pre-submission confirmation
- Demo: Full research workflow with visualization

#### Phase 3: Intelligence (Week 9-12)
- Implement `get_project_history`, `get_provenance`
- Implement knowledge base (`search_knowledge`, `record_insight`)
- Implement structured error diagnostics with suggested fixes
- Implement structure tools (fetch, create, modify)
- Add defer_loading and Tool Search compatibility
- Demo: Multi-calculation research project with memory

#### Phase 4: Polish (Week 13-16)
- Streamable HTTP transport for remote deployment
- Security hardening (auth, rate limiting, audit)
- Performance optimization (token budgets, caching)
- Documentation and tutorials
- Paper writing

---

## Writing Style

- Technical and precise. Use actual class names, function names, file paths from the codebase.
- Every design decision must have a "why" — grounded in either the design reference, competitive analysis, or engineering principles.
- Include code snippets (Python) showing MCP tool definitions where they illustrate the design.
- Use tables for comparisons.
- ASCII diagrams for architecture.
- No marketing fluff. This is an engineering document.

## Output

Save as `docs/design/AGENT_INTEGRATION_DESIGN.md` in the repo.

## Important Notes

- Read `AGENT_DESIGN_REFERENCE.md` FIRST — it contains the latest research on MCP spec features, context engineering, competitor analysis, cognitive science, and agent architecture patterns that MUST inform this design.
- Explore the ACTUAL codebase before writing — map every tool to real code.
- The `preview_compilation` tool is our single most important differentiator. Give it extensive treatment.
- The "Intelligent Researcher Model" framing in Section 2 is what makes this publishable. Invest heavily in this section.
- MCP Apps (interactive visualization) are brand new (Jan 2026) — we can be the first scientific computing platform to use them.
- The knowledge base (Section 7.3) is speculative but high-impact. Design it concretely enough to implement but acknowledge it's Phase 3.
- Do NOT propose LangGraph, LangChain, CrewAI, or any orchestration framework. The agent IS the orchestrator.
