# QMatSuite Agent Integration Design

**Status**: Design Document (Pre-Implementation)
**Date**: 2026-02-17
**Scope**: MCP server architecture for AI agent integration across 15 computational engines

---

## 1. Executive Summary

QMatSuite is becoming the first AI-native computational materials science platform. Rather than building yet another AI orchestration framework, we expose QMatSuite's 15-engine simulation infrastructure as a Model Context Protocol (MCP) server. Any AI agent — Claude Code, GPT Codex CLI, Gemini CLI, or future systems — connects to QMatSuite through the standard MCP protocol and gains immediate access to the full power of density functional theory, quantum chemistry, and classical molecular dynamics.

**The BYOE paradigm shift.** Every competitor (El Agente, ChemGraph, VASPilot, DREAMS, Masgent) bundles a specific LLM framework (LangGraph, CrewAI, pydantic-ai) and locks users into a particular agent architecture. QMatSuite inverts this: we build exceptional tools, and users Bring Your Own Engine. The agent is already intelligent; QMatSuite gives it hands, eyes, and a lab notebook.

**Three-sentence value proposition:**

*For researchers:* Run any calculation on any of 15 engines through natural language — preview every parameter before execution, get structured diagnostics when things fail, and build a searchable knowledge base of what works.

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

External actions decompose into four categories that map to MCP tool groups:

| Action | Scientific Equivalent | MCP Tool Category |
|---|---|---|
| Observe | Survey the lab, check what's available | Discovery tools (`list_engines`, `list_workflows`, `get_presets`) |
| Plan | Design an experiment | Preview tools (`preview_compilation`, `diff_presets`) |
| Execute | Run the experiment | Execution tools (`submit_calculation`, `get_status`) |
| Analyze | Read the results | Analysis tools (`get_results_summary`, `get_band_structure`) |

### 2.3 The Scientific Method as Agent Workflow

The scientific method is not a rigid sequence but a recursive loop: hypothesize, experiment, observe, reflect. This maps directly to agent workflow design:

**Hypothesis formation** maps to plan formulation. The agent, informed by the user's research question and its accumulated knowledge, decides what calculation to run. "This is a metallic system, so I should use Methfessel-Paxton smearing. Let me preview the compilation to verify."

**Experimental execution** maps to tool invocation. The agent calls `submit_calculation` and monitors via `get_status`. The calculation runs on the user's infrastructure (local machine, HPC cluster) — QMatSuite manages the execution, not the agent.

**Observation** maps to result analysis. The agent calls `get_results_summary` for a token-efficient overview, then drills into specifics with `get_band_structure` or `get_dos`. Structured returns mean the agent can reason numerically: "The bandgap is 0.67 eV, which is below the experimental value of 1.12 eV. This is the well-known DFT underestimation."

**Reflection** maps to strategy update. The agent records insights via `record_insight`: "PBE underestimates Si bandgap by ~40%. Use HSE06 for accurate gap values." This persists across sessions, building a personal computational expertise database.

### 2.4 Context Engineering as Cognitive Resource Management

Anthropic's context engineering framework treats the context window as an attention budget. Every token competes for the transformer's n-squared pairwise computation. Manus's 100:1 input-to-output ratio — 50 tool calls per task with ruthless output filtering — demonstrates that token efficiency is not optimization but architecture.

QMatSuite cooperates with context management through three mechanisms:

**Progressive disclosure.** Every tool returns a minimal summary by default. The agent requests more detail only when needed. A `get_results_summary` call returns ~200 tokens (energy, bandgap, forces, convergence status, wall time). A `get_band_structure` call returns ~1,000 tokens (k-resolved eigenvalues). The agent never pays for data it doesn't use.

**Context hints.** Every tool return includes a `context_hint` field that guides the agent's next step without trial-and-error. After `submit_calculation`, the hint says "Call get_status(job_id='...') to check progress." After a failed SCF, the hint says "Use preview_compilation with the suggested fix to see updated parameters before resubmitting." This is not prompt engineering — it is structured metadata that reduces wasted tool calls.

