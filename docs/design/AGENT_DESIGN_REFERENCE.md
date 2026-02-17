# Building an MCP server for scientific computing: a design reference

**The Model Context Protocol has matured into the universal standard for connecting AI agents to external tools, and scientific computing is one of its most compelling application domains.** This report synthesizes the latest MCP specification features, context engineering strategies, advanced tool patterns, scientific computing integrations, cognitive science foundations, and emerging architectural patterns — all as of February 2026. It serves as a comprehensive design reference for building an MCP server that connects AI agents to scientific computing infrastructure.

---

## MCP specification: from protocol to platform (2024–2026)

The MCP specification has evolved through four releases in under 18 months. The **2025-11-25 spec** (the latest) introduced Tasks for async workflows, URL-mode elicitation, sampling with tools, an extensions framework, and simplified authorization. In December 2025, Anthropic donated MCP to the **Agentic AI Foundation** under the Linux Foundation, co-founded with Block and OpenAI — cementing its status as an industry standard adopted by every major AI provider.

### Elicitation enables human-in-the-loop workflows

Elicitation allows MCP servers to request **structured input from users** mid-execution. A server sends an `elicitation/create` request containing a JSON Schema; the client renders a form, collects input, and returns it. The 2025-11-25 spec added **URL-mode elicitation**, where servers bounce users to a secure browser window for sensitive operations like OAuth flows or credential collection — the agent never sees passwords.

```python
from fastmcp import FastMCP, Context
from dataclasses import dataclass

mcp = FastMCP("Scientific Computing Server")

@dataclass
class ComputeConfig:
    num_nodes: int
    partition: str
    walltime_hours: int

@mcp.tool
async def submit_hpc_job(ctx: Context) -> str:
    result = await ctx.elicit(
        message="Configure your HPC job parameters",
        response_type=ComputeConfig
    )
    if result.action == "accept":
        return f"Submitting to {result.data.partition} on {result.data.num_nodes} nodes"
    return "Job submission cancelled"
```

Elicitation only supports shallow JSON objects with primitive types. Clients must declare the `elicitation` capability. For a scientific computing server, this is essential for confirming expensive operations — submitting large HPC jobs, authorizing data transfers, or approving resource allocations.

### Tool output schemas make results machine-readable

Since the 2025-06-18 spec, tools can declare an `outputSchema` alongside their `inputSchema`. When present, the tool response includes a `structuredContent` field with machine-parseable data conforming to that schema, plus traditional `content` for human-readable text. This dual-output design is critical for scientific computing, where downstream tools need to programmatically consume results (e.g., parsing molecular energies, extracting simulation parameters).

```json
{
  "name": "calculate_energy",
  "description": "Calculate molecular energy using DFT",
  "inputSchema": {
    "type": "object",
    "properties": { "smiles": { "type": "string" }, "method": { "type": "string" } }
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "total_energy_eV": { "type": "number" },
      "homo_lumo_gap_eV": { "type": "number" },
      "converged": { "type": "boolean" },
      "iterations": { "type": "integer" }
    },
    "required": ["total_energy_eV", "converged"]
  }
}
```

The schema philosophy is **soft enforcement** — tools should conform but clients handle graceful fallback. The root level must be `type: "object"`.

### Resources versus tools: a critical design choice

| Aspect | Resources | Tools |
|--------|-----------|-------|
| Control | Application/user decides when to fetch | LLM decides when to call |
| Purpose | Provide read-only context/data | Perform actions and computations |
| Side effects | None | Can modify state |
| Addressing | URI-based (`file://`, custom schemes) | Named with input/output schemas |

The design heuristic: **Resources are what the client should know; tools are what the client can do.** For a scientific computing server, expose dataset metadata, system status, and configuration as resources. Expose job submission, computation execution, and data transfer as tools. When the model needs to autonomously decide what data to retrieve, use tools — resources require user/application selection.

### Sampling inverts the LLM flow

Sampling lets MCP servers **request LLM completions from the client**. A server sends a `sampling/createMessage` request with messages, system prompt, and model preferences; the client forwards to its LLM and returns the completion. The 2025-11-25 spec added **sampling with tools**, enabling agentic servers that orchestrate multi-step reasoning. Use cases for science: error analysis ("interpret this convergence failure"), data extraction ("parse this experimental log into structured data"), and classification ("categorize this molecule's functional groups").

