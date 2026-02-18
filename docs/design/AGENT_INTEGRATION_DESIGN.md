# QMatSuite Agent Integration Design

**Status**: Design Document (Pre-Implementation)
**Date**: 2026-02-17
**Scope**: MCP server architecture for AI agent integration across 15 computational engines

---

## 1. Executive Summary

QMatSuite is becoming the first AI-native computational materials science platform. Rather than building yet another AI orchestration framework, we expose QMatSuite's 15-engine simulation infrastructure as a Model Context Protocol (MCP) server. Any AI agent — Claude Code, GPT Codex CLI, Gemini CLI, or future systems — connects to QMatSuite through the standard MCP protocol and gains immediate access to the full power of density functional theory, quantum chemistry, and classical molecular dynamics.

**The BYOE paradigm shift.** Every competitor (El Agente, ChemGraph, VASPilot, DREAMS, Masgent) bundles a specific LLM framework (LangGraph, CrewAI, pydantic-ai) and locks users into a particular agent architecture. QMatSuite inverts this: we build exceptional tools, and users Bring Your Own Engine. The agent is already intelligent; QMatSuite gives it hands, eyes, and a lab notebook.

**The "no preset" reality.** Only QE has partial preset coverage today. The other 14 engines have zero presets. The MCP server treats direct engine-specific parameter setting as a first-class workflow, not an override escape hatch. Presets are a convenience shortcut for the engines that have them, not the foundational assumption.

**Three-sentence value proposition:**

*For researchers:* Run any calculation on any of 15 engines through natural language — configure parameters directly or through presets, preview every input file before execution, get structured diagnostics when things fail, and build a searchable knowledge base of what works.

*For the paper:* We present a cognitive architecture for computational materials research grounded in the scientific method and memory theory, where the MCP protocol serves as the interface between artificial reasoning and deterministic simulation infrastructure.

*For adoption:* Zero lock-in, zero API key management, zero framework dependency — install QMatSuite, point your existing AI coding assistant at the MCP server, and start computing.

---

## 2. Philosophical Foundation: The Intelligent Researcher Model

### 2.1 Beyond Workflow Executors

The dominant paradigm in AI-for-science treats agents as workflow executors. El Agente decomposes tasks into a 58-agent hierarchy. ChemGraph builds LangGraph DAGs with conditional edges. DREAMS implements a supervisor-worker pattern. All encode the research process as a fixed graph that the agent traverses.

This is backwards. A competent researcher does not follow a flowchart. They hold a mental model of their system, form hypotheses, design experiments to test them, interpret results through domain knowledge, and revise their approach. The graph emerges from reasoning, not the other way around.

QMatSuite's agent integration is built on a different model: **the agent is an intelligent researcher who happens to have a well-equipped laboratory.** The laboratory (QMatSuite) provides instruments (tools), reference materials (resources), and a lab notebook (SSOT files + provenance). The researcher (the LLM) provides judgment, planning, and interpretation. Neither component tries to do the other's job.

### 2.2 The Cognitive Architecture Mapping

The CoALA framework (Sumers et al., 2023) maps human cognition to agent architecture along three axes: memory, action space, and decision-making. QMatSuite's existing infrastructure maps naturally onto this framework — not as an afterthought, but because well-designed simulation infrastructure already mirrors how researchers think.

**Memory mapping:**

| Cognitive Function | Human Researcher | QMatSuite Component | Implementation |
|---|---|---|---|
| Working memory | Current focus, active reasoning | Agent context window | Token-efficient tool returns, `context_hint` fields |
| Episodic memory | "Last time I ran Fe with PBE+U, U=4 eV worked best" | `.provenance/` CAS store, run history | `get_project_history`, `get_provenance` tools |
| Semantic memory | "Metals need Methfessel-Paxton smearing" | Engine tag JSONs (232 VASP tags, 170+ ABINIT tags, ...) | `search_parameters` tool with BM25 search |
| Procedural memory | "For band structures: SCF then NSCF then bands" | `StepTypeRegistry`, recipe classes, `WorkflowTemplate` | `list_workflows`, `preview_compilation` tools |

This mapping is not metaphorical — it is structural. The `search_parameters` tool performs the same function as a researcher scanning a manual. The `get_project_history` tool performs the same function as flipping through a lab notebook. The difference is that the AI agent can search 1,000 parameters in milliseconds and recall every past calculation perfectly.

**Action space mapping:**

The CoALA framework divides actions into external (tool use, API calls, dialogue) and internal (reasoning, retrieval, learning). QMatSuite's MCP server provides the external grounding actions. The agent's LLM provides the internal reasoning. The boundary is the MCP protocol.

External actions decompose into five categories that map to MCP tool groups:

| Action | Scientific Equivalent | MCP Tool Category |
|---|---|---|
| Observe | Survey the lab, check what's available | Discovery tools (`list_engines`, `list_workflows`, `get_presets`) |
| Configure | Set up the experiment | Configuration tools (`create_calculation`, `set_parameters`, `apply_preset`) |
| Verify | Check the setup before running | Inspection tools (`inspect_calculation`, `preview_compilation`) |
| Execute | Run the experiment | Execution tools (`run_calculation`, `get_status`) |
| Analyze | Read the results | Analysis tools (`get_results_summary`, `get_band_structure`) |

### 2.3 The Scientific Method as Agent Workflow

The scientific method is not a rigid sequence but a recursive loop: hypothesize, experiment, observe, reflect. This maps directly to agent workflow design:

**Hypothesis formation** maps to plan formulation. The agent, informed by the user's research question and its accumulated knowledge, decides what calculation to run. "This is a metallic system, so I should use Methfessel-Paxton smearing. Let me search for the right parameter and set it directly."

**Experimental setup** maps to configuration. The agent creates a calculation, applies presets if available, sets engine-specific parameters for anything not covered by presets, and inspects the resulting input files before committing compute time. The `inspect_calculation(dry_run=true)` flow is unique to QMatSuite — no competitor offers pre-execution input file verification.

**Experimental execution** maps to tool invocation. The agent calls `run_calculation` and monitors via `get_status`. The calculation runs on the user's infrastructure (local machine, HPC cluster) — QMatSuite manages the execution, not the agent.

**Observation** maps to result analysis. The agent calls `get_results_summary` for a token-efficient overview, then drills into specifics with `get_band_structure` or `get_dos`. Structured returns mean the agent can reason numerically: "The bandgap is 0.67 eV, which is below the experimental value of 1.12 eV. This is the well-known DFT underestimation."

**Reflection** maps to knowledge accumulation. The agent records intent before running (`record_intent`), interpretation after analyzing (`record_interpretation`), and synthesized insights when patterns emerge (`record_insight`). This persists across sessions, building a personal computational expertise database.

### 2.4 Context Engineering as Cognitive Resource Management

Anthropic's context engineering framework treats the context window as an attention budget. Every token competes for the transformer's n-squared pairwise computation. Manus's 100:1 input-to-output ratio — 50 tool calls per task with ruthless output filtering — demonstrates that token efficiency is not optimization but architecture.

QMatSuite cooperates with context management through three mechanisms:

**Progressive disclosure.** Every tool returns a minimal summary by default. The agent requests more detail only when needed. A `get_results_summary` call returns ~200 tokens (energy, bandgap, forces, convergence status, wall time). A `get_band_structure` call returns ~1,000 tokens (k-resolved eigenvalues). The agent never pays for data it doesn't use.

**Context hints.** Every tool return includes a `context_hint` field that guides the agent's next step without trial-and-error. After `run_calculation`, the hint says "Call get_status(job_id='...') to check progress." After a failed SCF, the hint says "Use inspect_calculation with the suggested fix to see updated parameters before resubmitting." This is not prompt engineering — it is structured metadata that reduces wasted tool calls.

