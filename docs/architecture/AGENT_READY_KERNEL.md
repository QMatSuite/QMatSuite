# Agent-Ready Kernel Design Specification

**Version**: 0.1
**Date**: 2025-01-19
**Status**: Research & Design Phase

---

## Executive Summary

This document synthesizes insights from a deep analysis of four external repositories (LangSim, AiiDA-core, material_agent, VASPilot) to propose design principles for making QMatSuite an "agent-ready backend" for LLM-driven computational materials science workflows.

---

# PART A: Unbiased Repository Analysis

## 1. LangSim

### A1. What is this project, really?

**One-paragraph summary**: LangSim is a Python framework that provides LLM-callable tools for atomistic simulations, wrapping existing codes (ASE, phonopy, LAMMPS, mace-mp) with Jupyter magic commands and structured tool interfaces. It bridges natural language interactions with computational materials science by exposing simulation capabilities as typed, tool-callable functions that an LLM agent can invoke.

**Problem being solved**: Researchers want to use LLMs to drive simulation workflows but existing simulation codes have complex, unstructured APIs that are hard for LLMs to use reliably. LangSim provides a curated set of well-documented, structured tools.

**Target users**: Researchers who want to explore materials simulations through conversational AI interfaces, particularly in Jupyter notebook environments.

**Execution model**: Library + Jupyter magics + tool wrappers. Not a standalone service or CLI, but rather a toolkit meant to be used within LLM agent frameworks (agno, langchain, etc.).

### A2. How does it work internally?

**Directory structure**:
```
langsim/
├── __init__.py          # Public API exports
├── llm.py               # LLM interaction utilities
├── magics.py            # Jupyter magic commands (%atomistic, etc.)
├── tools/               # Tool implementations
│   ├── simulation_atomistics.py   # Core simulation tools
│   └── __init__.py
├── examples/            # Example notebooks
└── tutorial/            # Tutorial materials
```

**Core data structures**:
- **ase.Atoms**: Primary structure representation (borrowed from ASE)
- **Tool function signatures**: Typed Python functions with docstrings that become LLM tool schemas
- No custom "unit of work" abstraction - tools are stateless functions

**Task representation**: Individual tool calls. No pipelines, graphs, or workflows built-in. The LLM agent (external) handles orchestration.

**Artifacts/caching**: Minimal. Tools operate on ephemeral in-memory data (Atoms objects, dicts). Results returned as structured dicts or file paths.

**Configuration**: Python function arguments. No YAML/JSON config system.

**Key files to read**:
- `/Users/hh7465/repo_research/LangSim/langsim/tools/simulation_atomistics.py:1-500` - Core tool implementations
- `/Users/hh7465/repo_research/LangSim/langsim/llm.py:1-200` - LLM client wrapper
- `/Users/hh7465/repo_research/LangSim/langsim/magics.py:1-300` - Jupyter integration
- `/Users/hh7465/repo_research/LangSim/langsim/__init__.py` - Public API surface
- `/Users/hh7465/repo_research/LangSim/README.md` - Usage patterns

### A3. From the perspective of an LLM agent

**Easiest/most delightful**:
- Clean, typed tool signatures with good docstrings
- Tools return structured dicts with clear field names
- Minimal setup required - just import and call
- Stateless design means no hidden state to track

**Awkward/fragile**:
- File path handling is implicit (tools write to working directory)
- No built-in provenance - what happened where is lost
- Error messages are Python exceptions, not structured
- No validation of tool sequences (agent can call tools in wrong order)

**Hallucination risks**:
- Material IDs (mp-xxx) - agent might hallucinate invalid IDs
- File paths - agent might reference non-existent files
- Parameter values - no bounds validation in tool signatures
- Element symbols - typos in element names pass through

**Tool-callable APIs** (structured I/O):
- `get_material_from_mp(material_id: str) -> dict` - Good
- `get_phonons(atoms: Atoms, supercell: list, **kwargs) -> dict` - Good
- `run_md(atoms: Atoms, **kwargs) -> Atoms` - Medium (Atoms object less structured)

**Non-tool-callable**:
- Jupyter magics (human-centric, not for programmatic use)

### A4. What would I improve?

1. **Add validation schemas for tool inputs** (location: `tools/simulation_atomistics.py`)
   - Use Pydantic models instead of loose kwargs
   - Add bounds checking for numerical parameters
   - Validate element symbols against periodic table

2. **Structured error responses** (location: `tools/*.py`)
   - Return `{"success": bool, "result": ..., "error": {...}}` instead of raising exceptions
   - Include error codes and suggested fixes

3. **Add provenance tracking** (new module: `provenance.py`)
   - Each tool call returns a trace_id
   - Optional logging to JSONL for audit trail

4. **File contract layer** (new module: `artifacts.py`)
   - Explicit artifact registry: what files a tool produces
   - Hash-based deduplication for expensive computations

---

## 2. AiiDA-core

### A1. What is this project, really?

**One-paragraph summary**: AiiDA is a comprehensive workflow engine for computational materials science that provides automatic provenance tracking, HPC job management, and data management through a PostgreSQL-backed object graph. It's designed for reproducibility and traceability, storing every computation in a directed acyclic graph where nodes are data/calculations and edges represent dependencies.

**Problem being solved**: Computational science has a reproducibility crisis. Researchers need to track what inputs led to what outputs, be able to restart failed calculations, and share workflows with confidence that they can be reproduced.

**Target users**: Research groups running large-scale HPC calculations who need rigorous provenance tracking and workflow management.

**Execution model**: Workflow engine with daemon process. Calculations are submitted to an engine that manages job scheduling, file transfer to/from HPC clusters, result parsing, and provenance recording.