**Filesystem as externalized memory.** Following Manus's principle, QMatSuite's SSOT files (`calculation.yaml`, `step.yaml`) serve as externalized agent memory. The agent can always re-read the current state from disk rather than maintaining it in context. The `get_project_history` tool queries the provenance database rather than relying on conversation history. This means context compaction (Claude Code's conversation summarization) loses no critical state.

### 2.5 Why This Framing Matters

The "intelligent researcher" model is not marketing. It has three concrete engineering consequences:

First, it determines tool granularity. Tools match the actions a researcher would take, not the internal API structure of QMatSuite. A researcher does not "call `QVService.Calculation.update_step_params` with a nested dict of SYSTEM parameters." A researcher "previews a standard-precision Si band structure calculation and adjusts the k-point density."

Second, it determines error handling strategy. A researcher encountering a failed SCF does not need a stack trace. They need a diagnosis: "Energy oscillating, likely charge sloshing. Try reducing mixing_beta from 0.7 to 0.3." QMatSuite's error returns are structured diagnostics with actionable suggestions, not exception dumps.

Third, it determines the memory architecture. A researcher's expertise grows over time. QMatSuite's knowledge base (`search_knowledge`, `record_insight`) makes this growth explicit and queryable. After 100 calculations, the agent doesn't start from scratch — it starts with accumulated wisdom about which functionals work for which systems, which convergence strategies resolve which failures, and which approximations are appropriate for which properties.

---

## 3. Architecture Overview

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
|  |Discovery|Execution |Analysis  |Structure         ||
|  |Tools    |Tools     |Tools     |Tools             ||
|  +--------+----------+-----------+------------------+|
|  |          QVService (existing API layer)           ||
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

### Layer Mapping to Code

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

---

## 4. MCP Primitives Mapping

| MCP Primitive | QMatSuite Usage | Why This Primitive | Concrete Example |
|---|---|---|---|
| **Tools** | Actions that modify state or produce computed results | Tools are LLM-controlled — the agent decides when to call them. Calculations, analysis, and knowledge recording are agent-driven decisions. | `submit_calculation({engine: "vasp", workflow: "bands", preset: "standard", structure_ulid: "01KC..."})` |
| **Resources** | Read-only reference data that the client loads into context | Resources are application-controlled — the client decides what the agent sees. Engine parameter schemas and preset definitions are reference material, not actions. | `qmatsuite://engines/vasp/parameters` returns JSON Schema for all 232 VASP INCAR tags |
| **Elicitation** | Human-in-the-loop confirmation for irreversible operations | Elicitation interrupts the agent to ask the user. Submitting expensive HPC jobs or deleting data requires human confirmation — the agent should not auto-approve. | Pre-submission review: "About to submit 128-atom VASP relaxation on 64 cores. Estimated wall time: 4 hours. Proceed?" |
| **Sampling** | Server-side LLM reasoning for complex interpretation | Sampling lets the server ask the client's LLM for help. Diagnosing complex convergence failures or interpreting ambiguous output sections benefits from LLM reasoning without polluting the main agent context. | Error diagnosis: server sends last 50 SCF iterations to client LLM with "Why did this oscillate?" prompt |
| **Tool Output Schema** | Machine-readable structured results | Output schemas let downstream tools programmatically consume results. Energy values, convergence status, and bandgap measurements must be machine-parseable, not buried in text. | `get_results_summary` output schema: `{total_energy_eV: number, bandgap_eV: number | null, converged: boolean, ...}` |
| **MCP Apps** | Interactive visualization in the conversation | MCP Apps render sandboxed HTML/JS in the client UI. Band structure plots with zoom/hover, 3D structure viewers with rotation, and convergence dashboards belong in interactive widgets, not ASCII art. | `get_band_structure` returns data + `_meta.ui.resourceUri` pointing to interactive Plotly band plot |
| **Tasks** | Long-running async operations | Tasks represent operations spanning minutes to hours. HPC calculations run asynchronously; the agent polls for completion rather than blocking. | `submit_calculation` returns a Task ID. Agent polls via `get_status(task_id)`. Server sends progress notifications. |

### Resources vs. Tools: The Decision Heuristic

The MCP spec distinguishes resources (read-only, application-controlled) from tools (actions, LLM-controlled). For QMatSuite:

**Resources** expose static reference data that the client can pre-load:
- `qmatsuite://engines` — List of 15 engines with capabilities
- `qmatsuite://engines/{engine}/parameters` — Full JSON Schema for engine parameters
- `qmatsuite://presets/{engine}/{workflow}` — Preset definitions with compiled defaults
- `qmatsuite://knowledge` — Accumulated research insights (if knowledge base exists)

**Tools** expose actions that the agent decides to take:
- Everything that creates, modifies, or computes is a tool
- The agent autonomously decides when to preview, submit, analyze, or record

The rule: if the agent must reason about *whether* to invoke it, it is a tool. If the application should just make it available as context, it is a resource.

---

## 5. Tool Design: The Complete Tool Catalog

### 5.1 Design Principles

Six principles govern every tool in the catalog. Each is grounded in a concrete engineering lesson.

**1. Progressive Disclosure.** Discovery, Preview, Execute, Analyze. The agent never needs all tools at once. Discovery tools are always loaded; detailed analysis tools are deferred. This mirrors how a researcher first surveys their equipment, then designs an experiment, then runs it, then analyzes results. Engineering basis: Tool Search with `defer_loading` reduces initial context by ~85% (Anthropic benchmark).

**2. Token Efficiency.** Every return is minimal by default. Summary tier: ~200 tokens. Detailed tier: ~500-2,000 tokens. Raw tier: paginated, unbounded. The agent requests more detail with explicit parameters. Engineering basis: Manus operates at 100:1 input-to-output ratio. Context rot research (Chroma 2025) shows models perform ~30% worse with full history vs. focused history.

**3. Structured + Human-Readable Dual Returns.** Every tool returns both `structuredContent` (for the agent to reason about programmatically) and `content` (for the user to read in the conversation). The structured content conforms to a declared `outputSchema`. Engineering basis: MCP spec 2025-06-18 introduced output schemas for exactly this purpose.

**4. Self-Describing.** Tool input schemas include defaults, constraints, enums, and `description` fields. Tools with complex inputs include `input_examples`. The agent can discover correct usage from the schema alone, without external documentation. Engineering basis: Input examples improve parameter accuracy by 18%+ (Anthropic benchmark).

**5. Idempotent Discovery.** Discovery and preview tools have zero side effects. Calling `preview_compilation` 10 times produces identical results and modifies nothing. The agent can explore freely without risk. Engineering basis: Idempotent reads enable aggressive caching and fearless exploration.

**6. Error as Data.** Failures return structured diagnostics with error type, severity, affected parameters, and suggested fixes with confidence levels. Never raw stack traces. The agent can act on suggestions without LLM parsing of error text. Engineering basis: El Agente's primary innovation is structured error recovery. QMatSuite achieves this at the protocol level rather than requiring 58 agents.

### 5.2 Always-Loaded Tools (defer_loading: false)

These ~9 tools are always present in the agent's context. They form the agent's "dashboard" — the core loop of discover, preview, execute, analyze.

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
  "context_hint": "Use get_presets(engine='vasp', workflow='bands') to see available quality presets."
}
```

---

#### `get_presets`

**Description**: List available presets (quality levels) for an engine+workflow combination, with brief descriptions of what each preset configures.

**Maps to**: `QVService.Calculation.get_preset_catalog(engine, workflow)` via `presets/spaces_registry.py` dimension enumeration and `presets/compiler.py` preview

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
    }
  }
}
```