**Filesystem as externalized memory.** Following Manus's principle, QMatSuite's SSOT files (`calculation.yaml`, `step.yaml`) serve as externalized agent memory. The agent can always re-read the current state from disk rather than maintaining it in context. The `get_project_history` tool queries the provenance database rather than relying on conversation history. This means context compaction (Claude Code's conversation summarization) loses no critical state.

### 2.5 Why This Framing Matters

The "intelligent researcher" model is not marketing. It has three concrete engineering consequences:

First, it determines tool granularity. Tools match the actions a researcher would take, not the internal API structure of QMatSuite. A researcher does not "call `QVService.Calculation.update_step_params` with a nested dict of SYSTEM parameters." A researcher "sets the cutoff energy to 520 eV for this VASP calculation."

Second, it determines error handling strategy. A researcher encountering a failed SCF does not need a stack trace. They need a diagnosis: "Energy oscillating, likely charge sloshing. Try reducing mixing_beta from 0.7 to 0.3." QMatSuite's error returns are structured diagnostics with actionable suggestions, not exception dumps.

Third, it determines the memory architecture. A researcher's expertise grows over time. QMatSuite's four-layer memory (Section 7) makes this growth explicit and queryable. After 100 calculations, the agent doesn't start from scratch — it starts with accumulated wisdom about which functionals work for which systems, which convergence strategies resolve which failures, and which approximations are appropriate for which properties.

---

## 3. Architecture Overview

### 3.1 System Architecture

```
+------------------------------------------------------+
|  User's AI Agent (Claude Code / Codex CLI / Gemini)  |
|  +-------------+  +----------+  +----------------+  |
|  | LLM Engine  |  | Context  |  | Sub-agents     |  |
|  | (their API) |  | Manager  |  | (optional)     |  |
|  +------+------+  +----+-----+  +-------+--------+  |
|         +---------------+----------------+           |
|                         | MCP Protocol               |
+-------------------------+----------------------------+
                          | stdio / Streamable HTTP
+-------------------------+----------------------------+
|  QMatSuite MCP Server                                |
|  +--------------------------------------------------+|
|  |          Tool Router + Registry                  ||
|  |  (defer_loading for on-demand tools)             ||
|  +--------+----------+-----------+------------------+|
|  |Discovery|Configure |Execution |Analysis          ||
|  |Tools    |Tools     |Tools     |Tools             ||
|  +--------+----------+-----------+------------------+|
|  |          QVService (API facade / ABI)             ||
|  |  .calculation  .structure  .analysis  .run        ||
|  |  .project      .history    .pseudo    .online     ||
|  +--------------------------------------------------+|
|  |          Preset Compiler / Detector               ||
|  |  ParamSpace, PrecisionAdvisor, Variants           ||
|  +--------------------------------------------------+|
|  |          QMatSuite Core                           ||
|  |  Intent: StepTypeRegistry, WorkflowTemplate       ||
|  |  IR:     parameters.py, dialects/                  ||
|  |  Engine: DriverRegistry, 15 driver bundles        ||
|  +--------------------------------------------------+|
|  |  inputformat (leaf package, no kernel deps)       ||
|  |  write_engine_inputs / parse_engine_inputs        ||
|  +--------------------------------------------------+|
|  |  SSOT: calculation.yaml + step.yaml               ||
|  |  Provenance: .provenance/ (SQLite + CAS)          ||
|  |  Engine Data: *_tags.json (VASP 232, ABINIT 170+) ||
|  +--------------------------------------------------+|
+------------------------------------------------------+
```

### 3.2 MCP as Equal Frontend

**QMatSuite's API facade (`QVService`) is the ABI. ALL frontends are equal consumers:**

```
GUI (Electron)  ─┐
CLI              ─┤
MCP Server       ─┼── QVService (API facade / ABI) ── Core Kernel
Daemon           ─┤
Jupyter (future) ─┘
```

**Rules:**

- MCP server MUST NOT call any core kernel code directly. Everything goes through `QVService`.
- If MCP needs a capability that `QVService` doesn't expose, the correct action is to ADD a method to `QVService`, not to hack around it in MCP.
- DTO structures and error types should be designed to serve ALL frontends. If MCP needs richer error diagnostics (e.g., `suggested_fixes`), this should be added to the core `ErrorDTO`, benefiting GUI and CLI too.
- During MCP development, if the existing API/DTO/error hierarchy is insufficient, **propose core refactors rather than MCP-layer workarounds**. MCP development is expected to drive improvements to the core API.

This principle ensures that every capability exposed to the AI agent is also available to the GUI and CLI. No frontend gets special treatment. The MCP server is architecturally identical to the Electron GUI: a thin adapter translating protocol-specific messages into `QVService` calls.

### 3.3 Layer Mapping to Code

**MCP Server Layer** (new code):
- `src/quantumvitas/mcp/server.py` — FastMCP server definition, tool registration
- `src/quantumvitas/mcp/tools/` — Tool implementations organized by category
- `src/quantumvitas/mcp/returns.py` — Standard return envelope, context hints
- `src/quantumvitas/mcp/apps/` — MCP App HTML/JS for interactive visualization

**API Bridge** (existing, consumed by MCP tools):
- `src/quantumvitas/api/service.py` — `QVService` with 8 nested facades, ~100 methods
- `src/quantumvitas/api/types/` — `CalculationDTO`, `StepDTO`, `StructureDTO`, `ErrorDTO`, etc.
- `src/quantumvitas/api/errors.py` — `APIError` hierarchy (8 error classes with structured codes)

**Kernel** (existing, untouched):
- `src/quantumvitas/core/driver_registry.py` — `DriverRegistry` singleton for engine dispatch
- `src/quantumvitas/core/driver_protocol.py` — `EngineDriver` protocol (7-method MUST interface)
- `src/quantumvitas/core/analysis/` — `BandStructure`, `DOS`, `Trajectory`, `Field3D` objects
- `src/quantumvitas/presets/` — `ParamSpace` framework, compiler, detector, spaces registry
- `src/quantumvitas/workflow/` — `StepTypeRegistry`, `WorkflowTemplate`, step type conversion
- `src/quantumvitas/inputformat/` — `write_engine_inputs`, `parse_engine_inputs` orchestrators

**Data Layer** (existing, untouched):
- `calculations/<slug>/calculation.yaml` — Calculation SSOT (engine, structure, steps, species map)
- `calculations/<slug>/raw/<step>.yaml` — Step SSOT (parameters, cards, kpath metadata)
- `.provenance/` — SQLite run history + CAS content-addressable store
- `src/quantumvitas/drivers/<engine>/data/*_tags.json` — Engine parameter metadata

The MCP server is a thin adapter layer. It translates MCP tool calls into `QVService` method calls. No kernel code is modified. No new abstractions are introduced between MCP and the existing API. This follows Argonne's "thin adapter" pattern from their science-mcps work: wrap existing mature services rather than building new ones.

### 3.4 Multi-Engine Workflows: Artifact Resolution

QMatSuite supports cross-engine workflows through artifact resolution — output files from engine A are automatically discovered and staged as inputs for engine B. This is a production feature, not a design concept.

**Verified multi-engine chains:**

| Workflow | Steps | Artifact Flow |
|---|---|---|
| QE → Wannier90 | `scf → nscf → pw2wannier → wannier` | QE produces `.amn`, `.mmn`, `.eig`; W90 resolver finds and stages them |
| QE → QMCPACK | `pw.x → pw2qmcpack → qmcpack` | QE produces wavefunctions; converter produces HDF5; QMCPACK reads via `href` |
| QE → Yambo | `scf → yambo_setup → yambo_gw/bse` | Yambo resolver finds QE's `prefix.save/` directory; `p2y` converts to Yambo DB |

**Mechanism** (code-verified):
- `drivers/*/artifact_resolver.py` — Engine-specific resolvers search completed steps for required files
- `calculation/step_artifacts.py` — Artifact rules registry: `wannierprep` produces `.nnkp`, `pw2wannier` produces `.amn/.mmn/.eig`
- `execution/relax_artifacts.py` — Structure inheritance: relaxed geometry from step N becomes structure for step N+1
- `execution/executor.py` — JobGraph executor respects cross-engine dependencies (sequential with `deps` list)

**Integration test**: `tests/integration/test_qmcpack_diamond_workflow.py` (387 lines) exercises the full QE SCF → pw2qmcpack → QMCPACK VMC chain with real executables and validates energy output.

---

## 4. MCP Primitives Mapping

| MCP Primitive | QMatSuite Usage | Why This Primitive | Concrete Example |
|---|---|---|---|
| **Tools** | Actions that modify state or produce computed results | Tools are LLM-controlled — the agent decides when to call them. Calculations, analysis, and knowledge recording are agent-driven decisions. | `run_calculation({calc_ulid: "01KC..."})` |
| **Resources** | Lightweight summary-level reference data | Resources are application-controlled — the client decides what the agent sees. Summary engine and preset info, not heavyweight parameter lookups. | `qmatsuite://engines` returns brief engine list with capabilities |
| **Elicitation** | Human-in-the-loop confirmation for irreversible operations | Elicitation interrupts the agent to ask the user. Submitting expensive HPC jobs or deleting data requires human confirmation — the agent should not auto-approve. | Pre-submission review: "About to submit 128-atom VASP relaxation on 64 cores. Estimated wall time: 4 hours. Proceed?" |
| **Sampling** | Server-side LLM reasoning for complex interpretation | Sampling lets the server ask the client's LLM for help. Diagnosing complex convergence failures or interpreting ambiguous output sections benefits from LLM reasoning without polluting the main agent context. | Error diagnosis: server sends last 50 SCF iterations to client LLM with "Why did this oscillate?" prompt |
| **Tool Output Schema** | Machine-readable structured results | Output schemas let downstream tools programmatically consume results. Energy values, convergence status, and bandgap measurements must be machine-parseable, not buried in text. | `get_results_summary` output schema: `{total_energy_eV: number, bandgap_eV: number | null, converged: boolean, ...}` |
| **MCP Apps** | Interactive visualization in the conversation | MCP Apps render sandboxed HTML/JS in the client UI. Band structure plots with zoom/hover, 3D structure viewers with rotation, and convergence dashboards belong in interactive widgets, not ASCII art. | `get_band_structure` returns data + `_meta.ui.resourceUri` pointing to interactive Plotly band plot |
| **Tasks** | Long-running async operations | Tasks represent operations spanning minutes to hours. HPC calculations run asynchronously; the agent polls for completion rather than blocking. | `run_calculation` returns a Task ID. Agent polls via `get_status(task_id)`. |
| **Notifications** | Server-initiated status updates (future) | Notifications eliminate polling for long-running jobs. For v1, polling via `get_status` is sufficient. Future versions can push completion events. | Server pushes "Job 01KC3F... completed" when DFT calculation finishes. |

### Resources: Lightweight by Design

Resources provide summary-level reference data that the client can pre-load. The heavyweight parameter lookup is handled by the `search_parameters` tool, not by Resources. Most agent interaction flows through Tools.

- `qmatsuite://engines` — Brief list of 15 engines with capabilities and installation status
- `qmatsuite://presets/{engine}/{workflow}` — Preset dimension summary (not full compiled parameters)

Don't over-invest in Resource design. Resources are for ambient context; Tools are for agent-driven action.

### Resources vs. Tools: The Decision Heuristic

The rule: if the agent must reason about *whether* to invoke it, it is a tool. If the application should just make it available as context, it is a resource. For QMatSuite, almost everything is a tool — the agent actively decides to discover, configure, run, and analyze.

---

## 5. Tool Design: The Complete Tool Catalog

### 5.1 Design Principles

Six principles govern every tool in the catalog. Each is grounded in a concrete engineering lesson.

**1. Progressive Disclosure.** Discover, Configure, Verify, Execute, Analyze. The agent never needs all tools at once. Core tools are always loaded; detailed analysis tools are deferred. This mirrors how a researcher first surveys their equipment, then sets up an experiment, then runs it, then analyzes results. Engineering basis: Tool Search with `defer_loading` reduces initial context by ~85% (Anthropic benchmark).

**2. Token Efficiency.** Every return is minimal by default. Summary tier: ~200 tokens. Detailed tier: ~500-2,000 tokens. Raw tier: paginated, unbounded. The agent requests more detail with explicit parameters. Engineering basis: Manus operates at 100:1 input-to-output ratio. Context rot research (Chroma 2025) shows models perform ~30% worse with full history vs. focused history.

**3. Structured + Human-Readable Dual Returns.** Every tool returns both `structuredContent` (for the agent to reason about programmatically) and `content` (for the user to read in the conversation). The structured content conforms to a declared `outputSchema`. Engineering basis: MCP spec 2025-06-18 introduced output schemas for exactly this purpose.

**4. Self-Describing.** Tool input schemas include defaults, constraints, enums, and `description` fields. Tools with complex inputs include `input_examples`. The agent can discover correct usage from the schema alone, without external documentation. Engineering basis: Input examples improve parameter accuracy by 18%+ (Anthropic benchmark).

**5. Idempotent Discovery.** Discovery, configuration-read, and preview tools have zero side effects. Calling `preview_compilation` 10 times produces identical results and modifies nothing. The agent can explore freely without risk. Engineering basis: Idempotent reads enable aggressive caching and fearless exploration.

**6. Error as Data.** Failures return structured diagnostics with error type, severity, affected parameters, and suggested fixes with confidence levels. Never raw stack traces. The agent can act on suggestions without LLM parsing of error text. Engineering basis: El Agente's primary innovation is structured error recovery. QMatSuite achieves this at the protocol level rather than requiring 58 agents.

### 5.2 The Four Usage Scenarios

The tool catalog is designed to support four equally important scenarios:

**Scenario A — Preset available, good enough.** Agent applies preset, optionally overrides a few params, runs. The "quick win" path. ~80% of QE calculations with common workflows.

**Scenario B — No preset exists.** Agent queries parameter documentation (`search_parameters`), sets engine-specific parameters directly (`set_parameters`), runs. **This is how ALL 14 non-QE engines work today**, and how uncommon QE parameters work.

**Scenario C — Preset as starting point, heavy modification.** Agent applies preset for a baseline, then overrides many parameters for specific research needs. Common for advanced users.

**Scenario D — Exploratory then refine.** Agent uses preset for a quick screening run, analyzes results, creates a new calculation with carefully tuned parameters based on what was learned. The scientific method in action.

### 5.3 Always-Loaded Tools (~13 tools, defer_loading: false)

These ~13 tools are always present in the agent's context (~3,500-4,000 tokens of tool definitions). They form the complete core cycle: discover → configure → verify → execute → analyze. This count is justified because the fine-grained configuration tools (`create_calculation`, `set_parameters`, `apply_preset`) are essential for the no-preset workflow that covers 14 of 15 engines today. The deferred tools (analysis, structure, batch, knowledge) add zero tokens until needed.

---

#### `list_engines`

**Description**: List available computational engines with installation status and capabilities.

**Maps to**: `DriverRegistry.list_registered()` + engine capability detection

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "installed_only": {
      "type": "boolean",
      "default": false,
      "description": "If true, only return engines with detected installations"
    }
  }
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "engines": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "display_name": { "type": "string" },
          "installed": { "type": "boolean" },
          "syntax_family": { "type": "string" },
          "capabilities": {
            "type": "array",
            "items": { "type": "string" }
          },
          "parameter_count": { "type": "integer" }
        }
      }
    },
    "total": { "type": "integer" }
  }
}
```

**Example Output**:
```json
{
  "engines": [
    {
      "name": "vasp",
      "display_name": "VASP",
      "installed": true,
      "syntax_family": "F1_namelist_card",
      "capabilities": ["scf", "relax", "bands", "dos", "md", "hybrid", "soc"],
      "parameter_count": 232
    },
    {
      "name": "qe",
      "display_name": "Quantum ESPRESSO",
      "installed": true,
      "syntax_family": "F1_namelist_card",
      "capabilities": ["scf", "relax", "bands", "dos", "phonons", "neb"],
      "parameter_count": 180
    }
  ],
  "total": 15,
  "context_hint": "Use list_workflows(engine='vasp') to see available workflows for a specific engine."
}
```

---

#### `list_workflows`

**Description**: List available workflows (calculation types) for a given engine, with brief descriptions.

**Maps to**: `QVService.Calculation.list_workflow_templates(engine)` via `StepTypeRegistry.get_step_type_specs(engine)` and `WorkflowTemplate` definitions

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "engine": {
      "type": "string",
      "description": "Engine name (e.g., 'vasp', 'qe', 'orca')"
    }
  },
  "required": ["engine"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "engine": { "type": "string" },
    "workflows": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "description": { "type": "string" },
          "steps": {
            "type": "array",
            "items": { "type": "string" }
          },
          "requires_structure": { "type": "boolean" }
        }
      }
    }
  }
}
```

**Example Output**:
```json
{
  "engine": "vasp",
  "workflows": [
    {"name": "scf", "description": "Self-consistent field calculation", "steps": ["vasp_scf"], "requires_structure": true},
    {"name": "relax", "description": "Ionic relaxation (ISIF=2)", "steps": ["vasp_relax"], "requires_structure": true},
    {"name": "vc_relax", "description": "Variable-cell relaxation (ISIF=3)", "steps": ["vasp_vc_relax"], "requires_structure": true},
    {"name": "bands", "description": "Band structure (SCF + NSCF on k-path)", "steps": ["vasp_scf", "vasp_bandspw"], "requires_structure": true},
    {"name": "dos", "description": "Density of states (SCF + NSCF uniform)", "steps": ["vasp_scf", "vasp_dos"], "requires_structure": true}
  ],
  "context_hint": "Use get_presets(engine='vasp', workflow='bands') to check for available quality presets. If no presets exist, use search_parameters to find relevant parameters."
}
```

---

#### `get_presets`

**Description**: List available presets (quality levels) for an engine+workflow combination. **Critically indicates when NO presets are available**, guiding the agent to the direct parameter-setting workflow.