### Streamable HTTP replaces SSE for production

Streamable HTTP, introduced in 2025-03-26, uses a **single endpoint** (typically `/mcp`) instead of the old dual-endpoint SSE transport. Clients send JSON-RPC via HTTP POST; servers respond with either standard JSON or SSE streams for long-running operations. Session management uses `Mcp-Session-Id` headers. Performance testing shows Streamable HTTP maintains **~0.0075s response time** under high concurrency versus SSE's degradation to ~1.5s. Standard HTTP infrastructure (load balancers, CDNs, API gateways) works natively — critical for deploying scientific computing MCP servers behind institutional firewalls.

### MCP Apps bring interactive visualization to conversations

Announced January 26, 2026, MCP Apps is the **first official MCP extension**. Tools return interactive HTML/JavaScript UI components rendered in sandboxed iframes. A tool declares a `_meta.ui.resourceUri` pointing to a `ui://` scheme resource; the host fetches and renders the UI with bidirectional JSON-RPC communication via `postMessage`. For scientific computing, this enables **interactive data dashboards, 3D molecular viewers, real-time simulation monitoring, and parameter space exploration** directly in the conversation. Client support includes Claude, ChatGPT, VS Code, and Goose.

### The MCP Registry catalogs 2,000+ servers

Launched September 2025 at `registry.modelcontextprotocol.io`, the registry is a **metaregistry** storing metadata that points to actual packages on npm, PyPI, or Docker Hub. It provides a REST API (`GET /v0/servers`) for programmatic discovery. As of November 2025, **~2,000 servers** were indexed with 407% growth from launch. The registry supports subregistries for enterprise private catalogs with curation, ratings, and security scanning.

### What's next for MCP

The roadmap includes hardening **Tasks** (async operations spanning minutes or hours), improving **statelessness and scalability** for enterprise deployment, finalizing **server identity** via `.well-known` URLs, expanding the **extensions framework**, and moving the registry to GA. The next spec version is expected ~Q2 2026 based on the six-month cadence.

---

## Context engineering: the art of token curation

Context engineering has emerged as the critical discipline for building effective AI agents. Three landmark publications define the field's best practices.

### Anthropic's framework: find the smallest high-signal token set

Anthropic's September 2025 engineering blog post defines context engineering as curating the **optimal set of tokens that maximize the likelihood of a desired outcome**. Their core insight is the **attention budget** — the transformer's n² pairwise relationship computation means 10K tokens create 100M relationships while 100K tokens create 10B. Performance degrades on a gradient, not a cliff.

Three strategies anchor their approach for long-horizon tasks. **Compaction** summarizes conversation history approaching context limits, preserving architectural decisions and unresolved issues while discarding redundant tool outputs. Claude Code implements this by passing full message history through a summarization model, then continuing with compressed context plus the 5 most recently accessed files. **Structured note-taking** externalizes persistent state to files like `CLAUDE.md` or `todo.md` that survive context resets. **Multi-agent architectures** give specialized sub-agents clean context windows; each explores 10K+ tokens but returns 1–2K token summaries.

Their tool design guidance is particularly relevant: tools should be **self-contained with minimal overlap and clear descriptions**. Bloated toolsets creating ambiguous decision points are the most common failure mode. "If a human engineer can't definitively say which tool should be used, an AI agent can't be expected to do better."

### Manus rebuilt their framework five times to learn six lessons

Yichao "Peak" Ji's widely-discussed blog post revealed that Manus operates at a **100:1 input-to-output token ratio** with ~50 tool calls per average task. Their six strategies are:

**Design around the KV-cache.** This is Manus's single most important optimization. Keep prompt prefixes stable, make context append-only, ensure deterministic serialization with stable JSON key ordering, and mark cache breakpoints explicitly. With Claude Sonnet, cached tokens cost **$0.30/MTok versus $3/MTok uncached** — a 10× difference.

**Mask, don't remove.** Never dynamically add or remove tools mid-iteration — this invalidates the KV-cache and confuses the model when prior actions reference now-removed tools. Instead, use a context-aware state machine that masks token logits during decoding.