**Example Output**:
```json
{
  "engine": "qe",
  "workflow": "bands",
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
        {"value": "nonmagnetic", "label": "Non-magnetic", "description": "nspin=1, no spin polarization"},
        {"value": "collinear_lsda", "label": "Collinear (LSDA)", "description": "nspin=2, collinear spin polarization"},
        {"value": "noncollinear", "label": "Non-collinear", "description": "noncolin=.true."},
        {"value": "noncollinear_soc", "label": "Non-collinear + SOC", "description": "noncolin=.true., lspinorb=.true."}
      ],
      "default": "nonmagnetic"
    }
  ],
  "context_hint": "Use preview_compilation to see the full parameter set for a specific preset combination."
}
```

---

#### `preview_compilation`

**Description**: Preview the complete compiled parameters and generated input file(s) for a calculation WITHOUT executing. Shows exactly what will be submitted, allowing inspection and modification before committing.

This is QMatSuite's single most important tool. No competitor offers it. El Agente generates ORCA input files via LLM and discovers errors after submission. ChemGraph uses ASE calculator parameters with no preview. VASPilot delegates to pymatgen templates with no visibility. QMatSuite's preset compiler produces deterministic, inspectable output that the agent and user can review token by token before spending compute time.

**Maps to**: `presets/compiler.py:compile_presets()` + `presets/precision_context.py:PrecisionAdvisor.recommend()` + `inputformat/writer.py:write_engine_inputs()` (to temp dir, discarded after preview)

**How it works**: The preset system guarantees mathematical reversibility: `detect(compile(options)) == options`. The `preview_compilation` tool exercises the forward direction — it takes high-level intent (engine + workflow + preset dimensions + optional overrides) and produces the complete, engine-specific parameter set. The agent sees every parameter that will appear in the input file, with the provenance of each value (from preset, from structure analysis, from user override, from engine default).

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
      "description": "Manual parameter overrides applied after preset compilation (e.g., {SYSTEM: {ecutwfc: 80}})",
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

**Example — Si band structure with standard preset**:

Input:
```json
{
  "engine": "qe",
  "workflow": "bands",
  "structure_ulid": "01KC38MBGSS8MX3Z4ETZMXZZY4",
  "presets": {"precision": "med", "magnetism": "nonmagnetic"},
  "show_input_file": true
}
```

Output:
```json
{
  "engine": "qe",
  "workflow": "bands",
  "steps": [
    {
      "step_type": "qe_scf",
      "parameters": {
        "CONTROL": {"calculation": "scf", "pseudo_dir": "./pseudo/"},
        "SYSTEM": {"ecutwfc": 40.0, "ecutrho": 320.0, "nspin": 1, "occupations": "smearing", "smearing": "gaussian", "degauss": 0.02},
        "ELECTRONS": {"conv_thr": 1e-8, "mixing_beta": 0.7}
      },
      "parameter_provenance": {
        "SYSTEM.ecutwfc": "precision_advisor(PP_min=30, factor=1.33)",
        "SYSTEM.nspin": "preset(magnetism=nonmagnetic)",
        "SYSTEM.occupations": "preset(occupations=smearing_gaussian)",
        "ELECTRONS.conv_thr": "preset(precision=med)"
      }
    },
    {
      "step_type": "qe_bands",
      "parameters": {
        "CONTROL": {"calculation": "bands"},
        "SYSTEM": {"ecutwfc": 40.0, "nbnd": 12}
      },
      "parameter_provenance": {
        "SYSTEM.nbnd": "structure(n_electrons=8, +4 empty)"
      }
    }
  ],
  "input_files": [
    {
      "filename": "scf.in",
      "content": "&CONTROL\n  calculation = 'scf'\n  pseudo_dir = './pseudo/'\n/\n&SYSTEM\n  ecutwfc = 40.0\n  ..."
    }
  ],
  "warnings": [],
  "context_hint": "To modify parameters, add overrides (e.g., overrides={SYSTEM: {ecutwfc: 60}}). To submit, call submit_calculation with these parameters."
}
```

**The preview flow in practice:**

1. Agent says "Si band structure with standard preset" → calls `preview_compilation`
2. Agent sees ecutwfc=40.0 Ry from PrecisionAdvisor, k-path L-G-X-W-K from structure symmetry
3. Agent can say "increase ecutwfc to 60" → calls `preview_compilation` with `overrides: {SYSTEM: {ecutwfc: 60}}`
4. Preview updates → user reviews in conversation → agent calls `submit_calculation`
5. Zero wasted compute. Every parameter visible before execution.

---

#### `submit_calculation`

**Description**: Submit a prepared calculation for execution. Returns a job ID for status tracking.