**Maps to**: `QVService.Calculation.get_preset_catalog(engine, workflow)` via `presets/spaces_registry.py` dimension enumeration

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "engine": { "type": "string" },
    "workflow": { "type": "string" }
  },
  "required": ["engine", "workflow"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "engine": { "type": "string" },
    "workflow": { "type": "string" },
    "presets_available": { "type": "boolean" },
    "dimensions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "description": { "type": "string" },
          "options": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "value": { "type": "string" },
                "label": { "type": "string" },
                "description": { "type": "string" }
              }
            }
          },
          "default": { "type": "string" }
        }
      }
    },
    "message": { "type": "string" }
  }
}
```

**Example Output — Presets available (QE):**
```json
{
  "engine": "qe",
  "workflow": "bands",
  "presets_available": true,
  "dimensions": [
    {
      "name": "precision",
      "description": "Controls cutoff energy, k-grid density, convergence threshold",
      "options": [
        {"value": "low", "label": "Low (fast)", "description": "ecutwfc from PP minimum, coarse k-grid, conv_thr=1e-6"},
        {"value": "med", "label": "Medium (standard)", "description": "1.2x PP minimum cutoff, standard k-grid, conv_thr=1e-8"},
        {"value": "high", "label": "High (precise)", "description": "1.5x PP minimum cutoff, dense k-grid, conv_thr=1e-10"}
      ],
      "default": "med"
    },
    {
      "name": "magnetism",
      "description": "Spin treatment",
      "options": [
        {"value": "nonmagnetic", "label": "Non-magnetic", "description": "nspin=1"},
        {"value": "collinear_lsda", "label": "Collinear (LSDA)", "description": "nspin=2"},
        {"value": "noncollinear_soc", "label": "Non-collinear + SOC", "description": "noncolin=.true., lspinorb=.true."}
      ],
      "default": "nonmagnetic"
    }
  ],
  "context_hint": "Use preview_compilation to see full parameters before committing, or quick_run for the fast path."
}
```

**Example Output — No presets (VASP):**
```json
{
  "engine": "vasp",
  "workflow": "scf",
  "presets_available": false,
  "dimensions": [],
  "message": "No presets defined for VASP/scf. Use search_parameters to find relevant parameters and set_parameters to configure directly.",
  "context_hint": "Use search_parameters(query='cutoff energy VASP') to find relevant parameters, then create_calculation + set_parameters to configure."
}
```

---

#### `search_parameters`

**Description**: Search engine parameter documentation using BM25-ranked keyword search. **This is the primary knowledge source for agents working without presets.** Searches across all engine tag JSON files (VASP: 232 tags, ABINIT: 170+ tags, CP2K: 215 tags, LAMMPS: 114 commands, ORCA: 120+ keywords, Gaussian: 130 keywords, QMCPACK: 65 tags).

**Maps to**: BM25 index over `drivers/<engine>/data/*_tags.json` files, accessed via `*_metadata.py` modules (e.g., `vasp_metadata.get_tag_info()`, `abinit_metadata.list_tags()`)

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Natural language or keyword search (e.g., 'smearing for metals', 'EDIFF convergence')"
    },
    "engine": {
      "type": "string",
      "description": "Optional: limit search to specific engine"
    },
    "category": {
      "type": "string",
      "description": "Optional: limit to parameter category (e.g., 'scf', 'structure', 'kpoints')"
    },
    "max_results": {
      "type": "integer",
      "default": 5,
      "description": "Maximum results to return"
    }
  },
  "required": ["query"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "engine": { "type": "string" },
          "tag": { "type": "string" },
          "type": { "type": "string" },
          "default": {},
          "category": { "type": "string" },
          "description": { "type": "string" },
          "relevance_score": { "type": "number" }
        }
      }
    },
    "total_matches": { "type": "integer" }
  }
}
```

**Example — No-preset workflow usage:**
```
Agent: search_parameters(query="convergence threshold VASP", engine="vasp")
→ [{tag: "EDIFF", type: "float", default: 1e-4, category: "scf",
    description: "Global energy convergence criterion (eV). Typical values: 1e-4 (screening), 1e-6 (production), 1e-8 (high precision)."}]

Agent: Now I know to set EDIFF. I'll use set_parameters(calc_ulid, step=0, params={INCAR: {EDIFF: 1e-6}})
```

---

#### `create_calculation`

**Description**: Create a calculation directory with engine, workflow template, and structure. Persists immediately to `calculation.yaml`. Returns `calc_ulid` for subsequent configuration and execution.

**Maps to**: `QVService.Calculation.create()` (line ~3756 of service.py)

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "engine": {
      "type": "string",
      "description": "Engine name (e.g., 'vasp', 'qe', 'orca')"
    },
    "workflow": {
      "type": "string",
      "description": "Workflow name (e.g., 'scf', 'bands', 'relax')"
    },
    "structure_ulid": {
      "type": "string",
      "description": "ULID of the crystal/molecular structure to use"
    },
    "name": {
      "type": "string",
      "description": "Human-readable name for this calculation (e.g., 'Si_scf_highprec')"
    }
  },
  "required": ["engine", "workflow", "structure_ulid"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": { "type": "string" },
    "name": { "type": "string" },
    "engine": { "type": "string" },
    "workflow": { "type": "string" },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "step_index": { "type": "integer" },
          "step_type": { "type": "string" },
          "step_ulid": { "type": "string" }
        }
      }
    }
  }
}
```

**Example Output**:
```json
{
  "calc_ulid": "01KC38MBGSS8MX3Z4ETZMXZZY4",
  "name": "Si_scf",
  "engine": "vasp",
  "workflow": "scf",
  "steps": [
    {"step_index": 0, "step_type": "vasp_scf", "step_ulid": "01KC38MBGSS8MX3Z4ETZMXZZZ1"}
  ],
  "context_hint": "Calculation created. Use set_parameters(calc_ulid='01KC38MB...', step=0, params={INCAR: {...}}) to configure, or apply_preset if presets are available."
}
```

---

#### `set_parameters`

**Description**: Set engine-specific parameters on a calculation's step. Persists immediately to the step's YAML. **This is the primary configuration tool for the no-preset workflow** — how all 14 non-QE engines are configured today. Accepts the engine's native parameter namespace.

**Maps to**: `QVService.Calculation.update_step_params()` (line ~3954 of service.py)

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": {
      "type": "string",
      "description": "Calculation ULID from create_calculation"
    },
    "step": {
      "type": "integer",
      "default": 0,
      "description": "Step index (0-based) within the workflow"
    },
    "params": {
      "type": "object",
      "description": "Engine-specific parameters in native namespace. Examples: VASP: {INCAR: {ENCUT: 520, EDIFF: 1e-6}}, QE: {SYSTEM: {ecutwfc: 40}}, ORCA: {keywords: ['B3LYP', 'def2-TZVP']}"
    }
  },
  "required": ["calc_ulid", "params"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": { "type": "string" },
    "step": { "type": "integer" },
    "params_set": {
      "type": "object",
      "description": "The parameters that were successfully set"
    },
    "validation_warnings": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Non-fatal validation warnings (e.g., unusual value range)"
    }
  }
}
```

**Example — VASP SCF configuration:**
```json
{
  "calc_ulid": "01KC38MB...",
  "step": 0,
  "params": {
    "INCAR": {
      "ENCUT": 520,
      "EDIFF": 1e-6,
      "ISMEAR": 1,
      "SIGMA": 0.1,
      "LREAL": false
    },
    "KPOINTS": {
      "grid": [8, 8, 8]
    }
  }
}
```

---

#### `apply_preset`

**Description**: Compile and apply preset dimensions to a calculation. Persists compiled parameters to YAML. **Only available when presets exist for the engine+workflow combination.** Returns the compiled parameters so the agent can see what was set.

**Maps to**: `QVService.Calculation.apply_presets()` (line ~4694 of service.py) which invokes `presets/compiler.py:compile_presets()`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": {
      "type": "string",
      "description": "Calculation ULID from create_calculation"
    },
    "presets": {
      "type": "object",
      "description": "Preset dimension selections (e.g., {precision: 'high', magnetism: 'collinear_lsda'})",
      "additionalProperties": { "type": "string" }
    }
  },
  "required": ["calc_ulid", "presets"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": { "type": "string" },
    "compiled_parameters": {
      "type": "object",
      "description": "The full parameter set after preset compilation"
    },
    "parameter_provenance": {
      "type": "object",
      "description": "Maps each parameter to its source: 'preset', 'structure', 'default'"
    }
  }
}
```

**Example Output:**
```json
{
  "calc_ulid": "01KC38MB...",
  "compiled_parameters": {
    "SYSTEM": {
      "ecutwfc": 40.0,
      "ecutrho": 320.0,
      "nspin": 1,
      "occupations": "smearing",
      "smearing": "gaussian",
      "degauss": 0.02
    },
    "ELECTRONS": {
      "conv_thr": 1e-8,
      "mixing_beta": 0.7
    }
  },
  "parameter_provenance": {
    "SYSTEM.ecutwfc": "precision_advisor(PP_min=30, factor=1.33)",
    "SYSTEM.nspin": "preset(magnetism=nonmagnetic)",
    "ELECTRONS.conv_thr": "preset(precision=med)"
  },
  "context_hint": "Preset applied. Use set_parameters to override specific values, or inspect_calculation to review the full state."
}
```

---

#### `inspect_calculation`

**Description**: Read the current state of a configured calculation from YAML. Shows all parameters currently set, their provenance (preset/manual/default), the structure, and the workflow steps. Supports `dry_run` flag that materializes input files and returns the generated content WITHOUT executing.

**Maps to**: `QVService.Calculation.get_detail()` (line ~4341) + `QVService.Calculation.get_step_detail()` (line ~3613) for reading current state. For `dry_run=true`, calls `write_engine_inputs()` to a temp dir and returns content.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": {
      "type": "string",
      "description": "Calculation ULID"
    },
    "dry_run": {
      "type": "boolean",
      "default": false,
      "description": "If true, materialize input files (call writer) and return generated content WITHOUT executing"
    },
    "step": {
      "type": "integer",
      "description": "Optional: inspect only this step (0-based). Default: all steps."
    }
  },
  "required": ["calc_ulid"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": { "type": "string" },
    "name": { "type": "string" },
    "engine": { "type": "string" },
    "workflow": { "type": "string" },
    "structure_summary": { "type": "string" },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "step_index": { "type": "integer" },
          "step_type": { "type": "string" },
          "parameters": { "type": "object" },
          "parameter_provenance": { "type": "object" }
        }
      }
    },
    "input_files": {
      "type": "array",
      "description": "Generated input file contents (only when dry_run=true)",
      "items": {
        "type": "object",
        "properties": {
          "filename": { "type": "string" },
          "content": { "type": "string" }
        }
      }
    },
    "warnings": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

**The three levels of pre-run inspection:**

| Level | Tool | State | Purpose |
|---|---|---|---|
| **Stateless what-if** | `preview_compilation` | No calculation exists | "What would standard precision Si bands look like?" |
| **Stateful read** | `inspect_calculation` | Calculation exists, YAML configured | "Show me what's currently set up." |
| **Stateful materialization** | `inspect_calculation(dry_run=true)` | Calculation exists, writer generates files | "Generate actual input files so I can verify writer output." |

---

#### `run_calculation`

**Description**: Execute a configured calculation. Only runs — does not configure. The calculation must already exist (via `create_calculation`) and be configured (via `set_parameters` and/or `apply_preset`).

**Maps to**: `QVService.Run.run_calculation()` (line ~6178 of service.py)

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": {
      "type": "string",
      "description": "Calculation ULID to execute"
    }
  },
  "required": ["calc_ulid"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "job_id": { "type": "string" },
    "calc_ulid": { "type": "string" },
    "status": { "type": "string", "enum": ["queued", "running"] },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "step_ulid": { "type": "string" },
          "step_type": { "type": "string" },
          "status": { "type": "string" }
        }
      }
    }
  }
}
```

---

#### `get_status`

**Description**: Check the status of a running or completed calculation.

**Maps to**: `QVService.Run.get_job_status(job_id)` via `JobManager`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "job_id": { "type": "string", "description": "Job ID from run_calculation" }
  },
  "required": ["job_id"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "job_id": { "type": "string" },
    "status": { "type": "string", "enum": ["queued", "running", "completed", "failed", "cancelled"] },
    "progress": {
      "type": "object",
      "properties": {
        "current_step": { "type": "string" },
        "steps_completed": { "type": "integer" },
        "steps_total": { "type": "integer" }
      }
    },
    "wall_time_seconds": { "type": "number" },
    "error_summary": { "type": "string" }
  }
}
```

---

#### `get_results_summary`

**Description**: Token-efficient summary of calculation results. Returns 5-10 key values that capture the essential outcome.

**Maps to**: `QVService.Analysis.get_step_digest(run_ulid, step_ulid)` which calls engine-specific `OutputParser.parse()` (e.g., `VASPOutputParser`, `QEOutputParser`)

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": { "type": "string" },
    "step_ulid": {
      "type": "string",
      "description": "Optional: specific step. Defaults to last step."
    }
  },
  "required": ["calc_ulid"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": { "type": "string" },
    "engine": { "type": "string" },
    "step_type": { "type": "string" },
    "converged": { "type": "boolean" },
    "total_energy_eV": { "type": "number" },
    "energy_per_atom_eV": { "type": "number" },
    "bandgap_eV": { "type": ["number", "null"] },
    "max_force_eV_per_ang": { "type": ["number", "null"] },
    "total_magnetization": { "type": ["number", "null"] },
    "scf_iterations": { "type": "integer" },
    "wall_time_seconds": { "type": "number" },
    "warnings": { "type": "array", "items": { "type": "string" } }
  }
}
```

**Example Output**:
```json
{
  "calc_ulid": "01KC38MFJZ...",
  "engine": "vasp",
  "step_type": "vasp_scf",
  "converged": true,
  "total_energy_eV": -10.9423,
  "energy_per_atom_eV": -5.4712,
  "bandgap_eV": 0.67,
  "max_force_eV_per_ang": null,
  "total_magnetization": null,
  "scf_iterations": 12,
  "wall_time_seconds": 45.3,
  "warnings": [],
  "context_hint": "For band structure details, call get_band_structure(calc_ulid='01KC38MFJZ...'). For DOS, call get_dos(calc_ulid='...')."
}
```

---

#### `quick_run` (convenience shortcut)

**Description**: One-shot: create calculation + apply preset + run. Equivalent to `create_calculation` → `apply_preset` → `run_calculation` in one call. Designed for the 80% case where presets exist and are good enough. **Only works when presets are available for the engine+workflow.**

**Maps to**: Sequential calls to `QVService.Calculation.create()` → `QVService.Calculation.apply_presets()` → `QVService.Run.run_calculation()`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "engine": { "type": "string" },
    "workflow": { "type": "string" },
    "structure_ulid": { "type": "string" },
    "presets": {
      "type": "object",
      "additionalProperties": { "type": "string" },
      "description": "Preset dimension selections"
    },
    "overrides": {
      "type": "object",
      "description": "Optional parameter overrides applied after preset compilation"
    },
    "name": {
      "type": "string",
      "description": "Human-readable name for this calculation"
    }
  },
  "required": ["engine", "workflow", "structure_ulid", "presets"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "calc_ulid": { "type": "string" },
    "job_id": { "type": "string" },
    "status": { "type": "string" },
    "compiled_parameters_summary": { "type": "object" }
  }
}
```

---

#### `preview_compilation` (stateless what-if)

**Description**: **Stateless query**: "What would the compiled parameters look like if I applied these presets to this structure?" Does NOT create a calculation, does NOT write to disk. Returns compiled parameters + parameter provenance + optionally generated input file content. Useful for exploration before committing. **Only works when presets are available** (otherwise there is nothing to "compile").

This is QMatSuite's unique capability. No competitor offers it. The preset system guarantees mathematical reversibility: `detect(compile(options)) == options`. The `preview_compilation` tool exercises the forward direction — it takes high-level intent (engine + workflow + preset dimensions + optional overrides) and produces the complete, engine-specific parameter set.

**Maps to**: `presets/compiler.py:compile_presets()` + `presets/precision_context.py:PrecisionAdvisor.recommend()` + optionally `inputformat/writer.py:write_engine_inputs()` (to temp dir, discarded after preview)

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "engine": {
      "type": "string",
      "description": "Engine name (e.g., 'vasp', 'qe')"
    },
    "workflow": {
      "type": "string",
      "description": "Workflow name (e.g., 'bands', 'relax')"
    },
    "structure_ulid": {
      "type": "string",
      "description": "ULID of the crystal structure to use"
    },
    "presets": {
      "type": "object",
      "description": "Preset dimension selections (e.g., {precision: 'high', magnetism: 'collinear_lsda'})",
      "additionalProperties": { "type": "string" }
    },
    "overrides": {
      "type": "object",
      "description": "Manual parameter overrides applied after preset compilation",
      "additionalProperties": {}
    },
    "show_input_file": {
      "type": "boolean",
      "default": false,
      "description": "If true, include the generated input file text in the response"
    }
  },
  "required": ["engine", "workflow", "structure_ulid"]
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "engine": { "type": "string" },
    "workflow": { "type": "string" },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "step_type": { "type": "string" },
          "parameters": { "type": "object" },
          "parameter_provenance": {
            "type": "object",
            "description": "Maps each parameter to its source: 'preset', 'structure', 'override', 'default'"
          }
        }
      }
    },
    "input_files": {
      "type": "array",
      "description": "Generated input file contents (only if show_input_file=true)",
      "items": {
        "type": "object",
        "properties": {
          "filename": { "type": "string" },
          "content": { "type": "string" }
        }
      }
    },
    "warnings": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

---

### 5.4 On-Demand Tools (defer_loading: true)

These tools are discovered via Tool Search when needed. They add zero tokens to initial context.

#### Detailed Analysis Tools

| Tool | Description | Maps To |
|---|---|---|
| `get_band_structure` | k-resolved eigenvalues with high-symmetry labels; optionally returns MCP App | `core/analysis/band_structure/model.py:BandStructure.to_primitives()` |
| `get_dos` | Total and projected DOS with atom/orbital decomposition | `core/analysis/dos/model.py:DOS.to_primitives()` |
| `get_convergence_history` | SCF iteration energies and forces for convergence analysis | Step digest series extraction |
| `get_trajectory` | Geometry frames for relaxation/MD with energies and forces | `core/analysis/trajectory/model.py:Trajectory` |
| `compare_calculations` | Side-by-side comparison of energy, bandgap, forces across runs | Multi-calc query over provenance DB |
| `get_field3d` | 3D scalar field data (charge density, wavefunction) | `core/analysis/field3d.py:Field3D` |
| `get_output_raw` | Paginated raw output file access (escape hatch) | `QVService.Analysis.read_step_artifact_text()` |

#### Structure Tools

| Tool | Description | Maps To |
|---|---|---|
| `list_structures` | List available crystal structures in the current project | `QVService.Structure.list()` |
| `fetch_structure` | Fetch structure from Materials Project, AFLOW, COD, or OPTIMADE | `QVService.OnlineSearch.search()` + `import_online_candidate()` |
| `import_structure` | Import structure from local file (CIF, POSCAR, XYZ, etc.) | `QVService.Structure.import_file()` |
| `get_structure_detail` | Full crystallographic data with visualization | `QVService.Structure.get()` + `get_structure_vis()` |

Note: `list_structures` is on-demand, not always-loaded. The agent usually knows the structure or fetches it; this doesn't need to be in initial context.

#### Batch Tools

| Tool | Description | Maps To |
|---|---|---|
| `submit_batch` | Submit multiple independent calculations in parallel. Creates and runs each as a separate job. Useful for parameter scans, convergence tests, screening. Input: array of calc specs. Output: array of {calc_ulid, job_id}. Internally loops over `create_calculation` + `run_calculation`. | MCP-side orchestration over `QVService.Calculation.create()` + `QVService.Run.run_calculation()` |
| `get_batch_status` | Poll status of multiple jobs at once. Returns status array. | MCP-side loop over `QVService.Run.get_job_status()` |

#### Parameter Tuning Tools

| Tool | Description | Maps To |
|---|---|---|
| `diff_presets` | Show parameter differences between two preset levels | `presets/compiler.py:compile_presets()` diff |
| `get_parameter_detail` | Full documentation for a specific engine parameter | `*_metadata.py:get_tag_info()` |

#### Provenance Tools

| Tool | Description | Maps To |
|---|---|---|
| `get_project_history` | Query past calculations in the current project (timeline of runs, edits, pins) | `QVService.History.get_timeline()` + `list_run_history()` (already implemented, 5 methods) |
| `get_provenance` | Full lineage of a calculation: run details, parameter snapshot, step results | `QVService.History.get_run_revision()` (already implemented) |
| `annotate_calculation` | Add researcher notes to a calculation | Journal entry creation (needs new write API) |
| `record_intent` | Record WHY a calculation is being run (before execution). Appends to provenance journal. | `QVService.History.add_journal_entry(calc_ulid, "intent", text)` (needs new method; Journal infra at `core/journal.py` exists) |
| `record_interpretation` | Record WHAT the agent concluded (after analysis). Appends to provenance journal. | `QVService.History.add_journal_entry(calc_ulid, "interpretation", text)` (needs new method) |

#### Knowledge Tools

| Tool | Description | Maps To |
|---|---|---|
| `search_knowledge` | Search accumulated insights by natural language query, material, engine, workflow, minimum grade, and confidence. Returns ranked results from all sources (builtin, local, community). Input: `{query_text?, material?, engine?, workflow?, grade_min?, source?, confidence_min?, limit?}`. | `~/.qmatsuite/knowledge.db` FTS5 query with scope filtering |
| `record_insight` | Record a distilled insight with structured grade, scope, and provenance links. Input: `{grade, scope: {material, engine, workflow}, content, confidence, tags?, provenance_refs?}`. | `~/.qmatsuite/knowledge.db` insert |
| `update_insight` | Update content/confidence or supersede an existing insight. Sets `superseded_by` on old entry, creates new entry. | `~/.qmatsuite/knowledge.db` update + insert |

### 5.5 API Surface Assessment and Gaps

Code review reveals that the existing QVService and infrastructure are more mature than initially assumed. The fine-grained tool model maps well to existing methods:

#### What Already Exists

| MCP Tool | QVService Method | Status |
|---|---|---|
| `create_calculation` | `QVService.Calculation.create()` | Fully implemented |
| `set_parameters` | `QVService.Calculation.update_step_params()` | Fully implemented |
| `apply_preset` | `QVService.Calculation.apply_presets()` | Fully implemented |
| `inspect_calculation` (read) | `QVService.Calculation.get_detail()` + `get_step_detail()` | Fully implemented |
| `run_calculation` | `QVService.Run.run_calculation()` | Fully implemented |
| `get_status` | `QVService.Run.get_job_status()` | Fully implemented (via JobManager) |
| `get_results_summary` | `QVService.Analysis.get_step_digest()` | Fully implemented (15 engine parsers) |
| `get_project_history` | `QVService.History.get_timeline()` + `list_run_history()` | Fully implemented (5 History methods) |
| `get_provenance` | `QVService.History.get_run_revision()` | Fully implemented |
| `duplicate_calculation` | `QVService.Calculation.duplicate()` | Fully implemented (copies SSOT + raw/, regenerates ULIDs) |

#### What Also Exists (Supporting Infrastructure)

| Infrastructure | What It Provides | Location |
|---|---|---|
| **Provenance system** (3,600+ lines) | Append-only event log, CAS, snapshots, restore, query | `src/quantumvitas/provenance/` |
| **ErrorDTO** with rich diagnostics | type, code, message, retryable, hint, context, cause | `api/types/error.py` |
| **30 DTOs** across 9 files | Fail-closed serialization, reference pattern, metadata normalization | `api/types/` |
| **Multi-engine artifact resolution** | Cross-engine data flow (QE→W90, QE→QMCPACK, QE→Yambo) | `drivers/*/artifact_resolver.py` |
| **OperationContext** | 20+ operation types for all SSOT mutations | `provenance/opctx.py` |

#### Gaps That Need New QVService Methods

| MCP Tool | Required QVService Capability | Gap Description |
|---|---|---|
| `inspect_calculation(dry_run=true)` | Materialize input files to temp dir without executing | **New method needed** — `QVService.Calculation.materialize_preview()` wrapping `write_engine_inputs()` |
| `record_intent` / `record_interpretation` | Write agent-authored journal entries to provenance | **New method needed** — `QVService.History.add_journal_entry(calc_ulid, entry_type, text)`. The Journal infrastructure (`core/journal.py`, 369 lines) provides append-only storage; the gap is exposing a typed write API. |
| `search_knowledge` / `record_insight` | Knowledge Base CRUD | **New module needed** — `knowledge/` package with SQLite+FTS5 store. Phase 1: read builtin entries. Phase 3: full CRUD + search. |
| Error `suggested_fixes` | Knowledge-backed error recovery suggestions | **Enhancement needed** — MCP layer enriches existing `ErrorDTO` + `*Digest` with `suggested_fixes` from Knowledge Base. No kernel changes needed. |

Per Section 3.2 (MCP as Equal Frontend), these capabilities should be added to `QVService`, not hacked around in the MCP layer. Both methods benefit all frontends: the GUI can use `materialize_preview` for input file inspection, and CLI can use journal entries for scripted workflows.

### 5.6 Tool Return Format Standard

Every tool returns a standard envelope:

```python
@dataclass
class ToolReturn:
    status: Literal["success", "error", "warning"]
    data: dict                          # The actual result
    context_hint: str | None = None     # Guides agent's next action
    token_cost: Literal["low", "medium", "high"] = "low"