**Use the filesystem as context.** Treat the filesystem as unlimited, persistent, externalized memory. Compression strategies must be restorable — drop web page content but preserve the URL; omit document content but keep the file path.

**Manipulate attention through recitation.** Manus creates a `todo.md` file and updates it step-by-step, checking off completed items. This "recites" objectives into the end of context, pushing the global plan into the model's recent attention span, mitigating lost-in-the-middle effects.

**Keep errors in context.** Leave failed actions and stack traces — don't clean up. Error evidence shifts the model's prior away from repeating mistakes.

**Don't get few-shotted.** Repetitive action-observation pairs cause pattern mimicry. Inject structured variation — different serialization templates, alternate phrasing — to break pattern fixation.

Their later evolution introduced a **"Pre-Rot Threshold"** at ~256K tokens for a 1M context window, a tiered preference of raw > compaction > summarization, and replaced constant `todo.md` rewriting (which wasted ~30% of tokens) with a Planner sub-agent.

### Google ADK separates storage from presentation

Google's Agent Development Kit implements a **three-tier context architecture** that rejects appending everything into one giant prompt:

- **Tier 1 — Session:** Raw chronological log of typed `Event` objects with metadata (not opaque text). Enables time-travel debugging and rich compaction operations.
- **Tier 2 — Memory:** Searchable long-term archive spanning conversations, retrieved on demand via `MemoryService`.
- **Tier 3 — Artifacts:** Large files and documents externalized from context, referenced by path/ID.

A **compilation pipeline** transforms sessions into working context through selection (filtering irrelevant events), transformation (flattening into Content objects), and injection (writing into the LLM request). ADK also provides four scoped context types following the **principle of least privilege**: `ReadonlyContext`, `CallbackContext`, `ToolContext`, and `InvocationContext`.

### Context rot is real and measurable

The "Lost in the Middle" research (Liu et al., 2023/2024) established the **U-shaped performance curve**: models perform best when relevant information is at the very beginning or end of context, with accuracy dropping **15–20 percentage points** for middle positions. GPT-3.5-Turbo with information in the middle performed worse than its no-document baseline.

Chroma's July 2025 "Context Rot" study tested **18 LLMs** and found that standard needle-in-a-haystack benchmarks are misleading because they test only lexical matching. With semantic matching, performance drops dramatically. On the LongMemEval benchmark, models performed **~30% worse** with full conversation history (~113K tokens) versus focused history (~100–300 tokens). A counterintuitive finding: models performed slightly better on randomly shuffled haystacks, suggesting LLMs don't process context in a linear, structured way.

**The practical implication for scientific computing MCP servers: every token returned by a tool is a bet against accuracy.** Design tool outputs that return structured, concise summaries rather than raw data dumps. Implement progressive disclosure — let the agent request more detail only when needed.

---

## Advanced tool patterns for scaling to thousands of tools

### Tool Search with defer_loading handles massive tool libraries

Anthropic's November 2025 Advanced Tool Use beta solves a critical scaling problem. Tools marked with `defer_loading: true` are excluded from initial context. Claude sees only the Tool Search Tool plus non-deferred tools. When it needs functionality, it searches the catalog (names, descriptions, argument names) and auto-loads **3–5 most relevant tools** as `tool_reference` blocks expanded to full definitions.

Two search variants exist: **Regex** (Claude constructs Python `re.search()` patterns) and **BM25** (natural language keyword-ranked search). The results are striking: **85% reduction in token usage** while supporting up to 10,000 tools. Opus 4 accuracy improved from 49% to 74%.

For an MCP server exposing hundreds of scientific tools across chemistry, physics, biology, and data science, this pattern is essential. Configure domain-specific tools with `defer_loading: true` and keep core infrastructure tools (job submission, file transfer) always loaded.

```json
{
  "type": "mcp_toolset",
  "mcp_server_name": "science-platform",
  "default_config": { "defer_loading": true },
  "configs": {
    "submit_job": { "defer_loading": false },
    "check_status": { "defer_loading": false }
  }
}
```

### Programmatic tool calling keeps data out of context