**Maps to**: `QVService.Run.run_calculation()` via daemon `JobManager.submit()`

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
      "additionalProperties": { "type": "string" }
    },
    "overrides": {
      "type": "object",
      "additionalProperties": {}
    },
    "name": {
      "type": "string",
      "description": "Human-readable name for this calculation"
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
    "job_id": { "type": "string", "description": "Job ID from submit_calculation" }
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

#### `search_parameters`

**Description**: Search engine parameter documentation using BM25-ranked keyword search. Searches across all engine tag JSON files (VASP: 232 tags, ABINIT: 170+ tags, CP2K: 215 tags, LAMMPS: 114 commands, ORCA: 120+ keywords, Gaussian: 130 keywords, QMCPACK: 65 tags).

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

---

#### `get_project_history`

**Description**: Query past calculations in the current project. The agent's "lab notebook" — returns a timeline of what was run, with what parameters, and what results.

**Maps to**: `QVService.History.get_project_timeline()` via `.provenance/` SQLite database

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "engine": {
      "type": "string",
      "description": "Optional: filter by engine"
    },
    "workflow": {
      "type": "string",
      "description": "Optional: filter by workflow type"
    },
    "status": {
      "type": "string",
      "enum": ["completed", "failed", "all"],
      "default": "all"
    },
    "limit": {
      "type": "integer",
      "default": 20
    }
  }
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "entries": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "calc_ulid": { "type": "string" },
          "name": { "type": "string" },
          "engine": { "type": "string" },
          "workflow": { "type": "string" },
          "status": { "type": "string" },
          "total_energy_eV": { "type": ["number", "null"] },
          "created_at": { "type": "string" },
          "wall_time_seconds": { "type": ["number", "null"] }
        }
      }
    },
    "total": { "type": "integer" }
  }
}
```

---

#### `list_structures`

**Description**: List available crystal structures in the current project.

**Maps to**: `QVService.Structure.list()`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Optional: filter by formula or name"
    }
  }
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "structures": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "structure_ulid": { "type": "string" },
          "name": { "type": "string" },
          "formula": { "type": "string" },
          "num_atoms": { "type": "integer" },
          "space_group": { "type": "string" },
          "cell_volume_ang3": { "type": "number" }
        }
      }
    }
  }
}
```

### 5.3 On-Demand Tools (defer_loading: true)

These tools are discovered via Tool Search when needed. They are organized by category.

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
| `fetch_structure` | Fetch structure from Materials Project, AFLOW, COD, or OPTIMADE | `QVService.OnlineSearch.search()` + `import_online_candidate()` |
| `import_structure` | Import structure from local file (CIF, POSCAR, XYZ, etc.) | `QVService.Structure.import_file()` |
| `get_structure_detail` | Full crystallographic data with visualization | `QVService.Structure.get()` + `get_structure_vis()` |

#### Parameter Tuning Tools

| Tool | Description | Maps To |
|---|---|---|
| `diff_presets` | Show parameter differences between two preset levels | `presets/compiler.py:compile_presets()` diff |
| `get_parameter_detail` | Full documentation for a specific engine parameter | `*_metadata.py:get_tag_info()` |

#### Project Management Tools

| Tool | Description | Maps To |
|---|---|---|
| `get_provenance` | Full lineage of a calculation (what led to it) | `QVService.History.get_run_revision()` |
| `annotate_calculation` | Add researcher notes to a calculation | Journal entry creation |

### 5.4 Tool Return Format Standard

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
  "context_hint": "Use preview_compilation with overrides={ELECTRONS: {mixing_beta: 0.3}} to see updated parameters before resubmitting."
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
| `list_workflows` | "Use get_presets(engine='...', workflow='...') for quality presets" |
| `get_presets` | "Use preview_compilation to see full parameters before submitting" |
| `preview_compilation` | "To submit, call submit_calculation. To modify, add overrides." |
| `submit_calculation` | "Call get_status(job_id='...') to check progress" |
| `get_status` (completed) | "Call get_results_summary(calc_ulid='...') for results" |
| `get_results_summary` | "For band structure: get_band_structure(...). For DOS: get_dos(...)" |
| Error return | "Use preview_compilation with the suggested fix to verify before resubmitting" |

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
| Current calculation state | `calculation.yaml` | `get_status`, `get_results_summary` |
| Detailed step parameters | `step.yaml` (under `raw/`) | `preview_compilation`, parameter inspection |
| Run history across calculations | `.provenance/` SQLite | `get_project_history` |
| Accumulated insights | `.qmatsuite/knowledge.yaml` (new) | `search_knowledge`, `record_insight` |

