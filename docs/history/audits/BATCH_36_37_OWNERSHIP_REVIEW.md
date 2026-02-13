# Batch 36/37 Capability Ownership Review

**Date**: 2026-02-02
**Purpose**: Analyze deleted entrypoints from Batches 36/37 for ownership correctness
**Trigger**: Review revealed that "0 daemon/CLI usage" is NOT sufficient deletion criteria

---

## Background

Batches 36 and 37 deleted 8 service_nested methods based on "0 daemon/CLI usage":

| Batch | Method | Stated Reason |
|-------|--------|---------------|
| 36 | `Analysis.list_properties` | 0 daemon/CLI usage |
| 36 | `Analysis.get_property_ref` | 0 daemon/CLI usage |
| 36 | `Analysis.load_artifact` | 0 daemon/CLI usage, "Jupyter-only" |
| 37 | `Structure.get_atoms` | 0 daemon/CLI usage, "Jupyter-only" |
| 37 | `Calculation.get_effective_params` | 0 daemon/CLI usage |
| 37 | `Engine.get_info` | 0 daemon/CLI usage |
| 37 | `Engine.list_step_types` | 0 daemon/CLI usage |
| 37 | `Engine.validate_installation` | 0 daemon/CLI usage |

**Critical finding**: `API_SLIMMING_REVIEW.md` Appendix B.2 explicitly marked 7 of these as **"Future Capability - KEEP"**.

---

## Ownership Analysis Framework

Per API Constitution, the API serves MULTIPLE consumers:
1. **Daemon** (JSON-RPC server for GUI)
2. **CLI** (command-line interface)
3. **Jupyter notebooks** (interactive Python)
4. **Agents** (LLM-driven automation)
5. **Future frontends** (web, mobile, etc.)

**Key principle**: "0 daemon/CLI usage" does NOT imply "0 capability value."

Ownership categories:
- **(i) Not an API capability** → Belongs to kernel/tools, deletion correct
- **(ii) API capability** → Restore (possibly in better form)
- **(iii) Deprecated/obsolete** → Deletion OK, but state replacement path

---

## Method-by-Method Analysis

### 1. Analysis.list_properties

**Original intent**: List available analysis property types for a calculation step.

**Who should own**: **API** - This is a discoverability capability. Agents/notebooks need to know what properties can be analyzed before calling `analyze_band`, `analyze_dos`, etc.

**Usage scenarios**:
- Agent: "What analysis types are available for this bands calculation?"
- Notebook: `svc.analysis.list_properties(calc_id, step_id)` to show available analyses

**DTO-based replacement**: Could return `list[AnalysisPropertyDTO]` with fields: `name`, `available`, `artifact_exists`, `description`

**Rollback decision**: **RESTORE** - Real capability for discoverability

---

### 2. Analysis.get_property_ref

**Original intent**: Get a reference to a specific analysis artifact (returns AnalysisRefDTO).

**Who should own**: **API** - This enables lazy loading patterns. Returns metadata/reference without loading full data.

**Usage scenarios**:
- Agent: Get artifact metadata to decide whether to load full data
- Notebook: Check if analysis has been run, get path for external tools

**DTO-based replacement**: Already returns `AnalysisRefDTO` - proper DTO boundary.

**Rollback decision**: **RESTORE** - Proper DTO-returning capability

---

### 3. Analysis.load_artifact

**Original intent**: Load full artifact data (JSON, NPZ) given an AnalysisRefDTO.

**Who should own**: **API** - This completes the lazy-loading pattern started by `get_property_ref`.

**Usage scenarios**:
- Notebook: Load band structure data for custom plotting
- Agent: Access raw numerical data for further processing

**DTO-based replacement**: Input is DTO (AnalysisRefDTO), output is dict (which may contain numpy arrays). This is acceptable for Jupyter boundary.

**Rollback decision**: **RESTORE** - Essential for artifact access pattern

---

### 4. Structure.get_atoms

**Original intent**: Get full atomic coordinates (positions, species, lattice) for a structure.

**Who should own**: **API** - Direct data access for interactive use.

**Usage scenarios**:
- Notebook: Visualize structure with custom tools
- Agent: Inspect atom positions, count atoms, check species

**DTO-based replacement**: Could be `StructureDataDTO` with fields: `positions: list[list[float]]`, `species: list[str]`, `num_atoms: int`, `lattice: list[list[float]] | None`, etc.

**Note**: This is purely a data accessor - users could also use pymatgen directly. However, requiring users to know internal file paths violates API encapsulation.

**Rollback decision**: **RESTORE** - API encapsulation for structure data access