### A2. How does it work internally?

**Directory structure** (src/aiida/):
```
src/aiida/
├── orm/                 # Object-Relational Mapping
│   ├── nodes/           # Node types (Data, Process, etc.)
│   │   ├── node.py      # Base Node class
│   │   ├── data/        # Data node types
│   │   └── process/     # Process node types
│   └── querybuilder.py  # Graph queries
├── engine/              # Workflow execution
│   ├── processes/       # Process implementations
│   │   ├── process.py   # Base Process
│   │   ├── calcjobs/    # CalcJob (external code execution)
│   │   └── workchains/  # WorkChain (workflow DAGs)
│   └── daemon/          # Background execution daemon
├── storage/             # Database backends
│   └── psql_dos/        # PostgreSQL + file repository
└── parsers/             # Output parsers
```

**Core data structures** (citations):
- **Node** (`src/aiida/orm/nodes/node.py:1-200`): Base class for all stored entities. Has UUID, label, description, attributes, extras. Immutable once stored.
- **Process** (`src/aiida/engine/processes/process.py:1-300`): Base class for computations. Defines input/output ports, execution logic.
- **CalcJob** (`src/aiida/engine/processes/calcjobs/calcjob.py:217-638`): External code execution (e.g., VASP, QE). Handles input generation, job submission, result retrieval.
- **WorkChain** (`src/aiida/engine/processes/workchains/workchain.py:1-200`): Composite workflows with conditional logic and error handling.

**Unit of work**: CalcJob or WorkChain instance
**Unit of state**: Node in the graph (immutable after storage)
**Unit of provenance**: Link between nodes (input/output relationships)

**Task representation**: Directed graph of Processes. WorkChains define steps as a spec with outline methods. CalcJobs are leaf nodes that run external codes.

**Artifacts**: Stored in file repository (content-addressed). FolderData nodes contain directories of files. RemoteData references files on HPC clusters.

**Caching**: Hash-based deduplication. If a CalcJob with identical inputs was already run, return cached result.

**Configuration**: YAML profiles + Python config objects + database. `~/.aiida/config.json` for global config.

**Key files to read**:
- `/Users/hh7465/repo_research/aiida-core/src/aiida/orm/nodes/node.py:1-300` - Core Node abstraction
- `/Users/hh7465/repo_research/aiida-core/src/aiida/engine/processes/process.py:1-400` - Process execution model
- `/Users/hh7465/repo_research/aiida-core/src/aiida/engine/processes/calcjobs/calcjob.py:217-638` - CalcJob implementation
- `/Users/hh7465/repo_research/aiida-core/src/aiida/storage/psql_dos/models/node.py:1-200` - Database schema
- `/Users/hh7465/repo_research/aiida-core/src/aiida/engine/processes/workchains/workchain.py:1-200` - Workflow definition

### A3. From the perspective of an LLM agent

**Easiest/most delightful**:
- `verdi` CLI is well-structured with clear subcommands
- QueryBuilder provides structured graph queries
- Typed port specifications make input requirements explicit
- Clear separation between "what to run" and "how to run it"

**Awkward/fragile**:
- Heavy abstraction layer - many concepts to understand (Node, Process, CalcJob, WorkChain, Group, Computer, Code)
- Database-centric design means agent must understand ORM patterns
- Python-based workflow definitions are hard to generate/modify programmatically
- Error messages often reference internal state (process states, node PKs)

**Hallucination risks**:
- Node PKs (agent might reference non-existent nodes)
- Process entry points (specific string identifiers like "quantumespresso.pw")
- Computer/Code names (must match database entries)
- Resource specifications (must match scheduler requirements)

**Tool-callable APIs**:
- `verdi process list` - Good (structured output)
- `verdi node show <PK>` - Good (structured node info)
- `verdi calcjob outputcat <PK>` - Good (file retrieval)
- `QueryBuilder` API - Good if agent can construct queries

**Non-tool-callable**:
- WorkChain definitions (Python code, not declarative)
- Port namespace specifications (complex nested structures)

### A4. What would I improve?

1. **Simplified "run this calculation" API** (new module: `simple_api.py`)
   - Single function: `run_dft(structure_file, parameters, computer) -> job_id`
   - Hide CalcJob/WorkChain complexity for simple cases

2. **JSON-based workflow definitions** (enhancement to WorkChain)
   - Allow workflows to be defined in JSON/YAML instead of Python
   - Enable programmatic workflow generation by agents

3. **Structured error catalogs** (new module: `errors.py`)
   - Error codes with machine-readable descriptions
   - Suggested fixes as structured data

4. **Status query endpoint** (enhancement to daemon)
   - Single endpoint: `GET /status/{job_id}` returning structured JSON
   - Include progress percentage, estimated time remaining

---

## 3. material_agent

### A1. What is this project, really?

**One-paragraph summary**: material_agent is a LangGraph-based multi-agent system specifically designed for DFT (Quantum ESPRESSO) workflow automation. It implements a "Plan-and-Execute" pattern with specialized agents (DFT_Agent, HPC_Agent) coordinated by a Supervisor, using a shared "canvas" for intermediate state and structured tool functions for QE input generation, job submission, and result analysis.

**Problem being solved**: Running DFT workflows requires expertise in both computational chemistry (setting up calculations) and HPC operations (job submission, resource allocation). This project attempts to automate both with specialized AI agents.

**Target users**: Researchers who want to automate DFT workflow creation and execution without deep expertise in either domain.

**Execution model**: Agent runtime using LangGraph. A supervisor agent creates plans, then delegates steps to worker agents (DFT_Agent, HPC_Agent) who execute tools and report back.