@dataclass
class ErrorReturn:
    status: Literal["error"] = "error"
    error_type: str                     # e.g., "SCF_NOT_CONVERGED"
    severity: Literal["fatal", "recoverable", "warning"]
    diagnostics: dict                   # Structured error data
    suggested_fixes: list[SuggestedFix]
    context_hint: str | None = None

@dataclass
class SuggestedFix:
    action: str                         # e.g., "reduce_mixing_beta"
    parameter: str                      # e.g., "ELECTRONS.mixing_beta"
    from_value: Any
    to_value: Any
    confidence: Literal["high", "medium", "low"]
    reason: str
```

**Error return example — SCF not converged:**

```json
{
  "status": "error",
  "error_type": "SCF_NOT_CONVERGED",
  "severity": "recoverable",
  "diagnostics": {
    "iterations_completed": 87,
    "max_iterations": 100,
    "energy_oscillating": true,
    "last_energy_change_eV": 0.003,
    "charge_sloshing_detected": true
  },
  "suggested_fixes": [
    {
      "action": "reduce_mixing_beta",
      "parameter": "ELECTRONS.mixing_beta",
      "from_value": 0.7,
      "to_value": 0.3,
      "confidence": "high",
      "reason": "Energy oscillation pattern indicates charge sloshing. Lower mixing stabilizes convergence."
    },
    {
      "action": "increase_max_iterations",
      "parameter": "ELECTRONS.electron_maxstep",
      "from_value": 100,
      "to_value": 200,
      "confidence": "medium",
      "reason": "May converge with more iterations, but oscillation should be addressed first."
    }
  ],
  "context_hint": "Use set_parameters to apply the suggested fix, then inspect_calculation(dry_run=true) to verify before resubmitting."
}
```

---

## 6. Context Engineering Strategy

### 6.1 Tiered Returns (Progressive Disclosure)

Every data-producing tool implements three tiers, controlled by an optional `detail` parameter:

| Tier | Default | Token Budget | Content | Use Case |
|---|---|---|---|---|
| **Summary** | Yes | ~200 tokens | 5-10 key values | Agent decides next step |
| **Detailed** | On request | ~500-2,000 tokens | Full structured data for one property | Agent needs specifics |
| **Raw** | On request | Paginated | Output file sections | Debugging, escape hatch |

**Implementation**: Every tool that returns data accepts `detail: "summary" | "detailed" | "raw"`. Default is always `"summary"`. The agent explicitly upgrades when needed:

```
Agent: get_results_summary(calc_ulid="01KC...") → 200 tokens, sees bandgap=0.67
Agent: get_band_structure(calc_ulid="01KC...", detail="detailed") → 1,500 tokens, full k-resolved data
```

This maps directly to the 100:1 input-to-output ratio principle. In a typical 10-calculation research workflow, the agent makes ~50 tool calls. At summary tier, total tool output is ~10,000 tokens. At detailed tier for every call, it would be ~100,000 tokens. Progressive disclosure gives 10x token savings while preserving access to full data when needed.

### 6.2 Context Hints

Every tool return includes a `context_hint` field. This is structured guidance, not prompt injection:

| After this tool... | Context hint |
|---|---|
| `list_engines` | "Use list_workflows(engine='...') to see available workflows" |
| `list_workflows` | "Use get_presets(engine='...', workflow='...') to check for available presets" |
| `get_presets` (has presets) | "Use preview_compilation to see full parameters, or quick_run for the fast path" |
| `get_presets` (no presets) | "Use search_parameters to find relevant parameters, then create_calculation + set_parameters" |
| `create_calculation` | "Use set_parameters or apply_preset to configure, then run_calculation to execute" |
| `set_parameters` | "Use inspect_calculation to review current state, or run_calculation to execute" |
| `apply_preset` | "Use set_parameters to override specific values, or run_calculation to execute" |
| `preview_compilation` | "To commit, call create_calculation + apply_preset + run_calculation, or use quick_run" |
| `inspect_calculation` | "Use run_calculation to execute, or set_parameters to adjust" |
| `run_calculation` | "Call get_status(job_id='...') to check progress" |
| `get_status` (completed) | "Call get_results_summary(calc_ulid='...') for results" |
| `get_results_summary` | "For band structure: get_band_structure(...). For DOS: get_dos(...)" |
| Error return | "Use set_parameters to apply the suggested fix, then inspect_calculation to verify" |

Context hints create a natural flow without hardcoding it. The agent can always ignore hints and take a different path — they are metadata, not instructions.

### 6.3 KV-Cache Cooperation

Following Manus's most important optimization, the MCP server cooperates with KV-cache efficiency:

**Stable tool definitions.** Tool schemas are declared once at server initialization and never modified. No dynamic tool addition/removal that would invalidate the cache prefix.

**Deterministic JSON key ordering.** All tool returns use `sort_keys=True` serialization. Identical results produce identical byte sequences, maximizing cache hits for repeated queries.

**Consistent URI patterns.** Resource URIs follow deterministic patterns: `qmatsuite://engines/{engine}/parameters`, `qmatsuite://calculations/{calc_ulid}/results`. Cache-friendly prefix matching works naturally.

**Append-only context.** Tool returns are designed to be appended to conversation history without modification. No "update previous result" patterns that would require rewriting earlier context.

### 6.4 Filesystem as External Memory

QMatSuite's SSOT files naturally serve as externalized agent memory:

| Memory Need | QMatSuite File | Agent Access |
|---|---|---|
| Current calculation state | `calculation.yaml` | `inspect_calculation` |
| Detailed step parameters | `step.yaml` (under `raw/`) | `inspect_calculation`, `set_parameters` |
| Run history across calculations | `.provenance/` SQLite | `get_project_history` |
| Accumulated insights | `~/.qmatsuite/knowledge.db` | `search_knowledge`, `record_insight` |