This means context compaction (Claude Code's conversation summarization when approaching context limits) loses no critical state. The agent can always re-query the filesystem for current state. The conversation history is for reasoning traces; the SSOT files are for ground truth.

---

## 7. Memory Architecture: Three Timescales

### 7.1 Working Memory (Within a Conversation)

The agent's context window, managed by the client (Claude Code's compaction, Gemini's 1M window, etc.). QMatSuite cooperates by:

- Returning token-efficient summaries by default (Section 6.1)
- Including `context_hint` fields that guide attention (Section 6.2)
- Using stable tool definitions for KV-cache efficiency (Section 6.3)
- Never requiring the agent to maintain state that could be re-queried from SSOT

The working memory contract: **QMatSuite never assumes the agent remembers a previous tool return.** Every tool return is self-contained. If the agent needs the energy from a previous calculation, it calls `get_results_summary` again rather than relying on conversation history.

### 7.2 Session Memory (Within a Project)

The project's provenance database stores calculation history, parameters, results, and lineage. This is episodic memory — the agent's record of what it has done and what happened.

**Tools for session memory:**
- `get_project_history(engine, workflow, status, limit)` — "What calculations have I run?"
- `get_provenance(calc_ulid)` — "What led to this calculation?"
- `compare_calculations(calc_ulids)` — "How do these results differ?"
- `annotate_calculation(calc_ulid, notes)` — "Record that PBE underestimates this bandgap"

**Storage**: Existing `.provenance/` directory with SQLite + CAS (content-addressable store). Run history, step digests, and journal entries are already persisted. Annotations extend the journal with agent-authored entries.

**Session memory enables multi-calculation reasoning.** The agent can query "show me all VASP relaxations that failed" and diagnose patterns across runs, rather than treating each calculation as an isolated event.

### 7.3 Long-Term Memory (Across Projects)

This is the most novel component — a knowledge base that accumulates computational insights across projects and sessions. Inspired by A-MEM's Zettelkasten principles (interconnected notes that grow organically) and ACE's evolving playbook (strategies that improve through experience).

**Storage**: `~/.qmatsuite/knowledge.db` (SQLite, user-global, not project-specific)

**Schema**:
```sql
CREATE TABLE insights (
    id TEXT PRIMARY KEY,           -- k_001, k_002, ...
    category TEXT NOT NULL,        -- convergence_strategy, functional_choice, etc.
    engine TEXT,                   -- 'vasp', 'qe', or NULL for engine-agnostic
    system_type TEXT,              -- 'metallic', 'semiconductor', 'molecular', etc.
    insight TEXT NOT NULL,         -- Natural language description
    evidence TEXT,                 -- JSON array of calc_ulids
    confidence TEXT DEFAULT 'medium', -- 'low', 'medium', 'high'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE insights_fts USING fts5(
    category, engine, system_type, insight,
    content='insights', content_rowid='rowid'
);
```

**Tools for long-term memory:**

`search_knowledge(query, engine?, category?)` — Full-text search over accumulated insights. Returns relevant strategies and their evidence basis.

`record_insight(category, insight, evidence, engine?, system_type?, confidence?)` — Record a new insight with provenance links. The agent calls this when it discovers something worth remembering: "For metallic Fe with VASP, SIGMA=0.1 with ISMEAR=1 (Methfessel-Paxton) converges in 15 iterations vs. 45 with Gaussian smearing."

**How this works in practice:** After running 20 calculations across three projects, the agent has accumulated insights like:

```yaml
- id: k_012
  category: convergence_strategy
  engine: vasp
  system_type: metallic
  insight: "Methfessel-Paxton smearing (ISMEAR=1, SIGMA=0.1) converges 3x faster than Gaussian for metals"
  evidence: ["01KC38...", "01KC39...", "01KC3A..."]
  confidence: high

- id: k_015
  category: functional_accuracy
  engine: qe
  system_type: semiconductor
  insight: "PBE underestimates Si bandgap by ~40% (0.67 vs 1.12 eV). Use HSE06 for gap-critical applications."
  evidence: ["01KC3B...", "01KC3C..."]
  confidence: high
```

When the agent starts a new project involving a metallic system, `search_knowledge(query="metallic convergence")` returns these insights, and the agent applies accumulated wisdom without rediscovering it.

**The analogy to researcher expertise is precise.** A postdoc with 5 years of VASP experience "just knows" that metals need Methfessel-Paxton smearing. This knowledge was built through dozens of convergence failures and successes. QMatSuite's knowledge base makes this accumulation explicit, queryable, and shareable.

---

## 8. Error Recovery Architecture

### Level 0: Prevention (Schema Validation)

The first line of defense prevents malformed requests from reaching the kernel.

**MCP input schema validation.** Every tool declares a JSON Schema for its inputs. The MCP protocol validates inputs before the tool function executes. Invalid parameters (wrong type, missing required field, value out of range) are caught at the protocol level.

**`preview_compilation` catches parameter conflicts.** This is the unique advantage. The agent can preview the full parameter set before submitting. A conflict between smearing type and occupation scheme, or an incompatible combination of magnetism and SOC settings, is visible in the preview. No compute time is wasted.

**Elicitation for expensive operations.** Before submitting a large calculation (many atoms, many k-points, many steps), elicitation can interrupt the agent to ask the user for confirmation: "This 128-atom VASP hybrid calculation will take approximately 8 hours on 64 cores. Proceed?"

### Level 1: Structured Diagnostics (Rule-Based)

When a calculation fails, QMatSuite's output parsers return structured diagnostics — not raw log files.

The existing `OutputParser` classes (e.g., `VASPOutputParser` at `drivers/vasp/parsers/output.py`, `QEOutputParser` at `drivers/qe/parsers/output.py`) already parse convergence status, energy traces, and error conditions. The MCP error return extends this with `suggested_fixes`:

| Error Pattern | Diagnostic | Suggested Fix | Confidence |
|---|---|---|---|
| Energy oscillating | `energy_oscillating: true` | Reduce mixing_beta: 0.7 → 0.3 | High |
| SCF not converging | `iterations: 100, max: 100` | Increase electron_maxstep: 100 → 200 | Medium |
| Negative eigenvalue | `negative_eigenvalue: true` | Increase ecutwfc by 20% | Medium |
| Out of memory | `oom_detected: true` | Reduce k-grid or use fewer bands | High |
| POSCAR mismatch | `species_mismatch: true` | Verify structure + POTCAR consistency | High |

These are deterministic rules, not LLM reasoning. The agent can act on them directly: call `preview_compilation` with the suggested parameter change, verify the fix looks correct, and resubmit.

### Level 2: Agent-Driven Recovery

For complex failures that defy rule-based diagnosis, the agent uses its own reasoning:

1. **Inspect output**: `get_output_raw(calc_ulid, section="convergence", lines=50)` to see the raw convergence trace
2. **Search parameters**: `search_parameters(query="convergence acceleration methods")` to find relevant settings
3. **Query knowledge**: `search_knowledge(query="convergence failure metallic")` to check for past solutions
4. **Use sampling**: The MCP server can invoke `sampling/createMessage` to ask the client's LLM for interpretation, keeping the diagnostic reasoning separate from the main agent context (following DREAMS' pattern of separate LLM calls for convergence debugging)

This three-level architecture is more elegant than alternatives. El Agente requires 58 specialized agents to achieve error recovery. DREAMS requires a separate LLM call hardcoded into the tool. QMatSuite provides structured data at Level 1 that a single intelligent agent can act on, with Level 2 as an escape hatch for genuinely novel failures.

---

## 9. Workflow Examples

### 9.1 Quick Win: "Calculate Si Band Structure" (5 minutes)

**User**: "Calculate the band structure of silicon using QE with standard settings."

**Tool call sequence:**