### A2. How does it work internally?

**Directory structure**:
```
src/
├── tools.py         # Tool implementations (QE input generation, HPC submission)
├── planNexe2.py     # LangGraph workflow definition
├── prompt.py        # Agent system prompts
├── var.py           # Global variables (working directory, etc.)
└── __init__.py
```

**Core data structures** (citations):
- **PlanExecute** (`src/planNexe2.py:45-50`): TypedDict state for workflow: `{input, plan, past_steps, response, next}`
- **myStep** (`src/planNexe2.py:37-43`): Pydantic model for plan steps: `{step: str, agent: str}`
- **Plan** (`src/planNexe2.py:52-62`): List of myStep objects
- **Canvas**: Shared dict stored in global variable (`var.myCANVAS`) for inter-agent communication

**Unit of work**: A "step" in the plan (delegated to an agent)
**Unit of state**: The `PlanExecute` state dict passed between graph nodes
**Unit of provenance**: Append to `his.txt` file (plain text log)

**Task representation**: LangGraph StateGraph with conditional edges. Supervisor creates Plan, workers execute steps, results flow back to supervisor.

**Artifacts**: Files written to working directory. QE inputs (.pwi files), job lists (job_list.json), outputs (.pwo files).

**Configuration**: Python dict passed to `create_planning_graph()` with API keys and settings.

**Key files to read**:
- `/Users/hh7465/repo_research/material_agent/src/planNexe2.py:260-421` - Graph construction and agent nodes
- `/Users/hh7465/repo_research/material_agent/src/tools.py:1-400` - Tool implementations (inspect_my_canvas, write_QE_script, etc.)
- `/Users/hh7465/repo_research/material_agent/src/prompt.py:1-180` - Agent prompts defining capabilities
- `/Users/hh7465/repo_research/material_agent/README.md` - Architecture overview

### A3. From the perspective of an LLM agent

**Easiest/most delightful**:
- Clear capability declarations in prompts (what each agent can do)
- Structured tool return values (mostly dicts)
- Canvas concept for shared state is intuitive
- Plan structure is explicit (list of steps with assigned agents)

**Awkward/fragile**:
- Global state via `var.py` - not thread-safe, hard to reason about
- `status.txt` file for pause/resume - fragile synchronization
- `his.txt` as plain text log - not machine-parseable
- Canvas is unstructured dict - no schema validation
- Hard-coded job submission scripts in prompts

**Hallucination risks**:
- Pseudopotential paths (agent must find correct files)
- HPC partition names (hard-coded in prompts)
- QE parameter values (no validation)
- File paths in canvas (agent might reference non-existent entries)

**Tool-callable APIs**:
- `inspect_my_canvas()` - Good (returns canvas state)
- `write_QE_script_w_ASE(...)` - Medium (complex parameters)
- `submit_and_monitor_job(...)` - Good (returns job status)

**Non-tool-callable**:
- Agent prompts (embedded in code)
- Graph structure (hard-coded in Python)

### A4. What would I improve?

1. **Typed Canvas with schema** (enhance `tools.py`)
   - Define Pydantic model for canvas entries
   - Validate before write, auto-complete on read

2. **Structured history** (replace `his.txt` with `history.jsonl`)
   - Machine-readable event log
   - Include timestamps, agent, action, inputs, outputs

3. **Configuration externalization** (new `config.yaml`)
   - Move HPC specs out of prompts
   - Allow runtime configuration without code changes

4. **Tool input validation** (enhance all tools)
   - Use Pydantic for tool parameters
   - Validate element symbols, parameter ranges

---

## 4. VASPilot

### A1. What is this project, really?

**One-paragraph summary**: VASPilot is a CrewAI-based multi-agent system with an MCP (Model Context Protocol) server that exposes VASP calculation tools. It provides structured tool interfaces for VASP relaxation/SCF/NSCF calculations, job status monitoring, result plotting, and Materials Project structure search, all backed by a SQLite database for calculation tracking.

**Problem being solved**: VASP calculations require careful setup (INCAR, KPOINTS, POTCAR) and monitoring. VASPilot provides a structured API for agents to submit and track calculations without needing to understand VASP file formats.

**Target users**: Researchers using VASP who want AI-assisted workflow automation.

**Execution model**: CrewAI multi-agent system + FastMCP server. The CrewAI crew handles high-level planning while MCP tools handle VASP-specific operations.

### A2. How does it work internally?

**Directory structure**:
```
src/vaspilot/
├── crew/
│   ├── vasp_crew.py     # CrewAI crew definition
│   ├── embedding.py     # Custom embedder
│   └── local_llm.py     # LLM wrapper
├── tools/
│   ├── mcp/
│   │   ├── mcp_server.py      # FastMCP server with VASP tools
│   │   ├── vasp_calculate.py  # VASP submission functions
│   │   ├── struct_tools.py    # Structure manipulation
│   │   └── sqlite_database.py # Calculation database
│   ├── wait_calc_tool.py      # Job monitoring
│   └── json_rag_tool.py       # RAG search
└── configs/                    # YAML configurations
```

**Core data structures** (citations):
- **Calculation Record** (SQLite table via `sqlite_database.py`): `{calculation_id, slurm_id, calc_type, calculate_path, status, ...results}`
- **LLM-friendly result** (`mcp_server.py:59-88`): Structured dict with status, error, results appropriate for LLM consumption
- **VaspCrew** (`crew/vasp_crew.py:21-176`): CrewAI Crew with manager agent and worker agents

**Unit of work**: A calculation submission (relaxation, SCF, NSCF)
**Unit of state**: SQLite database record + VASP output files
**Unit of provenance**: Database records with timestamps, job IDs, paths

