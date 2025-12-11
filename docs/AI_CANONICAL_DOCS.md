# Canonical Documentation for AI and Humans

This document lists the canonical documentation files that should be treated as the primary reference for understanding QuantumVITAS. These documents are authoritative, up-to-date, and cover the core topics needed to work with the codebase.

## Architecture & Design

### `docs/ARCHITECTURE.md`
- **Purpose**: High-level architectural overview of the Python v2 rewrite
- **Covers**: Layered structure, key concepts, project layout, ground rules
- **Tag**: `architecture`

### `docs/SCHEMA.md`
- **Purpose**: Complete schema specification for DAG + ID-only model
- **Covers**: Project/workflow/step/structure YAML formats, serialization behavior, backwards compatibility
- **Tag**: `schema`

## Core Features

### `docs/SNAPSHOTS.md`
- **Purpose**: Snapshot export and materialization behavior (Option B: Template with Fresh IDs)
- **Covers**: Export behavior, materialization with ULID regeneration, demo/reference features
- **Tag**: `snapshots`

### `docs/STANDALONE_QE.md`
- **Purpose**: Standalone QE execution mode (separate from DAG)
- **Covers**: CLI usage, file layout, implementation details, separation from project resources
- **Tag**: `standalone`

## APIs & Interfaces

### `docs/CLI_API_REFERENCE.md`
- **Purpose**: Comprehensive CLI command reference
- **Covers**: All `qv` commands with examples, selectors, overrides syntax
- **Tag**: `cli`

### `docs/DAEMON_API_REFERENCE.md`
- **Purpose**: JSON-RPC daemon interface for GUI
- **Covers**: Request/response format, all RPC methods, error handling
- **Tag**: `daemon`

### `docs/GUI_ARCHITECTURE.md`
- **Purpose**: Electron + React + TypeScript GUI architecture
- **Covers**: Technology stack, component structure, IPC handlers, state management
- **Tag**: `gui`

### `docs/GUI_DAEMON_API_MAPPING.md`
- **Purpose**: Mapping between GUI components and daemon endpoints
- **Covers**: Job submission, step detail retrieval, selector usage
- **Tag**: `gui`, `daemon`

## QE Engine

### `docs/QE_EXECUTABLE_DETECTION.md`
- **Purpose**: Automatic QE executable detection and path resolution
- **Covers**: Detection order, internal registry, cross-platform support
- **Tag**: `qe-engine`

### `docs/QE_MODULE_SUPPORT.md`
- **Purpose**: Supported QE modules and their purposes
- **Covers**: Module list, namelists, documentation links, detection methods
- **Tag**: `qe-engine`

### `docs/QE_MODULE_DOCUMENTATION.md`
- **Purpose**: QE module documentation links and metadata schema
- **Covers**: Runtime metadata via `quantumvitas.data.qe_metadata`, legacy v1 snapshot, tooling
- **Tag**: `qe-engine`
- **Note**: 
  - **`safe_load_metadata()` is the only runtime entry point for QE parameter metadata.**
  - **CLI/daemon code must never read `qe_module_parameters.json` directly.**
  - Runtime code should access QE metadata only through `quantumvitas.data.qe_metadata` helper functions (canonical interface)
  - Current metadata file: `src/quantumvitas/data/qe_module_parameters.json` (schema v2 with rich parameter map)
  - Legacy snapshot: `src/quantumvitas/data/qe_module_parameters.legacy.json` (frozen v1, used only by comparison tools)
  - Tools:
    - `tools/extract_qe_parameters_v1.py` (deprecated, v1 extractor)
    - `tools/extract_qe_parameters_v2.py` (current, v2 extractor with rich metadata)
    - `tools/compare_qe_parameter_maps.py` (schema diff, supports both v1 and v2)
  - All helper functions use `safe_load_metadata()` internally for consistent error handling

## Testing

### `docs/tests_overview.md`
- **Purpose**: Comprehensive test suite overview (1400+ lines)
- **Covers**: Test organization, per-file descriptions, fixtures, coverage, QE-backed integration tests
- **Tag**: `testing`

### `docs/testing_guide.md`
- **Purpose**: Condensed README-level testing guide
- **Covers**: Test organization, quick recipes, QE dependencies, QE-backed integration tests and the "one QE-running test per file" convention
- **Tag**: `testing`

### `tests/README.md`
- **Purpose**: Quick tests overview
- **Covers**: Test structure, running instructions, CI integration
- **Tag**: `testing`

### `extended-tests/README.md`
- **Purpose**: Extended tests overview (QE official test-suite based)
- **Covers**: Purpose, structure, usage, requirements, CI exclusion
- **Tag**: `testing`

## Supporting Documentation

### `AI_understanding.md` (root)
- **Purpose**: Comprehensive knowledge base (4500+ lines) for AI assistants
- **Covers**: Everything - architecture, schema, CLI, daemon, GUI, QE engine, analysis, snapshots, standalone, testing
- **Tag**: `meta`, `comprehensive`
- **Note**: Very detailed but overlaps with canonical docs above. Use for deep dives, but prefer canonical docs for specific topics.

### `README.md` (root)
- **Purpose**: Main entry point for the repository
- **Covers**: Project overview, installation, CLI usage, testing structure, links to detailed docs
- **Tag**: `meta`

### `docs/STRUCTURE_AND_CLI_USAGE.md`
- **Purpose**: Detailed examples and usage patterns for structure I/O and CLI
- **Covers**: Structure I/O functions, CLI examples, complete workflows
- **Tag**: `cli`, `supporting`

## Archive

Historical and refactor documents have been moved to:
- `docs/archive/` - Schema refactor plans, snapshot audits, refactoring summaries
- `tests/docs/archive/` - Test migration and refactoring docs
- `extended-tests/docs/archive/` - Extended test migration docs

These are kept for historical reference but are not canonical.

## Usage Guidelines

1. **For schema questions**: See `docs/SCHEMA.md`
2. **For API questions**: See `docs/CLI_API_REFERENCE.md` or `docs/DAEMON_API_REFERENCE.md`
3. **For architecture questions**: See `PROJECT_ARCHITECTURE.md` or `docs/GUI_ARCHITECTURE.md`
4. **For testing questions**: See `docs/testing_guide.md` or `docs/tests_overview.md`
5. **For deep dives**: See `AI_understanding.md` (but verify against canonical docs)

When updating documentation:
- Update the canonical doc first
- If `AI_understanding.md` covers the topic, update it to match
- Move outdated refactor/migration docs to `docs/archive/`