```
1. list_structures()
   → [{name: "Si_diamond", formula: "Si2", structure_ulid: "01KC38MB..."}]

2. preview_compilation(
     engine="qe", workflow="bands",
     structure_ulid="01KC38MB...",
     presets={precision: "med", magnetism: "nonmagnetic"}
   )
   → Steps: [qe_scf (ecutwfc=40, 8x8x8 k-grid), qe_bands (nbnd=12, L-G-X-W-K path)]
   → Agent shows user: "Here's what will run. ecutwfc=40 Ry, k-path L-Γ-X-W-K."
   → User: "Looks good"

3. submit_calculation(
     engine="qe", workflow="bands",
     structure_ulid="01KC38MB...",
     presets={precision: "med"},
     name="Si_bands_standard"
   )
   → {job_id: "01KC3F...", status: "running"}

4. get_status(job_id="01KC3F...")          # Poll after ~30 seconds
   → {status: "running", progress: {current_step: "qe_scf", steps_completed: 0, steps_total: 2}}

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

**Total tool calls: 7. Total agent output tokens: ~500. Total tool input tokens: ~3,000.** The agent discovered capabilities, previewed parameters, submitted, monitored, analyzed, and visualized in a natural flow.

### 9.2 Research Project: "Find Optimal U Parameter for FeO" (hours)

**User**: "I need to find the optimal Hubbard U parameter for FeO. Scan U from 2 to 6 eV in steps of 1 eV and compare the bandgap with experiment (2.4 eV)."

**Tool call sequence (abbreviated):**

```
1. list_structures() → find FeO structure
2. search_knowledge(query="FeO Hubbard U") → check for past insights
3. search_parameters(query="hubbard U VASP") → find LDAUTYPE, LDAUU syntax

4-8. For U = 2, 3, 4, 5, 6:
     preview_compilation(engine="vasp", workflow="scf",
       structure_ulid="...",
       presets={magnetism: "collinear_lsda"},
       overrides={SYSTEM: {LDAU: true, LDAUTYPE: 2, LDAUL: [2,-1], LDAUU: [U, 0]}})
     → Preview each parameter set

     submit_calculation(..., name=f"FeO_U{U}")

9-13. get_status for each job (polling)

14-18. get_results_summary for each completed calculation:
     U=2: bandgap=0.8 eV
     U=3: bandgap=1.4 eV
     U=4: bandgap=2.1 eV
     U=5: bandgap=2.5 eV
     U=6: bandgap=3.0 eV

19. compare_calculations(calc_ulids=[...])
    → Side-by-side comparison table

20. record_insight(
      category="hubbard_U",
      engine="vasp",
      system_type="transition_metal_oxide",
      insight="For FeO with PBE+U (LDAUTYPE=2), U=5 eV gives bandgap closest to experiment (2.5 vs 2.4 eV). U=4 slightly underestimates (2.1 eV).",
      evidence=[calc_ulids],
      confidence="high"
    )
```

**Key observations:** Progressive disclosure matters here. The agent made ~20 `get_results_summary` calls at ~200 tokens each (4,000 tokens total) rather than 5 `get_band_structure` calls at ~1,500 tokens each (7,500 tokens). For a parameter scan, summaries suffice. The agent only requests detailed data for the optimal U value.

### 9.3 Long-Term: "Systematic Study of Perovskite Stability" (days/weeks)

**Session 1 — Planning and screening (Day 1):**

```
1. search_knowledge(query="perovskite stability DFT")
   → Past insights about perovskite calculations

2. fetch_structure(source="materials_project", query="ABX3 perovskite", limit=20)
   → Import 20 candidate structures

3-22. For each candidate:
    preview_compilation + submit_calculation (scf, low precision)
    → Quick screening: which converge, which are stable?

23. compare_calculations(calc_ulids=[...])
    → Rank by formation energy, filter unstable
    → Agent narrows to 5 promising candidates
```

**Session 2 — Detailed calculations (Day 3):**

```
1. get_project_history(engine="vasp", workflow="scf")
   → Agent recovers context: "I screened 20 perovskites, 5 are promising"
   → No conversation history needed — provenance DB has everything

2-11. For each of 5 candidates:
    submit_calculation (relax, medium precision)
    submit_calculation (bands + DOS, medium precision)

12-21. Analyze results:
    get_results_summary → overview
    get_band_structure → detailed band structure for each
    get_dos → density of states for each

22. record_insight(
      category="perovskite_stability",
      insight="Among 20 ABX3 candidates, CsPbI3, MAPbBr3, and FAPbI3 show
               direct bandgaps in the 1.2-1.8 eV range suitable for photovoltaics.",
      evidence=[calc_ulids]
    )
```

**Session 3 — High-precision refinement (Day 7):**

```
1. search_knowledge(query="perovskite photovoltaic bandgap")
   → Recalls findings from Session 2

2-4. For top 3 candidates:
    submit_calculation (bands, high precision + HSE06 hybrid)
    → Accurate bandgap with hybrid functional

5. Final comparison and report generation
```

**Memory architecture enables this.** Session 2 starts with `get_project_history` — no conversation context from Session 1 is needed. Session 3 starts with `search_knowledge` — accumulated insights are queryable. The agent maintains research continuity across days without maintaining a single conversation.

---

## 10. MCP Apps: Interactive Visualization

MCP Apps (January 2026) render interactive HTML/JavaScript components in sandboxed iframes within the client UI. Tools return a `_meta.ui.resourceUri` pointing to a `ui://` scheme resource; the client fetches and renders the HTML with bidirectional JSON-RPC communication via `postMessage`.

### Band Structure Viewer

**Data from tool**: k-distances array, eigenvalue matrix (n_kpoints x n_bands), high-symmetry point labels and positions, Fermi energy, optional orbital projections (4D array from `BandStructure.projections`).