**Task representation**: CrewAI hierarchical process. Manager delegates to workers. Workers use MCP tools.

**Artifacts**: VASP input/output files in calculation directories. Results (structures, energies, bands) stored as pickled objects in SQLite.

**Configuration**: YAML config files for MCP server, agents, LLM settings.

**Key files to read**:
- `/Users/hh7465/repo_research/VASPilot/src/vaspilot/tools/mcp/mcp_server.py:89-470` - MCP tool implementations
- `/Users/hh7465/repo_research/VASPilot/src/vaspilot/tools/mcp/vasp_calculate.py:15-436` - VASP submission logic
- `/Users/hh7465/repo_research/VASPilot/src/vaspilot/crew/vasp_crew.py:21-176` - CrewAI setup
- `/Users/hh7465/repo_research/VASPilot/README.md` - Overview and usage

### A3. From the perspective of an LLM agent

**Easiest/most delightful**:
- MCP tools have excellent docstrings with parameter descriptions
- `extract_llm_friendly_result()` function specifically formats results for LLM consumption
- UUID-based calculation tracking (no need to manage file paths)
- Structured return values with success/error/status fields
- Plot generation tool with clear examples in docstring

**Awkward/fragile**:
- SQLite with pickled pymatgen objects - not easily queryable
- Hardcoded VASP defaults in settings dict
- SLURM-specific job submission (not portable)
- Some Chinese comments make code harder to understand

**Hallucination risks**:
- calculation_id UUIDs (agent must track from previous calls)
- POTCAR mapping (element symbols must be exact)
- INCAR tag names (must match VASP documentation)
- Structure file paths (must exist on filesystem)

**Tool-callable APIs** (excellent structured I/O):
- `vasp_relaxation(structure_path, incar_tags, kpoint_num, potcar_map)` - Excellent
- `check_calculation_status(calculation_ids)` - Excellent
- `python_plot(calculation_ids, plot_code, description)` - Good (allows custom plotting)
- `search_materials_project(search_criteria, limit)` - Excellent

**Non-tool-callable**:
- CrewAI agent definitions (Python code)

### A4. What would I improve?

1. **Portable job submission** (enhance `vasp_calculate.py`)
   - Abstract scheduler interface (SLURM, PBS, local)
   - Job submission returns structured status regardless of scheduler

2. **Query-able result storage** (enhance `sqlite_database.py`)
   - Store results as JSON instead of pickle
   - Enable SQL queries on result fields (energy, band_gap, etc.)

3. **Input validation layer** (new `validation.py`)
   - Validate INCAR tags against known VASP parameters
   - Validate POTCAR element symbols
   - Validate structure file before submission

4. **Calculation lineage** (enhance database schema)
   - Store `restart_id` chain explicitly
   - Enable querying "all calculations derived from X"

---

# PART B: Cross-Repository Comparison

## B1. Comparison Table

| Dimension | LangSim | AiiDA-core | material_agent | VASPilot |
|-----------|---------|------------|----------------|----------|
| **State & SSOT** | None (stateless tools) | PostgreSQL graph database | Global Python dict (canvas) + files | SQLite database + files |
| **Provenance/Audit Trail** | None | Full DAG with immutable nodes | Text file log (his.txt) | Database records with timestamps |
| **Tool Surface & Schema** | Typed Python functions | CLI + Python API | LangChain tools with docstrings | MCP tools with structured returns |
| **Determinism & Reproducibility** | Low (no state tracking) | High (hash-based caching, full inputs stored) | Low (global state, mutable canvas) | Medium (UUID tracking, but paths volatile) |
| **Error Semantics & Recovery** | Python exceptions | Exit codes + structured error nodes | Agent retries, text logs | Success/error dict, status polling |
| **Extensibility** | Add Python functions | Plugin system (entry points) | Add tools + prompts | Add MCP tools |
| **Human UX vs Agent UX** | Agent-first (tools) | Human-first (verdi CLI) | Agent-first (prompts/tools) | Agent-first (MCP tools) |

## B2. Minimum Viable Agent-Ready Backend Primitives

Based on analysis, the top 5 kernel primitives for agent-usability:

### 1. **Structured Calculation Submission**

**Purpose**: Submit a calculation with validated, typed inputs; receive a tracking ID.

**Inputs**:
```yaml
structure: StructureSpec  # Validated crystal structure
parameters: EngineParams  # Typed parameter dict with validation
compute_config: ComputeSpec  # Resources, queue, etc.
```

**Outputs**:
```yaml
calculation_id: str  # UUID for tracking
status: "submitted" | "failed"
error: Optional[ErrorSpec]  # Structured error if failed
```

**Validation**: Schema validation of all inputs before submission. Reject with specific error codes if invalid.

### 2. **Calculation Status Query**

**Purpose**: Check calculation status without needing to understand file system or database internals.

**Inputs**:
```yaml
calculation_ids: List[str]  # UUIDs to check
```

**Outputs**:
```yaml
results: Dict[str, StatusSpec]
# StatusSpec: {status, progress_pct, error, results_available}
```