This means context compaction (Claude Code's conversation summarization when approaching context limits) loses no critical state. The agent can always re-query the filesystem for current state. The conversation history is for reasoning traces; the SSOT files are for ground truth.

---

## 7. Memory Architecture: Four Layers

### 7.1 Layer 1: Agent Context (Ephemeral)

The LLM's context window, managed by the client (Claude Code's compaction, Gemini's 1M window, etc.). QMatSuite cooperates by:

- Returning token-efficient summaries by default (Section 6.1)
- Including `context_hint` fields that guide attention (Section 6.2)
- Using stable tool definitions for KV-cache efficiency (Section 6.3)
- Never requiring the agent to maintain state that could be re-queried from SSOT

**The working memory contract: QMatSuite NEVER assumes the agent remembers a previous tool return.** Every tool return is self-contained. If the agent needs the energy from a previous calculation, it calls `get_results_summary` again rather than relying on conversation history. This is essential because context compaction, conversation restart, and multi-session workflows all destroy ephemeral context.

### 7.2 Layer 2: Present-Tense SSOT (Current State, Flat)

**Storage**: `calculation.yaml`, `step.yaml`, `raw/*.in`, `raw/*.out`, `raw/artifacts/`

**Semantics**: "What IS the current state of this calculation?" Always flat, always current.

**Key property**: YAML is the single source of truth. Every `set_parameters`, `apply_preset` call immediately persists to YAML. Runtime logic reads YAML directly — never queries provenance or history to determine current state.

**Agent access**: `inspect_calculation` reads this layer.

**Design invariant**: The present-tense SSOT is flat and self-contained. You can understand the current state of any calculation by reading its `calculation.yaml` and `step.yaml` files. No need to replay a history of mutations or query a separate database.

### 7.3 Layer 3: Provenance (Append-Only Ledger, Project-Scoped)

**Storage**: `.provenance/` directory — SQLite run history + `.cas` content-addressable store

**Semantics**: "What HAPPENED?" An immutable audit trail of all actions and their outcomes.

**Key property**: Append-only. Never modified. Never used as runtime logic base. This is the "court of final record."

#### Existing Infrastructure (3,600+ lines, production-ready)

Layer 3 is the most mature layer — it already exists as a fully implemented, gate-tested subsystem:

| Component | Module | Status |
|---|---|---|
| **OperationContext** | `provenance/opctx.py` (256 lines) | Mandatory envelope for all SSOT writes. 20+ operation types (CALC_COPY, STEP_ADD, PRESET_APPLY, RESTORE, ROLLBACK, etc.). Frozen dataclass with actor, scope, payload, timestamp. |
| **SQLite Schema** | `provenance/schema.py` (289 lines) | 5-table schema (v3): `operations` (append-only event log), `runs` (execution records), `run_steps` (per-step results), `analysis_snapshots` (object linkage), `cas_objects` (blob metadata). |
| **CAS** | `provenance/cas.py` (220 lines) | Content-addressed store at `.provenance/.cas/objects/<sha256>`. Immutable blobs with 5 tiers (run snapshots → large optional). Dedup: same hash = no-op. |
| **Recording** | `provenance/recording.py` (451 lines) | `record_operation_event()` computes diff summary and appends to `operations` table. Called after every SSOT write. |
| **Snapshots** | `provenance/snapshots.py` (130 lines) | `create_run_snapshot()` serializes calculation.yaml + step.yaml to Tier-0 CAS (never auto-deleted). `get_run_snapshot()` retrieves from CAS. |
| **Restore** | `provenance/restore.py` (158 lines) | Restore SSOT from any snapshot. Records RESTORE operation. |
| **Journal** | `core/journal.py` (369 lines) | Append-only JSONL log with before/after snapshots. Hooks into `save_yaml_doc()`. |
| **Query API** | `provenance/query.py` (376 lines) | `query_operations()`, `query_runs()`, `get_run_details()`, `build_timeline_entry()`. Graceful degradation: missing tables return empty results. |
| **Pins** | `provenance/pins.py` (377 lines) | Pin analysis results (plots, JSON data) to run history with provenance linkage. |
| **Scanner** | `provenance/scanner.py` (275 lines) | Tracks which run/step produced each output file in `raw/`. |
| **Service API** | `api/service.py` QVService.History | 5 public methods: `get_timeline()`, `get_run_revision()`, `get_storage_summary()`, `list_run_history()`, `pin_analysis()`. |

**Governance**: 9 binding laws (P1–P9) in `docs/laws/L1/PROVENANCE_VERSIONED_HISTORY_SPEC.md`, enforced by 7 gate tests in CI. Key laws: P1 (SSOT separation — deleting `.provenance/` leaves project runnable), P2 (OperationContext required on all saves), P4 (append-only timeline), P7 (graceful degradation).

#### What Gets Recorded

| Category | Content | Source |
|---|---|---|
| Agent intent | WHY a calculation was submitted | Via `record_intent` tool (needs new journal write API) |
| Operation events | Every SSOT mutation with before/after diff | Auto-recorded by `save_yaml_doc()` hook |
| Run metadata | Start time, parameter snapshot (CAS Tier-0), engine version | Auto-recorded by Runner on `run_calculation` |
| Step results | Per-step status, timing, exit code, digest SHA | Auto-recorded by Runner on step completion |
| Result digest | Energy, convergence, forces, properties | Auto-recorded by OutputParser on completion |
| Analysis pins | Plots and JSON data linked to specific runs | Via `pin_analysis()` |
| Agent interpretation | WHAT the agent concluded from the results | Via `record_interpretation` tool (needs new journal write API) |

**Agent access**: `get_project_history`, `get_provenance`

**Critical design point**: Intent is NOT part of present-tense SSOT. Presets encode intent structurally (e.g., "precision=high" IS the intent). But the textual rationale ("testing U=5 because literature suggests 4-6 eV range") lives ONLY in provenance.

**Gap for MCP**: The existing provenance system records *system events* (operation diffs, run metadata, step results) automatically. What's missing is the ability to record *agent-authored entries* — intent and interpretation. This requires a new `QVService.History.add_journal_entry(calc_ulid, entry_type, text)` method. The Journal infrastructure (`core/journal.py`) provides the append-only storage mechanism; the gap is exposing a write API through QVService.

### 7.4 Layer 4: Knowledge Base (Evolvable Best-Knowledge, Multi-Scope)

**Storage**: `~/.qmatsuite/knowledge.db` (SQLite with FTS5, user-global, not project-specific)

**Semantics**: "What have we LEARNED?" Distilled insights from accumulated experience.

**Key property**: Unlike provenance, this IS mutable — insights can be updated, superseded, deduplicated. This is the agent's "best current understanding," not an audit trail.

#### The Insight Structure

Every knowledge entry is a structured insight with grade, scope, source, and provenance links:

```yaml
id: <ULID>                           # Unique identifier
grade: bookkeeping | observation | finding | principle
scope:
  material: "Si" | "GaAs" | "*"      # What material family
  engine: "QE" | "VASP" | "*"        # What engine
  workflow: "scf" | "bands" | "*"    # What workflow type
content: "natural language description"
confidence: low | medium | high       # Based on evidence count and consistency
source: local | literature | community | builtin
provenance_refs: [list of Layer 3 entry IDs]
created_by: agent | user | paper_doi | system
tags: [list of strings]
created_at: <ISO datetime>
updated_at: <ISO datetime>
upvotes: 0                            # For community voting (future)
superseded_by: null | <ULID>          # If updated by newer knowledge
```

**Grade semantics** — four levels of epistemic commitment:

| Grade | Semantics | Example | Typical Source |
|---|---|---|---|
| **bookkeeping** | Pure record, no insight | "Si SCF with ecutwfc=60 converged in 12 steps" | Auto-digest after every calculation |
| **observation** | Data without conclusion | "Increasing ecutwfc from 40→60 changed Si energy by 3 meV/atom" | Agent comparing two calculations |
| **finding** | Conclusion with evidence | "Si ecutwfc converges to <1 meV/atom above 50 Ry" | Agent analyzing convergence scan |
| **principle** | Cross-material/cross-engine general rule | "III-V semiconductors with PBE+SOC underestimate band gap by 30-40%" | Literature, accumulated findings |

Grades form a knowledge hierarchy. Bookkeeping entries are raw data. Observations notice patterns. Findings draw conclusions. Principles generalize across systems. A real researcher progresses up this hierarchy as expertise accumulates — and so does the agent.

**Scope** determines when an insight is relevant. An insight with `{material: "Si", engine: "QE", workflow: "scf"}` is surfaced when the agent configures a Si SCF calculation with QE. An insight with `{material: "*", engine: "VASP", workflow: "*"}` is surfaced for any VASP calculation. The wildcard `"*"` means "applies broadly."

**Source** tracks provenance of the knowledge itself:

| Source | Meaning | Trust Level |
|---|---|---|
| `local` | From user's own calculations | Highest (first-hand evidence) |
| `builtin` | Shipped with QMatSuite (error recovery strategies, best practices) | High (curated by developers) |
| `literature` | Extracted from papers (future: citation analysis) | High (peer-reviewed) |
| `community` | Contributed by other researchers (future) | Variable (voted/curated) |

#### Schema

```sql
CREATE TABLE insights (
    id TEXT PRIMARY KEY,                -- ULID
    grade TEXT NOT NULL,                -- bookkeeping, observation, finding, principle
    scope_material TEXT DEFAULT '*',    -- Material family or '*'
    scope_engine TEXT DEFAULT '*',      -- Engine name or '*'
    scope_workflow TEXT DEFAULT '*',    -- Workflow type or '*'
    content TEXT NOT NULL,              -- Natural language description
    confidence TEXT DEFAULT 'medium',   -- low, medium, high
    source TEXT NOT NULL DEFAULT 'local', -- local, builtin, literature, community
    provenance_refs TEXT,               -- JSON array of Layer 3 entry IDs
    created_by TEXT NOT NULL,           -- agent, user, paper_doi, system
    tags TEXT,                          -- JSON array of string tags
    upvotes INTEGER DEFAULT 0,         -- Community voting (future)
    superseded_by TEXT,                 -- ULID of superseding insight
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (superseded_by) REFERENCES insights(id)
);

CREATE VIRTUAL TABLE insights_fts USING fts5(
    content, tags, scope_material, scope_engine,
    content='insights', content_rowid='rowid'
);

CREATE INDEX idx_insights_grade ON insights(grade);
CREATE INDEX idx_insights_scope ON insights(scope_material, scope_engine, scope_workflow);
CREATE INDEX idx_insights_source ON insights(source);
CREATE INDEX idx_insights_confidence ON insights(confidence);
CREATE INDEX idx_insights_superseded ON insights(superseded_by);
```

**Deduplication**: When a new insight contradicts an existing one, the old insight is superseded (marked with `superseded_by` reference), not deleted. History is preserved. This mirrors how scientific understanding evolves — old findings aren't erased, they're refined.

**Agent access**: `search_knowledge`, `record_insight`, `update_insight`

### 7.5 The Distillation Pipeline: Four Triggers

Knowledge doesn't just accumulate — it distills. Raw experience becomes organized understanding through four distinct triggers:

```
Layer 3 (Provenance)                    Layer 4 (Knowledge)
┌──────────────────────┐               ┌──────────────────────┐
│ Run records           │──[auto]──────>│ bookkeeping entries  │
│ Parameter snapshots   │               │ (every calc)         │
│ Result digests        │               │                      │
│ Intent/interpretation │──[agent]─────>│ observations         │
│                       │               │ findings             │
│                       │──[review]────>│ principles           │
└──────────────────────┘               └──────────────────────┘
```

#### Trigger 1: Auto-Digest (Every Calculation Completion)

When a calculation completes, QMatSuite generates a structured digest (converged? energy? gap? forces? timing?). The agent reads this digest and SHOULD write at least one bookkeeping-level insight. This happens naturally in the INTERPRET step of the research cycle (Section 8).

Example auto-generated bookkeeping:
```
grade: bookkeeping
scope: {material: "Si", engine: "QE", workflow: "scf"}
content: "Si PBE SCF with ecutwfc=40 Ry, 8x8x8 k-mesh converged in 9 iterations.
          Energy: -310.42 eV. Bandgap: 0.67 eV. Wall time: 45s."
source: local
provenance_refs: ["01KC38MFJZ..."]
```

#### Trigger 2: User Pin ("Remember This")

The user explicitly marks something important: "remember that U=5 works for FeO" or "pin this finding." The agent converts the statement to a structured insight with grade ≥ finding. The pin action itself is recorded as a provenance event. (The existing `pin_analysis()` API at `provenance/pins.py` provides the infrastructure; knowledge pins extend this pattern.)

#### Trigger 3: Accumulation Review (Threshold)

When a scope (e.g., `{material: "Si", engine: "QE"}`) accumulates N bookkeeping/observation entries (e.g., N=5), the system suggests a review. The agent consolidates multiple observations into findings or principles:

```
System: "You have 7 observations about Si/QE convergence. Would you like me to
         summarize what we've learned?"
Agent: Queries provenance for all Si/QE runs → synthesizes patterns →
       writes finding: "Si ecutwfc converges to <1 meV/atom above 50 Ry"
```

#### Trigger 4: Review Session (User-Initiated)

The user requests "summarize what we've learned" or "generate a report." The agent:
1. Queries knowledge base for the relevant scope
2. Queries provenance for supporting evidence
3. Produces both a document (markdown) AND knowledge entries
4. Records the review session as a provenance event

This mirrors how a researcher writes a lab report at the end of a project — the act of writing is itself a learning exercise that crystallizes understanding.

### 7.6 Knowledge as Extensible Community Library

The Knowledge Base is designed as a **searchable, contributable, extensible library** — not just a local cache.

#### Four Knowledge Sources

```
┌─────────────────────────────────────────────────────┐
│                  Knowledge Base                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │  Builtin  │  │  Local   │  │Literature│  ┌──────┐│
│  │ (shipped) │  │ (user's  │  │ (papers) │  │Commty││
│  │           │  │  calcs)  │  │          │  │      ││
│  └──────────┘  └──────────┘  └──────────┘  └──────┘│
│       Phase 1       Phase 1      Phase 3+   Phase 4 │
└─────────────────────────────────────────────────────┘
```

**Builtin knowledge** (Phase 1): QMatSuite ships with a "starter pack" of curated principles. These are the error recovery suggestions, common best practices, and parameter guidelines that experienced practitioners know. Examples:

```yaml
- grade: principle
  scope: {material: "*", engine: "VASP", workflow: "scf"}
  content: "For metallic systems, use ISMEAR=1 (Methfessel-Paxton) with SIGMA=0.1-0.2.
            Gaussian smearing (ISMEAR=0) converges 2-3x slower for metals."
  source: builtin
  confidence: high

- grade: principle
  scope: {material: "*", engine: "*", workflow: "scf"}
  content: "When SCF oscillates without converging, reduce mixing parameter by 50%.
            For QE: mixing_beta 0.7→0.3. For VASP: AMIX 0.4→0.2."
  source: builtin
  confidence: high
```

**Local knowledge** (Phase 1): From the user's own calculations. Auto-generated bookkeeping plus agent-authored observations, findings, and principles.

**Literature knowledge** (Phase 3+): Extracted from paper analysis. Future: QE/VASP citation analysis projects could extract parameter statistics from thousands of published papers, creating a massive knowledge base of "what parameters does the community actually use for this system type?"

**Community knowledge** (Phase 4): Other researchers contribute findings. Distribution model:
- Community packs downloadable (like a package manager for computational knowledge)
- Users can upload their finding-and-above entries (provenance stripped to protect privacy, but scope/content/confidence preserved)
- Voting/curation mechanism for quality control
- Moderated by domain experts

#### Search Interface

```
search_knowledge(
  query_text?: str,          # Natural language FTS5 search
  material?: str,            # Scope filter
  engine?: str,              # Scope filter
  workflow?: str,            # Scope filter
  grade_min?: str,           # Minimum grade (e.g., "finding" excludes bookkeeping)
  source?: str,              # Source filter
  confidence_min?: str,      # Minimum confidence
  limit?: int = 10
) → list[Insight]
```

Results are ranked by `confidence × FTS5_relevance`, with `grade` as a secondary sort (principles first).

### 7.7 Error System ↔ Knowledge System Connection

**Key insight: Error recovery suggestions ARE knowledge entries.**

The structured error suggestions that QMatSuite provides (Section 10) are `{source: "builtin", grade: "principle"}` knowledge entries. This connection has three consequences:

1. **The error system is a downstream consumer of the Knowledge Base.** When a calculation fails with SCF_NOT_CONVERGED, the MCP error return's `suggested_fixes` are populated by querying the knowledge base for `{scope: {engine: X, workflow: "scf"}, grade: "principle", tags: ["error_recovery", "scf_convergence"]}`.

2. **Community knowledge enriches error recovery without code changes.** As the community contributes recovery strategies, the `suggested_fixes` list grows automatically. A VASP user discovers that `ALGO=All` fixes a specific convergence pathology → contributes finding → all future users see this suggestion.

3. **Agent can search knowledge after failure.** Beyond the rule-based suggestions in the error return, the agent can call `search_knowledge(query="SCF convergence failure metallic", engine="vasp")` to find both builtin and community strategies. This is Level 2 recovery (Section 10) powered by accumulated knowledge.

**Phase 1 implementation**: Error suggestions are hardcoded rules in the MCP layer (as currently designed in Section 10). The knowledge base stores them as `source=builtin` entries, but the error system reads them directly (no DB query in the critical path).

**Phase 2+ implementation**: Error suggestions are dynamically queried from the knowledge base. New builtin entries added by developers. Community entries added by users. The error system becomes a live, growing repository of recovery wisdom.

### 7.8 Knowledge Injection: Layer 4 → Layer 1

Knowledge is only useful if it reaches the agent's context at the right time. Three injection mechanisms:

#### On-Demand Retrieval

The agent explicitly calls `search_knowledge` when it needs accumulated wisdom. Typical triggers:
- Starting a new calculation for a material/engine combination the agent has seen before
- Encountering an error and looking for recovery strategies
- User asks "what do we know about X?"

This is the simplest mechanism and sufficient for Phase 1-2.

#### Proactive Injection

When QMatSuite detects the material/engine/workflow of a new calculation, it can include relevant high-confidence knowledge in the tool response. For example, `create_calculation` could return:

```json
{
  "calc_ulid": "01KC...",
  "relevant_knowledge": [
    {
      "grade": "principle",
      "content": "For metallic Fe with VASP, ISMEAR=1 (Methfessel-Paxton) converges 3x faster than Gaussian.",
      "confidence": "high",
      "source": "builtin"
    }
  ]
}
```

**Token budget management**: Only inject `finding` and `principle` grade entries. Limit to top-K (default K=3) by `confidence × scope_specificity`. A principle scoped to `{material: "Fe", engine: "VASP"}` ranks higher than one scoped to `{material: "*", engine: "VASP"}` when the agent creates an Fe/VASP calculation.

#### Error-Time Injection

When a calculation fails, the error return includes `suggested_fixes` from the knowledge base (Section 7.7). This is the highest-value injection point — the agent needs help precisely when things go wrong, and accumulated knowledge is most useful here.

### 7.9 The Researcher Expertise Analogy

The four-layer memory architecture mirrors how real researchers build expertise:

| Researcher Process | Memory Layer | Agent Equivalent |
|---|---|---|
| **Working on a problem** | Working memory (context window) | Layer 1: Ephemeral agent context |
| **Lab notebook** | Current experiment state | Layer 2: Present-tense SSOT (YAML) |
| **Publication record** | Immutable record of what was done | Layer 3: Provenance ledger (append-only) |
| **Domain expertise** | "I just know metals need MP smearing" | Layer 4: Knowledge base (evolving) |

A postdoc with 5 years of VASP experience "just knows" convergence tricks for different system types. This knowledge was built through dozens of convergence failures and successes — individual experiments (Layer 3) distilled into expertise (Layer 4). QMatSuite makes this accumulation explicit, queryable, and shareable.

The key difference from AiiDA (which has provenance but no learning) and ExpeL/Reflexion (which have learning but no provenance): **QMatSuite's provenance is *generative* — it's the raw material for knowledge distillation, not a terminal archival endpoint.**

**Implementation note**: The full distillation pipeline is Phase 3+. Phase 1 needs only: (a) provenance auto-logging of tool calls (already exists), (b) `search_knowledge` querying a shipped builtin knowledge SQLite, (c) `record_insight` writing to local knowledge. The community/literature/distillation features are Phase 3-4. But the data model (structured insights with grade/scope/source/provenance_refs) is designed now so it's extensible without schema changes.

---

## 8. Provenance Interaction Protocol

### 8.1 The Research Cycle Protocol

Every research cycle follows a four-step protocol that maps to MCP tool calls:

```
1. INTENT — Before running:
   record_intent(calc_ulid, reason="Testing Hubbard U=5 eV for FeO to match exp. bandgap of 2.4 eV")
   → Appended to provenance journal

2. EXECUTE — During run:
   run_calculation(calc_ulid)
   → QMatSuite auto-records: run start time, full parameter snapshot, engine version
   → QMatSuite auto-records on completion: result digest (energy, convergence, wall time, key properties)

3. INTERPRET — After analyzing results:
   record_interpretation(calc_ulid, interpretation="U=5 gives bandgap=2.5 eV, within 0.1 eV of experiment.
   Acceptable for screening. HSE06 needed for publication-quality gaps.")
   → Appended to provenance journal

4. LEARN (optional) — When a pattern emerges across calculations:
   record_insight(scope="project", insight="For this FeO system, PBE+U with U=5 eV reproduces
   experimental bandgap within 5%", evidence=[calc_ulid_1, calc_ulid_2, ...])
   → Written to knowledge base
```

### 8.2 What Gets Auto-Recorded (No Tool Call Needed)

QMatSuite automatically records the following on every `run_calculation` call:

| Data | When Recorded | Storage |
|---|---|---|
| Run start timestamp | On job start | `.provenance/` SQLite |
| Full parameter snapshot at time of execution | On job start | `.provenance/` CAS |
| Engine version and execution environment | On job start | `.provenance/` SQLite |
| Result digest (energy, forces, convergence, etc.) | On job completion | `.provenance/` SQLite |
| Run end timestamp + wall time | On job completion | `.provenance/` SQLite |

### 8.3 Provenance Tools

Two thin tools for agent-authored journal entries:

- `record_intent(calc_ulid, reason: str)` — Record WHY this calculation is being run. Called before `run_calculation`. Thin wrapper around journal entry creation.
- `record_interpretation(calc_ulid, interpretation: str)` — Record WHAT the agent concluded. Called after analyzing results. Thin wrapper around journal entry creation.

**Implementation note**: These require a new `QVService.History.add_journal_entry(calc_ulid, entry_type, text)` method (see Section 5.5). The Journal infrastructure (`core/journal.py`, 369 lines) provides append-only JSONL storage with before/after snapshots; the OperationContext system (`provenance/opctx.py`) defines 20+ operation types including `PIN_CREATE`. Adding `AGENT_INTENT` and `AGENT_INTERPRETATION` operation types and exposing them through QVService.History is a small extension of well-tested infrastructure. Both tools are on-demand (Phase 2+).

---

## 9. Input Generation Integrity

### 9.1 Principle: All Input Files Go Through QMatSuite's Writers

The agent is NEVER allowed to bypass QMatSuite and write engine input files directly. All parameter setting goes through `set_parameters` → YAML → writer materialization. This ensures:

- **Provenance completeness**: Every parameter is tracked and recorded
- **Validation**: QMatSuite validates parameters against engine-specific schemas
- **Reproducibility**: Any calculation can be reconstructed from YAML
- **Consistency**: The SSOT (YAML) always matches what was actually run

### 9.2 When the Writer Has a Bug

If the writer generates incorrect input for a specific parameter combination:

- The `dry_run` flag on `inspect_calculation` is the primary debugging tool — it materializes input files without executing, so the agent (or user) can inspect and catch issues
- The correct response is to REPORT the writer bug, not to work around it
- The agent should NOT attempt to manually edit generated input files
- The user should file an issue or fix the writer; future calculations benefit from the fix

### 9.3 Writer Reliability Expectations

Structured writers are inherently more reliable than hand-written input files because they enforce type checking, enum validation, and mutual exclusion rules. However, given that QMatSuite is in active development:

- Engine-specific parameter coverage varies across engines
- Some parameter combinations may not be well-tested
- The `dry_run` → inspect flow provides a safety net
- MCP development may uncover writer gaps that should be fixed in the writer, not worked around in MCP

---

## 10. Error Recovery Architecture

### Codebase Assessment: What Exists Today

Code review reveals a substantial error infrastructure already in place:

**What exists (ready to use):**
- Rich API error hierarchy with 8 error classes and stable error codes (`NOT_FOUND`, `VALIDATION_FAILED`, `ENGINE_EXEC_FAILED`, `ENGINE_OUTPUT_PARSE_FAILED`, `ENGINE_NOT_AVAILABLE`, `EDIT_LOCK_HELD`, `RUN_LOCK_HELD`, `INTERNAL_ERROR`)
- `ErrorDTO` with structured fields: `type`, `code`, `message`, `retryable`, `hint`, `context`, `cause`
- `RunResultDTO` with embedded `ErrorDTO` on failure
- 15 engine output parsers (`@register_parser`) returning structured `*Digest` dataclasses with convergence flags (`converged_electronic`, `converged_ionic`, `converged_scf`), iteration counts, `error_message`, and energy/force metrics
- Exception mapping layer (`api/_mapping/exc_mapping.py`) that transforms 20+ kernel exception types to API errors with stable context extraction
- Input parse `Diagnostic` class (`inputformat/parser.py`) with level/message/file/line/code
- Levenshtein-based "did you mean?" suggestions for step type errors
- QE engine resolution diagnostics with multi-state model

**What's missing (needed for MCP):**
- No systematic `suggested_fixes` mechanism — parsers detect failure patterns but don't recommend parameter changes
- No failure root-cause analysis beyond convergence flag extraction
- No cross-engine error catalog with remediation metadata
- `ErrorDTO.hint` field exists but is rarely populated with actionable recovery guidance

**MCP bridge strategy**: The MCP error return layer enriches existing `ErrorDTO` + `*Digest` data with `suggested_fixes` drawn from the Knowledge Base (`source=builtin, grade=principle` entries). This adds recovery intelligence without modifying the kernel error system.

### Level 0: Prevention (Schema Validation)

The first line of defense prevents malformed requests from reaching the kernel.

**MCP input schema validation.** Every tool declares a JSON Schema for its inputs. The MCP protocol validates inputs before the tool function executes. Invalid parameters (wrong type, missing required field, value out of range) are caught at the protocol level.

**`inspect_calculation(dry_run=true)` catches parameter conflicts.** The agent can materialize input files and inspect them before executing. A conflict between smearing type and occupation scheme, or an incompatible combination of magnetism and SOC settings, is visible in the dry run. No compute time is wasted.

**Elicitation for expensive operations.** Before submitting a large calculation (many atoms, many k-points, many steps), elicitation can interrupt the agent to ask the user for confirmation: "This 128-atom VASP hybrid calculation will take approximately 8 hours on 64 cores. Proceed?"

### Level 1: Structured Diagnostics (Rule-Based + Knowledge-Backed)

When a calculation fails, QMatSuite's output parsers return structured diagnostics — not raw log files.

The existing `OutputParser` classes (15 engines registered via `@register_parser`) already parse convergence status, energy traces, and error conditions. Each returns an engine-specific `*Digest` dataclass:

- **VASP**: `VASPDigest` — `converged_electronic` (SCF iterations vs NELM), `converged_ionic` (ionic steps vs NSW), band gap, forces
- **ORCA**: `ORCADigest` — `success` (normal termination check), `converged_scf`, `converged_geometry`, `error_message` (up to 500 chars)
- **Gaussian**: `GaussianDigest` — 23 fields including `success`, `converged_scf`, `converged_geometry`, `error_message`, MP2 energies, Link1 chain detection
- **LAMMPS**: `LAMMPSDigest` — `success`, `error_message`, `converged_minimize`, "lost atoms" detection

The MCP error return enriches these digest flags with `suggested_fixes`. In Phase 1, these are hardcoded rules. In Phase 2+, they are dynamically queried from the Knowledge Base (Section 7.7):

| Error Pattern | Digest Signal | Suggested Fix (from Knowledge Base) | Confidence |
|---|---|---|---|
| Energy oscillating | `converged_electronic=false`, oscillation in SCF trace | Reduce mixing_beta: 0.7 → 0.3 | High |
| SCF not converging | `n_electronic_steps >= NELM` | Increase electron_maxstep: 100 → 200 | Medium |
| Negative eigenvalue | Detected in output text | Increase ecutwfc by 20% | Medium |
| Out of memory | Exit code + OOM pattern in stderr | Reduce k-grid or use fewer bands | High |
| POSCAR mismatch | Species count mismatch | Verify structure + POTCAR consistency | High |
| Lost atoms (LAMMPS) | `error_message` contains "lost atoms" | Reduce timestep or check potential cutoffs | High |
| Error termination (ORCA) | `success=false`, `error_message` populated | Parse error type, suggest input correction | Medium |

These are deterministic rules, not LLM reasoning. The agent can act on them directly: call `set_parameters` with the suggested parameter change, verify with `inspect_calculation`, and resubmit.

### Level 2: Knowledge-Assisted Recovery

For failures where Level 1 rules are insufficient, the agent draws on accumulated knowledge:

1. **Query knowledge base**: `search_knowledge(query="SCF convergence failure metallic", engine="vasp")` — finds both builtin recovery strategies and community-contributed solutions
2. **Inspect output**: `get_output_raw(calc_ulid, section="convergence", lines=50)` — see the raw convergence trace
3. **Search parameters**: `search_parameters(query="convergence acceleration methods")` — find relevant engine settings
4. **Use sampling**: The MCP server can invoke `sampling/createMessage` to ask the client's LLM for interpretation, keeping the diagnostic reasoning separate from the main agent context

As the Knowledge Base grows (community contributions, literature extraction), Level 2 becomes more powerful without code changes. A convergence pathology that was novel for user A becomes a cataloged finding for user B.

### Level 3: Agent-Driven Recovery

For genuinely novel failures that no rule or knowledge entry covers, the agent uses its own reasoning to form a hypothesis, test it, and (if successful) record the solution as a new knowledge entry:

```
1. Agent encounters novel failure
2. Reads output, searches parameters, queries knowledge (no match)
3. Uses domain reasoning to hypothesize a fix
4. Applies fix via set_parameters → inspect_calculation(dry_run) → run_calculation
5. If fix works: record_insight(grade="finding", content="...", provenance_refs=[...])
6. Future agents with the same failure pattern find this in search_knowledge
```

This closes the learning loop: novel failures become cataloged knowledge through the Provenance → Knowledge distillation pipeline.

**Architecture comparison**: El Agente requires 58 specialized agents for error recovery. DREAMS requires a separate LLM call hardcoded into the tool. QMatSuite provides structured data at Level 1, accumulated knowledge at Level 2, and a learning loop at Level 3 that makes the system smarter with every failure.

---

## 11. Workflow Examples

### 11.1 Scenario A — With Preset: "Si Band Structure with QE" (5 minutes)

**User**: "Calculate the band structure of silicon using QE with standard settings."

**Tool call sequence:**

```
1. list_workflows(engine="qe")
   → [..., {name: "bands", steps: ["qe_scf", "qe_bands"]}]

2. get_presets(engine="qe", workflow="bands")
   → {presets_available: true, dimensions: [{name: "precision", options: [...]}]}

3. preview_compilation(
     engine="qe", workflow="bands",
     structure_ulid="01KC38MB...",
     presets={precision: "med", magnetism: "nonmagnetic"},
     show_input_file=true
   )
   → Steps: [qe_scf (ecutwfc=40, 8x8x8 k-grid), qe_bands (nbnd=12, L-G-X-W-K path)]
   → Agent shows user: "Here's what will run. ecutwfc=40 Ry, k-path L-Γ-X-W-K."
   → User: "Looks good"

4. quick_run(
     engine="qe", workflow="bands",
     structure_ulid="01KC38MB...",
     presets={precision: "med", magnetism: "nonmagnetic"},
     name="Si_bands_standard"
   )
   → {calc_ulid: "01KC3G...", job_id: "01KC3F...", status: "running"}

5. get_status(job_id="01KC3F...")          # Poll after ~2 minutes
   → {status: "completed", wall_time_seconds: 95}

6. get_results_summary(calc_ulid="01KC3G...")
   → {converged: true, total_energy_eV: -310.42, bandgap_eV: 0.67, scf_iterations: 9}
   → Agent: "Calculation complete. Si bandgap = 0.67 eV (PBE). Note: PBE
             underestimates the experimental value of 1.12 eV by ~40%."

7. get_band_structure(calc_ulid="01KC3G...", detail="detailed")
   → Returns k-resolved eigenvalues + MCP App with interactive plot
   → User sees interactive band structure in conversation
```

**Total tool calls: 7. Total agent output tokens: ~500. Total tool input tokens: ~3,000.**

### 11.2 Scenario B — No Preset: "VASP SCF for Silicon" (5 minutes)

**User**: "Run an SCF calculation for silicon using VASP."

**Tool call sequence:**

```
1. list_workflows(engine="vasp")
   → [{name: "scf", steps: ["vasp_scf"], ...}]

2. get_presets(engine="vasp", workflow="scf")
   → {presets_available: false, message: "No presets defined for VASP/scf.
      Use search_parameters to find relevant parameters and set_parameters to configure."}

3. search_parameters(query="cutoff energy VASP", engine="vasp")
   → [{tag: "ENCUT", type: "float", default: "max(ENMAX)", category: "basic",
       description: "Cutoff energy for plane wave basis (eV). Typical: 1.3x ENMAX from POTCAR."}]

4. search_parameters(query="k-points mesh VASP", engine="vasp")
   → [{tag: "KPOINTS", description: "Automatic k-point mesh for Brillouin zone sampling."}]

5. search_parameters(query="convergence threshold VASP", engine="vasp")
   → [{tag: "EDIFF", type: "float", default: 1e-4, description: "Energy convergence criterion (eV)."}]

6. create_calculation(engine="vasp", workflow="scf",
     structure_ulid="01KC38MB...", name="Si_scf_vasp")
   → {calc_ulid: "01KC4A...", steps: [{step_index: 0, step_type: "vasp_scf", ...}]}

7. set_parameters(calc_ulid="01KC4A...", step=0, params={
     INCAR: {ENCUT: 520, EDIFF: 1e-6, ISMEAR: 1, SIGMA: 0.1, LREAL: false},
     KPOINTS: {grid: [8, 8, 8]}
   })
   → {params_set: {...}, validation_warnings: []}

8. inspect_calculation(calc_ulid="01KC4A...", dry_run=true)
   → Agent reviews generated INCAR, POSCAR, KPOINTS files
   → "INCAR looks correct. ENCUT=520, EDIFF=1e-6, Monkhorst-Pack 8x8x8."

9. run_calculation(calc_ulid="01KC4A...")
   → {job_id: "01KC4B...", status: "running"}

10. get_status(job_id="01KC4B...")
    → {status: "completed", wall_time_seconds: 30}

11. get_results_summary(calc_ulid="01KC4A...")
    → {converged: true, total_energy_eV: -10.9423, bandgap_eV: 0.67, scf_iterations: 12}
```

**Total tool calls: 11.** More calls than Scenario A because the agent must discover parameters. This is the expected cost of working without presets — but the agent has full control and visibility.

### 11.3 Scenario C — Preset + Heavy Modification: "QE Bands with Hubbard U"

**User**: "Calculate band structure for FeO with QE. Use standard presets but add Hubbard U correction."

```
1. create_calculation(engine="qe", workflow="bands",
     structure_ulid="01KC...", name="FeO_bands_U")

2. apply_preset(calc_ulid="01KC...", presets={precision: "high", magnetism: "collinear_lsda"})
   → {compiled_parameters: {SYSTEM: {ecutwfc: 50, nspin: 2, ...}}}

3. set_parameters(calc_ulid="01KC...", step=0, params={
     SYSTEM: {lda_plus_u: true, Hubbard_U: {Fe: 5.0}}
   })
   → Preset baseline + manual Hubbard U

4. inspect_calculation(calc_ulid="01KC...", dry_run=true)
   → Agent verifies: "ecutwfc=50 from high-precision preset. nspin=2 from collinear preset.
      Hubbard U=5 eV on Fe from manual setting. Looks correct."

5. run_calculation(calc_ulid="01KC...")
```

### 11.4 Long-Running Job: Fire-and-Forget Pattern

For calculations that take hours (HSE06 hybrid, large supercells, HPC jobs):

**Session 1 (submit):**

```
1. create_calculation(engine="vasp", workflow="bands",
     structure_ulid="...", name="CsPbI3_HSE06_bands")

2. set_parameters(calc_ulid="...", step=0, params={
     INCAR: {LHFCALC: true, GGA: "PE", AEXX: 0.25, ENCUT: 520}})

3. record_intent(calc_ulid="...",
     reason="Running high-precision HSE06 band structure for CsPbI3
             to get accurate bandgap for photovoltaic screening")

4. run_calculation(calc_ulid="...")
   → {job_id: "01KC5A...", status: "queued"}

5. get_status(job_id="01KC5A...")
   → {status: "running", progress: {current_step: "vasp_scf", steps_completed: 0, steps_total: 2}}

Agent: "Your HSE06 calculation is submitted and running. It should complete in
        ~4 hours. Come back and ask me to check on it."
[User closes conversation]
```

**Session 2 (check, hours/days later):**

```
User: "How's my CsPbI3 calculation going?"

1. get_project_history(status="all")
   → Finds the HSE06 calc from provenance, with intent record

2. get_status(job_id="01KC5A...")
   → {status: "completed", wall_time_seconds: 14400}

3. get_results_summary(calc_ulid="...")
   → {converged: true, bandgap_eV: 1.73}

4. record_interpretation(calc_ulid="...",
     interpretation="HSE06 bandgap = 1.73 eV for CsPbI3, in excellent agreement
                     with experimental value of 1.73 eV. Material is suitable
                     for photovoltaic applications.")

Agent: "Your HSE06 calculation completed. Bandgap = 1.73 eV, matching experiment.
        CsPbI3 looks promising for photovoltaic applications."
```

**Key enabler**: Provenance records enough context (intent, parameters, structure) that the agent can fully reconstruct what was happening without any conversation history from Session 1.

**Future optimization**: MCP Notifications could eliminate polling — the server pushes a notification when a job completes. For v1, polling via `get_status` is sufficient.

### 11.5 Scenario D — Research Project: "FeO U-Parameter Scan"

**User**: "Find the optimal Hubbard U for FeO. Scan U from 2 to 6 eV and compare with experiment (2.4 eV bandgap)."

```
1. search_knowledge(query="FeO Hubbard U") → check for past insights
2. search_parameters(query="hubbard U VASP") → find LDAUTYPE, LDAUU syntax

3-7. For U = 2, 3, 4, 5, 6:
     create_calculation(engine="vasp", workflow="scf", ..., name=f"FeO_U{U}")
     set_parameters(calc_ulid, step=0, params={
       INCAR: {LDAU: true, LDAUTYPE: 2, LDAUL: [2,-1], LDAUU: [U, 0],
               ISMEAR: -5, EDIFF: 1e-6}})
     record_intent(calc_ulid, reason=f"Testing U={U} eV for FeO bandgap")
     run_calculation(calc_ulid)

8-12. get_status for each job (polling)

13-17. get_results_summary for each:
     U=2: bandgap=0.8 eV
     U=3: bandgap=1.4 eV
     U=4: bandgap=2.1 eV
     U=5: bandgap=2.5 eV
     U=6: bandgap=3.0 eV

18. compare_calculations(calc_ulids=[...])
    → Side-by-side comparison table

19. record_insight(
      scope="project",
      category="hubbard_U",
      engine="vasp",
      system_type="transition_metal_oxide",
      insight="For FeO with PBE+U (LDAUTYPE=2), U=5 eV gives bandgap closest
               to experiment (2.5 vs 2.4 eV). U=4 slightly underestimates (2.1 eV).",
      evidence=[calc_ulids],
      confidence="high"
    )
```

**Note**: With `submit_batch` (on-demand tool, Phase 2), steps 3-7 could be a single batch call, reducing agent-side orchestration.

---

## 12. MCP Apps: Interactive Visualization

MCP Apps (January 2026) render interactive HTML/JavaScript components in sandboxed iframes within the client UI. Tools return a `_meta.ui.resourceUri` pointing to a `ui://` scheme resource; the client fetches and renders the HTML with bidirectional JSON-RPC communication via `postMessage`.

### Implementation Order

The MCP Apps protocol is very new (January 2026). Implementation follows a complexity gradient:

**Phase 2 — 2D Plotly apps** (simplest, protocol is fresh):
- Convergence Dashboard
- Band Structure Viewer
- DOS Viewer

**Phase 4 — 3D viewers and complex interactive tools** (after protocol matures):
- Structure Viewer (Three.js/NGL)
- Parameter Space Explorer

### Existing Data Pipeline

QMatSuite already has a complete `AnalysisObject → canonical primitive → processed primitive → viz module` pipeline. MCP Apps are just another viz module consuming the same processed primitives (1D/2D/3D arrays + metadata). Implementation cost is low because the data pipeline already exists — only the renderer (HTML/JS in iframe) is new.

### Band Structure Viewer (Phase 2)

**Data from tool**: k-distances array, eigenvalue matrix (n_kpoints x n_bands), high-symmetry point labels and positions, Fermi energy, optional orbital projections (4D array from `BandStructure.projections`).

**Visualization**: Interactive Plotly chart. X-axis: k-distance with labeled high-symmetry points (vertical dashed lines). Y-axis: energy relative to Fermi level. Band lines colored by spin channel (if spin-polarized) or orbital character (if projections available). Hover shows exact k-point and energy. Zoom to inspect band crossings.

### DOS Viewer (Phase 2)

**Data from tool**: Energy array, total DOS, optional PDOS matrix (n_atoms x n_energies x n_orbitals), atom labels (e.g., "Ti_1", "O_1" from POSCAR), orbital labels.

**Visualization**: Interactive stacked area chart. Toggleable decomposition by element and orbital. Energy on x-axis, states/eV on y-axis. Vertical Fermi level line. Spin-up/spin-down for magnetic systems.

### Convergence Dashboard (Phase 2)

**Data from tool**: SCF iteration energies, force norms (for relaxation), stress tensors (for vc-relax), time per iteration.

**Visualization**: Multi-panel chart. Top: energy vs. iteration (log scale for energy difference). Bottom: max force vs. iteration. Horizontal threshold lines for convergence criteria. Color coding: green when converged, red when oscillating.

### Structure Viewer (Phase 4)

**Data from tool**: Atomic positions, species, unit cell, periodic boundary conditions.

**Visualization**: 3D viewer using Three.js or NGL Viewer. Atom spheres colored by element. Unit cell wireframe. Rotation, zoom, pan. Bond display. Supercell toggle.

### Parameter Space Explorer (Phase 4)

**Data from tool**: Parameter scan results (e.g., U-parameter scan from Section 11.5).

**Visualization**: Interactive heatmap or line plot. X-axis: scanned parameter. Y-axis: property of interest (bandgap, energy, force). Experimental reference line if provided. Click to see individual calculation details.

---

## 13. Competitive Differentiation

| Feature | El Agente | ChemGraph | VASPilot | DREAMS | Masgent | **QMatSuite** |
|---|---|---|---|---|---|---|
| **Agent architecture** | 58 custom agents | LangGraph DAG | CrewAI 4-agent | LangGraph 3-agent | pydantic-ai single | **MCP (BYOE)** |
| **LLM lock-in** | Claude Opus 4.5 | GPT-4/Claude/Gemini | GPT-4/Claude | Claude 3.7 Sonnet | 7 providers | **None** |
| **Engine coverage** | ORCA only | 9 (ASE-limited) | VASP only | QE only | VASP + 4 MLP | **15 engines native** |
| **Parameter access** | ~100% (1 engine) | ~25% (ASE) | ~30% (pymatgen) | ~25% (ASE) | ~30% (pymatgen) | **100% (all engines)** |
| **Solid-state workflows** | No | No (ASE ceiling) | Basic | Basic | Basic | **Full (bands/DOS/k-pts)** |
| **No-preset workflow** | N/A (generates text) | ASE calculator | pymatgen template | ASE calculator | pymatgen template | **search_parameters + set_parameters** |
| **Preview before execute** | No | No | No | No | No | **inspect_calculation(dry_run)** |
| **Interactive viz in chat** | No | No | No | No | No | **MCP Apps** |
| **Tool discovery scaling** | Manual 34 tools | Manual | Manual 17 tools | Manual | Manual 30 tools | **Tool Search + defer_loading** |
| **Structured error recovery** | LLM-driven | Anti-loop detection | Agent-driven | Separate LLM call | Schema validation | **3-level (prevent/diagnose/recover)** |
| **Long-term memory** | MongoDB episodic | In-memory only | SQLite + ChromaDB | Pickle state | None | **4-layer (context/SSOT/provenance/knowledge)** |
| **Multi-engine workflows** | No | No | No | No | No | **Yes (QE→W90→Yambo, etc.)** |
| **Tests** | Unknown | ~20% coverage | 2 files | 0 tests | 0 tests | **5,000+ tests, gate CI** |
| **API key management** | User provides to El Agente | User provides | User provides | Hardcoded | User provides | **User's own CLI (BYOE)** |
| **Open source** | Proprietary | Apache 2.0 | LGPL | Open | MIT | **Open** |

**The critical differentiators are structural, not incremental:**

1. **BYOE** — No framework lock-in. Works with any MCP-compatible agent today and tomorrow. Competitors must rewrite when LLM providers change APIs.

2. **15 engines at 100% parameter access** — ChemGraph is architecturally limited by ASE (no reciprocal space). VASPilot/Masgent are limited to pymatgen templates (~30% of VASP's parameters). El Agente has 100% access but only for ORCA. QMatSuite has native parsers/writers with full parameter documentation for all 15 engines.

3. **First-class no-preset workflow** — 14 of 15 engines have no presets today. QMatSuite's `search_parameters` + `set_parameters` + `inspect_calculation(dry_run)` flow gives agents full parameter access with full visibility, even without presets. No competitor has this.

4. **Mathematical reversibility** — The preset compiler/detector guarantee `detect(compile(options)) == options`. No other system has formally reversible presets. This enables the agent to understand *why* parameters have their values.

---

## 14. Security and Trust

**No API keys pass through QMatSuite.** BYOE means the agent connects directly to its LLM provider via the user's own CLI. QMatSuite never sees API keys, never proxies LLM calls, never stores credentials. This eliminates an entire attack surface that every competitor has.

**Elicitation for dangerous operations.** The MCP elicitation primitive is used before:
- Submitting calculations expected to consume >1 hour of compute
- Deleting calculations or projects
- Overwriting existing results
- Modifying structures in-place

The agent cannot unilaterally approve expensive operations. The human reviews and confirms.

**Audit trail.** Every tool call is logged with timestamp, input parameters, and result summary in the project's journal (`QVService.History`). The provenance system tracks the full lineage of every calculation. An agent-submitted calculation has the same auditability as a GUI-submitted one.

**Sandboxed MCP Apps.** Interactive visualizations run in iframe sandboxes with no access to the host page, no network access, and no filesystem access. Data is passed via `postMessage` JSON-RPC. A malicious visualization cannot exfiltrate data or modify state.

**Input validation.** All tool inputs are validated against JSON Schema before execution. The schema validation layer (`api/errors.py:ValidationError`) catches malformed parameters before they reach the kernel. Engine-specific validation (e.g., `vasp_metadata.validate_incar_params()`) catches semantically invalid parameters.

**Writer-only input generation.** The agent cannot bypass QMatSuite's writers to produce input files directly (Section 9). This ensures all parameters flow through validation and provenance tracking.

**Rate limiting.** Configurable limits on tool calls per minute/hour prevent runaway agents from consuming excessive resources. Default: 60 calls/minute for discovery tools, 10 calls/minute for execution tools.

---

## 15. Deployment Architecture

### 15.1 Local (Default)

The default deployment runs the MCP server locally via stdio transport. Zero network exposure, zero configuration, zero latency.

```json
{
  "mcpServers": {
    "qmatsuite": {
      "command": "python",
      "args": ["-m", "quantumvitas.mcp.server"],
      "env": {
        "QMATSUITE_PROJECT": "/path/to/project"
      }
    }
  }
}
```

This is identical to how the existing GUI daemon works: the Electron app spawns a Python subprocess communicating over stdin/stdout JSON-RPC (`daemon/server.py`). The MCP server reuses the same `QVService` layer, replacing the daemon's custom JSON-RPC protocol with the standard MCP protocol.

**Calculations run on the local machine.** The existing `JobManager` (`daemon/jobs.py`) manages background execution via `ThreadPoolExecutor`. The MCP server exposes this through `run_calculation` (non-blocking submit) and `get_status` (polling).

### 15.2 Remote (Future)

For HPC deployment, the MCP server runs via Streamable HTTP transport:

```
User's laptop                          HPC login node
+-------------------+                  +----------------------------+
| Claude Code /     |  HTTPS           | QMatSuite MCP Server       |
| Codex CLI /       |  ===============>| (Streamable HTTP)          |
| Gemini CLI        |  Mcp-Session-Id  |                            |
+-------------------+                  | QVService → SLURM sbatch  |
                                       +----------------------------+
```

**Streamable HTTP** (MCP spec 2025-03-26) uses a single `/mcp` endpoint. Clients send JSON-RPC via HTTP POST; the server responds with standard JSON for quick operations or SSE streams for long-running tasks. Session management uses `Mcp-Session-Id` headers.

**Authentication**: OAuth 2.0 via MCP's authorization framework. Institutional identity providers (Shibboleth, CILogon) can integrate via standard OIDC.

**SLURM integration**: Following Argonne's Pattern A (direct shell-out), the MCP server wraps SLURM commands (`sbatch`, `squeue`, `scancel`, `sacct`) for job management. The `run_calculation` tool generates the SLURM script, submits via `sbatch`, and returns the job ID.

### 15.3 Notifications (Future Optimization)

MCP Notifications can eliminate polling for long-running jobs. Instead of the agent repeatedly calling `get_status`, the server pushes a notification when job status changes:

```
Server → Client: notification("job_completed", {job_id: "01KC3F...", status: "completed"})
```

For v1, polling via `get_status` is sufficient and simpler to implement. Notifications are a Phase 4 optimization that improves UX for HPC workloads where calculations run for hours.

---

## 16. Testing Strategy

### Contract Tests

Every MCP tool has a contract test verifying:
- **Input schema validation**: Malformed inputs are rejected with structured errors
- **Output schema conformance**: Successful returns match the declared `outputSchema`
- **Error handling**: Known failure modes return structured diagnostics, not stack traces
- **Idempotency**: Discovery/preview tools return identical results on repeated calls

These extend the existing contract crawler infrastructure (`tests/contract_crawler/`) which already achieves 95.7% RPC coverage (111/116 methods).

### Integration Tests

Tool calls that exercise actual QMatSuite core with mock engines:
- `create_calculation` + `set_parameters` + `inspect_calculation(dry_run=true)` end-to-end
- `preview_compilation` with real preset compiler and PrecisionAdvisor
- `run_calculation` with mock engine handlers (no actual VASP/QE execution)
- Error recovery flow: run → fail → diagnose → fix via set_parameters → inspect → rerun
- Knowledge base CRUD: record → search → update → search
- Batch submission: `submit_batch` with 5 independent calculations

### Real-Run Smoke Tests

End-to-end with actual engine executions (extending existing `tests/integration/`):
- Si SCF with QE (existing: already runs in CI)
- Si bands with QE (existing: already has golden reference)
- VASP SCF (existing: runs with real VASP binary)
- Full Scenario A workflow: `list_engines` → `list_workflows` → `get_presets` → `preview_compilation` → `quick_run` → `get_status` → `get_results_summary` → `get_band_structure`
- Full Scenario B workflow: `list_workflows` → `get_presets` (no presets) → `search_parameters` → `create_calculation` → `set_parameters` → `inspect_calculation(dry_run)` → `run_calculation` → `get_results_summary`

### Agent Simulation Tests

Scripted tool call sequences mimicking realistic agent behavior:
- Scenario A (with preset) workflow as automated test
- Scenario B (no preset) workflow as automated test
- Scenario D (U-parameter scan) with mock calculations
- Error recovery scenario: inject SCF failure, verify structured diagnostics, verify fix suggestion works
- Cross-session scenario: submit in Session 1 → check in Session 2 via provenance

### Context Budget Tests

Measure total tokens consumed by typical workflows:
- Count tokens in tool definitions (~13 always-loaded: ~3,500-4,000 tokens)
- Count tokens in tool returns (summary vs. detailed tier)
- Verify typical 10-calculation workflow stays under 50K total tool tokens
- Compare with/without progressive disclosure

---

## 17. Implementation Roadmap

### Phase 1: RUN — "Agent can complete a real calculation end-to-end"

**User story**: Researcher says "Calculate Si band structure with QE" → agent discovers capabilities → configures → runs → returns results.

**Milestone demo**: Si SCF with QE, end-to-end. User says one sentence, gets energy + convergence status back.

**Tools implemented**:
- Always-loaded: `list_engines`, `list_workflows`, `get_presets`, `create_calculation`, `set_parameters`, `apply_preset`, `preview_compilation`, `inspect_calculation` (with dry_run), `run_calculation`, `quick_run`, `get_status`, `get_results_summary`, `search_parameters`
- On-demand: `list_structures`

**Infrastructure**:
- FastMCP server at `src/quantumvitas/mcp/server.py`
- stdio transport (reusing patterns from `daemon/server.py`)
- `.mcp.json` configuration for Claude Code
- Standard return envelope with `context_hint`
- BM25 index over `*_tags.json` files at server startup
- Contract tests for all tools

**Core milestone**: The "wow" moment. Agent can do a simple calculation that would take a new user 30 minutes to set up manually.

### Phase 2: RECOVER — "Agent can handle errors and do real research"

**User story**: Agent submits a calculation that fails SCF convergence → gets structured diagnostics → applies fix via `set_parameters` → inspects with dry_run → resubmits → succeeds. Also: agent does parameter scans (U-parameter, convergence testing).

**Milestone demo**: FeO U-parameter scan. Agent submits 5 calculations, compares bandgaps, identifies optimal U.

**Tools added**:
- `submit_batch`, `get_batch_status` (batch parameter scans)
- `compare_calculations` (multi-calc comparison)
- `record_intent`, `record_interpretation` (provenance journaling)
- Structured error diagnostics with `suggested_fixes` in error returns
- Detailed analysis: `get_band_structure`, `get_dos`, `get_convergence_history`, `get_output_raw`

**MCP Apps** (2D Plotly — simplest to implement):
- Convergence dashboard
- Band structure viewer
- DOS viewer

**Core milestone**: Agent handles failure gracefully. Agent can do multi-calculation research. Results are visualized interactively.

### Phase 3: LEARN — "Agent remembers and builds expertise"

**User story**: Agent starts a new project involving a metallic system → queries knowledge base → finds that Methfessel-Paxton smearing works best for metals (learned from previous project) → applies this knowledge automatically.

**Milestone demo**: Multi-session perovskite study. Session 1: screening. Session 2 (days later): agent recovers full context from provenance, continues detailed calculations.

**Tools added**:
- `get_project_history`, `get_provenance`, `annotate_calculation` (provenance access)
- `search_knowledge`, `record_insight`, `update_insight` (knowledge base)
- `fetch_structure`, `import_structure` (structure sourcing)
- `diff_presets`, `get_parameter_detail` (parameter tuning)
- Knowledge base SQLite + FTS5 implementation at `~/.qmatsuite/knowledge.db`
- Full provenance interaction protocol
- `defer_loading` and Tool Search compatibility for the complete tool catalog

**Core milestone**: Agent doesn't start from scratch. Accumulated wisdom persists across sessions and projects.

### Phase 4: MASTER — "Agent operates QMatSuite with full fluency"

**User story**: Agent operates remotely on HPC, manages complex multi-engine workflows, generates publication-quality visualizations, helps write methods sections.

**Tools added**:
- 3D Structure Viewer (Three.js/NGL MCP App)
- Parameter Space Explorer (interactive MCP App)

**Infrastructure**:
- Streamable HTTP transport for remote deployment
- OAuth 2.0 authentication
- SLURM integration for HPC job submission
- Full MCP Notifications support (push instead of poll)
- Security hardening, rate limiting
- Comprehensive documentation, tutorials
- Paper: "QMatSuite: A Cognitive Architecture for AI-Driven Computational Materials Research"

**Core milestone**: Production-ready. Agent is a fully capable research assistant.