**Visualization**: Interactive Plotly chart. X-axis: k-distance with labeled high-symmetry points (vertical dashed lines). Y-axis: energy relative to Fermi level. Band lines colored by spin channel (if spin-polarized) or orbital character (if projections available). Hover shows exact k-point and energy. Zoom to inspect band crossings. Horizontal Fermi level indicator.

### DOS Viewer

**Data from tool**: Energy array, total DOS, optional PDOS matrix (n_atoms x n_energies x n_orbitals), atom labels (e.g., "Ti_1", "O_1" from POSCAR), orbital labels.

**Visualization**: Interactive stacked area chart. Toggleable decomposition by element and orbital. Energy on x-axis, states/eV on y-axis. Vertical Fermi level line. Spin-up/spin-down for magnetic systems. Hover shows exact values.

### Convergence Dashboard

**Data from tool**: SCF iteration energies, force norms (for relaxation), stress tensors (for vc-relax), time per iteration.

**Visualization**: Multi-panel chart. Top: energy vs. iteration (log scale for energy difference). Bottom: max force vs. iteration. Horizontal threshold lines for convergence criteria. Color coding: green when converged, red when oscillating.

### Structure Viewer

**Data from tool**: Atomic positions, species, unit cell, periodic boundary conditions.

**Visualization**: 3D viewer using Three.js or NGL Viewer. Atom spheres colored by element. Unit cell wireframe. Rotation, zoom, pan. Bond display. Supercell toggle. Miller plane display for surfaces.

### Parameter Space Explorer

**Data from tool**: Parameter scan results (e.g., U-parameter scan from Section 9.2).

**Visualization**: Interactive heatmap or line plot. X-axis: scanned parameter. Y-axis: property of interest (bandgap, energy, force). Experimental reference line if provided. Click to see individual calculation details.

---

## 11. Competitive Differentiation

| Feature | El Agente | ChemGraph | VASPilot | DREAMS | Masgent | **QMatSuite** |
|---|---|---|---|---|---|---|
| **Agent architecture** | 58 custom agents | LangGraph DAG | CrewAI 4-agent | LangGraph 3-agent | pydantic-ai single | **MCP (BYOE)** |
| **LLM lock-in** | Claude Opus 4.5 | GPT-4/Claude/Gemini | GPT-4/Claude | Claude 3.7 Sonnet | 7 providers | **None** |
| **Engine coverage** | ORCA only | 9 (ASE-limited) | VASP only | QE only | VASP + 4 MLP | **15 engines native** |
| **Parameter access** | ~100% (1 engine) | ~25% (ASE) | ~30% (pymatgen) | ~25% (ASE) | ~30% (pymatgen) | **100% (all engines)** |
| **Solid-state workflows** | No | No (ASE ceiling) | Basic | Basic | Basic | **Full (bands/DOS/k-pts)** |
| **Preview before execute** | No | No | No | No | No | **`preview_compilation`** |
| **Interactive viz in chat** | No | No | No | No | No | **MCP Apps** |
| **Tool discovery scaling** | Manual 34 tools | Manual | Manual 17 tools | Manual | Manual 30 tools | **Tool Search + defer_loading** |
| **Structured error recovery** | LLM-driven | Anti-loop detection | Agent-driven | Separate LLM call | Schema validation | **3-level (prevent/diagnose/recover)** |
| **Long-term memory** | MongoDB episodic | In-memory only | SQLite + ChromaDB | Pickle state | None | **Provenance DB + knowledge base** |
| **Multi-engine workflows** | No | No | No | No | No | **Yes (QE→W90→Yambo, etc.)** |
| **Tests** | Unknown | ~20% coverage | 2 files | 0 tests | 0 tests | **5,000+ tests, gate CI** |
| **API key management** | User provides to El Agente | User provides | User provides | Hardcoded | User provides | **User's own CLI (BYOE)** |
| **Open source** | Proprietary | Apache 2.0 | LGPL | Open | MIT | **Open** |

**The critical differentiators are structural, not incremental:**

1. **BYOE** — No framework lock-in. Works with any MCP-compatible agent today and tomorrow. Competitors must rewrite when LLM providers change APIs.