Anthropic's Programmatic Tool Calling has Claude **write Python code** that orchestrates tool calls in a sandboxed execution environment. Only `stdout` output returns to Claude's context. Combined with the "Code Execution with MCP" pattern, tools are represented as a filesystem of typed functions that the agent discovers progressively:

```
servers/
├── materials-project/
│   ├── query_materials.ts
│   └── get_structure.ts
├── slurm/
│   ├── submit_job.ts
│   └── check_queue.ts
```

Agent-generated code filters and transforms data in the sandbox before returning summaries. The headline result: **150,000 tokens reduced to 2,000 (98.7% savings)**. For scientific computing where tool outputs can be enormous (simulation logs, molecular coordinates, spectral data), this pattern is transformative.

### Input examples improve parameter accuracy by 18%+

The `input_examples` feature provides concrete usage patterns alongside JSON Schema definitions. Each example must validate against the tool's `input_schema`. For scientific tools with complex nested parameters (basis sets, convergence criteria, boundary conditions), examples dramatically reduce malformed calls:

```json
{
  "name": "run_dft_calculation",
  "input_schema": { "..." },
  "input_examples": [{
    "molecule_smiles": "c1ccccc1",
    "method": "B3LYP",
    "basis_set": "6-311++G(d,p)",
    "convergence": { "energy_threshold": 1e-8, "max_iterations": 200 }
  }]
}
```

Note: `input_examples` and Tool Search Tool cannot be used simultaneously.

### How coding agents handle MCP tool discovery

**Claude Code** loads all tool definitions upfront but has an `ENABLE_TOOL_SEARCH` setting for the Tool Search beta. MCP is configured via `.mcp.json` at project root (team-shareable) or CLI commands. Subagents automatically inherit MCP tools from parent conversations.

**Cursor** limits MCP to **40 tools** (hard cap) and only supports tools, not resources. All tools load upfront with no on-demand discovery.

**Windsurf** loads MCP tools at startup and limits Cascade to **20 tool calls per prompt**. Its Deep Context Engine uses proprietary M-Query + RAG for codebase indexing.

**Gemini CLI** has the most sophisticated MCP conflict resolution: first registration wins the unprefixed name; subsequent servers get `serverName__toolName` prefixes. It supports OAuth 2.0 for remote MCP servers and auto-discovers MCP resources via `@` syntax.

### Docker Dynamic MCP provisions servers on demand

Docker's experimental Dynamic MCP (Desktop 4.50+) provides "primordial" tools — `mcp-find`, `mcp-add`, `mcp-remove`, `mcp-config-set` — that let agents **discover and install MCP servers during conversations** from Docker's curated catalog. Every MCP server runs in its own isolated container with 1 CPU and 2GB memory limits. An experimental **Code Mode** lets agents write JavaScript to compose multiple MCP tools into workflows. This pattern could be powerful for scientific computing: an agent could dynamically provision domain-specific tools (a chemistry MCP server, a materials database MCP server) as needed for a particular research workflow.

---

## Scientific computing already has a growing MCP ecosystem

### Argonne's science-mcps sets the template

The most comprehensive scientific MCP effort is Argonne National Laboratory's paper "Experiences with Model Context Protocol Servers for Science and HPC" (arXiv 2508.18489). Their **thin MCP adapter approach** wraps existing mature services rather than building new ones, deployed as separate Docker containers using Streamable HTTP transport.

They implemented seven MCP servers:

- **Globus Transfer MCP**: File discovery, browsing, and transfer across collections
- **Globus Compute MCP**: Remote Python/Shell function execution on HPC endpoints with `register_python_function`, `submit_task`, `get_task_status`
- **Globus Search MCP**: Create/query search indexes across distributed repositories
- **Computing Facility MCP**: Real-time status for ALCF and NERSC systems (queue status, maintenance schedules, system health)
- **Octopus MCP**: Event streaming via AWS Managed Kafka
- **Garden MCP**: Scientific ML model discovery and invocation
- **Rhea MCP**: Dynamic interface to Galaxy Toolshed bioinformatics tools using **RAG over documentation** with Qwen3-Embedding-0.6B — a standout pattern where one tool (`find_tools`) accepts natural language queries and dynamically generates MCP tool definitions

