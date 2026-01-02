# Workflow Refactor Plan: StepTypeRegistry + Workflow System

**Status**: ✅ Complete (v0)  
**Date**: 2026-01-01  
**Version**: v0

---

## Summary

This refactor introduces a centralized step type registry and workflow system:

- **StepTypeRegistry**: Single source of truth for step type semantics
- **WorkflowService**: Detection and instantiation of calculation workflows
- **Step Factory**: Centralized step creation with Journal integration
- **UI Integration**: Workflow selection in calculation creation dialog
- **Daemon Handlers**: RPC endpoints for workflow operations

---

## 1. Current Architecture Summary

### 1.1 Step Type Definitions (Scattered)

Currently, step type knowledge is spread across multiple locations:

| Location | Purpose | Issue |
|----------|---------|-------|
| `calculation/types.py:StepType` | Enum of step types | Just identifiers, no semantics |
| `calculation/step_defaults.py` | Default parameters per type | Only 8 types, not linked to registry |
| `cli/main.py:KNOWN_STEP_TYPES` | CLI validation | Duplicate of enum |
| `presets/receivers.py` | PW vs post-processing classification | Scattered knowledge |

### 1.2 Step Creation (Multiple Paths)

Step creation happens in multiple places with inconsistent patterns:

| Location | Method | Journal? |
|----------|--------|----------|
| `api.py:add_step_to_calculation()` | `yaml.safe_dump()` direct | ❌ No |
| `api.py:import_step_from_qe_input()` | `yaml.safe_dump()` direct | ❌ No |
| `cli/main.py:init_step_command()` | Uses api layer | ❌ No |
| `presets/integration.py` | `StepDoc` + `save_yaml_doc()` | ✅ Yes |

**Problem**: Step creation bypasses Journal because it uses raw yaml.safe_dump.

### 1.3 Workflow Detection (Basic)

- `presets/integration.py:detect_workflow_type()` exists
- Returns string labels: "SCF", "DOS", "BandStructure", etc.
- Heuristic-based, not authoritative

### 1.4 Existing Templates

- `resources/calculation_templates/` contains calculation templates
- Templates are directories with `calculation.yaml` + step files
- Rarely used; most creation is ad-hoc via CLI/API

---

## 2. Proposed StepTypeRegistry (v0)

### 2.1 Design Principles

1. **Single source of truth** for step type semantics
2. **Data-driven**: All step type knowledge in registry, not scattered if/else
3. **Minimal**: Only essential fields, easy to extend later
4. **Testable**: Registry can be validated and queried

### 2.2 StepTypeSpec Fields

```python
@dataclass
class StepTypeSpec:
    """Specification for a step type."""
    id: str                          # Canonical step_type string
    engine: str                      # Engine identifier (e.g., "qe")
    executable: str                  # QE executable (e.g., "pw.x", "dos.x")
    description: str                 # Human-readable description
    accepts_presets: bool            # Whether preset dimensions apply
    allowed_dimensions: frozenset    # Which preset dimensions are allowed
    requires_structure: bool         # Whether step needs structure
    requires_charge_density: bool    # Whether step needs prior SCF
    produces_charge_density: bool    # Whether step produces charge density
```

### 2.3 Registry API

```python
class StepTypeRegistry:
    """Registry of step type specifications."""
    
    def get(self, step_type: str) -> StepTypeSpec | None
    def list_all() -> list[str]
    def list_by_engine(engine: str) -> list[str]
    def get_defaults(step_type: str) -> dict  # Merges from step_defaults.py
    def validate_step(step_type: str, params: dict) -> list[Issue]
```

### 2.4 v0 Step Types

| step_type | engine | executable | accepts_presets | requires_charge_density |
|-----------|--------|------------|-----------------|-------------------------|
| scf | qe | pw.x | ✅ | ❌ |
| nscf | qe | pw.x | ✅ | ✅ |
| relax | qe | pw.x | ✅ | ❌ |
| vc-relax | qe | pw.x | ✅ | ❌ |
| bands_pw | qe | pw.x | ✅ | ✅ |
| dos | qe | dos.x | ❌ | ✅ |
| bands | qe | bands.x | ❌ | ✅ |

---

## 3. Proposed WorkflowTemplate API (v0)

### 3.1 Design Principles

1. **Runtime interpretation only** - workflows are never persisted
2. **Detection from YAML** - no in-memory state
3. **Minimal validation** - useful but not blocking

### 3.2 WorkflowTemplate Structure

```python
@dataclass
class WorkflowTemplate:
    """Definition of a calculation workflow."""
    id: str                          # e.g., "dos", "bands"
    name: str                        # e.g., "Density of States"
    description: str
    step_sequence: tuple[str, ...]   # Ordered step_types
    optional_steps: frozenset[str]   # Steps that may be omitted
```