**Validation**: Return "not_found" status for unknown IDs (don't raise exceptions).

### 3. **Result Extraction**

**Purpose**: Get specific results from completed calculations in structured format.

**Inputs**:
```yaml
calculation_id: str
result_type: "energy" | "structure" | "bands" | "dos" | "forces" | ...
format: "json" | "file_path"
```

**Outputs**:
```yaml
value: Any  # Typed result value
unit: str  # Physical unit
status: "ok" | "not_available" | "error"
```

**Validation**: Return "not_available" for result types not computed by the calculation type.

### 4. **Schema Discovery**

**Purpose**: Allow agent to discover available calculation types, parameters, and their constraints.

**Inputs**:
```yaml
query: "calculation_types" | "parameters" | "presets"
filter: Optional[Dict]  # e.g., {"engine": "qe"}
```

**Outputs**:
```yaml
items: List[SchemaItem]
# SchemaItem: {name, description, parameters: List[ParamSpec], constraints}
```

**Validation**: Return empty list for unknown queries (don't raise).

### 5. **Atomic Mutation with Validation**

**Purpose**: Modify calculation parameters with validation before persistence.

**Inputs**:
```yaml
calculation_id: str
mutations: List[Mutation]
# Mutation: {path: str, op: "set"|"delete", value: Any}
dry_run: bool  # If true, validate only
```

**Outputs**:
```yaml
valid: bool
errors: List[ValidationError]  # Empty if valid
applied: bool  # True if mutations were persisted
```

**Validation**: All mutations validated against schema. Either all apply or none apply (atomic).

## B3. Smells and Failure Modes

Top 10 design traps for LLM-driven simulation workflows:

### 1. **Hidden Truth in Memory**
- **Description**: Calculation state exists only in Python objects, not persisted.
- **Example**: material_agent's `var.myCANVAS` global dict
- **Mitigation**: All state changes must be persisted before returning to agent.

### 2. **Untyped Configuration**
- **Description**: Parameters passed as `Dict[str, Any]` without validation.
- **Example**: LangSim's `**kwargs` in tool functions
- **Mitigation**: Use Pydantic models or JSON Schema for all inputs.

### 3. **Stringly-Typed Identifiers**
- **Description**: Using arbitrary strings for IDs that could be hallucinated.
- **Example**: AiiDA's node PKs, material_agent's canvas keys
- **Mitigation**: Use UUIDs, provide lookup tools, validate before use.

### 4. **Implicit File Path Contracts**
- **Description**: Tools expect files at specific paths without declaring them.
- **Example**: material_agent's pseudopotential path detection
- **Mitigation**: Explicit artifact manifests; tools declare inputs/outputs.

### 5. **Silent Failures**
- **Description**: Operations fail without clear error signals.
- **Example**: VASPilot's empty try/except blocks
- **Mitigation**: Always return structured error with code and message.

### 6. **State Drift Between Sessions**
- **Description**: Agent expects state from previous session that's gone.
- **Example**: material_agent's in-memory canvas cleared on restart
- **Mitigation**: All state persisted; session resume loads from disk.

### 7. **Unstructured Provenance**
- **Description**: Audit trail exists but isn't machine-queryable.
- **Example**: material_agent's `his.txt` text log
- **Mitigation**: JSONL or database for provenance; structured queries.

### 8. **Brittle String Parsing**
- **Description**: Extracting information by parsing human-readable text.
- **Example**: VASPilot parsing SLURM output with string splitting
- **Mitigation**: Use structured APIs; parse once at boundary.

### 9. **Missing Schema Evolution**
- **Description**: No versioning for data formats; old data breaks new code.
- **Example**: LangSim has no schema at all
- **Mitigation**: Schema version field; migration path for old formats.

### 10. **Global Implicit Dependencies**
- **Description**: Tools depend on global configuration not passed as input.
- **Example**: material_agent's `var.my_WORKING_DIRECTORY`
- **Mitigation**: All dependencies explicit in function signature.

---

# PART C: QMatSuite Assessment and Design Inspirations

## C1. QMatSuite Current Architecture

### Documents Read:
- `/Users/hh7465/QMatSuite/docs/ARCHITECTURE_OVERVIEW.md` - High-level system architecture
- `/Users/hh7465/QMatSuite/docs/HISTORY_DESIGN.md` - Provenance and history system
- `/Users/hh7465/QMatSuite/docs/design/ir_step_engine_v0.md` - Parameter and step generalization
- `/Users/hh7465/QMatSuite/src/quantumvitas/core/models.py` - Data models
- `/Users/hh7465/QMatSuite/src/quantumvitas/calculation/runner.py` - Calculation execution
- `/Users/hh7465/QMatSuite/src/quantumvitas/engine/base.py` - Engine interface

### Current Kernel Philosophy:

**SSOT Policy (calculation.yaml + step.yaml)**:
- `step.yaml` is the ONLY on-disk SSOT for execution ("machine code")
- `calculation.yaml` contains step list with ULID references
- Presets and IR are runtime concepts, not persisted in step files
- All configuration flows through the three-tier system: Preset → IR → step.yaml

**Present Tense vs History**:
- Present tense = disk state (YAML files)
- History = append-only `.history/` with immutable events
- Run revisions capture digests at run completion
- Pins are only allowed for most recent run

**Manifest/Incremental Semantics**:
- Incremental run mode skips unchanged steps
- Each step has fingerprint for change detection
- Runner handles step0 (pseudo preparation) before execution

**Engine Backends & Materialization**:
- `EngineRegistry` maps step types to engine implementations
- Each engine implements `run_step(step, working_dir) -> StepResult`
- QE, PySCF, ORCA, VASP engines follow common interface

**AnalysisObject Direction**:
- Raw outputs → parser → engine-agnostic analysis objects
- Optional `.analysis` cache for parsed results
- Digests computed from analysis objects

## C2. Strengths and Weaknesses Relative to the Four Repos

### What QMatSuite Already Does Better:

1. **Clean SSOT hierarchy**: Three-tier parameter system (Preset → IR → step.yaml) is more principled than any of the four repos.

2. **Structured history with schema**: `.history/` with typed events and run revisions is more rigorous than material_agent's text logs.

3. **Engine abstraction**: Clean engine interface with registry is better organized than VASPilot's mixed MCP/calculation code.

4. **Incremental semantics**: Fingerprint-based change detection is more sophisticated than any of the four repos.

5. **ULID-based resource management**: Consistent ID system is better than AiiDA's mixed PK/UUID approach.

### Where QMatSuite is Behind or Missing Primitives:

1. **No MCP/tool-calling surface**: Unlike VASPilot, no structured tool interface for external agents.

2. **No schema discovery API**: Agent cannot query "what parameters are valid for SCF?"

3. **Limited structured error handling**: Errors are Python exceptions, not structured responses.

4. **No calculation status polling**: Unlike VASPilot's `check_calculation_status`, no structured status API.

5. **History not queryable**: Events are append-only JSONL but no query interface.

### Best Comparators by Subsystem:

| QMatSuite Subsystem | Best Comparator | Why |
|---------------------|-----------------|-----|
| Provenance/History | AiiDA | Both have immutable audit trails; AiiDA's graph model more powerful |
| Tool Surface | VASPilot | VASPilot's MCP tools are exactly what agents need |
| Parameter System | None | QMatSuite's three-tier is most sophisticated |
| Engine Abstraction | LangSim | Both provide clean tool abstractions for simulation |
| Workflow Orchestration | material_agent | Plan-and-execute pattern for complex workflows |

## C3. Concrete Design Inspirations

### Inspiration 1: MCP Tool Surface for Core Operations

**Problem for agents + humans**: No structured API for agent tool-calling. Agents must go through CLI or daemon RPC which isn't designed for tool schemas.

**Minimal interface**:
```yaml
# Tool: submit_calculation
inputs:
  project_path: str  # Path to project
  calculation_id: str  # Optional; creates new if not provided
  structure_id: str  # ULID of structure
  workflow: str  # "scf", "scf-nscf-bands", etc.
  preset: Dict[str, str]  # {"precision": "high", "magnetism": "collinear"}
outputs:
  calculation_id: str
  job_id: str
  status: "submitted" | "validation_error"
  errors: List[ValidationError]
```

**Validation/guardrails**:
- Validate structure_id exists
- Validate preset values against allowed enums
- Validate workflow against registered workflows

**SSOT + History fit**:
- Tool creates calculation.yaml and step.yaml files (SSOT)
- Run start recorded in history
- Job ID tracked in daemon

**Host module**: New `src/quantumvitas/mcp/` package with FastMCP server

---

### Inspiration 2: Structured Status Query

**Problem**: Agents need to check calculation status without parsing logs.

**Minimal interface**:
```yaml
# Tool: get_calculation_status
inputs:
  calculation_ids: List[str]
outputs:
  results: Dict[str, CalculationStatus]

# CalculationStatus schema:
status: "pending" | "running" | "success" | "failed" | "cancelled"
progress:
  total_steps: int
  completed_steps: int
  current_step: Optional[str]
result_summary:  # Only if success
  total_energy: Optional[float]
  fermi_energy: Optional[float]
  converged: bool
error_summary: Optional[str]  # Only if failed
```

**Validation**: Return `{"status": "not_found"}` for unknown IDs.

**SSOT + History fit**: Read from step status files + history run_revision.json. Status is derived, not stored separately.

**Host module**: `src/quantumvitas/mcp/status.py`

---

### Inspiration 3: Schema Discovery Endpoint

**Problem**: Agent doesn't know what parameters are valid, what presets exist, what workflows are available.

**Minimal interface**:
```yaml
# Tool: discover_schema
inputs:
  query_type: "workflows" | "presets" | "step_types" | "ir_parameters"
  filter: Optional[Dict]  # e.g., {"engine": "qe"}
outputs:
  items: List[SchemaItem]

# SchemaItem for workflow:
name: str  # "scf-nscf-bands"
description: str
steps: List[str]  # ["scf", "nscf", "bands_pw"]
required_inputs: List[str]  # ["structure"]
supported_presets: List[str]

# SchemaItem for ir_parameter:
name: str  # "ecutwfc"
description: str
physical_dimension: str  # "Energy"
unit: str  # "Ry"
type: str  # "float"
constraints: Dict  # {"min": 0, "typical_range": [20, 100]}
```

**Validation**: Always return valid JSON; empty list for unknown queries.

**SSOT + History fit**: Schema is read-only, derived from workflow registry and IR definitions. No SSOT impact.

**Host module**: `src/quantumvitas/mcp/discovery.py`

---

### Inspiration 4: Validated Parameter Mutation

**Problem**: Agent wants to change calculation parameters but might set invalid values.

**Minimal interface**:
```yaml
# Tool: mutate_parameters
inputs:
  calculation_id: str
  mutations:
    - path: "/steps/0/parameters/SYSTEM/ecutwfc"
      op: "set"
      value: 50.0
    - path: "/preset/precision"
      op: "set"
      value: "high"
  dry_run: bool  # If true, validate only
outputs:
  valid: bool
  validation_errors: List[ValidationError]
  applied: bool
  diff_preview: str  # Human-readable diff
```

**Validation**:
- Path must exist or be creatable
- Value must pass IR parameter validation
- Preset values must be valid enum members

**SSOT + History fit**:
- Mutations apply to step.yaml (SSOT)
- Edit event recorded in history
- History captures old_value and new_value

**Host module**: `src/quantumvitas/mcp/mutations.py`

---

### Inspiration 5: Result Extraction with Format Options

**Problem**: Agent needs specific results (energy, structure, bands) in structured format.

**Minimal interface**:
```yaml
# Tool: extract_result
inputs:
  calculation_id: str
  step_id: Optional[str]  # Latest if not specified
  result_type: "energy" | "structure" | "bands" | "dos" | "forces" | "stress"
  format: "value" | "analysis_object" | "file_path"
outputs:
  status: "ok" | "not_computed" | "parse_error"
  value: Any  # Depends on result_type and format
  unit: Optional[str]
  metadata: Dict
```

**Validation**: Return `{"status": "not_computed"}` if result type not applicable to step type.

**SSOT + History fit**:
- Results are derived from raw outputs (not SSOT)
- May use .analysis cache
- Read-only operation; no SSOT mutation

**Host module**: `src/quantumvitas/mcp/results.py`

---

### Inspiration 6: History Query Interface

**Problem**: Agent cannot ask "show me all runs for calculation X" or "what changed between runs?"

**Minimal interface**:
```yaml
# Tool: query_history
inputs:
  project_path: str
  query_type: "list_runs" | "run_detail" | "diff_runs" | "list_edits"
  filters:
    calculation_id: Optional[str]
    run_id: Optional[str]
    run_id_a: Optional[str]  # For diff
    run_id_b: Optional[str]
    since: Optional[datetime]
outputs:
  # For list_runs:
  runs: List[RunSummary]
  # For run_detail:
  run: RunRevision
  # For diff_runs:
  parameter_changes: List[ParameterDiff]
  result_changes: Dict[str, ResultDiff]
```

**Validation**: Return empty results for invalid queries.

**SSOT + History fit**: Pure read from .history/. No SSOT mutation.

**Host module**: `src/quantumvitas/mcp/history_query.py`

---

### Inspiration 7: Artifact Manifest

**Problem**: Agent doesn't know what files a calculation produces or where they are.

**Minimal interface**:
```yaml
# Tool: list_artifacts
inputs:
  calculation_id: str
  step_id: Optional[str]
outputs:
  artifacts: List[Artifact]

# Artifact schema:
name: str  # "bands.dat"
artifact_type: "input" | "output" | "log" | "checkpoint"
path: str  # Relative path from calculation dir
size_bytes: int
created_at: datetime
content_hash: Optional[str]  # SHA256 for outputs
```

**Validation**: Filter to known artifact types; don't expose raw directory listing.

**SSOT + History fit**: Artifacts are raw files (not SSOT). Manifest is derived on-demand.

**Host module**: `src/quantumvitas/mcp/artifacts.py`

---

### Inspiration 8: Preset Detection and Suggestion

**Problem**: Agent wants to know "what preset is this calculation using?" or "what preset should I use for metals?"

**Minimal interface**:
```yaml
# Tool: detect_preset
inputs:
  calculation_id: str
outputs:
  detected: Dict[str, str]  # {"precision": "high", "magnetism": "noncollinear"}
  confidence: Dict[str, float]  # {"precision": 0.95, "magnetism": 1.0}
  unknown_parameters: List[str]  # Parameters not covered by presets

# Tool: suggest_preset
inputs:
  material_type: "metal" | "insulator" | "semiconductor" | "magnetic"
  accuracy: "screening" | "standard" | "high"
outputs:
  suggested: Dict[str, str]
  rationale: Dict[str, str]  # Why each preset was chosen
```

**Validation**: Material type enum validation; return best-effort for unknown types.

**SSOT + History fit**: Detection reads from step.yaml (SSOT). Suggestion is advisory, not persisted.

**Host module**: `src/quantumvitas/mcp/presets.py`

---

## C4. Design Document

*This section is the design document itself, synthesized above.*

---

## Problem Statement

QMatSuite has a sophisticated calculation management system with clean SSOT principles and provenance tracking, but lacks a structured API surface optimized for LLM agent tool-calling. External agents (like Claude, GPT, or custom LangGraph systems) need:

1. **Typed tool interfaces** with JSON Schema descriptions
2. **Structured responses** with consistent success/error patterns
3. **Schema discovery** to understand available operations
4. **Validation feedback** before operations are executed
5. **Status polling** without parsing logs

## Non-Goals

1. **Full AiiDA-style workflow DAGs**: QMatSuite's step-based model is sufficient; no need for arbitrary graphs.
2. **Multi-tenant service deployment**: Agent-ready API is local-first; remote access is future work.
3. **Custom agent framework**: Use existing frameworks (LangGraph, CrewAI) with QMatSuite as backend.
4. **Real-time streaming**: Status polling is sufficient; no WebSocket requirements.
5. **GUI changes**: Agent API is backend-only; GUI continues using existing daemon RPC.

## Core Primitives / Tool Surface

### Primary Tools

| Tool | Purpose | Input Schema | Output Schema |
|------|---------|--------------|---------------|
| `submit_calculation` | Start new calculation | SubmitInput | SubmitOutput |
| `get_calculation_status` | Check status | StatusInput | StatusOutput |
| `extract_result` | Get specific results | ResultInput | ResultOutput |
| `discover_schema` | Query available operations | DiscoveryInput | DiscoveryOutput |
| `mutate_parameters` | Change parameters | MutationInput | MutationOutput |
| `query_history` | Search provenance | HistoryInput | HistoryOutput |
| `list_artifacts` | List produced files | ArtifactInput | ArtifactOutput |
| `detect_preset` | Identify current presets | DetectInput | DetectOutput |

### Schema Sketch (Pydantic-style)

```python
class SubmitInput(BaseModel):
    project_path: str
    structure_id: str
    workflow: str
    presets: Dict[str, str] = {}
    parameter_overrides: Dict[str, Any] = {}

class SubmitOutput(BaseModel):
    calculation_id: str
    job_id: str
    status: Literal["submitted", "validation_error"]
    errors: List[ValidationError] = []

class CalculationStatus(BaseModel):
    status: Literal["pending", "running", "success", "failed", "cancelled", "not_found"]
    progress: Optional[ProgressInfo]
    result_summary: Optional[ResultSummary]
    error_summary: Optional[str]
```

## Provenance Requirements

**What must be recorded**:
- All tool invocations with inputs and outputs (new: `tool_call` event type)
- All parameter mutations (existing: `edit` event type)
- All run starts and completions (existing: `run_started`, `run_finished`)
- Schema version for all persisted data

**Where it goes**:
- Tool invocations → `.history/events.jsonl`
- Parameter values → `step.yaml` (SSOT)
- Run details → `.history/runs/{run_id}/run_revision.json`
- Artifacts → Calculation `raw/` directory (not history)

## Safety & Determinism Constraints

### Validation Rules

1. **All inputs validated before mutation**: `dry_run` mode available for all mutating operations.
2. **Preset values must be enum members**: No arbitrary strings.
3. **IR parameters validated against schema**: Type, bounds, physical dimension.
4. **Structure IDs must exist**: No dangling references.

### Locking

1. **Per-calculation file lock**: Prevent concurrent mutations to same calculation.
2. **Atomic YAML writes**: Write to temp file, then rename.
3. **History append-only**: No lock needed (append is atomic for JSONL).

### Reproducibility

1. **All inputs captured**: Tool call events include full input dict.
2. **Random seeds explicit**: If any operation uses randomness, seed must be input.
3. **Engine versions recorded**: Run revision includes engine version.

## How External Agents Interact

### Mode 1: MCP Server (Recommended)

FastMCP server exposes all tools via Model Context Protocol.

```bash
# Start server
python -m quantumvitas.mcp.server --port 8080

# Agent connects via MCP client
# Tools available: submit_calculation, get_calculation_status, etc.
```

### Mode 2: CLI with JSON Output

Each tool has CLI equivalent with `--json` flag.

```bash
qv agent submit-calculation --json \
  --project . \
  --structure-id 01HXYZ... \
  --workflow scf \
  --preset precision=high

# Returns JSON: {"calculation_id": "...", "status": "submitted", ...}
```

### Mode 3: Copy/Paste (Minimal)

For agents without direct API access, tools can output copy-pasteable commands.

```yaml
# Agent requests:
"Generate the command to submit an SCF calculation for structure 01HXYZ"

# Tool returns:
command: "qv run --calc my_calc --step scf"
expected_output: "Started job {job_id}. Check status with: qv status {job_id}"
```

## Mapping from External Repos

### From LangSim
- **Lesson**: Typed tool functions with good docstrings are essential.
- **Applied**: All MCP tools have Pydantic schemas and detailed descriptions.

### From AiiDA
- **Lesson**: Immutable provenance graph enables reproducibility queries.
- **Applied**: History events are append-only with structured schemas.
- **Citation**: `/Users/hh7465/repo_research/aiida-core/src/aiida/orm/nodes/node.py` (immutable Node model)

### From material_agent
- **Lesson**: Canvas/shared state pattern useful for multi-step workflows.
- **Applied**: Calculation state is persisted (unlike global dict), but concept of "current context" for agents could be added.
- **Citation**: `/Users/hh7465/repo_research/material_agent/src/planNexe2.py:45-50` (PlanExecute state)

### From VASPilot
- **Lesson**: `extract_llm_friendly_result()` pattern is excellent.
- **Applied**: All tool outputs designed for LLM consumption with `status`, `error`, typed `result` fields.
- **Citation**: `/Users/hh7465/repo_research/VASPilot/src/vaspilot/tools/mcp/mcp_server.py:59-88`

## Open Questions / Risks

1. **MCP adoption**: MCP is new; may need fallback to REST or raw JSON-RPC.

2. **Tool proliferation**: How many tools before discovery becomes unwieldy? Consider tool categories.

3. **Long-running calculations**: Status polling works but may need event-based notification for very long jobs.

4. **Agent state management**: Should QMatSuite track "agent sessions" or leave that to external frameworks?

5. **Authentication**: MCP server currently trusts localhost. Multi-user scenario needs auth layer.

6. **Versioning**: How to handle API changes? Semantic versioning for tool schemas?

---

## Reading Map

For understanding the agent-ready kernel concept, read these QMatSuite files in order:

1. **Architectural Foundation**
   - `docs/ARCHITECTURE_OVERVIEW.md` - High-level system shape
   - `docs/HISTORY_DESIGN.md` - Provenance principles

2. **Core Data Models**
   - `src/quantumvitas/core/models.py` - CalculationModel, StepEntry
   - `src/quantumvitas/core/resources.py` - ResourceMeta, ULID handling

3. **Execution Layer**
   - `src/quantumvitas/calculation/runner.py` - CalculationRunner
   - `src/quantumvitas/engine/base.py` - Engine interface

4. **Parameter System**
   - `docs/design/ir_step_engine_v0.md` - Three-tier parameter model
   - `src/quantumvitas/presets/paramspace.py` - ParamSpace implementation

5. **Daemon API (Current)**
   - `src/quantumvitas/daemon/server.py` - JSON-RPC handlers
   - `docs/DAEMON_API_REFERENCE.md` - Existing RPC surface

6. **Future: Agent API**
   - `docs/architecture/AGENT_READY_KERNEL.md` (this document) - Design principles
   - `src/quantumvitas/mcp/` (to be created) - MCP tool implementations

---

*Document generated from repository research on 2025-01-19.*