2. **15 engines at 100% parameter access** — ChemGraph is architecturally limited by ASE (no reciprocal space). VASPilot/Masgent are limited to pymatgen templates (~30% of VASP's parameters). El Agente has 100% access but only for ORCA. QMatSuite has native parsers/writers with full parameter documentation for all 15 engines.

3. **`preview_compilation`** — No competitor previews the full parameter set before execution. This alone eliminates an entire class of errors (wrong parameters, unexpected defaults, preset conflicts) that other systems discover only after wasting compute time.

4. **Mathematical reversibility** — The preset compiler/detector guarantee `detect(compile(options)) == options`. No other system has formally reversible presets. This enables the agent to understand *why* parameters have their values (provenance tracking at the parameter level).

---

## 12. Security and Trust

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

**Rate limiting.** Configurable limits on tool calls per minute/hour prevent runaway agents from consuming excessive resources. Default: 60 calls/minute for discovery tools, 10 calls/minute for execution tools.

---

## 13. Deployment Architecture

### 13.1 Local (Default)

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

**Calculations run on the local machine.** The existing `JobManager` (`daemon/jobs.py`) manages background execution via `ThreadPoolExecutor`. The MCP server exposes this through `submit_calculation` (non-blocking submit) and `get_status` (polling).

### 13.2 Remote (Future)

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

**SLURM integration**: Following Argonne's Pattern A (direct shell-out), the MCP server wraps SLURM commands (`sbatch`, `squeue`, `scancel`, `sacct`) for job management. The `submit_calculation` tool generates the SLURM script, submits via `sbatch`, and returns the job ID. Status polling wraps `squeue`/`sacct`.

---

## 14. Testing Strategy

### Contract Tests

Every MCP tool has a contract test verifying:
- **Input schema validation**: Malformed inputs are rejected with structured errors
- **Output schema conformance**: Successful returns match the declared `outputSchema`
- **Error handling**: Known failure modes return structured diagnostics, not stack traces
- **Idempotency**: Discovery/preview tools return identical results on repeated calls

These extend the existing contract crawler infrastructure (`tests/contract_crawler/`) which already achieves 95.7% RPC coverage (111/116 methods).

### Integration Tests

Tool calls that exercise actual QMatSuite core with mock engines:
- `preview_compilation` end-to-end with real preset compiler and PrecisionAdvisor
- `submit_calculation` with mock engine handlers (no actual VASP/QE execution)
- Error recovery flow: submit → fail → diagnose → fix → resubmit
- Knowledge base CRUD: record → search → update → search

### Real-Run Smoke Tests

End-to-end with actual engine executions (extending existing `tests/integration/`):
- Si SCF with QE (existing: already runs in CI)
- Si bands with QE (existing: already has golden reference)
- VASP SCF (existing: runs with real VASP binary)
- Full workflow: `list_engines` → `list_workflows` → `get_presets` → `preview_compilation` → `submit_calculation` → `get_status` → `get_results_summary` → `get_band_structure`

### Agent Simulation Tests

Scripted tool call sequences mimicking realistic agent behavior:
- "Si band structure" workflow (Section 9.1) as automated test
- "U parameter scan" workflow (Section 9.2) with mock calculations
- Error recovery scenario: inject SCF failure, verify structured diagnostics, verify fix suggestion works

### Context Budget Tests

Measure total tokens consumed by typical workflows:
- Count tokens in tool definitions (always-loaded vs. deferred)
- Count tokens in tool returns (summary vs. detailed tier)
- Verify typical 10-calculation workflow stays under 50K total tool tokens
- Compare with/without progressive disclosure

---

## 15. Implementation Roadmap

### Phase 0: Foundation (Week 1-2)

**Goal**: MCP server skeleton. Agent can discover QMatSuite capabilities.

- Set up FastMCP server at `src/quantumvitas/mcp/server.py`
- Wire stdio transport (reusing patterns from `daemon/server.py`)
- Implement 3 always-loaded tools: `list_engines`, `list_workflows`, `get_presets`
- Map tools to existing `QVService` methods (thin adapter, no new logic)
- Add `.mcp.json` configuration for Claude Code
- First contract test: tool schemas validate, returns conform

**Deliverable**: `python -m quantumvitas.mcp.server` starts, agent can discover engines.

### Phase 1: Core Loop (Week 3-5)

**Goal**: Agent can preview, submit, and analyze calculations.

- Implement `preview_compilation` (the killer feature):
  - Wire to `presets/compiler.py:compile_presets()` + `PrecisionAdvisor`
  - Add parameter provenance tracking (which preset/override set each value)
  - Generate input file preview via `inputformat/writer.py:write_engine_inputs()` to temp dir
- Implement `submit_calculation`, `get_status`, `get_results_summary`
  - Wire to `QVService.Run` + `JobManager`
  - Define output schemas for all tools
- Implement `search_parameters`:
  - Build BM25 index over `*_tags.json` files at server startup
  - Index 1,000+ parameters across all engines
- Implement `list_structures`
- Add standard return envelope with `context_hint`
- First demo: "Calculate Si band structure" works end-to-end

**Deliverable**: Full discover-preview-submit-analyze loop working.

### Phase 2: Rich Analysis + Visualization (Week 6-8)

**Goal**: Interactive visualization and detailed analysis.

- Implement detailed analysis tools:
  - `get_band_structure` → `BandStructure.to_primitives()` + MCP App
  - `get_dos` → `DOS.to_primitives()` + MCP App
  - `get_convergence_history` → step digest series
  - `get_trajectory` → `Trajectory` frames
  - `compare_calculations` → multi-calc query
  - `get_output_raw` → paginated artifact access
- Build MCP App templates:
  - Band structure viewer (Plotly)
  - DOS viewer (Plotly)
  - Convergence dashboard (Plotly)
  - Structure viewer (Three.js/NGL)
- Add elicitation for pre-submission confirmation
- Implement `defer_loading` for analysis and structure tools
- Demo: Full research workflow with visualization

**Deliverable**: Agent can visualize results interactively in conversation.

### Phase 3: Intelligence (Week 9-12)

**Goal**: Memory, knowledge base, error recovery, structure tools.

- Implement session memory tools:
  - `get_project_history` → provenance DB queries
  - `get_provenance` → lineage tracing
  - `annotate_calculation` → journal entry creation
- Implement knowledge base:
  - SQLite schema at `~/.qmatsuite/knowledge.db`
  - `search_knowledge` with FTS5 full-text search
  - `record_insight` with provenance links
- Implement structured error diagnostics:
  - Extend output parsers with `suggested_fixes` generation
  - Rule-based diagnosis for common failure modes
- Implement structure tools:
  - `fetch_structure` → Materials Project/OPTIMADE integration
  - `import_structure` → local file import
- Demo: Multi-calculation research project with memory

**Deliverable**: Agent accumulates and retrieves knowledge across sessions.

### Phase 4: Polish (Week 13-16)

**Goal**: Production readiness, remote deployment, documentation.

- Streamable HTTP transport for remote/HPC deployment
- OAuth 2.0 authentication
- SLURM integration for HPC job submission
- Rate limiting and security hardening
- Performance optimization:
  - BM25 index caching
  - Tool return token budgets
  - Context budget test suite
- Documentation:
  - MCP server setup guide
  - Tool catalog reference
  - Workflow tutorials
- Paper writing: "QMatSuite: A Cognitive Architecture for AI-Driven Computational Materials Research"

**Deliverable**: Production-ready MCP server with remote deployment support.