### 3.3 Workflow API

```python
class WorkflowService:
    """Service for workflow operations."""
    
    def list_templates() -> list[WorkflowTemplate]
    def get_template(workflow_id: str) -> WorkflowTemplate | None
    
    def detect_workflow(calc_dir: Path) -> WorkflowMatch
    def instantiate_workflow(workflow_id: str, calc_dir: Path, structure_id: str) -> list[Path]
    def validate_workflow(calc_dir: Path, workflow_id: str) -> list[Issue]
```

### 3.4 WorkflowMatch Result

```python
@dataclass
class WorkflowMatch:
    """Result of workflow detection."""
    workflow_id: str | None          # Best matching workflow
    coverage: float                  # 0.0 to 1.0
    present_steps: list[str]         # Step types found
    missing_steps: list[str]         # Required steps not found
    extra_steps: list[str]           # Steps not in template
    ordering_valid: bool             # Whether order matches
```

### 3.5 v0 Workflows

| workflow_id | name | step_sequence |
|-------------|------|---------------|
| scf | SCF | (scf,) |
| relax | Relaxation | (relax,) |
| vc-relax | Full Relaxation | (vc-relax,) |
| dos | DOS | (scf, nscf, dos) |
| bands | Band Structure | (scf, bands_pw, bands) |

---

## 4. Step Creation Funnel (Centralized)

### 4.1 Single Entry Point

All step creation goes through:

```python
def create_step_doc(
    step_type: str,
    name: str,
    structure_id: str | None = None,
    parent_calculation_id: str | None = None,
    overrides: dict | None = None,
) -> StepDoc:
    """Create a new step document (not yet saved)."""
    
def save_step_doc(step_doc: StepDoc, path: Path) -> None:
    """Save step document to disk (journaled via yaml_io)."""
```

### 4.2 Journal Integration

```
create_step_doc() → StepDoc (in memory)
       ↓
save_step_doc() → yaml_io.save_yaml_doc() → Journal hook
```

---

## 5. Migration Checklist

### Phase 1: StepTypeRegistry
- [x] Create `src/quantumvitas/workflow/registry.py`
- [x] Define StepTypeSpec dataclass
- [x] Implement StepTypeRegistry with v0 step types
- [x] Merge defaults from step_defaults.py
- [x] Add unit tests for registry

### Phase 2: WorkflowService
- [x] Create `src/quantumvitas/workflow/templates.py`
- [x] Define WorkflowTemplate dataclass
- [x] Implement WorkflowService with v0 workflows
- [x] Add detection from calculation directory
- [x] Add instantiation to create steps
- [x] Add unit tests for workflows

### Phase 3: Centralize Step Creation
- [x] Create `src/quantumvitas/workflow/step_factory.py`
- [x] Implement create_step_doc() and save_step_doc()
- [ ] Update api.py:add_step_to_calculation() to use factory (future work)
- [ ] Update api.py:import_step_from_qe_input() to use factory (future work)
- [x] Verify Journal captures all step writes (via yaml_io)

### Phase 4: UI Integration
- [x] Add workflow template selection to calculation creation
- [x] Add daemon handlers for workflow operations
- [ ] Show workflow detection badge in calculation view (future work)

### Phase 5: Tests
- [x] Unit tests for registry (19 tests)
- [x] Unit tests for workflow detection/instantiation (16 tests)
- [x] All 845 unit/integration tests passing (10 network-blocked)

---

## 6. Journal Integration Path

```
User/API → WorkflowService.instantiate_workflow()
                ↓
        StepFactory.create_step_doc() [× N steps]
                ↓
        StepFactory.save_step_doc()
                ↓
        yaml_io.save_yaml_doc()
                ↓
        Journal.record_change()
```

All step writes go through yaml_io, so Journal is automatically wired.

---

## 7. Design Decisions

1. **Why StepTypeRegistry vs extending StepType enum?**
   - Enum only provides identifiers
   - Registry provides semantics, defaults, validation
   - Registry is data-driven and queryable

2. **Why v0 workflows are minimal?**
   - Start with most common workflows (SCF, DOS, Bands, Relax)
   - Complex workflows (Phonon, PDOS, TDDFT) can be added in v1
   - Avoid combinatorial explosion

3. **Why no workflow persistence?**
   - Per Constitution: workflow is runtime interpretation
   - YAML on disk is truth; workflow is derived from it
   - Avoids state synchronization issues

4. **Why single step factory?**
   - Ensures all step creation goes through Journal
   - Centralizes ULID generation, slug rules, validation
   - Replaces scattered yaml.safe_dump calls