Their four case studies demonstrate practical scientific workflows: molecular structure relaxation with MACE ML potentials on ALCF's Edith cluster, multi-site phylogenetic analysis distributed across ALCF Polaris and NERSC Perlmutter, quantum chemistry HOMO-LUMO gap calculations using PySCF/GPU4PySCF, and filesystem monitoring with event streaming.

The key architectural lessons: **build thin adapters over broad services, separate discovery from invocation** (the Rhea pattern for large tool ecosystems), and let agents replace custom glue code by generating it dynamically.

### The broader scientific MCP landscape

The **mcp.science** platform (github.com/pathintegral-institute/mcp.science) provides a curated monorepo including Materials Project, GPAW DFT, Jupyter Kernel, Wolfram/Mathematica, and NEMAD servers. **Jupyter MCP servers** are particularly mature, with datalayer/jupyter-mcp-server enabling real-time notebook interaction including multimodal output. Biology is well-served through servers for MaBoSS (Boolean biological models), NeKo (network biology), PhysiCell (multicellular simulations), NCBI datasets, PDB, and ChEMBL. Physics has quantum simulation MCP servers using QuTiP with Manim visualization, and Genesis World for robotics/embodied AI physics simulation.

### HPC job submission through MCP has three emerging patterns

**Pattern A — Direct SLURM Shell-Out** (exemplified by NCSA's hpcGPT): The MCP server runs on a login node and wraps SLURM CLI commands (`sinfo`, `squeue`, `sbatch`, `scancel`, `sacct`), parsing output into structured results. Simple and direct but requires login node access.

**Pattern B — Abstraction Layer** (exemplified by Argonne's Globus Compute approach): An intermediate service handles job dispatch. Globus Compute provides serverless function execution, with the MCP server handling registration, submission, and status monitoring. More portable across institutions.

**Pattern C — JupyterLab Bridge** (exemplified by jlab-mcp): Claude Code on a login node communicates via MCP to a JupyterLab instance running on a compute node allocated via `sbatch`. Connection info exchanges through the shared filesystem. Enables interactive GPU computation through the notebook paradigm.

The typical SLURM MCP tool set synthesized from implementations includes: `get_partition_info` (wrapping `sinfo`), `submit_batch_job` (wrapping `sbatch`), `get_job_queue` (wrapping `squeue`), `get_job_details` (wrapping `scontrol`), `cancel_job` (wrapping `scancel`), `get_job_history` (wrapping `sacct`), and resource estimation tools for memory/GPU prediction.

---

## Cognitive science provides the blueprint for agent memory

### CoALA maps human cognition to agent architecture

The CoALA framework (Sumers et al., 2023, published in TMLR 2024) from Princeton draws on production systems like Soar and ACT-R to propose a systematic blueprint organized along three dimensions:

**Memory** mirrors human cognitive science with working memory (active context), episodic memory (past experience trajectories), semantic memory (factual knowledge), and procedural memory (knowledge about *how* to act — stored as code, prompts, or policies).

**Action space** divides into external grounding actions (tool use, API calls, dialogue) and internal actions: reasoning (chain-of-thought, decomposition), retrieval (fetching from long-term stores), and learning (updating memories from experience).

**Decision-making** follows a generalized cycle: retrieve relevant information → reason about what to do → execute action → observe result → loop. The key insight: **LLMs function as probabilistic production systems**, where prompt engineering serves as control flow.

### Agent memory taxonomy spans three axes

The comprehensive "Memory in the Age of AI Agents" survey (Hu et al., December 2025, 102 pages, 47 authors) introduces a three-axis taxonomy. **Forms** describes physical representation: token-level (human-readable text chunks), parametric (model weights), and latent (continuous vectors/KV-cache). **Functions** describes purpose: factual memory (declarative knowledge), experiential memory (procedural/how-to, subdivided into case-based trajectories, strategy-based workflows, and skill-based executable code), and working memory. **Dynamics** describes temporal evolution: formation, evolution (consolidation/decay), and retrieval.

Critical distinctions for design: **Agent memory ≠ RAG** (RAG is static retrieval; agent memory involves active, self-optimizing storage with temporal evolution). **Agent memory ≠ context engineering** (context engineering optimizes the immediate window; agent memory maintains persistent state across sessions).

### A-MEM brings Zettelkasten principles to agent memory

A-MEM (Xu et al., 2025, accepted NeurIPS 2025) applies the Zettelkasten slip-box method: the agent **autonomously decides** how to organize, link, and evolve its memories without predefined schemas. Three operations drive the system: **note construction** (generating structured notes with content, contextual descriptions, keywords, and embeddings), **link generation** (LLM-determined connections between semantically related memories), and **memory evolution** (new memories trigger updates to existing notes' contextual representations). This produces interconnected knowledge networks that grow organically — directly applicable to a scientific computing agent that accumulates domain knowledge across sessions.

### ACE treats context as an evolving playbook

The ACE framework (Zhang et al., 2025, Stanford/SambaNova) addresses brevity bias and context collapse through a three-role architecture: **Generator** (produces reasoning trajectories), **Reflector** (distills insights from successes and failures), and **Curator** (converts lessons into structured delta updates with helpful/harmful counters). This mirrors how humans learn: experimenting → reflecting → consolidating. ACE achieved **+10.6% improvement** on agent tasks and **~87% reduction** in adaptation latency. For scientific computing, this means the agent's system prompt evolves to accumulate domain-specific strategies — "when running DFT calculations, always check convergence before accepting results."

### The scientific method maps directly to agent workflow design

The parallel is precise: hypothesis generation maps to plan formulation, experimental execution maps to tool invocation, result analysis maps to output evaluation, and synthesis/revision maps to reflection and strategy update. Multiple frameworks now operationalize this — Sakana AI's "The AI Scientist" automates the full cycle from idea generation through paper drafting, Google's AI Co-Scientist uses specialized agents for generation, reflection, proximity checking, and ranking, and ToolUniverse connects LLMs to 600+ scientific tools via MCP.

### Reflective patterns close the learning loop

The **Reflexion framework** (Shinn et al., NeurIPS 2023) introduced verbal reinforcement learning: instead of updating model weights, linguistic self-critique is stored in episodic memory as a "semantic gradient signal." Three distinct models collaborate — Actor (generates actions), Evaluator (scores trajectories), and Self-Reflection Model (generates nuanced verbal feedback). Results: **91% pass@1** on HumanEval, surpassing GPT-4's 80% at the time.

The broader metacognitive pattern involves periodic self-evaluation where the agent reviews memories, thoughts, and past actions, assigns a progress score, and if progress is insufficient, triggers introspection that generates new questions and retrieves relevant memories for strategy revision. A critical caveat: LLMs average a **64.5% failure rate** in detecting their own errors but correct identical errors in others' work — motivating the separation of actor and evaluator roles.

---

## The emerging consensus on agent architecture

### Start single, scale to multi — with clear criteria

The industry has converged on a pragmatic position. **Anthropic's evolution** tells the story: their December 2024 guide strongly favored simplicity ("find the simplest solution possible"), but their June 2025 engineering post revealed their own multi-agent research system achieved **90.2% performance improvement** over single-agent Claude Opus 4. Their January 2026 guide codified four multi-agent patterns: subagents, skills, handoffs, and routers.

Microsoft's criteria for multi-agent transition are concrete: crossing security/compliance boundaries, multiple teams with separate knowledge areas, or planned growth beyond 3–5 distinct functions. For scientific computing, multi-agent makes sense when **parallelizing across independent experiments, distributing work across HPC sites, or separating domain-specific reasoning** (a chemistry agent, a materials science agent, a data analysis agent).

Token usage alone explains **80% of performance variance** in multi-agent research systems. Multi-agent systems use ~15× more tokens than chat interactions. The economics matter.

### MCP has won the tool integration standard

MCP is now supported by Anthropic, OpenAI, Google, Microsoft, and AWS. The shift from passive context (prompt stuffing) to active tool use (agents calling MCP servers) is the **defining architectural change of 2025–2026**. An emerging protocol stack is crystallizing: MCP for tool/context integration, A2A (Google) for inter-agent collaboration, and MCP Gateways for enterprise authentication, audit trails, and policy enforcement.

### Claude Code's architecture reveals production patterns

Claude Code implements the most sophisticated subagent system among coding agents. Built-in subagents include **Explore** (fast, read-only codebase search), **Plan** (complex reasoning for implementation strategies), **Testing**, and **Documentation**. Each runs in its own context window with custom system prompts and specific tool access. Delegation happens automatically based on task analysis. Subagents are defined as **Markdown files with YAML frontmatter** in `.claude/agents/`, making them version-controllable and team-shareable.

Agent Teams enable parallel work where a lead agent decomposes tasks, spawns subagents with specific roles, and reconciles outputs. This addresses the context window problem: each subagent maintains context only for its domain. MCP tools are inherited from parent conversations by default.

### Codex CLI and Gemini CLI introduce competing patterns

OpenAI's Codex CLI (written in Rust) uses a **Submission Queue / Event Queue pattern** for async client-agent communication, with three UI implementations (TUI, exec mode, App Server) sharing the same core. Notably, Codex itself can **run as an MCP server** exposing `codex()` and `codex-reply()` tools — enabling it to be composed into larger agent systems. They initially tried a pure MCP approach for IDE integration but found maintaining MCP semantics "proved difficult" and evolved a custom JSON-RPC protocol optimized for streaming progress, tool use, and diffs.

Google's Gemini CLI leverages its **1M token context window** to reduce the need for sub-agents entirely. Its MCP integration has the most sophisticated conflict resolution (first registration wins unprefixed names; subsequent servers get prefixed), supports OAuth 2.0 for remote servers, and auto-discovers MCP resources via `@` syntax.

### Vibe coding meets scientific rigor

Andrej Karpathy coined "vibe coding" in February 2025 — fully accepting AI-generated code without deep understanding. By February 2026, he evolved this to **"agentic engineering"**: claiming agent leverage without compromising software quality. The distinction matters enormously for science.

Peer-reviewed applications have validated the approach with guardrails. A proteomics case study in the *Journal of Proteome Research* demonstrated that AI-generated analysis code produced results **"numerically indistinguishable"** from reference pipelines. A *BioData Mining* paper positioned vibe coding as a new paradigm for biomedical software development. But the risks are real: CodeRabbit found AI co-authored code had **1.7× more "major" issues**, and commercial AI models suggest non-existent packages 5.2% of the time.

For scientific computing MCP servers, the implication is clear: enable rapid exploration and prototyping through natural language interaction, but build in **automated validation against reference datasets, reproducibility tracking, and code provenance documentation** as first-class features.

---

## Conclusion

The design space for a scientific computing MCP server sits at the intersection of several maturing technologies. The MCP protocol itself provides the standardized transport, tool definition, and discovery mechanisms — with new features like Tasks (for long-running HPC jobs), elicitation (for confirming expensive operations), MCP Apps (for interactive visualization), and output schemas (for machine-readable results) directly addressing scientific computing needs.

The critical architectural insight from context engineering research is that **every token is a bet against accuracy**. Scientific tool outputs — simulation logs, molecular coordinates, spectral data — are inherently voluminous. The winning patterns are programmatic tool calling (processing data in sandboxes before returning summaries), progressive tool discovery (defer_loading with Tool Search), and tiered context management (Google ADK's session/memory/artifact separation).

Argonne's thin-adapter approach — wrapping existing services like Globus Compute, SLURM, and domain databases with lightweight MCP interfaces — provides the clearest architectural template. The Rhea pattern of using RAG to dynamically generate tool definitions from large catalogs is particularly compelling for platforms spanning multiple scientific domains.

The cognitive science foundations point toward an agent that maintains **Zettelkasten-style interconnected memory** (A-MEM), follows the **scientific method's hypothesis-experiment-analysis-revision cycle** as its core workflow, and uses **verbal self-reflection** (Reflexion) to accumulate domain expertise across sessions. The ACE framework's "evolving playbook" concept — where the system prompt grows to incorporate accumulated strategies and pitfalls — is directly applicable to a platform where researchers iteratively refine computational approaches.

The single most important design principle: **build the simplest system that works, and let the agent generate the complexity.** As Manus demonstrated through five framework rebuilds, and as models continue to improve, the optimal harness gets simpler over time. A well-designed MCP server with clear tool descriptions, structured outputs, and thoughtful context management will serve researchers better than an over-engineered orchestration layer.