---

### 5. Calculation.get_effective_params

**Original intent**: Get merged parameters (defaults + overrides) for all steps in a calculation.

**Who should own**: **UNCERTAIN** - This is borderline. It exposes internal parameter merging logic.

**Usage scenarios**:
- Debug: "What parameters will actually be used when I run?"
- Agent: Check effective k-points, cutoffs, etc. before running

**Concerns**:
- Complex output structure (nested dict per step)
- Internal implementation detail (how defaults merge with overrides)
- Could encourage agents to duplicate parameter logic

**Alternative**: Users can inspect `step.parameters` directly via `get_calculation` DTO.

**Rollback decision**: **KEEP DELETED** - Internal detail. Users should use `get_calculation` DTO which includes step parameters. If "effective merged parameters" is needed, it should be a DTO field on StepDTO, not a separate method.

---

### 6. Engine.get_info

**Original intent**: Get information about a specific engine (supported presets, version, executable path).

**Who should own**: **API** - Engine discoverability for frontends that need to show engine capabilities.

**Usage scenarios**:
- GUI: Show engine version and capabilities in settings
- Agent: "What presets does the QE engine support?"

**DTO-based replacement**: Could be `EngineInfoDTO` with fields: `name`, `supported_presets: list[str]`, `version: str | None`, `executable: str | None`

**Rollback decision**: **RESTORE** - Engine discoverability capability

---

### 7. Engine.list_step_types

**Original intent**: List available step types, optionally filtered by engine.

**Who should own**: **API** - Workflow discoverability. Critical for agents building calculations.

**Usage scenarios**:
- Agent: "What step types can I add to a QE calculation?"
- GUI: Populate step type dropdown
- Notebook: Discover available workflow steps

**DTO-based replacement**: Could be `list[StepTypeInfoDTO]` with fields: `name`, `engines: list[str]`, `description: str | None`

**Rollback decision**: **RESTORE** - Essential workflow discoverability

---

### 8. Engine.validate_installation

**Original intent**: Validate that an engine is correctly installed and return diagnostic info.

**Who should own**: **API** - Installation diagnostics for setup/troubleshooting.

**Usage scenarios**:
- CLI: `qv doctor` or similar health check
- GUI: Settings page showing engine status
- Agent: Check if engine is available before creating calculation

**DTO-based replacement**: Could be `EngineValidationDTO` with fields: `engine_name`, `ok: bool`, `version: str | None`, `binary: str | None`, `message: str | None`, `details: dict`, `warnings: list[str]`

**Rollback decision**: **RESTORE** - Critical diagnostic capability

---

## Summary: Rollback Decisions

| Method | Decision | Reason |
|--------|----------|--------|
| `Analysis.list_properties` | **RESTORE** | Discoverability capability |
| `Analysis.get_property_ref` | **RESTORE** | DTO-returning artifact metadata |
| `Analysis.load_artifact` | **RESTORE** | Artifact access pattern |
| `Structure.get_atoms` | **RESTORE** | API-encapsulated data access |
| `Calculation.get_effective_params` | **KEEP DELETED** | Internal detail, use get_calculation DTO |
| `Engine.get_info` | **RESTORE** | Engine discoverability |
| `Engine.list_step_types` | **RESTORE** | Workflow discoverability |
| `Engine.validate_installation` | **RESTORE** | Diagnostic capability |

**Restore count**: 7
**Keep deleted**: 1

---

## Restoration Plan

**Batch 38**: Restore 7 deleted methods

1. Revert the deletions from service.py
2. Revert the test deletions
3. Update worklog with:
   - Ownership review reference
   - Audit before/after (expect +7 service_nested)
   - Lesson learned: "0 daemon/CLI usage" ≠ "0 capability value"

**Future improvement**: Consider upgrading return types to proper DTOs:
- `Engine.get_info` → `EngineInfoDTO`
- `Engine.list_step_types` → `list[StepTypeInfoDTO]`
- `Engine.validate_installation` → `EngineValidationDTO`
- `Structure.get_atoms` → `StructureDataDTO`

This would strengthen the DTO boundary without adding surface (DTOs are already counted).

---

## Lesson Learned

**Deletion criteria must include capability value, not just usage counts.**

Correct deletion criteria:
1. Zero usage across ALL consumers (daemon + CLI + tests + notebooks + agents)
2. No future capability value documented
3. Not marked as "Future Capability" in review documents
4. Internal implementation detail that leaks abstraction

"0 daemon/CLI usage" alone is INSUFFICIENT.

---

**End of Ownership Review**
